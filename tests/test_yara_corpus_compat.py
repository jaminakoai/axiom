"""Pinned real-rule corpus compatibility checks against yara-python 4.5.4."""

import hashlib
import json
import os
import re
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
CORPUS = ROOT / "tests" / "fixtures" / "yara_corpus" / "trellix-atr-2025-03-18"
MANIFEST = CORPUS / "manifest.json"


@pytest.fixture(scope="module")
def corpus_scanner(tmp_path_factory):
    if yara is None:
        pytest.skip("yara-python is unavailable; pinned corpus oracle skipped")
    assert getattr(yara, "__version__", None) == "4.5.4", (
        "pinned real-rule corpus oracle must use yara-python 4.5.4"
    )
    scanner = tmp_path_factory.mktemp("yara-corpus") / "axiom-scan"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    built = subprocess.run(
        [str(AXIOM), "build", str(EXAMPLE), "-o", str(scanner)],
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    return scanner


def _manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _axiom(corpus_scanner, tmp_path, command, rule_file, target=None):
    args = [str(corpus_scanner), command]
    if target is not None:
        args.extend([str(target), "--rules", str(rule_file)])
    else:
        args.append(str(rule_file))
    return subprocess.run(args, capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize(
    ("rule_id", "target"),
    [
        (
            "malw_eicar",
            b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*",
        ),
        (
            "BackdoorFCKG",
            b"A" * 47 + b"\n" + b"keme132.DLL\nklospad.pdb\n",
        ),
    ],
)
def test_supported_real_rules_match_yara_and_axiom(
    corpus_scanner, tmp_path, rule_id, target
):
    entry = next(item for item in _manifest()["rules"] if item["id"] == rule_id)
    assert entry["classification"] == "supported"
    rule_file = CORPUS / entry["file"]
    reference = yara.compile(filepath=str(rule_file)).match(data=target)
    assert rule_id in {match.rule for match in reference}

    rules_path = tmp_path / f"{rule_id}.yar"
    target_path = tmp_path / f"{rule_id}.bin"
    rules_path.write_bytes(rule_file.read_bytes())
    target_path.write_bytes(target)
    result = _axiom(corpus_scanner, tmp_path, "scan", rules_path, target_path)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["match_count"] == len(reference)
    assert rule_id in {match["rule"] for match in report["matches"]}


@pytest.mark.parametrize(
    ("rule_id", "target"),
    [
        ("malw_eicar", b"ordinary harmless text"),
        ("BackdoorFCKG", b"ordinary harmless text"),
    ],
)
def test_supported_real_rules_negative_target_matches_yara_and_axiom(
    corpus_scanner, tmp_path, rule_id, target
):
    entry = next(item for item in _manifest()["rules"] if item["id"] == rule_id)
    rule_file = CORPUS / entry["file"]
    expected = bool(yara.compile(filepath=str(rule_file)).match(data=target))
    assert expected is False

    rules_path = tmp_path / f"{rule_id}-negative.yar"
    target_path = tmp_path / f"{rule_id}-negative.bin"
    rules_path.write_bytes(rule_file.read_bytes())
    target_path.write_bytes(target)
    result = _axiom(corpus_scanner, tmp_path, "scan", rules_path, target_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["match_count"] == int(expected)


def test_manifest_pins_redistributable_sources_and_classifies_every_rule():
    manifest = _manifest()
    assert manifest["source_commit"] == "1919562a59f190bda60c982424f6a24c542ee3e0"
    assert manifest["license"] == "Apache-2.0"
    assert manifest["oracle"] == "yara-python==4.5.4"
    assert manifest["samples"].startswith("Synthetic harmless")
    assert hashlib.sha256((CORPUS / manifest["license_file"]).read_bytes()).hexdigest() == (
        manifest["license_sha256"]
    )

    classified = {}
    for entry in manifest["rules"]:
        assert entry["classification"] in {
            "supported",
            "explicitly unsupported",
            "mismatch",
        }
        source_path = CORPUS / entry["file"]
        assert hashlib.sha256(source_path.read_bytes()).hexdigest() == entry["sha256"]
        assert entry["id"] not in classified
        classified[entry["id"]] = entry

    source_rules = {}
    for rule_file in CORPUS.glob("**/*.yar"):
        text = rule_file.read_text(encoding="utf-8")
        for name in re.findall(r"(?m)^\s*rule\s+([A-Za-z_][A-Za-z0-9_]*)", text):
            source_rules[name] = rule_file.relative_to(CORPUS).as_posix()
    assert set(classified) == set(source_rules)
    assert all(
        classified[name]["file"] == path for name, path in source_rules.items()
    )
    assert "mismatch" not in {entry["classification"] for entry in classified.values()}


@pytest.mark.parametrize(
    "entry",
    [
        item
        for item in _manifest()["rules"]
        if item["classification"] == "explicitly unsupported"
    ],
    ids=lambda item: item["id"],
)
def test_explicitly_unsupported_real_rules_fail_closed(corpus_scanner, tmp_path, entry):
    rule_file = CORPUS / entry["file"]
    # The reference engine must accept the upstream source. Axiom then either
    # reports the unsupported construct or rejects the file-level module.
    yara.compile(filepath=str(rule_file))
    result = _axiom(corpus_scanner, tmp_path, "rules", rule_file)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["ok"] is False
    assert "desteklenmeyen" in report["error"].lower() or "condition" in report["error"].lower()
