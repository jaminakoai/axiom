"""
Axiom - Registry v1 (P2-01)

Kapsam:
  - semver aralıkları (^ ~ = >= <= > < *, kısmi sürümler)
  - transitive çözümleme, yanked reddi, döngü tespiti, çakışma
  - indirme + sha256 doğrulama + ed25519 imza doğrulama
  - cache isabetinde YENİDEN doğrulama (bozuk cache atlatamaz)
  - unsigned politika (allow_unsigned)
  - axpm install uçtan uca (gerçek file:// registry)
"""
import base64
import gzip
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXPM = ROOT / "bin" / "axpm"

sys_path_added = str(ROOT)
import sys
if sys_path_added not in sys.path:
    sys.path.insert(0, sys_path_added)

from axiom.registry import (  # noqa: E402
    RegistryConfig, RegistryClient, RegistryIndex, resolve_tree,
    version_matches, SemverError, sha256_bytes,
)
from axiom import registry as registry_module  # noqa: E402
from axiom.package_manager import LockFile  # noqa: E402


# ---------------------------------------------------------------------------
# Semver
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("version,constraint,expected", [
    ("1.0.0", "*", True),
    ("2.3.4", "1", False),
    ("1.9.9", "1", True),
    ("1.2.9", "1.2", True),
    ("1.3.0", "1.2", False),
    ("1.2.3", "=1.2.3", True),
    ("1.2.4", "=1.2.3", False),
    ("1.5.0", ">=1.2", True),
    ("1.1.0", ">=1.2", False),
    ("1.2.0", "<=1.2", True),
    ("1.2.9", "<=1.2", True),
    ("1.3.0", "<=1.2", False),
    ("1.2.3", "~1.2", True),
    ("1.3.0", "~1.2", False),
    ("1.9.0", "^1.0", True),
    ("2.0.0", "^1.0", False),
    ("0.3.0", "^0.3", True),
    ("0.4.0", "^0.3", False),
    ("0.0.5", "^0.0.5", True),
    ("1.5.0", ">=1.0,<2.0", True),
    ("2.5.0", ">=1.0,<2.0", False),
])
def test_semver_ranges(version, constraint, expected):
    assert version_matches(version, constraint) is expected


def test_registry_config_keeps_existing_positional_arguments_compatible(tmp_path):
    config = RegistryConfig("file:///registry", "package-key", True, 12, tmp_path)
    assert config.public_key == "package-key"
    assert config.allow_unsigned is True
    assert config.timeout == 12
    assert config.cache_dir == tmp_path


# ---------------------------------------------------------------------------
# Çözümleme
# ---------------------------------------------------------------------------

def _idx(packages):
    return RegistryIndex(packages, "file:///test")


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ([], "kök değeri nesne"),
        ({"schema": True, "packages": {}}, "şeması"),
        ({"schema": 1, "packages": {"bad/name/shape": []}}, "paket adı"),
        ({"schema": 1, "packages": {"lib-a": None}}, "sürüm listesi"),
        ({"schema": 1, "packages": {"lib-a": ["1.0.0"]}}, "nesne olmalı"),
        ({"schema": 1, "packages": {"lib-a": [{"version": "not-semver"}]}}, "version"),
        ({"schema": 1, "packages": {"lib-a": [{"version": "9" * 5000 + ".0.0"}]}}, "version"),
        (
            {"schema": 1, "packages": {"lib-a": [{
                "version": "1.0.0", "sha256": "not-a-hash",
            }]}},
            "sha256",
        ),
        (
            {"schema": 1, "packages": {"lib-a": [{
                "version": "1.0.0", "sha256": "a" * 64, "sig": 42,
            }]}},
            "sig metin",
        ),
        (
            {"schema": 1, "packages": {"lib-a": [{
                "version": "1.0.0", "sha256": "a" * 64, "dependencies": [],
            }]}},
            "dependencies nesne",
        ),
        (
            {"schema": 1, "packages": {"lib-a": [{
                "version": "1.0.0", "sha256": "a" * 64, "yanked": "false",
            }]}},
            "yanked boolean",
        ),
    ],
)
def test_registry_index_rejects_malformed_schema(data, message):
    with pytest.raises(ValueError, match=message):
        RegistryIndex.from_json(data, "file:///test")


def test_resolve_picks_highest_matching():
    idx = _idx({"a": [
        {"version": "1.0.0", "sha256": "s1", "dependencies": {}},
        {"version": "1.4.0", "sha256": "s2", "dependencies": {}},
        {"version": "2.0.0", "sha256": "s3", "dependencies": {}},
    ]})
    tree = resolve_tree(idx, {"a": "^1"})
    assert tree["a"]["version"] == "1.4.0"


def test_resolve_skips_yanked():
    idx = _idx({"a": [
        {"version": "1.0.0", "sha256": "s1", "dependencies": {}},
        {"version": "1.4.0", "sha256": "s2", "dependencies": {}, "yanked": True},
    ]})
    assert resolve_tree(idx, {"a": "^1"})["a"]["version"] == "1.0.0"


def test_resolve_transitive():
    idx = _idx({
        "app-lib": [{"version": "1.0.0", "sha256": "a", "dependencies": {"json-lib": "^1.0"}}],
        "json-lib": [
            {"version": "1.0.0", "sha256": "b", "dependencies": {}},
            {"version": "1.2.0", "sha256": "c", "dependencies": {}},
        ],
    })
    tree = resolve_tree(idx, {"app-lib": "*"})
    assert set(tree) == {"app-lib", "json-lib"}
    assert tree["json-lib"]["version"] == "1.2.0"


def test_resolve_detects_cycle():
    idx = _idx({
        "a": [{"version": "1.0.0", "sha256": "a", "dependencies": {"b": "*"}}],
        "b": [{"version": "1.0.0", "sha256": "b", "dependencies": {"a": "*"}}],
    })
    with pytest.raises(RuntimeError, match="döngüsel"):
        resolve_tree(idx, {"a": "*"})


def test_resolve_missing_package_reports_available():
    idx = _idx({"a": [{"version": "1.0.0", "sha256": "x", "dependencies": {}}]})
    with pytest.raises(RuntimeError, match="uygun sürüm yok"):
        resolve_tree(idx, {"a": "^9"})


def test_resolve_unknown_package():
    idx = _idx({})
    with pytest.raises(RuntimeError, match="registry'de paket yok"):
        resolve_tree(idx, {"yok": "*"})


# ---------------------------------------------------------------------------
# Yardımcı: sahte registry + imzalı paketler
# ---------------------------------------------------------------------------

def _have_openssl() -> bool:
    return shutil.which("openssl") is not None


def test_fetch_reads_file_uri_with_escaped_spaces(tmp_path):
    source = tmp_path / "registry files" / "index.json"
    source.parent.mkdir()
    source.write_text('{"schema":1}', encoding="utf-8")

    uri = source.as_uri()
    assert registry_module._fetch(uri) == b'{"schema":1}'
    assert registry_module._fetch(uri.replace("file://", "FILE://", 1)) == b'{"schema":1}'


def test_fetch_stops_at_configured_byte_limit(tmp_path):
    source = tmp_path / "oversized-index.json"
    source.write_bytes(b"123456")
    with pytest.raises(RuntimeError, match="5 bayt sınırını aşıyor"):
        registry_module._fetch(source.as_uri(), max_bytes=5)


def test_fetch_rejects_remote_file_uri_host():
    with pytest.raises(ValueError, match="uzak bir host"):
        registry_module._fetch("file://example.invalid/index.json")


def test_fetch_index_reports_invalid_file_uri_as_registry_error():
    config = RegistryConfig(url="file://example.invalid/registry")

    with pytest.raises(RuntimeError, match="registry URL geçersiz"):
        registry_module.fetch_index(config)



def _isolated_env(tmp_path):
    """axpm alt-süreçleri için İZOLE ortam.

    Registry önbelleği varsayılan olarak `~/.axiom/cache` altına yazar.
    Sandbox/CI ortamlarında ev dizini salt-okunur olabilir; ayrıca testler
    birbirinin önbelleğini görmemeli. `AXIOM_CACHE_DIR` ile her test kendi
    geçici dizinine yazar.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["AXIOM_CACHE_DIR"] = str(tmp_path / "_axiom_cache")
    # Gerçek kullanıcı ayarları sızmasın
    env.pop("AXIOM_REGISTRY", None)
    env.pop("AXIOM_REGISTRY_KEY", None)
    env.pop("AXIOM_REGISTRY_INDEX_KEY", None)
    env.pop("AXIOM_ALLOW_UNSIGNED", None)
    return env

def _make_registry(base: Path, packages, sign: bool = True, tamper: bool = False):
    """
    packages: {"ad": [{"version":..., "deps": {...}}, ...]}
    Dönüş: (registry_dir, public_key_pem)
    """
    base.mkdir(parents=True, exist_ok=True)
    key = base / "key.pem"
    pub = base / "pub.pem"
    if sign:
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(key)],
                       check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(key), "-pubout", "-out", str(pub)],
                       check=True, capture_output=True)
    public_pem = pub.read_text() if sign else ""

    index = {"schema": 1, "packages": {}}
    for name, versions in packages.items():
        (base / name).mkdir(parents=True, exist_ok=True)
        index["packages"][name] = []
        for v in versions:
            ver = v["version"]
            with tempfile.TemporaryDirectory() as td:
                d = Path(td)
                (d / "src").mkdir()
                (d / "axiom.toml").write_text(
                    f'[package]\nname = "{name}"\nversion = "{ver}"\n\n[dependencies]\n'
                    + "".join(f'{k} = "{c}"\n' for k, c in (v.get("deps") or {}).items()),
                    encoding="utf-8",
                )
                source = v.get(
                    "source",
                    f"fn {name.replace('-', '_')}_v() -> int {{ return 1 }}\n",
                )
                (d / "src" / "lib.ax").write_text(source, encoding="utf-8")
                tarball = base / name / f"{ver}.tar.gz"
                with tarfile.open(tarball, "w:gz") as tf:
                    tf.add(d, arcname=".")
            # sha256 ve imza ORİJİNAL baytlar üzerinden hesaplanır
            entry = {
                "version": ver,
                "sha256": sha256_bytes(tarball.read_bytes()),
                "dependencies": dict(v.get("deps") or {}),
            }
            if sign:
                sig_path = base / name / f"{ver}.sig"
                subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", str(key),
                                "-rawin", "-in", str(tarball), "-out", str(sig_path)],
                               check=True, capture_output=True)
                entry["sig"] = base64.b64encode(sig_path.read_bytes()).decode()
            if tamper:
                # imzalandıktan SONRA boz: sha256 artık uyuşmaz
                tarball.write_bytes(tarball.read_bytes() + b"x")
            index["packages"][name].append(entry)
            if v.get("yanked"):
                index["packages"][name][-1]["yanked"] = True
    (base / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return base, public_pem


def _write_signed_index(registry: Path, index, signing_key: Path):
    raw = (json.dumps(index, indent=2, sort_keys=True) + "\n").encode("utf-8")
    index_path = registry / "index.json"
    index_path.write_bytes(raw)
    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "index.json"
        signature = Path(temp_dir) / "index.sig"
        source.write_bytes(raw)
        subprocess.run(
            ["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(signing_key),
             "-in", str(source), "-out", str(signature)],
            check=True, capture_output=True,
        )
        (registry / "index.json.sig").write_bytes(base64.b64encode(signature.read_bytes()) + b"\n")
    return raw


def _new_index_keypair(directory: Path):
    private_key = directory / "index-private.pem"
    public_key = directory / "index-public.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(private_key)],
                   check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
                   check=True, capture_output=True)
    return private_key, public_key.read_text(encoding="utf-8")


def _signed_index(sequence, packages=None, expires=None):
    if expires is None:
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat().replace("+00:00", "Z")
    return {"schema": 2, "sequence": sequence, "expires": expires,
            "packages": packages or {}}


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_signed_index_verifies_and_persists_accepted_sequence(tmp_path):
    registry = tmp_path / "signed-registry"
    registry.mkdir()
    key, public_key = _new_index_keypair(tmp_path)
    raw = _write_signed_index(registry, _signed_index(1), key)
    config = RegistryConfig(url=registry.as_uri(), index_public_key=public_key,
                            cache_dir=tmp_path / "cache")

    index = registry_module.fetch_index(config)
    assert index.schema == 2 and index.sequence == 1
    assert index.raw_sha256 == hashlib.sha256(raw).hexdigest()
    state_files = list((config.cache_dir / "index-state").glob("*.json"))
    assert len(state_files) == 1
    assert json.loads(state_files[0].read_text(encoding="utf-8"))["sequence"] == 1


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_signed_index_rejects_tampering_and_missing_trust_key(tmp_path):
    registry = tmp_path / "signed-registry"
    registry.mkdir()
    key, public_key = _new_index_keypair(tmp_path)
    _write_signed_index(registry, _signed_index(1), key)
    index_path = registry / "index.json"
    index_path.write_bytes(index_path.read_bytes() + b" ")

    with pytest.raises(RuntimeError, match="imzası doğrulanamadı"):
        registry_module.fetch_index(RegistryConfig(
            url=registry.as_uri(), index_public_key=public_key, cache_dir=tmp_path / "cache",
        ))
    with pytest.raises(RuntimeError, match="AXIOM_REGISTRY_INDEX_KEY gerekli"):
        registry_module.fetch_index(RegistryConfig(url=registry.as_uri(),
                                                   cache_dir=tmp_path / "other-cache"))


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_signed_index_rejects_rollback_and_same_sequence_equivocation(tmp_path):
    registry = tmp_path / "signed-registry"
    registry.mkdir()
    key, public_key = _new_index_keypair(tmp_path)
    config = RegistryConfig(url=registry.as_uri(), index_public_key=public_key,
                            cache_dir=tmp_path / "cache")
    _write_signed_index(registry, _signed_index(2), key)
    registry_module.fetch_index(config)

    _write_signed_index(registry, _signed_index(1), key)
    with pytest.raises(RuntimeError, match="rollback reddedildi"):
        registry_module.fetch_index(config)

    _write_signed_index(registry, _signed_index(2, {"new-package": []}), key)
    with pytest.raises(RuntimeError, match="aynı sequence"):
        registry_module.fetch_index(config)


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_signed_index_rejects_expired_and_excessively_long_expiration(tmp_path):
    registry = tmp_path / "signed-registry"
    registry.mkdir()
    key, public_key = _new_index_keypair(tmp_path)
    config = RegistryConfig(url=registry.as_uri(), index_public_key=public_key,
                            cache_dir=tmp_path / "cache")
    expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    _write_signed_index(registry, _signed_index(1, expires=expired), key)
    with pytest.raises(RuntimeError, match="süresi dolmuş"):
        registry_module.fetch_index(config)

    too_far = (datetime.now(timezone.utc) + timedelta(days=91)).isoformat().replace("+00:00", "Z")
    _write_signed_index(registry, _signed_index(1, expires=too_far), key)
    with pytest.raises(RuntimeError, match="90 günden"):
        registry_module.fetch_index(config)


def test_registry_index_state_lock_serializes_processes(tmp_path):
    lock_path = tmp_path / "registry-index.lock"
    started_path = tmp_path / "child-started"
    acquired_path = tmp_path / "child-acquired"
    child_script = "\n".join((
        "from pathlib import Path",
        "import sys",
        "from axiom.registry import _exclusive_registry_state_lock",
        "Path(sys.argv[2]).write_text('started', encoding='utf-8')",
        "with _exclusive_registry_state_lock(Path(sys.argv[1])):",
        "    Path(sys.argv[3]).write_text('acquired', encoding='utf-8')",
    ))
    child = None
    try:
        with registry_module._exclusive_registry_state_lock(lock_path):
            child = subprocess.Popen(
                [sys.executable, "-c", child_script, str(lock_path),
                 str(started_path), str(acquired_path)],
                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            deadline = time.monotonic() + 5
            while not started_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert started_path.is_file(), "alt süreç kilit denemesine başlayamadı"
            time.sleep(0.1)
            assert not acquired_path.exists(), "alt süreç kilit tutulurken içeri girdi"
        stdout, stderr = child.communicate(timeout=5)
        assert child.returncode == 0, stdout + stderr
        assert acquired_path.read_text(encoding="utf-8") == "acquired"
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=5)


# ---------------------------------------------------------------------------
# İndirme + doğrulama
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_download_verifies_and_caches(tmp_path):
    reg, pub = _make_registry(tmp_path / "reg", {"lib-a": [{"version": "1.0.0"}]})
    cache = tmp_path / "cache"
    cfg = RegistryConfig(url=f"file://{reg}", public_key=pub, cache_dir=cache)
    client = RegistryClient(cfg)
    entry = client.index.versions("lib-a")[0]

    d1, hit1 = client.download("lib-a", "1.0.0", entry["sha256"], entry["sig"])
    assert hit1 is False
    assert (d1 / "axiom.toml").exists()

    d2, hit2 = client.download("lib-a", "1.0.0", entry["sha256"], entry["sig"])
    assert hit2 is True and d2 == d1


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
@pytest.mark.parametrize(
    ("indexed_name", "indexed_version", "indexed_dependencies", "expected_error"),
    [
        ("alias", "9.9.9", {}, "paket adı imzalı manifestoyla uyuşmuyor"),
        ("real-package", "9.9.9", {}, "sürümü imzalı manifestoyla uyuşmuyor"),
        (
            "real-package", "1.0.0", {"injected-dep": "^1.0"},
            "bağımlılıkları imzalı manifestoyla uyuşmuyor",
        ),
    ],
)
def test_download_rejects_unsigned_index_metadata_mismatch(
    tmp_path, indexed_name, indexed_version, indexed_dependencies, expected_error,
):
    """A valid signature must not let an unsigned index relabel package metadata."""
    registry, public_key = _make_registry(
        tmp_path / "registry", {"real-package": [{"version": "1.0.0"}]}
    )
    index_path = registry / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    original_entry = index["packages"]["real-package"][0]
    source = registry / "real-package" / "1.0.0.tar.gz"
    if indexed_name != "real-package" or indexed_version != "1.0.0":
        package_path = registry / indexed_name
        package_path.mkdir(exist_ok=True)
        shutil.copyfile(source, package_path / f"{indexed_version}.tar.gz")
        index["packages"].pop("real-package")
        original_entry["version"] = indexed_version
        index["packages"][indexed_name] = [original_entry]
    original_entry["dependencies"] = indexed_dependencies
    index_path.write_text(json.dumps(index), encoding="utf-8")

    client = RegistryClient(RegistryConfig(
        url=f"file://{registry}", public_key=public_key,
        cache_dir=tmp_path / "cache",
    ))
    with pytest.raises(RuntimeError, match=expected_error):
        client.download(
            indexed_name, indexed_version, original_entry["sha256"],
            original_entry["sig"], indexed_dependencies,
        )


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_cache_hit_rejects_index_relabeling(tmp_path):
    registry, public_key = _make_registry(
        tmp_path / "registry", {"real-package": [{"version": "1.0.0"}]}
    )
    cache = tmp_path / "cache"
    client = RegistryClient(RegistryConfig(
        url=f"file://{registry}", public_key=public_key, cache_dir=cache,
    ))
    entry = client.index.versions("real-package")[0]
    client.download("real-package", "1.0.0", entry["sha256"], entry["sig"], {})

    index_path = registry / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    alias_entry = dict(index["packages"].pop("real-package")[0])
    (registry / "alias").mkdir()
    shutil.copyfile(
        registry / "real-package" / "1.0.0.tar.gz",
        registry / "alias" / "1.0.0.tar.gz",
    )
    index["packages"]["alias"] = [alias_entry]
    index_path.write_text(json.dumps(index), encoding="utf-8")
    changed_client = RegistryClient(RegistryConfig(
        url=f"file://{registry}", public_key=public_key, cache_dir=cache,
    ))

    with pytest.raises(RuntimeError, match="paket adı imzalı manifestoyla uyuşmuyor"):
        changed_client.download("alias", "1.0.0", entry["sha256"], entry["sig"])


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_cache_hit_rejects_dependency_metadata_substitution(tmp_path):
    registry, public_key = _make_registry(
        tmp_path / "registry", {"lib-a": [{"version": "1.0.0"}]}
    )
    client = RegistryClient(RegistryConfig(
        url=f"file://{registry}", public_key=public_key,
        cache_dir=tmp_path / "cache",
    ))
    entry = client.index.versions("lib-a")[0]
    client.download("lib-a", "1.0.0", entry["sha256"], entry["sig"], {})

    index_path = registry / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["packages"]["lib-a"][0]["dependencies"] = {"injected-dep": "^1.0"}
    index_path.write_text(json.dumps(index), encoding="utf-8")
    changed_client = RegistryClient(RegistryConfig(
        url=f"file://{registry}", public_key=public_key,
        cache_dir=tmp_path / "cache",
    ))

    with pytest.raises(RuntimeError, match="bağımlılıkları imzalı manifestoyla uyuşmuyor"):
        changed_client.download("lib-a", "1.0.0", entry["sha256"], entry["sig"])


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_download_rejects_tampered_tarball(tmp_path):
    reg, pub = _make_registry(tmp_path / "reg", {"lib-a": [{"version": "1.0.0"}]},
                              tamper=True)
    cfg = RegistryConfig(url=f"file://{reg}", public_key=pub, cache_dir=tmp_path / "c")
    client = RegistryClient(cfg)
    entry = client.index.versions("lib-a")[0]
    with pytest.raises(RuntimeError, match="sha256 uyuşmuyor"):
        client.download("lib-a", "1.0.0", entry["sha256"], entry["sig"])


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_download_heals_corrupted_cache(tmp_path):
    """Cache'teki tarball bozulursa doğrulanır, atılıp yeniden indirilir.

    Doğrulama atlanmaz; bozuk cache sessizce kullanılmaz.
    """
    reg, pub = _make_registry(tmp_path / "reg", {"lib-a": [{"version": "1.0.0"}]})
    cfg = RegistryConfig(url=f"file://{reg}", public_key=pub, cache_dir=tmp_path / "c")
    client = RegistryClient(cfg)
    entry = client.index.versions("lib-a")[0]
    d, _ = client.download("lib-a", "1.0.0", entry["sha256"], entry["sig"])

    (d / "pkg.tar.gz").write_bytes(b"bozuk")
    d2, hit = client.download("lib-a", "1.0.0", entry["sha256"], entry["sig"])
    assert hit is False, "bozuk cache isabet sayilmamali"
    assert sha256_bytes((d2 / "pkg.tar.gz").read_bytes()) == entry["sha256"]
    assert (d2 / "axiom.toml").exists()


def test_cache_hit_preserves_cache_on_transient_tarball_read_error(tmp_path, monkeypatch):
    registry, raw = _make_untrusted_registry(tmp_path, [
        (tarfile.TarInfo("axiom.toml"),
         b'[package]\nname = "evil"\nversion = "1.0.0"\n\n[dependencies]\n'),
    ])
    client = RegistryClient(RegistryConfig(
        url=registry.as_uri(), allow_unsigned=True, cache_dir=tmp_path / "cache"
    ))
    sha = sha256_bytes(raw)
    client._index = RegistryIndex({"evil": [{
        "version": "1.0.0", "sha256": sha, "sig": "", "dependencies": {},
    }]}, registry.as_uri())
    cache_dir, cache_hit = client.download("evil", "1.0.0", sha, "", {})
    assert cache_hit is False
    stored_tarball = cache_dir / "pkg.tar.gz"
    original_open = Path.open

    def transient_tarball_read_error(path, mode="r", *args, **kwargs):
        if path == stored_tarball and mode == "rb":
            raise OSError("temporary storage read error")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", transient_tarball_read_error)
    with pytest.raises(OSError, match="temporary storage read error"):
        client.download("evil", "1.0.0", sha, "", {})
    assert cache_dir.is_dir()
    assert stored_tarball.is_file()


def test_cache_parity_bounds_modified_file_before_hashing(tmp_path, monkeypatch):
    registry, raw = _make_untrusted_registry(tmp_path, [
        (tarfile.TarInfo("axiom.toml"),
         b'[package]\nname = "evil"\nversion = "1.0.0"\n\n[dependencies]\n'),
        (tarfile.TarInfo("payload.bin"), b"small"),
    ])
    client = RegistryClient(RegistryConfig(
        url=registry.as_uri(), allow_unsigned=True, cache_dir=tmp_path / "cache"
    ))
    sha = sha256_bytes(raw)
    client._index = RegistryIndex({"evil": [{
        "version": "1.0.0", "sha256": sha, "sig": "", "dependencies": {},
    }]}, registry.as_uri())
    cache_dir, _ = client.download("evil", "1.0.0", sha, "", {})
    oversized_cached_file = cache_dir / "payload.bin"
    oversized_cached_file.write_bytes(b"x" * 1024)
    monkeypatch.setattr(registry_module, "_MAX_REGISTRY_ARCHIVE_BYTES", 128)
    original_open = Path.open

    def forbid_oversized_extra_hash(path, mode="r", *args, **kwargs):
        if path == oversized_cached_file and mode == "rb":
            raise AssertionError("oversized cache file was hashed before the byte cap")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", forbid_oversized_extra_hash)
    assert not registry_module._cache_matches_archive(raw, cache_dir)


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_download_heals_modified_extracted_cache(tmp_path):
    """İmzalı tarball ile eşleşmeyen açılmış cache kaynağı kullanılmamalı."""
    reg, pub = _make_registry(tmp_path / "reg", {"lib-a": [{"version": "1.0.0"}]})
    cfg = RegistryConfig(url=f"file://{reg}", public_key=pub, cache_dir=tmp_path / "c")
    client = RegistryClient(cfg)
    entry = client.index.versions("lib-a")[0]
    d, _ = client.download("lib-a", "1.0.0", entry["sha256"], entry["sig"])

    manifest = d / "axiom.toml"
    original = manifest.read_bytes()
    manifest.write_bytes(original + b"# tampered\\n")
    d2, hit = client.download("lib-a", "1.0.0", entry["sha256"], entry["sig"])

    assert hit is False
    assert (d2 / "axiom.toml").read_bytes() == original


def test_cache_mode_check_handles_windows_chmod_semantics(monkeypatch, tmp_path):
    """Windows st_mode does not retain POSIX 0644/0755 distinctions."""
    reg, pub = _make_registry(tmp_path / "reg", {"lib-a": [{"version": "1.0.0"}]})
    cfg = RegistryConfig(url=f"file://{reg}", public_key=pub, cache_dir=tmp_path / "c")
    client = RegistryClient(cfg)
    entry = client.index.versions("lib-a")[0]
    cache_dir, _ = client.download("lib-a", "1.0.0", entry["sha256"], entry["sig"])
    raw = (cache_dir / "pkg.tar.gz").read_bytes()

    original_stat = Path.stat

    def windows_stat(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if path.name == "lib.ax":
            values = list(result)
            values[0] = (values[0] & ~0o777) | 0o666
            return os.stat_result(values)
        return result

    monkeypatch.setattr(Path, "stat", windows_stat)
    monkeypatch.setattr(registry_module.os, "name", "nt")
    assert registry_module._cache_matches_archive(raw, cache_dir)


def test_download_cache_hit_is_portable_on_current_platform(tmp_path):
    """A real cache hit works with the host filesystem's chmod semantics."""
    archive_buffer = io.BytesIO()
    with tempfile.TemporaryDirectory(dir=tmp_path) as source_dir:
        manifest = Path(source_dir) / "axiom.toml"
        manifest.write_text('[package]\nname = "portable-cache-test"\nversion = "1.0.0"\n',
                            encoding="utf-8")
        with tarfile.open(fileobj=archive_buffer, mode="w:gz") as archive:
            archive.add(manifest, arcname="./axiom.toml")
    raw = archive_buffer.getvalue()
    sha = sha256_bytes(raw)
    client = RegistryClient(RegistryConfig(
        url="https://registry.example.invalid", allow_unsigned=True,
        cache_dir=tmp_path / "cache",
    ))
    client._index = RegistryIndex({"portable-cache-test": [{
        "version": "1.0.0", "sha256": sha, "sig": "", "dependencies": {},
    }]}, "https://registry.example.invalid")
    cache_dir = client.cache_path_for(sha)
    cache_dir.mkdir(parents=True)
    (cache_dir / "pkg.tar.gz").write_bytes(raw)
    registry_module._extract_package_archive(raw, cache_dir)

    resolved_dir, hit = client.download("portable-cache-test", "1.0.0", sha, "")

    assert hit is True
    assert (resolved_dir / "axiom.toml").exists()


def test_download_rejects_invalid_sha_before_using_cache_path(tmp_path):
    """Untrusted index SHA cannot traverse to and delete outside the cache."""
    victim = tmp_path / "victim"
    victim.mkdir()
    marker = victim / "pkg.tar.gz"
    marker.write_bytes(b"keep this file")
    client = RegistryClient(RegistryConfig(
        url="file:///unused", allow_unsigned=True, cache_dir=tmp_path / "cache"
    ))

    with pytest.raises(RuntimeError, match="SHA-256"):
        client.download("lib-a", "1.0.0", "../../victim", "")

    assert marker.read_bytes() == b"keep this file"


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_download_rejects_bad_signature(tmp_path):
    reg, pub = _make_registry(tmp_path / "reg", {"lib-a": [{"version": "1.0.0"}]})
    cfg = RegistryConfig(url=f"file://{reg}", public_key=pub, cache_dir=tmp_path / "c")
    client = RegistryClient(cfg)
    entry = client.index.versions("lib-a")[0]
    bad_sig = base64.b64encode(b"x" * 64).decode()
    with pytest.raises(RuntimeError, match="imza"):
        client.download("lib-a", "1.0.0", entry["sha256"], bad_sig)


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_download_rejects_unsigned_by_default(tmp_path):
    reg, pub = _make_registry(tmp_path / "reg", {"lib-a": [{"version": "1.0.0"}]},
                              sign=False)
    cfg = RegistryConfig(url=f"file://{reg}", public_key=pub, cache_dir=tmp_path / "c")
    client = RegistryClient(cfg)
    entry = client.index.versions("lib-a")[0]
    with pytest.raises(RuntimeError, match="imzalanmamış"):
        client.download("lib-a", "1.0.0", entry["sha256"], "")


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_cached_download_rejects_bad_signature(tmp_path):
    """Cache isabeti de o andaki registry imzası ve anahtarıyla doğrulanmalı."""
    reg, pub = _make_registry(tmp_path / "reg", {"lib-a": [{"version": "1.0.0"}]})
    cache = tmp_path / "cache"
    cfg = RegistryConfig(url=f"file://{reg}", public_key=pub, cache_dir=cache)
    client = RegistryClient(cfg)
    entry = client.index.versions("lib-a")[0]
    client.download("lib-a", "1.0.0", entry["sha256"], entry["sig"])

    bad_sig = base64.b64encode(b"x" * 64).decode()
    with pytest.raises(RuntimeError, match="imza"):
        client.download("lib-a", "1.0.0", entry["sha256"], bad_sig)


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_cached_unsigned_download_rechecks_unsigned_policy(tmp_path):
    """Önceden izin verilen unsigned cache, varsayılan politikayı atlayamaz."""
    reg, pub = _make_registry(tmp_path / "reg", {"lib-a": [{"version": "1.0.0"}]},
                              sign=False)
    cache = tmp_path / "cache"
    allowed = RegistryConfig(url=f"file://{reg}", public_key=pub, allow_unsigned=True,
                             cache_dir=cache)
    client = RegistryClient(allowed)
    entry = client.index.versions("lib-a")[0]
    client.download("lib-a", "1.0.0", entry["sha256"], "")

    denied = RegistryClient(RegistryConfig(url=f"file://{reg}", public_key=pub,
                                           allow_unsigned=False, cache_dir=cache))
    with pytest.raises(RuntimeError, match="imzalanmamış"):
        denied.download("lib-a", "1.0.0", entry["sha256"], "")


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_download_allows_unsigned_when_opted_in(tmp_path):
    reg, pub = _make_registry(tmp_path / "reg", {"lib-a": [{"version": "1.0.0"}]},
                              sign=False)
    cfg = RegistryConfig(url=f"file://{reg}", public_key=pub, allow_unsigned=True,
                         cache_dir=tmp_path / "c")
    client = RegistryClient(cfg)
    entry = client.index.versions("lib-a")[0]
    d, hit = client.download("lib-a", "1.0.0", entry["sha256"], "")
    assert (d / "axiom.toml").exists()


def test_download_rejects_path_traversal(tmp_path):
    """Arşiv içinde '../' varsa reddedilmeli."""
    base = tmp_path / "reg"
    (base / "evil").mkdir(parents=True)
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "axiom.toml").write_text('[package]\nname="evil"\nversion="1.0.0"\n')
        outside = d / ".." / "hacked.txt"
        tarball = base / "evil" / "1.0.0.tar.gz"
        with tarfile.open(tarball, "w:gz") as tf:
            tf.add(d / "axiom.toml", arcname="axiom.toml")
            info = tarfile.TarInfo("../hacked.txt")
            payload = b"pwned"
            info.size = len(payload)
            import io as _io
            tf.addfile(info, _io.BytesIO(payload))
    data = tarball.read_bytes()
    (base / "index.json").write_text(json.dumps({
        "schema": 1,
        "packages": {"evil": [{"version": "1.0.0", "sha256": sha256_bytes(data),
                               "dependencies": {}}]},
    }))
    cfg = RegistryConfig(url=f"file://{base}", allow_unsigned=True, cache_dir=tmp_path / "c")
    client = RegistryClient(cfg)
    with pytest.raises(RuntimeError, match="güvensiz arşiv yolu"):
        client.download("evil", "1.0.0", sha256_bytes(data), "")


def _make_untrusted_registry(tmp_path, members):
    archive_buffer = io.BytesIO()
    with tarfile.open(fileobj=archive_buffer, mode="w:gz") as archive:
        for info, contents in members:
            if contents is None:
                archive.addfile(info)
            else:
                info.size = len(contents)
                archive.addfile(info, io.BytesIO(contents))
    raw = archive_buffer.getvalue()
    registry = _register_untrusted_archive(tmp_path, raw)
    return registry, raw


def _register_untrusted_archive(tmp_path, raw):
    registry = tmp_path / "registry"
    package_dir = registry / "evil"
    package_dir.mkdir(parents=True)
    (package_dir / "1.0.0.tar.gz").write_bytes(raw)
    (registry / "index.json").write_text(json.dumps({
        "schema": 1,
        "packages": {"evil": [{
            "version": "1.0.0", "sha256": sha256_bytes(raw), "dependencies": {}
        }]},
    }), encoding="utf-8")
    return registry


def _download_untrusted_members(tmp_path, members):
    registry, raw = _make_untrusted_registry(tmp_path, members)
    client = RegistryClient(RegistryConfig(
        url=f"file://{registry}", allow_unsigned=True, cache_dir=tmp_path / "cache"
    ))
    return client.download("evil", "1.0.0", sha256_bytes(raw), "")


@pytest.mark.parametrize(("body", "accepted"), [(b"1234", True), (b"12345", False)])
def test_http_fetch_enforces_limit_without_content_length(monkeypatch, body, accepted):
    class Response:
        def __init__(self):
            self.read_sizes = []
            self.offset = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, size=-1):
            self.read_sizes.append(size)
            if size < 0:
                return body[self.offset:]
            chunk_end = min(len(body), self.offset + min(size, 2))
            chunk = body[self.offset:chunk_end]
            self.offset = chunk_end
            return chunk

    response = Response()
    monkeypatch.setattr(
        registry_module.urllib.request,
        "urlopen",
        lambda _request, timeout: response,
    )

    if accepted:
        assert registry_module._fetch("https://registry.example/pkg.tar.gz", max_bytes=4) == body
    else:
        with pytest.raises(RuntimeError, match="indirilen içerik 4 bayt sınırını aşıyor"):
            registry_module._fetch("https://registry.example/pkg.tar.gz", max_bytes=4)
    assert response.read_sizes == [5, 3, 1]


def test_download_bounds_oversized_file_uri_tarball(tmp_path, monkeypatch):
    registry = tmp_path / "registry"
    package_dir = registry / "large"
    package_dir.mkdir(parents=True)
    raw = b"x" * 65
    (package_dir / "1.0.0.tar.gz").write_bytes(raw)
    client = RegistryClient(RegistryConfig(
        url=registry.as_uri(), allow_unsigned=True, cache_dir=tmp_path / "cache"
    ))
    sha = sha256_bytes(raw)
    client._index = RegistryIndex({"large": [{
        "version": "1.0.0", "sha256": sha, "sig": "", "dependencies": {},
    }]}, registry.as_uri())
    monkeypatch.setattr(registry_module, "_MAX_REGISTRY_PACK_BYTES", 64)

    with pytest.raises(RuntimeError, match="indirilen içerik 64 bayt sınırını aşıyor"):
        client.download("large", "1.0.0", sha, "", {})
    assert not (tmp_path / "cache").exists()


def test_download_discards_oversized_cache_before_reading_it(tmp_path, monkeypatch):
    registry = tmp_path / "registry"
    package_dir = registry / "cache-test"
    package_dir.mkdir(parents=True)
    archive_buffer = io.BytesIO()
    manifest = b'[package]\nname = "cache-test"\nversion = "1.0.0"\n\n[dependencies]\n'
    with tarfile.open(fileobj=archive_buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo("axiom.toml")
        info.size = len(manifest)
        archive.addfile(info, io.BytesIO(manifest))
    raw = archive_buffer.getvalue()
    sha = sha256_bytes(raw)
    (package_dir / "1.0.0.tar.gz").write_bytes(raw)
    client = RegistryClient(RegistryConfig(
        url=registry.as_uri(), allow_unsigned=True, cache_dir=tmp_path / "cache"
    ))
    client._index = RegistryIndex({"cache-test": [{
        "version": "1.0.0", "sha256": sha, "sig": "", "dependencies": {},
    }]}, registry.as_uri())
    cache_dir = client.cache_path_for(sha)
    cache_dir.mkdir(parents=True)
    stored_tarball = cache_dir / "pkg.tar.gz"
    stored_tarball.write_bytes(b"x" * (len(raw) + 1))
    monkeypatch.setattr(registry_module, "_MAX_REGISTRY_PACK_BYTES", len(raw))
    original_open = Path.open

    def guard_oversized_cache_open(path, *args, **kwargs):
        if path == stored_tarball and args and args[0] == "rb":
            raise AssertionError("oversized cache archive was read before its size check")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guard_oversized_cache_open)
    extracted, cache_hit = client.download("cache-test", "1.0.0", sha, "", {})

    assert cache_hit is False
    assert (extracted / "axiom.toml").read_bytes() == manifest


def test_download_rejects_gzip_expansion_before_creating_cache(tmp_path, monkeypatch):
    manifest = b'[package]\nname = "evil"\nversion = "1.0.0"\n\n[dependencies]\n'
    payload = b"z" * 4096
    member = tarfile.TarInfo("large.bin")
    monkeypatch.setattr(registry_module, "_MAX_REGISTRY_TAR_EXPANDED_BYTES", 1024)
    with pytest.raises(RuntimeError, match="tar akışı açılmış boyut sınırını aşıyor"):
        _download_untrusted_members(
            tmp_path,
            [(tarfile.TarInfo("axiom.toml"), manifest), (member, payload)],
        )
    assert not (tmp_path / "cache").exists()


def test_download_rejects_tar_member_with_truncated_payload_before_cache(tmp_path):
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:") as archive:
        info = tarfile.TarInfo("payload.bin")
        info.size = 32
        archive.addfile(info, io.BytesIO(b"x" * 32))
    truncated_tar = tar_buffer.getvalue()[:512 + 5]
    raw = gzip.compress(truncated_tar)
    registry = _register_untrusted_archive(tmp_path, raw)
    client = RegistryClient(RegistryConfig(
        url=registry.as_uri(), allow_unsigned=True, cache_dir=tmp_path / "cache"
    ))
    client._index = RegistryIndex({"evil": [{
        "version": "1.0.0", "sha256": sha256_bytes(raw), "sig": "", "dependencies": {},
    }]}, registry.as_uri())

    with pytest.raises(RuntimeError, match="arşiv girdisi kesik: payload.bin"):
        client.download("evil", "1.0.0", sha256_bytes(raw), "", {})
    assert not (tmp_path / "cache").exists()


def test_download_rejects_oversized_manifest_before_extraction(tmp_path):
    manifest = b"#" * (registry_module._MAX_REGISTRY_MANIFEST_BYTES + 1)
    with pytest.raises(RuntimeError, match="axiom.toml 1 MiB sınırını aşıyor"):
        _download_untrusted_members(tmp_path, [(tarfile.TarInfo("axiom.toml"), manifest)])
    assert not (tmp_path / "cache").exists()


def test_download_rejects_excessive_tar_member_count_before_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(registry_module, "_MAX_REGISTRY_ARCHIVE_MEMBERS", 2)
    manifest = b'[package]\nname = "evil"\nversion = "1.0.0"\n\n[dependencies]\n'
    with pytest.raises(RuntimeError, match="2 üye sınırını aşıyor"):
        _download_untrusted_members(tmp_path, [
            (tarfile.TarInfo("axiom.toml"), manifest),
            (tarfile.TarInfo("one.bin"), b"1"),
            (tarfile.TarInfo("two.bin"), b"2"),
        ])
    assert not (tmp_path / "cache").exists()


def test_cache_hit_rejects_expansion_limit_and_removes_cache(tmp_path, monkeypatch):
    registry, raw = _make_untrusted_registry(tmp_path, [
        (tarfile.TarInfo("axiom.toml"),
         b'[package]\nname = "evil"\nversion = "1.0.0"\n\n[dependencies]\n'),
        (tarfile.TarInfo("payload.bin"), b"a" * 4096),
    ])
    sha = sha256_bytes(raw)
    client = RegistryClient(RegistryConfig(
        url=registry.as_uri(), allow_unsigned=True, cache_dir=tmp_path / "cache"
    ))
    client._index = RegistryIndex({"evil": [{
        "version": "1.0.0", "sha256": sha, "sig": "", "dependencies": {},
    }]}, registry.as_uri())
    cache_dir = client.cache_path_for(sha)
    cache_dir.mkdir(parents=True)
    (cache_dir / "pkg.tar.gz").write_bytes(raw)
    monkeypatch.setattr(registry_module, "_MAX_REGISTRY_TAR_EXPANDED_BYTES", 1024)

    with pytest.raises(RuntimeError, match="tar akışı açılmış boyut sınırını aşıyor"):
        client.download("evil", "1.0.0", sha, "", {})
    assert not cache_dir.exists()


def test_download_rejects_oversized_pax_header_before_cache(tmp_path):
    manifest = b'[package]\nname = "evil"\nversion = "1.0.0"\n\n[dependencies]\n'
    info = tarfile.TarInfo("axiom.toml")
    info.pax_headers = {
        "comment": "x" * (registry_module._MAX_REGISTRY_TAR_METADATA_READ + 64)
    }
    with pytest.raises(RuntimeError, match="tar uzantı başlığı"):
        _download_untrusted_members(tmp_path, [(info, manifest)])
    assert not (tmp_path / "cache").exists()


def test_download_rejects_cumulative_tar_metadata_over_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(registry_module, "_MAX_REGISTRY_TAR_METADATA_TOTAL", 2048)
    pax_files = []
    for index in range(3):
        info = tarfile.TarInfo(f"file-{index}.txt")
        info.pax_headers = {"comment": "x" * 600}
        pax_files.append((info, b"x"))

    with pytest.raises(RuntimeError, match="tar başlık/manifest verisi toplam"):
        _download_untrusted_members(tmp_path, pax_files)
    assert not (tmp_path / "cache").exists()


def test_archive_limit_counts_concatenated_gzip_members(tmp_path, monkeypatch):
    empty_tar = io.BytesIO()
    with tarfile.open(fileobj=empty_tar, mode="w:"):
        pass
    concatenated = (
        gzip.compress(empty_tar.getvalue())
        + gzip.compress(b"x" * 4096)
    )
    monkeypatch.setattr(registry_module, "_MAX_REGISTRY_TAR_EXPANDED_BYTES", 12 * 1024)

    with pytest.raises(RuntimeError, match="tar akışı açılmış boyut sınırını aşıyor"):
        registry_module._validate_package_archive_limits(concatenated)


def test_archive_limit_wraps_invalid_gzip_header_and_crc():
    with pytest.raises(RuntimeError, match="arşivi sınır/biçim doğrulaması başarısız"):
        registry_module._validate_package_archive_limits(b"not a gzip archive")

    tar_data = io.BytesIO()
    with tarfile.open(fileobj=tar_data, mode="w:"):
        pass
    raw = bytearray(gzip.compress(tar_data.getvalue()))
    raw[-8] ^= 0x01  # Corrupt the gzip CRC while retaining a valid header.
    with pytest.raises(RuntimeError, match="arşivi sınır/biçim doğrulaması başarısız"):
        registry_module._validate_package_archive_limits(bytes(raw))


def test_large_tar_payload_is_not_charged_to_metadata_budget(tmp_path):
    from axiom.package_manager import _validate_registry_pack_archive

    manifest = (
        b'[package]\nname = "evil"\nversion = "1.0.0"\nentry = "large.bin"\n'
        b'\n[dependencies]\n'
    )
    payload_size = 33 * 1024 * 1024
    archive_buffer = io.BytesIO()
    with tarfile.open(fileobj=archive_buffer, mode="w:gz") as archive:
        manifest_info = tarfile.TarInfo("axiom.toml")
        manifest_info.size = len(manifest)
        archive.addfile(manifest_info, io.BytesIO(manifest))
        payload_info = tarfile.TarInfo("large.bin")
        payload_info.size = payload_size
        archive.addfile(payload_info, io.BytesIO(b"x" * payload_size))
    raw = archive_buffer.getvalue()
    registry = _register_untrusted_archive(tmp_path, raw)
    client = RegistryClient(RegistryConfig(
        url=registry.as_uri(), allow_unsigned=True, cache_dir=tmp_path / "cache"
    ))
    client._index = RegistryIndex({"evil": [{
        "version": "1.0.0", "sha256": sha256_bytes(raw), "sig": "", "dependencies": {},
    }]}, registry.as_uri())

    extracted, cache_hit = client.download("evil", "1.0.0", sha256_bytes(raw), "", {})
    assert not cache_hit
    assert (extracted / "large.bin").stat().st_size == payload_size
    _validate_registry_pack_archive(raw, Path("<generated-test-archive>"), "evil", "1.0.0", {})


@pytest.mark.parametrize("link_type", [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_download_rejects_archive_links_before_extracting_children(tmp_path, link_type):
    link = tarfile.TarInfo("pivot")
    link.type = link_type
    link.linkname = "../outside"
    child = tarfile.TarInfo("pivot/escaped.txt")
    with pytest.raises(RuntimeError, match="desteklenmeyen arşiv girdisi"):
        _download_untrusted_members(tmp_path, [(link, None), (child, b"pwned")])
    assert not (tmp_path / "cache" / "sha256" / "outside" / "escaped.txt").exists()


def test_download_rejects_archive_special_files(tmp_path):
    fifo = tarfile.TarInfo("named-pipe")
    fifo.type = tarfile.FIFOTYPE
    with pytest.raises(RuntimeError, match="desteklenmeyen arşiv girdisi"):
        _download_untrusted_members(tmp_path, [(fifo, None)])


@pytest.mark.parametrize("member_name", [r"..\escaped.txt", "C:payload.txt"])
def test_download_rejects_windows_style_archive_paths(tmp_path, member_name):
    member = tarfile.TarInfo(member_name)
    with pytest.raises(RuntimeError, match="güvensiz arşiv yolu"):
        _download_untrusted_members(tmp_path, [(member, b"pwned")])
    assert not (tmp_path / "escaped.txt").exists()


# ---------------------------------------------------------------------------
# axpm install uçtan uca
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_axpm_install_registry_end_to_end(tmp_path):
    reg, pub = _make_registry(tmp_path / "reg", {
        "json-lib": [{"version": "1.0.0"}, {"version": "1.2.0"}],
        "app-lib": [{"version": "0.3.0", "deps": {"json-lib": "^1.0"}}],
    })
    app = tmp_path / "app"
    env = _isolated_env(tmp_path)
    subprocess.run([str(AXPM), "init", str(app)], check=True, capture_output=True, env=env)

    (app / "axiom.toml").write_text(
        f'[package]\nname = "app"\nversion = "0.1.0"\nentry = "src/main.ax"\n\n'
        f'[dependencies]\napp-lib = "^0.3"\n\n'
        f'[registry]\nurl = "file://{reg}"\npublic_key = """{pub}"""\n',
        encoding="utf-8",
    )
    res = subprocess.run([str(AXPM), "install"], cwd=str(app),
                         capture_output=True, text=True, env=env)
    assert res.returncode == 0, res.stdout + res.stderr

    lock = (app / "axiom.lock").read_text()
    assert 'name = "json-lib"' in lock and 'version = "1.2.0"' in lock
    assert 'name = "app-lib"' in lock
    assert (app / ".axiom" / "deps" / "json-lib" / "axiom.toml").exists()
    assert (app / ".axiom" / "deps" / "app-lib" / "axiom.toml").exists()

    verify = subprocess.run([str(AXPM), "verify"], cwd=str(app),
                            capture_output=True, text=True, env=env)
    assert verify.returncode == 0, verify.stdout + verify.stderr

    remove = subprocess.run([str(AXPM), "remove", "app-lib"],
                            cwd=str(app), capture_output=True, text=True, env=env)
    assert remove.returncode == 0, remove.stdout + remove.stderr
    assert not (app / ".axiom" / "deps" / "app-lib").exists()
    assert not (app / ".axiom" / "deps" / "json-lib").exists()
    lock_after_remove = LockFile.from_file(app / "axiom.lock")
    assert lock_after_remove.packages == []

    verify_after_remove = subprocess.run([str(AXPM), "verify"], cwd=str(app),
                                         capture_output=True, text=True, env=env)
    assert verify_after_remove.returncode == 0, verify_after_remove.stdout + verify_after_remove.stderr


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_axpm_install_rejects_signed_package_relabelled_by_index(tmp_path):
    registry, public_key = _make_registry(
        tmp_path / "registry", {"real-package": [{"version": "1.0.0"}]}
    )
    index_path = registry / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entry = index["packages"].pop("real-package")[0]
    (registry / "alias").mkdir()
    shutil.copyfile(
        registry / "real-package" / "1.0.0.tar.gz",
        registry / "alias" / "9.9.9.tar.gz",
    )
    entry["version"] = "9.9.9"
    index["packages"]["alias"] = [entry]
    index_path.write_text(json.dumps(index), encoding="utf-8")

    app = tmp_path / "consumer"
    env = _isolated_env(tmp_path)
    subprocess.run([str(AXPM), "init", str(app)], check=True, capture_output=True, env=env)
    (app / "axiom.toml").write_text(
        '[package]\nname = "consumer"\nversion = "0.1.0"\nentry = "src/main.ax"\n\n'
        '[dependencies]\nalias = "*"\n\n'
        f'[registry]\nurl = "{registry.as_uri()}"\npublic_key = """{public_key}"""\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(AXPM), "install"], cwd=app, env=env, capture_output=True, text=True,
    )
    assert result.returncode != 0, result.stdout + result.stderr
    assert "paket adı imzalı manifestoyla uyuşmuyor" in result.stderr
    assert not (app / ".axiom" / "deps" / "alias" / "axiom.toml").exists()
    assert 'name = "alias"' not in (app / "axiom.lock").read_text(encoding="utf-8")

@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_axpm_registry_upgrade_replaces_installed_package_contents(tmp_path):
    reg, pub = _make_registry(tmp_path / "reg", {
        "lib-a": [
            {"version": "1.0.0", "source": "fn old_api() -> int { return 1 }\n"},
            {"version": "1.1.0", "source": "fn new_api() -> int { return 2 }\n"},
        ],
    })
    app = tmp_path / "app"
    env = _isolated_env(tmp_path)
    subprocess.run([str(AXPM), "init", str(app)], check=True, capture_output=True, env=env)

    manifest = app / "axiom.toml"
    manifest.write_text(
        f'[package]\nname = "app"\nversion = "0.1.0"\nentry = "src/main.ax"\n\n'
        f'[dependencies]\nlib-a = "=1.0.0"\n\n'
        f'[registry]\nurl = "file://{reg}"\npublic_key = """{pub}"""\n',
        encoding="utf-8",
    )
    install_v1 = subprocess.run([str(AXPM), "install"], cwd=str(app),
                                 capture_output=True, text=True, env=env)
    assert install_v1.returncode == 0, install_v1.stdout + install_v1.stderr
    installed_source = app / ".axiom" / "deps" / "lib-a" / "src" / "lib.ax"
    assert "old_api" in installed_source.read_text(encoding="utf-8")

    manifest.write_text(manifest.read_text(encoding="utf-8").replace("=1.0.0", "=1.1.0"), encoding="utf-8")
    install_v2 = subprocess.run([str(AXPM), "install"], cwd=str(app),
                                capture_output=True, text=True, env=env)
    assert install_v2.returncode == 0, install_v2.stdout + install_v2.stderr

    assert "new_api" in installed_source.read_text(encoding="utf-8")
    assert LockFile.from_file(app / "axiom.lock").packages[0]["version"] == "1.1.0"
    verify = subprocess.run([str(AXPM), "verify"], cwd=str(app),
                            capture_output=True, text=True, env=env)
    assert verify.returncode == 0, verify.stdout + verify.stderr


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_axpm_remove_keeps_registry_package_still_used_transitively(tmp_path):
    reg, pub = _make_registry(tmp_path / "reg", {
        "json-lib": [{"version": "1.0.0"}],
        "app-lib": [{"version": "0.3.0", "deps": {"json-lib": "^1.0"}}],
    })
    app = tmp_path / "app"
    env = _isolated_env(tmp_path)
    subprocess.run([str(AXPM), "init", str(app)], check=True, capture_output=True, env=env)
    (app / "axiom.toml").write_text(
        f'[package]\nname = "app"\nversion = "0.1.0"\nentry = "src/main.ax"\n\n'
        f'[dependencies]\napp-lib = "^0.3"\njson-lib = "^1.0"\n\n'
        f'[registry]\nurl = "file://{reg}"\npublic_key = """{pub}"""\n',
        encoding="utf-8",
    )
    install = subprocess.run([str(AXPM), "install"], cwd=str(app),
                             capture_output=True, text=True, env=env)
    assert install.returncode == 0, install.stdout + install.stderr

    remove = subprocess.run([str(AXPM), "remove", "app-lib", "--purge"],
                            cwd=str(app), capture_output=True, text=True, env=env)
    assert remove.returncode == 0, remove.stdout + remove.stderr
    assert not (app / ".axiom" / "deps" / "app-lib").exists()
    assert (app / ".axiom" / "deps" / "json-lib" / "axiom.toml").exists()
    lock = LockFile.from_file(app / "axiom.lock")
    assert [pkg["name"] for pkg in lock.packages] == ["json-lib"]


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_axpm_install_fails_on_tampered_and_keeps_nothing(tmp_path):
    reg, pub = _make_registry(tmp_path / "reg", {"lib-a": [{"version": "1.0.0"}]},
                              tamper=True)
    app = tmp_path / "app"
    env = _isolated_env(tmp_path)
    subprocess.run([str(AXPM), "init", str(app)], check=True, capture_output=True, env=env)
    (app / "axiom.toml").write_text(
        f'[package]\nname = "app"\nversion = "0.1.0"\nentry = "src/main.ax"\n\n'
        f'[dependencies]\nlib-a = "=1.0.0"\n\n'
        f'[registry]\nurl = "file://{reg}"\npublic_key = """{pub}"""\n',
        encoding="utf-8",
    )
    res = subprocess.run([str(AXPM), "install"], cwd=str(app),
                         capture_output=True, text=True, env=env)
    assert res.returncode != 0
    assert "sha256" in (res.stdout + res.stderr).lower()
    assert not (app / ".axiom" / "deps" / "lib-a").exists()


def test_registry_section_survives_manifest_rewrite(tmp_path):
    """axpm add/remove [registry] ayarını silmemeli."""
    from axiom.package_manager import Manifest
    p = tmp_path / "axiom.toml"
    p.write_text(
        '[package]\nname = "x"\nversion = "0.1.0"\n\n'
        '[dependencies]\n\n'
        '[registry]\nurl = "file:///r"\npublic_key = "K"\n',
        encoding="utf-8",
    )
    m = Manifest.from_file(p)
    m.dependencies["a"] = "^1"
    m.save(p)
    text = p.read_text()
    assert "[registry]" in text and 'url = "file:///r"' in text


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_axpm_search_lists_and_filters(tmp_path):
    reg, pub = _make_registry(tmp_path / "reg", {
        "json-lib": [{"version": "1.0.0"}, {"version": "1.2.0"}],
        "net-lib": [{"version": "0.1.0"}],
    })
    app = tmp_path / "app"
    env = _isolated_env(tmp_path)
    subprocess.run([str(AXPM), "init", str(app)], check=True, capture_output=True, env=env)
    (app / "axiom.toml").write_text(
        f'[package]\nname = "app"\nversion = "0.1.0"\nentry = "src/main.ax"\n\n'
        f'[dependencies]\n\n[registry]\nurl = "file://{reg}"\npublic_key = """{pub}"""\n',
        encoding="utf-8",
    )

    import re as _re
    def strip_ansi(t):
        return _re.sub(r"\x1b\[[0-9;]*m", "", t)

    all_res = subprocess.run([str(AXPM), "search"], cwd=str(app),
                             capture_output=True, text=True, env=env)
    assert all_res.returncode == 0, all_res.stdout + all_res.stderr
    plain = strip_ansi(all_res.stdout)
    assert "json-lib" in plain and "net-lib" in plain
    assert "json-lib 1.2.0" in plain  # en yüksek sürüm

    filtered = subprocess.run([str(AXPM), "search", "json"], cwd=str(app),
                              capture_output=True, text=True, env=env)
    assert filtered.returncode == 0
    fplain = strip_ansi(filtered.stdout)
    assert "json-lib" in fplain
    assert "net-lib" not in fplain

    none = subprocess.run([str(AXPM), "search", "zzz"], cwd=str(app),
                          capture_output=True, text=True, env=env)
    assert none.returncode == 0
    assert "Sonuç yok" in strip_ansi(none.stdout)


# ---------------------------------------------------------------------------
# P2-02 — Namespace (@kapsam/paket)
# ---------------------------------------------------------------------------

def test_dep_name_validation_and_dir_mapping():
    from axiom.package_manager import is_valid_dep_name, dep_dir_name, compute_dir_checksum

    assert is_valid_dep_name("plain")
    assert is_valid_dep_name("@user/pkg")
    assert is_valid_dep_name("@user.a/pkg-b_1")
    for bad in ("", "a/b/c", "@u/../x", "../evil", "a b", "a\\b"):
        assert not is_valid_dep_name(bad), bad

    assert dep_dir_name("@user/pkg") == "@user__pkg"
    assert dep_dir_name("plain") == "plain"


@pytest.mark.skipif(not _have_openssl(), reason="openssl gerekli")
def test_axpm_install_namespaced_package(tmp_path):
    reg, pub = _make_registry(tmp_path / "reg", {
        "@acme/json": [{"version": "1.0.0"}],
        "@other/json": [{"version": "2.0.0"}],
    })
    app = tmp_path / "app"
    env = _isolated_env(tmp_path)
    subprocess.run([str(AXPM), "init", str(app)], check=True, capture_output=True, env=env)
    (app / "axiom.toml").write_text(
        f'[package]\nname = "app"\nversion = "0.1.0"\nentry = "src/main.ax"\n\n'
        f'[dependencies]\n"@acme/json" = "*"\n"@other/json" = "*"\n\n'
        f'[registry]\nurl = "file://{reg}"\npublic_key = """{pub}"""\n',
        encoding="utf-8",
    )
    res = subprocess.run([str(AXPM), "install"], cwd=str(app),
                         capture_output=True, text=True, env=env)
    assert res.returncode == 0, res.stdout + res.stderr

    # Çakışma olmadan iki ayrı dizin
    assert (app / ".axiom" / "deps" / "@acme__json" / "axiom.toml").exists()
    assert (app / ".axiom" / "deps" / "@other__json" / "axiom.toml").exists()

    lock = (app / "axiom.lock").read_text()
    assert '@acme/json' in lock and '@other/json' in lock

    verify = subprocess.run([str(AXPM), "verify"], cwd=str(app),
                            capture_output=True, text=True, env=env)
    assert verify.returncode == 0, verify.stdout + verify.stderr


def test_axpm_rejects_invalid_dependency_name(tmp_path):
    app = tmp_path / "app"
    env = _isolated_env(tmp_path)
    subprocess.run([str(AXPM), "init", str(app)], check=True, capture_output=True, env=env)
    res = subprocess.run([str(AXPM), "add", "../evil", "--version", "*"],
                         cwd=str(app), capture_output=True, text=True, env=env)
    assert res.returncode != 0
    assert "Gecersiz paket adi" in (res.stdout + res.stderr)


def test_resolver_imports_namespaced_package(tmp_path):
    """import "@kapsam/paket" doğru dizine çözülmeli."""
    from axiom.lexer import Lexer
    from axiom.parser import Parser
    from axiom.resolver import ModuleResolver

    deps = tmp_path / ".axiom" / "deps" / "@acme__util" / "src"
    deps.mkdir(parents=True)
    (deps / "lib.ax").write_text("fn acme_fn() -> int { return 7 }\n", encoding="utf-8")

    main = tmp_path / "main.ax"
    main.write_text('import "@acme/util"\nfn main() -> int { return acme_fn() }\n',
                    encoding="utf-8")

    prog = Parser(Lexer(main.read_text(encoding="utf-8")).tokenize()).parse()
    resolver = ModuleResolver(base_file_path=str(main))
    resolver.search_paths = [tmp_path / ".axiom" / "deps"]
    resolved = resolver.resolve(prog)
    names = [getattr(d, "name", None) for d in resolved.declarations]
    assert "acme_fn" in names


def test_resolver_rejects_traversal_package_name(tmp_path):
    from axiom.lexer import Lexer
    from axiom.parser import Parser
    from axiom.resolver import ModuleResolver, ModuleError

    main = tmp_path / "main.ax"
    main.write_text('import "@u/../x"\nfn main() -> int { return 0 }\n', encoding="utf-8")
    prog = Parser(Lexer(main.read_text(encoding="utf-8")).tokenize()).parse()
    resolver = ModuleResolver(base_file_path=str(main))
    with pytest.raises(ModuleError, match="Gecersiz paket adi"):
        resolver.resolve(prog)
