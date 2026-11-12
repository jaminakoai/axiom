# Axiom (λx) Language Specification — v0.5

> 🌍 **Turkish:** [SPECIFICATION.md](../../SPECIFICATION.md)

**Status:** Alpha (`v0.5.0-alpha`)
**This document:** Defines the observable behavior of the language. The implementation is obligated to conform to this specification; if there is a conflict, **the implementation is at fault, not the specification** — either the implementation is fixed or this document is updated with justification.

> **Alpha warning:** Backward compatibility is **not guaranteed**. Syntax and semantics may change; changes are recorded in `CHANGELOG.md`.

---

## 1. Scope and terminology

| Term | Meaning |
|---|---|
| **MUST** | Every conforming implementation has to do this. |
| **SHOULD** | Not doing it is not an error, but it may lead to unexpected behavior. |
| **undefined** | Behavior is not guaranteed; the programmer MUST NOT rely on it. |
| **compile time** | During source → binary translation. |
| **runtime** | While the produced binary is executing. |

The specification takes the **C backend** (default) as its reference. The LLVM backend MUST provide the same observable behavior; deviations are listed in §13.4.

---

## 2. Design principles

1. **Zero cognitive load** — no borrow checker; `defer`-based scope cleanup and value semantics.
2. **Zero-GC** — no pauses; memory ownership is managed by cooperation between the compiler and the runtime.
3. **Safety by contract** — logic errors are halted at compile time or runtime via `requires` / `ensures` / `verify`.
4. **Native compilation** — a standalone ELF via C99 or LLVM IR; there is no interpreter.
5. **Two-tier error model** — *expected* errors use `Result<T,E>` + `?`; *programming* errors are contract violations → the program stops.

---

## 3. Lexical structure

### 3.1 Source encoding

Source files are UTF-8. The extension is `.ax`.

### 3.2 Comments

```axiom
# Single line (Python style)
// Single line (C style)
```

There are no block comments (`/* */`).

### 3.3 Keywords (complete list)

```
fn  let  mut  if  else  while  for  in  return  print
verify  requires  ensures  struct  import
break  continue  defer  invariant  as  match
true  false  and  or  not
```

These words cannot be used as identifiers.

### 3.4 Type names

```
int  float  bool  str  void
```

### 3.5 Identifiers

`[A-Za-z_][A-Za-z0-9_]*`. A standalone `_` is the wildcard pattern (`match`).

### 3.6 Numeric literals

```
42          # int
3.14        # float
```

- A negative number is not a literal; it is the unary `-` operator.
- `0x`, `0b`, and the underscore separator (`1_000`) are **not supported**.
- Scientific notation (`1e9`) is **not supported**.

### 3.7 String literals

Double quotes. Supported escape sequences:

| Escape | Meaning |
|---|---|
| `\n` | newline |
| `\r` | carriage return |
| `\t` | tab |
| `\\` | backslash |
| `\"` | double quote |

Other `\x` sequences are interpreted as `x`. There are no multi-line string blocks.

### 3.8 Operators and precedence (highest to lowest)

| Precedence | Operators | Associativity |
|---|---|---|
| 1 | `()` `[]` `.` `?` | postfix |
| 2 | `-` `+` `not` | unary (prefix) |
| 3 | `as` | type cast |
| 4 | `*` `/` `%` | left |
| 5 | `+` `-` | left |
| 6 | `<` `<=` `>` `>=` | left |
| 7 | `==` `!=` | left |
| 8 | `and` | left |
| 9 | `or` | left |
| 10 | `=` | assignment (statement) |

`=` produces no expression other than assignment.

---

## 4. Types

### 4.1 Built-in types

| Axiom | C equivalent | Description |
|---|---|---|
| `int` | `int64_t` | 64-bit signed integer |
| `float` | `double` | 64-bit IEEE-754 |
| `bool` | `bool` | `true` / `false` |
| `str` | `const char*` | UTF-8, NUL-terminated |
| `void` | `void` | no value |

### 4.2 Composite types

- **Array:** `T[]` — `{ length: int, capacity: int, data: T* }`.
- **Struct:** `struct Ad { alan: Tip, ... }` — a value type.
- **Generic parameter:** `T` (only in generic declarations).

### 4.3 Type inference

In the form `let x = <expression>`, the type is inferred from the expression. Inference is performed only at the first assignment; the type does not change afterwards.

### 4.4 Explicit conversion (`as`)

```axiom
let a = 3.9 as int      # 3 (fraction is discarded)
let b = 7 as float      # 7.0
let c = 1 as bool       # true
```

Supported targets: `int`, `float`, `bool`. `as str` is **not supported**; use `int_to_str` for conversion to text.

### 4.5 Type compatibility

- In arithmetic, `int` and `float` may be mixed; the result becomes `float`.
- In comparison (`<`, `<=`, `>`, `>=`), either both sides MUST be numeric **or** both sides MUST be `str`. `int < str` is a **compile error**.
- In equality (`==`, `!=`), the types MUST be the same (conversion between numeric types is allowed).
- Logical `and`/`or`/`not` accept only `bool`.

---

## 5. Variables and scope

```axiom
let sabit = 10          # immutable
let mut sayac = 0       # mutable
let port: int = 8080    # explicit type
```

- Assignment to a variable defined with `let` is a **compile error**.
- Scope is block-based (`{}`).
- A second `let` with the same name **in the same block** is a **compile error**.
- **In an inner block**, the same name may be redefined (shadowing); the inner definition is not visible outside its block.
- A variable defined in an inner block goes out of scope when the block ends (the outer value is preserved).
- Use of an undefined variable is a compile error.

---

## 6. Expressions

### 6.1 Arithmetic

`+ - * / %` — in `int` operations **overflow is checked**: overflow stops the program with `exit 101` and `ARITHMETIC_OVERFLOW`. `/` and `%` stop with `ARITHMETIC_ZERO_DIV` on a zero divisor.

Overflow is not checked in `float` operations (IEEE-754 behavior).

### 6.2 String concatenation

`str + str` produces a new `str` (heap). `str + int` is **invalid**; `int_to_str` MUST be used.

### 6.3 Comparison and logic

`< <= > >= == !=` → `bool`. `and` / `or` short-circuit. `not` is unary.

### 6.4 Indexing

`dizi[i]`, `metin[i]` → element / single character `str`.

Bounds checking is **mandatory at runtime**: `i < 0` or `i >= len` → `exit 102`.

### 6.5 Function call

`ad(arg1, arg2)`. The number and types of arguments are checked at compile time.

### 6.6 Struct construction and field access

```axiom
struct Point { x: int, y: int }
let p = Point { x: 1, y: 2 }
let a = p.x
p.x = 3        # only if `let mut p`
```

All fields MUST be provided; a missing field is a compile error.

### 6.7 `match` expression

```axiom
let ad = match x {
    1 => "bir",
    _ => "diger"
}
```

Pattern kinds: literal (`1`, `"a"`, `true`), identifier (binding), wildcard `_`. Guards are supported: `n if n > 10 => ...`.

For a `bool` and `int` to be exhaustive, a wildcard or all cases are required; a missing pattern is a compile error.

### 6.8 `?` operator

`<expression>?` — `<expression>` MUST be Result-like (§9).

---

## 7. Statements

### 7.1 `if` / `else`

```axiom
if kosul {
    ...
} else if diger {
    ...
} else {
    ...
}
```

The condition MUST be `bool`.

### 7.2 `while`

```axiom
while kosul {
    ...
}
```

Optional `invariant <expression>` (for the prover).

### 7.3 `for`

```axiom
for i in 0..10 { ... }     # 0,1,...,9  (upper bound exclusive)
```

The loop variable is `int` and cannot be modified inside the body. Optional `invariant`.

### 7.4 `break` / `continue`

Only inside a loop; outside a loop it is a compile error. Both release the `defer`s and owned resources of the innermost block that is open at that moment.

### 7.5 `return`

`return` or `return <expression>;`. If the return type is not `void`, a `return` MUST be present **on all code paths** (definite return analysis); if missing, it is a compile error.

### 7.6 `defer`

```axiom
fn main() -> int {
    defer { print("temizlik") }
    print("govde")
    return 0
}
```

- Runs in **LIFO** (last in, first out) order on scope exit.
- Also runs on early `return`, `break`, `continue`, and early return via `?`.
- The expression inside `defer` sees the values **at the moment it executes**, not the variable values at the moment it was registered.

### 7.7 `print`

`print(a, b, c)` — writes its arguments separated by a single space and appends a newline at the end. Types are formatted automatically (`int`, `float`, `bool`, `str`).

### 7.8 `verify`

`verify <condition>, "<message>"` — the condition is `bool`. If it can be proven at compile time, the prover rejects it; otherwise, `exit 101` at runtime.

---

## 8. Functions and contracts

### 8.1 Declaration

```axiom
fn ad(p1: Tip1, p2: Tip2) -> DonusTipi
    requires <bool ifade>
    ensures <bool ifade>          # the 'return' symbol may be used
{
    ...
}
```

### 8.2 Contracts

| Contract | When | Violation behavior |
|---|---|---|
| `requires` | On function entry | `exit 101`, `REQUIRES` |
| `ensures` | On every `return` path | `exit 101`, `ENSURES` |
| `verify` | As a statement | `exit 101`, `VERIFY` |

Inside `ensures`, the `return` symbol represents the returned value.

**Contracts are for programming errors.** *Expected* conditions such as user input or a missing file MUST be handled with `Result` (§9).

### 8.3 Overloading

The same name may be defined more than once with different parameter types. Resolution is performed according to argument types. The same signature cannot be defined twice.

### 8.4 Generic functions

```axiom
fn wrap<T>(x: T) -> Box<T> { return Box<T> { val: x } }
```

Type parameters are specified explicitly at the call site (`wrap<int>(42)`) or determined by inference from the arguments.

---

## 9. Error model

### 9.1 `Result<T, E>`

```axiom
struct Result<T, E> {
    is_ok: bool,
    value: T,
    error: E
}
```

The `?` operator works **structurally**: **every** struct with the fields `is_ok: bool`, `value`, and `error` counts as a Result. The user may define their own error type.

### 9.2 `?` operator rules

1. The expression MUST be Result-like; otherwise it is a compile error.
2. It may only be used inside the body of a function that returns a Result.
3. The error type (`E`) of the expression and the error type in the function's return MUST be **the same**.
4. If `Ok`, `value` is produced and flow continues.
5. If `Err`: the `defer`s open up to that point run in LIFO order, owned resources are released, and the error is returned to the calling function.

### 9.3 `main` and `Result`

```axiom
fn main() -> Result<int, str> { ... }
```

| Return | Behavior |
|---|---|
| `Ok` | `exit 0` |
| `Err(msg)` | `msg` → `stderr` (`[AXIOM HATA] ...`), `exit 1` |

If `fn main() -> int` is used, the return value is the exit code.

### 9.4 Two-tier summary

| Situation | Mechanism | Result |
|---|---|---|
| Expected error (file missing, port closed, parse error) | `Result` + `?` | Flows on; the caller decides |
| Programming error (invalid constant, wrong logic) | `requires` / `ensures` / `verify` | `exit 101` |
| Array bounds | Runtime check | `exit 102` |
| Integer overflow / division by zero | Runtime protection | `exit 101` |

---

## 10. Memory model

### 10.1 Value semantics

- Primitives (`int`, `float`, `bool`) and `str` (pointer) are copied.
- **Arrays are value types:** `let b = a` produces a **deep copy**. Modifying `b` does not affect `a`.
- Structs are value types.

### 10.2 String ownership

In Axiom, `str` is a pointer; strings allocated on the heap are tracked at runtime by **reference counting**.

- Runtime functions that return `str` record the result in the ownership table.
- On scope exit, temporary strings produced along `let`/assignment/`return` paths are released.
- Strings that "escape" into a struct field, an array, or a call argument are not released at the end of the scope (escape analysis).
- Literals and external pointers such as `os_getenv` are non-owned; freeing them is a no-op.

**Known limitation (v0.5):** temporary strings produced in expressions that are not assigned (`print(f(x))`) are not released at the end of the expression. In hot loops, assign the result to a variable.

### 10.3 Explicit free

`str_free(s)` frees a string immediately and `NULL`s the pointer (double free is safe).

### 10.4 `defer` and resource cleanup

`defer` runs on scope exit; it is the primary tool for owned resources.

---

## 11. Modules

```axiom
import "std:io:file"
import "std/io/file"
import "std/io/file.ax"
import "utils.ax"          # relative file
```

- The `std:` / `std/` prefix resolves the standard library.
- Relative paths are resolved relative to the importing file.
- A **cyclic dependency** is a compile error.
- A **diamond dependency** (the same file reached via two paths) is included once.
- There are no namespaces; all symbols are in a single flat plane.

### 11.1 Offensive module isolation

The following modules are **rejected** in the default compilation:

`std/security/shellcode.ax`, `std/security/evasion.ax`, `std/security/memdump.ax`,
`std/net/c2.ax`, `std/net/packet_crafter.ax`

They can only be compiled with the `--features offensive` flag or the `AXIOM_FEATURES=offensive` environment variable.

---

## 12. Concurrency

| Function | Signature | Note |
|---|---|---|
| `thread_create` | `(fn, arg: int) -> int` | The thread argument is **only `int`** |
| `thread_join` | `(id: int) -> int` | The thread's return value |
| `mutex_init` | `() -> int` | |
| `mutex_lock` / `mutex_unlock` | `(id: int) -> void` | |
| `atomic_init` / `atomic_add` / `atomic_get` | `(int) -> int` | |
| `sleep_ms` | `(ms: int) -> void` | |

Only `int` can be passed to a thread; for complex data, use the global/handle approach. There is **no** data-race checking; synchronization is the programmer's responsibility.

---

## 13. Built-in function catalog

A total of **86** user-facing built-ins (excluding internal `rt_*` aliases).

### 13.1 String

| Function | Signature | Description |
|---|---|---|
| `str_len` | `(str) -> int` | UTF-8 character count |
| `str_byte_len` | `(str) -> int` | Byte count |
| `str_char_at` | `(str, int) -> str` | Single character |
| `str_char_code` | `(str, int) -> int` | Code point |
| `char_to_str` | `(int) -> str` | Text from a code point |
| `str_sub` | `(str, int, int) -> str` | Substring (start, length) |
| `str_index_of` | `(str, str) -> int` | First position, `-1` if absent |
| `str_contains` | `(str, str) -> bool` | |
| `str_starts_with` | `(str, str) -> bool` | |
| `str_ends_with` | `(str, str) -> bool` | |
| `str_trim` | `(str) -> str` | Leading/trailing whitespace |
| `str_replace` | `(str, str, str) -> str` | Replace all |
| `str_split` | `(str, str) -> str[]` | Split on the delimiter |
| `str_join` | `(str[], str) -> str` | Join with the delimiter |
| `str_to_int` | `(str) -> int` | `0` if invalid |
| `int_to_str` | `(int) -> str` | |
| `str_free` | `(str) -> void` | Free immediately |
| `str_owned_count` | `() -> int` | **Diagnostic:** number of tracked strings |

### 13.2 Math

`math_abs(int)->int`, `math_min(int,int)->int`, `math_max(int,int)->int`, `math_pow(int,int)->int`

### 13.3 File and operating system

| Function | Signature | Error behavior |
|---|---|---|
| `file_read` | `(str) -> str` | `""` |
| `file_write` | `(str, str) -> bool` | `false` |
| `file_exists` | `(str) -> bool` | — |
| `os_getenv` | `(str) -> str` | `""` |
| `os_exec` | `(str) -> int` | Via the shell |
| `os_exec_argv` | `(str[]) -> int` | No shell (injection-safe) |
| `time_now_ms` | `() -> int` | — |

### 13.4 Network

`tcp_connect(str,int)->int`, `tcp_send(int,str)->int`, `tcp_recv(int,int)->str`, `socket_close(int)->void`

### 13.5 Array and SIMD

| Function | Signature |
|---|---|
| `array_push_int` / `array_push_str` | `(T[], T) -> T[]` |
| `simd_add_i64` / `sub` / `mul` | `(int[], int[]) -> int[]` |
| `simd_sum_i64` | `(int[]) -> int` |
| `simd_scan_match` | `(int[], int) -> int` |

### 13.6 Tensor

`tensor_create_2d(int,int)->int`, `tensor_set(int,int,int,float)->void`, `tensor_get(int,int,int)->float`,
`tensor_rows/cols(int)->int`, `tensor_matmul/add/transpose(int,int)->int`, `tensor_to_str(int)->str`, `tensor_free(int)->void`,
`dot_product(int,int)->float`, `nn_relu(float)->float`, `nn_sigmoid(float)->float`, `nn_argmax(int)->int`

### 13.7 Security / system diagnostics

`exec_mem_run/alloc/protect`, `packet_craft_ip/tcp/udp`, `diag_is_debugged/is_virtualized/set_dumpable`,
`proc_search_pattern`, `proc_get_maps`, `pcap_*`, `fim_hash_file`, `forensics_get_ports/modules`,
`crypto_memcmp`

> Most of these functions SHOULD be used through the corresponding `std/` module; direct calls are supported but portability is not guaranteed.

### 13.8 Module-level API

The `std/` modules additionally provide `Result`-based wrappers:
`std/io/file` (`read_file`, `write_file`, …), `std/encoding/json` (`json_get_*_result`),
`std/net/http` (`http_get_result`, `http_status`, `http_body`), `std/crypto/tls` (`https_get_result`),
`std/os/process` (`exec_output_result`).

---

## 14. Compilation pipeline

```
[ .ax source ]
      │
      ▼
  1. Lexer ──────► token stream
      │
      ▼
  2. Parser ─────► AST
      │
      ▼
  3. Resolver ───► module merging (cycle detection, diamond deduplication)
      │
      ▼
  4. Checker ────► types, scope, definite return, contracts, monomorphization
      │
      ▼
  5. Prover ─────► symbolic range analysis (default) / Z3 SMT (optional)
      │
      ├──► 6a. C99 codegen ──► clang ──► ELF
      └──► 6b. LLVM IR codegen ──► clang ──► ELF
```

`axiom check` runs 1–4 (+5 symbolic). `axiom build` runs all of them.

---

## 15. Runtime and ABI

### 15.1 Type mapping

| Axiom | C |
|---|---|
| `int` | `int64_t` |
| `float` | `double` |
| `bool` | `bool` |
| `str` | `const char*` |
| `T[]` | `struct { int64_t length; int64_t capacity; T* data; }` |

### 15.2 Struct return

Structs larger than 16 bytes are returned via **sret** (hidden pointer) per the SysV ABI. This MUST be implemented consistently in the C and LLVM backends.

### 15.3 Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | General error (`main` returned `Err`, CLI usage error) |
| `101` | Contract or arithmetic violation (`REQUIRES`/`ENSURES`/`VERIFY`/`ARITHMETIC_*`) |
| `102` | Array out of bounds |
| `127` | `exec` failed |

---

## 16. Defined and undefined behavior

### 16.1 Guaranteed

- `int` overflow → `exit 101` (no silent wrapping).
- Division/modulo by zero → `exit 101`.
- Array bounds → `exit 102`.
- Missing `return` → compile error.
- Type mismatch → compile error.
- Array assignment → deep copy.

### 16.2 Not guaranteed (undefined)

- `float` overflow/NaN behavior (left to IEEE-754).
- The result of a data race on concurrent access.
- Error codes of external C libraries (`file_read` cannot distinguish an error from `""`).
- Certificate verification when `AXIOM_TLS_INSECURE=1` is set.
- Passing data other than `int` to a thread.

---

## 17. Compatibility and versioning

- Version format: `MAJOR.MINOR.PATCH[-tag]`. During the alpha period, `0.x.y-alpha`.
- During the alpha period, **there is no backward compatibility commitment**.
- Every user-visible change is recorded in `CHANGELOG.md`.
- A change to the language surface increments the version of this specification.

---

## 18. Appendix: Syntax summary (EBNF-like)

```ebnf
program        = { declaration } ;
declaration    = struct_decl | function_decl | import_stmt | statement ;

import_stmt    = "import" STRING [ ";" ] ;
struct_decl    = "struct" IDENT [ "<" type_params ">" ] "{"
                     { IDENT ":" type [ "," ] }
                 "}" ;
function_decl  = "fn" IDENT [ "<" type_params ">" ] "(" [ params ] ")"
                 [ "->" type ] { contract } block ;
params         = param { "," param } ;
param          = IDENT ":" type ;
type_params    = IDENT { "," IDENT } ;
contract       = "requires" expr | "ensures" expr ;

type           = base_type { "[]" } ;
base_type      = "int" | "float" | "bool" | "str" | "void"
               | IDENT [ "<" type { "," type } ">" ] ;

block          = "{" { statement } "}" ;
statement      = let_decl | assign | if_stmt | while_stmt | for_stmt
               | return_stmt | break_stmt | continue_stmt | defer_stmt
               | print_stmt | verify_stmt | match_stmt | expr_stmt ;

let_decl       = "let" [ "mut" ] IDENT [ ":" type ] "=" expr ;
assign         = lvalue "=" expr ;
if_stmt        = "if" expr block [ "else" ( if_stmt | block ) ] ;
while_stmt     = "while" expr [ "invariant" expr ] block ;
for_stmt       = "for" IDENT "in" expr ".." expr [ "invariant" expr ] block ;
return_stmt    = "return" [ expr ] ;
break_stmt     = "break" ;
continue_stmt  = "continue" ;
defer_stmt     = "defer" ( block | statement ) ;
print_stmt     = "print" "(" [ expr { "," expr } ] ")" ;
verify_stmt    = "verify" expr [ "," STRING ] ;
match_stmt     = "match" expr "{" { match_arm } "}" ;

expr           = or_expr ;
or_expr        = and_expr { "or" and_expr } ;
and_expr       = cmp_expr { "and" cmp_expr } ;
cmp_expr       = add_expr { ( "<" | "<=" | ">" | ">=" | "==" | "!=" ) add_expr } ;
add_expr       = mul_expr { ( "+" | "-" ) mul_expr } ;
mul_expr       = cast_expr { ( "*" | "/" | "%" ) cast_expr } ;
cast_expr      = unary { "as" base_type } ;
unary          = ( "-" | "+" | "not" ) unary | postfix ;
postfix        = primary { "." IDENT | "[" expr "]" | "?" } ;
primary        = INT | FLOAT | STRING | "true" | "false"
               | IDENT | call | struct_init | array_literal
               | "match" expr "{" { match_arm } "}"
               | "(" expr ")" ;

call           = IDENT [ "<" type { "," type } ">" ] "(" [ args ] ")" ;
args           = expr { "," expr } ;
struct_init    = IDENT [ "<" type { "," type } ">" ] "{"
                     { IDENT ":" expr [ "," ] }
                 "}" ;
array_literal  = "[" [ expr { "," expr } ] "]" ;
match_arm      = pattern [ "if" expr ] "=>" ( expr | block ) ;
pattern        = "_" | IDENT | INT | FLOAT | STRING | "true" | "false" ;
```

> Note: A `match` guard is written with the `if` keyword: `n if n > 10 => ...`.

---

## 19. Known limitations (v0.5)

1. **Temporary strings:** strings produced in expressions such as `print(f(x))` that are not assigned are not released.
2. **Cross-compilation:** `--target` requires an external sysroot/WASI SDK; it is experimental.
3. **Registry:** there is no central package repository; `install` fails explicitly on a registry dependency.
4. **Dynamic linking:** the produced ELF is dynamically linked to `glibc`, `libssl`, `libcrypto`, `libz`, `libpthread`.
5. **Self-hosted compiler:** `bin/axiomc` is not a full equivalent of the Python driver (no contract checking and no SMT).
6. **`enum`, `trait`, closures, `try/except`** do not exist in the language.
7. **`match` guard** syntax is `if`, not `when` (`n if n > 0 => ...`).
