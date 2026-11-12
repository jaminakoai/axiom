# Axiom (λx) Başlangıç Rehberi

> 🌍 **English:** [docs/en/TUTORIAL.md](en/TUTORIAL.md)

Bu rehber, Axiom'u ilk kez kullanan bir geliştiricinin dili kurup çalıştırabilmesi, temel sözdizimini öğrenmesi, sözleşmeleri ve `Result` tabanlı hata modelini günlük kodda kullanabilmesi için hazırlandı.

Axiom; statik tipli, yerel derlenen ve sözleşme güdümlü (contract-driven) bir sistem programlama dilidir. Python'a yakın bir yazım ergonomisi sunarken C/LLVM üzerinden bağımsız ELF ikilisi üretir.

---

## 1. Kurulum

### Gereksinimler

- Linux (x86_64; ARM64 deneysel)
- Python 3.10 veya üzeri
- `clang` (tercih edilir) veya `gcc`
- Üretilen ikililer için sistemde `glibc`, `libssl`, `libcrypto`, `libz` ve `libpthread`

### Yol ayarı

Depoyu klonladıktan sonra `bin/` dizinini `PATH`'e ekleyin:

```bash
cd /path/to/axiom
export PATH="$PWD/bin:$PATH"
```

Bu ayar yalnızca mevcut kabuk oturumu için geçerlidir. Kalıcı hale getirmek isterseniz aynı satırı `~/.bashrc` veya `~/.zshrc` dosyanıza ekleyebilirsiniz.

### Sürüm kontrolü

```bash
axiom --version
```

Örnek çıktı:

```text
Axiom (λx) v0.5.0-alpha
```

`axpm` paket yöneticisi ve `axiom-lsp` dil sunucusu da aynı `bin/` dizininde bulunur.

---

## 2. İlk program

Depodaki hazır örneği çalıştırarak başlayın:

```bash
axiom run examples/01_hello.ax
```

Çıktı:

```text
Merhaba, Guvenlik Uzmani! Axiom dunyasina hos geldin.
1'den 10'a kadar olan sayilarin toplami:
55
[DOGRULAMA] Toplam hesabi basarili ve dogru!
```

`axiom run`, kaynak kodu önce denetler, C'ye derler, geçici bir ikili üretir ve çalıştırır.

### Bağımsız ikili dosya üretme

```bash
axiom build examples/01_hello.ax -o hello
./hello
```

`-o` verilmezse çıktı adı kaynak dosyanın adından türetilir (`01_hello`).

---

## 3. Temel sözdizimi

### Yorumlar

Axiom'da hem `#` hem de `//` satır yorumu olarak kullanılabilir:

```axiom
# Bu bir yorumdur
// Bu da bir yorumdur
```

### Değişkenler

Değişkenler varsayılan olarak değiştirilemezdir (immutable). Değiştirilecek değişkenler için `let mut` kullanılır:

```axiom
let port: int = 8080        # tip açıkça belirtildi
let host = "127.0.0.1"      # tip çıkarımı: str
let mut counter = 0         # değiştirilebilir, tip çıkarımı: int
```

Tip çıkarımı çoğu durumda yeterlidir; okunabilirlik veya belirsizlik durumunda tip açıkça yazılabilir.

### Fonksiyonlar

```axiom
fn square(x: int) -> int {
    return x * x
}

fn selamla(isim: str) -> void {
    print("Merhaba, " + isim)
}
```

- `-> int` dönüş tipini belirtir.
- Değer döndürmeyen fonksiyonlarda `-> void` kullanılır.
- Değer döndüren her fonksiyonun tüm kod yollarında `return` içermesi gerekir.

### Kontrol akışı

```axiom
fn square(x: int) -> int {
    return x * x
}

fn main() -> int {
    let name = "Axiom"
    let mut counter = 0

    if name == "Axiom" {
        print("Merhaba, " + name)
    } else {
        print("Baska bir dil")
    }

    while counter < 3 {
        counter = counter + 1
    }
    print("counter:", counter)

    for i in 0..3 {
        print("i =", i)
    }

    print("square:", square(7))
    return 0
}
```

> Bu blok kendi içinde çalışır: `axiom run` ile deneyebilirsiniz.
> (Yukarıdaki `square` tanımı kısa olması için burada yinelenmiştir.)

`0..3` aralığı `0, 1, 2` üretir; üst sınır dahil değildir.

`print` birden fazla argüman alabilir ve aralarına boşluk koyar:

```axiom
print("port:", 8080, "acik mi:", true)
```

### `match`

Axiom'da desen eşleştirme vardır:

```axiom
fn classify(x: int) -> str {
    return match x {
        1 => "bir",
        2 => "iki",
        _ => "diger"
    }
}
```

`int` ve `str` üzerinde yapılan `match` ifadelerinde tüm durumları kapsamak için genellikle `_` joker deseni gerekir.

### Axiom'da olmayan yapılar

- `try` / `catch` / `except` **yoktur**. Beklenen hatalar için `Result<T, E>` ve `?` kullanılır.
- `enum` **yoktur**.
- `trait` **yoktur**.
- Closure / lambda **yoktur**.

### Noktalı virgül

Noktalı virgül opsiyoneldir. Bu rehberdeki örneklerde tutarlılık için çoğunlukla kullanılmamıştır.

---

## 4. Tipler ve struct

### Yerleşik tipler

| Tip | Açıklama |
| :--- | :--- |
| `int` | 64-bit işaretli tamsayı |
| `float` | 64-bit IEEE 754 kayan noktalı sayı |
| `bool` | `true` veya `false` |
| `str` | UTF-8 metin |
| `T[]` | Dinamik dizi; örneğin `int[]`, `str[]`, `Point[]` |
| `void` | Yalnızca dönüş tipi olarak kullanılır |

### Struct tanımı

```axiom
struct Point {
    x: int,
    y: int
}
```

### Struct oluşturma ve alan erişimi

```axiom
struct Point {
    x: int,
    y: int
}

fn main() -> int {
    let p = Point { x: 1, y: 2 }
    print(p.x, p.y)

    let mut q = Point { x: 10, y: 20 }
    q.x = 30
    print(q.x, q.y)
    return 0
}
```

Struct başlatma notasyonu `Point { x: 1, y: 2 }` biçimindedir. Alanları değiştirmek için struct değişkeninin `let mut` ile tanımlanması gerekir.

Struct'lar fonksiyon parametresi ve dönüş tipi olarak kullanılabilir:

```axiom
fn move_point(p: Point, dx: int, dy: int) -> Point {
    return Point { x: p.x + dx, y: p.y + dy }
}
```

---

## 5. Diziler

### Dizi literali, `len` ve indeksleme

```axiom
fn main() -> int {
    let numbers = [1, 2, 3]
    print(len(numbers))
    print(numbers[0])
    print(numbers[2])
    return 0
}
```

İndeksler `0`'dan başlar. Erişim çalışma zamanında sınır denetimine tabidir. Geçersiz bir indeks programı durdurur:

```text
[AXIOM BELLEK IHLALI] Dizi sınır aşımı (Index out of bounds)!
```

Bu durumda çıkış kodu `102` olur.

### `array_push`

`array_push`, dizinin yeni halini döndürür. Sonucu mutlaka bir değişkene atayın:

```axiom
fn main() -> int {
    let mut values = [1, 2]
    values = array_push(values, 3)
    print(len(values), values[2])
    return 0
}
```

Dizinin değişebilmesi için `let mut` gerekir. `array_push` hem `int[]` hem de `str[]` ile çalışır.

### Dizi ataması değer semantiğindedir

Bir diziyi başka bir değişkene atadığınızda derin kopya (deep copy) oluşur. İki dizi sonrasında bağımsızdır:

```axiom
fn main() -> int {
    let a = [1, 2, 3]
    let mut b = a       # b, a'nin kopyasidir

    b[0] = 9

    print("a[0]:", a[0])   # 1
    print("b[0]:", b[0])   # 9
    return 0
}
```

Çıktı:

```text
a[0]: 1
b[0]: 9
```

Yani `let b = a` sonrasında `b` üzerinde yapılan değişiklik `a`'yı etkilemez. Bu davranış, dizilerin referans değil değer gibi davrandığı anlamına gelir.

---

## 6. Sözleşmeler

Axiom'un ayırt edici özelliklerinden biri, fonksiyonların ön koşul ve son koşullarını dilin parçası olarak ifade edebilmesidir.

### `requires`, `ensures` ve `verify`

```axiom
fn safe_divide(a: int, b: int) -> int
    requires b != 0
    ensures return * b <= a
{
    return a / b
}

fn main() -> int {
    let r = safe_divide(10, 2)
    verify r == 5, "bolme sonucu yanlis"
    print(r)
    return 0
}
```

- `requires`: Çağıranın sağlaması gereken ön koşuldur.
- `ensures`: Fonksiyonun dönüşünde garanti edilen son koşuldur.
- `verify`: Kodun belirli bir noktasında doğrulanan iddiadır. İsteğe bağlı bir mesaj alabilir.

### Ne zaman kullanılmalı?

Sözleşmeler **programlama hatası** durumları içindir:

- Bir port numarasının `1..65535` aralığında olması gerekiyorsa,
- Bir bölenin asla sıfır olmaması gerekiyorsa,
- Bir fonksiyonun dönüş değerinin negatif olmaması gerekiyorsa.

Dosya bulunamaması, ağ bağlantısının kurulamaması veya kullanıcı girdisinin geçersiz olması gibi **beklenen** durumlar için sözleşme değil, `Result<T, E>` kullanılmalıdır.

Sözleşme ihlali programı durdurur:

```text
[AXIOM GUVENLIK IHLALI] REQUIRES Basarisiz Oldu!
Program mantık bütünlüğü ve güvenlik gerekçesiyle durduruldu.
```

Çıkış kodu `101`'dir.

### İspat araçları

```bash
axiom prove examples/03_contracts.ax
axiom check --smt examples/03_contracts.ax
```

- `axiom prove`, sembolik yürütme ve aralık analizi ile sözleşmeleri ispatlamaya çalışır.
- `axiom check --smt`, Z3 SMT çözücüsünü kullanır.
- `axiom check --all`, hem sembolik hem SMT motorunu çalıştırır.
- Sözleşmeyi statik olarak ihlal eden bir çağrı, örneğin `safe_divide(10, 0)`, derleme aşamasında reddedilebilir.

Döngü içeren fonksiyonlarda sembolik motor her zaman kesin sonuç veremeyebilir. `axiom check` bu durumda `2` döndürebilir; `--smt` veya `--no-prove` seçeneklerini değerlendirin.

---

## 7. Hata yönetimi: `Result` ve `?`

Beklenen hatalar `Result<T, E>` ile taşınır. Axiom'da `try/except` yoktur.

### Kanonik `Result` tipi

`std/core/error` modülü şu yapıyı ve yardımcıları sağlar:

```axiom
struct Result<T, E> {
    is_ok: bool,
    value: T,
    error: E
}
```

Alan adları sabittir: `is_ok`, `value`, `error`.

### Kurucular

```axiom
result_ok<int>(42)
result_err_int("gecersiz port")
result_err_str("dosya okunamadi")
result_err_bool("islem basarisiz")
```

Kendi struct tipiniz için:

```axiom
result_err_with<Config>("yapilandirma yok", Config { name: "", port: 0 })
```

`result_ok<T>(v)` tipi argümandan çıkarır. Hata kurucularında ise taşınacak `T` değeri açıkça verilmelidir; bu nedenle yaygın tipler için `result_err_int`, `result_err_str`, `result_err_bool` hazırdır.

### `?` operatörü

`?`, bir `Result` ifadesini açar:

- `Ok` ise içindeki `value` değerini üretir.
- `Err` ise hatayı çağıran fonksiyona iletir.
- Erken dönüş sırasında `defer` blokları ve kapsam temizliği çalışır.

```axiom
import "std/core/error"

fn parse_port(s: str) -> Result<int, str> {
    let v = str_to_int(s)
    if v <= 0 or v > 65535 {
        return result_err_int("gecersiz port: " + s)
    }
    return result_ok<int>(v)
}

fn resolve(port_str: str) -> Result<int, str> {
    defer {
        print("[temizlik] resolve bitti")
    }
    let port = parse_port(port_str)?
    return result_ok<int>(port)
}

fn main() -> Result<int, str> {
    let port = resolve("8080")?
    print("port:", port)
    return result_ok<int>(0)
}
```

Çıktı:

```text
[temizlik] resolve bitti
port: 8080
```

`?` yalnızca `Result` döndüren bir fonksiyonun içinde kullanılabilir. Ayrıca ifadenin hata tipi, fonksiyonun hata tipiyle uyuşmalıdır.

### `Result` yardımcıları

```axiom
let r = parse_port("8080")

if r.is_ok {
    print("port:", r.value)
}

print(result_is_ok(r))
print(result_is_err(r))
print(result_unwrap_or<int>(r, -1))
```

- `result_unwrap<T>(r)`: `Ok` değilse sözleşme ihlali ile durur; yalnızca gerçekten `Ok` olduğundan emin olduğunuzda kullanın.
- `result_unwrap_or<T>(r, fallback)`: `Err` durumunda yedek değer döndürür.
- `result_expect<T>(r, msg)`: `Ok` değilse belirtilen mesajla durur.
- `result_error<T>(r)`: yalnızca `Err` üzerinde güvenlidir.

### `main` fonksiyonu `Result` döndürebilir

```axiom
import "std/core/error"

fn fail() -> Result<int, str> {
    return result_err_int("patladi")
}

fn main() -> Result<int, str> {
    let v = fail()?
    print("ULASILMAMALI")
    return result_ok<int>(v)
}
```

Bu programda `?` hatayı `main`'e taşır. `main` `Err` döndürdüğünde:

- Hata mesajı `stderr`'a yazılır.
- Çıkış kodu `1` olur.

`Ok` döndüğünde çıkış kodu `0` olur. `main` içinde özel bir çıkış kodu döndürmek istiyorsanız `fn main() -> int` kullanın.

### Kritik ayrım

| Durum | Mekanizma | Davranış |
| :--- | :--- | :--- |
| Dosya yok, port kapalı, ağ hatası, geçersiz kullanıcı girdisi | `Result<T, E>` + `?` | Hata `Err` olarak yukarı akar; çağıran karar verir |
| Kod hatası: geçersiz sabit, boş ön koşul, yanlış mantık | `requires` / `ensures` / `verify` | Derleme veya çalışma anında program durur (exit `101`) |
| Dizi sınırı aşımı | Çalışma zamanı sınır denetimi | Program durur (exit `102`) |
| Tamsayı taşması / sıfıra bölme | Çalışma zamanı aritmetik koruması | Program durur (exit `101`) |

Özet: **beklenen hata `Result` ile akar; programlama hatası sözleşme ile durur.**

---

## 8. Stdlib `Result` katmanı

Standart kütüphanenin birçok modülü, hata ayırt edilebilen `Result` tabanlı API sunar. Eski "sessiz" API'ler hata durumunda `""`, `0` veya `false` döndürür ve nedeni ayırt edemez; yeni kodda `Result` sürümlerini tercih edin.

### `std/io/file`

| Fonksiyon | Dönüş tipi | Açıklama |
| :--- | :--- | :--- |
| `read_file(path)` | `Result<str, str>` | Dosyayı okur; yoksa `Err` |
| `write_file(path, content)` | `Result<bool, str>` | Dosyanın üzerine yazar |
| `append_file(path, content)` | `Result<bool, str>` | Dosyaya ekler |
| `read_lines(path)` | `Result<str[], str>` | İçeriği satırlara böler |
| `file_present(path)` | `bool` | Dosya var mı? (hata üretmez) |

### `std/encoding/json`

| Fonksiyon | Dönüş tipi |
| :--- | :--- |
| `json_get_str_result(json, key)` | `Result<str, str>` |
| `json_get_int_result(json, key)` | `Result<int, str>` |
| `json_get_bool_result(json, key)` | `Result<bool, str>` |

Eksik anahtar, boş JSON veya tip uyuşmazlığı `Err` olarak döner.

### `std/net/http`

| Fonksiyon | Dönüş tipi | Açıklama |
| :--- | :--- | :--- |
| `http_get_result(host, port, path)` | `Result<str, str>` | HTTP GET yanıtı |
| `http_status(response)` | `Result<int, str>` | `"HTTP/1.1 200 OK"` → `200` |
| `http_body(response)` | `Result<str, str>` | Başlıklardan sonraki gövde |

### Diğer modüller

- `std/crypto/tls`: `https_get_result(host, port, path) -> Result<str, str>`
- `std/os/process`: `exec_output_result(cmd) -> Result<str, str>`

### Uçtan uca örnek: dosyadan JSON oku

```axiom
import "std/core/error"
import "std/io/file"
import "std/encoding/json"

fn load(path: str) -> Result<int, str> {
    let raw = read_file(path)?
    let port = json_get_int_result(raw, "port")?
    return result_ok<int>(port)
}

fn main() -> Result<int, str> {
    let path = "/tmp/axiom_tutorial.json"
    let payload = "{\"port\":8080}"

    let wrote = write_file(path, payload)?
    if wrote {
        print("yazildi")
    }

    let port = load(path)?
    print("port:", port)
    return result_ok<int>(0)
}
```

Çıktı:

```text
yazildi
port: 8080
```

### HTTP örneği

```axiom
import "std/core/error"
import "std/net/http"

fn fetch() -> Result<int, str> {
    let response = http_get_result("example.com", 80, "/")?
    let status = http_status(response)?
    let body = http_body(response)?
    print("durum:", status)
    print("govde uzunlugu:", len(body))
    return result_ok<int>(status)
}
```

Ağ erişimi olmayan ortamlarda bu örnek `Err` döndürür; bu beklenen bir hatadır ve program çökmez.

---

## 9. Modüller

### Standart kütüphane içe aktarma

İki eşdeğer biçim desteklenir:

```axiom
import "std:io:file"
import "std:core:error"
import "std:encoding:json"
```

veya eğik çizgi biçimi:

```axiom
import "std/io/file"
import "std/core/error"
import "std/encoding/json"
```

`.ax` uzantısı isteğe bağlıdır:

```axiom
import "std:net:http.ax"
```

### Yerel dosya içe aktarma

Aynı dizindeki bir dosya göreli yol ile içe aktarılır:

```axiom
import "utils.ax"
```

`examples/06_modules/main.ax` dosyasındaki `import "utils.ax"` buna örnektir. İçe aktarılan dosyadaki fonksiyonlar ve struct'lar doğrudan kullanılabilir; ayrı bir isim alanı (namespace) öneki yoktur.

```axiom
# utils.ax
struct ConfigReport {
    title: str,
    version: int
}

fn create_report(title: str, version: int) -> ConfigReport {
    return ConfigReport { title: title, version: version }
}
```

```axiom
# main.ax
import "utils.ax"

fn main() -> int {
    let report = create_report("Sistem", 1)
    print(report.title, report.version)
    return 0
}
```

Modül çözümleyici döngüsel bağımlılıkları tespit eder ve elmas bağımlılıklarda aynı dosyanın birden fazla kez üretilmesini engeller.

> **Not:** Yukarıdaki iki blok tek bir programın parçalarıdır. Denemek için aynı dizinde
> `utils.ax` ve `main.ax` dosyalarını oluşturup `axiom run main.ax` çalıştırın.
> Buradaki bloklar tek başına kopyalandığında `utils.ax` bulunamadığı için hata verir.

---

## 10. Eşzamanlılık

Axiom, POSIX pthread tabanlı iş parçacıkları, mutex ve atomik sayaçlar sunar.

### Fonksiyonlar

| Fonksiyon | Açıklama |
| :--- | :--- |
| `thread_create(fn_name, arg: int) -> int` | İş parçacığı başlatır; `fn_name` tek `int` parametreli ve `int` döndüren fonksiyon olmalıdır |
| `thread_join(th_id: int) -> int` | İş parçacığını bekler ve dönüş değerini verir |
| `mutex_init() -> int` | Mutex oluşturur |
| `mutex_lock(id) -> void` | Kilidi alır |
| `mutex_unlock(id) -> void` | Kilidi bırakır |
| `atomic_init(val) -> int` | Atomik sayaç oluşturur |
| `atomic_add(id, val) -> int` | Atomik toplama yapar |
| `atomic_get(id) -> int` | Atomik değeri okur |
| `sleep_ms(ms) -> void` | Belirtilen milisaniye kadar bekler |

### Örnek

```axiom
fn worker(n: int) -> int {
    return n * 2
}

fn main() -> int {
    let t1 = thread_create(worker, 21)
    let t2 = thread_create(worker, 10)

    let r1 = thread_join(t1)
    let r2 = thread_join(t2)
    print(r1, r2)

    let m = mutex_init()
    mutex_lock(m)
    print("kritik bolge")
    mutex_unlock(m)

    let counter = atomic_init(0)
    atomic_add(counter, 5)
    print(atomic_get(counter))

    sleep_ms(10)
    return 0
}
```

Çıktı:

```text
42 20
kritik bolge
5
```

### Uyarılar

- `thread_create` yalnızca **tek bir `int` argüman** alır. Struct veya birden fazla değer taşımanız gerekiyorsa değerleri paketleyip `int` olarak kodlamanız ya da iş parçacığı başına ayrı bir fonksiyon tanımlamanız gerekir.
- İş parçacıkları aynı süreç belleğini paylaşır. Paylaşılan durumu `mutex_*` veya `atomic_*` ile koruyun.
- `thread_join` çağrılmadan program sonlanırsa iş parçacığının sonucu alınamaz.

---

## 11. Araçlar

### Denetleme ve ispat

```bash
axiom check examples/01_hello.ax
axiom check --smt examples/03_contracts.ax
axiom check --all examples/03_contracts.ax
axiom check --no-prove examples/01_hello.ax
axiom prove examples/03_contracts.ax
axiom prove --smt examples/09_simd_vector_scan.ax
```

- `check`: sözdizimi, tip ve sözleşme denetimi.
- `check --smt`: Z3 SMT ile sözleşme doğrulaması.
- `check --all`: sembolik ve SMT motorlarını birlikte çalıştırır.
- `check --no-prove`: biçimsel ispat adımını atlar.
- `prove`: statik matematiksel ispat raporu üretir.
- `prove --smt`: Z3 tabanlı ispat.

### Kod üretme

```bash
axiom emit-c examples/01_hello.ax -o hello.c
axiom emit-llvm examples/01_hello.ax -o hello.ll
axiom emit-llvm examples/01_hello.ax -g
axiom emit-smt examples/03_contracts.ax -o contracts.smt2
```

- `emit-c`: üretilen C99 kodunu incelemek için.
- `emit-llvm`: üretilen LLVM IR'yi incelemek için.
- `emit-smt`: SMT-LIB2 biçiminde teorem çıktısı.

### Biçimlendirme

```bash
axiom fmt examples/01_hello.ax
axiom fmt --check examples/01_hello.ax
```

`axiom fmt` dosyayı yerinde biçimlendirir. `--check` yalnızca denetler; dosya standart formatta değilse `1` döndürür.

### REPL

```bash
axiom repl
```

Örnek oturum:

```text
Axiom (λx) v0.5.0-alpha - İnteraktif REPL
Yardım için 'help', çıkış için 'exit' veya 'quit' yazın.

axiom> let x = 40
axiom> x + 2
42
axiom> quit
```

### Proje ve paket yönetimi

```bash
axiom init my_project
cd my_project
axiom run src/main.ax
```

`axiom init`, `axiom.toml`, `src/main.ax`, `README.md` ve `.gitignore` içeren bir proje iskeleti oluşturur.

Paket yöneticisi `axpm` olarak da çağrılabilir:

```bash
axiom pkg init
axiom pkg add yerel_paket --path ../yerel_paket
axiom pkg add uzak_paket --git https://example.com/paket.git --rev main
axiom pkg install
axiom pkg update
axiom pkg verify
axiom pkg tree
axiom pkg remove yerel_paket
axiom pkg build
axiom pkg run
axiom pkg test
```

Eşdeğer kullanım:

```bash
axpm init
axpm add ...
axpm install
```

Notlar:

- Yerel (`--path`) ve Git (`--git`, `--rev`) bağımlılıkları desteklenir.
- `axiom.lock` içindeki SHA-256 sağlama toplamları `verify` ile denetlenir.
- Merkezi bir paket havuzu (registry) henüz yoktur; registry bağımlılıklarında `install` açık hata verir.

### Dil sunucusu

```bash
axiom lsp
# veya doğrudan:
axiom-lsp
```

`axiom lsp`, editörlerin kod tamamlama, tanıma gitme ve hata gösterme gibi özellikleri kullanabilmesi için stdio üzerinden Language Server Protocol sunar.

### Testler

```bash
axiom test
axiom test --asan
```

Depodaki pytest tabanlı test paketini çalıştırır.

---

## 12. Derleme

### Temel derleme

```bash
axiom build examples/01_hello.ax -o hello
```

### Optimizasyon

```bash
axiom build examples/02_fibonacci.ax -O0 -o fib_debug
axiom build examples/02_fibonacci.ax -O2 -o fib_o2
axiom build examples/02_fibonacci.ax -O3 -o fib_o3
```

Varsayılan optimizasyon seviyesi `-O3`'tür.

### Hata ayıklama sembolleri

```bash
axiom build examples/01_hello.ax -g -o hello_debug
```

`-g`, DWARF hata ayıklama bilgisi üretir. LLVM arka ucunda da kaynak satırları ve yerel değişkenler için DWARF metadata üretilir.

### LLVM arka ucu

```bash
axiom build examples/01_hello.ax --backend=llvm -o hello_llvm
axiom build examples/19_error_handling.ax --backend=llvm -o errors_llvm
```

Varsayılan arka uç C'dir (`--backend=c`). LLVM arka ucu `defer` ve `?` operatörünü destekler.

### Sanitizer'lar

```bash
axiom build examples/01_hello.ax --asan -o hello_asan
axiom build examples/01_hello.ax --ubsan -o hello_ubsan
axiom run examples/01_hello.ax --asan
```

- `--asan`: AddressSanitizer + UndefinedBehaviorSanitizer.
- `--ubsan`: yalnızca UndefinedBehaviorSanitizer.

Bellek sızıntısı veya tanımsız davranış şüphesinde `--asan` ile çalıştırın.

### Çapraz derleme (deneysel)

```bash
axiom build examples/01_hello.ax \
  --target aarch64-linux-gnu \
  --sysroot /path/to/aarch64-sysroot \
  -o hello_arm

axiom build examples/01_hello.ax \
  --target wasm32-wasi \
  --sysroot /path/to/wasi-sysroot \
  -o hello.wasm
```

Çapraz derleme harici toolchain ve sysroot gerektirir. Sysroot yoksa derleyici açıklayıcı bir hatayla durur. `aarch64` ve `wasm32-wasi` hedefleri deneysel statüdedir.

### Bağımlılıklar

Üretilen ELF ikilileri bağımsız çalıştırılabilir, ancak host sistemin `glibc`, `libssl`, `libcrypto`, `libz` ve `libpthread` kütüphanelerine dinamik olarak bağlanır.

---

## 13. Yaygın hatalar ve çözümleri

Aşağıdaki mesajlar sürüme göre küçük farklılıklar gösterebilir; anahtar ifadeler korunmuştur.

| Hata mesajı | Neden | Çözüm |
| :--- | :--- | :--- |
| `Degistirilemez (immutable) degiskene atama yapilamaz: 'x'. 'let mut' kullanin.` | Değişken `let` ile tanımlanmış, sonradan atama yapılmaya çalışılıyor. | `let x` yerine `let mut x` kullanın. |
| `Tanimlanmamis degisken: 'x'` | Değişken tanımlanmamış, yazımı yanlış veya kapsam dışında. | Değişkeni kullanmadan önce tanımlayın; yazımı ve kapsamı kontrol edin. |
| `Fonksiyon 'X' dondurme tipi 'int' olarak belirtilmis ancak tum kod dallarinda return bulunmuyor.` | `if/else` veya döngü sonrası bazı yollarda `return` yok. | Her kod yolunda uygun tipte `return` olduğundan emin olun. |
| `'safe_divide' fonksiyonunun 'requires' sözleşmesi kesin olarak ihlal edildi!` | Çağrı, statik olarak kanıtlanabilir biçimde ön koşulu ihlal ediyor. | Argümanı düzeltin veya sözleşmeyi gerçekten doğru olacak şekilde güncelleyin. |
| `[AXIOM GUVENLIK IHLALI] REQUIRES Basarisiz Oldu!` | Çalışma zamanında bir `requires` koşulu sağlanmadı. | Çağrı öncesi koşulu sağlayın; bu bir programlama hatasıdır, `Result` ile yakalanmaz. |
| `'?' kullanilan fonksiyon 'Result' dondurmeli; 'X' 'int' donduruyor.` | `?` yalnızca `Result` döndüren fonksiyonlarda kullanılabilir. | Fonksiyonun dönüş tipini `Result<T, str>` yapın veya `?` yerine `is_ok`/`error` ile elle işleyin. |
| `'?' hata tipi uyusmuyor: ifade 'str', fonksiyon 'int' donduruyor.` | `Result` ifadesinin hata tipi ile fonksiyonun hata tipi farklı. | Hata tiplerini aynı yapın; gerekirse `result_err_with` ile dönüştürün. |
| `[AXIOM BELLEK IHLALI] Dizi sınır aşımı (Index out of bounds)!` (exit `102`) | Dizi indeksi `0 <= i < len(dizi)` aralığının dışında. | `len` ile sınırı kontrol edin; negatif indeks kullanmayın. |
| `ARITHMETIC_OVERFLOW` / `Tamsayi toplama tasmasi!` (exit `101`) | 64-bit `int` aralığı taşıyor. | Girdi aralığını doğrulayın, ara sonuçları sınırlayın veya algoritmayı taşmayacak şekilde tasarlayın. |
| `ARITHMETIC_ZERO_DIV` / `Sifira bolme hatasi!` (exit `101`) | Bölen sıfır. | Böleni kontrol edin veya `requires b != 0` ile sözleşme tanımlayın. |
| `Hata: 'std:security:shellcode' ofansif güvenlik modülüdür. Yalnızca izinli test ortamlarında '--features offensive' bayrağı ile derlenebilir.` | Ofansif modül varsayılan derlemede kapalı. | Yalnızca yetkili test ortamında `--features offensive` veya `AXIOM_FEATURES=offensive` kullanın. |
| `Bilinmeyen fonksiyon cagrisi: 'foo'` | Fonksiyon tanımlanmamış, adı yanlış veya modül içe aktarılmamış. | Fonksiyonu tanımlayın, adını düzeltin veya ilgili `import` satırını ekleyin. |
| `Tuketici olmayan match` | `match` tüm olası durumları kapsamıyor. | `int`/`str` eşleşmelerinde `_ => ...` joker dalını ekleyin. |
| `C Derleme Hatasi` | Üretilen C kodu sistem derleyicisi tarafından reddedildi. | Mesajdaki C satırını inceleyin; çoğunlukla eksik sistem kütüphanesi veya desteklenmeyen bir kullanım söz konusudur. |

---

## 14. Bilinen sınırlamalar

Axiom `v0.5.0-alpha` araştırma/prototip aşamasındadır. Üretim kritik projelerde aşağıdaki sınırlamaları göz önünde bulundurun.

### Bellek ve string yaşam döngüsü

String'ler refcount tabanlı bir sahiplik tablosuyla izlenir. Atama, `return`, `file_read`, `str_split`, `str_replace`, `str_sub`, `str_trim`, base64/hex/hash üreticileri ve `array_push` sonuçları kapsam çıkışında temizlenir.

Bilinen sınır: `print(f(x))` gibi **atama yapılmayan** bazı ifadelerde üretilen geçici string'ler ifade sonunda hemen bırakılmayabilir. Intrusive-header ve `String`/`str` tip ayrımı ile bu alanın iyileştirilmesi planlanmaktadır.

### Paket registry'si

`axpm` yerel (`--path`) ve Git (`--git`, `--rev`) bağımlılıklarını gerçekten klonlar ve SHA-256 ile kilitler. Ancak merkezi bir paket havuzu (registry) henüz yoktur; registry bağımlılıklarında `install` açık hata verir.

### WASM hedefi

`--target wasm32-wasi` deneyseldir ve harici WASI SDK/sysroot gerektirir. Sysroot yoksa derleme yönlendirici bir hatayla durur.

### LLVM arka ucunda string temizliği

LLVM arka ucu `defer`, `?` ve DWARF üretimini destekler. String kapsamı ve temizliği tarafında iyileştirmeler sürüyor olabilir; bu alan hızla değişebilir. Bu konuda referans davranış için varsayılan C arka ucunu esas alın.

### ARM64 / çapraz derleme

`aarch64-linux-gnu` hedefi deneyseldir ve harici cross-toolchain ile sysroot gerektirir. x86_64 yerel derleme birincil hedeftir.

### Self-hosted derleyici

`bin/axiomc` (`compiler/main.ax`) temel sözdizimini ve bazı generic yapıları derleyebilen alfa prototipidir. Tam kapsamlı sözleşme denetimi ve Z3 SMT doğrulaması için Python tabanlı `bin/axiom` sürücüsü önerilir.

### Dinamik sistem kütüphaneleri

Üretilen ELF dosyaları tam statik değildir; host sistemin `glibc`, `libssl`, `libcrypto`, `libz` ve `libpthread` kütüphanelerine dinamik bağlanır. Tam statik/musl desteği yol haritasındadır.

### Dil kapsamı

- `match` vardır.
- `try/except`, `enum`, `trait` ve closure/lambda yoktur.
- Genel amaçlı ham işaretçi aritmetiği standart bloklarda engellenmiştir.

### Ofansif güvenlik modülleri

`shellcode`, `c2`, `evasion`, `memdump` ve `packet_crafter` modülleri varsayılan olarak reddedilir. Yalnızca yetkili test ortamlarında `--features offensive` ile derlenebilir.

---

## 15. Sırada ne var?

Axiom'un yol haritasındaki başlıca başlıklar:

- String sahipliği ve kapsam temizliğinin tamamlanması (intrusive header, `String`/`str` ayrımı).
- Merkezi paket registry'si ve daha olgun bağımlılık çözümlemesi.
- WASM ve ARM64 hedeflerinin deneysel statüden çıkarılması.
- LLVM arka ucunda string temizliği ve genel arka uç eşliğinin güçlendirilmesi.
- Self-hosted derleyicinin (`axiomc`) özellik eşliğinin artırılması.
- Daha geniş standart kütüphane ve örnek koleksiyonu.

Dili keşfetmenin en hızlı yolu `examples/` dizinindeki programları çalıştırmak ve `axiom check` / `axiom prove` ile sözleşmeleri denemektir.

---

> **Not:** Bu rehber v0.5.0-alpha içindir. Dil ve araçlar hızla geliştiği için davranışlar, hata mesajları ve bayraklar sürümler arasında değişebilir. Güncel bilgi için depodaki `README.md`, `SPECIFICATION.md` ve `examples/` dizinini esas alın.
