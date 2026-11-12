"""
Axiom - İngilizce doküman doğrulaması (P2-04)

Kurallar:
  1. `docs/en/TUTORIAL.md` ve `docs/en/SPECIFICATION.md` Türkçe sürümlerle
     yapısal olarak eşleşmeli (başlık ve kod bloğu sayısı).
  2. İngilizce belgelerdeki çalıştırılabilir `axiom` blokları derlenmeli.
  3. `README.en.md` mevcut olmalı ve bağlantıları çözülmeli.
"""
import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"

DOCS = {
    "tutorial": (ROOT / "docs" / "TUTORIAL.md", ROOT / "docs" / "en" / "TUTORIAL.md"),
    "specification": (ROOT / "SPECIFICATION.md", ROOT / "docs" / "en" / "SPECIFICATION.md"),
}

SKIP_MARKERS = ('import "utils.ax"',)
# Şartnamede gövdesi kasıtlı olarak `...` ile kısaltılmış bloklar (derlenemez).
ELISION_RE = re.compile(r"(^\s*\.\.\.\s*$)|(\{\s*\.\.\.\s*\})", re.M)
FENCE_RE = re.compile(r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n(.*?)```", re.S)


def _blocks(path: Path):
    return [(lang, body) for lang, body in FENCE_RE.findall(path.read_text(encoding="utf-8"))]


def _runnable(path: Path):
    out = []
    for lang, body in _blocks(path):
        if lang not in ("axiom", ""):
            continue
        if "fn main" not in body:
            continue
        if any(m in body for m in SKIP_MARKERS):
            continue
        if ELISION_RE.search(body):
            continue
        out.append(body)
    return out


def test_english_docs_exist():
    assert (ROOT / "README.en.md").is_file(), "README.en.md eksik"
    for name, (_tr, en) in DOCS.items():
        assert en.is_file(), f"İngilizce {name} eksik: {en}"
        assert en.stat().st_size > 5000, f"{en} şüpheli derecede küçük"


@pytest.mark.parametrize("name", list(DOCS))
def test_english_structure_matches_turkish(name):
    """Çeviri bölüm/kod bloğu kaybetmemeli."""
    tr, en = DOCS[name]
    tr_blocks, en_blocks = _blocks(tr), _blocks(en)
    assert len(en_blocks) >= len(tr_blocks), (
        f"{name}: TR {len(tr_blocks)} kod bloğu, EN {len(en_blocks)} — blok kaybı var"
    )

    def headings(p):
        return [len(m) for m in re.findall(r"^(#+)[ \t]+\S", p.read_text(encoding="utf-8"), re.M)]

    tr_h, en_h = headings(tr), headings(en)
    assert len(en_h) == len(tr_h), (
        f"{name}: TR {len(tr_h)} başlık, EN {len(en_h)} — bölüm kaybı/fazlası var"
    )
    assert en_h == tr_h, f"{name}: başlık seviyeleri farklı"


@pytest.mark.parametrize("name", list(DOCS))
def test_english_is_actually_english(name):
    """Çeviri yapılmadan kopyalanmış Türkçe metni yakalar."""
    _tr, en = DOCS[name]
    text = en.read_text(encoding="utf-8")
    # Türkçeye özgü harfler nesirde geçmemeli. Kod bloklarını çıkar.
    prose = FENCE_RE.sub("", text)
    hits = re.findall(r"[çğıöşüÇĞİÖŞÜ]", prose)
    assert len(hits) < 20, f"{name}: çevrilmemiş Türkçe metin ({len(hits)} Türkçe harf)"


@pytest.mark.parametrize("name", list(DOCS))
def test_english_code_blocks_still_compile(name):
    _tr, en = DOCS[name]
    runnable = _runnable(en)
    assert runnable, f"{name}: EN sürümde çalıştırılabilir blok yok"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    for idx, block in enumerate(runnable, start=1):
        with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
            f.write(block)
            src = f.name
        out = src + ".bin"
        try:
            res = subprocess.run(
                [str(AXIOM), "build", src, "-o", out],
                capture_output=True, text=True, timeout=240, env=env,
            )
            assert res.returncode == 0, (
                f"{name} EN blok {idx} derlenemedi:\n{res.stdout}\n{res.stderr}\n--- kaynak ---\n{block}"
            )
        finally:
            os.remove(src)
            if os.path.exists(out):
                os.remove(out)


def test_english_tutorial_does_not_leak_internal_apis():
    """Tutorial iç API içermemeli. Şartname `str_owned_count` gibi tanılama
    yerleşiklerini bilinçli olarak belgeler; bu kontrol ona uygulanmaz."""
    _tr, en = DOCS["tutorial"]
    text = en.read_text(encoding="utf-8")
    for internal in ("str_owned_count", "axiom_temp_mark", "g_axiom", "_ax_tm"):
        assert internal not in text, f"{en.name} iç API sızdırıyor: {internal}"


def test_readme_en_relative_links_resolve():
    readme = ROOT / "README.en.md"
    text = readme.read_text(encoding="utf-8")
    missing = []
    for target in re.findall(r"\]\((?!https?://|#|mailto:)([^)#]+)", text):
        if not (ROOT / target).exists():
            missing.append(target)
    assert not missing, f"README.en.md kırık bağlantılar: {missing}"
