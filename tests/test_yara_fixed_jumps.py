"""Parser and scan checks for bounded fixed-width YARA hex jumps."""
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
except ImportError:  # Optional differential oracle.
    yara = None


@pytest.fixture(scope="module")
def scanner(tmp_path_factory):
    if not EXAMPLE.exists():
        pytest.skip("scanner example is missing")
    output = tmp_path_factory.mktemp("fixed-jump-scan") / "axiom-scan"
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
        "rule FixedJump {\n strings:\n  $a = { " + pattern + " }\n"
        " condition:\n  $a\n}\n"
    )


@pytest.mark.parametrize(
    ("pattern", "target", "expected"),
    [
        ("41 [1] 42", b"AqB", True),
        ("41 [3] 42", b"AxyzB", True),
        ("41 [64] 42", b"A" + b"x" * 64 + b"B", True),
        ("41 [2] 42", b"AqB", False),
        ("4? [2] 42", b"AqzB", True),
        ("41 42", b"AB", True),
    ],
)
def test_fixed_width_jumps_match_and_agree_with_yara(scanner, tmp_path, pattern, target, expected):
    source = _rule(pattern)
    rules = tmp_path / "fixed-jump.yar"
    rules.write_text(source, encoding="utf-8")
    sample = tmp_path / "target.bin"
    sample.write_bytes(target)

    result = subprocess.run(
        [str(scanner), "scan", str(sample), "--rules", str(rules)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    axiom_match = json.loads(result.stdout)["match_count"] == 1
    assert axiom_match is expected

    if yara is not None:
        reference = yara.compile(source=source)
        assert bool(reference.match(data=target)) is axiom_match


@pytest.mark.parametrize(
    "pattern",
    [
        "41 [0] 42",        # zero-width form is intentionally unsupported
        "41 [65] 42",       # per-jump cap is 64 bytes
        "41 [1-2] 42",      # variable-width ranges are not in this subset
        "41 [1-] 42",        # unbounded jump
        "41 [] 42",
        "41 [abc] 42",
        "41 [2 42",
        "41 ]42",
        "41 (42 | 43)",      # alternation
        "41 ~00",            # negation
        "41 GG 42",          # invalid byte token
        "41 4 42",           # odd nibble
        "41 ? 42",           # lone wildcard nibble
        "?? [1] ??",          # no constrained byte
    ],
)
def test_unsupported_or_malformed_hex_is_rejected(scanner, tmp_path, pattern):
    rules = tmp_path / "invalid-fixed-jump.yar"
    rules.write_text(_rule(pattern), encoding="utf-8")
    result = subprocess.run(
        [str(scanner), "rules", str(rules)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


def test_total_fixed_jump_expansion_is_capped_before_runtime(scanner, tmp_path):
    # Each jump fits the per-jump cap, but the combined normalized pattern
    # would exceed the runtime's 8 KiB limit if the parser did not cap it too.
    pattern = " ".join(["41 [64]"] * 43) + " 41"
    rules = tmp_path / "oversized-expanded-pattern.yar"
    rules.write_text(_rule(pattern), encoding="utf-8")

    result = subprocess.run(
        [str(scanner), "rules", str(rules)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False
