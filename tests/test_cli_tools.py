"""
Axiom Programming Language (λx) - CLI Tools Tests (axiom init & axiom fmt)
"""
import subprocess
import tempfile
import shutil
from pathlib import Path
import pytest

from axiom.formatter import AxiomFormatter, format_source

AXIOM_BIN = Path(__file__).resolve().parent.parent / "bin" / "axiom"

def test_cli_init_creates_project(tmp_path):
    proj_name = "security_agent"
    target_dir = tmp_path / proj_name

    cmd = [str(AXIOM_BIN), "init", str(target_dir)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Yeni Axiom projesi" in res.stdout

    # Dosya varlığı kontrolleri
    assert (target_dir / "axiom.toml").exists()
    assert (target_dir / "src" / "main.ax").exists()
    assert (target_dir / "README.md").exists()
    assert (target_dir / ".gitignore").exists()

    # axiom.toml içeriği
    toml_content = (target_dir / "axiom.toml").read_text(encoding="utf-8")
    assert f'name = "{str(target_dir)}"' in toml_content or proj_name in toml_content

    # Proje kaynak kodunun check ve run testleri
    main_ax = target_dir / "src" / "main.ax"
    res_check = subprocess.run([str(AXIOM_BIN), "check", str(main_ax)], capture_output=True, text=True)
    assert res_check.returncode == 0
    assert "Doğrulama Başarılı" in res_check.stdout

    res_run = subprocess.run([str(AXIOM_BIN), "run", str(main_ax)], capture_output=True, text=True)
    assert res_run.returncode == 0
    assert "Hello from Axiom project" in res_run.stdout

def test_cli_init_fails_on_existing_nonempty_directory(tmp_path):
    proj_dir = tmp_path / "existing_proj"
    proj_dir.mkdir()
    (proj_dir / "dummy.txt").write_text("already here", encoding="utf-8")

    cmd = [str(AXIOM_BIN), "init", str(proj_dir)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode != 0
    assert "zaten mevcut ve boş değil" in res.stderr

def test_formatter_unit_simple():
    raw_code = """
fn   calc( x :int,y:  int )->int
requires x>0
ensures return >0
{
let z=x*y
return z
}
"""
    formatted = format_source(raw_code)
    expected_lines = [
        "fn calc(x: int, y: int) -> int",
        "    requires x > 0",
        "    ensures return > 0",
        "{",
        "    let z = x * y",
        "    return z",
        "}"
    ]
    for line in expected_lines:
        assert line in formatted

def test_cli_fmt_in_place_and_check(tmp_path):
    bad_code = """
fn compute( a : int ) -> int
requires a >= 0
{
let mut val = a + 10
if val > 15 {
print( "greater" )
} else {
print( "smaller" )
}
return val
}

fn main() -> void {
let res = compute( 10 )
print( "Result:" , res )
}
"""
    test_file = tmp_path / "test_unformatted.ax"
    test_file.write_text(bad_code, encoding="utf-8")

    # 1. --check bayrağı formatlanmamış dosyada 1 dönmeli
    res_check1 = subprocess.run([str(AXIOM_BIN), "fmt", "--check", str(test_file)], capture_output=True, text=True)
    assert res_check1.returncode == 1
    assert "Biçimlendirme gerekli" in res_check1.stderr

    # 2. axiom fmt dosyayı düzeltmeli
    res_fmt = subprocess.run([str(AXIOM_BIN), "fmt", str(test_file)], capture_output=True, text=True)
    assert res_fmt.returncode == 0
    assert "Formatlandı" in res_fmt.stdout

    # 3. Şimdi --check 0 dönmeli
    res_check2 = subprocess.run([str(AXIOM_BIN), "fmt", "--check", str(test_file)], capture_output=True, text=True)
    assert res_check2.returncode == 0
    assert "Doğrulandı" in res_check2.stdout

    # 4. Formatlanmış kodun hatasız çalıştığı doğrulanmalı
    res_run = subprocess.run([str(AXIOM_BIN), "run", str(test_file)], capture_output=True, text=True)
    assert res_run.returncode == 0
    assert "greater" in res_run.stdout
    assert "Result: 20" in res_run.stdout

def test_cli_fmt_preserves_strings_and_comments(tmp_path):
    code_with_strings = '''
// Header Comment: Security Module
# Alternative hash comment

fn format_test() -> void {
    // Inner comment
    let message = "   spaced   literal   "
    print(message)
}
'''
    test_file = tmp_path / "test_strings.ax"
    test_file.write_text(code_with_strings, encoding="utf-8")

    res_fmt = subprocess.run([str(AXIOM_BIN), "fmt", str(test_file)], capture_output=True, text=True)
    assert res_fmt.returncode == 0

    formatted_content = test_file.read_text(encoding="utf-8")
    assert '"   spaced   literal   "' in formatted_content
    assert "// Header Comment: Security Module" in formatted_content
    assert "# Alternative hash comment" in formatted_content

def test_formatter_handles_while_and_for_loops():
    code = """
fn loop_test() -> void {
let mut count = 0
while count < 5 {
count = count + 1
}
for i in 0..10 {
print(i)
}
}
"""
    formatted = format_source(code)
    assert "while count < 5 {" in formatted
    assert "for i in 0..10 {" in formatted
    assert "    count = count + 1" in formatted

def test_formatter_handles_struct_definitions():
    code = """
struct ServerConfig {
host: str,
port: int,
ssl_enabled: bool
}
"""
    formatted = format_source(code)
    assert "struct ServerConfig {" in formatted
    assert "    host: str," in formatted
    assert "    port: int," in formatted
    assert "    ssl_enabled: bool" in formatted

def test_cli_prove_command_success(tmp_path):
    test_file = tmp_path / "valid_code.ax"
    test_file.write_text("""
    fn safe_worker(x: int) -> int
        requires x >= 10 and x <= 100
        ensures return >= 0
    {
        return x * 2;
    }

    fn main() -> int {
        return safe_worker(50);
    }
    """, encoding="utf-8")

    cmd = [str(AXIOM_BIN), "prove", str(test_file)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Statik Matematiksel İspat Başarılı" in res.stdout
    assert "Doğrulanan Fonksiyon Sayısı" in res.stdout

def test_cli_prove_command_failure(tmp_path):
    test_file = tmp_path / "invalid_code.ax"
    test_file.write_text("""
    fn safe_worker(x: int) -> int
        requires x >= 10 and x <= 100
    {
        return x * 2;
    }

    fn main() -> int {
        return safe_worker(5);
    }
    """, encoding="utf-8")

    cmd = [str(AXIOM_BIN), "prove", str(test_file)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode != 0
    assert "Axiom Statik Matematiksel İspat Hatası" in res.stderr

