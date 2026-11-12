# P1-03c — `axiom-scan` v0.2 + DFIR odaklı GitHub hazırlığı

**Tarih:** 12 Kasım 2026
**Kapsam:** küçük ve doğrulanmış ürün geliştirmesi + TR/EN README + yerel GitHub hazırlığı
**Durum:** tamamlandı (push yok, uzak bağlama yok)

---

## 1. Başlangıç durumu

İncelenen kaynaklar:

| Belge / kod | Bulgu |
|---|---|
| `TODO.md` | 100 `[x]`, 11 açık madde; son doğrulanmış paket 1017 test |
| `README.md` / `README.en.md` | Dil odaklı tanıtım; DFIR ürün yönü ve "proje durumu/yol haritası" bölümü yok |
| `CHANGELOG.md` | P2-19b / sonsuz döngü düzeltmelerine kadar güncel |
| `docs/reports/` | 42 rapor + dizin |
| `examples/21_axiom_scan.ax` | v0.1: JSON çıktı var; **şema sürümü ve hedef hash'i yok**, bulgu exit kodunu değiştirmiyor |
| `examples/22_dfir_triage.ax` | süreç/port/bütünlük/Sigma → tek JSON; çalışıyor |
| `.github/workflows/ci.yml` | mevcut; README rozeti bu dosyaya işaret ediyor |
| `.gitignore` | Python/üretim artıkları var; **`bin/axiomc` (240 KB ELF) ignore edilmiyordu**; ayrıca `target/` deseni `std/target/wasm.ax` kaynağını da dışlıyordu |
| `LICENSE` | MIT, 2026 Axiom Language Contributors — README ile tutarlı |

**Ölçülen davranış (v0.1, düzeltme öncesi):**

```
$ ./axiom-scan scan dirty.txt --rules r.yar
{"ok":true,"target":"dirty.txt","scanned_bytes":18,"matches":[...]}
$ echo $?
0
```

Bulgu varken dahi exit 0; raporda taranan dosyanın SHA-256'sı yok. CI kapısı
olarak kullanılamıyor, "hangi baytlar tarandı" kanıtlanamıyor.

---

## 2. Seçilen geliştirme

**Sorun:** DFIR/CI kullanımı için rapor makine tarafından güvenilir biçimde
ayrıştırılamıyor ve bulgu çıkış koduna yansımıyor.

**Çözüm (katkısal, kırıcı değil):**

1. Rapora `schema_version`, `tool`, `tool_version`, `rules_count` eklendi.
2. `scan` raporuna `target_sha256` (tüm dosya) ve `match_count` eklendi;
   `scanned_bytes` karakter değil **bayt** oldu.
3. `pcap` raporuna `pcap_sha256` ve `match_count` eklendi.
4. `--fail-on-match` **opt-in** bayrağı: bulgu varsa exit 10, yoksa 0.
   Bayraksız davranış aynen korunur (exit 0).
5. Hata yolları da şemalı JSON döndürür: `{"ok":false,"error":...}` + exit 1.

**Etkilenen dosyalar:** `examples/21_axiom_scan.ax`, `tests/test_axiom_scan.py`
(yeni regresyonlar), `README.md`, `README.en.md`, `TODO.md`, `CHANGELOG.md`,
`.gitignore`, `compiler/main.ax` (makineye özel yol), 4 test dosyası (sabit yol).

---

## 3. Bulunan gerçek hata: `--fail-on-match` neden çalışmıyordu?

İlk denemede bayrak exit kodunu değiştirmedi. Kök neden ürün kodunda:

```python
# axiom/codegen_c.py — main köprüsü
elif main_shape is not None:
    ...
    self.emit_line("return 0;")   # ok değeri atılıyor
```

`fn main() -> Result<int, str>` için köprü, `ok` durumunda **her zaman 0**
döndürüyordu. Bu bilinçli ve testle kilitlenmiş bir davranıştır
(`tests/test_stdlib_result.py::test_main_returning_result_maps_ok_to_exit_0`,
`result_ok<int>(99)` → exit 0). Kırıcı değişiklik yapmamak için dil semantiği
değiştirilmedi; araç `main -> int` kullanacak şekilde düzenlendi:

```axiom
fn _dispatch() -> Result<int, str> { ... }   // eski main gövdesi

fn main() -> int {
    let r = _dispatch()
    if not r.is_ok {
        return _fail(r.error)      // şemalı JSON + exit 1
    }
    return r.value                 // 0 veya 10
}
```

Bu, "özel çıkış kodu için `int` main kullanın" kuralının araç tarafındaki
uygulamasıdır; dilin mevcut davranışı ve testi korunur.

---

## 4. Doğrulama (gerçek çıktı)

```
$ ./axiom-scan scan clean.txt --rules r.yar
... "match_count":0 ...                       exit=0
$ ./axiom-scan scan dirty.txt --rules r.yar
... "match_count":1 ...                       exit=0
$ ./axiom-scan scan dirty.txt --rules r.yar --fail-on-match
... "match_count":1 ...                       exit=10
$ ./axiom-scan scan clean.txt --rules r.yar --fail-on-match
... "match_count":0 ...                       exit=0
$ ./axiom-scan scan yok.txt --rules r.yar
{"schema_version":"1","tool":"axiom-scan","tool_version":"0.2.0",
 "ok":false,"error":"dosya bulunamadi: yok.txt"}          exit=1
```

`target_sha256` bağımsız `sha256sum` ile birebir:

```
21f10114c2932724770202eff83c9109322c2d605efd0e9e6c2a157dd0866551  dirty.txt
```

**Yeni regresyon testleri** (`tests/test_axiom_scan.py`, 5 test):

1. `test_scan_report_schema_and_target_hash` — şema alanları + `hashlib.sha256`
   eşitliği + bayt cinsinden `scanned_bytes`.
2. `test_rules_and_pcap_reports_carry_schema` — `rules` ve `pcap` de şemalı;
   `pcap_sha256` dosya hash'i ile aynı.
3. `test_fail_on_match_is_opt_in` — bayraksız 0, bayrakla 10, temizde 0.
4. `test_error_path_is_structured_json` — exit 1 + `ok:false` + `schema_version`.
5. `test_fail_on_match_llvm_parity` — C ve LLVM aynı exit kodunu verir.

---

## 5. README (TR + EN)

İki ayrı dosya korundu (`README.md`, `README.en.md`); her iki dilde de
birbirine bağlantı var. Gerekçe: GitHub'da dil rozetleri/bağlantıları daha
kolay bulunur ve mevcut yapı bozulmaz.

Eklenen bölümler (iki dilde tutarlı):

- **"Axiom bugün ne işe yarar?"** — çevrimdışı DFIR/güvenlik kanıtı triyajı,
  girdi → analiz → çıktı tablosu, hedef kullanıcı, dürüst sınırlar.
- **`axiom-scan` v0.2** — gerçek komutlar ve gerçek JSON çıktı, çıkış kodları.
- **Testleri çalıştırma** — komut, 900 s timeout, wine notu, son koşu sayısı.
- **Proje durumu ve yol haritası** — ✅ tamamlanan / 🟡 kısmi / ⬜ planlanan;
  her madde kod/test durumuyla; güncelleme yöntemi açık.
- **Katkı** — CONTRIBUTING + SECURITY bağlantıları.

Dürüstlük düzeltmeleri:

- Self-hosted derleyici "yalnız 01–04" ifadesi **21/21** olarak güncellendi
  (P2-18f ile doğrulanmış durum).
- "50+ modül" → **52 modül / 385 fonksiyon**.
- Rapor sayısı 40 → **43** (bu rapor dahil).
- Makineye özel `/home/mimar/Desktop/axiom` yolu README ve rehberlerden
  çıkarıldı → `/path/to/axiom`.

---

## 6. GitHub yerel hazırlığı

- `.gitignore`'a `/bin/axiomc` ve `/bin/*.bin` eklendi (derlenmiş 240 KB ELF
  depoya girmemeli; `bin/axiom`, `bin/axpm`, `bin/axiom-lsp` kaynak script
  olarak kalır).
- **Kritik `.gitignore` hatası bulundu ve düzeltildi:** `target/` deseni kök
  derleme çıktısını değil, **her** `target` dizinini dışlıyordu; bu yüzden
  `std/target/wasm.ax` depoya girmeyecekti (std 51/52 dosya). Desen `/target/`,
  `/build/`, `/dist/` olarak köke sabitlendi. Doğrulama: `git add -A -n`
  sayısı 282 → **283** ve `std/target/wasm.ax` listede.
- `compiler/main.ax` içindeki makineye özel son-çare yol kaldırıldı; kök
  `AXIOM_HOME` / `PWD` üzerinden bulunur.
- 4 testteki sabit `/home/mimar/...` yolu `Path(__file__).resolve().parent.parent`
  tabanlı hale getirildi (başka makinede de çalışır).
- Raporlar ve tarihsel TODO'lardaki kullanıcı adı `~/Desktop/...` olarak
  genelleştirildi.
- Lisans: `LICENSE` MIT (2026 Axiom Language Contributors) — README ile aynı.
- **Yapılmayanlar (talimat gereği):** `git init`, commit, uzak bağlama, push.

---

## 7. Riskler / kalan işler

| Risk | Durum |
|---|---|
| Gerçek Windows/macOS CI yok | Bilinen sınır; wine ile doğrulama var |
| YARA alt kümesi | Tam YARA değil; README'de açıkça yazıldı |
| PCAP akış birleştirme yok | Bilinçli sınır; README'de yazıldı |
| NUL'lu dosyada metin tarama kesilir | `target_sha256` tüm dosyayı kapsar; sınır belgelendi |
| Yayınlanmış paket yok | Registry altyapısı hazır |
| `axiom-scan` "kanıtlanmış üretim aracı" değil | Alfa; README'de belirtildi |

---

## 8. Test sonucu (tam paket)

```
$ python3 -m pytest -q --no-header -p no:cacheprovider
1022 passed in 921.59s (0:15:21)
EXIT=0
```

- 0 failed, 0 skipped.
- Önceki tam koşu 1017 → **+5** (yeni `axiom-scan` regresyonları).
- Ortam: Linux x86_64, clang, wine mevcut, `/tmp` 608 MB / 3.9 GB.
- Koşu sonrası: `/tmp/axiom-wine-*` kalıntısı **0**, yüksek CPU'lu süreç **0**.

---

## 9. Yayın öncesi inceleme düzeltmeleri (aynı gün)

Dış inceleme 5 noktayı işaret etti; hepsi düzeltildi:

| # | Bulgu | Yapılan |
|---|---|---|
| 1 | Rozetler sabit metin ("CI success", "1022 Passed") | **CI rozeti gerçek workflow'a bağlandı** (`.../actions/workflows/ci.yml/badge.svg`). **Tests rozeti** "yerel koşu" olarak etiketlendi ve tarih/komut/sonuç belgelenen bölüme bağlandı. Sahte "success" rozeti kaldırıldı. |
| 2 | Dil ile DFIR araçları iki ayrı yön gibi yarışıyor | **"Axiom nedir?"** bölümü eklendi: ana ürün dildir, güvenlik araçları bu dilin **amiral gemisi uygulamalarıdır**. DFIR bölümü "Bu dille yazılmış araçlar" olarak yeniden adlandırıldı. |
| 3 | Pazarlama iddiaları kanıtsız | Slogan ölçüme dayalı hâle getirildi (C `-O3`'ün 1,5–6,3× yavaşı, Python'un 6,6–29,7× hızlısı). **"İddialar ve kanıtlar"** tablosu eklendi: 6 iddia, gerçek durum, kanıt. "Sıfır bilişsel yük" → "borrow checker yok, sahiplik var". "Python kadar zarif" kaldırıldı. Karşılaştırma tablosundaki yıldızların ölçüm olmadığı yazıldı. |
| 4 | Test sayısı hangi koşudan, hangi hata durumuyla? | **"Son doğrulanmış koşu"**: 12 Kasım 2026, `python3 -m pytest -q --no-header -p no:cacheprovider`, 1022 geçti / 0 başarısız / 0 atlandı (921,59 s), ortam. Ayrıca **"CI durumu (dürüst)"**: 20 başarısız / 919 geçti / 83 atlandı, 4 kök neden. Sandbox koşusu (951/57/2) raporda linklendi. |
| 5 | Örnek numaraları atlıyor (11 → 13 → 12), iki kez "6." | 1–14 **sıralı** yeniden numaralandırıldı; kırık `#13` bağlantısı (`taraması`/`taramasi` harf hatası) düzeltildi. Doğrulama: TR ve EN'de **kırık bağlantı 0**. |

### Bu sırada bulunan gerçek hata (ürün)

**LLVM `main() -> Result<int,str>` köprüsü bozuk.** Üretilen IR:

```llvm
define %struct.ax_Result_int_str @ax_main() { ... }
define i32 @main(i32 %argc, i8** %argv) {
  call void @axiom_cli_init_args(i32 %argc, i8** %argv)
  call void @ax_main()        ; <-- struct dönen fonksiyon void çağrılıyor
  ret i32 0
}
```

- clang 21 (yerel) kabul ediyor ve **Err bilgisini sessizce düşürüyor** →
  `main() -> Result` ile yazılmış programlar LLVM'de hatada **exit 0** verebilir.
- clang 14 (ubuntu-22.04 CI) bunu **sert hata** olarak reddediyor:
  `'@ax_main' defined with type '%struct.ax_Result_int_str ()*' but expected 'void ()*'`.
- C arka ucunda aynı senaryo doğru çalışıyor (Err → stderr + exit 1).

Bu, "iki arka uç eşit" ilkesinin ihlalidir ve **bu turda düzeltilmedi**;
CI'daki 2 test hatasının kök nedenidir. Düzeltme önerisi: `main` köprüsünü
`Result` yapısını `sret` ile çağırıp `is_ok` kontrolü yapacak şekilde üret,
Err'de `error` alanını stderr'e yaz ve 1 döndür.

### Doğrulama

```
$ python3 -m pytest -q --no-header -p no:cacheprovider
1022 passed in 921.59s (0:15:21)      # yerel, 12 Kasım 2026
```

CI (gerçek, son iki koşu): `20 failed / 919 passed / 83 skipped`
(run 43212627639, 43219236120).

---

## 10. CI kök nedenlerinin giderilmesi (aynı gün, devam)

4 kök nedenin hepsi düzeltildi; her biri için test kanıtı var.

### 10.1 LLVM `main() -> Result` köprüsü — **gerçek ürün hatası**

**Belirti (CI):** `'@ax_main' defined with type '%struct.ax_Result_int_str ()*'
but expected 'void ()*'`.

**Gerçek etki (yerelde ölçüldü):** clang 21 bu IR'yi kabul ediyor ve **Err
bilgisini sessizce düşürüyor**:

```
$ ./mt.bin            # main -> Result, fail(7)? ile hata
calisiyor
exit=0                # <-- hata yutuldu (yanlış)
```

C arka ucu aynı programda `[AXIOM HATA] patladi: 7` + `exit 1` veriyor.

**Düzeltme:** `axiom/codegen_llvm.py`:
- `_struct_main_bridge_is_result()` — struct tipinde `is_ok`/`error` alanı var mı?
- `_emit_struct_main_bridge()` — `call %struct... @ax_main()`, `extractvalue`
  ile `is_ok`, Err'de `extractvalue` ile `error` → `axiom_eprint_error` → `ret 1`.
- `axiom/runtime.h` — yeni `axiom_eprint_error()` (stderr + `[AXIOM HATA]`
  öneki), C köprüsüyle aynı biçim.

**Doğrulama (gerçek çıktı):**

```
$ ./mt.bin ; echo exit=$?        # LLVM
[AXIOM HATA] patladi: 7
calisiyor
exit=1
$ ./mt.c.bin ; echo exit=$?      # C
[AXIOM HATA] patladi: 7
calisiyor
exit=1
```

**Regresyon testi:** `tests/test_llvm_main_bridge.py` (6 test). Düzeltme geçici
kaldırıldığında **3 test kırmızı** oluyor ve LLVM `exit 0` veriyor (kanıtlandı).

### 10.2 `bin/axiomc` sırası (13 test)

CI, `pytest`'i `make bootstrap`'tan önce koşuyordu; ikili depoda tutulmadığı
için `test_self_hosted.py` + `test_negative_security.py` dosyayı bulamıyordu.

**Düzeltme:** `.github/workflows/ci.yml` — `test` ve `sanitizers` işlerinde
bootstrap artık testlerden **önce**.

### 10.3 Unicode sürüm testi (2 test)

Test, tablo sürümünü **çalışan yorumlayıcının** `unicodedata` sürümüyle
karşılaştırıyordu. Tablo 15.1.0, CI Python 3.10/3.11 ise Unicode 14.0.0.

**Düzeltme (skip değil, sürümden bağımsızlaştırma):**
- `tools/gen_unicode_tables.py`: `PINNED_UCD_VERSION = "15.1.0"`. Yorumlayıcı
  sürümü uyuşmazsa üretici **durur** (`ALLOW_UCD_MISMATCH=1` bilinçli kaçış).
  Böylece tablo farklı UCD'den sessizce üretilemez.
- `tools/unicode_corpus.py`: korpüs tek kaynak (test + üretici paylaşır).
- `tools/gen_unicode_conformance.py` + `tests/data/unicode_conformance.json`:
  beklenen NFC/NFD değerleri **altın dosyada** sabit.
- Testler artık altın dosyaya ve sabitlenmiş sürüme bakar; yorumlayıcı
  sürümünden bağımsız. Ayrıca `test_golden_corpus_matches_test_corpus` kayma
  koruması ekler.

### 10.4 `readelf` uyarıları (2 test)

Yeni clang (DWARF5 formları) + eski binutils (Ubuntu 22.04, 2.38) readelf'i
uyarıyor ve `exit 1` dönüyordu.

**Düzeltme:** test artık çıkış koduna değil **aranan içeriğe** bakıyor
(`_readelf_dump`). Yalnızca bilinen araç-zinciri uyarıları tolere edilir
(`Unrecognized form`, `.debug_addr too big`, `abbreviation number`, ...);
başka bir hata hâlâ testi düşürür. Yani gevşetme değil, doğru sözleşme.

### 10.5 Biçimlendirme işi

`fmt` işi `z3` kurmuyordu; `bin/axiom` → `cli.py` → `import z3` düşüyordu.
`pip install -e ".[dev]"` eklendi.

---

## 11. İkinci CI koşusu ve kalan iki gerçek hata

İlk düzeltme turundan sonra CI (`43249869041`): `fmt` ✅, `sanitizers` ✅,
test işlerinde 2–3 başarısız kaldı. İki yeni gerçek hata ortaya çıktı.

### 11.1 Python 3.10'da paket bağımlılıkları sessizce çözülmüyordu

**Belirti (CI, Python 3.10):**

```
axiom.resolver.ModuleError: İçe aktarılacak modül dosyası bulunamadı: 'str_tools'
  (Aranan konum: .../app_consumer/src/str_tools)
```

**Kök neden:** `axiom/resolver.py` içinde

```python
try:
    import tomllib                      # Python 3.10'da YOK
    toml_data = tomllib.loads(...)
except Exception:
    pass                                # <-- sessiz yutma
```

Python 3.10'da `tomllib` stdlib'de yoktur; istisna yutulunca `dependencies`
hiç okunmuyor, dolayısıyla **path/git bağımlılıkları çözümlenmiyordu**.
`pyproject.toml` ise `requires-python = ">=3.10"` diyor — yani desteklenen bir
sürümde paket sistemi sessizce çalışmıyordu.

**Düzeltme:**
- `resolver.py` artık `axiom.package_manager.parse_toml` kullanır (tomli yedeği var).
- `pyproject.toml`: `tomli>=2.0; python_version < '3.11'` bağımlılığı eklendi.
- `parse_toml` yedek ayrıştırıcısı **inline tabloları** (`{ path = "..." }`)
  artık dict olarak ayrıştırır; tomli kurulu olmasa bile path/git bağımlılıkları
  okunur.
- Regresyon: `test_parse_toml_handles_inline_tables_without_tomllib`.

### 11.2 DWARF: `Bogus end-of-siblings` — araç hatası mı, bizim hatamız mı?

İlk turda `_readelf_dump` yalnızca **bilinen** uyarıları tolere ediyordu; CI'da
`Bogus end-of-siblings marker detected` çıktı ve test düştü. Bunu körü körüne
tolere listesine eklemek "testi yeşile boyamak" olurdu, o yüzden araştırıldı.

**Kanıtlar (sırayla):**

1. IR'de metadata **ID çakışması yok**, tanımsız referans yok:
   `toplam metadata: 41, çakışan id: {}, tanımsız referans: []`.
2. Aynı ikili **pyelftools** ile bağımsız ayrıştırıldı: 2 CU, `DW_TAG_subprogram`
   ve `DW_TAG_variable` DIE'leri (`product`, `result`) doğru okunuyor.
3. Yerel binutils **2.46** aynı ikilide **hiç uyarı vermiyor** (exit 0, stderr boş).
4. Arama sonucu: bu uyarı **binutils bug 28981** olarak kayıtlı; readelf'in
   clang ürettiği DWARF'ı okuyuşundaki bir kusur. Buildroot, host-rustc
   ikililerinde aynı uyarıları görüp readelf stderr'ini `/dev/null`'a yönlendiriyor.

**Karar:** testi readelf'in **çıkış koduna** bağlamak yanlıştı (araç sürümüne
bağlı). Yeni sözleşme:

1. `.debug_line` çıktısında kaynak dosya adı **bulunmalı**.
2. `.debug_info` çıktısında `DW_TAG_variable` + değişken adları **bulunmalı**.
3. **Bağımsız yapısal doğrulama:** `tests/test_llvm_dwarf.py::test_dwarf_structure_is_valid_via_independent_parser`
   pyelftools ile DIE ağacını gezer; subprogram, yerel değişkenler ve `.ax`
   kaynak adı doğrulanır (`pyelftools` dev bağımlılığına eklendi).
4. readelf hiç çıktı üretemezse test yine düşer.

Yani gevşetme değil: **doğru aracı doğru iş için** kullanmak + bağımsız kanıt.

### 11.3 Doğrulama

```
$ python3 -m pytest -q tests/test_package_manager.py tests/test_llvm_dwarf.py \
                        tests/test_llvm_main_bridge.py -p no:cacheprovider
25 passed
$ make fmt-check
✓ Biçimlendirme geçerli
```
