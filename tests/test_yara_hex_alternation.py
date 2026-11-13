"""Parser and differential tests for Axiom's bounded YARA hex alternation subset.

The intended subset is one flat alternation group per pattern, with 2..4
branches of the same fixed byte length (1..16 bytes), each branch containing
only complete hex bytes and/or byte wildcards. Fixed `[N]` jumps may appear
outside the group. Nested/multiple groups, ranges in the same pattern, and
variable-length branches remain unsupported and must fail during rule parsing.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from axiom.cli import find_c_compiler

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
EXAMPLE = ROOT / "examples" / "21_axiom_scan.ax"

try:
    import yara
except ImportError:  # Optional reference engine.
    yara = None


@pytest.fixture(scope="module")
def scanner(tmp_path_factory):
    if not EXAMPLE.exists():
        pytest.skip("scanner example is missing")
    output = tmp_path_factory.mktemp("hex-alternation-scan") / "axiom-scan"
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
        "rule HexAlternation {\n"
        " strings:\n"
        "  $a = { " + pattern + " }\n"
        " condition:\n"
        "  " + condition + "\n"
        "}\n"
    )


def _run(scanner, tmp_path, command, rules_text, target=None):
    rules_path = tmp_path / "hex-alternation.yar"
    rules_path.write_text(rules_text, encoding="utf-8")
    args = [str(scanner), command]
    if command == "scan":
        target_path = tmp_path / "target.bin"
        target_path.write_bytes(target)
        args.extend([str(target_path), "--rules", str(rules_path)])
    else:
        args.append(str(rules_path))
    return subprocess.run(args, capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize(
    ("pattern", "target", "expected"),
    [
        ("41 ( 42 | 44 ) 43", b"xABCy", (1, 3)),
        ("41 ( 42 | 44 ) 43", b"xADCy", (1, 3)),
        ("41 ( 42 43 | 44 45 ) 46", b"xABCFy", (1, 4)),
        ("41 ( 42 43 | 44 45 ) 46", b"xADEFy", (1, 4)),
        ("41 ( 4? 43 | 44 ?5 ) 46", b"xACCFy", (1, 4)),
        ("41 ( 4? 43 | 44 ?5 ) 46", b"xADEFy", (1, 4)),
        ("41 ( 42 | 43 | 44 | 45 ) 46", b"xADFy", (1, 3)),
        ("41 [2] ( 42 | 44 ) 43", b"xA12BCy", (1, 5)),
    ],
)
def test_hex_alternation_matches_yara_and_reports_instance(
    scanner, tmp_path, pattern, target, expected
):
    source = _rule(pattern)
    if yara is not None:
        reference_matches = yara.compile(source=source).match(data=target)
        assert reference_matches
        instances = [
            instance
            for string_match in reference_matches[0].strings
            for instance in getattr(string_match, "instances", [])
        ]
        assert instances, "yara-python must expose match instances for this check"
        assert (instances[0].offset, instances[0].matched_length) == expected

    result = _run(scanner, tmp_path, "scan", source, target)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["match_count"] == 1
    assert (report["matches"][0]["offset"], report["matches"][0]["length"]) == expected


@pytest.mark.parametrize(
    ("pattern", "target"),
    [
        ("41 ( 42 | 44 ) 43", b"xAECy"),
        ("41 ( 42 43 | 44 45 ) 46", b"xABDFy"),
        ("41 ( 4? 43 | 44 ?5 ) 46", b"xA43Fy"),
    ],
)
def test_hex_alternation_nonmatches_agree_with_yara(scanner, tmp_path, pattern, target):
    source = _rule(pattern)
    if yara is not None:
        assert not yara.compile(source=source).match(data=target)
    result = _run(scanner, tmp_path, "scan", source, target)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["match_count"] == 0


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ("$a at 4", (4, 3)),
        ("$a in (4..6)", (4, 3)),
        ("$a at 0 or $a at 4", (0, 3)),
        ("$a at 1 or $a at 4", (4, 3)),
        ("($a at 1) or ($a in (4..6))", (4, 3)),
    ],
)
def test_alternation_position_condition_reports_its_witness(scanner, tmp_path, condition, expected):
    source = _rule("41 ( 42 | 44 ) 43", condition)
    target = b"ABC ADC"
    if yara is not None:
        matches = yara.compile(source=source).match(data=target)
        assert matches
        offsets = [
            instance.offset
            for string_match in matches[0].strings
            for instance in getattr(string_match, "instances", [])
        ]
        assert expected[0] in offsets
    result = _run(scanner, tmp_path, "scan", source, target)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["match_count"] == 1
    assert (report["matches"][0]["offset"], report["matches"][0]["length"]) == expected


def test_alternation_default_report_matches_first_yara_instance(scanner, tmp_path):
    pattern = "41 ( 42 | 44 ) 43"
    target = b"ABC ADC"
    source = _rule(pattern)
    if yara is not None:
        matches = yara.compile(source=source).match(data=target)
        instances = [
            (instance.offset, instance.matched_length)
            for string_match in matches[0].strings
            for instance in getattr(string_match, "instances", [])
        ]
        assert instances == [(0, 3), (4, 3)]
    result = _run(scanner, tmp_path, "scan", source, target)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["match_count"] == 1
    assert (report["matches"][0]["offset"], report["matches"][0]["length"]) == (0, 3)


def test_same_offset_matching_alternation_branches_report_one_instance(scanner, tmp_path):
    pattern = "( 4? | ?2 )"
    target = b"B"  # 0x42 satisfies both one-byte branches at offset zero.
    source = _rule(pattern)
    if yara is not None:
        matches = yara.compile(source=source).match(data=target)
        instances = [
            (instance.offset, instance.matched_length)
            for string_match in matches[0].strings
            for instance in getattr(string_match, "instances", [])
        ]
        assert instances == [(0, 1)]
    result = _run(scanner, tmp_path, "scan", source, target)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["match_count"] == 1
    assert (report["matches"][0]["offset"], report["matches"][0]["length"]) == (0, 1)


@pytest.mark.parametrize(
    "pattern",
    [
        "41 ( | 42 ) 43",  # empty branch
        "41 ( 42 | ) 43",  # empty branch
        "41 ( 42 43 | 44 ) 45",  # variable-length branch
        "41 ( 42 | 43 ) ( 44 | 45 ) 46",  # more than one group
        "41 ( 42 | ( 43 | 44 ) ) 45",  # nested alternation
        "41 ( 42 | 43 | 44 | 45 | 46 ) 47",  # more than four branches
        "41 ( 42 | 43 ) [1-2] 45",  # range jump in the same pattern
        "41 ( 42 [1] | 43 ) 45",  # fixed jump inside a branch
        "41 ( 42 || 43 ) 45",  # malformed separator
        "41 ( GG | 43 ) 45",  # malformed byte
        "41 ( " + " ".join(["42"] * 17) + " | " + " ".join(["43"] * 17) + " ) 45",
    ],
)
def test_unsupported_or_malformed_hex_alternation_is_rejected(
    scanner, tmp_path, pattern
):
    result = _run(scanner, tmp_path, "rules", _rule(pattern))
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


@pytest.mark.parametrize("condition", ["#a == 1", "@a[1] == 0", "!a[1] == 3"])
def test_occurrence_operators_for_hex_alternation_fail_closed(scanner, tmp_path, condition):
    # The scanner does not yet provide occurrence metadata for the union of
    # alternate branches, so these operators must not silently guess.
    source = _rule("41 ( 42 | 44 ) 43", condition)
    if yara is not None:
        assert yara.compile(source=source).match(data=b"ABC")
    result = _run(
        scanner,
        tmp_path,
        "rules",
        source,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


def test_hex_alternation_runtime_matches_and_validates_encoded_branches():
    source = r'''
    #include "axiom/runtime.h"
    #include <stdio.h>

    #define CHECK(expr) do { if (!(expr)) { \
        fprintf(stderr, "failed at line %d: %s\n", __LINE__, #expr); return 1; \
    } } while (0)

    int main(void) {
        const char* encoded = "hexalt:41 42 43|41 44 43|41 45 43";
        const char target[] = {'x', 'A', 'D', 'C', 'y', 'A', 'E', 'C', '\0'};
        CHECK(axiom_yara_find_hex_alternation(target, encoded, -1, -1) == 1);
        CHECK(axiom_yara_find_hex_alternation(target, encoded, 2, -1) == 5);
        CHECK(axiom_yara_find_hex_alternation(target, encoded, 0, 4) == 1);
        CHECK(axiom_yara_find_hex_alternation(target, encoded, 2, 4) == -1);
        CHECK(axiom_yara_hex_alternation_len(encoded) == 3);

        CHECK(axiom_yara_find_hex_alternation("AB", "hexalt:4?|?2", -1, -1) == 0);
        CHECK(axiom_yara_hex_alternation_len("hexalt:4?|?2") == 1);
        CHECK(axiom_yara_find_hex_alternation("AB", "hexalt:??|??", -1, -1) == -1);
        CHECK(axiom_yara_find_hex_alternation("ABC", "hexalt:41|42 43", -1, -1) == -1);
        CHECK(axiom_yara_find_hex_alternation("ABC", "hexalt:41", -1, -1) == -1);
        CHECK(axiom_yara_find_hex_alternation("ABC", "hexalt:{41}|{42}", -1, -1) == -1);
        CHECK(axiom_yara_find_hex_alternation("ABC", "hexalt:41|42|43|44|45", -1, -1) == -1);
        CHECK(axiom_yara_hex_alternation_len("hexalt:41|42 43") == -1);
        CHECK(axiom_yara_find_hex_alternation("ABC", "hexalt:41 41 41 41 41 41 41 41 41 41 41 41 41 41 41 41 41|42 42 42 42 42 42 42 42 42 42 42 42 42 42 42 42 42", -1, -1) == -1);
        puts("YARA_HEX_ALTERNATION_RUNTIME_OK");
        return 0;
    }
    '''
    cc = find_c_compiler()
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as src_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        src_path, bin_path = src_file.name, bin_file.name
        src_file.write(source)
    try:
        compiled = subprocess.run(
            [cc, "-O2", "-Wall", "-I", str(ROOT), src_path, "-o", bin_path,
             "-lssl", "-lcrypto", "-lz", "-ldl", "-pthread"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert compiled.returncode == 0, compiled.stderr
        result = subprocess.run([bin_path], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        assert "YARA_HEX_ALTERNATION_RUNTIME_OK" in result.stdout
    finally:
        for path in (src_path, bin_path):
            if os.path.exists(path):
                os.remove(path)
