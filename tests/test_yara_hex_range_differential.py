"""Differential tests for bounded variable-width YARA hex jumps.

These cases exercise the planned `[min-max]` subset. The scanner fixture is
built when this test module is run; the authoring agent must not run it while
other agents are compiling the shared runtime.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

try:
    import yara
except ImportError:  # Optional reference engine.
    yara = None


ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
EXAMPLE = ROOT / "examples" / "21_axiom_scan.ax"
MAX_SUPPORTED_JUMP = 64
MAX_RANGE_SPAN = 16
YARA_UNAVAILABLE = object()


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


def _rule(pattern, condition="$a"):
    return (
        "rule HexRange {\n"
        " strings:\n"
        "  $a = { " + pattern + " }\n"
        " condition:\n"
        "  " + condition + "\n"
        "}\n"
    )


def _scan(scanner, tmp_path, pattern, target, condition="$a"):
    rules_path = tmp_path / "hex-range.yar"
    target_path = tmp_path / "target.bin"
    rules_path.write_text(_rule(pattern, condition), encoding="utf-8")
    target_path.write_bytes(target)
    result = subprocess.run(
        [str(scanner), "scan", str(target_path), "--rules", str(rules_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def _reference_instance(pattern, target):
    if yara is None:
        return YARA_UNAVAILABLE
    matches = yara.compile(source=_rule(pattern)).match(data=target)
    if not matches:
        return None
    match = matches[0]
    instances = []
    for string_match in match.strings:
        instances.extend(getattr(string_match, "instances", []))
    if not instances:
        pytest.skip("installed yara-python does not expose match instances")
    instance = instances[0]
    return instance.offset, instance.matched_length


@pytest.mark.parametrize(
    ("pattern", "target", "expected"),
    [
        # A zero-width range is an exact adjacency check.
        ("41 [0-0] 42", b"xxAByy", (2, 2)),
        # If two lengths match at the same start, YARA reports the shorter instance.
        ("41 [1-3] 42", b"A1B2B", (0, 3)),
        # Both inclusive bounds are exercised; the reported length includes
        # the number of bytes selected by the range at the successful match.
        ("41 [2-4] 42", b"xxA12Byy", (2, 4)),
        ("41 [2-4] 42", b"xxA1234Byy", (2, 6)),
    ],
)
def test_bounded_hex_ranges_match_yara_and_report_instance(
    scanner, tmp_path, pattern, target, expected
):
    reference = _reference_instance(pattern, target)
    result = _scan(scanner, tmp_path, pattern, target)
    if reference is not YARA_UNAVAILABLE:
        assert reference == expected
    assert result["match_count"] == 1
    assert result["matches"][0]["offset"] == expected[0]
    assert result["matches"][0]["length"] == expected[1]


@pytest.mark.parametrize(
    ("pattern", "target"),
    [
        ("41 [0-0] 42", b"xAqBy"),
        ("41 [2-4] 42", b"xA1Bq"),  # below the inclusive minimum
        ("41 [2-4] 42", b"xA12345Bq"),  # above the inclusive maximum
    ],
)
def test_bounded_hex_range_nonmatches_agree_with_yara(scanner, tmp_path, pattern, target):
    reference = _reference_instance(pattern, target)
    result = _scan(scanner, tmp_path, pattern, target)
    if reference is not YARA_UNAVAILABLE:
        assert reference is None
    assert result["match_count"] == 0


@pytest.mark.parametrize(
    "pattern",
    [
        "41 [4-2] 42",  # reversed bounds
        "41 [-4] 42",
        "41 [2--4] 42",
        "41 [a-4] 42",
        "41 [2-4 42",  # missing closing bracket
        "41 [2-4-6] 42",
        "[2-4]",  # wildcard-only effective pattern
    ],
)
def test_malformed_range_patterns_are_rejected_by_both_engines(scanner, tmp_path, pattern):
    if yara is not None:
        with pytest.raises(Exception):
            yara.compile(source=_rule(pattern))
    rules_path = tmp_path / "invalid-hex-range.yar"
    rules_path.write_text(_rule(pattern), encoding="utf-8")
    result = subprocess.run(
        [str(scanner), "rules", str(rules_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


@pytest.mark.parametrize(
    "pattern",
    [
        f"41 [{MAX_SUPPORTED_JUMP + 1}-{MAX_SUPPORTED_JUMP + 1}] 42",
        f"41 [0-{MAX_RANGE_SPAN + 1}] 42",  # span exceeds 16 bytes
    ],
)
def test_range_limits_are_rejected_even_if_upstream_yara_accepts_them(
    scanner, tmp_path, pattern
):
    if yara is not None:
        yara.compile(source=_rule(pattern))
    rules_path = tmp_path / "out-of-limit-hex-range.yar"
    rules_path.write_text(_rule(pattern), encoding="utf-8")
    result = subprocess.run(
        [str(scanner), "rules", str(rules_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


@pytest.mark.parametrize("pattern", ["41 [2-] 42"])
def test_valid_yara_ranges_outside_axiom_subset_are_explicitly_rejected(
    scanner, tmp_path, pattern
):
    if yara is not None:
        yara.compile(source=_rule(pattern))
    rules_path = tmp_path / "unsupported-valid-yara-range.yar"
    rules_path.write_text(_rule(pattern), encoding="utf-8")
    result = subprocess.run(
        [str(scanner), "rules", str(rules_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


@pytest.mark.parametrize(
    ("condition", "target", "expected_matches"),
    [
        ("$a at 2", b"xxA12Byy", 1),
        ("$a at 1", b"xxA12Byy", 0),
        ("$a in (2..3)", b"xxA12Byy", 1),
        ("$a in (0..1)", b"xxA12Byy", 0),
    ],
)
def test_range_jump_at_and_in_conditions(condition, target, expected_matches, scanner, tmp_path):
    rules_path = tmp_path / "hex-range-condition.yar"
    target_path = tmp_path / "target.bin"
    source = _rule("41 [2-4] 42", condition)
    if yara is not None:
        reference = yara.compile(source=source).match(data=target)
        assert bool(reference) is bool(expected_matches)
    rules_path.write_text(source, encoding="utf-8")
    target_path.write_bytes(target)
    result = subprocess.run(
        [str(scanner), "scan", str(target_path), "--rules", str(rules_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["match_count"] == expected_matches


@pytest.mark.parametrize(
    ("condition", "target", "expected"),
    [
        ("$a at 1", b"xA12B", (1, 4)),  # final possible start in the target
        ("$a at 2", b"xA12B", None),
        ("$a in (4..4)", b"xxxxA12B", (4, 4)),  # inclusive upper start; match ends later
        ("$a in (0..3)", b"xxxxA12B", None),
    ],
)
def test_range_condition_bounds_are_inclusive_start_offsets(
    scanner, tmp_path, condition, target, expected
):
    pattern = "41 [2-4] 42"
    source = _rule(pattern, condition)
    if yara is not None:
        reference = yara.compile(source=source).match(data=target)
        assert bool(reference) is (expected is not None)
        if expected is not None:
            offsets = [
                instance.offset
                for string_match in reference[0].strings
                for instance in getattr(string_match, "instances", [])
            ]
            assert expected[0] in offsets
    result = _scan(scanner, tmp_path, pattern, target, condition)
    if expected is None:
        assert result["match_count"] == 0
    else:
        assert result["match_count"] == 1
        assert (result["matches"][0]["offset"], result["matches"][0]["length"]) == expected


@pytest.mark.parametrize(
    ("pattern", "target", "condition", "expected"),
    [
        ("41 [1-3] 42", b"A1B A12B", "$a at 4", (4, 4)),
        ("41 [1-3] 42", b"A1B A12B", "$a in (4..7)", (4, 4)),
    ],
)
def test_range_condition_reports_the_occurrence_that_satisfied_it(
    scanner, tmp_path, pattern, target, condition, expected
):
    source = _rule(pattern, condition)
    # The reference engine exposes every instance; offset 4 is the one selected
    # by the condition, even though an earlier instance exists at offset 0.
    if yara is not None:
        matches = yara.compile(source=source).match(data=target)
        assert matches
        offsets = [
            instance.offset
            for string_match in matches[0].strings
            for instance in getattr(string_match, "instances", [])
        ]
        assert expected[0] in offsets
    result = _scan(scanner, tmp_path, pattern, target, condition)
    assert result["match_count"] == 1
    assert (result["matches"][0]["offset"], result["matches"][0]["length"]) == expected


def test_range_default_report_uses_first_yara_instance_when_many_exist(
    scanner, tmp_path
):
    pattern = "41 [1-3] 42"
    target = b"A1B A12B"
    source = _rule(pattern)
    if yara is not None:
        matches = yara.compile(source=source).match(data=target)
        instances = [
            (instance.offset, instance.matched_length)
            for string_match in matches[0].strings
            for instance in getattr(string_match, "instances", [])
        ]
        assert instances == [(0, 3), (4, 4)]
    result = _scan(scanner, tmp_path, pattern, target)
    assert result["match_count"] == 1
    assert (result["matches"][0]["offset"], result["matches"][0]["length"]) == (0, 3)


@pytest.mark.parametrize("condition", ["#a == 1", "@a[1] == 1", "!a[1] == 4"])
def test_occurrence_operators_for_range_jumps_fail_closed(condition, scanner, tmp_path):
    source = _rule("41 [2-4] 42", condition)
    if yara is not None:
        assert yara.compile(source=source).match(data=b"xA12B")
    rules_path = tmp_path / "hex-range-occurrence.yar"
    rules_path.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [str(scanner), "rules", str(rules_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False
