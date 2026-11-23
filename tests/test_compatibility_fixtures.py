"""Exercise the historical-release compatibility fixture harness."""

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from tools import check_compatibility_fixtures as compatibility


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _release_dir(root: Path, version: str) -> Path:
    release = root / f"v{version}"
    release.mkdir(parents=True)
    return release


def _write_manifest(release: Path, version: str, **groups) -> dict:
    manifest = {
        "schema_version": 2,
        "release": version,
        "source_examples": groups.get("source_examples", []),
        "package_projects": groups.get("package_projects", []),
        "scanner_schemas": groups.get("scanner_schemas", []),
        "scanner_cases": groups.get("scanner_cases", []),
    }
    (release / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def _write_report_schema(release: Path, schema: dict | None = None) -> dict:
    schema_path = release / "schemas" / "report.json"
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(
        json.dumps(schema or {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["target", "tool_version"],
            "properties": {
                "target": {"type": "string"},
                "tool_version": {"type": "string"},
            },
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"id": "report-v1", "path": "schemas/report.json", "sha256": _hash(schema_path)}


def _write_scanner_fixture(
    release: Path, *, version: str = "1.0.0",
    expected_report: dict | None = None, schema: dict | None = None
) -> tuple[dict, Path, Path]:
    scan_dir = release / "scan"
    scan_dir.mkdir()
    rules = scan_dir / "rules.yar"
    rules.write_text('rule R { strings: $a = "x" condition: $a }\n', encoding="utf-8")
    target = scan_dir / "target.bin"
    target.write_bytes(b"x")
    expected_json = scan_dir / "expected.json"
    expected_json.write_text(
        json.dumps(expected_report or {"target": "target.bin", "tool_version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    report_schema = _write_report_schema(release, schema)
    manifest = _write_manifest(
        release,
        version,
        scanner_schemas=[report_schema],
        scanner_cases=[{
            "id": "scanner",
            "rules": "scan/rules.yar",
            "rules_sha256": _hash(rules),
            "target": "scan/target.bin",
            "target_sha256": _hash(target),
            "expected_json": "scan/expected.json",
            "expected_json_sha256": _hash(expected_json),
            "schema_id": report_schema["id"],
            "backends": ["c"],
            "exit_code": 0,
        }],
    )
    return manifest, release / report_schema["path"], expected_json


def test_fixture_manifest_schema_validates_current_manifest_shapes(tmp_path):
    from jsonschema import Draft202012Validator

    schema_path = (
        Path(__file__).resolve().parent.parent
        / "docs"
        / "api"
        / "compat-fixture-manifest.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    release = _release_dir(tmp_path, "1.0.0")
    source = release / "sources" / "hello.ax"
    source.parent.mkdir()
    source.write_text("fn main() -> int { return 0; }\n", encoding="utf-8")

    package = release / "packages" / "sample"
    (package / "src").mkdir(parents=True)
    (package / "src" / "main.ax").write_text(
        "fn main() -> int { return 0; }\n", encoding="utf-8"
    )
    (package / "axiom.toml").write_text("[package]\nname = 'sample'\n", encoding="utf-8")
    (package / "axiom.lock").write_text("# fixture lock\n", encoding="utf-8")

    scanner = release / "scan"
    scanner.mkdir()
    rules = scanner / "rules.yar"
    rules.write_text('rule R { strings: $a = "x" condition: $a }\n', encoding="utf-8")
    target = scanner / "target.bin"
    target.write_bytes(b"x")
    expected_json = scanner / "expected.json"
    expected_json.write_text(
        json.dumps({"target": "target.bin", "tool_version": "0.5.0-alpha"}) + "\n",
        encoding="utf-8",
    )
    report_schema = _write_report_schema(release)

    valid_manifest = _write_manifest(
        release,
        "1.0.0",
        source_examples=[{
            "id": "hello",
            "source": "sources/hello.ax",
            "sha256": _hash(source),
            "backends": ["c", "llvm"],
            "stdout": "",
            "exit_code": 0,
        }],
        package_projects=[{
            "id": "package",
            "root": "packages/sample",
            "tree_sha256": compatibility.sha256_tree(package),
            "entry": "src/main.ax",
            "backends": ["c"],
            "stdout": "",
            "exit_code": 0,
        }],
        scanner_schemas=[report_schema],
        scanner_cases=[{
            "id": "scanner",
            "rules": "scan/rules.yar",
            "rules_sha256": _hash(rules),
            "target": "scan/target.bin",
            "target_sha256": _hash(target),
            "expected_json": "scan/expected.json",
            "expected_json_sha256": _hash(expected_json),
            "schema_id": "report-v1",
            "backends": ["llvm"],
            "exit_code": 0,
        }],
    )
    assert validator.is_valid(valid_manifest)
    assert compatibility.load_manifest(release) == valid_manifest
    assert not validator.is_valid({**valid_manifest, "unexpected": True})
    assert not validator.is_valid({
        **valid_manifest,
        "source_examples": [],
        "package_projects": [],
        "scanner_schemas": [],
        "scanner_cases": [],
    })
    assert not validator.is_valid({
        **valid_manifest,
        "scanner_cases": [{**valid_manifest["scanner_cases"][0], "target_sha256": "bad"}],
    })


def test_previous_minor_gate_starts_only_after_two_stable_minor_releases():
    assert compatibility.canonical_version("0.5.0a0") == "0.5.0-alpha"
    assert compatibility.canonical_version("1.2.0rc1") == "1.2.0-rc.1"
    assert compatibility.required_minor_lines("0.5.0a0") == []
    assert compatibility.required_minor_lines("1.0.0") == []
    assert compatibility.required_minor_lines("1.1.4") == []
    assert compatibility.required_minor_lines("1.2.0-alpha.0") == [(1, 1), (1, 0)]
    assert compatibility.required_minor_lines("1.3.2") == [(1, 2), (1, 1)]
    with pytest.raises(compatibility.FixtureError, match="1.1.x, 1.0.x"):
        compatibility.select_required_releases("1.2.0", [])


def test_source_fixtures_compile_and_run_on_both_backends(tmp_path):
    release = _release_dir(tmp_path, "1.0.0")
    source = release / "sources" / "hello.ax"
    source.parent.mkdir()
    source.write_text(
        'fn main() -> int { print("compat-fixture"); return 7; }\n',
        encoding="utf-8",
    )
    _write_manifest(
        release,
        "1.0.0",
        source_examples=[{
            "id": "hello",
            "source": "sources/hello.ax",
            "sha256": _hash(source),
            "backends": ["c", "llvm"],
            "stdout": "compat-fixture\n",
            "exit_code": 7,
        }],
    )

    manifest = compatibility.load_manifest(release)
    assert compatibility.run_release(release, manifest) == 1


def test_package_fixture_verifies_lock_and_runs_on_requested_backend(tmp_path):
    from axiom.package_manager import PackageManager

    release = _release_dir(tmp_path, "1.0.0")
    package = release / "packages" / "hello"
    manager = PackageManager(package)
    manager.init_package(target_dir=package, name="compat_hello", is_lib=False)
    entry = package / "src" / "main.ax"
    entry.write_text(
        'fn main() -> int { print("package-fixture"); return 0; }\n',
        encoding="utf-8",
    )
    manager.install()
    _write_manifest(
        release,
        "1.0.0",
        package_projects=[{
            "id": "hello-package",
            "root": "packages/hello",
            "tree_sha256": compatibility.sha256_tree(package),
            "entry": "src/main.ax",
            "backends": ["c"],
            "stdout": "package-fixture\n",
            "exit_code": 0,
        }],
    )

    manifest = compatibility.load_manifest(release)
    assert compatibility.run_release(release, manifest) == 1


def test_scanner_fixture_pins_inputs_and_exact_report_json(tmp_path):
    release = _release_dir(tmp_path, "1.0.0")
    rules = release / "scan" / "rules.yar"
    target = release / "scan" / "target.bin"
    expected_json = release / "scan" / "expected.json"
    rules.parent.mkdir()
    rules.write_text(
        'rule R1 {\n strings:\n  $a = "AxiomCompat"\n condition:\n  $a\n}\n',
        encoding="utf-8",
    )
    payload = b"before AxiomCompat after"
    target.write_bytes(payload)
    schema_source = (
        Path(__file__).resolve().parent.parent
        / "docs"
        / "api"
        / "axiom-scan-report.schema.json"
    )
    schema_path = release / "schemas" / "axiom-scan-report.schema.json"
    schema_path.parent.mkdir(parents=True)
    shutil.copyfile(schema_source, schema_path)
    expected = {
        "schema_version": "1",
        "tool": "axiom-scan",
        "tool_version": "0.1.0",
        "rules_count": 1,
        "ok": True,
        "target": "target.bin",
        "target_sha256": _hash(target),
        "scanned_bytes": len(payload),
        "match_count": 1,
        "matches": [{
            "rule": "R1",
            "tags": [],
            "meta": {},
            "pattern": "$a",
            "offset": payload.index(b"AxiomCompat"),
            "length": len(b"AxiomCompat"),
        }],
    }
    expected_json.write_text(json.dumps(expected, separators=(",", ":")) + "\n", encoding="utf-8")
    _write_manifest(
        release,
        "1.0.0",
        scanner_schemas=[{
            "id": "report-v1",
            "path": "schemas/axiom-scan-report.schema.json",
            "sha256": _hash(schema_path),
        }],
        scanner_cases=[{
            "id": "single-match",
            "rules": "scan/rules.yar",
            "rules_sha256": _hash(rules),
            "target": "scan/target.bin",
            "target_sha256": _hash(target),
            "expected_json": "scan/expected.json",
            "expected_json_sha256": _hash(expected_json),
            "schema_id": "report-v1",
            "backends": ["c", "llvm"],
            "exit_code": 0,
        }],
    )

    manifest = compatibility.load_manifest(release)
    assert compatibility.run_release(release, manifest) == 1


def test_scanner_fixture_rejects_schema_hash_mismatch(tmp_path):
    release = _release_dir(tmp_path, "1.0.0")
    _manifest, schema_path, _expected_json = _write_scanner_fixture(release)
    schema_path.write_text('{"type":"boolean"}\n', encoding="utf-8")
    with pytest.raises(compatibility.FixtureError, match="scanner schema hash mismatch"):
        compatibility.load_manifest(release)


def test_scanner_fixture_rejects_unknown_schema_reference(tmp_path):
    release = _release_dir(tmp_path, "1.0.0")
    manifest, _schema_path, _expected_json = _write_scanner_fixture(release)
    manifest["scanner_cases"][0]["schema_id"] = "missing-schema"
    (release / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    with pytest.raises(compatibility.FixtureError, match="unknown scanner schema"):
        compatibility.load_manifest(release)


def test_scanner_fixture_rejects_invalid_schema_and_expected_report(tmp_path):
    release = _release_dir(tmp_path, "1.0.0")
    _write_scanner_fixture(release, schema={"type": 42})
    with pytest.raises(compatibility.FixtureError, match="not valid Draft 2020-12"):
        compatibility.load_manifest(release)

    release = _release_dir(tmp_path, "1.0.1")
    _write_scanner_fixture(
        release, version="1.0.1",
        expected_report={"target": 42, "tool_version": "1.0.0"},
    )
    with pytest.raises(compatibility.FixtureError, match="expected_json does not validate"):
        compatibility.load_manifest(release)


def test_scanner_actual_report_must_validate_against_historical_schema(tmp_path, monkeypatch):
    release = _release_dir(tmp_path, "1.0.0")
    _manifest, _schema_path, _expected_json = _write_scanner_fixture(
        release,
        schema={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": ["target", "tool_version"],
            "properties": {
                "target": {"type": "string"},
                "tool_version": {"type": "string"},
            },
        },
    )
    monkeypatch.setattr(
        compatibility, "_build_scanner", lambda _backend, _temporary: Path("fake-scanner")
    )

    def fake_run(argv, **_kwargs):
        output = json.dumps({
            "target": "target.bin",
            "tool_version": "1.0.0",
            "new_unversioned_field": True,
        })
        return compatibility.subprocess.CompletedProcess(argv, 0, output, "")

    monkeypatch.setattr(compatibility, "_run", fake_run)
    manifest = compatibility.load_manifest(release)
    with pytest.raises(compatibility.FixtureError, match="actual report does not validate"):
        compatibility.run_release(release, manifest)


def test_fixture_hash_mismatch_and_path_escape_are_rejected(tmp_path):
    release = _release_dir(tmp_path, "1.0.0")
    source = release / "hello.ax"
    source.write_text("fn main() -> int { return 0; }\n", encoding="utf-8")
    _write_manifest(
        release,
        "1.0.0",
        source_examples=[{
            "id": "hello",
            "source": "hello.ax",
            "sha256": "0" * 64,
            "backends": ["c"],
            "stdout": "",
            "exit_code": 0,
        }],
    )
    with pytest.raises(compatibility.FixtureError, match="hash mismatch"):
        compatibility.load_manifest(release)
    with pytest.raises(compatibility.FixtureError, match="safe relative path"):
        compatibility._safe_path(release, "../outside.ax")


def test_release_directory_symlink_cannot_escape_fixture_root(tmp_path):
    fixture_root = tmp_path / "fixtures"
    fixture_root.mkdir()
    outside = tmp_path / "outside-release"
    outside.mkdir()
    _write_manifest(outside, "1.0.0")
    (fixture_root / "v1.0.0").symlink_to(outside, target_is_directory=True)

    with pytest.raises(compatibility.FixtureError, match="real directory inside fixture root"):
        compatibility.load_releases(fixture_root)


def test_alpha_current_tree_passes_without_unavailable_1x_history(tmp_path, capsys):
    assert compatibility.main([
        "--fixtures", str(tmp_path), "--current-version", "0.5.0a0"
    ]) == 0
    assert "No previous-two-minor fixture gate applies" in capsys.readouterr().out


def test_tagged_release_requires_its_own_committed_fixture(tmp_path):
    assert compatibility.main([
        "--fixtures", str(tmp_path),
        "--current-version", "1.0.0",
        "--require-current-release",
    ]) == 1


def test_alpha_tag_does_not_require_a_stable_release_fixture(tmp_path, capsys):
    assert compatibility.main([
        "--fixtures", str(tmp_path),
        "--current-version", "0.5.0a0",
        "--require-current-release",
    ]) == 0
    assert "No previous-two-minor fixture gate applies" in capsys.readouterr().out


def test_tagged_release_must_match_package_version(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_REF_TYPE", "tag")
    monkeypatch.setenv("GITHUB_REF_NAME", "v1.0.0")
    assert compatibility.main([
        "--fixtures", str(tmp_path),
        "--current-version", "1.1.0",
        "--require-current-release",
    ]) == 1
    assert "does not match package version" in capsys.readouterr().err
