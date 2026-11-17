"""Validate and stage a signed static registry for a manual Pages deployment."""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from axiom.registry import (
    RegistryConfig,
    RegistryIndex,
    _MAX_REGISTRY_INDEX_BYTES,
    _MAX_REGISTRY_PACK_BYTES,
    _extract_package_archive,
    _validate_package_archive_limits,
    _validate_package_manifest,
    _verify_package_tarball,
    verify_signature,
)


_MAX_PAGES_ARTIFACT_BYTES = 9_000_000_000
_MAX_PUBLIC_KEY_BYTES = 64 * 1024


class RegistryPagesError(ValueError):
    """The staged registry is unsafe or inconsistent and must not be published."""


def _read_public_key(path: Path, *, required: bool) -> str | None:
    if not path.exists():
        if required:
            raise RegistryPagesError(f"gerekli açık anahtar yok: {path}")
        return None
    if path.is_symlink() or not path.is_file():
        raise RegistryPagesError(f"açık anahtar normal dosya olmalı: {path}")
    if path.stat().st_size > _MAX_PUBLIC_KEY_BYTES:
        raise RegistryPagesError(f"açık anahtar boyut sınırını aşıyor: {path}")
    try:
        key = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RegistryPagesError(f"açık anahtar okunamadı: {path}: {exc}") from exc
    if "PRIVATE KEY" in key or "PUBLIC KEY" not in key:
        raise RegistryPagesError(f"yalnızca PEM açık anahtara izin verilir: {path}")
    return key


def _walk_regular_tree(root: Path) -> tuple[set[str], set[str]]:
    files: set[str] = set()
    directories: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise RegistryPagesError(f"registry ağacı symlink içeremez: {relative}")
        if path.is_dir():
            directories.add(relative)
        elif path.is_file():
            files.add(relative)
        else:
            raise RegistryPagesError(f"registry ağacı özel dosya içeremez: {relative}")
    return files, directories


def _verify_index_signature(index_path: Path, raw_index: bytes, public_key: str) -> None:
    signature_path = index_path.with_name("index.json.sig")
    if signature_path.is_symlink() or not signature_path.is_file():
        raise RegistryPagesError("Registry v2 index.json.sig dosyası eksik veya geçersiz")
    if signature_path.stat().st_size > 1024:
        raise RegistryPagesError("index.json.sig 1 KiB sınırını aşıyor")
    try:
        signature = signature_path.read_text(encoding="ascii").strip()
        base64.b64decode(signature, validate=True)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise RegistryPagesError(f"index.json.sig base64 biçimi geçersiz: {exc}") from exc
    valid, reason = verify_signature(raw_index, signature, public_key)
    if not valid:
        raise RegistryPagesError(f"Registry v2 index imzası doğrulanamadı: {reason}")


def validate_registry_tree(source_root: Path, *, now: datetime | None = None) -> tuple[Path, str]:
    """Validate the static registry and return its root plus the package key.

    The trusted public keys are checked from the source tree. Private keys are
    never accepted. Every package archive is checked for its SHA-256, Ed25519
    signature, safe tar structure, and signed manifest/index metadata binding.
    """
    source_root = source_root.expanduser()
    if source_root.is_symlink() or not source_root.is_dir():
        raise RegistryPagesError(f"registry kaynak dizini normal dizin olmalı: {source_root}")
    source_root = source_root.resolve()

    registry_root = source_root / "registry"
    if registry_root.is_symlink() or not registry_root.is_dir():
        raise RegistryPagesError(f"statik registry dizini bulunamadı: {registry_root}")

    # Reject symlinked ancestor directories before opening any indexed payload.
    _walk_regular_tree(source_root)

    package_key = _read_public_key(source_root / "package-public-key.pem", required=True)
    assert package_key is not None

    index_path = registry_root / "index.json"
    if index_path.is_symlink() or not index_path.is_file():
        raise RegistryPagesError("registry/index.json yok veya normal dosya değil")
    if index_path.stat().st_size > _MAX_REGISTRY_INDEX_BYTES:
        raise RegistryPagesError("registry/index.json boyut sınırını aşıyor")
    try:
        raw_index = index_path.read_bytes()
        parsed_index = json.loads(raw_index.decode("utf-8"))
        index = RegistryIndex.from_json(parsed_index, "https://registry.invalid/registry")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RegistryPagesError(f"registry/index.json geçersiz: {exc}") from exc
    if index.schema != 2:
        raise RegistryPagesError(
            "Pages yayını yalnızca Registry v2 index kabul eder; ayrı anahtar "
            "imzası ve süre doğrulanmalıdır"
        )
    if not index.packages:
        raise RegistryPagesError("yayın registry'si en az bir imzalı paket içermeli")

    index_key_path = source_root / "index-public-key.pem"
    index_key = _read_public_key(index_key_path, required=index.schema == 2)
    if index.schema == 2:
        assert index_key is not None
        assert index.expires is not None
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise RegistryPagesError("şimdiki zaman UTC saat dilimi içermeli")
        if index.expires <= current_time.astimezone(timezone.utc):
            raise RegistryPagesError("Registry v2 index süresi dolmuş")
        if index.expires > current_time.astimezone(timezone.utc) + timedelta(days=90):
            raise RegistryPagesError("Registry v2 index süresi 90 günden uzun")
        _verify_index_signature(index_path, raw_index, index_key)
    elif (registry_root / "index.json.sig").exists():
        raise RegistryPagesError("Registry v1 için beklenmeyen index.json.sig dosyası")

    expected_files = {"index.json"}
    if index.schema == 2:
        expected_files.add("index.json.sig")
    expected_directories: set[str] = set()
    total_bytes = index_path.stat().st_size
    if index.schema == 2:
        total_bytes += (registry_root / "index.json.sig").stat().st_size

    config = RegistryConfig(url="", public_key=package_key)
    with tempfile.TemporaryDirectory(prefix="axiom-registry-pages-verify-") as temp_name:
        extract_root = Path(temp_name)
        package_position = 0
        for name in sorted(index.packages):
            for entry in index.packages[name]:
                version = entry["version"]
                # RegistryClient downloads `<registry>/<name>/<version>.tar.gz`;
                # keep the Pages tree identical to the actual client URL layout.
                relative = Path(*name.split("/"), f"{version}.tar.gz")
                archive_path = registry_root / relative
                if archive_path.is_symlink() or not archive_path.is_file():
                    raise RegistryPagesError(f"registry paket arşivi yok/geçersiz: {relative}")
                size = archive_path.stat().st_size
                if size > _MAX_REGISTRY_PACK_BYTES:
                    raise RegistryPagesError(f"registry paket arşivi boyut sınırını aşıyor: {relative}")
                total_bytes += size
                if total_bytes > _MAX_PAGES_ARTIFACT_BYTES:
                    raise RegistryPagesError("Pages artifact toplam boyutu 9 GB sınırını aşıyor")
                raw_archive = archive_path.read_bytes()
                try:
                    _verify_package_tarball(
                        raw_archive, name, version, entry["sha256"], entry["sig"], config
                    )
                    _validate_package_archive_limits(raw_archive)
                    package_root = extract_root / str(package_position)
                    _extract_package_archive(raw_archive, package_root)
                    _validate_package_manifest(
                        package_root, name, version, entry.get("dependencies", {})
                    )
                except (OSError, RuntimeError, ValueError) as exc:
                    raise RegistryPagesError(f"{name}@{version} doğrulanamadı: {exc}") from exc
                package_position += 1
                relative_text = relative.as_posix()
                expected_files.add(relative_text)
                parent = Path(relative_text).parent
                while parent != Path("."):
                    expected_directories.add(parent.as_posix())
                    parent = parent.parent

    actual_files, actual_directories = _walk_regular_tree(registry_root)
    if actual_files != expected_files:
        missing = sorted(expected_files - actual_files)
        unexpected = sorted(actual_files - expected_files)
        raise RegistryPagesError(
            f"registry dosya ağacı index ile uyuşmuyor; eksik={missing}, beklenmeyen={unexpected}"
        )
    if actual_directories != expected_directories:
        missing = sorted(expected_directories - actual_directories)
        unexpected = sorted(actual_directories - expected_directories)
        raise RegistryPagesError(
            f"registry dizin ağacı index ile uyuşmuyor; eksik={missing}, beklenmeyen={unexpected}"
        )
    source_files, source_directories = _walk_regular_tree(source_root)
    expected_source_files = {"package-public-key.pem"}
    if index.schema == 2:
        expected_source_files.add("index-public-key.pem")
    expected_source_files.update(f"registry/{path}" for path in expected_files)
    expected_source_directories = {"registry"}
    expected_source_directories.update(
        f"registry/{path}" for path in expected_directories
    )
    if source_files != expected_source_files or source_directories != expected_source_directories:
        raise RegistryPagesError(
            "registry-site yalnızca güven anahtarlarını ve index'in belirttiği registry "
            "dosyalarını içerebilir"
        )
    if total_bytes > _MAX_PAGES_ARTIFACT_BYTES:
        raise RegistryPagesError("Pages artifact toplam boyutu 9 GB sınırını aşıyor")
    return registry_root, package_key


def build_pages_site(source_root: Path, output_root: Path) -> Path:
    """Validate source content, then create an upload-pages-artifact directory."""
    registry_root, _ = validate_registry_tree(source_root)
    output_root = output_root.expanduser()
    if output_root.exists() or output_root.is_symlink():
        raise RegistryPagesError(f"Pages çıktı dizini önceden var olmamalı: {output_root}")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    output_root.mkdir()
    shutil.copytree(registry_root, output_root / "registry")
    (output_root / ".nojekyll").write_text("", encoding="ascii")
    (output_root / "index.html").write_text(
        "<!doctype html>\n"
        "<html lang=\"en\"><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Axiom package registry</title>"
        "<h1>Axiom package registry</h1>"
        "<p>Static package index: <a href=\"registry/index.json\">registry/index.json</a>.</p>"
        "</html>\n",
        encoding="utf-8",
    )
    return output_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("registry-site"))
    parser.add_argument("--output", type=Path, default=Path("_site"))
    args = parser.parse_args(argv)
    try:
        build_pages_site(args.source, args.output)
    except (OSError, RegistryPagesError) as exc:
        parser.error(str(exc))
    print(f"validated Pages artifact: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
