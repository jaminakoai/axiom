# Axiom (λx) — TEK DOĞRULUK KAYNAĞI (TODO / PLAN)

> **Bu dosya, projenin tek geçerli yol haritasıdır.**
> Diğer tüm plan dosyaları (`MASTER_TODO.md`, `LIBRARIES_TODO.md`,
> `GLOBAL_LANGUAGE_ROADMAP.md`, `AUDIT_REMEDIATION_TODO.md`, `REMEDIATION_TODO_2026-11-05.md`)
> **tarihsel kayıttır**; çelişki varsa **bu dosya geçerlidir**.
> Eski `TODO.md` içeriği 2026-11-07'de bu dosyayla değiştirilmiştir.

| Alan | Değer |
|---|---|
| Proje | Axiom (λx) — contract-driven, native-compiled systems language |
| Sürüm | `v0.5.0-alpha` |
| Son güncelleme | 2026-11-12 |
| Aşama | **Faz 1 — Güvenlik araçları odaklı olgunlaşma** |
| Test (yerel) | 1031 geçiyor / 1031 (12 Kasım 2026, `pytest -q`) |
| CI (GitHub Actions) | 4 kök neden giderildi; **doğrulama koşusu bekleniyor** (ayrıntı: `docs/reports/P1-03c-axiom-scan-v02-dfir-readiness-2026-11-12.md` §9–§10) |

---

## 0. AI AJANLARI İÇİN OKUMA TALİMATI

Bu belge makine tarafından okunacak şekilde yazıldı. Kurallar:

1. **Durum işaretleri:**
   - `[x]` tamamlandı ve doğrulandı
   - `[~]` kısmi — kabul kriterlerinin **hepsi** sağlanmadı
   - `[ ]` yapılmadı
   - `[!]` engelleyici (blocker) — başka iş buna bağlı
2. **Bir görevi `[x]` yapmak için:** "Kabul" satırındaki **her** madde çalıştırılıp doğrulanmalı. Kod yazmak yetmez; test/komut kanıtı gerekir.
3. **Yeni görev eklerken** ID şemasını koru: `P<faz>-<sıra>` (ör. `P1-03`).
4. **Görev kapatırken** `CHANGELOG.md`'ye tek satır yaz ve test sayısını güncelle.
5. **Asla** "çalışıyor" yazma; **ne komutla, ne çıktıyla** doğrulandığını yaz.
6. **Ölçülmemiş iddia yasak.** "Hızlı", "güvenli", "tam" gibi sıfatlar ancak benchmark/test referansıyla kullanılabilir.

### Raporlar — BAĞLAYICI KURAL

**Her turun raporu `docs/reports/` altına yazılır.** Masaüstüne, `/tmp`'ye veya
başka bir yere rapor yazılmaz; orada bulunan eski raporlar bu klasöre taşınmıştır.

| Kural | Ayrıntı |
|---|---|
| Konum | `docs/reports/<GÖREV>-<kısa-ad>.md` (örn. `P2-19-platform-portability.md`) |
| Dizin | Yeni rapor eklenince `docs/reports/README.md` içindeki tarihsel listeye satır eklenir |
| İçerik | (1) ne yapıldı, (2) bulunan **gerçek** hatalar, (3) doğrulama komutları + çıktıları, (4) dürüst sınırlar, (5) sıradaki iş |
| Yasak | Ölçülmemiş iddia; "çalışıyor" yazıp komut/çıktı vermemek |

Güncel dizin: [`docs/reports/README.md`](docs/reports/README.md)

### Mevcut doğrulanmış durum (ajan bunu başlangıç kabul etsin)

| Metrik | Değer | Doğrulama komutu |
|---|---|---|
| Test (yerel) | 1031 geçiyor (skip yok) | `python3 -m pytest -q` |
| Redteam testleri | 17 (varsayılan; `AXIOM_SKIP_REDTEAM=1` ile atlanır) | `... tests/test_redteam_*.py` |
| Stdlib | 52 dosya / 385 fonksiyon / 3.946 satır | `find std -name '*.ax' \| wc -l` |
| Örnek | 21 | `ls examples/*.ax \| wc -l` |
| C backend örnek | 21/21 | `for f in examples/*.ax; do axiom build "$f"; done` |
| LLVM backend örnek | 21/21 | `... --backend=llvm` |
| Self-hosted (`bin/axiomc`) | **21/21** ✅ | `./bin/axiomc build examples/$f.ax` |
| Paket kayıt defteri | **v1 var** (ed25519, semver, transitive) | `tests/test_registry.py` |
| Windows desteği | **21/21 derleniyor + wine'da çalışıyor** | `axiom build --target windows` + `wine` |
| Doküman dili | TR + EN (tam) | `docs/en/TUTORIAL.md` |
| LSP | 10 metod (refs, rename, format, semantic tokens, signature help) | `tests/test_lsp_full_features.py` |
| API dokümanı | `axiom doc` → `docs/api/` | `axiom doc std/` |

---

## 1. NEREDEYİZ — dürüst durum

### 1.1 Güçlü yanlar (gerçek, testli)

- **Derleyici hattı eksiksiz:** lexer → parser → resolver → checker → prover → codegen (C99 + LLVM).
- **Sözleşmeli doğrulama çalışıyor:** `requires`/`ensures`/`verify` + Z3 SMT. Bu, Rust/C/Go/Python'da **yok**.
- **İki arka uç eşit:** `defer`, `?`, string/dizi kapsam temizliği, DWARF — C ve LLVM'de aynı sonuç.
- **Hata modeli modern:** `Result<T,E>` + `?`, `defer` ile uyumlu, zero-GC.
- **Bellek güvenliği büyük ölçüde:** taşma/sıfıra bölme/dizi sınırı yakalanıyor; ASan temiz.
- **290 yerleşik (86'sı kullanıcıya açık) + 385 stdlib fonksiyonu**, 52 modül (19'u güvenlik/ağ).
- **Doküman iki dilde:** TR + EN rehber (996 satır) ve şartname (691 satır); dört belgenin kod blokları CI'da derlenerek doğrulanıyor.
- **API dokümanı üretimi:** `axiom doc` — `///` yorumlarından HTML/JSON (std: 81 belgeli öğe).
- **Benchmark var:** C'nin 1,5–2,2× yavaşı (aritmetik), Python'un 6–30× hızlısı.

### 1.2 Zayıf yanlar (ekosistem)

| Blok | Durum | Etki |
|---|---|---|
| Paket sayısı | altyapı hazır, **0 yayınlanmış paket** | Dış katkı pratikte yok |
| Windows/macOS | yok / kısmi | Kullanıcı tabanı daralıyor |
| Self-hosted eşitlik | **21/21** ✅ (4→8→11→12→15→21) | Tam parite |
| IANA saat dilimi / DST | sabit ofset (bilinçli sınır) | Takvim uygulamaları için yetersiz |
| NFKC/NFKD | yok (NFC/NFD tam) | Homoglif normalleştirmesi yok |
| PCRE2/RE2 | yok; POSIX ERE + ReDoS kapısı | İleri regex özellikleri yok |
| Killer app | var (3 güvenlik aracı) ama **kullanıcısı yok** | Kimse denemiyor |

### 1.3 Son 10 turda kapatılan gerçek hatalar (bağlam)

Bu hatalar, "görünen tamlık ≠ gerçek güvenilirlik" dersini kanıtlar:

- LLVM `break`/`continue` hiç yoktu → sessiz yanlış sonuç (C `12` vs LLVM `55`)
- LLVM `defer` yok sayılıyordu
- `@simd` LLVM'de tanımsız attribute grubuna işaret ediyordu
- `ensures return ...` self-hosted'de bozuk C üretiyordu
- Aynı blokta `let` C'de derleme hatası veriyordu
- `as str` çöp kod üretiyordu
- 40 string üreticisi sızdırıyordu
- `array_push` O(n²) idi (139× hızlanma)
- **C: `str[]` use-after-free** — yerel `str` diziye konunca kapsam çıkışında `free`
  ediliyordu; çöp veri dönüyordu (P1-06)
- **LLVM: string literal çift çözümleme** — `"\\\""` tek tırnağa düşüyordu (P1-06)
- **LLVM: `str_join` ABI** — `ax_array_str` by-value geçiliyordu, clang `byval(ptr)`
  bekliyor → segfault (P1-06)
- **`file_read` procfs** — boyutu 0 görünen `/proc` dosyaları boş dönüyordu (P1-06)
- **Sigma fail-open** — bilinmeyen operatör `contains`'a düşüyordu (P1-04)
- **Hangul LVT ayrıştırması** — `(L, T)` üretiyordu, V kayıptı (P2-15)
- **`char_to_str` geçersiz UTF-8** — 0..255 aralığını ham bayt yazıyordu (P2-15)

**Sonuç:** Test yazmak hata buluyor. Yeni özellik eklemeden önce **o özelliğin testi** yazılmalı.
Özellikle: **iki arka ucu olan her örnek için parite testi zorunlu** — tek arka uçla
yeşil test sessiz yanlış sonucu gizler.

---

## 2. NEREYE GİDİYORUZ — misyon

### 2.1 Tek cümlelik misyon

> **Güvenlik ekiplerinin (red/blue) native hızda, doğrulanmış kod yazabildiği;
> daha sonra bu temelden genel amaçlı bir dile açılan platform olmak.**

### 2.2 Hedef sırası (kullanıcı kararı, onaylanmış)

```
FAZ 1: Güvenlik araçları (red team + blue team)   ✅ KAPANDI (2026-11-09)
   ↓
FAZ 2: Olgun kütüphane + ekosistem altyapısı      ← BURADAYIZ (altyapı bitti,
                                                     "0 yayınlanmış paket" kaldı)
   ↓
FAZ 3: Niş'te referans dil (güvenlik-kritik yazılım)
   ↓
FAZ 4: Genel amaçlı dile açılım
```

### 2.3 Hedef OLMAYAN şeyler (kapsam dışı, karar verildi)

- ❌ Python'un yerini almak (stdlib yarışı kaybedilir)
- ❌ Web backend / frontend dili olmak
- ❌ Veri bilimi / ML ana dili olmak
- ❌ Aynı anda 5 platform desteklemek
- ❌ 1.0-beta sonrası sözdizimi değişikliği

### 2.4 Kazanılabilir tek fark

| Fark | Kimde var | Axiom'da |
|---|---|---|
| `requires`/`ensures` + SMT ispat | SPARK (Ada, pahalı), D (SMT yok), Rust (yok) | ✅ |
| Zero-GC + native | C, Rust, Zig | ✅ |
| Modern ergonomi + bu ikisi | **hiçbirinde birlikte** | ✅ **(tek fark)** |

---

## 3. STRATEJİ — neden bu sıralama doğru, nerede düzeltildi

### 3.1 Doğru olan

- **Güvenlikle başlamak doğru.** 8 güvenlik + 11 ağ modülü zaten orada; en yakın çıktı burada. Ayrıca güvenlik topluluğu "hız + tek binary + doğrulama" hikâyesine açık.
- **Global'e sonra gitmek doğru.** Ekosistem olmadan global iddia boş.

### 3.2 Düzeltilen nokta: "önce araç, sonra kütüphane" **yanlış**

**Yanlış model:**
```
Araç bitir → sonra kütüphane yaz → sonra ekosistem
```

**Doğru model:**
```
Araç = kütüphanenin test case'i
```

Araç yazarken eksik kütüphane seni durdurur. Örneğin `axiom-scan` yazmak için
gerçek JSON ve HTTP gerekiyordu; ikisi de o turda yazıldı (P1-01/P1-02) ve araç
103 MB'ı 0,56 s'de taradı. Aynı şekilde DFIR aracı (P1-06) `forensics_list_processes`
ve `json_escape`'i doğurdu.

Yani **her araç, kütüphane için zorunlu bir kabul testidir.** Bu yüzden Faz 1 ve Faz 2 **paralel** yürür:

```
P1 (araç) ──┬──> eksik kütüphane tespiti ──> P2 (kütüphane) ──> araç tamamlanır
            └──> gerçek kullanıcı geri bildirimi
```

### 3.3 "Global" tanımı — ölçülebilir hâle getirildi

"Global dil olmak" bir his değil, eşik:

| Metrik | Eşik |
|---|---|
| Paket | 250+ / 30+ yazar |
| Dış katkı | 10+ PR/ay (3 ay üst üste) |
| Üretim kullanıcısı | 3+ bağımsız kurum |
| Doküman | EN + TR, sürümlenmiş, 5+ rehber |
| Platform | 2+ işletim sistemi gerçekten destekli |
| Kırıcı değişiklik | 1.0 sonrası 0 (major hariç) |

---

## 4. FAZ 1 — GÜVENLİK ARAÇLARI (şimdi)

### 4.1 Faz hedefi

Tek bir **gerçek ürün**: `axiom-scan` — YARA + Sigma + PCAP + ağ taraması,
tek statik binary, sıfır runtime bağımlılığı, ölçülebilir hız.

### 4.2 Faz kapısı (gate)

> **Kapı:** 1 dış kullanıcı `axiom-scan`'i kendi verisinde çalıştırdı ve sonucu
> paylaştı. Kapı açılmadan Faz 3'e geçilmez.

### 4.3 P1 görevleri

#### P1-01 — Gerçek HTTP/1.1 istemcisi `[x]`
- **Neden:** `axiom-scan` HTTP banner/endpoint kontrolü yapacak.
- **Kapsam:** `Content-Length`, `chunked`, header ayrıştırma, yönlendirme (max 5), timeout, TLS.
- **Kabul:** ✅ tümü doğrulandı
  - [x] `std/net/http.ax` chunked yanıtı doğru ayrıştırır
  - [x] 5 yönlendirme sonrası durur, döngü hatası verir (`yonlendirme dongusu`)
  - [x] `tcp_set_timeout` ile zaman aşımı; hata `Result` ile döner
  - [x] `tests/test_http_client.py` — 4 test (gerçek TCP sunucusu, C + LLVM paritesi)
- **API:** `http_request` (yapısal sonuç + redirect takibi), `http_once`,
  `http_header_value`, `http_chunked_decode`, `tcp_recv_all`, `tcp_set_timeout`
- **Not:** `tcp_recv_all` tek `recv` sınırını kaldırdı; 300 KB yanıt tam okunuyor.

#### P1-02 — Gerçek JSON parser `[x]`
- **Neden:** Sigma/YARA kural dosyaları, konfigürasyon, API yanıtları.
- **Kapsam:** iç içe nesne/dizi, `null`, ondalık, bilimsel gösterim, Unicode `\uXXXX`, serileştirme.
- **Kabul:** ✅ tümü doğrulandı
  - [x] `{"a":{"b":[1,2,{"c":null}]}}` derin erişim (`json_path("a.b[2].c")`)
  - [x] `\u00e7` → `ç`, surrogate pair `\ud83d\ude00` → 😀
  - [x] Geçersiz JSON `Result` ile `Err` döner (panik yok), konum bilgisi ile
  - [x] `01` gibi baştaki sıfır reddedilir; 200 seviye derinlik sınırı (stack taşması yok)
  - [x] `tests/test_json_real_parser.py` — 14 test, C + LLVM paritesi
- **API:** `json_parse`, `json_parse_result`, `json_free`, `json_path`,
  `json_get`, `json_at`, `json_len`, `json_key_at`, `json_node_{str,int,float,bool,is_null}`,
  `json_last_error`, `json_{str,int,float,bool}_at`, `json_has_path`, `json_is_null_at`, `json_len_at`

#### P1-03 — `axiom-scan` v0.1 `[x]` (C arka ucu)
- **Neden:** killer app; ekosistemin çekirdeği.
- **Kapsam (v0.1, küçük tut):**
  - `axiom-scan rules <dosya.yar>` → kural yükle, doğrula
  - `axiom-scan scan <dosya> --rules <kural>` → dosya tara, eşleşmeleri JSON yaz
  - `axiom-scan pcap <dosya.pcap> --rules <kural>` → PCAP tara
- **Kabul:** ✅ tümü doğrulandı (C arka ucu)
  - [x] Tek binary; `ldd` yalnızca glibc/OpenSSL/zlib (libaxiom yok)
  - [x] **100 MB dosya 0.56 s** (hedef < 2 s) — 10 MB 0.058 s
  - [x] Çıktı geçerli JSON (bağımsız `json.loads` ile doğrulanır)
  - [x] `examples/21_axiom_scan.ax`, `std/security/yara_rules.ax` (YARA alt küme ayrıştırıcı)
  - [x] `tests/test_axiom_scan.py` — 13 test (rules/scan/pcap, hata yolları)
- **LLVM eşitliği:** P1-03b'de kapatıldı; iki arka uç birebir aynı JSON'u üretir.

#### P1-03c — `axiom-scan` v0.2: DFIR rapor sözleşmesi `[x]`
- **Neden:** v0.1 raporu şema sürümlü değildi, taranan dosyanın hash'ini
  taşımıyordu ve bulgu çıkış kodunu değiştirmiyordu → CI kapısı olarak
  kullanılamıyordu; "hangi baytlar tarandı" kanıtlanamıyordu.
- **Kabul:** ✅ tümü doğrulandı
  - [x] `schema_version=1`, `tool`, `tool_version`, `rules_count` her komutta
  - [x] `scan`: `target_sha256` (tüm dosya; `sha256sum` ile birebir),
        `match_count`, bayt cinsinden `scanned_bytes`
  - [x] `pcap`: `pcap_sha256`, `match_count`
  - [x] `--fail-on-match` opt-in → bulgu varsa exit **10**, yoksa 0;
        bayraksız davranış değişmez (exit 0)
  - [x] Hata yolu şemalı JSON (`"ok":false`) + exit 1
  - [x] `tests/test_axiom_scan.py` — 15 → **20 test** (C + LLVM paritesi)
- **Bulunan gerçek hata:** `main() -> Result<int,str>` köprüsü ok değerini
  **her zaman 0'a** eşliyordu (bilinçli, testli davranış). Dil semantiği
  değiştirilmedi; araç `main -> int` + `_dispatch() -> Result` desenine geçti.
- **Rapor:** `docs/reports/P1-03c-axiom-scan-v02-dfir-readiness-2026-11-12.md`

#### P1-03d — CI kök nedenleri ve LLVM `main()` köprüsü `[x]`
- **Bulunan gerçek hata:** LLVM'de `main() -> Result<int,str>` köprüsü
  `call void @ax_main()` üretiyordu. clang 14 sert hata, clang 21 **sessiz
  yanlış sonuç** (Err düşürülür, exit 0). C arka ucunda doğruydu → parite ihlali.
- **Kabul:** ✅ tümü doğrulandı
  - [x] LLVM köprüsü `Result`'ı değer olarak çağırır; `is_ok`/`error` okunur
  - [x] Err → `[AXIOM HATA] <mesaj>` stderr + exit 1 (C ile birebir)
  - [x] `tests/test_llvm_main_bridge.py` — 6 test; düzeltme geri alınınca
        3 test kırmızı (kanıtlandı, LLVM `exit 0` veriyor)
  - [x] CI: `make bootstrap` testlerden önce (13 test)
  - [x] Unicode: sürüm sabitlendi + altın dosya (2 test, sürümden bağımsız)
  - [x] DWARF: `readelf` içerik sözleşmesi (2 test)
  - [x] CI `fmt` işine `z3` bağımlılığı eklendi
- **Rapor:** aynı dosya, §10

#### P1-03b — LLVM'de `axiom-scan` yanlış sonucu `[x]`
- **Belirti:** LLVM ile derlenen tarayıcı kural adlarını `strings:` gibi üretiyordu.
- **Kök neden (iki ayrı hata):**
  1. Literal ile başlatılan `str` değişkenleri LLVM'de sahiplik takibine
     alınmıyordu → sonraki atamalar `retain` etmiyordu → dangling pointer.
  2. `array_push` ile diziye konan `str` elemanı için ek referans alınmıyordu →
     kaynak kapsam kapanınca dizi öğesi dangle kalıyordu.
- **Kabul:** ✅ `tests/test_axiom_scan.py` C ve LLVM çıktısının **birebir eşit**
  olduğunu doğrular (3 test); 20/20 örnek LLVM ile derlenir.

#### P1-04 — Kural motoru sağlamlaştırma `[x]`
- **Kabul:** ✅
  - [x] YARA: `yara_rule_set_offset_bounds/at_offset`, `yara_scan_single_pattern`,
    `yara_scan_buf`, `yara_ruleset_has_match`, `yara_scan_regex/hex/buffer` testli
  - [x] Sigma: `sigma_eval_op`, `sigma_rule_set_condition`, `sigma_parse_syslog`,
    `sigma_engine_eval_raw`, `sigma_engine_has_alert`, `sigma_match_rule`,
    `sigma_count_matches`, `sigma_rule_eval` testli
  - [x] `tests/test_yara_sigma_coverage.py` — 13 test, C + LLVM paritesi
- **Bulunan 2 gerçek hata:**
  1. **Sigma fail-open:** `sigma_eval_op` bilinmeyen operatörde `contains`'a
     düşüyordu. Güvenlik motorunda yazım hatası (`contians`) sessizce eşleşmeye
     yol açabilirdi. Artık **fail-closed** (`false`).
  2. **`sigma_parse_syslog` yanlış servis adı:** `str_index_of` ilk boşluğu
     bulduğu için servis `sshd[123]` yerine `1 00:00:00 host sshd[123]` oluyordu.
     `_sigma_last_index_of` eklendi.
- **Bilinen davranış:** `sigma_engine_eval_raw(..., "syslog")` default kurallarla
  0 döner; çünkü varsayılan SSH kuralı `log_type = "auth"`. Log türü yalıtımı
  doğru çalışıyor (test edildi).

#### P1-05 — Red team modül sertleştirme `[x]`
- **Neden:** shellcode/C2/evasion var; `--features offensive` izolasyonu var; testler sınırlı.
- **Kabul:** ✅
  - [x] `--features offensive` olmadan import reddediliyor (test: `test_offensive_feature_isolation.py`)
  - [x] Offensive modüller için yasal uyarı başlıkları (5 modülün tümünde)
  - [x] `shellcode_allocate_rwx`, `shellcode_protect` testli (RW/RO/RWX, NULL/size ihlali
    prover'da derleme anında yakalanıyor)
  - [x] `c2_crypto_random_hex` (uzunluk, tekrarsızlık, hex), `c2_hmac_sha256`
    (determinizm, anahtar/veri duyarlılığı, RFC 4231 vektörü), `c2_crypto_memcmp`,
    `c2_generate_beacon`/`c2_parse_beacon` (roundtrip + kurcalama reddi)
  - [x] Testler varsayılan `pytest`'te **skip**, `AXIOM_ENABLE_REDTEAM=1` ile çalışır
    (`tests/test_redteam_libs.py` + `tests/test_redteam_hardening.py`, 17 test)
- **Not:** `--features offensive` izolasyon testleri **varsayılan çalışır** (kod
  çalıştırmaz, yalnızca derler) — güvenlik kontrolünün kendisi.

#### P1-06 — Blue team DFIR akışı `[x]`
- **Neden:** forensics/pcap/sigma/integrity var, uçtan uca akış yok.
- **Kabul:** ✅
  - [x] `examples/22_dfir_triage.ax`: süreç listesi (`/proc`) + açık port
    (`/proc/net/tcp`) + kritik dosya SHA-256 + Sigma eşleşmesi → **tek JSON rapor**
  - [x] Gerçek `/proc` verisiyle test (`tests/test_dfir_triage.py`, sandbox'ta skip)
  - [x] Risk skoru + verdict (info/low/medium/high/critical), C+LLVM paritesi
- **P1-06 sırasında bulunan ve düzeltilen 4 gerçek hata:**
  1. **C: `str[]` use-after-free** — yerel `str` diziye konup kapsamdan çıkınca
     serbest bırakılıyordu; `array_push` artık `str[]` için sahiplenen
     `axiom_array_push_str` kullanıyor.
  2. **LLVM: string literal çift çözümleme** — `"\""` (ters bölü + tırnak) tek
     tırnağa düşüyordu; kaçış tek noktada (`_llvm_escape_bytes`).
  3. **LLVM: `str_join` ABI** — `ax_array_str` by-value geçiliyordu, clang
     `byval(ptr)` bekliyor → segfault. `axiom_str_join_ptr` sarmalayıcısı eklendi.
  4. **`file_read` procfs** — boyutu 0 görünen sanal dosyalar boş dönüyordu;
     akış tabanlı okuma eklendi.
- **Yeni kütüphane (aracın ihtiyacı):** `forensics_list_processes()`,
  `json_escape()`.

---

## 5. FAZ 2 — KÜTÜPHANE VE EKOSİSTEM (Faz 1 ile paralel)

### 5.1 P2-A: Ekosistem altyapısı (en kritik)

#### P2-01 — Paket kayıt defteri (registry) v1 `[x]`
- **Engelleyici:** Dış katkı bunun olmadan imkânsız.
- **Kapsam:**
  - İçerik-adresli depo: `sha256` → tarball
  - **İmza:** minisign veya sigstore; imzasız paket reddedilir
  - `axpm add <ad>@<semver>` gerçekten indirir
  - Semver aralığı + transitive çözümleme + döngü tespiti
  - `yanked` sürüm reddi
  - Offline cache + `axpm verify` içerik doğrulaması
- **Kabul:** ✅ tümü doğrulandı
  - [x] `axpm install` gerçek indirme yapar (index → tarball → doğrula → aç)
  - [x] Bozulmuş tarball reddedilir (sha256, indirme sonrası)
  - [x] İmzasız paket reddedilir (`allow_unsigned` kapalıyken)
  - [x] ed25519 imza tarball baytları üzerinden doğrulanır
  - [x] `axpm tree` bağımlılık grafiğini gösterir
  - [x] Transitive çözümleme, yanked reddi, döngü tespiti, sürüm çakışması
  - [x] `axpm search` eklendi
  - [x] Bozuk önbellek kendini onarır (doğrulama atlanmaz)
  - [x] Path traversal reddedilir
  - [x] `tests/test_registry.py` — 38 test
- **Doküman:** `docs/REGISTRY.md`

#### P2-02 — Namespace `[x]`
- **Kapsam:** `@kapsam/paket` adlandırma; depo dizini `@kapsam__paket`.
- **Kabul:** ✅
  - [x] Aynı adlı iki paket (`@acme/json` ve `@other/json`) çakışmadan kurulur
  - [x] `import "@acme/util"` doğru dizine çözülür
  - [x] `..`, `\\`, çoklu `/` reddedilir (path traversal)
  - [x] `tests/test_registry.py` +5 test (toplam 43)

#### P2-03 — `///` doc comment + doküman üreteci `[x]`
- **Neden:** API dokümanı olmayan dile kimse paket yazmaz.
- **Kapsam:** `///` lexer/parser desteği; `axiom doc` komutu → statik HTML/JSON
- **Kabul:** ✅
  - [x] `///` → `DOC` token; `FunctionDecl.doc` / `StructDecl.doc`
  - [x] `axiom doc std/` → `docs/api/index.html` (52 dosya, 47 belgeli öğe)
  - [x] `axiom doc ... --json` makine okunur çıktı (`-` = stdout)
  - [x] `requires`/`ensures` sözleşmeleri ve struct alanları belgeye taşınır
  - [x] Bozuk dosya tüm üretimi düşürmez (atlanır)
  - [x] CI: `tests/test_docgen.py` — 16 test (lexer, parser, HTML/JSON, CLI, std/)
- **Not:** `std/security/yara.ax` ve `sigma.ax` gerçek `///` doc comment'leriyle
  belgelendi (47 öğe).

#### P2-04 — İngilizce doküman `[x]`
- **Kapsam:** `README.en.md`, `docs/en/TUTORIAL.md`, `docs/en/SPECIFICATION.md`
- **Kabul:** ✅
  - [x] `README.en.md` (404 satır, TR ile aynı bölümler + registry güncel)
  - [x] `docs/en/TUTORIAL.md` — 996/996 satır, 80/80 başlık, 10/10 çalıştırılabilir blok derlenir
  - [x] `docs/en/SPECIFICATION.md` — 691/691 satır, 76/76 başlık, tüm bloklar birebir
  - [x] CI: `tests/test_docs_en.py` — 9 test (yapısal eşitlik, derleme, "gerçekten İngilizce", kırık bağlantı)
  - [x] TR ↔ EN karşılıklı bağlantılar (README, TUTORIAL, SPECIFICATION)
- **Not:** Şartnamedeki `{ ... }` yer tutuculu bloklar kasıtlı; test bunları atlar.

#### P2-05 — Tam LSP `[x]`
- **Kapsam:** `references`, `rename`, `codeAction`, `documentFormatting`, `semanticTokens`, `signatureHelp`
- **Kabul:** ✅
  - [x] `textDocument/references` — bildirim + tüm kullanımlar; `includeDeclaration` desteği;
    yorum ve string'ler lexer sayesinde dışarıda
  - [x] `textDocument/prepareRename` + `textDocument/rename` — tüm oluşumlar tek düzenlemede;
    geçersiz/keyword yeni ad reddedilir
  - [x] `textDocument/codeAction` — yazım düzeltmesi (`str_lenn` → `str_len`) ve
    `let mut` hızlı düzeltmesi (quickfix)
  - [x] `textDocument/formatting` — `format_source` tabanlı tek düzenleme
  - [x] `textDocument/semanticTokens/full` — 12 tip legend (keyword/type/function/struct/
    parameter/variable/property/number/string/comment/operator/namespace), delta kodlama
  - [x] `textDocument/signatureHelp` — yerel + builtin; aktif parametre virgül sayımıyla
  - [x] `initialize` capabilities tüm yeni sağlayıcıları duyurur
  - [x] `tests/test_lsp_full_features.py` — 24 test (birim + gerçek ikili ile protokol)

### 5.2 P2-B: Kütüphane derinleştirme (araçların ihtiyacına göre)

> **Kural:** Yeni kütüphane fonksiyonu, **onu kullanan bir araç/örnek** olmadan eklenmez.

| ID | Modül | Eksik | Öncelik |
|---|---|---|---|
| P2-06 | `std/encoding/json` | ~~gerçek parser~~ ✅ P1-02'de yapıldı | — |
| P2-07 | `std/net/http` | ~~chunked, redirect, timeout~~ ✅ P1-01'de yapıldı | — |
| P2-08 | `std/io/file` | ~~`Result` tabanlı tüm API, dosya boyutu, dizin listesi~~ ✅ | — |
| P2-09 | `std/text/regex` | ~~geri izleme güvenliği (ReDoS kapısı)~~ ✅ | — |
| P2-10 | `std/collections/map` | ~~yeniden boyutlandırma, çarpışma testi~~ ✅ | — |
| P2-11 | `std/time/date` | ~~saat dilimi (sabit ofset), formatlama, ISO parse~~ ✅ | — |
| P2-12 | `std/security/yara` | ~~7 testsiz fonksiyon~~ ✅ P1-04 | — |
| P2-13 | `std/security/sigma` | ~~7 testsiz fonksiyon~~ ✅ P1-04 | — |
| P2-14 | `std/net/event_loop` | ~~epoll testleri~~ ✅ | — |
| P2-15 | `std/text/unicode` | ~~NFC/NFD normalizasyon~~ ✅ | — |
| P2-16 | `std/target/wasm` | gerçek WASM encoder | P3 |

### 5.3 P2-C: Tamamlanan kütüphane derinleştirmesi (2026-11-09)

#### P2-08 — `std/io/file` `[x]`
- **Yeni yerleşikler:** `file_size`, `is_directory`, `list_dir`, `remove_file`,
  `rename_file`, `create_dir` (C + LLVM, aynı semantik)
- **Result sarmalayıcıları:** `file_size_result`, `list_dir_result`,
  `remove_file_result`, `rename_file_result`, `create_dir_result`,
  `copy_file_result`, `dir_present`
- **Kural:** veri hatası `Err` döner; `requires`/`verify` kullanılmaz (testle sabit)
- **Test:** `tests/test_io_file_result_api.py` — 12 test, C + LLVM paritesi

#### P2-09 — `std/text/regex` `[x]`
- **ReDoS kapısı:** iç içe niceleyici (`(a+)+`, `(a*)*`), parantez derinliği > 32,
  `{n,m}` > 1024, desen > 4096 bayt → reddedilir (`regex_risk_level` = 2)
- **Result API:** `regex_is_match_result`, `regex_find_result`,
  `regex_replace_result`, `regex_compile_result` — geçersiz desen sessizce
  "eşleşmedi" demez, `Err` döner
- **Yardımcı:** `regex_escape` (literal arama)
- **Neden PCRE2/RE2 değil:** sistemde `libpcre2-dev` başlığı yok; glibc POSIX ERE
  zaten geri izleme yapmayan NFA. Ek bağımlılık yerine sert kaynak sınırları
  uygulandı. Bu, TODO'daki "geri izleme güvenliği" hedefini karşılar.
- **Test:** `tests/test_regex_safety.py` — 9 test (6 ReDoS kalıbı dahil)

#### P2-10 — `std/collections/map` `[x]`
- Yeniden boyutlandırma (16 → 1024+ bucket, 500 kayıt), çakışma zinciri
  (`djb2 % 16 == 9` olan `c1`/`c10`), silme, üzerine yazma, boş anahtar,
  uzun değerler doğrulandı
- **Test:** `tests/test_map_resize_collision.py` — 8 test, C + LLVM paritesi
- Kod değişikliği gerekmedi: uygulama zaten doğruydu; **doğrulanmamıştı**.

#### P2-11 — `std/time/date` `[x]`
- **Saat dilimi:** sabit ofset (dakika), ±14:00 sınırı; `date_format_tz`,
  `date_iso_tz`, `date_local_offset_minutes`, `date_offset_label`
- **ISO 8601:** `date_parse_iso` (`Z`, `+03:00`, `-0530`, ofsetsiz, boşluklu);
  geçersiz → `Err`
- **Süre:** `date_duration_label` (`1g 1sa 1dk 1sn`)
- **Açık sınır:** IANA tz veritabanı ve DST kural tablosu **yok**; modül
  başlığında ve testte (`test_scope_is_documented`) sabitlendi
- **Test:** `tests/test_date_timezone.py` — 9 test (53 ofset roundtrip dahil)

#### P2-14 — `std/net/event_loop` `[x]`
- **Durum:** 6 mevcut test lifecycle/pipe/socketpair/mod-del/reactor/nonblocking TCP'yi
  kapsıyordu; **7 fonksiyon kapsanmamıştı**.
- **Eklenen kapsam:** `event_is_writable`, `event_is_error`, `event_is_hangup`,
  `event_loop_mod`, `event_loop_event_fd`, `event_loop_event_events`,
  `net_set_nonblocking` + EPOLLHUP (karşı uç kapanınca), EventKind sabitleri,
  `event_loop_new_with_capacity` sınırı.
- **Kod değişikliği gerekmedi** — hepsi doğru çalışıyordu.
- **Test:** `tests/test_event_loop_coverage.py` — 11 test + "her `fn` en az bir
  kez testte geçmeli" bekçi testi (28 fonksiyon).

#### P2-15 — `std/text/unicode` NFC/NFD `[x]`
- **Gerçek normalizasyon:** tablolar Unicode Character Database'den **üretilir**
  (`tools/gen_unicode_tables.py` → `axiom/unicode_tables.h`, UCD 15.1.0):
  - 2.061 kanonik ayrıştırma, 922 birleştirici sınıf (ccc), 941 birleştirme çifti
  - Hangul (11.172 hece) **algoritmik** — tabloya yazılmaz (Unicode §3.12)
- **API:** `unicode_nfc`, `unicode_nfd`, `unicode_is_nfc`, `unicode_is_nfd`,
  `unicode_normalize`, `unicode_normalize_result`, `unicode_canonical_eq`,
  `unicode_ucd_version`
- **Konformans testi:** 28 metinlik korpus Python `unicodedata` ile birebir
  karşılaştırılır (NFC+NFD+is_nfc+is_nfd); ayrıca **11.172 Hangul hecesi**
  roundtrip, idempotans, bozuk UTF-8 dayanıklılığı
- **NFKC/NFKD:** compatibility tablosu gömülü değil → **açık hata** (`D7`
  ilkesi: sessiz yanlış yasak)
- **Bulunan 2 gerçek hata:**
  1. **Hangul LVT ayrıştırması** — `(L, T)` üretiyordu (V kayıp); `((LV), T)`
     olmalı ve özyineleme V'yi ekler.
  2. **`char_to_str` ASCII dışını bozuyordu** — 0..255 aralığını tek bayt
     yazdığı için U+0080..U+00FF geçersiz UTF-8 üretiyordu. Artık her kod
     noktası doğru UTF-8'e kodlanır (surrogate/aralık dışı → boş).
     Ham baytlar için `std/io/binary` `buf_*` API'si doğru araçtır.
- **Test:** `tests/test_unicode_normalization.py` — 16 test, C + LLVM paritesi

#### P2-17 — Geçici string sızıntısı `[x]` (intrusive header P2-17b'ye ayrıldı)
- **Kapsam:** README'de "bilinen sınır" olarak yazılı üç sızıntı kapatıldı.
- **Kabul:** ✅ (bu tur), tam intrusive-header refactor ertelendi
  - [x] `print(f(x))` — argüman geçicileri ifade sonunda bırakılır
  - [x] Sonucu atılan ifade deyimi (`make(x)` çıplak çağrı) — geçiciler bırakılır
  - [x] `continue` / `break` — döngü gövdesine ait kapsamlar temizlenir
    (`defer` de çalışır); döngü dışı değişkenler etkilenmez
  - [x] `axiom_temp_release_keep` saklanan değeri dış kapsama görünür bırakır
    (yoksa "adopt edilen" değer sızıyordu)
  - [x] `tests/test_temp_string_cleanup.py` — 15 test (C sayısal büyüme,
    iki arka uç davranış + ASan)
- **P2-17b — tamamlandı:** intrusive header + `String`/`str` tip ayrımı.
  Şu an alias güvenliği refcount tablosuyla sağlanıyor; ayrım performans ve
  ABI netliği için. 82 fonksiyon / 277 çağrı dokunur → tek başına tur.

#### P2-17b — Intrusive header bellek modeli `[x]`
- **Kabul:** ✅ — benchmark'la önce/sonra ölçüldü, 976 test yeşil, ASan 21/21.
- **Yapılan:** refcount artık string'in **hemen önünde** (24→32 bayt header,
  veriyle aynı cache satırı). Global `ptr→refs` hash tablosu tamamen kaldırıldı.
- **Ölçüm** (`benchmarks/str_ownership_bench.c`):

  | Senaryo | Önce | Sonra |
  |---|---:|---:|
  | `int_to_str` 300k | 31.4 ms | **26.8 ms** |
  | 150k canlı string oluştur | 31.9 ms | **16.5 ms** (−48%) |
  | 150k canlı string bırak | 9.9 ms | **4.0 ms** (−60%) |
  | Takip tablosu belleği | 10.0 MB | **0 MB** |

- **Güvenlik (kritik):** `str` literal ve dış kaynaklı işaretçileri de taşır.
  - `axiom_ptr_is_static`: ELF `PT_LOAD` (kodsuz) segment aralıkları bir kez
    toplanır; `dladdr` (17 ns/op) yerine 2-6 karşılaştırma.
  - Header'da magic; sahipsiz işaretçide retain/release **no-op** (eski davranış).
  - `os_getenv` / `cli_args_get` artık sahipli kopya döner (ham environ/argv
    işaretçisi sızmaz).
- **Gecicilik günlüğü thread-local** yapıldı; hot path'te kilit kalmadı.
- **Canceled:** `String`/`str` tip ayrımı **gerekmedi** — çift serbest bırakma
  ve literal koruması header magic + segment kontrolü ile sağlanıyor.

#### P2-19 — Platform taşınabilirliği: Linux + Windows `[x]`
- **Kabul:** ✅ `axiom build --target windows` → PE32+ ikili, **21/21 örnek**.
  Linux davranışı bozulmadı (C 21/21, LLVM 21/21, self-hosted 21/21).
- **Mimari:** `axiom/platform.h` — 4 katmanlı soyutlama:

  | Katman | Kapsam | Linux | Windows |
  |---|---|---|---|
  | 1 Çekirdek | string, dizi, dosya, thread, zaman | ✅ | ✅ |
  | 2 Ağ | TCP/UDP/DNS/HTTP | POSIX sockets | Winsock2 |
  | 3 Linux'a özel | epoll, /proc, ptrace, shellcode | ✅ | **açık hata** |
  | 4 Harici | OpenSSL (AES/TLS), zlib | ✅ | hash/HMAC **yedek**, AES/zlib **açık hata** |

- **`axiom/crypto_portable.h`:** SHA-256, SHA-1, MD5, HMAC-SHA256, sabit zamanlı
  karşılaştırma. OpenSSL yoksa devreye girer. FIPS 180-4 / RFC 1321 / RFC 2104
  vektörleriyle doğrulandı (`hashlib`/`hmac` ile birebir).
- **Açılan soyutlamalar:** thread/mutex/cond, zaman, dosya sistemi, ortam
  değişkeni, süreç yönetimi, soket seçenekleri/poll, dinamik kütüphane,
  yürütülebilir bellek, CPUID/XCR0, statik işaretçi tespiti.
- **Bulunan 3 gerçek hata (düzeltildi):**
  1. `wrap(safe_strdup(x))` — 8 yerde çift sarma → yeni modelde **geçersiz `free`**.
  2. `exec_mem_run` RW tahsis edip çalıştırıyordu → SEGV; `ax_os_alloc_rwx` ayrıldı.
  3. zlib bloğunda iç içe `#if` hatası.
- **Test:** `tests/test_portability.py` — 23 test. Windows kod yolu Linux'ta
  **çalıştırılarak** doğrulandı (hash'ler `hashlib` ile birebir); PE import
  tablosu yalnız `KERNEL32`/`msvcrt`/`WS2_32` içeriyor (çıplak Windows'ta başlar).
- **Sınır:** Windows ikilileri çalıştırılmadı (wine yok), yalnız derleme doğrulandı.

#### P2-19b — Wine ile gerçek Windows çalıştırma `[x]`
- **Kabul:** ✅ Wine 10.0 ile **21/21 örnek çalışıyor**, çıktılar Linux ile
  birebir (zamanlama/rastgelelik normalize edilerek).
- **Bulunan 3 GERÇEK hata (wine olmadan görünmezdi):**
  1. **`WSAStartup` hiç çağrılmıyordu** — Windows'ta hiçbir soket çalışmazdı.
     `platform.h`'ye `__attribute__((constructor))` + tembel başlatma;
     tüm soket oluşturmaları `ax_os_socket()` üzerinden.
  2. **POSIX regex yoktu** — Sigma/YARA/CVE tespiti Windows'ta sessizce `false`
     dönüyordu. `axiom/regex_portable.h` yazıldı: geri izlemeli ama **adım
     bütçeli** (ReDoS'a kapalı). `\1` geri referans ve `(?=)` **derleme hatası**.
  3. **Thread çıktı yarışı** (örnek 11) — UDP alıcı thread'i ile ana thread
     yarışıyordu; çıktı koşudan koşuya değişiyordu. `thread_join` sonrasına alındı.
- **Test:** `tests/test_portability.py` — 34 test (10'u wine ile gerçek koşum:
  çıktı paritesi, regex motoru, soket katmanı).

#### P2-21 — Atanmamış dizi serbest bırakma / sonsuz döngü `[x]`
- **Belirti:** üç test ikilisi **2 gün** %98 CPU ile döndü.
- **Kök neden:** `let l = read_lines(p)?` hata yolunda atanmamış `l`
  serbest bırakılıyordu; çöp `.length` yüzünden döngü milyonlarca kez dönüyordu.
- **Düzeltme:** `pending_init` koruması **dizi** kapsamlarına da uygulandı
  (3 nokta). Daha önce yalnız string kapsamlarındaydı.
- **Neden aralıklı:** çöp değer küçükse sessiz geçiyordu. Bu yüzden testi
  **üretilen C** üzerinde iddia ediyoruz; çalışma anı testi tek başına yetmez.
- **Regresyon:** `tests/test_uninit_array_release.py` (5 test); düzeltme geri
  alınınca kırmızı olduğu kanıtlandı.
- **Altyapı:** `conftest.py` varsayılan 900 s subprocess zaman aşımı; wine
  prefix oturum sonunda silinir (hook `conftest`'e taşındı).
- **Bu turda ayrıca bulunan 3 gerçek hata** (bellek modeli değişikliği ortaya
  çıkardı, hepsi düzeltildi):
  1. **`if`/`while` koşullarındaki geçiciler sızıyordu** — 500 iterasyonda 500
     string. Koşul bool'a çevrildikten hemen sonra `temp_release` eklendi.
  2. **Erken `return`, kapsamdaki diğer sahipli değişkenleri bırakmıyordu** —
     `_mark_escape` fonksiyon boyunca geçerli olduğu için. `str` dönüşünde
     escape işaretleme kaldırıldı (retain zaten koruyor).
  3. **Dizi literali stack'te compound literal üretiyordu** — döndürülünce
     sarkan işaretçi (`return [id, "str:" + text]`). Artık heap'e yazılıyor.
  4. **`?` hata yolu, atanmamış değişkeni serbest bırakıyordu** — çöp dizi
     üzerinde `axiom_array_str_free` sonsuz döngü. `pending_init` koruması.

#### P2-18 — Self-hosted tip çıkarımı `[x]` (4/21 → 8/21)
- **Kabul:** ✅ `bin/axiomc` ile derlenen+çalışan örnek 4 → **8**
  (`05_real_scanner`, `08_multithreaded_scanner`, `09_simd_vector_scan`,
  `17_ai_tensor_neural_net` eklendi)
- **Düzeltilen 5 gerçek hata:**
  1. **`len(str)` yanlış yerleşik** — `axiom_len` (dizi `.length`) çağrılıyordu.
     `axiom_slen_auto` makrosu eklendi: `_Generic` + statement expression ile
     hem `ax_str` hem `ax_array_*` için doğru sonuç (rvalue dahil).
  2. **UTF-8 kaynak kesilmesi** — self-hosted lexer `len(src)` (kod noktası) ile
     bayt indeksini karşılaştırıyordu; Türkçe/emoji içeren dosyalar sonda
     kesiliyor, son deyim yarım kalıyordu. `str_byte_len` kullanılıyor.
  3. **`codegen_wrap_ensures` bayt/kod-noktası karışımı** — `b_len = len(body)`
     iken `str_sub` bayt tabanlı; çok baytlı gövdede kapanış `}` kayboluyordu.
  4. **`thread_create` C üretimi** — `axiom_thread_create(worker, 80)` (fonksiyon
     adı çıplak, 3. argüman yok) → `axiom_thread_create((void*)ax_worker, 80, false)`.
  5. **`main` void dönüşü** — `return (int)ax_main();` yerine `ax_main(); return 0;`.
- **Ayrıca:** `let x = f()` için `__auto_type` (tek geçişli parser'da tip ortamı
  yok; struct dönen kullanıcı fonksiyonları artık doğru çalışıyor) ve
  `axiomc` geçici dosyaları PID ile tekilleştirildi (eşzamanlı çalışmada
  birbirini eziyordu — test kararsızlığının kaynağıydı).
- **Test:** `tests/test_selfhosted_contracts.py` — 8 örnek listesi gerçek
  derlemeyle doğrulanıyor + UTF-8 kesilme regresyon testi (`test_supported_list_is_accurate`)
- **Kalan 13 örnek:** generic struct somutlaştırma (`ax_Result_str_str` vb.),
  `str[]` alan erişimi, stdlib fonksiyon eşlemesi. P2-18b olarak kayıtlı.

#### P2-18b — Generic struct somutlaştırma ve stdlib eşlemesi `[x]`
- **Kabul:** ✅ altyapı düzeltildi; kalan örnekler P2-18c/d/e/f'te kapandı (21/21)
- **Düzeltilen 6 gerçek hata (hepsi ön koşuldu):**
  1. **`import "std/..."` uzantısız yollar sessizce atlanıyordu** — `std/core/error`
     gibi import'lar `.ax` eklenmediği için hiç yüklenmiyordu. Sessiz atlama,
     "tanımsız tip" hatalarının gizli kaynağıydı.
  2. **`E` tip parametresi tanınmıyordu** — `Result<T, E>` bu yüzden hiç
     somutlaşmıyordu (`is_generic_template` yalnız T/U/V/K bakıyordu).
  3. **Generic argümanda `str[]`** — monomorfizasyon döngüsü `[`/`]` token'larını
     reddediyordu; `Result<str[], str>` hiç üretilmiyordu.
  4. **C tanımlayıcısında `[]`** — `ax_Result_str[]_str` geçersiz C üretiyordu;
     struct adı, struct literal ve tip adı yollarında `_array` eşlemesi eklendi.
  5. **`rt_*` yerleşik eşlemesi eksikti** — `rt_base64_encode`, `rt_dns_resolve_ipv4`,
     `rt_buf_*`, `rt_regex_*`, `rt_forensics_*`, `rt_cli_*` C'ye çıplak geçiyordu.
     Genel kural eklendi: `rt_X` → `axiom_X`.
  6. **`result_ok<T>`/`result_err_with<T>` tip parametresi** — tek geçişli
     derleyici T'yi çözemiyor, her zaman `int` örnek üretiyordu. Çağrı yerinde
     açık tip argümanı varsa (`result_ok<str>(x)`) doğrudan
     `axiom_result_ok_str(x)` üretilir; yoksa `_Generic` tabanlı
     `axiom_result_ok_auto(v)` değerin C tipine göre seçer.
- **Ölçüm:** `examples/12_packet3_system_exploit.ax` 20 C hatasından **1**'e indi
  (kalan: `str + str` birleştirmesinin tip çıkarımı — self-hosted derleyicide
  değişken tip ortamı yok).
- **Kalan (P2-18c):** generic **fonksiyon** monomorfizasyonu (çağrı yerine göre
  gövde üretimi) ve `+` operatöründe string birleştirme çıkarımı.

#### P2-18c — Tip çözücü operatörler ve `?` desteği `[x]` (8/21 → 11/21)
- **Kabul:** ✅ `bin/axiomc` 11 örneği derliyor, çalıştırıyor ve **Python
  sürücüsüyle aynı çıktıyı** veriyor (PID/zaman normalizasyonu sonrası).
  Yeni: `12_packet3_system_exploit`, `14_packet5_full_security_suite`,
  `19_error_handling`.
- **Düzeltilen 5 gerçek hata:**
  1. **`==` iki değişkende pointer karşılaştırması yapıyordu** — `axiom_str_eq`
     yerine `(a == b)`. `12`/`14` derleniyor ama `verify` düşürüyordu (sessiz
     yanlış kod). `axiom_eq_auto`/`axiom_neq_auto` (`_Generic`) eklendi.
  2. **`+` operatöründe tip bilinmiyordu** — `out + c` derleme hatası
     veriyordu. `axiom_add_auto` (`_Generic`: metin→birleştirme, sayı→toplama).
  3. **`?` operatörü hiç desteklenmiyordu** — lexer `?` karakterini sessizce
     atıyordu; `let x = f(y)?` açılmamış `Result` üretiyordu. Artık
     `__auto_type` ile açılıp Err'de (defer'ler çalışarak) iletilir.
  4. **`return` + `defer` yolunda `ax_typeof(...)`** — ifade bir makro çağrısı
     olduğunda tipi yanlış çıkarıyordu; `__auto_type` kullanılıyor.
  5. **Bilinmeyen `ax_X(...)` çağrıları** — stdlib bazı yerleşikleri `rt_`
     öneki olmadan çağırıyor (`json_parse`, `tcp_ping`, `cli_set_args`);
     codegen artık kullanıcı fonksiyonu olmayanları `axiom_X`'e çeviriyor.
- **Test:** `tests/test_selfhosted_parity.py` — 14 test. Listedeki her örnek
  için **self-hosted çıktısı Python sürücüsüyle karşılaştırılır** (normalize
  edilmiş). "Derleniyor ama yanlış" durumu ayrı regresyon testiyle kilitli.
- **Kapsam dışı:** `Result<T,E>` generic **fonksiyon gövdesinin** çağrı yerine
  göre ayrı örneklenmesi (P2-18d). Şu an gövde T→int ikamesiyle tek kez
  üretiliyor; `result_*` yardımcıları tipli makrolara yönlendiriliyor.

#### P2-18d — `str[]` literali, `?` tipleri ve `result_ok<T>` `[x]` (11/21 → 12/21)
- **Kabul:** ✅ `13_packet4_fuzzer_scanner` açıldı; kalanı P2-18e/f'te kapandı
- **Düzeltilen 4 gerçek hata:**
  1. **Dizi literali her zaman `int[]` üretiliyordu** — `(ax_int[]){"a","b"}`
     geçersiz C. Tüm elemanlar metinse artık `ax_array_str`/`ax_str[]`.
     Boş dizi açık tiple (`let e: str[] = []`) dönüştürülür.
  2. **`str[]` bekleyen çağrı bağlamı** — `csv_add_row`, `cli_set_args`,
     `json_build_object` gibi yerleşiklere verilen dizi literali metin dizisi
     olarak üretilir (`expects_str_array`).
  3. **`?` dönüş tipi** — `read_lines` (`Result<str[],str>`) içinde
     `read_file` (`Result<str,str>`) hatası taşınırken struct tipi uyuşmuyordu.
     Parser artık yer tutucu bırakır (`__AXIOM_RET_TYPE__`), `parse_function`
     gerçek dönüş tipiyle doldurur; Err `memset` + `.error` ile taşınır.
  4. **`result_ok<T>` bilinmeyen T** — `result_ok<Config>`/`<YaraRuleSet>`
     `int` örneği üretiyordu. Artık her T için doğrudan struct literali
     (`((ax_Result_Config_str){...})`).
- **Ayrıca:** `axiom_str_split` `is_str_expr`'de `str` sanılıyordu (dizi döner).
- **Test:** `tests/test_selfhosted_parity.py` 15 test (13 dahil);
  zaman/ağ ölçüm satırları normalize edildi (flaky giderildi).
- **Kalan (P2-18e):** `x < y` karşılaştırmasının generic sanılması
  (`if size < 0` → `ax_size(...)`), struct dizi alanında `.capacity`,
  `ensures return.field`, `tls_id` benzeri struct alanları.

#### P2-18e — `x < y` generic çakışması ve struct dizi `capacity` `[x]` (12/21 → 15/21)
- **Kabul:** ✅ **Faz 1 hedefi (8/21) iki katına çıkarıldı** — 15/21.
  Yeni açılanlar: `11_packet2_advanced_network`, `18_web_api_framework`,
  `20_stdlib_result` (hepsi Python sürücüsüyle aynı çıktı).
- **Düzeltilen 4 gerçek hata:**
  1. **`x < y` generic sanılıyordu (en kritik)** — `parse_primary` generic
     taraması `>` ararken **sonraki ifadedeki** `result_ok<int>`in `>`ını
     yakalıyordu. `if size < 0 { ... result_ok<int>(size) }` → `ax_size(size)`.
     Tarama artık `; { } ( ) = + - * / == !=` görürse vazgeçer.
  2. **Struct dizi tipinde `capacity` yoktu** — `ax_array_Route` yalnız
     `{length, data}` idi; `axiom_array_push` `.capacity` kullandığı için
     derleme hatası. Alan eklendi (runtime `ax_array_*` ile aynı düzen).
  3. **`result_err_with<T>` argüman ayrımı** — `str_index_of(args, ", ")`
     iç içe çağrının virgülünü yakalıyordu:
     `axiom_str_concat("sayi degil: ", path), 0.0` → bozuk C.
     `split_top_level_args` (parantez derinliği + string farkındalığı).
  4. **`result_ok<float>`** `int` örneği üretiyordu; artık `float` için de
     struct literali.
- **Test:** parite listesi 15 örneğe çıkarıldı (17 test).
- **Kalan 6 örnek:** `07` (`ensures return.field`), `10`/`16` (struct dizi
  alanı ve `str[]` alan erişimi), `21` (`pcap_open_reader` benzeri eşleme),
  `22` (generic struct literal artığı).

#### P2-18f — Kalan tüm örnekler: 15/21 → 21/21 `[x]`
- **Kabul:** ✅ `bin/axiomc` **21 örneğin tamamını** derliyor, çalıştırıyor ve
  Python sürücüsüyle aynı çıktıyı veriyor (20 örnek birebir; redteam ayrı
  testte, rastgele beacon nedeniyle yalnız derleme+çalışma doğrulanır).
- **Düzeltilen 9 gerçek hata:**
  1. **Çoklu `requires`/`ensures` cümleleri yutuluyordu** — `pcap.ax` gibi
     dosyalarda ikinci `requires`tan sonraki her şey önceki fonksiyonun
     gövdesine giriyordu (sessiz bozulma). Artık `&&` ile birleştirilir.
  2. **`std:...` import'unda çift uzantı** — `import "std:net:http.ax"` →
     `std/net/http.ax.ax` aranıyor, dosya **sessizce atlanıyordu**.
  3. **`pcap_`/`fim_`/`forensics_` önekleri** doğrudan runtime'a eşleniyor,
     std sarmalayıcıları gölgeleniyordu (`axiom_pcap_open_reader` tanımsız).
  4. **Tip yayılımı yoktu** — `let x = <str ifade>` → `ax_int x = ...`.
     Codegen'e sabit-nokta tip çıkarımı eklendi: `str`/`str[]` parametreleri ve
     struct metin alanları tohum; `ax_str` bildirimleri de öğrenilir.
  5. **`__auto_type X = axiom_str_split(...)`** dizisi eleman erişiminde
     `ax_int` sanılıyordu; dizi taban adı haritası eklendi.
  6. **Struct dizi alanı elemanı** (`(rule).selections.data[i]`) `ax_int`
     sanılıyordu; alan→eleman-tipi haritası (`arrmap`) eklendi (struct alanları
     **ve** struct dizi parametreleri).
  7. **`T[]` döndüren fonksiyon sonucu** (`yara_ruleset_scan`) eleman erişimi
     için `fnret` haritası eklendi.
  8. **`main() -> Result<int,str>`** desteği yoktu — köprü `(int)ax_main()`
     üretiyordu. Artık Ok→exit 0, Err→stderr + exit 1 (Python sürücüsüyle aynı).
  9. **`rt_*` → `axiom_*` rewrite'ı `axiom_*` çağrılarını bozuyordu** —
     `rewrite_unknown_calls` iki öneki de tanıyacak şekilde yeniden yazıldı.
- **Ayrıca:** `axiomc` artık `-Wno-unused-*` kullanıyor (uyarı gürültüsü
  parite çıktısını kirletiyordu) ve `map_builtin_func` artık `pcap_`/`fim_`/
  `forensics_` öneklerini runtime'a kısa devre yapmıyor.
- **Test:** `tests/test_selfhosted_parity.py` — 20 örnek birebir çıktı +
  redteam derleme + "derleniyor ama yanlış" regresyonu + UTF-8 kesilmesi.

#### P2-20 — Atlanan (skip) testlerin kapatılması `[x]`
- [x] Redteam testleri artık **varsayılan çalışır** (17 test); izole olmayan
  ortam için `AXIOM_SKIP_REDTEAM=1` kaçış kapısı.
- [x] `test_axiom_scan.py` "ldd yok" skip mesajı netleştirildi (binutils yok).
- [x] Self-hosted örnek listesi 8 → **20** (parite testiyle senkron).
- **Sonuç:** `pytest -q` → **976 passed, 0 skipped**.

### 5.3 P2-C: Yapısal borçlar (planlı, tek seferde yapılmaz)

| ID | İş | Neden erteleniyor |
|---|---|---|
| P2-17b | ~~**Intrusive header**~~ ✅ (String/str ayrımı gerekmedi) | — |
| P2-18 | ~~**Self-hosted tip çıkarımı**~~ ✅ 4/21 → 8/21 | — |
| P2-18b | **Generic fonksiyon monomorfizasyonu** | `result_ok<T>` gibi yardımcılar tek `int` örneğine indirgeniyor; 12 örneği tek hata ayırıyor |
| P2-19 | ~~Runtime `platform` katmanı~~ ✅ (Linux + Windows) · WASI sysroot bekliyor | — |

---

## 6. FAZ 3 — NİŞ'TE REFERANS (Faz 1 kapısı açıldıktan sonra)

- [ ] 1.0 sürüm; 2 sürüm geriye uyum taahhüdü
- [x] ~~Windows çapraz derleme~~ ✅ (P2-19, 21/21) · macOS doğrulaması bekliyor
- [ ] 200+ paket, 20+ yazar
- [ ] İlk kurumsal kullanıcı (güvenlik ekibi veya gömülü)
- [ ] Regülasyon kanıt paketi: `axiom prove` çıktısı → IEC 62304 / ISO 26262 denetim dosyası
- [ ] Fon: NLnet NGI Zero / Sovereign Tech Fund başvurusu

---

## 7. FAZ 4 — GENEL AMAÇLI AÇILIM (koşullu)

Yalnızca Faz 3 metrikleri sağlanırsa:
- [ ] 500+ paket
- [ ] 3–5 kişilik çekirdek ekip
- [ ] Vakıf/şirket arkası
- [ ] Konferans + sertifikasyon programı

---

## 8. ÇALIŞMA KURALLARI (AI ajanları için bağlayıcı)

### 8.1 Kod yazmadan önce

1. Bu dosyada ilgili görevin **Kabul** maddelerini oku.
2. Kabul maddelerini **çalıştırılabilir komutlara** çevir.
3. Önce **testi** yaz (kırmızı), sonra kodu (yeşil).
4. Ölçüm gerekiyorsa `benchmarks/` altına ekle.

### 8.2 Yasaklar

- ❌ Ölçülmemiş performans iddiası
- ❌ Test edilmemiş özelliği `[x]` işaretlemek
- ❌ "Çalışıyor" demek; komut+çıktı göstermeden
- ❌ Sessiz yanlış sonuç üreten kodu bırakmak (LLVM `break` dersi)
- ❌ Bir arka uçta olmayan özelliği sessizce yok saymak
- ❌ Dokümanı koddan sonra güncellemeyi atlamak

### 8.3 Bir arka uçta özellik yoksa

**Derleme hatası ver**, sessizce yok sayma. Örnek doğru davranış:

```text
'?' operatoru LLVM arka ucunda henuz desteklenmiyor. C arka ucunu kullanin.
```

### 8.4 Bellek kuralları (kritik)

- `ax_str` döndüren fonksiyonun sonucu **asla** ham `free()` ile bırakılmaz → `axiom_str_release`
- Yeni string üreticisi eklerken `axiom_owned_str_wrap(...)` ile sar
- Bellek değişikliğinde `--asan` testi zorunlu
- `str_owned_count()` ile tablo şişmesini kontrol et (LSan tek başına yetmez)

### 8.5 Test kuralları

- Her özellik için **uçtan uca** test (Axiom → C/LLVM → binary → çıktı)
- İki arka uç varsa **parite testi** (`test_llvm_control_flow.py` örneği)
- Negatif test: hata bekleniyorsa `returncode != 0` doğrulanır
- Doküman kod blokları CI'da derlenir (`test_tutorial_examples.py`, `test_specification.py`)

---

## 9. KARAR KAYITLARI (ADR-lite)

| # | Karar | Gerekçe | Tarih |
|---|---|---|---|
| D1 | Önce güvenlik, sonra global | En yakın varlık + ölçülebilir çıktı | 2026-11-07 |
| D2 | Araç = kütüphane test case'i | Kütüphane boşluğu araç yazarken ortaya çıkar | 2026-11-07 |
| D3 | "Global" = 250 paket + 3 kurum eşiği | His değil, metrik | 2026-11-07 |
| D4 | Python stdlib yarışına girilmez | Kaybedilen oyun | 2026-11-07 |
| D5 | `Result` + `?` (try/except değil) | Zero-GC uyumu, defer ile normal akış | 2026-11-06 |
| D6 | Sözleşme = programlama hatası, `Result` = beklenen hata | İki katman netliği | 2026-11-06 |
| D7 | LLVM'de olmayan özellik → açık hata | Sessiz yanlış kod en tehlikeli | 2026-11-07 |
| D8 | Ofansif modüller `--features offensive` ile opt-in | Tedarik zinciri + yasal | 2026-11-05 |

---

## 10. ÖLÇÜM PANOSU (her turda güncelle)

| Metrik | Bugün | Faz 1 hedefi | Faz 3 hedefi |
|---|---:|---:|---:|
| Test | 1031 ✅ | 900 | 2000 |
| Stdlib fonksiyon | 385 | 450 | 900 |
| Örnek program | 21 | 25 | 60 |
| Paket (registry) | 0 → altyapı hazır | 10 | 250 |
| Dış katkı/ay | 0 | 2 | 10 |
| Üretim kullanıcısı | 0 | 1 | 3 |
| Self-hosted örnek | **21/21** ✅ | 8/21 | 21/21 |
| C'ye hız oranı (aritmetik) | 1,5–2,2× | ≤2× | ≤1,5× |
| Platform | **2 (Linux + Windows, wine'da 21/21 çalışıyor)** | 1 | 2+ |

---

## 11. ARŞİV — tarihsel belgeler

Aşağıdakiler **geçmiş kayıttır**, güncel değildir. Çelişki varsa bu dosya geçerlidir.

| Dosya | İçerik | Durum |
|---|---|---|
| `TODO.md` (bu dosya) | Tek doğruluk kaynağı | **Güncel** |
| `MASTER_TODO.md` | Faz 1–5 yol haritası (2026-11-04) | Arşiv |
| `LIBRARIES_TODO.md` | 5 paketlik kütüphane planı | Arşiv |
| `GLOBAL_LANGUAGE_ROADMAP.md` | Faz 1–7 teknik yol haritası | Arşiv |
| `AUDIT_REMEDIATION_TODO.md` | Denetim düzeltmeleri (2026-11-04) | Arşiv |
| `REMEDIATION_TODO_2026-11-05.md` | P0/P1 düzeltmeleri | Arşiv |
| `Axiom_*_Raporu_2026-11-*.md` (masaüstü) | Tur raporları | Kayıt |

---

## 12. HEMEN YAPILACAKLAR (bu hafta, sırayla)

1. **P1-02** — Gerçek JSON parser (Sigma/YARA kuralları buna bağlı)
2. **P1-01** — HTTP/1.1 chunked + redirect (tarama aracı buna bağlı)
3. **P2-01** — Registry v1 (dış katkının ön koşulu)
4. **P1-03** — `axiom-scan` v0.1 (killer app)
5. **P2-03 + P2-04** — `///` doc comment + İngilizce doküman

> **Not:** 1 ve 2 olmadan 3 anlamsız; 3 olmadan ekosistem başlamaz;
> 4 olmadan kimse 1–3'ü fark etmez.
