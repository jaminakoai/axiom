# Registry cache integrity hardening

**Date:** 2026-11-16  
**Status:** Implemented locally; focused tests pass. Full GitHub Actions for the
previous commit was still running when this report was written.

## Change

`RegistryClient.download` previously returned a cache hit after checking only
the tarball SHA-256. That allowed cached packages to bypass the current
signature and `allow_unsigned` policy, and it did not detect edits to the
already-extracted package files.

Cache hits now reapply SHA-256, the current Ed25519 signature or unsigned
policy, and compare every extracted regular file's path, content digest, size,
and normalized mode against the verified tarball. A modified extracted cache
is discarded and reconstructed from a verified download. The normal download
path uses the same SHA/signature/policy validation helper.

## Regression coverage

Added tests for:

- rejecting an invalid signature on a cache hit;
- rejecting an unsigned cache after policy changes from explicitly allowed to
  disallowed;
- restoring a modified extracted manifest from the signed archive.

The three new cases failed against the old behavior; they pass with the fix.

## Verification

```text
python -m pytest -q tests/test_registry.py
53 passed in 2.66s

python -m pytest -q tests/test_registry.py tests/test_package_manager.py
73 passed in 9.60s

make fmt-check && git diff --check
Biçimlendirme geçerli; git diff --check produced no errors.
```

The full GitHub CI run for base commit `cac4ab8` was still in progress and does
not contain this uncommitted change. It must not be counted as verification of
this patch; run CI again after commit/push.

## Remaining limits and next work

This hardening does not provide an upload path or official signing-key
operations. The G4 official package publication gate remains open. G3 still
requires an independent user to try `axiom-scan` with an authorized input and
share privacy-preserving feedback.
