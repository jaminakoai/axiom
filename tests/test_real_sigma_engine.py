"""
Axiom Programming Language (λx) - Real Sigma SIEM & Telemetry Rule Engine Tests
FAZ 4.3: Gerçek Sigma Telemetri ve Log Kural Motoru Doğrulaması
"""
import pytest
import subprocess
import tempfile
import os
from pathlib import Path

from axiom.cli import compile_axiom_source, find_c_compiler

def run_axiom_code(code_str: str) -> tuple[int, str, str]:
    c_code = compile_axiom_source(code_str)
    cc = find_c_compiler()
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        cmd = [cc, "-O3", "-Wall", c_path, "-o", bin_path, "-lssl", "-lcrypto", "-lz", "-ldl", "-pthread"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"C derleme hatasi:\n{res.stderr}\nUretilen C:\n{c_code}"

        run_res = subprocess.run([bin_path], capture_output=True, text=True, timeout=15)
        return run_res.returncode, run_res.stdout, run_res.stderr
    finally:
        if os.path.exists(c_path): os.remove(c_path)
        if os.path.exists(bin_path): os.remove(bin_path)


def test_sigma_field_operators():
    """Kural alan eşleme operatörleri: contains, startswith, endswith, equals, regex."""
    code = '''
    import "std:security:sigma"

    fn main() -> int {
        // 1. Operator: startswith
        let mut r_start = sigma_rule_new("RULE_START", "Prefix Test", "*", "Low")
        r_start = sigma_rule_add_selection(r_start, "uri", "startswith", "/api/v1/auth")

        let mut ev1 = sigma_event_new("web", "GET /api/v1/auth/login HTTP/1.1")
        ev1 = sigma_event_set(ev1, "uri", "/api/v1/auth/login")
        let a1 = sigma_rule_eval(r_start, ev1)
        verify a1.matched == true

        let mut ev1_neg = sigma_event_new("web", "GET /api/v2/auth/login HTTP/1.1")
        ev1_neg = sigma_event_set(ev1_neg, "uri", "/api/v2/auth/login")
        let a1_neg = sigma_rule_eval(r_start, ev1_neg)
        verify a1_neg.matched == false

        // 2. Operator: endswith
        let mut r_end = sigma_rule_new("RULE_END", "Suffix Test", "*", "Low")
        r_end = sigma_rule_add_selection(r_end, "uri", "endswith", ".php")
        let a2 = sigma_rule_eval(r_end, ev1)
        verify a2.matched == false
        let mut ev2 = sigma_event_new("web", "GET /shell.php HTTP/1.1")
        ev2 = sigma_event_set(ev2, "uri", "/shell.php")
        let a2_pos = sigma_rule_eval(r_end, ev2)
        verify a2_pos.matched == true

        // 3. Operator: regex
        let mut r_reg = sigma_rule_new("RULE_REG", "Regex Test", "*", "High")
        r_reg = sigma_rule_add_selection(r_reg, "user", "regex", "^adm.*[0-9]+$")
        let mut ev3 = sigma_event_new("auth", "User login")
        ev3 = sigma_event_set(ev3, "user", "admin99")
        let a3 = sigma_rule_eval(r_reg, ev3)
        verify a3.matched == true

        let mut ev3_bad = sigma_event_new("auth", "User login")
        ev3_bad = sigma_event_set(ev3_bad, "user", "guest")
        let a3_bad = sigma_rule_eval(r_reg, ev3_bad)
        verify a3_bad.matched == false

        print("SIGMA_OPERATORS_OK")
        return 0
    }
    '''
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Stderr: {err}"
    assert "SIGMA_OPERATORS_OK" in out


def test_sigma_false_positive_filtering():
    """Yanlış Pozitif (False Positive) filtreleme ve beyaz liste doğrulama testi."""
    code = '''
    import "std:security:sigma"

    fn main() -> int {
        // SQL Injection kurali tanimla
        let mut r = sigma_rule_new("RULE_SQLI", "SQL Injection Detection", "web", "Critical")
        r = sigma_rule_add_selection(r, "uri", "contains", "UNION SELECT")

        // Yanlis Pozitif Filtreleri:
        // 1. Dokumantasyon sayfalari (/docs/...) filtrelenmeli
        // 2. Dahili guvenlik tarayicisi (10.0.0.99) filtrelenmeli
        r = sigma_rule_add_filter(r, "uri", "startswith", "/docs/")
        r = sigma_rule_add_filter(r, "ip", "equals", "10.0.0.99")

        // 1. Saldiri Senaryosu: Normal saldirgan IP'si ve saldiri URI'si -> ALARM VERMELI
        let mut ev_attack = sigma_event_new("web", "GET /search?q=UNION SELECT password HTTP/1.1")
        ev_attack = sigma_event_set(ev_attack, "uri", "/search?q=UNION SELECT password")
        ev_attack = sigma_event_set(ev_attack, "ip", "192.168.1.100")
        let a1 = sigma_rule_eval(r, ev_attack)
        verify a1.matched == true
        verify a1.risk_score == 100

        // 2. Yanlis Pozitif Senaryosu 1: /docs/ sayfasinda gecen UNION SELECT -> FILTRELENMELI
        let mut ev_fp1 = sigma_event_new("web", "GET /docs/sql/UNION SELECT HTTP/1.1")
        ev_fp1 = sigma_event_set(ev_fp1, "uri", "/docs/sql/UNION SELECT")
        ev_fp1 = sigma_event_set(ev_fp1, "ip", "192.168.1.100")
        let a2 = sigma_rule_eval(r, ev_fp1)
        verify a2.matched == false
        verify a2.matched_reason == "FALSE_POSITIVE_FILTERED"

        // 3. Yanlis Pozitif Senaryosu 2: Yetkili guvenlik tarayici IP'si (10.0.0.99) -> FILTRELENMELI
        let mut ev_fp2 = sigma_event_new("web", "GET /api?id=UNION SELECT HTTP/1.1")
        ev_fp2 = sigma_event_set(ev_fp2, "uri", "/api?id=UNION SELECT")
        ev_fp2 = sigma_event_set(ev_fp2, "ip", "10.0.0.99")
        let a3 = sigma_rule_eval(r, ev_fp2)
        verify a3.matched == false
        verify a3.matched_reason == "FALSE_POSITIVE_FILTERED"

        print("SIGMA_FALSE_POSITIVE_OK")
        return 0
    }
    '''
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Stderr: {err}"
    assert "SIGMA_FALSE_POSITIVE_OK" in out


def test_sigma_severity_and_risk_scoring():
    """Risk şiddet derecelendirmesi ve puanlaması (Low, Medium, High, Critical)."""
    code = '''
    import "std:security:sigma"

    fn main() -> int {
        let r_low = sigma_rule_new("R_LOW", "Low Rule", "*", "Low")
        let r_med = sigma_rule_new("R_MED", "Med Rule", "*", "Medium")
        let r_high = sigma_rule_new("R_HIGH", "High Rule", "*", "High")
        let r_crit = sigma_rule_new("R_CRIT", "Crit Rule", "*", "Critical")

        verify sigma_level_to_score(r_low.level) == 25
        verify sigma_level_to_score(r_med.level) == 50
        verify sigma_level_to_score(r_high.level) == 75
        verify sigma_level_to_score(r_crit.level) == 100

        // Alerts dizisi ve en yuksek siddet tespiti
        let mut engine = sigma_engine_new()
        let mut r1 = sigma_rule_new("R1", "Port Scan", "syslog", "Medium")
        r1 = sigma_rule_add_selection(r1, "message", "contains", "scan")
        engine = sigma_engine_add_rule(engine, r1)

        let mut r2 = sigma_rule_new("R2", "Root Shell Escape", "syslog", "Critical")
        r2 = sigma_rule_add_selection(r2, "message", "contains", "root_escape")
        engine = sigma_engine_add_rule(engine, r2)

        let ev = sigma_event_new("syslog", "Alert: scan detected and root_escape executed")
        let alerts = sigma_engine_eval(engine, ev)

        verify len(alerts) == 2
        let highest = sigma_engine_highest_severity(alerts)
        verify highest == "Critical"
        let max_score = sigma_engine_highest_risk_score(alerts)
        verify max_score == 100

        print("SIGMA_SCORING_OK")
        return 0
    }
    '''
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Stderr: {err}"
    assert "SIGMA_SCORING_OK" in out


def test_sigma_log_types_isolation():
    """Log türü yalıtımı: web kuralı auth olayında tetiklenmemeli."""
    code = '''
    import "std:security:sigma"

    fn main() -> int {
        let mut r_web = sigma_rule_new("WEB_RULE", "Web Only", "web", "High")
        r_web = sigma_rule_add_selection(r_web, "message", "contains", "admin")

        // 1. Auth olayi: icinde 'admin' gecse dahi log_type 'web' olmadigindan tetiklenmemeli
        let ev_auth = sigma_event_new("auth", "User admin logged in via ssh")
        let a1 = sigma_rule_eval(r_web, ev_auth)
        verify a1.matched == false
        verify a1.matched_reason == "LOG_TYPE_MISMATCH"

        // 2. Web olayi: tetiklenmeli
        let ev_web = sigma_event_new("web", "GET /admin/dashboard HTTP/1.1")
        let a2 = sigma_rule_eval(r_web, ev_web)
        verify a2.matched == true

        print("SIGMA_LOG_TYPE_ISOLATION_OK")
        return 0
    }
    '''
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Stderr: {err}"
    assert "SIGMA_LOG_TYPE_ISOLATION_OK" in out


def test_sigma_web_log_parsing_and_attack_detection():
    """Gerçek Web telemetrisi (Apache/Nginx/Proxy) log ayrıştırma ve saldırı tespiti."""
    code = '''
    import "std:security:sigma"

    fn main() -> int {
        let default_engine = sigma_get_default_ruleset()

        // 1. SQL Injection Web Isteği
        let raw_sqli = "192.168.1.100 - - [04/Nov/2026:12:00:00 +0000] \\\"GET /api/users?id=1%20UNION%20SELECT%20password%20FROM%20admins HTTP/1.1\\\" 200 450"
        let ev_sqli = sigma_parse_web_log(raw_sqli)
        verify sigma_event_get(ev_sqli, "method") == "GET"
        verify sigma_event_get(ev_sqli, "ip") == "192.168.1.100"

        let sqli_alerts = sigma_engine_eval(default_engine, ev_sqli)
        verify len(sqli_alerts) > 0
        verify sqli_alerts[0].rule_id == "SQL_INJECTION"
        verify sqli_alerts[0].level == "Critical"

        // 2. XSS Web Isteği
        let raw_xss = "10.0.0.50 - - [04/Nov/2026:12:05:00 +0000] \\\"GET /comment?body=<script>alert(1)</script> HTTP/1.1\\\" 200 120"
        let ev_xss = sigma_parse_web_log(raw_xss)
        let xss_alerts = sigma_engine_eval(default_engine, ev_xss)
        verify len(xss_alerts) > 0
        verify xss_alerts[0].rule_id == "XSS_ATTACK"

        // 3. Path Traversal
        let raw_pt = "172.16.0.4 - - [04/Nov/2026:12:10:00 +0000] \\\"GET /download?file=../../../../etc/passwd HTTP/1.1\\\" 403 80"
        let ev_pt = sigma_parse_web_log(raw_pt)
        let pt_alerts = sigma_engine_eval(default_engine, ev_pt)
        verify len(pt_alerts) > 0
        verify pt_alerts[0].rule_id == "PATH_TRAVERSAL"

        print("SIGMA_WEB_TELEMETRY_OK")
        return 0
    }
    '''
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Stderr: {err}"
    assert "SIGMA_WEB_TELEMETRY_OK" in out


def test_sigma_auth_telemetry_bruteforce():
    """Auth/SSH telemetrisi log ayrıştırma ve brute-force saldırı tespiti."""
    code = '''
    import "std:security:sigma"

    fn main() -> int {
        let engine = sigma_get_default_ruleset()

        // 1. SSH Brute Force Saldiri Olayi
        let raw_auth = "Nov  4 19:30:00 debian-prod sshd[4567]: Failed password for invalid user root from 203.0.113.195 port 55432 ssh2"
        let ev = sigma_parse_auth_log(raw_auth)

        verify sigma_event_get(ev, "action") == "failed_login"
        verify sigma_event_get(ev, "service") == "sshd"
        verify sigma_event_get(ev, "user") == "root"
        verify sigma_event_get(ev, "ip") == "203.0.113.195"

        let alerts = sigma_engine_eval(engine, ev)
        verify len(alerts) == 1
        verify alerts[0].rule_id == "SSH_BRUTE_FORCE"
        verify alerts[0].level == "Critical"
        verify alerts[0].risk_score == 100

        // 2. Yanlis Pozitif: 127.0.0.1 Health Check (SSH Brute Force filtresi tetiklenmeli)
        let raw_local = "Nov  4 19:31:00 debian-prod sshd[4568]: Failed password for invalid user monitor from 127.0.0.1 port 55433 ssh2"
        let ev_local = sigma_parse_auth_log(raw_local)
        let alerts_local = sigma_engine_eval(engine, ev_local)
        verify len(alerts_local) == 0

        print("SIGMA_AUTH_TELEMETRY_OK")
        return 0
    }
    '''
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Stderr: {err}"
    assert "SIGMA_AUTH_TELEMETRY_OK" in out
