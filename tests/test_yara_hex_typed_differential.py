"""Differential edge cases for supported typed YARA hex AST patterns.

These cases focus on fixed-width gaps adjacent to alternation groups and on
the occurrence list produced when those patterns match more than once.
"""

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
except ImportError:  # Optional reference engine.
    yara = None


@pytest.fixture(scope="module")
def engines(tmp_path_factory):
    if yara is None:
        pytest.skip("yara-python 4.5.4 is required for differential checks")
    assert yara.__version__ == "4.5.4", "these cases are pinned to YARA 4.5.4 semantics"
    output = tmp_path_factory.mktemp("typed-hex-differential") / "axiom-scan"
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


def _rule(pattern, condition="$a"):
    return (
        "rule TypedHexEdge {\n strings:\n  $a = { " + pattern + " }\n"
        " condition:\n  " + condition + "\n}\n"
    )


def _yara_instances(matches):
    return [
        (instance.offset, instance.matched_length)
        for string_match in matches[0].strings
        for instance in getattr(string_match, "instances", [])
    ] if matches else []


def _axiom_scan(scanner, tmp_path, source, target):
    rule_file = tmp_path / "edge.yar"
    sample = tmp_path / "edge.bin"
    rule_file.write_text(source, encoding="utf-8")
    sample.write_bytes(target)
    result = subprocess.run(
        [str(scanner), "scan", str(sample), "--rules", str(rule_file)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    ("pattern", "target", "expected"),
    [
        # A fixed gap after the group must be part of the typed sequence.
        ("41 ( 42 | 44 ) [2] 45", b"xABxyEy", [(1, 5)]),
        ("41 ( 42 | 44 ) [2] 45", b"xADxyEy", [(1, 5)]),
        # Fixed gaps on both sides of the group exercise prefix/group/suffix.
        ("41 [2] ( 42 | 44 ) [1] 45", b"xAxyBzEy", [(1, 6)]),
        ("41 [2] ( 42 | 44 ) [1] 45", b"xAxyDzEy", [(1, 6)]),
        # A valid branch with the wrong trailing gap must not match.
        ("41 ( 42 | 44 ) [2] 45", b"xABxEy", []),
        # Multiple separated occurrences should preserve ordered offsets.
        ("41 ( 42 | 44 ) [1] 45", b"ABxEADyE", [(0, 4), (4, 4)]),
    ],
)
def test_fixed_jumps_adjacent_to_alternation_match_yara(
    engines, tmp_path, pattern, target, expected
):
    source = _rule(pattern)
    reference = yara.compile(source=source).match(data=target)
    assert _yara_instances(reference) == expected

    report = _axiom_scan(engines, tmp_path, source, target)
    assert report["match_count"] == (1 if expected else 0)
    if expected:
        assert (report["matches"][0]["offset"], report["matches"][0]["length"]) == expected[0]


@pytest.mark.parametrize(
    ("condition", "expected_match"),
    [
        ("#a == 2", True),
        ("#a == 1", False),
        ("@a[2] == 4", True),
        ("@a[2] == 5", False),
        ("!a[2] == 4", True),
        ("!a[2] == 3", False),
    ],
)
def test_alternation_with_trailing_jump_occurrence_operators_match_yara(
    engines, tmp_path, condition, expected_match
):
    source = _rule("41 ( 42 | 44 ) [1] 45", condition)
    target = b"ABxEADyE"
    instance_source = _rule("41 ( 42 | 44 ) [1] 45")
    instances = _yara_instances(yara.compile(source=instance_source).match(data=target))
    assert instances == [(0, 4), (4, 4)]
    reference = yara.compile(source=source).match(data=target)
    assert bool(reference) is expected_match

    report = _axiom_scan(engines, tmp_path, source, target)
    assert report["match_count"] == (1 if expected_match else 0)


@pytest.mark.parametrize(
    ("pattern", "target", "condition", "expected_instances"),
    [
        # Bounded jumps over binary data must retain all occurrences and spans.
        ("41 [1-2] 42", b"A\x00B A1B", "#a == 2", [(0, 3), (4, 3)]),
        ("41 [1-2] 42", b"A\x00B A1B", "@a[2] == 4", [(0, 3), (4, 3)]),
        # Overlapping variable-range matches use the same occurrence rules.
        ("41 [1-2] 41", b"A1A1A", "#a == 2", [(0, 3), (2, 3)]),
        ("41 [1-2] 41", b"A1A1A", "!a[2] == 3", [(0, 3), (2, 3)]),
        # For multiple valid lengths at one start, both engines choose the
        # shortest instance for the occurrence witness.
        ("41 [1-3] 42", b"A1B2B", "#a == 1", [(0, 3)]),
    ],
)
def test_bounded_jump_occurrences_match_yara_on_binary_and_overlap(
    engines, tmp_path, pattern, target, condition, expected_instances
):
    source = _rule(pattern, condition)
    reference = yara.compile(source=source).match(data=target)
    assert _yara_instances(reference) == expected_instances

    report = _axiom_scan(engines, tmp_path, source, target)
    assert report["match_count"] == 1
    assert (report["matches"][0]["offset"], report["matches"][0]["length"]) == (
        expected_instances[0]
    )


@pytest.mark.parametrize(
    ("target", "expected_instances"),
    [
        (bytes.fromhex("4A 00 52"), [(0, 3)]),
        (bytes.fromhex("4A 52"), [(0, 2)]),
        (bytes.fromhex("3A 00 52"), []),
    ],
)
def test_nibble_masks_around_bounded_jump_match_yara(
    engines, tmp_path, target, expected_instances
):
    source = _rule("4? [0-1] ?2")
    reference = yara.compile(source=source).match(data=target)
    assert _yara_instances(reference) == expected_instances

    report = _axiom_scan(engines, tmp_path, source, target)
    assert report["match_count"] == (1 if expected_instances else 0)
    if expected_instances:
        assert (report["matches"][0]["offset"], report["matches"][0]["length"]) == (
            expected_instances[0]
        )


def test_negated_byte_occurrences_after_embedded_nul_match_yara(
    engines, tmp_path
):
    pattern = "41 00 ~42 44"
    target = bytes.fromhex("41 00 43 44 41 00 42 44 41 00 45 44")
    condition = "#a == 2 and @a[2] == 8 and !a[2] == 4"
    source = _rule(pattern, condition)
    reference = yara.compile(source=source).match(data=target)
    assert _yara_instances(reference) == [(0, 4), (8, 4)]

    report = _axiom_scan(engines, tmp_path, source, target)
    assert report["match_count"] == 1
    assert (report["matches"][0]["offset"], report["matches"][0]["length"]) == (
        0,
        4,
    )

