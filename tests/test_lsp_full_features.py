"""
Axiom - LSP tam yetenek seti (P2-05)

Kapsam:
  - references / prepareRename / rename
  - semanticTokens/full (legend + delta kodlama)
  - signatureHelp (yerel fonksiyon + builtin + aktif parametre)
  - codeAction (yazım düzeltmesi, `let mut` hızlı düzeltmesi)
  - documentFormatting
  - protokol düzeyi (bin/axiom-lsp) uçtan uca akış
"""
import json
import re
import subprocess
from pathlib import Path

import pytest

from axiom.lsp import AxiomLanguageServer, SEMANTIC_TOKEN_TYPES

ROOT = Path(__file__).resolve().parent.parent
LSP = ROOT / "bin" / "axiom-lsp"

URI = "file:///test.ax"

SOURCE = '''/// Adds two numbers.
fn add(a: int, b: int) -> int {
    return a + b
}

struct Point {
    x: int,
    y: int
}

fn main() -> int {
    let p = Point { x: 1, y: 2 }
    let total = add(1, 2)
    let other = add(total, 3)
    # add burada yorum icinde
    let s = "add metin icinde"
    print(other)
    return 0
}
'''


class _Capture:
    def __init__(self):
        self.data = b""

    def write(self, data):
        self.data += data

    def flush(self):
        pass


def _server_with(text=SOURCE):
    srv = AxiomLanguageServer()
    srv.out_stream = _Capture()
    srv.handle_message({
        "jsonrpc": "2.0", "id": 1, "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": URI, "text": text}},
    })
    srv.out_stream = _Capture()
    return srv


def _diagnostics(srv, text):
    cap = _Capture()
    srv.out_stream = cap
    srv.publish_diagnostics(URI, text)
    payload = cap.data.decode()
    body = payload[payload.index("\r\n\r\n") + 4:]
    return json.loads(body)["params"]["diagnostics"]


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

def test_initialize_advertises_all_new_capabilities():
    srv = AxiomLanguageServer()
    srv.out_stream = _Capture()
    caps = srv.handle_message({
        "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}
    })["result"]["capabilities"]

    assert caps["referencesProvider"] is True
    assert caps["renameProvider"]["prepareProvider"] is True
    assert caps["documentFormattingProvider"] is True
    assert caps["codeActionProvider"]["codeActionKinds"] == ["quickfix"]
    assert caps["signatureHelpProvider"]["triggerCharacters"] == ["(", ","]
    legend = caps["semanticTokensProvider"]["legend"]["tokenTypes"]
    assert legend == SEMANTIC_TOKEN_TYPES
    assert caps["semanticTokensProvider"]["full"] is True


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------

def test_references_include_declaration_and_calls():
    srv = _server_with()
    refs = srv.compute_references(URI, 1, 4)  # fn add
    starts = [(r["range"]["start"]["line"], r["range"]["start"]["character"]) for r in refs]
    assert starts == [(1, 3), (12, 16), (13, 16)]
    assert all(r["uri"] == URI for r in refs)


def test_references_exclude_declaration_on_request():
    srv = _server_with()
    refs = srv.compute_references(URI, 1, 4, include_declaration=False)
    assert len(refs) == 2
    assert all(r["range"]["start"]["line"] != 1 for r in refs)


def test_references_ignore_comments_and_strings():
    srv = _server_with()
    refs = srv.compute_references(URI, 1, 4)
    lines = {r["range"]["start"]["line"] for r in refs}
    # 14. satır yorum, 15. satır string — ikisi de eşleşmemeli
    assert 14 not in lines
    assert 15 not in lines


def test_references_on_unknown_word_empty():
    srv = _server_with()
    assert srv.compute_references(URI, 10, 0) == []


# ---------------------------------------------------------------------------
# Rename
# ---------------------------------------------------------------------------

def test_prepare_rename_returns_range_and_placeholder():
    srv = _server_with()
    out = srv.compute_prepare_rename(URI, 12, 16)
    assert out["placeholder"] == "add"
    assert out["range"]["start"] == {"line": 12, "character": 16}


def test_prepare_rename_rejects_keyword_and_outside_symbol():
    srv = _server_with()
    assert srv.compute_prepare_rename(URI, 1, 0) is None      # 'fn'
    assert srv.compute_prepare_rename(URI, 8, 0) is None      # boş satır


def test_rename_produces_edits_for_all_occurrences():
    srv = _server_with()
    out = srv.compute_rename(URI, 12, 16, "topla")
    edits = out["changes"][URI]
    assert len(edits) == 3
    assert all(e["newText"] == "topla" for e in edits)


def test_rename_rejects_invalid_or_keyword_new_name():
    srv = _server_with()
    assert srv.compute_rename(URI, 12, 16, "fn") is None
    assert srv.compute_rename(URI, 12, 16, "1bad") is None
    assert srv.compute_rename(URI, 12, 16, "has space") is None


# ---------------------------------------------------------------------------
# Semantic tokens
# ---------------------------------------------------------------------------

def _decode(data):
    """LSP delta kodlamasını mutlak (line, char, len, type) listesine çevirir."""
    out = []
    line = char = 0
    for i in range(0, len(data), 5):
        dl, dc, length, ttype, _mods = data[i:i + 5]
        line += dl
        char = char + dc if dl == 0 else dc
        out.append((line, char, length, SEMANTIC_TOKEN_TYPES[ttype]))
    return out


def test_semantic_tokens_are_well_formed():
    srv = _server_with()
    data = srv.compute_semantic_tokens(URI)
    assert data and len(data) % 5 == 0
    toks = _decode(data)
    assert toks == sorted(toks, key=lambda t: (t[0], t[1]))
    # Aynı satırda çakışan token olmamalı
    for a, b in zip(toks, toks[1:]):
        if a[0] == b[0]:
            assert a[1] + a[2] <= b[1]


def test_semantic_tokens_classify_symbols():
    srv = _server_with()
    toks = _decode(srv.compute_semantic_tokens(URI))
    kinds = {(t[0], t[1]): t[3] for t in toks}

    assert kinds[(0, 0)] == "comment"        # /// Adds two numbers.
    assert kinds[(1, 0)] == "keyword"        # fn
    assert kinds[(1, 3)] == "function"       # add
    assert kinds[(2, 4)] == "keyword"        # return
    assert kinds[(5, 7)] == "struct"         # Point
    assert any(k == "number" for k in kinds.values())
    assert any(k == "string" for k in kinds.values())
    assert any(k == "operator" for k in kinds.values())


def test_semantic_tokens_empty_document():
    srv = _server_with("")
    assert srv.compute_semantic_tokens(URI) == []


# ---------------------------------------------------------------------------
# Signature help
# ---------------------------------------------------------------------------

def test_signature_help_local_function_active_parameter():
    srv = _server_with()
    out = srv.compute_signature_help(URI, 12, 23)  # add(1, |2)
    assert out["signatures"][0]["label"] == "fn add(a: int, b: int) -> int"
    assert out["activeParameter"] == 1
    assert out["signatures"][0]["parameters"] == [{"label": "a: int"}, {"label": "b: int"}]


def test_signature_help_first_parameter():
    srv = _server_with()
    out = srv.compute_signature_help(URI, 12, 20)  # add(|1, 2)
    assert out["activeParameter"] == 0


def test_signature_help_builtin():
    src = "fn main() -> int {\n    let n = str_sub(\"abc\", 1, 2)\n    return 0\n}\n"
    srv = _server_with(src)
    out = srv.compute_signature_help(URI, 1, 27)
    assert "str_sub" in out["signatures"][0]["label"]
    assert out["activeParameter"] == 1


def test_signature_help_outside_call_is_none():
    srv = _server_with()
    assert srv.compute_signature_help(URI, 1, 0) is None
    assert srv.compute_signature_help(URI, 8, 0) is None


# ---------------------------------------------------------------------------
# Code actions
# ---------------------------------------------------------------------------

def test_code_action_suggests_close_builtin_name():
    src = 'fn main() -> int {\n    let x = str_lenn("abc")\n    return 0\n}\n'
    srv = _server_with(src)
    diags = _diagnostics(srv, src)
    actions = srv.compute_code_actions(URI, {}, diags)
    assert len(actions) == 1
    assert actions[0]["kind"] == "quickfix"
    edit = actions[0]["edit"]["changes"][URI][0]
    assert edit["newText"] == "str_len"
    # Aralık tam olarak tanımlayıcıyı kapsamalı
    assert edit["range"]["start"] == {"line": 1, "character": 12}
    assert edit["range"]["end"] == {"line": 1, "character": 20}


def test_code_action_adds_mut_for_immutable_assignment():
    src = "fn main() -> int {\n    let x = 1\n    x = 2\n    return x\n}\n"
    srv = _server_with(src)
    diags = _diagnostics(srv, src)
    actions = srv.compute_code_actions(URI, {}, diags)
    assert len(actions) == 1
    edit = actions[0]["edit"]["changes"][URI][0]
    assert edit["newText"] == "mut "
    assert edit["range"]["start"]["line"] == 1
    assert edit["range"]["start"]["character"] == 4


def test_code_action_empty_for_clean_code():
    src = "fn main() -> int {\n    let x = 1\n    return x\n}\n"
    srv = _server_with(src)
    assert srv.compute_code_actions(URI, {}, _diagnostics(srv, src)) == []


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def test_formatting_returns_single_edit_when_needed():
    src = "fn main() -> int {\n   let x=1\n      return x\n}\n"
    srv = _server_with(src)
    edits = srv.compute_formatting(URI)
    assert len(edits) == 1
    assert edits[0]["newText"] == "fn main() -> int {\n    let x = 1\n    return x\n}\n"
    assert edits[0]["range"]["start"] == {"line": 0, "character": 0}


def test_formatting_no_edit_when_already_formatted():
    src = "fn main() -> int {\n    return 0\n}\n"
    srv = _server_with(src)
    assert srv.compute_formatting(URI) == []


def test_formatting_empty_document():
    srv = _server_with("")
    assert srv.compute_formatting(URI) == []


# ---------------------------------------------------------------------------
# Protokol düzeyi (gerçek ikili)
# ---------------------------------------------------------------------------

def _framed(messages):
    payload = b""
    for m in messages:
        body = json.dumps(m).encode()
        payload += f"Content-Length: {len(body)}\r\n\r\n".encode() + body
    return payload


def _parse_all(out: str):
    responses = []
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
    return responses


def test_protocol_end_to_end_new_methods():
    payload = _framed([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "initialized", "params": {}},
        {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
            "textDocument": {"uri": URI, "languageId": "axiom", "version": 1, "text": SOURCE}}},
        {"jsonrpc": "2.0", "id": 2, "method": "textDocument/references", "params": {
            "textDocument": {"uri": URI}, "position": {"line": 1, "character": 4},
            "context": {"includeDeclaration": True}}},
        {"jsonrpc": "2.0", "id": 3, "method": "textDocument/prepareRename", "params": {
            "textDocument": {"uri": URI}, "position": {"line": 12, "character": 16}}},
        {"jsonrpc": "2.0", "id": 4, "method": "textDocument/rename", "params": {
            "textDocument": {"uri": URI}, "position": {"line": 12, "character": 16},
            "newName": "topla"}},
        {"jsonrpc": "2.0", "id": 5, "method": "textDocument/semanticTokens/full", "params": {
            "textDocument": {"uri": URI}}},
        {"jsonrpc": "2.0", "id": 6, "method": "textDocument/signatureHelp", "params": {
            "textDocument": {"uri": URI}, "position": {"line": 12, "character": 23}}},
        {"jsonrpc": "2.0", "id": 7, "method": "textDocument/formatting", "params": {
            "textDocument": {"uri": URI}, "options": {"tabSize": 4, "insertSpaces": True}}},
        {"jsonrpc": "2.0", "id": 8, "method": "shutdown", "params": {}},
        {"jsonrpc": "2.0", "method": "exit", "params": {}},
    ])
    res = subprocess.run([str(LSP)], input=payload, capture_output=True, timeout=60)
    by_id = {r["id"]: r for r in _parse_all(res.stdout.decode()) if "id" in r}

    assert [r["range"]["start"]["line"] for r in by_id[2]["result"]] == [1, 12, 13]
    assert by_id[3]["result"]["placeholder"] == "add"
    assert len(by_id[4]["result"]["changes"][URI]) == 3
    data = by_id[5]["result"]["data"]
    assert len(data) % 5 == 0 and len(data) > 0
    assert by_id[6]["result"]["signatures"][0]["label"].startswith("fn add(")
    assert by_id[7]["result"] == []  # SOURCE zaten biçimli
    assert res.returncode == 0


def test_protocol_unknown_method_still_errors():
    payload = _framed([
        {"jsonrpc": "2.0", "id": 1, "method": "textDocument/unknownThing", "params": {}},
        {"jsonrpc": "2.0", "method": "exit", "params": {}},
    ])
    res = subprocess.run([str(LSP)], input=payload, capture_output=True, timeout=60)
    responses = _parse_all(res.stdout.decode())
    assert responses[0]["error"]["code"] == -32601
