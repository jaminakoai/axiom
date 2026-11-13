"""Parser-level tests for bounded variable-width YARA hex jumps."""
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
EXAMPLE = ROOT / "examples" / "21_axiom_scan.ax"

try:
    import yara
except ImportError:  # Optional reference parser.
    yara = None


@pytest.fixture(scope="module")
def scanner(tmp_path_factory):
    if not EXAMPLE.exists():
        pytest.skip("scanner example is missing")
    output = tmp_path_factory.mktemp("hex-range-scan") / "axiom-scan"
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


def _rule(pattern):
    return (
        "rule HexRange {\n strings:\n  $a = { " + pattern + " }\n"
        " condition:\n  $a\n}\n"
    )


def _parse_rule_file(scanner, tmp_path, source):
    rules = tmp_path / "hex-range.yar"
    rules.write_text(source, encoding="utf-8")
    return subprocess.run(
        [str(scanner), "rules", str(rules)],
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize(
    "pattern",
    [
        "41 [0-0] 42",
        "41 [0-16] 42",
        "41 [2-4] 42",
        "41 [64-64] 42",
        "41 [2] 42 [0-4] 43 [1] 44",  # fixed jumps still normalize to ??
        "4? [0-1] ?2",
    ],
)
def test_bounded_hex_range_jump_is_accepted_and_yara_compiles(scanner, tmp_path, pattern):
    source = _rule(pattern)
    result = _parse_rule_file(scanner, tmp_path, source)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ok"] is True

    if yara is not None:
        yara.compile(source=source)


@pytest.mark.parametrize(
    "pattern",
    [
        "[1-2] 41",          # empty left side
        "41 [1-2]",          # empty right side
        "41 [3-2] 42",       # reversed bounds
        "41 [0-65] 42",      # endpoint exceeds 64
        "41 [1-18] 42",      # range width exceeds 16
        "41 [1-2-3] 42",     # malformed range
        "41 [1 -2] 42",      # whitespace inside jump syntax
        "41 [1-] 42",        # unbounded jump
        "41 [1-2] [2-3] 42", # more than one variable-width jump
        "41 [1-2] [3] 42 [4-5] 43",
        "41 [65] 42",        # fixed-width jump cap still applies
    ],
)
def test_unsupported_hex_ranges_are_rejected(scanner, tmp_path, pattern):
    result = _parse_rule_file(scanner, tmp_path, _rule(pattern))
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


def test_hex_range_encoding_size_is_capped(scanner, tmp_path):
    # The parser's compact representation must also fit the runtime limit.
    left = " ".join(["41"] * 2050)
    right = " ".join(["42"] * 2050)
    result = _parse_rule_file(scanner, tmp_path, _rule(left + " [1-2] " + right))
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False
