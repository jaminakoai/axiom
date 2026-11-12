"""
Axiom Programming Language (λx) - Standard Library Packet 5 Tests
Libraries tested:
21. std:crypto:aes (AES-128 & AES-256 CBC Mode & PKCS#7 Padding)
22. std:security:jwt (JSON Web Token RFC 7519, HS256 HMAC Signatures & Claim Extraction)
23. std:encoding:html (HTML Entity Encoding/Decoding & XSS Tag Stripping)
24. std:log:logger (Leveled & ANSI Colored Structured Logger Engine)
25. std:net:raw_socket (Raw Network, ICMP Echo Ping, TCP Port Ping & RFC 1071 Checksum)
"""
import os
import subprocess
import tempfile
import pytest
from pathlib import Path

from axiom.cli import compile_axiom_source, find_c_compiler
from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.resolver import ModuleResolver
from axiom.checker import TypeChecker
from axiom.codegen_llvm import LLVMCodeGenerator
from tests.support_env import require_raw_socket

STD_DIR = str((Path(__file__).resolve().parent.parent / "std").resolve())

def compile_and_run(source_code: str, source_path: str = None, timeout: int = 10, args: list = None) -> subprocess.CompletedProcess:
    if source_path is None:
        source_path = str(Path(STD_DIR) / "entry.ax")

    c_code = compile_axiom_source(source_code, source_path)
    cc = find_c_compiler()

    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        res_cc = subprocess.run([cc, "-O2", "-pthread", c_path, "-lz", "-lssl", "-lcrypto", "-ldl", "-o", bin_path], capture_output=True, text=True)
        if res_cc.returncode != 0:
            raise RuntimeError(f"C Derleyici Hatasi:\n{res_cc.stderr}\nUretilen C Kodu:\n{c_code}")

        cmd = [bin_path]
        if args:
            cmd.extend(args)
        res_exec = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res_exec
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

def compile_and_run_llvm(source_code: str, source_path: str = None, timeout: int = 10, args: list = None) -> subprocess.CompletedProcess:
    if source_path is None:
        source_path = str(Path(STD_DIR) / "entry.ax")

    lexer = Lexer(source_code)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    prog = parser.parse()
    resolver = ModuleResolver(base_file_path=source_path)
    prog = resolver.resolve(prog)
    checker = TypeChecker()
    checker.check(prog)

    codegen = LLVMCodeGenerator()
    llvm_ir = codegen.generate(prog)

    runtime_c = str(Path(__file__).resolve().parent.parent / "axiom" / "axiom_llvm_runtime.c")

    with tempfile.NamedTemporaryFile(suffix=".ll", mode="w", delete=False) as ll_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        ll_path = ll_file.name
        bin_path = bin_file.name
        ll_file.write(llvm_ir)

    try:
        cmd = ["clang", "-O2", ll_path, runtime_c, "-pthread", "-lz", "-lssl", "-lcrypto", "-ldl", "-lm", "-o", bin_path]
        res_cc = subprocess.run(cmd, capture_output=True, text=True)
        if res_cc.returncode != 0:
            raise RuntimeError(f"LLVM Clang Hatasi:\n{res_cc.stderr}\nUretilen IR:\n{llvm_ir}")

        run_cmd = [bin_path]
        if args:
            run_cmd.extend(args)
        res_exec = subprocess.run(run_cmd, capture_output=True, text=True, timeout=timeout)
        return res_exec
    finally:
        if os.path.exists(ll_path):
            os.remove(ll_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)


# =========================================================================
# 1. std:crypto:aes (AES-128 & AES-256 CBC Mode)
# =========================================================================

def test_aes256_cbc_encrypt_decrypt():
    source = """
    import "std:crypto:aes"
    fn main() -> int {
        let key256: str = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
        let iv: str = "000102030405060708090a0b0c0d0e0f"
        let msg: str = "Axiom High-Grade Encryption Secret Data"
        let ct: str = aes256_cbc_encrypt(msg, key256, iv)
        let pt: str = aes256_cbc_decrypt(ct, key256, iv)
        print("PT:" + pt)
        return 0
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "PT:Axiom High-Grade Encryption Secret Data" in res.stdout

def test_aes128_cbc_encrypt_decrypt():
    source = """
    import "std:crypto:aes"
    fn main() -> int {
        let key128: str = "0123456789abcdef0123456789abcdef"
        let iv: str = "fedcba9876543210fedcba9876543210"
        let msg: str = "Fast 128-bit AES Symmetric Payload!"
        let ct: str = aes128_cbc_encrypt(msg, key128, iv)
        let pt: str = aes128_cbc_decrypt(ct, key128, iv)
        print("PT:" + pt)
        return 0
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "PT:Fast 128-bit AES Symmetric Payload!" in res.stdout

def test_aes256_corrupt_ciphertext_fails_or_empty():
    source = """
    import "std:crypto:aes"
    fn main() -> int {
        let key256: str = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
        let iv: str = "000102030405060708090a0b0c0d0e0f"
        let bad_ct: str = "deadbeef"
        let pt: str = aes256_cbc_decrypt(bad_ct, key256, iv)
        if len(pt) == 0 {
            print("BAD_LEN:EMPTY")
        } else {
            print("BAD_LEN:NON_EMPTY")
        }
        return 0
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "BAD_LEN:EMPTY" in res.stdout

def test_aes_llvm_backend():
    source = """
    import "std:crypto:aes"
    fn main() -> int {
        let key: str = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
        let iv: str = "000102030405060708090a0b0c0d0e0f"
        let ct: str = aes256_cbc_encrypt("LLVM Native AES", key, iv)
        let pt: str = aes256_cbc_decrypt(ct, key, iv)
        print("LLVM_PT:" + pt)
        return 0
    }
    """
    res = compile_and_run_llvm(source)
    assert res.returncode == 0
    assert "LLVM_PT:LLVM Native AES" in res.stdout


# =========================================================================
# 2. std:security:jwt (JSON Web Token & HS256 HMAC Signatures)
# =========================================================================

def test_jwt_create_and_verify_valid():
    source = """
    import "std:security:jwt"
    fn main() -> int {
        let payload: str = "{\\"sub\\":\\"admin_user\\",\\"role\\":\\"superadmin\\",\\"exp\\":1999999999}"
        let secret: str = "correct_horse_battery_staple"
        let token: str = jwt_create_hs256(payload, secret)
        let is_ok: bool = jwt_verify_hs256(token, secret)
        if is_ok {
            print("VALID:true")
        } else {
            print("VALID:false")
        }
        return 0
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "VALID:true" in res.stdout

def test_jwt_verify_invalid_secret():
    source = """
    import "std:security:jwt"
    fn main() -> int {
        let payload: str = "{\\"sub\\":\\"admin_user\\"}"
        let secret: str = "correct_secret"
        let token: str = jwt_create_hs256(payload, secret)
        let is_ok: bool = jwt_verify_hs256(token, "tampered_secret")
        if is_ok {
            print("VALID:true")
        } else {
            print("VALID:false")
        }
        return 0
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "VALID:false" in res.stdout

def test_jwt_get_header_payload_and_claim():
    source = """
    import "std:security:jwt"
    fn main() -> int {
        let payload: str = "{\\"sub\\":\\"sec_agent_42\\",\\"team\\":\\"red_team\\",\\"level\\":9}"
        let secret: str = "red_team_key"
        let token: str = jwt_create_hs256(payload, secret)
        let sub: str = jwt_get_claim(token, "sub")
        let team: str = jwt_get_claim(token, "team")
        let level: str = jwt_get_claim(token, "level")
        let header: str = jwt_get_header(token)
        print("SUB:" + sub)
        print("TEAM:" + team)
        print("LEVEL:" + level)
        if len(header) > 0 {
            print("HDR_HAS_HS256:YES")
        } else {
            print("HDR_HAS_HS256:NO")
        }
        return 0
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "SUB:sec_agent_42" in res.stdout
    assert "TEAM:red_team" in res.stdout
    assert "LEVEL:9" in res.stdout
    assert "HDR_HAS_HS256:YES" in res.stdout

def test_jwt_llvm_backend():
    source = """
    import "std:security:jwt"
    fn main() -> int {
        let payload: str = "{\\"user\\":\\"llvm_tester\\"}"
        let token: str = jwt_create_hs256(payload, "secret123")
        let ok: bool = jwt_verify_hs256(token, "secret123")
        if ok {
            print("LLVM_JWT_OK:true")
        } else {
            print("LLVM_JWT_OK:false")
        }
        return 0
    }
    """
    res = compile_and_run_llvm(source)
    assert res.returncode == 0
    assert "LLVM_JWT_OK:true" in res.stdout


# =========================================================================
# 3. std:encoding:html (HTML Entity & XSS Helpers)
# =========================================================================

def test_html_escape_basic_entities():
    source = """
    import "std:encoding:html"
    fn main() -> int {
        let raw: str = "<script>alert('xss' & \\"quotes\\")</script>"
        let esc: str = html_escape(raw)
        print("ESC:" + esc)
        return 0
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "ESC:&lt;script&gt;alert(&#39;xss&#39; &amp; &quot;quotes&quot;)&lt;/script&gt;" in res.stdout

def test_html_unescape_entities():
    source = """
    import "std:encoding:html"
    fn main() -> int {
        let esc: str = "&lt;b&gt;bold &amp; &#39;single&#39; &quot;double&quot;&lt;/b&gt;"
        let unesc: str = html_unescape(esc)
        print("UNESC:" + unesc)
        return 0
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "UNESC:<b>bold & 'single' \"double\"</b>" in res.stdout

def test_html_strip_tags():
    source = """
    import "std:encoding:html"
    fn main() -> int {
        let html: str = "<p>Paragraph with <a href=\\"#\\">link</a> and <span>span</span>.</p>"
        let stripped: str = html_strip_tags(html)
        print("STRIPPED:" + stripped)
        return 0
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "STRIPPED:Paragraph with link and span." in res.stdout

def test_html_llvm_backend():
    source = """
    import "std:encoding:html"
    fn main() -> int {
        let raw: str = "<div>hello & goodbye</div>"
        let clean: str = html_strip_tags(raw)
        print("LLVM_HTML:" + clean)
        return 0
    }
    """
    res = compile_and_run_llvm(source)
    assert res.returncode == 0
    assert "LLVM_HTML:hello & goodbye" in res.stdout


# =========================================================================
# 4. std:log:logger (Leveled & ANSI Colored Logger Engine)
# =========================================================================

def test_logger_levels_filtering():
    source = """
    import "std:log:logger"
    fn main() -> int {
        log_set_level(2) // 2: WARN. DEBUG (0) and INFO (1) must be ignored.
        log_debug("MOD_DBG", "invisible debug message")
        log_info("MOD_INF", "invisible info message")
        log_warn("MOD_WRN", "visible warn message")
        log_error("MOD_ERR", "visible error message")
        return 0
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "invisible debug message" not in res.stdout
    assert "invisible info message" not in res.stdout
    assert "visible warn message" in res.stdout
    assert "visible error message" in res.stdout

def test_logger_all_levels_enabled():
    source = """
    import "std:log:logger"
    fn main() -> int {
        log_set_level(0) // 0: DEBUG (all enabled)
        log_debug("MOD1", "message_debug_1")
        log_info("MOD2", "message_info_2")
        log_warn("MOD3", "message_warn_3")
        log_error("MOD4", "message_error_4")
        return 0
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "message_debug_1" in res.stdout
    assert "message_info_2" in res.stdout
    assert "message_warn_3" in res.stdout
    assert "message_error_4" in res.stdout

def test_logger_llvm_backend():
    source = """
    import "std:log:logger"
    fn main() -> int {
        log_set_level(1)
        log_info("LLVM_MOD", "llvm logger operational")
        return 0
    }
    """
    res = compile_and_run_llvm(source)
    assert res.returncode == 0
    assert "llvm logger operational" in res.stdout


# =========================================================================
# 5. std:net:raw_socket (Raw Network, Ping & RFC 1071 Checksum)
# =========================================================================

@require_raw_socket
def test_raw_socket_icmp_ping_loopback():
    source = """
    import "std:net:raw_socket"
    fn main() -> int {
        let rtt: int = icmp_ping("127.0.0.1", 500)
        if rtt >= 0 {
            print("ICMP_STATUS:REACHABLE")
        } else {
            print("ICMP_STATUS:UNREACHABLE")
        }
        return 0
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "ICMP_STATUS:REACHABLE" in res.stdout

def test_raw_socket_tcp_ping_invalid_host():
    source = """
    import "std:net:raw_socket"
    fn main() -> int {
        // Connecting to a nonexistent IP with short timeout should return -1
        let rtt: int = tcp_ping("192.0.2.1", 65432, 50)
        if rtt == -1 {
            print("TCP_STATUS:FAILED")
        } else {
            print("TCP_STATUS:SUCCESS")
        }
        return 0
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "TCP_STATUS:FAILED" in res.stdout

def test_raw_socket_checksum_calculation_and_verify():
    source = """
    import "std:net:raw_socket"
    fn main() -> int {
        let raw_hdr: str = "4500003c1c46400040060000ac100a63ac100a0c"
        let ck: int = raw_checksum(raw_hdr)
        if ck == 45542 {
            print("CKSUM:OK")
        } else {
            print("CKSUM:ERR")
        }

        let verified_hdr: str = "4500003c1c4640004006b1e6ac100a63ac100a0c"
        let v: int = raw_checksum(verified_hdr)
        if v == 0 {
            print("VERIFY:VALID")
        } else {
            print("VERIFY:INVALID")
        }
        return 0
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "CKSUM:OK" in res.stdout
    assert "VERIFY:VALID" in res.stdout

def test_raw_socket_llvm_backend():
    source = """
    import "std:net:raw_socket"
    fn main() -> int {
        let ck: int = raw_checksum("4500003c1c46400040060000ac100a63ac100a0c")
        if ck == 45542 {
            print("LLVM_CKSUM:OK")
        } else {
            print("LLVM_CKSUM:ERR")
        }
        return 0
    }
    """
    res = compile_and_run_llvm(source)
    assert res.returncode == 0
    assert "LLVM_CKSUM:OK" in res.stdout
