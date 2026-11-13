"""Focused behavior checks for the supported YARA text modifiers."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
EXAMPLE = ROOT / "examples" / "21_axiom_scan.ax"


@pytest.fixture(scope="module")
def scanner(tmp_path_factory):
    if not EXAMPLE.exists():
        pytest.skip("axiom-scan example not found")
    output = tmp_path_factory.mktemp("yara-modifiers") / "axiom-scan"
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


def _rule_source(pattern):
    return (
        "rule ModifierCheck {\n"
        " strings:\n"
        f"  $a = {pattern}\n"
        " condition:\n"
        "  $a\n"
        "}\n"
    )


def _axiom_scan(scanner, tmp_path, pattern, target):
    rules_path = tmp_path / "modifier.yar"
    target_path = tmp_path / "target.bin"
    rules_path.write_text(_rule_source(pattern), encoding="utf-8")
    target_path.write_bytes(target)
    result = subprocess.run(
        [str(scanner), "scan", str(target_path), "--rules", str(rules_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    ("pattern", "target", "expected_offset", "expected_length"),
    [
        ('"needle" nocase', b"xxNeEdLeYY", 2, 6),
        ('"needle" ascii', b"xxneedleYY", 2, 6),
        # YARA fullword boundaries exclude ASCII letters/digits, not `_` or punctuation.
        ('"domain" fullword', b"_domain_", 1, 6),
        # The first occurrence is inside an alphanumeric token; the second is valid.
        ('"domain" fullword', b"9domain9 domain", 9, 6),
        ('"needle" ascii nocase fullword', b"!!NEEDLE!YY", 2, 6),
    ],
)
def test_supported_modifiers_match_yara_reference(
    scanner, tmp_path, pattern, target, expected_offset, expected_length
):
    yara = pytest.importorskip("yara")
    source = _rule_source(pattern)
    reference = yara.compile(source=source).match(data=target)
    axiom = _axiom_scan(scanner, tmp_path, pattern, target)

    assert bool(reference) is True
    assert axiom["match_count"] == 1
    assert axiom["matches"][0]["offset"] == expected_offset
    assert axiom["matches"][0]["length"] == expected_length


def test_fullword_rejects_matches_inside_ascii_alphanumeric_tokens(scanner, tmp_path):
    yara = pytest.importorskip("yara")
    pattern = '"domain" fullword'
    target = b"9domain9"

    assert yara.compile(source=_rule_source(pattern)).match(data=target) == []
    axiom = _axiom_scan(scanner, tmp_path, pattern, target)
    assert axiom["match_count"] == 0


def test_wide_modifier_is_rejected_instead_of_scanned_as_ascii(scanner, tmp_path):
    rules_path = tmp_path / "wide.yar"
    rules_path.write_text(_rule_source('"needle" wide'), encoding="utf-8")

    result = subprocess.run(
        [str(scanner), "rules", str(rules_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


def test_yara_reference_accepts_wide_utf16le_string():
    yara = pytest.importorskip("yara")
    source = _rule_source('"needle" wide')
    assert yara.compile(source=source).match(data="needle".encode("utf-16le"))


def test_malformed_internal_modifier_flags_fail_closed():
    source = '''
import "std/security/yara"
fn main() -> int {
    let bad_text = yara_scan_single_pattern("needle", "$a", "str:flags:bad:needle", -1, -1)
    let bad_bits = yara_scan_single_pattern("needle", "$a", "str:flags:4:needle", -1, -1)
    print("bad_text:", bad_text.matched)
    print("bad_bits:", bad_bits.matched)
    print("bad_count:", yara_count_single_pattern("needle", "str:flags:bad:needle"))
    return 0
}
'''
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(source)
        source_path = f.name
    output_path = source_path + ".bin"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    try:
        build = subprocess.run(
            [str(AXIOM), "build", source_path, "-o", output_path],
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        assert build.returncode == 0, build.stdout + build.stderr
        run = subprocess.run([output_path], capture_output=True, text=True, timeout=120)
        assert run.returncode == 0, run.stdout + run.stderr
        assert run.stdout.splitlines() == ["bad_text: false", "bad_bits: false", "bad_count: -1"]
    finally:
        os.remove(source_path)
        if os.path.exists(output_path):
            os.remove(output_path)
