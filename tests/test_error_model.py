"""
Axiom - Hata Modeli Testleri (`Result<T, E>` + `?` operatoru)
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"


def _run(src: str, extra_args=None, timeout=180):
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            [str(AXIOM), "run", path] + (extra_args or []),
            capture_output=True, text=True, timeout=timeout, env=env,
        )
    finally:
        os.remove(path)


PROGRAM = """
import "std/core/error"

fn parse_positive(s: str) -> Result<int, str> {
    let v = str_to_int(s)
    if v <= 0 {
        return result_err_int("pozitif degil")
    }
    return result_ok<int>(v)
}

fn twice(s: str) -> Result<int, str> {
    let v = parse_positive(s)?
    return result_ok<int>(v * 2)
}

fn chain(x: int) -> Result<int, str> {
    let a = twice("5")?
    let b = twice("6")?
    return result_ok<int>(a + b + x)
}

fn main() -> int {
    let ok_case = twice("21")
    print("OK:", ok_case.value)

    let err_case = twice("x")
    print("ERR:", err_case.error)
    print("HAS_OK:", err_case.is_ok)

    let chained = chain(1)
    print("CHAIN:", chained.value)

    let fb = result_unwrap_or<int>(err_case, -1)
    print("FALLBACK:", fb)
    return 0
}
"""


def test_result_question_mark_basic_flow():
    res = _run(PROGRAM)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "OK: 42" in res.stdout
    assert "ERR: pozitif degil" in res.stdout
    assert "HAS_OK: false" in res.stdout
    assert "CHAIN: 23" in res.stdout
    assert "FALLBACK: -1" in res.stdout


def test_question_mark_requires_result_returning_function():
    src = """
    import "std/core/error"
    fn f() -> Result<int, str> { return result_ok<int>(1) }
    fn main() -> int {
        let x = f()?
        print(x)
        return 0
    }
    """
    res = _run(src)
    assert res.returncode != 0
    assert "Result" in (res.stdout + res.stderr)


def test_question_mark_rejects_non_result_expression():
    src = """
    import "std/core/error"
    fn f() -> Result<int, str> { return result_ok<int>(1) }
    fn g() -> Result<int, str> {
        let x = 5?
        return result_ok<int>(x)
    }
    fn main() -> int { print(1) return 0 }
    """
    res = _run(src)
    assert res.returncode != 0
    msg = (res.stdout + res.stderr)
    assert "Result" in msg or "'?'" in msg


def test_question_mark_runs_defer_on_early_return():
    src = """
    import "std/core/error"
    fn fail() -> Result<int, str> { return result_err_int("boom") }
    fn work() -> Result<int, str> {
        defer { print("DEFER_CALISTI") }
        let v = fail()?
        print("ULASILMAMALI")
        return result_ok<int>(v)
    }
    fn main() -> int {
        let r = work()
        print("ERR:", r.error)
        return 0
    }
    """
    res = _run(src)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "DEFER_CALISTI" in res.stdout
    assert "ULASILMAMALI" not in res.stdout
    assert "ERR: boom" in res.stdout


def test_result_paths_are_leak_free_under_asan():
    res = _run(PROGRAM, extra_args=["--asan"], timeout=300)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "LeakSanitizer" not in (res.stdout + res.stderr)
    assert "OK: 42" in res.stdout


def test_llvm_backend_supports_question_mark():
    """`?` LLVM arka ucunda da calismali ve C arka ucuyla ayni sonucu vermeli."""
    src = """
    import "std/core/error"

    fn parse_positive(s: str) -> Result<int, str> {
        let v = str_to_int(s)
        if v <= 0 { return result_err_int("pozitif degil") }
        return result_ok<int>(v)
    }

    fn twice(s: str) -> Result<int, str> {
        let v = parse_positive(s)?
        return result_ok<int>(v * 2)
    }

    fn main() -> int {
        let a = twice("21")
        let b = twice("x")
        if a.is_ok { print("OK:", a.value) }
        if b.is_ok { print("BEKLENMEZ") } else { print("E:", b.error) }
        return 0
    }
    """
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as fh:
        fh.write(src)
        path = fh.name
    out = path + ".bin"
    try:
        build = subprocess.run(
            [str(AXIOM), "build", path, "--backend=llvm", "-o", out],
            capture_output=True, text=True, timeout=240,
        )
        assert build.returncode == 0, build.stdout + build.stderr
        run = subprocess.run([out], capture_output=True, text=True, timeout=60)
        assert run.returncode == 0, run.stdout + run.stderr
        assert "OK: 42" in run.stdout
        assert "E: pozitif degil" in run.stdout
        assert "BEKLENMEZ" not in run.stdout
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)


def test_llvm_backend_runs_defer_on_early_return():
    """`?` erken donusunde defer'ler LLVM'de de LIFO calismali."""
    src = """
    import "std/core/error"

    fn fail() -> Result<int, str> { return result_err_int("boom") }

    fn work() -> Result<int, str> {
        defer { print("DEFER_A") }
        defer { print("DEFER_B") }
        let v = fail()?
        print("ULASILMAMALI")
        return result_ok<int>(v)
    }

    fn main() -> int {
        let r = work()
        print("ERR:", r.error)
        return 0
    }
    """
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as fh:
        fh.write(src)
        path = fh.name
    out = path + ".bin"
    try:
        build = subprocess.run(
            [str(AXIOM), "build", path, "--backend=llvm", "-o", out],
            capture_output=True, text=True, timeout=240,
        )
        assert build.returncode == 0, build.stdout + build.stderr
        run = subprocess.run([out], capture_output=True, text=True, timeout=60)
        assert run.returncode == 0, run.stdout + run.stderr
        lines = [l for l in run.stdout.splitlines() if l.strip()]
        assert "ULASILMAMALI" not in run.stdout
        assert lines[0] == "DEFER_B"
        assert lines[1] == "DEFER_A"
        assert "ERR: boom" in run.stdout
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)
