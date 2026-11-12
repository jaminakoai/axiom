# Axiom (λx) — Kapsamlı Teknik İnceleme ve İyileştirme Raporu

**İnceleme tarihi:** 5 Kasım 2026
**İnceleme kapsamı:** `~/Desktop/axiom` (kaynak kod, derleyici, runtime, standart kütüphane, testler, dokümantasyon, CLI araçları)
**Yöntem:** Statik kod incelemesi + gerçek derleme/çalıştırma denemeleri + test paketinin çalıştırılması + güvenlik ve bellek davranışı probları
**Raporun niteliği:** Bu rapor, masaüstündeki mevcut `Axiom_Inceleme_Raporu.md` dosyasından bağımsız, çalıştırmalı kanıtlara dayanan yeni bir değerlendirmedir.

---

## 0. Yönetici Özeti

Axiom, tek kişilik/küçük ekip ölçeğine göre **oldukça iddialı ve ciddi emek içeren bir dil/derleyici projesi**. Lexer, parser, tip denetleyici, C99 kod üreteci, LLVM IR arka ucu, runtime, LSP, paket yöneticisi, formatter ve 49 modüllük bir standart kütüphane iskeleti gerçekten mevcut. Test paketi bu makinede **509 test ile %100 geçti** (yaklaşık 4,5 dakika). Temel örnekler hem Python tabanlı `axiom` hem de kendi kendine derlenen `bin/axiomc` ile çalışıyor.

Ancak proje, **"üretime hazır sistem dili"** iddiasını henüz karşılamıyor. İncelemede dört kritik sorun doğrulandı:

1. **`bin/axiomc` içinde komut enjeksiyonu** — çıktı dosyası adı üzerinden rastgele komut çalıştırılabiliyor.
2. **Bellek modeli güvenli değil** — otomatik temizlik yok; 1.000 string birleştirmede 6,5 MB sızıntı oluşuyor; diziler "değer anlambilimi" yerine referans paylaşıyor; `str_free("literal")` çöküyor.
3. **Doğrulama motoru sesli (sound) değil** — `axiom check` sözleşmeleri hiç doğrulamıyor; `print(...)` içindeki sözleşme ihlalleri hem sembolik hem Z3 motorundan kaçıyor; `10 / 0` "Kesin İspat" raporuyla geçebiliyor.
4. **Aritmetik güvenlik yok** — sıfıra bölme sabit ifadede çöp değer üretip `exit 0` ile bitebiliyor, değişken ifadede SIGFPE ile çöküyor; taşma sessizce sarıyor.

Buna ek olarak self-hosted derleyici **%100 eşitlik iddiasını karşılamıyor** (generics derleyemiyor, tip denetleyicisi yok), LLVM arka ucu eksik, paket yöneticisi gerçek bağımlılık indirmiyor, çapraz derleme/WASM çalışmıyor ve ofansif güvenlik modülleri hiçbir uyarı/izolasyon olmadan varsayılan kurulumda geliyor.

### Olgunluk Karnesi

| Alan | Puan (10 üzerinden) | Kısa değerlendirme |
|---|---:|---|
| Vizyon ve mimari | 7 | Tutarlı, hırslı, iyi bölümlenmiş |
| Lexer / Parser / Checker | 7 | Gerçek ve çalışıyor; bazı semantik boşluklar var |
| C99 arka ucu | 7 | Temel programlarda sağlam; bellek modeli zayıf |
| LLVM arka ucu | 4 | Basit örneklerde çalışıyor; `ensures` yok, float hatası var |
| Self-hosted derleyici | 3 | Alt küme; tip denetimi ve generics yok, yollar sabit kodlu |
| Biçimsel doğrulama | 4 | Gösteri düzeyinde; sesliliği kanıtlanmamış |
| Bellek güvenliği | 2 | Sızıntı, aliasing ve hatalı `free` senaryoları doğrulandı |
| Standart kütüphane derinliği | 4 | 49 modül var ama çoğu ince C sarmalayıcısı |
| CLI / LSP / formatter | 6 | İş görüyor; üretim kalitesinde değil |
| Dokümantasyon tutarlılığı | 4 | Sürüm, test sayısı ve yetenek iddiaları çelişiyor |
| Test altyapısı | 7 | 509 gerçek E2E testi geçiyor; kapsam ve negatif test boşlukları var |
| **Üretim hazırlığı** | **2** | **Alfa/prototip seviyesi** |

**Genel hüküm:** Axiom güçlü bir araştırma prototipi ve etkileyici bir mühendislik gösterisi; ancak şu an **güvenlik açısından kritik sistemlerde, üretimde veya "C/Rust alternatifi" olarak konumlandırılmamalı**. Önce P0 maddeleri kapatılmalı, sonra iddialar yeniden kalibre edilmeli.

---

## 1. Projenin Amacı ve Konumlandırması

README ve yol haritalarına göre Axiom:

- **Python kadar kolay yazılan**, **C/Rust kadar hızlı çalışan**,
- **çöp toplayıcısız (zero-GC)**, deterministik gecikmeli,
- **`requires` / `ensures` / `verify` sözleşmeleriyle** mantık hatalarını derleme anında yakalayan,
- **tek komutla bağımsız yerel ikili** üreten,
- özellikle **red team / blue team / DFIR / AI / web** alanlarına odaklanan

bir sistem programlama dili olarak tanımlanıyor.

Mimari gerçekten bu vizyona uygun parçalara ayrılmış:

- **Bootstrap derleyici (Python):** `lexer.py`, `parser.py`, `checker.py`, `prover.py`, `z3_prover.py`, `codegen_c.py`, `codegen_llvm.py`
- **Self-hosted derleyici (Axiom):** `compiler/*.ax` → `bin/axiomc`
- **Runtime:** `axiom/runtime.h` (6.133 satır, 247 runtime fonksiyonu)
- **Standart kütüphane:** `std/` (49 `.ax` dosyası, 304 fonksiyon, 2.606 satır)
- **Araçlar:** `bin/axiom`, `bin/axpm`, `bin/axiom-lsp`, `axiom/formatter.py`, `axiom/package_manager.py`, `axiom/lsp.py`

Bu, "her şeyi tek dosyaya tıkıştırma" yerine gerçek bir derleyici hattı kurma çabasıdır; projenin en güçlü yanı budur.

---

## 2. Envanter ve Ölçümler

| Metrik | Değer |
|---|---:|
| Python çekirdek kodu | 8.557 satır |
| `axiom/runtime.h` | 6.133 satır / 247 `AXIOM_RUNTIME_FN` |
| LLVM runtime köprüsü | 5 satır |
| Self-hosted derleyici (`compiler/*.ax`) | 1.738 satır |
| Standart kütüphane | 49 dosya, 304 fonksiyon, 2.606 satır |
| Örnek program | 19 `.ax` dosyası |
| Test dosyası | 42 |
| Test fonksiyonu / toplanan vaka | 501 / **509** |
| Test süresi | ~4 dk 28 sn |
| Toplam proje boyutu | ~3,7 MB |
| Git deposu | **Yok** |
| `pyproject.toml` / `setup.py` / `requirements.txt` | **Yok** |
| `.github/` CI yapılandırması | **Yok** (yalnızca `tools/ci_matrix.sh`) |
| Sürüm numarası | **Tutarsız** (0.1.0 / 0.3.0 / 0.5.0 / 1.0.0) |

### Doğrulanan çalıştırmalar

```
$ python3 -m pytest -q
509 passed in 268.81s

$ axiom run examples/01_hello.ax
Merhaba, Guvenlik Uzmani! ...
55
[DOGRULAMA] Toplam hesabi basarili ve dogru!
exit 0

$ ./bin/axiomc run examples/01_hello.ax
(aynı çıktı)
exit 0

$ axiom run oob.ax
[AXIOM BELLEK IHLALI] Dizi sınır aşımı ...
exit 102
```

Dizi sınır denetimi, temel C üretimi, runtime sözleşme kontrolleri ve self-hosted alt küme gerçekten çalışıyor. Bu, raporun olumlu tarafıdır.

---

## 3. Doğrulanan Güçlü Yönler

1. **Gerçek bir derleyici hattı var.** Lexer → parser → resolver → checker → prover → codegen zinciri eksiksiz kurulmuş; oyuncak bir "interpreter" değil.
2. **C99 arka ucu temel programlarda sağlam.** `01_hello`, `02_fibonacci`, `03_contracts`, `05_real_scanner`, `09_simd_vector_scan` gibi örnekler derlenip çalışıyor.
3. **Runtime sözleşme kontrolleri çalışıyor.** `requires` ihlali çalışma anında `[AXIOM GUVENLIK IHLALI]` ile yakalanıyor ve program durduruluyor (ör. `safe_divide(10, 0)` → exit 101).
4. **Dizi sınır denetimi çalışıyor.** Negatif veya büyük indeks `exit 102` ile güvenli biçimde durduruluyor.
5. **Testler gerçek E2E testleri.** Birçoğu Axiom kaynağını C'ye derleyip binary'yi çalıştırıyor ve çıktıyı doğruluyor; yalnızca string karşılaştıran sahte testler değil.
6. **LSP, formatter, paket yöneticisi ve REPL iskeletleri mevcut.** Prototip için kayda değer.
7. **AVX2/FMA GEMM, epoll, YARA/Sigma, TLS/JWT gibi alanlarda ciddi runtime kodu var.** Özellikle `runtime.h` içindeki SIMD ve kriptografi bölümleri boş değil.
8. **Self-hosted binary gerçek bir ELF.** `bin/axiomc` 85 KB'lık, Python gerektirmeyen bir ikili ve temel örnekleri derleyebiliyor.

---

## 4. Kritik Bulgular (P0)

### P0-1 — `bin/axiomc` üzerinden komut enjeksiyonu (Keyfi komut çalıştırma)

**Kanıt:**

```bash
$ ./bin/axiomc build examples/01_hello.ax \
    -o '/tmp/opencode/pwned; touch /tmp/opencode/INJECTED'
[axiomc] Basariyla derlendi -> /tmp/opencode/pwned; touch /tmp/opencode/INJECTED

$ ls -l /tmp/opencode/INJECTED
-rw-rw-r-- 1 mimar mimar 0 ... /tmp/opencode/INJECTED
```

**Neden:** `compiler/main.ax:186` civarında C derleme komutu bir shell string'i olarak kuruluyor:

```axiom
let compile_cmd = "clang -O3 ... " + tmp_c + " ... -o " + output_bin
let status = os_exec(compile_cmd)
```

`os_exec` ise `axiom/runtime.h:898` içinde doğrudan `system(cmd)` çağırıyor. Kullanıcı tarafından verilen `-o` değeri tırnaklanmıyor/kaçırılmıyor.

**Etki:** Derleyiciyi çalıştıran kullanıcının yetkileriyle keyfi komut çalıştırma. CI/CD veya çok kullanıcılı ortamda kritik.

**Düzeltme:**
- `system()` yerine `execvp`/`posix_spawn` tabanlı argüman dizisi API'si kullanılmalı (`os_exec_argv` zaten var).
- `output_bin` ve tüm yollar doğrulanmalı; `-o` yalnızca güvenli karakter seti kabul etmeli.
- En azından shell kaçışı yapılmalı; ancak kalıcı çözüm shell'i tamamen kaldırmaktır.
- Regresyon testi: `-o 'x; touch /tmp/pwned'` çalıştırıldığında dosya oluşmamalı.

---

### P0-2 — Bellek modeli güvenli değil: sızıntı, aliasing ve hatalı `free`

Axiom "zero-GC + RAII + otomatik kaynak temizliği + zero-leak" iddia ediyor. Yapılan testler bunun tersini gösteriyor.

#### (a) String birleştirmede ciddi sızıntı

```axiom
fn main() -> int {
    let mut s = ""
    let mut i = 0
    while i < 1000 {
        s = s + "AxiomLeakTest"
        i = i + 1
    }
    print(len(s))
    return 0
}
```

```bash
$ axiom run --asan leak.ax
==...==ERROR: LeakSanitizer: detected memory leaks
Direct leak of 6507500 byte(s) in 1000 object(s)
SUMMARY: AddressSanitizer: 6507500 byte(s) leaked in 1000 allocation(s).
```

**Neden:** `axiom_str_concat` (`runtime.h:245`) her çağrıda `malloc` yapıyor; `codegen_c.py` otomatik `free` enjekte etmiyor. `str_free` yalnızca kullanıcı elle çağırırsa çalışıyor. `array_push` makrosu da (`runtime.h:219`) her eklemede yeni tampon ayırıp eski tamponu serbest bırakmıyor; döngüde dizi büyütmek de sızdırıyor.

#### (b) Diziler değer anlambilimi değil, referans paylaşımı

```axiom
fn main() -> int {
    let a = [1, 2, 3]
    let mut b = a
    b[0] = 99
    print("a0:", a[0])
    print("b0:", b[0])
    return 0
}
```

Çıktı:

```
a0: 99
b0: 99
```

`let a` değiştirilemez olmasına rağmen `b` üzerinden `a`'nın içeriği değişiyor. Nedeni, `ax_array_*` tiplerinin (`runtime.h:112-135`) yalnızca `length` + `data` pointer'ı tutması ve atamanın sığ (shallow) struct kopyası olması. SPECIFICATION.md'deki "değer anlambilimi" iddiası bununla çelişiyor.

#### (c) `str_free` ile literal serbest bırakma çöküyor

```axiom
fn main() -> int {
    let s = "literal"
    str_free(s)
    print("after")
    return 0
}
```

```
free(): invalid pointer
exit 250
```

Literal string ile heap string aynı `const char*` tipinde; sahiplik bilgisi yok. `str_free` (`runtime.h:147`) körlemesine `free` çağırıyor. Bu, kullanıcıya verilen "güvenli bellek yönetimi" API'sinin tehlikeli olduğunu gösteriyor.

**Etki:** Uzun ömürlü sunucularda/OOM riski, veri yarışı benzeri aliasing hataları, use-after-free ve çift serbest bırakma.

**Düzeltme önerisi:**
- String'i `{len, capacity, data, owned}` struct'ına dönüştürüp sahiplik bayrağı eklemek.
- Kapsam çıkışında otomatik `free` (RAII) veya arena/bölge tahsisi; `defer` altyapısı zaten var.
- Dizilerde copy-on-write veya açık `clone()`; `let` ile bağlanan dizinin içeriğinin başka isimle değiştirilememesi.
- `str_free` yerine sahiplik duyarlı `drop` mekanizması; literal için no-op.
- `array_push`'te `realloc` kullanımı ve eski tamponun doğru yönetimi.
- CI'da ASan/LSan zorunlu; sızıntı testleri başarısızsa build kırılmalı.

---

### P0-3 — Doğrulama motoru sesli değil; "Kesin İspat" yanıltıcı

#### (a) `axiom check` sözleşmeleri doğrulamıyor

```bash
$ axiom check contract_bad.ax
✓ Doğrulama Başarılı: ... sözdizimsel, tip ve sözleşme denetimlerinden geçti.
exit 0
```

Aynı dosya `axiom prove` ile reddediliyor:

```bash
$ axiom prove contract_bad.ax
... 'port_scan' fonksiyonunun 'requires' sözleşmesi kesin olarak ihlal edildi!
exit 1
```

**Neden:** `axiom/cli.py:236-253` içindeki `cmd_check` yalnızca `TypeChecker` çalıştırıyor; `SymbolicProver`/`Z3Prover` çağırmıyor. Oysa AUDIT belgesinde "1.2.3. `axiom check` ve `axiom prove` entegrasyonu" **tamamlandı** olarak işaretlenmiş.

#### (b) `print(...)` içindeki sözleşme ihlalleri her iki ispat motorundan kaçıyor

```axiom
fn check_port(port: int) -> bool
    requires port > 0 and port <= 65535
{ return true }

fn main() -> int {
    print(check_port(99999))
    return 0
}
```

```bash
$ axiom prove badprint.ax
✓ Statik Matematiksel İspat Başarılı ... 0 Hata - Kesin İspat
exit 0

$ axiom prove badprint.ax --smt
✓ ... UNSAT ... 0 Hata - Kesin İspat
exit 0
```

Aynı çağrı `let r = check_port(99999)` şeklinde yazıldığında yakalanıyor. Yani sorun ispat motorunun genel sesliliğinde değil, **`PrintStmt` düğümünün sembolik yürütmede hiç işlenmemesinde**. `axiom/prover.py:294-297` civarında `ExprStmt` ve `MatchStmt` var; `PrintStmt` yok.

#### (c) Fonksiyon çağrısı içindeki sıfıra bölme "ispatlanmış" sayılıyor

```axiom
fn safe_divide(a: int, b: int) -> int
    requires b != 0
{ return a / b }

fn main() -> int {
    print(safe_divide(10, 0))
    return 0
}
```

```bash
$ axiom prove divzero.ax --smt
✓ Statik Matematiksel İspat Başarılı ...
• İspatlanan Sözleşme Sayısı : 0
• Güvenli Bölme İşlemi (Div/0): 1
• Sözleşme İhlali veya Hata  : YOK (0 Hata - Kesin İspat)
exit 0
```

Çalışma anında ise program `[AXIOM GUVENLIK IHLALI] REQUIRES Basarisiz` ile duruyor (exit 101). Yani statik katman yanlış negatif veriyor.

**Etki:** Kullanıcı `axiom check` veya `axiom prove` çıktısına güvenerek hatalı kodu üretime alabilir. Dilin ana satış argümanı olan "matematiksel güvence" şu an güvenilir değil.

**Düzeltme:**
- `PrintStmt` (ve varsa diğer eksik düğümler) sembolik yürütmede argümanlarını değerlendirmeli.
- `cmd_check` varsayılan olarak prover çalıştırmalı; `--no-prove` açıkça sunulmalı.
- Sıfıra bölme, dizi sınırı, `requires`/`ensures` için pozitif **ve negatif** regresyon testleri eklenmeli.
- "Kesin İspat" ifadesi yalnızca seslilik testleri geçtikten sonra kullanılmalı; aksi hâlde "Kısmi/Doğrulanamadı" denmeli.
- İspat motorunun kapsamı (hangi ifadeler, hangi döngüler, hangi çağrılar) dokümante edilmeli.

---

### P0-4 — Aritmetik güvenlik yok: sıfıra bölme ve taşma

#### (a) Sabit sıfıra bölme çöp değer üretip başarıyla bitiyor

```axiom
fn main() -> int {
    let a = 10
    let b = 0
    print(a / b)
    return 0
}
```

```bash
$ axiom run dz_runtime.ax
140728270914680
exit 0
```

#### (b) Değişken sıfıra bölme SIGFPE ile çöküyor

```axiom
let a = str_to_int("10")
let b = str_to_int("0")
print(a / b)
```

```
exit 248 (sinyal kaynaklı çökme)
```

#### (c) Taşma sessizce sarıyor

```axiom
let a = 9223372036854775807
let b = a + 1
print(b)   # -9223372036854775808
```

**Neden:** `codegen_c.py` bölme/mod işlemlerine runtime kontrolü eklemiyor; `-O3` altında C'deki işaretli taşma ve sıfıra bölme tanımsız davranış (UB). `--ubsan` yalnızca kullanıcı açıkça isterse devreye giriyor.

**Etki:** "Güvenli sistem dili" iddiasıyla çelişen, sessiz veri bozulması ve çökme. Güvenlik aracı yazan kullanıcı için özellikle tehlikeli.

**Düzeltme:**
- Bölme/mod öncesi `b == 0` kontrolü ve `axiom_contract_fail` benzeri güvenli durdurma.
- Varsayılan `checked arithmetic` (veya en azından debug modda) ve taşmada hata; istenirse `wrapping_add` gibi açık API.
- `--ubsan`'ı test/CI'da varsayılan hâle getirmek.
- Negatif testler: `1/0`, `1%0`, `INT64_MAX+1`, `INT64_MIN/-1`.

---

## 5. Yüksek Öncelikli Bulgular (P1)

### P1-1 — Self-hosted derleyici "%100 eşitlik" iddiasını karşılamıyor

`GLOBAL_LANGUAGE_ROADMAP.md` "Dilin %100'ünü Derleyebilen `bin/axiomc`" diyor. Gerçek durum:

| Yetenek | Python `axiom` | `bin/axiomc` |
|---|---|---|
| Generics (`struct Box<T>`) | ✅ | ❌ C derleme hatası |
| Tip denetimi | ✅ (`SemanticError`) | ❌ Yok; C derleyicisine bırakılmış |
| Eksik `return` yakalama | ✅ | ❌ Uyarı ile derliyor |
| `int < str` tip karışıklığı | ✅ Reddediyor | ❌ Uyarı ile derliyor ve çalışıyor |
| `check` / `prove` / `fmt` / `lsp` | ✅ | ❌ Yok |
| Taşınabilir runtime yolu | ✅ | ❌ `~/Desktop/...` sabit |
| Statik sözleşme doğrulama | Kısmen | ❌ Yok, yalnızca runtime kontrol |

**Kanıt:**

```bash
$ ./bin/axiomc build generic.ax
/tmp/axiom_build_tmp.c:7:5: error: unknown type name 'ax_T'
...
exit 1
```

```bash
# Python derleyicisi reddediyor:
$ axiom check typeerr.ax
Semantik Hata: 'x' değişkeni 'int' olarak tanımlandı fakat 'str' atandı. exit 1

# axiomc derliyor:
$ ./bin/axiomc build typeerr.ax
[axiomc] Basariyla derlendi ...
```

Eksik `return` içeren fonksiyon da `axiomc` ile derleniyor (clang yalnızca uyarı veriyor), ardından çalışma zamanında tanımsız davranış riski taşıyor.

Ayrıca `compiler/main.ax` içinde runtime ve stdlib yolları sabit kodlu:

```axiom
resolved_mod_path = "~/Desktop/axiom/" + mod_slashed + ".ax"   # satır 37
let runtime_path = "~/Desktop/axiom/axiom/runtime.h"           # satır 111, 132, 180
```

`axiomc emit-c` çıktısı da makineye özgü mutlak `#include "~/Desktop/axiom/axiom/runtime.h"` satırı içeriyor; başka makinede derlenemez.

**Öneri:** Ya "deneysel alt küme derleyici" olarak etiketlenmeli, ya da tip denetleyicisi + generics + göreli yol + CLI eşitliği tamamlanmalı. `%100 parity` ifadesi şu an yanlış.

---

### P1-2 — LLVM arka ucu eksik ve kırılgan

- **`ensures` desteği yok.** `codegen_llvm.py:529` yalnızca `requires` döngüsünü işliyor; `ensures` için karşılık gelen bir blok yok. AUDIT'te bu madde açık (`2.3.1`) ama yol haritalarında "tamamlandı" görünümü var.
- **Örnek 17 (AI/tensor) LLVM ile derlenmiyor:**

```
/tmp/....ll:862:27: error: '%iop.37' defined with type 'i64' but expected 'double'
%fop.38 = fmul double %iop.37, 1.0
```

- **DWARF/debug sembolü yok.** `#line` yalnızca C arka ucunda (`codegen_c.py:399-401`) var; LLVM IR'de debug metadata üretilmiyor.
- **Test kapsamı yüzeysel.** `test_llvm.py` çoğunlukla IR string'i ve birkaç basit örnek çalıştırması kontrol ediyor; tüm örneklerin LLVM ile derlenip çalıştırılması CI'da yok.

**Öneri:** LLVM arka ucunu "deneysel" ilan etmek; `ensures`, float/int karışık aritmetik, string bellek yönetimi ve DWARF için test eklemek; 19 örneğin tamamını iki arka uçta da çalıştıran bir matris kurmak.

---

### P1-3 — Paket yöneticisi gerçek bağımlılık indirmiyor

`axiom/package_manager.py:383-448` incelendiğinde:

- `git` bağımlılıkları için yalnızca boş bir cache dizini oluşturuluyor (`git_cache_dir.mkdir(...)`), **`git clone` yapılmıyor**.
- `registry` bağımlılıkları için hiçbir ağ isteği yok; yalnızca `"registry:isim:versiyon"` string'inin SHA-256'sı checksum olarak yazılıyor.
- Lock dosyasındaki checksum, indirilen içeriğin değil, metadata string'inin özeti. Yani "deterministik kilit" güvenlik/tekrarlanabilirlik sağlamıyor.

**Doğrulama:**

```bash
$ axpm add foo --git https://example.com/foo.git
$ axpm install
✓ Bağımlılıklar kilitlendi: 1 paket -> axiom.lock

$ find .axiom -type f
(boş)
```

**Etki:** `axiom pkg install` bir projeyi gerçekten kurmuyor; bağımlılıklar derleme sırasında bulunamaz. Paket ekosistemi iddiası şu an kozmetik.

**Öneri:** Gerçek `git clone`/registry HTTP indirmesi, içerik checksum doğrulaması, offline/cache modu, hata yönetimi ve E2E testleri. Aksi hâlde "deneysel manifest/lock iskeleti" olarak etiketlenmeli.

---

### P1-4 — Çapraz derleme ve WASM hedefleri çalışmıyor

Roadmap "x86_64, aarch64, wasm32-wasi çoklu mimari" diyor. Denemeler:

```bash
$ axiom build examples/01_hello.ax --target wasm32-wasi -o hello.wasm
fatal error: 'bits/libc-header-start.h' file not found

$ axiom build examples/01_hello.ax --target aarch64-linux-gnu -o hello_arm
fatal error: 'bits/libc-header-start.h' file not found
```

**Neden:** `--target` yalnızca clang'a `--target=` bayrağı ekliyor; gerekli sysroot/cross-toolchain ve WASI libc sağlanmıyor. Ayrıca `runtime.h` POSIX (`epoll`, `pthread`, `mmap`, OpenSSL, zlib) varsayıyor; WASM'da bu başlıklar yok.

**Öneri:** Sysroot/toolchain konteyneri veya `zig cc`/WASI SDK entegrasyonu; WASM için ayrı, POSIX'siz bir runtime. Aksi hâlde bu hedefler yol haritasından çıkarılmalı.

---

### P1-5 — Ofansif güvenlik modülleri uyarısız ve izolasyonsuz

`AUDIT_REMEDIATION_TODO.md` "1.4.1. Ofansif modüllere açık güvenlik/etik uyarı başlıkları eklendi" diyor (işaretli). Gerçekte:

- `std/security/shellcode.ax`, `std/net/c2.ax`, `std/security/evasion.ax`, `std/security/memdump.ax`, `std/net/packet_crafter.ax` dosyalarının başlıklarında yalnızca birer açıklama satırı var; **etik/legal uyarı, yetki sınırı, "yalnızca izinli test ortamında" notu yok.**
- Modüller varsayılan `std/` ağacında, herhangi bir feature flag/opsiyonel paket olmadan geliyor.
- `tests/test_redteam_libs.py` varsayılan test paketinde **gerçek shellcode çalıştırıyor** (`b84d000000c3` → `ret 77`). Bu, CI ortamlarında AV/EDR alarmına ve bazı kurumsal politikaların ihlaline yol açabilir.

**Öneri:**
- Modülleri ayrı bir "opsiyonel/offensive" paketine taşımak veya `--features offensive` ile derlemeye bağlamak.
- Her dosyaya açık yasal/etik uyarı ve kullanım koşulu eklemek.
- Shellcode/C2 testlerini varsayılan CI'dan çıkarıp ayrı, izole bir iş akışına almak.
- `SECURITY.md` ve sorumlu açıklama politikası eklemek.

---

### P1-6 — Standart kütüphane geniş ama sığ; bazı iddialar gerçeği yansıtmıyor

49 modül / 2.606 satır ortalaması ~53 satır. Dağılım:

- 30+ modül **40 satırdan kısa**; çoğu yalnızca `rt_*` C fonksiyonuna ince sarmalayıcı.
- `std/encoding/json.ax` (22 satır) gerçek bir JSON parser değil; `runtime.h:1969` içindeki `axiom_json_find_key` düz metin içinde anahtar arıyor. İç içe nesne, dizi, ondalık sayı, Unicode kaçışı ve şema doğrulaması yok.
- `std/net/http.ax` (23 satır) tek `tcp_recv(65536)` yapıyor; chunked encoding, Content-Length, yönlendirme, TLS ve hata kodları yok. "Yüksek performanslı HTTP 1.1 istemcisi" değil, minimal düz TCP istemcisi.
- `std/target/wasm.ax` (49 satır) gerçek WASM ikilisi üretmiyor; yalnızca sihirli sayı (`0061736d...`) ve export metadata'sı tutuyor. "WASM ikili modül encoder" iddiası yanlış.
- `std/web/app.ax` middleware/context nesneleri sunuyor ama gerçek bir sunucu döngüsü, yönlendirme bağlama, JSON binding veya hata yönetimi yok. `std/net/http_server.ax` yalnızca 4 runtime sarmalayıcısı.
- `std/ai/*` modülleri AVX2 GEMM runtime'ına sarmalayıcı; autograd "computational graph" değil, birkaç manuel gradyan yardımcısı. `std/ai/inference.ax` ONNX/model dosyası okumuyor.
- `std/core/option.ax` / `result.ax` gerçek generic `Option<T>` / `Result<T,E>` değil; `OptionInt`, `OptionStr`, `OptionBool` gibi elle yazılmış kopyalar. `?` / `try` ile hata yayma operatörü yok.

**Öneri:** README'de "şu an mevcut" ve "planlanan" ayrımını net yapmak; her modül için olgunluk etiketi (`stable`, `beta`, `experimental`, `stub`) eklemek; sığ modülleri ya derinleştirmek ya da "ince sarmalayıcı" olarak işaretlemek.

---

## 6. Orta ve Düşük Öncelikli Bulgular (P2/P3)

### P2-1 — Sürüm ve test sayısı tutarsızlığı

| Yer | Değer |
|---|---|
| `axiom/__init__.py:4` | `0.1.0-alpha` |
| `README.md:3` | `v0.5.0-alpha` |
| `axiom/cli.py:632` (REPL) | `v0.3.0` |
| `axiom/lsp.py:156` | `0.5.0` |
| `compiler/main.ax` (`--version`) | `1.0.0` |
| `README.md:5` | 381 test |
| `MASTER_TODO.md:15` | 335 test |
| `TODO.md` | 138 / 161 / 189 test |
| **Gerçek** | **509 test** |

Tek bir sürüm kaynağı (ör. `pyproject.toml` + `__version__`) ve otomatik test sayısı rozeti olmalı.

### P2-2 — "Statik ikili" iddiası yanlış

```bash
$ file hello_bin
ELF 64-bit LSB pie executable, dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2

$ ldd hello_bin
libz.so.1, libssl.so.3, libcrypto.so.3, libm.so.6, libc.so.6, libzstd.so.1 ...
```

Üretilen ikili "bağımsız" değil; OpenSSL, zlib ve glibc'ye dinamik bağlı. README'deki "statik binary" ifadesi "Axiom runtime'ı gerektirmeyen tek dosya" anlamında yorumlanabilir ama teknik olarak statik değil. 17 KB'lık hello binary'si bunu doğruluyor.

### P2-3 — Proje/paketleme ve süreç eksikleri

- Git deposu yok (`git status` → "not a git repository").
- `pyproject.toml`, `setup.py`, `requirements.txt`, `Makefile`, `Dockerfile`, `CHANGELOG`, `CONTRIBUTING`, `SECURITY.md` yok.
- CI yalnızca `tools/ci_matrix.sh`; GitHub Actions/GitLab CI yok.
- Python bağımlılıkları (pytest, z3-solver, tomli) ve sistem bağımlılıkları (clang, OpenSSL, zlib) README'de eksik/eksik sürümlü.
- `tools/ci_matrix.sh` adım 1'de `axiom fmt compiler/*.ax` kaynak dosyaları **yerinde değiştiriyor**; CI'da kaynak mutasyonu kabul edilemez.

### P2-4 — Test altyapısı

- 509 test geçiyor; ancak kapsam (coverage) ölçümü yok.
- Negatif testler sınırlı: `str_free` literal, array aliasing, `print` içi sözleşme ihlali, `INT64` taşması, `axiomc` komut enjeksiyonu gibi bulgular test edilmiyor.
- Test süresi ~4,5 dakika; CI için paralelleştirme (pytest-xdist) ve katmanlı test (hızlı birim / yavaş E2E) yok.
- Bazı testler ağ, shellcode, `/proc` gibi ortama duyarlı özellikler kullanıyor; sandbox/CI uyumluluğu belirsiz.

### P2-5 — Dil ve tip sistemi boşlukları

- `enum`, `trait`/`interface`, `impl`, closure/lambda, namespace/modül sistemi yok (lexer anahtar kelimelerinde de yok).
- `Option`/`Result` generic değil; hata yayma operatörü yok.
- `null` güvenliği yalnızca elle yazılmış struct'larla sağlanıyor; dil seviyesinde garanti yok.
- Taşma/sıfıra bölme için dil seviyesinde güvenli aritmetik yok.
- String'ler `const char*`; sahiplik/ömür takibi yok.
- `break`/`continue` var; `loop`, etiketli döngü, `goto` yok (sorun değil, ama dokümante edilmeli).
- `defer` ve `invariant` var; ancak `invariant`'ın self-hosted ve LLVM tarafındaki desteği sınırlı.

### P2-6 — Formatter, LSP ve REPL sınırlı

- `formatter.py` 213 satır; pratikte çoğunlukla trailing whitespace siliyor. Girinti, boşluk, satır kırma, import sıralama gibi kanonik biçimlendirme yok. `examples/01_hello.ax` bile `fmt --check`'ten geçmiyor (yalnızca bir satır sonu boşluğu yüzünden).
- LSP temel `didOpen/didChange/completion/hover/definition` sunuyor; rename, references, code action, semantic tokens, formatting, incremental sync yok.
- REPL geçmişi, satır düzenleme, otomatik tamamlama ve çok satırlı bloklarda hata kurtarma sınırlı.

### P2-7 — Güvenlik yüzeyi ve yapılandırma riskleri

- `os_exec` (`runtime.h:898`) tasarım gereği `system()` kullanıyor; dilin standart API'si olarak sunulması riskli. `os_exec_argv` eklenmiş ama `os_exec` hâlâ varsayılan.
- `AXIOM_TLS_INSECURE=1` ortam değişkeni TLS sertifika doğrulamasını tamamen kapatıyor (`runtime.h:2438-2455`). Üretimde yanlışlıkla set edilirse MITM'e açık hâle gelir; en azından uyarı loglanmalı ve yalnızca debug build'de izin verilmeli.
- Ofansif modüllerin varsayılan gelmesi (P1-5) tedarik zinciri/AV/legal riski.
- `shellcode` RWX bellek tahsisi (`mmap` + `mprotect`) ve C2 protokolü içeriyor; kurumsal ortamda dağıtımı politika ihlali olabilir.

### P2-8 — Performans ve ölçüm eksikliği

- README'de "C/Rust kadar hızlı" deniyor; karşılaştırmalı benchmark, ölçüm metodolojisi veya sayı yok.
- `runtime.h` her derlemede header olarak işlendiği için derleme süreleri büyüyebilir; ölçüm yok.
- `-O3` varsayılan; güvenlik kontrolleri (bounds, contract) optimize edilmiş kodda ne kadar korunuyor, test edilmemiş.
- SIMD GEMM gerçek AVX2 kullanıyor (olumlu), ancak CPU fallback ve benchmark doğrulaması sınırlı.

### P2-9 — Dokümantasyon

- `SPECIFICATION.md` yalnızca 162 satır ve **v0.1**; generics, `match`, `defer`, `invariant`, `Option/Result`, LSP, paket yöneticisi, thread/atomic, hata modeli, bellek sahipliği, ABI, FFI gibi konular yok.
- Aynı belgede iki kez "## 3." başlığı var (satır 111 ve 119).
- README'deki bazı örnekler güncel olmayan sürüm/çıktı içeriyor (REPL çıktısı v0.3.0).
- Türkçe/İngilizce karışık terimler ve yazım tutarsızlıkları var.
- Dilbilgisi (EBNF), hata kodu kataloğu, bellek modeli ve güvenlik modeli referans dokümanı yok.

### P3-1 — Küçük kod hijyeni

- `axiom/cli.py:9`: `from typing import List, Optional, Tuple, Tuple` (yinelenen import).
- `axiom/package_manager.py` ve `cli.py` içinde birkaç `except Exception: pass` / `except: pass`; hatalar sessizce yutuluyor.
- `compiler/codegen.ax` `ensures`'ı string düzeyinde `"return"` arayarak dönüştürüyor; `return` kelimesi string literal içinde geçerse yanlış davranabilir.
- `axiomc` derleme komutunda `-Wno-parentheses-equality` gibi geniş susturmalar var.
- `runtime.h` tek dev header; modülerleştirme ve derleme süresi açısından iyileştirme alanı.

---

## 7. "İddia — Gerçek" Karşılaştırma Tablosu

| İddia | Gerçek durum | Kanıt |
|---|---|---|
| "Python kadar zarif, C/Rust kadar hızlı" | Yazım ergonomisi makul; performans kanıtlanmamış | Benchmark yok |
| "Borrow checker yükü yok" | Doğru; ama sahiplik modeli de yok | `str_free`/aliasing |
| "Zero-GC" | Doğru (GC yok) | — |
| "Zero-leak / RAII / otomatik temizlik" | **Yanlış** | ASan: 6,5 MB sızıntı |
| "Değer anlambilimi" | **Yanlış** (diziler referans paylaşıyor) | `a[0] == 99` testi |
| "Sözleşmeler derleme anında garanti" | **Kısmen/yanlış** | `check` geçiyor; `print` bypass |
| "Kesin İspat" | **Yanıltıcı** | `divzero.ax` "başarılı" |
| "Statik binary" | **Yanlış** (dinamik) | `ldd`: libssl, libz, libc |
| "Self-hosted %100 parity" | **Yanlış** | Generics/tip denetimi yok |
| "WASM ve çoklu mimari" | **Çalışmıyor** | `--target` derleme hatası |
| "Tam bağımlılık yönetimi (axpm)" | **Kozmetik** | Git clone/registry indirme yok |
| "35+ std modül" | Sayı doğru (49) ama derinlik yanıltıcı | 30+ modül < 40 satır |
| "381 test geçiyor" | Güncel değil | 509 test |
| "TLS anti-MITM" | Büyük ölçüde var; env ile kapatılabiliyor | `AXIOM_TLS_INSECURE` |
| "Ofansif modüller izole/uyarılı" | **Yanlış** | Uyarı yok, varsayılan geliyor |

---

## 8. Güvenlik ve Etik Değerlendirme

Axiom, güvenlik araçları yazmayı hedefleyen bir dil olduğu için güvenlik beklentisi yüksek olmalı. Mevcut durumda:

**Olumlu:**
- Dizi sınır denetimi çalışıyor.
- Runtime `requires` ihlallerini yakalıyor.
- TLS'te varsayılan olarak `SSL_VERIFY_PEER`, CA havuzu ve hostname doğrulaması var.
- JWT'de `alg: none` reddi, sabit zamanlı `CRYPTO_memcmp`, `exp`/`nbf` kontrolü var.
- C2'de rastgele IV ve HMAC-SHA256'ya geçilmiş; eski sabit IV yalnızca geriye dönük okuma yolunda.
- `os_exec_argv` ile shell'siz süreç çalıştırma API'si eklenmiş.

**Olumsuz / riskli:**
- Self-hosted derleyicide shell komut enjeksiyonu (P0-1).
- Bellek sahipliği modeli yok; UAF/double-free/leak mümkün (P0-2).
- Aritmetik UB (P0-4).
- `AXIOM_TLS_INSECURE` ile doğrulamayı kapatma.
- `os_exec` hâlâ `system()`.
- Ofansif modüllerin uyarısız dağıtımı ve shellcode testinin varsayılan CI'da çalışması.
- Paket yöneticisinin checksum'ları içerik doğrulamıyor; tedarik zinciri güvenliği yok.
- `--target`/WASM iddiaları yanlış güven verebilir.

**Öneri:** `SECURITY.md`, tehdit modeli, güvenli varsayılanlar, `unsafe`/`offensive` özellik bayrakları, bağımlılık imzalama/checksum doğrulaması ve sorumlu açıklama süreci.

---

## 9. Önceliklendirilmiş Yol Haritası

### 0–2 hafta — P0 (üretim bloğu)

| # | İş | Kabul kriteri |
|---|---|---|
| 1 | `axiomc` komut enjeksiyonunu kapat | `-o 'x; touch /tmp/pwned'` dosya oluşturmuyor; argv tabanlı exec |
| 2 | Bellek modeli acil yamaları | `str_free` literal'de no-op; `array_push` eski tamponu yönetiyor; ASan/LSan testi sıfır sızıntı |
| 3 | Dizi değer semantiği | `let b = a; b[0]=...` `a`'yı değiştirmiyor (veya dil bunu açıkça referans olarak belgeliyor) |
| 4 | Doğrulama sesliliği | `print(...)` içindeki ihlal yakalanıyor; `check` prover çalıştırıyor; `divzero` reddediliyor |
| 5 | Aritmetik güvenlik | `1/0`, `1%0`, taşma güvenli hata veriyor; `--ubsan` CI'da |
| 6 | Doküman/iddia senkronu | Tek sürüm kaynağı; README test sayısı 509; "bilinen sınırlamalar" bölümü |

### 2–8 hafta — P1

| # | İş | Kabul kriteri |
|---|---|---|
| 7 | Self-hosted derleyiciye tip denetleyicisi | `typeerr.ax`, `missing_ret.ax` reddediliyor |
| 8 | Self-hosted generics/match/Option-Result | `generic.ax`, `match.ax` derleniyor |
| 9 | Göreli runtime/stdlib yolları | Proje başka dizine taşınınca `axiomc` çalışıyor |
| 10 | LLVM `ensures` + float düzeltmesi + DWARF | 19 örnek LLVM ile derlenip çalışıyor |
| 11 | Gerçek paket yöneticisi | Git clone/registry indirme, içerik checksum, offline mod |
| 12 | Çapraz derleme/WASM | Sysroot/WASI SDK ile en az bir hedefte çalışan build; aksi hâlde iddia kaldırılıyor |
| 13 | Ofansif modül izolasyonu | Feature flag/ayrı paket, uyarılar, varsayılan CI'dan shellcode testi çıkarıldı |
| 14 | Stdlib olgunluk etiketleri | Her modül `stable/beta/experimental/stub` olarak işaretli |

### 2–6 ay — P2/P3

| # | İş |
|---|---|
| 15 | Git + `pyproject.toml` + GitHub Actions matrisi + coverage + benchmark |
| 16 | Gerçek JSON parser, HTTP/1.1 (chunked/TLS), web sunucu döngüsü |
| 17 | `enum`, `trait`, closure, namespace, hata yayma operatörü |
| 18 | EBNF dilbilgisi, bellek modeli, ABI/FFI, hata kodu kataloğu |
| 19 | Performans benchmark'ları (C/Rust/Python karşılaştırmalı) |
| 20 | Release süreci, CHANGELOG, CONTRIBUTING, SECURITY.md |

---

## 10. Doğrulama Eki — Kullanılan Komutlar

Aşağıdaki komutlar bulguların yeniden üretilmesi için kullanılabilir.

### Test paketi

```bash
cd ~/Desktop/axiom
python3 -m pytest -q
# 509 passed in 268.81s
```

### Komut enjeksiyonu

```bash
./bin/axiomc build examples/01_hello.ax \
  -o '/tmp/opencode/pwned; touch /tmp/opencode/INJECTED'
ls -l /tmp/opencode/INJECTED   # dosya oluşur
```

### Bellek sızıntısı

```bash
axiom run --asan /tmp/opencode/axprobe/leak.ax
# AddressSanitizer: 6507500 byte(s) leaked in 1000 allocation(s)
```

### Dizi aliasing

```bash
axiom run /tmp/opencode/axprobe/alias.ax
# a0: 99
# b0: 99
```

### Literal free

```bash
axiom run /tmp/opencode/axprobe/free_literal.ax
# free(): invalid pointer
```

### Doğrulama boşluğu

```bash
axiom check /tmp/opencode/axprobe/contract_bad.ax   # exit 0 (yanlış)
axiom prove /tmp/opencode/axprobe/contract_bad.ax   # exit 1 (doğru)
axiom prove /tmp/opencode/axprobe/badprint.ax       # exit 0 (yanlış)
axiom prove /tmp/opencode/axprobe/divzero.ax --smt  # exit 0 (yanlış)
```

### Aritmetik

```bash
axiom run /tmp/opencode/axprobe/dz_runtime.ax        # çöp değer, exit 0
axiom run /tmp/opencode/axprobe/dz_runtime2.ax       # sinyal/çökme
axiom run /tmp/opencode/axprobe/overflow.ax          # sessiz sarma
```

### Self-hosted eşitlik

```bash
./bin/axiomc build /tmp/opencode/axprobe/generic.ax  # C hatası
./bin/axiomc build /tmp/opencode/axprobe/typeerr.ax  # yanlışlıkla derlenir
./bin/axiomc build /tmp/opencode/axprobe/missing_ret2.ax  # yanlışlıkla derlenir
```

### Çapraz derleme

```bash
axiom build examples/01_hello.ax --target wasm32-wasi -o /tmp/hello.wasm
axiom build examples/01_hello.ax --target aarch64-linux-gnu -o /tmp/hello_arm
# her ikisi de 'bits/libc-header-start.h' bulunamadı
```

### LLVM

```bash
axiom build examples/17_ai_tensor_neural_net.ax --backend=llvm -o /tmp/nn
# fmul double %iop.37 tip hatası
```

---

## 11. Sonuç

Axiom'un temel fikri ve mühendislik iskeleti değerli. Özellikle tek bir projede lexer'dan LLVM'e, runtime'dan LSP'ye kadar bu genişlikte bir yapı kurulması takdire değer. 509 testin geçmesi ve temel örneklerin iki derleyiciyle de çalışması, projenin "demo" değil, gerçek bir geliştirme çabası olduğunu gösteriyor.

Ancak mevcut hâliyle Axiom:

- **güvenli değil** (komut enjeksiyonu, bellek sızıntısı, aliasing, aritmetik UB),
- **sesli değil** (doğrulama motoru yanlış negatifler veriyor),
- **taşınabilir değil** (sabit yollar, çalışmayan çapraz derleme),
- **kendi iddialarıyla tutarlı değil** (self-hosted parity, statik binary, paket yöneticisi, WASM).

Doğru strateji, iddiaları küçültüp güvenilirliği büyütmektir: **"alpha/araştırma dili"** etiketiyle yayınlamak, P0 maddelerini kapatmak, her iddia için çalıştırılabilir kanıt (test/benchmark) üretmek ve ancak ondan sonra "C/Rust alternatifi" konumlandırmasına geçmek.

Bu haliyle Axiom, öğrenme ve araştırma için mükemmel bir platform; üretim için henüz değil.
