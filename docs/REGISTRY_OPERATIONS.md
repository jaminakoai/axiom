# Registry signing-key backup and rotation

This runbook covers the package-signing Ed25519 key and the separate schema 2
index-signing Ed25519 key used by the official registry.

## Current key storage and backup

- Active private keys live outside the repository at
  `~/.config/axiom/registry-keys/`; directory permissions are `0700`, private
  PEM permissions are `0600`.
- A verified encrypted recovery archive is stored locally at
  `~/.config/axiom/registry-key-backups/registry-signing-keys-2026-11-17.tar.age`.
  It contains both private keys, both public anchors, and restore notes. It is
  encrypted with age to the maintainer's `~/.ssh/id_ed25519.pub` recipient and
  was decrypted with `~/.ssh/id_ed25519` to verify the archive and key contents.
- The encrypted file is currently on the same machine as the source keys. Copy
  it to removable/off-device storage before treating it as a disaster-recovery
  backup. The matching SSH private key must also remain recoverable; do not
  upload either private identity or plaintext signing keys.
- The SSH-recipient mode is age's supported convenience for an existing SSH
  key. For a long-lived backup, retain a separate offline recovery copy of the
  SSH identity or re-encrypt the archive to a separately managed age identity.

To restore, use age 1.3 or later and the matching SSH private key. Extract only
into a new private directory, compare each derived public key against the
included anchor, then restore the private PEM files with mode `0600`:

```bash
umask 077
RESTORE_DIR="$(mktemp -d)"
chmod 700 "$RESTORE_DIR"
age -d -i "$HOME/.ssh/id_ed25519" \
  -o "$RESTORE_DIR/registry-signing-keys.tar" \
  "$HOME/.config/axiom/registry-key-backups/registry-signing-keys-2026-11-17.tar.age"
tar -xf "$RESTORE_DIR/registry-signing-keys.tar" -C "$RESTORE_DIR"
openssl pkey -in "$RESTORE_DIR/package-signing.pem" -pubout \
  -out "$RESTORE_DIR/package-derived-public.pem"
openssl pkey -in "$RESTORE_DIR/index-signing.pem" -pubout \
  -out "$RESTORE_DIR/index-derived-public.pem"
cmp "$RESTORE_DIR/package-derived-public.pem" \
  "$RESTORE_DIR/registry-package-public.pem"
cmp "$RESTORE_DIR/index-derived-public.pem" \
  "$RESTORE_DIR/registry-index-public.pem"
```

The restored private files must not be committed or placed in `registry-site/`.
After recovery, verify permissions and test a signature against a disposable
payload before using a key for publication.

## Rotation policy and rollout constraint

The current Axiom source accepts up to eight package and index trust anchors
through `[registry].public_keys` and `[registry].index_public_keys`; official
trust-anchor PEM files can contain multiple concatenated PEM keys. The bundled
official files and the current live index still use one key per role. Existing
client distributions must be updated with both old and replacement anchors
before the registry changes its signer. Therefore routine rotation needs a
staged client release that overlaps old and new anchors. Keep the current keys
and their backup until that rollout has been completed; do not rotate as a
cleanup step.

For a planned key rotation, use this sequence:

1. Generate two new, separate Ed25519 signing keys in protected staging; never
   reuse the package key as the index key.
2. Put both current and replacement public keys in each role's trusted set and
   publish a client release. Verify that it accepts the current live index and
   package before proceeding.
3. Back up and round-trip verify the new private keys; update the committed
   package trust anchors and the public PEMs in `registry-site/`.
4. Re-sign published package artifacts and the schema 2 index with the new
   corresponding keys, increment the index sequence, set a fresh expiry, run
   the Pages validator, and test a clean consumer against the staged snapshot.
5. Publish the snapshot, verify it through the default HTTPS URL, and retain
   both trusted anchors through the migration window.
6. Publish a later client release that removes the old anchors only after
   supported clients have migrated. Retire or destroy old signing keys only
   after checking recovery policy and retaining the encrypted recovery archive
   for the required retention period.

For suspected compromise, stop registry publication immediately. Treat the
affected public key as untrusted, prepare a coordinated client/trust-anchor
recovery release, and do not rely on the ordinary overlap schedule. The signed
index sequence detects rollback only after a client has observed a higher
sequence; it cannot establish freshness on first use or after its local state
is deleted.
