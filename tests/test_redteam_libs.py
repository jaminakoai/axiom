"""
Axiom Programming Language (λx) - Phase 2 Red Team & Offensive Security Tests

==============================================================================
YASAL VE ETİK UYARI / LEGAL & ETHICAL DISCLAIMER:
YALNIZCA YASAL İZİNLİ VE ETİK TEST ORTAMLARINDA KULLANIM İÇİNDİR.
YETKİSİZ SİSTEMLERDE KULLANIMI YASALARA AYKIRIDIR.
==============================================================================
Bu test suiti yalnizca kontrollu ve izole test ortamlarinda ofansif guvenlik
modullerinin davranisini teyit etmek uzere calistirilmalidir.
"""
import pytest
import subprocess
import tempfile
import os
from pathlib import Path

# Ortam kontrolü: ofansif testler yalnızca açık onayla çalışır.
# Varsayılan `pytest` çalıştırmasında atlanır (kod çalıştırır).
#   AXIOM_SKIP_REDTEAM=1 python3 -m pytest -q tests/test_redteam_libs.py
# Ofansif testler artik VARSAYILAN olarak calisir: yalnizca bu surecte
# (fork/exec ile) sentetik shellcode calistirilir, disariya trafik gitmez.
# Izole olmayan ortamlarda AXIOM_SKIP_REDTEAM=1 ile atlanabilir.
if os.environ.get("AXIOM_SKIP_REDTEAM") == "1":
    pytest.skip(
        "AXIOM_SKIP_REDTEAM=1: ofansif testler atlandi.",
        allow_module_level=True,
    )

from axiom.cli import compile_axiom_source, find_c_compiler
from axiom.checker import SemanticError

def run_axiom_code(code_str: str, features: list[str] | None = None) -> tuple[int, str, str]:
    # Ofansif testler yalnizca acikca izin verilen features=["offensive"] ile derlenir
    active_features = features if features is not None else ["offensive"]
    c_code = compile_axiom_source(code_str, features=active_features)
    cc = find_c_compiler()
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        cmd = [cc, "-O3", "-Wall", c_path, "-o", bin_path, "-lssl", "-lcrypto", "-lz", "-ldl", "-pthread"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"C derleme hatasi:\n{res.stderr}"

        run_res = subprocess.run([bin_path], capture_output=True, text=True, timeout=15)
        return run_res.returncode, run_res.stdout, run_res.stderr
    finally:
        if os.path.exists(c_path): os.remove(c_path)
        if os.path.exists(bin_path): os.remove(bin_path)

def test_offensive_modules_rejected_without_feature_flag():
    """Bayraksiz cagrilarda ofansif modullerin derleme aninda kesin olarak reddedildigini dogrular."""
    code = 'import "std:security:shellcode"\nfn main() -> int { return 0; }'
    with pytest.raises(SemanticError) as excinfo:
        compile_axiom_source(code, features=[])
    err = str(excinfo.value)
    assert "ofansif güvenlik modülüdür" in err
    assert "--features offensive" in err

def test_shellcode_exec():
    code = '''
    import "std:security:shellcode"
    fn main() -> int {
        // mov eax, 77; ret
        let ret_code = shellcode_execute("b84d000000c3")
        verify ret_code == 77
        print("SHELLCODE_OK:", ret_code)
        return 0
    }
    '''
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "SHELLCODE_OK: 77" in out

def test_packet_crafting():
    code = '''
    import "std:net:packet_crafter"
    fn main() -> int {
        let ip = craft_ipv4_header("127.0.0.1", "127.0.0.1", 6, 20)
        verify len(ip) == 40
        let tcp = craft_tcp_syn("127.0.0.1", "127.0.0.1", 1234, 80)
        verify len(tcp) == 40
        let udp = craft_udp_packet(53, 53, "DNS_TEST")
        verify len(udp) >= 16
        print("PACKETS_CRAFTED_OK")
        return 0
    }
    '''
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "PACKETS_CRAFTED_OK" in out

def test_evasion_diagnostics():
    code = '''
    import "std:security:evasion"
    fn main() -> int {
        let is_dbg = evasion_is_debugger_present()
        let is_vm = evasion_is_vm_or_sandbox()
        evasion_disable_core_dump()
        evasion_enable_core_dump()
        print("EVASION_OK")
        return 0
    }
    '''
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "EVASION_OK" in out

def test_c2_beaconing():
    code = '''
    import "std:net:c2"
    fn main() -> int {
        let agent = "NODE_TEST_42"
        let secret = "super_secure_c2_secret_key_12345"
        let payload = "TASK:EXFILTRATE"
        let beacon = c2_generate_beacon(agent, secret, payload)
        verify len(beacon) > 20
        let parsed = c2_parse_beacon(beacon, secret)
        verify parsed == payload
        print("C2_BEACON_OK:", parsed)
        return 0
    }
    '''
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "C2_BEACON_OK: TASK:EXFILTRATE" in out

def test_memdump_pattern_search():
    code = '''
    import "std:security:memdump"
    import "std:os:process"
    fn main() -> int {
        let pid = process_get_pid()
        let marker = "FIND_ME_IN_RAM_TEST_MARKER_99"
        let count = memdump_search_pattern(pid, marker)
        verify count >= 1
        print("MEMDUMP_OK:", count)
        return 0
    }
    '''
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "MEMDUMP_OK:" in out
    count_val = int(out.split("MEMDUMP_OK:")[1].strip())
    assert count_val >= 1

def test_redteam_full_e2e_example():
    ex_path = Path(__file__).resolve().parent.parent / "examples/15_redteam_offensive_suite.ax"
    assert ex_path.exists()
    source = ex_path.read_text(encoding="utf-8")
    ret, out, _ = run_axiom_code(source)
    assert ret == 0
    assert "TUM FAZ 2 RED TEAM GUVENLIK MODULLERI BASARIYLA DOGRULANDI" in out
