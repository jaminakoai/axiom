"""Keep active G5 versioning and user-validation claims aligned."""

import re
import ast
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _normalized(relative: str) -> str:
    return " ".join(_read(relative).split())


def test_external_user_trial_is_optional_in_active_versioning_docs():
    versioning = _normalized("docs/VERSIONING.md")
    proposal = _normalized("docs/G5_API_STABILITY_PROPOSAL.md")
    validation = _normalized("docs/EXTERNAL_VALIDATION.md")

    assert "isteğe bağlı ürün geri bildirimi" in versioning
    assert "not a technical `v1.0` gate" in versioning
    assert "isteğe bağlı ürün geri bildirimi" in proposal
    assert "optional product feedback, not a `v1.0` technical gate" in proposal
    assert "isteğe bağlıdır" in validation
    assert "remains optional" in validation


def test_two_minor_compatibility_policy_is_explicit_and_bilingual():
    versioning = _normalized("docs/VERSIONING.md")
    proposal = _normalized("docs/G5_API_STABILITY_PROPOSAL.md")

    assert "en az iki sonraki minor" in versioning
    assert "previous two minor releases" in versioning
    assert "önceki iki minor sürüm" in proposal
    assert "previous two minor releases" in proposal
    assert "yalnız iki eski sürümünün desteklenmesi anlamına gelmez" in proposal
    assert "does not mean supporting only two old versions" in proposal
    assert "while preparing `v1.2`" in proposal
    assert "v1.0` and `v1.1` baselines" in proposal
    assert "while preparing `v1.2`" in versioning.lower()


def test_readmes_describe_remaining_v1_inventory_and_fixture_work():
    readme_tr = _normalized("README.md")
    readme_en = _normalized("README.en.md")

    assert "somut API envanteri" in readme_tr
    assert "uyumluluk" in readme_tr
    assert "Concrete API inventory" in readme_en
    assert "previous two minor releases" in readme_en
    assert "G5_API_STABILITY_PROPOSAL.md" in readme_tr
    assert "G5_API_STABILITY_PROPOSAL.md" in readme_en


def test_inventory_records_real_stdlib_and_abi_boundaries():
    policy = _normalized("docs/G5_API_STABILITY_PROPOSAL.md")

    assert "53 `std/**/*.ax`" in policy
    assert "`pub`/`export`" in policy
    assert "`Result<T, E>`" in policy
    assert "`ResultInt`" in policy
    assert "`ResultStr`" in policy
    assert "A symbol's presence in `std/` alone does not promise stability" in policy
    assert "only per fully specified target" in policy


def test_spec_builtin_raw_counts_match_checker_without_claiming_stability():
    checker = ast.parse(_read("axiom/checker.py"))
    builtin_map = next(
        ast.literal_eval(node.value)
        for node in checker.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "BUILTIN_FUNCTIONS" for target in node.targets)
    )
    non_runtime = sum(not name.startswith("rt_") for name in builtin_map)
    runtime_aliases = len(builtin_map) - non_runtime
    assert (len(builtin_map), non_runtime, runtime_aliases) == (358, 111, 247)

    for relative in ("SPECIFICATION.md", "docs/en/SPECIFICATION.md"):
        spec = _normalized(relative)
        assert "111" in spec
        assert "247" in spec
        if relative == "SPECIFICATION.md":
            assert "tamamlanmış bir" in spec
        else:
            assert "not a complete user-facing API catalog" in spec
    proposal = _normalized("docs/G5_API_STABILITY_PROPOSAL.md")
    assert "247'si `rt_*` önekli" in proposal
    assert "`rt_*` burada gizli API anlamına gelmiyor" in proposal


def test_generated_api_inventory_matches_current_source():
    result = subprocess.run(
        ["python", "tools/generate_api_inventory.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    snapshot = json.loads(_read("docs/api/v0.5.0-alpha.json"))
    rt_entry = next(
        entry for entry in snapshot["compiler_builtins"]
        if entry["name"] == "rt_str_len"
    )
    assert rt_entry["classification"] == "unclassified_checker_builtin"
    assert rt_entry["name_family"] == "rt_prefixed"


def test_rt_prefixed_checker_builtin_is_callable_from_axiom_source():
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "rt_builtin.ax"
        source.write_text(
            'fn main() -> int { return rt_str_len("x") - 1; }\n',
            encoding="utf-8",
        )
        result = subprocess.run(
            ["bin/axiom", "check", str(source)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    assert result.returncode == 0, result.stderr


def test_readme_stdlib_counts_match_the_source_tree():
    source_files = list((ROOT / "std").rglob("*.ax"))
    function_declarations = sum(
        len(re.findall(r"^\s*fn\s+[A-Za-z_][A-Za-z0-9_]*", path.read_text(encoding="utf-8"), re.M))
        for path in source_files
    )
    assert len(source_files) == 53
    assert function_declarations == 446

    assert "53 stdlib kaynak dosyası / 446 fonksiyon bildirimi" in _normalized("README.md")
    assert "53 standard-library source files / 446 function declarations" in _normalized("README.en.md")


def test_documented_cli_commands_and_flags_cover_installed_help():
    policy = _read("docs/G5_API_STABILITY_PROPOSAL.md")
    cli_table = policy.split(
        "### v0.5 CLI seçenekleri anlık envanteri", 1
    )[1].split("CLI tablosu komut", 1)[0]
    documented_rows = {}
    for line in cli_table.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        command = cells[0].strip("`")
        documented_rows[command] = set(
            re.findall(r"(?<!\w)--?[A-Za-z][A-Za-z0-9-]*", cells[1])
        )
    commands = [
        ["bin/axiom", "--help"],
        *[["bin/axiom", command, "--help"] for command in (
            "run", "build", "check", "prove", "emit-c", "emit-smt", "emit-llvm",
            "repl", "test", "init", "doc", "fmt", "pkg", "lsp",
        )],
        *[["bin/axpm", command, "--help"] for command in (
            "init", "add", "install", "verify", "tree", "remove", "search",
            "pack", "registry", "update", "build", "run", "test",
        )],
        ["bin/axpm", "registry", "assemble", "--help"],
    ]
    for argv in commands:
        result = subprocess.run(argv, capture_output=True, text=True, cwd=ROOT, check=False)
        assert result.returncode == 0, f"help failed: {' '.join(argv)}\n{result.stderr}"
        help_text = result.stdout + result.stderr
        help_options = set()
        for line in help_text.splitlines():
            # argparse option rows have a 2+ space separator before descriptions.
            column = line.strip().split("  ", 1)[0]
            for token in column.split():
                token = token.rstrip(",")
                if token.startswith("-") and re.fullmatch(r"--?[A-Za-z][A-Za-z0-9-]*", token):
                    help_options.add(token)
            if len(argv) > 2:
                # argparse adds help to every subcommand even though the
                # snapshot lists command-specific options separately.
                help_options.difference_update({"-h", "--help"})
        if argv[0] == "bin/axiom":
            key = "axiom" if len(argv) == 2 else f"axiom {argv[1]}"
        else:
            key = "axpm" if len(argv) == 2 else f"axpm {' '.join(argv[1:-1])}"
        assert key in documented_rows, f"missing CLI inventory row: {key}"
        assert help_options == documented_rows[key], (
            f"CLI option inventory differs for {key}: "
            f"help={sorted(help_options)}, docs={sorted(documented_rows[key])}"
        )


def test_scan_docs_match_schema_and_byte_buffer_behavior():
    readme_tr = _normalized("README.md")
    readme_en = _normalized("README.en.md")
    scan_source = _normalized("examples/21_axiom_scan.ax")

    expected_match = '"rule":"R1","tags":[],"meta":{},"pattern":"$a"'
    assert expected_match in readme_tr
    assert expected_match in readme_en
    assert "NUL sonrasindaki icerik de" in scan_source
    assert "taranir ve `scanned_bytes` tam dosya uzunlugudur" in scan_source
    assert "NUL bayti iceren dosya ILK NUL'da kesilir" not in scan_source
