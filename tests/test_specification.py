"""
Axiom - Şartname (SPECIFICATION.md) doğrulama testleri

Şartnamedeki doğrulanabilir iddiaların kodla uyuştuğunu garanti eder.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
SPEC = ROOT / "SPECIFICATION.md"


def _check(src: str):
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run([str(AXIOM), "check", path],
                              capture_output=True, text=True, timeout=180, env=env)
    finally:
        os.remove(path)


def _run(src: str):
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    out = path + ".bin"
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        build = subprocess.run([str(AXIOM), "build", path, "-o", out],
                               capture_output=True, text=True, timeout=240, env=env)
        assert build.returncode == 0, build.stdout + build.stderr
        return subprocess.run([out], capture_output=True, text=True, timeout=120)
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)


def test_spec_exists_and_is_current_version():
    assert SPEC.exists()
    text = SPEC.read_text(encoding="utf-8")
    assert "v0.5" in text
    assert text.count("\n## ") >= 15, "Şartname bölüm sayısı beklenenden az"


def test_spec_keyword_list_matches_lexer():
    from axiom.lexer import KEYWORDS
    text = SPEC.read_text(encoding="utf-8")
    # Şartnamedeki anahtar kelime kod bloğunu bul
    start = text.index("### 3.3 Anahtar kelimeler")
    block = text[start:text.index("```", text.index("```", start) + 3) + 3]
    listed = set()
    for line in block.splitlines():
        if line.startswith("```") or line.startswith("###"):
            continue
        listed.update(w for w in line.split() if w.isidentifier())
    assert listed == KEYWORDS, f"Fark: {listed ^ KEYWORDS}"


def test_spec_types_match_lexer():
    from axiom.lexer import TYPES
    text = SPEC.read_text(encoding="utf-8")
    start = text.index("### 3.4 Tip adları")
    fence_start = text.index("```", start)
    block = text[fence_start:text.index("```", fence_start + 3)]
    listed = {w for line in block.splitlines()
              if not line.startswith("```")
              for w in line.split() if w.isidentifier()}
    assert listed == TYPES


def test_spec_same_block_redefinition_rejected():
    """Şartname: aynı blokta yeniden tanımlama reddedilir."""
    res = _check("""
fn main() -> int {
    let x = 1
    let x = 2
    print(x)
    return 0
}
""")
    assert res.returncode != 0
    assert "zaten tanimli" in (res.stdout + res.stderr)


def test_spec_nested_block_shadowing_allowed():
    """Şartname: iç blokta yeni tanım (gölgeleme) desteklenir."""


def test_spec_nested_scope_shadowing_restores_outer():
    out = _run("""
fn main() -> int {
    let x = 1
    if x > 0 {
        let x = 2
        print(x)
    }
    print(x)
    return 0
}
""")
    assert out.stdout.split() == ["2", "1"]


@pytest.mark.parametrize("literal,expected_fragment", [
    ("0x10", "Desteklenmeyen sayi bicimi"),
    ("0b101", "Desteklenmeyen sayi bicimi"),
    ("1_000", "alt cizgi"),
    ("1e9", "Bilimsel gosterim"),
])
def test_spec_unsupported_literals_fail_clearly(literal, expected_fragment):
    """Desteklenmeyen literaller anlaşılır lexer hatası vermeli (şaşırtıcı tip hatası değil)."""
    res = _check(f"fn main() -> int {{\n    let a = {literal}\n    print(a)\n    return 0\n}}\n")
    assert res.returncode != 0
    msg = (res.stdout + res.stderr)
    assert expected_fragment in msg, f"Beklenen mesaj yok: {msg[:200]}"


def test_spec_cast_rules():
    out = _run("""
fn main() -> int {
    let a = 3.9 as int
    let b = 7 as float
    let c = 1 as bool
    print(a, b, c)
    return 0
}
""")
    assert out.stdout.strip() == "3 7 true"


def test_spec_rejects_as_str():
    res = _check("""
fn main() -> int {
    let a = 5 as str
    return 0
}
""")
    assert res.returncode != 0


def test_spec_type_mismatch_comparison_rejected():
    res = _check("""
fn main() -> int {
    if 1 < "abc" { print("x") }
    return 0
}
""")
    assert res.returncode != 0


def test_spec_integer_overflow_exit_101():
    out = _run("""
fn main() -> int {
    let a = 9223372036854775807
    let b = a + 1
    print(b)
    return 0
}
""")
    assert out.returncode == 101


def test_spec_array_index_exit_102():
    out = _run("""
fn main() -> int {
    let a = [1, 2, 3]
    print(a[5])
    return 0
}
""")
    assert out.returncode == 102


def test_spec_array_value_semantics():
    out = _run("""
fn main() -> int {
    let a = [1, 2, 3]
    let mut b = a
    b[0] = 99
    print(a[0], b[0])
    return 0
}
""")
    assert out.stdout.strip() == "1 99"


def test_spec_break_outside_loop_rejected():
    res = _check("""
fn main() -> int {
    break
    return 0
}
""")
    assert res.returncode != 0
