"""
Unit and Integration Tests for Exhaustive Pattern Matching (match) - FAZ 2.3
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

def check_source(source: str):
    tokens = Lexer(source).tokenize()
    prog = Parser(tokens).parse()
    checker = TypeChecker()
    checker.check(prog)
    return prog

# ---------------------------------------------------------------------------
# 1. Integer Pattern Matching
# ---------------------------------------------------------------------------

def test_match_int_expression_e2e():
    source = """
    fn classify(x: int) -> str {
        return match x {
            1 => "bir",
            2 => "iki",
            3 => "uc",
            _ => "diger"
        };
    }

    fn main() -> int {
        verify classify(1) == "bir";
        verify classify(2) == "iki";
        verify classify(3) == "uc";
        verify classify(99) == "diger";
        verify classify(-5) == "diger";
        print("Match Int OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Match Int OK" in res.stdout

def test_match_negative_int_literal():
    source = """
    fn test_neg(x: int) -> int {
        return match x {
            -1 => 100,
            -2 => 200,
            0 => 0,
            _ => -1
        };
    }

    fn main() -> int {
        verify test_neg(-1) == 100;
        verify test_neg(-2) == 200;
        verify test_neg(0) == 0;
        verify test_neg(5) == -1;
        print("Match Negative Int OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Match Negative Int OK" in res.stdout

# ---------------------------------------------------------------------------
# 2. String Pattern Matching
# ---------------------------------------------------------------------------

def test_match_str_expression_e2e():
    source = """
    fn http_status_code(method: str) -> int {
        return match method {
            "GET" => 200,
            "POST" => 201,
            "DELETE" => 204,
            _ => 400
        };
    }

    fn main() -> int {
        verify http_status_code("GET") == 200;
        verify http_status_code("POST") == 201;
        verify http_status_code("DELETE") == 204;
        verify http_status_code("OPTIONS") == 400;
        print("Match Str OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Match Str OK" in res.stdout

# ---------------------------------------------------------------------------
# 3. Boolean Exhaustiveness Without Wildcard
# ---------------------------------------------------------------------------

def test_match_bool_exhaustive_without_wildcard():
    source = """
    fn bool_to_bit(b: bool) -> int {
        return match b {
            true => 1,
            false => 0
        };
    }

    fn main() -> int {
        verify bool_to_bit(true) == 1;
        verify bool_to_bit(false) == 0;
        print("Match Bool Exhaustive OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Match Bool Exhaustive OK" in res.stdout

def test_match_bool_non_exhaustive_raises():
    source = """
    fn invalid(b: bool) -> int {
        return match b {
            true => 1
        };
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Tuketici olmayan match" in str(exc_info.value)
    assert "bool" in str(exc_info.value)

# ---------------------------------------------------------------------------
# 4. Pattern Guards
# ---------------------------------------------------------------------------

def test_match_arm_guard():
    source = """
    fn check_number(x: int) -> str {
        return match x {
            n if n > 100 => "buyuk",
            n if n > 0 => "pozitif",
            0 => "sifir",
            _ => "negatif"
        };
    }

    fn main() -> int {
        verify check_number(500) == "buyuk";
        verify check_number(42) == "pozitif";
        verify check_number(0) == "sifir";
        verify check_number(-10) == "negatif";
        print("Match Guard OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Match Guard OK" in res.stdout

# ---------------------------------------------------------------------------
# 5. Statement Match & Scope
# ---------------------------------------------------------------------------

def test_match_statement_with_blocks_and_mut():
    source = """
    fn main() -> int {
        let mut count = 0;
        let x = 2;

        match x {
            1 => {
                count = 10;
            },
            2 => {
                count = 20;
            },
            _ => {
                count = 999;
            }
        }

        verify count == 20;
        print("Match Stmt OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Match Stmt OK" in res.stdout

# ---------------------------------------------------------------------------
# 6. Exhaustiveness Errors (Negative Tests)
# ---------------------------------------------------------------------------

def test_match_int_missing_wildcard_raises():
    source = """
    fn test_missing(x: int) -> int {
        return match x {
            1 => 10,
            2 => 20
        };
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Tuketici olmayan match" in str(exc_info.value)
    assert "wildcard" in str(exc_info.value)

def test_match_str_missing_wildcard_raises():
    source = """
    fn test_missing_str(s: str) -> int {
        return match s {
            "a" => 1,
            "b" => 2
        };
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Tuketici olmayan match" in str(exc_info.value)
    assert "wildcard" in str(exc_info.value)

# ---------------------------------------------------------------------------
# 7. Type Mismatch In Patterns (Negative Tests)
# ---------------------------------------------------------------------------

def test_match_pattern_type_mismatch():
    source = """
    fn test_mismatch(x: int) -> int {
        return match x {
            "abc" => 1,
            _ => 0
        };
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "uyusmuyor" in str(exc_info.value)

def test_match_arm_return_types_mismatch():
    source = """
    fn test_inconsistent(x: int) -> int {
        return match x {
            1 => 10,
            _ => "string_value"
        };
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Match kollarinin donus tipleri uyumsuz" in str(exc_info.value)
