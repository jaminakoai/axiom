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
