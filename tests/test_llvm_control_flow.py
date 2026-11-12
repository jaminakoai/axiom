"""
Axiom - LLVM `break` / `continue` / `verify` / `as` parite testleri

Bu testler, LLVM arka ucunun C arka ucuyla AYNI sonucu vermesini dogrular.
Ozellikle `break`/`continue` once LLVM'de hic uygulanmiyordu ve sessizce
yanlis sonuc uretiyordu (hata vermeden).
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"


def _run_compiled(src: str, backend: str):
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
        res = subprocess.run(args, capture_output=True, text=True, timeout=240, env=env)
        assert res.returncode == 0, f"[{backend}] derleme hatasi:\n{res.stdout}\n{res.stderr}"
        run = subprocess.run([out], capture_output=True, text=True, timeout=120)
        return run.stdout.strip(), run.returncode
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)


def _parity(src: str, expected: str):
    c_out, c_rc = _run_compiled(src, "c")
    l_out, l_rc = _run_compiled(src, "llvm")
    assert c_out == expected, f"C ciktisi beklenenden farkli: {c_out!r}"
    assert l_out == c_out, f"LLVM ({l_out!r}) C ({c_out!r}) ile ayni degil"
    assert c_rc == l_rc


# --------------------------------------------------------------------------
# break / continue
# --------------------------------------------------------------------------

def test_break_continue_in_while():
    _parity("""
fn main() -> int {
    let mut i = 0
    let mut s = 0
    while i < 10 {
        i = i + 1
        if i == 3 { continue }
        if i == 6 { break }
        s = s + i
    }
    print("S:", s)
    return 0
}
""", "S: 12")


def test_break_continue_in_for():
    _parity("""
fn main() -> int {
    let mut s = 0
    for i in 0..10 {
        if i == 2 { continue }
        if i == 7 { break }
        s = s + i
    }
    print("FOR:", s)
    return 0
}
""", "FOR: 19")


def test_break_continue_in_nested_loops():
    _parity("""
fn main() -> int {
    let mut n = 0
    let mut i = 0
    while i < 3 {
        let mut j = 0
        while j < 5 {
            j = j + 1
            if j == 2 { continue }
            if j == 4 { break }
            n = n + 1
        }
        i = i + 1
    }
    print("NEST:", n)
    return 0
}
""", "NEST: 6")


def test_break_releases_loop_scope_strings():
    """break sirasinda dongu govdesindeki sahipli string birakilmali."""
    _parity("""
fn main() -> int {
    let mut i = 0
    while i < 5 {
        let s = "x" + int_to_str(i)
        i = i + 1
        if i == 3 { break }
        print(len(s))
    }
    print("SON:", i)
    return 0
}
""", "2\n2\nSON: 3")


# --------------------------------------------------------------------------
# verify / as (LLVM paritesi)
# --------------------------------------------------------------------------

def test_verify_statement_matches_both_backends():
    _parity("""
fn f(x: int) -> int requires x > 0 {
    verify x < 100, "x cok buyuk"
    return x
}
fn main() -> int {
    print(f(5))
    return 0
}
""", "5")


def test_verify_failure_stops_both_backends():
    """`verify` ihlali ya derleme anında (prover) ya çalışma anında durmalı."""
    src = """
fn main() -> int {
    let x = 500
    verify x < 100, "sinir asildi"
    print("ULASILMAMALI")
    return 0
}
"""
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    try:
        for backend in ("c", "llvm"):
            out_path = path + f".{backend}.bin"
            args = [str(AXIOM), "build", path, "-o", out_path]
            if backend == "llvm":
                args.insert(2, "--backend=llvm")
            build = subprocess.run(args, capture_output=True, text=True, timeout=240)
            if build.returncode != 0:
                # Derleme anında reddedildi: ispatlayıcı yakaladı (kabul edilebilir).
                assert "verify" in (build.stdout + build.stderr).lower()
                continue
            run = subprocess.run([out_path], capture_output=True, text=True, timeout=60)
            assert run.returncode != 0, f"[{backend}] verify ihlali durdurmadi"
            assert "ULASILMAMALI" not in run.stdout
            os.remove(out_path)
    finally:
        os.remove(path)


def test_explicit_casts_match_both_backends():
    _parity("""
fn main() -> int {
    let a = 3.9
    let b = a as int
    let c = 7 as float
    let d = 1 as bool
    print("B:", b, "C:", c, "D:", d)
    return 0
}
""", "B: 3 C: 7 D: true")
