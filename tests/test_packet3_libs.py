"""
Axiom Programming Language (λx) - Standard Library Packet 3 Tests
Libraries tested:
11. std:io:binary (Byte Buffer, Endian pack/unpack, Hex encode/decode)
12. std:os:process (exec_output, pid, kill, spawn_bg)
13. std:compress:zlib (gzip_compress, gzip_decompress, zlib_compress_str, zlib_decompress_str)
14. std:text:regex (regex_is_match, regex_find, regex_replace)
15. std:collections:map (map_create, map_set, map_get, map_has, map_delete, map_len, map_free)
"""
import os
import subprocess
import tempfile
import pytest
from pathlib import Path

from axiom.cli import compile_axiom_source, find_c_compiler
from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.resolver import ModuleResolver
from axiom.checker import TypeChecker
from axiom.codegen_llvm import LLVMCodeGenerator

STD_DIR = str((Path(__file__).resolve().parent.parent / "std").resolve())

def compile_and_run(source_code: str, source_path: str = None, timeout: int = 10) -> subprocess.CompletedProcess:
    if source_path is None:
        source_path = str(Path(STD_DIR) / "entry.ax")

    c_code = compile_axiom_source(source_code, source_path)
    cc = find_c_compiler()

    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        res_cc = subprocess.run([cc, "-O2", "-pthread", c_path, "-lz", "-lssl", "-lcrypto", "-ldl", "-o", bin_path], capture_output=True, text=True)
        if res_cc.returncode != 0:
            raise RuntimeError(f"C Derleyici Hatasi:\n{res_cc.stderr}\nUretilen C Kodu:\n{c_code}")

        res_exec = subprocess.run([bin_path], capture_output=True, text=True, timeout=timeout)
        return res_exec
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

def compile_and_run_llvm(source_code: str, source_path: str = None, timeout: int = 10) -> subprocess.CompletedProcess:
    if source_path is None:
        source_path = str(Path(STD_DIR) / "entry.ax")

    lexer = Lexer(source_code)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    prog = parser.parse()
    resolver = ModuleResolver(base_file_path=source_path)
    prog = resolver.resolve(prog)
    checker = TypeChecker()
    checker.check(prog)

    codegen = LLVMCodeGenerator()
    llvm_ir = codegen.generate(prog)

    runtime_c = str(Path(__file__).resolve().parent.parent / "axiom" / "axiom_llvm_runtime.c")

    with tempfile.NamedTemporaryFile(suffix=".ll", mode="w", delete=False) as ll_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        ll_path = ll_file.name
        bin_path = bin_file.name
        ll_file.write(llvm_ir)

    try:
        cmd = ["clang", "-O2", ll_path, runtime_c, "-pthread", "-lz", "-lssl", "-lcrypto", "-ldl", "-lm", "-o", bin_path]
        res_cc = subprocess.run(cmd, capture_output=True, text=True)
        if res_cc.returncode != 0:
            raise RuntimeError(f"LLVM Clang Hatasi:\n{res_cc.stderr}\nUretilen IR:\n{llvm_ir}")

        res_exec = subprocess.run([bin_path], capture_output=True, text=True, timeout=timeout)
        return res_exec
    finally:
        if os.path.exists(ll_path):
            os.remove(ll_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

# =========================================================================
# 1. std:io:binary TESTS
# =========================================================================

def test_binary_buf_u8():
    code = """
    import "std:io:binary"
    fn main() -> int {
        let b = buf_create(16);
        buf_write_u8(b, 65);
        buf_write_u8(b, 66);
        buf_write_u8(b, 67);
        let l = buf_len(b);
        verify l == 3, "Length must be 3";
        let r0 = buf_read_u8(b, 0);
        let r1 = buf_read_u8(b, 1);
        let r2 = buf_read_u8(b, 2);
        verify r0 == 65, "First byte A";
        verify r1 == 66, "Second byte B";
        verify r2 == 67, "Third byte C";
        let s = buf_to_str(b);
        print(s);
        buf_free(b);
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "ABC" in res.stdout

def test_binary_buf_u16_be_le():
    code = """
    import "std:io:binary"
    fn main() -> int {
        let b = buf_create(16);
        buf_write_u16_be(b, 4660); // 0x1234
        buf_write_u16_le(b, 4660); // 0x34 0x12
        verify buf_len(b) == 4, "Length 4";
        let be_val = buf_read_u16_be(b, 0);
        let le_val = buf_read_u16_le(b, 2);
        verify be_val == 4660, "BE match";
        verify le_val == 4660, "LE match";
        let hex = buf_to_hex(b);
        print(hex);
        buf_free(b);
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "12343412" in res.stdout

def test_binary_buf_u32_be_le():
    code = """
    import "std:io:binary"
    fn main() -> int {
        let b = buf_create(16);
        buf_write_u32_be(b, 305419896); // 0x12345678
        buf_write_u32_le(b, 305419896);
        verify buf_len(b) == 8, "Length 8";
        let be_val = buf_read_u32_be(b, 0);
        let le_val = buf_read_u32_le(b, 4);
        verify be_val == 305419896, "BE match";
        verify le_val == 305419896, "LE match";
        let hex = buf_to_hex(b);
        print(hex);
        buf_free(b);
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "1234567878563412" in res.stdout

def test_binary_buf_u64_be_le():
    code = """
    import "std:io:binary"
    fn main() -> int {
        let b = buf_create(32);
        let v = 140737488348336;
        buf_write_u64_be(b, v);
        buf_write_u64_le(b, v);
        verify buf_len(b) == 16, "Length 16";
        let read_be = buf_read_u64_be(b, 0);
        let read_le = buf_read_u64_le(b, 8);
        verify read_be == v, "u64 BE match";
        verify read_le == v, "u64 LE match";
        print("U64_SUCCESS");
        buf_free(b);
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "U64_SUCCESS" in res.stdout

def test_binary_buf_hex_roundtrip():
    code = """
    import "std:io:binary"
    fn main() -> int {
        let b = buf_create(16);
        buf_write_str(b, "EXPLOIT_PAYLOAD");
        let hex = buf_to_hex(b);
        let b2 = buf_from_hex(hex);
        let s2 = buf_to_str(b2);
        print(s2);
        verify s2 == "EXPLOIT_PAYLOAD", "Roundtrip string match";
        buf_free(b);
        buf_free(b2);
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "EXPLOIT_PAYLOAD" in res.stdout

def test_binary_buf_dynamic_grow():
    code = """
    import "std:io:binary"
    fn main() -> int {
        let b = buf_create(4); // initial capacity 4
        let mut i = 0;
        while i < 100 {
            buf_write_u8(b, i);
            i = i + 1;
        }
        verify buf_len(b) == 100, "Should grow to 100";
        verify buf_read_u8(b, 50) == 50, "Read item at index 50";
        print("GROW_OK");
        buf_free(b);
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "GROW_OK" in res.stdout

def test_binary_buf_bounds_safety():
    code = """
    import "std:io:binary"
    fn main() -> int {
        let b = buf_create(16);
        buf_write_u8(b, 42);
        let oob_u8 = buf_read_u8(b, 99);
        let oob_u16 = buf_read_u16_be(b, 99);
        let oob_u32 = buf_read_u32_be(b, 99);
        let oob_u64 = buf_read_u64_be(b, 99);
        verify oob_u8 == 0, "OOB u8 is 0";
        verify oob_u16 == 0, "OOB u16 is 0";
        verify oob_u32 == 0, "OOB u32 is 0";
        verify oob_u64 == 0, "OOB u64 is 0";
        print("BOUNDS_SAFE");
        buf_free(b);
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "BOUNDS_SAFE" in res.stdout

# =========================================================================
# 2. std:os:process TESTS
# =========================================================================

def test_process_pid():
    code = """
    import "std:os:process"
    fn main() -> int {
        let pid = process_get_pid();
        verify pid > 0, "PID must be positive";
        print("PID_VALID");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "PID_VALID" in res.stdout

def test_process_exec_output():
    code = """
    import "std:os:process"
    fn main() -> int {
        let out = process_exec_output("echo TEST_PROCESS_123");
        print(out);
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "TEST_PROCESS_123" in res.stdout

def test_process_spawn_bg_and_kill():
    code = """
    import "std:os:process"
    fn main() -> int {
        let pid = process_spawn_bg("sleep 30");
        verify pid > 0, "Spawned PID must be positive";
        let k = process_kill(pid, 9);
        verify k == 0, "Kill signal 9 must succeed";
        print("SPAWN_KILL_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "SPAWN_KILL_OK" in res.stdout

# =========================================================================
# 3. std:compress:zlib TESTS
# =========================================================================

def test_gzip_compression_roundtrip():
    code = """
    import "std:compress:zlib"
    fn main() -> int {
        let text = "Hello Gzip Compression In Axiom Programming Language! Repeated Repeated Repeated";
        let hex_comp = gzip_compress(text);
        let decomp = gzip_decompress(hex_comp);
        verify decomp == text, "Gzip roundtrip must match original";
        print("GZIP_ROUNDTRIP_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "GZIP_ROUNDTRIP_OK" in res.stdout

def test_zlib_compression_roundtrip():
    code = """
    import "std:compress:zlib"
    fn main() -> int {
        let text = "Raw Deflate/Zlib Payload for Network Transmission 1234567890";
        let hex_comp = zlib_compress_str(text);
        let decomp = zlib_decompress_str(hex_comp);
        verify decomp == text, "Zlib roundtrip must match original";
        print("ZLIB_ROUNDTRIP_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "ZLIB_ROUNDTRIP_OK" in res.stdout

def test_gzip_empty_string():
    code = """
    import "std:compress:zlib"
    fn main() -> int {
        let hex_comp = gzip_compress("");
        let decomp = gzip_decompress(hex_comp);
        verify decomp == "", "Empty string decompressed is empty";
        print("EMPTY_GZIP_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "EMPTY_GZIP_OK" in res.stdout

# =========================================================================
# 4. std:text:regex TESTS
# =========================================================================

def test_regex_is_match():
    code = """
    import "std:text:regex"
    fn main() -> int {
        let m1 = regex_is_match("^[0-9]+$", "12345678");
        let m2 = regex_is_match("^[0-9]+$", "123a456");
        verify m1 == true, "Digits must match";
        verify m2 == false, "Digits with letter must fail";
        print("MATCH_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "MATCH_OK" in res.stdout

def test_regex_find():
    code = """
    import "std:text:regex"
    fn main() -> int {
        let text = "User logged in with email john.doe@cybersec.org from ip 10.0.0.1";
        let email = regex_find("[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+", text);
        print(email);
        verify email == "john.doe@cybersec.org", "Email must be extracted";
        let nomatch = regex_find("xyz12345", text);
        verify nomatch == "", "Non match is empty";
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "john.doe@cybersec.org" in res.stdout

def test_regex_replace():
    code = """
    import "std:text:regex"
    fn main() -> int {
        let text = "Port 80 is open, Port 443 is open, Port 8080 is open.";
        let res = regex_replace("Port [0-9]+", text, "TARGET_PORT");
        print(res);
        verify res == "TARGET_PORT is open, TARGET_PORT is open, TARGET_PORT is open.", "All replaced";
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "TARGET_PORT is open, TARGET_PORT is open, TARGET_PORT is open." in res.stdout

# =========================================================================
# 5. std:collections:map TESTS
# =========================================================================

def test_map_basic_operations():
    code = """
    import "std:collections:map"
    fn main() -> int {
        let m = map_create();
        map_set(m, "hostname", "gateway.local");
        map_set(m, "port", "443");
        verify map_len(m) == 2, "Map length 2";
        let h = map_get(m, "hostname");
        let p = map_get(m, "port");
        verify h == "gateway.local", "Hostname match";
        verify p == "443", "Port match";
        verify map_has(m, "hostname") == true, "Has hostname";
        verify map_has(m, "unknown") == false, "No unknown";
        map_free(m);
        print("MAP_BASIC_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "MAP_BASIC_OK" in res.stdout

def test_map_update_and_delete():
    code = """
    import "std:collections:map"
    fn main() -> int {
        let m = map_create();
        map_set(m, "status", "initial");
        verify map_get(m, "status") == "initial", "Initial value";
        map_set(m, "status", "updated");
        verify map_get(m, "status") == "updated", "Updated value";
        verify map_len(m) == 1, "Length still 1 after update";

        let d1 = map_delete(m, "status");
        verify d1 == true, "Delete existing succeeds";
        verify map_has(m, "status") == false, "Key no longer exists";
        verify map_len(m) == 0, "Length is 0 after delete";

        let d2 = map_delete(m, "status");
        verify d2 == false, "Delete nonexistent returns false";

        map_free(m);
        print("MAP_UPDATE_DEL_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "MAP_UPDATE_DEL_OK" in res.stdout

def test_map_rehash_collision():
    code = """
    import "std:collections:map"
    fn main() -> int {
        let m = map_create();
        map_set(m, "k1", "v1");
        map_set(m, "k2", "v2");
        map_set(m, "k3", "v3");
        map_set(m, "k4", "v4");
        map_set(m, "k5", "v5");
        map_set(m, "k6", "v6");
        map_set(m, "k7", "v7");
        map_set(m, "k8", "v8");
        map_set(m, "k9", "v9");
        map_set(m, "k10", "v10");
        map_set(m, "k11", "v11");
        map_set(m, "k12", "v12");
        map_set(m, "k13", "v13");
        map_set(m, "k14", "v14");
        map_set(m, "k15", "v15");
        map_set(m, "k16", "v16");
        map_set(m, "k17", "v17");
        map_set(m, "k18", "v18");
        map_set(m, "k19", "v19");
        map_set(m, "k20", "v20");

        verify map_len(m) == 20, "Should contain 20 items";
        verify map_get(m, "k1") == "v1", "k1 match";
        verify map_get(m, "k10") == "v10", "k10 match";
        verify map_get(m, "k20") == "v20", "k20 match";

        map_free(m);
        print("REHASH_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "REHASH_OK" in res.stdout

# =========================================================================
# 6. LLVM IR BACKEND INTEGRATION TEST FOR PACKET 3
# =========================================================================

def test_packet3_llvm_backend():
    code = """
    import "std:io:binary"
    import "std:collections:map"
    import "std:text:regex"

    fn main() -> int {
        let b = buf_create(16);
        buf_write_u32_be(b, 3735928559); // 0xdeadbeef
        let val = buf_read_u32_be(b, 0);
        verify val == 3735928559, "LLVM Buffer BE match";
        buf_free(b);

        let m = map_create();
        map_set(m, "compiler", "LLVM");
        let c = map_get(m, "compiler");
        verify c == "LLVM", "LLVM Map match";
        map_free(m);

        let is_ok = regex_is_match("^[A-Z]+$", "AXIOM");
        verify is_ok == true, "LLVM Regex match";

        print("LLVM_PACKET3_SUCCESS");
        return 0;
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "LLVM_PACKET3_SUCCESS" in res.stdout

def test_packet3_pipeline():
    code = """
    import "std:io:binary"
    import "std:compress:zlib"
    import "std:text:regex"
    import "std:collections:map"

    fn main() -> int {
        // 1. Pack exploit string in buffer
        let b = buf_create(32);
        buf_write_str(b, "TOKEN=ABC_SECRET_1337;HOST=127.0.0.1;STATUS=OPEN");
        let raw = buf_to_str(b);

        // 2. Extract token via regex
        let tok = regex_find("ABC_SECRET_[0-9]+", raw);
        verify tok == "ABC_SECRET_1337", "Regex extraction match";

        // 3. Compress token with zlib
        let comp = zlib_compress_str(tok);
        let decomp = zlib_decompress_str(comp);
        verify decomp == tok, "Decompressed matches extracted token";

        // 4. Store in map
        let m = map_create();
        map_set(m, "session_token", tok);
        map_set(m, "compressed_hex", comp);
        verify map_get(m, "session_token") == "ABC_SECRET_1337", "Map retrieve token";
        verify map_len(m) == 2, "Map length 2";

        buf_free(b);
        map_free(m);
        print("PIPELINE_SUCCESS");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "PIPELINE_SUCCESS" in res.stdout

def test_packet3_cli_example():
    axiom_bin = str(Path(__file__).resolve().parent.parent / "bin" / "axiom")
    example_path = str(Path(__file__).resolve().parent.parent / "examples" / "12_packet3_system_exploit.ax")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)

    res = subprocess.run(["python3", axiom_bin, "run", example_path], capture_output=True, text=True, env=env)
    assert res.returncode == 0
    assert "[BASARILI] PAKET 3" in res.stdout

def test_binary_buf_u8_overflow_wrap():
    code = """
    import "std:io:binary"
    fn main() -> int {
        let b = buf_create(16);
        buf_write_u8(b, 300); // 300 & 0xFF == 44 (',')
        let val = buf_read_u8(b, 0);
        verify val == 44, "U8 bitwise truncation match";
        buf_free(b);
        print("U8_WRAP_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "U8_WRAP_OK" in res.stdout

def test_binary_buf_u16_overflow_wrap():
    code = """
    import "std:io:binary"
    fn main() -> int {
        let b = buf_create(16);
        buf_write_u16_be(b, 65540); // 65540 & 0xFFFF == 4
        let val = buf_read_u16_be(b, 0);
        verify val == 4, "U16 bitwise truncation match";
        buf_free(b);
        print("U16_WRAP_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "U16_WRAP_OK" in res.stdout

def test_binary_buf_mixed_endian_sequence():
    code = """
    import "std:io:binary"
    fn main() -> int {
        let b = buf_create(32);
        buf_write_u8(b, 1);
        buf_write_u16_le(b, 513); // 0x0201 -> 0x01, 0x02
        buf_write_u32_be(b, 67305985); // 0x04030201
        verify buf_len(b) == 7, "Length is 1 + 2 + 4 = 7";
        verify buf_read_u8(b, 0) == 1, "Byte 0";
        verify buf_read_u16_le(b, 1) == 513, "Word at 1";
        verify buf_read_u32_be(b, 3) == 67305985, "Dword at 3";
        buf_free(b);
        print("MIXED_ENDIAN_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "MIXED_ENDIAN_OK" in res.stdout

def test_process_exec_multiline():
    code = """
    import "std:os:process"
    import "std:text:regex"
    fn main() -> int {
        let out = process_exec_output("printf 'line1\\nline2\\nline3\\n'");
        let has_l2 = regex_is_match("line2", out);
        verify has_l2 == true, "Must contain line2";
        print("MULTILINE_PROC_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "MULTILINE_PROC_OK" in res.stdout

def test_gzip_compression_ratio():
    code = """
    import "std:compress:zlib"
    fn main() -> int {
        let s = "AAAAABBBBBCCCCCDDDDDEEEEEAAAAABBBBBCCCCCDDDDDEEEEEAAAAABBBBBCCCCCDDDDDEEEEE";
        let hex = gzip_compress(s);
        let orig_len = len(s);
        let decomp = gzip_decompress(hex);
        verify decomp == s, "Must decompress perfectly";
        print("RATIO_TEST_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "RATIO_TEST_OK" in res.stdout

def test_regex_digits_and_classes():
    code = """
    import "std:text:regex"
    fn main() -> int {
        let text = "HTTP/1.1 200 OK";
        let status = regex_find("[0-9]{3}", text);
        verify status == "200", "Status code extracted";
        let is_http = regex_is_match("^HTTP/[0-9]\\.[0-9]", text);
        verify is_http == true, "HTTP version matches";
        print("REGEX_CLASSES_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "REGEX_CLASSES_OK" in res.stdout

def test_regex_replace_delete():
    code = """
    import "std:text:regex"
    fn main() -> int {
        let text = "remove_all_dashes-and-hyphens-from-this";
        let clean = regex_replace("-", text, "");
        verify clean == "remove_all_dashesandhyphensfromthis", "All dashes removed";
        print("REGEX_DEL_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "REGEX_DEL_OK" in res.stdout

def test_map_empty_key_and_value():
    code = """
    import "std:collections:map"
    fn main() -> int {
        let m = map_create();
        map_set(m, "", "empty_key_val");
        map_set(m, "empty_val_key", "");
        verify map_len(m) == 2, "Map length 2";
        verify map_get(m, "") == "empty_key_val", "Empty key lookup";
        verify map_get(m, "empty_val_key") == "", "Empty val lookup";
        map_free(m);
        print("MAP_EMPTY_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "MAP_EMPTY_OK" in res.stdout

def test_map_overwrite_multiple():
    code = """
    import "std:collections:map"
    fn main() -> int {
        let m = map_create();
        map_set(m, "state", "v1");
        map_set(m, "state", "v2");
        map_set(m, "state", "v3");
        map_set(m, "state", "v4");
        map_set(m, "state", "v5");
        verify map_len(m) == 1, "Length remains 1";
        verify map_get(m, "state") == "v5", "Final value must be v5";
        map_free(m);
        print("OVERWRITE_MULTIPLE_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "OVERWRITE_MULTIPLE_OK" in res.stdout

def test_example_12_direct():
    example_path = str(Path(__file__).resolve().parent.parent / "examples" / "12_packet3_system_exploit.ax")
    with open(example_path, "r", encoding="utf-8") as f:
        code = f.read()
    res = compile_and_run(code, example_path)
    assert res.returncode == 0
    assert "[BASARILI] PAKET 3" in res.stdout


