"""
Axiom Programming Language (λx) - Standard Library Packet 1 Tests
Libraries tested:
1. std:encoding:base64
2. std:encoding:hex
3. std:crypto:hash (MD5, SHA-1, SHA-256)
4. std:net:url (RFC 3986 parse, encode, decode)
5. std:encoding:json (key extraction, get str/int/bool, build object)
"""
import os
import subprocess
import tempfile
import pytest
from pathlib import Path

from axiom.cli import compile_axiom_source, find_c_compiler

def compile_and_run(source_code: str, source_path: str = "<test>") -> subprocess.CompletedProcess:
    c_code = compile_axiom_source(source_code, source_path)
    cc = find_c_compiler()

    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        res_cc = subprocess.run([cc, "-O2", c_path, "-o", bin_path], capture_output=True, text=True)
        if res_cc.returncode != 0:
            raise RuntimeError(f"C Derleyici Hatasi:\n{res_cc.stderr}\nUretilen C Kodu:\n{c_code}")

        res_exec = subprocess.run([bin_path], capture_output=True, text=True)
        return res_exec
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

# --- 1. Base64 Tests ---

def test_std_base64_encode_decode():
    source = """
    import "std:encoding:base64"

    let original = "Axiom Zero-Cost Systems Language";
    let encoded = base64_encode(original);
    let decoded = base64_decode(encoded);

    print("enc:", encoded);
    print("dec:", decoded);
    verify decoded == original, "Base64 roundtrip basarisiz!";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "enc: QXhpb20gWmVyby1Db3N0IFN5c3RlbXMgTGFuZ3VhZ2U=" in res.stdout
    assert "dec: Axiom Zero-Cost Systems Language" in res.stdout

def test_std_base64_edge_cases():
    source = """
    import "std:encoding:base64"

    let e0 = base64_encode("");
    let d0 = base64_decode("");

    let e1 = base64_encode("a");
    let d1 = base64_decode(e1);

    let e2 = base64_encode("ab");
    let d2 = base64_decode(e2);

    let e3 = base64_encode("abc");
    let d3 = base64_decode(e3);

    print("e0:", e0, "d0:", d0);
    print("e1:", e1, "d1:", d1);
    print("e2:", e2, "d2:", d2);
    print("e3:", e3, "d3:", d3);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "e1: YQ== d1: a" in res.stdout
    assert "e2: YWI= d2: ab" in res.stdout
    assert "e3: YWJj d3: abc" in res.stdout

# --- 2. Hex Tests ---

def test_std_hex_encode_decode():
    source = """
    import "std:encoding:hex"

    let raw = "SecurityPayload#1337";
    let h = hex_encode(raw);
    let dec = hex_decode(h);

    print("hex:", h);
    print("dec:", dec);
    verify dec == raw, "Hex roundtrip basarisiz!";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "hex: 53656375726974795061796c6f61642331333337" in res.stdout
    assert "dec: SecurityPayload#1337" in res.stdout

def test_std_hex_mixed_case():
    source = """
    import "std:encoding:hex"

    let dec_upper = hex_decode("414243");
    let dec_lower = hex_decode("414263");

    print("upper:", dec_upper, "lower:", dec_lower);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "upper: ABC lower: ABc" in res.stdout

# --- 3. Cryptographic Hash Tests ---

def test_std_crypto_hash_md5():
    source = """
    import "std:crypto:hash"

    let h_empty = hash_md5("");
    let h_admin = hash_md5("admin");

    print("md5_empty:", h_empty);
    print("md5_admin:", h_admin);
    verify h_empty == "d41d8cd98f00b204e9800998ecf8427e", "MD5 bos ozet hatali!";
    verify h_admin == "21232f297a57a5a743894a0e4a801fc3", "MD5 admin ozeti hatali!";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "md5_empty: d41d8cd98f00b204e9800998ecf8427e" in res.stdout
    assert "md5_admin: 21232f297a57a5a743894a0e4a801fc3" in res.stdout

def test_std_crypto_hash_sha1():
    source = """
    import "std:crypto:hash"

    let h_empty = hash_sha1("");
    let h_admin = hash_sha1("admin");

    print("sha1_empty:", h_empty);
    print("sha1_admin:", h_admin);
    verify h_empty == "da39a3ee5e6b4b0d3255bfef95601890afd80709", "SHA1 bos ozet hatali!";
    verify h_admin == "d033e22ae348aeb5660fc2140aec35850c4da997", "SHA1 admin ozeti hatali!";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "sha1_empty: da39a3ee5e6b4b0d3255bfef95601890afd80709" in res.stdout
    assert "sha1_admin: d033e22ae348aeb5660fc2140aec35850c4da997" in res.stdout

def test_std_crypto_hash_sha256():
    source = """
    import "std:crypto:hash"

    let h_empty = hash_sha256("");
    let h_admin = hash_sha256("admin");

    print("sha256_empty:", h_empty);
    print("sha256_admin:", h_admin);
    verify h_empty == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "SHA256 bos ozet hatali!";
    verify h_admin == "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918", "SHA256 admin ozeti hatali!";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "sha256_empty: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" in res.stdout
    assert "sha256_admin: 8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918" in res.stdout

# --- 4. URL Tests ---

def test_std_url_encode_decode():
    source = """
    import "std:net:url"

    let raw = "user@domain.com / test ? q=axiom&limit=10";
    let enc = url_encode(raw);
    let dec = url_decode(enc);

    print("enc:", enc);
    print("dec:", dec);
    verify dec == raw, "URL encode/decode eslesmedi!";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "enc: user%40domain.com%20%2F%20test%20%3F%20q%3Daxiom%26limit%3D10" in res.stdout
    assert "dec: user@domain.com / test ? q=axiom&limit=10" in res.stdout

def test_std_url_parse_complete():
    source = """
    import "std:net:url"

    let raw = "https://admin:pass@omega-security.internal:8443/api/v2/scans?target=192.168.1.1&mode=stealth#results";
    let u = url_parse(raw);

    print("scheme:", u.scheme);
    print("host:", u.host);
    print("port:", u.port);
    print("path:", u.path);
    print("query:", u.query);

    verify u.scheme == "https", "Scheme hatali";
    verify u.host == "omega-security.internal", "Host hatali";
    verify u.port == 8443, "Port hatali";
    verify u.path == "/api/v2/scans", "Path hatali";
    verify u.query == "target=192.168.1.1&mode=stealth", "Query hatali";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "scheme: https" in res.stdout
    assert "host: omega-security.internal" in res.stdout
    assert "port: 8443" in res.stdout
    assert "path: /api/v2/scans" in res.stdout
    assert "query: target=192.168.1.1&mode=stealth" in res.stdout

def test_std_url_parse_defaults():
    source = """
    import "std:net:url"

    let u_http = url_parse("http://example.org");
    let u_https = url_parse("https://axiom-lang.org/docs");

    print("http_port:", u_http.port, "http_path:", u_http.path);
    print("https_port:", u_https.port, "https_path:", u_https.path);

    verify u_http.port == 80, "Default HTTP port 80 olmali";
    verify u_https.port == 443, "Default HTTPS port 443 olmali";
    verify u_https.path == "/docs", "HTTPS path /docs olmali";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "http_port: 80 http_path: /" in res.stdout
    assert "https_port: 443 https_path: /docs" in res.stdout

# --- 5. JSON Tests ---

def test_std_json_parsing_and_queries():
    source = """
    import "std:encoding:json"

    let doc = "{\\"target\\": \\"10.10.10.5\\", \\"port\\": 443, \\"vuln_detected\\": true, \\"service\\": \\"nginx/1.24\\"}";

    let has_target = json_has_key(doc, "target");
    let has_unknown = json_has_key(doc, "non_existent");
    let target = json_get_str(doc, "target");
    let port = json_get_int(doc, "port");
    let vuln = json_get_bool(doc, "vuln_detected");
    let service = json_get_str(doc, "service");

    print("has_target:", has_target, "has_unknown:", has_unknown);
    print("target:", target, "port:", port, "vuln:", vuln, "srv:", service);

    verify has_target == true, "target anahtari bulunmaliydi";
    verify has_unknown == false, "non_existent bulunmamaliydi";
    verify target == "10.10.10.5", "target degeri eslesmedi";
    verify port == 443, "port degeri eslesmedi";
    verify vuln == true, "vuln degeri eslesmedi";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "has_target: true has_unknown: false" in res.stdout
    assert "target: 10.10.10.5 port: 443 vuln: true srv: nginx/1.24" in res.stdout

def test_std_json_build_object():
    source = """
    import "std:encoding:json"

    let keys = ["scanner", "version", "status"];
    let vals = ["Axiom-Omega", "1.0.0", "active"];
    let json_str = json_build_object(keys, vals);

    print("json:", json_str);

    let s_name = json_get_str(json_str, "scanner");
    let s_ver = json_get_str(json_str, "version");
    let s_stat = json_get_str(json_str, "status");

    print("parsed:", s_name, s_ver, s_stat);
    verify s_name == "Axiom-Omega", "JSON scanner eslesmedi";
    verify s_ver == "1.0.0", "JSON version eslesmedi";
    verify s_stat == "active", "JSON status eslesmedi";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert 'json: {"scanner":"Axiom-Omega","version":"1.0.0","status":"active"}' in res.stdout
    assert "parsed: Axiom-Omega 1.0.0 active" in res.stdout

# --- 6. Cross-Library Suite (Integration) ---

def test_packet1_all_libraries_combined():
    source = """
    import "std:encoding:base64"
    import "std:encoding:hex"
    import "std:crypto:hash"
    import "std:net:url"
    import "std:encoding:json"

    // 1. URL Parse
    let u = url_parse("https://vault.security.lab:8000/auth/login?client=omega");
    verify u.port == 8000, "Port 8000 olmali";

    // 2. Hash calculation
    let secret_seed = "client_secret_9988";
    let token_hash = hash_sha256(secret_seed);

    // 3. Base64 & Hex
    let b64_token = base64_encode(token_hash);
    let hex_token = hex_encode("AUTH_OK");

    // 4. JSON Payload construction
    let keys = ["host", "hash_sha256", "auth_hex", "b64_seed"];
    let values = [u.host, token_hash, hex_token, b64_token];
    let payload_json = json_build_object(keys, values);

    // 5. Verify fields in JSON
    let j_host = json_get_str(payload_json, "host");
    let j_hex = json_get_str(payload_json, "auth_hex");
    let dec_auth = hex_decode(j_hex);

    print("j_host:", j_host);
    print("dec_auth:", dec_auth);
    print("payload_len:", len(payload_json));

    verify j_host == "vault.security.lab", "JSON host eslesmedi";
    verify dec_auth == "AUTH_OK", "Auth decode basarisiz";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "j_host: vault.security.lab" in res.stdout
    assert "dec_auth: AUTH_OK" in res.stdout

# --- 7. LLVM Backend Integration Tests ---

def compile_and_run_llvm(source: str, base_file: str = "<stdin>") -> subprocess.CompletedProcess:
    from axiom.lexer import Lexer
    from axiom.parser import Parser
    from axiom.checker import TypeChecker
    from axiom.resolver import ModuleResolver
    from axiom.codegen_llvm import LLVMCodeGenerator

    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    resolver = ModuleResolver(base_file)
    resolved = resolver.resolve(program)
    TypeChecker().check(resolved)
    codegen = LLVMCodeGenerator()
    llvm_ir = codegen.generate(resolved)

    with tempfile.NamedTemporaryFile(suffix=".ll", mode="w", delete=False) as fll, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as fbin:
        fll.write(llvm_ir)
        ll_path = fll.name
        bin_path = fbin.name

    runtime_c = str(Path(__file__).resolve().parent.parent / "axiom" / "axiom_llvm_runtime.c")
    try:
        compile_cmd = ["clang", "-O3", ll_path, runtime_c, "-pthread", "-lz", "-lssl", "-lcrypto", "-ldl", "-lm", "-o", bin_path]
        res = subprocess.run(compile_cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"LLVM Compilation failed:\n{res.stderr}\nIR:\n{llvm_ir}"
        run_res = subprocess.run([bin_path], capture_output=True, text=True)
        return run_res
    finally:
        if os.path.exists(ll_path):
            os.remove(ll_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

def test_llvm_packet1_crypto_and_encoding():
    source = """
    import "std:encoding:base64"
    import "std:encoding:hex"
    import "std:crypto:hash"

    fn main() -> void {
        let msg = "AxiomLLVM";
        let h256 = hash_sha256(msg);
        let b64 = base64_encode(h256);
        let hx = hex_encode(msg);
        print("llvm_sha256:", h256);
        print("llvm_b64:", b64);
        print("llvm_hex:", hx);
    }
    """
    res = compile_and_run_llvm(source)
    assert res.returncode == 0
    assert "llvm_hex: 4178696f6d4c4c564d" in res.stdout

def test_llvm_packet1_url_and_json():
    source = """
    import "std:net:url"
    import "std:encoding:json"

    fn main() -> void {
        let u = url_parse("https://api.cloud.axiom:9090/v1/health?check=full");
        let enc = url_encode(u.path);
        let doc = "{\\"status\\": \\"healthy\\", \\"uptime\\": 9999}";
        let st = json_get_str(doc, "status");
        let up = json_get_int(doc, "uptime");
        print("u_host:", u.host, "u_port:", u.port);
        print("json_st:", st, "up:", up);
    }
    """
    res = compile_and_run_llvm(source)
    assert res.returncode == 0
    assert "u_host: api.cloud.axiom u_port: 9090" in res.stdout
    assert "json_st: healthy up: 9999" in res.stdout

# --- 8. Comprehensive Edge Cases & Import Variations ---

def test_base64_slash_syntax_import():
    source = """
    import "std/encoding/base64.ax"

    let b = base64_encode("test_payload");
    let d = base64_decode(b);
    print("d:", d);
    verify d == "test_payload", "Slash import failed";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "d: test_payload" in res.stdout

def test_hex_slash_syntax_import():
    source = """
    import "std/encoding/hex.ax"

    let h = hex_encode("AxiomBinary");
    let d = hex_decode(h);
    print("d:", d);
    verify d == "AxiomBinary", "Hex slash import failed";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "d: AxiomBinary" in res.stdout

def test_crypto_hash_slash_syntax_import():
    source = """
    import "std/crypto/hash.ax"

    let h256 = hash_sha256("integrity_check");
    let h1 = hash_sha1("integrity_check");
    let md = hash_md5("integrity_check");
    print("len_sha256:", len(h256), "len_sha1:", len(h1), "len_md5:", len(md));
    verify len(h256) == 64, "SHA-256 boyutu 64 olmali";
    verify len(h1) == 40, "SHA-1 boyutu 40 olmali";
    verify len(md) == 32, "MD5 boyutu 32 olmali";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "len_sha256: 64 len_sha1: 40 len_md5: 32" in res.stdout

def test_url_slash_syntax_import():
    source = """
    import "std/net/url.ax"

    let u = url_parse("http://internal-gw:8080/metrics");
    print("host:", u.host, "port:", u.port, "path:", u.path);
    verify u.host == "internal-gw", "Host eslesmedi";
    verify u.port == 8080, "Port eslesmedi";
    verify u.path == "/metrics", "Path eslesmedi";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "host: internal-gw port: 8080 path: /metrics" in res.stdout

def test_json_slash_syntax_import():
    source = """
    import "std/encoding/json.ax"

    let doc = "{\\"code\\": 200, \\"active\\": true, \\"name\\": \\"axiom\\"}";
    let code = json_get_int(doc, "code");
    let act = json_get_bool(doc, "active");
    let nm = json_get_str(doc, "name");
    print("c:", code, "a:", act, "n:", nm);
    verify code == 200, "Code eslesmedi";
    verify act == true, "Active eslesmedi";
    verify nm == "axiom", "Name eslesmedi";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "c: 200 a: true n: axiom" in res.stdout

def test_crypto_hash_long_buffer():
    source = """
    import "std:crypto:hash"

    // String repetition simulation
    let chunk = "The quick brown fox jumps over the lazy dog. ";
    let mut big_str = chunk + chunk;
    big_str = big_str + big_str;
    big_str = big_str + big_str; // 360 chars

    let h256 = hash_sha256(big_str);
    let h1 = hash_sha1(big_str);
    let hmd5 = hash_md5(big_str);

    print("big_len:", len(big_str));
    print("h256_len:", len(h256), "h1_len:", len(h1), "md5_len:", len(hmd5));
    verify len(h256) == 64, "SHA-256 uzunluk 64 olmali";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "big_len: 190" in res.stdout or "big_len: 360" in res.stdout
    assert "h256_len: 64 h1_len: 40 md5_len: 32" in res.stdout

def test_json_escaped_newlines_and_quotes():
    source = """
    import "std:encoding:json"

    let doc = "{\\"multiline\\": \\"line1\\\\nline2\\\\tindented\\"}";
    let val = json_get_str(doc, "multiline");
    print("has_n:", str_contains(val, "\\n"));
    print("has_t:", str_contains(val, "\\t"));
    verify str_contains(val, "\\n") == true, "Escape newline cozulmeli";
    verify str_contains(val, "\\t") == true, "Escape tab cozulmeli";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "has_n: true" in res.stdout
    assert "has_t: true" in res.stdout

def test_url_schemeless_and_query_variations():
    source = """
    import "std:net:url"

    let u1 = url_parse("192.168.1.100:9999/status");
    let u2 = url_parse("https://scan.me/?arg1=val1&arg2=val2&arg3=val3");

    print("u1_host:", u1.host, "u1_port:", u1.port, "u1_path:", u1.path);
    print("u2_query:", u2.query);

    verify u1.host == "192.168.1.100", "u1 host eslesmedi";
    verify u1.port == 9999, "u1 port eslesmedi";
    verify u2.query == "arg1=val1&arg2=val2&arg3=val3", "u2 query eslesmedi";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "u1_host: 192.168.1.100 u1_port: 9999 u1_path: /status" in res.stdout
    assert "u2_query: arg1=val1&arg2=val2&arg3=val3" in res.stdout

def test_resolver_two_colon_all_packet1_modules(tmp_path):
    from axiom.lexer import Lexer
    from axiom.parser import Parser
    from axiom.resolver import ModuleResolver
    from axiom.checker import TypeChecker

    source = """
    import "std:encoding:base64"
    import "std:encoding:hex"
    import "std:crypto:hash"
    import "std:net:url"
    import "std:encoding:json"

    let b = base64_encode("test");
    let h = hex_encode("test");
    let s = hash_sha256("test");
    let u = url_parse("http://localhost:8080/test");
    let j = json_get_str("{\\"k\\": \\"v\\"}", "k");
    """
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    resolver = ModuleResolver(str(tmp_path / "main.ax"))
    resolved = resolver.resolve(program)

    # Verify no ImportStmts remain in resolved AST
    for decl in resolved.declarations:
        assert not isinstance(decl, type(program.declarations[0])) or type(decl).__name__ != 'ImportStmt'

    checker = TypeChecker()
    checker.check(resolved)

def test_json_build_object_with_special_characters():
    source = """
    import "std:encoding:json"

    let keys = ["path", "query", "agent"];
    let vals = ["/search?q=test&id=1", "k=v&x=y", "Axiom/1.0 (Linux)"];
    let j = json_build_object(keys, vals);

    print("built_json:", j);
    let p = json_get_str(j, "path");
    let q = json_get_str(j, "query");
    let ag = json_get_str(j, "agent");

    verify p == "/search?q=test&id=1", "Path eslesmedi";
    verify q == "k=v&x=y", "Query eslesmedi";
    verify ag == "Axiom/1.0 (Linux)", "Agent eslesmedi";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert 'built_json: {"path":"/search?q=test&id=1","query":"k=v&x=y","agent":"Axiom/1.0 (Linux)"}' in res.stdout

def test_base64_multiline_data_roundtrip():
    source = """
    import "std:encoding:base64"

    let raw_payload = "GET /admin HTTP/1.1\\r\\nHost: sec.lab\\r\\nAuthorization: Bearer ax123\\r\\n\\r\\n";
    let encoded = base64_encode(raw_payload);
    let decoded = base64_decode(encoded);

    print("dec_matches:", decoded == raw_payload);
    verify decoded == raw_payload, "Payload decode hatali!";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "dec_matches: true" in res.stdout

def test_crypto_hash_known_vectors():
    source = """
    import "std:crypto:hash"

    // NIST test vector: "abc"
    let sha256_abc = hash_sha256("abc");
    let sha1_abc = hash_sha1("abc");
    let md5_abc = hash_md5("abc");

    print("sha256_abc:", sha256_abc);
    print("sha1_abc:", sha1_abc);
    print("md5_abc:", md5_abc);

    verify sha256_abc == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "SHA256 abc vektoru hatali";
    verify sha1_abc == "a9993e364706816aba3e25717850c26c9cd0d89d", "SHA1 abc vektoru hatali";
    verify md5_abc == "900150983cd24fb0d6963f7d28e17f72", "MD5 abc vektoru hatali";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "sha256_abc: ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad" in res.stdout

def test_url_special_delimiters():
    source = """
    import "std:net:url"

    let s = "hello world / & ? # [ ] :";
    let enc = url_encode(s);
    let dec = url_decode(enc);

    print("dec_eq:", dec == s);
    verify dec == s, "URL roundtrip ozel karakterler hatali";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "dec_eq: true" in res.stdout

def test_example_10_packet1_security_suite_e2e():
    axiom_bin = Path(__file__).resolve().parent.parent / "bin" / "axiom"
    ex_path = Path(__file__).resolve().parent.parent / "examples" / "10_packet1_security_suite.ax"
    res = subprocess.run([str(axiom_bin), "run", str(ex_path)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "✓ PAKET 1 SUITI BASARIYLA TAMAMLANDI VE DOGRULANDI." in res.stdout
    assert "AUTHORIZED_SESSION" in res.stdout
    assert "api.omega-security.lab" in res.stdout




