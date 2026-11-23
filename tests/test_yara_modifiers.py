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


@pytest.fixture(scope="module")
def scanner_llvm(tmp_path_factory):
    if not EXAMPLE.exists():
        pytest.skip("axiom-scan example not found")
    output = tmp_path_factory.mktemp("yara-modifiers-llvm") / "axiom-scan"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        [str(AXIOM), "build", str(EXAMPLE), "--backend=llvm", "-o", str(output)],
        capture_output=True,
        text=True,
        timeout=900,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return output


def _rule_source(pattern, condition="$a"):
    return (
        "rule ModifierCheck {\n"
        " strings:\n"
        f"  $a = {pattern}\n"
        " condition:\n"
        f"  {condition}\n"
        "}\n"
    )


def _axiom_scan(scanner, tmp_path, pattern, target, condition="$a"):
    rules_path = tmp_path / "modifier.yar"
    target_path = tmp_path / "target.bin"
    rules_path.write_text(_rule_source(pattern, condition), encoding="utf-8")
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


@pytest.mark.parametrize(
    ("pattern", "condition", "target", "expected"),
    [
        ('"needle" wide', "$a", b"xx" + "needle".encode("utf-16le") + b"yy", (2, 12)),
        ('"NeEdLe" wide nocase', "$a", b"xx" + "needle".encode("utf-16le") + b"yy", (2, 12)),
        ('"needle" wide ascii', "#a == 2", b"needle xx" + "needle".encode("utf-16le"), (0, 6)),
        ('"needle" wide fullword', "$a", " needle ".encode("utf-16le"), (2, 12)),
        ('"needle" wide', "$a", b"xxneedleyy", None),
        ('"needle" wide fullword', "$a", "9needle9".encode("utf-16le"), None),
        ('"needle" wide', "$a", b"x" + "needle".encode("utf-16le"), (1, 12)),
        ('"A" wide ascii', "#a == 1 and !a[1] == 1", bytes((65, 0)), (0, 1)),
    ],
)
def test_wide_modifier_matches_yara_reference_on_both_backends(
    scanner, scanner_llvm, tmp_path, pattern, condition, target, expected
):
    yara = pytest.importorskip("yara")
    source = _rule_source(pattern, condition)
    reference = yara.compile(source=source).match(data=target)
    instances = []
    if reference:
        instances = [
            (instance.offset, instance.matched_length)
            for string_match in reference[0].strings
            for instance in string_match.instances
        ]
    assert bool(instances) is (expected is not None)
    if expected is not None:
        assert instances[0] == expected

    reports = []
    for executable in (scanner, scanner_llvm):
        report = _axiom_scan(executable, tmp_path, pattern, target, condition)
        assert report["match_count"] == int(expected is not None)
        if expected is not None:
            assert report["matches"][0]["offset"] == expected[0]
            assert report["matches"][0]["length"] == expected[1]
        reports.append(report)
    assert reports[0] == reports[1]


def test_wide_occurrence_selectors_match_yara_overlapping_instances(scanner, scanner_llvm, tmp_path):
    yara = pytest.importorskip("yara")
    pattern = '"aba" wide'
    target = "ababa".encode("utf-16le")
    for condition in (
        "#a == 2",
        "@a[2] == 4",
        "!a[1] == 6 and !a[2] == 6",
    ):
        source = _rule_source(pattern, condition)
        reference = yara.compile(source=source).match(data=target)
        assert reference
        for executable in (scanner, scanner_llvm):
            report = _axiom_scan(executable, tmp_path, pattern, target, condition)
            assert report["match_count"] == 1


def test_wide_offset_condition_reports_selected_occurrence(scanner, scanner_llvm, tmp_path):
    yara = pytest.importorskip("yara")
    pattern = '"aba" wide'
    target = "ababa".encode("utf-16le")
    for condition in ("$a at 4", "$a in (4..8)"):
        source = _rule_source(pattern, condition)
        assert yara.compile(source=source).match(data=target)
        reports = []
        for executable in (scanner, scanner_llvm):
            report = _axiom_scan(executable, tmp_path, pattern, target, condition)
            assert report["match_count"] == 1
            assert report["matches"][0]["offset"] == 4
            assert report["matches"][0]["length"] == 6
            reports.append(report)
        assert reports[0] == reports[1]


def test_ascii_wide_same_offset_is_one_ascii_instance(scanner, scanner_llvm, tmp_path):
    yara = pytest.importorskip("yara")
    pattern = '"A" ascii wide'
    target = bytes((65, 0))
    condition = "#a == 1 and !a[1] == 1"
    source = _rule_source(pattern, condition)
    assert yara.compile(source=source).match(data=target)
    for executable in (scanner, scanner_llvm):
        report = _axiom_scan(executable, tmp_path, pattern, target, condition)
        assert report["match_count"] == 1
        assert report["matches"][0]["offset"] == 0
        assert report["matches"][0]["length"] == 1


def test_malformed_internal_modifier_flags_fail_closed():
    source = '''
import "std/security/yara"
fn main() -> int {
    let bad_text = yara_scan_single_pattern("needle", "$a", "str:flags:bad:needle", -1, -1)
    let bad_bits = yara_scan_single_pattern("needle", "$a", "str:flags:16:needle", -1, -1)
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
