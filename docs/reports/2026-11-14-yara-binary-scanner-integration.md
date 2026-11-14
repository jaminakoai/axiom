# YARA binary hedef tarama entegrasyonu

**Tarih:** 14 Kasım 2026  
**Kapsam:** `axiom-scan` dosya ve PCAP hedeflerinde ByteBuffer'ın gerçek uzunluğunu uçtan uca korumak.

## Yapılan değişiklikler

- Scanner dosyaları NUL baytlarını kaybetmeden `read_file_bytes` ile ByteBuffer'a alıyor ve tüm buffer uzunluğunu tarıyor.
- Metin, hex, occurrence metadata'sı ve koşul değerlendirmesi length-aware YARA runtime API'lerini kullanıyor.
- PCAP paket içeriği hex'ten ByteBuffer'a çevrilerek binary tarama yoluna veriliyor.
- JSON raporundaki `scanned_bytes` artık tam taranan hedef/payload uzunluğunu gösteriyor.
- NUL içeren hedefte regex kullanımı, mevcut POSIX ERE arayüzü NUL içerebilen byte spanini doğru temsil edemediğinden, sessizce yanlış sonuç üretmek yerine açık yapılandırılmış hata veriyor. NUL içermeyen regex taraması mevcut davranışını koruyor.
- `buf_find_byte`/`rt_buf_find_byte` NUL kontrolünü `memchr` üzerinden yapıyor; her bayt için handle doğrulamasından kaçınıyor.
- Tarama sonucu için Axiom generic typechecker'ın desteklemediği `Result<YaraMatch[], str>` yerine somut `YaraBufferScanResult` kullanıldı.

## Önlenen hata

Önceki scanner hedefi C-string olarak alıyordu; `strlen` tabanlı yol ilk NUL baytında kesildiğinden sonrasındaki imzalar sessizce kaçırılabiliyordu. Yeni testler NUL öncesi, sonrası ve NUL sınırını aşan metin/hex eşleşmelerini ve PCAP payload'ını kapsıyor.

## Doğrulama

- `python -m pytest -q tests/test_yara_buffer_text.py tests/test_yara_sigma_coverage.py tests/test_yara_runtime_hex_occurrences.py` — **21 geçti** (47,64 sn).
- `python -m pytest -q tests/test_axiom_scan.py` — **154 geçti** (12,10 sn), somut sonuç tipi entegrasyonundan önce.
- Final değişikliklerden sonra binary scanner, regex-NUL hata yolu, PCAP ve builder regresyonları — **4 geçti** (14,29 sn).
- Final değişikliklerden sonra `python -m pytest -q tests/test_yara_*.py tests/test_axiom_scan.py tests/test_real_yara_engine.py` — **376 geçti** (154,49 sn).
- `python -m pytest -q -rs` — **1370 geçti** (1252,67 sn); bu tam paket, son somut sonuç tipi düzeltmesinden önce çalıştı. Son düzeltmeden sonra ilgili tam YARA/scanner paketi tekrar çalıştırılıp 376/376 geçti.
- `git diff --check` ve `make fmt-check` — temiz.
- İlk push `4fe4d7d` GitHub CI'sinde 4 Python matrix işi self-hosted `axiom-scan` derlemesinde başarısız oldu: `let matches = result.matches` yerel alias'ı array alanını `int` olarak üretti. ASan/UBSan, LLVM/DWARF ve format işleri başarılıydı. Alias kaldırılıp `result.matches` doğrudan kullanıldı.
- Düzeltme sonrası `./bin/axiomc build examples/21_axiom_scan.ax` — başarılı.
- Düzeltme sonrası self-hosted derleme/parity ile YARA/scanner paketi — **378 geçti** (169,14 sn).
- İlk `4fe4d7d` tam koşusu aynı self-hosted kusuru yakaladı; bu koşu düzeltme yapılmadan durduruldu. Düzeltme commit’i `8fe6315` sonrasında `python -m pytest -q -rs` — **1370 geçti, 0 hata, 0 atlandı** (1253,81 sn).
- `8fe6315` GitHub Actions — **7/7 başarılı** (Python 3.10–3.13, ASan/UBSan, LLVM/DWARF, biçim).

## Sınırlar ve riskler

- Regex NUL içeren hedeflerde hâlâ desteklenmiyor; şu an açık hata veriyor. Regex'i buffer uzunluğuyla taramak ve gerçek eşleşme offset/uzunluklarını üretmek ayrı runtime tasarımı gerektiriyor.
- Bu entegrasyon YARA'nın tamamına uyumluluk anlamına gelmez; yalnız belgelenmiş alt kümeyi kapsar.
- `4fe4d7d` CI kusuru giderildi; `8fe6315` için tam yerel paket ve GitHub CI 7/7 başarılı.

## Sıradaki adım

Değişiklikleri commit/push edip CI sonucunu doğrula; ardından G1 içinde regex için byte-span desteğinin maliyetini ve değerini değerlendir. Regex kapsamı şimdilik açık hata ile sınırlı kalmalıdır.


## Devam doğrulaması — runtime sınırları

- `tests/test_yara_runtime_hex_occurrences.py` içinde ortak typed executor'ın `INT64_MAX` üstü byte-span hedef uzunluğunu ve `INT64_MAX` min offset'i güvenli biçimde reddettiği doğrudan C runtime testi eklendi. Bu korumalar offset hesaplamasında signed taşmayı ve hedef belleğine erişmeden reddetmeyi doğrular.
- `python -m pytest -q tests/test_yara_runtime_hex_occurrences.py::test_occurrence_runtime_handles_indices_masks_and_malformed_patterns` — **1 geçti** (1,24 sn).
- `make fmt-check` ve `git diff --check` — temiz.
- Kalan: typed executor için büyük hedefte adversarial çalışma maliyetini ölçüp önceki 64 MiB benchmarkını yeni typed path üzerinde tekrarla.

- 64 MiB typed-executor dense-prefix regresyonu: `python -m pytest -q tests/test_yara_runtime_hex_occurrences.py::test_typed_executor_scans_large_dense_prefix_target` — **1 geçti** (2,83 sn; süre C derlemesini de içerir). Aynı C runtime çağrısının tarama süresi **1,443 sn**, 64 MiB hedefte tek geç occurrence. Fixture'ın tüm hedefi `A`, sondaki tek eşleşme `A [16 × C] B` biçimindedir; bu yoğun prefix tarama kontrolüdür, 999-byte near-match adversarial benchmarkının yerine geçmez.
