# Cross-platform registry cache smoke test

**Date:** 2026-11-16  
**Status:** Test and workflow change pushed in `ecc770d`. Native platform
smoke run 43871931643 passed on Linux, Windows, and macOS (3/3); the focused
registry cache-hit step passed on all three runners. Full CI run 43871931757
also passed (7/7 jobs): Python 3.10–3.13 each reported 1496 passed / 27
skipped, and documentation blocks reported 55 passed.

## Change

The `platform-smoke.yml` workflow now installs pytest and runs a focused
registry cache-hit test on Ubuntu, Windows, and macOS. The test constructs a
signed-content-independent local cache fixture and invokes `RegistryClient`
without requiring network access or OpenSSL. This exercises the current OS's
real filesystem mode behavior and proves the valid cache is reused.

The existing simulated-Windows permission test remains in the registry suite;
the new native smoke test supplements it with an actual cache hit on each
runner. This still does not run the complete pytest suite or `axiom-scan` on
Windows/macOS.

## Verification

```text
python -m pytest -q tests/test_registry.py -k 'download_cache_hit_is_portable_on_current_platform or cache_mode_check_handles_windows_chmod_semantics'
2 passed, 54 deselected in 0.26s

python -m pytest -q tests/test_registry.py tests/test_package_manager.py
76 passed in 10.53s
```

`make fmt-check` and `git diff --check` passed before commit. The previous
native smoke run 43871163733 predates this workflow edit and was not counted as
evidence. The new workflow result for 43871931643 is the cross-platform evidence;
full CI result 43871931757 is the full-project Linux test evidence.

## Remaining gates

G3 still requires an independent user validation. G4 still requires a chosen
hosted registry and signing-key operation before an official package can be
published.
