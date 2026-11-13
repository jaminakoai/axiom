"""Direct runtime coverage for YARA hex occurrence enumeration."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from axiom.cli import find_c_compiler

ROOT = Path(__file__).resolve().parent.parent


def _compile_and_run(source: str) -> tuple[int, str, str]:
    compiler = find_c_compiler()
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as src_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        src_path = src_file.name
        bin_path = bin_file.name
        src_file.write(source)
    try:
        compiled = subprocess.run(
            [
                compiler, "-O2", "-Wall", "-I", str(ROOT), src_path, "-o", bin_path,
                "-lssl", "-lcrypto", "-lz", "-ldl", "-pthread",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert compiled.returncode == 0, compiled.stderr
        result = subprocess.run(
            [bin_path], capture_output=True, text=True, timeout=15, check=False
        )
        return result.returncode, result.stdout, result.stderr
    finally:
        if os.path.exists(src_path):
            os.remove(src_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)


def test_occurrence_runtime_handles_indices_masks_and_malformed_patterns():
    source = r'''
    #include "axiom/runtime.h"
    #include <stdio.h>

    #define CHECK(expr) do { if (!(expr)) { \
        fprintf(stderr, "failed at line %d: %s\n", __LINE__, #expr); return 1; \
    } } while (0)

    int main(void) {
        CHECK(axiom_yara_count_hex_pattern("ABAB", "hexast:v1:B41 42;") == 2);
        CHECK(axiom_yara_find_hex_pattern("ABAB", "hexast:v1:B41 42;", 1, -1) == 2);
        CHECK(axiom_yara_count_hex_pattern("A1B2B", "hexast:v1:B41;J1-3;B42;") == 1);
        CHECK(axiom_yara_nth_hex_pattern_length("A1B2B", "hexast:v1:B41;J1-3;B42;", 1) == 3);
        CHECK(axiom_yara_count_hex_pattern("ABC ADC", "hexast:v1:B41;A42|44;B43;") == 2);
        CHECK(axiom_yara_count_hex_pattern("ADC ABC", "hexast:v1:B41;N42;B43;") == 1);
        CHECK(axiom_yara_count_hex_pattern("ACXC", "hexast:v1:N42;B43;") == 2);

        const char* malformed_ast[] = {
            "hexast:v1:", "hexast:v1:B41", "hexast:v1:X41;",
            "hexast:v1:B41;J1-3;", "hexast:v1:B41;J1-3;N42;",
            "hexast:v1:B41;J3-1;B42;", "hexast:v1:B41;J0-65;B42;",
            "hexast:v1:B??;J0-16;B??;",
            "hexast:v1:A41;", "hexast:v1:A41|42|43|44|45;",
            "hexast:v2:B41;"
        };
        for (int i = 0; i < (int)(sizeof(malformed_ast) / sizeof(malformed_ast[0])); i++) {
            CHECK(axiom_yara_count_hex_pattern("ABC", malformed_ast[i]) == -1);
        }

        CHECK(axiom_yara_find_hex_pattern("ABAB", "hex:41 42", -1, -1) == 0);
        CHECK(axiom_yara_find_hex_pattern("ABAB", "hex:41 42", 1, -1) == 2);
        CHECK(axiom_yara_find_hex_pattern("ABAB", "hex:41 42", 0, 0) == 0);
        CHECK(axiom_yara_find_hex_pattern("ABAB", "hex:41 42", 1, 1) == -1);
        CHECK(axiom_yara_find_hex_pattern("A1B2B", "hexrange:41|1|3|42", 1, -1) == -1);
        CHECK(axiom_yara_find_hex_pattern("A1B2B", "hexrange:41|1|3|42", 0, 0) == 0);
        CHECK(axiom_yara_find_hex_pattern("ABC", "hex:41", 2, 1) == -1);

        CHECK(axiom_yara_count_hex_pattern("", "hex:41") == 0);
        CHECK(axiom_yara_nth_hex_pattern_offset("", "hex:41", 1) == -1);
        CHECK(axiom_yara_nth_hex_pattern_length("", "hex:41", 1) == -1);
        CHECK(axiom_yara_count_hex_pattern("A", "hex:41 42") == 0);
        CHECK(axiom_yara_count_hex_pattern("A", "hexrange:41|1|3|42") == 0);

        const char* range = "hexrange:41|1|3|42";
        CHECK(axiom_yara_count_hex_pattern("A1B2B", range) == 1);
        CHECK(axiom_yara_nth_hex_pattern_offset("A1B2B", range, 1) == 0);
        CHECK(axiom_yara_nth_hex_pattern_length("A1B2B", range, 1) == 3);
        // The same start has both gap 1 and gap 3; only its shortest instance counts.
        CHECK(axiom_yara_count_hex_pattern("A1B2B", range) == 1);

        const char* alt = "hexalt:41 4? 43|41 42 43";
        CHECK(axiom_yara_count_hex_pattern("ABC", alt) == 1);
        CHECK(axiom_yara_nth_hex_pattern_offset("ABC", alt, 1) == 0);
        CHECK(axiom_yara_nth_hex_pattern_length("ABC", alt, 1) == 3);

        const char* suffix_negation = "hexnot:|42|43";
        CHECK(axiom_yara_count_hex_pattern("ACXC", suffix_negation) == 2);
        CHECK(axiom_yara_nth_hex_pattern_offset("ACXC", suffix_negation, 1) == 0);
        CHECK(axiom_yara_nth_hex_pattern_offset("ACXC", suffix_negation, 2) == 2);
        CHECK(axiom_yara_nth_hex_pattern_length("ACXC", suffix_negation, 2) == 2);

        CHECK(axiom_yara_nth_hex_pattern_offset("ABC", "hex:41", 0) == -1);
        CHECK(axiom_yara_nth_hex_pattern_offset("ABC", "hex:41", -1) == -1);
        CHECK(axiom_yara_nth_hex_pattern_length("ABC", "hex:41", 0) == -1);
        CHECK(axiom_yara_nth_hex_pattern_length("ABC", "hex:41", -1) == -1);
        CHECK(axiom_yara_nth_hex_pattern_offset("ABC", "hex:41", 4) == -1);
        CHECK(axiom_yara_nth_hex_pattern_length("ABC", "hex:41", 4) == -1);

        // The public occurrence index is signed 64-bit. Extreme indices must
        // fail closed without wrapping into an earlier occurrence.
        CHECK(axiom_yara_nth_hex_pattern_offset("ABC", "hex:41", INT64_MAX) == -1);
        CHECK(axiom_yara_nth_hex_pattern_length("ABC", "hex:41", INT64_MAX) == -1);

        const char overlapping[] = {(char)0xAA, (char)0xAB, (char)0xAC, '\0'};
        const char* masked = "hex:A? A?";
        CHECK(axiom_yara_count_hex_pattern(overlapping, masked) == 2);
        CHECK(axiom_yara_nth_hex_pattern_offset(overlapping, masked, 1) == 0);
        CHECK(axiom_yara_nth_hex_pattern_offset(overlapping, masked, 2) == 1);
        CHECK(axiom_yara_nth_hex_pattern_length(overlapping, masked, 2) == 2);

        const char* malformed[] = {
            "", "hex:", "hexrange:bad", "hexalt:41|42 43", "hexnot:|??|", "unknown:41",
            // Numeric overflow, malformed separators, excess branches, and
            // ambiguous nested/combined constructs are rejected at runtime.
            "hexrange:41|999999999999999999999999|999999999999999999999999|42",
            "hexrange:41|0|1||42", "hexalt:41|42|43|44|45",
            "hexalt:41 (42|43)|44", "hexnot:41|42|43|44"
        };
        for (int i = 0; i < (int)(sizeof(malformed) / sizeof(malformed[0])); i++) {
            CHECK(axiom_yara_count_hex_pattern("ABC", malformed[i]) == -1);
            CHECK(axiom_yara_nth_hex_pattern_offset("ABC", malformed[i], 1) == -1);
            CHECK(axiom_yara_nth_hex_pattern_length("ABC", malformed[i], 1) == -1);
        }

        puts("YARA_HEX_OCCURRENCE_RUNTIME_OK");
        return 0;
    }
    '''
    returncode, stdout, stderr = _compile_and_run(source)
    assert returncode == 0, stderr
    assert "YARA_HEX_OCCURRENCE_RUNTIME_OK" in stdout


def test_occurrence_runtime_matches_yara_454_instance_semantics():
    try:
        import yara
    except ImportError:
        pytest.skip("yara-python is unavailable for the differential oracle")

    cases = [
        (
            "{ 41 [1-3] 42 }",
            b"A1B2B",
            "hexrange:41|1|3|42",
            [(0, 3)],
        ),
        (
            "{ 41 ( 4? | 42 ) 43 }",
            b"ABC",
            "hexalt:41 4? 43|41 42 43",
            [(0, 3)],
        ),
        (
            "{ ~42 43 }",
            b"ACXC",
            "hexnot:|42|43",
            [(0, 2), (2, 2)],
        ),
        (
            "{ A? A? }",
            bytes((0xAA, 0xAB, 0xAC)),
            "hex:A? A?",
            [(0, 2), (1, 2)],
        ),
    ]

    for source_pattern, target, _, expected in cases:
        rule_source = (
            "rule OccurrenceOracle {\n"
            " strings:\n  $a = " + source_pattern + "\n"
            " condition:\n  #a >= 0\n}\n"
        )
        matches = yara.compile(source=rule_source).match(data=target)
        actual = []
        if matches:
            actual = [
                (instance.offset, instance.matched_length)
                for string_match in matches[0].strings
                for instance in getattr(string_match, "instances", [])
            ]
        assert actual == expected

    # The assertions above pin the oracle cases. The direct C-runtime API is
    # exercised against the same target/pattern semantics in the test above.
