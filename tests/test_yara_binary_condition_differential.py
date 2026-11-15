"""YARA 4.5.4 differential coverage for binary-buffer conditions."""

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
        pytest.skip("yara-python is unavailable; binary condition oracle skipped")
    assert getattr(yara, "__version__", None) == "4.5.4", (
        "binary condition differential oracle must be yara-python 4.5.4"
    )
    output = tmp_path_factory.mktemp("yara-binary-condition") / "axiom-scan"
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


def _compare(scanner, tmp_path, condition: str, target: bytes):
    source = (
        "rule BinaryConditionDiff {\n strings:\n  $a = { 41 00 42 }\n"
        " condition:\n  "
        + condition
        + "\n}\n"
    )
    reference = yara.compile(source=source).match(data=target)
    expected = bool(reference)

    rules_path = tmp_path / "binary-condition.yar"
    target_path = tmp_path / "binary-condition.bin"
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
    assert report["match_count"] == int(expected), (
        f"condition={condition!r}, YARA 4.5.4={expected}, "
        f"Axiom match_count={report['match_count']}"
    )
    return expected


@pytest.mark.parametrize(
    ("condition", "target"),
    [
        # Two occurrences of a hex string that itself crosses embedded NULs.
        ("#a == 2", b"P\x00A\x00BQ A\x00B".replace(b" ", b"")),
        ("#a == 1", b"P\x00A\x00BQ A\x00B".replace(b" ", b"")),
        ("@a[1] == 2 and @a[2] == 6", b"P\x00A\x00BQ A\x00B".replace(b" ", b"")),
        ("@a[2] == 7", b"P\x00A\x00BQ A\x00B".replace(b" ", b"")),
        ("!a[1] == 3 and !a[2] == 3", b"P\x00A\x00BQ A\x00B".replace(b" ", b"")),
        ("!a[2] == 2", b"P\x00A\x00BQ A\x00B".replace(b" ", b"")),
        ("$a at 2", b"P\x00A\x00BQ A\x00B".replace(b" ", b"")),
        ("$a at 1", b"P\x00A\x00BQ A\x00B".replace(b" ", b"")),
        ("$a in (6..6)", b"P\x00A\x00BQ A\x00B".replace(b" ", b"")),
        ("$a in (7..8)", b"P\x00A\x00BQ A\x00B".replace(b" ", b"")),
        (
            "#a == 2 and @a[2] == 6 and !a[1] == 3 and filesize == 9",
            b"P\x00A\x00BQ A\x00B".replace(b" ", b""),
        ),
        (
            "($a at 2 or $a in (6..6)) and #a == 2 and filesize == 9",
            b"P\x00A\x00BQ A\x00B".replace(b" ", b""),
        ),
        (
            "($a at 2 or $a in (6..6)) and filesize == 8",
            b"P\x00A\x00BQ A\x00B".replace(b" ", b""),
        ),
        ("#a == 0 and filesize == 5", b"P\x00ABC"),
        # Hexadecimal integer literals must behave like decimal values in
        # occurrence, file-size, and offset expressions.
        ("#a >= 0x2 and filesize == 0x6", b"A\x00BA\x00B"),
        ("#a < 0x2 and filesize == 0x6", b"A\x00BA\x00B"),
        ("$a in (0x1..0x2) and @a[1] == 0x1", b"zA\x00B"),
        ("$a at 0x0", b"zA\x00B"),
    ],
)
def test_binary_occurrence_and_range_conditions_match_yara_454(
    scanner, tmp_path, condition, target
):
    _compare(scanner, tmp_path, condition, target)
