# `axpm pack` to local registry smoke test

**Date:** 2026-11-16  
**Status:** Passed locally with the committed monorepo example. No package was
published to a public registry.

## Flow verified

1. Generated a temporary Ed25519 keypair outside the repository.
2. Ran `axpm pack` from `packages/axiom-scan-report` into a temporary output
   directory.
3. Verified the detached signature over the tarball bytes, checked that the
   five expected package files were present, and confirmed `axiom.lock` was
   excluded.
4. Served the artifact through a temporary `file://` registry and downloaded
   it with `RegistryClient` using the generated public key.
5. Ran `axpm test` from the extracted package.

Output:

```text
pack -> Ed25519 verify -> local registry download -> packaged axpm test: PASS
Sonuç: 1/1 test başarılı.
package=axiom-scan-report@0.1.0 files=5 sha256=7fce1896126e9c87fb74b54f332c8eb09cefb0b9d6c21e0e26f4d71683e8a310
```

The signing key and local registry lived in a temporary directory and were
removed after the smoke test.

## Limit

This proves the local pack/sign/verify/download/test flow. It does not publish
the package, validate an official hosting service, or establish official
signing-key operations. G4 publication remains open.
