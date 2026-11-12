"""
Axiom - Overload çözümlemesi ve CLI hata yolu regresyon testleri

Bu davranışlar v0.5'te doğru çalışıyor ancak test edilmiyordu; gelecekteki
değişikliklerin sessizce bozmasını engellemek için kilitlenir.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"


def _build_run(src: str, backend: str):
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
        if b.returncode != 0:
            return None, b.returncode, b.stdout + b.stderr
        r = subprocess.run([out], capture_output=True, text=True, timeout=120)
        return r.stdout, r.returncode, r.stderr
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)


def _parity(src: str, expected_lines):
    for backend in ("c", "llvm"):
        out, rc, err = _build_run(src, backend)
        assert out is not None, f"[{backend}] derleme hatasi:\n{err}"
        assert rc == 0, f"[{backend}] calisma hatasi ({rc}):\n{out}{err}"
        assert out.splitlines() == expected_lines, f"[{backend}]: {out!r}"


# --------------------------------------------------------------------------
# Overload
# --------------------------------------------------------------------------

def test_overload_by_parameter_type():
    _parity("""
fn show(x: int) -> str { return "int:" + int_to_str(x) }
fn show(x: str) -> str { return "str:" + x }
fn main() -> int {
    print(show(42))
    print(show("abc"))
    return 0
}
""", ["int:42", "str:abc"])


def test_overload_by_arity():
    _parity("""
fn f(a: int) -> str { return "one" + int_to_str(a) }
fn f(a: int, b: int) -> str { return "two" + int_to_str(a + b) }
fn main() -> int {
    print(f(1))
    print(f(1, 2))
    return 0
}
""", ["one1", "two3"])


def test_overload_three_way_int_str_bool():
    _parity("""
fn g(x: int) -> str { return "i" }
fn g(x: str) -> str { return "s" }
fn g(x: bool) -> str { return "b" }
fn main() -> int {
    print(g(1))
    print(g("a"))
    print(g(true))
    return 0
}
""", ["i", "s", "b"])


def test_overload_void_return():
    _parity("""
fn h(x: int) -> void { print("int", x) }
fn h(x: str) -> void { print("str", x) }
fn main() -> int {
    h(5)
    h("z")
    return 0
}
""", ["int 5", "str z"])


def test_overload_returning_generic_struct():
    _parity("""
struct Box<T> { val: T }
fn k(x: int) -> Box<int> { return Box<int> { val: x } }
fn k(x: str) -> Box<str> { return Box<str> { val: x } }
fn main() -> int {
    let a = k(3)
    let b = k("q")
    print(a.val, b.val)
    return 0
}
""", ["3 q"])


def test_overload_wrong_argument_type_is_rejected():
    src = """
fn m(x: int) -> str { return "i" }
fn main() -> int { print(m(3.5)); return 0 }
"""
    out, rc, err = _build_run(src, "c")
    assert out is None and rc != 0
    assert "tip uyumsuzlugu" in err


def test_duplicate_signature_is_rejected():
    src = """
fn d(x: int) -> int { return 1 }
fn d(x: int) -> int { return 2 }
fn main() -> int { return 0 }
"""
    out, rc, err = _build_run(src, "c")
    assert out is None and rc != 0


# --------------------------------------------------------------------------
# CLI hata yolları: eksik dosya
# --------------------------------------------------------------------------

MISSING = "/tmp/axiom_test_does_not_exist_12345.ax"


@pytest.mark.parametrize("cmd", [
    "run", "build", "check", "prove", "emit-c", "emit-llvm", "emit-smt", "fmt",
])
def test_cli_missing_file_exits_1_with_message(cmd):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    res = subprocess.run([str(AXIOM), cmd, MISSING],
                         capture_output=True, text=True, timeout=120, env=env)
    assert res.returncode == 1, f"'{cmd}' eksik dosyada 1 dondurmeliydi ({res.returncode})"
    msg = res.stdout + res.stderr
    assert "bulunamadi" in msg.lower() or "not found" in msg.lower()
    assert "✓" not in res.stdout, "eksik dosyada basari mesaji basilmamali"


# --------------------------------------------------------------------------
# CLI hata yolları: sözdizimi / modül hataları
# --------------------------------------------------------------------------

@pytest.mark.parametrize("cmd", ["run", "check", "emit-c"])
def test_cli_syntax_error_exits_nonzero(cmd):
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write("fn main() -> int {\n    let x = \n}\n")
        path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        res = subprocess.run([str(AXIOM), cmd, path],
                             capture_output=True, text=True, timeout=120, env=env)
        assert res.returncode != 0
        assert "hata" in (res.stdout + res.stderr).lower()
    finally:
        os.remove(path)


def test_cli_missing_module_import_exits_nonzero():
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write('import "yokboylemodul.ax"\nfn main() -> int { return 0 }\n')
        path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        res = subprocess.run([str(AXIOM), "check", path],
                             capture_output=True, text=True, timeout=120, env=env)
        assert res.returncode != 0
        assert "modul" in (res.stdout + res.stderr).lower()
    finally:
        os.remove(path)


def test_cli_semantic_error_exits_nonzero():
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write('fn main() -> int {\n    let x: int = "abc"\n    return 0\n}\n')
        path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        res = subprocess.run([str(AXIOM), "check", path],
                             capture_output=True, text=True, timeout=120, env=env)
        assert res.returncode == 1
        assert "tip uyumsuzlugu" in (res.stdout + res.stderr).lower()
    finally:
        os.remove(path)
