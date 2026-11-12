"""
Axiom Programming Language (λx) - Language Server Protocol Tests (axiom-lsp / axiom lsp)
Faz 5.2 Kapsamlı Test Suiti:
- JSON-RPC 2.0 protokol mesajlaşması ve Content-Length çerçeveleme
- initialize, shutdown ve lifecycle metodları
- didOpen, didChange, didSave ve didClose belge senkronizasyonu
- publishDiagnostics: Lexer, Parser ve Tip Denetimi (Checker) hatalarının yayınlanması ve temizlenmesi
- completion: Anahtar kelimeler, standart kütüphane fonksiyonları ve AST sembol önerileri
- definition: Sembol tanımına gitme (Go to Definition)
- hover: Fonksiyon imzaları, sözleşmeler ve tip ipuçları
- bin/axiom-lsp ikili dosyası ile canlı stdio testi
"""

import sys
import json
import subprocess
from pathlib import Path
import pytest

from axiom.lsp import AxiomLanguageServer

AXIOM_LSP_BIN = Path(__file__).resolve().parent.parent / "bin" / "axiom-lsp"


def test_lsp_initialize_and_capabilities():
    server = AxiomLanguageServer()
    resp = server.handle_message({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    })
    assert resp is not None
    assert resp["id"] == 1
    caps = resp["result"]["capabilities"]
    assert caps["textDocumentSync"] == 1
    assert caps["hoverProvider"] is True
    assert caps["definitionProvider"] is True
    assert caps["completionProvider"]["resolveProvider"] is False
    assert resp["result"]["serverInfo"]["name"] == "axiom-lsp"


def test_lsp_shutdown_and_exit():
    server = AxiomLanguageServer()
    resp = server.handle_message({
        "jsonrpc": "2.0",
        "id": 10,
        "method": "shutdown",
        "params": {}
    })
    assert resp["result"] is None
    assert server.is_shutdown is True


def test_lsp_diagnostics_on_syntax_and_semantic_errors():
    class DummyStream:
        def __init__(self):
            self.notifications = []
        def write(self, data):
            if b"publishDiagnostics" in data:
                # Başlıktan sonraki JSON'ı çıkar
                parts = data.split(b"\r\n\r\n")
                if len(parts) > 1:
                    self.notifications.append(json.loads(parts[1].decode("utf-8")))
        def flush(self):
            pass

    out_stream = DummyStream()
    server = AxiomLanguageServer(out_stream=out_stream)

    # 1. Parser Hatası
    bad_syntax = "fn bad() -> void { let x = \n }"
    server.handle_message({
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": "file:///bad.ax", "text": bad_syntax}}
    })
    assert len(out_stream.notifications) == 1
    diag = out_stream.notifications[-1]["params"]["diagnostics"]
    assert len(diag) > 0
    assert diag[0]["severity"] == 1
    assert diag[0]["source"] == "axiom-parser"

    # 2. Tip Hatası (Semantic Error)
    bad_types = """fn type_error() -> void {
    let a: int = "metin"
}
"""
    server.handle_message({
        "jsonrpc": "2.0",
        "method": "textDocument/didChange",
        "params": {
            "textDocument": {"uri": "file:///bad.ax", "version": 2},
            "contentChanges": [{"text": bad_types}]
        }
    })
    assert len(out_stream.notifications) == 2
    diag2 = out_stream.notifications[-1]["params"]["diagnostics"]
    assert len(diag2) > 0
    assert diag2[0]["source"] == "axiom-checker"

    # 3. Hatanın Düzeltilmesi (Boş Diagnostics Listesi)
    clean_code = """fn valid_calc(x: int) -> int {
    return x * 2
}
"""
    server.handle_message({
        "jsonrpc": "2.0",
        "method": "textDocument/didChange",
        "params": {
            "textDocument": {"uri": "file:///bad.ax", "version": 3},
            "contentChanges": [{"text": clean_code}]
        }
    })
    assert len(out_stream.notifications) == 3
    diag3 = out_stream.notifications[-1]["params"]["diagnostics"]
    assert len(diag3) == 0  # Hatalar tamamen temizlendi


def test_lsp_completion_and_filtering():
    server = AxiomLanguageServer()
    code = """struct PacketHeader {
    magic: int,
    length: int
}

fn process_packet(raw_size: int) -> int {
    let base_val = 100
    return raw_size + base_val
}
"""
    server.handle_message({
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": "file:///pkg.ax", "text": code}}
    })

    # Boş alanda tamamlama: anahtar kelimeler, yerel semboller ve yerleşik fonksiyonlar gelmeli
    comp = server.handle_message({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "textDocument/completion",
        "params": {
            "textDocument": {"uri": "file:///pkg.ax"},
            "position": {"line": 0, "character": 0}
        }
    })
    items = comp["result"]["items"]
    labels = {it["label"] for it in items}
    assert "PacketHeader" in labels
    assert "process_packet" in labels
    assert "print" in labels
    assert "fn" in labels
    assert "struct" in labels


def test_lsp_hover_information():
    server = AxiomLanguageServer()
    code = """struct UserRecord {
    id: int,
    active: bool
}

fn query_user(user_id: int) -> int
requires user_id > 0
ensures return >= 0
{
    let count = user_id + 1
    return count
}
"""
    server.handle_message({
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": "file:///app.ax", "text": code}}
    })

    # 1. Fonksiyon hover testi (sözleşmelerle birlikte)
    hov_fn = server.handle_message({
        "jsonrpc": "2.0",
        "id": 6,
        "method": "textDocument/hover",
        "params": {
            "textDocument": {"uri": "file:///app.ax"},
            "position": {"line": 5, "character": 4} # On 'query_user'
        }
    })
    md_val = hov_fn["result"]["contents"]["value"]
    assert "fn query_user(user_id: int) -> int" in md_val
    assert "requires" in md_val
    assert "ensures" in md_val

    # 2. Struct hover testi
    hov_st = server.handle_message({
        "jsonrpc": "2.0",
        "id": 7,
        "method": "textDocument/hover",
        "params": {
            "textDocument": {"uri": "file:///app.ax"},
            "position": {"line": 0, "character": 9} # On 'UserRecord'
        }
    })
    st_val = hov_st["result"]["contents"]["value"]
    assert "struct UserRecord" in st_val
    assert "id: int" in st_val

    # 3. Builtin hover testi
    hov_builtin = server.handle_message({
        "jsonrpc": "2.0",
        "id": 8,
        "method": "textDocument/hover",
        "params": {
            "textDocument": {"uri": "file:///app.ax"},
            "position": {"line": 10, "character": 12} # Fake hover on tcp_connect
        }
    })
    # tcp_connect hover kontrolü için kod satırına tcp_connect ekleyip deneyelim
    server.documents["file:///app.ax"] = "tcp_connect"
    hov_tcp = server.handle_message({
        "jsonrpc": "2.0",
        "id": 9,
        "method": "textDocument/hover",
        "params": {
            "textDocument": {"uri": "file:///app.ax"},
            "position": {"line": 0, "character": 3}
        }
    })
    assert "fn tcp_connect(host: str, port: int) -> int" in hov_tcp["result"]["contents"]["value"]


def test_lsp_go_to_definition():
    server = AxiomLanguageServer()
    code = """struct SecurityContext {
    token: int
}

fn execute(ctx_id: int) -> int {
    let target_key = ctx_id * 10
    return target_key
}
"""
    server.handle_message({
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": "file:///def_test.ax", "text": code}}
    })

    # 'execute' tanımına git
    defn_fn = server.handle_message({
        "jsonrpc": "2.0",
        "id": 11,
        "method": "textDocument/definition",
        "params": {
            "textDocument": {"uri": "file:///def_test.ax"},
            "position": {"line": 4, "character": 4} # On 'execute'
        }
    })
    assert defn_fn["result"]["range"]["start"]["line"] == 4

    # 'SecurityContext' tanımına git
    defn_st = server.handle_message({
        "jsonrpc": "2.0",
        "id": 12,
        "method": "textDocument/definition",
        "params": {
            "textDocument": {"uri": "file:///def_test.ax"},
            "position": {"line": 0, "character": 10}
        }
    })
    assert defn_st["result"]["range"]["start"]["line"] == 0

    # 'target_key' değişken tanımına git
    defn_var = server.handle_message({
        "jsonrpc": "2.0",
        "id": 13,
        "method": "textDocument/definition",
        "params": {
            "textDocument": {"uri": "file:///def_test.ax"},
            "position": {"line": 6, "character": 12}
        }
    })
    assert defn_var["result"]["range"]["start"]["line"] == 5


def test_lsp_process_stdio_live():
    proc = subprocess.Popen(
        [str(AXIOM_LSP_BIN)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    init_msg = {
        "jsonrpc": "2.0",
        "id": 100,
        "method": "initialize",
        "params": {}
    }
    body = json.dumps(init_msg).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
    proc.stdin.write(header + body)
    proc.stdin.flush()

    line1 = proc.stdout.readline().decode("utf-8")
    line2 = proc.stdout.readline().decode("utf-8")
    length = int(line1.split(":")[1].strip())
    resp_body = proc.stdout.read(length).decode("utf-8")
    parsed = json.loads(resp_body)
    assert parsed["id"] == 100
    assert parsed["result"]["capabilities"]["textDocumentSync"] == 1

    proc.terminate()
    proc.wait()
