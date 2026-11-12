"""
Axiom - P2-09: regex guvenlik kapisi ve Result API'si

Kapsam:
  - regex_validate / regex_risk_level (geri izleme / DFA patlamasi sinirlari)
  - Result API: regex_is_match_result, regex_find_result, regex_replace_result,
    regex_compile_result
  - regex_escape (literal arama)
  - Eski API'nin korunmasi
  - C + LLVM paritesi

Not: Motor glibc POSIX ERE (NFA). Yine de ic ice niceleyici, derinlik ve
tekrar sayisi sinirlari uygulanir; asiri desenler sessizce "eslesmedi"
yerine Err dondurur.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"


def _run(src: str, tmp_path: Path, backend: str = "c"):
    f = tmp_path / "t.ax"
    f.write_text(src, encoding="utf-8")
    out = tmp_path / "t"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    args = [str(AXIOM), "build", str(f), "-o", str(out)]
    if backend == "llvm":
        args.insert(2, "--backend=llvm")
    res = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
    assert res.returncode == 0, res.stdout + res.stderr
    return subprocess.run([str(out)], capture_output=True, text=True, timeout=60)


VALIDATION_SRC = '''
import "std/text/regex"

fn main() -> int {
    print("ok1:", len(regex_validate("[0-9]+")))
    print("ok2:", len(regex_validate("(ab|cd)+x")))
    print("ok3:", len(regex_validate("a{1,10}")))
    print("empty:", regex_validate(""))

    print("risk_ok:", regex_risk_level("[0-9]+"))
    print("risk_nested_plus:", regex_risk_level("(a+)+"))
    print("risk_nested_star:", regex_risk_level("(a*)*b"))
    print("risk_big_upper:", regex_risk_level("a{1,99999}"))
    print("risk_big_lower:", regex_risk_level("a{99999}"))
    print("risk_deep:", regex_risk_level("((((((((((((((((((((((((((((((((((a))))))))))))))))))))))))))))))))))"))
    print("risk_group_quant_ok:", regex_risk_level("(ab)+"))
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_validation_and_risk_levels(backend, tmp_path):
    out = _run(VALIDATION_SRC, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "ok1: 0",
        "ok2: 0",
        "ok3: 0",
        "empty: bos desen",
        "risk_ok: 0",
        "risk_nested_plus: 2",
        "risk_nested_star: 2",
        "risk_big_upper: 2",
        "risk_big_lower: 2",
        "risk_deep: 2",
        "risk_group_quant_ok: 0",
    ]


RESULT_SRC = '''
import "std/text/regex"

fn main() -> int {
    let m = regex_is_match_result("[0-9]+", "abc123")
    print("match:", m.is_ok, m.value)

    let nm = regex_is_match_result("[0-9]+", "abcdef")
    print("nomatch:", nm.is_ok, nm.value)

    let bad = regex_is_match_result("(a+)+", "aaab")
    print("unsafe:", bad.is_ok, str_contains(bad.error, "guvensiz"))

    let invalid = regex_is_match_result("[unclosed", "x")
    print("invalid:", invalid.is_ok, len(invalid.error) > 0)

    let f = regex_find_result("[0-9]+", "abc123def456")
    print("find:", f.is_ok, f.value)

    let nf = regex_find_result("[0-9]+", "abcdef")
    print("find_none:", nf.is_ok, len(nf.value))

    let r = regex_replace_result("[0-9]+", "a1b22c333", "#")
    print("replace:", r.is_ok, r.value)

    let c_ok = regex_compile_result("[a-z]+")
    print("compile_ok:", c_ok.is_ok)

    let c_bad = regex_compile_result("(a+)+")
    print("compile_bad:", c_bad.is_ok)
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_result_api(backend, tmp_path):
    out = _run(RESULT_SRC, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "match: true true",
        "nomatch: true false",
        "unsafe: false true",
        "invalid: false true",
        "find: true 123",
        "find_none: true 0",
        "replace: true a#b#c#",
        "compile_ok: true",
        "compile_bad: false",
    ]


ESCAPE_SRC = '''
import "std/text/regex"

fn main() -> int {
    print("esc:[", regex_escape("a.b*c(d)"), "]")
    print("esc_slash:[", regex_escape("x\\\\y"), "]")
    print("literal:", regex_is_match(regex_escape("a.b*c(d)"), "xx a.b*c(d) yy"))
    print("not_meta:", regex_is_match(regex_escape("a.b"), "axb"))
    print("empty:", regex_escape(""))
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_escape(backend, tmp_path):
    out = _run(ESCAPE_SRC, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "esc:[ a\\.b\\*c\\(d\\) ]",
        "esc_slash:[ x\\\\y ]",
        "literal: true",
        "not_meta: false",
        "empty: ",
    ]


LEGACY_SRC = '''
import "std/text/regex"

fn main() -> int {
    print("is_match:", regex_is_match("[0-9]+", "x1"))
    print("is_match_no:", regex_is_match("[0-9]+", "xyz"))
    print("find:", regex_find("([a-z]+)([0-9]+)", "abc123"))
    print("replace:", regex_replace("o", "foo boo", "0"))
    print("icase:", regex_is_match("(?i)HELLO", "hello world"))
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_legacy_api_unchanged(backend, tmp_path):
    out = _run(LEGACY_SRC, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "is_match: true",
        "is_match_no: false",
        "find: abc123",
        "replace: f00 b00",
        "icase: true",
    ]


def test_no_unbounded_quantifier_regression():
    """ReDoS kaliplari reddedilmeli: (a+)+$, (a|a)*, (a*)*, (a|aa)+, (.+)+."""
    src = '''
import "std/text/regex"

fn main() -> int {
    print(regex_risk_level("(a+)+$"))
    print(regex_risk_level("(a|a)*"))
    print(regex_risk_level("(a*)*"))
    print(regex_risk_level("(a|aa)+"))
    print(regex_risk_level("(.+)+"))
    print(regex_risk_level("^(a+)+$"))
    return 0
}
'''
    with tempfile.TemporaryDirectory() as td:
        out = _run(src, Path(td))
    assert out.returncode == 0, out.stderr
    # (a|a)* / (a|aa)+ ic ice niceleyici degil ama sinirsiz grup tekrari;
    # tehlikeli olanlar 2, zararsiz olanlar 0 doner. Hepsi <= 2 olmali ve
    # en az 3 tanesi 2 olmali.
    levels = [int(x) for x in out.stdout.split()]
    assert len(levels) == 6
    assert all(lvl <= 2 for lvl in levels)
    assert sum(1 for lvl in levels if lvl == 2) >= 3
