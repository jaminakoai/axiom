# G4 — Registry client archive resource bounds

**Date:** 17 November 2026
**Status:** Implementation, focused local tests, full GitHub CI, and native
platform smoke pass.

## Finding

`RegistryClient.download()` fetched package tarballs without a byte cap, read
cached tarballs completely before checking them, and sent gzip/tar data directly
to extraction and cache comparison. A registry response or local cache entry
could therefore consume excessive memory, decompression work, disk space, or
metadata memory. `axpm registry assemble` already enforced most archive limits,
but its consumer did not.

## Changes

- Centralized registry archive limits so package production, assembly, and
  client installation use the same policy: 256 MiB compressed package, 256 MiB
  aggregate regular-file payload, 20,000 archive members, 1 MiB manifest,
  1 MiB per PAX/GNU extension read, and 32 MiB cumulative tar metadata reads.
- Capped HTTP and `file://` downloads at `limit + 1` bytes, independent of
  `Content-Length`; checked cache file size before reading and used a bounded
  read. Cache tree parity checking exits on unexpected entries and caps member,
  directory, and aggregate-byte work.
- Decompressed gzip data incrementally into a spooled temporary file with an
  expanded-stream ceiling. Tar parsing uses the bounded reader and guarded
  `TarInfo` before the first header/PAX record is parsed. Regular payload reads
  are excluded from the metadata budget, while their actual byte count must
  equal the declared size. Extraction repeats that length check before the
  temporary cache is renamed into place.
- `axpm pack` preflights tracked member count, aggregate and manifest sizes
  before reading file payloads; it bounds reads against the remaining allowance
  and rejects over-limit compressed output before signing or staging it.
- Cache policy/signature errors remain errors. Transient cache read I/O errors
  preserve the cache; invalid archive limits remove the invalid cache and fail
  closed.

## Verification

```text
python3 -m pytest -q tests/test_registry.py tests/test_package_manager.py \
  tests/test_external_validation_docs.py tests/test_registry_docs.py
137 passed in 13.88s

make fmt-check
passed

python3 -m py_compile axiom/registry.py axiom/package_manager.py \
  tests/test_registry.py tests/test_package_manager.py
passed

git diff --check
passed
```

Regressions cover bounded HTTP and file downloads, oversized cache entries,
gzip expansion (including concatenated members), invalid gzip headers/CRC,
truncated tar payloads, manifest/member/PAX metadata limits, cumulative metadata
limits, cache I/O behavior, and package producer preflight. A valid 33 MiB
payload was installed by the client and accepted by the assembler using the
same archive, confirming payload bytes do not consume the 32 MiB metadata
budget.

Commit `476e06f` passed full GitHub CI [run
43984657720](https://github.com/jaminakoai/axiom/actions/runs/43984657720):
**7/7 jobs passed**. Python 3.10, 3.11, 3.12, and 3.13 each reported
**1558 passed, 27 skipped**; documentation code blocks reported **55 passed**.
The pinned real-YARA corpus differential job reported **29 passed** on each
Python version. Native platform smoke [run
43984657727](https://github.com/jaminakoai/axiom/actions/runs/43984657727)
passed **Linux, Windows, and macOS 3/3**.

## Limits and remaining work

- Packages above these fixed limits are intentionally rejected. Increasing
  them requires revisiting memory/disk budgets and producer/assembler/client
  parity together.
- `axpm pack` still builds bounded archive buffers in memory; the size cap
  prevents unbounded growth but does not make peak memory usage equal to the
  compressed archive size.
- G4 still requires a hosting decision, production key custody/rotation, and
  an officially published versioned package.
