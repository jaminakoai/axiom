"""Focused regression coverage for YARA string escapes and line comments."""

import json
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
EXAMPLE = ROOT / "examples" / "21_axiom_scan.ax"


@pytest.fixture(scope="module")
def scanner(tmp_path_factory):
    out = tmp_path_factory.mktemp("yara-escapes") / "axiom-scan"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        [str(AXIOM), "build", str(EXAMPLE), "-o", str(out)],
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return out


def _scan(scanner, tmp_path, pattern, target):
    rule_file = tmp_path / "escape-rule.yar"
    rule_file.write_text(
        'rule EscapeCheck {\n strings:\n  $a = "' + pattern + '"\n'
        ' condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    target_file = tmp_path / "target.bin"
    target_file.write_bytes(target)
    return subprocess.run(
        [str(scanner), "scan", str(target_file), "--rules", str(rule_file)],
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize(
    ("pattern", "target"),
    [
        (r"backslash: \\", b"backslash: \\"),
        (r'quote: \"', b'quote: "'),
        (r"line\nbreak", b"line\nbreak"),
        (r"carriage\rreturn", b"carriage\rreturn"),
        (r"tab\tstop", b"tab\tstop"),
        (r"hex: \x41", b"hex: A"),
        # Escaping a backslash must not cause a following xNN to be decoded.
        (r"literal: \\x41", b"literal: \\x41"),
    ],
)
def test_yara_text_escapes_are_decoded_once(scanner, tmp_path, pattern, target):
    result = _scan(scanner, tmp_path, pattern, target)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["match_count"] == 1


@pytest.mark.parametrize("pattern", [r"bad: \q", r"bad: \x", r"bad: \x4", r"bad: \xGG", r"bad: \x00"])
def test_unsupported_or_invalid_yara_escapes_are_rejected(scanner, tmp_path, pattern):
    rule_file = tmp_path / "invalid-escape.yar"
    rule_file.write_text(
        'rule InvalidEscape {\n strings:\n  $a = "' + pattern + '"\n'
        ' condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(scanner), "rules", str(rule_file)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


def test_line_comments_do_not_truncate_strings_and_trailing_comments_are_ignored(scanner, tmp_path):
    rule_file = tmp_path / "comment-string.yar"
    rule_file.write_text(
        'rule CommentString {\n strings:\n'
        '  $a = "http://example.invalid/#payload" // actual comment\n'
        '  $b = "quote: \\"//inside-quote" // another comment\n'
        ' condition:\n  $a and $b // condition comment\n}\n',
        encoding="utf-8",
    )
    target_file = tmp_path / "comment-target.bin"
    target_file.write_bytes(b'http://example.invalid/#payload quote: "//inside-quote')
    result = subprocess.run(
        [str(scanner), "scan", str(target_file), "--rules", str(rule_file)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["match_count"] == 1


def test_single_trailing_slash_is_not_treated_as_comment(scanner, tmp_path):
    rule_file = tmp_path / "trailing-slash.yar"
    rule_file.write_text(
        'rule TrailingSlash {\n strings:\n  $a = "needle"\n'
        ' condition:\n  $a\n}\n/\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(scanner), "rules", str(rule_file)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 1
    assert "desteklenmeyen ust-duzey" in json.loads(result.stdout)["error"]
