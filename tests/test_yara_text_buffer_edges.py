"""YARA 4.5.4 differential checks for text patterns over binary targets."""

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
        pytest.skip("yara-python is unavailable; text buffer oracle skipped")
    assert getattr(yara, "__version__", None) == "4.5.4", (
        "text buffer oracle must be yara-python 4.5.4"
    )
    output = tmp_path_factory.mktemp("yara-text-buffer") / "axiom-scan"
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


def _compare(scanner, tmp_path, pattern: str, condition: str, target: bytes):
    source = (
        'rule BinaryTextEdge {\n strings:\n  $a = "' + pattern + '"\n'
        ' condition:\n  ' + condition + "\n}\n"
    )
    reference = yara.compile(source=source).match(data=target)
    rules_path = tmp_path / "binary-text.yar"
    target_path = tmp_path / "binary-text.bin"
    rules_path.write_text(source, encoding="utf-8")
    target_path.write_bytes(target)
    result = subprocess.run(
        [str(scanner), "scan", str(target_path), "--rules", str(rules_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["match_count"] == len(reference)

    if not reference:
        assert report["matches"] == []
        return

    axiom_match = report["matches"][0]
    reference_match = reference[0]
    instances = [
        instance
        for string_match in reference_match.strings
        for instance in getattr(string_match, "instances", [])
    ]
    assert instances, "YARA matched the rule but returned no pattern instance"
    assert (axiom_match["offset"], axiom_match["length"]) == (
        instances[0].offset,
        instances[0].matched_length,
    )


@pytest.mark.parametrize(
    ("pattern", "modifier", "condition", "target"),
    [
        # ASCII-only nocase folds the letters while preserving byte offsets
        # across high bytes and an embedded NUL.
        ("needle", "ascii nocase", "any of them", b"\x80nEeDlE\x00NEEDLE\xff"),
        # High-bit bytes are not case-folded into ASCII letters.
        ("A", "ascii nocase", "any of them", b"\xc0"),
        # NUL and high-bit bytes act as fullword boundaries; both instances
        # count, and occurrence positions remain absolute byte offsets.
        (
            "needle",
            "fullword",
            "#a == 2 and @a[1] == 1 and @a[2] == 8 and !a[2] == 6",
            b"\xffneedle\x00needle\xfe",
        ),
        # A high byte is a boundary, but ASCII letters on either side block
        # fullword matches.
        ("needle", "fullword", "any of them", b"Aneedle\x00Xneedle\xff"),
        # Overlapping case-insensitive occurrences are counted at byte offsets.
        (
            "aba",
            "nocase",
            "#a == 2 and @a[1] == 0 and @a[2] == 2",
            b"ABaBa",
        ),
        # UTF-8 bytes before the match must not be counted as one character.
        ("needle", "ascii nocase", "$a at 2", b"\xc3\xa9NEEDLE\x00"),
    ],
)
def test_binary_text_edges_match_yara_454(
    scanner, tmp_path, pattern, modifier, condition, target
):
    _compare(scanner, tmp_path, pattern + " " + modifier, condition, target)
