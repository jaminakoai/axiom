# G4 — Signed Registry index v2

**Date:** 17 November 2026  
**Base commit:** `089ffde` · **Implementation commit:** `23a0aca` · **Cross-platform lock regression:** `cc7de3a`
**Status:** Signed index generation and client verification implemented. Local full suite and GitHub CI passed. Official hosting, production trust-key lifecycle, and initial-use freshness remain open.

## What changed

- Added optional Registry schema 2 output to `axpm registry assemble`:
  `--index-signing-key`, `--index-sequence`, and `--index-expires` are required
  together. The index is signed over its exact UTF-8 bytes with Ed25519 and
  emitted beside `index.json` as base64 `index.json.sig`.
- Added the separate `index_public_key` manifest setting and
  `AXIOM_REGISTRY_INDEX_KEY` environment override. Configuring this key requires
  a valid schema 2 index; old schema 1 remains available when no index key is
  configured.
- The client rejects expired indexes and expirations more than 90 days ahead.
  It stores the highest accepted sequence and raw index SHA-256 by registry URL,
  rejects lower sequences and rejects different index bytes at the same
  sequence. A cross-process lock serializes sequence checks and writes.
- Index JSON and signature sidecars are read with fixed byte limits instead of
  reading unbounded registry responses into memory.
- Updated Turkish and English README descriptions, registry protocol docs,
  changelog, and the G4 master TODO.

## Verification

```text
python3 -m pytest -q tests/test_registry.py tests/test_package_manager.py \
  tests/test_registry_docs.py tests/test_external_validation_docs.py
117 passed in 13.24s; after the native-lock regression was added, the focused
command passed 118 tests in 13.29s on the latest local working tree.

python3 -m pytest -q
1565 passed in 1331.91s (0:22:11)

make fmt-check
passed

git diff --check
passed

python3 -m py_compile axiom/registry.py axiom/package_manager.py
passed

GitHub Actions CI on `23a0aca`
7/7 jobs passed: Python 3.10–3.13, ASan/UBSan, LLVM/DWARF, format.
https://github.com/jaminakoai/axiom/actions/runs/43962051440

Native platform smoke on `23a0aca`
Linux, Windows, macOS: 3/3 jobs passed.
https://github.com/jaminakoai/axiom/actions/runs/43962051589

After this report was first committed, `cc7de3a` added a child-process
regression for the rollback-state file lock to the native platform smoke
workflow. The test passed on Linux, Windows, and macOS (3/3):
https://github.com/jaminakoai/axiom/actions/runs/43966078968. The full CI for
`cc7de3a` passed 7/7; each Python 3.10–3.13 job reported 1539 passed / 27
skipped, and 55 documentation blocks passed:
https://github.com/jaminakoai/axiom/actions/runs/43966078962.
```

The tests cover signature validation, tampering, expiry, sequence rollback,
same-sequence equivocation, bounded index reads, legacy positional
`RegistryConfig` compatibility, deterministic signed assembly, and a clean
consumer installing and testing the sample package through a signed index.

## Limits and remaining work

- First use cannot prove that the served signed index is the newest one. A
  still-valid older signed index may be replayed before the client has observed
  a higher sequence.
- Removing the local index-state cache removes the client's remembered
  sequence. This is not a TUF-style transparency or trusted-timestamp system.
- The system clock is used for expiry checks. Registry hosts and clients need
  reliable clocks.
- This change does not choose or deploy hosting, publish a package, establish
  an official index key, or define key revocation/rotation operations.
- The full signed-index cryptographic path has not yet run on native Windows or
  macOS. The portable cross-process lock itself is covered by the new native
  platform smoke test.

## Next

Decide and document production key custody/rotation and registry hosting; keep
the first-use replay limitation visible in the release policy. Add native
Windows/macOS coverage for the signed-index OpenSSL verification path after
confirming those runners have a supported OpenSSL Ed25519 implementation.
