# `axpm registry assemble` — offline static registry preparation

**Date:** 2026-11-16  
**Status:** Implemented and locally verified. No package was published.

## What changed

Added:

```text
axpm registry assemble --from PACK_OUTPUT --output NEW_DIR --public-key PUBKEY
```

The command validates `axpm pack` artifacts and prepares the Registry v1 static
tree (`index.json` plus `<package>/<version>.tar.gz`). It checks paired
archive/sidecar paths, package names and versions, canonical SHA-256 and
Ed25519 signatures, package metadata inside the signed `axiom.toml`, dependency
metadata, and tar paths/types/modes. Tar parsing is streaming and bounded for
compressed bytes, regular-file bytes, member count, PAX/GNU metadata, sidecar
size, and artifact count. It stages output beside the destination and renames
only after validation. Existing nonempty destinations, symlinks, nested source
and destination, and unmatched artifacts are rejected.

It is offline only: it does not upload, take a private key, or sign `index.json`.
The resulting files are not by themselves a public or fully authenticated
registry. Hosting, index integrity, and production key operations remain open.

The sample package release-preflight test now assembles the generated static
registry, checks deterministic output, installs the package into a clean
consumer using `file://`, and runs both the installed package test and consumer
integration test.

## Validation

```text
python -m pytest -q tests/test_package_manager.py tests/test_registry.py
87 passed in 12.88s
make fmt-check
passed
python -m py_compile axiom/package_manager.py
passed
git diff --check
passed
bin/axpm registry assemble --help
passed
```

The last successful full CI/platform matrix is source commit `2dda920`: full CI
7/7, with 1,500 passed and 27 skipped on each of Python 3.10–3.13; platform
smoke 3/3 with four selected tests passing on Linux, Windows, and macOS. The
assembler changes in this report were made after that CI run and need their own
CI run before being described as fully validated.
