"""
Axiom Audit Remediation Tests - Aşama 1 & 2
Tip Sistemi Sıkılaştırma, Definite Return, İç İçe Return ensures,
Prover Döngü Semantiği ve UTF-8 Karakter Sayımı Testleri
"""
import pytest
import subprocess
import tempfile
import os
from pathlib import Path

from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.checker import TypeChecker, SemanticError
from axiom.prover import SymbolicProver
from axiom.z3_prover import Z3Prover
from axiom.codegen_c import CCodeGenerator
from axiom.codegen_llvm import LLVMCodeGenerator

def check_code(source: str):
    tokens = Lexer(source).tokenize()
    prog = Parser(tokens).parse()
    checker = TypeChecker()
    checker.check(prog)
    return prog

# -------------------------------------------------------------
# 1. Tip Sistemi Sıkılaştırması
# -------------------------------------------------------------

def test_type_mismatch_comparison_rejected():
    # int < str derleme anında reddedilmeli
    code1 = """
    let x = 10 < "abc";
    """
    with pytest.raises(SemanticError) as exc_info:
        check_code(code1)
    assert "karsilastirmasi uyumsuz tipler arasinda yapilamaz" in str(exc_info.value)

    # str > int derleme anında reddedilmeli
    code2 = """
    let x = "hello" > 42;
    """
    with pytest.raises(SemanticError) as exc_info:
        check_code(code2)
    assert "karsilastirmasi uyumsuz tipler arasinda yapilamaz" in str(exc_info.value)

    # int == str derleme anında reddedilmeli
    code3 = """
    let x = 10 == "10";
    """
    with pytest.raises(SemanticError) as exc_info:
        check_code(code3)
    assert "esitlik karsilastirmasi uyumsuz tipler arasinda yapilamaz" in str(exc_info.value)

def test_valid_comparisons_allowed():
    # Sayısal ve metin karşılaştırmaları geçerli olmalı
    code = """
    let a = 10 < 20;
    let b = 3.14 >= 2.0;
    let c = 5 < 10.5;
    let d = "aaa" < "bbb";
    let e = 10 == 10;
    let f = "test" == "test";
    """
    check_code(code)

# -------------------------------------------------------------
# 2. Definite Return Analizi
# -------------------------------------------------------------

def test_definite_return_missing_in_function():
    # Dönüş tipi int ama return yok
    code1 = """
    fn calc(x: int) -> int {
        let y = x + 1;
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_code(code1)
    assert "tum kod dallarinda return bulunmuyor" in str(exc_info.value)

def test_definite_return_missing_in_if_else():
    # else dalında return yok
    code = """
    fn check_positive(x: int) -> int {
        if x > 0 {
            return 1;
        } else {
            let dummy = 0;
        }
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_code(code)
    assert "tum kod dallarinda return bulunmuyor" in str(exc_info.value)

def test_definite_return_missing_no_else():
    # else kolu hiç yok
    code = """
    fn check_positive(x: int) -> int {
        if x > 0 {
            return 1;
        }
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_code(code)
    assert "tum kod dallarinda return bulunmuyor" in str(exc_info.value)

def test_definite_return_valid():
    # Her dalda return var
    code = """
    fn abs_val(x: int) -> int {
        if x < 0 {
            return -x;
        } else {
            return x;
        }
    }

    fn simple_ret() -> int {
        return 42;
    }

    fn void_fn(x: int) -> void {
        let y = x;
    }
    """
    check_code(code)

# -------------------------------------------------------------
# 3. İç İçe Return ensures Sarmalaması
# -------------------------------------------------------------

def test_nested_return_ensures_wrapping_in_c():
    code = """
    fn classify(x: int) -> int
        ensures return > 0
    {
        if x > 10 {
            return 100;
        } else {
            return 0; // Bu ensures (return > 0) ihlal eder!
        }
    }
    """
    prog = check_code(code)
    codegen = CCodeGenerator()
    c_out = codegen.generate(prog)

    # Her iki dönüş dalının da axiom_contract_fail("ENSURES") ile sarmalandığını doğrula
    assert c_out.count('axiom_contract_fail("ENSURES"') >= 2

def test_nested_return_ensures_runtime_enforcement(tmp_path):
    axiom_code = """
    fn classify(x: int) -> int
        ensures return > 0
    {
        if x > 10 {
            return 100;
        } else {
            return 0; // İhlal!
        }
    }

    fn main() -> int {
        return classify(5);
    }
    """
    prog = check_code(axiom_code)
    runtime_path = Path(__file__).resolve().parent.parent / "axiom" / "runtime.h"
    codegen = CCodeGenerator(runtime_header_path=str(runtime_path))
    c_code = codegen.generate(prog)

    c_file = tmp_path / "test_nested_ensures.c"
    c_file.write_text(c_code, encoding="utf-8")
    bin_file = tmp_path / "test_nested_ensures"

    # Derle
    compile_res = subprocess.run(["gcc", "-O0", str(c_file), "-o", str(bin_file)], capture_output=True, text=True)
    assert compile_res.returncode == 0, f"Derleme hatası: {compile_res.stderr}"

    # Çalıştır -> Son-koşul (ENSURES) ihlali ile patlamalı
    run_res = subprocess.run([str(bin_file)], capture_output=True, text=True)
    assert run_res.returncode != 0
    assert "ENSURES" in run_res.stderr
    assert "classify" in run_res.stderr

# -------------------------------------------------------------
# 4. Prover Döngü Semantiği (Kesin İspat yerine Kısmi Doğrulama / Unknown)
# -------------------------------------------------------------

def test_prover_loop_unknown_warning():
    code = """
    fn sum_loop(n: int) -> int
        requires n > 0
        ensures return > 0
    {
        let mut total = 0;
        let mut i = 0;
        while i < n {
            total = total + 1;
            i = i + 1;
        }
        return total;
    }
    """
    tokens = Lexer(code).tokenize()
    prog = Parser(tokens).parse()
    TypeChecker().check(prog)

    # SymbolicProver testi
    sym_prover = SymbolicProver()
    sym_summary = sym_prover.verify_program(prog)
    assert sym_summary.has_loops is True
    assert "sum_loop" in sym_summary.loop_functions
    assert sym_summary.status == "PARTIAL_VERIFICATION_UNKNOWN"

    # Z3Prover testi
    z3_prover = Z3Prover()
    z3_summary = z3_prover.verify_program(prog)
    assert z3_summary.has_loops is True
    assert "sum_loop" in z3_summary.loop_functions
    assert z3_summary.status == "PARTIAL_VERIFICATION_UNKNOWN"

def test_cli_prove_loop_unknown_exit_code(tmp_path):
    f = tmp_path / "loop_fn.ax"
    f.write_text("""
    fn loop_fn(x: int) -> int
        requires x > 0
        ensures return > 0
    {
        let mut i = 0;
        while i < x {
            i = i + 1;
        }
        return i;
    }
    """, encoding="utf-8")

    axiom_bin = Path(__file__).resolve().parent.parent / "bin" / "axiom"
    res = subprocess.run([str(axiom_bin), "prove", str(f)], capture_output=True, text=True)
    assert res.returncode == 2
    assert "Kısmi Doğrulama / Döngü Nedeniyle Kanıtlanamadı (Unknown)" in res.stdout
    assert "Kesin İspat" not in res.stdout

# -------------------------------------------------------------
# 5. UTF-8 Karakter Sayımı & str_byte_len
# -------------------------------------------------------------

def test_utf8_char_length_and_byte_length_c_e2e(tmp_path):
    axiom_code = """
    fn main() -> int {
        let text = "ğüşiöç";
        let c_len = len(text);
        let b_len = str_byte_len(text);
        let s_len = str_len(text);

        print(c_len);
        print(b_len);
        print(s_len);

        verify c_len == 6;
        verify s_len == 6;
        verify b_len == 11;
        return 0;
    }
    """
    prog = check_code(axiom_code)
    runtime_path = Path(__file__).resolve().parent.parent / "axiom" / "runtime.h"
    codegen = CCodeGenerator(runtime_header_path=str(runtime_path))
    c_code = codegen.generate(prog)

    c_file = tmp_path / "test_utf8.c"
    c_file.write_text(c_code, encoding="utf-8")
    bin_file = tmp_path / "test_utf8"

    compile_res = subprocess.run(["gcc", "-O0", str(c_file), "-o", str(bin_file)], capture_output=True, text=True)
    assert compile_res.returncode == 0, f"Derleme hatası: {compile_res.stderr}"

    run_res = subprocess.run([str(bin_file)], capture_output=True, text=True)
    assert run_res.returncode == 0
    outputs = run_res.stdout.strip().splitlines()
    assert outputs[0] == "6"   # len("ğüşiöç") == 6
    assert outputs[1] == "11"  # str_byte_len("ğüşiöç") == 11 bayt (ğ:2, ü:2, ş:2, i:1, ö:2, ç:2)
    assert outputs[2] == "6"   # str_len("ğüşiöç") == 6
