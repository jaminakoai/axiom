# G4 registry publication — 2026-11-17

## Result

Published `axiom-scan-report` 0.1.0 at
`https://jaminakoai.github.io/axiom/registry`. GitHub Actions run
[44053918679](https://github.com/jaminakoai/axiom/actions/runs/44053918679)
completed the build and deploy jobs successfully. GitHub Pages uses the
workflow source with HTTPS enforced. The `github-pages` environment requires a
review and permits deployments from `master` only.

## Trust and package verification

- Package tarball and schema 2 index use separate Ed25519 signing keys.
- Private PEM files are outside the repository at
  `~/.config/axiom/registry-keys/`, with directory mode `0700` and file mode
  `0600`. No private key was committed or uploaded.
- Public trust anchors ship in the Axiom Python package; the built wheel was
  inspected to confirm both PEM files are included.
- The published index returned HTTP 200. `fetch_index(RegistryConfig.from_manifest({}))`
  verified its Ed25519 signature, schema 2, sequence 1, and package listing.
- A clean consumer with no registry URL or key environment overrides installed
  `axiom-scan-report` 0.1.0 from the live endpoint and passed `axpm test` (2/2).
- A local signed-file-registry consumer test also passed (2/2).
- Full local repository test suite after trust-anchor overlap changes: **1623
  passed, 0 failed, 0 skipped** in 1342 seconds. Registry, docs, Pages, and
  release preflight subset before snapshot creation: **117 passed**; subsequent
  registry/key-overlap/docs/Pages subset: **124 passed**.

## Commits

- `0b53c17` — official registry default and bundled public trust anchors.
- `355fe20` — signed `axiom-scan-report` 0.1.0 schema 2 snapshot.

## Remaining operational work

An age-encrypted backup was created at
`~/.config/axiom/registry-key-backups/registry-signing-keys-2026-11-17.tar.age`
and decrypted to a temporary directory to verify both private keys against the
archive. The maintainer accepted this local encrypted copy as sufficient for
now. The ciphertext and matching SSH identity are on the same machine, so loss
of that device also loses this recovery path. Rotation is documented in
[`REGISTRY_OPERATIONS.md`](../REGISTRY_OPERATIONS.md); the client currently has
source support for up to eight overlapping anchors, but current official trust
files and live signatures still use one key per role. Existing client
distributions must deliver overlap before planned rotation. Schema 2 sequence rollback
protection cannot detect a stale signed index on first use or after local
rollback state is deleted.

GitHub Actions emitted Node.js 20 deprecation warnings for pinned Pages
deployment actions (currently executed under Node.js 24) and an upcoming
`ubuntu-latest` image migration notice. The publish succeeded; update pinned
actions when Node 24-native releases are available.
