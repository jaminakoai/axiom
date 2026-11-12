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
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_VERSION = 1
DEFAULT_REGISTRY = "https://registry.axiom-lang.org"

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
                 cache_dir: Optional[Path] = None):
        self.url = url.rstrip("/")
        self.public_key = public_key
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
        allow = (os.environ.get("AXIOM_ALLOW_UNSIGNED") == "1"
                 or bool(reg.get("allow_unsigned", False)))
        return cls(url=url, public_key=key, allow_unsigned=allow)


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

class RegistryIndex:
    def __init__(self, packages: Dict[str, List[Dict[str, Any]]], base_url: str):
        self.packages = packages
        self.base_url = base_url

    @classmethod
    def from_json(cls, data: Dict[str, Any], base_url: str) -> "RegistryIndex":
        if data.get("schema", SCHEMA_VERSION) != SCHEMA_VERSION:
            raise ValueError(f"desteklenmeyen registry şeması: {data.get('schema')}")
        pkgs = data.get("packages") or {}
        if not isinstance(pkgs, dict):
            raise ValueError("index.json: 'packages' nesne olmalı")
        return cls(pkgs, base_url)

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
    return sha256_bytes(data) == (expected or "").lower()


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


# ---------------------------------------------------------------------------
# İndirme
# ---------------------------------------------------------------------------

def _fetch(url: str, timeout: int = 30) -> bytes:
    if url.startswith("file://"):
        return Path(urllib.parse.urlparse(url).path).read_bytes()
    if url.startswith("/"):
        return Path(url).read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": "axpm/0.5"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_index(config: RegistryConfig) -> RegistryIndex:
    url = f"{config.url}/index.json"
    try:
        raw = _fetch(url, config.timeout)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"registry index alınamadı ({url}): HTTP {e.code}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"registry'ye ulaşılamadı ({url}): {e.reason}")
    except OSError as e:
        raise RuntimeError(f"registry index okunamadı ({url}): {e}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise RuntimeError(f"index.json geçersiz JSON: {e}")
    return RegistryIndex.from_json(data, config.url)


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
        return self.config.cache_dir / "sha256" / sha

    def download(self, name: str, version: str, expected_sha: str,
                 sig_b64: str) -> Tuple[Path, bool]:
        """
        Paketi indirir, sha256 + imza doğrular, içerik-adresli cache'e açar.
        Dönüş: (açılmış_dizin, cache_iskaca_vurdu_mu)
        """
        cache_dir = self.cache_path_for(expected_sha)
        stored_tarball = cache_dir / "pkg.tar.gz"

        if cache_dir.exists() and stored_tarball.exists():
            # Cache isabeti: içeriği YİNE doğrula. Aksi halde bozulmuş/ele
            # geçirilmiş cache doğrulamayı atlatırdı.
            cached = stored_tarball.read_bytes()
            if verify_sha256(cached, expected_sha):
                return cache_dir, True
            # bozuk cache: temizle ve yeniden indir
            shutil.rmtree(cache_dir, ignore_errors=True)

        url = f"{self.config.url}/{name}/{version}.tar.gz"
        try:
            raw = _fetch(url, self.config.timeout)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"paket indirilemedi ({url}): HTTP {e.code}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"paket indirilemedi ({url}): {e.reason}")

        if not verify_sha256(raw, expected_sha):
            raise RuntimeError(
                f"'{name}@{version}' sha256 uyuşmuyor.\n"
                f"  beklenen: {expected_sha}\n  gerçek  : {sha256_bytes(raw)}"
            )

        if sig_b64:
            ok, why = verify_signature(raw, sig_b64, self.config.public_key)
            if not ok:
                raise RuntimeError(f"'{name}@{version}' imza doğrulanamadı: {why}")
        else:
            if not self.config.allow_unsigned:
                raise RuntimeError(
                    f"'{name}@{version}' imzalanmamış ve allow_unsigned kapalı. "
                    f"Registry'yi düzeltin veya AXIOM_ALLOW_UNSIGNED=1 kullanın."
                )

        # Açma (atomik: geçici dizin -> rename)
        cache_dir.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix="axpm-", dir=str(cache_dir.parent)))
        try:
            # Tarball'i cache'te sakla: sonraki isabetlerde yeniden doğrulanır.
            (tmp / "pkg.tar.gz").write_bytes(raw)
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
                for member in tf.getmembers():
                    target = (tmp / member.name).resolve()
                    if not str(target).startswith(str(tmp.resolve())):
                        raise RuntimeError(f"güvensiz arşiv yolu: {member.name}")
                tf.extractall(tmp)
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
