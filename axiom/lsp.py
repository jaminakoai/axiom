"""
Axiom Programming Language (λx) - Language Server Protocol (LSP Server)
Standart JSON-RPC 2.0 tabanlı Dil Sunucusu (axiom-lsp / axiom lsp).
VS Code, Neovim, Emacs ve diğer LSP istemcileri için tam entegrasyon:
- Diagnostics (Anlık Lexer, Parser ve Tip Denetimi hataları)
- Completion (Anahtar kelimeler, standart kütüphane fonksiyonları ve yerel semboller)
- Hover (Fonksiyon imzaları, sözleşmeler ve tip ipuçları)
- Definition (Sembol tanımına gitme - Go to Definition)
- References / Rename (Tüm kullanımlar, güvenli yeniden adlandırma)
- Code Actions (Yazım düzeltmesi, `let mut` quick fix)
- Formatting (Kanonik biçimlendirici)
- Semantic Tokens (Sözdizimsel renklendirme)
- Signature Help (Parametre ipuçları ve aktif parametre)
"""

import sys
import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from axiom.lexer import Lexer, LexerError, KEYWORDS
from axiom.parser import Parser, ParserError
from axiom.checker import TypeChecker, SemanticError, BUILTIN_FUNCTIONS
from axiom.ast_nodes import (
    Program, Stmt, FunctionDecl, StructDecl, LetDecl, Param, Block, IfStmt, WhileStmt, ForRangeStmt
)

# LSP CompletionItemKind Constants
KIND_TEXT = 1
KIND_METHOD = 2
KIND_FUNCTION = 3
KIND_CONSTRUCTOR = 4
KIND_FIELD = 5
KIND_VARIABLE = 6
KIND_CLASS = 7
KIND_INTERFACE = 8
KIND_MODULE = 9
KIND_PROPERTY = 10
KIND_KEYWORD = 14
KIND_SNIPPET = 15
KIND_STRUCT = 22

# LSP DiagnosticSeverity Constants
SEVERITY_ERROR = 1
SEVERITY_WARNING = 2
SEVERITY_INFO = 3
SEVERITY_HINT = 4

AXIOM_KEYWORDS = sorted(list(KEYWORDS | {
    "int", "float", "bool", "str", "void", "invariant", "defer", "requires", "ensures", "as"
}))

# LSP semantic token legend (index = tokenType)
SEMANTIC_TOKEN_TYPES = [
    "keyword", "type", "function", "struct", "parameter", "variable",
    "property", "number", "string", "comment", "operator", "namespace",
]
_SEM_KEYWORD_TYPES = {
    'FN', 'LET', 'MUT', 'IF', 'ELSE', 'WHILE', 'FOR', 'IN', 'RETURN',
    'VERIFY', 'REQUIRES', 'ENSURES', 'TRUE', 'FALSE', 'AND', 'OR', 'NOT',
    'STRUCT', 'IMPORT', 'BREAK', 'CONTINUE', 'DEFER', 'INVARIANT', 'AS', 'MATCH',
    'PRINT', 'TYPEOF',
}
_SEM_OPERATOR_TYPES = {
    'ASSIGN', 'EQ', 'NEQ', 'LT', 'GT', 'LE', 'GE', 'PLUS', 'MINUS', 'STAR',
    'SLASH', 'PERCENT', 'ARROW', 'AMP', 'PIPE', 'CARET', 'TILDE', 'NOT',
    'QUESTION', 'DOTDOT', 'DOTDOTEQ', 'PLUSEQ', 'MINUSEQ', 'STAREQ',
}


def _position_to_offset(text: str, line: int, character: int) -> int:
    lines = text.splitlines(keepends=True)
    if line < 0:
        return 0
    if line >= len(lines):
        return len(text)
    return sum(len(l) for l in lines[:line]) + max(0, min(character, len(lines[line])))


def _is_identifier(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name or "")) and name not in KEYWORDS

STANDARD_BUILTINS_DOC = {
    "print": ("fn print(...) -> void", "Konsola bir veya birden fazla ifadeyi ekrana yazdırır."),
    "file_read": ("fn file_read(path: str) -> str", "Belirtilen dosyanın içeriğini UTF-8 metin olarak okur."),
    "file_write": ("fn file_write(path: str, content: str) -> int", "Belirtilen dosyaya metin yazar."),
    "file_exists": ("fn file_exists(path: str) -> bool", "Dosyanın varlığını denetler."),
    "time_now_ms": ("fn time_now_ms() -> int", "Mevcut Unix zamanını milisaniye cinsinden döner."),
    "tcp_connect": ("fn tcp_connect(host: str, port: int) -> int", "TCP soketi oluşturur ve bağlanır."),
    "tcp_send": ("fn tcp_send(sock: int, data: str) -> int", "TCP soketine veri iletir."),
    "tcp_recv": ("fn tcp_recv(sock: int, max_len: int) -> str", "TCP soketinden veri okur."),
    "socket_close": ("fn socket_close(sock: int) -> void", "Soketi kapatır."),
    "os_exec": ("fn os_exec(cmd: str) -> str", "Sistem komutu çalıştırır ve çıktısını döner."),
    "str_len": ("fn str_len(s: str) -> int", "Metnin karakter uzunluğunu döner."),
    "str_contains": ("fn str_contains(haystack: str, needle: str) -> bool", "Alt metin arama."),
    "str_starts_with": ("fn str_starts_with(s: str, prefix: str) -> bool", "Önek denetimi."),
    "str_ends_with": ("fn str_ends_with(s: str, suffix: str) -> bool", "Sonek denetimi."),
    "str_sub": ("fn str_sub(s: str, start: int, len: int) -> str", "Alt metin çıkarımı."),
    "str_to_upper_tr": ("fn str_to_upper_tr(s: str) -> str", "Türkçe uyumlu büyük harfe dönüştürme."),
    "str_to_lower_tr": ("fn str_to_lower_tr(s: str) -> str", "Türkçe uyumlu küçük harfe dönüştürme."),
    "rt_buf_create": ("fn rt_buf_create(capacity: int) -> int", "Dinamik bayt tamponu oluşturur."),
    "rt_buf_free": ("fn rt_buf_free(handle: int) -> void", "Bayt tamponunu bellekten serbest bırakır."),
    "rt_buf_len": ("fn rt_buf_len(handle: int) -> int", "Tamponun bayt boyutunu döner."),
    "rt_epoll_create": ("fn rt_epoll_create() -> int", "Epoll dosya tanıtıcısı oluşturur."),
    "tensor_create_2d": ("fn tensor_create_2d(rows: int, cols: int) -> int", "2B Tensör matrisi oluşturur."),
    "tensor_matmul": ("fn tensor_matmul(a: int, b: int) -> int", "SIMD hızlandırmalı matris çarpımı."),
}


def get_prefix_at_position(text: str, line: int, character: int) -> str:
    """Tamamlama için imlecin hemen solundaki kelime önekini döner."""
    lines = text.splitlines()
    if line < 0 or line >= len(lines):
        return ""
    cur_line = lines[line]
    if character <= 0 or character > len(cur_line):
        return ""
    left = character
    while left > 0 and (cur_line[left - 1].isalnum() or cur_line[left - 1] == '_'):
        left -= 1
    return cur_line[left:character]


def get_word_at_position(text: str, line: int, character: int) -> str:
    """Verilen 0-tabanlı satır ve karakter indisindeki sembol kelimesini ayıklar."""
    lines = text.splitlines()
    if line < 0 or line >= len(lines):
        return ""
    cur_line = lines[line]
    if character < 0 or character > len(cur_line):
        return ""

    # Sola ve sağa doğru alfanumerik ve altçizgi tara
    left = character
    while left > 0 and (cur_line[left - 1].isalnum() or cur_line[left - 1] == '_'):
        left -= 1
    right = character
    while right < len(cur_line) and (cur_line[right].isalnum() or cur_line[right] == '_'):
        right += 1
    return cur_line[left:right]


class AxiomLanguageServer:
    """Axiom Language Server Protocol 3.x Uygulaması."""
    def __init__(self, in_stream=None, out_stream=None):
        self.in_stream = in_stream or sys.stdin.buffer
        self.out_stream = out_stream or sys.stdout.buffer
        self.documents: Dict[str, str] = {}
        self.document_asts: Dict[str, Program] = {}
        self.is_shutdown = False

    def send_response(self, response_id: Any, result: Any = None, error: Any = None):
        msg: Dict[str, Any] = {"jsonrpc": "2.0", "id": response_id}
        if error is not None:
            msg["error"] = error
        else:
            msg["result"] = result
        self._write_msg(msg)

    def send_notification(self, method: str, params: Any):
        msg: Dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params}
        self._write_msg(msg)

    def _write_msg(self, msg: Dict[str, Any]):
        body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        self.out_stream.write(header + body)
        self.out_stream.flush()

    def handle_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Gelen JSON-RPC mesajını işler."""
        msg_id = message.get("id")
        method = message.get("method")
        params = message.get("params", {})

        if method == "initialize":
            result = {
                "capabilities": {
                    "textDocumentSync": 1,  # TextDocumentSyncKind.Full
                    "completionProvider": {
                        "resolveProvider": False,
                        "triggerCharacters": [".", ":"]
                    },
                    "hoverProvider": True,
                    "definitionProvider": True,
                    "referencesProvider": True,
                    "renameProvider": {"prepareProvider": True},
                    "codeActionProvider": {"codeActionKinds": ["quickfix"]},
                    "documentFormattingProvider": True,
                    "semanticTokensProvider": {
                        "legend": {"tokenTypes": SEMANTIC_TOKEN_TYPES, "tokenModifiers": []},
                        "full": True
                    },
                    "signatureHelpProvider": {"triggerCharacters": ["(", ","]}
                },
                "serverInfo": {
                    "name": "axiom-lsp",
                    "version": "v0.5.0-alpha"
                }
            }
            if msg_id is not None:
                self.send_response(msg_id, result=result)
            return {"id": msg_id, "result": result}

        elif method == "initialized":
            # İstemci hazır olduğunu bildirdi
            return None

        elif method == "shutdown":
            self.is_shutdown = True
            if msg_id is not None:
                self.send_response(msg_id, result=None)
            return {"id": msg_id, "result": None}

        elif method == "exit":
            sys.exit(0 if self.is_shutdown else 1)

        elif method == "textDocument/didOpen":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            text = doc.get("text", "")
            self.documents[uri] = text
            self.publish_diagnostics(uri, text)
            return None

        elif method == "textDocument/didChange":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            changes = params.get("contentChanges", [])
            if changes:
                text = changes[-1].get("text", "")
                self.documents[uri] = text
                self.publish_diagnostics(uri, text)
            return None

        elif method == "textDocument/didSave":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            if uri in self.documents:
                self.publish_diagnostics(uri, self.documents[uri])
            return None

        elif method == "textDocument/didClose":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            self.documents.pop(uri, None)
            self.document_asts.pop(uri, None)
            return None

        elif method == "textDocument/completion":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            pos = params.get("position", {})
            line = pos.get("line", 0)
            char = pos.get("character", 0)

            items = self.compute_completions(uri, line, char)
            result = {"isIncomplete": False, "items": items}
            if msg_id is not None:
                self.send_response(msg_id, result=result)
            return {"id": msg_id, "result": result}

        elif method == "textDocument/hover":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            pos = params.get("position", {})
            line = pos.get("line", 0)
            char = pos.get("character", 0)

            hover_data = self.compute_hover(uri, line, char)
            if msg_id is not None:
                self.send_response(msg_id, result=hover_data)
            return {"id": msg_id, "result": hover_data}

        elif method == "textDocument/definition":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            pos = params.get("position", {})
            line = pos.get("line", 0)
            char = pos.get("character", 0)

            location = self.compute_definition(uri, line, char)
            if msg_id is not None:
                self.send_response(msg_id, result=location)
            return {"id": msg_id, "result": location}

        elif method == "textDocument/references":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            pos = params.get("position", {})
            ctx = params.get("context", {}) or {}
            result = self.compute_references(
                uri, pos.get("line", 0), pos.get("character", 0),
                include_declaration=bool(ctx.get("includeDeclaration", True)),
            )
            if msg_id is not None:
                self.send_response(msg_id, result=result)
            return {"id": msg_id, "result": result}

        elif method == "textDocument/prepareRename":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            pos = params.get("position", {})
            result = self.compute_prepare_rename(uri, pos.get("line", 0), pos.get("character", 0))
            if msg_id is not None:
                self.send_response(msg_id, result=result)
            return {"id": msg_id, "result": result}

        elif method == "textDocument/rename":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            pos = params.get("position", {})
            new_name = params.get("newName", "")
            result = self.compute_rename(uri, pos.get("line", 0), pos.get("character", 0), new_name)
            if msg_id is not None:
                self.send_response(msg_id, result=result)
            return {"id": msg_id, "result": result}

        elif method == "textDocument/codeAction":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            result = self.compute_code_actions(
                uri, params.get("range", {}) or {},
                params.get("context", {}).get("diagnostics", []) or [],
            )
            if msg_id is not None:
                self.send_response(msg_id, result=result)
            return {"id": msg_id, "result": result}

        elif method == "textDocument/formatting":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            result = self.compute_formatting(uri)
            if msg_id is not None:
                self.send_response(msg_id, result=result)
            return {"id": msg_id, "result": result}

        elif method == "textDocument/semanticTokens/full":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            result = {"data": self.compute_semantic_tokens(uri)}
            if msg_id is not None:
                self.send_response(msg_id, result=result)
            return {"id": msg_id, "result": result}

        elif method == "textDocument/signatureHelp":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            pos = params.get("position", {})
            result = self.compute_signature_help(uri, pos.get("line", 0), pos.get("character", 0))
            if msg_id is not None:
                self.send_response(msg_id, result=result)
            return {"id": msg_id, "result": result}

        else:
            if msg_id is not None:
                err = {"code": -32601, "message": f"Method '{method}' bulunamadi."}
                self.send_response(msg_id, error=err)
                return {"id": msg_id, "error": err}
        return None

    def publish_diagnostics(self, uri: str, text: str):
        """Metin üzerinde sözdizim ve tip analizi yaparak editöre diagnostik yayınlar."""
        diagnostics: List[Dict[str, Any]] = []
        try:
            # 1. Lexer
            lexer = Lexer(text)
            tokens = lexer.tokenize()

            # 2. Parser
            parser = Parser(tokens)
            program = parser.parse()

            # 3. TypeChecker
            checker = TypeChecker()
            checker.check(program)

            # Başarılı AST'yi sakla
            self.document_asts[uri] = program

        except LexerError as e:
            diagnostics.append({
                "range": {
                    "start": {"line": max(0, e.line - 1), "character": max(0, e.col - 1)},
                    "end": {"line": max(0, e.line - 1), "character": max(0, e.col)}
                },
                "severity": SEVERITY_ERROR,
                "source": "axiom-lexer",
                "message": str(e)
            })
        except ParserError as e:
            tok = e.token
            diagnostics.append({
                "range": {
                    "start": {"line": max(0, tok.line - 1), "character": max(0, tok.col - 1)},
                    "end": {"line": max(0, tok.line - 1), "character": max(0, tok.col - 1 + max(1, len(tok.value)))}
                },
                "severity": SEVERITY_ERROR,
                "source": "axiom-parser",
                "message": str(e)
            })
        except SemanticError as e:
            diagnostics.append({
                "range": {
                    "start": {"line": max(0, e.line - 1), "character": max(0, e.col - 1)},
                    "end": {"line": max(0, e.line - 1), "character": max(0, e.col + 15)}
                },
                "severity": SEVERITY_ERROR,
                "source": "axiom-checker",
                "message": str(e)
            })
        except Exception as e:
            diagnostics.append({
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 1}
                },
                "severity": SEVERITY_ERROR,
                "source": "axiom",
                "message": str(e)
            })

        self.send_notification("textDocument/publishDiagnostics", {
            "uri": uri,
            "diagnostics": diagnostics
        })

    def compute_completions(self, uri: str, line: int, char: int) -> List[Dict[str, Any]]:
        """Otomatik tamamlama adaylarını hesaplar."""
        items: List[Dict[str, Any]] = []
        text = self.documents.get(uri, "")
        prefix = get_prefix_at_position(text, line, char).lower()

        # 1. Anahtar Kelimeler
        for kw in AXIOM_KEYWORDS:
            if not prefix or kw.startswith(prefix):
                items.append({
                    "label": kw,
                    "kind": KIND_KEYWORD,
                    "detail": "Axiom Anahtar Kelimesi",
                    "insertText": kw
                })

        # 2. Standart Yerleşik Fonksiyonlar
        for name, (sig, doc) in STANDARD_BUILTINS_DOC.items():
            if not prefix or name.lower().startswith(prefix):
                items.append({
                    "label": name,
                    "kind": KIND_FUNCTION,
                    "detail": sig,
                    "documentation": doc,
                    "insertText": f"{name}("
                })

        # 3. Dosyadaki Yerel Semboller (AST'den)
        ast = self.document_asts.get(uri)
        if ast:
            for decl in ast.declarations:
                if isinstance(decl, FunctionDecl):
                    if not prefix or decl.name.lower().startswith(prefix):
                        params_str = ", ".join(f"{p.name}: {p.type_name}" for p in decl.params)
                        sig = f"fn {decl.name}({params_str}) -> {decl.return_type}"
                        items.append({
                            "label": decl.name,
                            "kind": KIND_FUNCTION,
                            "detail": sig,
                            "insertText": f"{decl.name}("
                        })
                elif isinstance(decl, StructDecl):
                    if not prefix or decl.name.lower().startswith(prefix):
                        fields_str = ", ".join(f"{f.name}: {f.type_name}" for f in decl.fields)
                        items.append({
                            "label": decl.name,
                            "kind": KIND_STRUCT,
                            "detail": f"struct {decl.name} {{ {fields_str} }}",
                            "insertText": decl.name
                        })
                elif isinstance(decl, LetDecl):
                    if not prefix or decl.name.lower().startswith(prefix):
                        items.append({
                            "label": decl.name,
                            "kind": KIND_VARIABLE,
                            "detail": f"let {decl.name}: {decl.type_annotation or 'inferred'}",
                            "insertText": decl.name
                        })

        return items

    def compute_hover(self, uri: str, line: int, char: int) -> Optional[Dict[str, Any]]:
        """İmleç altındaki sembol için zengin Markdown Hover bilgisini üretir."""
        text = self.documents.get(uri, "")
        word = get_word_at_position(text, line, char)
        if not word:
            return None

        # 1. Standart yerleşikler
        if word in STANDARD_BUILTINS_DOC:
            sig, doc = STANDARD_BUILTINS_DOC[word]
            md_val = f"```axiom\n{sig}\n```\n\n{doc}"
            return {"contents": {"kind": "markdown", "value": md_val}}

        # 2. Tip denetleyicisi builtin listesi
        if word in BUILTIN_FUNCTIONS:
            param_types, ret_t = BUILTIN_FUNCTIONS[word]
            params_str = ", ".join(f"arg{i}: {t}" for i, t in enumerate(param_types))
            sig = f"fn {word}({params_str}) -> {ret_t}"
            md_val = f"```axiom\n{sig}\n```\n\n*(Yerleşik Axiom Çekirdek Fonksiyonu)*"
            return {"contents": {"kind": "markdown", "value": md_val}}

        # 3. AST Yerel Sembolleri
        ast = self.document_asts.get(uri)
        if ast:
            for decl in ast.declarations:
                if isinstance(decl, FunctionDecl) and decl.name == word:
                    params_str = ", ".join(f"{p.name}: {p.type_name}" for p in decl.params)
                    sig = f"fn {decl.name}({params_str}) -> {decl.return_type}"
                    contract_lines = []
                    if decl.contract.requires:
                        contract_lines.append(f"  // requires: {len(decl.contract.requires)} ön-koşul")
                    if decl.contract.ensures:
                        contract_lines.append(f"  // ensures: {len(decl.contract.ensures)} son-koşul")
                    doc = "\n".join(contract_lines)
                    md_val = f"```axiom\n{sig}\n{doc}\n```"
                    return {"contents": {"kind": "markdown", "value": md_val}}

                elif isinstance(decl, StructDecl) and decl.name == word:
                    fields = "\n".join(f"    {f.name}: {f.type_name}" for f in decl.fields)
                    md_val = f"```axiom\nstruct {decl.name} {{\n{fields}\n}}\n```"
                    return {"contents": {"kind": "markdown", "value": md_val}}

                elif isinstance(decl, LetDecl) and decl.name == word:
                    t = decl.type_annotation or "inferred"
                    md_val = f"```axiom\nlet {'mut ' if decl.is_mut else ''}{decl.name}: {t}\n```"
                    return {"contents": {"kind": "markdown", "value": md_val}}

        if word in AXIOM_KEYWORDS:
            return {"contents": {"kind": "markdown", "value": f"**Axiom Dil Anahtar Kelimesi**: `{word}`"}}

        return None

    def compute_definition(self, uri: str, line: int, char: int) -> Optional[Dict[str, Any]]:
        """İmleç altındaki sembolün tanımlandığı AST konumuna gider (Go to Definition)."""
        text = self.documents.get(uri, "")
        word = get_word_at_position(text, line, char)
        if not word:
            return None

        ast = self.document_asts.get(uri)
        if not ast:
            return None

        for decl in ast.declarations:
            if isinstance(decl, (FunctionDecl, StructDecl, LetDecl)) and getattr(decl, "name", "") == word:
                def_line = max(0, decl.line - 1)
                def_col = max(0, decl.col - 1)
                return {
                    "uri": uri,
                    "range": {
                        "start": {"line": def_line, "character": def_col},
                        "end": {"line": def_line, "character": def_col + len(word)}
                    }
                }
            # Fonksiyon parametreleri ve gövdesindeki let tanımları
            if isinstance(decl, FunctionDecl):
                for p in decl.params:
                    if p.name == word:
                        p_line = max(0, p.line - 1)
                        p_col = max(0, p.col - 1)
                        return {
                            "uri": uri,
                            "range": {
                                "start": {"line": p_line, "character": p_col},
                                "end": {"line": p_line, "character": p_col + len(word)}
                            }
                        }
                # Gövde içerisindeki değişkenler
                for stmt in decl.body.statements:
                    if isinstance(stmt, LetDecl) and stmt.name == word:
                        s_line = max(0, stmt.line - 1)
                        s_col = max(0, stmt.col - 1)
                        return {
                            "uri": uri,
                            "range": {
                                "start": {"line": s_line, "character": s_col},
                                "end": {"line": s_line, "character": s_col + len(word)}
                            }
                        }

        return None

    # ------------------------------------------------------------------
    # References / Rename
    # ------------------------------------------------------------------

    def _lex_tokens(self, uri: str) -> List[Any]:
        text = self.documents.get(uri, "")
        try:
            return Lexer(text).tokenize()
        except LexerError:
            return []

    def _identifier_occurrences(self, uri: str, word: str) -> List[Tuple[int, int, bool]]:
        """(line, col, is_declaration) üçlüleri. Yorum ve string'ler lexer
        sayesinde kendiliğinden dışarıda kalır."""
        out: List[Tuple[int, int, bool]] = []
        prev_type = ""
        for tok in self._lex_tokens(uri):
            if tok.type == "IDENT" and tok.value == word:
                is_decl = prev_type in ("FN", "STRUCT", "LET")
                out.append((tok.line - 1, tok.col - 1, is_decl))
            if tok.type not in ("MUT",):
                prev_type = tok.type
        return out

    def compute_references(self, uri: str, line: int, char: int,
                           include_declaration: bool = True) -> List[Dict[str, Any]]:
        text = self.documents.get(uri, "")
        word = get_word_at_position(text, line, char)
        if not word or word in AXIOM_KEYWORDS:
            return []
        locations = []
        for ln, col, is_decl in self._identifier_occurrences(uri, word):
            if is_decl and not include_declaration:
                continue
            locations.append({
                "uri": uri,
                "range": {
                    "start": {"line": ln, "character": col},
                    "end": {"line": ln, "character": col + len(word)},
                },
            })
        return locations

    def compute_prepare_rename(self, uri: str, line: int, char: int) -> Optional[Dict[str, Any]]:
        text = self.documents.get(uri, "")
        word = get_word_at_position(text, line, char)
        if not word or not _is_identifier(word) or word in AXIOM_KEYWORDS:
            return None
        occurrences = self._identifier_occurrences(uri, word)
        if not occurrences:
            return None
        # İmlecin gerçekten bir tanımlayıcı üzerinde olduğunu doğrula.
        match = next(((l, c) for l, c, _ in occurrences
                      if l == line and c <= char <= c + len(word)), None)
        if not match:
            return None
        ln, col = match
        return {
            "range": {
                "start": {"line": ln, "character": col},
                "end": {"line": ln, "character": col + len(word)},
            },
            "placeholder": word,
        }

    def compute_rename(self, uri: str, line: int, char: int,
                       new_name: str) -> Optional[Dict[str, Any]]:
        text = self.documents.get(uri, "")
        word = get_word_at_position(text, line, char)
        if not word or not _is_identifier(word) or word in AXIOM_KEYWORDS:
            return None
        if not _is_identifier(new_name):
            return None
        edits = [
            {
                "range": {
                    "start": {"line": ln, "character": col},
                    "end": {"line": ln, "character": col + len(word)},
                },
                "newText": new_name,
            }
            for ln, col, _ in self._identifier_occurrences(uri, word)
        ]
        if not edits:
            return None
        return {"changes": {uri: edits}}

    # ------------------------------------------------------------------
    # Semantic tokens
    # ------------------------------------------------------------------

    def _symbol_kinds(self, uri: str) -> Dict[str, str]:
        """Tanımlayıcı adı -> semantik tip ('function' | 'struct' | 'parameter' | 'variable')."""
        kinds: Dict[str, str] = {}
        ast = self.document_asts.get(uri)
        if not ast:
            return kinds
        for decl in ast.declarations:
            if isinstance(decl, FunctionDecl):
                kinds.setdefault(decl.name, "function")
                for p in decl.params:
                    kinds.setdefault(p.name, "parameter")
                for stmt in getattr(decl.body, "statements", []) or []:
                    if isinstance(stmt, LetDecl):
                        kinds.setdefault(stmt.name, "variable")
            elif isinstance(decl, StructDecl):
                kinds.setdefault(decl.name, "struct")
                for f in decl.fields:
                    kinds.setdefault(f.name, "property")
            elif isinstance(decl, LetDecl):
                kinds.setdefault(decl.name, "variable")
        return kinds

    def compute_semantic_tokens(self, uri: str) -> List[int]:
        tokens = self._lex_tokens(uri)
        if not tokens:
            return []
        kinds = self._symbol_kinds(uri)

        entries: List[Tuple[int, int, int, int]] = []
        for tok in tokens:
            if tok.type == "EOF" or not tok.value:
                continue
            ttype: Optional[str] = None
            if tok.type == "DOC":
                ttype = "comment"
            elif tok.type == "STRING":
                ttype = "string"
            elif tok.type in ("INT", "FLOAT"):
                ttype = "number"
            elif tok.type == "TYPE":
                ttype = "type"
            elif tok.type in _SEM_KEYWORD_TYPES:
                ttype = "keyword"
            elif tok.type in _SEM_OPERATOR_TYPES:
                ttype = "operator"
            elif tok.type == "IDENT":
                ttype = kinds.get(tok.value, "variable")
            if ttype is None:
                continue
            entries.append((tok.line - 1, tok.col - 1, len(tok.value),
                            SEMANTIC_TOKEN_TYPES.index(ttype)))

        entries.sort(key=lambda e: (e[0], e[1]))
        data: List[int] = []
        prev_line = 0
        prev_char = 0
        for ln, col, length, ttype in entries:
            delta_line = ln - prev_line
            delta_char = col - prev_char if delta_line == 0 else col
            data.extend([delta_line, delta_char, length, ttype, 0])
            prev_line, prev_char = ln, col
        return data

    # ------------------------------------------------------------------
    # Signature help
    # ------------------------------------------------------------------

    @staticmethod
    def _find_enclosing_call(text: str, offset: int) -> Optional[Tuple[str, int]]:
        """İmleci kapsayan en içteki çağrının (ad, '(' ofseti) çiftini bulur."""
        depth = 0
        i = offset - 1
        while i >= 0:
            ch = text[i]
            if ch == ')':
                depth += 1
            elif ch == '(':
                if depth == 0:
                    j = i - 1
                    while j >= 0 and text[j] in " \t":
                        j -= 1
                    end = j + 1
                    while j >= 0 and (text[j].isalnum() or text[j] == "_"):
                        j -= 1
                    name = text[j + 1:end]
                    if name and _is_identifier(name):
                        return name, i
                    return None
                depth -= 1
            i -= 1
        return None

    @staticmethod
    def _count_top_level_args(segment: str) -> int:
        depth = 0
        in_str = False
        escaped = False
        count = 0
        for ch in segment:
            if in_str:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "," and depth == 0:
                count += 1
        return count

    def _lookup_signature(self, uri: str, name: str) -> Optional[Tuple[str, List[str], str]]:
        ast = self.document_asts.get(uri)
        if ast:
            for decl in ast.declarations:
                if isinstance(decl, FunctionDecl) and decl.name == name:
                    params = [f"{p.name}: {p.type_name}" for p in decl.params]
                    sig = f"fn {decl.name}({', '.join(params)}) -> {decl.return_type}"
                    return sig, params, "Yerel fonksiyon"
        if name in STANDARD_BUILTINS_DOC:
            sig, doc = STANDARD_BUILTINS_DOC[name]
            inner = sig[sig.find("(") + 1:sig.rfind(")")]
            params = [p.strip() for p in inner.split(",") if p.strip() and p.strip() != "..."]
            return sig, params, doc
        if name in BUILTIN_FUNCTIONS:
            param_types, ret_t = BUILTIN_FUNCTIONS[name]
            params = [f"arg{i}: {t}" for i, t in enumerate(param_types)]
            sig = f"fn {name}({', '.join(params)}) -> {ret_t}"
            return sig, params, "Yerleşik Axiom çekirdek fonksiyonu"
        return None

    def compute_signature_help(self, uri: str, line: int, char: int) -> Optional[Dict[str, Any]]:
        text = self.documents.get(uri, "")
        offset = _position_to_offset(text, line, char)
        found = self._find_enclosing_call(text, offset)
        if not found:
            return None
        name, open_idx = found
        lookup = self._lookup_signature(uri, name)
        if not lookup:
            return None
        sig, params, doc = lookup
        arg_index = self._count_top_level_args(text[open_idx + 1:offset])
        return {
            "signatures": [{
                "label": sig,
                "documentation": {"kind": "markdown", "value": doc},
                "parameters": [{"label": p} for p in params],
            }],
            "activeSignature": 0,
            "activeParameter": max(0, min(arg_index, max(0, len(params) - 1))),
        }

    # ------------------------------------------------------------------
    # Code actions
    # ------------------------------------------------------------------

    def compute_code_actions(self, uri: str, range_: Dict[str, Any],
                             diagnostics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        import difflib

        text = self.documents.get(uri, "")
        actions: List[Dict[str, Any]] = []
        candidates = sorted(set(BUILTIN_FUNCTIONS) | set(STANDARD_BUILTINS_DOC))

        for diag in diagnostics:
            msg = diag.get("message", "") or ""
            drange = diag.get("range") or range_

            m = re.search(r"Bilinmeyen fonksiyon cagrisi: '([^']+)'", msg)
            if m:
                bad = m.group(1)
                match = difflib.get_close_matches(bad, candidates, n=1, cutoff=0.6)
                if match:
                    # Tanılama aralığı geniş olabilir; gerçek tanımlayıcıya daralt.
                    start = drange.get("start", {}) or {}
                    occ = [
                        (l, c) for l, c, _ in self._identifier_occurrences(uri, bad)
                    ]
                    if occ:
                        l, c = min(occ, key=lambda o: (
                            abs(o[0] - start.get("line", 0)),
                            abs(o[1] - start.get("character", 0)),
                        ))
                        drange = {
                            "start": {"line": l, "character": c},
                            "end": {"line": l, "character": c + len(bad)},
                        }
                    actions.append({
                        "title": f"'{bad}' yerine '{match[0]}' kullan",
                        "kind": "quickfix",
                        "diagnostics": [diag],
                        "isPreferred": True,
                        "edit": {"changes": {uri: [{"range": drange, "newText": match[0]}]}},
                    })

            m = re.search(r"Degistirilemez \(immutable\) degiskene atama yapilamaz: '([^']+)'", msg)
            if m:
                var = m.group(1)
                found = None
                for idx, line_text in enumerate(text.splitlines()):
                    m2 = re.search(rf"\blet\s+({re.escape(var)})\b", line_text)
                    if m2:
                        found = (idx, m2.start(1) - 4)  # 'let ' başına taşı
                        break
                if found:
                    ln, col = found
                    actions.append({
                        "title": f"'{var}' değişkenini 'let mut' yap",
                        "kind": "quickfix",
                        "diagnostics": [diag],
                        "isPreferred": True,
                        "edit": {"changes": {uri: [{
                            "range": {
                                "start": {"line": ln, "character": col},
                                "end": {"line": ln, "character": col},
                            },
                            "newText": "mut ",
                        }]}},
                    })

        return actions

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def compute_formatting(self, uri: str) -> List[Dict[str, Any]]:
        from axiom.formatter import format_source

        text = self.documents.get(uri, "")
        if not text:
            return []
        try:
            formatted = format_source(text)
        except Exception:
            return []
        if formatted == text:
            return []
        lines = text.splitlines()
        end_line = max(0, len(lines) - 1)
        end_char = len(lines[-1]) if lines else 0
        return [{
            "range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": end_line, "character": end_char},
            },
            "newText": formatted,
        }]

    def serve_io(self):
        """Standart Girdi/Çıktı (stdio) üzerinden JSON-RPC akışını dinler."""
        buffer = bytearray()
        while True:
            try:
                line = self.in_stream.readline()
                if not line:
                    break
                if line.startswith(b"Content-Length:"):
                    length_str = line.split(b":")[1].strip()
                    content_length = int(length_str)
                    # Boş satırı oku (\r\n)
                    empty_line = self.in_stream.readline()
                    # Gövdeyi oku
                    body = self.in_stream.read(content_length)
                    if len(body) < content_length:
                        break
                    msg = json.loads(body.decode("utf-8"))
                    self.handle_message(msg)
            except (KeyboardInterrupt, SystemExit):
                break
            except Exception as e:
                # Log to stderr
                sys.stderr.write(f"[axiom-lsp error] {str(e)}\n")
                sys.stderr.flush()


def main():
    server = AxiomLanguageServer()
    server.serve_io()


if __name__ == "__main__":
    main()
