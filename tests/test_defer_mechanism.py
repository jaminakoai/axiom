"""
Axiom Programming Language (λx) - Deterministik Kapsam Temizliği (Defer) Test Paketi
FAZ 1.1 kapsamındaki LIFO scope-exit, erken dönüş garantisi ve kaynak yönetimi mekanizmalarını doğrular.
"""
import os
import subprocess
import tempfile
from pathlib import Path
import pytest

from axiom.cli import compile_axiom_source, find_c_compiler
from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.checker import TypeChecker, SemanticError
from axiom.ast_nodes import DeferStmt, Block, FunctionCall, PrintStmt

AXIOM_ROOT = Path(__file__).resolve().parent.parent
AXIOMC_BIN = AXIOM_ROOT / "bin" / "axiomc"

def compile_and_run(source_code: str, prove: bool = True):
    """Axiom kaynak kodunu C99 hedefine derler, GCC/Clang ile yerel ikili oluşturur ve çalıştırır."""
    c_code = compile_axiom_source(source_code, prove=prove)
    cc = find_c_compiler()

    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        res_cc = subprocess.run([cc, "-O2", "-pthread", c_path, "-o", bin_path], capture_output=True, text=True)
        if res_cc.returncode != 0:
            raise RuntimeError(f"C Derleyici Hatasi:\n{res_cc.stderr}\nUretilen C Kodu:\n{c_code}")

        res_exec = subprocess.run([bin_path], capture_output=True, text=True)
        return res_exec
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)


# =========================================================================
# 1. Lexer, Parser ve Checker Birim Testleri
# =========================================================================

def test_defer_lexer_keyword():
    """'defer' anahtar kelimesinin lexer tarafından doğru Token('DEFER') olarak tanındığını doğrular."""
    source = "defer print(1);"
    tokens = Lexer(source).tokenize()
    assert tokens[0].type == 'DEFER'
    assert tokens[0].value == 'defer'


def test_defer_parser_ast_nodes():
    """Parser'ın 'defer <stmt>;' ve 'defer { <block> }' sözdizimini DeferStmt olarak ayrıştırdığını doğrular."""
    # 1. Tek deyim
    source_single = "fn test() { defer print(42); }"
    prog1 = Parser(Lexer(source_single).tokenize()).parse()
    fn1 = prog1.declarations[0]
    first_stmt = fn1.body.statements[0]
    assert isinstance(first_stmt, DeferStmt)
    assert isinstance(first_stmt.stmt, PrintStmt)

    # 2. Blok deyim
    source_block = "fn test() { defer { let x = 10; print(x); } }"
    prog2 = Parser(Lexer(source_block).tokenize()).parse()
    fn2 = prog2.declarations[0]
    defer_blk = fn2.body.statements[0]
    assert isinstance(defer_blk, DeferStmt)
    assert isinstance(defer_blk.stmt, Block)
    assert len(defer_blk.stmt.statements) == 2


def test_defer_semantic_typechecker():
    """Checker'ın defer gövdesindeki değişken ve tip geçerliliğini denetlediğini doğrular."""
    # Tanımsız değişken defer içinde hata vermelidir
    invalid_source = "fn test() -> void { defer print(unresolved_var); }"
    prog = Parser(Lexer(invalid_source).tokenize()).parse()
    checker = TypeChecker()
    with pytest.raises(SemanticError) as exc_info:
        checker.check(prog)
    assert "Tanimlanmamis degisken: 'unresolved_var'" in str(exc_info.value)

    # Geçerli defer başarıyla geçmelidir
    valid_source = "fn test() -> void { let x = 100; defer print(x); }"
    prog_ok = Parser(Lexer(valid_source).tokenize()).parse()
    checker_ok = TypeChecker()
    checker_ok.check(prog_ok)


# =========================================================================
# 2. LIFO (Ters Sıra) Yürütme Testleri
# =========================================================================

def test_defer_lifo_execution_order():
    """Çoklu defer ifadelerinin LIFO (ters sırada) yürütüldüğünü e2e olarak doğrular."""
    source = """
    fn main() -> int {
        print("PROGRAM_START");
        defer print("DEFER_1_FIRST");
        defer print("DEFER_2_MIDDLE");
        defer print("DEFER_3_LAST");
        print("PROGRAM_END");
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]

    expected = [
        "PROGRAM_START",
        "PROGRAM_END",
        "DEFER_3_LAST",
        "DEFER_2_MIDDLE",
        "DEFER_1_FIRST"
    ]
    assert lines == expected, f"LIFO siralamasi hatali! Alinan cikti: {lines}"


def test_defer_block_lifo_execution():
    """Blok defer ifadelerinin ve karışık defer deyimlerinin LIFO sırasını doğrular."""
    source = """
    fn main() -> int {
        defer print("A");
        defer {
            print("B1");
            print("B2");
        }
        defer print("C");
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]

    # LIFO sırası:
    # 1. defer C -> C
    # 2. defer { B1; B2; } -> B1, B2
    # 3. defer A -> A
    expected = ["C", "B1", "B2", "A"]
    assert lines == expected, f"Blok defer siralamasi hatali! Alinan: {lines}"


# =========================================================================
# 3. Erken Return İçeren Dallarda Defer Garantisi Testleri
# =========================================================================

def test_defer_early_return_branches():
    """Erken return içeren if/else dallarında sadece o ana kadar kayıtlı defer'lerin çalıştığını doğrular."""
    source = """
    fn branch_eval(mode: int) -> int {
        defer print("ROOT_DEFER");
        if mode == 1 {
            defer print("MODE_1_DEFER");
            return 101;
        } else if mode == 2 {
            defer print("MODE_2_DEFER");
            return 202;
        }
        defer print("FALLTHROUGH_DEFER");
        return 303;
    }

    fn main() -> int {
        print("--- TEST 1 ---");
        let r1 = branch_eval(1);
        print("RET 1 =", r1);

        print("--- TEST 2 ---");
        let r2 = branch_eval(2);
        print("RET 2 =", r2);

        print("--- TEST 3 ---");
        let r3 = branch_eval(3);
        print("RET 3 =", r3);
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]

    expected = [
        "--- TEST 1 ---",
        "MODE_1_DEFER",
        "ROOT_DEFER",
        "RET 1 = 101",
        "--- TEST 2 ---",
        "MODE_2_DEFER",
        "ROOT_DEFER",
        "RET 2 = 202",
        "--- TEST 3 ---",
        "FALLTHROUGH_DEFER",
        "ROOT_DEFER",
        "RET 3 = 303"
    ]
    assert lines == expected, f"Erken return dallari defer sirasi hatali! Alinan:\n{lines}"


def test_defer_nested_scope_exit():
    """İç içe bloklardan (nested scopes) çıkışta kapsam defer'lerinin doğru anlarda çalıştığını doğrular."""
    source = """
    fn main() -> int {
        defer print("FUNC_SCOPE_END");
        print("OUTER_START");
        {
            defer print("INNER_SCOPE_END");
            print("INNER_BODY");
        }
        print("OUTER_AFTER_INNER");
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]

    expected = [
        "OUTER_START",
        "INNER_BODY",
        "INNER_SCOPE_END",
        "OUTER_AFTER_INNER",
        "FUNC_SCOPE_END"
    ]
    assert lines == expected, f"İç içe kapsam defer sirasi hatali! Alinan:\n{lines}"


# =========================================================================
# 4. Kaynak Kapatma (File / Socket Simülasyonu) Testleri
# =========================================================================

def test_defer_resource_cleanup_simulation():
    """Dosya/soket handle açma-kapama simülasyonunda hata durumunda bile defer ile sızıntısız temizliği doğrular."""
    source = """
    fn open_mock_file(path: str, id: int) -> int {
        print("OPEN:", path, "ID:", id);
        return id;
    }

    fn close_mock_file(fd: int) -> void {
        print("CLOSE_FD:", fd);
    }

    fn process_files(should_fail: bool) -> int {
        let f1 = open_mock_file("/etc/config", 101);
        defer close_mock_file(f1);

        if should_fail {
            print("HATA: Erken cikis yapiliyor!");
            return -1;
        }

        let f2 = open_mock_file("/var/log", 102);
        defer close_mock_file(f2);

        print("ISLEM_TAMAMLANDI");
        return 0;
    }

    fn main() -> int {
        print("=== SENARYO 1 (HATA ILE ERKEN DONUS) ===");
        let r1 = process_files(true);
        verify r1 == -1;

        print("=== SENARYO 2 (BASARILI ISLEM) ===");
        let r2 = process_files(false);
        verify r2 == 0;

        print("TUM KAYNAKLAR SIFIR KACAKLA TEMIZLENDI!");
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "TUM KAYNAKLAR SIFIR KACAKLA TEMIZLENDI!" in res.stdout
    assert "CLOSE_FD: 101" in res.stdout
    assert "CLOSE_FD: 102" in res.stdout


# =========================================================================
# 5. Dönen Değerin Defer'den Önce Değerlendirilmesi ve Sözleşme Entegrasyonu
# =========================================================================

def test_defer_return_value_evaluated_before_defer():
    """Return ifadesinin değerinin defer blokları çalışmadan önce değişkene alındığını garanti eder."""
    source = """
    fn compute_with_defer() -> int {
        let mut x = 42;
        defer {
            x = 999;
            print("DEFER_MUTATION_X =", x);
        }
        return x;
    }

    fn main() -> int {
        let result = compute_with_defer();
        print("FINAL_RETURNED_VAL =", result);
        verify result == 42;
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "DEFER_MUTATION_X = 999" in res.stdout
    assert "FINAL_RETURNED_VAL = 42" in res.stdout


def test_defer_with_ensures_contract():
    """Fonksiyon ensures sözleşmeleri ile defer mekanizmasının birlikte sorunsuz çalıştığını doğrular."""
    source = """
    fn safe_compute(n: int) -> int
        requires n > 0
        ensures return > n
    {
        defer print("CONTRACT_FUNCTION_CLEANUP");
        return n * 2;
    }

    fn main() -> int {
        let val = safe_compute(10);
        print("VAL =", val);
        verify val == 20;
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "CONTRACT_FUNCTION_CLEANUP" in res.stdout
    assert "VAL = 20" in res.stdout


# =========================================================================
# 6. Self-Hosted Derleyici (bin/axiomc) ile Defer Derleme Testi
# =========================================================================

def test_self_hosted_compiler_defer(tmp_path):
    """Axiom ile yazılmış bağımsız yerel binary 'bin/axiomc'nin defer ifadelerini doğru derlediğini doğrular."""
    assert AXIOMC_BIN.exists(), f"bin/axiomc bulunamadi: {AXIOMC_BIN}"

    ax_code = """
    fn test_native_defer() -> int {
        defer print("NATIVE_DEFER_1");
        defer print("NATIVE_DEFER_2");
        print("NATIVE_EXECUTION");
        return 77;
    }

    fn main() -> int {
        let r = test_native_defer();
        print("RESULT =", r);
        return 0;
    }
    """
    test_src = tmp_path / "test_defer_native.ax"
    test_src.write_text(ax_code, encoding="utf-8")
    test_bin = tmp_path / "test_defer_elf"

    # bin/axiomc build test_defer_native.ax -o test_defer_elf
    build_cmd = [str(AXIOMC_BIN), "build", str(test_src), "-o", str(test_bin)]
    build_res = subprocess.run(build_cmd, capture_output=True, text=True)
    assert build_res.returncode == 0, f"axiomc build basarisiz oldu:\n{build_res.stderr}\n{build_res.stdout}"
    assert test_bin.exists()

    run_res = subprocess.run([str(test_bin)], capture_output=True, text=True)
    assert run_res.returncode == 0
    lines = [l.strip() for l in run_res.stdout.strip().splitlines() if l.strip()]

    expected = [
        "NATIVE_EXECUTION",
        "NATIVE_DEFER_2",
        "NATIVE_DEFER_1",
        "RESULT = 77"
    ]
    assert lines == expected, f"Self-hosted native derleyici defer sirasi hatali! Alinan:\n{lines}"
