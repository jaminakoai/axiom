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
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
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


# ---------------------------------------------------------------------------
# Çözümleme
# ---------------------------------------------------------------------------

def _idx(packages):
    return RegistryIndex(packages, "file:///test")


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
                (d / "src" / "lib.ax").write_text(
                    f"fn {name.replace('-', '_')}_v() -> int {{ return 1 }}\n", encoding="utf-8")
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
