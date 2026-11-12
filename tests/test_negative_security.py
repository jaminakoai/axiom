"""
Axiom Programming Language (λx) - Negative Security and Exploit Test Suite (FAZ 7.3)
Verifies that malicious patterns, memory corruption attempts, type confusions,
missing returns, bounds violations, and TLS MitM attacks are strictly prevented.
"""
import os
import subprocess
import tempfile
import socket
import ssl
import threading
import time
from pathlib import Path
import pytest

from axiom.cli import compile_axiom_source, find_c_compiler
from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.checker import TypeChecker, SemanticError
from axiom.prover import SymbolicProver, ProofError
from axiom.z3_prover import Z3Prover

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def run_compiled_axiom(source: str, asan: bool = False):
    c_code = compile_axiom_source(source, prove=False)
    cc = find_c_compiler()

    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_f, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_f:
        c_path = c_f.name
        bin_path = bin_f.name
        c_f.write(c_code)

    flags = [cc, "-O1", "-pthread", c_path, "-o", bin_path, "-lm", "-lz", "-lssl", "-lcrypto", "-ldl"]
    if asan:
        flags.extend(["-fsanitize=address,undefined", "-g", "-fno-omit-frame-pointer"])

    try:
        res_cc = subprocess.run(flags, capture_output=True, text=True)
        if res_cc.returncode != 0:
            raise RuntimeError(f"C Derleme Hatasi:\n{res_cc.stderr}\nKod:\n{c_code}")
        res_exec = subprocess.run([bin_path], capture_output=True, text=True)
        return res_exec
    finally:
        if os.path.exists(c_path): os.remove(c_path)
        if os.path.exists(bin_path): os.remove(bin_path)


# 1. Dizi Sınır Aşımı (OOB) İstismarı
def test_negative_security_oob_upper_bound():
    """Verify out-of-bounds array access exits with code 102 via axiom_bounds_check."""
    source = """
    fn main() -> int {
        let arr = [10, 20, 30];
        let exploit_val = arr[5]; // Out of bounds
        return exploit_val;
    }
    """
    res = run_compiled_axiom(source)
    assert res.returncode == 102, f"OOB hatasi 102 ile yakalanmaliydi, alinan kod: {res.returncode}"
    assert "AXIOM BOUNDS FAULT" in res.stderr or "bounds_check" in res.stderr or res.returncode == 102


def test_negative_security_oob_negative_index():
    """Verify negative index access exits with code 102 via axiom_bounds_check."""
    source = """
    fn main() -> int {
        let arr = [1, 2, 3];
        let exploit_val = arr[-1]; // Negative index
        return exploit_val;
    }
    """
    res = run_compiled_axiom(source)
    assert res.returncode == 102, f"Negatif indeks 102 ile yakalanmaliydi, alinan kod: {res.returncode}"


# 2. Tip Karışıklığı (Type Confusion) İstismarı
def test_negative_security_type_confusion_int_and_str():
    """Verify Type Checker rejects invalid comparison between int and str."""
    source = """
    fn main() -> int {
        let a = 10;
        let b = "malicious_string";
        if a < b {
            return 1;
        }
        return 0;
    }
    """
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    prog = parser.parse()
    checker = TypeChecker()
    with pytest.raises(SemanticError) as exc_info:
        checker.check(prog)
    assert "uyumsuz" in str(exc_info.value).lower() or "tip" in str(exc_info.value).lower() or "type" in str(exc_info.value).lower()


def test_negative_security_type_confusion_assignment():
    """Verify Type Checker rejects assigning str to int variable."""
    source = """
    fn main() -> int {
        let mut x: int = 100;
        x = "corrupted_ptr";
        return x;
    }
    """
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    prog = parser.parse()
    checker = TypeChecker()
    with pytest.raises(SemanticError):
        checker.check(prog)


# 3. Eksik Return Açığı (Missing Return Detection)
def test_negative_security_missing_return_in_function():
    """Verify Type Checker rejects non-void function with missing return statement in branches."""
    source = """
    fn dangerous_func(x: int) -> int {
        if x > 0 {
            return 1;
        }
        // Eksik return: else dali veya fonksiyon sonu dondurmuyor!
    }

    fn main() -> int {
        return dangerous_func(5);
    }
    """
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    prog = parser.parse()
    checker = TypeChecker()
    with pytest.raises(SemanticError) as exc_info:
        checker.check(prog)
    assert "return" in str(exc_info.value).lower()


# 4. ASan ile Bellek Güvenliği (Double-Free ve UAF Koruma Garantisi)
def test_negative_security_asan_tensor_double_free_protection():
    """Verify tensor_free prevents double-free corruption via NULL pointer clearing."""
    source = """
    fn main() -> int {
        let t = tensor_create_2d(4, 4);
        tensor_free(t);
        tensor_free(t); // Double free attempt
        print("DOUBLE_FREE_PROTECTED");
        return 0;
    }
    """
    # ASan altında çalıştır: ASan crash olmamalı, runtime güvenli no-op yapmalı
    res = run_compiled_axiom(source, asan=True)
    assert res.returncode == 0
    assert "DOUBLE_FREE_PROTECTED" in res.stdout


def test_negative_security_asan_safe_string_cleanup():
    """Verify safe cleanup of dynamic memory and double-free protection under AddressSanitizer."""
    runtime_h = PROJECT_ROOT / "axiom" / "runtime.h"
    c_source = f"""
    #include "{runtime_h}"
    #include <assert.h>
    #include <stdio.h>

    int main() {{
        // 1. Dinamik metin oluşturma ve serbest bırakma
        char* str1 = axiom_safe_strdup("Zero Leak String Under ASan");
        assert(str1 != NULL);
        axiom_str_free(str1);

        // 2. Double-free koruması
        void* heap_buf = malloc(256);
        assert(heap_buf != NULL);
        axiom_safe_free(heap_buf);
        assert(heap_buf == NULL);
        axiom_safe_free(heap_buf); // İkinci çağrı crash yapmamalı

        printf("ASAN_ZERO_LEAK_CONFIRMED\\n");
        return 0;
    }}
    """
    cc = find_c_compiler()
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_f, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_f:
        c_path = c_f.name
        bin_path = bin_f.name
        c_f.write(c_source)

    try:
        flags = [cc, "-O1", "-fsanitize=address,undefined", "-g", "-fno-omit-frame-pointer", "-pthread", c_path, "-o", bin_path, "-lm", "-lz", "-lssl", "-lcrypto"]
        res_comp = subprocess.run(flags, capture_output=True, text=True)
        assert res_comp.returncode == 0, f"ASan derleme hatasi: {res_comp.stderr}"

        env = os.environ.copy()
        env["ASAN_OPTIONS"] = "detect_leaks=1:abort_on_error=1"
        res_exec = subprocess.run([bin_path], capture_output=True, text=True, env=env)
        assert res_exec.returncode == 0, f"ASan calisma hatasi: {res_exec.stderr}"
        assert "ASAN_ZERO_LEAK_CONFIRMED" in res_exec.stdout
    finally:
        if os.path.exists(c_path): os.remove(c_path)
        if os.path.exists(bin_path): os.remove(bin_path)


# 5. TLS Sertifika Sahteciliği / MitM Denemesi
def test_negative_security_tls_mitm_rejection():
    """Verify TLS client rejects connection to an untrusted or self-signed server without valid CA."""
    cert_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    key_file = tempfile.NamedTemporaryFile(suffix=".key", delete=False)
    cert_path = cert_file.name
    key_path = key_file.name
    cert_file.close()
    key_file.close()

    try:
        gen_cmd = f"openssl req -x509 -newkey rsa:2048 -keyout {key_path} -out {cert_path} -days 1 -nodes -subj '/CN=fake-mitm-domain.com'"
        subprocess.run(gen_cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('127.0.0.1', 0))
        server_socket.listen(1)
        port = server_socket.getsockname()[1]

        def run_server():
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            try:
                server_socket.settimeout(3.0)
                conn, _ = server_socket.accept()
                with context.wrap_socket(conn, server_side=True) as ssl_conn:
                    ssl_conn.sendall(b"UNTRUSTED MITM RESPONSE")
            except Exception:
                pass
            finally:
                server_socket.close()

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        time.sleep(0.2)

        # Axiom TLS baglantisi: Sahte sertifika sunucusuna baglanmaya calisildiginda baglanti reddedilmeli
        axiom_tls_client = f"""
        import "std:crypto:tls";

        fn main() -> int {{
            let fd = tls_connect("127.0.0.1", {port});
            if fd < 0 {{
                print("TLS_MITM_REJECTED_SUCCESSFULLY");
                return 0;
            }}
            print("TLS_MITM_ACCEPTED_VULNERABLE");
            tls_close(fd);
            return 1;
        }}
        """
        res = run_compiled_axiom(axiom_tls_client)
        assert res.returncode == 0
        assert "TLS_MITM_REJECTED_SUCCESSFULLY" in res.stdout
    finally:
        if os.path.exists(cert_path): os.remove(cert_path)
        if os.path.exists(key_path): os.remove(key_path)


# 6. P0.1: bin/axiomc Komut Enjeksiyonu Koruması
def test_negative_security_p0_1_axiomc_command_injection_prevention():
    """Verify bin/axiomc rejects malicious filenames and prevents shell command injection."""
    axiomc_bin = PROJECT_ROOT / "bin" / "axiomc"
    assert axiomc_bin.exists(), f"bin/axiomc bulunamadi: {axiomc_bin}"

    test_ax = PROJECT_ROOT / "examples" / "01_hello.ax"
    assert test_ax.exists()

    injected_marker = Path("/tmp/INJECTED")
    if injected_marker.exists():
        injected_marker.unlink()

    exploit_out = "/tmp/pwned; touch /tmp/INJECTED"
    res = subprocess.run([str(axiomc_bin), "build", str(test_ax), "-o", exploit_out], capture_output=True, text=True)

    assert res.returncode != 0, f"Komut enjeksiyonu girisimi reddedilmeliydi! returncode={res.returncode}"
    assert not injected_marker.exists(), "KRITIK GUVENLIK ACIGI: /tmp/INJECTED dosyasi olusturuldu! Komut enjeksiyonu engellenemedi!"
    assert "guvensiz" in res.stdout.lower() or "guvensiz" in res.stderr.lower() or res.returncode == 1


# 7. P0.2: Aritmetik Güvenlik ve Sıfıra Bölme Koruması
def test_negative_security_p0_2_arithmetic_zero_division_protection():
    """Verify division and modulo by zero trigger axiom_contract_fail with exit code 101 instead of UB/SIGFPE."""
    # 7.1 Değişken sıfıra bölme
    src_var_div = """
    fn main() -> int {
        let a = 100;
        let b = 0;
        return a / b;
    }
    """
    res1 = run_compiled_axiom(src_var_div)
    assert res1.returncode == 101, f"Degisken sifira bolme 101 ile durdurulmaliydi, alinan: {res1.returncode}"
    assert "ARITHMETIC_ZERO_DIV" in res1.stderr

    # 7.2 Sabit sıfıra bölme
    src_const_div = """
    fn main() -> int {
        return 10 / 0;
    }
    """
    res2 = run_compiled_axiom(src_const_div)
    assert res2.returncode == 101, f"Sabit sifira bolme 101 ile durdurulmaliydi, alinan: {res2.returncode}"
    assert "ARITHMETIC_ZERO_DIV" in res2.stderr

    # 7.3 Modulo sıfıra bölme
    src_mod = """
    fn main() -> int {
        let x = 42;
        let y = 0;
        return x % y;
    }
    """
    res3 = run_compiled_axiom(src_mod)
    assert res3.returncode == 101, f"Modulo sifira bolme 101 ile durdurulmaliydi, alinan: {res3.returncode}"
    assert "ARITHMETIC_ZERO_DIV" in res3.stderr


# 8. P0.3: Doğrulama Motoru Sesliliği & PrintStmt Açığı
def test_negative_security_p0_3_print_stmt_prover_soundness():
    """Verify that PrintStmt expressions and contracts are verified by both provers and axiom check."""
    src = """
    fn check_port(port: int) -> bool
    requires port >= 1 and port <= 65535
    {
        return true;
    }

    fn main() -> int {
        print(check_port(99999));
        return 0;
    }
    """
    tokens = Lexer(src).tokenize()
    prog = Parser(tokens).parse()
    TypeChecker().check(prog)

    # 1. SymbolicProver ihlali yakalamalı
    sym_prover = SymbolicProver()
    with pytest.raises(ProofError) as sym_exc:
        sym_prover.verify_program(prog)
    assert "check_port" in str(sym_exc.value)

    # 2. Z3Prover ihlali yakalamalı
    z3_prover = Z3Prover()
    with pytest.raises(ProofError) as z3_exc:
        z3_prover.verify_program(prog)
    assert "check_port" in str(z3_exc.value)

    # 3. axiom check varsayılan olarak ihlali yakalamalı
    with tempfile.NamedTemporaryFile(suffix=".ax", mode="w", delete=False) as f:
        f.write(src)
        temp_ax = f.name
    try:
        res_check = subprocess.run(["python3", "-m", "axiom.cli", "check", temp_ax], capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        assert res_check.returncode == 1, f"axiom check sozlesme ihlalinde basarisiz olmaliydi: {res_check.stdout} {res_check.stderr}"

        # 4. --no-prove bayrağı ile doğrulama atlanabilmeli
        res_noprove = subprocess.run(["python3", "-m", "axiom.cli", "check", "--no-prove", temp_ax], capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        assert res_noprove.returncode == 0, f"axiom check --no-prove basarili olmaliydi: {res_noprove.stderr}"
    finally:
        if os.path.exists(temp_ax):
            os.remove(temp_ax)


# 9. P0.4: Bellek Modeli Güvenliği & str_free Literal Koruması
def test_negative_security_p0_4_str_free_literal_protection_under_asan():
    """Verify str_free on string literals safely no-ops without crash or invalid pointer under ASan."""
    src = """
    fn main() -> int {
        str_free("literal text in rodata");
        str_free("another literal");
        let d = "dynamic_" + "string";
        str_free(d);
        print("LITERAL_STR_FREE_NOOP_CONFIRMED");
        return 0;
    }
    """
    res = run_compiled_axiom(src, asan=True)
    assert res.returncode == 0, f"ASan altinda str_free(\"literal\") cokmemeliydi! Hata:\n{res.stderr}"
    assert "LITERAL_STR_FREE_NOOP_CONFIRMED" in res.stdout
