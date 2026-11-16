# Registry metadata path validation and Windows cache parity

**Date:** 2026-11-16  
**Status:** Implemented locally; focused tests pass. GitHub CI for base commit
`d905d05` is still running and does not include this follow-up.

## Findings and changes

1. `expected_sha` came from registry index metadata and was used in the cache
   path before validation. An absolute or traversal value could point cleanup
   outside the cache. SHA values are now required to be exactly 64 hexadecimal
   characters before cache-path construction; `cache_path_for` enforces the
   same invariant independently.
2. The extracted-cache comparison expected POSIX permission bits to survive
   `chmod`. Windows only preserves its read-only state, so valid cache entries
   could be discarded on every hit. On Windows the comparison now checks the
   writable bit while POSIX systems retain the normalized mode comparison.

## Regression coverage

- A traversal SHA is rejected before the victim directory can be removed.
- A simulated Windows `st_mode` validates the cache despite Windows-style
  permission reporting.

## Verification

```text
python -m pytest -q tests/test_registry.py -k 'cache_mode_check_handles_windows_chmod_semantics or rejects_invalid_sha_before_using_cache_path or verifies_and_caches'
3 passed, 52 deselected in 0.23s

python -m pytest -q tests/test_registry.py tests/test_package_manager.py
75 passed in 9.96s
```

The Windows behavior is simulated by a regression test on the current host;
the native Windows smoke workflow does not run registry-cache tests. The next
full CI run must include this patch before it is considered verified across
platforms.

## Remaining gate

G3 still needs an independent `axiom-scan` user test. G4 still needs a real
registry hosting target and signing-key operations before the sample package
can be officially published.
