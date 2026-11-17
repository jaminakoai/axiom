"""
Axiom (λx) - Paket Kayıt Defteri (Registry) v1

Tasarım:
  - Index:      <url>/index.json  (sürüm listesi, sha256, imza, bağımlılıklar)
  - Paket:      <url>/<ad>/<sürüm>.tar.gz
  - Depo:       içerik-adresli; ~/.axiom/cache/registry/sha256/<hash>/
  - İmza:       ed25519 detached imza (openssl pkeyutl ile doğrulanır)
  - Semver:     *, =, ^, ~, >=, >, <=, <  (AND ile birleşik)

Güvenlik:
  - Tarball indirildikten sonra sha256 DOĞRULANIR (indirme sırasında değil).
  - İmza, TARBALL BAYTLARI üzerinden doğrulanır (index ele geçirilse bile
    içerik değiştirilemez).
  - İmza anahtarı yapılandırılmamışsa ve `allow_unsigned` açık değilse REDDEDİLİR.
"""
from __future__ import annotations

import hashlib
import gzip
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import zlib
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

SCHEMA_VERSION = 1
DEFAULT_REGISTRY = "https://jaminakoai.github.io/axiom/registry"
_SHA256_HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_REGISTRY_PACKAGE_NAME_RE = re.compile(r"^(@[A-Za-z0-9_.-]+/)?[A-Za-z0-9_.-]+$")
_MAX_REGISTRY_INDEX_BYTES = 16 * 1024 * 1024
_MAX_REGISTRY_INDEX_SIGNATURE_BYTES = 1024
_MAX_REGISTRY_PACK_BYTES = 256 * 1024 * 1024
_MAX_REGISTRY_ARCHIVE_BYTES = 256 * 1024 * 1024
_MAX_REGISTRY_ARCHIVE_MEMBERS = 20_000
_MAX_REGISTRY_MANIFEST_BYTES = 1024 * 1024
_MAX_REGISTRY_SIDECAR_BYTES = 1024 * 1024
_MAX_REGISTRY_PACKAGES = 10_000
_MAX_REGISTRY_PACK_DIRECTORIES = 30_000
_MAX_REGISTRY_TAR_METADATA_READ = 1024 * 1024
_MAX_REGISTRY_TAR_METADATA_TOTAL = 32 * 1024 * 1024
_MAX_REGISTRY_TAR_EXPANDED_BYTES = (
    _MAX_REGISTRY_ARCHIVE_BYTES + _MAX_REGISTRY_TAR_METADATA_TOTAL
    + _MAX_REGISTRY_ARCHIVE_MEMBERS * 1024 + 1024
)
_MAX_SIGNED_INDEX_LIFETIME_SECONDS = 90 * 24 * 60 * 60


class _BoundedTarReader:
    """Bound individual and cumulative metadata reads performed by tarfile."""

    def __init__(self, source, max_read: int, max_total: int):
        self.source = source
        self.max_read = max_read
        self.max_total = max_total
        self.total_read = 0
        self.payload_read = False

    def begin_payload_read(self) -> None:
        self.payload_read = True

    def end_payload_read(self) -> None:
        self.payload_read = False

    def read(self, size: int = -1) -> bytes:
        if not self.payload_read and (size < 0 or size > self.max_read):
            raise ValueError("tar uzantı başlığı tek okumada 1 MiB sınırını aşıyor")
        data = self.source.read(size)
        if not self.payload_read:
            self.total_read += len(data)
            if self.total_read > self.max_total:
                raise ValueError("tar başlık/manifest verisi toplam 32 MiB sınırını aşıyor")
        return data

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence != 0:
            raise ValueError("tar akışında yalnızca mutlak seek desteklenir")
        return self.source.seek(offset)

    def tell(self) -> int:
        return self.source.tell()

    def close(self) -> None:
        self.source.close()

    def __getattr__(self, name: str):
        return getattr(self.source, name)


class _BoundedRegistryTarInfo(tarfile.TarInfo):
    """Reject oversized PAX/GNU extension data before tarfile parses it."""

    def _proc_pax(self, archive):
        if self.size > _MAX_REGISTRY_TAR_METADATA_READ:
            raise ValueError("tar uzantı başlığı tek okumada 1 MiB sınırını aşıyor")
        return super()._proc_pax(archive)

    def _proc_gnulong(self, archive):
        if self.size > _MAX_REGISTRY_TAR_METADATA_READ:
            raise ValueError("GNU tar uzantı başlığı 1 MiB sınırını aşıyor")
        return super()._proc_gnulong(archive)


def _validate_package_archive_limits(raw: bytes) -> None:
    """Bound compressed input, gzip expansion, tar metadata and file payloads.

    Run before extracting both downloaded archives and cache hits. A spooled
    stream caps memory use while ensuring tarfile sees bounded, uncompressed
    input and a TarInfo subclass before it parses the first member.
    """
    if len(raw) > _MAX_REGISTRY_PACK_BYTES:
        raise RuntimeError(
            f"registry paket arşivi sıkıştırılmış {_MAX_REGISTRY_PACK_BYTES} bayt sınırını aşıyor"
        )

    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as compressed, \
                tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b") as tar_data:
            expanded_size = 0
            while True:
                chunk = compressed.read(64 * 1024)
                if not chunk:
                    break
                expanded_size += len(chunk)
                if expanded_size > _MAX_REGISTRY_TAR_EXPANDED_BYTES:
                    raise RuntimeError("registry paket tar akışı açılmış boyut sınırını aşıyor")
                tar_data.write(chunk)

            tar_data.seek(0)
            bounded_tar = _BoundedTarReader(
                tar_data,
                _MAX_REGISTRY_TAR_METADATA_READ,
                _MAX_REGISTRY_TAR_METADATA_TOTAL,
            )
            with tarfile.open(
                fileobj=bounded_tar, mode="r:", tarinfo=_BoundedRegistryTarInfo
            ) as archive:
                member_count = 0
                total_payload = 0
                while True:
                    member = archive.next()
                    if member is None:
                        break
                    member_count += 1
                    if member_count > _MAX_REGISTRY_ARCHIVE_MEMBERS:
                        raise RuntimeError(
                            f"registry paket arşivi {_MAX_REGISTRY_ARCHIVE_MEMBERS} üye sınırını aşıyor"
                        )
                    if member.isfile():
                        if member.size < 0:
                            raise RuntimeError("registry paket arşivinde negatif dosya boyutu")
                        total_payload += member.size
                        if total_payload > _MAX_REGISTRY_ARCHIVE_BYTES:
                            raise RuntimeError(
                                "registry paket arşivi açılmış dosya boyutu sınırını aşıyor"
                            )
                        if PurePosixPath(member.name).parts == ("axiom.toml",) \
                                and member.size > _MAX_REGISTRY_MANIFEST_BYTES:
                            raise RuntimeError("registry paket axiom.toml 1 MiB sınırını aşıyor")
                        source = archive.extractfile(member)
                        if source is None:
                            raise RuntimeError(f"registry arşiv girdisi okunamadı: {member.name}")
                        actual_size = 0
                        bounded_tar.begin_payload_read()
                        try:
                            with source:
                                while True:
                                    try:
                                        chunk = source.read(64 * 1024)
                                    except (EOFError, tarfile.ReadError) as exc:
                                        raise RuntimeError(
                                            f"registry arşiv girdisi kesik: {member.name}"
                                        ) from exc
                                    if not chunk:
                                        break
                                    actual_size += len(chunk)
                                    if actual_size > member.size:
                                        raise RuntimeError(
                                            "registry arşiv girdisi bildirilen boyutu aşıyor: "
                                            f"{member.name}"
                                        )
                        finally:
                            bounded_tar.end_payload_read()
                        if actual_size != member.size:
                            raise RuntimeError(
                                f"registry arşiv girdisi kesik: {member.name} "
                                f"(beklenen {member.size}, okunan {actual_size})"
                            )
    except RuntimeError:
        raise
    except (OSError, EOFError, tarfile.TarError, ValueError, zlib.error) as exc:
        raise RuntimeError(f"registry paket arşivi sınır/biçim doğrulaması başarısız: {exc}") from exc


def _extract_package_archive(raw: bytes, destination: Path) -> None:
    """Extract only regular files/directories from an untrusted package tarball.

    Python's extraction filters are not available on every supported Python
    version. Validate the complete member list before writing anything, reject
    links/special files, then copy file contents into paths below destination.
    This prevents a symlink member from redirecting a later member outside the
    extraction root.
    """
    root = destination.resolve()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        members = archive.getmembers()
        normalized = []
        for member in members:
            name = member.name
            path = PurePosixPath(name)
            parts = path.parts
            if (
                not name
                or "\\" in name
                or path.is_absolute()
                or any(part in ("..", "") for part in parts)
                or (parts and ":" in parts[0])
            ):
                raise RuntimeError(f"güvensiz arşiv yolu: {name}")
            if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
                raise RuntimeError(f"desteklenmeyen arşiv girdisi: {name}")
            if member.isfile() and not parts:
                raise RuntimeError(f"geçersiz arşiv dosya yolu: {name}")
            target = root.joinpath(*parts).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                raise RuntimeError(f"güvensiz arşiv yolu: {name}") from None
            if target == root / "pkg.tar.gz":
                raise RuntimeError("paket arşivi ayrılmış bir cache yolunu kullanıyor: pkg.tar.gz")
            normalized.append((member, target))

        for member, target in normalized:
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                target.chmod(0o755)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeError(f"arşiv girdisi okunamadı: {member.name}")
            copied = 0
            with source, target.open("xb") as output:
                while True:
                    try:
                        chunk = source.read(64 * 1024)
                    except (EOFError, tarfile.ReadError) as exc:
                        raise RuntimeError(f"arşiv girdisi kesik: {member.name}") from exc
                    if not chunk:
                        break
                    copied += len(chunk)
                    if copied > member.size:
                        raise RuntimeError(f"arşiv girdisi bildirilen boyutu aşıyor: {member.name}")
                    output.write(chunk)
            if copied != member.size:
                raise RuntimeError(
                    f"arşiv girdisi kesik: {member.name} "
                    f"(beklenen {member.size}, yazılan {copied})"
                )
            target.chmod(0o755 if member.mode & 0o111 else 0o644)


def _cache_matches_archive(raw: bytes, cache_dir: Path) -> bool:
    """Ensure extracted cache files still equal the verified archive contents."""
    expected: Dict[str, Tuple[int, str, int]] = {}
    expected_directories = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            member_count = 0
            for member in archive.getmembers():
                member_count += 1
                if member_count > _MAX_REGISTRY_ARCHIVE_MEMBERS:
                    return False
                name = member.name
                path = PurePosixPath(name)
                parts = path.parts
                if (
                    not name
                    or "\\" in name
                    or path.is_absolute()
                    or any(part in ("..", "") for part in parts)
                    or (parts and ":" in parts[0])
                ):
                    return False
                if member.isdir():
                    expected_directories.add("/".join(parts))
                    continue
                if member.issym() or member.islnk() or not member.isfile() or not parts:
                    return False
                relative_name = "/".join(parts)
                if relative_name == "pkg.tar.gz" or relative_name in expected:
                    return False
                source = archive.extractfile(member)
                if source is None:
                    return False
                digest = hashlib.sha256()
                size = 0
                with source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        size += len(chunk)
                        digest.update(chunk)
                mode = 0o755 if member.mode & 0o111 else 0o644
                if os.name == "nt":
                    # Windows chmod preserves the read-only flag, not POSIX
                    # distinctions such as 0644 vs 0755.
                    mode &= 0o200
                expected[relative_name] = (size, digest.hexdigest(), mode)

                parent = PurePosixPath(relative_name).parent
                while parent != PurePosixPath("."):
                    expected_directories.add(parent.as_posix())
                    parent = parent.parent

        actual: Dict[str, Tuple[int, str, int]] = {}
        actual_entries = 0
        actual_directories = 0
        actual_bytes = 0
        for path in cache_dir.rglob("*"):
            if path == cache_dir / "pkg.tar.gz":
                continue
            actual_entries += 1
            if actual_entries > _MAX_REGISTRY_ARCHIVE_MEMBERS + _MAX_REGISTRY_PACK_DIRECTORIES:
                return False
            if path.is_symlink():
                return False
            if path.is_dir():
                actual_directories += 1
                if actual_directories > _MAX_REGISTRY_PACK_DIRECTORIES:
                    return False
                relative = path.relative_to(cache_dir).as_posix()
                if relative not in expected_directories:
                    return False
                continue
            if not path.is_file():
                return False
            relative = path.relative_to(cache_dir).as_posix()
            if relative not in expected:
                return False
            expected_size = expected[relative][0]
            if path.stat().st_size != expected_size:
                return False
            remaining_bytes = _MAX_REGISTRY_ARCHIVE_BYTES - actual_bytes
            if path.stat().st_size > remaining_bytes:
                return False
            digest = hashlib.sha256()
            size = 0
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    size += len(chunk)
                    actual_bytes += len(chunk)
                    if actual_bytes > _MAX_REGISTRY_ARCHIVE_BYTES:
                        return False
                    digest.update(chunk)
            mode = path.stat().st_mode & 0o777
            if os.name == "nt":
                mode &= 0o200
            actual[relative] = (size, digest.hexdigest(), mode)
        return actual == expected
    except (tarfile.TarError, ValueError):
        return False

# ---------------------------------------------------------------------------
# Semver
# ---------------------------------------------------------------------------

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.\-]+))?(?:\+[0-9A-Za-z.\-]+)?$")


class SemverError(ValueError):
    pass


def parse_version(text: str) -> Tuple[int, int, int, str]:
    m = _SEMVER_RE.match(text.strip())
    if not m:
        raise SemverError(f"geçersiz sürüm: {text!r} (beklenen MAJOR.MINOR.PATCH)")
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), (m.group(4) or "")


def version_key(text: str) -> Tuple[int, int, int, int, str]:
    major, minor, patch, pre = parse_version(text)
    # ön sürüm (pre-release) kararlı sürümden KÜÇÜKTÜR
    pre_rank = 1 if pre == "" else 0
    return (major, minor, patch, pre_rank, pre)


def _parse_partial(text: str) -> Tuple[int, int, int, int]:
    """'1', '1.2', '1.2.3' -> ((1,0,0), verilen_parts)."""
    parts = text.strip().split(".")
    if len(parts) > 3:
        raise SemverError(f"geçersiz sürüm: {text!r}")
    nums = []
    for p in parts:
        if not p.isdigit():
            raise SemverError(f"geçersiz sürüm: {text!r}")
        nums.append(int(p))
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2], len(parts))


def _padded_key(nums: Tuple[int, int, int, int]) -> Tuple[int, int, int, int, str]:
    return (nums[0], nums[1], nums[2], 1, "")


def version_matches(version: str, constraint: str) -> bool:
    """Semver aralığı. Kısmi sürümler desteklenir (^0.3, ~1.2, =1.2 ...)."""
    c = (constraint or "*").strip()
    if c in ("*", "", "latest"):
        return True
    if "," in c:
        return all(version_matches(version, part) for part in c.split(",") if part.strip())

    try:
        v = parse_version(version)
    except SemverError:
        return False
    vk = version_key(version)

    for op in (">=", "<=", ">", "<", "=", "^", "~"):
        if c.startswith(op):
            rest = c[len(op):].strip()
            try:
                nums = _parse_partial(rest)
            except SemverError:
                return False
            given = nums[3]
            k = _padded_key(nums)
            if op == "=":
                # =1 -> 1.x.x ; =1.2 -> 1.2.x ; =1.2.3 tam
                if given == 1:
                    return v[0] == nums[0]
                if given == 2:
                    return v[0] == nums[0] and v[1] == nums[1]
                return v[:3] == nums[:3]
            if op == ">=":
                return vk >= k
            if op == "<=":
                # <=1.2 -> 1.2.x dahil
                if given == 1:
                    return v[0] <= nums[0]
                if given == 2:
                    return (v[0], v[1]) <= (nums[0], nums[1])
                return vk <= k
            if op == ">":
                return vk > k
            if op == "<":
                return vk < k
            if op == "^":
                if vk < k:
                    return False
                if nums[0] > 0 or given == 1:
                    return v[0] == nums[0]
                if nums[1] > 0 or given == 2:
                    return v[0] == 0 and v[1] == nums[1]
                return v[:3] == nums[:3]
            if op == "~":
                if vk < k:
                    return False
                if given == 1:
                    return v[0] == nums[0]
                return v[0] == nums[0] and v[1] == nums[1]

    # operatörsüz
    try:
        nums = _parse_partial(c)
        given = nums[3]
        if given == 1:
            return v[0] == nums[0]
        if given == 2:
            return v[0] == nums[0] and v[1] == nums[1]
        return v[:3] == nums[:3]
    except SemverError:
        return False


# ---------------------------------------------------------------------------
# Yapılandırma
# ---------------------------------------------------------------------------

class RegistryConfig:
    def __init__(self, url: str, public_key: Optional[str] = None,
                 allow_unsigned: bool = False, timeout: int = 30,
                 cache_dir: Optional[Path] = None,
                 index_public_key: Optional[str] = None):
        self.url = url.rstrip("/")
        self.public_key = public_key
        self.index_public_key = index_public_key
        self.allow_unsigned = allow_unsigned
        self.timeout = timeout
        env_cache = os.environ.get("AXIOM_CACHE_DIR")
        if cache_dir is not None:
            self.cache_dir = cache_dir
        elif env_cache:
            self.cache_dir = Path(env_cache) / "registry"
        else:
            self.cache_dir = Path.home() / ".axiom" / "cache" / "registry"

    @classmethod
    def from_manifest(cls, raw_data: Dict[str, Any]) -> "RegistryConfig":
        reg = raw_data.get("registry") or {}
        url = os.environ.get("AXIOM_REGISTRY") or reg.get("url") or DEFAULT_REGISTRY
        key = os.environ.get("AXIOM_REGISTRY_KEY") or reg.get("public_key")
        index_key = (os.environ.get("AXIOM_REGISTRY_INDEX_KEY")
                     or reg.get("index_public_key"))
        # Ship trust anchors for the official endpoint so a clean consumer can
        # verify packages and the signed schema-2 index without per-project PEMs.
        if url.rstrip("/") == DEFAULT_REGISTRY:
            key = key or Path(__file__).with_name("registry-package-public.pem").read_text(
                encoding="ascii"
            )
            index_key = index_key or Path(__file__).with_name(
                "registry-index-public.pem"
            ).read_text(encoding="ascii")
        allow = (os.environ.get("AXIOM_ALLOW_UNSIGNED") == "1"
                 or bool(reg.get("allow_unsigned", False)))
        return cls(url=url, public_key=key, index_public_key=index_key,
                   allow_unsigned=allow)


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

class RegistryIndex:
    def __init__(self, packages: Dict[str, List[Dict[str, Any]]], base_url: str,
                 schema: int = SCHEMA_VERSION, sequence: Optional[int] = None,
                 expires: Optional[datetime] = None, raw_sha256: Optional[str] = None):
        self.packages = packages
        self.base_url = base_url
        self.schema = schema
        self.sequence = sequence
        self.expires = expires
        self.raw_sha256 = raw_sha256

    @classmethod
    def from_json(cls, data: Dict[str, Any], base_url: str) -> "RegistryIndex":
        if not isinstance(data, dict):
            raise ValueError("index.json kök değeri nesne olmalı")
        schema = data.get("schema", SCHEMA_VERSION)
        if type(schema) is not int or schema not in (1, 2):
            raise ValueError(f"desteklenmeyen registry şeması: {schema}")
        sequence = None
        expires = None
        if schema == 2:
            sequence = data.get("sequence")
            if type(sequence) is not int or sequence < 1:
                raise ValueError("index.json v2: sequence pozitif bir tam sayı olmalı")
            expiration = data.get("expires")
            if not isinstance(expiration, str):
                raise ValueError("index.json v2: expires UTC zaman metni olmalı")
            try:
                expires = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("index.json v2: expires geçersiz") from exc
            if expires.tzinfo is None or expires.utcoffset() is None:
                raise ValueError("index.json v2: expires saat dilimi içermeli")
            expires = expires.astimezone(timezone.utc)
        pkgs = data.get("packages", {})
        if not isinstance(pkgs, dict):
            raise ValueError("index.json: 'packages' nesne olmalı")

        validated: Dict[str, List[Dict[str, Any]]] = {}
        for name, entries in pkgs.items():
            if (
                not isinstance(name, str)
                or ".." in name
                or name.count("/") > 1
                or not _REGISTRY_PACKAGE_NAME_RE.fullmatch(name)
            ):
                raise ValueError(f"index.json: geçersiz paket adı: {name!r}")
            if not isinstance(entries, list):
                raise ValueError(f"index.json: '{name}' sürüm listesi dizi olmalı")
            versions = set()
            validated_entries = []
            for position, entry in enumerate(entries):
                location = f"packages.{name}[{position}]"
                if not isinstance(entry, dict):
                    raise ValueError(f"index.json: {location} nesne olmalı")
                version = entry.get("version")
                if not isinstance(version, str):
                    raise ValueError(f"index.json: {location}.version metin olmalı")
                try:
                    version_key(version)
                except (SemverError, ValueError, OverflowError) as exc:
                    raise ValueError(f"index.json: {location}.version geçersiz") from exc
                if version in versions:
                    raise ValueError(f"index.json: {location}.version yinelenmiş")
                versions.add(version)

                sha = entry.get("sha256")
                if not isinstance(sha, str) or _SHA256_HEX_RE.fullmatch(sha) is None:
                    raise ValueError(f"index.json: {location}.sha256 64 hexadecimal karakter olmalı")
                signature = entry.get("sig", "")
                if not isinstance(signature, str):
                    raise ValueError(f"index.json: {location}.sig metin olmalı")
                dependencies = entry.get("dependencies", {})
                if not isinstance(dependencies, dict):
                    raise ValueError(f"index.json: {location}.dependencies nesne olmalı")
                for dep_name, constraint in dependencies.items():
                    if (
                        not isinstance(dep_name, str)
                        or ".." in dep_name
                        or dep_name.count("/") > 1
                        or not _REGISTRY_PACKAGE_NAME_RE.fullmatch(dep_name)
                        or not isinstance(constraint, str)
                    ):
                        raise ValueError(
                            f"index.json: {location}.dependencies geçersiz"
                        )
                yanked = entry.get("yanked", False)
                if not isinstance(yanked, bool):
                    raise ValueError(f"index.json: {location}.yanked boolean olmalı")
                validated_entries.append(entry)
            validated[name] = validated_entries
        return cls(validated, base_url, schema=schema, sequence=sequence,
                   expires=expires)

    def versions(self, name: str) -> List[Dict[str, Any]]:
        return list(self.packages.get(name) or [])

    def resolve(self, name: str, constraint: str) -> Optional[Dict[str, Any]]:
        """Aralığa uyan en yüksek, yanked olmayan sürüm."""
        candidates = [v for v in self.versions(name)
                      if not v.get("yanked", False) and version_matches(v.get("version", ""), constraint)]
        if not candidates:
            return None
        candidates.sort(key=lambda v: version_key(v["version"]))
        return candidates[-1]


# ---------------------------------------------------------------------------
# Doğrulama
# ---------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_sha256(data: bytes, expected: str) -> bool:
    return (isinstance(expected, str) and _SHA256_HEX_RE.fullmatch(expected) is not None
            and sha256_bytes(data) == expected.lower())


def _openssl_verify(data: bytes, signature: bytes, public_key_pem: str) -> bool:
    """ed25519 detached imzayı openssl CLI ile doğrular (yeni Python bağımlılığı yok)."""
    with tempfile.TemporaryDirectory() as d:
        dpath = Path(d)
        (dpath / "data").write_bytes(data)
        (dpath / "sig").write_bytes(signature)
        (dpath / "key.pem").write_text(public_key_pem, encoding="utf-8")
        try:
            res = subprocess.run(
                ["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(dpath / "key.pem"),
                 "-rawin", "-in", str(dpath / "data"), "-sigfile", str(dpath / "sig")],
                capture_output=True, text=True, timeout=30,
            )
        except FileNotFoundError:
            raise RuntimeError("imza doğrulaması için 'openssl' gerekli (sistemde yok)")
        return res.returncode == 0


@contextmanager
def _exclusive_registry_state_lock(path: Path):
    """Serialize sequence checks/updates across concurrent axpm processes."""
    if path.is_symlink():
        raise RuntimeError("registry index rollback kilidi symlink olamaz")
    with path.open("a+b") as lock_file:
        if os.name == "nt":
            import msvcrt
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _validate_signed_index_freshness(index: RegistryIndex, raw: bytes,
                                     config: RegistryConfig) -> None:
    """Reject expired signed indexes and locally observed sequence rollback."""
    if index.schema != 2 or index.sequence is None or index.expires is None:
        raise RuntimeError("imzalı registry index'i schema 2, sequence ve expires gerektirir")
    now = datetime.now(timezone.utc)
    remaining = (index.expires - now).total_seconds()
    if remaining <= 0:
        raise RuntimeError("imzalı registry index'inin süresi dolmuş")
    if remaining > _MAX_SIGNED_INDEX_LIFETIME_SECONDS:
        raise RuntimeError("imzalı registry index'i 90 günden daha ileri tarihli")

    state_root = config.cache_dir / "index-state"
    if state_root.is_symlink():
        raise RuntimeError("registry index rollback dizini symlink olamaz")
    state_root.mkdir(parents=True, exist_ok=True)
    registry_id = hashlib.sha256(config.url.encode("utf-8")).hexdigest()
    state_path = state_root / f"{registry_id}.json"
    if state_path.is_symlink():
        raise RuntimeError("registry index rollback durumu symlink olamaz")
    lock_path = state_path.with_suffix(".lock")
    with _exclusive_registry_state_lock(lock_path):
        raw_hash = hashlib.sha256(raw).hexdigest()
        old_sequence = None
        if state_path.exists():
            try:
                if state_path.stat().st_size > 4096:
                    raise ValueError("rollback durumu 4 KiB sınırını aşıyor")
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if not isinstance(state, dict):
                    raise ValueError("rollback durumu nesne olmalı")
                old_sequence = state["sequence"]
                old_hash = state["sha256"]
                if (type(old_sequence) is not int or old_sequence < 1
                        or not isinstance(old_hash, str)
                        or _SHA256_HEX_RE.fullmatch(old_hash) is None):
                    raise ValueError("rollback durumu biçimi geçersiz")
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(f"registry index rollback durumu okunamadı: {exc}") from exc
            if index.sequence < old_sequence:
                raise RuntimeError(
                    f"registry index rollback reddedildi (güncel {old_sequence}, alınan {index.sequence})"
                )
            if index.sequence == old_sequence and raw_hash != old_hash:
                raise RuntimeError("aynı sequence için farklı registry index içeriği reddedildi")

        if old_sequence is None or index.sequence > old_sequence:
            temp_path = state_path.with_name(f".{state_path.name}.{os.getpid()}.tmp")
            try:
                with temp_path.open("x", encoding="utf-8") as output:
                    json.dump({"sequence": index.sequence, "sha256": raw_hash}, output,
                              sort_keys=True, separators=(",", ":"))
                    output.write("\n")
                os.replace(temp_path, state_path)
            finally:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass


def verify_signature(data: bytes, signature_b64: str, public_key: Optional[str]) -> Tuple[bool, str]:
    """
    Dönüş: (geçerli_mi, neden)
    İmza yoksa: (False, "imza yok")
    """
    if not signature_b64:
        return False, "paket imzalanmamış"
    if not public_key:
        return False, "registry açık anahtarı tanımlı değil"
    try:
        sig = __import__("base64").b64decode(signature_b64, validate=True)
    except Exception:
        return False, "imza base64 çözülemedi"
    try:
        ok = _openssl_verify(data, sig, public_key)
    except RuntimeError as e:
        return False, str(e)
    return (True, "") if ok else (False, "imza geçersiz")


def _verify_package_tarball(raw: bytes, name: str, version: str, expected_sha: str,
                           sig_b64: str, config: RegistryConfig) -> None:
    """Her kullanımdan önce tarball bütünlüğünü ve güncel güven politikasını doğrula."""
    if not verify_sha256(raw, expected_sha):
        raise RuntimeError(
            f"'{name}@{version}' sha256 uyuşmuyor.\n"
            f"  beklenen: {expected_sha}\n  gerçek  : {sha256_bytes(raw)}"
        )
    if sig_b64:
        ok, why = verify_signature(raw, sig_b64, config.public_key)
        if not ok:
            raise RuntimeError(f"'{name}@{version}' imza doğrulanamadı: {why}")
    elif not config.allow_unsigned:
        raise RuntimeError(
            f"'{name}@{version}' imzalanmamış ve allow_unsigned kapalı. "
            "Registry'yi düzeltin veya AXIOM_ALLOW_UNSIGNED=1 kullanın."
        )


def _validate_package_manifest(
    package_dir: Path,
    name: str,
    version: str,
    indexed_dependencies: Dict[str, str],
) -> None:
    """Bind unsigned index metadata to the manifest covered by the tarball signature."""
    manifest_path = package_dir / "axiom.toml"
    try:
        if manifest_path.stat().st_size > 1024 * 1024:
            raise RuntimeError(f"'{name}@{version}' axiom.toml 1 MiB sınırını aşıyor")
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError(f"'{name}@{version}' paket manifestosu okunamadı: {exc}") from exc

    package = manifest.get("package") or manifest.get("project") or {}
    if not isinstance(package, dict):
        raise RuntimeError(f"'{name}@{version}' manifestosundaki [package] geçersiz")
    if package.get("name") != name:
        raise RuntimeError(f"registry paket adı imzalı manifestoyla uyuşmuyor: {name!r}")
    if package.get("version") != version:
        raise RuntimeError(f"registry sürümü imzalı manifestoyla uyuşmuyor: {version!r}")

    manifest_dependencies = manifest.get("dependencies") or {}
    if not isinstance(manifest_dependencies, dict):
        raise RuntimeError(f"'{name}@{version}' manifestosundaki [dependencies] geçersiz")
    if manifest_dependencies != indexed_dependencies:
        raise RuntimeError(
            f"'{name}@{version}' registry bağımlılıkları imzalı manifestoyla uyuşmuyor"
        )

# ---------------------------------------------------------------------------
# İndirme
# ---------------------------------------------------------------------------

def _fetch(url: str, timeout: int = 30, max_bytes: Optional[int] = None) -> bytes:
    def read_limited(source) -> bytes:
        if max_bytes is None:
            return source.read()
        chunks = bytearray()
        while True:
            remaining = max_bytes + 1 - len(chunks)
            if remaining <= 0:
                raise RuntimeError(f"indirilen içerik {max_bytes} bayt sınırını aşıyor")
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                return bytes(chunks)
            chunks.extend(chunk)
            if len(chunks) > max_bytes:
                raise RuntimeError(f"indirilen içerik {max_bytes} bayt sınırını aşıyor")

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() == "file":
        if parsed.netloc.lower() not in ("", "localhost"):
            raise ValueError("file:// registry URL uzak bir host içeremez")
        if parsed.query or parsed.fragment:
            raise ValueError("file:// registry URL query veya fragment içeremez")
        # url2pathname decodes escaped characters and converts drive-letter
        # paths such as /C:/... correctly on Windows.
        path = urllib.request.url2pathname(parsed.path)
        with Path(path).open("rb") as source:
            return read_limited(source)
    if not parsed.scheme and url.startswith("/"):
        with Path(parsed.path).open("rb") as source:
            return read_limited(source)
    req = urllib.request.Request(url, headers={"User-Agent": "axpm/0.5"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return read_limited(resp)


def fetch_index(config: RegistryConfig) -> RegistryIndex:
    url = f"{config.url}/index.json"
    try:
        raw = _fetch(url, config.timeout, _MAX_REGISTRY_INDEX_BYTES)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"registry index alınamadı ({url}): HTTP {e.code}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"registry'ye ulaşılamadı ({url}): {e.reason}")
    except OSError as e:
        raise RuntimeError(f"registry index okunamadı ({url}): {e}")
    except ValueError as e:
        raise RuntimeError(f"registry URL geçersiz ({url}): {e}") from e
    signature_b64 = ""
    if config.index_public_key:
        try:
            signature_raw = _fetch(f"{url}.sig", config.timeout,
                                   _MAX_REGISTRY_INDEX_SIGNATURE_BYTES)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as exc:
            raise RuntimeError(f"imzalı registry index imzası alınamadı: {exc}") from exc
        try:
            signature_b64 = signature_raw.decode("ascii").strip()
        except UnicodeDecodeError as exc:
            raise RuntimeError("registry index imzası ASCII base64 olmalı") from exc
        ok, why = verify_signature(raw, signature_b64, config.index_public_key)
        if not ok:
            raise RuntimeError(f"registry index imzası doğrulanamadı: {why}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise RuntimeError(f"index.json geçersiz JSON: {e}")
    index = RegistryIndex.from_json(data, config.url)
    if config.index_public_key and index.schema != 2:
        raise RuntimeError("imza anahtarı yapılandırıldığında registry index schema 2 olmalı")
    if index.schema == 2:
        if not config.index_public_key:
            raise RuntimeError("schema 2 registry index için AXIOM_REGISTRY_INDEX_KEY gerekli")
        _validate_signed_index_freshness(index, raw, config)
    return RegistryIndex(index.packages, index.base_url, schema=index.schema,
                         sequence=index.sequence, expires=index.expires,
                         raw_sha256=hashlib.sha256(raw).hexdigest())


class RegistryClient:
    def __init__(self, config: RegistryConfig):
        self.config = config
        self._index: Optional[RegistryIndex] = None

    @property
    def index(self) -> RegistryIndex:
        if self._index is None:
            self._index = fetch_index(self.config)
        return self._index

    def cache_path_for(self, sha: str) -> Path:
        if not isinstance(sha, str) or _SHA256_HEX_RE.fullmatch(sha) is None:
            raise ValueError("registry SHA-256 değeri tam 64 hexadecimal karakter olmalı")
        return self.config.cache_dir / "sha256" / sha

    def download(self, name: str, version: str, expected_sha: str,
                 sig_b64: str,
                 indexed_dependencies: Optional[Dict[str, str]] = None) -> Tuple[Path, bool]:
        """
        Paketi indirir, sha256 + imza doğrular, içerik-adresli cache'e açar.
        Dönüş: (açılmış_dizin, cache_iskaca_vurdu_mu)
        `indexed_dependencies`, çözümleyicinin kullandığı bağımlılık haritasıdır.
        Yüklenmiş index girdisiyle de eşleşmeli ve imzalı manifestoyla doğrulanır.
        """
        if not isinstance(expected_sha, str) or _SHA256_HEX_RE.fullmatch(expected_sha) is None:
            raise RuntimeError(
                f"'{name}@{version}' registry index SHA-256 değeri geçersiz; "
                "64 hexadecimal karakter bekleniyor"
            )
        index_entries = [
            entry for entry in self.index.versions(name)
            if entry.get("version") == version
            and str(entry.get("sha256", "")).lower() == expected_sha.lower()
        ]
        if len(index_entries) != 1:
            raise RuntimeError(f"'{name}@{version}' registry index girdisi tekil değil")
        index_entry = index_entries[0]
        if index_entry.get("sig", "") != sig_b64:
            raise RuntimeError(f"'{name}@{version}' registry imza alanı index ile uyuşmuyor")
        index_dependencies = index_entry.get("dependencies")
        if index_dependencies is None:
            index_dependencies = {}
        if not isinstance(index_dependencies, dict):
            raise RuntimeError(f"'{name}@{version}' registry bağımlılık listesi geçersiz")
        if indexed_dependencies is not None and indexed_dependencies != index_dependencies:
            raise RuntimeError(
                f"'{name}@{version}' çözümleme ve registry bağımlılık bilgileri uyuşmuyor"
            )
        indexed_dependencies = index_dependencies
        if not isinstance(indexed_dependencies, dict):
            raise RuntimeError(f"'{name}@{version}' registry bağımlılık listesi geçersiz")

        cache_dir = self.cache_path_for(expected_sha)
        stored_tarball = cache_dir / "pkg.tar.gz"

        if cache_dir.exists() and stored_tarball.exists():
            # Cache isabeti: içeriği YİNE doğrula. Aksi halde bozulmuş/ele
            # geçirilmiş cache doğrulamayı atlatırdı. İmzayı ve unsigned
            # politikasını da mevcut yapılandırmaya göre yeniden uygula.
            if cache_dir.is_symlink():
                raise RuntimeError(f"registry önbellek yolu symlink olamaz: {cache_dir}")
            if not stored_tarball.is_symlink() \
                    and stored_tarball.stat().st_size <= _MAX_REGISTRY_PACK_BYTES:
                with stored_tarball.open("rb") as cached_file:
                    cached = cached_file.read(_MAX_REGISTRY_PACK_BYTES + 1)
                if len(cached) <= _MAX_REGISTRY_PACK_BYTES \
                        and verify_sha256(cached, expected_sha):
                    _verify_package_tarball(cached, name, version, expected_sha,
                                            sig_b64, self.config)
                    try:
                        _validate_package_archive_limits(cached)
                    except RuntimeError:
                        shutil.rmtree(cache_dir, ignore_errors=True)
                        raise
                    if _cache_matches_archive(cached, cache_dir):
                        _validate_package_manifest(
                            cache_dir, name, version, indexed_dependencies
                        )
                        return cache_dir, True
            # bozuk cache: temizle ve yeniden indir
            shutil.rmtree(cache_dir, ignore_errors=True)

        url = f"{self.config.url}/{name}/{version}.tar.gz"
        try:
            raw = _fetch(url, self.config.timeout, _MAX_REGISTRY_PACK_BYTES)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"paket indirilemedi ({url}): HTTP {e.code}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"paket indirilemedi ({url}): {e.reason}")

        _verify_package_tarball(raw, name, version, expected_sha, sig_b64,
                                self.config)
        _validate_package_archive_limits(raw)

        # Açma (atomik: geçici dizin -> rename)
        cache_dir.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix="axpm-", dir=str(cache_dir.parent)))
        try:
            # Tarball'i cache'te sakla: sonraki isabetlerde yeniden doğrulanır.
            (tmp / "pkg.tar.gz").write_bytes(raw)
            _extract_package_archive(raw, tmp)
            _validate_package_manifest(tmp, name, version, indexed_dependencies)
            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
            tmp.rename(cache_dir)
        finally:
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)
        return cache_dir, False


# ---------------------------------------------------------------------------
# Çözümleme (transitive)
# ---------------------------------------------------------------------------

def resolve_tree(index: RegistryIndex, root_deps: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """
    Kök bağımlılıklardan başlayarak tüm ağacı çözer.
    Dönüş: {ad: {"version":..., "sha256":..., "sig":..., "deps": {...}}}
    Döngü tespiti ve çakışma hataları RuntimeError.
    """
    resolved: Dict[str, Dict[str, Any]] = {}
    visiting: List[str] = []

    def visit(name: str, constraint: str, chain: List[str]):
        if name in visiting:
            raise RuntimeError("döngüsel bağımlılık: " + " -> ".join(visiting + [name]))

        entry = index.resolve(name, constraint)
        if entry is None:
            available = sorted({v.get("version", "?") for v in index.versions(name)})
            if not available:
                raise RuntimeError(f"registry'de paket yok: '{name}' (constraint {constraint})")
            raise RuntimeError(
                f"'{name}' için uygun sürüm yok (constraint {constraint}). "
                f"Mevcut: {', '.join(available)}"
            )

        existing = resolved.get(name)
        if existing is not None:
            if existing["version"] == entry["version"]:
                return
            # iki farklı sürüm: daha yükseğini seç, kısıtı yeniden doğrula
            higher = max(existing["version"], entry["version"], key=version_key)
            if not version_matches(higher, constraint):
                raise RuntimeError(
                    f"'{name}' sürüm çakışması: {existing['version']} ve {entry['version']} "
                    f"(constraint {constraint})"
                )
            return

        resolved[name] = {
            "version": entry["version"],
            "sha256": entry.get("sha256", ""),
            "sig": entry.get("sig", ""),
            "deps": dict(entry.get("dependencies") or {}),
        }
        visiting.append(name)
        try:
            for dep_name, dep_constraint in (entry.get("dependencies") or {}).items():
                visit(dep_name, str(dep_constraint), chain + [name])
        finally:
            visiting.pop()

    for dep_name, constraint in root_deps.items():
        visit(dep_name, str(constraint), [])

    return resolved
