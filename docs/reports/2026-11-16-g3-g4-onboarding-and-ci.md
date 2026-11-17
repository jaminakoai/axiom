# G3/G4 onboarding fixes and current CI evidence

**Date:** 17 November 2026
**Reviewed source commit:** `dd0f997` (includes the guide, issue form, tests, and latest CI record)
**Status:** Documentation improvements and local checks complete; external G3 and official G4 release gates remain open.

## What changed

- Made `docs/EXTERNAL_VALIDATION.md` fully usable in Turkish and English, including
  prerequisites, setup, expected output, real file/PCAP steps, and feedback fields.
- Clarified that the five-minute estimate assumes Debian/Ubuntu system tools are
  already installed and added the tested commit command and expected match offset
  and length.
- Routed sanitized, non-security usability reports to GitHub Issues. The guide
  tells testers not to publish suspected vulnerabilities, raw files/PCAPs,
  contents, rule text, credentials, personal data, or private paths. SHA-256 is
  blank by default. Reports without public consent need a private channel agreed
  with the maintainer before details are sent.
- Added `.github/ISSUE_TEMPLATE/external-scan-trial.yml`, a bilingual public
  issue form. It requires authorization and public-disclosure consent, has no
  upload field, and asks for selected output values only; it warns against
  sharing whole JSON, target names, paths, hashes, or other private values.
- Added `tests/test_external_validation_docs.py` to guard guide links, the smoke
  instructions and result, bilingual fields, privacy guidance, the issue form,
  and report routes.
- Marked `registry.axiom-lang.org` as not deployed in `docs/REGISTRY.md`; the
  `DEFAULT_REGISTRY` code behavior was not changed. Added a local signed package
  → `file://` registry → clean consumer install/test procedure and
  `tests/test_registry_docs.py`.
- Updated `TODO.md` with the new G3/G4 documentation work and the latest CI
  evidence.

## Verification

### Clean-clone onboarding smoke

Executed the documented flow from a fresh shallow clone of GitHub `master`:

```text
commit: 1e9dd235394b1f5d1fbc730c84c2b6be6d8972c5
environment: Linux x86_64, Python 3.13
elapsed: 18.2 s
axiom --version: Axiom (λx) v0.5.0-alpha
rules: ok=true, rules=1
scan: ok=true, match_count=1
match: Axiom_External_Validation, offset=36, length=37
target_sha256: 1672850fcdc2a61c372188931ea164f8df197a0f87df96e0dd211a4ff02ed405
```

The target was the harmless sentinel from the guide. This is install/build/smoke
evidence only and does **not** satisfy independent-user validation.

Repeated from a fresh shallow clone after the latest roadmap/documentation
commit:

```text
commit: dd0f9977be99a3ca89b09c41fdd3ea502205351a
environment: Linux x86_64, Python 3.13
axiom --version: Axiom (λx) v0.5.0-alpha
rules: ok=true, rules=1
scan: ok=true, match_count=1
match: Axiom_External_Validation, offset=36, length=37
target_sha256: 1672850fcdc2a61c372188931ea164f8df197a0f87df96e0dd211a4ff02ed405
```

This repeated check proves the onboarding steps still work at `dd0f997`; it is
still only a synthetic smoke test and does **not** satisfy G3 acceptance.

### GitHub checks for source commit `dd0f997`

- Full CI [run 43980332183](https://github.com/jaminakoai/axiom/actions/runs/43980332183):
  **7/7 jobs passed**. Python 3.10, 3.11, 3.12, and 3.13 each reported
  **1539 passed, 27 skipped**; documentation code blocks reported **55 passed**.
  The pinned real-YARA corpus differential job reported **29 passed** on each
  Python version.
- Native platform smoke [run 43980332305](https://github.com/jaminakoai/axiom/actions/runs/43980332305):
  **Linux, Windows, and macOS 3/3 passed**.

### Earlier GitHub checks for source commit `468e3d9`

- Full CI [run 43936054939](https://github.com/jaminakoai/axiom/actions/runs/43936054939):
  **7/7 jobs passed**. Python 3.10, 3.11, 3.12, and 3.13 each reported
  **1514 passed, 27 skipped**; documentation code blocks reported **55 passed**.
  The pinned real-YARA corpus differential job reported **29 passed** on each
  Python version.
- Native platform smoke [run 43936054928](https://github.com/jaminakoai/axiom/actions/runs/43936054928):
  **Linux, Windows, and macOS 3/3 passed**.

The modified docs and added regression tests were also checked locally:

```text
PyYAML 6.0.3 safe_load: valid document, 11 body elements, unique IDs, no upload field

python -m pytest -q tests/test_external_validation_docs.py tests/test_registry_docs.py \
  tests/test_docs_en.py tests/test_docgen.py tests/test_tutorial_examples.py \
  tests/test_package_manager.py::test_sample_scan_report_signed_registry_release_preflight
45 passed in 24.33s

make fmt-check: passed
git diff --check: passed
python -m py_compile tests/test_external_validation_docs.py tests/test_registry_docs.py: passed
```

The local registry documentation flow was also executed in a clean clone by the
release audit: package signing and assembly succeeded, and the consumer's
`axpm test` reported **2/2 passed**. This did not upload a package or sign a
registry index.

## Remaining gates and limitations

- G3 remains open until an independent user tests a real authorized file or
  PCAP workflow and shares sanitized feedback.
- G4 remains open until hosting/canonical URL and production signing-key
  operations are selected and at least one versioned package is officially
  published. `registry.axiom-lang.org` does not currently resolve; the guide
  now states that clearly.
- Windows/macOS validation remains native build/run and the documented cache/file
  URL smoke subset. The full pytest and `axiom-scan` trial have not been verified
  on those operating systems.
- The public issue form URL redirects anonymous visitors to GitHub sign-in, so
  its authenticated browser rendering was not inspected. Its YAML was parsed
  locally and the committed issue-form content is covered by CI tests.

## Next steps

1. Obtain one independent, authorized G3 real-workflow report.
2. Decide the G4 registry host/deployment method and production signing-key
   custody; then stage and publish the first versioned example package.
