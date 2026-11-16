"""
Axiom Programming Language (λx) - Package Manager (axpm / axiom pkg)
Deterministik bağımlılık yönetimi, axiom.toml manifestosu, axiom.lock kilit mekanizması.
"""

import os
import re
import sys
import json
import base64
import gzip
import hashlib
import io
import shutil
import subprocess
import argparse
import tempfile
import tarfile
import zlib
from pathlib import Path, PurePosixPath
from typing import Dict, Any, List, Optional, Tuple

from axiom.registry import (
    RegistryConfig, RegistryClient, resolve_tree, SemverError, parse_version,
    sha256_bytes, verify_sha256, verify_signature, version_key,
)

try:
    import tomllib
except ImportError:
    # Python < 3.11 fallback if needed
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

# Renkler
CLR_RED = "\033[1;31m"
CLR_GREEN = "\033[1;32m"
CLR_YELLOW = "\033[1;33m"
CLR_CYAN = "\033[1;36m"
CLR_BOLD = "\033[1m"
CLR_RESET = "\033[0m"

_REGISTRY_INDEX_ENTRY_KEYS = {"version", "sha256", "sig", "dependencies", "yanked"}
_REGISTRY_CONSTRAINT_PART_RE = re.compile(
    r"^(?:>=|<=|>|<|=|\^|~)?\s*\d+(?:\.\d+){0,2}$"
)
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


class _BoundedTarReader:
    """Bound reads performed internally by tarfile for PAX/GNU metadata."""

    def __init__(self, source, max_read: int, max_total: int):
        self.source = source
        self.max_read = max_read
        self.max_total = max_total
        self.total_read = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0 or size > self.max_read:
            raise ValueError("tar uzantı başlığı tek okumada 1 MiB sınırını aşıyor")
        data = self.source.read(size)
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
    """Reject oversized extension headers before tarfile parses their payload."""

    def _proc_pax(self, archive):
        if self.size > _MAX_REGISTRY_TAR_METADATA_READ:
            raise ValueError("tar uzantı başlığı tek okumada 1 MiB sınırını aşıyor")
        return super()._proc_pax(archive)

    def _proc_gnulong(self, archive):
        if self.size > _MAX_REGISTRY_TAR_METADATA_READ:
            raise ValueError("GNU tar uzantı başlığı 1 MiB sınırını aşıyor")
        return super()._proc_gnulong(archive)


class TomlWriter:
    """Temiz ve standart TOML çıktı serileştirici."""
    @staticmethod
    def dumps(data: Dict[str, Any]) -> str:
        lines: List[str] = []
        # Primitive / top-level keys first
        simple_items = {k: v for k, v in data.items() if not isinstance(v, (dict, list))}
        for k, v in simple_items.items():
            lines.append(f"{k} = {TomlWriter._format_val(v)}")
        if simple_items:
            lines.append("")

        # Tables (dict)
        for section, table in data.items():
            if isinstance(table, dict):
                lines.append(f"[{section}]")
                for k, v in table.items():
                    lines.append(f"{k} = {TomlWriter._format_val(v)}")
                lines.append("")
            elif isinstance(table, list) and all(isinstance(item, dict) for item in table):
                # Array of tables
                for item in table:
                    lines.append(f"[[{section}]]")
                    for k, v in item.items():
                        lines.append(f"{k} = {TomlWriter._format_val(v)}")
                    lines.append("")
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _format_val(val: Any) -> str:
        if isinstance(val, bool):
            return "true" if val else "false"
        elif isinstance(val, (int, float)):
            return str(val)
        elif isinstance(val, str):
            escaped = val.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            return f'"{escaped}"'
        elif isinstance(val, list):
            items_str = ", ".join(TomlWriter._format_val(x) for x in val)
            return f"[{items_str}]"
        elif isinstance(val, dict):
            # Inline table
            pairs = [f"{k} = {TomlWriter._format_val(v)}" for k, v in val.items()]
            return "{" + ", ".join(pairs) + "}"
        return f'"{str(val)}"'


def parse_toml(content: str) -> Dict[str, Any]:
    if tomllib is not None:
        return tomllib.loads(content)
    # Basit acil durum parser'ı
    result: Dict[str, Any] = {}
    current_section = result
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            sec_name = line[1:-1].strip()
            result[sec_name] = {}
            current_section = result[sec_name]
        elif "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if v.startswith("{") and v.endswith("}"):
                # Inline table: { path = "/x", rev = "main" }
                table = {}
                for part in v[1:-1].split(","):
                    if "=" not in part:
                        continue
                    ik, iv = part.split("=", 1)
                    table[ik.strip()] = iv.strip().strip('"').strip("'")
                current_section[k] = table
            else:
                current_section[k] = v.strip('"').strip("'")
    return result


_DEP_NAME_RE = re.compile(r"^(@[A-Za-z0-9_.\-]+/)?[A-Za-z0-9_.\-]+$")


def is_valid_dep_name(name: str) -> bool:
    """Paket adi: 'ad' veya '@kapsam/ad'. Yol ayirici/kaçış karakteri yasak."""
    if not name or ".." in name or "\\" in name:
        return False
    if name.count("/") > 1:
        return False
    return bool(_DEP_NAME_RE.match(name))


def dep_dir_name(name: str) -> str:
    """Paket adini dosya sistemi icin guvenli dizin adina cevirir."""
    return name.replace("/", "__")


def _valid_registry_constraint(value: str) -> bool:
    if value in ("*", "latest"):
        return True
    parts = value.split(",")
    return bool(parts) and all(
        part.strip() in ("*", "latest")
        or _REGISTRY_CONSTRAINT_PART_RE.fullmatch(part.strip())
        for part in parts
    )


def _validate_registry_pack_archive(
    raw: bytes,
    archive_path: Path,
    package_name: str,
    package_version: str,
    indexed_dependencies: Dict[str, str],
) -> None:
    """Validate a signed pack's tar structure and metadata without extracting it."""
    if len(raw) > _MAX_REGISTRY_PACK_BYTES:
        raise ValueError(f"paket arşivi sıkıştırılmış boyut sınırını aşıyor: {archive_path}")
    try:
        # Bound gzip expansion before tarfile parses PAX/GNU extension headers.
        # SpooledTemporaryFile keeps large but valid packages off Python memory.
        with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as compressed, \
                tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b") as tar_data:
            expanded_size = 0
            while True:
                chunk = compressed.read(64 * 1024)
                if not chunk:
                    break
                expanded_size += len(chunk)
                if expanded_size > _MAX_REGISTRY_TAR_EXPANDED_BYTES:
                    raise ValueError("tar arşivi açılmış akış boyutu sınırını aşıyor")
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
                entries: Dict[str, Tuple[bool, tarfile.TarInfo]] = {}
                total_size = 0
                member_count = 0
                manifest_text = None
                regular_files = set()
                while True:
                    member = archive.next()
                    if member is None:
                        break
                    member_count += 1
                    if member_count > _MAX_REGISTRY_ARCHIVE_MEMBERS:
                        raise ValueError(f"paket arşivindeki dosya sayısı sınır dışında: {archive_path}")
                    name = member.name
                    is_directory = member.isdir()
                    normalized_name = name[:-1] if is_directory and name.endswith("/") else name
                    if (
                        not normalized_name
                        or normalized_name.startswith("/")
                        or "\\" in normalized_name
                        or any(part in ("", ".", "..") for part in normalized_name.split("/"))
                        or ":" in normalized_name.split("/", 1)[0]
                    ):
                        raise ValueError(f"güvensiz tarball yolu: {name!r}")
                    if not (member.isfile() or is_directory):
                        raise ValueError(f"desteklenmeyen tarball girdisi: {name!r}")
                    if member.mode & ~0o777:
                        raise ValueError(f"özel izin bitli tarball girdisi: {name!r}")
                    if is_directory and member.size != 0:
                        raise ValueError(f"boyutlu dizin girdisi desteklenmiyor: {name!r}")
                    if member.isfile():
                        if name.endswith("/") or member.size < 0:
                            raise ValueError(f"geçersiz tarball dosya girdisi: {name!r}")
                        total_size += member.size
                        if total_size > _MAX_REGISTRY_ARCHIVE_BYTES:
                            raise ValueError("paket arşivi açılmış boyut sınırını aşıyor")
                        regular_files.add(normalized_name)
                        if normalized_name == "axiom.toml":
                            if member.size > _MAX_REGISTRY_MANIFEST_BYTES:
                                raise ValueError("paket manifesto boyutu 1 MiB sınırını aşıyor")
                            manifest_stream = archive.extractfile(member)
                            if manifest_stream is None:
                                raise ValueError("paket tarball'ındaki axiom.toml okunamadı")
                            with manifest_stream:
                                manifest_text = manifest_stream.read(member.size).decode("utf-8")
                    if normalized_name in entries:
                        raise ValueError(f"yinelenen tarball yolu: {normalized_name}")
                    entries[normalized_name] = (is_directory, member)

                if member_count == 0:
                    raise ValueError(f"paket arşivi boş: {archive_path}")

                for name, (is_directory, _) in entries.items():
                    parent = PurePosixPath(name).parent
                    while parent != PurePosixPath("."):
                        parent_name = parent.as_posix()
                        if parent_name in entries and not entries[parent_name][0]:
                            raise ValueError(f"tarball dosyası başka bir yolun üst dizini: {parent_name}")
                        parent = parent.parent
                    if not is_directory and any(
                        candidate.startswith(name + "/") for candidate in entries
                    ):
                        raise ValueError(f"tarball dosyası alt yol içeriyor: {name}")

                if manifest_text is None:
                    raise ValueError("paket tarball'ında kök axiom.toml yok")
                manifest_data = parse_toml(manifest_text)
    except (OSError, EOFError, tarfile.TarError, UnicodeDecodeError, zlib.error) as exc:
        raise ValueError(f"geçersiz paket tarball'ı: {archive_path}: {exc}") from exc

    package_data = manifest_data.get("package") or manifest_data.get("project") or {}
    if not isinstance(package_data, dict):
        raise ValueError("tarball axiom.toml içindeki [package] nesne olmalı")
    if package_data.get("name") != package_name:
        raise ValueError(
            f"index paket adı tarball manifestosuyla uyuşmuyor: {package_name!r}"
        )
    if package_data.get("version") != package_version:
        raise ValueError(
            f"index sürümü tarball manifestosuyla uyuşmuyor: {package_version!r}"
        )
    build_data = manifest_data.get("build") or {}
    if not isinstance(build_data, dict):
        raise ValueError("tarball axiom.toml içindeki [build] nesne olmalı")
    entry = package_data.get("entry") or build_data.get("entry") or "src/main.ax"
    if not isinstance(entry, str) or entry not in regular_files:
        raise ValueError(f"paket giriş dosyası tarball'da yok: {entry!r}")

    manifest_dependencies = manifest_data.get("dependencies") or {}
    if not isinstance(manifest_dependencies, dict):
        raise ValueError("tarball axiom.toml içindeki [dependencies] nesne olmalı")
    for dependency, constraint in manifest_dependencies.items():
        if (
            not is_valid_dep_name(dependency)
            or not isinstance(constraint, str)
            or not _valid_registry_constraint(constraint)
        ):
            raise ValueError(f"geçersiz registry bağımlılığı: {dependency!r}")
    if manifest_dependencies != indexed_dependencies:
        raise ValueError("index bağımlılıkları tarball manifestosuyla uyuşmuyor")


def compute_dir_checksum(directory: Path) -> str:
    """Bir dizindeki tüm .ax ve konfigürasyon dosyalarının deterministik SHA-256 sağlama toplamı."""
    hasher = hashlib.sha256()
    if not directory.exists():
        return hasher.hexdigest()

    all_files: List[Path] = []
    if directory.is_file():
        all_files = [directory]
    else:
        for root, dirs, files in os.walk(directory):
            if ".git" in dirs:
                dirs.remove(".git")
            for f in sorted(files):
                if f.endswith((".ax", ".toml", ".c", ".h")):
                    all_files.append(Path(root) / f)

    all_files.sort(key=lambda p: str(p.relative_to(directory.parent if directory.is_file() else directory)))
    for p in all_files:
        rel = str(p.relative_to(directory.parent if directory.is_file() else directory))
        hasher.update(rel.encode("utf-8"))
        try:
            hasher.update(p.read_bytes())
        except OSError:
            pass
    return hasher.hexdigest()


class Manifest:
    """Axiom proje manifestosu (axiom.toml)."""
    def __init__(
        self,
        name: str,
        version: str = "0.1.0",
        authors: Optional[List[str]] = None,
        edition: str = "2026",
        entry: Optional[str] = None,
        description: str = "",
        license_str: str = "MIT",
        dependencies: Optional[Dict[str, Any]] = None,
        raw_data: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.version = version
        self.authors = authors or ["Axiom Developer"]
        self.edition = edition
        self.entry = entry or "src/main.ax"
        self.description = description
        self.license = license_str
        self.dependencies: Dict[str, Any] = dependencies or {}
        self.raw_data = raw_data or {}

    @classmethod
    def from_file(cls, path: Path) -> "Manifest":
        if not path.exists():
            raise FileNotFoundError(f"Manifesto dosyası bulunamadı: {path}")
        content = path.read_text(encoding="utf-8")
        data = parse_toml(content)

        pkg_info = data.get("package") or data.get("project") or {}
        name = pkg_info.get("name", path.parent.name)
        version = pkg_info.get("version", "0.1.0")
        authors = pkg_info.get("authors") or ([pkg_info["author"]] if "author" in pkg_info else ["Axiom Developer"])
        edition = pkg_info.get("edition", "2026")
        entry = pkg_info.get("entry") or (data.get("build", {}).get("entry")) or "src/main.ax"
        desc = pkg_info.get("description", "")
        lic = pkg_info.get("license", "MIT")
        deps = data.get("dependencies", {})

        return cls(
            name=name,
            version=version,
            authors=authors,
            edition=edition,
            entry=entry,
            description=desc,
            license_str=lic,
            dependencies=deps,
            raw_data=data
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "package": {
                "name": self.name,
                "version": self.version,
                "authors": self.authors,
                "edition": self.edition,
                "entry": self.entry,
                "description": self.description,
                "license": self.license
            },
            "dependencies": self.dependencies
        }
        # Bilinmeyen bolumleri koru ([registry], [build], [features] ...).
        # Aksi halde axpm add/remove bu ayarlari sessizce siler.
        for key, value in (self.raw_data or {}).items():
            if key in ("package", "project", "dependencies"):
                continue
            d[key] = value
        return d

    def save(self, path: Path):
        data = self.to_dict()
        toml_str = TomlWriter.dumps(data)
        path.write_text(toml_str, encoding="utf-8")


class LockFile:
    """Deterministik ve doğrulanabilir Axiom kilit dosyası (axiom.lock)."""
    def __init__(self, version: int = 1, packages: Optional[List[Dict[str, Any]]] = None):
        self.version = version
        self.packages: List[Dict[str, Any]] = packages or []

    @classmethod
    def from_file(cls, path: Path) -> "LockFile":
        if not path.exists():
            return cls(version=1, packages=[])
        content = path.read_text(encoding="utf-8")
        data = parse_toml(content)
        ver = int(data.get("version", 1))
        pkgs = data.get("package") or data.get("packages") or []
        if isinstance(pkgs, dict):
            pkgs = [pkgs]
        return cls(version=ver, packages=pkgs)

    def save(self, path: Path):
        content_lines = [
            "# Bu dosya Axiom Paket Yöneticisi (axpm) tarafından otomatik olarak üretilmiştir.",
            "# Manuel olarak değiştirilmesi önerilmez; 'axiom pkg install' ile güncelleyin.",
            "",
            f"version = {self.version}",
            ""
        ]
        for pkg in self.packages:
            content_lines.append("[[package]]")
            for k, v in pkg.items():
                content_lines.append(f"{k} = {TomlWriter._format_val(v)}")
            content_lines.append("")
        path.write_text("\n".join(content_lines).strip() + "\n", encoding="utf-8")

    def verify(self, root_dir: Path) -> Tuple[bool, str]:
        """Kilit dosyasındaki paketlerin SHA-256 sağlama toplamlarını yerel durumla doğrular."""
        for pkg in self.packages:
            name = pkg.get("name")
            locked_checksum = pkg.get("checksum")
            source = pkg.get("source", "")
            if source.startswith("path:"):
                rel_path = source[5:]
                target_dir = (root_dir / rel_path).resolve()
                if not target_dir.exists():
                    return False, f"Bağımlılık hedef yolu bulunamadı: '{target_dir}' (Paket: {name})"
                actual_checksum = compute_dir_checksum(target_dir)
                if actual_checksum != locked_checksum:
                    return False, (
                        f"Kilit doğrulama hatası! '{name}' için SHA-256 uyumsuzluğu.\n"
                        f"  Kilitli: {locked_checksum}\n"
                        f"  Gerçek : {actual_checksum}"
                    )
            elif source.startswith("registry:"):
                target_dir = (root_dir / ".axiom" / "deps" / dep_dir_name(name)).resolve()
                if not target_dir.exists():
                    return False, f"Registry bağımlılığı kurulu değil: '{name}' (axpm install)"
                actual_checksum = compute_dir_checksum(target_dir)
                if actual_checksum != locked_checksum:
                    return False, (
                        f"Kilit doğrulama hatası! '{name}' registry paketi için SHA-256 uyumsuzluğu.\n"
                        f"  Kilitli: {locked_checksum}\n"
                        f"  Gerçek : {actual_checksum}"
                    )
            elif source.startswith("git:"):
                target_dir = (root_dir / ".axiom" / "deps" / dep_dir_name(name)).resolve()
                if not target_dir.exists():
                    return False, f"Git bağımlılık hedef yolu bulunamadı: '{target_dir}' (Paket: {name})"
                actual_checksum = compute_dir_checksum(target_dir)
                if actual_checksum != locked_checksum:
                    return False, (
                        f"Kilit doğrulama hatası! '{name}' git paketi için SHA-256 uyumsuzluğu.\n"
                        f"  Kilitli: {locked_checksum}\n"
                        f"  Gerçek : {actual_checksum}"
                    )
        return True, "Doğrulama başarılı"


class PackageManager:
    """Axiom Paket Yönetim Motoru."""
    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.manifest_path = self.root_dir / "axiom.toml"
        self.lock_path = self.root_dir / "axiom.lock"
        self.deps_dir = self.root_dir / ".axiom" / "deps"

    def init_package(
        self,
        target_dir: Optional[Path] = None,
        name: Optional[str] = None,
        is_lib: bool = False
    ) -> Path:
        dest = (target_dir or self.root_dir).resolve()
        if dest.exists() and any(dest.iterdir()):
            # İçi boş olmayan dizin kontrolü
            manifest_check = dest / "axiom.toml"
            if manifest_check.exists():
                raise RuntimeError(f"'{dest}' dizininde zaten bir axiom.toml manifestosu mevcut.")

        dest.mkdir(parents=True, exist_ok=True)
        pkg_name = name or dest.name

        src_dir = dest / "src"
        src_dir.mkdir(exist_ok=True)
        tests_dir = dest / "tests"
        tests_dir.mkdir(exist_ok=True)

        entry_file = "src/lib.ax" if is_lib else "src/main.ax"
        manifest = Manifest(
            name=pkg_name,
            version="0.1.0",
            authors=["Axiom Developer <developer@axiom-lang.org>"],
            edition="2026",
            entry=entry_file,
            description=f"Axiom {pkg_name} paketi",
            dependencies={}
        )
        manifest.save(dest / "axiom.toml")

        if is_lib:
            lib_content = f"""// Axiom (λx) - {pkg_name} Kütüphanesi

fn add(a: int, b: int) -> int
requires true
ensures return == a + b
{{
    return a + b
}}

fn greeting(who: str) -> str {{
    return "Merhaba, " + who
}}
"""
            (src_dir / "lib.ax").write_text(lib_content, encoding="utf-8")
        else:
            main_content = f"""// Axiom (λx) - {pkg_name} Giriş Noktası

fn main() -> void {{
    let name = "{pkg_name}"
    print("Axiom Paketi Çalışıyor:", name)
}}
"""
            (src_dir / "main.ax").write_text(main_content, encoding="utf-8")

        if is_lib:
            test_content = f"""// Axiom Test - {pkg_name}
import "../{entry_file}"

fn main() -> void {{
    let res = add(10, 20)
    verify res == 30
    print("Testler basariyla tamamlandi:", greeting("{pkg_name}"))
}}
"""
        else:
            test_content = f"""// Axiom Test - {pkg_name}

fn main() -> void {{
    print("Testler basariyla tamamlandi: {pkg_name}")
}}
"""
        (tests_dir / "test_main.ax").write_text(test_content, encoding="utf-8")

        # .gitignore
        (dest / ".gitignore").write_text(
            "# Axiom derleme ve kilit artıkları\n*.o\n*.c\ntarget/\n.axiom/\n",
            encoding="utf-8"
        )
        # README.md
        (dest / "README.md").write_text(
            f"# {pkg_name}\n\nAxiom (λx) paketi.\n\n```bash\naxiom pkg build\naxiom pkg run\naxiom pkg test\n```\n",
            encoding="utf-8"
        )

        # İlk boş lock dosyası
        lock = LockFile(version=1, packages=[])
        lock.save(dest / "axiom.lock")
        return dest

    def add_dependency(
        self,
        dep_name: str,
        path: Optional[str] = None,
        git: Optional[str] = None,
        version: Optional[str] = None,
        rev: Optional[str] = None
    ):
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"axiom.toml bulunamadı: {self.manifest_path}")

        if not is_valid_dep_name(dep_name):
            raise ValueError(
                f"Gecersiz paket adi: '{dep_name}'. Beklenen: 'ad' veya '@kapsam/ad'."
            )
        manifest = Manifest.from_file(self.manifest_path)
        if path:
            manifest.dependencies[dep_name] = {"path": path}
        elif git:
            manifest.dependencies[dep_name] = {"git": git, "rev": rev or "main"}
        elif version:
            manifest.dependencies[dep_name] = version
        else:
            # Varsayılan son kararlı sürüm
            manifest.dependencies[dep_name] = "0.1.0"

        manifest.save(self.manifest_path)
        print(f"{CLR_GREEN}✓ Bağımlılık eklendi:{CLR_RESET} '{dep_name}' -> axiom.toml")
        self.install()

    def install(self) -> LockFile:
        """Tüm bağımlılıkları çözümler, deterministik SHA-256 hesaplar ve axiom.lock üretir."""
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"axiom.toml bulunamadı: {self.manifest_path}")

        manifest = Manifest.from_file(self.manifest_path)
        locked_packages: List[Dict[str, Any]] = []

        self.deps_dir.mkdir(parents=True, exist_ok=True)

        for dep_name, dep_spec in manifest.dependencies.items():
            if isinstance(dep_spec, dict) and "path" in dep_spec:
                rel_path = dep_spec["path"]
                dep_dir = (self.root_dir / rel_path).resolve()
                if not dep_dir.exists():
                    raise FileNotFoundError(f"Yerel bağımlılık dizini bulunamadı: '{dep_dir}'")
                
                # Alt manifestoyu kontrol et
                sub_manifest_path = dep_dir / "axiom.toml"
                sub_version = "0.1.0"
                if sub_manifest_path.exists():
                    try:
                        sub_manifest = Manifest.from_file(sub_manifest_path)
                        sub_version = sub_manifest.version
                    except Exception:
                        pass

                checksum = compute_dir_checksum(dep_dir)
                locked_packages.append({
                    "name": dep_name,
                    "version": sub_version,
                    "source": f"path:{rel_path}",
                    "checksum": checksum,
                    "dependencies": []
                })
            elif isinstance(dep_spec, dict) and "git" in dep_spec:
                git_url = dep_spec["git"]
                rev = dep_spec.get("rev", "main")
                target_dir = (self.deps_dir / dep_dir_name(dep_name)).resolve()

                # Hedef dizin varsa ve geçerli bir git deposu/dizinse koru; boş veya bozuksa temizle
                if target_dir.exists() and not (target_dir / ".git").exists() and not any(target_dir.iterdir()):
                    shutil.rmtree(target_dir, ignore_errors=True)

                if not target_dir.exists() or not any(target_dir.iterdir()):
                    target_dir.parent.mkdir(parents=True, exist_ok=True)
                    clone_cmd = ["git", "clone", "--depth", "1"]
                    if rev and rev != "HEAD":
                        clone_cmd.extend(["-b", rev])
                    clone_cmd.extend([git_url, str(target_dir)])
                    try:
                        res = subprocess.run(clone_cmd, capture_output=True, text=True)
                        if res.returncode != 0:
                            if target_dir.exists():
                                shutil.rmtree(target_dir, ignore_errors=True)
                            raise RuntimeError(
                                f"Git bağımlılığı klonlanamadı ('{dep_name}' -> {git_url} @ {rev}):\n{res.stderr.strip()}"
                            )
                    except FileNotFoundError:
                        raise RuntimeError("Sistemde 'git' aracı bulunamadı. Lütfen git kurun.")

                sub_version = rev
                sub_manifest_path = target_dir / "axiom.toml"
                if sub_manifest_path.exists():
                    try:
                        sub_manifest = Manifest.from_file(sub_manifest_path)
                        sub_version = sub_manifest.version
                    except Exception:
                        pass

                checksum = compute_dir_checksum(target_dir)
                locked_packages.append({
                    "name": dep_name,
                    "version": sub_version,
                    "source": f"git:{git_url}#{rev}",
                    "checksum": checksum,
                    "dependencies": []
                })
            # registry bağımlılıkları toplu çözülür (aşağıda)

        # --- Registry bağımlılıkları (transitive çözümleme) ---
        registry_deps = {name: spec for name, spec in manifest.dependencies.items()
                         if not (isinstance(spec, dict) and ("path" in spec or "git" in spec))}
        if registry_deps:
            config = RegistryConfig.from_manifest(manifest.raw_data)
            client = RegistryClient(config)
            tree = resolve_tree(client.index, {k: str(v) for k, v in registry_deps.items()})
            for name, info in sorted(tree.items()):
                version = info["version"]
                target_dir = (self.deps_dir / dep_dir_name(name)).resolve()
                src_dir, cache_hit = client.download(
                    name, version, info["sha256"], info["sig"], info["deps"]
                )
                target_dir.parent.mkdir(parents=True, exist_ok=True)
                # A new lock version must replace the previous installed
                # contents. Stage beside the destination so the final rename
                # is atomic; restore the old directory if promotion fails.
                with tempfile.TemporaryDirectory(
                    prefix=".axpm-package-", dir=str(target_dir.parent)
                ) as staging_root:
                    staged_dir = Path(staging_root) / "package"
                    backup_dir = Path(staging_root) / "previous"
                    shutil.copytree(src_dir, staged_dir)
                    had_previous = target_dir.exists()
                    if had_previous:
                        os.replace(target_dir, backup_dir)
                    try:
                        os.replace(staged_dir, target_dir)
                    except Exception:
                        if had_previous and backup_dir.exists():
                            os.replace(backup_dir, target_dir)
                        raise
                checksum = compute_dir_checksum(target_dir)
                locked_packages.append({
                    "name": name,
                    "version": version,
                    "source": f"registry:{version}",
                    "checksum": checksum,
                    "dependencies": sorted(info["deps"].keys()),
                    "sha256": info["sha256"],
                })

        # Deterministik sıralama
        locked_packages.sort(key=lambda p: p["name"])
        lock = LockFile(version=1, packages=locked_packages)
        lock.save(self.lock_path)
        print(f"{CLR_GREEN}✓ Bağımlılıklar kilitlendi:{CLR_RESET} {len(locked_packages)} paket -> axiom.lock")
        return lock

    def pack(self, signing_key: Path, output_dir: Optional[Path] = None) -> Path:
        """Create a deterministic, signed registry artifact from a clean Git tree."""
        key_path = signing_key.expanduser()
        if not key_path.is_absolute():
            key_path = self.root_dir / key_path
        key_path = key_path.resolve()
        if not key_path.is_file():
            raise FileNotFoundError(f"Ed25519 imza anahtarı bulunamadı: {key_path}")

        if not self.manifest_path.is_file():
            raise FileNotFoundError(f"Manifesto dosyası bulunamadı: {self.manifest_path}")
        manifest = Manifest.from_file(self.manifest_path)
        if not is_valid_dep_name(manifest.name):
            raise ValueError(f"geçersiz paket adı: {manifest.name!r}")
        try:
            parse_version(manifest.version)
        except SemverError as exc:
            raise ValueError(f"geçersiz paket sürümü: {manifest.version!r}") from exc

        dependencies = {}
        for name, constraint in manifest.dependencies.items():
            if not is_valid_dep_name(name) or not isinstance(constraint, str):
                raise ValueError(
                    "registry paketi bağımlılıkları geçerli ad ve sürüm aralığı olmalı; "
                    f"'{name}' path/git bağımlılıkları registry'de yayımlanamaz"
                )
            dependencies[name] = constraint

        def git(*args: str) -> bytes:
            try:
                result = subprocess.run(
                    ["git", "-C", str(self.root_dir), *args],
                    capture_output=True, check=False, timeout=30,
                )
            except FileNotFoundError as exc:
                raise RuntimeError("axpm pack için Git gerekli") from exc
            if result.returncode:
                detail = result.stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"Git komutu başarısız: {' '.join(args)}\n{detail}")
            return result.stdout

        repo_root = Path(os.fsdecode(git("rev-parse", "--show-toplevel")).strip()).resolve()
        package_rel = self.root_dir.relative_to(repo_root)
        try:
            key_path.relative_to(repo_root)
        except ValueError:
            pass
        else:
            raise ValueError("registry imza anahtarını Git deposunun dışında tutun")
        dirty = git("status", "--porcelain", "--untracked-files=no").decode("utf-8", errors="replace")
        if dirty:
            raise RuntimeError("axpm pack için izlenen dosyalardaki değişiklikleri önce commit edin")

        tracked = git("ls-files", "--full-name", "--stage", "-z").split(b"\0")
        files = []
        for record in tracked:
            if not record:
                continue
            metadata, raw_path = record.split(b"\t", 1)
            mode = metadata.split(b" ", 1)[0]
            repo_relative = Path(os.fsdecode(raw_path))
            try:
                relative = repo_relative.relative_to(package_rel)
            except ValueError:
                continue
            parts = relative.parts
            if (
                relative.is_absolute()
                or any(part in ("..", ".git", ".axiom") for part in parts)
                or "\\" in relative.as_posix()
                or (parts and ":" in parts[0])
            ):
                raise RuntimeError(f"paket içinde güvenli olmayan yol: {relative}")
            if any(part in {"target", "dist", ".venv", "venv", "__pycache__"} for part in parts):
                continue
            lower_name = relative.name.lower()
            if (lower_name == "axiom.lock" or lower_name == ".env"
                    or lower_name.startswith(".env.")
                    or lower_name.endswith((".pem", ".key", ".p12", ".pfx"))
                    or lower_name in {"id_rsa", "id_ed25519"}):
                continue
            if mode not in (b"100644", b"100755"):
                raise RuntimeError(f"paket symlink veya özel Git girdisi içeremez: {relative}")
            source = repo_root / repo_relative
            if source.is_symlink() or not source.is_file():
                raise RuntimeError(f"paket girdisi normal dosya değil: {relative}")
            files.append((relative, source, mode == b"100755"))
        files.sort(key=lambda item: item[0].as_posix())
        file_names = {path.as_posix() for path, _, _ in files}
        if "axiom.toml" not in file_names:
            raise RuntimeError("axiom.toml Git tarafından izlenmeli ve commit edilmiş olmalı")
        if manifest.entry not in file_names:
            raise RuntimeError(f"paket giriş dosyası Git tarafından izlenmiyor: {manifest.entry}")

        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for relative, source, executable in files:
                content = source.read_bytes()
                info = tarfile.TarInfo(relative.as_posix())
                info.size = len(content)
                info.mode = 0o755 if executable else 0o644
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(content))
        compressed = io.BytesIO()
        with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=0, compresslevel=9) as gz:
            gz.write(tar_buffer.getvalue())
        archive_bytes = compressed.getvalue()

        with tempfile.TemporaryDirectory(prefix="axpm-pack-sign-") as temp_dir:
            temp = Path(temp_dir)
            payload = temp / "package.tar.gz"
            signature = temp / "package.sig"
            payload.write_bytes(archive_bytes)
            sign_args = ["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(key_path),
                         "-in", str(payload), "-out", str(signature)]
            if os.environ.get("AXIOM_REGISTRY_SIGNING_PASSPHRASE"):
                sign_args.extend(["-passin", "env:AXIOM_REGISTRY_SIGNING_PASSPHRASE"])
            try:
                result = subprocess.run(
                    sign_args, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                    timeout=30, check=False,
                )
            except FileNotFoundError as exc:
                raise RuntimeError("axpm pack için OpenSSL gerekli") from exc
            if result.returncode:
                detail = result.stderr.strip()
                raise RuntimeError(f"Ed25519 paketi imzalanamadı: {detail}")
            signature_b64 = base64.b64encode(signature.read_bytes()).decode("ascii")

        output_root = (output_dir or (self.root_dir / "dist" / "registry")).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        package_dir = output_root
        for component in manifest.name.split("/"):
            package_dir = package_dir / component
            if package_dir.is_symlink():
                raise RuntimeError(f"çıktı yolu symlink içeremez: {package_dir}")
            package_dir.mkdir(exist_ok=True)
        if not package_dir.resolve().is_relative_to(output_root):
            raise RuntimeError(f"paket çıktı dizini registry kökü dışına taşıyor: {package_dir}")
        final_dir = package_dir / manifest.version
        if final_dir.exists() or final_dir.is_symlink():
            raise FileExistsError(f"paket çıktısı zaten var: {final_dir}")

        entry = {
            "version": manifest.version,
            "sha256": sha256_bytes(archive_bytes),
            "sig": signature_b64,
            "dependencies": dependencies,
            "yanked": False,
        }
        with tempfile.TemporaryDirectory(prefix=".axpm-pack-", dir=str(package_dir)) as stage_name:
            stage = Path(stage_name)
            (stage / f"{manifest.version}.tar.gz").write_bytes(archive_bytes)
            (stage / f"{manifest.version}.index-entry.json").write_text(
                json.dumps(entry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            os.replace(stage, final_dir)
        return final_dir

    def assemble_registry(self, pack_dir: Path, output_dir: Path, public_key_path: Path) -> Path:
        """Build and verify an offline static Registry v1 tree from ``axpm pack`` output.

        This command never uploads content and never accepts a private key. The
        destination is committed atomically only after every input artifact has
        passed validation.
        """
        source_arg = pack_dir.expanduser()
        if source_arg.is_symlink() or not source_arg.is_dir():
            raise ValueError(f"pack çıktısı normal bir dizin olmalı: {source_arg}")
        source_root = source_arg.resolve()

        def ensure_source_file(path: Path) -> None:
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"pack girdisi normal dosya olmalı: {path}")
            try:
                path.resolve().relative_to(source_root)
            except ValueError:
                raise ValueError(f"pack girdisi kaynak dizin dışına taşıyor: {path}") from None
            parent = path.parent
            while parent != source_root:
                if parent.is_symlink():
                    raise ValueError(f"pack girdisi symlink dizin içeremez: {parent}")
                parent = parent.parent

        output_arg = output_dir.expanduser()
        if output_arg.name in ("", ".", ".."):
            raise ValueError("registry çıktısı yeni bir dizin adı olmalı")
        if output_arg.is_symlink():
            raise ValueError(f"registry çıktı yolu symlink olamaz: {output_arg}")
        output_parent = output_arg.parent.resolve()
        if not output_parent.is_dir():
            raise FileNotFoundError(f"registry çıktı üst dizini yok: {output_parent}")
        output_root = output_parent / output_arg.name
        if output_root.exists():
            if not output_root.is_dir() or any(output_root.iterdir()):
                raise FileExistsError(f"registry çıktı dizini boş olmalı: {output_root}")

        if (output_root == source_root or output_root.is_relative_to(source_root)
                or source_root.is_relative_to(output_root)):
            raise ValueError("pack girdisi ve registry çıktısı iç içe olamaz")

        key_arg = public_key_path.expanduser()
        if key_arg.is_symlink() or not key_arg.is_file():
            raise FileNotFoundError(f"registry açık anahtarı normal bir dosya olmalı: {key_arg}")
        try:
            public_key = key_arg.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(f"registry açık anahtarı okunamadı: {exc}") from exc
        if not public_key.strip():
            raise ValueError("registry açık anahtarı boş olamaz")

        # The pack output is deliberately a staging layout. Require every
        # payload and sidecar to form exactly one name/version pair.
        artifacts: Dict[Tuple[str, str], Dict[str, Path]] = {}
        seen_directories = set()
        artifact_count = 0

        def walk_error(exc: OSError) -> None:
            raise ValueError(f"pack girdisi okunamadı: {exc}") from exc

        for current, directory_names, file_names in os.walk(
            source_root, followlinks=False, onerror=walk_error
        ):
            current_path = Path(current)
            for directory in directory_names:
                directory_path = current_path / directory
                if directory_path.is_symlink():
                    raise ValueError(f"pack girdisi symlink içeremez: {directory_path}")
                seen_directories.add(directory_path.relative_to(source_root).as_posix())
                if len(seen_directories) > _MAX_REGISTRY_PACK_DIRECTORIES:
                    raise ValueError("pack çıktısındaki dizin sayısı sınırı aşıyor")
            for filename in file_names:
                path = current_path / filename
                ensure_source_file(path)
                relative = path.relative_to(source_root)
                parts = relative.parts
                if filename.endswith(".index-entry.json"):
                    artifact_kind = "entry"
                    artifact_version = filename[:-len(".index-entry.json")]
                elif filename.endswith(".tar.gz"):
                    artifact_kind = "archive"
                    artifact_version = filename[:-len(".tar.gz")]
                else:
                    raise ValueError(f"beklenmeyen pack çıktısı: {relative}")
                if len(parts) < 3 or parts[-2] != artifact_version:
                    raise ValueError(f"pack girdisi name/version yapısında değil: {relative}")
                package_name = "/".join(parts[:-2])
                if not is_valid_dep_name(package_name):
                    raise ValueError(f"geçersiz paket yolu: {relative}")
                try:
                    parse_version(artifact_version)
                except SemverError as exc:
                    raise ValueError(f"geçersiz sürüm dizini: {relative}") from exc
                key = (package_name, artifact_version)
                slot = artifacts.setdefault(key, {})
                if artifact_kind in slot:
                    raise ValueError(f"yinelenen paket çıktısı: {package_name}@{artifact_version}")
                slot[artifact_kind] = path
                artifact_count += 1
                if artifact_count > _MAX_REGISTRY_PACKAGES * 2:
                    raise ValueError("pack çıktısındaki paket/sidecar sayısı sınırı aşıyor")

        if not artifacts:
            raise ValueError(f"pack çıktısında imzalı paket bulunamadı: {source_root}")
        for relative_dir in seen_directories:
            if not any(
                Path(*key[0].split("/"), key[1]).as_posix() == relative_dir
                or Path(*key[0].split("/"), key[1]).as_posix().startswith(relative_dir + "/")
                for key in artifacts
            ):
                raise ValueError(f"pack girdisinde kullanılmayan dizin: {relative_dir}")

        validated: List[Tuple[str, str, Dict[str, Any], Path]] = []
        for (package_name, package_version), pair in sorted(
            artifacts.items(), key=lambda item: (item[0][0], version_key(item[0][1]))
        ):
            if set(pair) != {"archive", "entry"}:
                raise ValueError(f"paket arşivi ve index girdisi eşleşmiyor: {package_name}@{package_version}")
            sidecar_path = pair["entry"]
            ensure_source_file(sidecar_path)
            if sidecar_path.stat().st_size > _MAX_REGISTRY_SIDECAR_BYTES:
                raise ValueError(f"index girdisi 1 MiB sınırını aşıyor: {sidecar_path}")
            try:
                with sidecar_path.open("rb") as sidecar_file:
                    sidecar_bytes = sidecar_file.read(_MAX_REGISTRY_SIDECAR_BYTES + 1)
                if len(sidecar_bytes) > _MAX_REGISTRY_SIDECAR_BYTES:
                    raise ValueError(f"index girdisi 1 MiB sınırını aşıyor: {sidecar_path}")
                entry = json.loads(sidecar_bytes.decode("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"geçersiz index girdisi {sidecar_path}: {exc}") from exc
            if not isinstance(entry, dict) or set(entry) != _REGISTRY_INDEX_ENTRY_KEYS:
                raise ValueError(f"index girdisi Registry v1 alanlarıyla eşleşmiyor: {sidecar_path}")
            if entry.get("version") != package_version:
                raise ValueError(f"index sürümü dosya yoluyla uyuşmuyor: {sidecar_path}")
            if type(entry.get("yanked")) is not bool:
                raise ValueError(f"index girdisindeki yanked bool olmalı: {sidecar_path}")
            dependencies = entry.get("dependencies")
            if not isinstance(dependencies, dict):
                raise ValueError(f"index girdisindeki dependencies nesne olmalı: {sidecar_path}")
            for dependency, constraint in dependencies.items():
                if (not is_valid_dep_name(dependency) or not isinstance(constraint, str)
                        or not _valid_registry_constraint(constraint)):
                    raise ValueError(f"geçersiz bağımlılık index girdisinde: {dependency!r}")

            archive_path = pair["archive"]
            ensure_source_file(archive_path)
            if archive_path.stat().st_size > _MAX_REGISTRY_PACK_BYTES:
                raise ValueError(f"paket arşivi sıkıştırılmış boyut sınırını aşıyor: {archive_path}")
            with archive_path.open("rb") as archive_file:
                archive_bytes = archive_file.read(_MAX_REGISTRY_PACK_BYTES + 1)
            if len(archive_bytes) > _MAX_REGISTRY_PACK_BYTES:
                raise ValueError(f"paket arşivi sıkıştırılmış boyut sınırını aşıyor: {archive_path}")
            if not verify_sha256(archive_bytes, entry.get("sha256")):
                raise ValueError(f"paket SHA-256 doğrulaması başarısız: {package_name}@{package_version}")
            signature_b64 = entry.get("sig")
            if not isinstance(signature_b64, str):
                raise ValueError(f"paket imzası metin olmalı: {package_name}@{package_version}")
            try:
                signature = base64.b64decode(signature_b64, validate=True)
            except (ValueError, base64.binascii.Error) as exc:
                raise ValueError(f"paket imzası geçerli base64 değil: {package_name}@{package_version}") from exc
            if len(signature) != 64 or base64.b64encode(signature).decode("ascii") != signature_b64:
                raise ValueError(f"paket imzası Ed25519 biçiminde değil: {package_name}@{package_version}")
            signature_ok, reason = verify_signature(archive_bytes, signature_b64, public_key)
            if not signature_ok:
                raise ValueError(f"paket imzası doğrulanamadı {package_name}@{package_version}: {reason}")

            _validate_registry_pack_archive(
                archive_bytes, archive_path, package_name, package_version, dependencies
            )
            normalized_entry = {
                "version": package_version,
                "sha256": entry["sha256"].lower(),
                "sig": signature_b64,
                "dependencies": dict(sorted(dependencies.items())),
                "yanked": entry["yanked"],
            }
            validated.append((package_name, package_version, normalized_entry, archive_path))

        if len(validated) > _MAX_REGISTRY_PACKAGES:
            raise ValueError("pack çıktısındaki paket sayısı sınırı aşıyor")

        packages: Dict[str, List[Dict[str, Any]]] = {}
        for package_name, package_version, entry, _ in validated:
            package_versions = packages.setdefault(package_name, [])
            if any(item["version"] == package_version for item in package_versions):
                raise ValueError(f"yinelenen paket sürümü: {package_name}@{package_version}")
            package_versions.append(entry)
        for package_versions in packages.values():
            package_versions.sort(key=lambda item: version_key(item["version"]))

        # Verify the output remains a fresh/empty directory, then stage next to
        # it so the final rename is atomic on the same filesystem.
        stage = Path(tempfile.mkdtemp(prefix=".axpm-registry-assemble-", dir=str(output_parent)))
        try:
            for package_name, package_version, entry, archive_path in validated:
                ensure_source_file(archive_path)
                destination = stage.joinpath(*package_name.split("/"), f"{package_version}.tar.gz")
                destination.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                total_bytes = 0
                with archive_path.open("rb") as source, destination.open("xb") as target:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        total_bytes += len(chunk)
                        if total_bytes > _MAX_REGISTRY_PACK_BYTES:
                            raise RuntimeError(
                                f"paket arşivi kopyalanırken boyut sınırını aştı: "
                                f"{package_name}@{package_version}"
                            )
                        digest.update(chunk)
                        target.write(chunk)
                if digest.hexdigest() != entry["sha256"]:
                    raise RuntimeError(f"paket kopyalanırken değişti: {package_name}@{package_version}")

            index = {"schema": 1, "packages": {name: packages[name] for name in sorted(packages)}}
            (stage / "index.json").write_text(
                json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

            if output_root.is_symlink():
                raise ValueError(f"registry çıktı yolu symlink olamaz: {output_root}")
            if output_root.exists():
                if not output_root.is_dir() or any(output_root.iterdir()):
                    raise FileExistsError(f"registry çıktı dizini boş olmalı: {output_root}")
                output_root.rmdir()
            os.replace(stage, output_root)
        finally:
            if stage.exists():
                shutil.rmtree(stage, ignore_errors=True)
        return output_root

    def get_search_paths(self) -> List[Path]:
        """Paket bağımlılıklarının include / arama yollarını derler."""
        paths: List[Path] = [self.root_dir, self.root_dir / "src", self.deps_dir]
        if self.manifest_path.exists():
            manifest = Manifest.from_file(self.manifest_path)
            for dep_name, dep_spec in manifest.dependencies.items():
                if isinstance(dep_spec, dict) and "path" in dep_spec:
                    p = (self.root_dir / dep_spec["path"]).resolve()
                    paths.append(p)
                    paths.append(p / "src")
                elif isinstance(dep_spec, dict) and "git" in dep_spec:
                    p = (self.deps_dir / dep_dir_name(dep_name)).resolve()
                    if p.exists():
                        paths.append(p)
                        paths.append(p / "src")
        return paths

    def verify(self) -> bool:
        """axiom.lock içindeki checksum'ları yerel bağımlılıklarla karşılaştırır."""
        if not self.lock_path.exists():
            raise FileNotFoundError(f"axiom.lock bulunamadı: {self.lock_path}")
        lock = LockFile.from_file(self.lock_path)
        ok, msg = lock.verify(self.root_dir)
        if ok:
            print(f"{CLR_GREEN}✓ Kilit doğrulaması başarılı:{CLR_RESET} {len(lock.packages)} paket")
        else:
            print(f"{CLR_RED}✗ Kilit doğrulaması başarısız:{CLR_RESET} {msg}", file=sys.stderr)
        return ok

    def tree(self) -> None:
        """Bağımlılık ağacını ve kilitli sürümleri listeler."""
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"axiom.toml bulunamadı: {self.manifest_path}")
        manifest = Manifest.from_file(self.manifest_path)
        lock = LockFile.from_file(self.lock_path) if self.lock_path.exists() else LockFile()
        locked = {p.get("name"): p for p in lock.packages}

        print(f"{CLR_BOLD}{manifest.name}{CLR_RESET} v{manifest.version}")
        if not manifest.dependencies:
            print("  (bağımlılık yok)")
            return
        for dep_name, spec in manifest.dependencies.items():
            if isinstance(spec, dict) and "path" in spec:
                src = f"path:{spec['path']}"
            elif isinstance(spec, dict) and "git" in spec:
                src = f"git:{spec['git']}#{spec.get('rev', 'main')}"
            else:
                src = f"registry:{spec}"
            pkg = locked.get(dep_name)
            if pkg:
                print(f"  ├── {dep_name} {pkg.get('version', '')} [{src}]")
                print(f"  │   └── checksum {str(pkg.get('checksum', ''))[:16]}…")
            else:
                print(f"  ├── {dep_name} [{src}] (kilitli değil)")

    def remove_dependency(self, dep_name: str, purge: bool = False) -> None:
        """axiom.toml ve axiom.lock üzerinden bir bağımlılığı kaldırır."""
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"axiom.toml bulunamadı: {self.manifest_path}")
        manifest = Manifest.from_file(self.manifest_path)
        if dep_name not in manifest.dependencies:
            raise KeyError(f"Bağımlılık bulunamadı: '{dep_name}'")
        spec = manifest.dependencies.pop(dep_name)
        manifest.save(self.manifest_path)

        if self.lock_path.exists():
            lock = LockFile.from_file(self.lock_path)
            previous_packages = lock.packages
            packages_by_name = {p.get("name"): p for p in previous_packages if p.get("name")}

            # Keep only the lockfile graph reachable from dependencies that
            # remain in the manifest. This also drops orphaned registry
            # transitive dependencies instead of leaving stale lock entries.
            reachable = set()
            pending = list(manifest.dependencies)
            while pending:
                name = pending.pop()
                if name in reachable:
                    continue
                reachable.add(name)
                pkg = packages_by_name.get(name, {})
                dependencies = pkg.get("dependencies", [])
                if isinstance(dependencies, list):
                    pending.extend(dep for dep in dependencies if isinstance(dep, str))

            lock.packages = [p for p in previous_packages if p.get("name") in reachable]
            lock.save(self.lock_path)

            # Registry packages are per-project installed copies and should
            # disappear when no remaining root dependency can reach them.
            # Path dependencies are external; Git clones retain the existing
            # opt-in purge behavior.
            for pkg in previous_packages:
                name = pkg.get("name")
                source = pkg.get("source", "")
                should_remove = source.startswith("registry:") or (
                    purge and source.startswith("git:") and name == dep_name
                )
                if name not in reachable and should_remove:
                    dep_dir = self.deps_dir / dep_dir_name(name)
                    if dep_dir.exists():
                        shutil.rmtree(dep_dir, ignore_errors=True)
        elif not (isinstance(spec, dict) and "path" in spec) and (
            purge or not (isinstance(spec, dict) and "git" in spec)
        ):
            # With no lockfile, the removed direct registry package can still
            # be cleaned. Git remains opt-in and path dependencies are external.
            dep_dir = self.deps_dir / dep_dir_name(dep_name)
            if dep_dir.exists():
                shutil.rmtree(dep_dir, ignore_errors=True)

        print(f"{CLR_GREEN}✓ Bağımlılık kaldırıldı:{CLR_RESET} '{dep_name}'")

    def update(self, dep_name: Optional[str] = None) -> None:
        """Git bağımlılıklarını yeniden çeker ve kilidi yeniden üretir.

        - dep_name verilmezse tüm git bağımlılıkları güncellenir.
        - Yerel (path) bağımlılıklar sadece checksum'ları yeniden hesaplanır.
        """
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"axiom.toml bulunamadı: {self.manifest_path}")

        manifest = Manifest.from_file(self.manifest_path)
        targets = [dep_name] if dep_name else [
            k for k, v in manifest.dependencies.items()
            if isinstance(v, dict) and "git" in v
        ]
        for name in targets:
            spec = manifest.dependencies.get(name)
            if not isinstance(spec, dict) or "git" not in spec:
                if dep_name:
                    raise KeyError(f"'{name}' bir git bağımlılığı değil.")
                continue
            dep_dir = (self.deps_dir / dep_dir_name(name)).resolve()
            if dep_dir.exists():
                shutil.rmtree(dep_dir, ignore_errors=True)
            print(f"{CLR_CYAN}↻{CLR_RESET} '{name}' yeniden çekiliyor…")

        # install() eksik git bağımlılıklarını klonlar ve kilidi yeniden yazar.
        self.install()
        print(f"{CLR_GREEN}✓ Güncelleme tamamlandı:{CLR_RESET} {len(targets)} git bağımlılığı")

    def search(self, query: str) -> None:
        """Registry'de paket arar (ad ve açıklama içinde)."""
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"axiom.toml bulunamadı: {self.manifest_path}")
        manifest = Manifest.from_file(self.manifest_path)
        config = RegistryConfig.from_manifest(manifest.raw_data)
        index = RegistryClient(config).index
        q = (query or "").lower()
        hits = []
        for name, versions in sorted(index.packages.items()):
            latest = index.resolve(name, "*")
            desc = (latest or {}).get("description", "")
            if not q or q in name.lower() or q in desc.lower():
                hits.append((name, (latest or {}).get("version", "?"), desc, len(versions)))
        if not hits:
            print(f"{CLR_YELLOW}Sonuç yok:{CLR_RESET} '{query}'")
            return
        for name, ver, desc, count in hits:
            line = f"{CLR_BOLD}{name}{CLR_RESET} {ver}"
            if count > 1:
                line += f" {CLR_CYAN}({count} sürüm){CLR_RESET}"
            if desc:
                line += f" — {desc}"
            print(line)

    def build(
        self,
        release: bool = False,
        debug: bool = False,
        target: Optional[str] = None,
        sysroot: Optional[str] = None,
        output: Optional[str] = None,
        features: Optional[str] = None
    ) -> Path:
        """Axiom projesini derleyerek hedef ikili dosyayı (target/) üretir."""
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"axiom.toml bulunamadı: {self.manifest_path}")

        # Kilit dosyasını kontrol et ve gerekirse oluştur
        if not self.lock_path.exists():
            self.install()
        else:
            lock = LockFile.from_file(self.lock_path)
            ok, msg = lock.verify(self.root_dir)
            if not ok:
                print(f"{CLR_YELLOW}Uyarı:{CLR_RESET} {msg}. Yeniden yükleniyor...")
                self.install()

        manifest = Manifest.from_file(self.manifest_path)
        entry_file = (self.root_dir / manifest.entry).resolve()
        if not entry_file.exists():
            # src/main.ax veya src/lib.ax fallback
            for alt in [self.root_dir / "src" / "main.ax", self.root_dir / "src" / "lib.ax"]:
                if alt.exists():
                    entry_file = alt
                    break

        if not entry_file.exists():
            raise FileNotFoundError(f"Paket giriş dosyası bulunamadı: {entry_file}")

        mode = "release" if release else "debug"
        target_dir = self.root_dir / "target" / mode
        target_dir.mkdir(parents=True, exist_ok=True)

        out_bin = Path(output).resolve() if output else target_dir / manifest.name

        # Axiom CLI build çağrısı yap
        import types
        from axiom.cli import cmd_build
        args = types.SimpleNamespace(
            file=str(entry_file),
            output=str(out_bin),
            opt="3" if release else "0",
            backend="c",
            asan=False,
            ubsan=False,
            debug=debug or (not release),
            target=target,
            sysroot=sysroot,
            features=features
        )

        cmd_build(args)
        return out_bin

    def run(self, extra_args: Optional[List[str]] = None, debug: bool = False, features: Optional[str] = None) -> int:
        """Projeyi derler ve çalıştırır."""
        out_bin = self.build(release=False, debug=debug, features=features)
        cmd = [str(out_bin)] + (extra_args or [])
        res = subprocess.run(cmd)
        return res.returncode

    def test(self, extra_args: Optional[List[str]] = None, features: Optional[str] = None) -> int:
        """tests/ dizinindeki .ax test dosyalarını çalıştırır."""
        tests_dir = self.root_dir / "tests"
        if not tests_dir.exists():
            print(f"{CLR_YELLOW}Uyarı:{CLR_RESET} '{tests_dir}' bulunamadı, çalıştırılacak test yok.")
            return 0

        test_files = sorted(list(set(tests_dir.glob("*.ax"))))
        if not test_files:
            print(f"{CLR_YELLOW}Uyarı:{CLR_RESET} '{tests_dir}' altında .ax test dosyası bulunamadı.")
            return 0

        print(f"{CLR_CYAN}=== Axiom Paket Test Koşucusu ==={CLR_RESET}")
        total = len(test_files)
        passed = 0

        axiom_root = str(Path(__file__).resolve().parent.parent)
        env = dict(os.environ)
        current_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{axiom_root}:{current_pythonpath}" if current_pythonpath else axiom_root

        for tf in test_files:
            print(f"Koşuluyor: {tf.name} ... ", end="", flush=True)
            cmd_run_args = [sys.executable, "-m", "axiom.cli", "run", str(tf)]
            if features:
                cmd_run_args.extend(["--features", features])
            res = subprocess.run(cmd_run_args, capture_output=True, text=True, env=env)
            if res.returncode == 0:
                print(f"{CLR_GREEN}BAŞARILI{CLR_RESET}")
                passed += 1
            else:
                print(f"{CLR_RED}BAŞARISIZ{CLR_RESET}\n{res.stderr}")

        print(f"{CLR_BOLD}Sonuç:{CLR_RESET} {passed}/{total} test başarılı.")
        return 0 if passed == total else 1


def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(
        prog="axpm",
        description=f"{CLR_BOLD}axpm (Axiom Package Manager){CLR_RESET} - Deterministik Axiom Paket ve Bağımlılık Yöneticisi"
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Yeni Axiom paketi iskeleti oluşturur")
    p_init.add_argument("path", nargs="?", default=".", help="Proje dizini (varsayılan: aktif dizin)")
    p_init.add_argument("--name", help="Paket adı")
    p_init.add_argument("--lib", action="store_true", help="Kütüphane paketi (lib.ax) oluşturur")

    # add
    p_add = subparsers.add_parser("add", help="axiom.toml dosyasına yeni bir bağımlılık ekler")
    p_add.add_argument("dependency", help="Eklenecek bağımlılık adı")
    p_add.add_argument("--path", help="Yerel bağımlılık dosya yolu")
    p_add.add_argument("--git", help="Git depo URL adresi")
    p_add.add_argument("--rev", help="Git revizyonu (branch, tag veya commit)")
    p_add.add_argument("--version", help="Paket sürümü")

    # install
    p_install = subparsers.add_parser("install", help="Bağımlılıkları çözümler ve axiom.lock dosyasını üretir")

    # verify
    subparsers.add_parser("verify", help="axiom.lock sağlama toplamlarını doğrular")

    # tree
    subparsers.add_parser("tree", help="Bağımlılık ağacını gösterir")

    # remove
    p_remove = subparsers.add_parser("remove", help="Bir bağımlılığı kaldırır")
    p_remove.add_argument("dependency", help="Kaldırılacak bağımlılık adı")
    p_remove.add_argument("--purge", action="store_true", help="İndirilmiş Git bağımlılığı klonunu da sil")

    # search
    p_search = subparsers.add_parser("search", help="Registry'de paket arar")
    p_search.add_argument("query", nargs="?", default="", help="Arama metni")

    # pack
    p_pack = subparsers.add_parser(
        "pack", help="Temiz Git commit'inden deterministik ve imzalı registry paketi hazırlar"
    )
    p_pack.add_argument(
        "--signing-key", required=True,
        help="Ed25519 özel anahtar PEM dosyası (AXIOM_REGISTRY_SIGNING_PASSPHRASE desteklenir)",
    )
    p_pack.add_argument(
        "--output", type=Path, help="Registry kök çıktı dizini (varsayılan: dist/registry)",
    )

    p_registry = subparsers.add_parser(
        "registry", help="Yerel registry artefact'larını doğrula ve hazırla (ağ kullanmaz)"
    )
    registry_commands = p_registry.add_subparsers(dest="registry_cmd", required=True)
    p_registry_assemble = registry_commands.add_parser(
        "assemble", help="İmzalı axpm pack çıktılarını statik Registry v1 dizinine dönüştürür"
    )
    p_registry_assemble.add_argument(
        "--from", dest="pack_output", type=Path, required=True,
        help="axpm pack komutunun çıktı kökü",
    )
    p_registry_assemble.add_argument(
        "--output", type=Path, required=True,
        help="Oluşturulacak, mevcut değilse daha iyi olan yeni/boş registry dizini",
    )
    p_registry_assemble.add_argument(
        "--public-key", type=Path, required=True,
        help="Tarball imzalarını doğrulamak için güvenilen Ed25519 PEM açık anahtarı",
    )

    # update
    p_update = subparsers.add_parser("update", help="Git bağımlılıklarını yeniden çeker ve kilidi günceller")
    p_update.add_argument("dependency", nargs="?", help="Yalnızca bu bağımlılığı güncelle")

    # build
    p_build = subparsers.add_parser("build", help="Paketi target/ dizinine derler")
    p_build.add_argument("--release", action="store_true", help="Release optimizasyonları ile derle (-O3)")
    p_build.add_argument("-g", "--debug", action="store_true", help="DWARF hata ayıklama sembolleri ile derle")
    p_build.add_argument("--target", help="Çapraz derleme hedef mimarisi (örn. x86_64-linux-gnu, aarch64-linux-gnu, wasm32-wasi)")
    p_build.add_argument("--sysroot", help="Çapraz derleme hedef sysroot dizini")
    p_build.add_argument("-o", "--output", help="Çıktı ikili dosya yolu")
    p_build.add_argument("--features", help="Etkinleştirilecek özellikler (örn. 'offensive')")

    # run
    p_run = subparsers.add_parser("run", help="Paketi derleyip çalıştırır")
    p_run.add_argument("-g", "--debug", action="store_true", help="DWARF hata ayıklama sembolleri ile çalıştır")
    p_run.add_argument("--features", help="Etkinleştirilecek özellikler (örn. 'offensive')")
    p_run.add_argument("extra_args", nargs="*", help="Program argümanları")

    # test
    p_test = subparsers.add_parser("test", help="Paket testlerini çalıştırır")
    p_test.add_argument("--features", help="Etkinleştirilecek özellikler (örn. 'offensive')")
    p_test.add_argument("extra_args", nargs="*", help="Ek test argümanları")

    args = parser.parse_args(argv)
    pm = PackageManager()

    try:
        if args.cmd == "init":
            target_p = Path(args.path)
            res = pm.init_package(target_dir=target_p, name=args.name, is_lib=args.lib)
            print(f"{CLR_GREEN}✓ Başarılı:{CLR_RESET} Yeni Axiom paketi oluşturuldu: {res}")
        elif args.cmd == "add":
            pm.add_dependency(args.dependency, path=args.path, git=args.git, version=args.version, rev=getattr(args, "rev", None))
        elif args.cmd == "install":
            pm.install()
        elif args.cmd == "verify":
            if not pm.verify():
                sys.exit(1)
        elif args.cmd == "tree":
            pm.tree()
        elif args.cmd == "search":
            pm.search(getattr(args, "query", ""))
        elif args.cmd == "pack":
            result = pm.pack(Path(args.signing_key), output_dir=args.output)
            print(f"{CLR_GREEN}✓ İmzalı registry paketi hazırlandı:{CLR_RESET} {result}")
        elif args.cmd == "registry" and args.registry_cmd == "assemble":
            result = pm.assemble_registry(args.pack_output, args.output, args.public_key)
            print(f"{CLR_GREEN}✓ Doğrulanmış statik registry hazırlandı:{CLR_RESET} {result}")
            print("Bu komut hiçbir yere yükleme yapmadı; index.json ayrıca imzalanmaz.")
        elif args.cmd == "update":
            pm.update(getattr(args, "dependency", None))
        elif args.cmd == "remove":
            pm.remove_dependency(args.dependency, purge=getattr(args, "purge", False))
        elif args.cmd == "build":
            out = pm.build(
                release=args.release,
                debug=args.debug,
                target=args.target,
                sysroot=args.sysroot,
                output=args.output,
                features=getattr(args, "features", None)
            )
            print(f"{CLR_GREEN}✓ Paket başarıyla derlendi:{CLR_RESET} {out}")
        elif args.cmd == "run":
            code = pm.run(extra_args=args.extra_args, debug=args.debug, features=getattr(args, "features", None))
            sys.exit(code)
        elif args.cmd == "test":
            code = pm.test(extra_args=args.extra_args, features=getattr(args, "features", None))
            sys.exit(code)
    except Exception as e:
        print(f"{CLR_RED}Hata:{CLR_RESET} {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
