"""
Axiom - P1-06 DFIR triyaj akisi + P1-06'da bulunan arka uc hatalari

Kapsam:
  - examples/22_dfir_triage.ax: tek JSON rapor (surec, port, butunluk, Sigma)
  - Gercek /proc verisiyle kosma (sandbox'ta atlanir)
  - C ve LLVM ciktilarinin ayni olmasi (parite)
  - Regresyon: C'de str[] icin use-after-free, LLVM'de string literal
    cift-cozumlenmesi ve str_join ABI uyumsuzlugu
"""
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
EXAMPLE = ROOT / "examples" / "22_dfir_triage.ax"

HAVE_PROC = Path("/proc/self/comm").exists()


def _build(src: Path, out: Path, backend: str = "c") -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    args = [str(AXIOM), "build", str(src), "-o", str(out)]
    if backend == "llvm":
        args.insert(2, "--backend=llvm")
    res = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
    assert res.returncode == 0, res.stdout + res.stderr


def _run_binary(path: Path, env_extra=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run([str(path)], capture_output=True, text=True, timeout=120, env=env)


def _report(backend: str, log_path: Path):
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "dfir"
        _build(EXAMPLE, out, backend)
        res = _run_binary(out, {"AXIOM_DFIR_LOG": str(log_path)})
        assert res.returncode == 0, res.stderr
        return json.loads(res.stdout)


@pytest.fixture()
def auth_log(tmp_path):
    p = tmp_path / "auth.log"
    p.write_text(
        'Jan  1 00:00:00 web01 sshd[1]: Failed password for root from 1.2.3.4 port 22 ssh2\n'
        'Jan  1 00:00:01 web01 sshd[1]: Accepted password for root from 1.2.3.4 port 22 ssh2\n'
        'Jan  1 00:00:02 web01 apache: 10.0.0.9 - - "GET /index.php?id=1%20union%20select%20password HTTP/1.1" 200\n',
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# JSON semasi
# ---------------------------------------------------------------------------

def test_example_exists_and_compiles():
    assert EXAMPLE.is_file()
    with tempfile.TemporaryDirectory() as td:
        _build(EXAMPLE, Path(td) / "dfir")


@pytest.mark.skipif(not HAVE_PROC, reason="/proc yok (sandbox)")
def test_report_is_valid_json_with_expected_schema(auth_log):
    d = _report("c", auth_log)

    assert d["tool"] == "axiom-dfir-triage"
    assert d["version"] == "0.1.0"
    assert d["host"]
    assert int(d["timestamp_ms"]) > 0

    assert int(d["processes"]["count"]) > 0
    assert isinstance(d["processes"]["top"], list)
    assert d["processes"]["top"]
    # Her kayit tam olarak pid/name icermeli
    for p in d["processes"]["top"]:
        assert set(p) == {"pid", "name"}
        assert p["pid"].isdigit()

    assert isinstance(d["network"]["listening"], list)
    for p in d["network"]["listening"]:
        assert set(p) == {"ip", "port"}
        assert p["port"].isdigit()

    assert len(d["integrity"]) == 4
    for e in d["integrity"]:
        assert set(e) == {"path", "sha256", "status"}
        assert e["status"] in ("hashed", "missing", "unreadable")
        if e["status"] == "hashed":
            assert len(e["sha256"]) == 64

    assert d["log"]["source"] == str(auth_log)
    assert int(d["log"]["lines"]) == 3


@pytest.mark.skipif(not HAVE_PROC, reason="/proc yok")
def test_report_detects_sigma_matches(auth_log):
    d = _report("c", auth_log)
    ids = {i["rule_id"] for i in d["detections"]["items"]}
    assert "SSH_BRUTE_FORCE" in ids
    assert "SQL_INJECTION" in ids
    assert int(d["detections"]["total"]) >= 2
    assert int(d["detections"]["unique"]) == len(d["detections"]["items"])
    assert d["risk"]["verdict"] == "critical"
    assert int(d["risk"]["score"]) == 100


def test_report_without_log_is_still_valid(tmp_path):
    empty = tmp_path / "empty.log"
    empty.write_text("", encoding="utf-8")
    d = _report("c", empty)
    assert d["log"]["source"] == "none"
    assert d["detections"]["total"] == "0"
    assert d["risk"]["verdict"] == "info"


def test_real_proc_data_used(auth_log):
    """Surec listesi gercekten /proc'tan gelmeli (en az pid 1)."""
    d = _report("c", auth_log)
    pids = {p["pid"] for p in d["processes"]["top"]}
    assert "1" in pids


# ---------------------------------------------------------------------------
# Parite (iki arka uc ayni raporu uretmeli)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAVE_PROC, reason="/proc yok")
def test_c_and_llvm_reports_match(auth_log):
    c = _report("c", auth_log)
    llvm = _report("llvm", auth_log)
    for key in ("tool", "version", "host", "log", "detections",
                "risk", "network", "integrity"):
        assert c[key] == llvm[key], f"'{key}' C/LLVM farki: {c[key]} != {llvm[key]}"
    # Surec sayisi kosular arasinda degisebilir; alan yapisi ayni olmali
    assert set(c["processes"]) == set(llvm["processes"])


# ---------------------------------------------------------------------------
# Regresyonlar (P1-06 sirasinda bulunan gercek hatalar)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_str_array_of_locals_survives_scope_exit(backend):
    """C: `array_push` str elemani sahiplenmeli (use-after-free regresyonu)."""
    src = '''
fn build() -> str[] {
    let raw = str_split("aa\\nbb\\ncc", "\\n")
    let mut out: str[] = []
    let mut i = 0
    while (i < len(raw)) {
        let t = str_trim(raw[i])
        out = array_push(out, t)
        i = i + 1
    }
    return out
}

fn main() -> int {
    let parts = build()
    print(str_join(parts, ","))
    return 0
}
'''
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.ax"
        f.write_text(src, encoding="utf-8")
        out = Path(td) / "t"
        _build(f, out, backend)
        res = _run_binary(out)
        assert res.returncode == 0, res.stderr
        assert res.stdout.strip() == "aa,bb,cc"


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_string_escape_backslash_quote_preserved(backend):
    """LLVM: '\\"' tekrar cozumlenip veri kaybetmemeli."""
    src = '''
fn main() -> int {
    let a = str_replace("a\\"b", "\\"", "\\\\\\"")
    print(a)
    return 0
}
'''
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.ax"
        f.write_text(src, encoding="utf-8")
        out = Path(td) / "t"
        _build(f, out, backend)
        res = _run_binary(out)
        assert res.returncode == 0, res.stderr
        assert res.stdout.strip() == 'a\\"b'


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_str_join_array_literal(backend):
    """LLVM: str_join struct-by-value yerine byval ABI ile cagrilmali."""
    src = '''
fn main() -> int {
    let parts: str[] = ["x", "y", "z"]
    print(str_join(parts, "-"))
    let mut acc: str[] = []
    acc = array_push(acc, "1")
    acc = array_push(acc, "2")
    print(str_join(acc, "+"))
    return 0
}
'''
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.ax"
        f.write_text(src, encoding="utf-8")
        out = Path(td) / "t"
        _build(f, out, backend)
        res = _run_binary(out)
        assert res.returncode == 0, res.stderr
        assert res.stdout.splitlines() == ["x-y-z", "1+2"]


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_file_read_works_on_procfs(backend):
    """procfs dosyalari 'boyut 0' gorunur; file_read akisa gore okumali."""
    if not HAVE_PROC:
        pytest.skip("/proc yok")
    src = '''
fn main() -> int {
    let host = str_trim(file_read("/proc/sys/kernel/hostname"))
    print(len(host) > 0)
    let version = file_read("/proc/version")
    print(str_contains(version, "Linux"))
    return 0
}
'''
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.ax"
        f.write_text(src, encoding="utf-8")
        out = Path(td) / "t"
        _build(f, out, backend)
        res = _run_binary(out)
        assert res.returncode == 0, res.stderr
        assert res.stdout.splitlines() == ["true", "true"]
