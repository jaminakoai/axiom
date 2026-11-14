"""Direct C runtime checks for typed YARA hex AST encoding limits."""

import os
import subprocess
import tempfile
from pathlib import Path

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


def test_typed_ast_rejects_malformed_opcodes_and_oversized_operands():
    source = r'''
    #include "axiom/runtime.h"
    #include <stdio.h>

    #define CHECK(expr) do { if (!(expr)) { \
        fprintf(stderr, "failed at line %d: %s\n", __LINE__, #expr); return 1; \
    } } while (0)

    int main(void) {
        const char *malformed[] = {
            "hexast:v1:B;",
            "hexast:v1:B41",
            "hexast:v1:B4;",
            "hexast:v1:X41;",
            "hexast:v1:J0-1;B42;",
            "hexast:v1:B41;J0-17;B42;",
            "hexast:v1:B41;J0--1;B42;",
            "hexast:v1:B41;J999999999999999999999-1;B42;",
            "hexast:v1:B41;J0-1;A42|43;",
            "hexast:v1:A41|;",
            "hexast:v1:A41||42;",
            "hexast:v1:A??|??;",
            "hexast:v1:A41|4243;",
            "hexast:v1:A41|42|43|44|45;",
            "hexast:v1:N??;",
            "hexast:v1:N?G;",
            "hexast:v1:N41;N42;"
        };
        for (size_t i = 0; i < sizeof(malformed) / sizeof(malformed[0]); i++) {
            CHECK(axiom_yara_count_hex_pattern("ABC", malformed[i]) == -1);
            CHECK(axiom_yara_nth_hex_pattern_offset("ABC", malformed[i], 1) == -1);
            CHECK(axiom_yara_nth_hex_pattern_length("ABC", malformed[i], 1) == -1);
        }

        const size_t max_text = AXIOM_YARA_MAX_HEX_PATTERN_TEXT;
        char *at_limit = (char*)calloc(max_text + 2, 1);
        CHECK(at_limit != NULL);
        const char *tag = "hexast:v1:";
        size_t used = strlen(tag);
        memcpy(at_limit, tag, used);
        at_limit[used++] = 'B';
        // 2727 `41` byte tokens separated by spaces make the full encoded AST
        // exactly 8192 bytes while keeping the payload syntactically valid.
        for (size_t i = 0; i < 2727; i++) {
            if (i) at_limit[used++] = ' ';
            at_limit[used++] = '4';
            at_limit[used++] = '1';
        }
        at_limit[used++] = ';';
        at_limit[used] = '\0';
        CHECK(used == max_text);
        // The target is shorter than the valid pattern, so successful parsing
        // yields zero occurrences; malformed/over-limit encoding yields -1.
        CHECK(axiom_yara_count_hex_pattern("A", at_limit) == 0);
        at_limit[used++] = 'X';
        at_limit[used] = '\0';
        CHECK(used == max_text + 1);
        CHECK(axiom_yara_count_hex_pattern("A", at_limit) == -1);
        free(at_limit);

        puts("YARA_TYPED_AST_LIMITS_OK");
        return 0;
    }
    '''
    returncode, stdout, stderr = _compile_and_run(source)
    assert returncode == 0, stderr
    assert "YARA_TYPED_AST_LIMITS_OK" in stdout
