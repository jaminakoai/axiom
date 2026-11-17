# PCAP reader: fail-closed parsing and status reporting

**Date:** 2026-11-17  
**Status:** Local targeted validation passed. Full CI is pending for the source change.

## Finding

The PCAP reader returned an empty string for clean EOF, a zero-byte packet,
partial record headers, invalid lengths, and short packet data. The scanner
treated every empty result as EOF and could therefore report ok:true for an
incomplete capture. Record fields were read in host byte order without honoring
the file's byte order. The command scans captured packet bytes as-is; it does
not decode protocol headers or reassemble TCP streams.

## Changes

- Added pcap_read_status: 1 means a packet was read (including an empty
  packet), 0 means clean EOF at a record boundary, and -1 means invalid
  handle or a failed read. The existing pcap_read_next signature remains.
- The reader now parses classic PCAP global and record fields in either byte
  order, recognizes microsecond and nanosecond timestamp magic, and rejects
  invalid or truncated global headers.
- PCAPNG is detected and explicitly rejected (pcap_open_reader returns
  -3). Truncated record headers and payloads, incl_len > orig_len, values
  above the existing 65,535-byte packet cap, and values above snaplen fail
  closed.
- axiom-scan pcap counts empty packets and continues; it returns an error for
  malformed or truncated records instead of emitting a successful partial
  report.
- The writer now rejects odd-length/non-hex input and records larger than its
  65,535-byte snap length; allocation and write/flush failures return false and
  do not increment its packet count.
- README and the external trial guide now say that only classic PCAP is
  supported and that matching scans raw captured frames, including headers.
- The native smoke workflow now has a targeted PCAP test step; its Linux,
  Windows, and macOS run is pending.

## Validation

    python3 -m pytest -q --tb=short tests/test_pcap_runtime.py tests/test_axiom_scan.py tests/test_blueteam_libs.py tests/test_external_validation_docs.py
    178 passed in 23.85s
    make fmt-check
    passed
    git diff --check
    passed

Coverage includes empty packet followed by a matching packet, microsecond and
nanosecond PCAP in both byte orders, pcapng rejection, truncated global and
record headers, short payload, inconsistent captured/original lengths, the
65,535-byte limit, C/LLVM result parity, writer rejection of over-limit and
invalid hex, exact-limit writer roundtrip, and the existing PCAP API readback
path.

## Limits and next step

PCAPNG, protocol decoding, and TCP stream reassembly remain unsupported. This
does not close G3: an independent user still needs to test an authorized real
file or capture and provide sanitized feedback. The full CI and the added
Windows/macOS/Linux PCAP smoke run must pass before treating this implementation
as complete.
