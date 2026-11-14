# NUL korumalı ByteBuffer dosya okuma

**Tarih:** 2026-11-14  
**Kapsam:** Binary hedefleri uzunluğu koruyarak okuma altyapısı  
**Durum:** Stdlib/runtime ve C/LLVM doğrulandı; `axiom-scan` entegrasyonu açık

## Yapılan değişiklik

Runtime'a `axiom_buf_read_file` eklendi. Dosya akışını 4096 baytlık
ByteBuffer'a okur, kapasiteyi taşma kontrolleriyle büyütür ve NUL baytlarını
string terminatörü saymaz. I/O, allocation veya temsil edilebilir uzunluk
hatasında buffer serbest bırakılır ve `0` döner.

`std/io/binary.read_file_bytes(path)` bunu `Result<int, str>` olarak sunar.
Başarılı boş dosya `len=0` buffer handle'ı verir; boş yol veya okuma hatası
`Err` döndürür. C backend ve LLVM runtime bağlantıları eklendi.

## Doğrulama

| Komut | Sonuç |
|---|---|
| `python -m pytest -q tests/test_yara_runtime_hex_occurrences.py::test_length_aware_yara_buffer_api_has_backend_parity` | **2 passed**, 7.01 s; C ve LLVM 4097 baytlık NUL içeren dosyayı okudu, gerçek uzunluğu, NUL sonrası offset'i ve NUL üzerinden geçen eşleşmeyi doğruladı; boş dosya ve boş yol da kapsandı |
| `python -m pytest -q tests/test_io_file_result_api.py tests/test_yara_runtime_hex_occurrences.py::test_length_aware_yara_buffer_api_has_backend_parity` | **14 passed**, 30.13 s |
| `git diff --check` | Geçti |
| `make fmt-check` | Geçti |

## Sınırlar ve sıradaki iş

- `axiom-scan` hâlâ `read_file` ve `str` hedefleriyle tarama yapıyor; bu nedenle
  kullanıcıya dönük NUL sonrası yanlış negatif sorunu henüz giderilmedi.
- Runtime buffer okuyucu akışla büyür; gerçek dosya boyutunu ve NUL baytlarını
  korur. Bu adım regex veya text pattern'leri buffer üzerinden yürütmüyor.
- Sırada ruleset taramasını buffer handle'a taşımak, text matcher'a açık hedef
  uzunluğu vermek ve embedded-NUL hedefte regex için açık hata/politika
  belirlemek var. Sonra `axiom-scan` fixture'ları YARA 4.5.4 ile karşılaştırılmalı.
