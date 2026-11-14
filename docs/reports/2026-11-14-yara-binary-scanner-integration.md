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

## Sınırlar ve riskler

- Regex NUL içeren hedeflerde hâlâ desteklenmiyor; şu an açık hata veriyor. Regex'i buffer uzunluğuyla taramak ve gerçek eşleşme offset/uzunluklarını üretmek ayrı runtime tasarımı gerektiriyor.
- Bu entegrasyon YARA'nın tamamına uyumluluk anlamına gelmez; yalnız belgelenmiş alt kümeyi kapsar.
- Mevcut çalışma ağacı için GitHub CI henüz çalışmadı. Önceki `d04e0a8` commit'inin CI'si 7/7 başarılıydı.

## Sıradaki adım

Değişiklikleri commit/push edip CI sonucunu doğrula; ardından G1 içinde regex için byte-span desteğinin maliyetini ve değerini değerlendir. Regex kapsamı şimdilik açık hata ile sınırlı kalmalıdır.
