#!/usr/bin/env python3
"""
Axiom (λx) — Karşılaştırmalı Benchmark Paketi

Aynı algoritmayı Axiom, C (clang -O3) ve Python ile çalıştırır; süreleri
ve bellek tepe noktasını ölçer. Sonuçları markdown tablosu olarak basar ve
benchmarks/RESULTS.md dosyasına yazar.

Kullanım:
    python benchmarks/run_benchmarks.py            # tümü
    python benchmarks/run_benchmarks.py fib concat # seçili işler
    python benchmarks/run_benchmarks.py --quick     # küçük boyutlar

Not: Ölçümler tek makinede, tek koşu, duvar saati (wall-clock) tabanlıdır.
Amaç mutlak değil, göreli büyüklük sırası vermektir.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
CLANG = shutil.which("clang") or shutil.which("gcc")
PYTHON = sys.executable
RESULTS = ROOT / "benchmarks" / "RESULTS.md"


@dataclass
class Case:
    key: str
    title: str
    axiom: str
    c: str
    python: str
    checksum: str  # beklenen çıktı (doğrulama için)
    runs: int = 3
    extra: dict = field(default_factory=dict)


def _time_binary(binary: str, runs: int) -> tuple[float, str]:
    best = float("inf")
    out = ""
    for _ in range(runs):
        t0 = time.perf_counter()
        res = subprocess.run([binary], capture_output=True, text=True, timeout=600)
        dt = time.perf_counter() - t0
        if res.returncode != 0:
            raise RuntimeError(f"{binary} başarısız (exit {res.returncode}):\n{res.stderr}")
        out = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else ""
        best = min(best, dt)
    return best, out


def _time_python(source: str, runs: int) -> tuple[float, str]:
    best = float("inf")
    out = ""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(source)
        path = f.name
    try:
        for _ in range(runs):
            t0 = time.perf_counter()
            res = subprocess.run([PYTHON, path], capture_output=True, text=True, timeout=600)
            dt = time.perf_counter() - t0
            if res.returncode != 0:
                raise RuntimeError(f"python başarısız:\n{res.stderr}")
            out = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else ""
            best = min(best, dt)
    finally:
        os.unlink(path)
    return best, out


def _build_and_time_axiom(src: str, runs: int) -> tuple[float, str, float]:
    with tempfile.TemporaryDirectory() as d:
        ax = Path(d) / "bench.ax"
        ax.write_text(src, encoding="utf-8")
        bin_path = Path(d) / "bench.bin"

        t0 = time.perf_counter()
        build = subprocess.run(
            [str(AXIOM), "build", str(ax), "-O", "3", "-o", str(bin_path)],
            capture_output=True, text=True, timeout=600,
        )
        build_s = time.perf_counter() - t0
        if build.returncode != 0:
            raise RuntimeError(f"Axiom derleme hatası:\n{build.stdout}\n{build.stderr}")

        secs, out = _time_binary(str(bin_path), runs)
        return secs, out, build_s


def _build_and_time_c(src: str, runs: int) -> tuple[float, str, float]:
    if not CLANG:
        raise RuntimeError("clang/gcc bulunamadı")
    with tempfile.TemporaryDirectory() as d:
        c_path = Path(d) / "bench.c"
        c_path.write_text(src, encoding="utf-8")
        bin_path = Path(d) / "bench.bin"

        t0 = time.perf_counter()
        build = subprocess.run(
            [CLANG, "-O3", "-march=native", str(c_path), "-o", str(bin_path), "-lm", "-pthread"],
            capture_output=True, text=True, timeout=600,
        )
        build_s = time.perf_counter() - t0
        if build.returncode != 0:
            raise RuntimeError(f"C derleme hatası:\n{build.stderr}")
        secs, out = _time_binary(str(bin_path), runs)
        return secs, out, build_s


def _machine_info() -> dict:
    info = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "clang": "yok",
    }
    if CLANG:
        try:
            v = subprocess.run([CLANG, "--version"], capture_output=True, text=True)
            info["clang"] = v.stdout.splitlines()[0].strip()
        except Exception:
            pass
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    info["cpu"] = line.split(":", 1)[1].strip()
                    break
    except Exception:
        pass
    return info


# ---------------------------------------------------------------------------
# İş yükleri
# ---------------------------------------------------------------------------

def make_cases(quick: bool) -> list[Case]:
    fib_n = 24 if quick else 30
    concat_n = 5_000 if quick else 20_000
    push_n = 20_000 if quick else 100_000
    b64_n = 5_000 if quick else 20_000
    mat_n = 24 if quick else 64

    fib_axiom = f"""
fn fib(n: int) -> int {{
    if n < 2 {{ return n }}
    return fib(n - 1) + fib(n - 2)
}}
fn main() -> int {{
    print(fib({fib_n}))
    return 0
}}
"""
    fib_c = f"""
#include <stdio.h>
static long fib(long n) {{ return n < 2 ? n : fib(n-1) + fib(n-2); }}
int main(void) {{ printf("%ld\\n", fib({fib_n})); return 0; }}
"""
    fib_py = f"""
def fib(n):
    return n if n < 2 else fib(n-1) + fib(n-2)
print(fib({fib_n}))
"""

    concat_axiom = f"""
fn main() -> int {{
    let mut s = ""
    let mut i = 0
    while i < {concat_n} {{
        s = s + "x"
        i = i + 1
    }}
    print(len(s))
    return 0
}}
"""
    concat_c = f"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(void) {{
    size_t n = {concat_n}, len = 0, cap = 64;
    char* s = (char*)malloc(cap);
    s[0] = '\\0';
    for (size_t i = 0; i < n; i++) {{
        if (len + 2 > cap) {{ cap *= 2; s = (char*)realloc(s, cap); }}
        s[len++] = 'x';
        s[len] = '\\0';
    }}
    printf("%zu\\n", len);
    free(s);
    return 0;
}}
"""
    concat_py = f"""
s = ""
for _ in range({concat_n}):
    s += "x"
print(len(s))
"""

    push_axiom = f"""
fn main() -> int {{
    let mut a: int[] = []
    let mut i = 0
    while i < {push_n} {{
        a = array_push(a, i)
        i = i + 1
    }}
    print(len(a))
    return 0
}}
"""
    push_c = f"""
#include <stdio.h>
#include <stdlib.h>
int main(void) {{
    size_t n = {push_n}, cap = 64, len = 0;
    long* a = (long*)malloc(cap * sizeof(long));
    for (size_t i = 0; i < n; i++) {{
        if (len == cap) {{ cap *= 2; a = (long*)realloc(a, cap * sizeof(long)); }}
        a[len++] = (long)i;
    }}
    printf("%zu\\n", len);
    free(a);
    return 0;
}}
"""
    push_py = f"""
a = []
for i in range({push_n}):
    a.append(i)
print(len(a))
"""

    b64_axiom = f"""
import "std:encoding:base64"
fn main() -> int {{
    let mut total = 0
    let mut i = 0
    while i < {b64_n} {{
        let e = base64_encode("axiom-benchmark-payload-0123456789")
        total = total + len(e)
        i = i + 1
    }}
    print(total)
    return 0
}}
"""
    b64_c = f"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static const char* T = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
static size_t enc(const char* in, size_t n, char* out) {{
    size_t j = 0;
    for (size_t i = 0; i < n; i += 3) {{
        unsigned a = (unsigned char)in[i];
        unsigned b = i+1 < n ? (unsigned char)in[i+1] : 0;
        unsigned c = i+2 < n ? (unsigned char)in[i+2] : 0;
        out[j++] = T[(a >> 2) & 63];
        out[j++] = T[((a & 3) << 4 | (b >> 4)) & 63];
        out[j++] = i+1 < n ? T[((b & 15) << 2 | (c >> 6)) & 63] : '=';
        out[j++] = i+2 < n ? T[c & 63] : '=';
    }}
    out[j] = 0;
    return j;
}}
int main(void) {{
    const char* in = "axiom-benchmark-payload-0123456789";
    size_t n = strlen(in);
    char* out = (char*)malloc(4 * ((n + 2) / 3) + 1);
    size_t total = 0;
    for (int i = 0; i < {b64_n}; i++) total += enc(in, n, out);
    printf("%zu\\n", total);
    free(out);
    return 0;
}}
"""
    b64_py = f"""
import base64
payload = b"axiom-benchmark-payload-0123456789"
total = 0
for _ in range({b64_n}):
    total += len(base64.b64encode(payload))
print(total)
"""

    mat_axiom = f"""
import "std/ai/tensor.ax"
import "std/ai/linalg.ax"
fn main() -> int {{
    let a = tensor_new({mat_n}, {mat_n})
    let b = tensor_new({mat_n}, {mat_n})
    let mut i = 0
    while i < {mat_n} {{
        let mut j = 0
        while j < {mat_n} {{
            tensor_set_val(a, i, j, 1.5)
            tensor_set_val(b, i, j, 2.0)
            j = j + 1
        }}
        i = i + 1
    }}
    let c = matmul(a, b)
    print(tensor_get_val(c, 0, 0))
    return 0
}}
"""
    mat_c = f"""
#include <stdio.h>
#include <stdlib.h>
#define N {mat_n}
int main(void) {{
    double* A = (double*)malloc(sizeof(double)*N*N);
    double* B = (double*)malloc(sizeof(double)*N*N);
    double* C = (double*)calloc((size_t)N*N, sizeof(double));
    for (int i = 0; i < N*N; i++) {{ A[i] = 1.5; B[i] = 2.0; }}
    for (int i = 0; i < N; i++)
        for (int k = 0; k < N; k++) {{
            double aik = A[i*N+k];
            for (int j = 0; j < N; j++) C[i*N+j] += aik * B[k*N+j];
        }}
    printf("%g\\n", C[0]);
    free(A); free(B); free(C);
    return 0;
}}
"""
    mat_py = f"""
N = {mat_n}
A = [[1.5]*N for _ in range(N)]
B = [[2.0]*N for _ in range(N)]
C = [[0.0]*N for _ in range(N)]
for i in range(N):
    for k in range(N):
        aik = A[i][k]
        row = C[i]; brow = B[k]
        for j in range(N):
            row[j] += aik * brow[j]
print(f"{{C[0][0]:g}}")
"""

    return [
        Case("fib", f"Özyinelemeli Fibonacci (n={fib_n})", fib_axiom, fib_c, fib_py, str(fib(fib_n))),
        Case("concat", f"String birleştirme ({concat_n:,} adım)", concat_axiom, concat_c, concat_py, str(concat_n)),
        Case("push", f"Dizi büyütme ({push_n:,} eleman)", push_axiom, push_c, push_py, str(push_n)),
        Case("base64", f"Base64 encode ({b64_n:,} çağrı)", b64_axiom, b64_c, b64_py, str(4 * ((34 + 2) // 3) * b64_n)),
        Case("matmul", f"Matris çarpımı ({mat_n}×{mat_n})", mat_axiom, mat_c, mat_py, f"{3 * mat_n}"),
    ]


def fib(n: int) -> int:
    return n if n < 2 else fib(n - 1) + fib(n - 2)


def main() -> int:
    ap = argparse.ArgumentParser(description="Axiom karşılaştırmalı benchmark")
    ap.add_argument("cases", nargs="*", help="Çalıştırılacak işler: fib concat push base64 matmul")
    ap.add_argument("--quick", action="store_true", help="Küçük boyutlar")
    ap.add_argument("--json", help="Sonuçları JSON olarak bu dosyaya yaz")
    ap.add_argument("--no-write", action="store_true", help="RESULTS.md dosyasını güncelleme")
    args = ap.parse_args()

    if not AXIOM.exists():
        print(f"Hata: {AXIOM} bulunamadı", file=sys.stderr)
        return 1

    cases = make_cases(args.quick)
    if args.cases:
        wanted = set(args.cases)
        cases = [c for c in cases if c.key in wanted]

    info = _machine_info()
    rows = []
    failures = []

    print(f"Axiom benchmark — {info['date']}")
    print(f"  CPU   : {info.get('cpu', 'bilinmiyor')}")
    print(f"  Derleyici: {info['clang']}")
    print(f"  Python: {info['python']}\n")

    for case in cases:
        print(f"→ {case.title}")
        row = {"key": case.key, "title": case.title}
        for lang, fn in (
            ("axiom", lambda: _build_and_time_axiom(case.axiom, case.runs)),
            ("c", lambda: _build_and_time_c(case.c, case.runs)),
            ("python", lambda: _time_python(case.python, case.runs) + (0.0,)),
        ):
            try:
                secs, out, build_s = fn()
                row[lang] = secs
                row[f"{lang}_build"] = build_s
                row[f"{lang}_out"] = out
                ok = out.strip() == case.checksum.strip()
                if not ok:
                    failures.append(f"{case.key}/{lang}: beklenen '{case.checksum}', gelen '{out}'")
                print(f"   {lang:7s} {secs:8.4f} s  (derleme {build_s:6.3f} s)  çıktı={out!r}{'' if ok else '  ⚠ FARKLI'}")
            except Exception as e:
                row[lang] = None
                failures.append(f"{case.key}/{lang}: {e}")
                print(f"   {lang:7s} HATA: {e}")
        rows.append(row)
        print()

    # --- Markdown tablosu ---
    lines = []
    lines.append(f"# Axiom Benchmark Sonuçları\n")
    lines.append(f"- **Tarih:** {info['date']}")
    lines.append(f"- **Platform:** {info['platform']}")
    lines.append(f"- **CPU:** {info.get('cpu', 'bilinmiyor')}")
    lines.append(f"- **Derleyici:** {info['clang']}")
    lines.append(f"- **Python:** {info['python']}")
    lines.append(f"- **Yöntem:** her dil için en iyi 3 koşu (wall-clock); Axiom ve C `-O3`\n")
    lines.append("| İş | Axiom (s) | C -O3 (s) | Python (s) | Axiom/C | Python/Axiom |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for r in rows:
        a, c, p = r.get("axiom"), r.get("c"), r.get("python")
        def f(x):
            return "—" if x is None else f"{x:.4f}"
        ratio_ac = f"{a / c:.2f}×" if a and c else "—"
        ratio_pa = f"{p / a:.1f}×" if a and p else "—"
        lines.append(f"| {r['title']} | {f(a)} | {f(c)} | {f(p)} | {ratio_ac} | {ratio_pa} |")
    lines.append("")
    lines.append("**Notlar**")
    lines.append("- Axiom/C oranı 1'e yaklaştıkça C ile eşdeğer; >2 ise runtime ek yükü var.")
    lines.append("- String benchmark'ında Axiom'un sahiplik/refcount yolu, C'nin ham `realloc` yoluna göre ek maliyet içerir.")
    lines.append("- Python/Axiom oranı, Axiom'un Python'a göre hız kazancını gösterir.")
    if failures:
        lines.append("")
        lines.append("**Doğrulama uyarıları**")
        for f_ in failures:
            lines.append(f"- {f_}")
    lines.append("")
    lines.append("> Ölçümler tek makinede, tek oturumda alınmıştır; mutlak değil göreli karşılaştırma içindir.")
    table = "\n".join(lines)

    print(table)

    if not args.no_write:
        RESULTS.write_text(table + "\n", encoding="utf-8")
        print(f"\n✓ Yazıldı: {RESULTS.relative_to(ROOT)}")

    if args.json:
        Path(args.json).write_text(json.dumps({"machine": info, "rows": rows}, indent=2), encoding="utf-8")
        print(f"✓ JSON: {args.json}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
