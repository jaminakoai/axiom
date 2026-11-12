"""
Axiom Programming Language (λx) - Self-Hosted Full Generics Tests
Verifies that Box<str>, Box<float>, Pair<int, str>, Pair<float, int> compile and run
correctly with both python driver (axiom) and native self-hosted compiler (bin/axiomc).
"""
import subprocess
import tempfile
import os
from pathlib import Path
import pytest

AXIOM_ROOT = Path(__file__).resolve().parent.parent
AXIOMC_BIN = AXIOM_ROOT / "bin" / "axiomc"


def run_with_python_axiom(src_code: str) -> tuple[int, str, str]:
    from axiom.cli import compile_axiom_source, find_c_compiler
    c_code = compile_axiom_source(src_code)
    cc = find_c_compiler()
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_f, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as b_f:
        c_path = c_f.name
        b_path = b_f.name
        c_f.write(c_code)

    try:
        cmd = [cc, "-O3", "-Wall", c_path, "-o", b_path, "-lssl", "-lcrypto", "-lz", "-ldl", "-pthread"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"C derleme hatasi:\n{res.stderr}"

        run_res = subprocess.run([b_path], capture_output=True, text=True, timeout=10)
        return run_res.returncode, run_res.stdout, run_res.stderr
    finally:
        if os.path.exists(c_path): os.remove(c_path)
        if os.path.exists(b_path): os.remove(b_path)


def run_with_self_hosted_axiomc(src_code: str) -> tuple[int, str, str]:
    if not AXIOMC_BIN.exists():
        pytest.skip("bin/axiomc bulunamadi")

    with tempfile.NamedTemporaryFile(suffix=".ax", mode="w", delete=False) as src_f, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as b_f:
        src_path = src_f.name
        b_path = b_f.name
        src_f.write(src_code)

    try:
        cmd_build = [str(AXIOMC_BIN), "build", src_path, "-o", b_path]
        res_build = subprocess.run(cmd_build, capture_output=True, text=True)
        assert res_build.returncode == 0, f"axiomc derleme hatasi:\n{res_build.stdout}\n{res_build.stderr}"

        run_res = subprocess.run([b_path], capture_output=True, text=True, timeout=10)
        return run_res.returncode, run_res.stdout, run_res.stderr
    finally:
        if os.path.exists(src_path): os.remove(src_path)
        if os.path.exists(b_path): os.remove(b_path)


def test_box_str_in_python_and_self_hosted():
    src = """
    struct Box<T> {
        val: T
    }

    fn main() -> int {
        let b: Box<str> = Box<str> { val: "axiom_compiler_generics" }
        print("BOX_STR:", b.val)
        return 0
    }
    """
    # 1. Python bootstrap derleyicisi
    ret_py, out_py, _ = run_with_python_axiom(src)
    assert ret_py == 0
    assert "BOX_STR: axiom_compiler_generics" in out_py

    # 2. Self-hosted bin/axiomc
    ret_sh, out_sh, _ = run_with_self_hosted_axiomc(src)
    assert ret_sh == 0
    assert "BOX_STR: axiom_compiler_generics" in out_sh


def test_box_float_in_python_and_self_hosted():
    src = """
    struct Box<T> {
        val: T
    }

    fn main() -> int {
        let b: Box<float> = Box<float> { val: 3.14159 }
        print("BOX_FLOAT:", b.val)
        return 0
    }
    """
    ret_py, out_py, _ = run_with_python_axiom(src)
    assert ret_py == 0
    assert "BOX_FLOAT: 3.14159" in out_py

    ret_sh, out_sh, _ = run_with_self_hosted_axiomc(src)
    assert ret_sh == 0
    assert "BOX_FLOAT: 3.14159" in out_sh


def test_pair_int_str_multiple_generics_in_python_and_self_hosted():
    src = """
    struct Pair<T, U> {
        first: T,
        second: U
    }

    fn main() -> int {
        let p: Pair<int, str> = Pair<int, str> { first: 42, second: "guvenlik" }
        print("PAIR_INT_STR:", p.first, p.second)
        return 0
    }
    """
    ret_py, out_py, _ = run_with_python_axiom(src)
    assert ret_py == 0
    assert "PAIR_INT_STR: 42 guvenlik" in out_py

    ret_sh, out_sh, _ = run_with_self_hosted_axiomc(src)
    assert ret_sh == 0
    assert "PAIR_INT_STR: 42 guvenlik" in out_sh


def test_pair_float_int_multiple_generics_in_python_and_self_hosted():
    src = """
    struct Pair<T, U> {
        first: T,
        second: U
    }

    fn main() -> int {
        let p: Pair<float, int> = Pair<float, int> { first: 2.718, second: 100 }
        print("PAIR_FLOAT_INT:", p.first, p.second)
        return 0
    }
    """
    ret_py, out_py, _ = run_with_python_axiom(src)
    assert ret_py == 0
    assert "PAIR_FLOAT_INT: 2.718 100" in out_py

    ret_sh, out_sh, _ = run_with_self_hosted_axiomc(src)
    assert ret_sh == 0
    assert "PAIR_FLOAT_INT: 2.718 100" in out_sh


def test_multiple_specializations_in_same_program():
    src = """
    struct Box<T> {
        val: T
    }

    fn main() -> int {
        let b1: Box<int> = Box<int> { val: 123 }
        let b2: Box<str> = Box<str> { val: "coklu_ozellestirme" }
        let b3: Box<float> = Box<float> { val: 1.25 }
        print("MULTI:", b1.val, b2.val, b3.val)
        return 0
    }
    """
    ret_py, out_py, _ = run_with_python_axiom(src)
    assert ret_py == 0
    assert "MULTI: 123 coklu_ozellestirme 1.25" in out_py

    ret_sh, out_sh, _ = run_with_self_hosted_axiomc(src)
    assert ret_sh == 0
    assert "MULTI: 123 coklu_ozellestirme 1.25" in out_sh
