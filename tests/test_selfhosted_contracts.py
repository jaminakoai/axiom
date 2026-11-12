"""
Axiom - Self-hosted derleyici (`bin/axiomc`) sözleşme ve kapsam testleri

`ensures` içindeki `return` sembolü self-hosted parser tarafından işlenmiyordu;
`ensures return * b <= a` bozuk C'ye (`(( * b) <= a)`) dönüşüyordu.
Bu dosya hatayı ve şu an desteklenen örnek kümesini kilitler.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOMC = ROOT / "bin" / "axiomc"
EXAMPLES = ROOT / "examples"

# Self-hosted derleyicinin (bin/axiomc) derleyip çalıştırabildiği örnekler.
# P2-18 turunda 4 -> 8'e çıktı: `len(str)` tip çözümü, __auto_type tabanlı
# dönüş tipi çıkarımı, UTF-8 bayt/kod-noktası karışımı düzeltmeleri.
# Liste, gerçekten DERLENEN ve ÇALIŞAN örneklerle senkron tutulmalı
# (tests/test_selfhosted_contracts.py::test_supported_list_is_accurate).
# Ag erisimi gerektiren ornekler: ag yoksa SKIP (hata degil).
NEEDS_NETWORK = {"11_packet2_advanced_network.ax"}

SUPPORTED = [
    "01_hello.ax",
    "02_fibonacci.ax",
    "03_contracts.ax",
    "04_security_scan.ax",
    "05_real_scanner.ax",
    "07_http_banner_grabber.ax",
    "08_multithreaded_scanner.ax",
    "09_simd_vector_scan.ax",
    "10_packet1_security_suite.ax",
    "11_packet2_advanced_network.ax",
    "12_packet3_system_exploit.ax",
    "13_packet4_fuzzer_scanner.ax",
    "14_packet5_full_security_suite.ax",
    "16_blueteam_defensive_suite.ax",
    "17_ai_tensor_neural_net.ax",
    "18_web_api_framework.ax",
    "19_error_handling.ax",
    "20_stdlib_result.ax",
    "21_axiom_scan.ax",
    "22_dfir_triage.ax",
]


def _axiomc_build(src_path: Path):
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        out = f.name
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        res = subprocess.run([str(AXIOMC), "build", str(src_path), "-o", out],
                             capture_output=True, text=True, timeout=300, env=env)
        return res, out
    except Exception:
        if os.path.exists(out):
            os.remove(out)
        raise


@pytest.mark.parametrize("example", SUPPORTED)
def test_selfhosted_compiles_supported_example(example):
    if not AXIOMC.exists():
        pytest.skip("bin/axiomc bulunamadi")
    if example in NEEDS_NETWORK:
        from tests.support_env import network_probe
        _ok, _why = network_probe()
        if not _ok:
            pytest.skip(f"Ağ gerektiren örnek: {_why}")
    res, out = _axiomc_build(EXAMPLES / example)
    try:
        assert res.returncode == 0, f"{example}:\n{res.stdout}\n{res.stderr}"
        run = subprocess.run([out], capture_output=True, text=True, timeout=120)
        # CLI araclari argumansiz "kullanim" mesaji + exit 1 dondurur;
        # bu bir derleme/calisma hatasi degildir.
        assert run.returncode in (0, 1), run.stdout + run.stderr
        assert "GUVENLIK IHLALI" not in run.stdout + run.stderr
    finally:
        if os.path.exists(out):
            os.remove(out)


def test_selfhosted_ensures_return_symbol():
    """`ensures return ...` geçerli C üretmeli ve çalışma anında doğru denetlemeli."""
    if not AXIOMC.exists():
        pytest.skip("bin/axiomc bulunamadi")
    src = """
fn safe_div(a: int, b: int) -> int
    requires b != 0
    ensures return * b <= a
{
    return a / b
}

fn nonneg(x: int) -> int
    ensures return >= 0
{
    if x < 0 { return 0 }
    return x
}

fn main() -> int {
    print(safe_div(100, 5))
    print(nonneg(-3))
    print(nonneg(7))
    return 0
}
"""
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    out = path + ".bin"
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        build = subprocess.run([str(AXIOMC), "build", path, "-o", out],
                               capture_output=True, text=True, timeout=300, env=env)
        assert build.returncode == 0, build.stdout + build.stderr
        run = subprocess.run([out], capture_output=True, text=True, timeout=120)
        assert run.returncode == 0, run.stdout + run.stderr
        assert run.stdout.splitlines() == ["20", "0", "7"]
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)


def test_selfhosted_ensures_violation_is_caught():
    """`ensures` ihlali çalışma anında exit 101 ile durmalı."""
    if not AXIOMC.exists():
        pytest.skip("bin/axiomc bulunamadi")
    src = """
fn broken(x: int) -> int
    ensures return > 100
{
    return x
}

fn main() -> int {
    print(broken(5))
    return 0
}
"""
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    out = path + ".bin"
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        build = subprocess.run([str(AXIOMC), "build", path, "-o", out],
                               capture_output=True, text=True, timeout=300, env=env)
        assert build.returncode == 0, build.stdout + build.stderr
        run = subprocess.run([out], capture_output=True, text=True, timeout=120)
        assert run.returncode == 101
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)


def test_selfhosted_emit_c_has_no_return_symbol_in_ensures():
    """Üretilen C'de `ensures` ifadesi `__ax_ret` içermeli, çıplak `(` ile başlamamalı."""
    if not AXIOMC.exists():
        pytest.skip("bin/axiomc bulunamadi")
    src = """
fn f(a: int) -> int
    ensures return >= 0
{
    return a
}
fn main() -> int { print(f(1)) return 0 }
"""
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        res = subprocess.run([str(AXIOMC), "emit-c", path],
                             capture_output=True, text=True, timeout=180, env=env)
        assert res.returncode == 0, res.stderr
        assert "__ax_ret >= 0" in res.stdout
        assert "( >= 0)" not in res.stdout
    finally:
        os.remove(path)


def test_selfhosted_simd_and_math_builtins_are_mapped():
    """Self-hosted haritasında simd_/math_/thread_/mutex_/atomic_ çözülmeli."""
    text = (ROOT / "compiler" / "parser.ax").read_text(encoding="utf-8")
    for name in ("simd_add_i64", "simd_mul_i64", "simd_sub_i64", "simd_sum_i64",
                 "simd_scan_match"):
        assert name in text, f"map_builtin_func'ta eksik: {name}"
    assert 'str_starts_with(name, "simd_")' in text
    assert 'str_starts_with(name, "thread_")' in text


def test_supported_list_is_accurate():
    """Listedeki her örnek gerçekten derlenmeli; liste şişirilmemeli."""
    if not AXIOMC.exists():
        pytest.skip("bin/axiomc bulunamadi")
    failures = []
    for name in SUPPORTED:
        res, out = _axiomc_build(EXAMPLES / name)
        try:
            if res.returncode != 0:
                failures.append(name)
        finally:
            if os.path.exists(out):
                os.remove(out)
    assert not failures, f"Listede olup derlenemeyenler: {failures}"


def test_utf8_source_is_not_truncated_by_selfhosted_lexer():
    """Cok baytli (UTF-8) kaynak dosyalar sonda kesilmemeli (P2-18 hatasi).

    Self-hosted lexer eskiden `len(src)` (kod noktasi) ile bayt indeksini
    karsilastiriyordu; Turkce/emoji iceren dosyalar sonda kesiliyor ve son
    deyim yarim kaliyordu.
    """
    if not AXIOMC.exists():
        pytest.skip("bin/axiomc bulunamadi")
    src = (
        'fn main() -> int {\n'
        '    print("Açık Port • test ✓ ğüşiöç")\n'
        '    print("İstanbul - Açık - Güvenlik")\n'
        '    let x = 41\n'
        '    let y = x + 1\n'
        '    print("SON-DEGER:", y)\n'
        '    verify y == 42\n'
        '    print("BITTI")\n'
        '    return 0\n'
        '}\n'
    )
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    try:
        res, out = _axiomc_build(Path(path))
        try:
            assert res.returncode == 0, res.stdout + res.stderr
            run = subprocess.run([out], capture_output=True, text=True, timeout=120)
            assert run.returncode == 0, run.stdout + run.stderr
            assert "BITTI" in run.stdout, f"son satir kayboldu: {run.stdout!r}"
            assert "SON-DEGER: 42" in run.stdout, run.stdout
        finally:
            if os.path.exists(out):
                os.remove(out)
    finally:
        os.remove(path)
