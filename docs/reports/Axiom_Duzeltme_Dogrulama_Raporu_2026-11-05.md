# Axiom (λx) — Düzeltme Doğrulama Raporu

**Tarih:** 5 Kasım 2026
**İncelenen sürüm:** `v0.5.0-alpha`
**Önceki rapor:** `~/Desktop/Axiom_Kapsamli_Inceleme_Raporu_2026-11-05.md`
**İlgili iyileştirme dosyası:** `~/Desktop/axiom/REMEDIATION_TODO_2026-11-05.md`
**Yöntem:** Her madde için kaynak kodu okuması + gerçek derleme/çalıştırma + ASan + test paketi

---

## 0. Özet

`REMEDIATION_TODO_2026-11-05.md` içindeki maddelerin bir kısmı gerçekten kapatılmış. Özellikle **komut enjeksiyonu**, **sıfıra bölme**, **`print` içi sözleşme denetimi** ve **`str_free` literal koruması** anlamlı biçimde düzeltilmiş. Test paketi bu makinede **520 test ile %100 geçti** (269,72 sn).

Ancak maddelerin çoğu **kısmen** kapatılmış; bazı iddialar hâlâ kodla uyuşmuyor. En kritik üç açık:

1. **Bellek modeli hâlâ güvenli değil.** String birleştirme sızıntısı (6,5 MB / 1.000 işlem), dizi aliasing’i ve double-free devam ediyor. README hâlâ “otomatik temizlik + değer anlambilimi” diyor.
2. **Varsayılan `axiom check` hâlâ sesli değil.** `if` / `while` / `verify` koşulu içindeki fonksiyon çağrıları sembolik ispatlayıcıdan kaçıyor; `check` yeşil verirken `--smt` kırmızı veriyor.
3. **Aritmetik taşma koruması yok.** Sıfıra bölme düzeltildi ama `INT64_MAX + 1` hâlâ sessizce sarıyor.

Ayrıca düzeltmelerden biri **yeni bir kullanılabilirlik regresyonu** üretti: `bin/axiomc` artık boşluk ve Türkçe karakter içeren dosya yollarını reddediyor.

### Durum Tablosu

| Madde | Durum | Kısa gerekçe |
|---|---|---|
| P0.1 Komut enjeksiyonu | ✅ **Düzeltildi** | `execvp` tabanlı `compile_c` + yol beyaz listesi |
| P0.2 Sıfıra bölme | 🟡 **Kısmi** | `/` ve `%` korunuyor; **taşma açık** |
| P0.3 Prover sesliliği | 🟡 **Kısmi** | `print` düzeldi; **koşul/verify çağrıları kaçıyor** |
| P0.4 Bellek güvenliği | 🟡 **Kısmi** | Literal `free` düzeldi; **sızıntı, aliasing, double-free açık** |
| P1.1 Self-hosted tip+generics | 🟡 **Kısmi** | Generic struct çalışıyor; **tip denetleyici yok**, generic dönüş tipi kırık |
| P1.2 LLVM backend | 🟡 **Kısmi** | Örnek 17 düzeldi; **19 örnekten 6’sı hâlâ derlenmiyor** |
| P1.3 Paket yöneticisi | 🟡 **Kısmi** | Git clone + içerik checksum var; **registry hâlâ sahte** |
| P1.4 Çapraz derleme/WASM | 🟡 **Dürüstleştirildi** | Gerçek derleme yok; artık açık hata + rehber var |
| P1.5 Ofansif izolasyon | 🟡 **Kısmi** | Uyarılar eklendi; **izolasyon/feature flag yok** |
| P2.1 Sürüm/test senkronu | ✅ **Büyük ölçüde** | Sürüm ve rozet güncel; **bellek iddiaları hâlâ yanlış** |
| P2.2 Negatif testler | 🟡 **Kısmi** | Yeni testler var; **kritik boşluklar test edilmiyor** |

**Genel:** 4 P0 maddesinden yalnızca 1’i tam kapalı. Geri kalan 3’ü kısmi. Proje hâlâ **alfa/araştırma prototipi** seviyesinde.

---

## 1. Test Paketi

```bash
$ cd ~/Desktop/axiom
$ python3 -m pytest -q --no-header
520 passed in 269.72s (0:04:29)
```

Önceki raporda 509 test vardı; 11 yeni test eklenmiş. README rozeti `520+ Passed` olarak güncellenmiş; bu kez tutarlı.

**Ancak:** Yeşil test paketi, aşağıdaki bulguların hiçbirini kapsamıyor. Test sayısı arttı diye güvenlik açıkları kapandı sayılmamalı.

---

## 2. P0 Maddelerinin Ayrıntılı Doğrulaması

### P0.1 — `bin/axiomc` komut enjeksiyonu → ✅ DÜZELTİLDİ

**Yapılan doğru işler:**

- `compiler/main.ax` artık `system()` tabanlı string komut kurmuyor; `compile_c(tmp_c, output_bin)` çağırıyor.
- `axiom/runtime.h:975` içindeki `axiom_compile_c`, `fork` + `execvp` ile clang’i argüman dizisiyle çalıştırıyor.
- `compiler/main.ax:101` içinde `is_safe_path` beyaz listesi var; `-o` ve girdi yolu denetleniyor.
- Python CLI tarafı (`axiom build`) zaten argüman dizisi kullanıyordu; o da güvenli.

**Kanıt:**

```bash
$ ./bin/axiomc build examples/01_hello.ax \
    -o '/tmp/opencode/pwned2; touch /tmp/opencode/INJ2'
[HATA] Guvensiz cikti dosya yolu tespit edildi: ...; touch ...
exit 1

$ ls /tmp/opencode/INJ2
No such file or directory
```

```bash
$ axiom build examples/01_hello.ax -o '/tmp/opencode/x; touch /tmp/opencode/INJ3'
clang: error: linker command failed ...
$ ls /tmp/opencode/INJ3
No such file or directory
```

**Sonuç:** Komut enjeksiyonu kapandı. Bu, raporun en net kazanımı.

**Yeni yan etki (P2):** `is_safe_path` yalnızca ASCII harf, rakam ve `._-/` kabul ediyor. Bu yüzden:

```bash
$ ./bin/axiomc build '/tmp/opencode/boş luk/merhaba.ax' -o /tmp/opencode/merhaba
[HATA] Guvensiz kaynak dosya yolu tespit edildi: /tmp/opencode/boş luk/merhaba.ax
exit 1
```

Türkçe karakterli veya boşluklu dizinlerde çalışmıyor. Ayrıca `..` serbest; beyaz liste yerine “exec’e argüman olarak gitmesi yeterli” yaklaşımı daha doğru olurdu.

---

### P0.2 — Aritmetik güvenlik → 🟡 KISMİ

**Düzelen:**

- `/` ve `%` için `axiom_safe_div` / `axiom_safe_mod` makroları eklendi (`runtime.h:227`, `:236`).
- Sabit sıfıra bölme artık sembolik ispatlayıcı tarafından yakalanıyor.
- Değişken sıfıra bölme çalışma anında `exit 101` ile güvenli duruyor.

**Kanıt:**

```bash
$ axiom run dz_runtime.ax          # sabit 10 / 0
Axiom Statik Matematiksel İspat Hatası: Kesin sıfıra bölme ...
exit 1

$ axiom run dz_runtime2.ax         # str_to_int("0") ile bölme
[AXIOM GUVENLIK IHLALI] ... Sifira bolme hatasi!
exit 101
```

**Düzelmeyen — taşma:**

```bash
$ axiom run overflow.ax
-9223372036854775808
exit 0
```

`INT64_MAX + 1` hâlâ sessizce sarıyor. `REMEDIATION_TODO` P0.2 metninde “taşmalar sessizce sarıyor” problem olarak yazılmış, ancak çözüm yalnızca bölme/mod kapsıyor. `axiom_safe_add`, `axiom_safe_sub`, `axiom_safe_mul` veya `__builtin_add_overflow` ailesi yok.

**Sonuç:** Yarısı kapalı. Taşma, güvenlik aracı yazan biri için hâlâ sessiz veri bozulması riski.

---

### P0.3 — Doğrulama sesliliği → 🟡 KISMİ

**Düzelen:**

- `PrintStmt` artık sembolik yürütmede argümanlarını değerlendiriyor.
- `axiom check` varsayılan olarak `SymbolicProver` çalıştırıyor; `--no-prove` ile atlanabiliyor.
- `print(check_port(99999))` artık hem sembolik hem Z3 tarafından yakalanıyor.
- `safe_divide(10, 0)` Z3 tarafından da reddediliyor.

**Kanıt:**

```bash
$ axiom prove badprint.ax
... 'check_port' fonksiyonunun 'requires' sözleşmesi kesin olarak ihlal edildi!
exit 1

$ axiom prove badprint.ax --smt
... ihlal ediyor!
exit 1

$ axiom check contract_bad.ax
... 'port_scan' requires ihlali ...
exit 1

$ axiom check --no-prove contract_bad.ax
✓ Doğrulama Başarılı
exit 0
```

**Düzelmeyen — koşul ve `verify` içindeki çağrılar:**

```axiom
fn check_port(port: int) -> bool
    requires port > 0 and port <= 65535
{ return true }

fn main() -> int {
    if check_port(99999) { print("ok") }
    return 0
}
```

```bash
$ axiom prove cond_call.ax
✓ ... 0 Hata - Kesin İspat
exit 0
```

```bash
$ axiom prove cond_call.ax --smt
... requires ihlali! exit 1
```

Aynı durum `verify check_port(99999)` için de geçerli. Sebep: `prover.py:418` içindeki `eval_condition`, `BinaryOp` dallarında `eval_expr_interval` çağırıyor; ancak koşul doğrudan bir `FunctionCall` ise hiç `check_function_call` yapmıyor. `IfStmt`, `WhileStmt` ve `VerifyStmt` bu yolu kullanıyor.

**Kritik sonuç:** `axiom check` hâlâ yanlış yeşil verebiliyor:

```bash
$ axiom check cond_call.ax
✓ Doğrulama Başarılı
exit 0
```

`axiom check` için `--smt` seçeneği de yok; yalnızca sembolik motor var. Yani kullanıcı `check`’e güvenirse Z3’ün yakaladığı ihlali kaçırır.

**Sonuç:** `print` özel durumu kapatılmış ama seslilik genel olarak tamamlanmamış.

---

### P0.4 — Bellek modeli → 🟡 KISMİ

**Düzelen:**

- `axiom_str_free` artık `dladdr` ile literal/rodata adreslerini tespit edip no-op yapıyor.
- `str_free("literal")` çökmüyor.

**Kanıt:**

```bash
$ axiom run free_literal.ax
after
exit 0
```

**Düzelmeyen 1 — string birleştirme sızıntısı:**

```bash
$ axiom run --asan leak.ax
ERROR: LeakSanitizer: detected memory leaks
Direct leak of 6507500 byte(s) in 1000 object(s)
SUMMARY: AddressSanitizer: 6507500 byte(s) leaked in 1000 allocation(s).
exit 1
```

`axiom_str_concat` her çağrıda `malloc` yapıyor; eski string serbest bırakılmıyor; kapsam çıkışında otomatik `free` yok. REMEDIATION P0.4 yalnızca literal `free` senaryosunu ele almış; asıl sızıntı duruyor.

**Düzelmeyen 2 — dizi aliasing / “değer anlambilimi” ihlali:**

```axiom
let a = [1, 2, 3]
let mut b = a
b[0] = 99
print("a0:", a[0])   # 99
print("b0:", b[0])   # 99
```

`a` değiştirilemez olmasına rağmen `b` üzerinden değişiyor. README satır 19 ve SPECIFICATION satır 9 hâlâ “değer anlambilimi” ve “otomatik derleme zamanı referans temizliği” diyor. Bu iddia kodla çelişiyor.

**Düzelmeyen 3 — double-free:**

```bash
$ axiom run --asan double_free.ax
ERROR: AddressSanitizer: attempting double-free ...
exit 1
```

`str_free` serbest bıraktıktan sonra işaretçiyi null’lamıyor; ikinci çağrı çöküyor. GLOBAL_LANGUAGE_ROADMAP’teki “sıfır UAF / çift serbest bırakma garantisi” iddiası geçersiz.

**Sonuç:** P0.4’ün en dar senaryosu düzeltilmiş; bellek modelinin kendisi hâlâ güvenli değil. Bu, raporun en büyük açık maddesi.

---

## 3. P1 Maddelerinin Doğrulaması

### P1.1 — Self-hosted tip denetimi & generics → 🟡 KISMİ

**Düzelen:**

- `struct Box<T>` monomorflaştırması çalışıyor:

```bash
$ ./bin/axiomc build gen_struct_only.ax
val: 42
exit 0
```

- Basit generic fonksiyon (aynı tip döndüren) çalışıyor:

```bash
$ ./bin/axiomc build gen_func_only.ax
a: 42
exit 0
```

- `get_axiom_root()` / `get_runtime_path()` eklendi; kaynakta sabit `~/Desktop/...` yolu kalmadı (fallback hâlâ var).

**Düzelmeyen 1 — generic fonksiyonun generic struct döndürmesi:**

```axiom
struct Box<T> { val: T }
fn wrap<T>(x: T) -> Box<T> { return Box<T> { val: x }; }
fn main() -> int {
    let b: Box<int> = wrap<int>(42);
    print(b.val);
    return 0;
}
```

```bash
$ ./bin/axiomc build generic.ax
error: initializing 'ax_Box_int' ... with an expression of incompatible type 'ax_Box_T'
exit 1
```

Bu, generics desteğinin tam olmadığını gösteriyor. Test yalnızca `Box<int> { ... }` literalini kapsıyor; generic fonksiyon dönüş tipini kapsamıyor.

**Düzelmeyen 2 — tip denetleyici yok:**

`REMEDIATION_TODO` başlığı “Tip Denetimi & Generics” diyor; ancak `compiler/` içinde tip denetleyici yok. `axiomc` hâlâ şunları derliyor:

```bash
$ ./bin/axiomc build typeerr.ax        # let x: int = "hello"
[axiomc] Basariyla derlendi ...
```

Bunun yerine `axiom_compile_c` (`runtime.h:975`) `-Wno-int-conversion`, `-Wno-int-to-pointer-cast`, `-Wno-pointer-to-int-cast` ile uyarıları susturuyor. Yani tip hataları gizleniyor.

```bash
$ ./bin/axiomc build missing_ret2.ax   # eksik return
1 warning generated.
[axiomc] Basariyla derlendi ...

$ ./bin/axiomc build typeconf2.ax      # 1 < "abc"
2 warnings generated.
[axiomc] Basariyla derlendi ...
```

Bu üçü Python derleyicisinde `SemanticError` ile reddediliyor; self-hosted tarafta kabul ediliyor. “%100 parity” iddiası hâlâ yanlış.

**Düzelmeyen 3 — emit-c mutlak yol:**

```bash
$ cd /tmp/opencode
$ ~/Desktop/axiom/bin/axiomc emit-c ~/Desktop/axiom/examples/01_hello.ax | head -2
#include "~/Desktop/axiom/axiom/runtime.h"
```

`get_axiom_root()` çağrıldığı dizine göre çalışıyor; `PWD` proje kökü değilse son çare sabit masaüstü yoluna düşüyor. Taşınabilirlik tam değil.

**Yeni regresyon:** Boşluk/Türkçe karakterli yollar `is_safe_path` tarafından reddediliyor (P0.1 bölümünde kanıtlandı).

---

### P1.2 — LLVM arka ucu → 🟡 KISMİ

**Düzelen:**

- `examples/17_ai_tensor_neural_net.ax` artık LLVM ile derlenip çalışıyor:

```bash
$ axiom build examples/17_ai_tensor_neural_net.ax --backend=llvm -o nn
✓ Başarılı (LLVM IR Backend)
$ ./nn
TEBRIKLER! FAZ 4: AI & ML TENSOR ENGINE BASARIYLA CALISTI!
```

- `ensures` için LLVM tarafında denetim eklendi; `test_llvm.py` 16/16 geçiyor.
- float/int karışık aritmetik için `sitofp` eklendi.

**Düzelmeyen — tüm örnekler LLVM ile derlenmiyor:**

| Örnek | LLVM hatası |
|---|---|
| `08_multithreaded_scanner.ax` | `alloca void` geçersiz |
| `11_packet2_advanced_network.ax` | `verify_ok.13:` etiketi void tip hatası |
| `12_packet3_system_exploit.ax` | `store %struct.ax_array` eksik tip |
| `15_redteam_offensive_suite.ax` | `ret void` tip hatası |
| `16_blueteam_defensive_suite.ax` | `load i8*` / pointer tipi |
| `18_web_api_framework.ax` | `store %struct.ax_array , ...` sözdizimi |

Yani 19 örnekten **6’sı** hâlâ LLVM ile derlenmiyor. `test_llvm.py` bu örnekleri kapsamıyor; yalnızca küçük sentetik programları test ediyor.

**Ayrıca:** LLVM IR’de DWARF/debug metadata yok; `--target` + LLVM kombinasyonu da test edilmemiş.

---

### P1.3 — Paket yöneticisi → 🟡 KISMİ

**Düzelen:**

- Git bağımlılıkları artık gerçekten klonlanıyor (`git clone --depth 1 -b <rev>`).
- Lock checksum’u `compute_dir_checksum` ile **dosya içeriğinden** hesaplanıyor (`.git` atlanarak).
- `LockFile.verify` ve resolver entegrasyonu eklenmiş.

**Kanıt:**

```bash
$ axpm add foo --git https://github.com/octocat/Hello-World.git
$ axpm install
Hata: Git bağımlılığı klonlanamadı ... Remote branch main not found
```

Klonlama denemesi gerçekten yapılıyor (branch adı yüzünden başarısız; bu beklenen).

**Düzelmeyen 1 — registry hâlâ sahte:**

```bash
$ axpm add bar --version 1.2.3
$ axpm install
✓ Bağımlılıklar kilitlendi: 1 paket
$ find .axiom -maxdepth 3
.axiom/deps      # boş, hiçbir dosya indirilmedi
```

Lock dosyasındaki checksum hâlâ `sha256("registry:bar:1.2.3")`; yani indirilen içeriğin değil, metadata string’inin özeti. Merkezi registry yok. README bunu “deneysel” diye işaretlemiş (dürüst), ama `install` başarı mesajı verip hiçbir şey kurmuyor; bu yanıltıcı.

**Düzelmeyen 2 — `--rev` yok:**

```bash
$ axpm add --help
--path, --git, --version     # --rev yok
```

Manifest’e her zaman `"rev": "main"` yazılıyor. `master` kullanan depolar (ör. Hello-World) varsayılan olarak başarısız oluyor.

---

### P1.4 — Çapraz derleme / WASM → 🟡 DÜRÜSTLEŞTİRİLDİ

**Yapılan:**

- `validate_target_toolchain` eklendi; sysroot/toolchain yoksa anlaşılır hata veriyor.
- `--sysroot` bayrağı eklendi.
- README’de “harici toolchain gerekir, deneysel” notu var.

**Kanıt:**

```bash
$ axiom build examples/01_hello.ax --target aarch64-linux-gnu -o h
... 'bits/libc-header-start.h' file not found
Lütfen aarch64 cross-toolchain paketini kurun ... veya --sysroot belirtin.
exit 1
```

**Gerçek durum:** Çapraz derleme hâlâ çalışmıyor; yalnızca hata mesajı iyileştirildi. “Deneysel” etiketiyle bu kabul edilebilir. Ancak README rozeti hâlâ `Target Native x86_64 | ARM64` diyor; ARM64 hedefi fiilen yok.

**WASM:** `std/target/wasm.ax` hâlâ gerçek ikili üretmiyor; yalnızca sihirli sayı ve export metadata’sı tutuyor. WASM hedefi hem derleyici hem kütüphane tarafında stub.

---

### P1.5 — Ofansif modül izolasyonu → 🟡 KISMİ

**Yapılan:**

- 5 modüle (`shellcode`, `c2`, `evasion`, `memdump`, `packet_crafter`) yasal/etik uyarı başlığı eklendi.
- Test dosyasına `AXIOM_SKIP_REDTEAM_TESTS=1` ile atlama mekanizması eklendi.

**Düzelmeyen:**

- Modüller hâlâ varsayılan `std/` ağacında, feature flag/paket ayrımı olmadan geliyor.
- Shellcode testi varsayılan olarak çalışıyor; yalnızca kullanıcı ortam değişkeni set ederse atlanıyor. CI’da varsayılan davranış hâlâ gerçek shellcode çalıştırmak.
- “İzolasyon” maddesi başlıkta var, uygulamada yok.

**Öneri:** `--features offensive` veya ayrı `axiom-offensive` paketi; testleri varsayılan `pytest` seçiminden çıkarmak; `AXIOM_ENABLE_REDTEAM=1` gibi **opt-in** model.

---

## 4. P2 Maddelerinin Doğrulaması

### P2.1 — Sürüm ve doküman senkronu → ✅ BÜYÜK ÖLÇÜDE

| Yer | Değer | Durum |
|---|---|---|
| `axiom/__init__.py` | `v0.5.0-alpha` | ✅ |
| `README.md` | `v0.5.0-alpha` | ✅ |
| `cli.py` REPL / `--version` | `v0.5.0-alpha` | ✅ |
| `lsp.py` | `v0.5.0-alpha` | ✅ |
| `compiler/main.ax` | `v0.5.0-alpha` | ✅ |
| README test rozeti | `520+ Passed` | ✅ (gerçek 520) |
| “Statik binary” | “OpenSSL/glibc dinamik bağlı” | ✅ |
| Proje statüsü | “v0.5.0-alpha, araştırma prototipi” | ✅ |
| Bilinen sınırlamalar | 4 madde eklendi | ✅ |

**Kalan yanlış iddialar:**

- `README.md:19` — “Otomatik derleme zamanı referans temizliği ve değer anlambilimi”. Kod bunu yapmıyor (sızıntı + aliasing).
- `SPECIFICATION.md:9-10,135` — “değer anlambilimi”, “RAII ile anında temizlenir”. Aynı şekilde yanlış.
- `GLOBAL_LANGUAGE_ROADMAP.md:7,14` — “Zero-Leak RAII”, “sıfır kaçak / sıfır UAF garantisi”. ASan testi aksini gösteriyor.
- `SPECIFICATION.md` hâlâ **v0.1**; generics, `defer`, `invariant`, `match`, `Option/Result`, LSP, paket yöneticisi yok. Ayrıca iki kez “## 3.” başlığı var (satır 111 ve 119).

### P2.2 — Negatif testler → 🟡 KISMİ

**Eklenen testler:**

- `test_negative_security_p0_1_axiomc_command_injection_prevention`
- `test_negative_security_p0_2_arithmetic_zero_division_protection`
- `test_negative_security_p0_3_print_stmt_prover_soundness`
- `test_negative_security_p0_4_str_free_literal_protection_under_asan`
- `test_self_hosted_generics_box`
- `test_llvm_ensures_contract_success` / `_violation`
- `test_git_dependency_clone_and_lock_verification`
- `test_git_dependency_build_and_run_end_to_end`

**Kapsanmayan kritik senaryolar:**

| Senaryo | Neden önemli | Test var mı |
|---|---|---|
| `INT64_MAX + 1` / `INT64_MIN * -1` | Sessiz taşma | ❌ |
| 1.000 string birleştirme + ASan | Sızıntı | ❌ |
| `let b = a; b[0]=...` | Aliasing / değer semantiği | ❌ |
| `str_free(s); str_free(s)` | Double-free | ❌ |
| `if` / `while` / `verify` içinde sözleşme ihlali | Prover sesliliği | ❌ |
| 19 örneğin tamamı `--backend=llvm` | LLVM eşitliği | ❌ |
| `axiomc` ile tip hatası / eksik return | Self-hosted parity | ❌ |
| Registry bağımlılığı gerçekten kuruldu mu | Axpm doğruluğu | ❌ |
| Boşluk/Türkçe karakterli yol | Yeni regresyon | ❌ |

Yani testler yalnızca “mutlu yol + dar özel durum” düzeyinde. Regresyon koruması zayıf.

---

## 5. Yeni / Kalan Bulgular (önceki raporda olmayan veya güncellenen)

| # | Bulgu | Önem |
|---|---|---|
| N1 | `is_safe_path` boşluk ve non-ASCII yolları reddediyor | P2 — kullanılabilirlik |
| N2 | `axiom_compile_c` `-Wno-int-conversion` vb. ile tip hatalarını gizliyor | P1 — self-hosted güvenliği |
| N3 | `axiomc emit-c` hâlâ mutlak `#include` yolu üretiyor | P2 — taşınabilirlik |
| N4 | `str_free` double-free’e karşı korumasız | P1 — bellek |
| N5 | `axiom check` için `--smt` seçeneği yok; sembolik motor tek başına eksik | P1 — doğrulama |
| N6 | Registry `install` başarı mesajı verip hiçbir şey kurmuyor | P1 — yanıltıcı davranış |
| N7 | `axpm` `--rev` desteklemiyor; varsayılan `main` birçok depoyu kırıyor | P2 — paket yöneticisi |
| N8 | README/SPEC/roadmap’te bellek iddiaları hâlâ yanlış | P1 — doküman güveni |
| N9 | 19 örnekten 6’sı LLVM ile derlenmiyor | P1 — backend eşitliği |
| N10 | Ofansif modüller hâlâ varsayılan geliyor; test opt-out değil opt-in olmalı | P1 — güvenlik/uyum |

---

## 6. Sonuç

**Gerçekten kapananlar:**

- P0.1 komut enjeksiyonu
- P0.2’nin sıfıra bölme kısmı
- P0.3’ün `PrintStmt` kısmı ve `check` entegrasyonu
- P0.4’ün literal `str_free` kısmı
- P1.2’nin örnek 17 / `ensures` kısmı
- P1.3’ün git clone + içerik checksum kısmı
- P2.1’in sürüm/test rozeti kısmı

**Kapanmayanlar (özet):**

- Taşma koruması
- String sızıntısı, dizi aliasing, double-free
- Koşul/`verify` içi sözleşme ihlalleri ve `check --smt`
- Self-hosted tip denetleyicisi ve tam generics
- LLVM’de 6 örnek
- Registry ve `--rev`
- Ofansif izolasyon
- Bellek iddialarının dokümanlardan temizlenmesi

**Hüküm:** İyileştirme gerçek ve yönü doğru; ancak “tüm maddeler düzeltildi” ifadesi doğru değil. P0’ların 3’ü kısmi, P1’lerin 5’i kısmi. Proje hâlâ alfa.

Kalan işlerin önceliklendirilmiş listesi ayrı dosyada:
`~/Desktop/Axiom_Kalan_Isler_ve_Gelistirme_Yol_Haritasi_2026-11-05.md`
