# Axiom historical compatibility fixtures

The release fixture harness is `tools/check_compatibility_fixtures.py`; the
manifest format is [compat-fixture-manifest.schema.json](../../../docs/api/compat-fixture-manifest.schema.json).
Each immutable release snapshot belongs in `releases/vMAJOR.MINOR.PATCH/` and
contains `manifest.json` plus the source, package-project, and scanner files it
references. Keep fixtures from published release commits unchanged.

Manifest schema version 2 supports:

- source programs with exact stdout/exit status and C/LLVM backend coverage;
- complete package projects, including `axiom.toml` and `axiom.lock`, whose
  directory tree is SHA-256 pinned and built with current tools;
- scanner rules and target bytes, plus expected JSON reports validated against a
  release-pinned scanner report JSON Schema. Schema, inputs and reports are all
  SHA-256 pinned; each scanner case references its schema by ID.

The JSON Schema captures the portable manifest shape; the Python validator also
enforces semantic constraints such as globally unique IDs, matching
release-directory names, valid Draft 2020-12 report schemas, schema/report
compatibility, and content hashes. During a compatibility run, actual scanner
reports are checked against the pinned historical schema before exact comparison
with expected JSON. All fixture paths are relative to their release directory;
the validator rejects path traversal and release directory symlinks, and package
trees may not contain symlinks. Builds run in temporary directories. The
scanner's reported target is normalized to its basename, and `tool_version` must
remain a string but may advance, so checkout paths and new scanner releases do
not invalidate the historical report contract.

The current project is still `0.5.0-alpha`; it has no published `1.x` release
fixtures. CI validates any snapshots that exist, but the two-previous-minor gate
first becomes eligible while preparing `v1.2`, after `v1.0` and `v1.1` fixtures
have been committed.
