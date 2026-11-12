"""
Axiom Programming Language (λx) - Phase 3 Blue Team & DFIR Tests
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
        assert res.returncode == 0, f"C derleme hatasi:\n{res.stderr}"

        run_res = subprocess.run([bin_path], capture_output=True, text=True, timeout=15)
        return run_res.returncode, run_res.stdout, run_res.stderr
    finally:
        if os.path.exists(c_path): os.remove(c_path)
        if os.path.exists(bin_path): os.remove(bin_path)

def test_yara_scanner():
    code = '''
    import "std:security:yara"
    fn main() -> int {
        let sample = "BINARY_HEADER_START:MALWARE_SAMPLE_ABC:BINARY_END"
        let is_found = yara_scan_buffer(sample, "MALWARE_SAMPLE_ABC")
        verify is_found == true
        let not_found = yara_scan_buffer(sample, "BENIGN_SIGNATURE")
        verify not_found == false
        print("YARA_SCAN_OK")
        return 0
    }
    '''
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "YARA_SCAN_OK" in out

def test_pcap_io():
    code = '''
    import "std:net:pcap"
    fn main() -> int {
        let path = "/tmp/test_axiom_unit.pcap"
        let writer = pcap_open_writer(path)
        verify writer > 0
        let pkt = "aabbccddeeff0011223344550800450000140001000040007ce77f0000017f000001"
        let ok = pcap_record_packet(writer, pkt)
        verify ok == true
        pcap_file_close(writer)

        let reader = pcap_open_reader(path)
        verify reader > 0
        let read_pkt = pcap_read_next(reader)
        verify read_pkt == pkt
        pcap_file_close(reader)
        print("PCAP_IO_OK")
        return 0
    }
    '''
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "PCAP_IO_OK" in out

def test_sigma_rules():
    code = '''
    import "std:security:sigma"
    fn main() -> int {
        let log1 = "Failed password for root from 10.0.0.5"
        let t1 = sigma_detect_attack(log1)
        verify t1 == "SSH_BRUTE_FORCE"

        let log2 = "GET /v1/users?id=1%20UNION%20SELECT%20null,null HTTP/1.1"
        let t2 = sigma_detect_attack(log2)
        verify t2 == "SQL_INJECTION"

        let log3 = "Normal application request processing completed"
        let t3 = sigma_detect_attack(log3)
        verify t3 == "BENIGN"

        print("SIGMA_RULES_OK")
        return 0
    }
    '''
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "SIGMA_RULES_OK" in out

def test_forensics():
    code = '''
    import "std:os:forensics"
    fn main() -> int {
        let ports = forensics_list_listening_ports()
        // verify ports is a string
        verify len(ports) >= 0
        let mods = forensics_list_kernel_modules()
        verify len(mods) > 0
        print("FORENSICS_OK")
        return 0
    }
    '''
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "FORENSICS_OK" in out

def test_integrity_fim():
    code = '''
    import "std:security:integrity"
    fn main() -> int {
        let path = "/tmp/test_fim_check.txt"
        file_write(path, "SECURE_BASELINE_2026")
        let h = fim_calculate_hash(path)
        verify len(h) == 64
        let verified = fim_verify_baseline(path, h)
        verify verified == true
        print("INTEGRITY_OK")
        return 0
    }
    '''
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "INTEGRITY_OK" in out

def test_blueteam_full_e2e_example():
    ex_path = Path(__file__).resolve().parent.parent / "examples/16_blueteam_defensive_suite.ax"
    assert ex_path.exists()
    source = ex_path.read_text(encoding="utf-8")
    ret, out, _ = run_axiom_code(source)
    assert ret == 0
    assert "TUM FAZ 3 BLUE TEAM DEFANSIF MODULLERI BASARIYLA DOGRULANDI" in out
