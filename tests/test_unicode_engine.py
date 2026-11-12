"""
Axiom Programming Language (λx) - FAZ 4.4: Tam Unicode UTF-8 & Grapheme Cluster & Türkçe Motoru Testleri
"""
import pytest
import subprocess
import tempfile
import os

from axiom.cli import compile_axiom_source, find_c_compiler

def run_axiom_code(code_str: str) -> tuple[int, str, str]:
    c_code = compile_axiom_source(code_str)
    cc = find_c_compiler()
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        cmd = [cc, "-O3", "-Wall", c_path, "-o", bin_path, "-lssl", "-lcrypto", "-lz", "-ldl", "-lm", "-pthread"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"C derleme hatasi:\n{res.stderr}"

        run_res = subprocess.run([bin_path], capture_output=True, text=True, timeout=10)
        return run_res.returncode, run_res.stdout, run_res.stderr
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

def test_turkish_casing_roundtrip():
    code = """
    import "std/text/unicode.ax"

    fn main() -> int {
        let original: str = "istanbul ılık çavdar şöleni güneşi";
        let upper: str = to_upper_tr(original);
        print("UPPER:", upper);

        if (upper == "İSTANBUL ILIK ÇAVDAR ŞÖLENİ GÜNEŞİ") {
            print("TURKISH_UPPER_OK");
        }

        let lower: str = to_lower_tr(upper);
        print("LOWER:", lower);

        if (lower == original) {
            print("TURKISH_ROUNDTRIP_OK");
        }
        return 0;
    }
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0
    assert "TURKISH_UPPER_OK" in out
    assert "TURKISH_ROUNDTRIP_OK" in out

def test_turkish_dotted_and_dotless_i():
    code = """
    import "std/text/unicode.ax"

    fn main() -> int {
        let s1: str = to_upper_tr("iğdır");
        let s2: str = to_upper_tr("ılık");
        let s3: str = to_lower_tr("ISPARTA");
        let s4: str = to_lower_tr("İZMİR");

        if (s1 == "İĞDIR" and s2 == "ILIK" and s3 == "ısparta" and s4 == "izmir") {
            print("DOTTED_DOTLESS_I_OK");
        }
        return 0;
    }
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0
    assert "DOTTED_DOTLESS_I_OK" in out

def test_unicode_grapheme_combining_characters():
    # "e" + combining acute (U+0301) = 2 codepoints, 1 grapheme cluster
    code = """
    import "std/text/unicode.ax"

    fn main() -> int {
        let text: str = "e\u0301";
        let c_count: int = utf8_codepoint_count(text);
        let g_count: int = grapheme_len(text);

        print("CODEPOINTS:", c_count);
        print("GRAPHEMES:", g_count);

        if (c_count == 2 and g_count == 1) {
            print("COMBINING_MARK_GRAPHEME_OK");
        }
        return 0;
    }
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0
    assert "COMBINING_MARK_GRAPHEME_OK" in out

def test_unicode_grapheme_crlf_and_emojis():
    code = r"""
    import "std/text/unicode.ax"

    fn main() -> int {
        // \r\n tek grapheme cluster olmalıdır (UAX #29 kuralı)
        let crlf: str = "satir1\r\nsatir2";
        let crlf_g: int = grapheme_len(crlf);
        if (crlf_g == 13) {
            print("CRLF_GRAPHEME_OK");
        }

        // Aile Emojisi (4 insan + 3 ZWJ = 7 codepoint) tek grapheme olmalıdır
        let family: str = "👨‍👩‍👧‍👦";
        let f_codepoints: int = utf8_codepoint_count(family);
        let f_graphemes: int = grapheme_len(family);
        if (f_codepoints == 7 and f_graphemes == 1) {
            print("FAMILY_EMOJI_GRAPHEME_OK");
        }
        return 0;
    }
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0
    assert "CRLF_GRAPHEME_OK" in out
    assert "FAMILY_EMOJI_GRAPHEME_OK" in out

def test_unicode_grapheme_indexing():
    code = """
    import "std/text/unicode.ax"

    fn main() -> int {
        let s: str = "Türkçe";
        let g0: str = grapheme_at(s, 0);
        let g1: str = grapheme_at(s, 1);
        let g2: str = grapheme_at(s, 2);
        let g3: str = grapheme_at(s, 3);
        let g4: str = grapheme_at(s, 4);
        let g5: str = grapheme_at(s, 5);

        if (g0 == "T" and g1 == "ü" and g2 == "r" and g3 == "k" and g4 == "ç" and g5 == "e") {
            print("GRAPHEME_INDEXING_OK");
        }
        return 0;
    }
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0
    assert "GRAPHEME_INDEXING_OK" in out
