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


def test_pcap_guidance_documents_format_limits_and_fail_closed_behavior():
    guide = _read_guide()
    normalized_guide = " ".join(guide.split())
    readmes = [
        (ROOT / "README.md").read_text(encoding="utf-8"),
        (ROOT / "README.en.md").read_text(encoding="utf-8"),
    ]
    for text in [guide, *readmes]:
        assert "classic PCAP" in text or "klasik PCAP" in text
        assert "pcapng" in text
        assert "truncated" in text.lower() or "kesik" in text.lower()
        assert "TCP" in text
    assert "Her kaydın yakalanmış baytları opak veri" in normalized_guide
    assert "Each record's captured bytes are scanned" in normalized_guide
    assert "linktype yok sayılır" in normalized_guide
    assert "linktype is ignored" in normalized_guide
    assert "Protokol çözümleme" in normalized_guide
    assert "protocol decoding" in normalized_guide


def test_feedback_routing_separates_public_usability_from_security_reports():
    guide = _read_guide()
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    normalized_guide = re.sub(r"\s+", " ", guide)

    assert (
        "https://github.com/jaminakoai/axiom/issues/new?template=external-scan-trial.yml"
        in guide
    )
    assert "güvenlik açığı şüphesi olmayan" in guide.lower()
    assert "never open a public issue" in normalized_guide
    assert "GitHub hesabınızla oturum açmanız gerekir" in guide
    assert "sign in with a GitHub account" in guide
    assert "../SECURITY.md" in guide
    assert "**Lütfen herkese açık issue açmayın.**" in security
    assert "security@axiom-lang.org" in security
    assert "kamuya açık kullanılmasına izin vermiyorsanız formu" in normalized_guide
    assert "agree on a private channel with the maintainer" in guide


def test_public_trial_issue_form_requires_consent_and_avoids_private_artifacts():
    guide = _read_guide()
    form_path = ROOT / ".github" / "ISSUE_TEMPLATE" / "external-scan-trial.yml"
    form = form_path.read_text(encoding="utf-8")

    assert "https://github.com/jaminakoai/axiom/issues/new?template=external-scan-trial.yml" in guide
    for field in (
        "id: authorization",
        "required: true",
        "id: environment",
        "id: axiom-commit",
        "id: input-type",
        "id: command",
        "id: expected-result",
        "id: actual-result",
        "id: match-summary",
        "id: sha256",
    ):
        assert field in form

    for instruction in (
        "Güvenlik açığı şüphesini buraya yazmayın",
        "Dosya, PCAP, paket içeriği, kural metni",
        "Do not attach or paste files, PCAPs",
        "suspected security vulnerability here",
        "I was authorized to use the tested file or PCAP",
        "I consent to publishing this sanitized report publicly",
        "Never paste full JSON",
        "Tam JSON'u ya da target_sha256 değerini",
        "Only report match_count, rules, offset, length, or exit_code",
        "SHA-256 can identify a file",
        "SHA-256 (paylaşma yetkiniz yoksa boş bırakın)",
    ):
        assert instruction in guide + form

    assert "type: upload" not in form
