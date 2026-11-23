"""
Axiom - axiom-scan v0.1 (P1-03)

YARA alt kümesi ayrıştırma + dosya/PCAP tarama + JSON çıktısı + hata yolları.
"""
import json
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
EXAMPLE = ROOT / "examples" / "21_axiom_scan.ax"
SCAN_REPORT_SCHEMA = json.loads(
    (ROOT / "docs" / "api" / "axiom-scan-report.schema.json").read_text(encoding="utf-8")
)
Draft202012Validator.check_schema(SCAN_REPORT_SCHEMA)
SCAN_REPORT_VALIDATOR = Draft202012Validator(SCAN_REPORT_SCHEMA)


def _assert_report_matches_schema(report):
    SCAN_REPORT_VALIDATOR.validate(report)
    if "rules" in report:
        assert report["rules"] == report["rules_count"]
    if "matches" in report:
        assert report["match_count"] == len(report["matches"])
    if "packets" in report:
        assert report["packet_count"] >= len(report["packets"])
        assert report["match_count"] == sum(len(packet["rules"]) for packet in report["packets"])

RULES = """
// yorum satiri
rule Suspicious_Powershell {
    strings:
        $a = "powershell -enc"
        $b = "CreateRemoteThread"
    condition:
        any of them
}

rule Hex_Shellcode {
    strings:
        $x = { 48 89 ?? 55 }
    condition:
        any of them
}

rule Both_Required {
    strings:
        $m = "MZ"
        $p = "This program cannot be run"
    condition:
        all of them
}
"""


@pytest.fixture(scope="module")
def scanner(tmp_path_factory):
    if not EXAMPLE.exists():
        pytest.skip("ornek bulunamadi")
    exe = ".exe" if os.name == "nt" else ""
    out = tmp_path_factory.mktemp("scan") / f"axiom-scan{exe}"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "ascii:backslashreplace"
    res = subprocess.run(
        [sys.executable, str(AXIOM), "build", str(EXAMPLE), "-o", str(out)],
        capture_output=True, text=True, timeout=600, env=env,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    return out


def _run(scanner, *args):
    return subprocess.run([str(scanner)] + list(args), capture_output=True,
                          text=True, timeout=120)


def test_rules_command_counts(scanner, tmp_path):
    r = tmp_path / "rules.yar"
    r.write_text(RULES, encoding="utf-8")
    res = _run(scanner, "rules", str(r))
    assert res.returncode == 0, res.stdout + res.stderr
    data = json.loads(res.stdout)
    _assert_report_matches_schema(data)
    assert data["ok"] is True
    assert data["rules"] == 3


def test_public_onboarding_sentinel(scanner, tmp_path):
    """Exercise the documented harmless rules + scan flow on native runners."""
    import hashlib

    marker = "AXIOM_EXTERNAL_VALIDATION_SENTINEL_v1"
    rules = tmp_path / "external-validation.yar"
    rules.write_text(
        'rule Axiom_External_Validation {\n'
        '  strings:\n'
        f'    $marker = "{marker}" ascii\n'
        '  condition:\n'
        '    $marker\n'
        '}\n',
        encoding="utf-8",
    )
    payload = f"Axiom external validation sentinel: {marker}\n".encode("ascii")
    target = tmp_path / "external-validation.txt"
    target.write_bytes(payload)

    rules_result = _run(scanner, "rules", str(rules))
    assert rules_result.returncode == 0, rules_result.stdout + rules_result.stderr
    rules_report = json.loads(rules_result.stdout)
    assert rules_report["ok"] is True
    assert rules_report["rules"] == 1

    scan_result = _run(scanner, "scan", str(target), "--rules", str(rules))
    assert scan_result.returncode == 0, scan_result.stdout + scan_result.stderr
    report = json.loads(scan_result.stdout)
    assert report["ok"] is True
    assert report["match_count"] == 1
    assert report["target_sha256"] == hashlib.sha256(payload).hexdigest()
    assert report["matches"] == [{
        "rule": "Axiom_External_Validation",
        "tags": [],
        "meta": {},
        "pattern": "$marker",
        "offset": payload.index(marker.encode("ascii")),
        "length": len(marker),
    }]


@pytest.mark.parametrize("condition", [
    "entrypoint",
    "uint16(0) == 0x5A4D",
    # YARA accepts signed integer literals, but this subset deliberately
    # rejects unary numeric operators instead of silently mis-evaluating them.
    "filesize > -1",
])
def test_unsupported_conditions_are_rejected_instead_of_defaulting_to_any(scanner, tmp_path, condition):
    rules = tmp_path / "unsupported.yar"
    rules.write_text(
        'rule Unsupported {\n strings:\n  $a = "needle"\n condition:\n  '
        + condition + "\n}\n",
        encoding="utf-8",
    )
    res = _run(scanner, "rules", str(rules))
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["ok"] is False
    assert "condition" in data["error"]


@pytest.mark.parametrize(("condition", "target", "expected"), [
    ("$a and not $b", b"alpha", True),
    ("$a and not $b", b"alpha beta", False),
    ("$a or $b and $c", b"alpha", True),
    ("($a or $b) and $c", b"alpha", False),
    ("not ($a or $b)", b"gamma", True),
    ("not ($a or $b)", b"alpha", False),
])
def test_boolean_condition_subset(scanner, tmp_path, condition, target, expected):
    rules = tmp_path / "boolean.yar"
    rules.write_text(
        'rule BooleanRule {\n strings:\n  $a = "alpha"\n  $b = "beta"\n'
        '  $c = "gamma"\n condition:\n  ' + condition + "\n}\n",
        encoding="utf-8",
    )
    sample = tmp_path / "target.bin"
    sample.write_bytes(target)
    res = _run(scanner, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["match_count"] == int(expected)


@pytest.mark.parametrize(("condition", "target", "expected"), [
    ("any of ($a*)", b"beta", 1),
    ("all of ($a*)", b"alpha beta", 1),
    ("all of ($a*)", b"alpha", 0),
    ("none of ($a*)", b"gamma", 1),
    ("2 of ($a*)", b"alpha beta", 1),
    ("2 of ($a*)", b"alpha", 0),
    ("0 of ($a*)", b"gamma", 1),
    ("0 of ($a*)", b"alpha", 0),
    ("any of ($b)", b"gamma", 1),
    ("any of ($a1, $b)", b"gamma", 1),
    ("2 of ($a1, $b)", b"alpha gamma", 1),
    ("all of ($a*, $b)", b"alpha beta gamma", 1),
    ("3 of ($a*, $a1, $b)", b"alpha beta gamma", 1),
    ("any of ($a*) or $b", b"gamma", 1),
    ("any of them and filesize == 5", b"alpha", 1),
    ("none of them or $b", b"gamma", 1),
    ("2 of them and filesize == 10", b"alpha beta", 1),
    ("0 of them", b"nothing", 1),
    ("0 of them", b"alpha", 0),
    ("any of ($a*) at 6", b"xxxxxxalpha beta", 1),
    ("all of ($a*) in (6..15)", b"xxxxxxalpha beta", 1),
    ("2 of ($a*) in (0..10)", b"xxxxxxalpha beta", 0),
    ("none of them at 0", b"xalpha", 1),
])
def test_pattern_group_conditions(scanner, tmp_path, condition, target, expected):
    rules = tmp_path / "pattern-groups.yar"
    rules.write_text(
        'rule PatternGroups {\n strings:\n  $a1 = "alpha"\n  $a2 = "beta"\n'
        '  $b = "gamma"\n condition:\n  ' + condition + "\n}\n",
        encoding="utf-8",
    )
    sample = tmp_path / "group-target.bin"
    sample.write_bytes(target)
    res = _run(scanner, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["match_count"] == expected


@pytest.mark.parametrize("condition", [
    "any of ($missing*)", "any of ($a*, $missing)", "any of ($a*", "any of (a*)",
    "any of ($a?)",
])
def test_invalid_pattern_group_conditions_are_rejected(scanner, tmp_path, condition):
    rules = tmp_path / "invalid-pattern-group.yar"
    rules.write_text(
        'rule InvalidGroup {\n strings:\n  $a1 = "alpha"\n condition:\n  '
        + condition + "\n}\n",
        encoding="utf-8",
    )
    res = _run(scanner, "rules", str(rules))
    assert res.returncode == 1
    assert "condition" in json.loads(res.stdout)["error"]


@pytest.mark.parametrize("condition", [
    "any of ($a*) in (10..2)", "any of ($a*) at", "any of ($a*) in (1..2",
])
def test_invalid_pattern_group_ranges_are_rejected(scanner, tmp_path, condition):
    rules = tmp_path / "invalid-pattern-group-range.yar"
    rules.write_text(
        'rule InvalidRange {\n strings:\n  $a1 = "alpha"\n condition:\n  '
        + condition + "\n}\n",
        encoding="utf-8",
    )
    res = _run(scanner, "rules", str(rules))
    assert res.returncode == 1
    assert "condition" in json.loads(res.stdout)["error"]


def test_pattern_group_range_counts_each_pattern_once(scanner, tmp_path):
    rules = tmp_path / "pattern-group-overlap.yar"
    rules.write_text(
        'rule GroupRangeOverlap {\n strings:\n  $a1 = "aa"\n  $a2 = "bb"\n'
        ' condition:\n  2 of ($a*) in (0..10)\n}\n',
        encoding="utf-8",
    )
    sample = tmp_path / "repeated-pattern.bin"
    sample.write_bytes(b"aaaa")
    res = _run(scanner, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["match_count"] == 0


def test_pattern_group_range_matches_in_c_and_llvm(scanner, scanner_llvm, tmp_path):
    rules = tmp_path / "pattern-group-range-parity.yar"
    rules.write_text(
        'rule GroupRangeParity {\n strings:\n  $a1 = "alpha"\n  $a2 = "beta"\n'
        ' condition:\n  all of ($a*) in (6..15)\n}\n',
        encoding="utf-8",
    )
    sample = tmp_path / "pattern-group-range-target.bin"
    sample.write_bytes(b"xxxxxxalpha beta")
    c_result = _run(scanner, "scan", str(sample), "--rules", str(rules))
    llvm_result = _run(scanner_llvm, "scan", str(sample), "--rules", str(rules))
    assert c_result.returncode == llvm_result.returncode == 0
    assert json.loads(c_result.stdout) == json.loads(llvm_result.stdout)


@pytest.mark.parametrize(
    ("definition", "target", "condition", "expected"),
    [
        ("{ 41 ( 42 | 44 ) 43 }", b"ABC ADC", "$a at 4", (4, 3)),
        ('"needle"', b"needle xxneedle", "$a in (9..14)", (9, 6)),
    ],
)
def test_positional_condition_reports_selected_occurrence_in_c_and_llvm(
    scanner, scanner_llvm, tmp_path, definition, target, condition, expected
):
    rules = tmp_path / "position-witness.yar"
    rules.write_text(
        'rule PositionWitness {\n strings:\n  $a = ' + definition + '\n'
        ' condition:\n  ' + condition + '\n}\n',
        encoding="utf-8",
    )
    sample = tmp_path / "position-witness.bin"
    sample.write_bytes(target)
    c_result = _run(scanner, "scan", str(sample), "--rules", str(rules))
    llvm_result = _run(scanner_llvm, "scan", str(sample), "--rules", str(rules))
    assert c_result.returncode == llvm_result.returncode == 0
    c_report = json.loads(c_result.stdout)
    llvm_report = json.loads(llvm_result.stdout)
    assert c_report == llvm_report
    assert c_report["match_count"] == 1
    assert (c_report["matches"][0]["offset"], c_report["matches"][0]["length"]) == expected


@pytest.mark.parametrize(
    ("definition", "target", "condition", "expected"),
    [
        ("{ 41 [1-3] 42 }", b"A1B A12B", "#a == 2", (True, (0, 3))),
        ("{ 41 ( 42 | 44 ) 43 }", b"ABC ADC", "@a[2] == 4", (True, (0, 3))),
        ("{ 41 ~42 43 }", b"ADC ABC AEC", "!a[2] == 3", (True, (0, 3))),
        ("{ 41 ~42 43 }", b"ADC ABC AEC", "#a == 3", (False, None)),
    ],
)
def test_complex_hex_occurrence_conditions_match_in_c_and_llvm(
    scanner, scanner_llvm, tmp_path, definition, target, condition, expected
):
    should_match, witness = expected
    rules = tmp_path / "complex-occurrence.yar"
    rules.write_text(
        'rule ComplexOccurrence {\n strings:\n  $a = ' + definition + '\n'
        ' condition:\n  ' + condition + '\n}\n',
        encoding="utf-8",
    )
    sample = tmp_path / "complex-occurrence.bin"
    sample.write_bytes(target)
    c_result = _run(scanner, "scan", str(sample), "--rules", str(rules))
    llvm_result = _run(scanner_llvm, "scan", str(sample), "--rules", str(rules))
    assert c_result.returncode == llvm_result.returncode == 0
    c_report = json.loads(c_result.stdout)
    llvm_report = json.loads(llvm_result.stdout)
    assert c_report == llvm_report
    assert c_report["match_count"] == (1 if should_match else 0)
    if should_match:
        assert (c_report["matches"][0]["offset"], c_report["matches"][0]["length"]) == witness


def test_rule_meta_and_tags_are_returned_as_typed_json(scanner, scanner_llvm, tmp_path):
    rules = tmp_path / "metadata.yar"
    rules.write_text(
        'rule TaggedRule : malware triage {\n'
        ' meta:\n  author = "Axiom"\n  severity = 7\n'
        '  enabled = true\n  magic = 0x10\n  note = "line\\nnext"\n'
        ' strings:\n  $a = "needle"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    sample = tmp_path / "metadata-target.bin"
    sample.write_bytes(b"needle")
    res = _run(scanner, "scan", str(sample), "--rules", str(rules))
    llvm_res = _run(scanner_llvm, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    assert llvm_res.returncode == 0, llvm_res.stdout + llvm_res.stderr
    assert json.loads(res.stdout) == json.loads(llvm_res.stdout)
    match = json.loads(res.stdout)["matches"][0]
    assert match["tags"] == ["malware", "triage"]
    assert match["meta"] == {
        "author": "Axiom", "severity": 7, "enabled": True,
        "magic": 16, "note": "line\nnext",
    }


def test_metadata_x_escape_is_rejected(scanner, tmp_path):
    rules = tmp_path / "metadata-x-escape.yar"
    rules.write_text(
        r'''rule InvalidMeta {
 meta:
  author = "\x41"
 strings:
  $a = "needle"
 condition:
  $a
}
''',
        encoding="utf-8",
    )

    result = _run(scanner, "rules", str(rules))

    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads(result.stdout)
    _assert_report_matches_schema(report)
    assert report["ok"] is False


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("9" * 18, int("9" * 18)),
        ("-" + "9" * 18, -int("9" * 18)),
        ("0x" + "F" * 15, int("F" * 15, 16)),
        ("0X" + "F" * 15, int("F" * 15, 16)),
        ("-0x" + "F" * 15, -int("F" * 15, 16)),
    ],
)
def test_metadata_integer_digit_limits_and_signed_values(scanner, tmp_path, value, expected):
    rules = tmp_path / "metadata-integer.yar"
    rules.write_text(
        'rule IntegerMeta {\n meta:\n  number = ' + value
        + '\n strings:\n  $a = "needle"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    target = tmp_path / "metadata-target.bin"
    target.write_bytes(b"needle")

    result = _run(scanner, "scan", str(target), "--rules", str(rules))

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    _assert_report_matches_schema(report)
    assert report["matches"][0]["meta"]["number"] == expected


@pytest.mark.parametrize("value", ["9" * 19, "0x" + "F" * 16])
def test_metadata_integer_values_over_digit_limits_fail_closed(scanner, tmp_path, value):
    rules = tmp_path / "metadata-overflow.yar"
    rules.write_text(
        'rule IntegerMeta {\n meta:\n  number = ' + value
        + '\n strings:\n  $a = "needle"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )

    result = _run(scanner, "rules", str(rules))

    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads(result.stdout)
    _assert_report_matches_schema(report)
    assert report["ok"] is False


@pytest.mark.parametrize("meta_lines", [
    '  flag = maybe\n',
    '  author = "unterminated\n',
    '  duplicate = 1\n  duplicate = 2\n',
])
def test_invalid_or_duplicate_rule_meta_is_rejected(scanner, tmp_path, meta_lines):
    rules = tmp_path / "invalid-metadata.yar"
    rules.write_text(
        'rule InvalidMeta {\n meta:\n' + meta_lines
        + ' strings:\n  $a = "needle"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    res = _run(scanner, "rules", str(rules))
    assert res.returncode == 1
    assert json.loads(res.stdout)["ok"] is False


def test_duplicate_rule_names_are_rejected(scanner, tmp_path):
    rules = tmp_path / "duplicate-rule-names.yar"
    rules.write_text(
        'rule Duplicate {\n condition:\n  true\n}\n'
        'rule Duplicate {\n condition:\n  true\n}\n',
        encoding="utf-8",
    )
    res = _run(scanner, "rules", str(rules))
    assert res.returncode == 1
    assert "yinelenen kural adi" in json.loads(res.stdout)["error"]


@pytest.mark.parametrize("condition", ["$missing", "$a and", "($a or $b", "$a $b"])
def test_invalid_boolean_conditions_are_rejected(scanner, tmp_path, condition):
    rules = tmp_path / "invalid-condition.yar"
    rules.write_text(
        'rule Invalid {\n strings:\n  $a = "alpha"\n condition:\n  '
        + condition + "\n}\n",
        encoding="utf-8",
    )
    res = _run(scanner, "rules", str(rules))
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["ok"] is False
    assert "condition" in data["error"]


def test_boolean_conditions_match_in_c_and_llvm(scanner, scanner_llvm, tmp_path):
    rules = tmp_path / "boolean-parity.yar"
    rules.write_text(
        'rule BooleanRule {\n strings:\n  $a = "alpha"\n  $b = "beta"\n'
        ' condition:\n  ($a or $b) and not $b\n}\n',
        encoding="utf-8",
    )
    sample = tmp_path / "boolean-target.bin"
    sample.write_bytes(b"alpha")
    c_result = _run(scanner, "scan", str(sample), "--rules", str(rules))
    llvm_result = _run(scanner_llvm, "scan", str(sample), "--rules", str(rules))
    assert c_result.returncode == llvm_result.returncode == 0
    assert json.loads(c_result.stdout) == json.loads(llvm_result.stdout)

    count_rules = tmp_path / "count-parity.yar"
    count_rules.write_text(
        'rule CountParity {\n strings:\n  $a = "aa"\n condition:\n  #a == 3\n}\n',
        encoding="utf-8",
    )
    sample.write_bytes(b"aaaa")
    c_count = _run(scanner, "scan", str(sample), "--rules", str(count_rules))
    llvm_count = _run(scanner_llvm, "scan", str(sample), "--rules", str(count_rules))
    assert c_count.returncode == llvm_count.returncode == 0
    assert json.loads(c_count.stdout) == json.loads(llvm_count.stdout)

    offset_rules = tmp_path / "offset-parity.yar"
    offset_rules.write_text(
        'rule OffsetParity {\n strings:\n  $a = "needle"\n'
        ' condition:\n  $a in (0x2..0x8)\n}\n',
        encoding="utf-8",
    )
    sample.write_bytes(b"xxneedle")
    c_offset = _run(scanner, "scan", str(sample), "--rules", str(offset_rules))
    llvm_offset = _run(scanner_llvm, "scan", str(sample), "--rules", str(offset_rules))
    assert c_offset.returncode == llvm_offset.returncode == 0
    assert json.loads(c_offset.stdout) == json.loads(llvm_offset.stdout)

    indexed_rules = tmp_path / "indexed-parity.yar"
    indexed_rules.write_text(
        'rule IndexedParity {\n strings:\n  $a = "aa"\n'
        ' condition:\n  @a[2] == 1 and !a[3] == 2\n}\n',
        encoding="utf-8",
    )
    sample.write_bytes(b"aaaa")
    c_indexed = _run(scanner, "scan", str(sample), "--rules", str(indexed_rules))
    llvm_indexed = _run(scanner_llvm, "scan", str(sample), "--rules", str(indexed_rules))
    assert c_indexed.returncode == llvm_indexed.returncode == 0
    assert json.loads(c_indexed.stdout) == json.loads(llvm_indexed.stdout)

    indexed_hex_rules = tmp_path / "indexed-hex-parity.yar"
    indexed_hex_rules.write_text(
        'rule IndexedHexParity {\n strings:\n  $a = { 41 42 }\n'
        ' condition:\n  @a[2] == 2 and !a[1] == 2\n}\n',
        encoding="utf-8",
    )
    sample.write_bytes(b"ABAB")
    c_hex_indexed = _run(scanner, "scan", str(sample), "--rules", str(indexed_hex_rules))
    llvm_hex_indexed = _run(scanner_llvm, "scan", str(sample), "--rules", str(indexed_hex_rules))
    assert c_hex_indexed.returncode == llvm_hex_indexed.returncode == 0
    assert json.loads(c_hex_indexed.stdout) == json.loads(llvm_hex_indexed.stdout)

    count_hex_rules = tmp_path / "count-hex-parity.yar"
    count_hex_rules.write_text(
        'rule CountHexParity {\n strings:\n  $a = { 41 42 }\n'
        ' condition:\n  #a == 2\n}\n',
        encoding="utf-8",
    )
    sample.write_bytes(b"ABAB")
    c_hex_count = _run(scanner, "scan", str(sample), "--rules", str(count_hex_rules))
    llvm_hex_count = _run(scanner_llvm, "scan", str(sample), "--rules", str(count_hex_rules))
    assert c_hex_count.returncode == llvm_hex_count.returncode == 0
    assert json.loads(c_hex_count.stdout) == json.loads(llvm_hex_count.stdout)

    group_rules = tmp_path / "group-parity.yar"
    group_rules.write_text(
        'rule GroupParity {\n strings:\n  $a1 = "alpha"\n  $a2 = "beta"\n'
        '  $b = "gamma"\n condition:\n  3 of ($a*, $a1, $b) and filesize == 16\n}\n',
        encoding="utf-8",
    )
    sample.write_bytes(b"alpha beta gamma")
    c_group = _run(scanner, "scan", str(sample), "--rules", str(group_rules))
    llvm_group = _run(scanner_llvm, "scan", str(sample), "--rules", str(group_rules))
    assert c_group.returncode == llvm_group.returncode == 0
    assert json.loads(c_group.stdout) == json.loads(llvm_group.stdout)


@pytest.mark.parametrize(("condition", "expected"), [("true", 1), ("false", 0)])
def test_boolean_constant_conditions_can_have_no_patterns(scanner, tmp_path, condition, expected):
    rules = tmp_path / "constant-condition.yar"
    rules.write_text(
        'rule Constant {\n condition:\n  ' + condition + "\n}\n",
        encoding="utf-8",
    )
    sample = tmp_path / "empty.bin"
    sample.write_bytes(b"sample")
    res = _run(scanner, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["match_count"] == expected


@pytest.mark.parametrize(("expression", "expected"), [
    ("filesize < 4", 1),
    ("filesize <= 3", 1),
    ("filesize > 2", 1),
    ("filesize >= 3", 1),
    ("filesize == 3", 1),
    ("filesize != 3", 0),
    ("filesize < 3", 0),
    ("$a and filesize == 3", 1),
])
def test_filesize_comparisons(scanner, tmp_path, expression, expected):
    rules = tmp_path / "filesize.yar"
    rules.write_text(
        'rule FileSize {\n strings:\n  $a = "abc"\n condition:\n  '
        + expression + "\n}\n",
        encoding="utf-8",
    )
    sample = tmp_path / "three-bytes.bin"
    sample.write_bytes(b"abc")
    res = _run(scanner, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["match_count"] == expected


def test_filesize_and_scanned_bytes_use_full_file_length_with_nul(scanner, tmp_path):
    rules = tmp_path / "filesize-nul.yar"
    rules.write_text(
        'rule FullLength {\n condition:\n  filesize == 5\n}\n',
        encoding="utf-8",
    )
    sample = tmp_path / "nul.bin"
    sample.write_bytes(b"a\x00bcd")
    res = _run(scanner, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    report = json.loads(res.stdout)
    assert report["match_count"] == 1
    assert report["scanned_bytes"] == 5


@pytest.mark.parametrize(("pattern", "target", "condition", "expected"), [
    ('"aa"', b"aaaa", "#a == 3", 1),
    ('"aa"', b"aaaa", "#a == 2", 0),
    ('"needle" nocase', b"NEEDLE needle", "#a == 2", 1),
    ('"domain" fullword', b"www.my-domain.com", "#a == 1", 1),
    ('"domain" fullword', b"www.mydomain.com", "#a == 0", 1),
    ("{ 41 42 }", b"ABAB", "#a == 2", 1),
    ("{ 4? 42 }", b"ABAB", "#a == 2", 1),
    ("{ 41 42 }", b"ABAB", "#a == 3", 0),
    ('"aa"', b"aaaa", "#a >= 3 and filesize == 4", 1),
])
def test_pattern_occurrence_count_conditions(scanner, tmp_path, pattern, target, condition, expected):
    rules = tmp_path / "count.yar"
    rules.write_text(
        'rule CountHits {\n strings:\n  $a = ' + pattern + '\n condition:\n  '
        + condition + "\n}\n",
        encoding="utf-8",
    )
    sample = tmp_path / "count-target.bin"
    sample.write_bytes(target)
    res = _run(scanner, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["match_count"] == expected


@pytest.mark.parametrize(("pattern", "filename"), [("/a+/", "regex-count.yar")])
def test_pattern_occurrence_count_rejects_unsupported_types(scanner, tmp_path, pattern, filename):
    rules = tmp_path / filename
    rules.write_text(
        'rule UnsupportedCount {\n strings:\n  $a = ' + pattern + '\n condition:\n  #a > 0\n}\n',
        encoding="utf-8",
    )
    res = _run(scanner, "rules", str(rules))
    assert res.returncode == 1
    assert "regex" in json.loads(res.stdout)["error"]


@pytest.mark.parametrize(("pattern", "target", "condition", "expected"), [
    ('"needle"', b"needle xx", "$a at 0", 1),
    ('"needle"', b"xxneedle", "$a at 0x2", 1),
    ('"needle"', b"xxneedle", "$a at 0", 0),
    ('"needle"', b"xxneedle yyneedle", "$a in (0..7)", 1),
    ('"needle"', b"xxneedle yyneedle", "$a in (8..20)", 1),
    ('"needle"', b"xxneedle", "$a in (0..1)", 0),
    ('"needle" nocase', b"xxNEEDLE", "$a in (2..7)", 1),
    ("{ 4D 5A }", b"xxxxMZ", "$a at 4", 1),
    ("{ 4D 5A }", b"xxxxMZ", "$a in (3..5)", 1),
])
def test_pattern_offset_conditions(scanner, tmp_path, pattern, target, condition, expected):
    rules = tmp_path / "offset.yar"
    rules.write_text(
        'rule OffsetRule {\n strings:\n  $a = ' + pattern + '\n condition:\n  '
        + condition + "\n}\n",
        encoding="utf-8",
    )
    sample = tmp_path / "offset-target.bin"
    sample.write_bytes(target)
    res = _run(scanner, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["match_count"] == expected


@pytest.mark.parametrize("condition", [
    "$a at", "$a at -1", "$a at 999999999999999999999",
    "$a in 0..4", "$a in (5..2)",
])
def test_malformed_pattern_offset_conditions_are_rejected(scanner, tmp_path, condition):
    rules = tmp_path / "bad-offset.yar"
    rules.write_text(
        'rule BadOffset {\n strings:\n  $a = "needle"\n condition:\n  '
        + condition + "\n}\n",
        encoding="utf-8",
    )
    res = _run(scanner, "rules", str(rules))
    assert res.returncode == 1
    assert "condition" in json.loads(res.stdout)["error"]


def test_pattern_offset_conditions_reject_regex(scanner, tmp_path):
    rules = tmp_path / "regex-offset.yar"
    rules.write_text(
        'rule RegexOffset {\n strings:\n  $a = /needle/\n condition:\n  $a at 0\n}\n',
        encoding="utf-8",
    )
    res = _run(scanner, "rules", str(rules))
    assert res.returncode == 1
    assert "condition" in json.loads(res.stdout)["error"]


@pytest.mark.parametrize(("pattern", "target", "condition", "expected"), [
    ('"aa"', b"aaaa", "@a[1] == 0", 1),
    ('"aa"', b"aaaa", "@a[2] == 1", 1),
    ('"aa"', b"aaaa", "@a[3] >= 2", 1),
    ('"aa"', b"aaaa", "!a[1] == 2", 1),
    ('"aa"', b"aaaa", "!a[2] >= 2", 1),
    ('"aa"', b"aaaa", "@a[4] != 0", 0),
    ('"needle" nocase', b"xxNEEDLE", "@a[1] == 2 and !a[1] == 6", 1),
    ('"domain" fullword', b"www.mydomain.com", "#a == 0 and @a[1] == 0", 0),
])
def test_pattern_occurrence_offset_and_length_conditions(scanner, tmp_path, pattern, target, condition, expected):
    rules = tmp_path / "occurrence-index.yar"
    rules.write_text(
        'rule OccurrenceIndex {\n strings:\n  $a = ' + pattern + '\n condition:\n  '
        + condition + "\n}\n",
        encoding="utf-8",
    )
    sample = tmp_path / "occurrence-target.bin"
    sample.write_bytes(target)
    res = _run(scanner, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["match_count"] == expected


@pytest.mark.parametrize(("pattern", "target", "condition", "expected"), [
    ("{ 41 42 }", b"ABAB", "@a[1] == 0", 1),
    ("{ 41 42 }", b"ABAB", "@a[2] == 2", 1),
    ("{ 41 42 }", b"ABAB", "!a[1] == 2", 1),
    ("{ 4? 42 }", b"ABAB", "@a[2] == 2 and !a[2] == 2", 1),
    ("{ 41 42 }", b"ABAB", "@a[3] == 4", 0),
])
def test_hex_occurrence_offset_and_length_conditions(scanner, tmp_path, pattern, target, condition, expected):
    rules = tmp_path / "hex-occurrence-index.yar"
    rules.write_text(
        'rule HexOccurrenceIndex {\n strings:\n  $a = ' + pattern + '\n condition:\n  '
        + condition + "\n}\n",
        encoding="utf-8",
    )
    sample = tmp_path / "hex-occurrence-target.bin"
    sample.write_bytes(target)
    res = _run(scanner, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["match_count"] == expected


@pytest.mark.parametrize("condition", ["@a[0] == 0", "!a[0] > 0", "@a[1]", "!a[1] =="])
def test_malformed_occurrence_index_conditions_are_rejected(scanner, tmp_path, condition):
    rules = tmp_path / "bad-occurrence-index.yar"
    rules.write_text(
        'rule BadOccurrenceIndex {\n strings:\n  $a = "needle"\n condition:\n  '
        + condition + "\n}\n",
        encoding="utf-8",
    )
    res = _run(scanner, "rules", str(rules))
    assert res.returncode == 1
    assert "condition" in json.loads(res.stdout)["error"]


@pytest.mark.parametrize("pattern", ["/needle/"])
def test_occurrence_index_conditions_reject_non_text_patterns(scanner, tmp_path, pattern):
    rules = tmp_path / "unsupported-occurrence-index.yar"
    rules.write_text(
        'rule UnsupportedIndex {\n strings:\n  $a = ' + pattern
        + '\n condition:\n  @a[1] == 0\n}\n',
        encoding="utf-8",
    )
    res = _run(scanner, "rules", str(rules))
    assert res.returncode == 1
    assert "condition" in json.loads(res.stdout)["error"]


def test_comment_markers_inside_yara_text_are_preserved(scanner, tmp_path):
    rules = tmp_path / "comment-markers.yar"
    rules.write_text(
        'rule UrlAndHash {\n strings:\n'
        '  $url = "http://evil.example/gate"\n'
        '  $hash = "#malware"\n'
        ' condition:\n  any of them\n}\n',
        encoding="utf-8",
    )
    target = tmp_path / "sample.txt"
    target.write_text("#malware http://evil.example/gate", encoding="utf-8")
    res = _run(scanner, "scan", str(target), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    data = json.loads(res.stdout)
    assert data["match_count"] == 1


@pytest.mark.parametrize(("literal", "target"), [
    (r'"path\\to"', b"path\\to"),
    (r'"quote\"yes"', b'quote"yes'),
    (r'"line\n"', b"line\n"),
    (r'"return\r"', b"return\r"),
    (r'"tab\t"', b"tab\t"),
    (r'"\x41"', b"A"),
])
def test_yara_text_escapes_decode_as_expected(scanner, tmp_path, literal, target):
    rules = tmp_path / "escaped.yar"
    rules.write_text(
        "rule Escaped {\n strings:\n  $a = " + literal
        + "\n condition:\n  any of them\n}\n",
        encoding="utf-8",
    )
    sample = tmp_path / "sample.bin"
    sample.write_bytes(target)
    res = _run(scanner, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["match_count"] == 1


def test_nocase_text_modifier_matches_ascii_without_changing_offsets(scanner, tmp_path):
    rules = tmp_path / "nocase.yar"
    rules.write_text(
        'rule IgnoreCase {\n strings:\n  $a = "needle" nocase\n'
        ' condition:\n  any of them\n}\n',
        encoding="utf-8",
    )
    sample = tmp_path / "sample.txt"
    sample.write_bytes(b"xxNeEdLeYY")
    res = _run(scanner, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    match = json.loads(res.stdout)["matches"][0]
    assert match["offset"] == 2
    assert match["length"] == 6


def test_nocase_text_modifier_llvm_backend(scanner_llvm, tmp_path):
    rules = tmp_path / "nocase-llvm.yar"
    rules.write_text(
        'rule IgnoreCase {\n strings:\n  $a = "needle" nocase\n'
        ' condition:\n  any of them\n}\n',
        encoding="utf-8",
    )
    sample = tmp_path / "sample.txt"
    sample.write_bytes(b"xxNeEdLeYY")
    res = _run(scanner_llvm, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["matches"][0]["offset"] == 2


@pytest.mark.parametrize(("literal", "target", "matched", "offset"), [
    (r'"needle" ascii', b"xxneedleYY", True, 2),
    (r'"domain" fullword', b"www.mydomain.com", False, -1),
    (r'"domain" fullword', b"www.my-domain.com", True, 7),
    (r'"domain" fullword', b"_domain_", True, 1),
    (r'"needle" ascii nocase fullword', b"!!NEEDLE!YY", True, 2),
])
def test_ascii_and_fullword_modifiers(scanner, tmp_path, literal, target, matched, offset):
    rules = tmp_path / "text-modifiers.yar"
    rules.write_text(
        "rule TextModifier {\n strings:\n  $a = " + literal
        + "\n condition:\n  any of them\n}\n",
        encoding="utf-8",
    )
    sample = tmp_path / "sample.bin"
    sample.write_bytes(target)
    res = _run(scanner, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    matches = json.loads(res.stdout)["matches"]
    assert (len(matches) == 1) is matched
    if matched:
        assert matches[0]["offset"] == offset


def test_ascii_and_fullword_modifiers_llvm_backend(scanner_llvm, tmp_path):
    rules = tmp_path / "text-modifiers-llvm.yar"
    rules.write_text(
        'rule TextModifier {\n strings:\n  $a = "domain" fullword\n'
        ' condition:\n  any of them\n}\n',
        encoding="utf-8",
    )
    sample = tmp_path / "sample.txt"
    sample.write_bytes(b"www.my-domain.com")
    res = _run(scanner_llvm, "scan", str(sample), "--rules", str(rules))
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["matches"][0]["offset"] == 7


@pytest.mark.parametrize("literal", [r'"\x00"', r'"\q"', r'"\xG1"'])
def test_unrepresentable_or_invalid_yara_escapes_are_rejected(scanner, tmp_path, literal):
    rules = tmp_path / "bad-escape.yar"
    rules.write_text(
        "rule BadEscape {\n strings:\n  $a = " + literal
        + "\n condition:\n  any of them\n}\n",
        encoding="utf-8",
    )
    res = _run(scanner, "rules", str(rules))
    assert res.returncode == 1
    assert json.loads(res.stdout)["ok"] is False


@pytest.mark.parametrize("pattern", [
    '"needle" wide',
    '/[/',
])
def test_unsupported_or_invalid_patterns_are_rejected(scanner, tmp_path, pattern):
    rules = tmp_path / "unsupported-pattern.yar"
    rules.write_text(
        "rule UnsupportedPattern {\n strings:\n  $a = " + pattern
        + "\n condition:\n  any of them\n}\n",
        encoding="utf-8",
    )
    res = _run(scanner, "rules", str(rules))
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["ok"] is False


def test_scan_text_pattern(scanner, tmp_path):
    r = tmp_path / "rules.yar"
    r.write_text(RULES, encoding="utf-8")
    target = tmp_path / "sample.txt"
    target.write_text("cmd: powershell -enc AAAA\n", encoding="utf-8")
    res = _run(scanner, "scan", str(target), "--rules", str(r))
    assert res.returncode == 0, res.stdout + res.stderr
    data = json.loads(res.stdout)
    _assert_report_matches_schema(data)
    assert data["target"] == str(target)
    assert data["scanned_bytes"] > 0
    names = [m["rule"] for m in data["matches"]]
    assert names == ["Suspicious_Powershell"]
    m = data["matches"][0]
    assert m["pattern"] == "$a"
    assert m["offset"] == 5
    assert m["length"] == len("powershell -enc")


def test_scan_hex_wildcard_pattern(scanner, tmp_path):
    r = tmp_path / "rules.yar"
    r.write_text(RULES, encoding="utf-8")
    target = tmp_path / "shell.bin"
    target.write_bytes(b"AAAA\x48\x89\x01\x55BBBB")
    res = _run(scanner, "scan", str(target), "--rules", str(r))
    assert res.returncode == 0, res.stdout + res.stderr
    data = json.loads(res.stdout)
    assert [m["rule"] for m in data["matches"]] == ["Hex_Shellcode"]
    assert data["matches"][0]["offset"] == 4


def test_scan_all_of_them_requires_every_pattern(scanner, tmp_path):
    r = tmp_path / "rules.yar"
    r.write_text(RULES, encoding="utf-8")
    only_mz = tmp_path / "mz.bin"
    only_mz.write_bytes(b"MZ....")
    res = _run(scanner, "scan", str(only_mz), "--rules", str(r))
    data = json.loads(res.stdout)
    assert "Both_Required" not in [m["rule"] for m in data["matches"]]

    both = tmp_path / "pe.bin"
    both.write_bytes(b"MZ..This program cannot be run..")
    res2 = _run(scanner, "scan", str(both), "--rules", str(r))
    data2 = json.loads(res2.stdout)
    assert "Both_Required" in [m["rule"] for m in data2["matches"]]


def test_none_of_them_matches_only_when_no_pattern_is_present(scanner, tmp_path):
    rules = tmp_path / "none.yar"
    rules.write_text(
        'rule NoNeedle {\n strings:\n  $a = "needle"\n'
        ' condition:\n  none of them\n}\n',
        encoding="utf-8",
    )
    clean = tmp_path / "clean.txt"
    clean.write_bytes(b"ordinary content")
    dirty = tmp_path / "dirty.txt"
    dirty.write_bytes(b"contains needle")

    clean_result = _run(scanner, "scan", str(clean), "--rules", str(rules))
    dirty_result = _run(scanner, "scan", str(dirty), "--rules", str(rules))
    assert clean_result.returncode == 0
    assert [m["rule"] for m in json.loads(clean_result.stdout)["matches"]] == ["NoNeedle"]
    assert dirty_result.returncode == 0
    assert json.loads(dirty_result.stdout)["matches"] == []


def test_scan_no_match_is_empty_list(scanner, tmp_path):
    r = tmp_path / "rules.yar"
    r.write_text(RULES, encoding="utf-8")
    clean = tmp_path / "clean.txt"
    clean.write_text("hello world", encoding="utf-8")
    res = _run(scanner, "scan", str(clean), "--rules", str(r))
    assert res.returncode == 0
    assert json.loads(res.stdout)["matches"] == []


def test_scan_pcap_packet(scanner, tmp_path):
    r = tmp_path / "rules.yar"
    r.write_text(RULES, encoding="utf-8")
    pcap = tmp_path / "t.pcap"
    payload = b"powershell -enc Zm9v"
    header = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    rec = struct.pack("<IIII", 1700000000, 0, len(payload), len(payload)) + payload
    pcap.write_bytes(header + rec)

    res = _run(scanner, "pcap", str(pcap), "--rules", str(r))
    assert res.returncode == 0, res.stdout + res.stderr
    data = json.loads(res.stdout)
    assert data["packet_count"] == 1
    assert data["match_count"] == 1
    assert data["packets"][0]["rules"] == ["Suspicious_Powershell"]


def test_scan_pcap_counts_empty_packet_and_continues(scanner, tmp_path):
    rules = tmp_path / "rules.yar"
    rules.write_text(
        'rule PacketNeedle {\n strings:\n  $a = "NEEDLE"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    pcap = tmp_path / "empty-then-valid.pcap"
    global_header = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    empty_record = struct.pack("<IIII", 1700000000, 0, 0, 0)
    payload = b"NEEDLE"
    valid_record = struct.pack(
        "<IIII", 1700000001, 0, len(payload), len(payload)
    ) + payload
    pcap.write_bytes(global_header + empty_record + valid_record)

    result = _run(scanner, "pcap", str(pcap), "--rules", str(rules))

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["packet_count"] == 2
    assert report["match_count"] == 1
    assert report["packets"][0]["index"] == 1
    assert report["packets"][0]["rules"] == ["PacketNeedle"]


def test_pcap_match_does_not_span_records(scanner, scanner_llvm, tmp_path):
    rules = tmp_path / "split-signature.yar"
    rules.write_text(
        'rule SplitSignature {\n strings:\n  $a = "NEEDLE"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    pcap = tmp_path / "split-signature.pcap"
    header = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    first = b"prefix NEE"
    second = b"DLE suffix"
    pcap.write_bytes(
        header
        + struct.pack("<IIII", 1700000000, 0, len(first), len(first)) + first
        + struct.pack("<IIII", 1700000001, 0, len(second), len(second)) + second
    )

    reports = []
    for executable in (scanner, scanner_llvm):
        result = _run(executable, "pcap", str(pcap), "--rules", str(rules))
        assert result.returncode == 0, result.stdout + result.stderr
        report = json.loads(result.stdout)
        _assert_report_matches_schema(report)
        assert report["packet_count"] == 2
        assert report["match_count"] == 0
        assert report["packets"] == []
        reports.append(report)
    assert reports[0] == reports[1]


def test_scan_pcap_empty_capture_reports_zero_packets(scanner, tmp_path):
    rules = tmp_path / "rules.yar"
    rules.write_text(
        'rule PacketNeedle {\n strings:\n  $a = "NEEDLE"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    pcap = tmp_path / "empty-capture.pcap"
    pcap.write_bytes(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))

    result = _run(scanner, "pcap", str(pcap), "--rules", str(rules))

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["packet_count"] == 0
    assert report["match_count"] == 0


def test_scan_pcap_opposite_endian_classic_file(scanner, tmp_path):
    rules = tmp_path / "rules.yar"
    rules.write_text(
        'rule PacketNeedle {\n strings:\n  $a = "NEEDLE"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    pcap = tmp_path / "big-endian.pcap"
    global_header = struct.pack(">IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    payload = b"NEEDLE"
    record = struct.pack(">IIII", 1700000000, 0, len(payload), len(payload)) + payload
    pcap.write_bytes(global_header + record)

    result = _run(scanner, "pcap", str(pcap), "--rules", str(rules))

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["packet_count"] == 1
    assert report["match_count"] == 1
    assert report["packets"][0]["rules"] == ["PacketNeedle"]


@pytest.mark.parametrize("byte_order,label", [("<", "little"), (">", "big")])
def test_scan_pcap_nanosecond_timestamp_magic(scanner, tmp_path, byte_order, label):
    rules = tmp_path / "rules.yar"
    rules.write_text(
        'rule PacketNeedle {\n strings:\n  $a = "NEEDLE"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    pcap = tmp_path / f"nanosecond-{label}.pcap"
    global_header = struct.pack(
        f"{byte_order}IHHIIII", 0xA1B23C4D, 2, 4, 0, 0, 65535, 1
    )
    payload = b"NEEDLE"
    record = struct.pack(
        f"{byte_order}IIII", 1700000000, 123456789, len(payload), len(payload)
    ) + payload
    pcap.write_bytes(global_header + record)

    result = _run(scanner, "pcap", str(pcap), "--rules", str(rules))

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["packet_count"] == 1
    assert report["match_count"] == 1
    assert report["packets"][0]["rules"] == ["PacketNeedle"]


@pytest.mark.parametrize("truncated", [
    b"\xd4\xc3\xb2\xa1\x02\x00\x04",  # truncated global header
    struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    + b"\x00" * 8,  # truncated per-packet header
    struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    + struct.pack("<IIII", 1700000000, 0, 6, 6) + b"NEE",  # short payload
    struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    + struct.pack("<IIII", 1700000000, 0, 1, 0) + b"x",  # incl_len > orig_len
    struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    + struct.pack("<IIII", 1700000000, 0, 65536, 65536),  # incl_len > snaplen cap
])
def test_scan_pcap_malformed_or_truncated_records_fail_closed(scanner, tmp_path, truncated):
    rules = tmp_path / "rules.yar"
    rules.write_text(
        'rule PacketNeedle {\n strings:\n  $a = "NEEDLE"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    pcap = tmp_path / "truncated.pcap"
    pcap.write_bytes(truncated)

    result = _run(scanner, "pcap", str(pcap), "--rules", str(rules))

    assert result.returncode != 0, result.stdout + result.stderr
    error_report = json.loads(result.stdout)
    _assert_report_matches_schema(error_report)
    assert error_report["ok"] is False
    assert error_report["error"]


def test_scan_pcap_rejects_record_over_custom_snaplen(scanner, tmp_path):
    rules = tmp_path / "rules.yar"
    rules.write_text(
        'rule PacketNeedle {\n strings:\n  $a = "NEEDLE"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    pcap = tmp_path / "small-snaplen.pcap"
    header = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 2, 1)
    payload = b"abc"
    record = struct.pack("<IIII", 1700000000, 0, len(payload), len(payload)) + payload
    pcap.write_bytes(header + record)

    result = _run(scanner, "pcap", str(pcap), "--rules", str(rules))

    assert result.returncode != 0, result.stdout + result.stderr
    assert '"ok":true' not in result.stdout


def test_scan_pcap_rejects_record_over_65535_bytes_even_with_large_snaplen(scanner, tmp_path):
    rules = tmp_path / "rules.yar"
    rules.write_text(
        'rule PacketNeedle {\n strings:\n  $a = "NEEDLE"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    pcap = tmp_path / "large-record.pcap"
    header = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 131072, 999)
    # The header promises a record over the implementation's fixed cap; the
    # reader must reject it before trying to read or allocate the payload.
    record_header = struct.pack("<IIII", 1700000000, 0, 65536, 65536)
    pcap.write_bytes(header + record_header)

    result = _run(scanner, "pcap", str(pcap), "--rules", str(rules))

    assert result.returncode != 0, result.stdout + result.stderr
    assert '"ok":true' not in result.stdout


def test_scan_pcap_ignores_linktype_and_scans_captured_bytes(scanner, tmp_path):
    rules = tmp_path / "rules.yar"
    rules.write_text(
        'rule PacketNeedle {\n strings:\n  $a = "NEEDLE"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    pcap = tmp_path / "unknown-linktype.pcap"
    payload = b"NEEDLE"
    header = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 999)
    record = struct.pack("<IIII", 1700000000, 0, len(payload), len(payload)) + payload
    pcap.write_bytes(header + record)

    result = _run(scanner, "pcap", str(pcap), "--rules", str(rules))

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["packet_count"] == 1
    assert report["match_count"] == 1
    assert report["packets"][0]["index"] == 0


def test_scan_rejects_pcapng(scanner, tmp_path):
    rules = tmp_path / "rules.yar"
    rules.write_text(
        'rule PacketNeedle {\n strings:\n  $a = "NEEDLE"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    pcapng = tmp_path / "capture.pcapng"
    # Section Header Block magic followed by a minimal recognizable prefix.
    pcapng.write_bytes(b"\x0a\x0d\x0d\x0a" + b"\x1c\x00\x00\x00" + b"\x4d\x3c\x2b\x1a")

    result = _run(scanner, "pcap", str(pcapng), "--rules", str(rules))

    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads(result.stdout)
    _assert_report_matches_schema(report)
    assert report["ok"] is False
    assert "pcapng desteklenmiyor" in report["error"].lower()


def test_pcap_fail_on_match_is_opt_in_and_matches_c_llvm(scanner, scanner_llvm, tmp_path):
    rules = tmp_path / "rules.yar"
    rules.write_text(
        'rule PacketNeedle {\n strings:\n  $a = "NEEDLE"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    header = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    matched_payload = b"captured NEEDLE bytes"
    matching_pcap = tmp_path / "matching.pcap"
    matching_pcap.write_bytes(
        header
        + struct.pack(
            "<IIII", 1700000000, 0, len(matched_payload), len(matched_payload)
        )
        + matched_payload
    )
    clean_payload = b"no finding"
    clean_pcap = tmp_path / "clean.pcap"
    clean_pcap.write_bytes(
        header
        + struct.pack("<IIII", 1700000000, 0, len(clean_payload), len(clean_payload))
        + clean_payload
    )

    reports_by_backend = []
    for executable in (scanner, scanner_llvm):
        plain = _run(executable, "pcap", str(matching_pcap), "--rules", str(rules))
        gated = _run(
            executable, "pcap", str(matching_pcap), "--rules", str(rules),
            "--fail-on-match",
        )
        clean = _run(
            executable, "pcap", str(clean_pcap), "--rules", str(rules),
            "--fail-on-match",
        )

        assert plain.returncode == 0, plain.stdout + plain.stderr
        assert gated.returncode == 10, gated.stdout + gated.stderr
        assert clean.returncode == 0, clean.stdout + clean.stderr
        plain_report = json.loads(plain.stdout)
        gated_report = json.loads(gated.stdout)
        clean_report = json.loads(clean.stdout)
        for report in (plain_report, gated_report, clean_report):
            _assert_report_matches_schema(report)
        assert plain_report["match_count"] == gated_report["match_count"] == 1
        assert clean_report["match_count"] == 0
        reports_by_backend.append((plain_report, gated_report, clean_report))

    assert reports_by_backend[0] == reports_by_backend[1]


def test_scan_pcap_binary_payload_matches_after_nul(scanner, tmp_path):
    rules = tmp_path / "pcap-binary.yar"
    rules.write_text(
        'rule PacketNeedle {\n strings:\n  $a = "NEEDLE"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    pcap = tmp_path / "binary-payload.pcap"
    payload = b"prefix\x00NEEDLE"
    header = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    record = struct.pack("<IIII", 1700000000, 0, len(payload), len(payload)) + payload
    pcap.write_bytes(header + record)

    result = _run(scanner, "pcap", str(pcap), "--rules", str(rules))
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["packet_count"] == 1
    assert report["match_count"] == 1
    assert report["packets"][0]["rules"] == ["PacketNeedle"]


@pytest.mark.parametrize("args,expect", [
    (("scan", "/tmp/yok_boyle_dosya_xyz", "--rules", "r.yar"), "bulunamadi"),
    (("scan", "somefile"), "--rules"),
    (("bilinmeyen",), "bilinmeyen alt komut"),
    ((), "alt komut"),
])
def test_error_paths(scanner, args, expect):
    res = _run(scanner, *args)
    assert res.returncode == 1, res.stdout + res.stderr
    assert expect in (res.stdout + res.stderr)
    report = json.loads(res.stdout)
    _assert_report_matches_schema(report)
    assert report["ok"] is False


def test_invalid_rules_report_line(scanner, tmp_path):
    r = tmp_path / "bad.yar"
    r.write_text("rule Bozuk {\n strings:\n $a = \"x\"\n", encoding="utf-8")
    res = _run(scanner, "rules", str(r))
    assert res.returncode == 1
    assert "kapatilmadi" in (res.stdout + res.stderr)


def test_empty_rules_file_is_error(scanner, tmp_path):
    r = tmp_path / "empty.yar"
    r.write_text("", encoding="utf-8")
    res = _run(scanner, "rules", str(r))
    assert res.returncode == 1


def test_binary_is_standalone(scanner):
    """Üretilen ikili yalnızca sistem kütüphanelerine bağlı olmalı."""
    res = subprocess.run(["ldd", str(scanner)], capture_output=True, text=True)
    if res.returncode != 0:
        pytest.skip("ldd bulunamadi (binutils kurulu degil)")
    out = res.stdout
    for lib in ("libz", "libssl", "libcrypto", "libc", "libm"):
        assert lib in out or "not a dynamic executable" in out
    # Axiom runtime'ı gömülü olmalı (ayrı .so yok)
    assert "libaxiom" not in out


@pytest.fixture(scope="module")
def scanner_llvm(tmp_path_factory):
    """Aynı tarayıcı LLVM arka ucuyla (P1-03b regresyonu)."""
    if not EXAMPLE.exists():
        pytest.skip("ornek bulunamadi")
    exe = ".exe" if os.name == "nt" else ""
    out = tmp_path_factory.mktemp("scan_llvm") / f"axiom-scan-llvm{exe}"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "ascii:backslashreplace"
    res = subprocess.run(
        [sys.executable, str(AXIOM), "build", str(EXAMPLE), "--backend=llvm", "-o", str(out)],
        capture_output=True, text=True, timeout=900, env=env,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    return out


def test_llvm_scanner_matches_c(scanner, scanner_llvm, tmp_path):
    """P1-03b: LLVM arka ucu C ile birebir aynı JSON'u üretmeli."""
    r = tmp_path / "rules.yar"
    r.write_text(RULES, encoding="utf-8")
    target = tmp_path / "sample.txt"
    target.write_text("cmd: powershell -enc AAAA\n", encoding="utf-8")

    c_res = _run(scanner, "scan", str(target), "--rules", str(r))
    l_res = _run(scanner_llvm, "scan", str(target), "--rules", str(r))
    assert c_res.returncode == 0 and l_res.returncode == 0
    c_report = json.loads(c_res.stdout)
    llvm_report = json.loads(l_res.stdout)
    _assert_report_matches_schema(c_report)
    _assert_report_matches_schema(llvm_report)
    assert c_report == llvm_report

    bin_target = tmp_path / "shell.bin"
    bin_target.write_bytes(b"AAAA\x48\x89\x01\x55BBBB")
    c_bin = _run(scanner, "scan", str(bin_target), "--rules", str(r))
    l_bin = _run(scanner_llvm, "scan", str(bin_target), "--rules", str(r))
    c_bin_report = json.loads(c_bin.stdout)
    l_bin_report = json.loads(l_bin.stdout)
    _assert_report_matches_schema(c_bin_report)
    _assert_report_matches_schema(l_bin_report)
    assert c_bin_report == l_bin_report
    assert l_bin_report["matches"][0]["rule"] == "Hex_Shellcode"

    # Exercise the new reader-status builtin through both code generators.
    pcap = tmp_path / "empty_then_match_big_endian.pcap"
    payload = b"powershell -enc AAAA"
    global_header = struct.pack(">IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    empty_record = struct.pack(">IIII", 1700000000, 0, 0, 0)
    packet_record = struct.pack(
        ">IIII", 1700000001, 0, len(payload), len(payload)
    ) + payload
    pcap.write_bytes(global_header + empty_record + packet_record)
    c_pcap = _run(scanner, "pcap", str(pcap), "--rules", str(r))
    l_pcap = _run(scanner_llvm, "pcap", str(pcap), "--rules", str(r))
    assert c_pcap.returncode == l_pcap.returncode == 0
    c_pcap_data = json.loads(c_pcap.stdout)
    l_pcap_data = json.loads(l_pcap.stdout)
    _assert_report_matches_schema(c_pcap_data)
    _assert_report_matches_schema(l_pcap_data)
    assert c_pcap_data == l_pcap_data
    assert c_pcap_data["packet_count"] == 2
    assert c_pcap_data["packets"][0]["index"] == 1
    assert c_pcap_data["match_count"] == 1


def test_binary_nul_text_hex_and_crossing_matches_have_c_llvm_parity(
    scanner, scanner_llvm, tmp_path
):
    rules = tmp_path / "binary-nul.yar"
    rules.write_text(
        'rule TextAfterNul {\n strings:\n  $t = "needle"\n condition:\n  $t\n}\n'
        'rule HexCrossesNul {\n strings:\n  $x = { 41 00 42 }\n condition:\n  $x\n}\n'
        'rule HexAfterNul {\n strings:\n  $h = { 42 43 }\n condition:\n  $h\n}\n'
        'rule HexAtAfterNul {\n strings:\n  $h = { 42 43 }\n condition:\n  $h at 13\n}\n'
        'rule TextInAfterNul {\n strings:\n  $t = "needle"\n condition:\n  $t in (0..8)\n}\n'
        'rule NulCrossingOccurrence {\n strings:\n  $x = { 41 00 42 }\n condition:\n  #x == 1 and @x[1] == 10 and !x[1] == 3\n}\n',
        encoding="utf-8",
    )
    payload = b"PRE\x00needleA\x00BBC"
    target = tmp_path / "binary-nul.bin"
    target.write_bytes(payload)

    c_res = _run(scanner, "scan", str(target), "--rules", str(rules))
    llvm_res = _run(scanner_llvm, "scan", str(target), "--rules", str(rules))
    assert c_res.returncode == llvm_res.returncode == 0
    c_data = json.loads(c_res.stdout)
    llvm_data = json.loads(llvm_res.stdout)
    assert c_data == llvm_data
    assert c_data["scanned_bytes"] == len(payload)
    assert c_data["match_count"] == 6
    assert {
        item["rule"]: (item["pattern"], item["offset"], item["length"])
        for item in c_data["matches"]
    } == {
        "TextAfterNul": ("$t", 4, 6),
        "HexCrossesNul": ("$x", 10, 3),
        "HexAfterNul": ("$h", 13, 2),
        "HexAtAfterNul": ("$h", 13, 2),
        "TextInAfterNul": ("$t", 4, 6),
        "NulCrossingOccurrence": ("$x", 10, 3),
    }

    try:
        import yara
    except ImportError:
        yara = None
    if yara is not None:
        reference_matches = yara.compile(source=rules.read_text(encoding="utf-8")).match(data=payload)
        reference = {}
        for rule_match in reference_matches:
            for string_match in rule_match.strings:
                for instance in getattr(string_match, "instances", []):
                    reference[rule_match.rule] = (
                        string_match.identifier,
                        instance.offset,
                        instance.matched_length,
                    )
        assert reference == {
            "TextAfterNul": ("$t", 4, 6),
            "HexCrossesNul": ("$x", 10, 3),
            "HexAfterNul": ("$h", 13, 2),
            "HexAtAfterNul": ("$h", 13, 2),
            "TextInAfterNul": ("$t", 4, 6),
            "NulCrossingOccurrence": ("$x", 10, 3),
        }


def test_regex_scan_with_embedded_nul_is_structured_error_and_text_control(
    scanner, scanner_llvm, tmp_path
):
    rules = tmp_path / "regex-binary.yar"
    rules.write_text(
        'rule RegexRule {\n strings:\n  $r = /[0-9]+/\n condition:\n  $r\n}\n',
        encoding="utf-8",
    )
    text_target = tmp_path / "regex-text.bin"
    text_target.write_bytes(b"prefix 123 suffix")
    binary_target = tmp_path / "regex-binary.bin"
    binary_target.write_bytes(b"prefix\x00 123 suffix")

    for executable in (scanner, scanner_llvm):
        text_res = _run(executable, "scan", str(text_target), "--rules", str(rules))
        assert text_res.returncode == 0, text_res.stdout + text_res.stderr
        text_data = json.loads(text_res.stdout)
        assert text_data["ok"] is True
        assert text_data["match_count"] == 1
        assert text_data["matches"][0]["rule"] == "RegexRule"

        binary_res = _run(executable, "scan", str(binary_target), "--rules", str(rules))
        assert binary_res.returncode == 1
        error_data = json.loads(binary_res.stdout)
        assert error_data["ok"] is False
        assert error_data["schema_version"] == "1"
        assert "regex" in error_data["error"].lower()


def test_llvm_scanner_rules_count(scanner_llvm, tmp_path):
    r = tmp_path / "rules.yar"
    r.write_text(RULES, encoding="utf-8")
    res = _run(scanner_llvm, "rules", str(r))
    assert res.returncode == 0, res.stdout + res.stderr
    report = json.loads(res.stdout)
    _assert_report_matches_schema(report)
    assert report["rules"] == 3


# ---------------------------------------------------------------------------
# v0.2 — DFIR rapor sözleşmesi (D10) ve --fail-on-match (D11)
# ---------------------------------------------------------------------------

def test_scan_report_schema_and_target_hash(scanner, tmp_path):
    """Rapor şema sürümlü olmalı ve taranan dosyanın SHA-256'sını taşımalı."""
    import hashlib

    r = tmp_path / "rules.yar"
    r.write_text(RULES, encoding="utf-8")
    target = tmp_path / "sample.bin"
    payload = b"MZ..This program cannot be run..powershell -enc AAAA"
    target.write_bytes(payload)

    res = _run(scanner, "scan", str(target), "--rules", str(r))
    assert res.returncode == 0, res.stdout + res.stderr
    data = json.loads(res.stdout)

    assert data["schema_version"] == "1"
    assert data["tool"] == "axiom-scan"
    assert data["tool_version"] == "0.2.0"
    assert data["rules_count"] == 3
    assert data["target_sha256"] == hashlib.sha256(payload).hexdigest()
    # v0.2: bayt cinsinden (karakter değil)
    assert data["scanned_bytes"] == len(payload)
    assert data["match_count"] == len(data["matches"])


def test_rules_and_pcap_reports_carry_schema(scanner, tmp_path):
    import hashlib

    r = tmp_path / "rules.yar"
    r.write_text(RULES, encoding="utf-8")
    rr = _run(scanner, "rules", str(r))
    assert rr.returncode == 0, rr.stdout + rr.stderr
    rd = json.loads(rr.stdout)
    _assert_report_matches_schema(rd)
    assert rd["schema_version"] == "1"
    assert rd["tool_version"] == "0.2.0"

    pcap = tmp_path / "t.pcap"
    payload = b"powershell -enc Zm9v"
    header = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    rec = struct.pack("<IIII", 1700000000, 0, len(payload), len(payload)) + payload
    pcap.write_bytes(header + rec)

    res = _run(scanner, "pcap", str(pcap), "--rules", str(r))
    assert res.returncode == 0, res.stdout + res.stderr
    data = json.loads(res.stdout)
    _assert_report_matches_schema(data)
    assert data["schema_version"] == "1"
    assert data["pcap_sha256"] == hashlib.sha256(pcap.read_bytes()).hexdigest()


def test_fail_on_match_is_opt_in(scanner, tmp_path):
    """Bayraksız davranış korunur (exit 0); bayrakla bulgu exit 10."""
    r = tmp_path / "rules.yar"
    r.write_text(RULES, encoding="utf-8")
    dirty = tmp_path / "dirty.txt"
    dirty.write_text("here powershell -enc AAAA\n", encoding="utf-8")

    plain = _run(scanner, "scan", str(dirty), "--rules", str(r))
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert json.loads(plain.stdout)["match_count"] == 1

    gated = _run(scanner, "scan", str(dirty), "--rules", str(r), "--fail-on-match")
    assert gated.returncode == 10, gated.stdout + gated.stderr
    # Rapor yine tam olarak üretilmeli (çıkış kodu raporu bozmamalı).
    gd = json.loads(gated.stdout)
    assert gd["ok"] is True and gd["match_count"] == 1

    clean = tmp_path / "clean.txt"
    clean.write_text("nothing to see\n", encoding="utf-8")
    ok = _run(scanner, "scan", str(clean), "--rules", str(r), "--fail-on-match")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert json.loads(ok.stdout)["match_count"] == 0


def test_error_path_is_structured_json(scanner, tmp_path):
    """Hata da şemalı JSON olmalı; stdout'u ayrıştıran araç tek biçim görür."""
    res = _run(scanner, "scan", str(tmp_path / "yok.bin"), "--rules", "r.yar")
    assert res.returncode == 1
    data = json.loads(res.stdout)
    _assert_report_matches_schema(data)
    assert data["ok"] is False
    assert data["schema_version"] == "1"
    assert "bulunamadi" in data["error"]


def test_report_schema_rejects_invalid_digest_and_unpublished_field():
    invalid_digest = {
        "schema_version": "1",
        "tool": "axiom-scan",
        "tool_version": "0.2.0",
        "rules_count": 0,
        "ok": True,
        "target": "sample.bin",
        "target_sha256": "not-a-sha256",
        "scanned_bytes": 0,
        "match_count": 0,
        "matches": [],
    }
    with pytest.raises(ValidationError):
        SCAN_REPORT_VALIDATOR.validate(invalid_digest)

    unpublished_field = dict(invalid_digest, target_sha256="0" * 64, debug="internal")
    with pytest.raises(ValidationError):
        SCAN_REPORT_VALIDATOR.validate(unpublished_field)


def test_fail_on_match_llvm_parity(scanner, scanner_llvm, tmp_path):
    """--fail-on-match her iki arka uçta aynı çıkış kodunu vermeli."""
    r = tmp_path / "rules.yar"
    r.write_text(RULES, encoding="utf-8")
    dirty = tmp_path / "dirty.txt"
    dirty.write_text("powershell -enc AAAA\n", encoding="utf-8")

    for exe in (scanner, scanner_llvm):
        res = _run(exe, "scan", str(dirty), "--rules", str(r), "--fail-on-match")
        assert res.returncode == 10, (exe, res.stdout + res.stderr)
        assert json.loads(res.stdout)["match_count"] == 1
