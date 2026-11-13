"""Focused regressions for the YARA regex validation and safety gate."""
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"


def _run(src: str):
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    out = path + ".bin"
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        build = subprocess.run(
            [str(AXIOM), "build", path, "-o", out],
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        assert build.returncode == 0, build.stdout + build.stderr
        return subprocess.run([out], capture_output=True, text=True, timeout=120)
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)


def test_yara_regex_rejects_invalid_and_unsafe_patterns():
    run = _run(r'''
import "std/security/yara"
fn main() -> int {
    let invalid_error = yara_validate_pattern("regex:[unclosed")
    let unsafe_error = yara_validate_pattern("regex:(a+)+$")
    let valid_error = yara_validate_pattern("regex:[0-9]+")
    let invalid = yara_scan_regex_result("anything", "[unclosed")
    let unsafe = yara_scan_regex_result("aaaaaaaaaaaaaaaaaaaaaaaa!", "(a+)+$")
    let legacy = yara_scan_regex("anything", "[unclosed")
    let valid_scan = yara_scan_single_pattern("abc123", "$r", "regex:[0-9]+", -1, -1)

    print("validate_invalid:", len(invalid_error) > 0)
    print("validate_unsafe:", len(unsafe_error) > 0)
    print("validate_valid:", len(valid_error) == 0)
    print("checked_invalid:", invalid.is_ok, len(invalid.error) > 0)
    print("checked_unsafe:", unsafe.is_ok, len(unsafe.error) > 0)
    print("legacy_invalid_closed:", legacy)
    print("valid_match:", valid_scan.matched)
    return 0
}
''')
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout.splitlines() == [
        "validate_invalid: true",
        "validate_unsafe: true",
        "validate_valid: true",
        "checked_invalid: false true",
        "checked_unsafe: false true",
        "legacy_invalid_closed: false",
        "valid_match: true",
    ]
