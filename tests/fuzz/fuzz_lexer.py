"""
Axiom Programming Language (λx) - Lexer Fuzzer
Fuzzes the Lexer with randomized byte sequences, invalid UTF-8 sequences,
extreme token lengths, null bytes, and malicious control characters.
Guarantees zero crashes, zero unhandled panics, and controlled error handling.
"""
import random
import string
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from axiom.lexer import Lexer, LexerError

MUTATION_STRINGS = [
    "\x00", "\xff", "\xfe\xff", "\x00\x00\x00\x00",
    "fn \x00 main() { let x = \xff; }",
    'let str_val = "' + "A" * 10000 + '"',
    'let broken = "' + "\x00" * 50 + "\\n",
    "#" + "\x00" * 100 + "\n",
    "// " + "\xff\xfe\x00" * 50 + "\n",
    "\"" + "\\\\" * 500 + "\"",
    "let mut \U0001f4a9 = 123;",
    "0" * 5000 + "." + "9" * 5000,
    "..." * 200,
    "->->=>==!==<===>>=",
    "\t\r\n\x0b\x0c" * 100,
]

def generate_fuzz_sample() -> str:
    choice = random.randint(0, 5)
    if choice == 0:
        # Rastgele ASCII ve özel semboller
        length = random.randint(1, 500)
        return "".join(random.choice(string.printable) for _ in range(length))
    elif choice == 1:
        # Rastgele unicode kod noktaları
        length = random.randint(1, 200)
        chars = []
        for _ in range(length):
            try:
                cp = random.randint(0, 0x10FFFF)
                chars.append(chr(cp))
            except ValueError:
                chars.append("?")
        return "".join(chars)
    elif choice == 2:
        # Rastgele bozuk bayt dizisi (surrogate / errors='replace' ile decode)
        byte_data = bytes(random.randint(0, 255) for _ in range(random.randint(1, 500)))
        return byte_data.decode("utf-8", errors="replace")
    elif choice == 3:
        # Bilinen mutasyon şablonu + gürültü
        base = random.choice(MUTATION_STRINGS)
        noise = "".join(random.choice("0123456789abcdef+-*/=<>{}(),;.: \t\n\"") for _ in range(random.randint(0, 50)))
        return base + noise
    elif choice == 4:
        # Kırpılmış veya dengesiz tırnak/yorum
        prefix = random.choice(['"', "'", "#", "//", "/*", "let x = "])
        body = "".join(random.choice(string.ascii_letters + string.digits + "\\\n\r\t\"") for _ in range(random.randint(1, 300)))
        return prefix + body
    else:
        # Derin iç içe operatör kombinasyonları
        return "".join(random.choice(["(", ")", "{", "}", "[", "]", "->", "=>", "==", "!=", "<=", ">=", "+", "-", "*", "/", "%", " "]) for _ in range(200))


def run_lexer_fuzz(iterations: int = 1000):
    for i in range(iterations):
        sample = generate_fuzz_sample()
        try:
            lexer = Lexer(sample)
            tokens = lexer.tokenize()
            assert isinstance(tokens, list)
            # Her token geçerli alanlara sahip olmalı
            for tok in tokens:
                assert hasattr(tok, 'type')
                assert hasattr(tok, 'value')
                assert hasattr(tok, 'line')
                assert hasattr(tok, 'col')
        except LexerError:
            # Beklenen güvenli hata
            pass
        except Exception as e:
            raise AssertionError(f"Fuzzing Crash detected on Lexer at iteration {i}!\nInput: {repr(sample[:100])}\nException: {type(e).__name__}: {e}")


def test_fuzz_lexer_random_bytes_and_utf8():
    """Pytest entrypoint for Lexer robustness fuzzing."""
    run_lexer_fuzz(iterations=1000)


if __name__ == "__main__":
    print("[*] Lexer Fuzzer baslatiliyor (2000 iterasyon)...")
    run_lexer_fuzz(iterations=2000)
    print("[+] Lexer Fuzzing basariyla tamamlandi! Sifir cokme (0 crash).")
