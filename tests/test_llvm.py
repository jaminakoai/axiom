"""
Axiom Programming Language (λx) - LLVM IR Backend Unit and E2E Tests
"""
import pytest
import subprocess
import tempfile
import os
from pathlib import Path

from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.checker import TypeChecker
from axiom.codegen_llvm import LLVMCodeGenerator

def compile_and_run_llvm(source: str) -> subprocess.CompletedProcess:
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    TypeChecker().check(program)
    codegen = LLVMCodeGenerator()
    llvm_ir = codegen.generate(program)

    with tempfile.NamedTemporaryFile(suffix=".ll", mode="w", delete=False) as fll, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as fbin:
        fll.write(llvm_ir)
        ll_path = fll.name
        bin_path = fbin.name

    runtime_c = str(Path(__file__).resolve().parent.parent / "axiom" / "axiom_llvm_runtime.c")
    try:
        compile_cmd = ["clang", "-O3", ll_path, runtime_c, "-pthread", "-lz", "-lssl", "-lcrypto", "-ldl", "-lm", "-o", bin_path]
        res = subprocess.run(compile_cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"LLVM Compilation failed:\n{res.stderr}\nIR:\n{llvm_ir}"
        run_res = subprocess.run([bin_path], capture_output=True, text=True)
        return run_res
    finally:
        if os.path.exists(ll_path):
            os.remove(ll_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

def test_llvm_hello_world():
    code = """
    fn main() -> void {
        print("Hello from LLVM backend!");
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "Hello from LLVM backend!" in res.stdout

def test_llvm_arithmetic_and_variables():
    code = """
    fn main() -> void {
        let a = 20;
        let b = 22;
        let c = a + b;
        print("Sum:", c);
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "Sum: 42" in res.stdout

def test_llvm_conditionals_if_else():
    code = """
    fn check_val(x: int) -> void {
        if x > 10 {
            print("GREATER");
        } else {
            print("LESS_OR_EQUAL");
        }
    }

    fn main() -> void {
        check_val(15);
        check_val(5);
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "GREATER" in res.stdout
    assert "LESS_OR_EQUAL" in res.stdout

def test_llvm_recursion_fibonacci():
    code = """
    fn fib(n: int) -> int {
        if n <= 1 {
            return n;
        }
        return fib(n - 1) + fib(n - 2);
    }

    fn main() -> void {
        let f = fib(9);
        print("Fib9:", f);
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "Fib9: 34" in res.stdout

def test_llvm_while_loop():
    code = """
    fn main() -> void {
        let mut i = 0;
        let mut sum = 0;
        while i < 5 {
            sum = sum + i;
            i = i + 1;
        }
        print("WhileSum:", sum);
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "WhileSum: 10" in res.stdout

def test_llvm_for_range_loop():
    code = """
    fn main() -> void {
        let mut total = 0;
        for k in 1..6 {
            total = total + k;
        }
        print("ForSum:", total);
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "ForSum: 15" in res.stdout

def test_llvm_array_and_len():
    code = """
    fn main() -> void {
        let arr = [100, 200, 300];
        print("Length:", len(arr));
        print("Elem0:", arr[0]);
        print("Elem1:", arr[1]);
        print("Elem2:", arr[2]);
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "Length: 3" in res.stdout
    assert "Elem0: 100" in res.stdout
    assert "Elem1: 200" in res.stdout
    assert "Elem2: 300" in res.stdout

def test_llvm_simd_vector_operations():
    code = """
    fn main() -> void {
        let a = [10, 20, 30, 40];
        let b = [1, 2, 3, 4];
        let sum_vec = simd_add_i64(a, b);
        let s = simd_sum_i64(sum_vec);
        print("SIMD Sum:", s);

        let ports = [80, 443, 80, 8080, 80];
        let hits = simd_scan_match(ports, 80);
        print("Hits80:", hits);
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "SIMD Sum: 110" in res.stdout
    assert "Hits80: 3" in res.stdout

def test_llvm_contract_violation_exit_101():
    code = """
    fn req_positive(x: int) -> int
        requires x > 0
    {
        return x;
    }

    fn main() -> void {
        req_positive(-5);
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 101

def test_llvm_cli_build_and_emit(tmp_path):
    f = tmp_path / "hello.ax"
    f.write_text("""
    fn main() -> void {
        print("Compiled via LLVM CLI!");
    }
    """, encoding="utf-8")

    out_bin = tmp_path / "hello_bin"
    axiom_bin = Path(__file__).resolve().parent.parent / "bin" / "axiom"

    # 1. emit-llvm
    res_emit = subprocess.run([str(axiom_bin), "emit-llvm", str(f)], capture_output=True, text=True)
    assert res_emit.returncode == 0
    assert "target triple" in res_emit.stdout
    assert "ax_main" in res_emit.stdout

    # 2. build --backend=llvm
    res_build = subprocess.run([str(axiom_bin), "build", str(f), "--backend=llvm", "-o", str(out_bin)], capture_output=True, text=True)
    assert res_build.returncode == 0
    assert "LLVM IR Backend" in res_build.stdout

    # 3. execute binary
    res_run = subprocess.run([str(out_bin)], capture_output=True, text=True)
    assert res_run.returncode == 0
    assert "Compiled via LLVM CLI!" in res_run.stdout

def test_llvm_string_ops():
    code = """
    fn main() -> void {
        let s1 = "axiom";
        let s2 = "_systems";
        let s3 = s1 + s2;
        if s3 == "axiom_systems" {
            print("STR_MATCH");
        }
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "STR_MATCH" in res.stdout

def test_llvm_simd_sub_and_mul():
    code = """
    fn main() -> void {
        let a = [100, 200, 300, 400];
        let b = [10, 20, 30, 40];
        let diff = simd_sub_i64(a, b);
        let s = simd_sum_i64(diff);
        print("DiffSum:", s);
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "DiffSum: 900" in res.stdout

def test_llvm_match_statement():
    code = """
    fn test_val(x: int) -> int {
        return match x {
            1 => 10,
            2 => 20,
            _ => 99
        };
    }

    fn main() -> void {
        let v1 = test_val(1);
        let v2 = test_val(2);
        let v3 = test_val(5);
        print("LLVM Match:", v1, v2, v3);
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "LLVM Match: 10 20 99" in res.stdout

def test_llvm_generics():
    code = """
    struct Box<T> {
        val: T
    }

    fn wrap<T>(item: T) -> Box<T> {
        return Box<T> { val: item };
    }

    fn main() -> void {
        let b = wrap<int>(42);
        print("LLVM Generic:", b.val);
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "LLVM Generic: 42" in res.stdout

def test_llvm_ensures_contract_success():
    code = """
    fn calc_positive(x: int) -> int
        ensures return > 0
    {
        return x + 10;
    }

    fn main() -> void {
        let v = calc_positive(5);
        print("LLVM Ensures OK:", v);
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "LLVM Ensures OK: 15" in res.stdout

def test_llvm_ensures_contract_violation():
    code = """
    fn calc_broken(x: int) -> int
        ensures return > 0
    {
        return x - 100;
    }

    fn main() -> void {
        calc_broken(5);
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 101
    assert "Sozlesme ihlali" in res.stdout

