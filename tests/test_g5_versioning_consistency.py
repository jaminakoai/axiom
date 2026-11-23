"""Keep active G5 versioning and user-validation claims aligned."""

import re
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
