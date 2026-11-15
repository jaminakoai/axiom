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

Selector düzeltmesini, YARA 4.5.4 pinini ve yeni differential/stress testlerini commit/push edip CI sonucunu doğrula. Ardından G1 içinde daha geniş condition/pattern birleşimlerini ve C/LLVM sınır paritesini tamamla. Regex NUL kapsamı şimdilik açık hata ile sınırlı kalmalıdır.


## Devam doğrulaması — runtime sınırları

- `tests/test_yara_runtime_hex_occurrences.py` içinde ortak typed executor'ın `INT64_MAX` üstü byte-span hedef uzunluğunu ve `INT64_MAX` min offset'i güvenli biçimde reddettiği doğrudan C runtime testi eklendi. Bu korumalar offset hesaplamasında signed taşmayı ve hedef belleğine erişmeden reddetmeyi doğrular.
- `python -m pytest -q tests/test_yara_runtime_hex_occurrences.py::test_occurrence_runtime_handles_indices_masks_and_malformed_patterns` — **1 geçti** (1,24 sn).
- `make fmt-check` ve `git diff --check` — temiz.
- Kalan: typed executor için büyük hedefte adversarial çalışma maliyetini ölçüp önceki 64 MiB benchmarkını yeni typed path üzerinde tekrarla.

- 64 MiB typed-executor dense-prefix regresyonu: `python -m pytest -q tests/test_yara_runtime_hex_occurrences.py::test_typed_executor_scans_large_dense_prefix_target` — **1 geçti** (2,83 sn; süre C derlemesini de içerir). Aynı C runtime çağrısının tarama süresi **1,443 sn**, 64 MiB hedefte tek geç occurrence. Fixture'ın tüm hedefi `A`, sondaki tek eşleşme `A [16 × C] B` biçimindedir; bu yoğun prefix tarama kontrolüdür, 999-byte near-match adversarial benchmarkının yerine geçmez.


## G1 paralel doğrulaması — selector semantiği ve typed stress

- Read-only test audit’i kesin bir sessiz yanlış negatif yakaladı: YARA 4.5.4, `2 of ($a*, $a1)` koşulunu `$a1="alpha"`, `$a2="beta"`, hedef `alpha` için true sayıyor; Axiom önce false veriyordu. Nedeni, evaluator'ın selected toplamında selector overlap'i iki sayıp matched toplamında aynı pattern'i yalnız bir saymasıydı. Değerlendirici artık her pattern için eşleşen selector adedini hem toplam hem match count'a ekliyor.
- `tests/test_yara_condition_differential.py` grup overlap, and/or/not önceliği, parantez, `at/in` sınırları ve filesize birleşimini yara-python oracle'ına karşı kapsıyor. `python -m pytest -q tests/test_yara_condition_differential.py` — **13 geçti** (6,95 sn).
- `yara-python==4.5.4` geliştirme bağımlılığına eklendi ve differential fixture sürümü doğruluyor; CI `.[dev]` kurduğu için bu oracle artık CI'da isteğe bağlı skip değildir.
- `tests/test_yara_typed_executor_stress.py` 64 MiB hedefte 999-byte suffix, 16 near-match ve tek geç suffix kuruyor. 17 occurrence doğrulandı; typed runtime ölçümü **1,455 sn**, derleme hariç. Bu önceki rapordaki benchmarkın birebir aynısı değil; benzer typed-AST near-match yüküdür.
- Birleşik YARA/scanner/real-YARA/differential/stress paketi: `python -m pytest -q tests/test_yara_*.py tests/test_axiom_scan.py tests/test_real_yara_engine.py` — **391 geçti** (167,23 sn).
- Selector düzeltmesi sonrası `python -m pytest -q -rs` — **1385 geçti, 0 hata, 0 atlandı** (1265,62 sn). Bu değişiklik henüz commit edilmediğinde alınan sonuçtur; kod değişikliğini içeren yeni CI bekleniyor.


## G1 ikinci paralel turu — CI, selector ve AST limitleri

- CI ajanı `4fa4dcc` GitHub Actions run `43609623527`'yi doğruladı: **7/7 başarılı**. Python 3.10–3.13 işlerinin her birinde `yara-python==4.5.4` kuruldu; her iş 1358 geçti ve 27 genel test skip'i raporladı. YARA oracle koşulları skip olmadı.
- Selector differential ajanı `tests/test_yara_selector_differential.py` ekledi: wildcard/explicit overlap, explicit duplicate selector, any/all/none/N, hedef varyantları ve `at/in`. `python -m pytest -q tests/test_yara_selector_differential.py` — **17 geçti** (7,17 sn); ek mismatch bulunmadı.
- Typed AST limits ajanı `tests/test_yara_typed_ast_limits.py` ekledi: bozuk/eksik opcode, operand, jump, alternation, negation ve 8192-byte encoded text sınırı. 8192 byte kabul edilip kısa hedefte 0 occurrence; 8193 byte encoding açıkça reddediliyor. Hedefli test — **1 geçti** (1,50 sn).
- Birleşik son YARA/scanner/differential/stress/AST-limits paketi: `python -m pytest -q tests/test_yara_*.py tests/test_axiom_scan.py tests/test_real_yara_engine.py` — **409 geçti** (174,73 sn).
- Tam yerel paket: `python -m pytest -q -rs` — **1403 geçti, 0 hata, 0 atlandı** (1273,68 sn).
- `make fmt-check` ve `git diff --check` — temiz. Yeni test dosyaları ve güncel rapor bu tur commit’ine dahil edilecek; yeni commit için CI push sonrası doğrulanmalı.


## G1 üçüncü paralel turu — koşul birleşimleri ve backend sınır paritesi

- CI denetimi: `20d3fa6` run `43618282310` **7/7 başarılı**; Python 3.10–3.13’te `yara-python==4.5.4` kuruldu ve her matrix 1376 geçti / 27 genel testi atladı.
- `tests/test_yara_condition_combinations.py`: 19 YARA 4.5.4 differential vaka; zero-of, any/all/none, `them`/wildcard grupları, filesize, Boolean/not ve inclusive `at/in` sınırları. Tekil koşu 19/19 geçti; birleşik son pakette de geçti.
- `tests/test_yara_condition_backend_parity.py`: embedded-NUL hedefte text/hex occurrence ve offset sınırları, filesize ve koşul birleşimleri için C/LLVM rapor eşitliği + YARA oracle. 1/1 geçti (13,29 sn).
- Son birleşik odaklı paket: `python -m pytest -q tests/test_yara_*.py tests/test_axiom_scan.py tests/test_real_yara_engine.py` — **429 geçti** (212,34 sn).
- Son tam yerel paket: `python -m pytest -q -rs` — **1423 geçti, 0 hata, 0 atlandı** (1322,14 sn).
- `20d3fa6` CI, bu turdaki iki yeni test dosyası eklenmeden önce 7/7 başarılıydı. Yeni test commit’inin CI’si push sonrasında doğrulanmalı.


## G1 dördüncü paralel turu — typed hex ve text buffer edge’leri

- CI ajanı `3c5668e` run `43634432087` **7/7 başarılı** olarak doğruladı; Python 3.10–3.13’te her job 1396 geçti / 27 genel ortam skip’i raporladı.
- `tests/test_yara_hex_typed_differential.py`: 12 YARA 4.5.4 karşılaştırması; alternation öncesi/sonrası sabit gap, wrong-gap near miss, çoklu occurrence ve `#/@/!`. **12 geçti**, mismatch yok.
- `tests/test_yara_text_buffer_edges.py`: 6 YARA 4.5.4 karşılaştırması; NUL/yüksek-byte sınırları, `nocase`, `fullword`, overlap count/offset ve UTF-8 prefix sonrası byte offset’i. **6 geçti**, mismatch yok.
- Son birleşik odaklı paket: `python -m pytest -q tests/test_yara_*.py tests/test_axiom_scan.py tests/test_real_yara_engine.py` — **447 geçti** (237,45 sn).
- Son tam yerel paket: `python -m pytest -q -rs` — **1441 geçti, 0 hata, 0 atlandı** (1343,27 sn).
- `git diff --check` ve `make fmt-check` temiz. Yeni test dosyaları için CI, commit push sonrasında doğrulanmalı.


## G1 beşinci paralel turu — binary condition ve parser yapısı

- `tests/test_yara_binary_condition_differential.py`: 14 YARA 4.5.4 oracle vakası; embedded-NUL binary pattern, `#a`, `@a[i]`, `!a[i]`, `at/in`, filesize ve boolean birleşimleri. **14/14 geçti**.
- `tests/test_yara_parser_structure_differential.py`: metadata/tags ve satır sonu yorumları için 1 vaka; literal ve modifier davranışı için 3 vaka. **4/4 geçti**. İki yeni test dosyası birlikte **18/18 geçti**.
- Test tasarımı sırasında YARA’nın kabul ettiği `rule Inline { strings: ... condition: ... }` biçiminin Axiom’da `gecersiz rule etiketi` hatasıyla reddedildiği bulundu. Kök neden parser’ın satır tabanlı olması; yalnızca etiket kontrolünü değiştirmek sonraki bölümlerin/kapama ayrıştırmasının sorununu çözmez. Bozuk olabilecek bir normalizasyon eklenmedi. Inline tek satırlık kural biçimi mevcut destek sınırı olarak kaydedildi.
- Birleşik odaklı paket: `python -m pytest -q tests/test_yara_*.py tests/test_axiom_scan.py tests/test_real_yara_engine.py` — **465 geçti** (232,78 sn).
- Tam yerel paket: `python -m pytest -q -rs` — **1459 geçti, 0 hata, 0 atlandı** (1336,18 sn).
- Önceki commit `fe36b31`, GitHub Actions run `43688747130` **7/7 başarılı**; her Python 3.10–3.13 işi 1414 geçti/27 genel ortam testi skip etti ve 55 doküman testi geçti. Bu run yeni 18 test eklenmeden önce oluştu; yeni değişikliklerin CI sonucu commit/push sonrasında doğrulanmalı.
- `git diff --check` ve `make fmt-check` bu rapor güncellemesinden sonra tekrar çalıştırılacak.
- G1 açık: daha geniş pattern/condition birleşimleri ve parser’ın tek satırlı yapı sınırı için çalışma devam etmeli.


## G1 altıncı paralel turu — integer ve bounded-jump occurrence sınırları

- Koşul denetim ajanı dört YARA 4.5.4 vakası önerdi: `0x` sayılarının `#a`, `filesize`, `@a[i]`, `at/in` içinde kullanımı; embedded-NUL binary hedeflerle eşleşmeler. `tests/test_yara_binary_condition_differential.py` bu dört vakayla genişletildi ve hedefli koşu geçti.
- Hex denetim ajanı bounded jump + embedded NUL, bounded jump + overlap ve aynı başlangıçta en kısa geçerli instance seçimlerini doğruladı. `tests/test_yara_hex_typed_differential.py` beş vaka ile genişletildi; YARA oracle instance ofseti/uzunluğu ve Axiom witness sonucu karşılaştırıldı.
- İki test grubundaki yeni vakalar **9/9 geçti**; hedefli birleşik iki dosya **35 geçti** (14,42 sn).
- Birleşik odaklı YARA/scanner paketi: `python -m pytest -q tests/test_yara_*.py tests/test_axiom_scan.py tests/test_real_yara_engine.py` — **474 geçti** (230,29 sn).
- Tam yerel paket: `python -m pytest -q -rs` — **1468 geçti, 0 hata, 0 atlandı** (1345,33 sn).
- Son commit `0aff466`, GitHub Actions run `43691677198` **7/7 başarılı**; Python 3.10–3.13’de her iş 1432 geçti/27 genel ortam testi skip etti, doküman blokları 55 geçti. Bu turdaki 9 yeni test henüz CI’da değil; sonraki push sonrası doğrulanmalı.
- README/doküman kontrolü: `python -m pytest -q tests/test_docs_en.py tests/test_docgen.py` — **25 geçti** (11,42 sn).
- `git diff --check` ve `make fmt-check` — temiz.
- G1 açık: desteklenen YARA davranışları için geniş diferansiyel kanıt, parser sınırları ve runtime maliyet limitleri tamamlanmalı.


## G1 yedinci paralel turu — negated range ve boş hedef

- Condition denetim ajanı `not $a at 0`, `not $a in (0..0)` ve `filesize == 0 and #a == 0` için üç vaka önerdi. Bunlar binary pattern ve sıfır baytlı target ile `tests/test_yara_binary_condition_differential.py` içine eklendi; `yara-python==4.5.4` oracle ile **3/3 geçti**.
- Hedefli condition dosyası **21 geçti** (8,99 sn); birleşik YARA/scanner paketi **477 geçti** (231,34 sn).
- Tam yerel paket: `python -m pytest -q -rs` — **1471 geçti, 0 hata, 0 atlandı** (1353,33 sn).
- Önceki commit `3a6b42c`, GitHub Actions run `43700896871` **7/7 başarılı**; her Python 3.10–3.13 işi 1441 geçti/27 genel ortam skip’i verdi, doküman testleri 55 geçti. Bu turdaki 3 yeni test henüz CI’da değil.
- G1 açık: test kapsamı genişletiliyor; bilinen inline-rule parser sınırı ve runtime bütçeleri kapatılmadı.


## G1 sekizinci paralel turu — mask/jump birleşimi ve fail-closed koşul

- Hex denetim ajanı `4? [0-1] ?2` pattern’ini üç hedefte doğruladı: nibble wildcard + bounded jump + embedded NUL eşleşmesi, sıfır uzunluklu jump eşleşmesi ve yanlış nibble near-miss. YARA 4.5.4 instance offset/length değerleri Axiom ile aynı; üç vaka eklendi.
- Condition denetimi YARA’nın kabul ettiği negatif sayı (`filesize > -1`) sözdiziminin Axiom alt kümesinde desteklenmediğini not etti. Sessiz yanlış karar olmaması için mevcut unsupported-condition ret testine bu koşul eklendi.
- Bu turdaki dört yeni test **4/4 geçti**; hedefli test dosyaları **23 geçti** (15,42 sn).
- Birleşik YARA/scanner paketi: **481 geçti** (224,32 sn). Tam yerel paket: **1475 geçti, 0 hata, 0 atlandı** (1349,95 sn).
- Önceki commit `25dd23a`, GitHub Actions run `43704119797` **7/7 başarılı**; Python 3.10–3.13’de her iş 1444 geçti/27 genel ortam testi atladı, doküman testleri 55 geçti. Bu turdaki dört test CI’da henüz çalışmadı.
- G1 açık: yeni testler ve açık kapsam retleri devam ediyor; tek satırlı kural parser desteği ve runtime limit bütçeleri hâlâ çözülmedi.


## G1 dokuzuncu paralel turu — backend parity ve numeric metadata

- C/LLVM parity denetimi `$a = { 4? [0-1] ?2 }`, embedded-NUL hedef ve `#a/@a[i]/!a[i]` koşullarını doğruladı. YARA 4.5.4 iki instance `(0,3),(3,2)` buluyor; C ve LLVM aynı match count ve schema v1 witness raporunu verdi. `tests/test_yara_condition_backend_parity.py` içine test eklendi.
- Parser metadata denetimi `meta` içindeki negatif decimal `-7` ve hex `0x2A` değerlerinin YARA ile aynı şekilde JSON’da `-7` ve `42` raporlandığını doğruladı; `tests/test_yara_parser_structure_differential.py` içine test eklendi.
- Yeni iki test birlikte **2/2 geçti**; iki hedefli dosya **7 geçti** (18,14 sn).
- Birleşik YARA/scanner paketi **483 geçti** (223,16 sn); tam yerel paket **1477 geçti, 0 hata/skip** (1338,52 sn).
- Önceki commit `4098a19`, CI run `43706653949` **7/7 başarılı**; Python 3.10–3.13’de her biri 1448 geçti/27 genel ortam testi atladı, doküman testleri 55 geçti. Bu turdaki iki yeni test henüz CI’da değil.
- G1 açık kalıyor; bilinen tek satırlı rule parser sınırı, daha geniş destek matrisi ve runtime limit kanıtları sonraki işlerde ele alınacak.


## G1 onuncu paralel turu — modifier occurrence ve negated group offset

- Modifier denetim ajanı `$a = "aba" nocase fullword`, `#a == 2 and @a[2] == 5 and !a[2] == 3` koşulunu yüksek byte/NUL içeren hedefte doğruladı. YARA 4.5.4 iki instance `(1,3),(5,3)` buluyor; Axiom aynı sayıyı ve byte witness offset/length’ini raporluyor. `tests/test_yara_text_buffer_edges.py` içine eklendi.
- Condition denetim ajanı unary `not` altında doğrudan `at` suffix’i olan selector grubunu doğruladı: offset 0 için true, offset 6 için false. İki YARA 4.5.4 vakası `tests/test_yara_condition_combinations.py` içine eklendi.
- Yeni vakalar **3/3 geçti**; iki hedefli dosya **28 geçti** (13,86 sn).
- Birleşik YARA/scanner paketi **486 geçti** (232,88 sn); tam yerel paket **1480 geçti, 0 hata, 0 atlandı** (1486,83 sn).
- Önceki commit `342b21d`, GitHub Actions run `43710390385` **7/7 başarılı**; Python 3.10–3.13’de her iş 1450 geçti/27 genel ortam testi atladı, doküman testleri 55 geçti. Bu turdaki 3 test henüz CI’da değil.
- G1 açık: geniş diferansiyel kanıt ve bilinen multiline parser kısıtları/runtime limit çalışmaları sürüyor.


## G1 on birinci paralel turu — escaped metadata ve alternation parity

- Parser ajanı escaped metadata değerlerini doğruladı: quote (`\"`), Windows path backslash’ları ve `\n` newline metadata’sı YARA 4.5.4 ile aynı JSON değerlerine çözülüyor. `tests/test_yara_parser_structure_differential.py` içine eklendi.
- Runtime ajanı `{ 4? ( 42 | 44 ) [1] 45 }` pattern’ini NUL içeren hedefte `#/@/!` koşullarıyla doğruladı. YARA iki instance `(0,4),(4,4)` buluyor; C ve LLVM raporları eşit. `tests/test_yara_condition_backend_parity.py` içine eklendi.
- İki hedefli dosya **9 geçti** (18,12 sn); yeni vakalar **2/2 geçti**.
- Birleşik YARA/scanner paketi **488 geçti** (222,70 sn); tam yerel paket **1482 geçti, 0 hata/skip** (1345,34 sn).
- Önceki commit `b923830`, GitHub Actions run `43727336970` **7/7 başarılı**; her Python 3.10–3.13 işi 1453 geçti/27 genel ortam testi atladı, doküman testleri 55 geçti. Bu turdaki iki test henüz CI’da çalışmadı.
- G1 açık: test kapsamı, parser layout sınırları ve runtime limit kanıtları devam ediyor.


## G1 on ikinci paralel turu — selector overlap ve NUL/negation

- Condition denetim ajanı `2 of ($a*, $a1) at 6` koşulunu doğruladı: overlap sayımı offset suffix’iyle birlikte YARA 4.5.4 ve Axiom’da true. `tests/test_yara_condition_combinations.py` içine diferansiyel vaka eklendi.
- Hex denetim ajanı `{ 41 00 ~42 44 }` pattern’ini embedded-NUL hedefte doğruladı: YARA instance’ları `(0,4),(8,4)`; orta aday negated byte nedeniyle eleniyor. `#a/@a[i]/!a[i]` koşullarıyla Axiom witness sonucu YARA ile aynı. `tests/test_yara_hex_typed_differential.py` içine eklendi.
- İki yeni vaka ve hedefli test dosyaları **43/43 geçti** (13,92 sn). Birleşik YARA/scanner paketi **490 geçti** (225,68 sn), tam yerel paket **1484 geçti, 0 hata/skip** (1348,87 sn).
- Önceki commit `a4f3166`, CI run `43738079067` **7/7 başarılı**; Python 3.10–3.13 her biri 1455 geçti/27 genel ortam testi atladı; doküman blokları 55 geçti. Bu turdaki iki yeni test henüz CI’da değil.
- G1 açık: diferansiyel kapsam genişletiliyor; YARA parser’ın bilinen tek satırlı rule sınırı ve runtime limit kanıtları sürüyor.


## G1 on üçüncü tur — signed alt sınır

- G1 runtime denetimi doğrudan occurrence C harness’inde `INT64_MIN` için min offset ve max offset ret kanıtının eksik olduğunu buldu. `tests/test_yara_runtime_hex_occurrences.py` içine iki kontrol eklendi: her iki giriş de `-1` sentinel’inden ayrı değerlendirilip offset aritmetiği yapılmadan `-1` olarak reddediliyor.
- Hedefli runtime testi: **1 geçti** (1,24 sn). Birleşik YARA/scanner paketi **490 geçti** (223,89 sn); tam yerel paket **1484 geçti, 0 hata/skip** (1344,44 sn).
- Önceki commit `058484e`, CI run `43742268638` **7/7 başarılı**; Python 3.10–3.13 her biri 1457 geçti/27 genel ortam testi atladı, doküman testleri 55 geçti. `INT64_MIN` eklemesi bu CI koşusundan sonra geldi.
- G2 için paralel denetim, Trellix Yara-Rules Apache-2.0 sabit kaynaklı corpus önerisi hazırladı; G1 kapısı kapanmadan G2 uygulamasına geçilmedi.
