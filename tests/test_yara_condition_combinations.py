"""Differential tests for composed YARA group/range/boolean conditions."""

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
def scanner(tmp_path_factory):
    if yara is None:
        pytest.skip("yara-python is unavailable; condition oracle skipped")
    assert getattr(yara, "__version__", None) == "4.5.4", (
        "condition combinations require yara-python 4.5.4"
    )
    output = tmp_path_factory.mktemp("yara-condition-combinations") / "axiom-scan"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    built = subprocess.run(
        [str(AXIOM), "build", str(EXAMPLE), "-o", str(output)],
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    return output


def _rule(condition: str) -> str:
    if "$a*" in condition or "of them" in condition:
        strings = '  $a1 = "alpha"\n  $a2 = "beta"\n'
    else:
        strings = '  $a1 = "alpha"\n'
    return f"rule ConditionCombinations {{\n strings:\n{strings} condition:\n  {condition}\n}}\n"


def _compare(scanner, tmp_path, condition: str, target: bytes) -> bool:
    source = _rule(condition)
    expected = bool(yara.compile(source=source).match(data=target))
    rules = tmp_path / "condition.yar"
    sample = tmp_path / "target.bin"
    rules.write_text(source, encoding="utf-8")
    sample.write_bytes(target)
    actual = subprocess.run(
        [str(scanner), "scan", str(sample), "--rules", str(rules)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert actual.returncode == 0, actual.stdout + actual.stderr
    report = json.loads(actual.stdout)
    assert report["ok"] is True
    assert report["match_count"] == int(expected), (
        f"condition={condition!r}, target={target!r}, YARA={expected}, "
        f"Axiom={report}"
    )
    return expected


@pytest.mark.parametrize(
    ("condition", "target", "expected"),
    [
        # Zero threshold remains the complement of any selected match and
        # composes with filesize in both directions.
        ("0 of ($a*) and filesize == 5", b"delta", True),
        ("0 of ($a*) and filesize == 4", b"delta", False),
        ("0 of ($a*) or filesize == 5", b"alpha", True),
        ("0 of ($a*) or filesize == 4", b"alpha", False),
        # Group truth values compose with ordinary pattern and boolean terms.
        ("any of ($a*) and filesize == 5", b"alpha", True),
        ("all of ($a*) and filesize == 5", b"alpha", False),
        ("none of ($a*) or filesize == 5", b"alpha", True),
        ("none of ($a*) or $a1", b"alpha", True),
        ("none of ($a*) and $a1", b"alpha", False),
        # Offset-constrained groups are negated/grouped before boolean
        # composition; ranges are inclusive and filesize is independently
        # checked on the same target.
        ("not (any of ($a*) at 0) and filesize == 11", b"xxxxxxalpha", True),
        ("not (any of ($a*) at 6) and filesize == 11", b"xxxxxxalpha", False),
        ("all of ($a*) in (6..15) and filesize == 16", b"xxxxxxalpha beta", True),
        ("all of ($a*) in (6..10) or filesize == 16", b"xxxxxxalpha beta", True),
        ("all of ($a*) in (6..10) and filesize == 16", b"xxxxxxalpha beta", False),
        ("2 of ($a*) in (6..15) and filesize == 16", b"xxxxxxalpha beta", True),
        ("2 of ($a*) in (7..15) and filesize == 16", b"xxxxxxalpha beta", False),
        # `them` selectors and zero-of edge behavior remain composable too.
        ("none of them and filesize == 5", b"delta", True),
        ("0 of them or filesize == 5", b"alpha", True),
        ("0 of them and filesize == 5", b"alpha", False),
    ],
)
def test_group_boolean_filesize_combinations_match_yara(
    scanner, tmp_path, condition, target, expected
):
    assert _compare(scanner, tmp_path, condition, target) is expected
