"""Guard the Registry guide against implying that the public endpoint is live."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REGISTRY_GUIDE = ROOT / "docs" / "REGISTRY.md"


def test_registry_guide_marks_default_host_as_not_deployed():
    text = REGISTRY_GUIDE.read_text(encoding="utf-8")

    assert "registry.axiom-lang.org` henüz dağıtılmamıştır" in text
    assert "`DEFAULT_REGISTRY`" in text
    assert 'url = "https://registry.axiom-lang.org" # henüz dağıtılmadı' in text


def test_registry_guide_documents_local_file_registry_round_trip():
    text = REGISTRY_GUIDE.read_text(encoding="utf-8")

    for required in (
        "pack --signing-key",
        "registry assemble --from",
        "AXIOM_REGISTRY=",
        "AXIOM_REGISTRY_KEY=",
        "add axiom-scan-report --version 0.1.0",
        "install",
        "test",
        "`2/2 test başarılı`",
        "`index.json` için imza üretmez",
    ):
        assert required in text, f"docs/REGISTRY.md eksik: {required}"


def test_registry_guide_states_index_binding_and_unsigned_index_limits():
    text = " ".join(REGISTRY_GUIDE.read_text(encoding="utf-8").split())

    for required in (
        "İmzalı manifest adı/sürümü ve bağımlılıkları index kaydıyla eşleşmelidir",
        "`index.json` Registry v1'de imzalanmaz",
        "`yanked` değeri değiştirilebilir",
        "eski ama",
        "rollback/freshness korumalı",
        "test_download_rejects_unsigned_index_metadata_mismatch",
    ):
        assert required in text, f"docs/REGISTRY.md güven sınırı eksik: {required}"
