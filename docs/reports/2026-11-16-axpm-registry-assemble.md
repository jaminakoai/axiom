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
metadata, and tar paths/types/modes. Gzip expansion is bounded and spooled to
temporary storage before tar parsing; PAX/GNU headers, regular-file bytes,
member count, sidecar size, and artifact count have explicit limits. It stages output beside the destination and renames
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
87 passed in 12.92s
make fmt-check
passed
python -m py_compile axiom/package_manager.py
passed
git diff --check
passed
bin/axpm registry assemble --help
passed
```

CI run `43886676395` for `c71e026` found that Python 3.13 did not reject the
oversized PAX test fixture, while Python 3.10, 3.11, and 3.12 each passed 1,507
tests and the other CI jobs succeeded. The local fix now decompresses through a
bounded spool and supplies a PAX/GNU guard before `tarfile` parses members. The
87 focused tests and PAX regression pass locally; a new CI run is still
required. The previous successful full CI was `2dda920` (7/7, 1,500 passed / 27
skipped per Python 3.10–3.13), and `c71e026` platform smoke passed 3/3 with four
selected tests on each OS.
