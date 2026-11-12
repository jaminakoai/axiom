"""
Axiom - P2-15: `std/text/unicode` NFC/NFD konformans testi

Tablo tabanlı normalleştirme, Python'un `unicodedata` modülü (Unicode
Character Database) ile **birebir** karşılaştırılır. Bu, elle yazılmış
tablo hatalarını ve Hangul algoritma hatalarını yakalar.

Kapsam:
  - NFC / NFD gidiş-dönüş
  - Kanonik sıralama (farklı ccc'li birleştiriciler)
  - Hangul LV / LVT (algoritmik)
  - Türkçe karakterler
  - Yunan, Kiril, Latin Genişletilmiş
  - Astral düzlem (emoji, matematik)
  - NFKC/NFKD açık reddi
  - C + LLVM paritesi
"""
import os
import subprocess
import tempfile
import unicodedata as ucd
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"

# Konformans korpusu: (aciklama, metin)
CORPUS = [
    ("ascii", "hello"),
    ("bos", ""),
    ("nfc-e-acute", "\u00e9"),                      # é
    ("nfd-e-acute", "e\u0301"),                     # e + combining acute
    ("nfc-A-ring", "\u00c5"),                       # Å
    ("nfd-A-ring", "A\u030a"),
    ("turkish-I-dot", "\u0130"),                    # İ
    ("turkish-i-dotless", "\u0131"),                # ı
    ("turkish-word", "\u0130stanbul \u011f\u00fc\u015fi\u00f6\u00e7"),
    ("greek-tonos", "\u03ac"),                      # ά
    ("greek-decomp", "\u03b1\u0301"),
    ("cyrillic", "\u0439"),                         # й
    ("cyrillic-decomp", "\u0438\u0306"),
    ("order-dot-below-circumflex", "a\u0323\u0302"),
    ("order-circumflex-dot-below", "a\u0302\u0323"),
    ("q-dot-above-dot-below", "q\u0307\u0323"),
    ("triple-stack", "o\u0308\u0304\u0323"),
    ("hangul-LV", "\uac00"),                        # 가
    ("hangul-LVT", "\ud55c"),                       # 한
    ("hangul-jamo", "\u1100\u1161"),                # L + V
    ("hangul-jamo-T", "\u1100\u1161\u11a8"),
    ("hangul-mixed", "\ud55c\uad6d\uc5b4"),
    ("emoji", "\U0001f600\U0001f44d"),
    ("math-astral", "\U0001d518"),
    ("combining-only", "\u0301\u0302"),
    ("latin-ext", "\u01ea\u0323"),                  # Ǫ + dot below
    ("vietnamese", "\u1ec7"),                       # ệ
    ("multi-word", "Cafe\u0301 na\u00efve \u00c5ngstr\u00f6m"),
]


def _ax_literal(text: str) -> str:
    """Metni Axiom string literaline çevirir (yalnızca \\ ve \" kaçışlanır)."""
    out = []
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _build_program() -> str:
    lines = ['import "std/text/unicode"', 'import "std/encoding/hex"', ""]
    lines.append("fn main() -> int {")
    for i, (_desc, text) in enumerate(CORPUS):
        lit = _ax_literal(text)
        lines.append(f'    print("nfd{i}:", hex_encode(unicode_nfd({lit})))')
        lines.append(f'    print("nfc{i}:", hex_encode(unicode_nfc({lit})))')
        lines.append(f'    print("isnfc{i}:", unicode_is_nfc({lit}))')
        lines.append(f'    print("isnfd{i}:", unicode_is_nfd({lit}))')
    lines.append("    return 0")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _run(backend: str, tmp_path: Path):
    src = _build_program()
    f = tmp_path / "conf.ax"
    f.write_text(src, encoding="utf-8")
    out = tmp_path / "conf"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    args = [str(AXIOM), "build", str(f), "-o", str(out)]
    if backend == "llvm":
        args.insert(2, "--backend=llvm")
    res = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
    assert res.returncode == 0, res.stdout + res.stderr
    run = subprocess.run([str(out)], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    parsed = {}
    for line in run.stdout.splitlines():
        key, _, val = line.partition(":")
        parsed[key.strip()] = val.strip()
    return parsed


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_conformance_against_python_ucd(backend, tmp_path):
    got = _run(backend, tmp_path)

    problems = []
    for i, (desc, text) in enumerate(CORPUS):
        exp_nfd = ucd.normalize("NFD", text).encode("utf-8").hex()
        exp_nfc = ucd.normalize("NFC", text).encode("utf-8").hex()

        if got[f"nfd{i}"] != exp_nfd:
            problems.append(f"{desc}: NFD {got[f'nfd{i}']} != {exp_nfd}")
        if got[f"nfc{i}"] != exp_nfc:
            problems.append(f"{desc}: NFC {got[f'nfc{i}']} != {exp_nfc}")

        exp_is_nfc = (text == ucd.normalize("NFC", text))
        exp_is_nfd = (text == ucd.normalize("NFD", text))
        if got[f"isnfc{i}"] != ("true" if exp_is_nfc else "false"):
            problems.append(f"{desc}: is_nfc {got[f'isnfc{i}']}")
        if got[f"isnfd{i}"] != ("true" if exp_is_nfd else "false"):
            problems.append(f"{desc}: is_nfd {got[f'isnfd{i}']}")

    assert not problems, "UCD uyumsuzlukları:\n  " + "\n  ".join(problems)


def test_ucd_version_is_reported():
    src = '''
import "std/text/unicode"
fn main() -> int {
    print(unicode_ucd_version())
    return 0
}
'''
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "v.ax"
        f.write_text(src, encoding="utf-8")
        out = Path(td) / "v"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        res = subprocess.run([str(AXIOM), "build", str(f), "-o", str(out)],
                             capture_output=True, text=True, timeout=300, env=env)
        assert res.returncode == 0, res.stderr
        run = subprocess.run([str(out)], capture_output=True, text=True, timeout=60)
    assert run.stdout.strip() == ucd.unidata_version


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_unsupported_forms_are_explicit_errors(backend, tmp_path):
    src = '''
import "std/text/unicode"

fn main() -> int {
    let r = unicode_normalize_result("x", "NFKC")
    print("nfkc:", r.is_ok, str_contains(r.error, "NFKC"))

    let k = unicode_normalize_result("x", "NFKD")
    print("nfkd:", k.is_ok, str_contains(k.error, "NFKD"))

    let ok = unicode_normalize_result("x", "NFC")
    print("nfc:", ok.is_ok, ok.value)

    let d = unicode_normalize_result("x", "NFD")
    print("nfd:", d.is_ok, d.value)

    print("silent_empty:", len(unicode_normalize("x", "NOPE")))
    return 0
}
'''
    f = tmp_path / "r.ax"
    f.write_text(src, encoding="utf-8")
    out = tmp_path / "r"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    args = [str(AXIOM), "build", str(f), "-o", str(out)]
    if backend == "llvm":
        args.insert(2, "--backend=llvm")
    res = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
    assert res.returncode == 0, res.stderr
    run = subprocess.run([str(out)], capture_output=True, text=True, timeout=60)
    assert run.stdout.splitlines() == [
        "nfkc: false true",
        "nfkd: false true",
        "nfc: true x",
        "nfd: true x",
        "silent_empty: 0",
    ]


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_char_to_str_encodes_utf8(backend, tmp_path):
    """`char_to_str` ASCII disi kod noktalarini da UTF-8'e cevirmeli."""
    src = '''
import "std/text/unicode"
import "std/encoding/hex"

fn main() -> int {
    print("a:", hex_encode(char_to_str(65)))          // 41
    print("ea:", hex_encode(char_to_str(233)))       // c3a9
    print("acute:", hex_encode(char_to_str(769)))   // cc81
    print("hangul:", hex_encode(char_to_str(54620))) // ed959c
    print("emoji:", hex_encode(char_to_str(128512))) // f09f9880
    print("surrogate:", len(char_to_str(55296)))     // gecersiz
    print("too_big:", len(char_to_str(1114112)))
    print("neg:", len(char_to_str(-1)))
    return 0
}
'''
    f = tmp_path / "c.ax"
    f.write_text(src, encoding="utf-8")
    out = tmp_path / "c"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    args = [str(AXIOM), "build", str(f), "-o", str(out)]
    if backend == "llvm":
        args.insert(2, "--backend=llvm")
    res = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
    assert res.returncode == 0, res.stderr
    run = subprocess.run([str(out)], capture_output=True, text=True, timeout=60)
    assert run.stdout.splitlines() == [
        "a: 41",
        "ea: c3a9",
        "acute: cc81",
        "hangul: ed959c",
        "emoji: f09f9880",
        "surrogate: 0",
        "too_big: 0",
        "neg: 0",
    ]


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_grapheme_and_codepoint_counts(backend, tmp_path):
    src = '''
import "std/text/unicode"

fn main() -> int {
    // "e" + combining acute = 2 kod noktasi, 1 grapheme
    let decomposed = "e" + char_to_str(769)
    print("cp:", utf8_codepoint_count(decomposed), "gr:", grapheme_len(decomposed))

    // Aile emojisi: ZWJ dizisi tek grapheme
    let family = char_to_str(128104) + char_to_str(8205) + char_to_str(128105)
    print("cp2:", utf8_codepoint_count(family), "gr2:", grapheme_len(family))

    print("ascii:", utf8_codepoint_count("abc"), grapheme_len("abc"))
    return 0
}
'''
    f = tmp_path / "g.ax"
    f.write_text(src, encoding="utf-8")
    out = tmp_path / "g"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    args = [str(AXIOM), "build", str(f), "-o", str(out)]
    if backend == "llvm":
        args.insert(2, "--backend=llvm")
    res = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
    assert res.returncode == 0, res.stderr
    run = subprocess.run([str(out)], capture_output=True, text=True, timeout=60)
    assert run.stdout.splitlines() == [
        "cp: 2 gr: 1",
        "cp2: 3 gr2: 1",
        "ascii: 3 3",
    ]


def test_tables_are_generated_not_handwritten():
    """Tablolar üretici script ile UCD'den gelmeli; elle düzenlenmemeli."""
    header = (ROOT / "axiom" / "unicode_tables.h").read_text(encoding="utf-8")
    assert "OTOMATİK ÜRETİLDİ" in header
    assert "tools/gen_unicode_tables.py" in header
    assert f'AXIOM_UCD_VERSION "{ucd.unidata_version}"' in header
    assert "AXIOM_UCD_DECOMP_COUNT" in header
    assert "AXIOM_UCD_COMP_COUNT" in header


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_all_hangul_syllables_roundtrip(backend, tmp_path):
    """11.172 Hangul hecesi: NFC sabit, NFD/NFC gidis-donus kayipsiz."""
    src = '''
import "std/text/unicode"

fn main() -> int {
    // SBase..SBase+SCount-1
    let mut all = ""
    let mut i = 44032          // 0xAC00
    while (i < 55203 + 1) {    // 0xD7A3
        all = all + char_to_str(i)
        i = i + 1
    }
    let total = utf8_codepoint_count(all)
    print("syllables:", total)

    let nfd = unicode_nfd(all)
    let nfd_cp = utf8_codepoint_count(nfd)
    print("nfd_at_least_2x:", nfd_cp >= total * 2)
    print("nfd_at_most_3x:", nfd_cp <= total * 3)
    print("nfd_is_nfd:", unicode_is_nfd(nfd))
    print("nfd_not_nfc:", not unicode_is_nfc(nfd))

    let back = unicode_nfc(nfd)
    print("roundtrip:", back == all)
    print("all_is_nfc:", unicode_is_nfc(all))
    return 0
}
'''
    f = tmp_path / "h.ax"
    f.write_text(src, encoding="utf-8")
    out = tmp_path / "h"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    args = [str(AXIOM), "build", str(f), "-o", str(out)]
    if backend == "llvm":
        args.insert(2, "--backend=llvm")
    res = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
    assert res.returncode == 0, res.stderr
    run = subprocess.run([str(out)], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    lines = run.stdout.splitlines()
    assert lines[0] == "syllables: 11172"
    for line in lines[1:]:
        assert line.endswith("true"), f"başarısız: {line}"


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_normalization_is_idempotent(backend, tmp_path):
    src = '''
import "std/text/unicode"
import "std/encoding/hex"

fn main() -> int {
    let samples: str[] = [
        "e" + char_to_str(769),
        "a" + char_to_str(803) + char_to_str(770),
        char_to_str(54620) + char_to_str(44397),
        "Cafe" + char_to_str(769),
        "abc",
        ""
    ]
    let mut nfc_idem = true
    let mut nfd_idem = true
    let mut i = 0
    while (i < len(samples)) {
        let n = unicode_nfc(samples[i])
        if unicode_nfc(n) != n {
            nfc_idem = false
        }
        let d = unicode_nfd(samples[i])
        if unicode_nfd(d) != d {
            nfd_idem = false
        }
        i = i + 1
    }
    print("nfc_idempotent:", nfc_idem)
    print("nfd_idempotent:", nfd_idem)
    return 0
}
'''
    f = tmp_path / "i.ax"
    f.write_text(src, encoding="utf-8")
    out = tmp_path / "i"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    args = [str(AXIOM), "build", str(f), "-o", str(out)]
    if backend == "llvm":
        args.insert(2, "--backend=llvm")
    res = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
    assert res.returncode == 0, res.stderr
    run = subprocess.run([str(out)], capture_output=True, text=True, timeout=60)
    assert run.stdout.splitlines() == ["nfc_idempotent: true", "nfd_idempotent: true"]


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_invalid_utf8_does_not_crash(backend, tmp_path):
    """Bozuk bayt dizisi çökmemeli; U+FFFD ile değiştirilmeli."""
    src = '''
import "std/text/unicode"
import "std/io/binary"

fn main() -> int {
    let b = buf_create(8)
    buf_write_u8(b, 65)       // A
    buf_write_u8(b, 255)      // gecersiz
    buf_write_u8(b, 66)       // B
    let raw = buf_to_str(b)
    let n = unicode_nfc(raw)
    print("survived:", len(n) > 0)
    let d = unicode_nfd(raw)
    print("nfd_ok:", len(d) > 0)
    buf_free(b)
    return 0
}
'''
    f = tmp_path / "x.ax"
    f.write_text(src, encoding="utf-8")
    out = tmp_path / "x"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    args = [str(AXIOM), "build", str(f), "-o", str(out)]
    if backend == "llvm":
        args.insert(2, "--backend=llvm")
    res = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
    assert res.returncode == 0, res.stderr
    run = subprocess.run([str(out)], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0
    assert run.stdout.splitlines() == ["survived: true", "nfd_ok: true"]
