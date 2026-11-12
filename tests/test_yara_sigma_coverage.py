"""
Axiom - YARA / Sigma kapsam tamamlama (P1-04)

Ajan raporunda "testsiz" görünen fonksiyonlar. Hepsi doğrulandı;
bu dosya davranışlarını kilitler.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"


def _run(src: str, backend: str = "c"):
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    out = path + ".bin"
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        args = [str(AXIOM), "build", path, "-o", out]
        if backend == "llvm":
            args.insert(2, "--backend=llvm")
        b = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
        assert b.returncode == 0, b.stdout + b.stderr
        return subprocess.run([out], capture_output=True, text=True, timeout=120)
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)


# ---------------------------------------------------------------------------
# YARA — kural oluşturucular ve ofset API'si
# ---------------------------------------------------------------------------

def test_yara_rule_offset_builders():
    out = _run("""
import "std/security/yara"
fn main() -> int {
    let base = yara_rule_new("R", "any of them")
    let b = yara_rule_set_offset_bounds(base, 4, 10)
    let a = yara_rule_set_at_offset(base, 7)
    print("bounds:", b.min_offset, b.max_offset)
    print("at:", a.min_offset, a.max_offset)
    print("name:", b.name, "cond:", b.condition)
    return 0
}
""")
    assert out.stdout.splitlines() == ["bounds: 4 10", "at: 7 7", "name: R cond: any of them"]


def test_yara_scan_single_pattern_all_kinds():
    out = _run("""
import "std/security/yara"
import "std/io/binary"
fn main() -> int {
    let s = yara_scan_single_pattern("hello world", "$a", "str:world", -1, -1)
    print("str:", s.matched, s.offset, s.matched_len, s.pattern_id)

    let r = yara_scan_single_pattern("abc123", "$r", "regex:[0-9]+", -1, -1)
    print("regex:", r.matched)

    // Ham baytlar icin buf_* API'si kullanilir; char_to_str artik UTF-8 uretir
    // (0x89 tek basina gecerli UTF-8 degildir).
    let bb = buf_create(16)
    buf_write_u8(bb, 65)
    buf_write_u8(bb, 65)
    buf_write_u8(bb, 65)
    buf_write_u8(bb, 72)
    buf_write_u8(bb, 137)
    buf_write_u8(bb, 1)
    buf_write_u8(bb, 85)
    let raw = buf_to_str(bb)
    let h = yara_scan_single_pattern(raw, "$h", "hex:48 89 ?? 55", -1, -1)
    buf_free(bb)
    print("hex:", h.matched, h.offset)

    let miss = yara_scan_single_pattern("abc", "$x", "str:zzz", -1, -1)
    print("miss:", miss.matched, miss.offset)

    // ofset kısıtı: eşleşme 6'da, min 10 -> bulunmamalı
    let o = yara_scan_single_pattern("hello world", "$a", "str:world", 10, -1)
    print("offset_reject:", o.matched)
    return 0
}
""")
    assert out.stdout.splitlines() == [
        "str: true 6 5 $a",
        "regex: true",
        "hex: true 3",
        "miss: false -1",
        "offset_reject: false",
    ]


def test_yara_ruleset_helpers():
    out = _run("""
import "std/security/yara"
fn main() -> int {
    let rs = yara_ruleset_add_rule(
        yara_ruleset_new(),
        yara_rule_add_pattern(yara_rule_new("R", "any of them"), "$a", "str:needle"))
    print("has:", yara_ruleset_has_match("a needle here", rs))
    print("count:", yara_ruleset_count_matches("a needle here", rs))
    print("none:", yara_ruleset_has_match("temiz", rs))
    print("count_none:", yara_ruleset_count_matches("temiz", rs))
    return 0
}
""")
    assert out.stdout.splitlines() == ["has: true", "count: 1", "none: false", "count_none: 0"]


def test_yara_legacy_buffer_regex_hex():
    out = _run("""
import "std/security/yara"
fn main() -> int {
    print("buffer:", yara_scan_buffer("some text here", "text"))
    print("buffer_miss:", yara_scan_buffer("some text", "zzz"))
    print("regex:", yara_scan_regex("abc123", "[0-9]+"))
    print("hex_wild:", yara_scan_hex("48 65 6c 6c 6f", "48 65 ?? 6c"))
    print("hex_plain:", yara_scan_hex("hello", "ell"))
    return 0
}
""")
    assert out.stdout.splitlines() == [
        "buffer: true", "buffer_miss: false", "regex: true",
        "hex_wild: true", "hex_plain: true",
    ]


def test_yara_scan_buf_with_binary_buffer():
    out = _run("""
import "std/security/yara"
import "std/io/binary"
fn main() -> int {
    let h = buf_create(16)
    buf_write_u8(h, 72)   # H
    buf_write_u8(h, 73)   # I
    buf_write_u8(h, 33)   # !
    let off = yara_scan_buf(h, "48 49", -1, -1)
    print("off:", off)
    let miss = yara_scan_buf(h, "5A 5A", -1, -1)
    print("miss:", miss)
    buf_free(h)
    return 0
}
""")
    assert out.stdout.splitlines() == ["off: 0", "miss: -1"]


# ---------------------------------------------------------------------------
# Sigma
# ---------------------------------------------------------------------------

def test_sigma_eval_operators():
    out = _run("""
import "std/security/sigma"
fn main() -> int {
    print("eq:", sigma_eval_op("abc", "equals", "abc"))
    print("eq_neg:", sigma_eval_op("abc", "equals", "abd"))
    print("contains:", sigma_eval_op("hello world", "contains", "world"))
    print("sw:", sigma_eval_op("hello", "startswith", "he"))
    print("ew:", sigma_eval_op("hello", "endswith", "lo"))
    print("rx:", sigma_eval_op("abc123", "regex", "[0-9]+"))
    print("rx_neg:", sigma_eval_op("abcdef", "regex", "[0-9]+"))
    print("bilinmeyen:", sigma_eval_op("a", "yokboyle", "a"))
    return 0
}
""")
    assert out.stdout.splitlines() == [
        "eq: true", "eq_neg: false", "contains: true", "sw: true",
        "ew: true", "rx: true", "rx_neg: false", "bilinmeyen: false",
    ]


def test_sigma_rule_set_condition():
    out = _run("""
import "std/security/sigma"
fn main() -> int {
    let r0 = sigma_rule_new("t1", "T", "auth", "high")
    print("default:", r0.condition)
    let r1 = sigma_rule_set_condition(r0, "selection and not filter")
    print("set:", r1.condition)
    print("id_kept:", r1.id, r1.log_type, r1.level)
    return 0
}
""")
    assert out.stdout.splitlines() == [
        "default: selection and not filter",
        "set: selection and not filter",
        "id_kept: t1 auth high",
    ]


def test_sigma_parse_syslog_and_auth_log():
    out = _run("""
import "std/security/sigma"
fn main() -> int {
    let s = sigma_parse_syslog("Jan  1 00:00:00 host sshd[123]: Failed password for root")
    print("syslog_type:", s.log_type)
    print("syslog_service:", sigma_event_get(s, "service"))
    print("syslog_msg_has:", str_contains(sigma_event_get(s, "message"), "Failed password"))

    let a = sigma_parse_auth_log("Jan 1 00:00:00 host sshd[1]: Failed password for root from 1.2.3.4 port 22 ssh2")
    print("auth_type:", a.log_type)
    print("auth_user:", sigma_event_get(a, "user"))
    print("auth_ip:", sigma_event_get(a, "ip"))
    print("auth_action:", sigma_event_get(a, "action"))
    return 0
}
""")
    assert out.stdout.splitlines() == [
        "syslog_type: syslog",
        "syslog_service: sshd[123]",
        "syslog_msg_has: true",
        "auth_type: auth",
        "auth_user: root",
        "auth_ip: 1.2.3.4",
        "auth_action: failed_login",
    ]


def test_sigma_engine_raw_and_has_alert():
    out = _run("""
import "std/security/sigma"
fn main() -> int {
    let e = sigma_get_default_ruleset()
    print("rules:", len(e.rules))

    let line = "Jan 1 00:00:00 host sshd[1]: Failed password for root from 1.2.3.4 port 22 ssh2"
    print("auth_alerts:", len(sigma_engine_eval_raw(e, line, "auth")))
    // syslog tipi: SSH kuralı "auth" tipinde olduğu için eşleşmez
    print("syslog_alerts:", len(sigma_engine_eval_raw(e, line, "syslog")))
    print("web_alerts:", len(sigma_engine_eval_raw(e, line, "web")))

    let ev = sigma_parse_auth_log(line)
    print("has_alert:", sigma_engine_has_alert(e, ev))

    let clean = sigma_parse_auth_log("Jan 1 00:00:00 host sshd[1]: Accepted password for root")
    print("clean_has:", sigma_engine_has_alert(e, clean))
    return 0
}
""")
    assert out.stdout.splitlines() == [
        "rules: 5",
        "auth_alerts: 1",
        "syslog_alerts: 0",
        "web_alerts: 0",
        "has_alert: true",
        "clean_has: false",
    ]


def test_sigma_legacy_match_and_count():
    out = _run("""
import "std/security/sigma"
fn main() -> int {
    print("match:", sigma_match_rule("Failed password for root", "Failed password"))
    print("match_no:", sigma_match_rule("Accepted password", "Failed password"))
    let logs = ["Failed password", "Accepted password", "Failed password", "x"]
    print("count:", sigma_count_matches(logs, "Failed password"))
    let empty: str[] = []
    print("empty:", sigma_count_matches(empty, "x"))
    return 0
}
""")
    assert out.stdout.splitlines() == ["match: true", "match_no: false", "count: 2", "empty: 0"]


def test_sigma_rule_eval_direct():
    out = _run("""
import "std/security/sigma"
fn main() -> int {
    let mut r = sigma_rule_new("R1", "T", "auth", "High")
    r = sigma_rule_add_selection(r, "message", "contains", "boom")
    let ev = sigma_event_new("auth", "kaboom happened")
    let alert = sigma_rule_eval(r, ev)
    print("matched:", alert.matched, "rule:", alert.rule_id)
    let ev2 = sigma_event_new("auth", "sakin")
    print("nomatch:", sigma_rule_eval(r, ev2).matched)
    return 0
}
""")
    assert out.stdout.splitlines() == ["matched: true rule: R1", "nomatch: false"]


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_yara_sigma_llvm_parity(backend):
    src = """
import "std/security/yara"
import "std/security/sigma"
fn main() -> int {
    let s = yara_scan_single_pattern("hello world", "$a", "str:world", -1, -1)
    print("yara:", s.matched, s.offset, s.matched_len)
    let e = sigma_get_default_ruleset()
    let line = "Jan 1 00:00:00 host sshd[1]: Failed password for root from 1.2.3.4 port 22 ssh2"
    print("sigma:", len(sigma_engine_eval_raw(e, line, "auth")))
    print("op:", sigma_eval_op("abc123", "regex", "[0-9]+"))
    return 0
}
"""
    out = _run(src, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == ["yara: true 6 5", "sigma: 1", "op: true"]
