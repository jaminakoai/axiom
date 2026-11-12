"""
Static Mathematical Prover & Symbolic Contract Verifier Tests for Axiom (λx)
"""
import pytest
from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.checker import TypeChecker
from axiom.prover import SymbolicProver, ProofError, Interval, INF, NEGINF
from axiom.cli import compile_axiom_source

def verify_code(source: str):
    lexer = Lexer(source)
    parser = Parser(lexer.tokenize())
    program = parser.parse()
    checker = TypeChecker()
    checker.check(program)
    prover = SymbolicProver()
    return prover.verify_program(program)

def test_interval_arithmetic():
    i1 = Interval(10, 20)
    i2 = Interval(5, 10)

    # Addition
    i_add = i1 + i2
    assert i_add.min == 15 and i_add.max == 30

    # Subtraction
    i_sub = i1 - i2
    assert i_sub.min == 0 and i_sub.max == 15

    # Multiplication
    i_mul = i1 * i2
    assert i_mul.min == 50 and i_mul.max == 200

    # Division
    i_div = i1 / i2
    assert i_div.min == 1.0 and i_div.max == 4.0

    # Intersection
    i_inter = i1.intersect(i2)
    assert i_inter.min == 10 and i_inter.max == 10

    # Point
    pt = Interval.point(42)
    assert pt.is_point
    assert pt.contains(42)
    assert not pt.contains(43)

def test_prover_valid_port_requires():
    source = """
    fn scan_port(port: int) -> int
        requires port >= 1 and port <= 65535
        ensures return >= 0
    {
        return 1;
    }

    fn main() -> int {
        let res = scan_port(80);
        return res;
    }
    """
    summary = verify_code(source)
    assert summary.verified_functions >= 2
    assert summary.verified_contracts >= 2

def test_prover_reject_negative_port():
    source = """
    fn scan_port(port: int) -> int
        requires port >= 1 and port <= 65535
    {
        return 1;
    }

    fn main() -> int {
        let res = scan_port(-5);
        return res;
    }
    """
    with pytest.raises(ProofError) as exc_info:
        verify_code(source)
    assert "kesin olarak ihlal edildi" in str(exc_info.value)
    assert "port = [-5, -5]" in str(exc_info.value)

def test_prover_reject_port_exceeding_max():
    source = """
    fn scan_port(port: int) -> int
        requires port >= 1 and port <= 65535
    {
        return 1;
    }

    fn main() -> int {
        let bad_port = 70000;
        let res = scan_port(bad_port);
        return res;
    }
    """
    with pytest.raises(ProofError) as exc_info:
        verify_code(source)
    assert "kesin olarak ihlal edildi" in str(exc_info.value)
    assert "port = [70000, 70000]" in str(exc_info.value)

def test_prover_reject_division_by_zero():
    source = """
    fn calc() -> int {
        let x = 100;
        let y = 0;
        let res = x / y;
        return res;
    }
    """
    with pytest.raises(ProofError) as exc_info:
        verify_code(source)
    assert "sıfıra bölme" in str(exc_info.value)

def test_prover_variable_range_propagation():
    source = """
    fn validate_age(age: int) -> bool
        requires age >= 18 and age <= 120
    {
        return true;
    }

    fn main() -> void {
        let base = 20;
        let bonus = 5;
        let age = base + bonus;
        validate_age(age);
    }
    """
    summary = verify_code(source)
    assert summary.verified_functions >= 2

def test_prover_variable_range_violation():
    source = """
    fn validate_age(age: int) -> bool
        requires age >= 18 and age <= 120
    {
        return true;
    }

    fn main() -> void {
        let age = 10 + 5;
        validate_age(age);
    }
    """
    with pytest.raises(ProofError) as exc_info:
        verify_code(source)
    assert "kesin olarak ihlal edildi" in str(exc_info.value)
    assert "age = [15, 15]" in str(exc_info.value)

def test_prover_loop_range_valid():
    source = """
    fn test_val(x: int) -> void
        requires x >= 0 and x <= 100
    {
    }

    fn main() -> void {
        for i in 0..100 {
            test_val(i);
        }
    }
    """
    summary = verify_code(source)
    assert summary.verified_functions >= 2

def test_prover_verify_statement_success():
    source = """
    fn main() -> void {
        let x = 50;
        let y = 20;
        let total = x + y;
        verify total == 70;
    }
    """
    summary = verify_code(source)
    assert summary.verified_assertions >= 1

def test_prover_verify_statement_failure():
    source = """
    fn main() -> void {
        let x = 10;
        verify x > 100;
    }
    """
    with pytest.raises(ProofError) as exc_info:
        verify_code(source)
    assert "'verify' assertion" in str(exc_info.value)

def test_prover_ensures_violation():
    source = """
    fn get_positive() -> int
        ensures return >= 0
    {
        return -10;
    }
    """
    with pytest.raises(ProofError) as exc_info:
        verify_code(source)
    assert "'ensures' sozlesmesini ihlal eden bir deger" in str(exc_info.value)

def test_compile_rejects_violating_contract_at_compile_time():
    source = """
    fn scan_port(p: int) -> int
        requires p >= 1 and p <= 65535
    {
        return 0;
    }

    fn main() -> int {
        return scan_port(99999);
    }
    """
    with pytest.raises(ProofError):
        compile_axiom_source(source)
