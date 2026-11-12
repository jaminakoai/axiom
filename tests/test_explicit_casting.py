"""
Unit and Integration Tests for Explicit Type Casting with 'as' Keyword (FAZ 2.4)
"""
import pytest
import subprocess
import tempfile
import os
from pathlib import Path

from axiom.cli import compile_axiom_source, find_c_compiler
from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.checker import TypeChecker, SemanticError

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

def test_explicit_cast_float_to_int():
    source = """
    fn main() -> int {
        let f: float = 42.99;
        let i: int = f as int;
        verify i == 42;

        let neg_f: float = -7.8;
        let neg_i: int = neg_f as int;
        verify neg_i == -7;

        print("Float to Int OK:", i, neg_i);
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Float to Int OK: 42 -7" in res.stdout

def test_explicit_cast_int_to_float():
    source = """
    fn main() -> int {
        let count: int = 7;
        let total: int = 2;
        let avg: float = (count as float) / (total as float);
        verify avg > 3.4;
        verify avg < 3.6;

        print("Int to Float OK:", avg);
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Int to Float OK: 3.5" in res.stdout

def test_explicit_cast_bool_to_int():
    source = """
    fn main() -> int {
        let t: bool = true;
        let f: bool = false;
        let t_int: int = t as int;
        let f_int: int = f as int;
        verify t_int == 1;
        verify f_int == 0;

        print("Bool to Int OK:", t_int, f_int);
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Bool to Int OK: 1 0" in res.stdout

def test_explicit_cast_in_arithmetic_expressions():
    source = """
    fn main() -> int {
        let x: int = 15;
        let y: float = (x + 5) as float / 4.0;
        verify y == 5.0;

        let z: int = (y * 2.5) as int;
        verify z == 12;

        print("Expression Cast OK:", y, z);
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Expression Cast OK: 5 12" in res.stdout

def test_invalid_cast_type_rejected_by_checker():
    source = """
    fn main() -> int {
        let x: int = 10;
        let y = x as invalid_type;
        return 0;
    }
    """
    tokens = Lexer(source).tokenize()
    prog = Parser(tokens).parse()
    with pytest.raises(SemanticError) as exc_info:
        TypeChecker().check(prog)
    assert "Gecersiz acik tip donusumu hedefi" in str(exc_info.value)
