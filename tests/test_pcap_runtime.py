"""Direct runtime regression coverage for classic PCAP writer bounds."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from axiom.cli import find_c_compiler

ROOT = Path(__file__).resolve().parent.parent


def test_pcap_writer_rejects_invalid_or_oversized_hex_and_roundtrips_cap(tmp_path):
    compiler = find_c_compiler()
    if not compiler:
        pytest.skip("C compiler unavailable")

    source = r'''
    #include "axiom/runtime.h"
    #include <stdio.h>
    #include <string.h>

    #define CHECK(expr) do { if (!(expr)) { \
        fprintf(stderr, "failed at line %d: %s\n", __LINE__, #expr); return 1; \
    } } while (0)

    int main(int argc, char** argv) {
        CHECK(argc == 2);
        ax_int writer = axiom_pcap_create_writer(argv[1]);
        CHECK(writer > 0);

        char max_hex[65535 * 2 + 1];
        char oversized_hex[65536 * 2 + 1];
        memset(max_hex, 'a', sizeof(max_hex) - 1);
        max_hex[sizeof(max_hex) - 1] = '\0';
        memset(oversized_hex, 'a', sizeof(oversized_hex) - 1);
        oversized_hex[sizeof(oversized_hex) - 1] = '\0';

        CHECK(axiom_pcap_write_packet(writer, max_hex));
        CHECK(!axiom_pcap_write_packet(writer, oversized_hex));
        CHECK(!axiom_pcap_write_packet(writer, "0g"));
        CHECK(!axiom_pcap_write_packet(writer, "abc"));
        CHECK(axiom_pcap_packet_count(writer) == 1);
        axiom_pcap_close(writer);

        ax_int reader = axiom_pcap_open_file(argv[1]);
        CHECK(reader > 0);
        ax_str packet = axiom_pcap_next_packet(reader);
        CHECK(axiom_pcap_reader_status(reader) == 1);
        CHECK(strlen(packet) == 65535 * 2);
        CHECK(packet[0] == 'a' && packet[1] == 'a');
        CHECK(axiom_pcap_packet_count(reader) == 1);

        ax_str eof = axiom_pcap_next_packet(reader);
        CHECK(eof[0] == '\0');
        CHECK(axiom_pcap_reader_status(reader) == 0);
        axiom_pcap_close(reader);
        return 0;
    }
    '''

    with tempfile.NamedTemporaryFile(
        suffix=".c", mode="w", encoding="utf-8", delete=False
    ) as src_file:
        src_path = Path(src_file.name)
        src_file.write(source)
    binary_path = tmp_path / "pcap-runtime-test"
    pcap_path = tmp_path / "roundtrip.pcap"
    try:
        compiled = subprocess.run(
            [
                compiler, "-O2", "-Wall", "-I", str(ROOT), str(src_path),
                "-o", str(binary_path), "-lssl", "-lcrypto", "-lz", "-ldl",
                "-pthread",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert compiled.returncode == 0, compiled.stderr
        result = subprocess.run(
            [str(binary_path), str(pcap_path)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        if src_path.exists():
            os.remove(src_path)
