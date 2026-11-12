"""
Axiom Programming Language (λx) - Real YARA Byte & Wildcard Mask Engine Tests
FAZ 4.3: Gerçek YARA Bayt & Maske Tarama Motoru Doğrulaması
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


def test_yara_hex_wildcard_match_and_mismatch():
    """Hex wildcard desenleri (örn. '48 89 ?? 55 ?? 8b') eslesme ve negatif eslesmeme testi."""
    code = '''
    import "std:security:yara"
    import "std:encoding:hex"

    fn main() -> int {
        // Hedef tampon: icinde 0x48, 0x89, 0xaa, 0x55, 0xbb, 0x8b bayt dizilimi bulunan veri
        let sample = "HEADER_START:__" + hex_decode("4889aa55bb8b") + "__:FOOTER_END"
        let pattern = "48 89 ?? 55 ?? 8b"

        let offset = yara_find_hex_wildcard(sample, pattern)
        verify offset >= 0
        verify yara_match_hex_wildcard(sample, pattern) == true

        // Negatif Test: Ortadaki sabit bayt 0x55 yerine 0x99 varsa eslesmemeli
        let bad_sample = "HEADER_START:__" + hex_decode("4889aa99bb8b") + "__:FOOTER_END"
        let bad_offset = yara_find_hex_wildcard(bad_sample, pattern)
        verify bad_offset == -1
        verify yara_match_hex_wildcard(bad_sample, pattern) == false

        print("YARA_WILDCARD_HEX_OK: offset=", offset)
        return 0
    }
    '''
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Stderr: {err}"
    assert "YARA_WILDCARD_HEX_OK" in out


def test_yara_call_e8_wildcard():
    """x86 CALL E8 ?? ?? ?? ?? desen tarama testi."""
    code = '''
    import "std:security:yara"

    fn main() -> int {
        let code_hex = "909090e83412000058c3"
        let call_pattern = "e8 ?? ?? ?? ??"

        let off = yara_find_hex_wildcard(code_hex, call_pattern)
        verify off == 3

        let fake_hex = "909090eb3412000058c3"
        let bad_off = yara_find_hex_wildcard(fake_hex, call_pattern)
        verify bad_off == -1

        print("YARA_CALL_E8_OK")
        return 0
    }
    '''
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Stderr: {err}"
    assert "YARA_CALL_E8_OK" in out


def test_yara_offset_constraints():
    """Bayt kaydırma ve ofset sınır denetimleri (min_offset, max_offset, exact offset)."""
    code = '''
    import "std:security:yara"
    import "std:encoding:hex"

    fn main() -> int {
        // Desen 10. indekste yer alsin: 10 adet 'A' + 0x55, 0x89, 0xe5
        let target = "AAAAAAAAAA" + hex_decode("5589e5") + "ZZZZZZZZZZ"
        let sig = "55 89 e5"

        // 1. Ofset araligi icinde (min=5, max=15) -> Eslesmeli
        let off1 = yara_find_hex_wildcard_at(target, sig, 5, 15)
        verify off1 == 10

        // 2. Ofset araligi disinda (min=0, max=8) -> Eslesmemeli (-1)
        let off2 = yara_find_hex_wildcard_at(target, sig, 0, 8)
        verify off2 == -1

        // 3. Exact ofset (tam 10. baytta mi?) -> Eslesmeli
        let off3 = yara_find_hex_wildcard_at(target, sig, 10, 10)
        verify off3 == 10

        // 4. Exact ofset hatali (tam 12. baytta mi?) -> Eslesmemeli (-1)
        let off4 = yara_find_hex_wildcard_at(target, sig, 12, 12)
        verify off4 == -1

        print("YARA_OFFSET_CONSTRAINTS_OK")
        return 0
    }
    '''
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Stderr: {err}"
    assert "YARA_OFFSET_CONSTRAINTS_OK" in out


def test_yara_condition_all_of_them():
    """Çoklu imza koşul testi: condition: 'all of them'."""
    code = '''
    import "std:security:yara"
    import "std:encoding:hex"

    fn main() -> int {
        let mut rule = yara_rule_new("Axiom_Backdoor_Rule", "all of them")
        rule = yara_rule_add_pattern(rule, "$h1", "48 89 ?? 55")
        rule = yara_rule_add_pattern(rule, "$s1", "str:MALICIOUS_C2_CMD")

        // Pozitif Senaryo: Her iki desen de mevcut
        let payload1 = "PREFIX:" + hex_decode("48891155") + ":PAYLOAD:MALICIOUS_C2_CMD:SUFFIX"
        let match1 = yara_scan_rule(payload1, rule)
        verify match1.matched == true
        verify match1.rule_name == "Axiom_Backdoor_Rule"

        // Negatif Senaryo: Sadece $h1 var, $s1 eksik -> 'all of them' basarisiz olmali
        let payload2 = "PREFIX:" + hex_decode("48891155") + ":PAYLOAD:BENIGN_SAFE_CMD:SUFFIX"
        let match2 = yara_scan_rule(payload2, rule)
        verify match2.matched == false

        print("YARA_ALL_OF_THEM_OK")
        return 0
    }
    '''
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Stderr: {err}"
    assert "YARA_ALL_OF_THEM_OK" in out


def test_yara_condition_any_of_them():
    """Çoklu imza koşul testi: condition: 'any of them'."""
    code = '''
    import "std:security:yara"
    import "std:encoding:hex"

    fn main() -> int {
        let mut rule = yara_rule_new("Axiom_Suspicious_Strings", "any of them")
        rule = yara_rule_add_pattern(rule, "$str1", "str:mimikatz")
        rule = yara_rule_add_pattern(rule, "$str2", "str:cobaltstrike")
        rule = yara_rule_add_pattern(rule, "$hex1", "90 90 90 cc")

        // 1. Durum: Sadece $str2 mevcut -> Eslesmeli
        let buf1 = "System log: agent loaded cobaltstrike module in memory"
        verify yara_rule_is_match(buf1, rule) == true

        // 2. Durum: Sadece $hex1 mevcut -> Eslesmeli
        let buf2 = "Binary header:" + hex_decode("909090cc") + ":code"
        verify yara_rule_is_match(buf2, rule) == true

        // 3. Durum: Hicbiri yok -> Eslesmemeli
        let buf3 = "Completely clean benign payload"
        verify yara_rule_is_match(buf3, rule) == false

        print("YARA_ANY_OF_THEM_OK")
        return 0
    }
    '''
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Stderr: {err}"
    assert "YARA_ANY_OF_THEM_OK" in out


def test_yara_condition_n_of_them():
    """Çoklu imza eşik testi: condition: '2 of them'."""
    code = '''
    import "std:security:yara"
    import "std:encoding:hex"

    fn main() -> int {
        let mut rule = yara_rule_new("APT_Threshold_Check", "2 of them")
        rule = yara_rule_add_pattern(rule, "$p1", "str:BEACON_CONFIG")
        rule = yara_rule_add_pattern(rule, "$p2", "str:PIPE_COMMUNICATION")
        rule = yara_rule_add_pattern(rule, "$p3", "48 89 ?? 55")

        // 1 desen var -> Basarisiz olmali (< 2)
        let buf1 = "Buffer contains BEACON_CONFIG only"
        verify yara_rule_is_match(buf1, rule) == false

        // 2 desen var ($p1 ve $p2) -> Basarili olmali
        let buf2 = "BEACON_CONFIG activated via PIPE_COMMUNICATION"
        verify yara_rule_is_match(buf2, rule) == true

        // 3 desenin hepsi var -> Basarili olmali (>= 2)
        let buf3 = "BEACON_CONFIG + PIPE_COMMUNICATION + " + hex_decode("4889ff55")
        verify yara_rule_is_match(buf3, rule) == true

        print("YARA_N_OF_THEM_OK")
        return 0
    }
    '''
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Stderr: {err}"
    assert "YARA_N_OF_THEM_OK" in out


def test_yara_ruleset_multi_rule():
    """YaraRuleSet veri yapısı ile çoklu kural tarama testi."""
    code = '''
    import "std:security:yara"
    import "std:encoding:hex"

    fn main() -> int {
        let mut rset = yara_ruleset_new()

        let mut r_trojan = yara_rule_new("Trojan_Downloader", "any")
        r_trojan = yara_rule_add_pattern(r_trojan, "$t1", "str:powershell -enc")
        rset = yara_ruleset_add_rule(rset, r_trojan)

        let mut r_exploit = yara_rule_new("Exploit_NOP_Sled", "all")
        r_exploit = yara_rule_add_pattern(r_exploit, "$nops", "90 90 90 90")
        rset = yara_ruleset_add_rule(rset, r_exploit)

        let mut r_ransom = yara_rule_new("Ransomware_Note", "all")
        r_ransom = yara_rule_add_pattern(r_ransom, "$r1", "str:YOUR_FILES_ARE_ENCRYPTED")
        rset = yara_ruleset_add_rule(rset, r_ransom)

        // Hedef tampon sadece Trojan ve Exploit barindiriyor
        let sample = "Cmd: powershell -enc aabbcc shellcode: " + hex_decode("90909090cc") + " finish"
        let matches = yara_ruleset_scan(sample, rset)

        // 2 adet kural eslesmeli (Trojan_Downloader ve Exploit_NOP_Sled)
        verify len(matches) == 2
        verify matches[0].rule_name == "Trojan_Downloader"
        verify matches[1].rule_name == "Exploit_NOP_Sled"

        let total = yara_ruleset_count_matches(sample, rset)
        verify total == 2

        print("YARA_RULESET_OK: matched_count=", total)
        return 0
    }
    '''
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Stderr: {err}"
    assert "YARA_RULESET_OK" in out


def test_yara_hex_stream_scanning():
    """Hex stream biçimindeki hedef üzerinde wildcard arama."""
    code = '''
    import "std:security:yara"

    fn main() -> int {
        // 48 89 00 55 aa 8b baytlarinin hex karsiligi
        let hex_stream = "48890055aa8b"
        let pat = "48 89 ?? 55 ?? 8b"

        let ok = yara_scan_hex_stream(hex_stream, pat)
        verify ok == true

        let off = yara_find_hex_stream(hex_stream, pat)
        verify off == 0

        let bad_stream = "48890011aa8b"
        let bad_ok = yara_scan_hex_stream(bad_stream, pat)
        verify bad_ok == false

        print("YARA_HEX_STREAM_OK")
        return 0
    }
    '''
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Stderr: {err}"
    assert "YARA_HEX_STREAM_OK" in out
