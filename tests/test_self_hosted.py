"""
Axiom Programming Language (λx) - Self-Hosted Compiler E2E Tests
Tests the independent native ELF compiler (bin/axiomc) written in Axiom itself.
"""
import subprocess
import tempfile
import os
from pathlib import Path
import pytest

AXIOM_ROOT = Path(__file__).resolve().parent.parent
AXIOMC_BIN = AXIOM_ROOT / "bin" / "axiomc"
EXAMPLES_DIR = AXIOM_ROOT / "examples"

def test_self_hosted_binary_exists():
    """Verify bin/axiomc exists and is an executable file."""
    assert AXIOMC_BIN.exists(), f"Self-hosted binary bulunamadi: {AXIOMC_BIN}"
    assert os.access(AXIOMC_BIN, os.X_OK), "bin/axiomc calistirilabilir (executable) degil!"


def test_self_hosted_cli_help_and_version():
    """Verify axiomc --help and --version subcommands."""
    res_help = subprocess.run([str(AXIOMC_BIN), "--help"], capture_output=True, text=True)
    assert res_help.returncode == 0
    assert "Axiom Self-Hosted Compiler" in res_help.stdout
    assert "axiomc build" in res_help.stdout

    res_ver = subprocess.run([str(AXIOMC_BIN), "--version"], capture_output=True, text=True)
    assert res_ver.returncode == 0
    assert "Self-Hosted Compiler v0.5.0-alpha" in res_ver.stdout


def test_self_hosted_emit_c():
    """Verify axiomc emit-c generates valid C99 code."""
    hello_ax = EXAMPLES_DIR / "01_hello.ax"
    res = subprocess.run([str(AXIOMC_BIN), "emit-c", str(hello_ax)], capture_output=True, text=True)
    assert res.returncode == 0
    out = res.stdout
    assert "runtime.h" in out
    assert "ax_greet" in out
    assert "ax_calculate_sum" in out
    assert "int main(int argc, char** argv)" in out


def test_self_hosted_build_and_run_hello(tmp_path):
    """Compile and run 01_hello.ax using native bin/axiomc without Python."""
    hello_ax = EXAMPLES_DIR / "01_hello.ax"
    output_bin = tmp_path / "hello_elf"

    cmd_build = [str(AXIOMC_BIN), "build", str(hello_ax), "-o", str(output_bin)]
    res_build = subprocess.run(cmd_build, capture_output=True, text=True)
    assert res_build.returncode == 0
    assert output_bin.exists()

    res_run = subprocess.run([str(output_bin)], capture_output=True, text=True)
    assert res_run.returncode == 0
    assert "Merhaba, Guvenlik Uzmani! Axiom dunyasina hos geldin." in res_run.stdout
    assert "55" in res_run.stdout
    assert "[DOGRULAMA] Toplam hesabi basarili ve dogru!" in res_run.stdout


def test_self_hosted_build_and_run_fibonacci(tmp_path):
    """Compile and run 02_fibonacci.ax using native bin/axiomc."""
    fibo_ax = EXAMPLES_DIR / "02_fibonacci.ax"
    output_bin = tmp_path / "fibo_elf"

    cmd_build = [str(AXIOMC_BIN), "build", str(fibo_ax), "-o", str(output_bin)]
    res_build = subprocess.run(cmd_build, capture_output=True, text=True)
    assert res_build.returncode == 0
    assert output_bin.exists()

    res_run = subprocess.run([str(output_bin)], capture_output=True, text=True)
    assert res_run.returncode == 0
    assert "fib(45) degeri = 1134903170" in res_run.stdout
    assert "fib( 10 ) = 55" in res_run.stdout or "fib(10) = 55" in res_run.stdout


def test_self_hosted_run_subcommand():
    """Verify axiomc run command compiles and runs directly."""
    hello_ax = EXAMPLES_DIR / "01_hello.ax"
    cmd_run = [str(AXIOMC_BIN), "run", str(hello_ax)]
    res_run = subprocess.run(cmd_run, capture_output=True, text=True)
    assert res_run.returncode == 0
    assert "Merhaba, Guvenlik Uzmani!" in res_run.stdout
    assert "55" in res_run.stdout


def test_self_hosted_struct_and_member_access(tmp_path):
    """Compile a program containing struct declarations and field accesses."""
    code = """
    struct Point {
        x: int,
        y: int
    }

    fn calculate_dist_sq(p: Point) -> int {
        return p.x * p.x + p.y * p.y
    }

    fn main() -> int {
        let pt = Point { x: 3, y: 4 }
        let d = calculate_dist_sq(pt)
        print("Distance squared:", d)
        return 0
    }
    """
    ax_file = tmp_path / "point.ax"
    ax_file.write_text(code, encoding="utf-8")
    out_bin = tmp_path / "point_bin"

    res_build = subprocess.run([str(AXIOMC_BIN), "build", str(ax_file), "-o", str(out_bin)], capture_output=True, text=True)
    assert res_build.returncode == 0
    res_run = subprocess.run([str(out_bin)], capture_output=True, text=True)
    assert res_run.returncode == 0
    assert "Distance squared: 25" in res_run.stdout


def test_self_hosted_string_builtins(tmp_path):
    """Compile and verify built-in string functions."""
    code = """
    fn main() -> int {
        let msg = "Axiom Security Engine"
        let sub = str_sub(msg, 0, 5)
        let ch = str_char_at(msg, 6)
        print("Sub:", sub, "Char:", ch)
        return 0
    }
    """
    ax_file = tmp_path / "str_test.ax"
    ax_file.write_text(code, encoding="utf-8")
    out_bin = tmp_path / "str_test_bin"

    res_build = subprocess.run([str(AXIOMC_BIN), "build", str(ax_file), "-o", str(out_bin)], capture_output=True, text=True)
    assert res_build.returncode == 0
    res_run = subprocess.run([str(out_bin)], capture_output=True, text=True)
    assert res_run.returncode == 0
    assert "Sub: Axiom Char: S" in res_run.stdout


def test_self_hosted_invalid_file_handling():
    """Verify proper error output when an input file does not exist."""
    res = subprocess.run([str(AXIOMC_BIN), "build", "/tmp/non_existent_file.ax"], capture_output=True, text=True)
    assert res.returncode != 0
    assert "Dosya bulunamadi" in res.stdout or "Dosya bulunamadi" in res.stderr


def test_self_hosted_phase6_features(tmp_path):
    """Compile and verify Faz 6 features: defer, invariant, as, match, Option, Result."""
    code = """
    import "std:core:option"
    import "std:core:result"

    fn test_runner() -> int {
        let mut count = 10
        defer {
            print("DEFER_RAN_COUNT:", count)
        }

        let mut i = 0
        while i < 5 invariant i >= 0 {
            i = i + 1
        }
        print("WHILE_INVARIANT_OK:", i)

        let float_val = 99.4
        let int_val = float_val as int
        print("CAST_VAL:", int_val)

        let status_code = 404
        match status_code {
            200 => print("STATUS_200_OK"),
            404 => print("STATUS_404_NOT_FOUND"),
            else => print("STATUS_UNKNOWN")
        }

        let opt = some_int(777)
        if opt.has_value {
            print("OPTION_VAL:", opt.value)
        }

        let res = ok_str("axiom_is_secure")
        if res.is_ok {
            print("RESULT_VAL:", res.value)
        }

        return 0
    }

    fn main() -> int {
        return test_runner()
    }
    """
    ax_file = tmp_path / "phase6_test.ax"
    ax_file.write_text(code, encoding="utf-8")
    out_bin = tmp_path / "phase6_bin"

    res_build = subprocess.run([str(AXIOMC_BIN), "build", str(ax_file), "-o", str(out_bin)], capture_output=True, text=True)
    assert res_build.returncode == 0, f"Build hatasi:\nSTDOUT:\n{res_build.stdout}\nSTDERR:\n{res_build.stderr}"
    assert out_bin.exists()

    res_run = subprocess.run([str(out_bin)], capture_output=True, text=True)
    assert res_run.returncode == 0, f"Run hatasi:\nSTDOUT:\n{res_run.stdout}\nSTDERR:\n{res_run.stderr}"
    stdout = res_run.stdout
    assert "WHILE_INVARIANT_OK: 5" in stdout
    assert "CAST_VAL: 99" in stdout
    assert "STATUS_404_NOT_FOUND" in stdout
    assert "OPTION_VAL: 777" in stdout
    assert "RESULT_VAL: axiom_is_secure" in stdout
    assert "DEFER_RAN_COUNT: 10" in stdout


def test_self_hosted_deterministic_emit_c(tmp_path):
    """Verify deterministic build: identical source yields byte-for-byte identical C code."""
    import hashlib

    code = """
    struct Metric {
        id: int,
        score: float
    }

    fn calculate(m: Metric) -> int {
        defer {
            print("cleanup metric")
        }
        let score_int = m.score as int
        match score_int {
            100 => return 1,
            else => return 0
        }
    }

    fn main() -> int {
        let m = Metric { id: 1, score: 100.0 }
        return calculate(m)
    }
    """
    ax_file = tmp_path / "det_test.ax"
    ax_file.write_text(code, encoding="utf-8")

    res1 = subprocess.run([str(AXIOMC_BIN), "emit-c", str(ax_file)], capture_output=True, text=True)
    assert res1.returncode == 0

    res2 = subprocess.run([str(AXIOMC_BIN), "emit-c", str(ax_file)], capture_output=True, text=True)
    assert res2.returncode == 0

    hash1 = hashlib.sha256(res1.stdout.encode("utf-8")).hexdigest()
    hash2 = hashlib.sha256(res2.stdout.encode("utf-8")).hexdigest()

    assert hash1 == hash2, "Deterministik C üretimi başarısız: Hash değerleri farklı!"
    assert res1.stdout == res2.stdout, "C kodları baytı baytına eşit değil!"


def test_self_hosted_generics_box(tmp_path):
    """Verify bin/axiomc compiles and runs struct Box<T> generics without syntax errors."""
    code = """
    struct Box<T> {
        val: T
    }

    fn main() -> int {
        let b: Box<int> = Box<int> { val: 42 }
        print("GENERIC_BOX_VAL:", b.val)
        return 0
    }
    """
    ax_file = tmp_path / "generic_box.ax"
    ax_file.write_text(code, encoding="utf-8")
    out_bin = tmp_path / "generic_box.bin"

    res_build = subprocess.run([str(AXIOMC_BIN), "build", str(ax_file), "-o", str(out_bin)], capture_output=True, text=True)
    assert res_build.returncode == 0, f"Derleme hatasi:\n{res_build.stderr}\nSTDOUT:\n{res_build.stdout}"
    assert out_bin.exists()

    res_run = subprocess.run([str(out_bin)], capture_output=True, text=True)
    assert res_run.returncode == 0
    assert "GENERIC_BOX_VAL: 42" in res_run.stdout


