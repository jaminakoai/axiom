"""Parser and differential tests for exact-byte YARA hex negation."""

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
    output = tmp_path_factory.mktemp("hex-negation-scan") / "axiom-scan"
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
        "rule HexNegation {\n"
        " strings:\n"
        "  $a = { " + pattern + " }\n"
        " condition:\n"
        "  " + condition + "\n"
        "}\n"
    )


def _run(scanner, tmp_path, command, rules_text, target=None):
    rules_path = tmp_path / "hex-negation.yar"
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
        ("41 ~42 43", b"xADCy", (1, 3)),
        ("41 ~?2 43", b"xADCy", (1, 3)),
        ("41 ~A? 43", b"xABCy", (1, 3)),
        ("41 ~42 43", b"xABCy", None),
        ("41 ~?2 43", b"xABCy", None),
        ("41 4? ~43 44", b"xABEDy", (1, 4)),
        ("41 [2] ~42 43", b"xA12DCy", (1, 5)),
        ("~42", b"AB", (0, 1)),
        ("~42", b"B", None),
    ],
)
def test_exact_byte_negation_matches_yara_and_reports_instance(
    scanner, tmp_path, pattern, target, expected
):
    source = _rule(pattern)
    if yara is not None:
        reference = yara.compile(source=source).match(data=target)
        if expected is None:
            assert not reference
        else:
            assert reference
            instances = [
                instance
                for string_match in reference[0].strings
                for instance in getattr(string_match, "instances", [])
            ]
            assert instances, "yara-python must expose match instances for this check"
            assert (instances[0].offset, instances[0].matched_length) == expected

    result = _run(scanner, tmp_path, "scan", source, target)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    if expected is None:
        assert report["match_count"] == 0
    else:
        assert report["match_count"] == 1
        assert (report["matches"][0]["offset"], report["matches"][0]["length"]) == expected


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ("$a at 8", (8, 3)),
        ("$a in (8..10)", (8, 3)),
        ("$a at 4", None),
        ("$a in (4..7)", None),
    ],
)
def test_negation_position_condition_reports_its_witness(scanner, tmp_path, condition, expected):
    source = _rule("41 ~42 43", condition)
    target = b"ADC ABC AEC"
    if yara is not None:
        matches = yara.compile(source=source).match(data=target)
        assert bool(matches) is (expected is not None)
        if expected is not None:
            offsets = [
                instance.offset
                for string_match in matches[0].strings
                for instance in getattr(string_match, "instances", [])
            ]
            assert expected[0] in offsets
    result = _run(scanner, tmp_path, "scan", source, target)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["match_count"] == (1 if expected is not None else 0)
    if expected is not None:
        assert (report["matches"][0]["offset"], report["matches"][0]["length"]) == expected


def test_negation_default_report_matches_first_yara_instance(scanner, tmp_path):
    pattern = "41 ~42 43"
    target = b"ADC ABC AEC"
    source = _rule(pattern)
    if yara is not None:
        matches = yara.compile(source=source).match(data=target)
        instances = [
            (instance.offset, instance.matched_length)
            for string_match in matches[0].strings
            for instance in getattr(string_match, "instances", [])
        ]
        assert instances == [(0, 3), (8, 3)]
    result = _run(scanner, tmp_path, "scan", source, target)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["match_count"] == 1
    assert (report["matches"][0]["offset"], report["matches"][0]["length"]) == (0, 3)


@pytest.mark.parametrize(
    "pattern",
    [
        "~?? 41",
        "~ 41",
        "~~42 41",
        "~GG 41",
        "~4 41",
        "~42 ~43",  # only one negated byte per pattern
        "41 [1-2] ~42",  # negation and variable-width range are not composed yet
        "41 (42 | 43) ~44",  # negation and alternation are not composed yet
    ],
)
def test_unsupported_or_malformed_negation_is_rejected(scanner, tmp_path, pattern):
    result = _run(scanner, tmp_path, "rules", _rule(pattern))
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


@pytest.mark.parametrize("condition", ["#a == 1", "@a[1] == 0", "!a[1] == 3"])
def test_negated_pattern_occurrence_operators_fail_closed(scanner, tmp_path, condition):
    source = _rule("41 ~42 43", condition)
    if yara is not None:
        assert yara.compile(source=source).match(data=b"ADC")
    result = _run(
        scanner,
        tmp_path,
        "rules",
        source,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


def test_hex_negation_runtime_full_and_nibble_masks():
    source = r'''
    #include "axiom/runtime.h"
    #include <stdio.h>

    #define CHECK(expr) do { if (!(expr)) { \
        fprintf(stderr, "failed at line %d: %s\n", __LINE__, #expr); return 1; \
    } } while (0)

    int main(void) {
        const char* encoded = "hexnot:41|42|43";
        CHECK(axiom_yara_find_hex_negation("xADCy", encoded, -1, -1) == 1);
        CHECK(axiom_yara_find_hex_negation("xABCy", encoded, -1, -1) == -1);
        CHECK(axiom_yara_find_hex_negation("xADCy", encoded, 2, -1) == -1);
        CHECK(axiom_yara_hex_negation_len(encoded) == 3);

        CHECK(axiom_yara_find_hex_negation("A", "hexnot:|?2|", -1, -1) == 0);
        CHECK(axiom_yara_find_hex_negation("B", "hexnot:|?2|", -1, -1) == -1);
        CHECK(axiom_yara_find_hex_negation("B", "hexnot:|A?|", -1, -1) == 0);
        const char excluded_high_nibble[] = {(char)0xA1, '\0'};
        CHECK(axiom_yara_find_hex_negation(excluded_high_nibble, "hexnot:|A?|", -1, -1) == -1);
        CHECK(axiom_yara_find_hex_negation("AC", "hexnot:|42|43", -1, -1) == 0);
        CHECK(axiom_yara_find_hex_negation("AB", "hexnot:|42|43", -1, -1) == -1);
        CHECK(axiom_yara_find_hex_negation("xAD", "hexnot:41|42|", -1, -1) == 1);

        CHECK(axiom_yara_find_hex_negation("xA12DCy", "hexnot:41 ?? ??|42|43", -1, -1) == 1);
        CHECK(axiom_yara_hex_negation_len("hexnot:41 ?? ??|42|43") == 5);
        CHECK(axiom_yara_find_hex_negation("ABC", "hexnot:41|??|43", -1, -1) == -1);
        CHECK(axiom_yara_find_hex_negation("ABC", "hexnot:41|4|43", -1, -1) == -1);
        CHECK(axiom_yara_find_hex_negation("ABC", "hexnot:41|42", -1, -1) == -1);
        CHECK(axiom_yara_find_hex_negation("ABC", "hexnot:41|42|43|44", -1, -1) == -1);
        puts("YARA_HEX_NEGATION_RUNTIME_OK");
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
        assert "YARA_HEX_NEGATION_RUNTIME_OK" in result.stdout
    finally:
        for path in (src_path, bin_path):
            if os.path.exists(path):
                os.remove(path)
