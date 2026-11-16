# Signed registry release preflight for the sample package

**Date:** 2026-11-16  
**Status:** Local integration test passed. No package was published.

## What changed

Added `test_sample_scan_report_signed_registry_release_preflight` to
`tests/test_package_manager.py`. It copies the real `packages/axiom-scan-report`
into a temporary monorepo and commits that fixture, creates an ephemeral
Ed25519 keypair, runs `axpm pack`, writes a temporary `file://` registry, then
installs the package into a clean consumer and executes its test with `axpm test`.
The temporary key, registry, and checkout live under pytest's temporary path.

This keeps the `axpm pack` clean-commit requirement testable even if the main
working tree has unrelated local changes. It does not upload artifacts or use a
production key.

## Validation

Commands run:

```text
python -m pytest -q tests/test_package_manager.py tests/test_registry.py
77 passed in 11.05s
make fmt-check
passed
git diff --check
passed
```

## Limits and next step

This is a release preflight for the repository's example package. It does not
resolve hosting, upload/index administration, or production signing-key
operations. G4's official package publication remains open until those are
configured and a version is actually published.
