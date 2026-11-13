"""Regression tests for strict YARA hex parsing in direct runtime APIs."""

import os
import subprocess
import tempfile

from axiom.cli import compile_axiom_source, find_c_compiler


def run_axiom_code(source: str) -> tuple[int, str, str]:
    c_code = compile_axiom_source(source)
    cc = find_c_compiler()
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        command = [cc, "-O3", "-Wall", c_path, "-o", bin_path,
                   "-lssl", "-lcrypto", "-lz", "-ldl", "-pthread"]
        compiled = subprocess.run(command, capture_output=True, text=True, timeout=120)
        assert compiled.returncode == 0, compiled.stderr
        result = subprocess.run([bin_path], capture_output=True, text=True, timeout=15)
        return result.returncode, result.stdout, result.stderr
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)


def test_runtime_accepts_documented_byte_and_wildcard_forms():
    source = r'''
    import "std:security:yara"
    import "std:encoding:hex"

    fn main() -> int {
        verify rt_yara_pattern_len("4142") == 2
        verify rt_yara_pattern_len("41 42") == 2
        verify rt_yara_pattern_len("{ 41 42 }") == 2
        verify rt_yara_pattern_len("??") == 1
        verify rt_yara_pattern_len("A?") == 1
        verify rt_yara_pattern_len("?A") == 1

        verify rt_yara_find_hex_wildcard("AB", "4142", -1, -1) == 0
        verify rt_yara_find_hex_wildcard("AB", "41 42", -1, -1) == 0
        verify rt_yara_find_hex_wildcard("AB", "{ 41 42 }", -1, -1) == 0
        verify rt_yara_find_hex_wildcard("AB", "??", -1, -1) == 0
        verify rt_yara_find_hex_wildcard(hex_decode("AB"), "A?", -1, -1) == 0
        verify rt_yara_find_hex_wildcard("AB", "?2", -1, -1) == 1

        // Encoded targets accept compact or byte-pair hexadecimal only.
        verify rt_yara_find_hex_stream("4142", "41 42") == 0
        verify rt_yara_find_hex_stream("41 42", "4142") == 0
        print("STRICT_YARA_HEX_VALID_FORMS_OK")
        return 0
    }
    '''
    ret, out, err = run_axiom_code(source)
    assert ret == 0, err
    assert "STRICT_YARA_HEX_VALID_FORMS_OK" in out


def test_runtime_rejects_odd_nibbles_and_illegal_pattern_characters():
    patterns = [
        '""',
        '"4"',
        '"?"',
        '"41#comment"',
        '"41//comment"',
        '"41,"',
        '"41|42"',
        '"41[1]"',
        '"41(42)"',
        '"41~00"',
        '"41\\\\x42"',
        '"{41}trailing"',
    ]
    checks = "\n".join(
        f"verify rt_yara_pattern_len({pattern}) == 0" for pattern in patterns
    )
    source = f'''
    import "std:security:yara"

    fn main() -> int {{
        {checks}
        verify rt_yara_find_hex_wildcard("A", "41#comment", -1, -1) == -1
        // Raw-byte failure must not let malformed syntax match in the
        // encoded-hex fallback, even when the target is valid hex text.
        verify yara_find_hex_wildcard("41", "41#comment") == -1
        verify rt_yara_find_hex_wildcard("A", "?", -1, -1) == -1
        verify rt_yara_find_hex_stream("4", "04") == -1
        verify rt_yara_find_hex_stream("41,42", "41 42") == -1
        print("STRICT_YARA_HEX_INVALID_FORMS_REJECTED")
        return 0
    }}
    '''
    ret, out, err = run_axiom_code(source)
    assert ret == 0, err
    assert "STRICT_YARA_HEX_INVALID_FORMS_REJECTED" in out


def test_runtime_rejects_oversized_patterns_and_safe_offset_bounds():
    oversized = "41" * 4097
    source = f'''
    import "std:security:yara"

    fn main() -> int {{
        verify rt_yara_pattern_len("{oversized}") == 0
        verify rt_yara_find_hex_wildcard("X", "41", 0, 9223372036854775807) == -1
        verify rt_yara_find_hex_wildcard("AB", "41", 9223372036854775807, 9223372036854775807) == -1
        print("STRICT_YARA_HEX_LIMITS_OK")
        return 0
    }}
    '''
    ret, out, err = run_axiom_code(source)
    assert ret == 0, err
    assert "STRICT_YARA_HEX_LIMITS_OK" in out
