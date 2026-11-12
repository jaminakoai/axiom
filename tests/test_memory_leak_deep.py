import os
import subprocess
import sys
import tempfile
from pathlib import Path

AXIOM_BIN = Path(__file__).resolve().parent.parent / "bin" / "axiom"

from tests.support_env import require_asan


def _run_cli(args, timeout=120):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


def _write(src: str, ext: str = ".ax") -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=ext, delete=False)
    f.write(src)
    f.close()
    return f.name


@require_asan
def test_str_replace_loop_has_no_leak_under_asan():
    src = """
    fn main() -> int {
        let mut s = "The quick brown fox jumps over the lazy dog"
        let mut i = 0
        while i < 1000 {
            s = str_replace(s, "dog", "fox")
            s = str_replace(s, "fox", "dog")
            i = i + 1
        }
        print(len(s))
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "run", "--asan", path], timeout=180)
        assert res.returncode == 0, res.stdout + res.stderr
        assert "43" in res.stdout
        assert "LeakSanitizer" not in (res.stdout + res.stderr)
    finally:
        os.remove(path)


@require_asan
def test_file_read_loop_has_no_leak_under_asan():
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("Axiom Safe File Read Content With High Entropy 1234567890\n")
        data_path = f.name

    src = f"""
    fn main() -> int {{
        let mut i = 0
        let mut total_len = 0
        while i < 1000 {{
            let content = file_read("{data_path}")
            total_len = total_len + len(content)
            i = i + 1
        }}
        print("TotalLen:", total_len)
        return 0
    }}
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "run", "--asan", path], timeout=180)
        assert res.returncode == 0, res.stdout + res.stderr
        assert "TotalLen: 58000" in res.stdout
        assert "LeakSanitizer" not in (res.stdout + res.stderr)
    finally:
        os.remove(path)
        if os.path.exists(data_path):
            os.remove(data_path)


@require_asan
def test_str_split_loop_has_no_leak_under_asan():
    src = """
    fn main() -> int {
        let mut i = 0
        let mut count = 0
        while i < 1000 {
            let parts = str_split("alpha,beta,gamma,delta,epsilon", ",")
            count = count + len(parts)
            i = i + 1
        }
        print("Count:", count)
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "run", "--asan", path], timeout=180)
        assert res.returncode == 0, res.stdout + res.stderr
        assert "Count: 5000" in res.stdout
        assert "LeakSanitizer" not in (res.stdout + res.stderr)
    finally:
        os.remove(path)


@require_asan
def test_str_sub_and_trim_loop_has_no_leak_under_asan():
    src = """
    fn main() -> int {
        let mut i = 0
        let mut total = 0
        while i < 1000 {
            let raw = "   hello axiom formal verification   "
            let trimmed = str_trim(raw)
            let sub = str_sub(trimmed, 6, 5)
            total = total + len(sub)
            i = i + 1
        }
        print("SubLen:", total)
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "run", "--asan", path], timeout=180)
        assert res.returncode == 0, res.stdout + res.stderr
        assert "SubLen: 5000" in res.stdout
        assert "LeakSanitizer" not in (res.stdout + res.stderr)
    finally:
        os.remove(path)


@require_asan
def test_array_push_loop_has_no_leak_under_asan():
    src = """
    fn main() -> int {
        let mut arr: str[] = []
        let mut i = 0
        while i < 1000 {
            arr = array_push(arr, "s" + int_to_str(i))
            i = i + 1
        }
        print("ArrLen:", len(arr))
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "run", "--asan", path], timeout=180)
        assert res.returncode == 0, res.stdout + res.stderr
        assert "ArrLen: 1000" in res.stdout
        assert "LeakSanitizer" not in (res.stdout + res.stderr)
    finally:
        os.remove(path)


def test_int_array_push_loop_has_no_leak_under_asan():
    src = """
    fn main() -> int {
        let mut arr: int[] = []
        let mut i = 0
        while i < 3000 {
            arr = array_push(arr, i)
            i = i + 1
        }
        print("IntLen:", len(arr), arr[2999])
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "run", "--asan", path], timeout=180)
        assert res.returncode == 0, res.stdout + res.stderr
        assert "IntLen: 3000 2999" in res.stdout
        assert "LeakSanitizer" not in (res.stdout + res.stderr)
    finally:
        os.remove(path)


def test_string_reassignment_loop_does_not_grow_ownership_table():
    """s = f(i) her turda eski degeri birakmali; tablo sabit kalmali."""
    src = """
    fn main() -> int {
        let mut s = "a"
        let mut i = 0
        while i < 5000 {
            s = "y" + int_to_str(i)
            i = i + 1
        }
        print("LEN:", len(s))
        print("OWNED:", str_owned_count())
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "run", path], timeout=180)
        assert res.returncode == 0, res.stdout + res.stderr
        assert "LEN: 5" in res.stdout
        owned = int(res.stdout.split("OWNED:")[1].strip())
        assert owned <= 3, f"Sahiplik tablosu büyüdü: {owned}"
        assert "LeakSanitizer" not in (res.stdout + res.stderr)
    finally:
        os.remove(path)


def test_string_returning_function_does_not_leak():
    """Fonksiyondan dönen string'ler ve iç geçici string'ler temizlenmeli."""
    src = """
    fn make(i: int) -> str {
        return "v" + int_to_str(i)
    }
    fn main() -> int {
        let mut i = 0
        let mut total = 0
        while i < 5000 {
            let s = make(i)
            total = total + len(s)
            i = i + 1
        }
        print("T:", total)
        print("OWNED:", str_owned_count())
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "run", path], timeout=180)
        assert res.returncode == 0, res.stdout + res.stderr
        assert "T: 23890" in res.stdout
        owned = int(res.stdout.split("OWNED:")[1].strip())
        assert owned <= 3, f"Sahiplik tablosu büyüdü: {owned}"
    finally:
        os.remove(path)


def test_nested_temporary_strings_are_released():
    """İç içe üretilen geçici string'ler (f(g(x))) ifade sonunda bırakılmalı."""
    src = """
    fn main() -> int {
        let mut i = 0
        while i < 3000 {
            let e = "x" + int_to_str(i) + "y"
            i = i + 1
        }
        print("OWNED:", str_owned_count())
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "run", path], timeout=180)
        assert res.returncode == 0, res.stdout + res.stderr
        owned = int(res.stdout.split("OWNED:")[1].strip())
        assert owned <= 3, f"Geçici string'ler bırakılmadı: {owned}"
    finally:
        os.remove(path)
