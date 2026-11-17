"""Regression tests for the manually dispatched static registry Pages build."""

import base64
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest

from axiom.registry_pages import RegistryPagesError, build_pages_site


OPENSSL = shutil.which("openssl")
pytestmark = pytest.mark.skipif(OPENSSL is None, reason="OpenSSL is required for registry signatures")


def _run(*args):
    return subprocess.run(
        [OPENSSL, *map(str, args)], check=True, capture_output=True, timeout=30
    )


def _keypair(root: Path, name: str) -> tuple[Path, Path]:
    private = root / f"{name}-private.pem"
    public = root / f"{name}-public.pem"
    _run("genpkey", "-algorithm", "ED25519", "-out", private)
    _run("pkey", "-in", private, "-pubout", "-out", public)
    return private, public


def _sign(private_key: Path, payload: bytes, output: Path) -> str:
    input_path = output.with_suffix(".input")
    input_path.write_bytes(payload)
    _run("pkeyutl", "-sign", "-rawin", "-inkey", private_key,
         "-in", input_path, "-out", output)
    signature = base64.b64encode(output.read_bytes()).decode("ascii")
    input_path.unlink()
    output.unlink()
    return signature


def _archive(name: str = "axiom-scan-report", version: str = "0.1.0") -> bytes:
    manifest = f"[package]\nname = \"{name}\"\nversion = \"{version}\"\n".encode()
    payload = BytesIO()
    with tarfile.open(fileobj=payload, mode="w:gz") as tar:
        info = tarfile.TarInfo("axiom.toml")
        info.size = len(manifest)
        tar.addfile(info, BytesIO(manifest))
    return payload.getvalue()


def _registry_tree(root: Path, *, schema: int = 2) -> tuple[Path, bytes]:
    site = root / "registry-site"
    registry = site / "registry"
    (registry / "axiom-scan-report").mkdir(parents=True)
    package_private, package_public = _keypair(root, "package")
    shutil.copyfile(package_public, site / "package-public-key.pem")

    archive = _archive()
    archive_path = registry / "axiom-scan-report" / "0.1.0.tar.gz"
    archive_path.write_bytes(archive)
    entry = {
        "version": "0.1.0",
        "sha256": hashlib.sha256(archive).hexdigest(),
        "sig": _sign(package_private, archive, root / "package.sig"),
        "dependencies": {},
        "yanked": False,
    }
    index = {"schema": schema, "packages": {"axiom-scan-report": [entry]}}
    if schema == 2:
        index_private, index_public = _keypair(root, "index")
        shutil.copyfile(index_public, site / "index-public-key.pem")
        index.update({
            "sequence": 1,
            "expires": (datetime.now(timezone.utc) + timedelta(days=30))
            .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        })
    raw_index = (json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n").encode()
    index_path = registry / "index.json"
    index_path.write_bytes(raw_index)
    if schema == 2:
        signature = _sign(index_private, raw_index, root / "index.sig")
        (registry / "index.json.sig").write_text(signature + "\n", encoding="ascii")
    return site, raw_index


def test_pages_build_validates_signed_package_and_generates_project_site(tmp_path):
    site, raw_index = _registry_tree(tmp_path)
    output = build_pages_site(site, tmp_path / "_site")

    assert (output / "index.html").is_file()
    assert "registry/index.json" in (output / "index.html").read_text()
    assert (output / ".nojekyll").is_file()
    assert (output / "registry" / "index.json").read_bytes() == raw_index
    assert (output / "registry" / "axiom-scan-report" / "0.1.0.tar.gz").is_file()
    assert not (output / "package-public-key.pem").exists()
    assert not (output / "index-public-key.pem").exists()


def test_pages_build_verifies_separately_signed_v2_index(tmp_path):
    site, _ = _registry_tree(tmp_path, schema=2)
    output = build_pages_site(site, tmp_path / "_site")
    assert (output / "registry" / "index.json.sig").is_file()


def test_pages_build_rejects_unsigned_v1_index(tmp_path):
    site, _ = _registry_tree(tmp_path, schema=1)

    with pytest.raises(RegistryPagesError, match="yalnızca.*Registry v2"):
        build_pages_site(site, tmp_path / "_site")


def test_pages_build_rejects_tampered_package_and_does_not_create_output(tmp_path):
    site, _ = _registry_tree(tmp_path)
    archive = site / "registry" / "axiom-scan-report" / "0.1.0.tar.gz"
    archive.write_bytes(archive.read_bytes() + b"tampered")
    output = tmp_path / "_site"

    with pytest.raises(RegistryPagesError, match="sha256|imza"):
        build_pages_site(site, output)
    assert not output.exists()


def test_pages_build_rejects_invalid_package_signature_after_hash_matches(tmp_path):
    site, _ = _registry_tree(tmp_path)
    archive_path = site / "registry" / "axiom-scan-report" / "0.1.0.tar.gz"
    archive = archive_path.read_bytes() + b"tampered"
    archive_path.write_bytes(archive)
    index_path = site / "registry" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entry = index["packages"]["axiom-scan-report"][0]
    entry["sha256"] = hashlib.sha256(archive).hexdigest()
    index_path.write_text(
        json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    raw_index = index_path.read_bytes()
    signature = _sign(
        tmp_path / "index-private.pem", raw_index, tmp_path / "updated-index.sig"
    )
    (index_path.parent / "index.json.sig").write_text(signature + "\n", encoding="ascii")

    with pytest.raises(RegistryPagesError, match="imza geçersiz"):
        build_pages_site(site, tmp_path / "_site")


def test_pages_build_rejects_missing_v2_index_signature(tmp_path):
    site, _ = _registry_tree(tmp_path, schema=2)
    (site / "registry" / "index.json.sig").unlink()

    with pytest.raises(RegistryPagesError, match="index.json.sig"):
        build_pages_site(site, tmp_path / "_site")


def test_pages_build_rejects_invalid_v2_index_signature(tmp_path):
    site, _ = _registry_tree(tmp_path, schema=2)
    signature_path = site / "registry" / "index.json.sig"
    signature_path.write_text(base64.b64encode(bytes(64)).decode("ascii") + "\n")

    with pytest.raises(RegistryPagesError, match="index imzası doğrulanamadı"):
        build_pages_site(site, tmp_path / "_site")


def test_pages_build_rejects_unindexed_files_and_symlinks(tmp_path):
    site, _ = _registry_tree(tmp_path)
    (site / "registry" / "unexpected.txt").write_text("not indexed")
    with pytest.raises(RegistryPagesError, match="ağacı index ile uyuşmuyor"):
        build_pages_site(site, tmp_path / "_site")

    (site / "registry" / "unexpected.txt").unlink()
    try:
        (site / "registry" / "link").symlink_to(
            site / "registry" / "index.json"
        )
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(RegistryPagesError, match="symlink"):
        build_pages_site(site, tmp_path / "_site")


def test_pages_build_rejects_symlinked_ancestor_before_reading_archive(tmp_path):
    site, _ = _registry_tree(tmp_path)
    registry = site / "registry"
    package_dir = registry / "axiom-scan-report"
    outside = tmp_path / "outside-package"
    package_dir.rename(outside)
    try:
        package_dir.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")

    with pytest.raises(RegistryPagesError, match="symlink"):
        build_pages_site(site, tmp_path / "_site")


def test_pages_build_rejects_expired_v2_index(tmp_path):
    site, _ = _registry_tree(tmp_path, schema=2)
    index_path = site / "registry" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["expires"] = (datetime.now(timezone.utc) - timedelta(days=1)) \
        .replace(microsecond=0).isoformat().replace("+00:00", "Z")
    raw_index = (json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n").encode()
    index_path.write_bytes(raw_index)
    # The old signature no longer verifies; expiry is checked before signature.
    with pytest.raises(RegistryPagesError, match="süresi dolmuş"):
        build_pages_site(site, tmp_path / "_site")


def test_pages_workflow_is_manual_confirmed_and_sha_pinned():
    workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "publish-registry-pages.yml"
    workflow = workflow_path.read_text(encoding="utf-8")

    assert re.search(r"(?m)^on:\s*$", workflow)
    assert re.search(r"(?m)^  workflow_dispatch:\s*$", workflow)
    assert re.search(r"(?m)^  (?:push|pull_request|schedule):", workflow) is None
    assert "options:\n          - cancel\n          - publish" in workflow
    assert workflow.count("if: github.ref == 'refs/heads/master' && inputs.confirmation == 'publish'") == 2
    pinned_uses = re.findall(r"(?m)^[ \t]+uses: ([^\s]+)(?:[ \t]+#.*)?$", workflow)
    assert len(pinned_uses) == 4
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", action) for action in pinned_uses)
    assert "pages: write" in workflow
    assert "id-token: write" in workflow
