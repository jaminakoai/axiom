"""YARA 4.5.4 differential checks for supported parser structure."""

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
        pytest.skip("yara-python is unavailable; parser differential oracle skipped")
    assert getattr(yara, "__version__", None) == "4.5.4"
    output = tmp_path_factory.mktemp("yara-parser-structure") / "axiom-scan"
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


def _compare(scanner, tmp_path, source, target):
    expected_matches = yara.compile(source=source).match(data=target)
    rules = tmp_path / "structure.yar"
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
    assert report["match_count"] == len(expected_matches)
    return report


def test_tags_typed_metadata_and_trailing_comments_match_yara(scanner, tmp_path):
    source = '''
// Header comments and trailing comments must not change rule structure.
rule StructureMeta : malware triage_2 // tags remain attached to the rule
{
  meta:
    author = "Axiom // parser # check" // comment after metadata
    enabled = true
    severity = 3
  strings:
    $a = "needle" ascii // comment after string
  condition:
    $a // trailing condition comment
}
'''
    report = _compare(scanner, tmp_path, source, b"needle")
    match = report["matches"][0]
    assert match["tags"] == ["malware", "triage_2"]
    assert match["meta"] == {
        "author": "Axiom // parser # check",
        "enabled": True,
        "severity": 3,
    }


def test_signed_and_hex_metadata_match_yara(scanner, tmp_path):
    source = '''
rule MetaNumbers : triage {
  meta:
    negative = -7
    hexadecimal = 0x2A
  strings:
    $a = "needle" ascii
  condition:
    $a
}
'''
    report = _compare(scanner, tmp_path, source, b"needle")
    match = report["matches"][0]
    assert match["tags"] == ["triage"]
    assert match["meta"] == {"negative": -7, "hexadecimal": 42}


def test_escaped_metadata_strings_match_yara(scanner, tmp_path):
    source = r'''
rule MetaEscapes : triage {
  meta:
    quoted = "say: \"hello\""
    path = "C:\\Windows\\System32"
    multiline = "first\nsecond"
  strings:
    $a = "needle"
  condition:
    $a
}
'''
    report = _compare(scanner, tmp_path, source, b"needle")
    match = report["matches"][0]
    assert match["tags"] == ["triage"]
    assert match["meta"] == {
        "quoted": 'say: "hello"',
        "path": "C:\\Windows\\System32",
        "multiline": "first\nsecond",
    }


@pytest.mark.parametrize(
    ("pattern", "target"),
    [
        (r'"http://host/#fragment" nocase ascii', b"HTTP://HOST/#FRAGMENT"),
        (r'"say: \"hello\"" fullword ascii', b'say: "hello"'),
        (r'"backslash: \\" ascii', b"backslash: " + bytes([92])),
    ],
)
def test_string_literals_and_modifier_order_match_yara(
    scanner, tmp_path, pattern, target
):
    source = (
        "rule LiteralStructure {\n"
        " strings:\n"
        f"  $a = {pattern}\n"
        " condition:\n"
        "  $a\n"
        "}\n"
    )
    _compare(scanner, tmp_path, source, target)
