"""
Unit tests for Axiom Interactive REPL
"""
import pytest
from axiom.cli import REPLSession

def test_repl_basic_expression():
    session = REPLSession()
    out = session.evaluate("15 + 27")
    assert out == "42"

def test_repl_string_expression():
    session = REPLSession()
    out = session.evaluate('"Hello, " + "Axiom!"')
    assert out == "Hello, Axiom!"

def test_repl_variable_state_persistence():
    session = REPLSession()
    out1 = session.evaluate("let x = 100")
    assert out1 is None or out1 == ""
    out2 = session.evaluate("x + 25")
    assert out2 == "125"

def test_repl_mutable_assignment():
    session = REPLSession()
    session.evaluate("let mut counter = 10")
    session.evaluate("counter = counter + 5")
    out = session.evaluate("counter")
    assert out == "15"

def test_repl_function_definition_and_call():
    session = REPLSession()
    fn_def = """
fn multiply(a: int, b: int) -> int
    requires a >= 0 and b >= 0
{
    return a * b
}
"""
    out_def = session.evaluate(fn_def)
    assert out_def is None or out_def == ""
    out_call = session.evaluate("multiply(6, 7)")
    assert out_call == "42"

def test_repl_struct_definition_and_usage():
    session = REPLSession()
    struct_def = """
struct Vector2 {
    x: int,
    y: int
}
"""
    session.evaluate(struct_def)
    session.evaluate("let v = Vector2 { x: 3, y: 4 }")
    out = session.evaluate("v.x + v.y")
    assert out == "7"

def test_repl_file_io_builtins(tmp_path):
    session = REPLSession()
    test_file = str(tmp_path / "repl_io.txt")
    out_w = session.evaluate(f'file_write("{test_file}", "REPL_PAYLOAD")')
    assert out_w == "true"

    out_ex = session.evaluate(f'file_exists("{test_file}")')
    assert out_ex == "true"

    out_r = session.evaluate(f'file_read("{test_file}")')
    assert out_r == "REPL_PAYLOAD"

def test_repl_error_handling_graceful():
    session = REPLSession()
    # Syntax / parse error
    err_out = session.evaluate("let = = = invalid")
    assert "Hata:" in err_out

    # Semantic error
    err_type = session.evaluate('let n: int = "string_mismatch"')
    assert "Hata:" in err_type

    # Session should still be healthy
    session.evaluate("let safe = 99")
    ok_out = session.evaluate("safe + 1")
    assert ok_out == "100"

def test_repl_empty_and_whitespace():
    session = REPLSession()
    assert session.evaluate("") is None
    assert session.evaluate("   \n\t  ") is None
