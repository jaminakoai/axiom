"""YARA 4.5.4 differential tests for condition-composition edge cases."""

import json
import os
import subprocess
from pathlib import Path

import pytest

try:
    import yara
except ImportError:
    yara = None

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
EXAMPLE = ROOT / "examples" / "21_axiom_scan.ax"


@pytest.fixture(scope="module")
def engines(tmp_path_factory):
    if yara is None:
        pytest.skip("yara-python is unavailable; condition differential oracle skipped")
    assert getattr(yara, "__version__", None) == "4.5.4", (
        "condition differential oracle must be yara-python 4.5.4"
    )
    if not EXAMPLE.exists():
        pytest.skip("axiom-scan example is missing")

    scanner = tmp_path_factory.mktemp("yara-condition-diff") / "axiom-scan"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    built = subprocess.run(
        [str(AXIOM), "build", str(EXAMPLE), "-o", str(scanner)],
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    return scanner


def _compare(engines, tmp_path, rule_source: str, target: bytes):
    scanner = engines
    reference = yara.compile(source=rule_source).match(data=target)
    expected = bool(reference)

    rules_path = tmp_path / "condition.yar"
    target_path = tmp_path / "target.bin"
    rules_path.write_text(rule_source, encoding="utf-8")
    target_path.write_bytes(target)
    result = subprocess.run(
        [str(scanner), "scan", str(target_path), "--rules", str(rules_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["match_count"] == int(expected)
    return expected


def _rule(strings: str, condition: str) -> str:
    return f"rule ConditionDiff {{\n strings:\n{strings} condition:\n  {condition}\n}}\n"


def test_explicit_selector_overlapping_wildcard_matches_yara_counting(engines, tmp_path):
    source = _rule(
        '  $a1 = "alpha"\n  $a2 = "beta"\n',
        "2 of ($a*, $a1)",
    )
    # YARA 4.5.4 counts the explicit selector alongside the wildcard match:
    # the same matched identifier satisfies both selector entries.
    assert _compare(engines, tmp_path, source, b"alpha") is True


@pytest.mark.parametrize(
    ("condition", "target"),
    [
        ("$a or $b and $c", b"alpha"),  # and binds more tightly than or
        ("($a or $b) and $c", b"alpha gamma"),
        ("($a or $b) and $c", b"alpha"),
        ("not ($a or $b) and $c and filesize == 5", b"gamma"),
        ("not ($a or $b) and $c and filesize == 4", b"gamma"),
    ],
)
def test_boolean_precedence_and_parentheses_match_yara(engines, tmp_path, condition, target):
    source = _rule(
        '  $a = "alpha"\n  $b = "beta"\n  $c = "gamma"\n',
        condition,
    )
    _compare(engines, tmp_path, source, target)


@pytest.mark.parametrize(
    ("condition", "target"),
    [
        ("any of ($a*) at 6", b"xxxxxxalpha beta"),
        ("any of ($a*) at 7", b"xxxxxxalpha beta"),
        ("all of ($a*) in (6..15)", b"xxxxxxalpha beta"),
        ("all of ($a*) in (6..11)", b"xxxxxxalpha beta"),
        ("any of ($a*) at 6 and filesize == 16", b"xxxxxxalpha beta"),
        ("any of ($a*) at 6 and filesize == 15", b"xxxxxxalpha beta"),
        ("2 of ($a*) in (0..10) and filesize == 16", b"xxxxxxalpha beta"),
    ],
)
def test_pattern_group_ranges_and_filesize_composition_match_yara(
    engines, tmp_path, condition, target
):
    source = _rule(
        '  $a1 = "alpha"\n  $a2 = "beta"\n',
        condition,
    )
    _compare(engines, tmp_path, source, target)
