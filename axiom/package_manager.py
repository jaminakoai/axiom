"""
Axiom Programming Language (λx) - Package Manager (axpm / axiom pkg)
Deterministik bağımlılık yönetimi, axiom.toml manifestosu, axiom.lock kilit mekanizması.
"""

import os
import re
import sys
import json
import hashlib
import shutil
import subprocess
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from axiom.registry import (
    RegistryConfig, RegistryClient, resolve_tree, SemverError,
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
                src_dir, cache_hit = client.download(name, version, info["sha256"], info["sig"])
                if not target_dir.exists() or not any(target_dir.iterdir()):
                    target_dir.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(src_dir, target_dir)
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
            lock.packages = [p for p in lock.packages if p.get("name") != dep_name]
            lock.save(self.lock_path)

        if purge and isinstance(spec, dict) and "git" in spec:
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
    p_remove.add_argument("--purge", action="store_true", help="İndirilmiş git bağımlılığını da sil")

    # search
    p_search = subparsers.add_parser("search", help="Registry'de paket arar")
    p_search.add_argument("query", nargs="?", default="", help="Arama metni")

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
