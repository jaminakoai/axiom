"""Regression checks for the external user validation guide."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "docs" / "EXTERNAL_VALIDATION.md"


def _read_guide():
    return GUIDE.read_text(encoding="utf-8")


def test_external_validation_links_resolve_from_guide_and_readmes():
    guide = _read_guide()
    relative_targets = re.findall(r"\]\((?!https?://|#)([^)#]+)", guide)
    assert relative_targets
    for target in relative_targets:
        assert (GUIDE.parent / target).resolve().is_file(), target

    for readme in (ROOT / "README.md", ROOT / "README.en.md"):
        text = readme.read_text(encoding="utf-8")
        targets = re.findall(r"\]\((?!https?://|#)([^)#]+)", text)
        assert "docs/EXTERNAL_VALIDATION.md" in targets
        for target in targets:
            assert (ROOT / target).resolve().exists(), f"{readme.name}: {target}"


def test_smoke_instructions_and_expected_result_are_documented_in_both_languages():
    guide = _read_guide()
    assert "## 5 dakikalık kurulum ve zararsız duman testi / Five-minute setup and smoke test" in guide
    assert "git rev-parse HEAD" in guide
    assert "python -m pip install -e ." in guide
    assert "axiom build examples/21_axiom_scan.ax -o /tmp/axiom-scan" in guide
    assert "/tmp/axiom-scan rules /tmp/axiom-external.yar" in guide
    assert "/tmp/axiom-scan scan /tmp/axiom-external.txt --rules /tmp/axiom-external.yar" in guide
    assert '"match_count":1' in guide
    assert "Eşleşme ofseti 36, uzunluğu 37 olur." in guide
    assert "The match offset is 36 and its length is 37." in guide


def test_feedback_routing_separates_public_usability_from_security_reports():
    guide = _read_guide()
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")

    assert "https://github.com/jaminakoai/axiom/issues/new" in guide
    assert "güvenlik açığı şüphesi olmayan" in guide.lower()
    assert "do not open a public issue" in guide
    assert "../SECURITY.md" in guide
    assert "**Lütfen herkese açık issue açmayın.**" in security
    assert "security@axiom-lang.org" in security
    assert "kamuya açık kullanılmasına izin vermiyorsanız public issue" in guide
    assert "first agree on an appropriate private channel" in guide


def test_public_feedback_template_does_not_request_private_artifacts():
    guide = _read_guide()
    template = guide.split("```text\n", maxsplit=1)[1].split("\n```", maxsplit=1)[0]

    for instruction in (
        "Ham dosya/PCAP",
        "paket içeriği",
        "kimlik bilgisi",
        "kişisel veri",
        "Never attach a raw file/PCAP",
        "packet contents",
        "credentials",
        "personal data",
    ):
        assert instruction in guide

    assert "SHA-256 (varsayılan boş" in template
    assert "SHA-256 can identify a file" in guide
    assert "Komut (tam yolları ve gizli değerleri maskeleyin" in template
    assert "Command (redact full paths and secrets)" in template
    assert "Can the maintainer use this report in a public issue?" not in template
    assert "Kamuya açık issue olarak paylaşılmasına izin var mı?" in template
