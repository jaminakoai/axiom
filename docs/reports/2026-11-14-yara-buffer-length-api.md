# YARA ByteBuffer uzunluk-duyarlı occurrence API'si

**Tarih:** 2026-11-14  
**Kapsam:** G1 hex matcher hedef uzunluğu için temel API  
**Durum:** Runtime ve C/LLVM API doğrulandı; `axiom-scan` entegrasyonu açık

## Yapılan değişiklik

Hex occurrence çekirdeği artık byte pointer ve açık uzunluk alıyor. Eski
string tabanlı fonksiyonlar `strlen` ile aynı eski sözleşmeyi koruyarak çekirdeği
çağırıyor. ByteBuffer handle için count, find, belirli ofsette uzunluk ve nth
occurrence offset/length işlevleri eklendi. C backend, LLVM backend, checker ve
`std/security/yara.ax` bu işlevleri dışarı açıyor.

## Bulunan gerçek hata

`axiom-scan` dosya hedefini `read_file` ile Axiom `str` türüne alıyor.
`axiom_owned_str_wrap` dosya tamponunun uzunluğunu `strlen` ile çıkardığından
gömülü NUL baytında string kısalıyor ve kalan baytlar kayboluyor. Mevcut YARA
hex occurrence işlevleri de string uzunluğunu `strlen` ile buluyor. Bu nedenle
NUL sonrasındaki bir imza mevcut CLI taramasında sessizce kaçabilir.

Bu turda düzeltmenin runtime temel katmanı eklendi; tarayıcı henüz yeni buffer
API'sini kullanmıyor. Dolayısıyla ürün seviyesindeki yanlış negatif riski
devam ediyor ve G1 kapanmış sayılmamalı.

## Doğrulama

| Komut | Sonuç |
|---|---|
| `python -m pytest -q tests/test_yara_runtime_hex_occurrences.py::test_length_aware_occurrence_api_scans_bytes_after_embedded_nul tests/test_yara_runtime_hex_occurrences.py::test_length_aware_yara_buffer_api_has_backend_parity` | **3 passed**, 8.21 s; NUL sonrası offset/length C runtime'da ve C/LLVM Axiom çağrılarında doğrulandı |
| `python -m pytest -q tests/test_yara_runtime_hex_occurrences.py tests/test_yara_runtime_hex_ranges.py tests/test_yara_hex_range_differential.py tests/test_yara_hex_alternation.py tests/test_yara_hex_negation.py` | **118 passed**, 36.44 s |
| `make fmt-check` | Geçti |
| `git diff --check` | Geçti |
| GitHub Actions, `8b2686a` | **7/7 iş başarılı**; Python 3.10–3.13 işlerinin her birinde 1326 passed, 35 skipped, hata yok |

## Sınırlar ve sıradaki iş

- ByteBuffer oluşturma API'si var, ancak dosyayı ByteBuffer'a okuyan stdlib
  fonksiyonu henüz yok.
- Scanner hâlâ `str` hedef kullanıyor; yeni API bu davranışı tek başına
  değiştirmiyor.
- Hex matcher NUL baytları üzerinde uzunluk-duyarlı; text matcher ve regex'in
  binary hedef davranışı henüz ele alınmadı.

Sıradaki iş: dosyayı gerçek uzunluğuyla ByteBuffer'a oku; text aramasını da
length-aware yap; regex'in NUL içeren hedefte destek politikasını belirle;
`axiom-scan`'i buffer yoluna geçir ve NUL öncesi/sonrası/kesişen imzaları YARA
4.5.4 ile karşılaştır.
