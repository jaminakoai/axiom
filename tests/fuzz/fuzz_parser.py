"""
Axiom Programming Language (λx) - Parser Fuzzer
Fuzzes the Parser with malformed ASTs, mismatched brackets, deeply nested expressions,
truncated statements, and random keyword combinations.
Guarantees graceful failure (ParserError or LexerError) without unhandled crashes.
"""
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from axiom.lexer import Lexer, LexerError
from axiom.parser import Parser, ParserError

SAMPLE_CONSTRUCTS = [
    "fn test(a: int, b: str) -> int { return a; }",
    "let mut x: int = 10 + 20 * 30;",
    "if x > 0 { print(x); } else { print(0); }",
    "while x > 0 invariant x >= 0 { x = x - 1; }",
    "for i in 0..10 invariant i >= 0 { print(i); }",
    "struct User { id: int, name: str }",
    "defer { print(\"done\"); }",
    "let y = x as float;",
    "verify x >= 0, \"Positive expected\";",
    "match x { 1 => print(\"one\"), else => print(\"other\") }",
]

KEYWORDS = [
    "fn", "let", "mut", "if", "else", "while", "for", "in", "return",
    "print", "verify", "requires", "ensures", "struct", "import", "true",
    "false", "and", "or", "not", "defer", "invariant", "as", "match"
]

OPERATORS = ["+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">=", "->", "=>", "=", ".", ":", ",", ";"]
DELIMITERS = ["(", ")", "{", "}", "[", "]"]

def generate_parser_fuzz_sample() -> str:
    choice = random.randint(0, 5)
    if choice == 0:
        # Dengesiz parantez fırtınası
        depth = random.randint(10, 200)
        open_c = random.choice(["(", "{", "["])
        close_c = random.choice([")", "}", "]"])
        return (open_c * depth) + "let x = 1;" + (close_c * random.randint(0, depth))
    elif choice == 1:
        # Rastgele anahtar kelime çorbası
        length = random.randint(5, 50)
        return " ".join(random.choice(KEYWORDS + OPERATORS + DELIMITERS) for _ in range(length))
    elif choice == 2:
        # Geçerli bir yapıyı bozma (truncation & mutation)
        base = random.choice(SAMPLE_CONSTRUCTS)
        cut_point = random.randint(1, len(base))
        mutated = base[:cut_point]
        if random.random() < 0.5:
            mutated += " " + random.choice(KEYWORDS + OPERATORS)
        return mutated
    elif choice == 3:
        # Aşırı derin iç içe if/while/block
        code = ""
        depth = random.randint(5, 50)
        for _ in range(depth):
            code += random.choice(["if true { ", "while false { ", "{ ", "for i in 0..1 { "])
        code += "let x = 42;"
        for _ in range(random.randint(0, depth)):
            code += " }"
        return code
    elif choice == 4:
        # Zincirleme ikili operatörler
        ops = ["+", "-", "*", "/", "and", "or", "==", "!=", "<", "as int", "as float"]
        expr = "1 " + " ".join(f"{random.choice(ops)} {random.randint(1, 100)}" for _ in range(random.randint(10, 80)))
        return f"fn main() -> int {{ return {expr}; }}"
    else:
        # Rastgele identifier ve eksik noktalı virgüller
        return "let a = b let c = d fn f( fn g() { return 1"


def run_parser_fuzz(iterations: int = 1000):
    for i in range(iterations):
        sample = generate_parser_fuzz_sample()
        try:
            lexer = Lexer(sample)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            prog = parser.parse()
            assert prog is not None
        except (ParserError, LexerError):
            # Beklenen güvenli sözdizim hatası
            pass
        except RecursionError:
            raise AssertionError(f"Stack overflow / RecursionError in parser at iter {i}!")
        except Exception as e:
            raise AssertionError(f"Parser unhandled crash at iteration {i}!\nInput: {repr(sample[:100])}\nException: {type(e).__name__}: {e}")


def test_fuzz_parser_random_ast_and_delimiters():
    """Pytest entrypoint for Parser fuzzing."""
    run_parser_fuzz(iterations=1000)


if __name__ == "__main__":
    print("[*] Parser Fuzzer baslatiliyor (1500 iterasyon)...")
    run_parser_fuzz(iterations=1500)
    print("[+] Parser Fuzzing basariyla tamamlandi! Sifir panik/crash (0 crash).")
