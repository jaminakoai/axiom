"""
End-to-End (E2E) Native Compilation and Execution Tests for Axiom
"""
import subprocess
import tempfile
import os
from pathlib import Path
import pytest

from axiom.cli import compile_axiom_source, find_c_compiler

def compile_and_run(source_code: str, prove: bool = True):
    """
    Compiles Axiom source to C99 and compiles native ELF with gcc/clang,
    then executes it and returns CompletedProcess.
    """
    c_code = compile_axiom_source(source_code, prove=prove)
    cc = find_c_compiler()

    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        # Compile C to binary
        res_cc = subprocess.run([cc, "-O2", "-pthread", c_path, "-o", bin_path], capture_output=True, text=True)
        if res_cc.returncode != 0:
            raise RuntimeError(f"C Derleyici Hatasi:\n{res_cc.stderr}\nUretilen C Kodu:\n{c_code}")

        # Run native binary
        res_exec = subprocess.run([bin_path], capture_output=True, text=True)
        return res_exec
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

def test_e2e_hello_world():
    source = """
    fn main() -> int {
        print("Hello, Axiom Native!");
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Hello, Axiom Native!" in res.stdout

def test_e2e_top_level_statements():
    source = """
    let a = 15;
    let b = 25;
    print("Toplam:", a + b);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Toplam: 40" in res.stdout

def test_e2e_recursion_and_functions():
    source = """
    fn factorial(n: int) -> int {
        if n <= 1 {
            return 1;
        }
        return n * factorial(n - 1);
    }

    fn main() -> int {
        let f5 = factorial(5);
        print("5! =", f5);
        verify f5 == 120, "5! 120 olmalidir";
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "5! = 120" in res.stdout

def test_e2e_loops_and_mutability():
    source = """
    fn main() -> int {
        let mut sum = 0;
        for i in 1..11 {
            sum = sum + i;
        }
        print("Sum 1..10:", sum);
        verify sum == 55, "Toplam 55 olmali";

        let mut count = 3;
        while count > 0 {
            count = count - 1;
        }
        verify count == 0;
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Sum 1..10: 55" in res.stdout

def test_e2e_string_concatenation_and_comparison():
    source = """
    fn main() -> int {
        let s1 = "Axiom";
        let s2 = "Language";
        let full = s1 + " " + s2;
        print(full);
        verify full == "Axiom Language";
        verify s1 != s2;
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Axiom Language" in res.stdout

def test_e2e_contract_success():
    source = """
    fn safe_div(a: int, b: int) -> int
        requires b != 0
        ensures return * b <= a
    {
        return a / b;
    }

    fn main() -> int {
        let q = safe_div(20, 4);
        print("20 / 4 =", q);
        verify q == 5;
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "20 / 4 = 5" in res.stdout

def test_e2e_contract_requires_violation_exits_101():
    source = """
    fn safe_div(a: int, b: int) -> int
        requires b != 0
    {
        return a / b;
    }

    fn main() -> int {
        # This must violate 'requires b != 0'
        safe_div(10, 0);
        return 0;
    }
    """
    res = compile_and_run(source, prove=False)
    assert res.returncode == 101
    assert "[AXIOM GUVENLIK IHLALI] REQUIRES Basarisiz Oldu!" in res.stderr
    assert "safe_div" in res.stderr
    assert "(b != 0)" in res.stderr

def test_e2e_contract_ensures_violation_exits_101():
    source = """
    fn faulty_abs(x: int) -> int
        ensures return >= 0
    {
        return -5;
    }

    fn main() -> int {
        faulty_abs(10);
        return 0;
    }
    """
    res = compile_and_run(source, prove=False)
    assert res.returncode == 101
    assert "[AXIOM GUVENLIK IHLALI] ENSURES Basarisiz Oldu!" in res.stderr
    assert "faulty_abs" in res.stderr

def test_e2e_verify_statement_violation_exits_101():
    source = """
    fn main() -> int {
        let expected = 100;
        let actual = 99;
        verify actual == expected, "Degerler eslesmedi!";
        return 0;
    }
    """
    res = compile_and_run(source, prove=False)
    assert res.returncode == 101
    assert "[AXIOM GUVENLIK IHLALI] VERIFY Basarisiz Oldu!" in res.stderr
    assert "Degerler eslesmedi!" in res.stderr

def test_e2e_struct_operations():
    source = """
    struct ServerNode {
        host: str,
        port: int,
        is_active: bool
    }

    fn main() -> int {
        let mut s = ServerNode {
            host: "10.0.0.1",
            port: 8080,
            is_active: true
        }
        print("Server:", s.host, s.port, s.is_active);
        verify s.port == 8080;
        verify s.is_active;

        s.port = 443;
        verify s.port == 443;
        print("Updated Port:", s.port);
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Server: 10.0.0.1 8080 true" in res.stdout
    assert "Updated Port: 443" in res.stdout

def test_e2e_array_and_len():
    source = """
    fn sum_array(items: int[]) -> int {
        let n = len(items);
        let mut total = 0;
        for i in 0..n {
            total = total + items[i];
        }
        return total;
    }

    fn main() -> int {
        let numbers = [10, 20, 30, 40];
        let total = sum_array(numbers);
        print("Total:", total);
        verify total == 100;
        verify len(numbers) == 4;
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Total: 100" in res.stdout

def test_e2e_time_and_socket_builtins():
    source = """
    fn main() -> int {
        let t1 = time_now_ms();
        verify t1 > 0;

        # Localhost invalid port connection (should fail fast and return -1)
        let sock = tcp_connect("127.0.0.1", 1);
        socket_close(sock);

        let t2 = time_now_ms();
        verify t2 >= t1;
        print("Time elapsed ok:", t2 - t1);
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Time elapsed ok:" in res.stdout

@pytest.mark.parametrize("example_file", [
    "01_hello.ax",
    "02_fibonacci.ax",
    "03_contracts.ax",
    "04_security_scan.ax",
    "05_real_scanner.ax"
])
def test_e2e_all_examples(example_file):
    axiom_root = Path(__file__).resolve().parent.parent
    file_path = axiom_root / "examples" / example_file
    assert file_path.exists(), f"Ornek dosyasi bulunamadi: {file_path}"

    source = file_path.read_text(encoding="utf-8")
    res = compile_and_run(source)
    assert res.returncode == 0, f"{example_file} calistirmasi basarisiz oldu:\n{res.stderr}"
