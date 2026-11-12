# Axiom (λx) — Global Standart Sistem Dili Master Yol Haritası (Production Roadmap)

> **Mühendislik İlkesi:** Sıfır Taviz, Derin Mühendislik, Sesli Matematiksel İspat ve Gerçek Donanım Başarımı.

---

## 📌 FAZ 1: Bellek Güvenliği & Deterministik Temizlik (Zero-Leak RAII & Defer)
- [x] **1.1. `defer` Sözdizimi ve Kapsam Temizliği (LIFO Scope Exit):**
  - `defer <stmt>;` veya `defer { <block> }` sözdiziminin Lexer, Parser, AST, Checker ve Kod Üreticilerine eklenmesi.
  - Erken dönüşlerde (`return`) ve blok sonlarında ertelenen ifadelerin ters sırada (LIFO) garantili yürütülmesi.
- [x] **1.2. Otomatik Kaynak Temizliği (Scope-Based Resource Cleanup):**
  - Dinamik ayrılan metinler ve tensörler için güvenli serbest bırakma ve çift serbest bırakma koruması (axiom_safe_free, axiom_str_free, axiom_buf_free, axiom_tensor_free).
- [x] **1.3. ASan / UBSan Entegrasyonu ve Bellek Kaçağı Sıfırlama:**
  - `axiom test --asan`, `axiom build --asan` / `--ubsan` ve C derleme flag'lerinde `-fsanitize=address,undefined -g -fno-omit-frame-pointer` ile sıfır kaçak / sıfır UAF (use-after-free) garantisi.

---

## 📌 FAZ 2: Gelişmiş Tip Sistemi & Null-Safety (Option, Result, Match, Generics)
- [x] **2.1. Null-Safety & `Option<T>` / `Result<T, E>`:**
  - `Option<T>` (`OptionInt`, `OptionStr`, `OptionBool`) ve `Result<T, E>` (`ResultInt`, `ResultStr`) `std/core/option.ax` ve `std/core/result.ax` mimarisi, güvenli `unwrap`, `unwrap_or`, `unwrap_err` sözleşmeleri.
- [x] **2.2. Generic (Şablon) Tip Parametreleri (`<T>` Monomorphization):**
  - Fonksiyon ve veri yapılarında (`struct Box<T>`, `fn wrap<T>`) tip parametre soyutlaması.
  - Tip denetleyicide tam monomorflaştırma (monomorphization), somut tür (`Box_int`, `wrap_int`) üretimi ve C/LLVM arka uç entegrasyonu (`tests/test_generics.py`).
- [x] **2.3. Tüketici Örüntü Eşleme (`match` Expression & Statement):**
  - Tüm varyasyonları denetleyen ve eksik dallara izin vermeyen tüketici (exhaustive) örüntü eşleme.
  - Wildcard (`_`), literal ve değişken bağlama desenleri; derleme anında exhaustiveness ve tip kontrolü (`tests/test_match_pattern.py`).
- [x] **2.4. Sıkı Açık Tip Dönüşümleri (Explicit Casting):**
  - `as int`, `as float` desteği, `((ax_int)(<expr>))` güvenli C ve LLVM cast kod üretimi.

---

## 📌 FAZ 3: Sesli SMT İspatlayıcı & Döngü İnvariantları
- [x] **3.1. Döngü İnvariantı (`invariant` Keyword):**
  - `while` ve `for` döngülerinde `invariant <expr>` sözdizimi, Floyd-Hoare tümevarımı (Base case, Inductive step, Postcondition) ile Z3 SMT üzerinden sesli ispat (PROVEN) motoru.
- [x] **3.2. Statik Dizi Sınır İspatı (Static Bounds Proof):**
  - Döngü invariantı ile dizi sınırlarının ve değişken invariantlarının SMT tümevarımıyla matematiksel garantilenmesi.

---

## 📌 FAZ 4: Derin Standart Kütüphane (Gerçek AVX2 SIMD, Epoll Async, YARA/Sigma, Unicode)
- [x] **4.1. Donanımsal AVX2/FMA SIMD GEMM:**
  - x86_64 `_mm256_fmadd_pd` vektörel komutları ile önbellek bloklamalı (cache-blocked) gerçek SIMD tensör matris çarpımı ve CPU özellik denetimli runtime fallback mimarisi.
- [x] **4.2. Linux Epoll Asenkron Ağ Reaktörü:**
  - `std/net/event_loop.ax` ile non-blocking 100K+ bağlantı yönetimi, pipe/socketpair ve non-blocking TCP desteği.
- [x] **4.3. Gerçek YARA & Sigma Kural Motorları:**
  - `std/security/yara.ax`, `std/security/sigma.ax` ve runtime motoru ile hex wildcard ('48 89 ?? 55', 'E8 ?? ?? ?? ??'), Boyer-Moore-Horspool / Sunday Quick-Search bayt tarama, ofset denetimleri, 'all/any/N of them' çoklu imza koşulları; Sigma telemetri alan eşleme ('contains', 'startswith', 'endswith', 'regex', 'equals'), log türü yalıtımı (syslog, web, auth), false positive filtreleme ve risk şiddet puanlaması (Low, Medium, High, Critical).
- [x] **4.4. Tam Unicode (UTF-8 Grapheme Cluster) Motoru:**
  - UAX #29 grapheme cluster parsing, Türkçe `İ`/`ı` case folding ve tam UTF-8 kodlama motoru.

---

## 📌 FAZ 5: Paket Yöneticisi, LSP & Hata Ayıklama (axpm, LSP, DWARF)
- [x] **5.1. Paket Yöneticisi (`axiom pkg` / `axpm`):**
  - `axiom.toml` manifestosu ve `axiom.lock` deterministik kilit dosyası (SHA-256 sağlama toplamı) ile tam bağımlılık yönetimi; `init`, `add`, `install`, `build`, `run`, `test` alt komutları.
- [x] **5.2. Language Server Protocol (LSP - `axiom-lsp` / `axiom lsp`):**
  - JSON-RPC 2.0 stdio protokolü, didOpen/didChange/didSave/didClose yaşam döngüsü, anlık Lexer/Parser/Checker publishDiagnostics, otomatik tamamlama (completion), kaynak tanımına gitme (go-to-definition) ve sözleşme/tip hover kartları.
- [x] **5.3. DWARF Debug Sembolleri (`-g`):**
  - GDB ve LLDB ile doğrudan `.ax` kaynak kod satırlarında adım adım hata ayıklama (source-level debugging) sağlayan `#line` C önişlemci direktifleri ve `-g3 -O0 -fno-omit-frame-pointer` derleme altyapısı.
- [x] **5.4. Çoklu Mimari Desteği (Cross-compilation):**
  - x86_64 (`x86_64-linux-gnu`), aarch64 (`aarch64-linux-gnu`), WebAssembly (`wasm32-wasi`) çoklu mimari derleme altyapısı ve `--target` CLI bayrağı.

---

## 📌 FAZ 6: Self-Hosted Derleyici Eşitliği (`bin/axiomc` %100 Parity)
- [x] **6.1. Dilin %100'ünü Derleyebilen `bin/axiomc`:**
  - Axiom dilinin tamamını bağımsız olarak derleyen native ikili (`compiler/tokens.ax`, `compiler/lexer.ax`, `compiler/parser.ax`, `compiler/codegen.ax`, `compiler/main.ax`).
  - Yeni dil sözdizimlerinin (`defer`, `invariant`, `as`, `match`, `Option`, `Result`) self-hosted derleyicide sorunsuz parse edilmesi ve C99 kod üretimi (`tests/test_self_hosted.py`).
- [x] **6.2. Deterministik / Hermetik Derleme:**
  - Aynı kaynak kod iki kez derlendiğinde üretilen C kodunun SHA256 özetleri ve baytları birebir özdeş (%100 deterministik çıktı).

---

## 📌 FAZ 7: Fuzzing, Sürekli Entegrasyon & Sertleştirme
- [x] **7.1. Fuzzing Altyapısı (`tests/fuzz/`):**
  - `fuzz_lexer.py`: Rastgele bayt ve UTF-8 bozulmaları ile Lexer çökme ve bellek taşması testleri.
  - `fuzz_parser.py`: Rastgele bozuk AST, parantez fırtınası ve özyineleme derinlik sınırı koruması.
  - `fuzz_json.py`: `std/encoding/json.ax` için derin iç içe JSON ve geçersiz unicode/escape fuzzing'i.
  - `fuzz_yara.py`: Bozuk hex wildcard ve karmaşık regex pattern'leri ile YARA/Regex motoru fuzzing'i.
- [x] **7.2. Otomatik CI Regresyon Matrisi (`tools/ci_matrix.sh`):**
  - Tüm test suitini, ASan ve UBSan kontrollerini, self-hosted bootstrap testini ve kod biçimlendirmeyi tek bir güvenli bash betiğinde çalıştıran 0 hata garantili CI matrisi.
- [x] **7.3. Negatif Güvenlik ve İstismar Test Suiti (`tests/test_negative_security.py`):**
  - Dizi sınır aşımı (OOB) istismarı denemesi -> `axiom_bounds_check` tarafından kod 102 ile yakalama.
  - Tip karışıklığı (Type confusion: int < str, vb.) -> Checker tarafından SemanticError ile engelleme.
  - Eksik return açığı (Missing return) -> SemanticError ile tam kontrol akışı doğrulaması.
  - ASan ile Tensor double-free ve dinamik bellek UAF koruma garantisi.
  - TLS sertifika sahteciliği / MitM denemesi -> Geçersiz sertifikada bağlantının anında reddedilmesi.
