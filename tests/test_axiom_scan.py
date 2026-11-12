"""
Axiom - axiom-scan v0.1 (P1-03)

YARA alt kümesi ayrıştırma + dosya/PCAP tarama + JSON çıktısı + hata yolları.
"""
import json
import os
import struct
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
EXAMPLE = ROOT / "examples" / "21_axiom_scan.ax"

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
    out = tmp_path_factory.mktemp("scan") / "axiom-scan"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    res = subprocess.run([str(AXIOM), "build", str(EXAMPLE), "-o", str(out)],
                         capture_output=True, text=True, timeout=600, env=env)
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
    assert data["ok"] is True
    assert data["rules"] == 3


@pytest.mark.parametrize("condition", [
    "none of them",
    "$a and not $b",
    "$a at 0",
    "#a == 2",
    "filesize < 10",
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
    '"needle" fullword',
    '{ 4D 5A [2-4] 50 45 }',
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
    out = tmp_path_factory.mktemp("scan_llvm") / "axiom-scan-llvm"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    res = subprocess.run([str(AXIOM), "build", str(EXAMPLE), "--backend=llvm", "-o", str(out)],
                         capture_output=True, text=True, timeout=900, env=env)
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
    assert json.loads(c_res.stdout) == json.loads(l_res.stdout)

    bin_target = tmp_path / "shell.bin"
    bin_target.write_bytes(b"AAAA\x48\x89\x01\x55BBBB")
    c_bin = _run(scanner, "scan", str(bin_target), "--rules", str(r))
    l_bin = _run(scanner_llvm, "scan", str(bin_target), "--rules", str(r))
    assert json.loads(c_bin.stdout) == json.loads(l_bin.stdout)
    assert json.loads(l_bin.stdout)["matches"][0]["rule"] == "Hex_Shellcode"


def test_llvm_scanner_rules_count(scanner_llvm, tmp_path):
    r = tmp_path / "rules.yar"
    r.write_text(RULES, encoding="utf-8")
    res = _run(scanner_llvm, "rules", str(r))
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout)["rules"] == 3


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
    assert data["ok"] is False
    assert data["schema_version"] == "1"
    assert "bulunamadi" in data["error"]


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
