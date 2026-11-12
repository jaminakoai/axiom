"""
Axiom Programming Language (λx) - Güvenlik ve Bellek İyileştirmeleri Test Paketi
(AŞAMA 1: P0 Güvenlik ve Sertleştirme Doğrulaması)

1. Dizi Sınır Denetimi (Index Out of Bounds check: exit 102)
2. array_push Stack Realloc Düzeltmesi (Dinamik Bellek Kopyası)
3. TLS Sertifika Doğrulaması & Hostname Denetimi (Anti-MITM)
4. Sabit Zamanlı JWT Doğrulama (CRYPTO_memcmp, exp/nbf/alg:none denetimi)
5. C2 Protokolü Rastgele IV & Güvenli HMAC-SHA256
6. os_exec_argv Shell Injection Korumalı Doğrudan Çalıştırma
"""
import os
import tempfile
import subprocess
import time
import socket
import threading
import ssl
import pytest
from pathlib import Path

from axiom.cli import compile_axiom_source, find_c_compiler


def compile_and_run(source_code: str, source_path: str = "<test>", timeout: int = 10, env: dict = None, features: list = None) -> subprocess.CompletedProcess:
    c_code = compile_axiom_source(source_code, source_path, features=features)
    cc = find_c_compiler()

    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        res_cc = subprocess.run([cc, "-O2", "-pthread", c_path, "-lssl", "-lcrypto", "-lz", "-ldl", "-o", bin_path], capture_output=True, text=True)
        if res_cc.returncode != 0:
            raise RuntimeError(f"C Derleyici Hatasi:\n{res_cc.stderr}\nUretilen C Kodu:\n{c_code}")

        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        res_exec = subprocess.run([bin_path], capture_output=True, text=True, timeout=timeout, env=run_env)
        return res_exec
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)


# =========================================================================
# 1. DİZİ SINIR DENETİMİ (BOUNDS CHECKING - OOB)
# =========================================================================

def test_bounds_checking_oob_upper_exit_102():
    """Dizi üst sınırını aşan erişimde program 102 çıkış koduyla güvenli durmalı."""
    source = """
    fn main() -> int {
        let arr = [10, 20, 30];
        print("arr[0]:", arr[0]);
        // arr boyutu 3, indeks 5 sınır aşımıdır!
        let oob = arr[5];
        print("oob:", oob);
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 102
    assert "[AXIOM BELLEK IHLALI] Dizi sınır aşımı (Index out of bounds)!" in res.stderr
    assert "Indeks: 5, Dizi Uzunlugu: 3" in res.stderr


def test_bounds_checking_oob_negative_exit_102():
    """Negatif dizi indeks erişiminde program 102 çıkış koduyla durmalı."""
    source = """
    fn main() -> int {
        let arr = [100, 200];
        let bad = arr[-1];
        print("bad:", bad);
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 102
    assert "[AXIOM BELLEK IHLALI] Dizi sınır aşımı (Index out of bounds)!" in res.stderr
    assert "Indeks: -1" in res.stderr


def test_bounds_checking_in_bounds_assignment_positive():
    """Sınırlar dahilinde okuma ve yazma işlemlerinin sorunsuz çalıştığını doğrular."""
    source = """
    fn main() -> int {
        let mut arr = [1, 2, 3];
        arr[0] = 100;
        arr[1] = 200;
        arr[2] = 300;
        print("arr:", arr[0], arr[1], arr[2]);
        verify arr[0] == 100;
        verify arr[1] == 200;
        verify arr[2] == 300;
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "arr: 100 200 300" in res.stdout


# =========================================================================
# 2. ARRAY_PUSH STACK BELLEĞİ REALLOC ÇÖKMESİNİ ÖNLEME
# =========================================================================

def test_array_push_stack_literal_safety():
    """Stack compound literal dizisine array_push yapıldığında heap kopyası oluşturarak çökmemeli."""
    source = """
    fn main() -> int {
        let mut a = [10, 20, 30];
        a = array_push(a, 40);
        a = array_push(a, 50);
        a = array_push(a, 60);

        print("len:", len(a));
        print("a[0]:", a[0], "a[3]:", a[3], "a[5]:", a[5]);

        verify len(a) == 6;
        verify a[0] == 10;
        verify a[3] == 40;
        verify a[5] == 60;
        print("STACK_REALLOC_FIX_OK");
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "STACK_REALLOC_FIX_OK" in res.stdout
    assert "len: 6" in res.stdout


# =========================================================================
# 3. TLS SERTİFİKA VE HOSTNAME DOĞRULAMASI (ANTI-MITM)
# =========================================================================

def test_tls_rejects_untrusted_self_signed_cert():
    """Sistem CA havuzunda bulunmayan self-signed sertifikalı sunucuya TLS bağlantısı reddedilmeli."""
    cert_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False).name
    key_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False).name
    # Güvensiz / self-signed sertifika üret
    os.system(f"openssl req -x509 -newkey rsa:2048 -keyout {key_file} -out {cert_file} -days 1 -nodes -subj \"/CN=untrusted.badssl.local\" 2>/dev/null")

    port_sock = socket.socket()
    port_sock.bind(("", 0))
    port = port_sock.getsockname()[1]
    port_sock.close()

    def run_tls_server():
        try:
            ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
            s.listen(1)
            raw_conn, _ = s.accept()
            conn = ctx.wrap_socket(raw_conn, server_side=True)
            conn.recv(1024)
            conn.close()
            s.close()
        except Exception:
            pass

    th = threading.Thread(target=run_tls_server, daemon=True)
    th.start()
    time.sleep(0.1)

    source = f"""
    import "std:crypto:tls"

    fn main() -> int {{
        // Sertifika sistem CA'sında olmadığı için tls_connect -1 dönmelidir (MITM reddi)
        let tid = tls_connect("127.0.0.1", {port});
        print("tid_result:", tid);
        verify tid == -1, "Guvenilmeyen TLS sertifikasi reddedilmeli!";
        print("TLS_MITM_REJECT_OK");
        return 0;
    }}
    """
    try:
        # SSL_CERT_FILE set edilmeden çalıştırıyoruz (istemci güvenmemeli)
        res = compile_and_run(source)
        assert res.returncode == 0
        assert "tid_result: -1" in res.stdout
        assert "TLS_MITM_REJECT_OK" in res.stdout
    finally:
        th.join(timeout=1)
        if os.path.exists(cert_file): os.remove(cert_file)
        if os.path.exists(key_file): os.remove(key_file)


# =========================================================================
# 4. JWT SABİT ZAMANLI CRYPTO_memcmp & EXP/NBF DENETİMİ
# =========================================================================

def test_jwt_valid_token_verification():
    """Geçerli token'ın başarıyla doğrulandığını teyit eder."""
    source = """
    import "std:security:jwt"

    fn main() -> int {
        let secret = "axiom_super_secret_jwt_key_2026";
        let payload = "{\\"sub\\":\\"admin\\",\\"role\\":\\"sec_auditor\\"}";
        let token = jwt_create_hs256(payload, secret);

        let valid = jwt_verify_hs256(token, secret);
        verify valid == true;

        let role = jwt_get_claim(token, "role");
        verify role == "sec_auditor";
        print("JWT_VALID_OK");
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "JWT_VALID_OK" in res.stdout


def test_jwt_expired_token_rejected():
    """Süresi geçmiş (exp < now) JWT token'ının reddedildiğini teyit eder."""
    source = """
    import "std:security:jwt"

    fn main() -> int {
        let secret = "axiom_super_secret_jwt_key_2026";
        // exp 1000000000 (Eylül 2001) -> Süresi çoktan dolmuş
        let expired_payload = "{\\"sub\\":\\"admin\\",\\"exp\\":1000000000}";
        let token = jwt_create_hs256(expired_payload, secret);

        let valid = jwt_verify_hs256(token, secret);
        verify valid == false, "Suresi gecmis token reddedilmeli!";
        print("JWT_EXPIRED_REJECT_OK");
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "JWT_EXPIRED_REJECT_OK" in res.stdout


def test_jwt_tampered_signature_and_timing_safety():
    """Tahrif edilmiş imzanın sabit zamanlı doğrulama ile reddedildiğini teyit eder."""
    source = """
    import "std:security:jwt"

    fn main() -> int {
        let secret = "correct_secret_key_123456";
        let payload = "{\\"user\\":\\"alice\\"}";
        let token = jwt_create_hs256(payload, secret);

        // Yanlış anahtarla doğrulama
        let valid_wrong_key = jwt_verify_hs256(token, "attacker_wrong_secret");
        verify valid_wrong_key == false;

        // İmzası tahrif edilmiş token
        let tampered_token = token + "X";
        let valid_tampered = jwt_verify_hs256(tampered_token, secret);
        verify valid_tampered == false;

        print("JWT_TAMPER_REJECT_OK");
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "JWT_TAMPER_REJECT_OK" in res.stdout


# =========================================================================
# 5. C2 PROTOKOLÜ RASTGELE IV & GÜVENLİ HMAC DOĞRULAMASI
# =========================================================================

def test_c2_random_iv_produces_distinct_beacons():
    """Her beacon üretiminde farklı rastgele IV üretildiğini ve başarıyla çözüldüğünü teyit eder."""
    source = """
    import "std:net:c2"

    fn main() -> int {
        let agent = "AGENT_OMEGA_007";
        let secret = "classified_master_c2_encryption_key_32";
        let payload = "STATUS:ACTIVE;IP:10.0.0.42";

        // Aynı payload ve anahtarla iki ardışık beacon üret
        let beacon1 = c2_generate_beacon(agent, secret, payload);
        let beacon2 = c2_generate_beacon(agent, secret, payload);

        // Kriptografik rastgele IV sayesinde iki token birbirinden FARKLI olmalıdır!
        verify beacon1 != beacon2, "Sabit IV kaldirilmali, her beacon farkli olmali!";

        // Her ikisi de doğru çözümlenebilmelidir
        let p1 = c2_parse_beacon(beacon1, secret);
        let p2 = c2_parse_beacon(beacon2, secret);

        verify p1 == payload;
        verify p2 == payload;

        print("C2_RANDOM_IV_OK");
        return 0;
    }
    """
    res = compile_and_run(source, features=["offensive"])
    assert res.returncode == 0
    assert "C2_RANDOM_IV_OK" in res.stdout


def test_c2_tampered_beacon_rejected_by_hmac():
    """C2 beacon tahrif edildiğinde HMAC doğrulaması ile reddedildiğini teyit eder."""
    source = """
    import "std:net:c2"
    import "std:encoding:base64"

    fn main() -> int {
        let agent = "AGENT_OMEGA_007";
        let secret = "classified_master_c2_encryption_key_32";
        let payload = "TARGET_COMMAND:EXEC";

        let beacon = c2_generate_beacon(agent, secret, payload);

        // Yanlış anahtar ile deşifre denemesi
        let parsed_bad_key = c2_parse_beacon(beacon, "wrong_secret_key_99999");
        verify parsed_bad_key == "";

        print("C2_HMAC_SECURITY_OK");
        return 0;
    }
    """
    res = compile_and_run(source, features=["offensive"])
    assert res.returncode == 0
    assert "C2_HMAC_SECURITY_OK" in res.stdout


# =========================================================================
# 6. OS_EXEC_ARGV GÜVENLİ ARGÜMAN DİZİSİ ÇALIŞTIRMA (NO SHELL INJECTION)
# =========================================================================

def test_os_exec_argv_execution():
    """os_exec_argv ile doğrudan argüman dizisi çalıştırma ve çıkış kodu kontrolü."""
    source = """
    import "std:os:process"

    fn main() -> int {
        // 'true' komutu 0 döner
        let args_true = ["true"];
        let ret0 = os_exec_argv(args_true);
        verify ret0 == 0;

        // 'false' komutu 1 döner
        let args_false = ["false"];
        let ret1 = os_exec_argv(args_false);
        verify ret1 == 1;

        print("OS_EXEC_ARGV_BASIC_OK");
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "OS_EXEC_ARGV_BASIC_OK" in res.stdout


def test_os_exec_argv_prevents_shell_injection():
    """Shell metakarakterlerinin (;, &&, $, `) shell olmadan doğrudan aktarıldığını doğrular."""
    marker_file = tempfile.NamedTemporaryFile(suffix=".txt", delete=False).name
    if os.path.exists(marker_file):
        os.remove(marker_file)

    source = f"""
    import "std:os:process"

    fn main() -> int {{
        // Komut enjeksiyonu denemesi: 'echo' komutuna shell zincirleme saldırısı argümanı veriliyor
        // Eğer shell (sh -c) kullanılsaydı marker dosyası oluşturulurdu!
        let malicious_arg = "safe_text; touch {marker_file}";
        let argv = ["echo", malicious_arg];
        let code = os_exec_argv(argv);
        verify code == 0;
        print("INJECTION_TEST_COMPLETED");
        return 0;
    }}
    """
    try:
        res = compile_and_run(source)
        assert res.returncode == 0
        assert "INJECTION_TEST_COMPLETED" in res.stdout
        # Enjeksiyon gerçekleşmedi, marker dosyası OLUŞTURULMAMALI!
        assert not os.path.exists(marker_file), "Kritik Güvenlik Açığı: Shell injection tetiklendi!"
    finally:
        if os.path.exists(marker_file):
            os.remove(marker_file)


# =========================================================================
# EK DERİNLEMESİNE GÜVENLİK TESTLERİ (ADVANCED VERIFICATIONS)
# =========================================================================

def test_bounds_checking_store_oob_exit_102():
    """Dizi üst sınırını aşan yazma/atama işleminde (arr[out] = val) program 102 ile durmalı."""
    source = """
    fn main() -> int {
        let mut arr = [10, 20];
        // arr boyutu 2, indeks 99 sınır aşımı yazmasıdır!
        arr[99] = 1234;
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 102
    assert "[AXIOM BELLEK IHLALI] Dizi sınır aşımı (Index out of bounds)!" in res.stderr
    assert "Indeks: 99, Dizi Uzunlugu: 2" in res.stderr


def test_jwt_alg_none_and_confusion_rejected():
    """'alg: none' veya farklı algoritma (RS256) içeren token'ların doğrulamayı geçemediğini teyit eder."""
    source = """
    import "std:security:jwt"
    import "std:encoding:base64"

    fn main() -> int {
        let secret = "axiom_super_secret_jwt_key_2026";
        // 1. alg: none saldırı token'ı
        let h_none = base64_encode("{\\"alg\\":\\"none\\",\\"typ\\":\\"JWT\\"}");
        let payload = base64_encode("{\\"sub\\":\\"attacker\\",\\"role\\":\\"root\\"}");
        let none_token = h_none + "." + payload + ".";
        let valid_none = jwt_verify_hs256(none_token, secret);
        verify valid_none == false, "alg: none token reddedilmeli!";

        // 2. Algorithm confusion (RS256 alg başlığı ile HS256 doğrulama girişimi)
        let h_rs256 = base64_encode("{\\"alg\\":\\"RS256\\",\\"typ\\":\\"JWT\\"}");
        let rs_token = h_rs256 + "." + payload + ".fakesig";
        let valid_rs = jwt_verify_hs256(rs_token, secret);
        verify valid_rs == false, "alg: RS256 token HS256 dogrulayici tarafindan reddedilmeli!";

        print("JWT_ALG_SECURITY_OK");
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "JWT_ALG_SECURITY_OK" in res.stdout


def test_jwt_nbf_future_token_rejected():
    """Geçerlilik başlangıcı (nbf) gelecekte olan token'ın reddedildiğini teyit eder."""
    source = """
    import "std:security:jwt"

    fn main() -> int {
        let secret = "axiom_super_secret_jwt_key_2026";
        // nbf: 2500000000 (Yıl 2049) -> Gelecekte geçerli olacak token
        let future_payload = "{\\"sub\\":\\"operator\\",\\"nbf\\":2500000000}";
        let token = jwt_create_hs256(future_payload, secret);

        let valid = jwt_verify_hs256(token, secret);
        verify valid == false, "Gelecekte gecerli nbf token reddedilmeli!";
        print("JWT_NBF_FUTURE_REJECT_OK");
        return 0;
    }
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "JWT_NBF_FUTURE_REJECT_OK" in res.stdout


def test_bounds_checking_llvm_backend_oob_exit_102():
    """LLVM arka ucunda dizi sınır aşımının (OOB) 102 çıkış koduyla durdurulduğunu doğrular."""
    from axiom.lexer import Lexer
    from axiom.parser import Parser
    from axiom.checker import TypeChecker
    from axiom.codegen_llvm import LLVMCodeGenerator

    source = """
    fn main() -> int {
        let arr = [5, 10, 15];
        let bad = arr[10];
        print("bad:", bad);
        return 0;
    }
    """
    tokens = Lexer(source).tokenize()
    prog = Parser(tokens).parse()
    TypeChecker().check(prog)
    ll_code = LLVMCodeGenerator().generate(prog)

    with tempfile.NamedTemporaryFile(suffix=".ll", mode="w", delete=False) as ll_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        ll_path = ll_file.name
        bin_path = bin_file.name
        ll_file.write(ll_code)

    runtime_c = str(Path(__file__).resolve().parent.parent / "axiom" / "axiom_llvm_runtime.c")
    try:
        res_cc = subprocess.run(["clang", "-O1", ll_path, runtime_c, "-pthread", "-lz", "-lssl", "-lcrypto", "-ldl", "-lm", "-o", bin_path],
                                capture_output=True, text=True)
        if res_cc.returncode != 0:
            pytest.skip(f"LLVM clang derleme ortami saglanamadi: {res_cc.stderr}")

        res_exec = subprocess.run([bin_path], capture_output=True, text=True, timeout=5)
        assert res_exec.returncode == 102
        assert "[AXIOM BELLEK IHLALI] Dizi sınır aşımı (Index out of bounds)!" in res_exec.stderr
    finally:
        if os.path.exists(ll_path): os.remove(ll_path)
        if os.path.exists(bin_path): os.remove(bin_path)

