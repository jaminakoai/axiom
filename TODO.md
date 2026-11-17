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
| Son güncelleme | 2026-11-17 |
| Aşama | **Alfa sağlamlaştırma — kullanıcı doğrulaması ve YARA alt kümesi doğruluğu** |
| Son tamamlanmış tam test paketi | GitHub Actions `52544da`: Python 3.10–3.13'te her biri 1558 geçti / 27 skip, doküman blokları 55 geçti; [run 43987784851](https://github.com/jaminakoai/axiom/actions/runs/43987784851), **7/7 başarılı** |
| Son CI denemesi | `52544da` [run 43987784851](https://github.com/jaminakoai/axiom/actions/runs/43987784851), **7/7 başarılı** |
| Son başarılı tam CI | `52544da` [run 43987784851](https://github.com/jaminakoai/axiom/actions/runs/43987784851), **7/7 başarılı** |
| Son platform smoke | `52544da`, native build/run, cache/file URL, süreçler arası kilit ve imzalı index doğrulaması Linux/Windows/macOS run 43987784833 **3/3 başarılı** |
| CI skip açıklaması | 27 skip Linux CI'da MinGW (16) ve Wine (11) bulunmamasından. Yerel `tests/test_portability.py`: ikisi de kurulu ortamda **34 geçti, 0 skip** (100,70 sn). |
| Son G1 hedefli doğrulama | YARA/scanner/differential/stress/AST limits/C-LLVM parity: **490 geçti, 0 skip** (224,36 sn) |
| Son kaydedilmiş başarılı CI | `52544da` — [run 43987784851](https://github.com/jaminakoai/axiom/actions/runs/43987784851), **7/7 başarılı** |
| Son tam yerel test paketi | `23a0aca`: **1565 geçti, 0 başarısız** (1331,91 sn); aynı commit için GitHub CI **7/7 başarılı** |

---

## AKTİF MASTER ROADMAP — HER TURDA ÖNCE BURAYI UYGULA

Bu bölüm **şu anki yürütme sırasıdır**. Aşağıdaki P1/P2 tabloları bitmiş işlerin
kanıtını ve daha geniş ürün yönünü korur; burada daha güncel durum varsa aktif
roadmap geçerlidir. Başka TODO dosyası açılmaz.

### Mevcut konum ve ilerleme tahmini

- Axiom'ın derleyici, iki arka uç, standart kütüphane, paket altyapısı ve
  `axiom-scan`/DFIR örnekleri mevcut. G0, G1 ve G2 tamamlandı. Genel G4 platform
  smoke daha önce üç işletim sisteminde geçti; yeni PCAP özel smoke Windows'ta
  heap corruption açığa çıkardı ve düzeltme doğrulaması sürüyor.
- Faz 1'in dış kullanıcı kapısı **açılmadı**: `axiom-scan`'i kendi verisinde
  deneyip geri bildirim vermiş bağımsız kullanıcı henüz belgelenmedi.
- Registry için bir kaynak örneği (`packages/axiom-scan-report`) ve yerel imzalı
  paket hazırlama akışı var; resmi paket yayımlanmış değil. Yükleme yolu ve resmi
  imza anahtarı işletimi hâlâ belirlenmeli. Varsayılan registry alan adı henüz
  dağıtılmadı; doküman bunu açıkça belirtiyor ve çalışan yerel `file://` akışını gösteriyor.
- Registry istemci incelemesinde imzalı tarball'ın `axiom.toml` kimliğinin
  imzasız index metadata'sına bağlanmadığı bulundu. İstemci doğrulaması ve
  regresyon kanıtı eklendi. Ayrı anahtarlı imzalı schema 2 index ve gözlemlenmiş
  sequence rollback kontrolü de eklendi; ilk kullanım/yerel state silinmesi
  sınırı ile üretim anahtarı ve hosting kararı açık kapıdır:
  [G4 metadata binding raporu](docs/reports/2026-11-16-registry-index-metadata-binding.md).
- Son dört YARA commit'i sabit jump, bounded jump, sınırlı alternation ve bir
  negated byte ekledi. Bunlar belgelenmiş bir alt kümedir; tam YARA uyumluluğu
  iddiası değildir.
- G1 kapandı: YARA 4.5.4 differential, C/LLVM parity, runtime limit kontrolleri
  ve bounded stress eşiği geçti; `53839c3` CI 7/7 başarılı. Tam YARA uyumluluğu
  değildir.
- İlk güvenilir public release hedefine göre yaklaşık **%75** ilerleme tahmini
  kullanılıyor. Bu ölçülmüş KPI değildir. G2 gerçek kural corpus'u kapandı;
  önceki genel platform smoke geçti, fakat PCAP özel Windows smoke şu anda
  başarısız olduğundan ilgili G4 maddesi açık. G3 bağımsız kullanıcı kanıtı ve
  G4 resmi örnek paket yayını da açık. Yüzde kaba milestone tahminidir;
  kullanıcı geri bildirimi ve yayın altyapısı süresini öngörmez.

### İş sırası ve kabul kapıları

#### G0 — Güncel ve güvenilir başlangıç noktası `[x]` — 13 Kasım 2026 tamamlandı

- [x] `python -m pytest -q -rs` komutunu güncel `master` üzerinde çalıştır;
  toplam geçti/hata/skip sayısını ve commit SHA'yı kaydet.
- [x] Hata/skip triage: tam koşuda başarısızlık ve skip yoktu; yeni hata
  sınıflandırması gerekmemedi.
- [x] `a5a0018` sonrası GitHub Actions sonucunu doğrula: `gh run view
  43419634279 --repo jaminakoai/axiom`; 7/7 job başarılı. CI tam test paketini
  Python 3.10–3.13 ve sanitizer/LLVM/DWARF işlerinde çalıştırdı.
- [x] Aynı commit için yerel tam test paketini koşup CI sonucundan ayrı kaydet:
  `a5a0018`, 1297 geçti / 0 başarısız / 0 atlandı, 1205.72 s.
- [x] `README.md`, `README.en.md`, `CHANGELOG.md` ve bu dosyadaki test/özellik
  durumlarının birbirini tuttuğunu denetle.
- **Kapı:** güncel test sonucu biliniyor; hata ve skip'ler açıklanmış; README ile
  kod arasındaki özellik iddiaları eşleşiyor.

#### G1 — YARA alt kümesini tek bir güvenilir modele taşı `[x]` — 15 Kasım 2026 kapandı

Mevcut `hexrange:`, `hexalt:` ve `hexnot:` dahili etiketleri ayrı özel yollar
oluşturdu. Yeni sözdizimi eklemeden önce bu temsili gözden geçir.

- [x] Başlangıç tasarım notu: [YARA pattern AST/modeli ve G1 tasarım kararı](docs/reports/2026-11-13-master-roadmap-refresh.md#yara-pattern-modeli-g1-tasarim-notu).
- [x] `$a at N` / `$a in (...)` kuralı daha sonraki bir occurrence ile
  sağlandığında raporda koşulu sağlayan occurrence'ın offset/uzunluğunu ver;
  range/alternation/negation ve C/LLVM için regresyon ekle.
- [x] Diferansiyel testlerle kalan eşleşme/ofset/uzunluk ve alternatif eşitlik
  semantiğini kesinleştir; selector-overlap, boolean precedence/parantez, filesize
  birleşimi ve group at/in için YARA 4.5.4 oracle testleri eklendi (13 geçti).
  `yara-python==4.5.4` dev bağımlılığıyla oracle CI testlerinin atlanmaması sağlandı;
  daha geniş condition/pattern birleşimleri, occurrence sınırları ve ret durumları
  için ek kanıt eklendi; son hedefli paket 490 geçti, oracle skip olmadı.
- [x] `axiom-scan` schema v1 kanıt kapsamını belirle: `matches` ve
  `match_count` kural başına kalır; her eşleşen kural için tek bir temsilî
  witness döner. `at/in` varsa koşulun seçtiği occurrence raporlanır. Bu alanlar
  tam YARA instance listesi veya koşulun tüm mantıksal kanıt ağacı değildir;
  tam instance listesi ancak schema v2 tasarımı ve dış kullanıcı doğrulamasında
  ihtiyaç kanıtlanırsa eklenir.
- [x] YARA 4.5.4'e göre destek matrisini belirle ve özel hex türlerinde
  `#/@/!` occurrence semantiğini diferansiyel testlerle doğrula:

  | Pattern türü | `$a at N` / `$a in (...)` | `#a` / `@a[i]` / `!a[i]` |
  |---|---|---|
  | Metin + desteklenen modifier'lar | desteklenir | desteklenir |
  | Sabit hex, wildcard, `[N]` | desteklenir | desteklenir; overlap sayılır |
  | Bounded `[N-M]` jump | desteklenir; seçilen occurrence raporlanır | overlap sayılır; aynı başlangıçta en kısa geçerli instance |
  | Tek düz, eşit uzunluklu alternation | desteklenir; aynı başlangıç tek instance | aynı offset'teki dallar bir instance sayılır |
  | Tek negated byte | desteklenir; seçilen occurrence raporlanır | overlap sayılır |
  | Regex | açık hata | açık hata |

  Bu davranış YARA 4.5.4 ile diferansiyel test edilir; regex için occurrence
  metadata'sı bulunmadığından ilgili koşullar fail-closed olarak reddedilir.
- [x] Sabit hex, bounded jump, alternation ve negation için find/count/nth
  çağrılarını aynı runtime occurrence yürütücüsüne bağla; offset sınırlarını
  tek API'de uygula ve seçilen offset'in canonical uzunluğunu ortak API'den al.
  Eski `hexrange:`/`hexalt:`/`hexnot:` etiketleri AST geçişi bitene kadar parser
  ile runtime arasındaki geçici uyumluluk kodlamalarıdır.
- [x] Bir pattern AST/modeli kullanıp özel `hex*:` string etiketlerinin
  çoğalmasını durdur; geçişte mevcut public fonksiyon imzalarını koru veya
  gerekiyorsa uyumluluk katmanı ekle. Parser artık byte/mask, bounded jump,
  alternation ve negation atomlarını `hexast:v1:` programına yazar. Runtime bu
  programı fail-closed doğrulayıp `AxiomYaraHexAtom[]` dizisine parse eder. Tek
  occurrence executor Byte/Jump/Alternation/NotByte atomlarını sıralı yürütür;
  eski doğrudan runtime API'leri aynı modele çeviren legacy adapter olarak kalır.

  **G1 geçiş tasarımı:** `YaraRule` alanlarını ve `yara_rule_add_pattern`
  imzasını koru; kaynak pattern'i parser aşamasında `hexast:v1:` adlı tek,
  sürümlü ASCII programına normalize et. Programın byte/mask, bounded jump,
  flat alternation ve negated-byte opkodları uzunlukla sınırlandırılmış olsun.
  C runtime'da tek doğrulayıcı/yürütücü; find/count/nth API'leri aynı
  occurrence motorunu kullansın. Mevcut `hexrange:`/`hexalt:`/`hexnot:`
  kodlamaları geçiş testlerinde adapter olarak okunup sonra iç akıştan kaldırılsın.
  Tek `Byte/Jump/Alternation/NotByte` atom dizisi executor'ı tamamlandı. Eski
  `find_hex_range/alternation/negation` giriş noktaları artık bu ortak executor'a
  yönleniyor; `hexrange:`/`hexalt:`/`hexnot:` doğrudan girdi biçimleri parse
  adapter'ı olarak destekleniyor. Parse edilmiş range/negation `match_at`
  yardımcıları da typed atom matcher'ına yönlendirildi. Tür-özel parser ve
  anchor yardımcıları hâlâ adapter/optimizasyon olarak kullanılıyor; kaldırma
  öncesi kalan doğrudan runtime erişimleri ve limit/oracle kanıtları denetlenmeli.
  Mevcut sınırlar (`8 KiB`, jump 64, span 16, alternation 4×16) korunmalı;
  parser/overflow/bozuk bytecode doğrudan runtime testleriyle fail-closed
  doğrulanmalı. `INT64_MIN` min/max offset de doğrudan C runtime testinde
  `-1` sentinel değerinden ayrı olarak açıkça reddedildi. Basit sabit byte dizileri için mevcut hızlı arama yolu generic
  API içinde optimizasyon olarak korunabilir. 64 MiB/999-byte suffix near-match
  fixture'ı için ölçülen runtime bütçesi 15 sn olarak belirlendi ve CI regression
  assertion'ı ile uygulanıyor; bu sınır yalnız tarifli fixture için geçerlidir.
  Genel kod yolu hedefe göre sınırsız `candidate × atom × gap` taramasına
  bırakılmaz.
- [x] Ortak occurrence yürütücüsüyle `#/@/!` desteğini bounded jump,
  alternation ve negation için aç. YARA oracle'ına göre her
  başlangıç offset'i en çok bir instance üretir, farklı başlangıçlar overlap
  edebilir, sıralama offset'e göredir; bounded jump'ta aynı başlangıçta en kısa
  geçerli instance seçilir; aynı offset'te birden çok alternation dalı tek
  instance sayılır. `#` bu instance sayısını, `@a[i]` 1 tabanlı occurrence'ın
  sıfır tabanlı offset'ini, `!a[i]` eşleşme uzunluğunu döndürür. `axiom-scan`
  schema v1 yine kural başına tek temsilî witness taşır.
- [x] Ortak occurrence yürütücüsünün çalışma maliyetini büyük hedefte ölç ve
  kabul edilen hex alt kümesi için benchmark kanıtı ekle: standart 64 MiB
  bounded/alt/neg occurrence sayımı sırasıyla 0.141/0.437/0.010 sn; bounded `[0-16]`
  uzun-suffix yakın-eşleşme testi 64 MiB'de 17 occurrence'ı 1.321 sn'de saydı.
  Bounded range için geçici anchor bitset'i en çok hedef boyutunun 1/8'i kadar
  ek bellek tutar.
- [x] Mevcut desteklenen biçimlerin birleşimini ve ret sınırlarını belirle:
  normal bayt/nibble wildcard, sabit ve bounded jump, alternation, negation.

  | Yapı | Kabul edilen alt küme | Açık ret sınırı |
  |---|---|---|
  | Bayt dizisi | tam bayt, `??`, nibble wildcard | bozuk/tek nibble token |
  | Sabit jump `[N]` | 1–64 bayt; diziye wildcard olarak eklenir | sıfır veya limit üstü |
  | Bounded jump `[N-M]` | tek aralık; en çok 64, genişliği en çok 16; constrained prefix/suffix | ikinci aralık, bozuk/sınırsız aralık |
  | Alternation `( ... \| ... )` | tek düz grup, 2–4 dal, her dal 1–16 sabit uzunluklu tam/nibble byte; sabit jump grup dışında olabilir | iç içe/ikinci grup, dal içinde jump, bounded jump ile aynı kalıp |
  | Negation `~HH` / `~?H` / `~H?` | tek negated byte; sabit jump ve sıradan byte dizisiyle birleşebilir | ikinci negation, `~??`, bounded jump veya alternation ile aynı kalıp |

  Bu tablo parser testlerinin tarif ettiği mevcut alt kümeyi kaydeder; YARA'nın
  tamamı için uyumluluk iddiası değildir ve AST geçişinde regresyon testleriyle
  korunmalıdır.
- [x] `#a`, `@a[i]`, `!a[i]`, `$a at N` ve `$a in (N..M)` için her pattern
  türünün davranış tablosunu yaz; özel hex occurrence operatörlerini YARA ile
  karşılaştırmalı test et. Matris yukarıda.
- [x] YARA 4.5.4 diferansiyel testleri:
  bounded jump uzunluk seçimi, çoklu/örtüşen fixed pattern'ler, aynı başlangıçta
  eşleşen alternation dalları, bounded/alternation/negation `#/@/!`, positional
  witness ve tüm desteklenen türlerde ilk/son start sınırları test edildi.
  Destek matrisindeki pattern/condition birleşimleri, occurrence sınırları,
  binary hedefler ve backend paritesi YARA oracle'ına karşı test edildi. Bilinçli
  destek dışı örnekler açık ret testlerine bağlıdır.
- [x] Parser limitleri, overflow, hedef boyutu, çalışma maliyeti ve bozuk dahili
  kodlamayı doğrudan C runtime testleriyle doğrula. Legacy kodlamalar için
  malformed range/alternation/negation, 8 KiB pattern limiti, signed offset
  sınırı ve occurrence indeks taşması; `hexast:v1` için eksik/yanlış opcode,
  çoklu özel atom, hatalı/taşan jump ve fazla alternation dalı doğrudan test
  ediliyor. Ek olarak typed executor doğrudan çağrısında `INT64_MAX` üstü hedef
  uzunluğunun ve uç `min_offset` değerinin fail-closed olduğu doğrulandı. 64 MiB
  yoğun prefix + geç tek eşleşme testi eklendi. 999-byte suffix, 16 near-match ve
  17 occurrence içeren typed-executor stres fixture'ında 15 sn regresyon eşiği
  belirlendi (30 sn process timeout ayrıca korunur); hedefli test geçti. Bu eşik
  yalnızca tarifli fixture'a aittir, tüm hedefler için süre garantisi değildir.
- [x] `axiom-scan` dosya ve PCAP yolları ByteBuffer gerçek uzunluğuyla taranıyor;
  NUL öncesi/sonrası ve NUL sınırını aşan text/hex eşleşmeleri YARA 4.5.4 ve
  C/LLVM parity testleriyle doğrulandı. NUL içeren hedefte regex, byte-span
  regex desteği bulunmadığı için açık yapılandırılmış hatayla reddediliyor.
  Kanıt: `docs/reports/2026-11-14-yara-binary-scanner-integration.md`.
- **Kapı (kapandı):** destek matrisinin differential/regresyon vakaları YARA ile
  eşleşti; destek dışı durumlar açıkça reddedildi; C ve LLVM raporları eşit.
  Yerel oracle paketi 490 geçti, skip olmadı. `53839c3` GitHub Actions run
  `43758677082` **7/7 başarılı**; Python 3.10–3.13 testleri 1457 geçti/27 genel
  ortam skip’i, doküman testleri 55 geçti.

#### G2 — Gerçek kural dosyalarıyla uyumluluk kanıtı `[x]` — 16 Kasım 2026

- [x] Lisansı ve sürümü kayıtlı, küçük ve yeniden dağıtılabilir bir YARA kural
  örnek kümesi seç; zararlı örnek indirmeden sentetik/zararsız hedef dosyaları
  kullan.
- [x] Her kuralı `supported`, `explicitly unsupported` veya `mismatch` olarak
  sınıflandır; sessiz mismatch kabul etme.
- [x] Kuralların destek durumunu README'de sürümlü özellik matrisiyle göster.
- [x] Bu matrisi CI'da koşan diferansiyel/regresyon testine bağla.
- **Kapı:** örnek kümesindeki her kural ya doğru eşleşiyor ya neden destek
  dışında olduğu açıkça raporlanıyor.

#### G3 — Dış kullanıcı doğrulaması `[~]` — Faz 1 ürün kapısı

- [x] Bir dış kullanıcı için tekrar üretilebilir kurulum ve 5 dakikalık
  başlangıç akışı hazırlandı; temiz klon/venv kurulumunda doğrulandı:
  [`docs/EXTERNAL_VALIDATION.md`](docs/EXTERNAL_VALIDATION.md) ve
  [`docs/reports/2026-11-16-g3-external-onboarding.md`](docs/reports/2026-11-16-g3-external-onboarding.md).
- [x] Başlangıç akışını `2871874` commit'inde (doğrulama anındaki güncel master)
  yeniden doğrula: temiz klon,
  venv/kurulum, örnek derleme, `rules` ve sentetik sentinel `scan` başarılı;
  15 saniye, `match_count=1`. Bu sentetik kontrol bağımsız kullanıcı kapısını
  kapatmaz; güncel kanıt G3 raporundadır.
- [x] Rehberin yönergelerini ve geri bildirim alanlarını Türkçe/İngilizce sun;
  kullanılabilirlik ile güvenlik bildirimlerinin kanallarını ayır; kamuya açık
  `.github/ISSUE_TEMPLATE/external-scan-trial.yml` formunda yalnız temizlenmiş
  alanlar iste; yetki ve kamuya açık paylaşım onaylarını zorunlu kıl. Formda
  dosya yükleme alanı yok. Link, içerik, dil ve gizlilik kuralları doküman
  regresyon testleriyle korunuyor.
- [x] Aynı temiz klon/kurulum/build/sentinel akışını `1e9dd23` commit'inde
  yeniden çalıştır: Linux x86_64, Python 3.13, 18,2 saniye, `rules ok=true`,
  `scan match_count=1`, offset 36/length 37. Bu sentetik doğrulama bağımsız
  kullanıcı kabulü değildir; tam çıktı G3/G4 raporundadır.
- [x] Akışı GitHub `master` üzerindeki `dd0f997` temiz klonunda yeniden çalıştır:
  Python 3.13 kurulumu, `axiom --version`, örnek derleme ve `rules`/sentinel
  `scan` başarılı; `match_count=1`, offset 36/length 37, hedef SHA-256 alanı
  64 karakter. Bu sentetik doğrulama bağımsız kullanıcı kabulü değildir;
  ayrıntı G3/G4 onboarding raporuna eklendi.
- [x] Aynı akışı `4097bda` temiz klonunda tekrar doğrula: Python 3.13.14,
  kurulum ve örnek derleme başarılı; `rules ok=true, rules=1`; sentinel
  `scan ok=true, match_count=1`, offset 36/length 37 ve hedef SHA-256
  `1672850fcdc2a61c372188931ea164f8df197a0f87df96e0dd211a4ff02ed405`.
  Bu sentetik doğrulama bağımsız kullanıcı kabulü değildir; ayrıntı G3/G4
  onboarding raporundadır.
- [x] PCAP başlangıç yönergesini gerçek okuyucu davranışıyla eşleştir: yalnız
  klasik PCAP, mikro/nanosaniye ve iki byte order; raw yakalanmış frame taraması;
  pcapng açık ret. Temiz EOF, boş paket ve bozuk/kesik kayıt artık ayrı
  durumlarla raporlanıyor. Yazıcı da 65.535 bayt sınırını, hex doğrulamasını ve
  yazma hatalarını denetliyor. Sentetik sınır testleri, C/LLVM parity ve writer
  sınır/readback regresyonları geçti. Kanıt:
  [PCAP okuyucu raporu](docs/reports/2026-11-17-pcap-reader-fail-closed.md).
  Bu yerel doğrulama bağımsız kullanıcı kapısını kapatmaz.
- [ ] Kullanıcı `axiom-scan`'i kendi yetkili dosyası veya PCAP'i üzerinde
  çalıştırıp sonuç, hata veya eksik kullanım senaryosu paylaşsın.
- [ ] Geri bildirimi (girdi türü, komut, beklenen/gerçek sonuç, SHA-256 gibi
  gizli olmayan kanıt) izin verilen sınırlar içinde kaydet; kullanıcı verisini
  projeye toplamayı varsayılan yapma.
- [ ] Kullanıcı testindeki bulguları `TODO.md`'ye issue/iş olarak ekle ve
  önceliklendir.
- **Kapı:** en az bir bağımsız kullanıcının gerçek iş akışı ve sonucu
  belgelenmeden Faz 3/1.0 iddiasına geçme.

#### G4 — Alfa dağıtımını sağlamlaştır `[~]`

- [x] Yerel derleme hazırlığında POSIX'e özgü `which` ve `/dev/null`
  varsayımlarını taşınabilir Python karşılıklarına taşı; native Windows/macOS
  linker bayraklarını host'a göre seç. Platform seçim testleri Linux'ta geçti;
  native bayraklar üç OS smoke CI'sinde de doğrulandı.
- [x] `.github/workflows/platform-smoke.yml` ile gerçek Linux, Windows ve
  macOS runner'larında temiz Python kurulumu, native derleme ve çalıştırma
  doğrulandı; Wine kullanılmadı. Sonradan registry cache hit testi de native
  dosya izinleriyle çalışacak şekilde eklendi. [CI run 43871931643](https://github.com/jaminakoai/axiom/actions/runs/43871931643)
  içinde gerçek cache testi ve native build/run Linux, Windows ve macOS'ta 3/3 geçti.
  Bu tam pytest paketinin üç işletim sisteminde çalıştığı anlamına gelmez; tam
  paket CI'si Linux'ta kalıyor.
- [x] Temiz runner'larda kurulum/yerel örnek derle-çalıştır akışını doğrula;
  Linux, Windows ve macOS test kapsamını ve Linux sistem kütüphanesi
  gereksinimlerini iki README'de açıkça yaz. Windows/macOS için tam test paketi,
  `axiom-scan` ve elle kurulum adımlarının henüz doğrulanmadığı açıkça belirtili.
- [ ] Yeni fail-closed classic PCAP okuyucu sınır testlerini native
  Windows/macOS smoke matrisinde çalıştır; bu dar PCAP testi geçse bile tam
  `axiom-scan` iş akışı ve tam pytest paketi bu platformlarda doğrulanmış
  sayılmaz.
- [x] Registry paketlerinin imza/checksum/bozuk cache testleri zaten vardı;
  sürüm yükseltmede yerel içeriğin atomik yenilenmesi ve `remove` ile
  erişilemeyen transitive registry bağımlılıklarının temizlenmesi eklendi;
  paylaşımlı transitive paketleri koruma da test edildi. `remove --purge` Git
  klonunu ayrıca temizler. Registry + paket yöneticisi hedef testleri **87 geçti**
  (59 registry, 28 paket yöneticisi). Yerel `file://` URL'leri artık yüzde
  kaçışlarını ve Windows sürücü yollarını platforma uygun çözüyor; uzak host'lar
  açık hata veriyor. Cache hit ve file URL regresyonları Linux/Windows/macOS
  platform smoke'da platform başına 4/4 geçti (run 43886676224). Assembler
  commit'i `c71e026` CI'sinde Python 3.13, PAX uzantı başlığı sınır testini
  kaçırdı (1 başarısız, 1506 geçti, 27 skip); Python 3.10/11/12'de 1507 test
  geçti/27 skip, diğer job'lar başarılı. Kök neden, `tarfile.open()` çağrısından
  sonra takılan sınır wrapper'ının ilk/uzantı başlıklarını her Python sürümünde
  yakalayamamasıydı. Gzip açılımı artık boyut sınırına kadar geçici spool'a
  yazılıyor; `TarInfo` PAX/GNU boyut kontrolü arşiv açılırken uygulanıyor.
  Düzeltme Python 3.10/12/13'teki tam CI paketlerinde de geçti; her biri 1507
  geçti/27 genel ortam testi atlandı. Aynı CI'da Python 3.11 tam paketi 1506
  geçti/27 skip ile tek `test_selfhosted_matches_python_driver[22_dfir_triage.ax]`
  başarısızlığı verdi: örnek, iki backend çalıştırması arasında değişen canlı
  `/var/log/auth.log` dosyasını okumuş (83 satır vs. 81). Bu bir backend
  ayrışması değil, parite testinin değişken girdisiydi. Test artık `tmp_path`
  altındaki sabit üç satırlı auth log'u iki backend'e de `AXIOM_DFIR_LOG` ile
  veriyor; `log.lines=3` ve SSH brute-force/SQL injection tespitlerini de
  doğruluyor. Tam self-hosted parite dosyası **27 geçti**. Bu koşu ayrıca iki
  HTTP örneğinin backend çalıştırmaları arasında `Date` header'ının saniye
  değişimini gösterdi; normalizasyon yalnızca satır başındaki HTTP `Date`
  header'ını etkisizleştiriyor ve server header'ı gibi sabit çıktıları hâlâ
  karşılaştırıyor; buna özel regresyon eklendi. Düzeltme commit'i `b874434`
  için tam CI 7/7 geçti: Python 3.10–3.13'te her biri 1508 geçti/27 skip,
  doküman kod blokları 55 geçti. Platform smoke Linux/Windows/macOS'ta 3/3
  geçti (run 43895118939); önceki parite hatası kapandı.
- [ ] En az bir resmi, sürümlenmiş örnek paketi yayınla. `axpm pack` artık temiz
  Git commit'inden deterministik tarball ve imzalı index girdisi hazırlar; ancak
  upload komutu, barındırılan registry yazma yolu ve resmi imza anahtarı yönetimi
  yok. `packages/axiom-scan-report` kaynak örneği ve gerçek path bağımlılık testi
  hazır, ancak bunlar resmi yayın sayılmaz. Bunlar çözülüp örnek paket gerçekten
  yayınlanmadan bu madde kapanmaz.
  Hosting kararı için anlık kanıt: GitHub deposu public (`master`), Pages etkin
  değil (`gh api repos/jaminakoai/axiom/pages` → HTTP 404) ve
  `registry.axiom-lang.org` DNS'te çözülmüyor. Uygun hedef seçilmeden yayın
  altyapısı veya resmi imza anahtarı oluşturulamaz.
  Yerel teknik akış uçtan uca doğrulandı: imzalı `pack`, Ed25519 doğrulaması,
  geçici `file://` registry indirmesi ve çıkarılan pakette `axpm test` 1/1 geçti;
  kanıt `docs/reports/2026-11-16-axpm-pack-local-registry-smoke.md`.
  CI'da gerçek `axiom-scan-report` örneğini geçici anahtarla paketleyip imzalayan,
  yerel registry'den temiz tüketiciye kuran, kurulu paketin kendi testini ve
  tüketici import testini `axpm test` ile çalıştıran yayın ön kontrolü eklendi.
  `axpm registry assemble --from ... --output ... --public-key ...` komutu
  paket çıktısını imza/SHA/manifest kontrollerinden geçirerek deterministik,
  çevrimdışı statik Registry v1 veya ayrı anahtarla imzalı v2 dosya düzenine
  dönüştürüyor. Schema 2, 90 günlük süre ve gözlemlenmiş sequence rollback
  kontrollerini içeriyor; ilk bağlantıdaki eski index'i kanıtlayamaz ve yerel
  rollback state silinebilir. Hiçbir yere yükleme yapmıyor. Kanıt:
  `docs/reports/2026-11-16-axpm-signed-release-preflight.md`.
  İndirme tarafında tar symlink/hardlink ve özel dosya kaçışları reddediliyor;
  kötü niyetli arşiv regresyonları test edildi. Cache isabetlerinde güncel imza/
  unsigned politikası ve açılmış dosyaların tarball bütünlüğü de yeniden
  doğrulanıyor; `docs/reports/2026-11-16-registry-cache-integrity.md` içinde 73
  registry/paket-yöneticisi testiyle kanıtlandı. Son güvenlik incelemesi ayrıca
  istemcinin tarball içindeki imzalı `axiom.toml` adını, sürümünü ve bağımlılık
  haritasını unsigned index kaydıyla karşılaştırmadığını gösterdi. Client artık
  bu karşılaştırmayı hem indirmede hem cache hit'te yapıyor; PackageManager
  çözümlediği bağımlılık haritasını doğrulamaya geçiriyor. Registry ve paket
  yöneticisi hedef testleri yeni regresyonlarla **104 geçti**; kayıt şeması
  doğrulaması da buna dahildir. Güncel doküman+registry+paket yöneticisi hedef
  paketi **118 geçti** (cc7de3a), MinGW/Windows taşınabilirlik testi **34 geçti**. Ayrıntı
  ve kalan ilk-bağlantı rollback sınırı
  `docs/reports/2026-11-16-registry-index-metadata-binding.md`. İmzalı schema 2
  biçimi uygulanmıştır; resmi yayın öncesi hosting, üretim anahtarı koruma/
  rotasyonu ve ilk bağlantı rollback sınırını operasyonel olarak kabul et.
  Sequence-state kilidinin iki süreç arasındaki bloklama testi `cc7de3a` ile
  Linux/Windows/macOS smoke matrisine eklendi ve 3/3 geçti; imzalı index'in
  OpenSSL Ed25519 doğrulama/rollback testleri de `4bf3b8b` ile native smoke'a
  eklendi; Linux, Windows ve macOS'ta OpenSSL 3 altında 9'ar test geçti.
  Önceki tam CI `52544da` [run 43987784851](https://github.com/jaminakoai/axiom/actions/runs/43987784851)
  için 7/7 geçti: Python 3.10–3.13'ün her birinde 1558 geçti/27 skip ve 55
  doküman testi geçti. Güncel tam CI `4097bda` [run 43991703164](https://github.com/jaminakoai/axiom/actions/runs/43991703164)
  için 7/7 geçti: Python 3.10–3.13'ün her birinde **1559 geçti/27 skip**,
  doküman kod bloklarında 55 geçti; sabitlenmiş YARA diferansiyel testinde her
  sürümde 29 geçti. Güncel native smoke `4097bda` [run 43991703153](https://github.com/jaminakoai/axiom/actions/runs/43991703153)
  Linux, Windows ve macOS'ta 3/3 geçti. 27 Linux CI skip'i MinGW gerektiren 16 ve Wine gerektiren
  11 taşınabilirlik testidir; MinGW ve Wine kurulu yerel ortamda bu dosyanın
  tamamı **34 geçti, 0 skip** (100,70 sn). Native platform smoke `52544da`
  için Linux/Windows/macOS'ta 3/3 başarılı: [run 43987784833](https://github.com/jaminakoai/axiom/actions/runs/43987784833).
- [x] Henüz dağıtılmamış `registry.axiom-lang.org` varsayılan adresini
  `docs/REGISTRY.md` içinde açıkça etiketle; gerçek upload/hosting varmış gibi
  sunma. Ürün davranışını değiştirmeden çalışan yerel `file://` imzalı paket
  → registry assemble → temiz tüketicide install/test akışını belgele ve
  regresyon testi ekle. Akış yerel tüketici testlerinde 2/2 geçti; bu resmi
  yayın değildir. Ayrı anahtarlı Registry v2 imza/sequence akışı bu turda eklendi;
  hosting, üretim anahtarı işletimi ve ilk kullanımda eski index'in
  önlenememesi hâlâ açık yayın sınırlarıdır.
- [x] İmzalı örnek paket yayın ön kontrolünü Windows/macOS dâhil native smoke'a
  ekle. Windows'ta eski konsol kodlamalarının Türkçe çıktıyı kaçış dizisine
  çevirmesi nedeniyle testteki iki metin karşılaştırması sayısal özete
  dayandırıldı (`4097bda`). Native smoke Linux, Windows ve macOS'ta 3/3 geçti:
  [CI run 43991703153](https://github.com/jaminakoai/axiom/actions/runs/43991703153).
- [x] Registry istemcisinde paket indirme, önbellek okuma ve arşiv açma
  sınırlarını `axpm pack`/`assemble` politikasıyla hizala: sıkıştırılmış paket,
  açılmış dosya toplamı, üye sayısı, manifesto, gzip genişlemesi ve PAX/GNU
  metadata sınırlarını uygula; kesik payload'ı cache'e yayımlama; bozuk veya
  fazla büyük cache'i sınırlı okuma/tarama ile ele al. `axpm pack` de bu
  sınırlara uymayan girdileri payload'ı okumadan önce reddeder. Büyük geçerli
  33 MiB payload'ın client ve assembler tarafından kabul edildiği ayrıca
  doğrulandı. Yerel hedefli doğrulama: **137 geçti**; `476e06f` tam CI'si
  Python 3.10–3.13'te her birinde **1558 geçti/27 skip**, doküman testlerinde
  55 geçti ve 7/7 iş başarılı; native smoke 3/3 geçti. `make fmt-check`, Python
  derleme kontrolü ve `git diff --check` de geçti. Ayrıntı:
  [`2026-11-17-registry-client-archive-bounds.md`](docs/reports/2026-11-17-registry-client-archive-bounds.md).
- [x] `v1.0` öncesi sürümleme ve doğrulanmış platform matrisi kararı yazıldı:
  [`docs/VERSIONING.md`](docs/VERSIONING.md). İki sürüm geriye uyumluluk
  taahhüdü özellikle 1.0 kararı öncesine bırakıldı; README'ler ARM64 durumunu
  deneysel/doğrulanmamış olarak düzeltiyor.
- **Kapı:** temiz ortamda kurulumdan örnek taramaya kadar belgelenmiş akış
  çalışıyor; desteklenmeyen ortamlar açıkça belirtiliyor.

#### G5 — Nişte büyüme ve 1.0 `[ ]` — G3/G4 sonrası

- [ ] Gerçek kullanıcı ve bakım kapasitesi oluştukça paket/yazar hedefleri koy;
  hedef sayısını kullanıcı ihtiyacının yerine geçirme.
- [ ] 1.0 API kararlılığı ve iki sürüm geriye uyumluluk politikasını onayla.
- [ ] Regülasyon kanıt paketi, fon başvurusu ve genel amaçlı dil hedeflerini
  yalnız somut talep/ortak bulunduğunda başlat.

### Aktif kapı ve paralel hazırlık

**G3 — Dış kullanıcı doğrulaması** hâlâ Faz 1'in açık kabul kapısıdır. G3
bağımsız kullanıcı geri bildirimi beklerken, G4 için G3 kanıtına bağlı olmayan
taşınabilirlik hazırlıkları paralel yürütülebilir; bu hazırlıklar G3'ü veya G4
kapısını kapatmış sayılmaz. G1 ve G2 kapandı. G1: NUL
korumalı dosya/PCAP taraması, 64 MiB typed stress ölçümü, signed offset/length ret
testleri ve yeni condition differential matrisinin ilk bölümü tamamlandı. Selector
overlap vakasında bulunan sessiz yanlış negatif düzeltildi. Tam GitHub CI doğrulaması `53839c3` için Python 3.10–3.13 matrix’inde her biri **1457 geçti/27 genel ortam skip’i** verdi. 15 Kasım hedefli YARA/scanner/differential/stress/AST-limits/C-LLVM parity paketi **490 geçti, 0 skip** (224,36 sn). Doğrudan C runtime testleri `INT64_MIN` min/max offset, `INT64_MAX` üstü hedef uzunluğu, hatalı AST/legacy kodlamaları ve occurrence index sınırlarının fail-closed olduğunu doğruluyor. 64 MiB/999-byte suffix near-match fixture'ına 15 sn regresyon eşiği eklendi; hedefli test **1 geçti**. `53839c3` GitHub Actions [run 43758677082](https://github.com/jaminakoai/axiom/actions/runs/43758677082) **7/7 başarılı**: Python 3.10–3.13’de 1457 geçti/27 genel ortam testi atlandı; doküman testleri 55 geçti. Tek satırlı inline YARA ve NUL içeren regex destek dışı ve açıkça belgeli ret sınırlarıdır. G2 corpus'unun güncel test kanıtı `docs/reports/2026-11-16-g2-yara-real-rule-corpus.md` içindedir. G3 kurulum/başlangıç rehberi temiz klon ve sentetik hedefle doğrulandı; artık kapının kalan kısmı bağımsız kullanıcının yetkili dosya veya PCAP'inde gerçek iş akışını deneyip gizli olmayan geri bildirim vermesidir: [`docs/EXTERNAL_VALIDATION.md`](docs/EXTERNAL_VALIDATION.md).

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
| Son tamamlanmış tam test paketi | CI `52544da`: Python 3.10–3.13'te her biri 1558 geçti/27 skip; 1565 yerel test `23a0aca` commit'inde geçti | GitHub Actions run 43987784851; `python3 -m pytest -q` |
| Son native platform smoke | `52544da`: süreçler arası registry kilidi + native build/run Linux/Windows/macOS 3/3 geçti | GitHub Actions run 43987784833 |
| G1 hedefli testler | YARA/scanner/differential/stress/AST limits/backend parity: 490 geçti, 0 skip (224,36 sn) | G1 kapanış raporundaki komut |
| Redteam testleri | 17 (varsayılan; `AXIOM_SKIP_REDTEAM=1` ile atlanır) | `... tests/test_redteam_*.py` |
| Stdlib | 52 dosya / 385 fonksiyon / 3.946 satır | `find std -name '*.ax' \| wc -l` |
| Örnek | 21 | `ls examples/*.ax \| wc -l` |
| C backend örnek | 21/21 | `for f in examples/*.ax; do axiom build "$f"; done` |
| LLVM backend örnek | 21/21 | `... --backend=llvm` |
| Self-hosted (`bin/axiomc`) | **21/21** ✅ | `./bin/axiomc build examples/$f.ax` |
| Paket kayıt defteri | **v1 var** (ed25519, semver, transitive) | `tests/test_registry.py` |
| Windows desteği | **21/21 cross-compile + Wine**; native build + registry cache/file URL smoke geçti | P2-19b ve run 43881080465 |
| macOS | native build + registry cache/file URL smoke geçti; tam pytest/`axiom-scan` doğrulanmamış | run 43881080465 ve README sınırları |
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
| Windows/macOS | Native build + registry cache smoke Linux/Windows/macOS'ta 3/3 geçti; tam pytest ve `axiom-scan` yalnız Linux'ta doğrulanıyor | Platform kapsamı hâlâ sınırlı |
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
FAZ 1: Güvenlik araçları (kod/test)                ✅ tamam; dış kullanıcı kapısı ⬜
   ↓
FAZ 2: Olgun kütüphane + ekosistem altyapısı      🟡 büyük ölçüde hazır; 0 paket yayınlı
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

#### P1-03e — Eşzamanlı `tcp_connect` yarışı (SIGSEGV) `[x]`
- **Belirti:** CI'da `examples/08_multithreaded_scanner.ax` aralıklı olarak
  `exit -11` / `245` (segfault) ile düştü; yerelde 10/10 temizdi.
- **Kök neden:** `axiom_tcp_connect` (ve `udp_sendto`, `icmp_ping`, `tcp_ping`)
  IPv4 çözümlemesinde POSIX'te **MT-Unsafe** `gethostbyname` kullanıyordu.
  Dört thread aynı anda çağırınca statik `hostent` eziliyor, `h_length`
  bozuluyor, `memcpy` taşıyor → SIGSEGV.
- **Düzeltme:** `axiom_internal_resolve_ipv4()` — `inet_pton` (sayısal) /
  `getaddrinfo` (thread-safe). Runtime'da `gethostbyname` kalmadı.
- **Kabul:** ✅
  - [x] 8 thread × 40 bağlantı, 25 koşu: eski **18/25 segfault**, yeni **0/25**
  - [x] `tests/test_thread_safe_resolve.py` (3 test); eski runtime'da 3/3 kırmızı
  - [x] C ve LLVM arka uçlarında aynı davranış
- **Rapor:** aynı dosya, §12

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
- [x] ~~Windows çapraz derleme~~ ✅ (P2-19, 21/21); native Windows/macOS
  smoke CI de geçti (tam pytest/`axiom-scan` bu platformlarda doğrulanmış değil).
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
| Son tam CI | `52544da`: Python 3.10–13’te her biri 1558 geçti/27 skip; doküman 55 geçti; 7/7 başarılı | Run 43987784851 | 2000 |
| Son native platform smoke | `52544da`: cache/file URL + signed index + build/run Linux/Windows/macOS 3/3 başarılı | Run 43987784833 | — |
| Güncel G1 hedefli doğrulama | YARA/scanner/differential/stress/AST limits/backend parity 490 geçti, 0 skip (224,36 sn) | — | — |
| Stdlib fonksiyon | 385 | 450 | 900 |
| Örnek program | 21 | 25 | 60 |
| Yayımlanmış registry paketi | 0; 1 kaynak örneği paketlenebilir, yayınlanmadı | 10 | 250 |
| Dış katkı/ay | 0 | 2 | 10 |
| Üretim kullanıcısı | 0 | 1 | 3 |
| Self-hosted örnek | **21/21** ✅ | 8/21 | 21/21 |
| C'ye hız oranı (aritmetik) | 1,5–2,2× | ≤2× | ≤1,5× |
| Platform | Linux tam CI; Windows/macOS native smoke 3/3; tam pytest/scan doğrulaması Linux'ta | 2 işletim sistemi runner'ı | 2+ gerçek runner |

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

## 12. GÜNCEL YÜRÜTME SIRASI

Bu bölüm aktif listedeki sırayı tekrarlar; görev ayrıntıları ve kabul kapıları
belgenin başındaki **Aktif Master Roadmap** bölümündedir.

1. **G3:** en az bir bağımsız kullanıcının `axiom-scan` ile gerçek iş akışı;
   gizli olmayan geri bildirimi kaydet ve bulguları önceliklendir.
2. **G4:** örnek paket için upload/hosted registry yazma yolunu ve resmi imza
   anahtarı işletimini kararlaştır; en az bir sürümlü paketi gerçekten yayımla.
   G4 platform smoke kısmı Linux/Windows/macOS'ta geçti, fakat tam test/scan
   kapsamı Windows/macOS'ta doğrulanmış değildir.
3. **G5:** kullanıcı kanıtı ve bakım kapasitesi oluştuktan sonra 1.0 ve ekosistem
   hedeflerini kararlaştır.

**G0, G1 ve G2 kapandı.** Native platform smoke doğrulaması da tamamlandı;
`52544da` tam CI'si 7/7 başarılı. Sıradaki kabul kapıları G3 dış kullanıcı
doğrulaması ve G4 resmi örnek paket yayınıdır. Yeni YARA sözdizimi differential
kanıt ve açık kapsam sınırlarıyla eklenir.
