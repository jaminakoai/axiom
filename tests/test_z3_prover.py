"""
Axiom Programming Language (λx) - Z3 SMT Theorem Prover Unit and E2E Tests
"""
import pytest
import subprocess
import tempfile
import os
from pathlib import Path

from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.checker import TypeChecker
from axiom.prover import ProofError
from axiom.z3_prover import Z3Prover

def run_z3_prover(source: str):
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    TypeChecker().check(program)
    prover = Z3Prover()
    return prover.verify_program(program)

def test_z3_prover_basic_positive():
    code = """
    fn identity(x: int) -> int
        requires x >= 0
        ensures return >= 0
    {
        return x;
    }
    """
    summary = run_z3_prover(code)
    assert summary.verified_functions == 1
    assert summary.proved_theorems >= 1

def test_z3_prover_postcondition_violation_counterexample():
    code = """
    fn faulty(x: int) -> int
        requires x >= 0
        ensures return > 0
    {
        return x;
    }
    """
    with pytest.raises(ProofError) as exc_info:
        run_z3_prover(code)
    err = str(exc_info.value)
    assert "ensures" in err
    assert "x = 0" in err or "return = 0" in err

def test_z3_prover_if_else_branches():
    code = """
    fn abs_val(x: int) -> int
        requires true
        ensures return >= 0
    {
        if x < 0 {
            return 0 - x;
        } else {
            return x;
        }
    }
    """
    summary = run_z3_prover(code)
    assert summary.verified_functions == 1
    assert summary.proved_theorems == 2

def test_z3_prover_division_by_zero_counterexample():
    code = """
    fn calc(a: int, b: int) -> int
        requires a > 0
    {
        return a / b;
    }
    """
    with pytest.raises(ProofError) as exc_info:
        run_z3_prover(code)
    err = str(exc_info.value)
    assert "sıfıra bölme" in err.lower() or "division-by-zero" in err.lower()
    assert "b = 0" in err

def test_z3_prover_safe_division():
    code = """
    fn safe_div(a: int, b: int) -> int
        requires a >= 0 and b > 0
        ensures return >= 0
    {
        return a / b;
    }
    """
    summary = run_z3_prover(code)
    assert summary.verified_functions == 1
    assert summary.safe_divisions >= 1

def test_z3_prover_callsite_contract_violation():
    code = """
    fn validate_port(port: int) -> bool
        requires port >= 1 and port <= 65535
    {
        return true;
    }

    fn main() -> void {
        validate_port(70000);
    }
    """
    with pytest.raises(ProofError) as exc_info:
        run_z3_prover(code)
    err = str(exc_info.value)
    assert "ön koşulunu (requires) ihlal ediyor" in err
    assert "port = 70000" in err

def test_z3_prover_callsite_contract_valid():
    code = """
    fn validate_port(port: int) -> bool
        requires port >= 1 and port <= 65535
    {
        return true;
    }

    fn main() -> void {
        validate_port(443);
    }
    """
    summary = run_z3_prover(code)
    assert summary.verified_functions == 2

def test_z3_prover_verify_statement_pass():
    code = """
    fn test_math() -> void {
        let x = 10;
        let y = 20;
        verify x + y == 30, "Toplam 30 olmali";
    }
    """
    summary = run_z3_prover(code)
    assert summary.verified_functions == 1

def test_z3_prover_verify_statement_fail():
    code = """
    fn test_math() -> void {
        let x = 10;
        let y = 20;
        verify x + y == 35, "Toplam 35 olmali";
    }
    """
    with pytest.raises(ProofError) as exc_info:
        run_z3_prover(code)
    err = str(exc_info.value)
    assert "Toplam 35 olmali" in err or "verify" in err

def test_z3_prover_math_builtins():
    code = """
    fn test_builtins(a: int, b: int) -> int
        requires a >= 0 and b >= 0
        ensures return >= 0
    {
        let m = math_max(a, b);
        let n = math_min(a, b);
        let diff = math_abs(m - n);
        return diff;
    }
    """
    summary = run_z3_prover(code)
    assert summary.verified_functions == 1
    assert summary.proved_theorems >= 1

def test_z3_prover_unsatisfiable_preconditions():
    code = """
    fn impossible(x: int) -> int
        requires x > 10 and x < 5
    {
        return x;
    }
    """
    with pytest.raises(ProofError) as exc_info:
        run_z3_prover(code)
    err = str(exc_info.value)
    assert "çelişkili" in err or "unsatisfiable" in err

def test_z3_prover_emit_smt2():
    code = """
    fn add(x: int, y: int) -> int
        requires x > 0 and y > 0
        ensures return > 0
    {
        return x + y;
    }
    """
    tokens = Lexer(code).tokenize()
    program = Parser(tokens).parse()
    TypeChecker().check(program)
    prover = Z3Prover()
    smt2 = prover.emit_smt2(program)
    assert "(set-logic ALL)" in smt2
    assert "(check-sat)" in smt2
    assert "declare-fun" in smt2 or "assert" in smt2

def test_z3_cli_prove_smt_e2e(tmp_path):
    f = tmp_path / "test.ax"
    f.write_text("""
    fn inc(x: int) -> int
        requires x >= 0
        ensures return > 0
    {
        return x + 1;
    }
    """, encoding="utf-8")

    axiom_bin = Path(__file__).resolve().parent.parent / "bin" / "axiom"
    res = subprocess.run([str(axiom_bin), "prove", str(f), "--smt"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Statik Matematiksel İspat Başarılı (Z3 SMT Motoru)" in res.stdout
    assert "UNSAT" in res.stdout

def test_z3_cli_emit_smt_e2e(tmp_path):
    f = tmp_path / "test.ax"
    f.write_text("""
    fn double_num(x: int) -> int
        requires x > 0
        ensures return > 0
    {
        return x * 2;
    }
    """, encoding="utf-8")

    axiom_bin = Path(__file__).resolve().parent.parent / "bin" / "axiom"
    res = subprocess.run([str(axiom_bin), "emit-smt", str(f)], capture_output=True, text=True)
    assert res.returncode == 0
    assert "(set-logic ALL)" in res.stdout
    assert "(check-sat)" in res.stdout

def test_z3_prover_simd_and_array_len():
    code = """
    fn scan(ports: int[]) -> int
        requires len(ports) > 0
        ensures return >= 0
    {
        return simd_scan_match(ports, 80);
    }
    """
    summary = run_z3_prover(code)
    assert summary.verified_functions == 1
    assert summary.proved_theorems >= 1

def test_z3_prover_complex_boolean_logic():
    code = """
    fn logic_gate(a: bool, b: bool) -> bool
        requires (a or b) and not (a and b)
        ensures return == true
    {
        return true;
    }
    """
    summary = run_z3_prover(code)
    assert summary.verified_functions == 1
    assert summary.proved_theorems >= 1
