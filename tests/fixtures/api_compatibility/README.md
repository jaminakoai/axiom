# Axiom historical compatibility fixtures

The release fixture harness is `tools/check_compatibility_fixtures.py`; the
manifest format is [compat-fixture-manifest.schema.json](../../../docs/api/compat-fixture-manifest.schema.json).
Each immutable release snapshot belongs in `releases/vMAJOR.MINOR.PATCH/` and
contains `manifest.json` plus the source, package-project, and scanner files it
references. Keep fixtures from published release commits unchanged.

The manifest supports:

- source programs with exact stdout/exit status and C/LLVM backend coverage;
- complete package projects, including `axiom.toml` and `axiom.lock`, whose
  directory tree is SHA-256 pinned and built with current tools;
- scanner rules, target bytes and expected JSON reports, each SHA-256 pinned.

All fixture paths are relative to their release directory; the validator rejects
path traversal, and package trees may not contain symlinks. Builds run in
temporary directories. The scanner's reported target is normalized to its
basename, and `tool_version` must remain a string but may advance, so checkout
paths and new scanner releases do not invalidate the historical report contract.

The current project is still `0.5.0-alpha`; it has no published `1.x` release
fixtures. CI validates any snapshots that exist, but the two-previous-minor gate
first becomes eligible while preparing `v1.2`, after `v1.0` and `v1.1` fixtures
have been committed.
