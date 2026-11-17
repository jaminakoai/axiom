"""Guard the Registry guide against implying that the public endpoint is live."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REGISTRY_GUIDE = ROOT / "docs" / "REGISTRY.md"
REGISTRY_OPERATIONS = ROOT / "docs" / "REGISTRY_OPERATIONS.md"


def test_registry_guide_documents_official_default_and_bundled_trust_anchors():
    text = REGISTRY_GUIDE.read_text(encoding="utf-8")

    assert "https://jaminakoai.github.io/axiom/registry" in text
    assert "`DEFAULT_REGISTRY`" in text
    assert "paket/index açık anahtarları" in text


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
        "--index-signing-key",
        "--index-sequence",
        "--index-expires",
        "AXIOM_REGISTRY_INDEX_KEY",
        "ilk bağlantıda en yeni index'in sunulduğunu kanıtlamaz",
    ):
        assert required in text, f"docs/REGISTRY.md eksik: {required}"


def test_registry_guide_states_index_binding_and_unsigned_index_limits():
    text = " ".join(REGISTRY_GUIDE.read_text(encoding="utf-8").split())

    for required in (
        "İmzalı manifest adı/sürümü ve bağımlılıkları index kaydıyla eşleşmelidir",
        "Registry v1 `index.json` imzasızdır",
        "`yanked` değeri değiştirilebilir",
        "eski ama",
        "ilk bağlantı veya yerel state silindikten sonraki eski index",
        "test_download_rejects_unsigned_index_metadata_mismatch",
    ):
        assert required in text, f"docs/REGISTRY.md güven sınırı eksik: {required}"


def test_registry_guide_documents_offline_pages_snapshot_preparation():
    text = REGISTRY_GUIDE.read_text(encoding="utf-8")

    for required in (
        "Yayın kaynağını offline hazırlama",
        '"$SOURCE/registry"',
        "--index-signing-key",
        "--index-sequence",
        "--index-expires",
        'python -m axiom.registry_pages --source "$SOURCE"',
        'cp -a "$SOURCE" "$REPO_ROOT/registry-site"',
        "özel anahtarları depoya",
        "Bu adım yalnızca yerel snapshot hazırlar",
    ):
        assert required in text, f"docs/REGISTRY.md eksik: {required}"


def test_registry_key_operations_document_backup_and_rotation_limitations():
    text = " ".join(REGISTRY_OPERATIONS.read_text(encoding="utf-8").split())

    for required in (
        "registry-key-backups/registry-signing-keys-2026-11-17.tar.age",
        "same machine as the source keys",
        "staged client release that overlaps old and new anchors",
        "up to eight package and index trust anchors",
        "do not rotate as a cleanup step",
        "The signed index sequence detects rollback",
    ):
        assert required in text, f"docs/REGISTRY_OPERATIONS.md eksik: {required}"
