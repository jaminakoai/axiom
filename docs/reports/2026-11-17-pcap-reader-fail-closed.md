# PCAP reader: fail-closed parsing and status reporting

**Date:** 2026-11-17  
**Status:** PCAP reader implementation and local targeted validation passed.
The Windows runtime ownership fault was fixed in `4d81ffe`; native PCAP smoke
passed on Linux, Windows, and macOS (run 43998977308, 3/3). Full CI for that
commit passed 7/7 (run 43998977282): Python 3.10–3.13 each had 1,573 passed / 27
skipped; docs 55, YARA differential 29, sanitizer 40, LLVM 20 passed.

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
- The native smoke workflow now has a targeted PCAP test step. Windows' first
  run failed while the test
  captured the compiler's Unicode checkmark using the legacy console encoding;
  the test fixture now sets an ASCII-safe Python output encoding. The next
  Windows run then exposed `0xC0000374` while the scanner wrapped a static empty
  string as an owned result. `axiom_ptr_is_static()` had a Linux ELF segment
  implementation but returned false on Windows, so `axiom_owned_str_wrap()`
  attempted to free the literal. It now delegates to `ax_os_ptr_is_static()` in
  `platform.h`, which uses `VirtualQuery`/`MEM_IMAGE` on Windows and the existing
  platform checks elsewhere. Independent code review confirmed this root cause.
  Commit `4d81ffe` passed the targeted PCAP suite on all three native OS runners.

## Validation

    python3 -m pytest -q --tb=short tests/test_pcap_runtime.py tests/test_axiom_scan.py tests/test_blueteam_libs.py tests/test_external_validation_docs.py
    180 passed in 23.82s
    make fmt-check
    passed
    git diff --check
    passed
    pytest -q --tb=short tests/test_axiom_scan.py -k pcap tests/test_pcap_runtime.py
    16 passed
    pytest -q --tb=short tests/test_negative_security.py -k str_free_literal
    1 passed
    pytest -q --tb=short tests/test_portability.py -k 'windows_target_produces_pe_binary or windows_code_path_runs_natively or windows_binary_runs_under_wine'
    3 passed (local MinGW/Wine portability checks; native Windows smoke also passed in run 43998977308)
    GitHub Actions full CI, commit 4d81ffe (run 43998977282)
    7/7 jobs passed; Python 3.10–3.13 each 1573 passed / 27 skipped;
    docs 55, YARA differential 29, sanitizer 40, LLVM 20 passed
    GitHub Actions native platform smoke, commit 4d81ffe (run 43998977308)
    Linux, Windows, macOS 3/3 passed, including PCAP scanner tests

Coverage includes empty packet followed by a matching packet, a valid capture
with no records, microsecond and nanosecond PCAP in both byte orders, pcapng
rejection, truncated global and record headers, short payload, inconsistent
captured/original lengths, default and custom snaplen limits, the 65,535-byte
limit, C/LLVM result parity, writer rejection of over-limit and invalid hex,
exact-limit writer roundtrip, and the existing PCAP API readback path.

## Limits and next step

PCAPNG, protocol decoding, and TCP stream reassembly remain unsupported. This
does not close G3: an independent user still needs to test an authorized real
file or capture and provide sanitized feedback. Native PCAP smoke is green on
Linux, Windows, and macOS, and full CI passed for `4d81ffe`.
