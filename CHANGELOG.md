# Changelog

Tüm önemli değişiklikler bu dosyada tutulur.
Biçim: [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) · Sürümleme: [SemVer](https://semver.org/lang/tr/)

## [Unreleased]

### Değiştirilen
- YARA sabit ve özel hex biçimlerinin arama, sayım ve seçili occurrence
  uzunluğu tek runtime occurrence yürütücüsünü kullanıyor. C ve LLVM için yeni
  ortak find API'si offset sınırlarını aynı yerde uyguluyor.
- Kural parser'ı sabit/wildcard byte, bounded jump, düz alternation ve negation
  kalıplarını `hexast:v1` sürümlü bytecode'a normalize ediyor. C runtime programı
  sınırlarıyla doğrulayıp geçiş sırasında önceki matcher temsillerine uyarlar;
  uyumluluk etiketlerinin tamamen kaldırılması henüz tamamlanmadı.

### Testler
- YARA occurrence runtime testleri signed 64-bit uç occurrence indekslerini ve
  taşan/bozuk bounded-range ile alternation kodlamalarını kapsıyor; geçersiz
  girdiler eşleşme üretmeden reddedilmeli.

### Düzeltilen (13 Kasım — bounded YARA occurrence maliyeti)
- `#a` bounded-jump sayımında tekrarlanan prefix ve uzun, neredeyse eşleşen
  suffix'lerin her olası jump'ta tekrar taranması önlendi. Hedefe göre nadir
  suffix baytı seçiliyor; kompakt bitset, geçerli jump penceresinde bu bayt yoksa
  suffix karşılaştırmasını atlıyor. Tek byte prefix araması `memchr` yolunu kullanıyor.
- 64 MiB adversarial hedefte 17 instance **1,321 sn**'de sayıldı; yardımcı bitset
  en çok hedef boyutunun 1/8'i kadar geçici bellek kullanır.
- Bozuk kodlama, kısa hedef, hatalı indeks, overlap, canonical uzunluk ve YARA
  4.5.4 occurrence semantiği için doğrudan runtime regresyonları eklendi.

### Geliştirilen (13 Kasım — YARA hex occurrence yürütücüsü)
- Bounded jump, alternation ve negation hex desenleri için `#a`, `@a[i]` ve
  `!a[i]` desteği eklendi. Eşleşen start offset'leri overlap edebilir, aynı
  başlangıç tek instance sayılır; bounded jump'ta aynı başlangıçtaki en kısa
  geçerli eşleşme seçilir, eşit uzunluklu alternation dalları birleştirilir.
- C ve LLVM runtime bağları ortak occurrence API'sine taşındı; doğrudan runtime,
  YARA oracle ve backend parity regresyonları eklendi.

### Düzeltilen (13 Kasım — YARA koşul kanıtı)
- `$a at N` veya `$a in (...)` daha sonraki bir occurrence ile doğru olduğunda
  `axiom-scan` artık kanıt offset/uzunluğu olarak ilk, ilgisiz occurrence'ı
  raporlamıyor; koşulu sağlayan occurrence'ı raporluyor. C ve LLVM parity
  regresyonları eklendi.

### Eklenen (13 Kasım — sınırlı YARA negated byte)
- Hex desenlerinde her kalıp için tek bir `~HH`, `~?H` veya `~H?` byte
  negation'ı destekleniyor. Sabit `[N]` jump'larıyla kullanılabilir; ikinci
  negation, `~??`, bounded `[N-M]` ve alternation ile birleşim reddedilir.
- Negated desenlerde `$a at/in` ve sabit eşleşme uzunluğu desteklenir;
  `#a`, `@a[i]` ve `!a[i]` occurrence verisi sunulmadığından açıkça reddedilir.
- Runtime, dahili negation kodlamasını ve byte maskesini doğrular; prefix veya
  suffix bulunmayan desenleri de güvenli biçimde tarar.
- YARA diferansiyel, parser ve doğrudan C runtime testleri eklendi.

### Eklenen (13 Kasım — sınırlı YARA hex alternation)
- Hex kalıpları artık bir düz alternation grubunda 2–4 eşit uzunluklu (1–16
  bayt) dalı destekliyor. Dallar yalnızca tam bayt veya nibble wildcard token'larından
  oluşabilir; sabit `[N]` jump grup dışında kullanılabilir. İç içe/çoklu grup,
  `[N-M]` ile birleşim ve değişken dal uzunlukları reddedilir.
- `$a at/in` kontrolleri alternation desenlerinde çalışır; `#a`, `@a[i]` ve
  `!a[i]` için occurrence desteği olmadığından bu operatörler açıkça reddedilir.
- Alternation branch runtime'ı her dalı katı biçimde doğrular, en erken ofseti
  döndürür ve eşit uzunluk nedeniyle eşleşme uzunluğunu tek anlamlı tutar.
- Parser, runtime ve YARA diferansiyel regresyon testleri eklendi.

### Eklenen (13 Kasım — sınırlı değişken genişlikli YARA hex jump)
- Hex kuralları artık her desende tek bir sınırlı `[N-M]` jump'ını kabul ediyor:
  `0<=N<=M<=64`, aralık genişliği en fazla 16 bayt ve jump'ın iki yanında da
  en az bir bayt gerekir. `$a at/in` bu desenlerde çalışır; `#a`, `@a[i]` ve
  `!a[i]` açıkça reddedilir. Sınırsız ve kapsam dışı sözdizimi parse hatası verir.
- Runtime, en erken offset'i ve aynı offset'teki en kısa eşleşmeyi döndürür;
  runtime API'si kodlanmış aralık ve offset sınırlarını da doğrular.
- YARA diferansiyel, parser ve runtime testleri eklendi.

### Eklenen (13 Kasım — güvenli sabit genişlikli YARA hex jump)
- Hex kurallarında `[N]` artık `N=1..64` için joker bayt dizisine normalize
  edilerek destekleniyor. Değişken aralık, sınırsız jump, alternation,
  negation ve hatalı bayt sözdizimi açık parse hatası veriyor.
- Runtime hex parserı doğrudan API çağrılarında da geçersiz karakterleri
  yutmuyor; tek nibble/tek `?`, bozuk encoded-target verisi ve 8 KiB üzeri
  desenler reddediliyor. Offset sınırları signed overflow'a karşı güvenli.
- Genişletilmiş kalıp parser aşamasında runtime'ın 8 KiB sınırına göre
  doğrulanıyor; böylece kabul edilen kuralın taramada sessizce kaçırılması
  önleniyor.
- Diferansiyel ve regresyon doğrulaması: YARA/self-hosted odaklı paket
  **217 geçti, 0 atlandı**.

### Düzeltilen (13 Kasım — YARA alt kümesi doğruluğu ve regex güvenliği)
- `nocase`/`ascii`/`fullword` modifier bayrakları taramada ve desen sayımında
  yalnızca bilinen birleşimler olarak kabul ediliyor; bozuk veya bilinmeyen
  dahili flag değerleri sessizce ASCII aramasına düşmüyor. `wide`, mevcut
  NUL-sonlanan hedef gösterimi nedeniyle açık hata olarak kalıyor.
- YARA regex taraması artık doğrulama ve risk kapısını kullanıyor. Yeni
  `yara_scan_regex_result` hatayı çağırana taşır; eski bool API'si geçersiz/
  riskli desende fail-closed davranır.
- Kaçışlar, string içindeki `//`, satır sonu yorumları ve tek başına son `/`
  için regresyon testleri eklendi; yorum taramasındaki sınır kontrolü LLVM
  değerlendirme davranışına karşı güvenli hale getirildi.
- Doğrulama: YARA/self-hosted odaklı paket **193 geçti, 0 atlandı**.

### Düzeltilen (13 Kasım — self-hosted codegen tür çıkarımı)
- **Fonksiyon kapsamı:** self-hosted C codegen artık yerel string türlerini
  fonksiyonlar arasında taşımıyor; aynı isimli string, integer ve boolean
  değişkenleri birbirinin türünü bozmuyor.
- **Dizi ve alan türleri:** `str[]` parametrelerinden alınan elemanların türü
  doğru belirleniyor. Daha büyük boolean ifadelerdeki dizi erişimleri yanlış
  biçimde string sayılmıyor; aynı isimli fakat farklı tipli struct alanları
  tür çıkarımını kirletmiyor.
- **`__auto_type` string sonuçları:** HTTP başlık değerleri gibi string
  döndüren runtime çağrılarının türü yerel değişkenlere aktarılıyor.
- **Regresyon kapsamı:** self-hosted tip çakışması testi eklendi; YARA ve
  self-hosted test paketi 221 geçti, 0 atlandı; codegen uçtan uca testleri
  17 geçti.

### Eklenen (P2-19 — platform taşınabilirliği: Linux + Windows)
### Eklenen (P2-19 devamı — Windows doğrulaması)
### Düzeltilen (12 Kasım — atanmamış dizi serbest bırakma / sonsuz döngü)
- **ÜRÜN HATASI:** `let l = read_lines(p)?` deseninde `?` hata yolu, **henüz
  atanmamış** `l` dizisini serbest bırakıyordu:
  `ax_array_str l = ({ ... if (!ok) { axiom_array_str_free(&l); ... } });`
  `l`'nin çöp `.length` alanı yüzünden serbest bırakma döngüsü milyonlarca kez
  dönüyor, süreç **%98 CPU** ile kilitleniyordu (olay: 3 test ikilisi 2 gün).
- **Düzeltme:** `pending_init` koruması dizi kapsamlarına da uygulandı —
  `_emit_all_owned_releases`, `_capture_loop_cleanup`, `generate_block_contents`.
- **Regresyon testi:** `tests/test_uninit_array_release.py` (5 test). Üretilen
  C'de `X = ({ ...free(&X)... })` deseni yasak; 300 kez hata yolu 60 s'de biter;
  C ve LLVM paritesi. Düzeltme geri alınınca test **kırmızı** oluyor (kanıtlandı).
- **Test altyapısı:** `conftest.py` — `subprocess.run` çağrılarına varsayılan
  900 s zaman aşımı (`AXIOM_TEST_TIMEOUT`). 168 testsiz çağrı kaçak süreç
  bırakabiliyordu.
- **Wine prefix sızıntısı:** oturum başına tek prefix + `conftest.pytest_sessionfinish`
  ile silme (hook test modülündeydi, pytest yok sayıyordu) + bayat prefix temizliği.

### Değişen (12 Kasım — CI yeşil)
- GitHub Actions **7/7 iş yeşil** (koşu `43266408601`); CI rozeti `passing`.
  Toplam 6 kök neden giderildi, üçü gerçek ürün hatasıydı (LLVM `main()`
  köprüsü, Python 3.10 TOML çözümleme, `gethostbyname` yarışı).
- Yerel tam paket: **1034 geçti, 0 başarısız, 0 atlandı**.

### Düzeltilen (12 Kasım — üçüncü CI turu: thread-safety)
- **`gethostbyname` yarış hatası (gerçek ürün hatası):** `axiom_tcp_connect`
  (ve `udp_sendto`, `icmp_ping`, `tcp_ping`) IPv4 çözümlemesinde POSIX'te
  **MT-Unsafe** olan `gethostbyname`'i kullanıyordu. Dört thread aynı anda
  çağırınca statik `hostent` tamponu eziliyor, `h_length` bozuluyor ve `memcpy`
  taşarak **SIGSEGV** veriyordu. CI'da `examples/08_multithreaded_scanner.ax`
  aralıklı olarak `-11` / `245` ile düştü; yerelde 10/10 temizdi.
- **Düzeltme:** `axiom_internal_resolve_ipv4()` — sayısal adreslerde
  `inet_pton` (DNS yok), aksi hâlde thread-safe `getaddrinfo`. Dört çağrı yeri
  geçirildi; runtime'da `gethostbyname` kalmadı.
- **Ölçüm:** 8 thread × 40 bağlantı, 25 koşu → eski runtime **18/25 segfault**,
  yeni runtime **0/25**.
- **Regresyon:** `tests/test_thread_safe_resolve.py` (C + LLVM + kaynak yasağı);
  eski runtime'da 3/3 kırmızı (`-11`).

### Düzeltilen (12 Kasım — ikinci CI turu)
- **Python 3.10'da paket bağımlılıkları sessizce çözülmüyordu (gerçek hata):**
  `axiom/resolver.py` doğrudan `import tomllib` yapıyordu; 3.10'da stdlib'de
  olmadığı için istisna yutuluyor ve `dependencies` hiç okunmuyordu
  (`import "paket"` → "modül bulunamadı"). `pyproject.toml` ise `>=3.10`
  diyor. Artık `axiom.package_manager.parse_toml` kullanılıyor; `tomli`
  (3.11 altı) bağımlılığı eklendi ve yedek ayrıştırıcı inline tabloları
  destekliyor. Regresyon: `test_parse_toml_handles_inline_tables_without_tomllib`.
- **DWARF testi araç sürümüne bağlıydı:** `readelf` çıkış kodu yerine içerik
  doğrulanıyor; `Bogus end-of-siblings` uyarısının **binutils bug 28981**
  olduğu kanıtlandı (ID çakışması yok, pyelftools temiz okuyor, binutils 2.46
  uyarısız). Bağımsız yapısal doğrulama eklendi
  (`test_dwarf_structure_is_valid_via_independent_parser`, pyelftools).

### Düzeltilen (12 Kasım — CI kök nedenleri)
- **LLVM `main() -> Result` köprüsü (gerçek ürün hatası):** köprü
  `call void @ax_main()` üretiyordu; `@ax_main` struct döndürüyor. clang 14
  derleme hatası veriyor, clang 21 kabul edip **Err'i sessizce düşürüyordu**
  (hata durumunda `exit 0`). Köprü artık `Result`'ı değer olarak çağırır,
  `is_ok` alanını okur, Err'de `error` alanını stderr'e yazar ve 1 döndürür.
  C arka ucuyla birebir aynı davranış.
  Regresyon: `tests/test_llvm_main_bridge.py` (6 test); düzeltme geri alınınca
  3 test kırmızı oluyor (kanıtlandı).
- **`axiom/runtime.h`:** `axiom_eprint_error()` eklendi (stderr + `[AXIOM HATA]`).
- **CI sırası:** `make bootstrap` artık `test` ve `sanitizers` işlerinde
  pytest'ten **önce** çalışıyor. `bin/axiomc` depoda tutulmadığı için 13 test
  dosyayı bulamıyordu.
- **Unicode testleri sürümden bağımsızlaştırıldı:** tablo sürümü
  `tools/gen_unicode_tables.py` içinde **sabitlendi** (`PINNED_UCD_VERSION =
  "15.1.0"`); yorumlayıcı uyuşmazsa üretici durur (sessiz farklı UCD yasak).
  Beklenen NFC/NFD değerleri `tests/data/unicode_conformance.json` altın
  dosyasına taşındı; korpüs `tools/unicode_corpus.py`'de tek kaynak.
  Python 3.10/3.11 (Unicode 14.0.0) artık testi düşürmüyor.
- **DWARF testleri:** `readelf` çıkış koduna değil aranan içeriğe bakıyor;
  yalnızca bilinen araç-zinciri uyarıları (yeni clang + eski binutils)
  tolere edilir, başka hata hâlâ testi düşürür.
- **CI `fmt` işi:** `pip install -e ".[dev]"` eklendi (`import z3` eksikti).

### Düzeltilen (12 Kasım — yayın öncesi inceleme: rozet/iddia/numaralandırma)
- **Rozetler:** sahte "CI — GitHub Actions success" ve "1022 Passed" rozetleri
  kaldırıldı. CI rozeti **gerçek workflow'a** bağlandı
  (`github.com/jaminakoai/axiom/actions/workflows/ci.yml`); test rozeti
  "yerel koşu" olarak etiketlendi ve tarih/komut/sonuç belgelenen bölüme bağlandı.
- **Ürün anlatımı:** "Axiom nedir?" bölümü eklendi — ana ürün dildir; `axiom-scan`
  ve DFIR triyajı bu dilin **amiral gemisi uygulamalarıdır**. DFIR bölümü
  "Bu dille yazılmış araçlar" olarak yeniden adlandırıldı.
- **İddialar:** slogan ölçüme dayalı hâle getirildi. Yeni "İddialar ve kanıtlar"
  tablosu 6 iddiayı gerçek durum + kanıtla eşler. "Sıfır bilişsel yük" ve
  "Python kadar zarif" kaldırıldı; karşılaştırma tablosunun yıldızlarının ölçüm
  olmadığı yazıldı.
- **Test/CI şeffaflığı:** "Son doğrulanmış koşu" (tarih, komut, 1022/0/0) ve
  "CI durumu (dürüst)" (20 başarısız / 919 geçti / 83 atlandı + 4 kök neden)
  bölümleri eklendi. Sandbox koşusu (951/57/2) rapora linklendi.
- **Numaralandırma:** README örnek başlıkları 1–14 sıralı; kırık `#13` bağlantısı
  (`taraması`/`taramasi`) düzeltildi. TR ve EN'de kırık bağlantı **0**.
- **Bulunan gerçek hata (açık):** LLVM `main() -> Result<int,str>` köprüsü
  `call void @ax_main()` üretiyor; `@ax_main` struct döndürüyor. clang 21 kabul
  edip Err'i sessizce düşürüyor, clang 14 reddediyor. C arka ucunda doğru.
  CI'daki 2 test hatasının kök nedeni; rapor §9'da kayıtlı.

### Eklenen / Düzeltilen (P1-03c — axiom-scan v0.2, DFIR rapor sözleşmesi)
- **`axiom-scan` v0.2:** rapor artık `schema_version=1`, `tool`, `tool_version`,
  `rules_count` taşır. `scan` çıktısına **`target_sha256`** (tüm dosya,
  `sha256sum` ile birebir), `match_count` ve bayt cinsinden `scanned_bytes`;
  `pcap` çıktısına `pcap_sha256` ve `match_count` eklendi.
- **`--fail-on-match` (opt-in):** bulgu varsa exit **10**, yoksa 0. Bayraksız
  davranış korunur (exit 0) — kırıcı değişiklik yok.
- **Hata yolları:** şemalı JSON (`{"ok":false,"error":...}`) + exit 1.
- **Bulunan gerçek hata:** `fn main() -> Result<int,str>` köprüsü ok değerini
  daima 0'a eşliyordu; `--fail-on-match` bu yüzden etkisizdi. Dil semantiği
  (testli) değiştirilmedi; araç `int main` + `_dispatch()` desenine geçirildi.
- **Test:** `tests/test_axiom_scan.py` 15 → **20 test** (şema, hash eşitliği,
  exit 10/0, hata JSON'u, C/LLVM paritesi).
- **Doküman:** README (TR+EN) DFIR/güvenlik kanıtı odaklı yeniden konumlandı;
  "Proje durumu ve yol haritası" + "Testleri çalıştırma" bölümleri eklendi.
- **GitHub hazırlığı:** `.gitignore`'a `/bin/axiomc`; makineye özel yollar
  (`/home/mimar/...`) README, rehberler, `compiler/main.ax` ve 4 testten
  kaldırıldı. Push/uzak bağlama yapılmadı.

### Eklenen (P2-19b — wine ile gerçek Windows çalıştırma)
- **21/21 örnek wine 10.0 altında çalışıyor**; çıktılar Linux ile birebir
  (zamanlama/rastgelelik normalize edilerek).
- **`axiom/regex_portable.h`:** POSIX regex olmayan platformlarda devreye giren
  taşınabilir motor. Karakter sınıfı, niceleyici, gruplama, alternasyon, çapa,
  `(?i)`. Geri izlemeli ama **adım bütçeli** (ReDoS'a kapalı).
- **Test:** `tests/test_portability.py` 23 → 34 (10'u wine ile gerçek koşum).

### Düzeltilen (P2-19b — wine olmadan görünmeyen 3 gerçek hata)
- **`WSAStartup` hiç çağrılmıyordu** → Windows'ta hiçbir soket çalışmazdı.
  `platform.h`'ye constructor + tembel başlatma; `ax_os_socket()` sarmalayıcısı.
- **Regex Windows'ta tamamen devre dışıydı** → Sigma/YARA/CVE tespiti sessizce
  `false` dönüyordu (güvenlikte sessiz kaçırma). Taşınabilir motor eklendi.
- **Örnek 11'de thread çıktı yarışı** → çıktı koşudan koşuya değişiyordu;
  `thread_join` sonrasına alındı (5/5 koşu birebir).


- **PE import denetimi:** 21 ikilinin tamamı yalnız `KERNEL32`/`msvcrt`
  (ağ kullananlarda `WS2_32`) import ediyor. `libssl`/`libcrypto`/`libz` yok →
  çıplak Windows kurulumunda başlar.
- **Windows kod yolu Linux'ta çalıştırıldı:** `-DAXIOM_DISABLE_OPENSSL
  -DAXIOM_DISABLE_ZLIB` ile derlenen runtime'da SHA-256/SHA-1/MD5/HMAC
  `hashlib`/`hmac` ile birebir; AES/zlib açık hata veriyor.
- `AXIOM_HAVE_OPENSSL` / `AXIOM_HAVE_ZLIB` artık her zaman 0/1 tanımlı ve
  `-DAXIOM_DISABLE_*` ile kapatılabilir (yalnız test/doğrulama için).
- **Test:** `tests/test_portability.py` 21 → 23.


- **`axiom/platform.h`:** 4 katmanlı taşınabilirlik katmanı — çekirdek, ağ,
  Linux'a özel, harici kütüphane. Her platforma özgü çağrı tek yerde.
- **`axiom build --target windows`:** mingw-w64 ile **21/21 örnek** PE32+ üretir.
  Bağlama bayrakları platforma göre seçilir (`-lws2_32` vs `-lssl -lz ...`).
- **`axiom/crypto_portable.h`:** OpenSSL yoksa SHA-256 / SHA-1 / MD5 /
  HMAC-SHA256 / sabit zamanlı karşılaştırma. FIPS 180-4, RFC 1321, RFC 2104
  vektörleriyle doğrulandı. Güvenlik araçları hash olmadan çalışamaz.
- **Windows karşılıkları:** Winsock2, SRWLOCK, CONDITION_VARIABLE,
  CreateProcess, BCryptGenRandom, VirtualAlloc/VirtualQuery, `_stat64`,
  `_beginthreadex`, loopback TCP ile `socketpair`.
- **Açık hata politikası (D7):** epoll, `/proc`, ptrace, AES, zlib Windows'ta
  sessizce boş sonuç **vermez**; açık hata döndürür.
- **Test:** `tests/test_portability.py` — 21 test.

### Düzeltilen (P2-19 sırasında bulunan gerçek hatalar)
- **Çift sarma geçersiz `free`:** `axiom_owned_str_wrap(axiom_safe_strdup(x))`
  8 yerde; yeni intrusive modelde sahipli tamponu ham `free` ile bırakıyordu
  (date/hash fonksiyonları çöküyordu).
- **`exec_mem_run` SEGV:** RW tahsis edilmiş belleği çalıştırıyordu;
  `ax_os_alloc_rwx` ayrıldı.
- **zlib bloğunda iç içe `#if`:** regex guard'ı zlib bloğuna kaymıştı.

### Değişen (P2-17b — intrusive header bellek modeli)
- **String sahipliği artık intrusive header ile:** refcount verinin hemen
  önünde (32 bayt), veriyle aynı cache satırında. Global `ptr→refs` hash
  tablosu **tamamen kaldırıldı**.
- **Ölçüm** (`benchmarks/str_ownership_bench.c`): 150k canlı string oluşturma
  **−48%**, bırakma **−60%**, takip tablosu belleği **10 MB → 0**.
- **`axiom_ptr_is_static`:** `dladdr` yerine ELF segment aralığı kontrolü.
- **Geçicilik günlüğü thread-local:** hot path'te kilit yok.
- **`os_getenv` / `cli_args_get`** artık sahipli kopya döner.
- **`String`/`str` tip ayrımı gerekmedi:** çift serbest bırakma ve literal
  koruması header magic + segment kontrolü ile sağlanıyor.

### Düzeltilen (P2-17b sırasında bulunan gerçek hatalar)
- **`if`/`while` koşullarındaki geçici string'ler sızıyordu** (500 iterasyon →
  500 canlı string). Koşul bool'a çevrildikten sonra temizlik eklendi.
- **Erken `return` kapsamdaki diğer sahipli değişkenleri bırakmıyordu**
  (`_mark_escape` fonksiyon geneliydi). `str` dönüşünde escape kaldırıldı.
- **Dizi literali stack'te compound literal üretiyordu**; döndürülünce sarkan
  işaretçi (`return [id, "str:" + text]` → bozuk veri). Artık heap'te.
- **`?` hata yolu atanmamış değişkeni serbest bırakıyordu**; çöp dizi üzerinde
  `axiom_array_str_free` sonsuz döngüye giriyordu. `pending_init` koruması.
- **ASan taraması artık 21/21 temiz** (önce 18/21: 89 B sızıntı + redteam SEGV).

### Eklenen (P2-18f — self-hosted 15/21 → 21/21, tam parite)
- `bin/axiomc` artık **21 örneğin tamamını** derleyip doğru çalıştırıyor.
  Üç arka uç da tam: C 21/21, LLVM 21/21, self-hosted 21/21.
- **Tip yayılımı:** codegen'de sabit-nokta tip çıkarımı — `str`/`str[]`
  parametreleri ve struct metin alanları tohum; `ax_str` bildirimleri öğrenilir;
  struct dizi alanları ve `T[]` dönen fonksiyonlar için eleman-tipi haritaları.
- **`main() -> Result<int,str>`** desteği: Ok → exit 0, Err → stderr + exit 1.

### Düzeltilen (P2-18f'de bulunan gerçek hatalar)
- **Çoklu `requires`/`ensures` cümleleri** yutuluyordu (ikinci cümleden sonraki
  her şey önceki fonksiyonun gövdesine giriyordu).
- **`import "std:net:http.ax"`** çift uzantı (`http.ax.ax`) yüzünden dosya
  sessizce atlanıyordu.
- **`pcap_`/`fim_`/`forensics_` önekleri** std sarmalayıcılarını gölgeliyordu.
- **`__auto_type X = axiom_str_split(...)`**, struct dizi alanı elemanı ve
  `T[]` dönen fonksiyon sonucu `ax_int` sanılıyordu.
- **`rewrite_unknown_calls`** `axiom_*` çağrılarını bozuyordu (çift önek taraması).

### Değişen (P2-20 — skip'ler kapatıldı)
- **Redteam testleri artık varsayılan çalışır** (17 test). Kaçış kapısı:
  `AXIOM_SKIP_REDTEAM=1`. Önceki `AXIOM_ENABLE_REDTEAM=1` kapısı kaldırıldı.
- Self-hosted örnek listesi 8 → 20 (parite testiyle senkron tutulur).
- **Test sonucu: 976 passed, 0 skipped** (önce 945 + 2 skipped).

### Eklenen (P2-18e — self-hosted 12/21 → 15/21)
- `bin/axiomc` artık `11_packet2_advanced_network`, `18_web_api_framework` ve
  `20_stdlib_result` örneklerini de derleyip **doğru** çalıştırıyor
  (Faz 1 hedefi 8/21'in ~2 katı).

### Düzeltilen (P2-18e'de bulunan gerçek hatalar)
- **`x < y` generic sanılıyordu:** generic taraması `>` ararken sonraki
  ifadedeki `result_ok<int>`in `>`ını yakalıyordu; `if size < 0 { ...
  result_ok<int>(size) }` → `ax_size(size)`. Tarama ifade sınırında vazgeçiyor.
- **Struct dizi tipinde `capacity` alanı yoktu**; `axiom_array_push` onu
  kullandığı için struct dizili her program derlenemiyordu.
- **`result_err_with<T>` argüman ayrımı:** iç içe çağrının virgülü ayırıcı
  sanılıyordu; `split_top_level_args` (parantez derinliği + string farkındalığı).
- **`result_ok<float>`** `int` örneği üretiyordu.

### Eklenen (P2-18d — self-hosted 11/21 → 12/21)
- `bin/axiomc` artık `13_packet4_fuzzer_scanner` örneğini de derleyip doğru
  çalıştırıyor.
- **Dizi literalinde tip:** tüm elemanlar metinse `ax_array_str`/`ax_str[]`
  üretilir (önceden her dizi `int[]` idi → geçersiz C).
- **Çağrı bağlamı:** `csv_add_row`, `cli_set_args`, `json_build_object` gibi
  `str[]` bekleyen yerleşiklerde literal metin dizisine çevrilir.
- **`?` dönüş tipi:** yer tutucu (`__AXIOM_RET_TYPE__`) ile dış fonksiyonun
  Result tipi kullanılır; farklı value tipli Result'lar arasında hata taşınır.
- **`result_ok<T>` bilinmeyen T:** doğrudan struct literali üretilir.

### Düzeltilen (P2-18d'de bulunan gerçek hatalar)
- **Dizi literali tipi:** `(ax_int[]){"a","b"}` — geçersiz C.
- **`axiom_str_split`** `is_str_expr`'de `str` sanılıyordu (dizi döner).
- **`?` ile farklı Result tipleri arasında dönüş** derlenmiyordu.
- **`result_ok<Config>`** `int` örneği üretiyordu.
- **Parite testi flaky:** zaman/ağ ölçüm satırları normalize edildi.

### Eklenen (P2-18c — self-hosted 8/21 → 11/21)
- `bin/axiomc` artık `12_packet3_system_exploit`, `14_packet5_full_security_suite`
  ve `19_error_handling` örneklerini de derleyip **doğru** çalıştırıyor.
- **`?` operatörü** self-hosted derleyicide destekleniyor: `let x = f(y)?`
  Err'de (defer'ler çalışarak) üst fonksiyona iletir.
- **Tip çözücü operatörler:** `axiom_add_auto`, `axiom_eq_auto`,
  `axiom_neq_auto` — karar `_Generic` ile C derleyicisine bırakılır.
- **`tests/test_selfhosted_parity.py`** (14 test): self-hosted çıktısı Python
  sürücüsüyle karşılaştırılır; "derleniyor ama yanlış" ayrı regresyon testiyle
  kilitlendi.

### Düzeltilen (P2-18c'de bulunan gerçek hatalar)
- **`==` iki değişkende pointer karşılaştırması** yapıyordu (metin içeriği
  yerine adres). `12`/`14` derlenip `verify` düşürüyordu — sessiz yanlış kod.
- **`+` operatörü** tip bilinmediğinde derleme hatası veriyordu.
- **`?` karakteri lexer'da sessizce atılıyordu** (Result açılmıyordu).
- **`return` + `defer`** yolunda `ax_typeof` makro çağrılarında yanlış tip.
- **Bilinmeyen `ax_X(...)` çağrıları:** `rt_` öneki olmadan çağrılan
  yerleşikler (`json_parse`, `tcp_ping`, `cli_set_args`) C'ye çıplak geçiyordu.

### Eklenen (P2-18b — kısmi)
- **Self-hosted import çözümü:** `import "std/x/y"` (uzantısız) artık `.ax`
  eklenerek yükleniyor; önceden sessizce atlanıyordu.
- **Generic struct somutlaştırma düzeltmeleri:** `E` tip parametresi tanındı;
  `str[]` generic argümanı desteklendi; C tanımlayıcılarında `[]` → `_array`.
- **`rt_*` yerleşik eşlemesi:** genel `rt_X` → `axiom_X` kuralı eklendi
  (base64, dns, buf, regex, forensics, cli...).
- **`result_ok<T>` / `result_err_with<T>`:** açık tip argümanı varsa tipe özel
  makro, yoksa `_Generic` tabanlı `axiom_result_ok_auto`.

### Düzeltilen (P2-18b'de bulunan gerçek hata — HTTP sunucusu)
- **`http_server_send_response` RST üretiyordu:** yanıt gönderildikten sonra
  istemcinin isteği okunmadan soket kapatılıyordu. Okunmamış veri bulunan
  soketi kapatmak TCP RST gönderir ve **gönderilmiş yanıtı düşürebilir**;
  istemci bozuk/yarım veri görüyordu. Kapanıştan önce drain döngüsü eklendi.
  `tests/test_packet2_libs.py` artık 4/4 temiz (önceden ~%20 flaky).
- **Test port tahsisi:** `get_free_port` aynı portu tekrar dağıtabiliyordu;
  verilen portlar süreç boyunca tekrar kullanılmıyor.

### Eklenen (P2-18 — self-hosted 4/21 → 8/21)
- `bin/axiomc` artık `05_real_scanner`, `08_multithreaded_scanner`,
  `09_simd_vector_scan` ve `17_ai_tensor_neural_net` örneklerini de
  derleyip çalıştırıyor.

### Düzeltilen (P2-18'de bulunan gerçek hatalar)
- **`len(str)`** yanlış yerleşiğe gidiyordu (`axiom_len` = dizi `.length`).
  `axiom_slen_auto` makrosu eklendi (`_Generic` + statement expression, rvalue
  dahil).
- **UTF-8 kaynak kesilmesi:** self-hosted lexer `len(src)` (kod noktası) ile
  bayt indeksini karşılaştırıyordu; Türkçe/emoji içeren dosyalar sonda
  kesiliyordu. `str_byte_len` kullanılıyor.
- **`codegen_wrap_ensures`:** `b_len = len(body)` iken `str_sub` bayt tabanlı;
  çok baytlı gövdede kapanış `}` kayboluyordu.
- **`thread_create`:** `axiom_thread_create((void*)ax_fn, arg, false)` üretiliyor.
- **`main` void dönüşü:** `ax_main(); return 0;`.
- **`let x = f()`:** `__auto_type` ile struct dönen fonksiyonlar destekleniyor.
- **`axiomc` geçici dosyaları** PID ile tekilleştirildi (eşzamanlı çalışmada
  birbirini eziyordu).

### Düzeltilen (P2-17 — geçici string sızıntıları)
- **`print(f(x))` sızıntısı:** `PrintStmt` artık argümanlar bitince geçici
  mark'a kadar temizliyor. 500 iterasyonda izlenen string sayısı sabit (önce +500).
- **Sonucu atılan ifade deyimi:** çıplak `make(x)` çağrısının geçicileri bırakılır.
- **`continue` / `break` sızıntısı:** kısmi kapsam temizliği eklendi
  (`_capture_loop_cleanup`); döngü gövdesindeki `defer` de `continue`'da çalışır.
  Döngü dışı değişkenler etkilenmez (iç içe döngü testi).
- **`axiom_temp_release_keep`:** saklanan değer artık günlüğe geri konuyor; dış
  kapsam da görebildiği için "adopt edilen" değer sızmıyor.
- **Test:** `tests/test_temp_string_cleanup.py` — 15 test (C'de `str_owned_count`
  ile sayısal büyüme, iki arka uçta davranış, ASan).
- README (TR/EN) "bilinen sınır" maddesi kaldırıldı.

### Eklenen (P2-14 / P2-15)
- **`std/net/event_loop`:** kapsanmayan 7 fonksiyon test edildi
  (`event_is_writable/error/hangup`, `event_loop_mod`, `event_loop_event_fd/events`,
  `net_set_nonblocking`) + EPOLLHUP senaryosu. Kod değişikliği gerekmedi.
- **`std/text/unicode` NFC/NFD:** UCD 15.1.0 tabloları `tools/gen_unicode_tables.py`
  ile üretilir (2.061 ayrıştırma / 922 ccc / 941 birleştirme); Hangul algoritmik.
  `unicode_nfc`, `unicode_nfd`, `unicode_is_nfc`, `unicode_is_nfd`,
  `unicode_normalize(_result)`, `unicode_canonical_eq`, `unicode_ucd_version`.
  NFKC/NFKD gömülü tablo gerektirdiği için **açık hata** döner.
- **Test:** `tests/test_event_loop_coverage.py` (11), `tests/test_unicode_normalization.py` (16)
  — UCD konformansı Python `unicodedata` ile birebir, 11.172 Hangul hecesi roundtrip.

### Düzeltilen (P2-15'te bulunan gerçek hatalar)
- **Hangul LVT ayrıştırması** `(L, T)` üretiyordu (V kayıp). Doğrusu `((LV), T)`;
  özyineleme V'yi ekler. 11.172 heceli roundtrip testi bunu kilitler.
- **`char_to_str` ASCII dışı kod noktalarında geçersiz UTF-8 üretiyordu**
  (0..255 aralığını ham bayt yazıyordu). Artık tam UTF-8 kodlaması; surrogate ve
  aralık dışı değerler boş döner. Ham baytlar için `std/io/binary` `buf_*` kullanılır.

### Eklenen (P2-08 / P2-09 / P2-10 / P2-11)
- **`std/io/file` tam Result API:** yeni yerleşikler `file_size`, `is_directory`,
  `list_dir`, `remove_file`, `rename_file`, `create_dir`; sarmalayıcılar
  `file_size_result`, `list_dir_result`, `remove_file_result`,
  `rename_file_result`, `create_dir_result`, `copy_file_result`, `dir_present`.
  Veri hatası `Err` döner, sözleşme ihlali üretmez.
- **`std/text/regex` ReDoS kapısı:** iç içe niceleyici / aşırı derinlik /
  `{n,m} > 1024` / desen > 4096 bayt reddedilir (`regex_risk_level`).
  `regex_validate`, `regex_is_match_result`, `regex_find_result`,
  `regex_replace_result`, `regex_compile_result`, `regex_escape`.
- **`std/time/date` saat dilimi:** sabit ofsetli `date_format_tz`, `date_iso_tz`,
  `date_parse_iso`, `date_local_offset_minutes`, `date_offset_label`,
  `date_duration_label`. IANA tz veritabanı **yok** (belgelenmiş sınır).
- **Test:** `test_io_file_result_api.py` (12), `test_regex_safety.py` (9),
  `test_map_resize_collision.py` (8), `test_date_timezone.py` (9) — tümü C + LLVM
  paritesiyle.

### Doğrulanan (kod değişikliği yok)
- **`std/collections/map`:** yeniden boyutlandırma, çakışma zinciri, silme,
  üzerine yazma ve 500 kayıtlı ölçek test edildi. Uygulama zaten doğruydu;
  eksik olan doğrulamaydı.

### Eklenen (P1-05 + P1-06)
- **Red team sertleştirme:** `shellcode_allocate_rwx`/`shellcode_protect` (RW/RO/RWX,
  sözleşme ihlali derleme anında), `c2_crypto_random_hex` (CSPRNG, tekrarsızlık),
  `c2_hmac_sha256` (RFC 4231 vektörü), `c2_crypto_memcmp`, beacon roundtrip +
  kurcalama reddi. Ofansif testler artık varsayılan `pytest`'te atlanır;
  `AXIOM_ENABLE_REDTEAM=1` ile 17 test çalışır.
- **DFIR triyajı:** `examples/22_dfir_triage.ax` — `/proc` süreç listesi, dinlenen
  portlar, kritik dosya SHA-256, Sigma eşleşmesi → tek JSON rapor (risk + verdict).
- **Yeni kütüphane:** `forensics_list_processes()`, `json_escape()`.

### Düzeltilen (P1-06'da bulunan gerçek hatalar)
- **C: `str[]` use-after-free** — yerel `str` diziye eklendikten sonra kapsam
  çıkışında serbest bırakılıyordu. `array_push` artık `str[]` için sahiplenen
  `axiom_array_push_str` üretir.
- **LLVM: string literal çift çözümleme** — `"\\\""` (ters bölü + tırnak) tek tırnağa düşüyordu
  (sessiz veri kaybı). Kaçış tek noktada: `_llvm_escape_bytes`.
- **LLVM: `str_join` ABI** — `ax_array_str` by-value geçildiği için segfault.
  `axiom_str_join_ptr` (byval pointer) sarmalayıcısı eklendi.
- **`file_read` procfs** — boyutu 0 görünen `/proc` dosyaları boş dönüyordu;
  akış tabanlı okuma eklendi.

### Eklenen (P2-05)
- **LSP tam yetenek seti:** `references`, `prepareRename`/`rename`, `codeAction`,
  `documentFormatting`, `semanticTokens/full`, `signatureHelp`; `initialize`
  capabilities bunları duyurur.
- **Semantic tokens:** 12 tipli legend, LSP delta kodlaması; AST'den
  fonksiyon/struct/parametre/değişken sınıflandırması.
- **Quick fix:** bilinmeyen fonksiyon adı için en yakın builtin önerisi,
  değiştirilemez değişkene atama için `let mut` düzeltmesi.
- **Test:** `tests/test_lsp_full_features.py` — 24 test (birim + gerçek
  `bin/axiom-lsp` üzerinden protokol düzeyi).

### Eklenen (P2-04)
- **İngilizce doküman:** `README.en.md`, `docs/en/TUTORIAL.md` (994 satır),
  `docs/en/SPECIFICATION.md` (689 satır). TR ↔ EN karşılıklı bağlantılar.
- **CI doğrulaması:** `tests/test_docs_en.py` — 9 test: yapısal eşitlik
  (başlık seviyeleri + kod bloğu sayısı), çalıştırılabilir blokların derlenmesi,
  "çevrilmemiş Türkçe" tespiti, kırık bağlantı kontrolü.
- **README güncelliği:** registry v1 (P2-01/P2-02) ve `axiom doc` (P2-03)
  bilgileri her iki README'ye işlendi.

### Eklenen (P2-03)
- **`///` doc comment:** lexer `DOC` token; parser bunu `FunctionDecl.doc` /
  `StructDecl.doc` alanlarına bağlar. Blok içindeki `///` yorumları yok sayılır.
- **`axiom doc`:** `///` yorumlarından statik HTML (`docs/api/index.html`) veya
  JSON (`--json`, `-` = stdout) üretir. `requires`/`ensures` ve struct alanları
  dahil edilir; bozuk dosyalar atlanır.
- **std belgeleme:** `std/security/yara.ax` ve `sigma.ax` gerçek doc comment'leri
  ile belgelendi (47 öğe).
- **Test:** `tests/test_docgen.py` — 16 test (lexer, parser, HTML/JSON, CLI,
  gerçek `std/` üretimi).

### Eklenen (P1-04 + P2-02)
- **YARA/Sigma kapsamı:** 13 test (C + LLVM paritesi); ofset API'si, tek desen
  tarama, buffer tarama, motor `eval_raw`/`has_alert`, legacy yardımcılar.
- **Namespace:** `@kapsam/paket` desteği (depo dizini `@kapsam__paket`);
  paket adı doğrulaması ve path-traversal koruması.

### Düzeltilen
- **Sigma fail-open:** bilinmeyen operatör `contains`'a düşüyordu; artık `false`.
- **`sigma_parse_syslog`:** servis adı ilk boşluktan kesiliyordu (son olmalı).

### Eklenen (P1-03)
- **`axiom-scan` v0.1** (`examples/21_axiom_scan.ax`): `rules`, `scan`, `pcap`
  komutları; JSON çıktısı; tek statik ikili. 103 MB dosyada **0.56 s**.
- `std/security/yara_rules.ax`: YARA kural metni ayrıştırıcı (strings/condition,
  metin/hex-wildcard/regex desenleri, `any|all|N of them`).
- `tests/test_axiom_scan.py` — 13 test.
- Düzeltme: LLVM IR'de kaçışsız ters bölü (`\`) geçersiz string sabiti üretiyordu.
- Düzeltme (P1-03b): LLVM'de literal ile başlatılan `str` değişkenleri sahiplik
  takibine alınmıyordu (dangling pointer) ve `array_push` str elemanı için ek
  referans almıyordu. İki arka uç artık birebir aynı sonucu verir.

### Eklenen (P2-01)
- **Registry v1** (`axiom/registry.py`): içerik-adresli depo, ed25519 imza
  doğrulaması (openssl), semver aralıkları, transitive çözümleme, yanked reddi,
  döngü tespiti, path-traversal koruması, kendini onaran önbellek.
- `axpm search`; `[registry]` bölümü artık manifest yeniden yazımında korunuyor.
- `tests/test_registry.py` — 38 test; `docs/REGISTRY.md`.

### Eklenen (P1-01)
- **HTTP/1.1 istemcisi sağlamlaştırıldı:** `tcp_recv_all` (tek `recv` sınırı
  kaldırıldı), `http_chunked_decode`, `http_header_value` (büyük/küçük harf
  duyarsız), `tcp_set_timeout`, `http_request` (yapısal sonuç + yönlendirme
  takibi, döngü tespiti).
- `tests/test_http_client.py` — 4 test, gerçek TCP sunucusu, C + LLVM paritesi.

### Eklenen (P1-02)
- **Gerçek JSON parser** (`axiom_json_parse` …): recursive-descent DOM, iç içe
  nesne/dizi, `null`, ondalık/bilimsel sayı, `\uXXXX` + surrogate pair,
  200 seviye derinlik sınırı, konumlu hata mesajı, `01` reddi.
- `std/encoding/json` üzerinde `Result` tabanlı API: `json_parse_result`,
  `json_{str,int,float,bool}_at`, `json_has_path`, `json_is_null_at`, `json_len_at`.
- `tests/test_json_real_parser.py` — 14 test (C + LLVM paritesi).

### Düzeltilen
- LLVM: `return <struct>` içinde string argümanı kaçış olarak işaretlenmiyordu
  (`return result_err_str(pre)` → dangling pointer). Artık her `return` ifadesi
  kaçış analizine giriyor.

### Doküman
- **`TODO.md` yeniden yazıldı** — tek doğruluk kaynağı: nerede olduğumuz (ölçülmüş),
  nereye gittiğimiz (4 faz, kapılar), AI ajanları için okuma/çalışma kuralları,
  karar kayıtları (D1–D8), ölçüm panosu, arşiv listesi.

### Eklenecek
- Intrusive-header tabanlı string sahipliği ve `String`/`str` tip ayrımı.
- `runtime/core` + `runtime/platform` ayrımı; WASI hedefi.
- Merkezi paket registry'si veya resmî "git-only" politikası.
- AST tabanlı self-hosted derleyici (tam generics + sözleşme denetimi).
- Karşılaştırmalı benchmark paketi sonuçları.

## [0.5.0-alpha] — 2026-11-06

### Eklenen
- **Hata modeli:** `Result<T, E>` (`std/core/error.ax`) ve `?` operatörü.
  `?` Ok değerini açar, Err'yi üst fonksiyona iletir; erken dönüşte `defer` ve
  sahiplik temizliği çalışır. LLVM arka ucunda açık hata verir.
- `examples/19_error_handling.ax` — uçtan uca hata akışı örneği.
- **Stdlib `Result` katmanı:** `std/io/file` (`read_file`, `write_file`,
  `append_file`, `read_lines`), `json_get_*_result`, `http_get_result` +
  `http_status` + `http_body`, `https_get_result`, `exec_output_result`.
- `main` artık `Result<int, str>` dönebilir (Ok → 0, Err → stderr mesajı + exit 1).
- `result_err_with<T>`, `result_err_int/str/bool/strs` kurucuları.
- `examples/20_stdlib_result.ax`.
- **`docs/TUTORIAL.md`** — 15 bölümlük Türkçe başlangıç rehberi (kurulum,
  sözdizimi, struct/dizi, sözleşmeler, `Result`+`?`, stdlib, eşzamanlılık,
  araçlar, yaygın hatalar, bilinen sınırlamalar).
- `tests/test_tutorial_examples.py` — rehberdeki çalıştırılabilir kod bloklarını
  derleyerek doküman/dil ayrışmasını (doc rot) engeller; CI'a eklendi.
- **`SPECIFICATION.md` v0.5** — 19 bölümlük tam şartname (sözcüksel yapı, tipler,
  ifadeler, sözleşmeler, hata modeli, bellek modeli, modüller, eşzamanlılık,
  86 builtin kataloğu, ABI, çıkış kodları, EBNF özeti).
- `tests/test_specification.py` — şartnamedeki iddiaları kodla karşılaştırır
  (anahtar kelime listesi, tip listesi, gölgeleme, `as`, exit kodları).
- **LLVM `break`/`continue`** desteği (döngü etiket yığını, kapsam temizliği).
- `@simd` LLVM'de gerçek karşılık kazandı: `attributes #0 = { "target-features"="+avx2,+fma" }`
  (önceden tanımsız `#0` idi ve clang sessizce yok sayıyordu).
- Self-hosted derleyicide `ensures return ...` bozuk C üretiyordu
  (`(( * b) <= a)`); `return` artık `__ax_ret`'e bağlanıyor.
- Self-hosted builtin haritasına `simd_*`, `math_*`, `thread_*`, `mutex_*`,
  `atomic_*` eklendi.
- `tests/test_lsp_lifecycle_and_array_builtins.py` — LSP yaşam döngüsü
  (`didSave`/`didClose`/`initialized`/`exit`, bilinmeyen metod `-32601`,
  diagnostic yayını) ve dizi fabrika builtin'leri (`array_create_*`,
  `array_push_*`) kilitlendi.
- `tests/test_selfhosted_contracts.py` — `ensures` davranışı ve desteklenen
  örnek kümesi kilitlendi.
- `tests/test_error_helpers_and_simd.py` — `std/core/error` yardımcıları
  (parite + yanlış varyant abort) ve `@simd` kapsamı.
- `tests/test_overload_and_cli_errors.py` — overload çözümlemesi (tip, arity,
  void, generic dönüş, hatalı tip, yinelenen imza) ve CLI hata yolları
  (eksik dosya × 8 komut, sözdizimi/yarısmantik/modül hatası) kilitlendi.
- `?` operatörü ve `defer` LLVM arka ucunda destekleniyor; 19/19 örnek iki
  arka uçta da derlenip çalışıyor.
- LLVM arka ucunda **string kapsam temizliği**: `let` ile sahiplenilen string'ler
  döngü gövdesi, if/else dalları ve erken dönüşlerde `axiom_str_owned_release`
  ile bırakılıyor; struct alanına/diziye/cağrı argümanına kaçan değerler kaçış
  analizi ile korunuyor. Dönen string'ler caller için `retain` ediliyor.
- `axpm update` — git bağımlılıklarını yeniden çeker, kilidi yeniler.
- `axpm verify` — `axiom.lock` SHA-256 doğrulaması, kurcalama tespiti.
- `axpm tree` — bağımlılık ağacı ve checksum özeti.
- `axpm remove [--purge]` — manifest + lock temizliği.
- `axiom check --smt` / `--all` — SMT tabanlı sözleşme doğrulaması.
- `--features offensive` — ofansif modüllerin derleme zamanı izolasyonu (varsayılan kapalı).
- LLVM arka ucunda DWARF: `DICompileUnit`, `DISubprogram`, `DILocation`, `DILocalVariable`, `llvm.dbg.declare`.
- Self-hosted derleyicide `Box<str>`, `Box<float>`, `Pair<T,U>` generics.
- `str_owned_count()` tanılama builtin'i.
- Proje altyapısı: `pyproject.toml`, `Makefile`, `.gitignore`, GitHub Actions CI matrisi.

### Düzeltilen
- **LLVM `break`/`continue` sessizce yok sayılıyordu** (C `S: 12`, LLVM `S: 55`);
  artık döngü etiketiyle doğru dallanıyor ve döngü kapsamını temizliyor.
- **Aynı blokta `let` yeniden tanımı** C'de derleme hatası veriyordu; artık
  checker net bir semantik hata veriyor (iç blokta gölgeleme serbest).
- **`as str`** kabul edilip çöp kod üretiyordu; artık reddediliyor (`int_to_str` önerilir).
- **Döngü dışında `break`/`continue`** kabul ediliyordu; artık derleme hatası.
- **`0x10` / `1_000` / `1e9`** "Tanimlanmamis degisken" gibi şaşırtıcı hatalar
  veriyordu; artık anlaşılır `LexerError`.
- LLVM arka ucunda `defer` sessizce yok sayılıyordu; artık LIFO çalışıyor.
- Struct döndüren runtime fonksiyonları LLVM'de kayıt dönüşü ile çağrılıyordu
  (C tarafı sret kullanıyor) → segfault. Bildirim ve çağrılar açık `sret`'e sabitlendi.
- Generic tip argümanı dizi içerdiğinde geçersiz C tanımlayıcısı üretiliyordu
  (`Result<str[], str>` → `Result_str[]_str`); artık `Result_str_array_str`.
- Struct tanımları bağımlılık sırasına göre üretilmiyordu (struct alanı olarak
  başka struct kullanıldığında derleme hatası); topolojik sıralama eklendi.
- `?` erken dönüşünde hedef `Result`'ın `value` alanı yanlış tiple
  dolduruluyordu (struct/dizi tiplerinde derleme hatası).
- `axiomc` komut enjeksiyonu (`execvp` + kabuk metakarakteri filtresi).
- Tamsayı taşması sessiz sarması → `ARITHMETIC_OVERFLOW` (exit 101).
- Sıfıra bölme/mod (`axiom_safe_div` / `axiom_safe_mod`).
- Dizi atamasında referans paylaşımı → derin kopya (değer anlambilimi).
- `array_push` döngü sızıntısı (heap dizi tampon kayıt defteri).
- `str_split`, base64/hex/hash/json gibi 40+ üreticinin sahiplik kaydı.
- `str_free` double-free ve literal `free` çökmesi.
- JWT doğrulamada double-free (ham `free` → `axiom_str_release`).
- Prover: `if` / `while` / `verify` koşullarındaki fonksiyon çağrılarının denetlenmemesi.
- Self-hosted derleyicide tip hatalarının sessizce geçmesi (`-Werror` seti).
- Boşluk/Türkçe karakterli dosya yollarının reddedilmesi.

### Bilinen sınırlamalar
- İfade içi geçici string'ler (`print(f(x))`) sahiplik tablosunda kalır; intrusive header sonrası çözülecek.
- Merkezi registry yok; `install` registry bağımlılığında açık hata verir.
- `--target wasm32-wasi` / `aarch64` harici sysroot gerektirir ve deneyseldir.
- LLVM arka ucunda struct-array ve bazı optimizasyon yolları C arka ucuna göre daha sınırlı.
- Bağımsız benchmark sonuçları henüz yayınlanmadı.

## [0.4.0] — 2026-11-05

### Eklenen
- `defer`, `match`, `invariant`, `as` sözdizimi.
- `Option`/`Result` çekirdek modülleri.
- LSP sunucusu (`axiom-lsp`), paket yöneticisi iskeleti, DWARF (`#line`) C arka ucunda.
- Fuzzing altyapısı (`tests/fuzz/`).

## [0.3.0] — 2026-11-04

### Eklenen
- Z3 SMT teorem ispat motoru (`axiom prove --smt`, `emit-smt`).
- Doğrudan LLVM IR arka ucu (`emit-llvm`, `--backend=llvm`).
- SIMD (`@simd`) vektör desteği.
- REPL, formatter, `axiom init`.

## [0.2.0] — 2026-11-04

### Eklenen
- Red team / blue team / AI / web standart kütüphane paketleri.
- Self-hosted derleyici (`bin/axiomc`).

## [0.1.0] — 2026-11-04

### Eklenen
- Lexer, parser, tip denetleyici, C99 kod üretici.
- `requires` / `ensures` / `verify` sözleşmeleri ve sembolik ispatlayıcı.
- Yerel ELF üretimi (`axiom build`).
