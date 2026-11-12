"""
Unit & Integration Tests for File I/O and OS System Calls in Axiom
"""
import pytest
import os
import subprocess
from pathlib import Path

from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.checker import TypeChecker, SemanticError
from axiom.cli import compile_axiom_source, find_c_compiler

def run_axiom_snippet(tmp_path, code: str) -> tuple[int, str, str]:
    c_code = compile_axiom_source(code, str(tmp_path / "snippet.ax"))
    cc = find_c_compiler()
    c_file = tmp_path / "snip.c"
    bin_file = tmp_path / "snip.bin"
    c_file.write_text(c_code, encoding="utf-8")

    compile_res = subprocess.run([cc, "-O2", str(c_file), "-o", str(bin_file)], capture_output=True, text=True)
    assert compile_res.returncode == 0, compile_res.stderr

    run_res = subprocess.run([str(bin_file)], capture_output=True, text=True)
    return run_res.returncode, run_res.stdout, run_res.stderr

def test_typechecker_file_write_valid():
    code = 'let ok: bool = file_write("/tmp/foo.txt", "hello")'
    prog = Parser(Lexer(code).tokenize()).parse()
    checker = TypeChecker()
    checker.check(prog)

def test_typechecker_file_write_invalid_arg():
    code = 'let ok = file_write(123, "hello")'
    prog = Parser(Lexer(code).tokenize()).parse()
    checker = TypeChecker()
    with pytest.raises(SemanticError) as exc_info:
        checker.check(prog)
    assert "file_write" in str(exc_info.value)

def test_typechecker_file_read_valid():
    code = 'let content: str = file_read("/tmp/foo.txt")'
    prog = Parser(Lexer(code).tokenize()).parse()
    checker = TypeChecker()
    checker.check(prog)

def test_typechecker_file_read_invalid_ret():
    code = 'let content: int = file_read("/tmp/foo.txt")'
    prog = Parser(Lexer(code).tokenize()).parse()
    checker = TypeChecker()
    with pytest.raises(SemanticError) as exc_info:
        checker.check(prog)
    assert "Tip uyumsuzlugu" in str(exc_info.value)

def test_typechecker_file_exists_valid():
    code = 'let ex: bool = file_exists("/tmp/foo.txt")'
    prog = Parser(Lexer(code).tokenize()).parse()
    checker = TypeChecker()
    checker.check(prog)

def test_typechecker_os_exec_valid():
    code = 'let ret: int = os_exec("ls -la")'
    prog = Parser(Lexer(code).tokenize()).parse()
    checker = TypeChecker()
    checker.check(prog)

def test_typechecker_os_getenv_valid():
    code = 'let home: str = os_getenv("HOME")'
    prog = Parser(Lexer(code).tokenize()).parse()
    checker = TypeChecker()
    checker.check(prog)

def test_file_write_and_read_e2e(tmp_path):
    target_file = tmp_path / "test_io_e2e.txt"
    code = f'''
fn main() -> int {{
    let path = "{target_file}"
    let w_ok = file_write(path, "AXIOM_NATIVE_IO_PAYLOAD_123")
    verify w_ok == true, "Yazma basarili olmali"
    let content = file_read(path)
    print("CONTENT:", content)
    verify content == "AXIOM_NATIVE_IO_PAYLOAD_123", "Icerik eslesmeli"
    return 0
}}
'''
    ret, stdout, stderr = run_axiom_snippet(tmp_path, code)
    assert ret == 0
    assert "CONTENT: AXIOM_NATIVE_IO_PAYLOAD_123" in stdout
    assert target_file.read_text(encoding="utf-8") == "AXIOM_NATIVE_IO_PAYLOAD_123"

def test_file_exists_e2e(tmp_path):
    existing = tmp_path / "exist.txt"
    existing.write_text("dummy", encoding="utf-8")
    missing = tmp_path / "missing.txt"

    code = f'''
fn main() -> int {{
    let ex_yes = file_exists("{existing}")
    let ex_no = file_exists("{missing}")
    print("YES:", ex_yes)
    print("NO:", ex_no)
    verify ex_yes == true, "exist.txt var olmali"
    verify ex_no == false, "missing.txt yok olmali"
    return 0
}}
'''
    ret, stdout, _ = run_axiom_snippet(tmp_path, code)
    assert ret == 0
    assert "YES: true" in stdout
    assert "NO: false" in stdout

def test_file_read_missing_returns_empty(tmp_path):
    missing = tmp_path / "does_not_exist_xyz.txt"
    code = f'''
fn main() -> int {{
    let data = file_read("{missing}")
    print("LEN:", len(data))
    verify len(data) == 0, "Olmayan dosya bos metin donmeli"
    return 0
}}
'''
    ret, stdout, _ = run_axiom_snippet(tmp_path, code)
    assert ret == 0
    assert "LEN: 0" in stdout

def test_file_overwrite_e2e(tmp_path):
    target = tmp_path / "overwrite.txt"
    code = f'''
fn main() -> int {{
    let path = "{target}"
    file_write(path, "FIRST")
    let c1 = file_read(path)
    file_write(path, "SECOND_OVERWRITTEN")
    let c2 = file_read(path)
    print("C1:", c1)
    print("C2:", c2)
    verify c2 == "SECOND_OVERWRITTEN", "Icerik guncellenmeli"
    return 0
}}
'''
    ret, stdout, _ = run_axiom_snippet(tmp_path, code)
    assert ret == 0
    assert "C1: FIRST" in stdout
    assert "C2: SECOND_OVERWRITTEN" in stdout

def test_os_exec_success_and_failure(tmp_path):
    code = '''
fn main() -> int {
    let code_ok = os_exec("true")
    let code_fail = os_exec("sh -c 'exit 42'")
    print("CODE_OK:", code_ok)
    print("CODE_FAIL:", code_fail)
    verify code_ok == 0, "true komutu 0 donmeli"
    verify code_fail == 42, "exit 42 yakalanmali"
    return 0
}
'''
    ret, stdout, _ = run_axiom_snippet(tmp_path, code)
    assert ret == 0
    assert "CODE_OK: 0" in stdout
    assert "CODE_FAIL: 42" in stdout

def test_os_getenv_present_and_absent(tmp_path):
    os.environ["AXIOM_TEST_KEY"] = "SPECTRE_99"
    code = '''
fn main() -> int {
    let val_present = os_getenv("AXIOM_TEST_KEY")
    let val_absent = os_getenv("AXIOM_DEFINITELY_NOT_SET_123456")
    print("VAL:", val_present)
    print("ABSENT_LEN:", len(val_absent))
    verify val_present == "SPECTRE_99", "Cevre degiskeni okunmali"
    verify len(val_absent) == 0, "Olmayan degisken bos donmeli"
    return 0
}
'''
    ret, stdout, _ = run_axiom_snippet(tmp_path, code)
    assert ret == 0
    assert "VAL: SPECTRE_99" in stdout
    assert "ABSENT_LEN: 0" in stdout
