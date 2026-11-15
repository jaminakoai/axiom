"""Large-target stress coverage for the typed YARA hex executor."""

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
            [bin_path], capture_output=True, text=True, timeout=30, check=False
        )
        return result.returncode, result.stdout, result.stderr
    finally:
        if os.path.exists(src_path):
            os.remove(src_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)


def test_typed_executor_64mib_near_match_suffix_stress():
    """Count the 17 instances induced by one long bounded-jump match."""
    source = r'''
    #include "axiom/runtime.h"
    #include <stdio.h>
    #include <stdlib.h>
    #include <string.h>
    #include <time.h>

    int main(void) {
        const size_t target_len = (size_t)64 * 1024 * 1024;
        const size_t near_match_count = 16;
        const size_t stride = 2048;
        const size_t suffix_len = 999;
        uint8_t *target = (uint8_t*)malloc(target_len + 1);
        if (!target) return 2;
        memset(target, 'A', target_len);

        // Each suffix has 998 matching bytes. Sixteen candidates fail on the
        // final suffix byte; the seventeenth is exact. Dense A prefixes before
        // that one valid suffix yield 17 overlapping bounded-jump instances.
        for (size_t i = 0; i <= near_match_count; i++) {
            size_t prefix = 4096 + i * stride;
            target[prefix] = 'A';
            memset(target + prefix + 2, 'X', suffix_len - 1);
            target[prefix + 2 + suffix_len - 1] = i == near_match_count ? 'X' : 'Y';
        }
        target[target_len] = 0;

        const char *head = "hexast:v1:B41;J0-16;";
        size_t head_len = strlen(head);
        char *encoded = (char*)malloc(head_len + suffix_len * 4 + 1);
        if (!encoded) { free(target); return 2; }
        memcpy(encoded, head, head_len);
        size_t cursor = head_len;
        for (size_t i = 0; i < suffix_len; i++) {
            encoded[cursor++] = 'B';
            encoded[cursor++] = '5';
            encoded[cursor++] = '8';
            encoded[cursor++] = ';';
        }
        encoded[cursor] = 0;
        struct timespec before, after;
        clock_gettime(CLOCK_MONOTONIC, &before);
        ax_int count = axiom_yara_count_hex_pattern((const char*)target, encoded);
        clock_gettime(CLOCK_MONOTONIC, &after);
        double seconds = (double)(after.tv_sec - before.tv_sec) +
            (double)(after.tv_nsec - before.tv_nsec) / 1e9;
        printf("count=%lld target_bytes=%zu suffix_bytes=%zu near_matches=%zu seconds=%.6f\n",
            (long long)count, target_len, suffix_len, near_match_count, seconds);

        free(encoded);
        free(target);
        return count == 17 ? 0 : 1;
    }
    '''
    returncode, stdout, stderr = _compile_and_run(source)
    assert returncode == 0, stdout + stderr
    assert "count=17" in stdout
    assert "suffix_bytes=999" in stdout
    # Keep this adversarial fixture as a bounded performance regression gate.
    # The baseline is about 1.5 s on the reference development machine; the
    # 15 s ceiling leaves room for slower CI hosts while catching a major
    # candidate × suffix rescanning regression. The subprocess also has a
    # 30 s hard timeout as a final guard.
    measured = next(
        (field.split("=", 1)[1] for field in stdout.split() if field.startswith("seconds=")),
        None,
    )
    assert measured is not None, stdout
    assert float(measured) <= 15.0, stdout
