"""
Axiom - Kalan Isler Regresyon Testleri (5 Kasim 2026)
P0 bellek/aritmetik/prover duzeltmeleri, self-hosted generics, LLVM ornekleri,
axpm registry davranisi ve yol guvenligi icin negatif/pozitif testler.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

AXIOM_ROOT = Path(__file__).resolve().parent.parent
AXIOM_BIN = AXIOM_ROOT / "bin" / "axiom"
AXIOMC_BIN = AXIOM_ROOT / "bin" / "axiomc"
EXAMPLES = AXIOM_ROOT / "examples"


def _write(src: str, suffix: str = ".ax") -> str:
    f = tempfile.NamedTemporaryFile(suffix=suffix, mode="w", delete=False, encoding="utf-8")
    f.write(src)
    f.close()
    return f.name


def _run_cli(args, timeout=120, env=None):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env)


def test_arithmetic_overflow_is_trapped():
    src = """
    fn main() -> int {
        let a = 9223372036854775807
        let b = a + 1
        print(b)
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "run", path])
        assert res.returncode == 101
        assert "tasmasi" in (res.stdout + res.stderr).lower()
    finally:
        os.remove(path)


def test_array_binding_has_value_semantics():
    src = """
    fn main() -> int {
        let a = [1, 2, 3]
        let mut b = a
        b[0] = 99
        print("a0:", a[0])
        print("b0:", b[0])
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "run", path])
        assert res.returncode == 0
        assert "a0: 1" in res.stdout
        assert "b0: 99" in res.stdout
    finally:
        os.remove(path)


def test_string_concat_loop_has_no_leak_under_asan():
    src = """
    fn main() -> int {
        let mut s = ""
        let mut i = 0
        while i < 1000 {
            s = s + "AxiomLeakTest"
            i = i + 1
        }
        print(len(s))
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "run", "--asan", path], timeout=240)
        assert res.returncode == 0, res.stdout + res.stderr
        assert "13000" in res.stdout
        assert "LeakSanitizer" not in (res.stdout + res.stderr)
    finally:
        os.remove(path)


def test_str_free_double_free_is_safe_under_asan():
    src = """
    fn main() -> int {
        let mut s = "a" + "b"
        str_free(s)
        str_free(s)
        print("after")
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "run", "--asan", path], timeout=240)
        assert res.returncode == 0, res.stdout + res.stderr
        assert "after" in res.stdout
        assert "double-free" not in (res.stdout + res.stderr)
    finally:
        os.remove(path)


def test_prover_checks_function_call_in_if_condition():
    src = """
    fn check_port(port: int) -> bool
        requires port > 0 and port <= 65535
    { return true }

    fn main() -> int {
        if check_port(99999) { print("ok") }
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "prove", path])
        assert res.returncode != 0
        assert "requires" in (res.stdout + res.stderr).lower()

        res_check = _run_cli([str(AXIOM_BIN), "check", path])
        assert res_check.returncode != 0
    finally:
        os.remove(path)


def test_self_hosted_generic_function_returning_generic_struct():
    if not AXIOMC_BIN.exists():
        pytest.skip("bin/axiomc bulunamadi")
    src = """
    struct Box<T> { val: T }
    fn wrap<T>(x: T) -> Box<T> { return Box<T> { val: x }; }
    fn main() -> int {
        let b: Box<int> = wrap<int>(42)
        print("GENERIC_FN_VAL:", b.val)
        return 0
    }
    """
    ax = _write(src)
    out = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
    out.close()
    try:
        build = _run_cli([str(AXIOMC_BIN), "build", ax, "-o", out.name])
        assert build.returncode == 0, build.stdout + build.stderr
        run = _run_cli([out.name])
        assert run.returncode == 0
        assert "GENERIC_FN_VAL: 42" in run.stdout
    finally:
        os.remove(ax)
        if os.path.exists(out.name):
            os.remove(out.name)


@pytest.mark.parametrize("example", [
    "12_packet3_system_exploit.ax",
    "15_redteam_offensive_suite.ax",
    "16_blueteam_defensive_suite.ax",
    "18_web_api_framework.ax",
])
def test_llvm_backend_compiles_previously_failing_examples(example):
    out = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
    out.close()
    try:
        cmd = [
            str(AXIOM_BIN), "build", str(EXAMPLES / example),
            "--backend=llvm", "-o", out.name
        ]
        if "offensive" in example:
            cmd.extend(["--features", "offensive"])
        res = _run_cli(cmd, timeout=300)
        assert res.returncode == 0, res.stdout + res.stderr
        assert os.path.exists(out.name)
    finally:
        if os.path.exists(out.name):
            os.remove(out.name)


def test_axpm_registry_dependency_fails_loudly(tmp_path):
    work = tmp_path / "pkg"
    init = _run_cli([str(AXIOM_ROOT / "bin" / "axpm"), "init", str(work)])
    assert init.returncode == 0
    add = subprocess.run([
        str(AXIOM_ROOT / "bin" / "axpm"), "add", "missing_pkg", "--version", "1.2.3"
    ], capture_output=True, text=True, timeout=60, cwd=str(work))
    # add_dependency once manifest'e yazar, sonra install acik hata verir.
    assert add.returncode != 0
    assert "registry" in (add.stdout + add.stderr).lower()


def test_axiomc_accepts_unicode_and_space_paths(tmp_path):
    if not AXIOMC_BIN.exists():
        pytest.skip("bin/axiomc bulunamadi")
    d = tmp_path / "boş luk"
    d.mkdir()
    src = d / "merhaba.ax"
    src.write_text('fn main() -> int { print("UNICODE_OK"); return 0; }\n', encoding="utf-8")
    out = d / "bin_out"
    res = _run_cli([str(AXIOMC_BIN), "build", str(src), "-o", str(out)])
    assert res.returncode == 0, res.stdout + res.stderr
    run = _run_cli([str(out)])
    assert "UNICODE_OK" in run.stdout


def test_owned_string_table_stays_bounded_for_named_variables():
    """İsimli string değişkenleri kapsam sonunda bırakılır: tablo şişmemeli."""
    src = """
    fn main() -> int {
        let mut s = ""
        let mut i = 0
        while i < 2000 {
            s = s + "x"
            i = i + 1
        }
        print("LEN:", len(s))
        print("OWNED:", str_owned_count())
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "run", path])
        assert res.returncode == 0, res.stdout + res.stderr
        assert "LEN: 2000" in res.stdout
        owned = int(res.stdout.split("OWNED:")[1].strip())
        assert owned <= 5, f"Sahiplik tablosu şişti: {owned}"
    finally:
        os.remove(path)
