"""
Concurrency & POSIX Pthreads Tests for Axiom (λx)
"""
import pytest
import subprocess
import tempfile
import os

from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.checker import TypeChecker, SemanticError
from axiom.codegen_c import CCodeGenerator
from axiom.cli import compile_axiom_source, find_c_compiler

def compile_and_run(source_code: str):
    c_code = compile_axiom_source(source_code)
    cc = find_c_compiler()

    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        res_cc = subprocess.run([cc, "-O2", "-pthread", c_path, "-o", bin_path], capture_output=True, text=True)
        if res_cc.returncode != 0:
            raise RuntimeError(f"C Derleme Hatasi:\n{res_cc.stderr}\nC Kodu:\n{c_code}")

        res_exec = subprocess.run([bin_path], capture_output=True, text=True, timeout=10)
        return res_exec
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

def test_thread_create_and_join():
    source = """
    fn worker(x: int) -> int {
        return x * 2;
    }

    fn main() -> int {
        let th = thread_create(worker, 21);
        let res = thread_join(th);
        print("Thread Sonuc:", res);
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Thread Sonuc: 42" in res.stdout

def test_multiple_threads():
    source = """
    fn worker(id: int) -> int {
        return id + 100;
    }

    fn main() -> int {
        let t1 = thread_create(worker, 1);
        let t2 = thread_create(worker, 2);
        let t3 = thread_create(worker, 3);

        let r1 = thread_join(t1);
        let r2 = thread_join(t2);
        let r3 = thread_join(t3);

        print("Sonuclar:", r1, r2, r3);
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Sonuclar: 101 102 103" in res.stdout

def test_atomic_counter():
    source = """
    fn main() -> int {
        let counter = atomic_init(10);
        let val1 = atomic_add(counter, 5);
        let val2 = atomic_get(counter);
        print("Atomik Deger:", val1, val2);
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Atomik Deger: 15 15" in res.stdout

def test_mutex_synchronization():
    source = """
    fn main() -> int {
        let m = mutex_init();
        mutex_lock(m);
        print("Kilit alindi");
        mutex_unlock(m);
        print("Kilit birakildi");
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Kilit alindi" in res.stdout
    assert "Kilit birakildi" in res.stdout

def test_sleep_ms():
    source = """
    fn main() -> int {
        let t0 = time_now_ms();
        sleep_ms(50);
        let t1 = time_now_ms();
        let diff = t1 - t0;
        print("Gecen sure:", diff >= 40);
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Gecen sure: true" in res.stdout

def test_thread_semantic_unknown_function():
    source = """
    fn main() -> void {
        let th = thread_create(non_existent_fn, 10);
    }
    """
    with pytest.raises(SemanticError, match="tanimsiz fonksiyon"):
        lexer = Lexer(source)
        parser = Parser(lexer.tokenize())
        program = parser.parse()
        TypeChecker().check(program)

def test_thread_semantic_invalid_arg_count():
    source = """
    fn bad_worker(a: int, b: int) -> int {
        return a + b;
    }

    fn main() -> void {
        let th = thread_create(bad_worker, 10);
    }
    """
    with pytest.raises(SemanticError, match="tek bir 'int' parametresi almalidir"):
        lexer = Lexer(source)
        parser = Parser(lexer.tokenize())
        program = parser.parse()
        TypeChecker().check(program)

def test_thread_semantic_invalid_param_type():
    source = """
    fn bad_worker(msg: str) -> void {
        print(msg);
    }

    fn main() -> void {
        let th = thread_create(bad_worker, 10);
    }
    """
    with pytest.raises(SemanticError, match="tek bir 'int' parametresi almalidir"):
        lexer = Lexer(source)
        parser = Parser(lexer.tokenize())
        program = parser.parse()
        TypeChecker().check(program)

def test_thread_semantic_invalid_thread_create_args():
    source = """
    fn main() -> void {
        let th = thread_create(10);
    }
    """
    with pytest.raises(SemanticError, match="2 arguman bekler"):
        lexer = Lexer(source)
        parser = Parser(lexer.tokenize())
        program = parser.parse()
        TypeChecker().check(program)
