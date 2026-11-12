"""
Axiom - HTTP/1.1 istemcisi (P1-01)

Gerçek bir yerel HTTP sunucusuna karşı: Content-Length, chunked,
yönlendirme takibi, büyük yanıt (tek recv ile kesilmez), döngü tespiti.
"""
import os
import socket
import socketserver
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from tests.support_env import require_network
AXIOM = ROOT / "bin" / "axiom"


# --- Minimal HTTP/1.1 test sunucusu (harici bağımlılık yok) ---

class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        req = b""
        while b"\r\n\r\n" not in req:
            chunk = self.rfile.readline()
            if not chunk:
                return
            req += chunk
        line = req.split(b"\r\n", 1)[0].decode(errors="replace")
        parts = line.split(" ")
        path = parts[1] if len(parts) > 1 else "/"

        if path == "/chunked":
            self.wfile.write(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Type: text/plain\r\n\r\n")
            for part in (b"hello ", b"chunked ", b"world"):
                self.wfile.write(f"{len(part):x}\r\n".encode() + part + b"\r\n")
            self.wfile.write(b"0\r\n\r\n")
        elif path == "/redirect":
            self.wfile.write(b"HTTP/1.1 302 Found\r\nLocation: /final\r\nContent-Length: 0\r\n\r\n")
        elif path == "/final":
            self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Length: 12\r\n\r\nfinal-target")
        elif path == "/loop":
            self.wfile.write(b"HTTP/1.1 302 Found\r\nLocation: /loop\r\nContent-Length: 0\r\n\r\n")
        elif path == "/big":
            self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Length: 300000\r\n\r\n" + b"X" * 300000)
        else:
            self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nok")
        self.wfile.flush()


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


@pytest.fixture(scope="module")
def server():
    srv = _Server(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.02)
    yield type("S", (), {"port": port})()
    srv.shutdown()
    srv.server_close()


def _run(src: str, backend: str = "c"):
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    out = path + ".bin"
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        args = [str(AXIOM), "build", path, "-o", out]
        if backend == "llvm":
            args.insert(2, "--backend=llvm")
        b = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
        assert b.returncode == 0, b.stdout + b.stderr
        return subprocess.run([out], capture_output=True, text=True, timeout=120)
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)


def _program(port: int) -> str:
    return f'''
import "std/core/error"
import "std/net/http"

fn main() -> Result<int, str> {{
    let r1 = http_request("127.0.0.1", {port}, "GET", "/", 3000)?
    print("status:", r1.status)
    print("body:", r1.body)

    let r2 = http_request("127.0.0.1", {port}, "GET", "/chunked", 3000)?
    print("chunked:", r2.body)

    let r3 = http_request("127.0.0.1", {port}, "GET", "/redirect", 3000)?
    print("final:", r3.body, "redirects:", r3.redirects)

    let r4 = http_request("127.0.0.1", {port}, "GET", "/big", 5000)?
    print("big:", len(r4.body))

    let r5 = http_request("127.0.0.1", {port}, "GET", "/loop", 2000)
    print("loop_ok:", r5.is_ok)

    let bad = http_request("", {port}, "GET", "/", 1000)
    print("empty_host:", bad.error)
    let badport = http_request("127.0.0.1", 0, "GET", "/", 1000)
    print("bad_port:", badport.error)
    return result_ok<int>(0)
}}
'''


EXPECTED = [
    "status: 200",
    "body: ok",
    "chunked: hello chunked world",
    "final: final-target redirects: 1",
    "big: 300000",
    "loop_ok: false",
    "empty_host: bos host",
    "bad_port: gecersiz port: 0",
]


@pytest.mark.parametrize("backend", ["c", "llvm"])
@require_network
def test_http_client(server, backend):
    out = _run(_program(server.port), backend)
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.splitlines() == EXPECTED


def test_http_chunked_decoder_edge_cases():
    src = """
fn main() -> int {
    print("A[" + http_chunked_decode("5\\r\\nhello\\r\\n0\\r\\n\\r\\n") + "]")
    print("B[" + http_chunked_decode("3;ext=1\\r\\nabc\\r\\n0\\r\\n\\r\\n") + "]")
    print("C[" + http_chunked_decode("zz\\r\\n") + "]")
    print("D[" + http_chunked_decode("") + "]")
    return 0
}
"""
    out = _run(src)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == ["A[hello]", "B[abc]", "C[]", "D[]"]


def test_http_header_value_case_insensitive():
    src = """
fn main() -> int {
    let r = "HTTP/1.1 200 OK\\r\\nContent-Length: 42\\r\\nX-Test: abc\\r\\n\\r\\nbody"
    print("A[" + http_header_value(r, "content-length") + "]")
    print("B[" + http_header_value(r, "X-TEST") + "]")
    print("C[" + http_header_value(r, "yok") + "]")
    return 0
}
"""
    out = _run(src)
    assert out.stdout.splitlines() == ["A[42]", "B[abc]", "C[]"]
