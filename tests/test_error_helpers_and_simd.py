"""
Axiom - `std/core/error` yardımcıları ve `@simd` dekoratörü testleri

Her iki alan da v0.5'te çalışıyordu ancak testsizdi.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"


def _run(src: str, backend: str = "c"):
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    out = path + ".bin"
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        args = [str(AXIOM), "build", path, "-o", out]
        if backend == "llvm":
            args.insert(2, "--backend=llvm")
        b = subprocess.run(args, capture_output=True, text=True, timeout=240, env=env)
        assert b.returncode == 0, b.stdout + b.stderr
        return subprocess.run([out], capture_output=True, text=True, timeout=120)
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)


# --------------------------------------------------------------------------
# std/core/error yardımcıları
# --------------------------------------------------------------------------

HELPERS = """
import "std/core/error"

fn main() -> int {
    let a = result_ok<int>(5)
    let b = result_err_int("bozuk")

    print("is_ok:", result_is_ok(a), result_is_ok(b))
    print("is_err:", result_is_err(a), result_is_err(b))
    print("unwrap:", result_unwrap(a))
    print("unwrap_or:", result_unwrap_or(b, -1))
    print("error:", result_error(b))
    print("expect:", result_expect(a, "olmali"))

    let c = result_err_str("metin")
    let d = result_err_bool("bool")
    let e = result_err_strs("dizi")
    print("errs:", c.error, d.error, e.error)
    print("empty_arr:", len(e.value))

    let f = result_err_with<int>("ozel", 0)
    print("with:", f.error, f.value)
    return 0
}
"""

EXPECTED = [
    "is_ok: true false",
    "is_err: false true",
    "unwrap: 5",
    "unwrap_or: -1",
    "error: bozuk",
    "expect: 5",
    "errs: metin bool dizi",
    "empty_arr: 0",
    "with: ozel 0",
]


def test_result_helpers_c_and_llvm_parity():
    for backend in ("c", "llvm"):
        out = _run(HELPERS, backend)
        assert out.returncode == 0, f"[{backend}] {out.stderr}"
        assert out.stdout.splitlines() == EXPECTED, f"[{backend}]: {out.stdout!r}"


@pytest.mark.parametrize("src,what", [
    ("""import "std/core/error"
fn main() -> int { print(result_unwrap(result_err_int("x"))) return 0 }
""", "result_unwrap(Err)"),
    ("""import "std/core/error"
fn main() -> int { print(result_expect(result_err_int("x"), "m")) return 0 }
""", "result_expect(Err)"),
    ("""import "std/core/error"
fn main() -> int { print(result_error(result_ok<int>(1))) return 0 }
""", "result_error(Ok)"),
])
def test_result_helpers_abort_on_wrong_variant(src, what):
    """Yanlış varyantta çağrı sözleşme ihlaliyle durmalı (exit 101)."""
    for backend in ("c", "llvm"):
        out = _run(src, backend)
        assert out.returncode == 101, f"[{backend}] {what} exit {out.returncode} olmamali"


# --------------------------------------------------------------------------
# @simd dekoratörü
# --------------------------------------------------------------------------

SIMD_SRC = """
@simd
fn scale(x: int) -> int {
    return x * 2
}

fn plain(x: int) -> int {
    return x + 1
}

fn main() -> int {
    let mut t = 0
    let mut i = 0
    while i < 4 {
        t = t + scale(i) + plain(i)
        i = i + 1
    }
    print("T:", t)
    return 0
}
"""


def test_simd_function_runs_identically_both_backends():
    results = {}
    for backend in ("c", "llvm"):
        out = _run(SIMD_SRC, backend)
        assert out.returncode == 0, f"[{backend}] {out.stderr}"
        results[backend] = out.stdout.strip()
    assert results["c"] == results["llvm"] == "T: 22"


def test_simd_emits_vectorization_hint_in_c():
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(SIMD_SRC)
        path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        res = subprocess.run([str(AXIOM), "emit-c", path],
                             capture_output=True, text=True, timeout=180, env=env)
        assert res.returncode == 0, res.stderr
        c_code = res.stdout
        # @simd fonksiyonunda optimize/tree-vectorize bulunmali
        simd_fn = c_code[c_code.index("ax_scale"):]
        assert "optimize(" in simd_fn and "tree-vectorize" in simd_fn
    finally:
        os.remove(path)


def test_simd_emits_target_features_in_llvm():
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(SIMD_SRC)
        path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        res = subprocess.run([str(AXIOM), "emit-llvm", path],
                             capture_output=True, text=True, timeout=180, env=env)
        assert res.returncode == 0, res.stderr
        ir = res.stdout
        assert 'attributes #0 = { "target-features"="+avx2,+fma" }' in ir
        # Yalnizca @simd fonksiyonlari #0 kullanmali
        assert "define i64 @ax_scale(i64 %param.x) #0" in ir
        assert "define i64 @ax_plain(i64 %param.x) #0" not in ir
    finally:
        os.remove(path)


def test_non_simd_program_has_no_attribute_group():
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write("fn main() -> int { print(1) return 0 }\n")
        path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        res = subprocess.run([str(AXIOM), "emit-llvm", path],
                             capture_output=True, text=True, timeout=180, env=env)
        assert res.returncode == 0, res.stderr
        assert "attributes #0" not in res.stdout
    finally:
        os.remove(path)


def test_simd_example_runs_both_backends():
    example = ROOT / "examples" / "09_simd_vector_scan.ax"
    for backend in ("c", "llvm"):
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            out_path = f.name
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT)
            args = [str(AXIOM), "build", str(example), "-o", out_path]
            if backend == "llvm":
                args.insert(2, "--backend=llvm")
            b = subprocess.run(args, capture_output=True, text=True, timeout=240, env=env)
            assert b.returncode == 0, b.stdout + b.stderr
            r = subprocess.run([out_path], capture_output=True, text=True, timeout=120)
            assert r.returncode == 0, f"[{backend}] {r.stderr}"
            assert "SIMD Donanim Hizlandirmali Tarama Tamamlandi" in r.stdout
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)
