"""
Unit and Integration Tests for Generic Type Parameters (<T>, <T, U>) - FAZ 2.2
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
# 1. Generic Structs
# ---------------------------------------------------------------------------

def test_generic_struct_monomorphization_e2e():
    source = """
    struct Box<T> {
        val: T
    }

    fn main() -> int {
        let b1: Box<int> = Box<int> { val: 42 };
        let b2: Box<str> = Box<str> { val: "axiom generics" };
        let b3: Box<bool> = Box<bool> { val: true };

        verify b1.val == 42;
        verify b2.val == "axiom generics";
        verify b3.val;

        print("Generic Struct OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Generic Struct OK" in res.stdout

# ---------------------------------------------------------------------------
# 2. Generic Functions with Explicit & Inferred Type Parameters
# ---------------------------------------------------------------------------

def test_generic_functions_explicit_and_inferred_e2e():
    source = """
    struct Box<T> {
        val: T
    }

    fn wrap<T>(item: T) -> Box<T> {
        return Box<T> { val: item };
    }

    fn unbox<T>(b: Box<T>) -> T {
        return b.val;
    }

    fn main() -> int {
        let b_int = wrap<int>(100);
        let val_int = unbox<int>(b_int);
        verify val_int == 100;

        # Inferred type arguments
        let b_str = wrap("dynamic inference");
        let val_str = unbox(b_str);
        verify val_str == "dynamic inference";

        print("Generic Function Wrap/Unbox OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Generic Function Wrap/Unbox OK" in res.stdout

# ---------------------------------------------------------------------------
# 3. Multiple Type Parameters (<T, U>)
# ---------------------------------------------------------------------------

def test_generic_multiple_type_params_pair_e2e():
    source = """
    struct Pair<T, U> {
        first: T,
        second: U
    }

    fn make_pair<T, U>(a: T, b: U) -> Pair<T, U> {
        return Pair<T, U> { first: a, second: b };
    }

    fn get_first<T, U>(p: Pair<T, U>) -> T {
        return p.first;
    }

    fn get_second<T, U>(p: Pair<T, U>) -> U {
        return p.second;
    }

    fn main() -> int {
        let p = make_pair(77, "seven seven");
        verify get_first(p) == 77;
        verify get_second(p) == "seven seven";

        let p2 = make_pair("key", true);
        verify get_first(p2) == "key";
        verify get_second(p2);

        print("Multiple Type Params Pair OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Multiple Type Params Pair OK" in res.stdout

# ---------------------------------------------------------------------------
# 4. Identity and Generic Computation
# ---------------------------------------------------------------------------

def test_generic_identity_function_e2e():
    source = """
    fn id<T>(x: T) -> T {
        return x;
    }

    fn main() -> int {
        verify id(123) == 123;
        verify id("hello") == "hello";
        verify id(true);
        print("Generic Identity OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Generic Identity OK" in res.stdout

def test_generic_and_match_combined_e2e():
    source = """
    struct ResultBox<T> {
        code: int,
        val: T
    }

    fn inspect_result<T>(r: ResultBox<T>, fallback: T) -> T {
        return match r.code {
            0 => r.val,
            _ => fallback
        };
    }

    fn main() -> int {
        let r1 = ResultBox<str> { code: 0, val: "success_payload" };
        let r2 = ResultBox<str> { code: 500, val: "internal_error" };

        let v1 = inspect_result(r1, "default");
        let v2 = inspect_result(r2, "default");

        verify v1 == "success_payload";
        verify v2 == "default";

        print("Generic and Match Combined OK");
        return 0;
    }
    """
    res = run_axiom(source)
    assert res.returncode == 0
    assert "Generic and Match Combined OK" in res.stdout

# ---------------------------------------------------------------------------
# 5. Type Checking Errors (Negative Tests)
# ---------------------------------------------------------------------------

def test_generic_function_call_type_mismatch():
    source = """
    fn wrap<T>(item: T) -> T {
        return item;
    }

    fn main() -> int {
        let x = wrap<int>("not an integer");
        return 0;
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "tip uyumsuzlugu" in str(exc_info.value).lower()

def test_generic_struct_field_type_mismatch():
    source = """
    struct Box<T> {
        val: T
    }

    fn main() -> int {
        let b = Box<int> { val: "should_be_int" };
        return 0;
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "bekliyor" in str(exc_info.value).lower()

def test_generic_wrong_number_of_type_params():
    source = """
    struct Pair<T, U> {
        first: T,
        second: U
    }

    fn main() -> int {
        let p = Pair<int> { first: 1, second: 2 };
        return 0;
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "tip parametresi bekliyor" in str(exc_info.value)
