"""
Unit and Integration Tests for Option<T> and Result<T, E> Null-Safety Architecture (FAZ 2.1)
"""
import pytest
import subprocess
import tempfile
import os
from pathlib import Path

from axiom.cli import compile_axiom_source, find_c_compiler
from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.resolver import ModuleResolver
from axiom.checker import TypeChecker

def run_axiom(source: str):
    c_code = compile_axiom_source(source, prove=False)
    cc = find_c_compiler()

    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        res_cc = subprocess.run([cc, "-O2", "-pthread", c_path, "-o", bin_path, "-lm"], capture_output=True, text=True)
        if res_cc.returncode != 0:
            raise RuntimeError(f"C Derleme Hatasi:\n{res_cc.stderr}\nKod:\n{c_code}")
        res_exec = subprocess.run([bin_path], capture_output=True, text=True)
        return res_exec
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

def test_option_int_some_and_none():
    source = """
    import "std:core:option";

    fn main() -> int {
        let opt = some_int(42);
        verify is_some(opt);
        verify not is_none(opt);
        let val = unwrap(opt);
        verify val == 42;

        let empty = none_int();
        verify is_none(empty);
        verify not is_some(empty);
        let fallback = unwrap_or(empty, 99);
        verify fallback == 99;

        print("OptionInt OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "OptionInt OK" in res.stdout

def test_option_str_and_bool():
    source = """
    import "std:core:option";

    fn main() -> int {
        let opt_s = some("hello axiom");
        verify is_some(opt_s);
        verify unwrap(opt_s) == "hello axiom";

        let empty_s = none_str();
        verify is_none(empty_s);
        verify unwrap_or(empty_s, "default") == "default";

        let opt_b = some_bool(true);
        verify is_some(opt_b);
        verify unwrap(opt_b);

        let empty_b = none_bool();
        verify is_none(empty_b);
        verify not unwrap_or(empty_b, false);

        print("OptionStr & OptionBool OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "OptionStr & OptionBool OK" in res.stdout

def test_option_none_unwrap_panics():
    source = """
    import "std:core:option";

    fn main() -> int {
        let empty = none_int();
        let val = unwrap(empty);
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode != 0
    assert "Called unwrap on None OptionInt" in res.stderr

def test_result_int_ok_and_err():
    source = """
    import "std:core:result";

    fn divide(a: int, b: int) -> ResultInt {
        if b == 0 {
            return err_int("division by zero");
        }
        return ok_int(a / b);
    }

    fn main() -> int {
        let res_ok = divide(10, 2);
        verify is_ok(res_ok);
        verify not is_err(res_ok);
        verify unwrap(res_ok) == 5;

        let res_err = divide(10, 0);
        verify is_err(res_err);
        verify not is_ok(res_err);
        verify unwrap_err(res_err) == "division by zero";

        print("ResultInt OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "ResultInt OK" in res.stdout

def test_result_str_ok_and_err():
    source = """
    import "std:core:result";

    fn main() -> int {
        let r_ok = ok_str("success data");
        verify is_ok(r_ok);
        verify unwrap(r_ok) == "success data";

        let r_err = err_str("io timeout");
        verify is_err(r_err);
        verify unwrap_err(r_err) == "io timeout";

        print("ResultStr OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "ResultStr OK" in res.stdout

def test_result_err_unwrap_panics():
    source = """
    import "std:core:result";

    fn main() -> int {
        let r_err = err_int("fatal failure");
        let val = unwrap(r_err);
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode != 0
    assert "Called unwrap on Err ResultInt" in res.stderr

def test_result_ok_unwrap_err_panics():
    source = """
    import "std:core:result";

    fn main() -> int {
        let r_ok = ok_int(42);
        let err_msg = unwrap_err(r_ok);
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode != 0
    assert "Called unwrap_err on Ok ResultInt" in res.stderr
