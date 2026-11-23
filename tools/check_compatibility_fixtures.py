#!/usr/bin/env python3
"""Validate and run immutable compatibility fixtures from prior Axiom releases."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "api_compatibility" / "releases"
AXIOM = ROOT / "bin" / "axiom"
AXPM = ROOT / "bin" / "axpm"
SCANNER_SOURCE = ROOT / "examples" / "21_axiom_scan.ax"
SUPPORTED_BACKENDS = {"c", "llvm"}
HEX_256 = re.compile(r"^[0-9a-f]{64}$")
CASE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
STABLE_RELEASE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
CURRENT_RELEASE = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+)|-(alpha|beta|rc)(?:\.?(\d+))?)?$"
)


class FixtureError(ValueError):
    pass


def current_project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"\n]+)"', text)
    if not match:
        raise FixtureError("pyproject.toml has no static project version")
    return match.group(1)


def version_parts(version: str) -> tuple[int, int, int]:
    match = CURRENT_RELEASE.fullmatch(version)
    if not match:
        raise FixtureError(f"unsupported Axiom version format: {version!r}")
    return tuple(int(part) for part in match.groups()[:3])


def canonical_version(version: str) -> str:
    stable = STABLE_RELEASE.fullmatch(version)
    if stable:
        return version
    match = CURRENT_RELEASE.fullmatch(version)
    if not match:
        raise FixtureError(f"unsupported Axiom version format: {version!r}")
    major, minor, patch = match.groups()[:3]
    marker, number = match.group(4), match.group(5)
    label, label_number = match.group(6), match.group(7)
    if marker:
        label = {"a": "alpha", "b": "beta", "rc": "rc"}[marker]
        label_number = number
    suffix = f".{label_number}" if label_number and label_number != "0" else ""
    return f"{major}.{minor}.{patch}-{label}{suffix}" if label else f"{major}.{minor}.{patch}"


def required_minor_lines(version: str) -> list[tuple[int, int]]:
    major, minor, _ = version_parts(version)
    if major == 0 or minor < 2:
        return []
    return [(major, minor - 1), (major, minor - 2)]


def _safe_path(root: Path, relative: str, *, want_dir: bool = False) -> Path:
    if not isinstance(relative, str) or not relative:
        raise FixtureError("fixture paths must be non-empty strings")
    path_part = PurePosixPath(relative)
    if path_part.is_absolute() or ".." in path_part.parts or "\\" in relative:
        raise FixtureError(f"fixture path must be a safe relative path: {relative!r}")
    root = root.resolve()
    path = (root / Path(*path_part.parts)).resolve(strict=True)
    if not path.is_relative_to(root):
        raise FixtureError(f"fixture path escapes its release directory: {relative!r}")
    if want_dir and not path.is_dir():
        raise FixtureError(f"fixture directory does not exist: {relative!r}")
    if not want_dir and not path.is_file():
        raise FixtureError(f"fixture file does not exist: {relative!r}")
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*"), key=lambda candidate: candidate.relative_to(path).as_posix()):
        if item.is_symlink():
            raise FixtureError(f"package fixture may not contain symlinks: {item}")
        if not item.is_file():
            continue
        relative = item.relative_to(path).as_posix().encode("utf-8")
        content = item.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _require_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HEX_256.fullmatch(value):
        raise FixtureError(f"{label} must be a lowercase SHA-256 hex digest")
    return value


def _validate_backends(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise FixtureError(f"{label}.backends must be a non-empty list")
    if any(not isinstance(backend, str) or backend not in SUPPORTED_BACKENDS for backend in value):
        raise FixtureError(f"{label}.backends may contain only {sorted(SUPPORTED_BACKENDS)}")
    if len(set(value)) != len(value):
        raise FixtureError(f"{label}.backends may not contain duplicates")
    return value


def load_manifest(release_dir: Path) -> dict[str, Any]:
    from jsonschema import ValidationError

    manifest_path = _safe_path(release_dir, "manifest.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureError(f"cannot read {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise FixtureError(f"{manifest_path} must contain a JSON object")
    required = {
        "schema_version", "release", "source_examples", "package_projects",
        "scanner_schemas", "scanner_cases",
    }
    if set(manifest) != required:
        raise FixtureError(
            f"{manifest_path} keys must be exactly {sorted(required)}; got {sorted(manifest)}"
        )
    if (
        not isinstance(manifest["schema_version"], int)
        or isinstance(manifest["schema_version"], bool)
        or manifest["schema_version"] != 2
    ):
        raise FixtureError(f"unsupported fixture manifest schema: {manifest['schema_version']!r}")
    release = manifest["release"]
    match = STABLE_RELEASE.fullmatch(release) if isinstance(release, str) else None
    if not match:
        raise FixtureError("fixture release must be a stable MAJOR.MINOR.PATCH version")
    canonical_release = ".".join(match.groups())
    if release_dir.name != f"v{canonical_release}":
        raise FixtureError(
            f"release directory must be v{canonical_release}, got {release_dir.name!r}"
        )
    for group in ("source_examples", "package_projects", "scanner_schemas", "scanner_cases"):
        if not isinstance(manifest[group], list):
            raise FixtureError(f"{group} must be a list")
    if not any(manifest[group] for group in ("source_examples", "package_projects", "scanner_cases")):
        raise FixtureError("a release fixture manifest must contain at least one case")

    case_ids: set[str] = set()
    scanner_schemas: dict[str, Any] = {}
    for item in manifest["scanner_schemas"]:
        _validate_case_id(item, case_ids, "scanner_schemas")
        if set(item) != {"id", "path", "sha256"}:
            raise FixtureError(f"scanner schema {item['id']} has an invalid shape")
        scanner_schemas[item["id"]] = _load_report_schema(release_dir, item)

    for item in manifest["source_examples"]:
        _validate_case_id(item, case_ids, "source_examples")
        if set(item) != {"id", "source", "sha256", "backends", "stdout", "exit_code"}:
            raise FixtureError(f"source example {item['id']} has an invalid shape")
        source = _safe_path(release_dir, item["source"])
        _require_hash(item["sha256"], f"source example {item['id']}.sha256")
        if sha256_file(source) != item["sha256"]:
            raise FixtureError(f"source example hash mismatch: {item['id']}")
        _validate_backends(item["backends"], f"source example {item['id']}")
        _validate_expectations(item, f"source example {item['id']}")

    for item in manifest["package_projects"]:
        _validate_case_id(item, case_ids, "package_projects")
        if set(item) != {"id", "root", "tree_sha256", "entry", "backends", "stdout", "exit_code"}:
            raise FixtureError(f"package project {item['id']} has an invalid shape")
        package_root = _safe_path(release_dir, item["root"], want_dir=True)
        _require_hash(item["tree_sha256"], f"package project {item['id']}.tree_sha256")
        if sha256_tree(package_root) != item["tree_sha256"]:
            raise FixtureError(f"package project tree hash mismatch: {item['id']}")
        _safe_path(package_root, item["entry"])
        if not (package_root / "axiom.toml").is_file() or not (package_root / "axiom.lock").is_file():
            raise FixtureError(f"package project {item['id']} must contain axiom.toml and axiom.lock")
        _validate_backends(item["backends"], f"package project {item['id']}")
        _validate_expectations(item, f"package project {item['id']}")

    for item in manifest["scanner_cases"]:
        _validate_case_id(item, case_ids, "scanner_cases")
        expected_keys = {
            "id", "rules", "rules_sha256", "target", "target_sha256",
            "expected_json", "expected_json_sha256", "schema_id", "backends", "exit_code",
        }
        if set(item) != expected_keys:
            raise FixtureError(f"scanner case {item['id']} has an invalid shape")
        schema_id = item["schema_id"]
        if not isinstance(schema_id, str) or not CASE_ID.fullmatch(schema_id):
            raise FixtureError(f"scanner case {item['id']}.schema_id is invalid")
        for path_field, hash_field in (
            ("rules", "rules_sha256"),
            ("target", "target_sha256"),
            ("expected_json", "expected_json_sha256"),
        ):
            path = _safe_path(release_dir, item[path_field])
            _require_hash(item[hash_field], f"scanner case {item['id']}.{hash_field}")
            if sha256_file(path) != item[hash_field]:
                raise FixtureError(f"scanner case {item['id']} hash mismatch: {path_field}")
        try:
            expected = json.loads(_safe_path(release_dir, item["expected_json"]).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FixtureError(f"scanner case {item['id']} expected_json is invalid JSON") from exc
        if not isinstance(expected, dict):
            raise FixtureError(f"scanner case {item['id']} expected_json must be an object")
        schema_validator = scanner_schemas.get(schema_id)
        if schema_validator is None:
            raise FixtureError(
                f"scanner case {item['id']} references an unknown scanner schema: "
                f"{schema_id!r}"
            )
        try:
            schema_validator.validate(expected)
        except ValidationError as exc:
            raise FixtureError(
                f"scanner case {item['id']} expected_json does not validate against "
                f"schema {schema_id}: {exc.message}"
            ) from exc
        _validate_backends(item["backends"], f"scanner case {item['id']}")
        if not isinstance(item["exit_code"], int) or isinstance(item["exit_code"], bool):
            raise FixtureError(f"scanner case {item['id']}.exit_code must be an integer")

    referenced_schemas = {item["schema_id"] for item in manifest["scanner_cases"]}
    if set(scanner_schemas) != referenced_schemas:
        raise FixtureError("scanner schema fixtures must be referenced by scanner cases")

    return manifest


def _load_report_schema(release_dir: Path, item: dict[str, Any]) -> Any:
    from jsonschema import Draft202012Validator, SchemaError

    schema_path = _safe_path(release_dir, item["path"])
    _require_hash(item["sha256"], f"scanner schema {item['id']}.sha256")
    if sha256_file(schema_path) != item["sha256"]:
        raise FixtureError(f"scanner schema hash mismatch: {item['id']}")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureError(f"scanner schema {item['id']} is invalid JSON: {exc}") from exc
    if not isinstance(schema, dict):
        raise FixtureError(f"scanner schema {item['id']} must be a JSON object")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise FixtureError(f"scanner schema {item['id']} is not valid Draft 2020-12: {exc.message}") from exc
    return Draft202012Validator(schema)


def _validate_case_id(item: Any, ids: set[str], group: str) -> None:
    if (
        not isinstance(item, dict)
        or not isinstance(item.get("id"), str)
        or not CASE_ID.fullmatch(item["id"])
    ):
        raise FixtureError(f"each {group} case must have a valid lowercase id")
    if item["id"] in ids:
        raise FixtureError(f"duplicate fixture case id: {item['id']}")
    ids.add(item["id"])


def _validate_expectations(item: dict[str, Any], label: str) -> None:
    if not isinstance(item["stdout"], str):
        raise FixtureError(f"{label}.stdout must be a string")
    if not isinstance(item["exit_code"], int) or isinstance(item["exit_code"], bool):
        raise FixtureError(f"{label}.exit_code must be an integer")


def _environment() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{ROOT}{os.pathsep}{existing}" if existing else str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run(argv: list[str], *, cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv, cwd=cwd, env=_environment(), capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FixtureError(f"fixture command timed out after {timeout}s: {' '.join(argv)}") from exc


def _check_process(result: subprocess.CompletedProcess[str], expected_code: int, expected_stdout: str, label: str) -> None:
    if result.returncode != expected_code or result.stdout != expected_stdout:
        raise FixtureError(
            f"{label} differs: expected exit/stdout {expected_code}/{expected_stdout!r}, "
            f"got {result.returncode}/{result.stdout!r}; stderr={result.stderr!r}"
        )


def _build_and_run(source: Path, backend: str, expected_stdout: str, expected_code: int, label: str, cwd: Path | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix="axiom-compat-") as temporary:
        output = Path(temporary) / ("fixture.exe" if os.name == "nt" else "fixture")
        build = _run([
            str(AXIOM), "build", str(source), "--backend", backend,
            "--output", str(output),
        ], cwd=cwd)
        if build.returncode != 0:
            raise FixtureError(f"{label} {backend} build failed: {build.stdout}{build.stderr}")
        run = _run([str(output)], cwd=cwd, timeout=120)
        _check_process(run, expected_code, expected_stdout, f"{label} ({backend})")


def _run_source_case(release_dir: Path, item: dict[str, Any]) -> None:
    source = _safe_path(release_dir, item["source"])
    for backend in item["backends"]:
        _build_and_run(
            source, backend, item["stdout"], item["exit_code"],
            f"{release_dir.name}/{item['id']}", cwd=release_dir,
        )


def _run_package_case(release_dir: Path, item: dict[str, Any]) -> None:
    source_root = _safe_path(release_dir, item["root"], want_dir=True)
    with tempfile.TemporaryDirectory(prefix="axiom-compat-package-") as temporary:
        package_root = Path(temporary) / "package"
        shutil.copytree(source_root, package_root)
        verified = _run([str(AXPM), "verify"], cwd=package_root)
        if verified.returncode != 0:
            raise FixtureError(
                f"{release_dir.name}/{item['id']} lock verification failed: "
                f"{verified.stdout}{verified.stderr}"
            )
        entry = _safe_path(package_root, item["entry"])
        for backend in item["backends"]:
            if backend == "c":
                from axiom.package_manager import PackageManager

                try:
                    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                        output = PackageManager(package_root).build(release=False)
                except Exception as exc:
                    raise FixtureError(
                        f"{release_dir.name}/{item['id']} package-manager C build failed: {exc}"
                    ) from exc
                run = _run([str(output)], cwd=package_root, timeout=120)
                _check_process(
                    run, item["exit_code"], item["stdout"],
                    f"{release_dir.name}/{item['id']} (axpm/C)",
                )
                continue
            _build_and_run(
                entry, backend, item["stdout"], item["exit_code"],
                f"{release_dir.name}/{item['id']}", cwd=package_root,
            )


def _build_scanner(backend: str, temporary: Path) -> Path:
    output = temporary / (f"axiom-scan-{backend}.exe" if os.name == "nt" else f"axiom-scan-{backend}")
    build = _run([
        str(AXIOM), "build", str(SCANNER_SOURCE), "--backend", backend,
        "--output", str(output),
    ])
    if build.returncode != 0:
        raise FixtureError(f"axiom-scan {backend} build failed: {build.stdout}{build.stderr}")
    return output


def _run_scanner_case(
    release_dir: Path, item: dict[str, Any], scanner: Path, schema_validator: Any
) -> None:
    from jsonschema import ValidationError

    target = _safe_path(release_dir, item["target"])
    rules = _safe_path(release_dir, item["rules"])
    expected_path = _safe_path(release_dir, item["expected_json"])
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    result = _run([
        str(scanner), "scan", str(target), "--rules", str(rules),
    ], timeout=120)
    if result.returncode != item["exit_code"]:
        raise FixtureError(
            f"{release_dir.name}/{item['id']} scanner exit code differs: "
            f"{result.returncode}; {result.stdout}{result.stderr}"
        )
    try:
        actual = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise FixtureError(f"{release_dir.name}/{item['id']} scanner returned invalid JSON") from exc
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        raise FixtureError(f"{release_dir.name}/{item['id']} scanner JSON must be objects")
    for label, report in (("actual", actual), ("expected", expected)):
        try:
            schema_validator.validate(report)
        except ValidationError as exc:
            raise FixtureError(
                f"{release_dir.name}/{item['id']} {label} report does not validate "
                f"against schema {item['schema_id']}: {exc.message}"
            ) from exc
    actual = dict(actual)
    expected = dict(expected)
    for report in (actual, expected):
        if not isinstance(report.get("target"), str) or not isinstance(report.get("tool_version"), str):
            raise FixtureError(
                f"{release_dir.name}/{item['id']} scanner JSON lacks target/tool_version strings"
            )
    actual["target"] = Path(actual["target"]).name
    expected["target"] = Path(expected["target"]).name
    # Paths vary with the checkout/temp directory and tool versions intentionally
    # advance. Check their presence/types above; compare the stable report contract.
    actual.pop("tool_version")
    expected.pop("tool_version")
    if actual != expected:
        raise FixtureError(
            f"{release_dir.name}/{item['id']} scanner JSON differs:\n"
            f"expected={json.dumps(expected, sort_keys=True, ensure_ascii=False)}\n"
            f"actual={json.dumps(actual, sort_keys=True, ensure_ascii=False)}"
        )


def load_releases(
    fixture_root: Path,
) -> list[tuple[Path, dict[str, Any], tuple[int, int, int]]]:
    if not fixture_root.exists():
        return []
    if not fixture_root.is_dir():
        raise FixtureError(f"fixture root is not a directory: {fixture_root}")
    resolved_root = fixture_root.resolve(strict=True)
    releases = []
    for release_dir in sorted(fixture_root.glob("v*")):
        if not release_dir.is_dir():
            continue
        try:
            resolved_release_dir = release_dir.resolve(strict=True)
        except OSError as exc:
            raise FixtureError(f"cannot resolve release fixture directory: {release_dir}") from exc
        if release_dir.is_symlink() or not resolved_release_dir.is_relative_to(resolved_root):
            raise FixtureError(
                f"release fixture directory must be a real directory inside fixture root: {release_dir}"
            )
        manifest = load_manifest(release_dir)
        major, minor, patch = version_parts(manifest["release"])
        releases.append((release_dir, manifest, (major, minor, patch)))
    return releases


def select_required_releases(
    version: str, releases: list[tuple[Path, dict[str, Any], tuple[int, int, int]]]
) -> list[tuple[Path, dict[str, Any], tuple[int, int, int]]]:
    required = required_minor_lines(version)
    selected = []
    missing = []
    for major, minor in required:
        candidates = [item for item in releases if item[2][:2] == (major, minor)]
        if not candidates:
            missing.append(f"{major}.{minor}.x")
        else:
            selected.append(max(candidates, key=lambda item: item[2][2]))
    if missing:
        raise FixtureError(
            f"compatibility gate for {version} requires release fixtures for: {', '.join(missing)}"
        )
    return selected


def select_current_release(
    version: str, releases: list[tuple[Path, dict[str, Any], tuple[int, int, int]]]
) -> tuple[Path, dict[str, Any], tuple[int, int, int]]:
    match = STABLE_RELEASE.fullmatch(version)
    if not match:
        raise FixtureError("a tag build must use a stable MAJOR.MINOR.PATCH package version")
    wanted = tuple(int(part) for part in match.groups())
    for release in releases:
        if release[2] == wanted:
            return release
    raise FixtureError(f"release tag {version} requires its own v{version} fixture")


def run_release(release_dir: Path, manifest: dict[str, Any]) -> int:
    case_count = 0
    for item in manifest["source_examples"]:
        _run_source_case(release_dir, item)
        case_count += 1
    for item in manifest["package_projects"]:
        _run_package_case(release_dir, item)
        case_count += 1
    if manifest["scanner_cases"]:
        schema_items = {item["id"]: item for item in manifest["scanner_schemas"]}
        schema_validators = {
            schema_id: _load_report_schema(release_dir, schema_item)
            for schema_id, schema_item in schema_items.items()
        }
        with tempfile.TemporaryDirectory(prefix="axiom-compat-scanner-") as temporary_name:
            temporary = Path(temporary_name)
            scanners: dict[str, Path] = {}
            for item in manifest["scanner_cases"]:
                for backend in item["backends"]:
                    scanner = scanners.get(backend)
                    if scanner is None:
                        scanner = _build_scanner(backend, temporary)
                        scanners[backend] = scanner
                    _run_scanner_case(
                        release_dir, item, scanner, schema_validators[item["schema_id"]]
                    )
                case_count += 1
    return case_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURE_ROOT)
    parser.add_argument("--current-version", default=current_project_version())
    parser.add_argument(
        "--require-current-release",
        action="store_true",
        help="require and execute the fixture for the stable version being tagged",
    )
    args = parser.parse_args(argv)
    try:
        if args.require_current_release and os.environ.get("GITHUB_REF_TYPE") == "tag":
            tag_name = os.environ.get("GITHUB_REF_NAME", "")
            tag_version = tag_name[1:] if tag_name.startswith("v") else tag_name
            if canonical_version(tag_version) != canonical_version(args.current_version):
                raise FixtureError(
                    f"release tag {tag_name!r} does not match package version "
                    f"{args.current_version!r}"
                )
        releases = load_releases(args.fixtures)
        selected = select_required_releases(args.current_version, releases)
        if (
            args.require_current_release
            and version_parts(args.current_version)[0] >= 1
            and STABLE_RELEASE.fullmatch(args.current_version)
        ):
            current = select_current_release(args.current_version, releases)
            selected = [release for release in selected if release[0] != current[0]] + [current]
        if not selected:
            print(
                f"No previous-two-minor fixture gate applies to Axiom {args.current_version}; "
                f"validated {len(releases)} available release fixture(s)."
            )
            return 0
        total = 0
        for release_dir, manifest, _version in selected:
            count = run_release(release_dir, manifest)
            total += count
            print(f"✓ {manifest['release']}: {count} compatibility case(s) passed")
        print(f"✓ compatibility gate passed: {total} case(s), current {args.current_version}")
        return 0
    except (FixtureError, OSError) as exc:
        print(f"compatibility fixture error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
