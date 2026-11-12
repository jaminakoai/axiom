# Axiom (λx) — Kalan İşler ve Geliştirme Yol Haritası

**Tarih:** 5 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Dayanak:** `~/Desktop/Axiom_Duzeltme_Dogrulama_Raporu_2026-11-05.md`
**Amaç:** Düzeltilmesi tamamlanmayan maddeler + henüz hiç ele alınmamış eksikler + eklenmesi gereken yetenekler için uygulanabilir plan.

---

## 0. Öncelik Matrisi

| Öncelik | Konu | Neden şimdi |
|---|---|---|
| **P0-A** | Bellek sahipliği (sızıntı, aliasing, double-free) | Dilin ana güvenlik iddiası çürük |
| **P0-B** | Aritmetik taşma | Sessiz veri bozulması |
| **P0-C** | Prover sesliliği (koşul/`verify` çağrıları) | `check` yanlış yeşil veriyor |
| **P1-A** | Self-hosted tip denetleyicisi + tam generics | `%100 parity` iddiası |
| **P1-B** | LLVM’de kalan 6 örnek + DWARF | İki backend eşitliği |
| **P1-C** | Registry + `--rev` + gerçek kurulum | Paket ekosistemi |
| **P1-D** | Ofansif modül opt-in izolasyonu | Uyum/CI güvenliği |
| **P1-E** | Doküman iddialarının temizlenmesi | Güven ve dürüstlük |
| **P2** | Araçlar, standart kütüphane derinliği, süreç | Üretime yaklaşma |

Tahmini efor: P0 ~2–3 hafta, P1 ~6–8 hafta, P2 ~3–6 ay (tek geliştirici varsayımıyla).

---

## 1. P0-A — Bellek Sahipliği Modeli

Bu, projenin en büyük teknik borcu. Üç ayrı hata aynı kökten geliyor: **string ve dizi tiplerinde sahiplik bilgisi yok.**

### 1.1 String tipini sahiplik duyarlı hâle getir

**Mevcut:** `typedef const char* ax_str;`

**Öneri:**

```c
typedef struct {
    ax_int len;
    ax_int cap;
    char*  data;
    bool   owned;   // literal ise false
} ax_string;
```

- `owned == false` ise `free` no-op.
- `axiom_str_concat` yeni tampon ayırırken eski tamponu sahiplenme kuralına bağla.
- Geçiş maliyeti yüksekse kısa vadeli çözüm: yan yana bir sahiplik tablosu (arena) — ama uzun vadede struct doğru yol.

**Kabul kriteri:** `axiom run --asan leak.ax` sıfır sızıntı; `str_free` double-free’de çökmez; literal `free` no-op.

### 1.2 Kapsam tabanlı otomatik temizlik (RAII/defer)

Altyapı zaten var: `codegen_c.py` içinde `defer_stack` ve `emit_deferred` mevcut.

**Yapılacak:**

- `LetDecl` ile tanımlanan sahipli string/dizi/tensor için kapsam sonunda otomatik `drop` enjekte et.
- Erken `return` yollarında `defer` zincirini çalıştır (kısmen var, test edilmeli).
- `str_free` çağrısından sonra işaretçiyi `NULL` yap (mevcut `axiom_safe_str_free` makrosu bunu yapıyor; `axiom_str_free` fonksiyonu yapmıyor).

**Kabul kriteri:** 1.000 iterasyonluk string birleştirme döngüsü ASan/LSan altında temiz; `defer` erken `return`’de çalışıyor.

### 1.3 Dizi değer semantiği veya açık referans semantiği

İki seçenek var; biri seçilip **dokümante edilmeli**:

**Seçenek A — Değer semantiği (README’nin iddiası):**
- `let b = a` sırasında derin kopya üret (`axiom_array_clone_*`).
- `array_push` copy-on-write ile çalışsın.
- Dezavantaj: performans ve bellek maliyeti.

**Seçenek B — Referans semantiği (Rust `Rc`/paylaşımlı):**
- README/SPEC’te “diziler referanstır, `clone()` gerekir” diye düzelt.
- `let a` immutable ise `a` üzerinden mutasyon derleme zamanında engellensin.

**Kabul kriteri:** `let b = a; b[0] = 99` ya `a`’yı değiştirmez (A) ya da derleyici bunu açıkça belgeler/engeller (B). Test eklenir.

### 1.4 Double-free / use-after-free koruması

- `axiom_str_free` sonrası işaretçi `NULL`’lansın (fonksiyon imzası `const char**` olmalı veya makro kullanılmalı).
- `axiom_safe_free` makrosu zaten var; standart API bu makroya yönlendirilmeli.
- ASan testi: `str_free(s); str_free(s)` temiz geçmeli.

### 1.5 Dizi `array_push` sızıntısı

Mevcut makro her eklemede yeni `malloc` yapıyor, eskisini bırakmıyor. `realloc` tabanlı ve kapasiteli (`len`/`cap`) bir yapıya geçilmeli.

---

## 2. P0-B — Aritmetik Taşma Koruması

### 2.1 Güvenli aritmetik makroları

`runtime.h` içine ekle:

```c
#define axiom_safe_add(a, b, line) ({ \
    ax_int _r; \
    if (__builtin_add_overflow((a), (b), &_r)) \
        axiom_contract_fail("ARITHMETIC_OVERFLOW", "no overflow", "add", (int)(line), "Tasma hatasi!"); \
    _r; \
})
```

Aynı şekilde `sub`, `mul`, `neg` (INT64_MIN). `codegen_c.py` ve `compiler/codegen.ax` içindeki `BinaryOp` üretimini bu makrolara bağla.

### 2.2 Politika seçimi

- Varsayılan: **checked** (taşmada hata).
- `--release` veya `--fast-math` benzeri bir bayrakla wrapping/sarma opsiyonu.
- Açık API: `wrapping_add`, `saturating_add`.

### 2.3 Testler

| Girdi | Beklenen |
|---|---|
| `INT64_MAX + 1` | exit 101, `ARITHMETIC_OVERFLOW` |
| `INT64_MIN - 1` | exit 101 |
| `INT64_MIN * -1` | exit 101 |
| `INT64_MIN / -1` | exit 101 |
| `INT64_MAX * 2` | exit 101 |

**Kabul kriteri:** Tümü güvenli durur; `--ubsan` altında da temiz.

---

## 3. P0-C — Prover Sesliliği

### 3.1 `eval_condition` içinde fonksiyon çağrılarını denetle

`axiom/prover.py:418` içindeki `eval_condition` şu an `FunctionCall` düğümünü işlemiyor. Ekle:

```python
if isinstance(expr, FunctionCall):
    self.check_function_call(expr, env)
    return None  # veya bilinen aralık
```

Aynı şekilde `UnaryOp`, `CastExpr`, `MatchExpr` içindeki çağrılar için de özyinelemeli denetim.

### 3.2 Etkilenen düğümler

- `IfStmt.condition`
- `WhileStmt.condition`
- `VerifyStmt.condition`
- `MatchStmt` guard’ları (varsa)
- `ForRangeStmt` start/end (zaten `eval_expr_interval` üzerinden gidiyor)

### 3.3 `axiom check` için `--smt`

`check` şu an yalnızca sembolik motoru çalıştırıyor. Ekle:

```bash
axiom check file.ax          # sembolik (hızlı)
axiom check file.ax --smt    # Z3 (sesli)
axiom check file.ax --all    # ikisi
```

Varsayılan davranış netleştirilmeli; “Kesin İspat” yalnızca her iki motor da onaylarsa yazılmalı.

### 3.4 Seslilik test matrisi

| Konum | Örnek | Beklenen |
|---|---|---|
| `print(...)` | `print(f(99999))` | ✅ yakalanır (mevcut) |
| `let` | `let r = f(99999)` | ✅ (mevcut) |
| `if` | `if f(99999) {}` | ❌ **yakalanmıyor** |
| `while` | `while f(99999) {}` | ❌ |
| `verify` | `verify f(99999)` | ❌ |
| iç içe çağrı | `g(f(99999))` | ✅ |
| `match` | `match f(99999) {}` | test edilmeli |

**Kabul kriteri:** Tüm satırlar hem sembolik hem Z3’te kırmızı; `check` varsayılanı kırmızı.

---

## 4. P1-A — Self-Hosted Derleyici Eşitliği

### 4.1 Tip denetleyici ekle

`compiler/` içine `checker.ax` ekle veya `parser.ax` sonrası bir doğrulama geçişi yaz:

- `let x: int = "hello"` → hata
- `1 < "abc"` → hata
- eksik `return` → hata
- tanımsız değişken/fonksiyon → hata
- argüman sayısı/tipi uyuşmazlığı → hata

**Geçici önlem:** `axiom_compile_c` içindeki `-Wno-int-conversion`, `-Wno-int-to-pointer-cast`, `-Wno-pointer-to-int-cast` susturmalarını **kaldır**. Bu, hataları gizlemek yerine görünür yapar.

### 4.2 Tam generics

Şu an kırılan senaryo:

```axiom
fn wrap<T>(x: T) -> Box<T> { return Box<T> { val: x }; }
```

Monomorflaştırma sırasında dönüş tipi ve gövdedeki `Box<T>` birlikte çözülmeli. `Box<T>` → `Box_int` dönüşümü hem imzada hem `return` ifadesinde uygulanmalı.

Test matrisi:
- `Box<T>` alan/ilkleyen ✅ (mevcut)
- `<T>` dönen fonksiyon ❌
- `<T, U>` çift parametre → test edilmeli
- generic fonksiyon → generic fonksiyon çağrısı → test edilmeli
- generic + struct alanı içinde generic → test edilmeli

### 4.3 Taşınabilir yol çözümü

- `get_axiom_root()` yalnızca `PWD`/`AXIOM_HOME` ile değil, **çalıştırılabilir dosyanın konumu** ile de çalışmalı (`/proc/self/exe` benzeri; runtime’a `axiom_exe_dir()` eklenebilir).
- `emit-c` çıktısında mutlak `#include` yerine göreli veya `-I` ile çözülen bir yol kullanılmalı.
- Masaüstü sabit yolu tamamen kaldırılmalı.

### 4.4 Yol beyaz listesini düzelt

`is_safe_path` yerine:

- Yasaklı karakterler: `; | & $ ` \n \r` ve kontrol karakterleri.
- Boşluk, Unicode ve diğer meşru karakterlere izin ver.
- Mümkünse hiç yol filtresi kullanma; `execvp` zaten shell çalıştırmıyor. Filtre yalnızca savunma katmanı olmalı, işlevi kısıtlamamalı.

**Kabul kriteri:** `boş luk/merhaba.ax` derlenir; `x;touch y` reddedilir.

---

## 5. P1-B — LLVM Backend Tamamlama

### 5.1 Kırılan 6 örnek

| Örnek | Kök neden | Düzeltme |
|---|---|---|
| `08_multithreaded_scanner` | `alloca void` | `thread_create` dönüş tipi `void` sanılıyor; `i64` olmalı |
| `11_packet2_advanced_network` | `verify_ok.13:` void etiketi | `verify` ifadesi basic block olarak üretiliyor; `i1` koşul bloğu olmalı |
| `12_packet3_system_exploit` | `store %struct.ax_array` | struct dizi tipi eksik parametre (`ax_array_str` gibi) |
| `15_redteam_offensive_suite` | `ret void` | `void` dönen fonksiyonda `ret i64` üretiliyor |
| `16_blueteam_defensive_suite` | `load i8*` | pointer tipi `i8**` yerine `i8*` |
| `18_web_api_framework` | `store %struct.ax_array ,` | boş tip parametresi; struct alan tipi çözülmemiş |

### 5.2 Test matrisi

- 19 örneğin **tamamı** `--backend=llvm` ile derlenip çalıştırılmalı.
- CI’da iki backend paralel çalışmalı; biri kırılırsa build kırılmalı.

### 5.3 DWARF

LLVM IR’e `!dbg` metadata ekle:
- `DIFile`, `DISubprogram`, `DILocation`.
- `--debug` bayrağı LLVM backend’inde de çalışmalı.
- GDB/LLDB ile `.ax` satırlarında breakpoint testi.

### 5.4 `ensures` kapsamı

Statik ispatlayıcı zaten çoğu ihlali yakalıyor; yine de LLVM’de runtime `ensures` denetimi tüm `return` yollarında olduğundan emin ol (iç içe `if`, `match`, erken dönüşler).

---

## 6. P1-C — Paket Yöneticisi

### 6.1 Registry protokolü

İki seçenek:

**A. Basit HTTP registry:**
- `GET /packages/<name>/<version>` → tarball
- `GET /packages/<name>/<version>/checksum`
- İndirilen tarball’ın SHA-256’sı lock’a yazılır.
- `axpm install` gerçekten indirir, açar, checksum doğrular.

**B. Git-only model (daha kolay):**
- Registry’yi kaldır; tüm bağımlılıklar `git` + `rev`/`tag` olsun.
- README’de “registry deneysel” yerine “registry yok, git kullanın” denir.

### 6.2 `--rev` desteği

```bash
axpm add foo --git URL --rev v1.2.3
axpm add foo --git URL --branch develop
axpm add foo --git URL --tag v1.0.0
```

Manifest’e doğru alan yazılmalı; `main` varsayılanı kaldırılmalı veya `HEAD` kullanılmalı.

### 6.3 Kurulum doğruluğu

- Bağımlılık gerçekten yoksa `install` **hata** vermeli, başarı mesajı vermemeli.
- `axiom.lock` checksum’u yeniden doğrulanmalı (`axpm verify`).
- `axpm tree`, `axpm update`, `axpm remove` eklenmeli.

### 6.4 Testler

- Gerçek bir genel Git deposundan (veya yerel `file://` repo) klonla → build → çalıştır.
- Checksum bozulduğunda `install` reddetmeli.
- Ağ yokken anlaşılır hata.

---

## 7. P1-D — Ofansif Modül İzolasyonu

### 7.1 Opt-in model

- Modülleri `std/security/` altından `offensive/` ayrı köküne taşı veya `std:offensive:*` ad alanına al.
- Derleme zamanı bayrak: `axiom build --features offensive`.
- `import "std:security:shellcode"` yalnızca bayrak açıksa çözülsün.
- README’de açık uyarı ve kullanım koşulları.

### 7.2 Testler

- Varsayılan `pytest` çalıştırmasında shellcode testleri **skip** (opt-in `AXIOM_ENABLE_REDTEAM=1`).
- CI’da ayrı, izole bir job.

### 7.3 Ek dokümanlar

- `SECURITY.md`: sorumlu açıklama, kapsam, yasal uyarı.
- `docs/offensive.md`: yalnızca izinli ortam kuralları.

---

## 8. P1-E — Doküman ve İddia Temizliği

### 8.1 Kaldırılacak/revize edilecek ifadeler

| Dosya | Satır | Sorun | Öneri |
|---|---|---|---|
| `README.md` | 19 | “Otomatik referans temizliği + değer anlambilimi” | “Kapsam tabanlı `defer` var; otomatik temizlik yol haritasında” |
| `SPECIFICATION.md` | 9, 10, 135 | “değer anlambilimi”, “RAII ile anında temizlenir” | Gerçek davranışı yaz veya “hedef” olarak işaretle |
| `GLOBAL_LANGUAGE_ROADMAP.md` | 7, 14 | “Zero-Leak”, “sıfır kaçak garantisi” | “Hedef: sıfır kaçak”; ölçüm sonucunu ekle |
| `README.md` | 6 | “ARM64” rozeti | “x86_64 (ARM64 deneysel)” |
| `README.md` | 326–330 | Performans yıldızları | Benchmark eklenene kadar “ölçülmedi” |

### 8.2 SPECIFICATION güncellemesi

- Sürüm `v0.5` yapılmalı.
- Eklenecek bölümler:
  - Generics ve monomorflaştırma
  - `defer`, `invariant`, `match`, `as`
  - `Option`/`Result` (mevcut hâli ve sınırları)
  - Bellek modeli (gerçek davranış)
  - Hata modeli ve çıkış kodları
  - Thread/atomic
  - LSP/paket yöneticisi
  - ABI/FFI
- Yinelenen “## 3.” başlığı düzeltilmeli.
- EBNF dilbilgisi eklenmeli.

### 8.3 Çıkış kodu kataloğu

| Kod | Anlam |
|---|---|
| 101 | Sözleşme/aritmetik ihlali |
| 102 | Dizi sınır ihlali |
| 127 | exec başarısız |
| 128+N | sinyal |

Dokümante edilmeli.

---

## 9. P2 — Araçlar ve Altyapı

### 9.1 Proje/süreç

- **Git deposu başlat.** `.gitignore`: `__pycache__`, `.pytest_cache`, `target/`, `*.pyc`, `bin/axiomc` (veya release artifact).
- `pyproject.toml`: paket adı, sürüm, Python >= 3.10, bağımlılıklar (`z3-solver`, `pytest`, `tomli` fallback).
- `requirements-dev.txt` veya `[project.optional-dependencies]`.
- `Makefile`: `make test`, `make build`, `make bootstrap`, `make fmt`, `make lint`.
- `.github/workflows/ci.yml` veya `.gitlab-ci.yml`: matris (Python 3.10/3.11/3.12), ASan, LLVM, self-hosted.
- `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`.
- Lisans başlıkları kaynak dosyalara.

### 9.2 CI düzeltmeleri

- `tools/ci_matrix.sh` adım 1’de `fmt` kaynağı **yerinde değiştiriyor**; `--check` kullan.
- Testleri paralelleştir (`pytest-xdist`), yavaş/hızlı katman ayır.
- Coverage ölç (`pytest-cov`), eşik koy.
- Shellcode/ağ testlerini ayrı job’a al.

### 9.3 Formatter

Mevcut formatter yalnızca boşluk siliyor. Eklenmesi gerekenler:
- Girinti normalizasyonu
- Operatör boşlukları
- Virgül/satır kuralları
- Import sıralama
- `fmt --check` örneklerde temiz geçmeli (`examples/` dahil)
- Idempotency testi: `fmt(fmt(x)) == fmt(x)`

### 9.4 LSP

- `--smt`/tam prover diagnostikleri (opsiyonel, yavaş olabilir).
- `textDocument/references`, `rename`, `codeAction`, `formatting`.
- Incremental sync.
- Proje genelinde tanım bulma (şu an tek dosya olabilir).
- Hover’da sözleşme ve tip bilgisi daha zengin.

### 9.5 REPL

- Geçmiş (`~/.axiom_history`).
- `readline`/`prompt_toolkit` ile satır düzenleme.
- Otomatik tamamlama.
- Çok satırlı bloklarda hata kurtarma.
- `:type`, `:ast`, `:c` gibi meta komutlar.

### 9.6 Debugger

- C backend `#line` zaten var; GDB kılavuzu ekle.
- LLVM DWARF (P1-B).
- `axiom debug` komutu (gdb sarmalayıcı).

---

## 10. P2 — Standart Kütüphane Derinleştirme

Mevcut 49 modülün 37’si 40 satırdan kısa. Öncelik sırası:

### 10.1 JSON

Şu an `axiom_json_find_key` düz metin arama. Gereken:
- Gerçek tokenizer/parser
- İç içe nesne/dizi
- `null`, ondalık, bilimsel gösterim
- Unicode `\uXXXX` ve surrogate pair
- Serileştirme (escape kuralları)
- Şema/doğrulama (opsiyonel)

### 10.2 HTTP

- `Content-Length` ve `chunked` desteği
- Yönlendirme
- Header ayrıştırma/serileştirme
- TLS entegrasyonu (`https_get` var ama sınırlı)
- Zaman aşımı, keep-alive
- Sunucu tarafı: gerçek istek döngüsü, yönlendirme bağlama, middleware zinciri

### 10.3 WASM

- Gerçek ikili encoder (section’lar, type/function/export)
- `wasm32-wasi` hedefi için ayrı runtime (POSIX’siz)
- Tarayıcı örneği ve test

### 10.4 AI

- Autograd: gerçek hesaplama grafiği, topolojik sıralama, gradyan birikimi
- ONNX/model dosyası okuyucu
- Softmax/cross-entropy tam implementasyon
- Benchmark (AVX2 vs scalar)

### 10.5 Koleksiyonlar ve metin

- `Map` gerçek hash tablosu (çarpışma, yeniden boyutlandırma)
- `Queue` thread-safe doğrulama
- Regex: POSIX yerine PCRE2 veya RE2 (geri izleme güvenliği)
- Unicode: tam grapheme cluster, normalizasyon (NFC/NFD)
- Tarih/saat: saat dilimi, formatlama

### 10.6 Hata yönetimi

- `Option<T>` / `Result<T,E>` gerçek generic
- `?` / `try` operatörü
- `match` ile `Some`/`None`/`Ok`/`Err` desenleri
- `std/core/option.ax` ve `result.ax` elle yazılmış kopyalardan kurtarılmalı

---

## 11. P2 — Dil Özellikleri (eklenmesi gerekenler)

| Özellik | Gerekçe | Öncelik |
|---|---|---|
| `enum` + `match` entegrasyonu | Durum makineleri, hata tipleri | Yüksek |
| Trait/interface + `impl` | Polimorfizm, kütüphane tasarımı | Yüksek |
| Closure/lambda | Callback, middleware | Orta |
| Namespace/modül sistemi | Büyük projelerde isim çakışması | Orta |
| `?` hata yayma | Ergonomi | Yüksek |
| Generic constraint (`T: Ord`) | Tip güvenliği | Orta |
| `defer` kapsam semantiği netleştirme | Kaynak yönetimi | Yüksek |
| `invariant` tam desteği (LLVM + self-hosted) | Sesli ispat | Orta |
| Etiketli döngü / `loop` | Kontrol akışı | Düşük |
| `const`/`comptime` | Derleme zamanı hesaplama | Düşük |
| Modül görünürlüğü (`pub`/`private`) | Kapsülleme | Orta |
| FFI (`extern "C"`) | C kütüphaneleri | Orta |

---

## 12. P2 — Performans ve Ölçüm

- Benchmark paketi: fibonacci, string işleme, JSON parse, HTTP, GEMM, dosya I/O.
- C/Rust/Python karşılaştırması; metodoloji ve donanım belirtilmeli.
- Derleme süresi ölçümü (runtime.h tek header sorunu).
- `runtime.h` modülerleştirme (ayrı header’lar: `string.h`, `net.h`, `crypto.h`, `ai.h`).
- `-O3` ile güvenlik kontrollerinin korunduğunu doğrulayan testler.
- SIMD GEMM için gerçek benchmark (AVX2 vs fallback).

---

## 13. Sprint Planı (öneri)

### Sprint 1 — Bellek ve aritmetik (1–2 hafta)

- [ ] String sahiplik modeli (P0-A.1)
- [ ] Otomatik kapsam temizliği (P0-A.2)
- [ ] Dizi semantiği kararı + uygulama (P0-A.3)
- [ ] Double-free koruması (P0-A.4)
- [ ] `array_push` realloc (P0-A.5)
- [ ] Taşma makroları (P0-B)
- [ ] ASan/LSan test matrisi

### Sprint 2 — Doğrulama (1 hafta)

- [ ] `eval_condition` çağrı denetimi (P0-C.1)
- [ ] `check --smt` / `--all` (P0-C.3)
- [ ] Seslilik test matrisi (P0-C.4)
- [ ] “Kesin İspat” ifadesinin koşullu kullanımı

### Sprint 3 — Self-hosted (2 hafta)

- [ ] `checker.ax` veya doğrulama geçişi (P1-A.1)
- [ ] `-Wno-*` susturmalarının kaldırılması
- [ ] Generic dönüş tipleri (P1-A.2)
- [ ] Taşınabilir yol (`/proc/self/exe`) (P1-A.3)
- [ ] `is_safe_path` düzeltmesi (P1-A.4)

### Sprint 4 — LLVM (2 hafta)

- [ ] 6 örneğin düzeltilmesi (P1-B.1)
- [ ] 19 örnek × 2 backend CI matrisi
- [ ] DWARF (P1-B.3)
- [ ] `ensures` tüm dönüş yolları (P1-B.4)

### Sprint 5 — Paket yöneticisi ve ofansif (1–2 hafta)

- [ ] Registry veya git-only kararı (P1-C.1)
- [ ] `--rev` / `--branch` / `--tag` (P1-C.2)
- [ ] Gerçek kurulum doğruluğu (P1-C.3)
- [ ] Ofansif opt-in izolasyon (P1-D)

### Sprint 6 — Doküman ve süreç (1 hafta)

- [ ] Bellek iddialarının düzeltilmesi (P1-E)
- [ ] SPECIFICATION v0.5
- [ ] Git + pyproject + CI + Makefile
- [ ] `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`
- [ ] Çıkış kodu kataloğu

### Sprint 7+ — Derinlik (3–6 ay)

- [ ] JSON/HTTP/WASM/AI derinleştirme (P2)
- [ ] Dil özellikleri (enum, trait, closure, `?`)
- [ ] Benchmark ve performans
- [ ] Formatter/LSP/REPL/debugger iyileştirmeleri

---

## 14. Genel Kabul Kriterleri

Aşağıdakilerin **tamamı** sağlanmadan proje “beta” ilan edilmemeli:

1. `axiom run --asan` tüm örneklerde sıfır sızıntı.
2. `INT64` taşma/bölme testleri güvenli duruyor.
3. `axiom check` hiçbir sözleşme ihlalini kaçırmıyor (koşullar dahil).
4. `bin/axiomc`, Python derleyicisinin reddettiği tip hatalarını da reddediyor.
5. 19 örneğin tamamı hem C hem LLVM backend’inde derlenip çalışıyor.
6. `axpm install` gerçekten bağımlılık kuruyor veya açıkça hata veriyor.
7. Ofansif modüller varsayılan derlemede yok.
8. README/SPEC’teki her iddia bir test veya benchmark ile destekleniyor.
9. CI’da git repo, pyproject, coverage ve matris var.
10. `axiom check` / `prove` çıktısı “Kesin İspat” diyorsa, iki motor da onaylıyor.

---

## 15. Kısa Vadeli “Hızlı Kazanımlar” (1–3 gün)

Bunlar düşük eforla güvenilirliği artırır:

1. `axiom_str_free` sonrası `NULL` (double-free).
2. `eval_condition` içine `FunctionCall` denetimi (3 satır).
3. `str_free` testini double-free ile genişlet.
4. README satır 19 ve SPEC bellek iddialarını düzelt.
5. `is_safe_path`’e boşluk/Unicode izni ver.
6. `axiom_compile_c`’den `-Wno-int-conversion` susturmalarını kaldır (hataları görünür yap).
7. CI’da `fmt` yerine `fmt --check`.
8. README rozetini “ARM64 deneysel” yap.

Bu sekiz madde, tek başına projenin dürüstlüğünü ve güvenilirliğini belirgin biçimde artırır.
