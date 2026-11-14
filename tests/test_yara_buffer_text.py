"""Length-aware YARA text matching over binary buffers."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"


def _compile_and_run_c(source: str) -> tuple[int, str, str]:
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as source_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as binary_file:
        source_path = source_file.name
        binary_path = binary_file.name
        source_file.write(source)
    try:
        compiler = os.environ.get("CC", "cc")
        built = subprocess.run(
            [compiler, "-O2", "-Wall", "-I", str(ROOT), source_path, "-o", binary_path,
             "-lssl", "-lcrypto", "-lz", "-ldl", "-pthread"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert built.returncode == 0, built.stderr
        result = subprocess.run([binary_path], capture_output=True, text=True, timeout=15)
        return result.returncode, result.stdout, result.stderr
    finally:
        for path in (source_path, binary_path):
            if os.path.exists(path):
                os.remove(path)


def test_runtime_text_buffer_matches_nul_bytes_and_occurrence_semantics():
    source = r'''
    #include "axiom/runtime.h"
    #include <stdio.h>

    #define CHECK(expr) do { if (!(expr)) { \
        fprintf(stderr, "failed at line %d: %s\n", __LINE__, #expr); return 1; \
    } } while (0)

    int main(void) {
        ax_int buffer = axiom_buf_create(8);
        CHECK(buffer > 0);
        const unsigned char bytes[] = {'x', 0, 'A', 'b', 'B', 'B', 0, 'c', 'a', 't', 0, 'y'};
        for (size_t i = 0; i < sizeof(bytes); i++) axiom_buf_write_u8(buffer, bytes[i]);

        CHECK(axiom_yara_find_text_buf_handle(buffer, "A", 0, -1, -1) == 2);
        CHECK(axiom_yara_find_text_buf_handle(buffer, "a", 1, -1, -1) == 2);
        CHECK(axiom_yara_count_text_buf_handle(buffer, "b", 1) == 3);
        CHECK(axiom_yara_count_text_buf_handle(buffer, "bb", 1) == 2);
        CHECK(axiom_yara_nth_text_offset_buf_handle(buffer, "bb", 1, 2) == 4);
        CHECK(axiom_yara_nth_text_length_buf_handle(buffer, "bb", 1, 2) == 2);
        CHECK(axiom_yara_find_text_buf_handle(buffer, "cat", 8, -1, -1) == 7);
        CHECK(axiom_yara_find_text_buf_handle(buffer, "A", 8, -1, -1) == -1);
        CHECK(axiom_yara_find_text_buf_handle(buffer, "A", 0, 3, -1) == -1);
        CHECK(axiom_yara_count_text_buf_handle(buffer, "cat", 8) == 1);
        CHECK(axiom_yara_nth_text_offset_buf_handle(buffer, "missing", 0, 1) == -1);
        CHECK(axiom_yara_find_text_buf_handle(-1, "A", 0, -1, -1) == -1);
        CHECK(axiom_yara_count_text_buf_handle(12345, "A", 0) == -1);
        CHECK(axiom_yara_nth_text_offset_buf_handle(12345, "A", 0, 1) == -1);
        CHECK(axiom_yara_nth_text_length_buf_handle(12345, "A", 0, 1) == -1);

        // Existing string APIs retain their NUL-terminated behavior.
        const char legacy[] = {'x', 0, 'A', 'b', 'B', 'B', 0};
        CHECK(axiom_yara_find_text(legacy, "A", 0, -1, -1) == -1);
        CHECK(axiom_yara_count_text(legacy, "A", 0) == 0);
        CHECK(axiom_yara_find_text("xAbB", "A", 0, -1, -1) == 1);
        CHECK(axiom_yara_count_text("ababa", "aba", 0) == 2);
        CHECK(axiom_yara_nth_text_offset("ababa", "aba", 0, 2) == 2);

        axiom_buf_free(buffer);
        CHECK(axiom_yara_count_text_buf_handle(buffer, "A", 0) == -1);
        puts("YARA_BUFFER_TEXT_RUNTIME_OK");
        return 0;
    }
    '''
    code, stdout, stderr = _compile_and_run_c(source)
    assert code == 0, stderr
    assert "YARA_BUFFER_TEXT_RUNTIME_OK" in stdout


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_axiom_text_buffer_builtins_have_backend_parity(backend, tmp_path):
    source = r'''
    import "std/io/binary"

    fn main() -> int {
        let buffer = buf_create(8)
        buf_write_u8(buffer, 120)
        buf_write_u8(buffer, 0)
        buf_write_u8(buffer, 65)
        buf_write_u8(buffer, 98)
        buf_write_u8(buffer, 66)
        buf_write_u8(buffer, 66)
        buf_write_u8(buffer, 0)
        buf_write_u8(buffer, 99)
        buf_write_u8(buffer, 97)
        buf_write_u8(buffer, 116)
        buf_write_u8(buffer, 0)
        buf_write_u8(buffer, 121)

        verify rt_yara_find_text_buf_handle(buffer, "A", 0, -1, -1) == 2
        verify rt_yara_find_text_buf_handle(buffer, "a", 1, -1, -1) == 2
        verify rt_yara_count_text_buf_handle(buffer, "bb", 1) == 2
        verify rt_yara_nth_text_offset_buf_handle(buffer, "bb", 1, 2) == 4
        verify rt_yara_nth_text_length_buf_handle(buffer, "bb", 1, 2) == 2
        verify rt_yara_find_text_buf_handle(buffer, "cat", 8, -1, -1) == 7
        verify rt_yara_find_text_buf_handle(buffer, "A", 8, -1, -1) == -1
        verify rt_yara_count_text_buf_handle(12345, "A", 0) == -1
        buf_free(buffer)
        print("YARA_BUFFER_TEXT_BUILTIN_OK")
        return 0
    }
    '''
    source_path = tmp_path / "yara_buffer_text.ax"
    output_path = tmp_path / "yara_buffer_text"
    source_path.write_text(source, encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    command = [str(AXIOM), "build", str(source_path), "-o", str(output_path)]
    if backend == "llvm":
        command.insert(2, "--backend=llvm")
    built = subprocess.run(command, capture_output=True, text=True, timeout=300, env=env)
    assert built.returncode == 0, built.stdout + built.stderr
    result = subprocess.run([str(output_path)], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "YARA_BUFFER_TEXT_BUILTIN_OK" in result.stdout
