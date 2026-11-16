# Registry index metadata binding review

**Date:** 16 November 2026  
**Reviewed base commit:** `9fd0d52`  
**Status:** Client-side package metadata binding and registry index shape
validation are implemented locally. Targeted tests pass. Signed-index and
rollback policy remain release decisions.

## Finding

Registry v1 downloads `index.json` without authenticating it. Package tarballs
are SHA-256 checked and Ed25519-verified, but the installer did not compare the
signed package's `axiom.toml` with the unsigned index entry. The index controls
the package name, version, and dependency graph used for resolution and the lock
file.

The release audit reproduced this in an isolated temporary directory: it copied
a valid signed `real-package@1.0.0` archive under an `alias@9.9.9` registry path
and changed only the unsigned index metadata. `PackageManager.install()` then
succeeded and recorded `alias@9.9.9` in the lock file, while the signed manifest
still identified `real-package@1.0.0`.

This is a package identity and dependency integrity failure. It does not let an
attacker alter the signed archive bytes, but it can make a consumer receive a
different validly signed package than the requested registry identity implies.

## Fix applied

- The client reads the extracted, signature-covered `axiom.toml` and checks its
  package name and version against the registry coordinates.
- The client compares the manifest dependency map with the resolved index
  dependency map.
- The check runs before a new cache entry is promoted and before a cache hit is
  returned.
- `PackageManager.install()` passes the resolved dependencies to the client
  validation path.
- The manifest is limited to 1 MiB before TOML parsing.
- Registry index JSON now fails with clear `ValueError` messages for malformed
  roots, package names, version lists/entries, semver, hashes, signature types,
  dependency maps, and `yanked` values rather than leaking `AttributeError` from
  resolver code.

## Regression evidence

`tests/test_registry.py` now checks package-name relabeling, version retagging,
dependency-map substitution, and cache-hit relabeling. An end-to-end `axpm
install` test confirms a signed package aliased in the index fails and is not
installed or written to the lock file.

Local targeted verification:

```text
python3 -m pytest -q tests/test_registry.py tests/test_package_manager.py
104 passed
make fmt-check: passed
git diff --check: passed
```

Combined targeted verification (104 registry/package-manager tests plus 7
external-validation/registry documentation tests):

```text
python3 -m pytest -q tests/test_registry.py tests/test_package_manager.py \
  tests/test_external_validation_docs.py tests/test_registry_docs.py
111 passed in 13.02s
```

The local full suite reported **1521 passed, 27 failed** in 1264.57 s. All 27
failures were Windows cross-compilation/Wine tests that exposed the same
case-sensitive include issue: the source requested `BaseTsd.h`, while the
installed MinGW header is `basetsd.h`. The include was corrected and the entire
affected `tests/test_portability.py` file then passed (**34 passed in 100.61 s**).
The full suite was not repeated locally after that fix; the post-change full CI
run is the final broad verification gate. `make fmt-check`, `git diff --check`,
and Python byte compilation passed.

## Remaining registry trust limits

The client-side binding closes the observed package identity/version/dependency
substitution. Registry v1 still has no signed index, so an index operator or
attacker able to replace the index can change `yanked`, remove entries, or replay
an older otherwise valid signed package under its original identity/version.
Authenticating those policy and freshness decisions requires a signed-index
format and a rollback/freshness policy. The trusted key, rotation, and hosted
registry choices are not configured yet, so that design remains a G4 release
gate; do not treat current Registry v1 as tamper-evident metadata.
