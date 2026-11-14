"""Differential tests for YARA group selector expansion and overlap counting."""

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
        pytest.skip("yara-python is unavailable; selector oracle skipped")
    assert getattr(yara, "__version__", None) == "4.5.4", (
        "selector differential oracle must be yara-python 4.5.4"
    )
    output = tmp_path_factory.mktemp("yara-selector-diff") / "axiom-scan"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        [str(AXIOM), "build", str(EXAMPLE), "-o", str(output)],
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return output


def _source(condition: str) -> str:
    if "$a*" in condition:
        strings = '  $a1 = "alpha"\n  $a2 = "beta"\n  $a3 = "gamma"\n'
    else:
        # YARA rejects unreferenced strings; explicit duplicate-selector cases
        # intentionally declare only the one identifier they select.
        strings = '  $a1 = "alpha"\n'
    return "rule SelectorDiff {\n strings:\n" + strings + " condition:\n  " + condition + "\n}\n"


def _assert_same(scanner, tmp_path, condition: str, target: bytes):
    source = _source(condition)
    reference = bool(yara.compile(source=source).match(data=target))
    rules = tmp_path / "selector.yar"
    sample = tmp_path / "target.bin"
    rules.write_text(source, encoding="utf-8")
    sample.write_bytes(target)
    result = subprocess.run(
        [str(scanner), "scan", str(sample), "--rules", str(rules)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["match_count"] == int(reference), (
        f"condition={condition!r}, target={target!r}, "
        f"YARA={reference}, Axiom={report}"
    )
    return reference


@pytest.mark.parametrize(
    ("condition", "target", "expected"),
    [
        ("any of ($a*, $a1)", b"alpha", True),
        ("any of ($a*, $a1)", b"beta", True),
        ("any of ($a*, $a1)", b"delta", False),
        ("all of ($a*, $a1)", b"alpha beta gamma", True),
        ("all of ($a*, $a1)", b"alpha beta", False),
        ("none of ($a*, $a1)", b"delta", True),
        ("none of ($a*, $a1)", b"beta", False),
        ("2 of ($a*, $a1)", b"alpha", True),
        ("3 of ($a*, $a1)", b"alpha", False),
        ("2 of ($a1, $a1)", b"alpha", True),
        ("all of ($a1, $a1)", b"alpha", True),
        ("none of ($a1, $a1)", b"delta", True),
        ("none of ($a1, $a1)", b"alpha", False),
        ("2 of ($a*, $a1) at 6", b"xxxxxxalpha", True),
        ("2 of ($a*, $a1) at 7", b"xxxxxxalpha", False),
        ("2 of ($a*, $a1) in (6..10)", b"xxxxxxalpha", True),
        ("2 of ($a*, $a1) in (7..10)", b"xxxxxxalpha", False),
    ],
)
def test_selector_overlap_and_thresholds_match_yara(
    scanner, tmp_path, condition, target, expected
):
    assert _assert_same(scanner, tmp_path, condition, target) is expected
