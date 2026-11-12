"""
Axiom Programming Language (λx) - Standard Library Packet 4 Tests
Libraries tested:
16. std:collections:queue (Thread-Safe FIFO Queue)
17. std:security:fuzzer (Web & API Fuzzing & Wordlist)
18. std:time:date (Date, Time, ISO 8601 & Epoch)
19. std:io:csv (CSV Reporting & RFC 4180 Escaping)
20. std:cli:args (CLI Arguments & Option Parser)
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

def compile_and_run(source_code: str, source_path: str = None, timeout: int = 10, args: list = None) -> subprocess.CompletedProcess:
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

        cmd = [bin_path]
        if args:
            cmd.extend(args)
        res_exec = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res_exec
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

def compile_and_run_llvm(source_code: str, source_path: str = None, timeout: int = 10, args: list = None) -> subprocess.CompletedProcess:
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

        run_cmd = [bin_path]
        if args:
            run_cmd.extend(args)
        res_exec = subprocess.run(run_cmd, capture_output=True, text=True, timeout=timeout)
        return res_exec
    finally:
        if os.path.exists(ll_path):
            os.remove(ll_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

# =========================================================================
# 1. std:collections:queue TESTS
# =========================================================================

def test_queue_basic_push_pop():
    code = """
    import "std:collections:queue"
    fn main() -> int {
        let q = queue_create();
        verify queue_is_empty(q) == true, "New queue must be empty";
        verify queue_len(q) == 0, "Initial length 0";

        queue_push(q, "target_1");
        queue_push(q, "target_2");
        queue_push(q, "target_3");

        verify queue_is_empty(q) == false, "Queue not empty";
        verify queue_len(q) == 3, "Queue length 3";

        let item1 = queue_pop(q);
        verify item1 == "target_1", "FIFO order first";
        verify queue_len(q) == 2, "Length 2 after 1 pop";

        let item2 = queue_pop(q);
        verify item2 == "target_2", "FIFO order second";

        let item3 = queue_pop(q);
        verify item3 == "target_3", "FIFO order third";

        verify queue_len(q) == 0, "Length 0 after popping all";
        verify queue_is_empty(q) == true, "Empty after popping all";

        let empty_pop = queue_pop(q);
        verify empty_pop == "", "Empty pop returns empty string";

        queue_free(q);
        print("QUEUE_BASIC_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "QUEUE_BASIC_OK" in res.stdout

def test_queue_push_multiple_and_interleaved():
    code = """
    import "std:collections:queue"
    fn main() -> int {
        let q = queue_create();
        let mut i = 0;
        while i < 50 {
            queue_push(q, "job");
            i = i + 1;
        }
        verify queue_len(q) == 50, "50 items queued";

        let mut popped = 0;
        while popped < 25 {
            let s = queue_pop(q);
            verify s == "job", "Item match";
            popped = popped + 1;
        }
        verify queue_len(q) == 25, "25 items remaining";

        queue_push(q, "extra_job");
        verify queue_len(q) == 26, "26 items after extra push";

        queue_free(q);
        print("QUEUE_INTERLEAVED_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "QUEUE_INTERLEAVED_OK" in res.stdout

# =========================================================================
# 2. std:security:fuzzer TESTS
# =========================================================================

def test_fuzzer_marker_replacement():
    code = """
    import "std:security:fuzzer"
    fn main() -> int {
        let tpl = "GET /search?q=FUZZ&category=FUZZ HTTP/1.1";
        let res = fuzz_replace_marker(tpl, "FUZZ", "<script>alert(1)</script>");
        verify res == "GET /search?q=<script>alert(1)</script>&category=<script>alert(1)</script> HTTP/1.1", "Markers replaced";
        print("FUZZ_REPLACE_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "FUZZ_REPLACE_OK" in res.stdout

def test_fuzzer_url_encoding():
    code = """
    import "std:security:fuzzer"
    fn main() -> int {
        let payload = "admin' OR '1'='1";
        let enc = fuzz_url_encode(payload);
        verify enc == "admin%27%20OR%20%271%27%3D%271", "URL encoded match";

        let dbl = fuzz_double_encode(payload);
        verify dbl == "admin%2527%2520OR%2520%25271%2527%253D%25271", "Double URL encoded match";

        print("ENCODING_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "ENCODING_OK" in res.stdout

def test_fuzzer_null_byte_injection():
    code = """
    import "std:security:fuzzer"
    fn main() -> int {
        let path = "image.png";
        let poisoned = fuzz_add_null_byte(path);
        verify poisoned == "image.png%00", "Null byte injected";
        print("NULL_BYTE_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "NULL_BYTE_OK" in res.stdout

def test_fuzzer_wordlist_loader():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as tf:
        tf.write("admin\nroot\nguest\nmoderator\n")
        wpath = tf.name

    try:
        code = f"""
        import "std:security:fuzzer"
        fn main() -> int {{
            let wl = wordlist_load("{wpath}");
            let count = wordlist_count(wl);
            verify count == 4, "4 wordlist items";
            let w0 = wordlist_get(wl, 0);
            let w1 = wordlist_get(wl, 1);
            let w2 = wordlist_get(wl, 2);
            let w3 = wordlist_get(wl, 3);
            verify w0 == "admin", "admin line";
            verify w1 == "root", "root line";
            verify w2 == "guest", "guest line";
            verify w3 == "moderator", "moderator line";
            let oob = wordlist_get(wl, 99);
            verify oob == "", "Out of bounds is empty";
            wordlist_free(wl);
            print("WORDLIST_LOAD_OK");
            return 0;
        }}
        """
        res = compile_and_run(code)
        assert res.returncode == 0
        assert "WORDLIST_LOAD_OK" in res.stdout
    finally:
        if os.path.exists(wpath):
            os.remove(wpath)

# =========================================================================
# 3. std:time:date TESTS
# =========================================================================

def test_date_iso_and_epoch():
    code = """
    import "std:time:date"
    fn main() -> int {
        let iso = date_now_iso();
        verify len(iso) == 20, "ISO 8601 format length 20 (YYYY-MM-DDTHH:MM:SSZ)";
        let ep = date_now_epoch();
        verify ep > 1700000000, "Epoch must be valid Unix timestamp";
        let diff = date_diff_seconds(ep + 60, ep);
        verify diff == 60, "Diff 60 seconds";
        let diff_rev = date_diff_seconds(ep, ep + 60);
        verify diff_rev == 60, "Absolute diff 60 seconds";
        print("DATE_BASIC_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "DATE_BASIC_OK" in res.stdout

def test_date_format_epoch():
    code = """
    import "std:time:date"
    fn main() -> int {
        // 1700000000 = 2023-11-14 22:13:20 UTC
        let s = date_format_epoch(1700000000, "%Y-%m-%d");
        verify s == "2023-11-14", "Formatted date match";
        let st = date_format_epoch(1700000000, "%H:%M:%S");
        verify st == "22:13:20", "Formatted time match";
        print("FORMAT_EPOCH_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "FORMAT_EPOCH_OK" in res.stdout

# =========================================================================
# 4. std:io:csv TESTS
# =========================================================================

def test_csv_basic_generation():
    code = """
    import "std:io:csv"
    fn main() -> int {
        let c = csv_create();
        csv_add_row(c, ["id", "vuln", "severity"]);
        csv_add_row(c, ["1", "SQL Injection", "CRITICAL"]);
        csv_add_row(c, ["2", "Open Redirect", "LOW"]);
        let s = csv_to_str(c);
        print(s);
        csv_free(c);
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "id,vuln,severity\n1,SQL Injection,CRITICAL\n2,Open Redirect,LOW\n" in res.stdout

def test_csv_rfc4180_escaping():
    code = r"""
    import "std:io:csv"
    fn main() -> int {
        let c = csv_create();
        csv_add_row(c, ["name", "description"]);
        csv_add_row(c, ["test, comma", "contains \"quotes\" inside"]);
        let s = csv_to_str(c);
        print(s);
        csv_free(c);
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert '"test, comma","contains ""quotes"" inside"\n' in res.stdout

def test_csv_save_and_verify():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        tmp_csv = f.name

    try:
        code = f"""
        import "std:io:csv"
        fn main() -> int {{
            let c = csv_create();
            csv_add_row(c, ["HOST", "PORT", "STATUS"]);
            csv_add_row(c, ["127.0.0.1", "443", "OPEN"]);
            let ok = csv_save_file(c, "{tmp_csv}");
            verify ok == true, "Save file must return true";
            csv_free(c);
            print("CSV_SAVED_OK");
            return 0;
        }}
        """
        res = compile_and_run(code)
        assert res.returncode == 0
        assert "CSV_SAVED_OK" in res.stdout
        with open(tmp_csv, "r", encoding="utf-8") as f:
            content = f.read()
        assert "HOST,PORT,STATUS\n127.0.0.1,443,OPEN\n" == content
    finally:
        if os.path.exists(tmp_csv):
            os.remove(tmp_csv)

# =========================================================================
# 5. std:cli:args TESTS
# =========================================================================

def test_cli_args_commandline():
    code = """
    import "std:cli:args"
    fn main() -> int {
        let count = cli_args_count();
        verify count >= 1, "Count at least 1 (program name)";
        let has_verbose = cli_has_flag("--verbose");
        verify has_verbose == true, "Must have --verbose flag";
        let has_debug = cli_has_flag("--debug");
        verify has_debug == false, "Must not have --debug flag";
        let target = cli_get_option("--target", "default_target");
        verify target == "https://api.gateway.local", "Target option match";
        let port = cli_get_int_option("-p", 80);
        verify port == 8443, "Port integer option match";
        let threads = cli_get_int_option("--threads", 4);
        verify threads == 4, "Fallback default value 4";
        print("CLI_ARGS_CLI_OK");
        return 0;
    }
    """
    args = ["--target", "https://api.gateway.local", "-p", "8443", "--verbose"]
    res = compile_and_run(code, args=args)
    assert res.returncode == 0
    assert "CLI_ARGS_CLI_OK" in res.stdout

def test_cli_args_synthetic_set():
    code = """
    import "std:cli:args"
    fn main() -> int {
        cli_set_args(["my_scanner", "--host=10.0.0.1", "-f", "--threads", "16"]);
        verify cli_args_count() == 5, "Count 5";
        verify cli_has_flag("-f") == true, "Flag -f present";
        verify cli_get_option("--host", "") == "10.0.0.1", "Equal-separated host parsed";
        verify cli_get_int_option("--threads", 1) == 16, "Threads parsed";
        print("CLI_SYNTHETIC_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "CLI_SYNTHETIC_OK" in res.stdout

# =========================================================================
# 6. LLVM IR BACKEND INTEGRATION TEST FOR PACKET 4
# =========================================================================

def test_packet4_llvm_backend():
    code = """
    import "std:collections:queue"
    import "std:security:fuzzer"
    import "std:time:date"
    import "std:cli:args"

    fn main() -> int {
        // 1. Queue in LLVM
        let q = queue_create();
        queue_push(q, "LLVM_JOB_1");
        let j1 = queue_pop(q);
        verify j1 == "LLVM_JOB_1", "LLVM Queue match";
        queue_free(q);

        // 2. Fuzzer in LLVM
        let enc = fuzz_url_encode("hello world");
        verify enc == "hello%20world", "LLVM URL encode";

        // 3. Date in LLVM
        let iso = date_now_iso();
        verify len(iso) == 20, "LLVM Date ISO length 20";

        // 4. CLI in LLVM
        cli_set_args(["llvm_test", "--opt", "LLVM_VAL"]);
        let v = cli_get_option("--opt", "none");
        verify v == "LLVM_VAL", "LLVM CLI option match";

        print("LLVM_PACKET4_SUCCESS");
        return 0;
    }
    """
    res = compile_and_run_llvm(code)
    assert res.returncode == 0
    assert "LLVM_PACKET4_SUCCESS" in res.stdout

# =========================================================================
# 7. INTEGRATED PIPELINE TEST
# =========================================================================

def test_packet4_integrated_scanner():
    code = """
    import "std:collections:queue"
    import "std:security:fuzzer"
    import "std:time:date"
    import "std:io:csv"
    import "std:cli:args"

    fn main() -> int {
        cli_set_args(["axiom_fuzzer", "--url", "http://app.internal/api?id=FUZZ"]);
        let target_url = cli_get_option("--url", "");
        verify target_url == "http://app.internal/api?id=FUZZ", "URL argument received";

        let q = queue_create();
        queue_push(q, "1' OR '1'='1");
        queue_push(q, "<script>alert(1)</script>");
        queue_push(q, "../../../../etc/passwd");

        let csv = csv_create();
        csv_add_row(csv, ["TIMESTAMP", "TARGET", "PAYLOAD", "STATUS"]);

        while queue_is_empty(q) == false {
            let payload = queue_pop(q);
            let encoded_payload = fuzz_url_encode(payload);
            let final_url = fuzz_replace_marker(target_url, "FUZZ", encoded_payload);
            let timestamp = date_now_iso();
            csv_add_row(csv, [timestamp, final_url, payload, "TESTED"]);
        }

        let report = csv_to_str(csv);
        verify len(report) > 50, "CSV Report generated";

        queue_free(q);
        csv_free(csv);
        print("PIPELINE_PACKET4_SUCCESS");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "PIPELINE_PACKET4_SUCCESS" in res.stdout

def test_example_13_direct():
    example_path = str(Path(__file__).resolve().parent.parent / "examples" / "13_packet4_fuzzer_scanner.ax")
    with open(example_path, "r", encoding="utf-8") as f:
        code = f.read()
    res = compile_and_run(code, example_path)
    assert res.returncode == 0
    assert "[BASARILI] PAKET 4" in res.stdout

def test_packet4_cli_example():
    axiom_bin = str(Path(__file__).resolve().parent.parent / "bin" / "axiom")
    example_path = str(Path(__file__).resolve().parent.parent / "examples" / "13_packet4_fuzzer_scanner.ax")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)

    res = subprocess.run(["python3", axiom_bin, "run", example_path], capture_output=True, text=True, env=env)
    assert res.returncode == 0
    assert "[BASARILI] PAKET 4" in res.stdout

def test_fuzzer_marker_not_found():
    code = """
    import "std:security:fuzzer"
    fn main() -> int {
        let tpl = "http://api.com/users/list";
        let res = fuzz_replace_marker(tpl, "FUZZ", "123");
        verify res == tpl, "Template unchanged if marker not found";
        print("NOT_FOUND_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "NOT_FOUND_OK" in res.stdout

def test_fuzzer_empty_payload():
    code = """
    import "std:security:fuzzer"
    fn main() -> int {
        let tpl = "prefix_FUZZ_suffix";
        let res = fuzz_replace_marker(tpl, "FUZZ", "");
        verify res == "prefix__suffix", "Marker replaced with empty";
        print("EMPTY_PAYLOAD_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "EMPTY_PAYLOAD_OK" in res.stdout

def test_fuzzer_wordlist_nonexistent():
    code = """
    import "std:security:fuzzer"
    fn main() -> int {
        let wl = wordlist_load("/nonexistent_path_xyz_12345.txt");
        let count = wordlist_count(wl);
        verify count == 0, "Count 0 for nonexistent file";
        let val = wordlist_get(wl, 0);
        verify val == "", "Empty string for nonexistent file items";
        wordlist_free(wl);
        print("NONEXISTENT_WL_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "NONEXISTENT_WL_OK" in res.stdout

def test_date_diff_zero():
    code = """
    import "std:time:date"
    fn main() -> int {
        let ep = date_now_epoch();
        let diff = date_diff_seconds(ep, ep);
        verify diff == 0, "Diff with self must be 0";
        print("DATE_DIFF_ZERO_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "DATE_DIFF_ZERO_OK" in res.stdout

def test_csv_empty():
    code = """
    import "std:io:csv"
    fn main() -> int {
        let c = csv_create();
        let s = csv_to_str(c);
        verify s == "", "Empty CSV gives empty string";
        csv_free(c);
        print("CSV_EMPTY_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "CSV_EMPTY_OK" in res.stdout

def test_cli_args_missing_and_defaults():
    code = """
    import "std:cli:args"
    fn main() -> int {
        cli_set_args(["prog", "--flag1"]);
        let opt = cli_get_option("--nonexistent", "FALLBACK");
        verify opt == "FALLBACK", "Fallback string option";
        let int_opt = cli_get_int_option("--port", 9999);
        verify int_opt == 9999, "Fallback int option";
        verify cli_has_flag("--flag1") == true, "Flag exists";
        verify cli_has_flag("--flag2") == false, "Flag does not exist";
        print("CLI_DEFAULTS_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "CLI_DEFAULTS_OK" in res.stdout

def test_queue_large_throughput():
    code = """
    import "std:collections:queue"
    fn main() -> int {
        let q = queue_create();
        let mut i = 0;
        while i < 1000 {
            queue_push(q, "throughput_item");
            i = i + 1;
        }
        verify queue_len(q) == 1000, "1000 items in queue";
        let mut popped = 0;
        while popped < 1000 {
            let val = queue_pop(q);
            verify val == "throughput_item", "Item match";
            popped = popped + 1;
        }
        verify queue_is_empty(q) == true, "Empty after 1000 pops";
        queue_free(q);
        print("THROUGHPUT_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "THROUGHPUT_OK" in res.stdout

def test_fuzzer_nested_markers():
    code = """
    import "std:security:fuzzer"
    fn main() -> int {
        let tpl = "HEADER=FUZZ;URI=/FUZZ/sub;QUERY=id=FUZZ";
        let res = fuzz_replace_marker(tpl, "FUZZ", "TEST_INJECT");
        verify res == "HEADER=TEST_INJECT;URI=/TEST_INJECT/sub;QUERY=id=TEST_INJECT", "Multiple occurrences replaced";
        print("NESTED_MARKERS_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "NESTED_MARKERS_OK" in res.stdout

def test_date_iso_regex_validation():
    code = """
    import "std:time:date"
    import "std:text:regex"
    fn main() -> int {
        let iso = date_now_iso();
        let matches = regex_is_match("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$", iso);
        verify matches == true, "ISO 8601 regex pattern must strictly match";
        print("ISO_REGEX_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "ISO_REGEX_OK" in res.stdout

def test_csv_multiline_fields():
    code = """
    import "std:io:csv"
    fn main() -> int {
        let c = csv_create();
        csv_add_row(c, ["col1", "col2"]);
        csv_add_row(c, ["first line\\nsecond line", "normal"]);
        let s = csv_to_str(c);
        verify len(s) > 10, "CSV with multiline field parsed";
        csv_free(c);
        print("CSV_MULTILINE_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "CSV_MULTILINE_OK" in res.stdout

def test_cli_args_boundary_indices():
    code = """
    import "std:cli:args"
    fn main() -> int {
        cli_set_args(["test_runner", "arg1", "arg2"]);
        let neg = cli_args_get(-1);
        let oob = cli_args_get(100);
        verify neg == "", "Negative index returns empty string";
        verify oob == "", "Out of bounds index returns empty string";
        let valid = cli_args_get(0);
        verify valid == "test_runner", "First index is program name";
        print("CLI_BOUNDS_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "CLI_BOUNDS_OK" in res.stdout

def test_cli_args_empty_set():
    code = """
    import "std:cli:args"
    fn main() -> int {
        cli_set_args([]);
        verify cli_args_count() == 0, "Empty args count is 0";
        verify cli_has_flag("--any") == false, "No flag in empty args";
        let opt = cli_get_option("--any", "DEF");
        verify opt == "DEF", "Default returned for empty args";
        print("CLI_EMPTY_OK");
        return 0;
    }
    """
    res = compile_and_run(code)
    assert res.returncode == 0
    assert "CLI_EMPTY_OK" in res.stdout


