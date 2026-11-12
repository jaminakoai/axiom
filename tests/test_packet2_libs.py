"""
Axiom Programming Language (λx) - Standard Library Packet 2 Tests
Libraries tested:
6. std:net:dns (A, AAAA, PTR reverse lookup)
7. std:net:udp (udp_socket, udp_bind, udp_sendto, udp_recvfrom, udp_close)
8. std:net:http_server (http_server_create, accept, send_response, close)
9. std:crypto:tls (tls_connect, tls_send, tls_recv, tls_close, https_get)
10. std:net:websocket (RFC 6455 ws_connect, ws_send, ws_recv, ws_close)
"""
import os
import subprocess
import tempfile
import time
import socket
import threading
import ssl
import pytest
from pathlib import Path

from axiom.cli import compile_axiom_source, find_c_compiler
from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.resolver import ModuleResolver
from axiom.checker import TypeChecker
from axiom.codegen_llvm import LLVMCodeGenerator

from tests.support_env import require_network

# Bu dosya TAMAMEN ag testleri icerir (dns/udp/http_server/tls/websocket).
# Sandbox'ta soket izni yoksa testler sessizce gecmez; acik gerekceyle atlanir.
pytestmark = require_network

def compile_and_run(source_code: str, source_path: str = "<test>", timeout: int = 10) -> subprocess.CompletedProcess:
    c_code = compile_axiom_source(source_code, source_path)
    cc = find_c_compiler()

    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        res_cc = subprocess.run([cc, "-O2", "-pthread", c_path, "-lssl", "-lcrypto", "-ldl", "-o", bin_path], capture_output=True, text=True)
        if res_cc.returncode != 0:
            raise RuntimeError(f"C Derleyici Hatasi:\n{res_cc.stderr}\nUretilen C Kodu:\n{c_code}")

        res_exec = subprocess.run([bin_path], capture_output=True, text=True, timeout=timeout)
        return res_exec
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

_USED_PORTS = set()
_PORT_LOCK = threading.Lock()


def get_free_port():
    """Kullanilmamis bir port dondurur.

    Eski surum bind->close yapiyor ve ayni portu tekrar dagitabiliyordu; test
    sunucusu henuz bind etmeden port baska bir teste verilince yaris olusuyor
    ve testler ara sira dusuyordu (flaky). Artik bir kez verilen port surec
    boyunca tekrar kullanilmaz.
    """
    with _PORT_LOCK:
        for _ in range(500):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind(('', 0))
                port = s.getsockname()[1]
            finally:
                s.close()
            if port in _USED_PORTS:
                continue
            _USED_PORTS.add(port)
            return port
    raise RuntimeError("bos port bulunamadi")

# =========================================================================
# 1. DNS TESTS (std:net:dns)
# =========================================================================

def test_std_dns_resolve_ipv4():
    source = """
    import "std:net:dns"

    let ip = dns_resolve_ipv4("localhost");
    print("localhost ip:", ip);
    verify ip == "127.0.0.1", "localhost 127.0.0.1 olarak cozulmeli";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "localhost ip: 127.0.0.1" in res.stdout

def test_std_dns_resolve_ipv4_numeric():
    source = """
    import "std:net:dns"

    let ip = dns_resolve_ipv4("127.0.0.1");
    print("numeric ip:", ip);
    verify ip == "127.0.0.1", "Numerik IP ayni kalmali";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "numeric ip: 127.0.0.1" in res.stdout

def test_std_dns_resolve_invalid_host():
    source = """
    import "std:net:dns"

    let ip = dns_resolve_ipv4("invalid-domain-axiom-test-xyz-404.nonexistent");
    print("invalid ip:", ip);
    verify ip == "", "Gecersiz host bos donmeli";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "invalid ip: " in res.stdout

def test_std_dns_reverse_lookup():
    source = """
    import "std:net:dns"

    let host = dns_reverse_lookup("127.0.0.1");
    print("reverse host:", host);
    verify host != "", "Ters DNS cozumlemesi basarili olmali";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "reverse host:" in res.stdout

def test_std_dns_resolve_ipv6():
    source = """
    import "std:net:dns"

    let ip6 = dns_resolve_ipv6("::1");
    print("ipv6:", ip6);
    verify ip6 == "::1", "IPv6 loopback cozulmeli";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "ipv6: ::1" in res.stdout

def test_std_dns_empty_and_invalid():
    source = """
    import "std:net:dns"

    let empty_ip = dns_resolve_ipv4("");
    let rev_inv = dns_reverse_lookup("999.999.999.999");
    print("empty_ip:", empty_ip);
    print("rev_inv:", rev_inv);
    verify empty_ip == "", "Bos host bos donmeli";
    verify rev_inv == "", "Gecersiz IP bos host donmeli";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "empty_ip: " in res.stdout
    assert "rev_inv: " in res.stdout

# =========================================================================
# 2. UDP TESTS (std:net:udp)
# =========================================================================

def test_std_udp_socket_creation_and_close():
    source = """
    import "std:net:udp"

    let fd = udp_socket();
    print("udp fd:", fd);
    verify fd >= 0, "UDP soketi acilamadi";
    udp_close(fd);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "udp fd:" in res.stdout

def test_std_udp_bind_and_close():
    port = get_free_port()
    source = f"""
    import "std:net:udp"

    let fd = udp_bind({port});
    print("bound udp fd:", fd);
    verify fd >= 0, "UDP bind basarisiz";
    udp_close(fd);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "bound udp fd:" in res.stdout

def test_std_udp_bind_invalid_port():
    source = """
    import "std:net:udp"

    let fd1 = udp_bind(-1);
    let fd2 = udp_bind(999999);
    print("invalid bind:", fd1, fd2);
    verify fd1 == -1, "Gecersiz port -1 donmeli";
    verify fd2 == -1, "Gecersiz port -1 donmeli";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "invalid bind: -1 -1" in res.stdout

def test_std_udp_sendto_recvfrom_loopback():
    port = get_free_port()
    source = f"""
    import "std:net:udp"

    fn server_worker(p: int) -> int {{
        let sfd = udp_bind(p);
        if sfd < 0 {{ return 1; }}
        let data = udp_recvfrom(sfd, 1024);
        print("Server Received:", data);
        udp_close(sfd);
        return 0;
    }}

    fn main() -> int {{
        let p = {port};
        let th = thread_create(server_worker, p);
        sleep_ms(60);
        let cfd = udp_socket();
        if cfd >= 0 {{
            udp_sendto(cfd, "127.0.0.1", p, "Axiom UDP Datagram 1337");
            udp_close(cfd);
        }}
        thread_join(th);
        return 0;
    }}
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Server Received: Axiom UDP Datagram 1337" in res.stdout

# =========================================================================
# 3. HTTP SERVER TESTS (std:net:http_server)
# =========================================================================

def test_std_http_server_create_and_close():
    port = get_free_port()
    source = f"""
    import "std:net:http_server"

    let sfd = http_server_create({port});
    print("server sfd:", sfd);
    verify sfd >= 0, "HTTP sunucusu olusturulamadi";
    http_server_close(sfd);
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "server sfd:" in res.stdout

def test_std_http_server_invalid_port():
    source = """
    import "std:net:http_server"

    let sfd = http_server_create(-5);
    print("invalid server sfd:", sfd);
    verify sfd == -1, "Gecersiz port -1 donmeli";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "invalid server sfd: -1" in res.stdout

def test_std_http_server_response_loopback():
    port = get_free_port()
    source = f"""
    import "std:net:http_server"

    fn http_worker(p: int) -> int {{
        let sfd = http_server_create(p);
        if sfd < 0 {{ return 1; }}
        let cfd = http_server_accept(sfd);
        if cfd >= 0 {{
            http_server_send_response(cfd, 200, "application/json", "{{\\"status\\":\\"ok\\"}}");
        }}
        http_server_close(sfd);
        return 0;
    }}

    fn main() -> int {{
        let p = {port};
        let th = thread_create(http_worker, p);
        sleep_ms(50);
        let client = tcp_connect("127.0.0.1", p);
        if client >= 0 {{
            tcp_send(client, "GET /api/status HTTP/1.1\\r\\nHost: localhost\\r\\n\\r\\n");
            let resp = tcp_recv(client, 2048);
            print("Client Got:", resp);
            socket_close(client);
        }}
        thread_join(th);
        return 0;
    }}
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "HTTP/1.1 200 OK" in res.stdout
    assert "Content-Type: application/json" in res.stdout
    assert '{"status":"ok"}' in res.stdout

def test_std_http_server_not_found():
    port = get_free_port()
    source = f"""
    import "std:net:http_server"

    fn http_worker(p: int) -> int {{
        let sfd = http_server_create(p);
        if sfd < 0 {{ return 1; }}
        let cfd = http_server_accept(sfd);
        if cfd >= 0 {{
            http_server_send_response(cfd, 404, "text/plain", "Sayfa Bulunamadi");
        }}
        http_server_close(sfd);
        return 0;
    }}

    fn main() -> int {{
        let p = {port};
        let th = thread_create(http_worker, p);
        sleep_ms(50);
        let client = tcp_connect("127.0.0.1", p);
        if client >= 0 {{
            tcp_send(client, "GET /unknown HTTP/1.1\\r\\nHost: localhost\\r\\n\\r\\n");
            let resp = tcp_recv(client, 1024);
            print("Response 404:", resp);
            socket_close(client);
        }}
        thread_join(th);
        return 0;
    }}
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "HTTP/1.1 404 Not Found" in res.stdout
    assert "Sayfa Bulunamadi" in res.stdout

# =========================================================================
# 4. TLS TESTS (std:crypto:tls)
# =========================================================================

def test_std_tls_connect_failure():
    source = """
    import "std:crypto:tls"

    let tid = tls_connect("127.0.0.1", 19998);
    print("tls fail id:", tid);
    verify tid == -1, "Kapali porta baglanti basarisiz olmali";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "tls fail id: -1" in res.stdout

def test_std_tls_connect_send_recv_mock():
    cert_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False).name
    key_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False).name
    os.system(f"openssl req -x509 -newkey rsa:2048 -keyout {key_file} -out {cert_file} -days 1 -nodes -subj \"/CN=127.0.0.1\" 2>/dev/null")

    port = get_free_port()

    def run_tls_server():
        try:
            ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)
            bind_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            bind_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            bind_sock.bind(("127.0.0.1", port))
            bind_sock.listen(1)
            raw_conn, _ = bind_sock.accept()
            conn = ctx.wrap_socket(raw_conn, server_side=True)
            data = conn.recv(1024).decode()
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 17\r\n\r\nTLS Axiom Handled")
            time.sleep(0.05)
            conn.close()
            bind_sock.close()
        except Exception as e:
            pass

    th = threading.Thread(target=run_tls_server, daemon=True)
    th.start()
    time.sleep(0.1)

    source = f"""
    import "std:crypto:tls"

    let tid = tls_connect("127.0.0.1", {port});
    print("connected tid:", tid);
    verify tid >= 0, "TLS baglantisi basarisiz";

    tls_send(tid, "GET / HTTP/1.1\\r\\nHost: 127.0.0.1\\r\\n\\r\\n");
    let resp = tls_recv(tid, 1024);
    print("tls resp:", resp);
    verify resp != "", "TLS yaniti bos donmemeli";
    tls_close(tid);
    """
    try:
        os.environ["AXIOM_TLS_INSECURE"] = "1"
        res = compile_and_run(source)
        assert res.returncode == 0
        assert "connected tid: 0" in res.stdout
        assert "TLS Axiom Handled" in res.stdout
    finally:
        os.environ.pop("AXIOM_TLS_INSECURE", None)
        th.join(timeout=2)
        if os.path.exists(cert_file): os.remove(cert_file)
        if os.path.exists(key_file): os.remove(key_file)

def test_std_tls_https_get_mock():
    cert_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False).name
    key_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False).name
    os.system(f"openssl req -x509 -newkey rsa:2048 -keyout {key_file} -out {cert_file} -days 1 -nodes -subj \"/CN=127.0.0.1\" 2>/dev/null")

    port = get_free_port()

    def run_tls_server():
        try:
            ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)
            bind_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            bind_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            bind_sock.bind(("127.0.0.1", port))
            bind_sock.listen(1)
            raw_conn, _ = bind_sock.accept()
            conn = ctx.wrap_socket(raw_conn, server_side=True)
            data = conn.recv(1024).decode()
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\nHTTPS_OK!!")
            time.sleep(0.05)
            conn.close()
            bind_sock.close()
        except Exception:
            pass

    th = threading.Thread(target=run_tls_server, daemon=True)
    th.start()
    time.sleep(0.1)

    source = f"""
    import "std:crypto:tls"

    let resp = https_get("127.0.0.1", {port}, "/test/api");
    print("https_get resp:", resp);
    verify resp != "", "https_get basarili olmali";
    """
    try:
        os.environ["AXIOM_TLS_INSECURE"] = "1"
        res = compile_and_run(source)
        assert res.returncode == 0
        assert "HTTPS_OK!!" in res.stdout
    finally:
        os.environ.pop("AXIOM_TLS_INSECURE", None)
        th.join(timeout=2)
        if os.path.exists(cert_file): os.remove(cert_file)
        if os.path.exists(key_file): os.remove(key_file)

# =========================================================================
# 5. WEBSOCKET TESTS (std:net:websocket)
# =========================================================================

def test_std_ws_connect_failure():
    source = """
    import "std:net:websocket"

    let ws = ws_connect("127.0.0.1", 19997, "/ws");
    print("ws fail fd:", ws);
    verify ws == -1, "Kapali porta websocket baglantisi -1 donmeli";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "ws fail fd: -1" in res.stdout

def test_std_ws_handshake_send_recv():
    port = get_free_port()

    def run_ws_server():
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", port))
            srv.listen(1)
            conn, _ = srv.accept()
            req = conn.recv(1024).decode()
            if "Upgrade: websocket" in req:
                conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n")
                hdr = conn.recv(2)
                b0, b1 = hdr[0], hdr[1]
                plen = b1 & 0x7F
                mask = conn.recv(4)
                payload = bytearray(conn.recv(plen))
                unmasked = bytes([payload[i] ^ mask[i % 4] for i in range(plen)]).decode()
                # Reply unmasked text frame
                reply = f"Echo: {unmasked}"
                s_frame = bytearray([0x81, len(reply)]) + reply.encode()
                conn.sendall(s_frame)
            time.sleep(0.05)
            conn.close()
            srv.close()
        except Exception:
            pass

    th = threading.Thread(target=run_ws_server, daemon=True)
    th.start()
    time.sleep(0.05)

    source = f"""
    import "std:net:websocket"

    let ws = ws_connect("127.0.0.1", {port}, "/chat");
    print("ws fd:", ws);
    verify ws >= 0, "WebSocket el sikismasi basarisiz";

    ws_send(ws, "Hello Axiom WS");
    let reply = ws_recv(ws);
    print("ws reply:", reply);
    verify reply == "Echo: Hello Axiom WS", "WebSocket yaniti eslesmedi";
    ws_close(ws);
    """
    try:
        res = compile_and_run(source)
        assert res.returncode == 0
        assert "ws reply: Echo: Hello Axiom WS" in res.stdout
    finally:
        th.join(timeout=2)

def test_std_ws_extended_payload():
    port = get_free_port()

    def run_ws_server():
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", port))
            srv.listen(1)
            conn, _ = srv.accept()
            req = conn.recv(1024).decode()
            conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n")
            hdr = conn.recv(2)
            b0, b1 = hdr[0], hdr[1]
            plen_byte = b1 & 0x7F
            assert plen_byte == 126  # extended 16-bit payload
            ext = conn.recv(2)
            actual_len = (ext[0] << 8) | ext[1]
            mask = conn.recv(4)
            payload = bytearray()
            while len(payload) < actual_len:
                chunk = conn.recv(actual_len - len(payload))
                if not chunk: break
                payload.extend(chunk)
            unmasked = bytes([payload[i] ^ mask[i % 4] for i in range(actual_len)]).decode()
            reply = f"Length verified: {len(unmasked)}"
            s_frame = bytearray([0x81, len(reply)]) + reply.encode()
            conn.sendall(s_frame)
            time.sleep(0.05)
            conn.close()
            srv.close()
        except Exception:
            pass

    th = threading.Thread(target=run_ws_server, daemon=True)
    th.start()
    time.sleep(0.05)

    source = f"""
    import "std:net:websocket"

    let ws = ws_connect("127.0.0.1", {port}, "/ext");
    print("ext ws fd:", ws);
    verify ws >= 0, "WS baglanamadi";

    let big_msg = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
    ws_send(ws, big_msg);
    let reply = ws_recv(ws);
    print("ext reply:", reply);
    verify reply == "Length verified: 164", "Uzatilmis payload dogrulanamadi";
    ws_close(ws);
    """
    try:
        res = compile_and_run(source)
        assert res.returncode == 0
        assert "ext reply: Length verified: 164" in res.stdout
    finally:
        th.join(timeout=2)

# =========================================================================
# 6. ENTEGRASYON VE LLVM BACKEND TESTLERİ
# =========================================================================

def test_std_packet2_all_imports():
    source = """
    import "std:net:dns"
    import "std:net:udp"
    import "std:net:http_server"
    import "std:crypto:tls"
    import "std:net:websocket"

    let ip = dns_resolve_ipv4("127.0.0.1");
    let ufd = udp_socket();
    let sfd = http_server_create(0);
    let tid = tls_connect("127.0.0.1", -1);
    let wfd = ws_connect("127.0.0.1", -1, "/");

    udp_close(ufd);
    http_server_close(sfd);

    print("Packet 2 All Imported Successfully!");
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Packet 2 All Imported Successfully!" in res.stdout

def test_std_packet2_llvm_codegen():
    source = """
    import "std:net:dns"
    import "std:net:udp"

    fn main() -> int {
        let ip = dns_resolve_ipv4("localhost");
        print("LLVM DNS:", ip);
        let ufd = udp_socket();
        print("LLVM UDP:", ufd);
        udp_close(ufd);
        return 0;
    }
    """
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    prog = parser.parse()
    resolver = ModuleResolver()
    prog = resolver.resolve(prog)
    checker = TypeChecker()
    checker.check(prog)
    gen = LLVMCodeGenerator()
    ir = gen.generate(prog)
    assert "@axiom_dns_resolve_ipv4" in ir
    assert "@axiom_udp_socket" in ir
    assert "@axiom_udp_close" in ir

    with tempfile.NamedTemporaryFile(suffix=".ll", mode="w", delete=False) as ll_f, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_f:
        ll_path = ll_f.name
        bin_path = bin_f.name
        ll_f.write(ir)

    try:
        runtime_c = str(Path(__file__).resolve().parent.parent / "axiom" / "axiom_llvm_runtime.c")
        cmd = ["clang", "-O2", ll_path, runtime_c, "-pthread", "-lssl", "-lcrypto", "-ldl", "-lm", "-o", bin_path]
        res_cc = subprocess.run(cmd, capture_output=True, text=True)
        assert res_cc.returncode == 0, f"Clang Error: {res_cc.stderr}"

        res_exec = subprocess.run([bin_path], capture_output=True, text=True, timeout=5)
        assert res_exec.returncode == 0
        assert "LLVM DNS: 127.0.0.1" in res_exec.stdout
        assert "LLVM UDP:" in res_exec.stdout
    finally:
        if os.path.exists(ll_path): os.remove(ll_path)
        if os.path.exists(bin_path): os.remove(bin_path)

def test_std_tls_close_safe():
    source = """
    import "std:crypto:tls"

    tls_close(-1);
    tls_close(999);
    print("Safe TLS close passed");
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Safe TLS close passed" in res.stdout

def test_std_ws_close_safe():
    source = """
    import "std:net:websocket"

    ws_close(-1);
    print("Safe WS close passed");
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "Safe WS close passed" in res.stdout

def test_std_udp_multiple_packets():
    port = get_free_port()
    source = f"""
    import "std:net:udp"

    fn server_worker(p: int) -> int {{
        let sfd = udp_bind(p);
        if sfd < 0 {{ return 1; }}
        let m1 = udp_recvfrom(sfd, 1024);
        let m2 = udp_recvfrom(sfd, 1024);
        print("m1:", m1);
        print("m2:", m2);
        udp_close(sfd);
        return 0;
    }}

    fn main() -> int {{
        let p = {port};
        let th = thread_create(server_worker, p);
        sleep_ms(60);
        let cfd = udp_socket();
        if cfd >= 0 {{
            udp_sendto(cfd, "127.0.0.1", p, "PACKET_ONE");
            udp_sendto(cfd, "127.0.0.1", p, "PACKET_TWO");
            udp_close(cfd);
        }}
        thread_join(th);
        return 0;
    }}
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "m1: PACKET_ONE" in res.stdout
    assert "m2: PACKET_TWO" in res.stdout

def test_std_http_server_multiple_requests():
    port = get_free_port()
    source = f"""
    import "std:net:http_server"

    fn http_worker(p: int) -> int {{
        let sfd = http_server_create(p);
        if sfd < 0 {{ return 1; }}
        let c1 = http_server_accept(sfd);
        if c1 >= 0 {{
            http_server_send_response(c1, 200, "text/plain", "RESP_1");
        }}
        let c2 = http_server_accept(sfd);
        if c2 >= 0 {{
            http_server_send_response(c2, 200, "text/plain", "RESP_2");
        }}
        http_server_close(sfd);
        return 0;
    }}

    fn main() -> int {{
        let p = {port};
        let th = thread_create(http_worker, p);
        sleep_ms(60);

        // Sunucu thread'i baglanana kadar kisa araliklarla dene (flaky onlemi).
        let mut cl1 = -1;
        let mut tries1 = 0;
        while (cl1 < 0 and tries1 < 40) {{
            cl1 = tcp_connect("127.0.0.1", p);
            if (cl1 < 0) {{ sleep_ms(25); }}
            tries1 = tries1 + 1;
        }}
        if cl1 >= 0 {{
            tcp_send(cl1, "GET /one HTTP/1.1\\r\\n\\r\\n");
            let r1 = tcp_recv(cl1, 1024);
            print("c1 got:", r1);
            socket_close(cl1);
        }}

        let mut cl2 = -1;
        let mut tries2 = 0;
        while (cl2 < 0 and tries2 < 40) {{
            cl2 = tcp_connect("127.0.0.1", p);
            if (cl2 < 0) {{ sleep_ms(25); }}
            tries2 = tries2 + 1;
        }}
        if cl2 >= 0 {{
            tcp_send(cl2, "GET /two HTTP/1.1\\r\\n\\r\\n");
            let r2 = tcp_recv(cl2, 1024);
            print("c2 got:", r2);
            socket_close(cl2);
        }}

        thread_join(th);
        return 0;
    }}
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "RESP_1" in res.stdout
    assert "RESP_2" in res.stdout

def test_std_http_server_no_content_204():
    port = get_free_port()
    source = f"""
    import "std:net:http_server"

    fn http_worker(p: int) -> int {{
        let sfd = http_server_create(p);
        if sfd < 0 {{ return 1; }}
        let cfd = http_server_accept(sfd);
        if cfd >= 0 {{
            http_server_send_response(cfd, 204, "text/plain", "");
        }}
        http_server_close(sfd);
        return 0;
    }}

    fn main() -> int {{
        let p = {port};
        let th = thread_create(http_worker, p);
        sleep_ms(60);
        let client = tcp_connect("127.0.0.1", p);
        if client >= 0 {{
            tcp_send(client, "DELETE /item HTTP/1.1\\r\\n\\r\\n");
            let resp = tcp_recv(client, 1024);
            print("Resp 204:", resp);
            socket_close(client);
        }}
        thread_join(th);
        return 0;
    }}
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "HTTP/1.1 204 No Content" in res.stdout

def test_std_dns_resolve_ipv6_loopback_string():
    source = """
    import "std:net:dns"

    let res = dns_resolve_ipv6("::1");
    print("res ipv6:", res);
    verify res == "::1", "IPv6 ::1 cozulmeli";
    """
    res = compile_and_run(source)
    assert res.returncode == 0
    assert "res ipv6: ::1" in res.stdout


