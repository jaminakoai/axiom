"""C/LLVM parity at inclusive YARA condition boundaries around embedded NUL."""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yara

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
EXAMPLE = ROOT / "examples" / "21_axiom_scan.ax"


@pytest.fixture(scope="module")
def scanners(tmp_path_factory):
    assert yara.__version__ == "4.5.4"
    outputs = {}
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    for backend in ("c", "llvm"):
        output = tmp_path_factory.mktemp(f"scan-condition-{backend}") / "axiom-scan"
        command = [str(AXIOM), "build", str(EXAMPLE), "-o", str(output)]
        if backend == "llvm":
            command.insert(2, "--backend=llvm")
        built = subprocess.run(
            command, capture_output=True, text=True, timeout=900, env=env
        )
        assert built.returncode == 0, built.stdout + built.stderr
        outputs[backend] = output
    return outputs


def test_condition_inclusive_offset_boundaries_and_nul_have_backend_parity(
    scanners, tmp_path
):
    rules_source = '''
rule TextAtBoundary {
 strings:
  $text = "needle"
 condition:
  $text at 4
}
rule TextInExactBoundary {
 strings:
  $text = "needle"
 condition:
  $text in (4..4)
}
rule TextOutsideBoundary {
 strings:
  $text = "needle"
 condition:
  $text in (5..8)
}
rule HexCrossNulAtBoundary {
 strings:
  $cross = { 41 00 42 }
 condition:
  $cross at 10
}
rule HexCrossNulWithSize {
 strings:
  $cross = { 41 00 42 }
 condition:
  $cross in (10..10) and filesize == 15
}
rule HexTailAtUpperInclusive {
 strings:
  $tail = { 42 43 }
 condition:
  $tail in (13..13)
}
rule HexTailOutsideUpper {
 strings:
  $tail = { 42 43 }
 condition:
  $tail in (14..20)
}
rule BooleanAtBoundaryWithSize {
 strings:
  $text = "needle"
  $cross = { 41 00 42 }
 condition:
  ($text in (4..4) or $cross at 11) and filesize == 15
}
rule WrongOffsetAfterNul {
 strings:
  $cross = { 41 00 42 }
 condition:
  $cross at 11 and filesize == 15
}
'''
    payload = b"PRE\x00needleA\x00BBC"
    rules_path = tmp_path / "condition-boundaries.yar"
    target_path = tmp_path / "target.bin"
    rules_path.write_text(rules_source, encoding="utf-8")
    target_path.write_bytes(payload)

    reference = {
        match.rule
        for match in yara.compile(source=rules_source).match(data=payload)
    }
    expected = {
        "TextAtBoundary",
        "TextInExactBoundary",
        "HexCrossNulAtBoundary",
        "HexCrossNulWithSize",
        "HexTailAtUpperInclusive",
        "BooleanAtBoundaryWithSize",
    }
    assert reference == expected

    reports = {}
    for backend, executable in scanners.items():
        scanned = subprocess.run(
            [str(executable), "scan", str(target_path), "--rules", str(rules_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert scanned.returncode == 0, scanned.stdout + scanned.stderr
        reports[backend] = json.loads(scanned.stdout)
        assert reports[backend]["ok"] is True
        assert reports[backend]["scanned_bytes"] == len(payload)
        actual = {item["rule"] for item in reports[backend]["matches"]}
        assert actual == expected

    assert reports["c"] == reports["llvm"]


def test_nibble_jump_occurrences_with_nul_have_backend_parity(scanners, tmp_path):
    rules_source = '''
rule MaskJumpOccurrence {
 strings:
  $a = { 4? [0-1] ?2 }
 condition:
  #a == 2 and @a[2] == 3 and !a[2] == 2
}
'''
    payload = bytes.fromhex("4A 00 52 4B 52")
    reference = yara.compile(source=rules_source).match(data=payload)
    assert len(reference) == 1
    assert [
        (instance.offset, instance.matched_length)
        for item in reference[0].strings
        for instance in getattr(item, "instances", [])
    ] == [(0, 3), (3, 2)]

    rules_path = tmp_path / "mask-jump-parity.yar"
    target_path = tmp_path / "mask-jump-parity.bin"
    rules_path.write_text(rules_source, encoding="utf-8")
    target_path.write_bytes(payload)

    reports = {}
    for backend, executable in scanners.items():
        scanned = subprocess.run(
            [str(executable), "scan", str(target_path), "--rules", str(rules_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert scanned.returncode == 0, scanned.stdout + scanned.stderr
        reports[backend] = json.loads(scanned.stdout)
        assert reports[backend]["match_count"] == 1
        assert reports[backend]["scanned_bytes"] == len(payload)
        witness = reports[backend]["matches"][0]
        assert (witness["offset"], witness["length"]) == (0, 3)

    assert reports["c"] == reports["llvm"]
