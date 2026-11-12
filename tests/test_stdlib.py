"""
Axiom Programming Language (λx) - Standard Library & Built-in Functions Tests
"""
import socket
import threading
import time
import os
import tempfile
import subprocess
from pathlib import Path
import pytest

from tests.support_env import require_network

from axiom.cli import compile_axiom_source, find_c_compiler
from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.checker import TypeChecker
from axiom.resolver import ModuleResolver

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

def test_builtin_str_contains():
    source = """
    let text = "Security and Vulnerability Scanner";
    let ok = str_contains(text, "Vulnerability");
    let fail = str_contains(text, "exploit");
    print("ok:", ok, "fail:", fail);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "ok: true fail: false" in res.stdout

def test_builtin_str_starts_with():
    source = """
    let url = "https://axiom-lang.org";
    let is_https = str_starts_with(url, "https://");
    let is_http = str_starts_with(url, "http://");
    print("https:", is_https, "http:", is_http);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "https: true http: false" in res.stdout

def test_builtin_str_ends_with():
    source = """
    let filename = "payload.ax";
    let is_ax = str_ends_with(filename, ".ax");
    let is_c = str_ends_with(filename, ".c");
    print("ax:", is_ax, "c:", is_c);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "ax: true c: false" in res.stdout

def test_builtin_str_trim():
    source = """
    let dirty = "   hello axiom runtime   ";
    let clean = str_trim(dirty);
    print("len:", len(clean), "val:[", clean, "]");
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "len: 19 val:[ hello axiom runtime ]" in res.stdout

def test_builtin_str_to_int():
    source = """
    let s1 = "1337";
    let s2 = "-42";
    let n1 = str_to_int(s1);
    let n2 = str_to_int(s2);
    print("res:", n1 + n2);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "res: 1295" in res.stdout

def test_builtin_int_to_str():
    source = """
    let val = 98765;
    let s = int_to_str(val);
    let msg = "ID: " + s;
    print(msg);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "ID: 98765" in res.stdout

def test_builtin_math_functions():
    source = """
    let a = math_abs(-25);
    let b = math_abs(40);
    let mn = math_min(a, b);
    let mx = math_max(a, b);
    let p = math_pow(2, 10);
    print("abs:", a, b, "min:", mn, "max:", mx, "pow:", p);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "abs: 25 40 min: 25 max: 40 pow: 1024" in res.stdout

def test_std_import_resolution():
    source = """
    import "std:net/http.ax"

    let target = "127.0.0.1";
    let res = http_get(target, 65534, "/ping");
    print("done:", len(res));
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "done: 0" in res.stdout

def test_std_import_slash_syntax():
    source = """
    import "std/net/http.ax"

    let res = http_get("127.0.0.1", 65533, "/status");
    print("res_len:", len(res));
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "res_len: 0" in res.stdout

@require_network
def test_http_get_with_live_mock_server():
    # Start a temporary local HTTP server in a thread
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", 0))
    port = server_sock.getsockname()[1]
    server_sock.listen(1)

    received_request = []

    def mock_server():
        try:
            client, _ = server_sock.accept()
            data = client.recv(1024).decode("utf-8")
            received_request.append(data)
            resp = "HTTP/1.1 200 OK\r\nServer: AxiomTest/1.0\r\nContent-Length: 13\r\n\r\nHello Socket!"
            client.sendall(resp.encode("utf-8"))
            client.close()
        except Exception:
            pass
        finally:
            server_sock.close()

    t = threading.Thread(target=mock_server, daemon=True)
    t.start()
    time.sleep(0.05)

    source = f"""
    import "std:net/http.ax"

    let host = "127.0.0.1";
    let port = {port};
    let response = http_get(host, port, "/test-banner");
    let is_ok = str_contains(response, "200 OK");
    let has_server = str_contains(response, "AxiomTest");
    print("ok:", is_ok, "server:", has_server);
    """
    res = compile_and_run(source)
    t.join(timeout=2)

    assert res.returncode == 0
    assert "ok: true server: true" in res.stdout
    assert len(received_request) == 1
    assert "GET /test-banner HTTP/1.1" in received_request[0]

def test_examples_07_http_banner_grabber():
    axiom_bin = Path(__file__).resolve().parent.parent / "bin" / "axiom"
    ex_path = Path(__file__).resolve().parent.parent / "examples" / "07_http_banner_grabber.ax"
    res = subprocess.run([str(axiom_bin), "run", str(ex_path)], capture_output=True, text=True)
    assert res.returncode == 0
    assert "✓ Banner teshis mantigi basariyla dogrulandi." in res.stdout
    assert "AXIOM HTTP BANNER GRABBER" in res.stdout

def test_str_contains_edge_cases():
    source = """
    let empty_haystack = "";
    let empty_sub = "";
    let c1 = str_contains("hello", "");
    let c2 = str_contains("world", "world");
    let c3 = str_contains("", "something");
    print("c1:", c1, "c2:", c2, "c3:", c3);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "c1: true c2: true c3: false" in res.stdout

def test_str_starts_with_edge_cases():
    source = """
    let s1 = str_starts_with("prefix_match", "prefix");
    let s2 = str_starts_with("exact", "exact");
    let s3 = str_starts_with("short", "longer_prefix");
    print("s1:", s1, "s2:", s2, "s3:", s3);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "s1: true s2: true s3: false" in res.stdout

def test_str_ends_with_edge_cases():
    source = """
    let e1 = str_ends_with("filename.ax", ".ax");
    let e2 = str_ends_with("exact", "exact");
    let e3 = str_ends_with("short", "longer_suffix");
    print("e1:", e1, "e2:", e2, "e3:", e3);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "e1: true e2: true e3: false" in res.stdout

def test_str_trim_empty_and_spaces():
    source = """
    let t1 = str_trim("   ");
    let t2 = str_trim("");
    let t3 = str_trim("word");
    print("t1:", len(t1), "t2:", len(t2), "t3:", t3);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "t1: 0 t2: 0 t3: word" in res.stdout

def test_math_pow_edge_cases():
    source = """
    let p0 = math_pow(10, 0);
    let p1 = math_pow(7, 1);
    let p2 = math_pow(3, 4);
    print("p0:", p0, "p1:", p1, "p2:", p2);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "p0: 1 p1: 7 p2: 81" in res.stdout

def test_checker_type_validation_builtins():
    from axiom.checker import SemanticError
    # str_contains expects (str, str)
    bad_code = "let x = str_contains(123, 'test');"
    with pytest.raises(Exception):
        tokens = Lexer(bad_code).tokenize()
        ast = Parser(tokens).parse()
        TypeChecker().check(ast)

