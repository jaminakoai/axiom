"""
Axiom - LSP yaşam döngüsü ve dizi oluşturma builtin'leri

Her ikisi de v0.5'te çalışıyordu ama testsizdi:
  - LSP: didSave/didClose/initialized/exit/bilinmeyen metod (-32601)
  - array_create_int/str, array_push_int/str
"""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
LSP = ROOT / "bin" / "axiom-lsp"


def _lsp_session(messages):
    payload = b""
    for m in messages:
        body = json.dumps(m).encode()
        payload += f"Content-Length: {len(body)}\r\n\r\n".encode() + body
    res = subprocess.run([str(LSP)], input=payload, capture_output=True, timeout=60)
    responses = []
    out = res.stdout.decode(errors="replace")
    pos = 0
    while True:
        m = re.search(r"Content-Length: (\d+)\r\n\r\n", out[pos:])
        if not m:
            break
        start = pos + m.end()
        length = int(m.group(1))
        try:
            responses.append(json.loads(out[start:start + length]))
        except json.JSONDecodeError:
            pass
        pos = start + length
    return res.returncode, responses


def test_lsp_full_lifecycle():
    uri = "file:///tmp/axiom_lsp_lifecycle.ax"
    code, responses = _lsp_session([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"capabilities": {}}},
        {"jsonrpc": "2.0", "method": "initialized", "params": {}},
        {"jsonrpc": "2.0", "method": "textDocument/didOpen",
         "params": {"textDocument": {"uri": uri, "languageId": "axiom",
                                     "version": 1,
                                     "text": "fn main() -> int { return 0 }\n"}}},
        {"jsonrpc": "2.0", "method": "textDocument/didSave",
         "params": {"textDocument": {"uri": uri}}},
        {"jsonrpc": "2.0", "method": "textDocument/didClose",
         "params": {"textDocument": {"uri": uri}}},
        {"jsonrpc": "2.0", "id": 2, "method": "bilinmeyen/metod", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
        {"jsonrpc": "2.0", "method": "exit"},
    ])
    assert code == 0, "shutdown sonrasi exit 0 dondurmeli"

    by_id = {r.get("id"): r for r in responses}
    assert 1 in by_id and by_id[1]["result"]["capabilities"]["hoverProvider"] is True
    assert 2 in by_id and by_id[2]["error"]["code"] == -32601
    assert 3 in by_id and by_id[3]["result"] is None


def test_lsp_publishes_diagnostics_for_broken_document():
    uri = "file:///tmp/axiom_lsp_broken.ax"
    _, responses = _lsp_session([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"capabilities": {}}},
        {"jsonrpc": "2.0", "method": "textDocument/didOpen",
         "params": {"textDocument": {"uri": uri, "languageId": "axiom", "version": 1,
                                     "text": "fn main() -> int { let x: int = \"abc\" }\n"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
    ])
    diags = [r for r in responses if r.get("method") == "textDocument/publishDiagnostics"]
    assert diags, "bozuk belge icin diagnostic yayinlanmali"
    assert diags[0]["params"]["diagnostics"], "tanilama listesi bos olmamali"


# --------------------------------------------------------------------------
# Dizi oluşturma builtin'leri
# --------------------------------------------------------------------------

def _run(src: str):
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    out = path + ".bin"
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        b = subprocess.run([str(AXIOM), "build", path, "-o", out],
                           capture_output=True, text=True, timeout=240, env=env)
        assert b.returncode == 0, b.stdout + b.stderr
        return subprocess.run([out], capture_output=True, text=True, timeout=120)
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)


@pytest.mark.parametrize("expr,expected", [
    ("array_create_int(5)", "5"),
    ("array_create_str(3)", "3"),
    ("array_push_int(array_create_int(2), 7)", "3"),
    ("array_push_str(array_create_str(2), \"x\")", "3"),
])
def test_array_factory_builtins(expr, expected):
    out = _run(f"fn main() -> int {{\n    let a = {expr}\n    print(len(a))\n    return 0\n}}\n")
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == expected


def test_array_create_is_zero_initialized():
    out = _run("""
fn main() -> int {
    let a = array_create_int(3)
    print(a[0], a[1], a[2])
    return 0
}
""")
    assert out.stdout.strip() == "0 0 0"
