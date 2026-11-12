"""
Axiom - P2-17 (kısmi): sonucu atılan ifadelerin geçici string temizliği

Bilinen sınır (README/TODO'da yazılıydı):
    `print(f(x))` gibi ATAMA YAPILMAYAN ifadelerde üretilen geçici string'ler
    ifade sonunda bırakılmıyordu.

Bu dosya düzeltmeyi kilitler:
  - `PrintStmt`: argümanlar bitince geçici mark'a kadar temizlenir
  - `ExprStmt`: atılan sonucun geçicileri temizlenir
  - `axiom_temp_release_keep`: saklanan değeri dış kapsam da görebilir
    (yoksa "adopt edilen" değer de sızıyordu)

Parite notu: `str_owned_count()` yalnızca C arka ucunda vardır (LLVM'de
diagnostik builtin yok). Bu yüzden sayısal büyüme kontrolü C'de, davranış
kontrolü iki arka uçta yapılır; ASan testi de iki arka uçta koşar.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"


def _write(src: str) -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8")
    f.write(src)
    f.close()
    return f.name


def _run(args, timeout=300):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(args, capture_output=True, text=True, env=env, timeout=timeout)


def _run_source(src: str, backend: str = "c", asan: bool = False):
    path = _write(src)
    out = path + ".bin"
    try:
        args = [str(AXIOM), "build", path, "-o", out]
        if backend == "llvm":
            args.insert(2, "--backend=llvm")
        if asan:
            args.insert(2, "--asan")
        b = _run(args)
        assert b.returncode == 0, b.stdout + b.stderr
        return subprocess.run([out], capture_output=True, text=True, timeout=180)
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)


# ---------------------------------------------------------------------------
# Sayısal büyüme (C: str_owned_count)
# ---------------------------------------------------------------------------

def test_print_of_temporary_does_not_grow_owned_count():
    src = '''
fn make(s: str) -> str {
    return s + "-x"
}

fn main() -> int {
    let base = str_owned_count()
    let mut i = 0
    while (i < 500) {
        print(make("b"))
        i = i + 1
    }
    print("__GROWTH__", str_owned_count() - base)
    return 0
}
'''
    res = _run_source(src)
    assert res.returncode == 0, res.stderr
    line = [l for l in res.stdout.splitlines() if l.startswith("__GROWTH__")][0]
    assert line == "__GROWTH__ 0", f"print(f(x)) sızıntısı: {line}"


def test_discarded_expression_statement_does_not_grow():
    src = '''
fn make(s: str) -> str {
    return s + "-x"
}

fn main() -> int {
    let base = str_owned_count()
    let mut i = 0
    while (i < 500) {
        make("c")          # ifade deyimi: sonuc atılır
        i = i + 1
    }
    print("__GROWTH__", str_owned_count() - base)
    return 0
}
'''
    res = _run_source(src)
    assert res.returncode == 0, res.stderr
    line = [l for l in res.stdout.splitlines() if l.startswith("__GROWTH__")][0]
    assert line == "__GROWTH__ 0", f"ifade deyimi sızıntısı: {line}"


def test_adopted_let_still_freed_at_scope_exit():
    """Saklanan değer sızmamalı; kapsam çıkışında bırakılmalı."""
    src = '''
fn make(s: str) -> str {
    return s + "-x"
}

fn main() -> int {
    let base = str_owned_count()
    let mut i = 0
    while (i < 300) {
        let v = make("a")
        if len(v) > 0 {
            i = i + 1
            continue
        }
    }
    print("__GROWTH__", str_owned_count() - base)
    return 0
}
'''
    res = _run_source(src)
    assert res.returncode == 0, res.stderr
    line = [l for l in res.stdout.splitlines() if l.startswith("__GROWTH__")][0]
    assert line == "__GROWTH__ 0", f"let sızıntısı: {line}"


def test_nested_call_chain_does_not_grow():
    """f(g(h(x))) zincirinde ara sonuçlar da bırakılmalı."""
    src = '''
import "std/encoding/hex"
import "std/encoding/base64"

fn main() -> int {
    let base = str_owned_count()
    let mut i = 0
    while (i < 300) {
        print(base64_encode(hex_encode("payload")))
        i = i + 1
    }
    print("__GROWTH__", str_owned_count() - base)
    return 0
}
'''
    res = _run_source(src)
    assert res.returncode == 0, res.stderr
    line = [l for l in res.stdout.splitlines() if l.startswith("__GROWTH__")][0]
    assert line == "__GROWTH__ 0", f"iç içe çağrı sızıntısı: {line}"


# ---------------------------------------------------------------------------
# Davranış doğruluğu (iki arka uç) — temizlik değeri bozmamalı
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_values_are_correct_after_cleanup(backend):
    src = '''
fn make(s: str) -> str {
    return s + "-x"
}

fn main() -> int {
    let mut acc = ""
    let mut i = 0
    while (i < 40) {
        let v = make("a")
        acc = acc + v + ","
        print(make("p"))
        i = i + 1
    }
    print("ACC_LEN", len(acc))
    print("STARTS", str_starts_with(acc, "a-x,a-x,"))
    print("COUNT", str_len(acc) / 4)
    return 0
}
'''
    res = _run_source(src, backend)
    assert res.returncode == 0, res.stderr
    lines = res.stdout.splitlines()
    assert "ACC_LEN 160" in lines
    assert "STARTS true" in lines
    assert "COUNT 40" in lines


# ---------------------------------------------------------------------------
# ASan: gerçek sızıntı yok (iki arka uç)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_no_leak_under_asan(backend):
    src = '''
fn make(s: str) -> str {
    return s + "-x"
}

fn main() -> int {
    let mut i = 0
    while (i < 800) {
        print(make("b"))
        i = i + 1
    }
    return 0
}
'''
    res = _run_source(src, backend, asan=True)
    assert res.returncode == 0, (res.stdout + res.stderr)[:3000]
    combined = res.stdout + res.stderr
    assert "LeakSanitizer" not in combined, combined[:3000]
    assert "AddressSanitizer" not in combined, combined[:3000]


# ---------------------------------------------------------------------------
# Belge: sınır artık "bilinen sınır" değil
# ---------------------------------------------------------------------------

def test_readme_no_longer_lists_this_as_known_limit():
    """README'deki 'atama yapılmayan ifadelerde sızıntı' maddesi kalkmış olmalı."""
    for name in ("README.md", "README.en.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "atama yapılmayan ifadelerde" not in text, f"{name} hâlâ eski sınırı yazıyor"
        assert "not assigned" not in text, f"{name} hâlâ eski sınırı yazıyor"


# ---------------------------------------------------------------------------
# break / continue: döngü gövdesi kapsamı temizlenmeli
# ---------------------------------------------------------------------------

def test_continue_cleans_loop_body_scope():
    src = '''
fn make(s: str) -> str { return s + "-x" }
fn main() -> int {
    let base = str_owned_count()
    let mut i = 0
    while (i < 300) {
        let v = make("a")
        if len(v) > 0 {
            i = i + 1
            continue
        }
    }
    print("__GROWTH__", str_owned_count() - base)
    return 0
}
'''
    res = _run_source(src)
    assert res.returncode == 0, res.stderr
    line = [l for l in res.stdout.splitlines() if l.startswith("__GROWTH__")][0]
    assert line == "__GROWTH__ 0", f"continue sızıntısı: {line}"


def test_break_cleans_loop_body_scope():
    src = '''
fn make(s: str) -> str { return s + "-x" }
fn main() -> int {
    let base = str_owned_count()
    let mut i = 0
    while (i < 300) {
        let v = make("b")
        i = i + 1
        break
    }
    print("__GROWTH__", str_owned_count() - base)
    return 0
}
'''
    res = _run_source(src)
    assert res.returncode == 0, res.stderr
    line = [l for l in res.stdout.splitlines() if l.startswith("__GROWTH__")][0]
    assert line == "__GROWTH__ 0", f"break sızıntısı: {line}"


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_nested_continue_does_not_break_outer_scope(backend):
    src = '''
fn make(s: str) -> str { return s + "-x" }
fn main() -> int {
    let outer = "outer-value"
    let mut bad = 0
    let mut a = 0
    while (a < 40) {
        let mut b = 0
        while (b < 40) {
            let t = make("c")
            if b % 2 == 0 {
                b = b + 1
                continue
            }
            b = b + 1
        }
        if outer != "outer-value" {
            bad = bad + 1
        }
        a = a + 1
    }
    print("BAD", bad)
    print("OUTER", outer)
    return 0
}
'''
    res = _run_source(src, backend)
    assert res.returncode == 0, res.stderr
    assert res.stdout.splitlines() == ["BAD 0", "OUTER outer-value"]


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_defer_runs_on_continue(backend):
    """Döngü gövdesindeki defer, continue'da da çalışmalı (kapsam çıkışı)."""
    src = '''
fn main() -> int {
    let mut i = 0
    let mut hits = 0
    while (i < 5) {
        defer { hits = hits + 1 }
        i = i + 1
        continue
    }
    print("HITS", hits)
    return 0
}
'''
    res = _run_source(src, backend)
    assert res.returncode == 0, res.stderr
    assert res.stdout.splitlines() == ["HITS 5"]
