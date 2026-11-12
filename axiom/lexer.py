"""
Axiom Programming Language (λx) - Lexer
"""
import re
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Token:
    type: str
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type}, {repr(self.value)}, line={self.line}, col={self.col})"

class LexerError(Exception):
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"LexerError at line {line}, col {col}: {message}")
        self.line = line
        self.col = col

KEYWORDS = {
    'fn', 'let', 'mut', 'if', 'else', 'while', 'for', 'in',
    'return', 'print', 'verify', 'requires', 'ensures',
    'true', 'false', 'and', 'or', 'not', 'struct', 'import',
    'break', 'continue', 'defer', 'invariant', 'as', 'match'
}

TYPES = {'int', 'float', 'bool', 'str', 'void'}

class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.length = len(source)
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: List[Token] = []

    def current_char(self) -> Optional[str]:
        if self.pos < self.length:
            return self.source[self.pos]
        return None

    def peek_char(self, offset: int = 1) -> Optional[str]:
        target = self.pos + offset
        if target < self.length:
            return self.source[target]
        return None

    def advance(self) -> Optional[str]:
        ch = self.current_char()
        if ch is not None:
            self.pos += 1
            if ch == '\n':
                self.line += 1
                self.col = 1
            else:
                self.col += 1
        return ch

    def tokenize(self) -> List[Token]:
        while self.pos < self.length:
            ch = self.current_char()

            # Skip whitespace
            if ch in (' ', '\t', '\r', '\n'):
                self.advance()
                continue

            # Doc comment: '///' -> DOC token (sonraki bildirime baglanir)
            if ch == '/' and self.peek_char() == '/' and self.peek_char(2) == '/':
                start_line, start_col = self.line, self.col
                self.advance(); self.advance(); self.advance()
                if self.current_char() == ' ':
                    self.advance()
                buf = []
                while self.current_char() is not None and self.current_char() != '\n':
                    buf.append(self.current_char())
                    self.advance()
                self.tokens.append(Token('DOC', "".join(buf).rstrip(), start_line, start_col))
                continue

            # Skip comments (# ... or // ...)
            if ch == '#' or (ch == '/' and self.peek_char() == '/'):
                while self.current_char() is not None and self.current_char() != '\n':
                    self.advance()
                continue

            start_line = self.line
            start_col = self.col

            # Two-character operators
            if ch == '-' and self.peek_char() == '>':
                self.advance()
                self.advance()
                self.tokens.append(Token('ARROW', '->', start_line, start_col))
                continue

            if ch == '.':
                if self.peek_char() == '.':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token('DOTDOT', '..', start_line, start_col))
                else:
                    self.advance()
                    self.tokens.append(Token('DOT', '.', start_line, start_col))
                continue

            if ch == '=' and self.peek_char() == '=':
                self.advance()
                self.advance()
                self.tokens.append(Token('EQEQ', '==', start_line, start_col))
                continue

            if ch == '=' and self.peek_char() == '>':
                self.advance()
                self.advance()
                self.tokens.append(Token('FAT_ARROW', '=>', start_line, start_col))
                continue

            if ch == '!' and self.peek_char() == '=':
                self.advance()
                self.advance()
                self.tokens.append(Token('NOTEQ', '!=', start_line, start_col))
                continue

            if ch == '<' and self.peek_char() == '=':
                self.advance()
                self.advance()
                self.tokens.append(Token('LTEQ', '<=', start_line, start_col))
                continue

            if ch == '>' and self.peek_char() == '=':
                self.advance()
                self.advance()
                self.tokens.append(Token('GTEQ', '>=', start_line, start_col))
                continue

            # Decorator / Attribute '@'
            if ch == '@':
                if self.peek_char() and (self.peek_char().isalpha() or self.peek_char() == '_'):
                    self.advance()
                    self.tokens.append(Token('AT', '@', start_line, start_col))
                    continue
                else:
                    raise LexerError(f"Gecersiz karakter: {repr(ch)}", start_line, start_col)

            # Try operator '?' (Result propagasyonu)
            if ch == '?':
                self.advance()
                self.tokens.append(Token('QUESTION', '?', start_line, start_col))
                continue

            # Single character operators & punctuation
            if ch in "+-*/%()[]{}:;,=<>":
                self.advance()
                type_map = {
                    '+': 'PLUS', '-': 'MINUS', '*': 'STAR', '/': 'SLASH', '%': 'PERCENT',
                    '(': 'LPAREN', ')': 'RPAREN', '{': 'LBRACE', '}': 'RBRACE',
                    '[': 'LBRACKET', ']': 'RBRACKET', ':': 'COLON', ';': 'SEMICOLON',
                    ',': 'COMMA', '=': 'ASSIGN', '<': 'LT', '>': 'GT'
                }
                self.tokens.append(Token(type_map[ch], ch, start_line, start_col))
                continue

            # Strings: "..."
            if ch == '"':
                self.advance()  # Skip opening quote
                val = []
                while self.current_char() is not None and self.current_char() != '"':
                    if self.current_char() == '\\':
                        self.advance()
                        esc = self.current_char()
                        if esc == 'n': val.append('\n')
                        elif esc == 'r': val.append('\r')
                        elif esc == 't': val.append('\t')
                        elif esc == '\\': val.append('\\')
                        elif esc == '"': val.append('"')
                        else: val.append(esc or '')
                    else:
                        val.append(self.current_char())
                    self.advance()

                if self.current_char() != '"':
                    raise LexerError("Sonlandirilmamis string literali (Unterminated string)", start_line, start_col)
                self.advance()  # Skip closing quote
                self.tokens.append(Token('STRING', "".join(val), start_line, start_col))
                continue

            # Numbers: integer or float
            if ch.isdigit():
                # Desteklenmeyen sayi bicimleri icin ANLASILIR hata ver.
                # Aksi halde '0x10' -> '0' + 'x10' olarak ayrilip kafa karistirici
                # "Tanimlanmamis degisken: 'x10'" hatasi cikiyordu.
                nxt = self.peek_char()
                if nxt in ('x', 'X', 'b', 'B', 'o', 'O'):
                    raise LexerError(
                        f"Desteklenmeyen sayi bicimi: '{ch}{nxt}...'. "
                        f"Axiom yalnizca ondalik tamsayi ve float literallerini destekler.",
                        start_line, start_col)
                if nxt == 'e' or nxt == 'E':
                    raise LexerError(
                        f"Bilimsel gosterim desteklenmiyor: '{ch}{nxt}...'. "
                        f"Ondalik bicim kullanin (orn. 1000000000.0).",
                        start_line, start_col)
                num_str = []
                is_float = False
                while self.current_char() is not None and (self.current_char().isdigit() or self.current_char() == '.'):
                    # Check for '..' range operator before treating '.' as float dot
                    if self.current_char() == '.' and self.peek_char() == '.':
                        break
                    if self.current_char() == '.':
                        if is_float:
                            break
                        is_float = True
                    num_str.append(self.current_char())
                    self.advance()
                if self.current_char() == '_':
                    raise LexerError(
                        "Sayilarda alt cizgi ayirici desteklenmiyor ('1_000' gecersiz). "
                        "Duz yazin: 1000.",
                        start_line, start_col)

                full_num = "".join(num_str)
                token_type = 'FLOAT' if is_float else 'INT'
                self.tokens.append(Token(token_type, full_num, start_line, start_col))
                continue

            # Identifiers & Keywords
            if ch.isalpha() or ch == '_':
                ident = []
                while self.current_char() is not None and (self.current_char().isalnum() or self.current_char() == '_'):
                    ident.append(self.current_char())
                    self.advance()
                word = "".join(ident)

                if word == '_':
                    self.tokens.append(Token('UNDERSCORE', '_', start_line, start_col))
                elif word in KEYWORDS:
                    self.tokens.append(Token(word.upper(), word, start_line, start_col))
                elif word in TYPES:
                    self.tokens.append(Token('TYPE', word, start_line, start_col))
                else:
                    self.tokens.append(Token('IDENT', word, start_line, start_col))
                continue

            raise LexerError(f"Gecersiz karakter: {repr(ch)}", start_line, start_col)

        self.tokens.append(Token('EOF', '', self.line, self.col))
        return self.tokens
