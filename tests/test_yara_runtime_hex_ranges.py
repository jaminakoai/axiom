"""Direct C-runtime regression coverage for bounded YARA hex jumps."""

import os
import subprocess
import tempfile
from pathlib import Path

from axiom.cli import find_c_compiler


ROOT = Path(__file__).resolve().parent.parent


def _compile_and_run(source: str) -> tuple[int, str, str]:
    cc = find_c_compiler()
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as src_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        src_path = src_file.name
        bin_path = bin_file.name
        src_file.write(source)
    try:
        command = [
            cc, "-O2", "-Wall", "-I", str(ROOT), src_path, "-o", bin_path,
            "-lssl", "-lcrypto", "-lz", "-ldl", "-pthread",
        ]
        compiled = subprocess.run(command, capture_output=True, text=True, timeout=120)
        assert compiled.returncode == 0, compiled.stderr
        result = subprocess.run([bin_path], capture_output=True, text=True, timeout=15)
        return result.returncode, result.stdout, result.stderr
    finally:
        if os.path.exists(src_path):
            os.remove(src_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)


def test_range_finds_lowest_offset_and_shortest_gap_at_ties():
    source = r'''
    #include "axiom/runtime.h"
    #include <stdio.h>

    #define CHECK(expr) do { if (!(expr)) { \
        fprintf(stderr, "failed at line %d: %s\n", __LINE__, #expr); return 1; \
    } } while (0)

    int main(void) {
        const char* encoded = "hexrange:41|1|3|44";
        const char later_shorter[] = {'A', 'x', 'x', 'D', 'A', 'x', 'D', '\0'};
        CHECK(axiom_yara_find_hex_range(later_shorter, encoded, -1, -1) == 0);
        CHECK(axiom_yara_find_hex_range_length(later_shorter, encoded, 0) == 4);
        CHECK(axiom_yara_find_hex_range(later_shorter, encoded, 1, -1) == 4);
        CHECK(axiom_yara_find_hex_range_length(later_shorter, encoded, 4) == 3);
        CHECK(axiom_yara_find_hex_range_length(later_shorter, encoded, 1) == -1);

        const char two_gaps[] = {'A', 'x', 'D', 'x', 'D', '\0'};
        CHECK(axiom_yara_find_hex_range_length(two_gaps, encoded, 0) == 3);

        CHECK(axiom_yara_find_hex_range("AB", "hexrange:41|0|0|42", -1, -1) == 0);
        CHECK(axiom_yara_find_hex_range_length("AB", "hexrange:41|0|0|42", 0) == 2);
        CHECK(axiom_yara_find_hex_range("AB", "hexrange:{ 4? }|0|2|?2", -1, -1) == 0);
        CHECK(axiom_yara_find_hex_range_length("AB", "hexrange:{ 4? }|0|2|?2", 0) == 2);
        puts("YARA_HEX_RANGE_MATCHING_OK");
        return 0;
    }
    '''
    ret, out, err = _compile_and_run(source)
    assert ret == 0, err
    assert "YARA_HEX_RANGE_MATCHING_OK" in out


def test_range_rejects_invalid_encoding_and_bounds():
    source = r'''
    #include "axiom/runtime.h"
    #include <stdio.h>
    #include <string.h>

    #define CHECK_REJECTS(encoded) do { \
        if (axiom_yara_find_hex_range("AB", (encoded), -1, -1) != -1) { \
            fprintf(stderr, "accepted invalid encoding: %s\n", (encoded)); return 1; \
        } \
    } while (0)

    int main(void) {
        CHECK_REJECTS("hexrange:|0|1|42");
        CHECK_REJECTS("hexrange:41|0|1|");
        CHECK_REJECTS("hexrange:41|0|1");
        CHECK_REJECTS("hexrange:41|0|1|42|43");
        CHECK_REJECTS("hexrange:41|-1|1|42");
        CHECK_REJECTS("hexrange:41|2|1|42");
        CHECK_REJECTS("hexrange:41|0|65|42");
        CHECK_REJECTS("hexrange:41|0|17|42");
        CHECK_REJECTS("hexrange:4|0|1|42");
        CHECK_REJECTS("hexrange:41|0|1|42#comment");
        CHECK_REJECTS("hexrange:41[1]|0|1|42");
        CHECK_REJECTS("hexrange:41|x|1|42");
        CHECK_REJECTS("hexrange:41|0|1|4");

        char oversized[8194];
        memcpy(oversized, "hexrange:", 9);
        memset(oversized + 9, '4', sizeof(oversized) - 10);
        oversized[sizeof(oversized) - 1] = '\0';
        CHECK_REJECTS(oversized);

        if (axiom_yara_find_hex_range_length("AB", "hexrange:41|0|0|42", -1) != -1) {
            fprintf(stderr, "accepted negative exact offset\n");
            return 1;
        }
        puts("YARA_HEX_RANGE_INVALID_FORMS_REJECTED");
        return 0;
    }
    '''
    ret, out, err = _compile_and_run(source)
    assert ret == 0, err
    assert "YARA_HEX_RANGE_INVALID_FORMS_REJECTED" in out


def test_range_offset_bounds_are_overflow_safe():
    source = r'''
    #include "axiom/runtime.h"
    #include <stdio.h>

    int main(void) {
        const char* encoded = "hexrange:41|0|0|42";
        if (axiom_yara_find_hex_range("XB", encoded, 0, INT64_MAX) != -1) return 1;
        if (axiom_yara_find_hex_range("AB", encoded, INT64_MAX, INT64_MAX) != -1) return 1;
        if (axiom_yara_find_hex_range("AB", encoded, 0, 0) != 0) return 1;
        if (axiom_yara_find_hex_range("AB", encoded, 1, 1) != -1) return 1;
        puts("YARA_HEX_RANGE_OFFSETS_OK");
        return 0;
    }
    '''
    ret, out, err = _compile_and_run(source)
    assert ret == 0, err
    assert "YARA_HEX_RANGE_OFFSETS_OK" in out


def test_shared_hex_occurrence_api_counts_and_selects_canonical_instances():
    source = r'''
    #include "axiom/runtime.h"
    #include <stdio.h>

    #define CHECK(expr) do { if (!(expr)) { \
        fprintf(stderr, "failed at line %d: %s\n", __LINE__, #expr); return 1; \
    } } while (0)

    int main(void) {
        const char* range = "hexrange:41|1|3|42";
        CHECK(axiom_yara_count_hex_pattern("A1B A12B", range) == 2);
        CHECK(axiom_yara_nth_hex_pattern_offset("A1B A12B", range, 1) == 0);
        CHECK(axiom_yara_nth_hex_pattern_offset("A1B A12B", range, 2) == 4);
        CHECK(axiom_yara_nth_hex_pattern_length("A1B A12B", range, 1) == 3);
        CHECK(axiom_yara_nth_hex_pattern_length("A1B A12B", range, 2) == 4);
        CHECK(axiom_yara_nth_hex_pattern_offset("A1B A12B", range, 3) == -1);
        // Multiple valid jump lengths at one start yield one shortest instance.
        CHECK(axiom_yara_count_hex_pattern("A1B2B", range) == 1);
        CHECK(axiom_yara_nth_hex_pattern_length("A1B2B", range, 1) == 3);
        // Different starts may overlap; each start is counted once.
        CHECK(axiom_yara_count_hex_pattern("AAA", "hexrange:41|0|1|41") == 2);

        const char* alt = "hexalt:41 42 43|41 44 43";
        CHECK(axiom_yara_count_hex_pattern("ABC ADC", alt) == 2);
        CHECK(axiom_yara_nth_hex_pattern_offset("ABC ADC", alt, 2) == 4);
        CHECK(axiom_yara_nth_hex_pattern_length("ABC ADC", alt, 2) == 3);
        // Both branches match at offset zero, but YARA reports one instance.
        CHECK(axiom_yara_count_hex_pattern("ABC", "hexalt:41 4? 43|41 42 43") == 1);

        const char* negation = "hexnot:41|42|43";
        CHECK(axiom_yara_count_hex_pattern("ADC ABC AEC", negation) == 2);
        CHECK(axiom_yara_nth_hex_pattern_offset("ADC ABC AEC", negation, 2) == 8);
        CHECK(axiom_yara_nth_hex_pattern_length("ADC ABC AEC", negation, 2) == 3);
        CHECK(axiom_yara_count_hex_pattern("AB", "hexnot:|42|") == 1);
        CHECK(axiom_yara_nth_hex_pattern_offset("AB", "hexnot:|42|", 1) == 0);
        CHECK(axiom_yara_nth_hex_pattern_length("AB", "hexnot:|42|", 1) == 1);

        CHECK(axiom_yara_count_hex_pattern("ABAB", "hex:41 42") == 2);
        CHECK(axiom_yara_nth_hex_pattern_offset("ABAB", "hex:41 42", 2) == 2);
        CHECK(axiom_yara_count_hex_pattern("AB", "hexrange:bad") == -1);
        puts("YARA_HEX_OCCURRENCE_API_OK");
        return 0;
    }
    '''
    ret, out, err = _compile_and_run(source)
    assert ret == 0, err
    assert "YARA_HEX_OCCURRENCE_API_OK" in out
