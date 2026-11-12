"""
Unit tests for Axiom Lexer
"""
import pytest
from axiom.lexer import Lexer, Token, LexerError

def get_tokens(source: str):
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    # Exclude EOF for easier comparison in focused tests
    return [(t.type, t.value) for t in tokens if t.type != 'EOF']

def test_keywords():
    source = "fn let mut if else while for in return print verify requires ensures true false and or not struct"
    expected = [
        ('FN', 'fn'), ('LET', 'let'), ('MUT', 'mut'), ('IF', 'if'),
        ('ELSE', 'else'), ('WHILE', 'while'), ('FOR', 'for'), ('IN', 'in'),
        ('RETURN', 'return'), ('PRINT', 'print'), ('VERIFY', 'verify'),
        ('REQUIRES', 'requires'), ('ENSURES', 'ensures'),
        ('TRUE', 'true'), ('FALSE', 'false'),
        ('AND', 'and'), ('OR', 'or'), ('NOT', 'not'),
        ('STRUCT', 'struct')
    ]
    assert get_tokens(source) == expected

def test_types():
    source = "int float bool str void"
    expected = [
        ('TYPE', 'int'), ('TYPE', 'float'), ('TYPE', 'bool'),
        ('TYPE', 'str'), ('TYPE', 'void')
    ]
    assert get_tokens(source) == expected

def test_identifiers():
    source = "foo bar_baz _secret camelCase port80"
    expected = [
        ('IDENT', 'foo'),
        ('IDENT', 'bar_baz'),
        ('IDENT', '_secret'),
        ('IDENT', 'camelCase'),
        ('IDENT', 'port80')
    ]
    assert get_tokens(source) == expected

def test_operators():
    source = "+ - * / % ( ) { } [ ] : ; , = < > -> .. . == != <= >="
    expected = [
        ('PLUS', '+'), ('MINUS', '-'), ('STAR', '*'), ('SLASH', '/'), ('PERCENT', '%'),
        ('LPAREN', '('), ('RPAREN', ')'), ('LBRACE', '{'), ('RBRACE', '}'),
        ('LBRACKET', '['), ('RBRACKET', ']'), ('COLON', ':'), ('SEMICOLON', ';'),
        ('COMMA', ','), ('ASSIGN', '='), ('LT', '<'), ('GT', '>'),
        ('ARROW', '->'), ('DOTDOT', '..'), ('DOT', '.'), ('EQEQ', '=='), ('NOTEQ', '!='),
        ('LTEQ', '<='), ('GTEQ', '>=')
    ]
    assert get_tokens(source) == expected

def test_numbers():
    source = "0 42 1000 3.14 0.05 123.456"
    expected = [
        ('INT', '0'), ('INT', '42'), ('INT', '1000'),
        ('FLOAT', '3.14'), ('FLOAT', '0.05'), ('FLOAT', '123.456')
    ]
    assert get_tokens(source) == expected

def test_range_vs_float():
    source = "0..10"
    tokens = get_tokens(source)
    assert tokens == [('INT', '0'), ('DOTDOT', '..'), ('INT', '10')]

def test_dot_member_access():
    source = "point.x = 10"
    tokens = get_tokens(source)
    assert tokens == [
        ('IDENT', 'point'),
        ('DOT', '.'),
        ('IDENT', 'x'),
        ('ASSIGN', '='),
        ('INT', '10')
    ]

def test_strings_and_escapes():
    source = r'"hello world" "tab\tnewline\nquote\"backslash\\"'
    tokens = get_tokens(source)
    assert tokens[0] == ('STRING', 'hello world')
    assert tokens[1] == ('STRING', 'tab\tnewline\nquote"backslash\\')

def test_empty_string():
    source = '""'
    tokens = get_tokens(source)
    assert tokens == [('STRING', '')]

def test_unterminated_string():
    source = '"unfinished string'
    with pytest.raises(LexerError) as exc_info:
        Lexer(source).tokenize()
    assert "Sonlandirilmamis string" in str(exc_info.value)

def test_comments():
    source = """
    # Full line comment
    let x = 5 # Inline comment
    # Another comment
    """
    tokens = get_tokens(source)
    assert tokens == [('LET', 'let'), ('IDENT', 'x'), ('ASSIGN', '='), ('INT', '5')]

def test_invalid_character():
    source = "let x = @10;"
    with pytest.raises(LexerError) as exc_info:
        Lexer(source).tokenize()
    assert "Gecersiz karakter" in str(exc_info.value)
    assert exc_info.value.line == 1
    assert exc_info.value.col == 9

def test_line_and_col_tracking():
    source = "let a = 1\nlet b = 2"
    tokens = Lexer(source).tokenize()
    # token 'b' is on line 2
    tok_b = next(t for t in tokens if t.value == 'b')
    assert tok_b.line == 2
    assert tok_b.col == 5

def test_eof_token():
    source = "let x = 1;"
    tokens = Lexer(source).tokenize()
    assert tokens[-1].type == 'EOF'
