# Master roadmap yenileme ve YARA pattern tasarım notu

**Tarih:** 13 Kasım 2026  
**Durum:** G0 doğrulaması tamamlandı; G1'de positional evidence hatası düzeltildi.

**Kod değişikliği:** YARA condition sonucu, pozisyon koşulunun seçtiği eşleşmeyi raporluyor.

## Amaç ve sonuç

`TODO.md` ana ve tek yürütme planı olarak güncellendi. Eski test sayıları,
eski CI koşusu ve tamamlanmış işi sıradaki iş gibi gösteren maddeler düzeltildi.
Sıra artık açık kabul kapılarından oluşuyor: G0 doğrulama, G1 pattern modeli,
G2 gerçek kurallar, G3 dış kullanıcı, G4 platform/dağıtım, G5 sürüm/ekosistem.

G0 tamamlandı. G1 sırasında farklı bir doğruluk kusuru bulundu ve dar kapsamlı
şekilde düzeltildi. Ortak pattern AST henüz uygulanmadı; yeni YARA sözdizimi
eklenmedi.

## G0 doğrulama kanıtı

| Kanıt | Sonuç |
|---|---|
| Commit | `a5a0018d3fdf3ee43f843a4cc65239a553786fb8` |
| Yerel tam test | `python -m pytest -q -rs` — **1297 passed, 0 failed, 0 skipped** |
| Süre | 1205.72 s |
| Önceki hedefli doğrulama | 304 YARA/runtime/self-hosted + 58 LLVM/codegen test geçti |
| GitHub Actions | run `43419634279` — **7/7 jobs success** |

CI matrisi Python 3.10–3.13, ASan/UBSan, LLVM/DWARF ve biçimlendirme işlerini
kapsıyor. Bu kanıt yalnız belirtilen SHA ve Linux yerel ortamı için geçerlidir;
macOS veya gerçek Windows runner sonucu değildir.

## YARA pattern modeli — G1 tasarım notu

### Bugünkü yapı

- `YaraRule.patterns` ve `pattern_names`, aynı indeksle eşlenen iki paralel
  `str[]` dizisidir. `yara_rule_add_pattern` bu public builder biçimini kullanır.
- `yara_rules.ax` kaynak sözdizimini özel `hexrange:`, `hexalt:` ve `hexnot:`
  metin etiketlerine kodlar.
- `yara.ax` bu etiketleri ayrı ayrı tanır ve üç farklı runtime çağrısına
  yönlendirir. `axiom/runtime.h` içinde üç ayrı doğrulayıcı/tarama yolu vardır.
- `yara_condition.ax` da bazı etiketleri ayrıca tanımak zorundadır; örneğin
  `#` sayımının destek dışı olup olmadığını pattern türünden çıkarır.
- Sonuç modeli `YaraMatch` başına tek `offset` ve `matched_len` taşır. Bazı
  türlerde occurrence sayımı açık hata ile reddedilir.

Bu düzen yeni pattern biçimlerinde parser, evaluator, condition kontrolü ve
runtime dispatch'inin birlikte güncellenmesini gerektiriyor. Paralel diziler de
isim/değer indekslerinin eş kalmasına bağlı.

### Önerilen hedef model

1. **Tek bir tipli pattern modeli:** kimlik, pattern türü/flags ve içerik aynı
   kayıtta taşınmalı. YARA hex içeriği sıralı AST olarak temsil edilmeli:
   `Sequence` içinde `Byte(mask/value)`, `Jump(min,max)`, `Alternation(branches)`
   ve `NotByte(mask/value)` atomları. Mevcut wildcard bayt `Byte` atomunun tam
   maskesiz hali olur. Sabit/bounded jump mevcut sınırları korur.
2. **Tek hex parser ve doğrulayıcı:** kaynak konumuyla parse; boş dallar, bozuk
   aralık, sınır taşması, desteklenmeyen iç içe yapı ve resource limit aşımı
   açık hata üretmeli. Kısmi parse veya sessiz düzleştirme yok.
3. **Tek runtime yürütücüsü:** C runtime bir sürümlü, uzunluğu açıkça taşınan
   pattern programını okur. Tür başına ayrı dispatch/tag yerine sequence
   atomlarını yürütür. C99 ve LLVM aynı public/runtime helper'ı kullanmalı.
4. **Uyumluluk geçişi:** `yara_rule_new` ve `yara_rule_add_pattern` imzaları
   korunmalı. Eski düz metin pattern girdileri aynı parser'a girer. Yeni typed
   model önce internal/compiled representation olarak eklenir; doğrudan
   `YaraRule` struct literal kullanan istemciler ve ABI/source compatibility
   etkisi ayrıca ölçülmeden struct değiştirilmez.
5. **Tek doğruluk tablosu:** parser, condition evaluator ve raporlama aynı
   `PatternKind` bilgisini tüketmeli. `#`, `@`, `!`, `at`, `in` davranışları
   tür bazında test edilene kadar sessizce yaklaşık sonuç vermemeli; destek
   dışı ise kaynak konumuyla reddedilmeli.

### Henüz karara bağlanmamış semantik

Tasarım tek başına YARA referans davranışını kanıtlamaz. Aşağıdakiler YARA
4.5.4 ile diferansiyel testlerden önce sabitlenmemeli:

- En erken başlangıçta birden çok match varsa hangi uzunluk/ofset raporlanır?
- Alternation dalları aynı konumda ya da farklı uzunlukta eşleştiğinde seçim
  kuralı nedir?
- Overlap eden occurrence'lar `#`, `@` ve `!` için nasıl sayılır/sıralanır?
- `$a at N` ve `$a in (N..M)` değişken uzunluklu pattern'larda hangi aralık
  sınırlarını uygular?
- `Jump`, `Alternation` ve `NotByte` hangi birleşimlerde ve hangi iç içe
  derinlikte desteklenir?
- Koşul birden fazla pozitif pattern occurrence gerektirdiğinde tek witness
  alanı yeterli mi; rapor tüm occurrence'ları mı, yoksa kural başına tek kanıtı
  mı göstermeli?

## G1 bulgusu: positional condition yanlış occurrence raporluyordu

### Tekrar üretim

YARA 4.5.4'te `{ 41 ( 42 | 44 ) 43 }`, `ABC ADC` hedefi ve `$a at 4` koşulu
offset `4`'teki occurrence ile eşleşir. YARA iki instance'ı `(0, 3)` ve `(4, 3)`
olarak sunar. Axiom kuralı doğru eşleştiriyordu, fakat JSON raporunda ilk
instance'ı, yani `(0, 3)` değerini yazıyordu. `in (...)` ve bounded jump/negation
ile de aynı problem vardı: condition evaluator bir occurrence buluyor, scanner
ise koşuldan bağımsız ilk instance'ı raporluyordu.

### Düzeltme

- `YaraConditionParse` artık koşulun seçtiği pattern kimliğini ve offset'i
  taşıyor.
- `$a at N` ve `$a in (N..M)` arama fonksiyonları boolean yerine bulunan
  occurrence offset'ini condition sonucuna aktarıyor.
- Boolean `and` / `or` birleşimleri true dalın witness'ını koruyor; parantezler
  da witness bilgisini geçiriyor.
- Kural raporu aynı pattern'i tam offset'te tekrar doğrulayıp gerçek eşleşme
  uzunluğunu alıyor. Public `YaraMatch`/builder imzaları değişmedi.
- C ve LLVM backend testleri aynı JSON'u doğruluyor.

Bu düzeltme kural başına tek witness modelini korur. `#`, `@`, `!` ve birden
fazla koşulun ayrı ayrı ihtiyaç duyduğu instance listesini raporlama işi bu
değişikliğin kapsamında değildir.

## G1 diferansiyel semantik matrisi

YARA 4.5.4 ile ek karşılaştırmalar aşağıdaki davranışı sabitledi:

| Durum | Referans YARA | Axiom alt kümesi | Sonuç |
|---|---|---|---|
| Aynı bounded-jump başlangıcında birden çok olası uzunluk (`A1B2B`) | ilk instance `(0, 3)` | `(0, 3)` | aynı en kısa eşleşme |
| Bounded-jump çoklu instance (`A1B A12B`) | `(0,3)`, `(4,4)` | varsayılan rapor ilkini verir; `at/in` ikinciyi seçebilir | aynı koşul davranışı; rapor başına tek kanıt |
| Fixed hex `41 41` ve sabit `[1]` jump, hedefte örtüşme | `#/@/!` koşulları geçerli | sayım/ofset/uzunluk koşulları çalışır | örtüşen sonuçlar eşleşti |
| Alternation farklı başlangıçlarda | `(0,3)`, `(4,3)` | varsayılan rapor `(0,3)` | ilk instance eşit |
| İki alternation dalı aynı offset/uzunlukta (`(4? | ?2)`, `B`) | tek instance `(0,1)` | tek instance `(0,1)` | aynı konum deduplikasyonu |
| Negated-byte çoklu eşleşme | `(0,3)`, `(8,3)` | varsayılan rapor `(0,3)`; `at/in` sonraki occurrence'ı seçebilir | ilk ve seçili witness eşit |
| `#/@/!` + bounded jump/alternation/negation | YARA derler ve sentetik hedefte eşleşir | rules komutu açık hata verir | bilinçli, fail-closed alt küme sınırı |

### Pattern bileşimi sınırı

Parser/regresyon testlerinin tarif ettiği alt küme:

- Tam bayt, `??` ve nibble wildcard'lar sıralı byte dizisinde kullanılabilir.
- Sabit `[N]` (1–64) byte wildcard'lara normalize edilir; bounded jump ile
  birlikte bir pattern'de bulunabilir.
- Bir bounded `[N-M]` aralığı için constrained prefix/suffix gerekir; ikinci
  bounded aralık ve sınırsız jump reddedilir.
- Bir düz alternation 2–4 adet eşit sabit uzunluklu dal taşır; dal başına 1–16
  byte vardır. Sabit jump alternation grubunun dışında olabilir; dal içinde
  jump ve aynı pattern'de bounded jump reddedilir.
- Bir negated byte normal dizinin ve fixed jump'ın yanında olabilir. İkinci
  negation, `~??`, bounded jump ile aynı pattern ve alternation ile aynı pattern
  reddedilir.

Bu sınırlar destek matrisidir; yeni birleşim eklemek için değil, AST geçişinde
regresyonları korumak için kaydedildi.

Bounded jump için koşul aralığı alt/üst sınırlarını da diferansiyel olarak
kontrol ettim: son geçerli dosya başlangıç ofseti kabul ediliyor; `$a in (4..4)`
eşleşmesi ofset 4'te başlatıyor ve eşleşme bitişi 4'ü geçse bile doğru.
Alt/üst dışındaki ofsetler false dönüyor. Sabit `[N]` jump için de tek olası ve
son geçerli başlangıç ofseti `at` ve `in` koşullarıyla doğrulandı; alternation
testleri ofset 0 ile son olası başlangıç, negation testleri ofset 0 ile son
olası eşleşmeyi kapsıyor.

Bu matrisin kapsamı genel YARA uyumluluk iddiası değildir. YARA özel hex
pattern'lerinde occurrence operatörlerini desteklerken Axiom henüz tüm
instance'ları aynı sonuç modelinde temsil etmiyor; bu nedenle sessiz yaklaşık
hesap yerine parse hatası veriyor.

Oracle'dan saptanan hedef davranış occurrence motoru için yeterince somut:
YARA her distinct start offset için bir instance üretir; farklı offset'lerin
eşleşmeleri overlap edebilir ve offset artan sıradadır. Variable-width jump aynı
başlangıçta birkaç geçerli uzunluk bulursa en kısa instance'ı seçer. Aynı
offset'te iki alternation dalı eşleşirse bir instance sayar. Sonraki G1 işi bu
semantiği generic matcher'a taşıyıp bugün fail-closed olan `#/@/!` kullanımını
bounded/alternation/negation türlerinde diferansiyel olarak açmaktır.

### `axiom-scan` schema v1 için rapor sözleşmesi

- `match_count` eşleşen **kural sayısıdır**, pattern occurrence sayısı değildir.
- Her matching rule için `matches` dizisi bir kayıt taşır; kayıt tek bir
  temsilî pattern witness'ı (`pattern`, `offset`, `length`) içerir.
- `$a at N` / `$a in (...)` koşulu varsa witness o koşulu sağlayan
  occurrence'tır. Diğer boolean koşullarda mevcut deterministic seçim korunur.
- Witness alanları tam YARA instance listesi veya bütün condition AST'sinin
  proof trace'i anlamına gelmez. `none of them` gibi pozitif occurrence
  üretmeyen doğru koşullarda offset `-1` olabilir.
- Tüm instance'ları JSON'a eklemek schema v2 tasarımıdır; G3 dış kullanıcı
  doğrulaması kullanım ihtiyacını kanıtlamadan v1'e ek alan/sayı semantiği
  eklenmeyecek.

### Doğrulama

Ön düzeltme regresyon koşusu altı yeni senaryonun tamamında hatayı gösterdi:
`offset 0` raporlandı, beklenen offset bounded jump için 4, alternation için 4,
negation için 8 idi.

| Komut | Sonuç |
|---|---|
| `python -m pytest -q tests/test_axiom_scan.py tests/test_real_yara_engine.py tests/test_yara_fixed_jumps.py tests/test_yara_hex_alternation.py tests/test_yara_hex_negation.py tests/test_yara_hex_range_differential.py tests/test_yara_hex_ranges.py tests/test_yara_modifiers.py tests/test_yara_parser_escapes.py tests/test_yara_regex_safety.py tests/test_yara_runtime_hex_ranges.py tests/test_yara_runtime_hex_validation.py tests/test_yara_sigma_coverage.py tests/test_real_sigma_engine.py` | **315 passed**, 139.76 s |
| Son witness/OR ve C/LLVM parity koşuları | **10 passed**, ardından **2 passed** (son koşuda bir hex senaryosu tekrarlandı; toplam 11 farklı yeni senaryo) |
| G1 occurrence differential grubu | **128 passed**: fixed jumps, bounded ranges, alternation, negation, true/false occurrence conditions, target start bounds ve C/LLVM positional witness |
| Tam güncel paket (`e00c56d`) | `python -m pytest -q -rs` — **1308 passed, 0 failed, 0 skipped**, 1252.41 s |
| `make fmt-check` | geçti |
| GitHub Actions (positional witness düzeltmesi) | run `43433833667` (`e00c56d`) — **7/7 success** |
| GitHub Actions (son occurrence differential test commit'i) | run `43441565454` (`1648283`) — **7/7 success** |

### Uygulama öncesi kabul ölçütleri

- En az birim/runtime ve parser testleri, her AST atomunu ve sınır hatalarını
  kapsar.
- Lisansı ve sürümü sabit YARA 4.5.4 ile benign sentetik hedeflerde sonuç,
  offset, length ve occurrence sayısı karşılaştırılır.
- Her test ya tam eşleşme üretir ya da açık unsupported/parse hatası verir;
  sessiz mismatch sıfır olmalıdır.
- Aralık, toplam pattern uzunluğu, dallanma ve çalışma maliyetine test edilmiş
  sert limitler konur. Taşan boyutlarda integer overflow ve sınırsız tarama
  olmamalıdır.
- C backend ve LLVM aynı test örneklerinde aynı raporu üretir.
- Önceki `hexrange`, `hexalt`, `hexnot`, `??` ve nibble wildcard örnekleri
  geriye dönük regresyon kümesinde kalır.

### G1'de ortak model için önerilen geçiş

Public `YaraRule` alanlarını ve `yara_rule_add_pattern` imzasını koru. Kaynak
pattern parser'ı tek `hexast:v1:` sürümlü ASCII programına normalize etsin; bu
program içte tipli byte/mask, bounded jump, flat alternation ve negation
opkodlarını taşısın. Runtime tek doğrulayıcı ve ortak occurrence yürütücüsü
kullansın; find/count/nth yardımcıları aynı matcher'ın arayüzleri olsun. Mevcut
`hexrange:`, `hexalt:` ve `hexnot:` kodlamaları geçiş sırasında adapter olarak
okunup diferansiyel regresyonlar geçince iç akıştan çıkarılsın.

Mevcut 8 KiB pattern, 64-byte jump, 16-byte range span ve 4×16 alternation
limitleri korunur. Basit fixed-byte desenleri için mevcut hızlı arama generic
matcher içinde bir optimizasyon olarak kalabilir. Resource bütçesi, C runtime
testleri ve gerçek dosya benchmark'ı olmadan genel backtracking ya da
`candidate × atom × gap` taramasına geçilmez. Bu bir geçiş önerisidir; henüz
uygulanmadı.

## Değişen dosyalar

- `std/security/yara_condition.ax`, `std/security/yara.ax`: koşul witness'ını
  sonuçtan rapora taşıma.
- `tests/test_yara_hex_range_differential.py`,
  `tests/test_yara_hex_alternation.py`, `tests/test_yara_hex_negation.py`,
  `tests/test_axiom_scan.py`: YARA diferansiyel ve C/LLVM regressions.
- `TODO.md`: G0 kapandı; G1 ilerlemesi ve kalan kanıt işleri.
- `README.md`, `README.en.md`: son tam koşu ile güncel G1 hedefli koşuyu ayrı
  anlatır.
- `CHANGELOG.md`: düzeltilen rapor kanıtı hatası.

Tam YARA pattern AST'si henüz yapılmadı. Positional witness düzeltmesi ve
occurrence differential test genişletmesinin CI işleri geçti. Kural başına
tek-witness API'sinin kapsamı ve occurrence semantiklerinin tam differential
testi G1'de devam ediyor.

## Sıradaki iş

G1'in sıradaki işi tek-witness rapor sözleşmesinin kullanıcıya sunulma kararını
vermek, kalan target sınırı ve koşul birleşimlerini diferansiyel test etmek,
ardından typed modelin geriye uyumlu API tasarımını kesinleştirmek. Bu kapılar
geçmeden yeni runtime/grammar sözdizimine geçilmez.
