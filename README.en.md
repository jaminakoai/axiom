# Axiom Programming Language (λx)

[![Axiom Version](https://img.shields.io/badge/Axiom-v0.5.0--alpha-blue.svg)](#)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/jaminakoai/axiom/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/jaminakoai/axiom/actions/workflows/ci.yml)
[![Tests (last full run)](https://img.shields.io/badge/tests%20(last%20full%20run)-1361-blue.svg)](#last-full-verified-run)
[![Benchmarks](https://img.shields.io/badge/Benchmarks-results-blue.svg)](benchmarks/RESULTS.md)
[![Target](https://img.shields.io/badge/Target-Native%20x86__64%20%7C%20ARM64-experimental-orange.svg)](#)

> About the badges: the **CI** badge is live from GitHub Actions (currently
> green). The **Tests** badge is static and shows only the **local** run
> documented below with its date, command and result; it is not a CI result —
> they are two separate pieces of evidence.

> **Axiom (λx): a contract-driven, natively compiled systems programming language.**
> Measured comparison (benchmarks in this repo, single machine): Axiom is
> **1.5–6.3×** slower than C `-O3` and **6.6–29.7×** faster than Python
> ([benchmarks/RESULTS.md](benchmarks/RESULTS.md)). Contract checking runs at
> compile time, but reports "could not prove" for functions with loops — it does
> not claim to catch every error.

> 🌍 **Türkçe:** [README.md](README.md)

---

## 🧭 What is Axiom?

**The language is the main product.** Axiom (λx) is a systems programming
language with contracts (`requires`/`ensures`/`verify`), a `Result<T,E>` + `?`
error model, no garbage collector, and **two backends** (C99 and LLVM) that
produce native binaries.

The security tools below are **not a separate product**: they are flagship
**applications written in the language** with its own standard library, showing
what the language can do on a real job. For the language itself see "Why Axiom?"
and "Architecture Overview"; the table below is enough to try the tools.

---

## 🔎 Tools written in this language: offline DFIR and security-evidence triage

The two tools below can already be used for **offline** security triage (no live
service or network required):

| Tool | Input | Analysis | Output |
|---|---|---|---|
| **`axiom-scan`** (`examples/21_axiom_scan.ax`) | A YARA-subset rule file + a file **or** a PCAP | text, hex wildcards/bounded jumps, bounded alternation/negation and regex; group and Boolean conditions | Schema-versioned JSON: `schema_version`, `tool_version`, `rules_count`, `target_sha256`, `scanned_bytes`, `match_count`, matches |
| **DFIR triage** (`examples/22_dfir_triage.ax`) | The running system (`/proc`) and an optional log file (`AXIOM_DFIR_LOG`) | process list, listening TCP ports, SHA-256 integrity of critical files, Sigma log scanning | A single JSON report: `processes`, `network`, `integrity`, `log`, `detections`, `risk` |

**What concrete job does it make easier?**

- Answers "does this file/PCAP contain a known pattern?" during incident
  response with **a single standalone binary** — no Python, venv or pip.
- The report carries the **SHA-256** of the scanned target, so "which bytes
  were scanned" can be tied into the chain of custody.
- With `--fail-on-match` it returns **exit 10** when there is a finding, so CI
  or shell scripts can gate on it (without the flag the behaviour is unchanged,
  exit 0).
- Errors are schema-shaped JSON too (`"ok":false`) with **exit 1**, so a
  consumer sees a single output format.

**Target users:** SOC/DFIR analysts, incident responders, malware-triage
security engineers, and teams collecting evidence in offline/air-gapped
environments — as well as systems programmers who want to write security tools
in their own language.

**Honest limits (v0.2):**

- `axiom-scan` is **not all of YARA**: subset patterns and conditions. It
  accepts `any/all/none/N of them` (`0 of them` is true only when no string
  matches), `any/all/none/N of ($a*)`
  and explicit pattern sets such as `any of ($a,$b)`, composable with boolean
  expressions, `$a` pattern references,
  `$a at N` / `$a in (N..M)` offset checks, `@a[i]` offsets, `!a[i]` match
  lengths, pattern-group `at N` / `in (N..M)` ranges, `#a` occurrence counts,
  and rule `meta:` string, boolean, integer values and tags in scan JSON reports,
  while `\xNN` escapes in metadata strings are explicitly rejected,
  `filesize` comparisons, `true`/`false`, parentheses, and `not`/`and`/`or`
  (`not` > `and` > `or` precedence). Offset bounds are decimal or `0x` hex
  integer literals.
  Text patterns support `nocase`, `ascii`, and `fullword` (`ascii` is the
  default). `wide` is explicitly rejected because the current text-reading
  path cannot represent target bytes containing NUL. Unknown conditions,
  other unsupported modifiers and unbounded/out-of-subset hex jumps are
  rejected with a parse error. Hex patterns support nibble
  wildcards, fixed `[N]` jumps (N=1..64), and one bounded `[N-M]` jump per
  pattern (`0<=N<=M<=64`, `M-N<=16`, with at least one byte on both sides).
  They also support one flat alternation group with 2–4 equal-length branches
  of 1–16 bytes; branches contain only byte/nibble-wildcard tokens. Fixed `[N]` jumps can be
  outside the group, but `[N-M]` cannot be combined with alternation. One
  `~HH`, `~?H`, or `~H?` negated byte per pattern is also supported and can be
  combined with fixed jumps, but not with `[N-M]` or alternation. `~??` and
  multiple negated bytes are rejected. Nested or multiple alternation groups
  are rejected. All-wildcard patterns are rejected and the
  encoded pattern is limited to 8 KiB. `#a`, `@a[i]`, and `!a[i]` support text
  and all supported hex patterns, including bounded jumps, alternation, and
  negation. Occurrence indexes are 1-based and offsets are 0-based. For a
  bounded jump with multiple valid lengths at one start, the shortest match is
  selected; alternation branches matching at the same start count as one
  occurrence. Regex counts, offsets, and index checks are rejected.
- Text patterns support `\\`, `\"`, `\n`, `\r`, `\t`, and `\xNN` escapes.
  `\x00` is rejected because Axiom represents strings as NUL-terminated text.
  `//` inside a pattern is preserved; `#` is not a YARA comment marker.
- `scan` is text-based: a file containing a NUL byte **is truncated at the
  first NUL**. `target_sha256` still covers the whole file; `scanned_bytes`
  shows only the readable prefix.
- PCAP packets are scanned individually; there is **no TCP reassembly**.
- The DFIR tool is Linux `/proc` based; no process/port collection on
  Windows/macOS. It is not a policy engine: it produces a risk score but does
  not change the exit code.
- These tools are not "production-proven"; they are alpha prototypes verified
  by tests and examples.

Detailed usage: [axiom-scan v0.2](#13-axiom-scan-v02--security-evidence-scanning)
and [DFIR triage](#12-dfir-triage-single-json-report-phase-1-closing-tool).

---

## ⚡ Why Axiom?

Today's languages sit at two extremes:
* **Python:** Incredibly ergonomic to learn and develop in; but slow at runtime, with huge memory consumption, and it only surfaces type/logic errors in production.
* **Rust:** Enormous memory safety and bare-metal speed; but the borrow checker rules, `'a` lifetime accounting, and long compile times impose a high cognitive load.

**Axiom sits between these two poles.** The items below are the *intended
design*; measurements and caveats are in "Claims and evidence" below:
1. **No borrow checker, but ownership still exists:** no lifetime/`'a`
   accounting; `defer`-based scope cleanup, refcount-based string ownership, and
   bounds-checked arrays. (This is not "zero cognitive load": string ownership
   and `let` scope rules still have to be learned.)
2. **Garbage-Collector-Free (Zero-GC):** No pauses. Predictable micro-second latency for real-time systems and security tooling.
3. **Contract-Driven Logic Safety:** With `requires`, `ensures`, and `verify` blocks, logic errors and bounds overflows are caught at compile time.
4. **`Result<T, E>` + `?` for Expected Errors:** *Expected* conditions such as a missing file, a closed port, or a network error flow through `Result`; the `?` operator propagates the error to the caller while `defer` cleanup runs. `main` can also return `Result<int, str>` (Err → stderr + exit 1). The stdlib's `Result` layer is ready: `std/io/file`, `std/encoding/json`, `std/net/http`, `std/crypto/tls`, `std/os/process`. Contract violations (`requires`/`ensures`/`verify`) are treated as *programming errors* and halt the program.
5. **Standalone ELF Binary:** No dependency hell like Python; a single command produces a standalone ELF binary (dynamically linked against the system OpenSSL and glibc libraries).

---

## 🚀 Quick Start

### Requirements
* Linux (x86_64 / ARM64)
* Python 3.10+ (for the Axiom bootstrap compiler)
* `clang` or `gcc` (for native binary compilation)

### Installation and CLI Access
```bash
cd /path/to/axiom
export PATH="$PWD/bin:$PATH"

# (Optional) Build the self-hosted compiler written in Axiom:
# no ELF binary is committed, so `bin/axiomc` is built locally.
axiom build compiler/main.ax -o bin/axiomc
```

### Interactive REPL (Interactive Shell)
```bash
axiom repl
```
```
Axiom (λx) v0.5.0-alpha - Interactive REPL
Type 'help' for help, 'exit' or 'quit' to quit.

axiom> let x = 40
axiom> x + 2
42
axiom> file_write("test.txt", "Axiom Native IO")
true
axiom> file_read("test.txt")
Axiom Native IO
axiom> quit
```

### 🎯 Roadmap

The single source of truth for the project: **[TODO.md](TODO.md)** — where we are, where we are going,
phase gates, the measurement board, and working rules for AI agents.

### 📘 Tutorial and Specification

- **[docs/en/TUTORIAL.md](docs/en/TUTORIAL.md)** — for beginners: installation,
  basic syntax, structs/arrays, contracts, the `Result` + `?` error model,
  stdlib, concurrency, tooling, common mistakes.
- **[docs/en/SPECIFICATION.md](docs/en/SPECIFICATION.md)** — the v0.5 language specification: lexical structure,
  types, expressions, error model, memory model, ABI, exit codes, EBNF summary.
- **[docs/reports/](docs/reports/README.md)** — reports for every development round
  (43 reports, chronological index; each lists the real bugs found and the exact
  verification commands).

Code blocks in both documents are compiled and verified in CI.

### Running Your First Axiom Program
```bash
axiom run examples/01_hello.ax
```

### Building a Standalone Native Binary
```bash
axiom build examples/01_hello.ax -o hello
./hello

# Cross-compilation (requires an external toolchain and sysroot / experimental):
axiom build examples/01_hello.ax --target aarch64-linux-gnu -o hello_arm
axiom build examples/01_hello.ax --target wasm32-wasi --sysroot /path/to/wasi-sysroot -o hello.wasm
```

---

## 📖 Code Examples

### 1. Hello World & Basic Logic
```axiom
# examples/01_hello.ax
fn main() -> int {
    let msg = "Welcome to the Axiom system!"
    print(msg)

    let mut sum: int = 0
    for i in 1..11 {
        sum = sum + i
    }

    print("Sum from 1 to 10:")
    print(sum)
    return 0
}
```

### 2. Security Contracts (Formal Verification)
```axiom
# examples/03_contracts.ax
fn port_scan(target_ip: str, port: int) -> bool
    requires port > 0 and port <= 65535      # Invalid ports are rejected at compile/run time
{
    print("Scanning target...")
    print(target_ip)
    print(port)
    return true
}

fn main() -> int {
    port_scan("192.168.1.1", 80)
    # port_scan("192.168.1.1", 70000)  <-- This line raises an error!
    return 0
}
```

### 3. Data Structures (Struct), Dynamic Arrays and Native POSIX Network Sockets
```axiom
# examples/05_real_scanner.ax
struct TargetHost {
    ip: str,
    port: int
}

fn scan_target(target: TargetHost) -> int {
    let fd = tcp_connect(target.ip, target.port)
    if fd >= 0 {
        print("[OPEN PORT FOUND]", target.ip, target.port)
        socket_close(fd)
        return 1
    }
    return 0
}

fn main() -> int {
    let ports = [22, 80, 443, 8080]
    let t_start = time_now_ms()

    for i in 0..len(ports) {
        let t = TargetHost { ip: "127.0.0.1", port: ports[i] }
        scan_target(t)
    }

    let elapsed = time_now_ms() - t_start
    print("Total scan time (ms):", elapsed)
    return 0
}
```

### 4. Multiple Modules, File I/O and System Calls
```axiom
# examples/06_modules/main.ax
import "utils.ax"

fn main() -> int {
    let report = create_report("System Configuration", 3)
    let ok = file_write("/tmp/log.txt", "Axiom v0.5.0-alpha I/O")
    if ok and file_exists("/tmp/log.txt") {
        let content = file_read("/tmp/log.txt")
        print("Read:", content)
    }
    let user = os_getenv("USER")
    print("User:", user)
    return 0
}
```

### 5. Standard Library (std:net/http.ax) & Security Banner Grabber
```axiom
# examples/07_http_banner_grabber.ax
import "std:net/http.ax"

struct BannerReport {
    target: str,
    port: int,
    is_http: bool,
    server_nginx: bool
}

fn scan_target(host: str, port: int) -> void {
    let response = http_get(host, port, "/")
    let is_nginx = str_contains(response, "nginx")
    print("Target:", host, "Is nginx:", is_nginx)
}
```

### 6. Multithreaded Concurrent Scanner & Static Proof Engine
```axiom
# examples/08_multithreaded_scanner.ax
fn worker(port: int) -> int
    requires port >= 1 and port <= 65535
{
    let fd = tcp_connect("127.0.0.1", port)
    if fd >= 0 { socket_close(fd); return 1; }
    return 0;
}

fn main() -> int {
    let t1 = thread_create(worker, 80)
    let t2 = thread_create(worker, 443)
    let r1 = thread_join(t1)
    let r2 = thread_join(t2)
    return 0
}
```

Running the mathematical proof engine:
```bash
axiom prove examples/08_multithreaded_scanner.ax
```

### 7. Heterogeneous SIMD Vector Acceleration and Z3 SMT Theorem Proving
```axiom
# examples/09_simd_vector_scan.ax
@simd
fn parallel_signature_score(weights: int[], base_risk: int[]) -> int
    requires len(weights) > 0 and len(base_risk) > 0
    ensures return >= 0
{
    let multiplied = simd_mul_i64(weights, base_risk)
    return simd_sum_i64(multiplied)
}
```

Full theorem proving with the Z3 SMT Solver and LLVM IR compilation:
```bash
# Formal theorem proving with the Z3 SMT engine:
axiom prove examples/09_simd_vector_scan.ax --smt

# Exporting in standard SMT-LIB2 format:
axiom emit-smt examples/09_simd_vector_scan.ax

# Generating LLVM IR directly and compiling with Clang:
axiom emit-llvm examples/09_simd_vector_scan.ax
axiom build examples/09_simd_vector_scan.ax --backend=llvm -o simd_scan
```

### 8. Red Team & Offensive Cybersecurity Suite (Phase 2)
```axiom
# examples/15_redteam_offensive_suite.ax
import "std/security/shellcode.ax"
import "std/net/packet_crafter.ax"
import "std/security/evasion.ax"
import "std/net/c2.ax"
import "std/security/memdump.ax"

// Anti-debugging, dynamic API hashing, in-memory shellcode execution, raw IP packet crafting
```

> **Note:** Offensive modules are rejected in the default build. Use `--features offensive` (or `AXIOM_FEATURES=offensive`) to compile them.

### 9. Blue Team & DFIR Defensive Security Suite (Phase 3)
```axiom
# examples/16_blueteam_defensive_suite.ax
import "std/security/yara.ax"
import "std/net/pcap.ax"
import "std/security/sigma.ax"
import "std/os/forensics.ax"
import "std/security/integrity.ax"

// Live PCAP capture, Sigma rule engine, YARA pattern scanning, FIM integrity checking
```

### 10. Artificial Intelligence (AI/ML) Tensor & Deep Learning Engine (Phase 4)
```axiom
# examples/17_ai_tensor_neural_net.ax
import "std/ai/tensor.ax"
import "std/ai/linalg.ax"
import "std/ai/autograd.ax"
import "std/ai/nn.ax"
import "std/ai/inference.ax"

// AVX2 SIMD GEMM matrix multiplication, ReLU & Sigmoid forward pass, Argmax classification, Autograd backpropagation
```

### 11. Modern Web Framework & WASM Target (Phase 5)
```axiom
# examples/18_web_api_framework.ax
import "std/web/router.ax"
import "std/web/app.ax"
import "std/web/template.ax"
import "std/target/wasm.ax"

// Radix pattern router, CORS & Auth Guard middleware, XSS-safe templating, WebAssembly binary module
```

### 12. DFIR Triage: Single JSON Report (Phase 1 closing tool)
```axiom
# examples/22_dfir_triage.ax
import "std/os/forensics"
import "std/security/integrity"
import "std/security/sigma"
import "std/encoding/json"

// /proc process list + listening ports + SHA-256 integrity + Sigma matches
// -> a single JSON report (with risk score and verdict)
```
```bash
axiom run examples/22_dfir_triage.ax
AXIOM_DFIR_LOG=/var/log/auth.log axiom run examples/22_dfir_triage.ax
```

### 13. `axiom-scan` v0.2 — Security-evidence scanning

```bash
# Build a single standalone binary (no runtime dependency)
axiom build examples/21_axiom_scan.ax -o axiom-scan

# Validate a rule file
./axiom-scan rules rules.yar

# Scan a file (JSON on stdout)
./axiom-scan scan sample.bin --rules rules.yar

# Exit 10 when there is a finding (CI gate); exit 0 when clean
./axiom-scan scan sample.bin --rules rules.yar --fail-on-match

# Scan a PCAP (each packet separately; no stream reassembly)
./axiom-scan pcap traffic.pcap --rules rules.yar --fail-on-match
```

Real output (finding present, no `--fail-on-match` → `exit 0`):

```json
{"schema_version":"1","tool":"axiom-scan","tool_version":"0.2.0","rules_count":1,
 "ok":true,"target":"dirty.txt",
 "target_sha256":"21f10114c2932724770202eff83c9109322c2d605efd0e9e6c2a157dd0866551",
 "scanned_bytes":18,"match_count":1,
 "matches":[{"rule":"R1","pattern":"$a","offset":5,"length":7}]}
```

Exit codes: `0` report produced (no finding, or flag not given) · `10`
`--fail-on-match` given and a finding exists · `1` error (file/rule/usage).

### 14. Error Model: `Result<T, E>` and the `?` Operator

```axiom
# examples/19_error_handling.ax
import "std/core/error"

fn parse_port(s: str) -> Result<int, str> {
    let v = str_to_int(s)
    if v <= 0 or v > 65535 {
        return result_err<int>("invalid port: " + s)
    }
    return result_ok<int>(v)
}

fn resolve_port(host: str, port_str: str) -> Result<int, str> {
    defer { print("[cleanup] resolve_port exit") }
    let port = parse_port(port_str)?      # On Err the error is propagated upward
    return result_ok<int>(port)
}

fn main() -> int {
    let r = resolve_port("127.0.0.1", "99999")
    print("ERROR:", r.error)
    print("FALLBACK:", result_unwrap_or<int>(r, -1))
    return 0
}
```

> `?` can only be used in functions returning `Result`; on early return,
> `defer` blocks and ownership cleanup run. Contract violations (`requires`,
> `ensures`, `verify`) do not go through this path — they are programming
> errors and halt the program.

---

## 📏 Claims and evidence

Not marketing copy — measurement and scope:

| Claim | Actual state | Evidence |
|---|---|---|
| "As fast as C/Rust" | **Overclaim.** Measured: 1.5–6.3× slower than C `-O3` | [benchmarks/RESULTS.md](benchmarks/RESULTS.md) |
| "Faster than Python" | Measured: 6.6–29.7× faster (5 selected workloads) | same file |
| "Garbage-collector free" | True: no GC at runtime; refcount overhead exists | `axiom/runtime.h`, P2-17b report |
| "Stops logic errors at compile time" | **Partial:** `requires`/`ensures`/`verify` are checked symbolically/Z3; loop-containing functions report "Unknown" instead of silently passing | `axiom check` output, `tests/test_prover*.py` |
| "Standalone binary" | Dynamic: glibc, libssl, libcrypto, libz, libpthread | `ldd`, README limits §2 |
| "As elegant as Python" | **Unmeasurable claim; removed.** Replaced by readable syntax + `docs/en/TUTORIAL.md` | — |

---

## 🛠️ Architecture Overview

The Axiom compiler consists of modular architectural components:

```
axiom/
├── lexer.py        # Tokenizer: clean blocks and syntax parsing (@simd support)
├── ast_nodes.py    # Abstract Syntax Tree (AST) node definitions
├── parser.py       # Recursive Descent Parser
├── resolver.py     # Dependency and stdlib import resolver ('std:...')
├── checker.py      # Type inference, scope and contract analysis
├── prover.py       # Symbolic execution and static mathematical proof engine ('axiom prove')
├── z3_prover.py    # Z3 SMT Solver theorem proving engine ('axiom prove --smt', 'emit-smt')
├── formatter.py    # Canonical source code formatter
├── codegen_c.py    # High-performance C99 / native code generator
├── codegen_llvm.py # Direct LLVM Intermediate Representation (.ll) code generator
├── runtime.h       # AVX2/SSE SIMD, POSIX pthread, OpenSSL 3 TLS/AES, tensor engine and network sockets
└── cli.py          # 'axiom' CLI driver (run, build, check, prove, emit-c, emit-smt, emit-llvm, doc, init, fmt, repl, test)
compiler/           # Self-Hosted Compiler written in Axiom (λx)
├── tokens.ax       # Token constants
├── lexer.ax        # Lexical analyzer
├── ast.ax          # AST definitions
├── parser.ax       # Syntax parser
├── codegen.ax      # Standalone C99 code generator
└── main.ax         # 'bin/axiomc' CLI binary (does not require Python!)
std/                # 52 Standard Library Modules / 385 functions
├── ai/             # tensor, linalg, autograd, nn, inference
├── web/            # router, app, template
├── target/         # wasm
├── security/       # shellcode, evasion, memdump, yara, sigma, integrity
├── net/            # packet_crafter, c2, pcap, http_server, tls, websocket, udp, dns
├── os/             # forensics, process
├── crypto/         # aes, jwt, hash
└── encoding/       # json, base64, hex, html, csv, zlib
```

---

## 📊 Comparison Table

| Feature | Python | Rust | Axiom (λx) |
| :--- | :---: | :---: | :---: |
| **Writing Speed & Ergonomics** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Raw Machine Speed** | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐☆ (1.5–6× slower than C; see benchmarks/RESULTS.md) |
| **No Garbage Collector (No GC)** | ❌ | ✅ | ✅ |
| **Borrow Checker Burden** | None | High | **None** (no lifetime accounting; ownership via refcount) |
| **Logic Verification (`requires`/`ensures`)** | ❌ | Partial/External | **Built-in** |
| **Distribution** | Cumbersome (venv/pip) | Static Binary | **Standalone ELF Binary (OpenSSL/glibc dynamically linked)** |

> The stars in this table are **not measurements** (except the speed row); the
> ergonomics score is subjective. The only measured comparison is in
> `benchmarks/RESULTS.md`.

---

## 🧪 Running the tests

```bash
# Requirements: python3 + pytest, clang/gcc
python3 -m pytest -q --no-header -p no:cacheprovider
```

Target a single area/file:

```bash
python3 -m pytest -q tests/test_axiom_scan.py -p no:cacheprovider
python3 -m pytest -q tests/test_self_hosted.py -p no:cacheprovider
```

Test-infrastructure notes:

- `subprocess` calls in tests get a default **900 s** timeout (configurable via
  `AXIOM_TEST_TIMEOUT`), so a stuck binary does not run for days.
- Windows-target tests really execute under `wine`; if wine is missing those
  tests are skipped for environment reasons. Wine prefixes are removed at the
  end of the session.

### Last full verified run

| Field | Value |
|---|---|
| Date | 13 November 2026 |
| Tested tree | `fbae263` plus the bounded-range performance fix |
| Command | `python -m pytest -q -rs` |
| Result | **1361 passed, 0 failed, 0 skipped** (1214.75 s) |
| Environment | Linux x86_64; clang, wine, z3, and local `bin/axiomc` |

This full local run includes the positional-evidence fix and the new `#/@/!`
support for bounded jumps, alternation, and negation, plus the bounded-range
near-match performance fix. The focused YARA/scanner suite passed 373 tests.
The latest completed GitHub Actions run was for `fbae263` (7/7); CI for this fix
will run after push.

### CI status

The badge is wired to the real workflow (`.github/workflows/ci.yml`, `master`).
All 7 jobs passed in the latest completed run for commit `fbae263`:

| Job | Status |
|---|---|
| Test (Python 3.10 / 3.11 / 3.12 / 3.13) | ✅ |
| ASan/UBSan + memory leaks | ✅ |
| LLVM backend + DWARF | ✅ |
| Formatting (`make fmt-check`) | ✅ |

Last verified run: `43456582647` (13 November 2026, `master`, SHA
`fbae26377819ae535524a969ec3d35f7322872a4`).

Six root causes fixed on the way here (details: report §9–§12):

| # | Root cause | Fix |
|---|---|---|
| 1 | `bin/axiomc` was built after the tests (13 tests) | CI runs `make bootstrap` before pytest |
| 2 | **LLVM `main() -> Result` bridge** emitted `call void @ax_main()` (2 tests) | Calls `Result` by value; Err → stderr + exit 1. **Real bug:** clang 21 silently dropped the Err and returned `exit 0` |
| 3 | Unicode test depended on the interpreter version (2 tests) | Version pinned via `PINNED_UCD_VERSION`; expected values in a golden file |
| 4 | `readelf` warnings returned `exit 1` (2 tests) | Content assertions + independent structural check via pyelftools |
| 5 | No `tomllib` on Python 3.10 → deps silently unresolved (1 test) | `parse_toml` (tomli fallback) + inline table support |
| 6 | **`gethostbyname` race** → intermittent SIGSEGV (1 test) | `axiom_internal_resolve_ipv4()` — `inet_pton`/`getaddrinfo`. Measured: old 18/25 segfault, new 0/25 |

**Note:** items 2, 5 and 6 were **product bugs**, not test issues. Wiring the
badge to the real workflow instead of a fake "success" is what surfaced them.
The cited 1034-test run matched CI at that time. The latest full local run is
1361 tests with the G1 occurrence and bounded-range performance changes. The
latest completed CI for baseline `fbae263` passed all 7 jobs.

---

## 🧭 Project status and roadmap

> This section is the **product view**; the technical source of truth is
> [TODO.md](TODO.md). Marks: ✅ done and test-verified · 🟡 partial · ⬜ not started.
> Percentages are estimates based on feature/test/documentation state, not an
> exact measurement.

### ✅ Done (test-verified)

- Compiler pipeline: lexer → parser → resolver → checker → prover → C99/LLVM codegen.
- Backend parity: `defer`, `?`, string/array scope cleanup, DWARF.
- `requires` / `ensures` / `verify` contracts and static proof with Z3 SMT.
- `Result<T,E>` + `?` error model; `main` as `int` or `Result<int,str>`.
- 21 example programs: C **21/21**, LLVM **21/21**, self-hosted `bin/axiomc`
  **21/21**, Windows target **21/21** under wine.
- 52 stdlib modules / 385 functions: security, networking, encoding, file, time, regex.
- `axiom-scan` v0.2: schema-versioned JSON, `target_sha256`, `--fail-on-match`.
- DFIR triage tool (`examples/22_dfir_triage.ax`): processes/ports/integrity/Sigma → one JSON.
- HTTP client, real JSON parser, YARA/Sigma engines, PCAP reader.
- Package manager + registry v1 (ed25519 signatures, semver, transitive, yanked).
- LSP (10 methods), `axiom doc`, TR+EN tutorial and specification, 43 development reports.
- Linux and Windows targets; NFC/NFD normalization; epoll event loop.

### 🟡 In progress / partial

- **CI:** green (7/7 jobs); six root causes fixed, three of them real product
  bugs (LLVM `main()` bridge, Python 3.10 TOML resolution, `gethostbyname`
  race). Details in "CI status" above.
- **Windows:** cross-compilation + execution under `wine` verified; no CI run on
  a real Windows machine.
- **macOS:** no runner/verification.
- **WASI:** does not build without `--sysroot`; WASM encoder is experimental.
- **Static linking:** binaries link dynamically to glibc/OpenSSL/zlib; no full
  static musl support.
- **Registry:** infrastructure ready, zero published packages.
- **Time zones:** fixed offset; no IANA/DST database.
- **Unicode:** NFC/NFD present; NFKC/NFKD absent.
- **Regex:** POSIX ERE + ReDoS step budget; no PCRE2/RE2.
- **YARA:** subset only, not full YARA. No PCAP stream reassembly.

### ⬜ Planned

- `v1.0` API stability and a two-release backward-compatibility promise.
- Real Windows and macOS CI runners; end-to-end WASI tests with a sysroot.
- Static (musl) binary production.
- Published package ecosystem (target: 200+ packages) and a first enterprise user.
- An IEC 62304 / ISO 26262 audit evidence pack from `axiom prove` output.
- For the DFIR tool: Windows/macOS collection, PCAP stream reassembly, signed reports.

**How this section is updated:** when an item becomes `[x]` in `TODO.md` and its
acceptance criteria have been executed and the full test suite is still green,
the line moves to ✅; the same change updates `CHANGELOG.md` and the test count
in the README. Nothing becomes ✅ without code + test evidence; estimates stay
under "planned".

---

## 🤝 Contributing

Contribution rules live in [CONTRIBUTING.md](CONTRIBUTING.md). In short: small,
reversible changes; test first; report real output; parity tests for both
backends. For security reports see [SECURITY.md](SECURITY.md).

---

## 📌 Project Status and Known Limitations

> **Current Version:** `v0.5.0-alpha` (Development / Research Prototype)
> Axiom is an experimental systems programming language under active development and research.

### Known Limitations and Technical Scope:
1. **Cross-Compilation and WASM Targets:** Targets such as `--target wasm32-wasi` and `--target aarch64-linux-gnu` require an external sysroot and cross-compilation toolchain (e.g. WASI SDK, gcc-aarch64). When no sysroot is installed on the system, the compiler halts safely with a clear and actionable error message; these targets are experimental.
2. **Dynamic System Library Dependencies:** While the produced ELF binaries are standalone executables, they dynamically link against the host system's `glibc`, `libssl`, `libcrypto`, `libz`, and `libpthread` libraries (full static musl support is on the roadmap).
3. **Self-Hosted Compiler Status:** `bin/axiomc` (`compiler/main.ax`) is a compiler written in Axiom and **compiles all 21/21 examples**, producing the same output as the Python driver (`tests/test_self_hosted.py`). It is still an alpha prototype: for diagnostics and full contract/Z3 verification the Python bootstrap driver (`bin/axiom`) is recommended.
4. **Package Manager (`axpm`):** Supports the `init/add/install/update/verify/tree/search/remove/build/run/test` commands. Local (`--path`) and Git (`--git`, `--rev`) dependencies are actually cloned and locked with content-based SHA-256; `axpm verify` detects tampering. Registry v1 is implemented: content-addressed store, ed25519 signatures, semver, transitive resolution, yanked versions, and path-traversal protection (see [docs/REGISTRY.md](docs/REGISTRY.md)). Unsigned packages are rejected by default; namespace packages (`@scope/name`) are supported.
5. **Memory Model:** Strings are tracked with a refcount-based ownership table. Nested temporary strings are released at the end of the expression along `let`/assignment/`return` paths **and** for `print(f(x))` and discarded expression statements; `continue`/`break` also clean up the scopes owned by the loop body. Producers such as `file_read`, `str_split`, `str_replace`, `str_sub`, `str_trim`, base64/hex/hash, and `array_push` results are cleaned up on scope exit. The number of tracked strings is observable via `str_owned_count()` (C backend).
6. **LLVM Backend:** All 21 example programs compile with `--backend=llvm` (the offensive `15_redteam_offensive_suite.ax` requires `--features offensive`). `defer`, `?`, and **string scope cleanup** are also supported in LLVM (loop bodies, if/else branches, early returns; escape analysis preserves struct fields/call arguments). With `-g`, DWARF metadata (`DICompileUnit`, `DISubprogram`, `DILocation`, `DILocalVariable`) is emitted into LLVM IR; the produced binary contains source lines via `readelf --debug-dump=line` and local variables (`DW_TAG_variable`) via `--debug-dump=info`.
7. **Offensive Security Modules:** The `shellcode`, `c2`, `evasion`, `memdump`, and `packet_crafter` modules are rejected by default; they can only be compiled with `--features offensive` (or `AXIOM_FEATURES=offensive`).


---

## 📄 License
This project is protected by the MIT license.
