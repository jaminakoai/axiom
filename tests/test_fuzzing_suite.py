"""
Axiom Programming Language (λx) - Fuzzing Test Suite Adapter
Integrates tests/fuzz/ (fuzz_lexer, fuzz_parser, fuzz_json, fuzz_yara)
into the standard pytest regression matrix.
"""
import pytest
from tests.fuzz.fuzz_lexer import test_fuzz_lexer_random_bytes_and_utf8
from tests.fuzz.fuzz_parser import test_fuzz_parser_random_ast_and_delimiters
from tests.fuzz.fuzz_json import test_fuzz_json_runtime_stability
from tests.fuzz.fuzz_yara import test_fuzz_yara_hex_and_regex

def test_suite_fuzz_lexer():
    """Execute Lexer robustness fuzzer."""
    test_fuzz_lexer_random_bytes_and_utf8()

def test_suite_fuzz_parser():
    """Execute Parser grammar and delimiter fuzzer."""
    test_fuzz_parser_random_ast_and_delimiters()

def test_suite_fuzz_json():
    """Execute JSON runtime fuzzer."""
    test_fuzz_json_runtime_stability()

def test_suite_fuzz_yara():
    """Execute YARA hex and regex fuzzer."""
    test_fuzz_yara_hex_and_regex()
