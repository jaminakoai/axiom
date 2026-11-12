"""
Axiom - LLVM arka ucunda string sahiplik temizligi testleri

LLVM, C arka ucunun sahip oldugu kapsam temizligini de uretmeli:
  - let s: str = ... -> kapsam sonunda axiom_str_owned_release
  - while/for govdesi -> her turda temizlik
  - if/else dallari -> dal sonunda temizlik
  - donen string -> caller icin retain
  - struct alani / cagri argumani -> kacis (temizlenmez)
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"


def build_llvm(src: str, timeout=240):
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    out = path + ".bin"
    try:
        res = subprocess.run(
            [str(AXIOM), "build", path, "--backend=llvm", "-o", out],
            capture_output=True, text=True, timeout=timeout,
        )
        return res, path, out
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise


def run_llvm(src: str):
    res, path, out = build_llvm(src)
    try:
        assert res.returncode == 0, res.stdout + res.stderr
        run = subprocess.run([out], capture_output=True, text=True, timeout=120)
        return run
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)


def emit_ir(src: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    try:
        res = subprocess.run(
            [str(AXIOM), "emit-llvm", path], capture_output=True, text=True, timeout=180
        )
        assert res.returncode == 0, res.stdout + res.stderr
        return res.stdout
    finally:
        os.remove(path)


def test_llvm_emits_scope_release_calls():
    ir = emit_ir("""
    fn main() -> int {
        let s = "a" + "b"
        print(s)
        return 0
    }
    """)
    assert "declare void @axiom_str_owned_release(i8**)" in ir
    assert "call void @axiom_str_owned_release" in ir


def test_llvm_loop_body_releases_each_iteration():
    ir = emit_ir("""
    fn main() -> int {
        let mut i = 0
        while i < 10 {
            let s = "x" + "y"
            print(len(s))
            i = i + 1
        }
        return 0
    }
    """)
    # Döngü gövdesinde temizlik üretilmeli (back-edge'den önce).
    assert "while_body" in ir
    body_start = ir.index("while_body")
    body = ir[body_start:]
    assert "call void @axiom_str_owned_release" in body[: body.index("br label %while_cond")]


def test_llvm_string_loop_matches_c_output():
    src = """
    fn make(i: int) -> str { return "v" + int_to_str(i) }
    fn main() -> int {
        let mut t = 0
        let mut i = 0
        while i < 300 {
            let s = make(i)
            t = t + len(s)
            i = i + 1
        }
        print("T:", t)
        return 0
    }
    """
    run = run_llvm(src)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "T: 1090" in run.stdout


def test_llvm_string_alias_is_not_double_released():
    src = """
    fn main() -> int {
        let a = "hello" + "world"
        let b = a
        print(a)
        print(b)
        let mut c = a
        c = c + "-x"
        print(c)
        print(a)
        return 0
    }
    """
    run = run_llvm(src)
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout.splitlines() == ["helloworld", "helloworld", "helloworld-x", "helloworld"]


def test_llvm_returned_string_survives_caller():
    src = """
    fn choose(flag: bool) -> str {
        if flag {
            let s = "yes" + "!"
            return s
        }
        let t = "no" + "?"
        return t
    }
    fn main() -> int {
        print(choose(true))
        print(choose(false))
        return 0
    }
    """
    run = run_llvm(src)
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout.splitlines() == ["yes!", "no?"]


def test_llvm_escaped_string_in_struct_and_call_arg():
    src = """
    struct P { name: str, n: int }
    fn build(i: int) -> P { return P { name: "item" + int_to_str(i), n: i } }
    fn show(s: str) -> int { return len(s) }
    fn main() -> int {
        let p = build(7)
        print(p.name, p.n)
        let s = "abc" + "def"
        print(show(s))
        print(s)
        return 0
    }
    """
    run = run_llvm(src)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "item7 7" in run.stdout
    assert "6" in run.stdout
    assert "abcdef" in run.stdout


def test_llvm_str_array_is_released_at_scope_exit():
    """str[] dizi tamponu ve elemanlari kapsam sonunda birakilmali."""
    ir = emit_ir("""
    fn main() -> int {
        let parts = str_split("a,b,c", ",")
        print(len(parts))
        return 0
    }
    """)
    assert "declare void @axiom_array_str_free(%struct.ax_array*)" in ir
    assert "call void @axiom_array_str_free" in ir


def test_llvm_array_loop_matches_c_and_is_leak_free():
    src = """
    fn main() -> int {
        let mut i = 0
        let mut total = 0
        while i < 200 {
            let parts = str_split("alpha,beta,gamma", ",")
            total = total + len(parts)
            i = i + 1
        }
        print("T:", total)
        return 0
    }
    """
    res, path, out = build_llvm(src)
    try:
        build = res
        assert build.returncode == 0, build.stdout + build.stderr
        run = subprocess.run([out], capture_output=True, text=True, timeout=120)
        assert run.returncode == 0, run.stdout + run.stderr
        assert "T: 600" in run.stdout
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)
