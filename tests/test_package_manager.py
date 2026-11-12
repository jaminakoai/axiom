"""
Axiom Programming Language (λx) - Package Manager Tests (axpm / axiom pkg)
Faz 5.1 Kapsamlı Test Suiti:
- axiom.toml manifest ayrıştırma ve kaydetme
- axiom.lock deterministik kilit üretimi ve sağlama toplamı doğrulaması
- axpm init (bin ve lib şablonları)
- axpm add (yerel bağımlılık ekleme)
- axpm install ve bağımlılık çözümleme
- axpm build, run ve test uçtan uca doğrulaması
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
import pytest

from axiom.package_manager import (
    Manifest, LockFile, PackageManager, compute_dir_checksum, TomlWriter, parse_toml
)

AXIOM_BIN = Path(__file__).resolve().parent.parent / "bin" / "axiom"
AXPM_BIN = Path(__file__).resolve().parent.parent / "bin" / "axpm"


def test_toml_writer_and_parser():
    data = {
        "package": {
            "name": "crypto_core",
            "version": "1.2.3",
            "authors": ["Security Lead <sec@axiom.org>"],
            "edition": "2026"
        },
        "dependencies": {
            "math_utils": {"path": "../math_utils"},
            "logger": "0.5.0"
        }
    }
    dumped = TomlWriter.dumps(data)
    assert "[package]" in dumped
    assert 'name = "crypto_core"' in dumped
    assert 'version = "1.2.3"' in dumped
    assert "[dependencies]" in dumped

    parsed = parse_toml(dumped)
    assert parsed["package"]["name"] == "crypto_core"
    assert parsed["package"]["version"] == "1.2.3"
    assert parsed["dependencies"]["logger"] == "0.5.0"


def test_manifest_roundtrip(tmp_path):
    manifest_path = tmp_path / "axiom.toml"
    manifest = Manifest(
        name="firewall_agent",
        version="0.2.0",
        authors=["Alice <alice@axiom.org>"],
        edition="2026",
        entry="src/main.ax",
        description="Axiom Firewall Engine",
        dependencies={"net_core": {"path": "../net_core"}}
    )
    manifest.save(manifest_path)
    assert manifest_path.exists()

    loaded = Manifest.from_file(manifest_path)
    assert loaded.name == "firewall_agent"
    assert loaded.version == "0.2.0"
    assert loaded.edition == "2026"
    assert "net_core" in loaded.dependencies


def test_lockfile_generation_and_tamper_detection(tmp_path):
    dep_dir = tmp_path / "dep_lib"
    dep_dir.mkdir()
    (dep_dir / "lib.ax").write_text("fn helper() -> int { return 42; }\n", encoding="utf-8")

    initial_hash = compute_dir_checksum(dep_dir)
    lock = LockFile(version=1, packages=[{
        "name": "dep_lib",
        "version": "0.1.0",
        "source": "path:dep_lib",
        "checksum": initial_hash,
        "dependencies": []
    }])
    lock_path = tmp_path / "axiom.lock"
    lock.save(lock_path)

    # 1. İlk doğrulama başarılı olmalı
    ok, msg = lock.verify(tmp_path)
    assert ok is True
    assert "başarılı" in msg

    # 2. Dosya içeriği değiştirilirse tamper tespit edilmeli
    (dep_dir / "lib.ax").write_text("fn helper() -> int { return 999; }\n", encoding="utf-8")
    ok, msg = lock.verify(tmp_path)
    assert ok is False
    assert "SHA-256 uyumsuzluğu" in msg


def test_package_init_binary(tmp_path):
    pkg_dir = tmp_path / "app_server"
    pm = PackageManager()
    res = pm.init_package(target_dir=pkg_dir, name="app_server", is_lib=False)
    assert res == pkg_dir
    assert (pkg_dir / "axiom.toml").exists()
    assert (pkg_dir / "axiom.lock").exists()
    assert (pkg_dir / "src" / "main.ax").exists()
    assert (pkg_dir / "tests" / "test_main.ax").exists()
    assert (pkg_dir / ".gitignore").exists()
    assert (pkg_dir / "README.md").exists()

    manifest = Manifest.from_file(pkg_dir / "axiom.toml")
    assert manifest.name == "app_server"
    assert manifest.entry == "src/main.ax"


def test_package_init_library(tmp_path):
    lib_dir = tmp_path / "math_lib"
    pm = PackageManager()
    pm.init_package(target_dir=lib_dir, name="math_lib", is_lib=True)
    assert (lib_dir / "src" / "lib.ax").exists()
    lib_content = (lib_dir / "src" / "lib.ax").read_text(encoding="utf-8")
    assert "fn add(a: int, b: int) -> int" in lib_content


def test_package_add_dependency_and_install(tmp_path):
    # Kütüphane oluştur
    lib_dir = tmp_path / "calc_lib"
    pm_lib = PackageManager()
    pm_lib.init_package(target_dir=lib_dir, name="calc_lib", is_lib=True)

    # Uygulama paketi oluştur
    app_dir = tmp_path / "calc_app"
    pm_app = PackageManager(root_dir=app_dir)
    pm_app.init_package(target_dir=app_dir, name="calc_app", is_lib=False)

    # Bağımlılığı ekle
    pm_app.add_dependency("calc_lib", path=str(lib_dir))

    # axiom.toml ve axiom.lock denetimleri
    manifest = Manifest.from_file(app_dir / "axiom.toml")
    assert "calc_lib" in manifest.dependencies
    assert manifest.dependencies["calc_lib"]["path"] == str(lib_dir)

    lock = LockFile.from_file(app_dir / "axiom.lock")
    assert len(lock.packages) == 1
    assert lock.packages[0]["name"] == "calc_lib"
    assert lock.packages[0]["source"] == f"path:{str(lib_dir)}"
    assert len(lock.packages[0]["checksum"]) == 64


def test_package_build_and_run_end_to_end(tmp_path):
    # 1. Kütüphane paketi oluştur
    lib_dir = tmp_path / "str_tools"
    pm_lib = PackageManager(root_dir=lib_dir)
    pm_lib.init_package(target_dir=lib_dir, name="str_tools", is_lib=True)

    (lib_dir / "src" / "lib.ax").write_text("""// String Tools Kütüphanesi
fn duplicate_text(s: str) -> str {
    return s + s
}
""", encoding="utf-8")

    # 2. Ana uygulama paketi oluştur
    app_dir = tmp_path / "app_consumer"
    pm_app = PackageManager(root_dir=app_dir)
    pm_app.init_package(target_dir=app_dir, name="app_consumer", is_lib=False)

    pm_app.add_dependency("str_tools", path=str(lib_dir))

    (app_dir / "src" / "main.ax").write_text("""// Consumer App
import "str_tools"

fn main() -> void {
    let dup = duplicate_text("Axiom")
    print("Sonuc:", dup)
}
""", encoding="utf-8")

    # 3. Build & Run
    out_bin = pm_app.build(release=False)
    assert out_bin.exists()
    assert os.access(out_bin, os.X_OK)

    res = subprocess.run([str(out_bin)], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Sonuc: AxiomAxiom" in res.stdout


def test_package_test_runner(tmp_path):
    pkg_dir = tmp_path / "tested_pkg"
    pm = PackageManager(root_dir=pkg_dir)
    pm.init_package(target_dir=pkg_dir, name="tested_pkg", is_lib=True)

    code = pm.test()
    assert code == 0


def test_cli_axpm_integration(tmp_path):
    # bin/axpm CLI aracı üzerinden test
    pkg_dir = tmp_path / "cli_pkg"
    cmd_init = [str(AXPM_BIN), "init", str(pkg_dir), "--name", "cli_test_pkg"]
    res = subprocess.run(cmd_init, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Yeni Axiom paketi oluşturuldu" in res.stdout

    # axiom pkg build
    cmd_build = [str(AXIOM_BIN), "pkg", "build"]
    res_b = subprocess.run(cmd_build, cwd=str(pkg_dir), capture_output=True, text=True)
    assert res_b.returncode == 0
    assert "Paket başarıyla derlendi" in res_b.stdout

    # axpm run
    cmd_run = [str(AXPM_BIN), "run"]
    res_r = subprocess.run(cmd_run, cwd=str(pkg_dir), capture_output=True, text=True)
    assert res_r.returncode == 0
    assert "Axiom Paketi Çalışıyor: cli_test_pkg" in res_r.stdout


def test_git_dependency_clone_and_lock_verification(tmp_path):
    # 1. Uzak sahte Git deposu oluştur (bare veya yerel git repo)
    git_repo = tmp_path / "remote_git_lib"
    git_repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=str(git_repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Axiom Test"], cwd=str(git_repo), check=True)
    subprocess.run(["git", "config", "user.email", "test@axiom.org"], cwd=str(git_repo), check=True)

    pm_git = PackageManager(root_dir=git_repo)
    pm_git.init_package(target_dir=git_repo, name="remote_git_lib", is_lib=True)
    (git_repo / "src" / "lib.ax").write_text("""// Remote Git Library
fn git_multiply(a: int, b: int) -> int {
    return a * b
}
""", encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=str(git_repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(git_repo), check=True, capture_output=True)

    expected_content_hash = compute_dir_checksum(git_repo)

    # 2. Tüketici paketi oluştur
    consumer_dir = tmp_path / "git_consumer_app"
    pm_consumer = PackageManager(root_dir=consumer_dir)
    pm_consumer.init_package(target_dir=consumer_dir, name="git_consumer_app", is_lib=False)

    # 3. Git bağımlılığını ekle ve install çağır
    pm_consumer.add_dependency("remote_git_lib", git=str(git_repo))

    # Klonlanan dizinin varlığını doğrula
    cloned_dir = consumer_dir / ".axiom" / "deps" / "remote_git_lib"
    assert cloned_dir.exists()
    assert (cloned_dir / "src" / "lib.ax").exists()

    # 4. axiom.lock içeriğini doğrula: Gerçek içerik hash'i ve git kaynağı yazılmış olmalı
    lock = LockFile.from_file(consumer_dir / "axiom.lock")
    assert len(lock.packages) == 1
    pkg = lock.packages[0]
    assert pkg["name"] == "remote_git_lib"
    assert pkg["source"] == f"git:{str(git_repo)}#main"
    assert pkg["checksum"] == expected_content_hash

    # 5. LockFile.verify doğrulama kontrolü
    ok, msg = lock.verify(consumer_dir)
    assert ok is True
    assert "başarılı" in msg

    # 6. Tamper tespiti: İndirilen paketin içeriği bozulursa lock doğrulaması başarısız olmalı
    (cloned_dir / "src" / "lib.ax").write_text("// Tampered content\n", encoding="utf-8")
    ok, msg = lock.verify(consumer_dir)
    assert ok is False
    assert "SHA-256 uyumsuzluğu" in msg


def test_git_dependency_build_and_run_end_to_end(tmp_path):
    # 1. Uzak Git deposu oluştur
    git_repo = tmp_path / "git_calc_lib"
    git_repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=str(git_repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Axiom Git"], cwd=str(git_repo), check=True)
    subprocess.run(["git", "config", "user.email", "git@axiom.org"], cwd=str(git_repo), check=True)

    pm_git = PackageManager(root_dir=git_repo)
    pm_git.init_package(target_dir=git_repo, name="git_calc_lib", is_lib=True)
    (git_repo / "src" / "lib.ax").write_text("""// Git Calc Lib
fn calc_power(x: int) -> int {
    return x * x
}
""", encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=str(git_repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Release 0.1.0"], cwd=str(git_repo), check=True, capture_output=True)

    # 2. Tüketici paketi oluştur
    consumer_dir = tmp_path / "calc_consumer"
    pm_consumer = PackageManager(root_dir=consumer_dir)
    pm_consumer.init_package(target_dir=consumer_dir, name="calc_consumer", is_lib=False)

    pm_consumer.add_dependency("git_calc_lib", git=str(git_repo))

    (consumer_dir / "src" / "main.ax").write_text("""// Consumer Main
import "git_calc_lib"

fn main() -> void {
    let p = calc_power(7)
    print("Power:", p)
}
""", encoding="utf-8")

    # 3. Derle ve çalıştır
    out_bin = pm_consumer.build(release=False)
    assert out_bin.exists()

    res = subprocess.run([str(out_bin)], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Power: 49" in res.stdout




def test_package_verify_tree_and_remove(tmp_path):
    lib_dir = tmp_path / "verify_lib"
    pm_lib = PackageManager()
    pm_lib.init_package(target_dir=lib_dir, name="verify_lib", is_lib=True)
    (lib_dir / "src" / "lib.ax").write_text("fn vf() -> int { return 1 }\n", encoding="utf-8")

    app_dir = tmp_path / "verify_app"
    pm_app = PackageManager(root_dir=app_dir)
    pm_app.init_package(target_dir=app_dir, name="verify_app", is_lib=False)
    pm_app.add_dependency("verify_lib", path=str(lib_dir))

    # 1. verify basarili
    assert pm_app.verify() is True

    # 2. tree ciktisi (capsys ile)
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        pm_app.tree()
    out = buf.getvalue()
    assert "verify_app" in out
    assert "verify_lib" in out
    assert "checksum" in out

    # 3. tamper tespiti
    (lib_dir / "src" / "lib.ax").write_text("fn vf() -> int { return 999 }\n", encoding="utf-8")
    assert pm_app.verify() is False

    # 4. remove
    pm_app.remove_dependency("verify_lib")
    manifest = Manifest.from_file(app_dir / "axiom.toml")
    assert "verify_lib" not in manifest.dependencies
    lock = LockFile.from_file(app_dir / "axiom.lock")
    assert all(p["name"] != "verify_lib" for p in lock.packages)


def test_package_update_refetches_git_dependency(tmp_path):
    repo = tmp_path / "upd_lib"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Axiom"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "a@axiom.org"], cwd=str(repo), check=True)
    pm_lib = PackageManager(root_dir=repo)
    pm_lib.init_package(target_dir=repo, name="upd_lib", is_lib=True)
    (repo / "src" / "lib.ax").write_text("fn one() -> int { return 1 }\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "v1"], cwd=str(repo), check=True, capture_output=True)

    app = tmp_path / "upd_app"
    pm_app = PackageManager(root_dir=app)
    pm_app.init_package(target_dir=app, name="upd_app", is_lib=False)
    pm_app.add_dependency("upd_lib", git=str(repo))

    lock_before = LockFile.from_file(app / "axiom.lock")
    checksum_before = lock_before.packages[0]["checksum"]

    # Kütüphaneyi değiştir ve commit'le
    (repo / "src" / "lib.ax").write_text("fn two() -> int { return 2 }\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "v2"], cwd=str(repo), check=True, capture_output=True)

    pm_app.update()
    lock_after = LockFile.from_file(app / "axiom.lock")
    checksum_after = lock_after.packages[0]["checksum"]

    assert checksum_after != checksum_before
    assert "fn two" in (app / ".axiom" / "deps" / "upd_lib" / "src" / "lib.ax").read_text(encoding="utf-8")
    assert pm_app.verify() is True


def test_package_update_rejects_non_git_dependency(tmp_path):
    app = tmp_path / "upd_bad"
    pm = PackageManager(root_dir=app)
    pm.init_package(target_dir=app, name="upd_bad", is_lib=False)
    with pytest.raises(KeyError):
        pm.update("missing_dep")


def test_parse_toml_handles_inline_tables_without_tomllib(monkeypatch):
    """Python 3.10 yedeği: `tomllib` yokken de bağımlılık tabloları ayrıştırılmalı.

    Gerçek hata (CI, Python 3.10): resolver `tomllib`'i doğrudan import ediyordu.
    3.10'da modül olmadığı için istisna yutuluyor, `dependencies` hiç
    okunmuyor ve `import "paket"` "modül bulunamadı" ile düşüyordu.
    """
    import axiom.package_manager as pm

    monkeypatch.setattr(pm, "tomllib", None)
    data = pm.parse_toml(
        '[package]\nname = "app"\n\n[dependencies]\n'
        'str_tools = { path = "/tmp/x/str_tools" }\n'
        'yaml = { git = "https://example/x.git", rev = "v1" }\n'
    )
    deps = data["dependencies"]
    assert deps["str_tools"] == {"path": "/tmp/x/str_tools"}
    assert deps["yaml"] == {"git": "https://example/x.git", "rev": "v1"}
