# Axiom (λx) Getting Started Guide

> 🌍 **Türkçe:** [docs/TUTORIAL.md](../TUTORIAL.md)

This guide is written so that a developer using Axiom for the first time can install and run the language, learn the basic syntax, and use contracts and the `Result`-based error model in everyday code.

Axiom is a statically typed, natively compiled, contract-driven systems programming language. It offers a writing ergonomics close to Python while producing standalone ELF binaries through C/LLVM.

---

## 1. Installation

### Requirements

- Linux (x86_64; ARM64 experimental)
- Python 3.10 or later
- `clang` (preferred) or `gcc`
- `glibc`, `libssl`, `libcrypto`, `libz` and `libpthread` on the system for the produced binaries

### Path setup

After cloning the repository, add the `bin/` directory to `PATH`:

```bash
cd /path/to/axiom
export PATH="$PWD/bin:$PATH"
```

This setting applies only to the current shell session. If you want to make it permanent, you can add the same line to your `~/.bashrc` or `~/.zshrc` file.

### Version check

```bash
axiom --version
```

Example output:

```text
Axiom (λx) v0.5.0-alpha
```

The `axpm` package manager and the `axiom-lsp` language server are also located in the same `bin/` directory.

---

## 2. First program

Start by running the ready-made example in the repository:

```bash
axiom run examples/01_hello.ax
```

Output:

```text
Merhaba, Guvenlik Uzmani! Axiom dunyasina hos geldin.
1'den 10'a kadar olan sayilarin toplami:
55
[DOGRULAMA] Toplam hesabi basarili ve dogru!
```

`axiom run` first checks the source code, compiles it to C, produces a temporary binary, and runs it.

### Producing a standalone binary

```bash
axiom build examples/01_hello.ax -o hello
./hello
```

If `-o` is not given, the output name is derived from the source file name (`01_hello`).

---

## 3. Basic syntax

### Comments

In Axiom, both `#` and `//` can be used as line comments:

```axiom
# This is a comment
// This is also a comment
```

### Variables

Variables are immutable by default. For variables that will be changed, `let mut` is used:

```axiom
let port: int = 8080        # type explicitly specified
let host = "127.0.0.1"      # type inference: str
let mut counter = 0         # mutable, type inference: int
```

Type inference is sufficient in most cases; the type can be written explicitly for readability or in cases of ambiguity.

### Functions

```axiom
fn square(x: int) -> int {
    return x * x
}

fn selamla(isim: str) -> void {
    print("Merhaba, " + isim)
}
```

- `-> int` specifies the return type.
- `-> void` is used for functions that do not return a value.
- Every function that returns a value must contain a `return` on all code paths.

### Control flow

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

> This block is self-contained: you can try it with `axiom run`.
> (The `square` definition above is repeated here to keep it short.)

The range `0..3` produces `0, 1, 2`; the upper bound is not included.

`print` can take multiple arguments and puts a space between them:

```axiom
print("port:", 8080, "acik mi:", true)
```

### `match`

Axiom has pattern matching:

```axiom
fn classify(x: int) -> str {
    return match x {
        1 => "bir",
        2 => "iki",
        _ => "diger"
    }
}
```

In `match` expressions on `int` and `str`, the `_` wildcard pattern is generally required to cover all cases.

### Constructs that do not exist in Axiom

- There is **no** `try` / `catch` / `except`. For expected errors, `Result<T, E>` and `?` are used.
- There is **no** `enum`.
- There is **no** `trait`.
- There are **no** closures / lambdas.

### Semicolon

The semicolon is optional. In the examples in this guide it is mostly not used, for consistency.

---

## 4. Types and struct

### Built-in types

| Type | Description |
| :--- | :--- |
| `int` | 64-bit signed integer |
| `float` | 64-bit IEEE 754 floating-point number |
| `bool` | `true` or `false` |
| `str` | UTF-8 text |
| `T[]` | Dynamic array; for example `int[]`, `str[]`, `Point[]` |
| `void` | Used only as a return type |

### Struct definition

```axiom
struct Point {
    x: int,
    y: int
}
```

### Creating a struct and accessing fields

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

The struct initialization notation is `Point { x: 1, y: 2 }`. To modify fields, the struct variable must be declared with `let mut`.

Structs can be used as function parameters and return types:

```axiom
fn move_point(p: Point, dx: int, dy: int) -> Point {
    return Point { x: p.x + dx, y: p.y + dy }
}
```

---

## 5. Arrays

### Array literal, `len` and indexing

```axiom
fn main() -> int {
    let numbers = [1, 2, 3]
    print(len(numbers))
    print(numbers[0])
    print(numbers[2])
    return 0
}
```

Indexes start at `0`. Access is subject to bounds checking at runtime. An invalid index stops the program:

```text
[AXIOM BELLEK IHLALI] Dizi sınır aşımı (Index out of bounds)!
```

In this case the exit code is `102`.

### `array_push`

`array_push` returns the new state of the array. Always assign the result to a variable:

```axiom
fn main() -> int {
    let mut values = [1, 2]
    values = array_push(values, 3)
    print(len(values), values[2])
    return 0
}
```

`let mut` is required for the array to be changeable. `array_push` works with both `int[]` and `str[]`.

### Array assignment has value semantics

When you assign an array to another variable, a deep copy is created. The two arrays are independent afterwards:

```axiom
fn main() -> int {
    let a = [1, 2, 3]
    let mut b = a       # b is a copy of a

    b[0] = 9

    print("a[0]:", a[0])   # 1
    print("b[0]:", b[0])   # 9
    return 0
}
```

Output:

```text
a[0]: 1
b[0]: 9
```

That is, after `let b = a`, a change made on `b` does not affect `a`. This behavior means that arrays behave like values rather than references.

---

## 6. Contracts

One of the distinguishing features of Axiom is that it can express the preconditions and postconditions of functions as part of the language.

### `requires`, `ensures` and `verify`

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

- `requires`: The precondition that the caller must satisfy.
- `ensures`: The postcondition guaranteed on the function's return.
- `verify`: An assertion checked at a specific point in the code. It can take an optional message.

### When should they be used?

Contracts are for **programming error** situations:

- When a port number must be in the `1..65535` range,
- When a divisor must never be zero,
- When a function's return value must not be negative.

For **expected** situations such as a file not being found, a network connection failing, or user input being invalid, `Result<T, E>` should be used rather than a contract.

A contract violation stops the program:

```text
[AXIOM GUVENLIK IHLALI] REQUIRES Basarisiz Oldu!
Program mantık bütünlüğü ve güvenlik gerekçesiyle durduruldu.
```

The exit code is `101`.

### Proof tools

```bash
axiom prove examples/03_contracts.ax
axiom check --smt examples/03_contracts.ax
```

- `axiom prove` attempts to prove contracts with symbolic execution and range analysis.
- `axiom check --smt` uses the Z3 SMT solver.
- `axiom check --all` runs both the symbolic and SMT engines.
- A call that statically violates a contract, for example `safe_divide(10, 0)`, can be rejected at the compilation stage.

For functions containing loops, the symbolic engine may not always give a definitive result. In this case `axiom check` may return `2`; consider the `--smt` or `--no-prove` options.

---

## 7. Error handling: `Result` and `?`

Expected errors are carried with `Result<T, E>`. Axiom has no `try/except`.

### Canonical `Result` type

The `std/core/error` module provides the following structure and helpers:

```axiom
struct Result<T, E> {
    is_ok: bool,
    value: T,
    error: E
}
```

The field names are fixed: `is_ok`, `value`, `error`.

### Constructors

```axiom
result_ok<int>(42)
result_err_int("gecersiz port")
result_err_str("dosya okunamadi")
result_err_bool("islem basarisiz")
```

For your own struct type:

```axiom
result_err_with<Config>("yapilandirma yok", Config { name: "", port: 0 })
```

`result_ok<T>(v)` infers the type from the argument. In error constructors, however, the `T` value to be carried must be given explicitly; therefore `result_err_int`, `result_err_str`, `result_err_bool` are ready-made for common types.

### The `?` operator

`?` unwraps a `Result` expression:

- If it is `Ok`, it produces the `value` inside it.
- If it is `Err`, it propagates the error to the calling function.
- During the early return, `defer` blocks and scope cleanup run.

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

Output:

```text
[temizlik] resolve bitti
port: 8080
```

`?` can only be used inside a function that returns `Result`. In addition, the error type of the expression must match the error type of the function.

### `Result` helpers

```axiom
let r = parse_port("8080")

if r.is_ok {
    print("port:", r.value)
}

print(result_is_ok(r))
print(result_is_err(r))
print(result_unwrap_or<int>(r, -1))
```

- `result_unwrap<T>(r)`: Stops with a contract violation if it is not `Ok`; use it only when you are sure it really is `Ok`.
- `result_unwrap_or<T>(r, fallback)`: Returns the fallback value in the `Err` case.
- `result_expect<T>(r, msg)`: Stops with the specified message if it is not `Ok`.
- `result_error<T>(r)`: Safe only on `Err`.

### The `main` function can return `Result`

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

In this program, `?` propagates the error to `main`. When `main` returns `Err`:

- The error message is written to `stderr`.
- The exit code becomes `1`.

When it returns `Ok`, the exit code becomes `0`. If you want to return a special exit code inside `main`, use `fn main() -> int`.

### Critical distinction

| Situation | Mechanism | Behavior |
| :--- | :--- | :--- |
| File missing, port closed, network error, invalid user input | `Result<T, E>` + `?` | The error flows upward as `Err`; the caller decides |
| Code error: invalid constant, empty precondition, wrong logic | `requires` / `ensures` / `verify` | The program stops at compile time or runtime (exit `101`) |
| Array out-of-bounds | Runtime bounds checking | The program stops (exit `102`) |
| Integer overflow / division by zero | Runtime arithmetic protection | The program stops (exit `101`) |

Summary: **an expected error flows through `Result`; a programming error stops through a contract.**

---

## 8. Stdlib `Result` layer

Many modules of the standard library offer a `Result`-based API that makes errors distinguishable. The old "silent" APIs return `""`, `0` or `false` on error and cannot distinguish the cause; prefer the `Result` versions in new code.

### `std/io/file`

| Function | Return type | Description |
| :--- | :--- | :--- |
| `read_file(path)` | `Result<str, str>` | Reads the file; `Err` if it does not exist |
| `write_file(path, content)` | `Result<bool, str>` | Overwrites the file |
| `append_file(path, content)` | `Result<bool, str>` | Appends to the file |
| `read_lines(path)` | `Result<str[], str>` | Splits the content into lines |
| `file_present(path)` | `bool` | Does the file exist? (does not produce an error) |

### `std/encoding/json`

| Function | Return type |
| :--- | :--- |
| `json_get_str_result(json, key)` | `Result<str, str>` |
| `json_get_int_result(json, key)` | `Result<int, str>` |
| `json_get_bool_result(json, key)` | `Result<bool, str>` |

A missing key, empty JSON or a type mismatch is returned as `Err`.

### `std/net/http`

| Function | Return type | Description |
| :--- | :--- | :--- |
| `http_get_result(host, port, path)` | `Result<str, str>` | HTTP GET response |
| `http_status(response)` | `Result<int, str>` | `"HTTP/1.1 200 OK"` → `200` |
| `http_body(response)` | `Result<str, str>` | The body after the headers |

### Other modules

- `std/crypto/tls`: `https_get_result(host, port, path) -> Result<str, str>`
- `std/os/process`: `exec_output_result(cmd) -> Result<str, str>`

### End-to-end example: reading JSON from a file

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

Output:

```text
yazildi
port: 8080
```

### HTTP example

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

In environments without network access, this example returns `Err`; this is an expected error and the program does not crash.

---

## 9. Modules

### Importing the standard library

Two equivalent forms are supported:

```axiom
import "std:io:file"
import "std:core:error"
import "std:encoding:json"
```

or the slash form:

```axiom
import "std/io/file"
import "std/core/error"
import "std/encoding/json"
```

The `.ax` extension is optional:

```axiom
import "std:net:http.ax"
```

### Importing a local file

A file in the same directory is imported with a relative path:

```axiom
import "utils.ax"
```

`import "utils.ax"` in `examples/06_modules/main.ax` is an example of this. Functions and structs in the imported file can be used directly; there is no separate namespace prefix.

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

The module resolver detects circular dependencies and prevents the same file from being produced more than once in diamond dependencies.

> **Note:** The two blocks above are parts of a single program. To try it, create the
> `utils.ax` and `main.ax` files in the same directory and run `axiom run main.ax`.
> When the blocks here are copied on their own, they give an error because `utils.ax` cannot be found.

---

## 10. Concurrency

Axiom offers POSIX pthread-based threads, mutexes and atomic counters.

### Functions

| Function | Description |
| :--- | :--- |
| `thread_create(fn_name, arg: int) -> int` | Starts a thread; `fn_name` must be a function with a single `int` parameter that returns `int` |
| `thread_join(th_id: int) -> int` | Waits for the thread and gives its return value |
| `mutex_init() -> int` | Creates a mutex |
| `mutex_lock(id) -> void` | Acquires the lock |
| `mutex_unlock(id) -> void` | Releases the lock |
| `atomic_init(val) -> int` | Creates an atomic counter |
| `atomic_add(id, val) -> int` | Performs atomic addition |
| `atomic_get(id) -> int` | Reads the atomic value |
| `sleep_ms(ms) -> void` | Waits for the specified number of milliseconds |

### Example

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

Output:

```text
42 20
kritik bolge
5
```

### Warnings

- `thread_create` takes only **a single `int` argument**. If you need to carry a struct or multiple values, you must pack the values and encode them as an `int`, or define a separate function per thread.
- Threads share the same process memory. Protect shared state with `mutex_*` or `atomic_*`.
- If the program terminates without `thread_join` being called, the thread's result cannot be obtained.

---

## 11. Tools

### Checking and proving

```bash
axiom check examples/01_hello.ax
axiom check --smt examples/03_contracts.ax
axiom check --all examples/03_contracts.ax
axiom check --no-prove examples/01_hello.ax
axiom prove examples/03_contracts.ax
axiom prove --smt examples/09_simd_vector_scan.ax
```

- `check`: syntax, type and contract checking.
- `check --smt`: contract verification with Z3 SMT.
- `check --all`: runs the symbolic and SMT engines together.
- `check --no-prove`: skips the formal proof step.
- `prove`: produces a static mathematical proof report.
- `prove --smt`: Z3-based proof.

### Code generation

```bash
axiom emit-c examples/01_hello.ax -o hello.c
axiom emit-llvm examples/01_hello.ax -o hello.ll
axiom emit-llvm examples/01_hello.ax -g
axiom emit-smt examples/03_contracts.ax -o contracts.smt2
```

- `emit-c`: for inspecting the generated C99 code.
- `emit-llvm`: for inspecting the generated LLVM IR.
- `emit-smt`: theorem output in SMT-LIB2 format.

### Formatting

```bash
axiom fmt examples/01_hello.ax
axiom fmt --check examples/01_hello.ax
```

`axiom fmt` formats the file in place. `--check` only checks; it returns `1` if the file is not in the standard format.

### REPL

```bash
axiom repl
```

Example session:

```text
Axiom (λx) v0.5.0-alpha - İnteraktif REPL
Yardım için 'help', çıkış için 'exit' veya 'quit' yazın.

axiom> let x = 40
axiom> x + 2
42
axiom> quit
```

### Project and package management

```bash
axiom init my_project
cd my_project
axiom run src/main.ax
```

`axiom init` creates a project skeleton containing `axiom.toml`, `src/main.ax`, `README.md` and `.gitignore`.

The package manager can also be invoked as `axpm`:

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

Equivalent usage:

```bash
axpm init
axpm add ...
axpm install
```

Notes:

- Local (`--path`) and Git (`--git`, `--rev`) dependencies are supported.
- The SHA-256 checksums in `axiom.lock` are checked with `verify`.
- There is not yet a central package registry; for registry dependencies, `install` gives an explicit error.

### Language server

```bash
axiom lsp
# or directly:
axiom-lsp
```

`axiom lsp` provides the Language Server Protocol over stdio so that editors can use features such as code completion, go to definition and error display.

### Tests

```bash
axiom test
axiom test --asan
```

Runs the pytest-based test suite in the repository.

---

## 12. Compilation

### Basic compilation

```bash
axiom build examples/01_hello.ax -o hello
```

### Optimization

```bash
axiom build examples/02_fibonacci.ax -O0 -o fib_debug
axiom build examples/02_fibonacci.ax -O2 -o fib_o2
axiom build examples/02_fibonacci.ax -O3 -o fib_o3
```

The default optimization level is `-O3`.

### Debug symbols

```bash
axiom build examples/01_hello.ax -g -o hello_debug
```

`-g` produces DWARF debug information. The LLVM backend also produces DWARF metadata for source lines and local variables.

### LLVM backend

```bash
axiom build examples/01_hello.ax --backend=llvm -o hello_llvm
axiom build examples/19_error_handling.ax --backend=llvm -o errors_llvm
```

The default backend is C (`--backend=c`). The LLVM backend supports `defer` and the `?` operator.

### Sanitizers

```bash
axiom build examples/01_hello.ax --asan -o hello_asan
axiom build examples/01_hello.ax --ubsan -o hello_ubsan
axiom run examples/01_hello.ax --asan
```

- `--asan`: AddressSanitizer + UndefinedBehaviorSanitizer.
- `--ubsan`: UndefinedBehaviorSanitizer only.

When you suspect a memory leak or undefined behavior, run with `--asan`.

### Cross-compilation (experimental)

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

Cross-compilation requires an external toolchain and sysroot. If the sysroot is missing, the compiler stops with a descriptive error. The `aarch64` and `wasm32-wasi` targets are experimental.

### Dependencies

The produced ELF binaries are standalone executables, but they link dynamically against the host system's `glibc`, `libssl`, `libcrypto`, `libz` and `libpthread` libraries.

---

## 13. Common errors and solutions

The following messages may show minor differences depending on the version; the key phrases have been preserved.

| Error message | Cause | Solution |
| :--- | :--- | :--- |
| `Degistirilemez (immutable) degiskene atama yapilamaz: 'x'. 'let mut' kullanin.` | The variable was declared with `let`, and an assignment is attempted afterwards. | Use `let mut x` instead of `let x`. |
| `Tanimlanmamis degisken: 'x'` | The variable is not declared, its spelling is wrong, or it is out of scope. | Declare the variable before using it; check the spelling and scope. |
| `Fonksiyon 'X' dondurme tipi 'int' olarak belirtilmis ancak tum kod dallarinda return bulunmuyor.` | There is no `return` on some paths after `if/else` or a loop. | Make sure there is a `return` of the appropriate type on every code path. |
| `'safe_divide' fonksiyonunun 'requires' sözleşmesi kesin olarak ihlal edildi!` | The call violates the precondition in a statically provable way. | Fix the argument or update the contract so that it is actually correct. |
| `[AXIOM GUVENLIK IHLALI] REQUIRES Basarisiz Oldu!` | A `requires` condition was not satisfied at runtime. | Satisfy the condition before the call; this is a programming error and is not caught with `Result`. |
| `'?' kullanilan fonksiyon 'Result' dondurmeli; 'X' 'int' donduruyor.` | `?` can only be used in functions that return `Result`. | Make the function's return type `Result<T, str>`, or handle it manually with `is_ok`/`error` instead of `?`. |
| `'?' hata tipi uyusmuyor: ifade 'str', fonksiyon 'int' donduruyor.` | The error type of the `Result` expression differs from the function's error type. | Make the error types the same; convert with `result_err_with` if necessary. |
| `[AXIOM BELLEK IHLALI] Dizi sınır aşımı (Index out of bounds)!` (exit `102`) | The array index is outside the range `0 <= i < len(array)`. | Check the bound with `len`; do not use negative indexes. |
| `ARITHMETIC_OVERFLOW` / `Tamsayi toplama tasmasi!` (exit `101`) | The 64-bit `int` range is exceeded. | Validate the input range, bound intermediate results, or design the algorithm so that it does not overflow. |
| `ARITHMETIC_ZERO_DIV` / `Sifira bolme hatasi!` (exit `101`) | The divisor is zero. | Check the divisor or define a contract with `requires b != 0`. |
| `Hata: 'std:security:shellcode' ofansif güvenlik modülüdür. Yalnızca izinli test ortamlarında '--features offensive' bayrağı ile derlenebilir.` | The offensive module is disabled in the default build. | Use `--features offensive` or `AXIOM_FEATURES=offensive` only in an authorized test environment. |
| `Bilinmeyen fonksiyon cagrisi: 'foo'` | The function is not defined, its name is wrong, or the module is not imported. | Define the function, fix its name, or add the relevant `import` line. |
| `Tuketici olmayan match` | The `match` does not cover all possible cases. | Add the `_ => ...` wildcard branch in `int`/`str` matches. |
| `C Derleme Hatasi` | The generated C code was rejected by the system compiler. | Inspect the C line in the message; it is usually a missing system library or an unsupported usage. |

---

## 14. Known limitations

Axiom `v0.5.0-alpha` is at the research/prototype stage. Consider the following limitations in production-critical projects.

### Memory and string lifetime

Strings are tracked with a refcount-based ownership table. The results of assignment, `return`, `file_read`, `str_split`, `str_replace`, `str_sub`, `str_trim`, the base64/hex/hash producers and `array_push` are cleaned up on scope exit.

Known limitation: in some expressions that **do not assign**, such as `print(f(x))`, the temporary strings produced may not be released immediately at the end of the expression. Intrusive headers and a `String`/`str` type distinction are planned to improve this area.

### Package registry

`axpm` really clones and SHA-256 locks local (`--path`) and Git (`--git`, `--rev`) dependencies. However, there is not yet a central package registry; for registry dependencies, `install` gives an explicit error.

### WASM target

`--target wasm32-wasi` is experimental and requires an external WASI SDK/sysroot. If the sysroot is missing, compilation stops with a guiding error.

### String cleanup in the LLVM backend

The LLVM backend supports `defer`, `?` and DWARF generation. Improvements on the string scope and cleanup side may still be ongoing; this area can change rapidly. For reference behavior on this subject, take the default C backend as the basis.

### ARM64 / cross-compilation

The `aarch64-linux-gnu` target is experimental and requires an external cross-toolchain and sysroot. Native x86_64 compilation is the primary target.

### Self-hosted compiler

`bin/axiomc` (`compiler/main.ax`) is an alpha prototype that can compile the basic syntax and some generic constructs. For full-scope contract checking and Z3 SMT verification, the Python-based `bin/axiom` driver is recommended.

### Dynamic system libraries

The produced ELF files are not fully static; they link dynamically against the host system's `glibc`, `libssl`, `libcrypto`, `libz` and `libpthread` libraries. Full static/musl support is on the roadmap.

### Language scope

- `match` exists.
- `try/except`, `enum`, `trait` and closures/lambdas do not exist.
- General-purpose raw pointer arithmetic is blocked in standard blocks.

### Offensive security modules

The `shellcode`, `c2`, `evasion`, `memdump` and `packet_crafter` modules are rejected by default. They can be compiled with `--features offensive` only in authorized test environments.

---

## 15. What's next?

The main items on Axiom's roadmap:

- Completing string ownership and scope cleanup (intrusive header, `String`/`str` distinction).
- A central package registry and more mature dependency resolution.
- Moving the WASM and ARM64 targets out of experimental status.
- String cleanup in the LLVM backend and strengthening overall backend parity.
- Increasing the feature parity of the self-hosted compiler (`axiomc`).
- A broader standard library and example collection.

The fastest way to explore the language is to run the programs in the `examples/` directory and try the contracts with `axiom check` / `axiom prove`.

---

> **Note:** This guide is for v0.5.0-alpha. Because the language and tools evolve rapidly, behaviors, error messages and flags may change between versions. For up-to-date information, refer to `README.md`, `SPECIFICATION.md` and the `examples/` directory in the repository.
