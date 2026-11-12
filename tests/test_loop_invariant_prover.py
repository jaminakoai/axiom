"""
Unit and Integration Tests for Axiom (λx) Loop Invariant Syntax & Z3 SMT Floyd-Hoare Induction Prover
"""
import pytest
from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.checker import TypeChecker
from axiom.z3_prover import Z3Prover
from axiom.prover import ProofError

def test_while_loop_valid_invariant_proven():
    code = """
    fn sum_to_n(n: int) -> int
        requires n >= 0
        ensures return >= 0
    {
        let mut i = 0;
        let mut total = 0;
        while (i < n)
            invariant i >= 0 and i <= n and total >= 0
        {
            total = total + i;
            i = i + 1;
        }
        return total;
    }
    """
    tokens = Lexer(code).tokenize()
    prog = Parser(tokens).parse()
    TypeChecker().check(prog)

    prover = Z3Prover()
    summary = prover.verify_program(prog)

    assert summary.status == "PROVED"
    assert summary.has_loops is False
    assert summary.verified_functions == 1
    assert summary.proved_theorems >= 3  # base case, inductive step, postcondition
    assert any("SESLİ VE KANITLANMIŞTIR (PROVEN)" in d for d in summary.details)

def test_while_loop_base_case_counterexample():
    code = """
    fn invalid_base(n: int) -> int
        requires n >= 0
        ensures return >= 0
    {
        let mut i = 0;
        let mut total = 0;
        while (i < n)
            invariant total > 10
        {
            total = total + i;
            i = i + 1;
        }
        return total;
    }
    """
    tokens = Lexer(code).tokenize()
    prog = Parser(tokens).parse()
    TypeChecker().check(prog)

    prover = Z3Prover()
    with pytest.raises(ProofError) as exc_info:
        prover.verify_program(prog)

    err_msg = str(exc_info.value)
    assert "temel adımda (döngü girişinde) sağlanamadı" in err_msg
    assert exc_info.value.counterexample != ""
    assert "total = 0" in exc_info.value.counterexample

def test_while_loop_inductive_step_counterexample():
    code = """
    fn invalid_step(n: int) -> int
        requires n > 0
        ensures return >= 0
    {
        let mut i = 0;
        let mut total = 0;
        while (i < n)
            invariant total >= 0
        {
            total = total - 1;
            i = i + 1;
        }
        return total;
    }
    """
    tokens = Lexer(code).tokenize()
    prog = Parser(tokens).parse()
    TypeChecker().check(prog)

    prover = Z3Prover()
    with pytest.raises(ProofError) as exc_info:
        prover.verify_program(prog)

    err_msg = str(exc_info.value)
    assert "tümevarım adımında (döngü gövdesi sonunda) korunamadı" in err_msg
    assert exc_info.value.counterexample != ""

def test_while_loop_postcondition_violation_counterexample():
    code = """
    fn invalid_post(n: int) -> int
        requires n >= 0
        ensures return > 500
    {
        let mut i = 0;
        let mut total = 0;
        while (i < n)
            invariant i >= 0 and i <= n and total >= 0
        {
            total = total + i;
            i = i + 1;
        }
        return total;
    }
    """
    tokens = Lexer(code).tokenize()
    prog = Parser(tokens).parse()
    TypeChecker().check(prog)

    prover = Z3Prover()
    with pytest.raises(ProofError) as exc_info:
        prover.verify_program(prog)

    err_msg = str(exc_info.value)
    assert "son koşul sözleşmesi (ensures) ihlal edildi" in err_msg
    assert exc_info.value.counterexample != ""
    assert "return = 0" in exc_info.value.counterexample

def test_for_range_loop_with_invariant_proven():
    code = """
    fn sum_for(n: int) -> int
        requires n >= 0
        ensures return >= 0
    {
        let mut total = 0;
        for i in 0..n
            invariant total >= 0 and i >= 0 and i <= n
        {
            total = total + i;
        }
        return total;
    }
    """
    tokens = Lexer(code).tokenize()
    prog = Parser(tokens).parse()
    TypeChecker().check(prog)

    prover = Z3Prover()
    summary = prover.verify_program(prog)

    assert summary.status == "PROVED"
    assert summary.verified_functions == 1
    assert any("SESLİ VE KANITLANMIŞTIR (PROVEN)" in d for d in summary.details)

def test_loop_without_invariant_remains_partial_unknown():
    code = """
    fn unproven_loop(n: int) -> int
        requires n >= 0
        ensures return >= 0
    {
        let mut i = 0;
        let mut total = 0;
        while (i < n) {
            total = total + i;
            i = i + 1;
        }
        return total;
    }
    """
    tokens = Lexer(code).tokenize()
    prog = Parser(tokens).parse()
    TypeChecker().check(prog)

    prover = Z3Prover()
    summary = prover.verify_program(prog)

    assert summary.has_loops is True
    assert "unproven_loop" in summary.loop_functions
    assert summary.status == "PARTIAL_VERIFICATION_UNKNOWN"

def test_multiple_invariants_syntax():
    code = """
    fn multi_inv(n: int) -> int
        requires n >= 0
        ensures return >= 0
    {
        let mut i = 0;
        let mut total = 0;
        while (i < n)
            invariant i >= 0 and i <= n;
            invariant total >= 0;
        {
            total = total + i;
            i = i + 1;
        }
        return total;
    }
    """
    tokens = Lexer(code).tokenize()
    prog = Parser(tokens).parse()
    assert len(prog.declarations[0].body.statements[2].invariants) == 2
    TypeChecker().check(prog)

    prover = Z3Prover()
    summary = prover.verify_program(prog)
    assert summary.status == "PROVED"
    assert any("SESLİ VE KANITLANMIŞTIR (PROVEN)" in d for d in summary.details)
