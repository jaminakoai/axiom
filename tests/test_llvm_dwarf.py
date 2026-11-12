import os
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

AXIOM_BIN = Path(__file__).resolve().parent.parent / "bin" / "axiom"


def _run_cli(args, timeout=60):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


def _write(src: str, ext: str = ".ax") -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=ext, delete=False)
    f.write(src)
    f.close()
    return f.name


def test_llvm_ir_contains_dwarf_metadata_when_debug_enabled():
    src = """
    fn add(a: int, b: int) -> int {
        let sum = a + b
        return sum
    }

    fn main() -> int {
        let x = 10
        let y = 20
        let res = add(x, y)
        print(res)
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "emit-llvm", "-g", path])
        assert res.returncode == 0, res.stdout + res.stderr
        ir = res.stdout

        # DWARF Modül Düzeyi Metadata Kontrolleri
        assert "!llvm.dbg.cu" in ir, "Modül düzeyinde !llvm.dbg.cu metadata bulunamadı"
        assert "!DICompileUnit" in ir, "DICompileUnit tanımı bulunamadı"
        assert "!DIFile" in ir, "DIFile tanımı bulunamadı"
        assert os.path.basename(path) in ir, f"Kaynak dosya adı ({os.path.basename(path)}) DIFile içinde bulunamadı"
        assert "!DISubprogram" in ir, "DISubprogram tanımı bulunamadı"
        assert "!DILocation" in ir, "DILocation tanımı bulunamadı"

        # Fonksiyon ve instruksiyon seviyesinde !dbg referansları
        assert "!dbg" in ir, "İnstruksiyonlarda !dbg metadata referansı bulunamadı"
    finally:
        os.remove(path)


def test_llvm_binary_contains_dwarf_line_info():
    src = """
    fn calculate(base: int, mult: int) -> int {
        let step1 = base * mult
        let step2 = step1 + 42
        return step2
    }

    fn main() -> int {
        let v = calculate(10, 5)
        print("Sonuc:", v)
        return 0
    }
    """
    path = _write(src)
    base_name = os.path.basename(path)
    out_bin = path + ".bin"
    try:
        build_res = _run_cli([str(AXIOM_BIN), "build", "-g", "--backend=llvm", path, "-o", out_bin])
        assert build_res.returncode == 0, build_res.stdout + build_res.stderr
        assert os.path.exists(out_bin), "Üretilen ikili dosya bulunamadı"

        # İkiliyi çalıştırarak doğrula
        run_res = subprocess.run([out_bin], capture_output=True, text=True)
        assert run_res.returncode == 0
        assert "Sonuc: 92" in run_res.stdout

        # readelf ile .debug_line tablosunu kontrol et
        readelf_res = subprocess.run(["readelf", "--debug-dump=line", out_bin], capture_output=True, text=True)
        assert readelf_res.returncode == 0, readelf_res.stderr

        dump_output = readelf_res.stdout
        assert base_name in dump_output, f"readelf .debug_line çıktısında '{base_name}' kaynak dosyası bulunamadı!\n{dump_output}"
        assert "The File Name Table" in dump_output or "Line Number Statements" in dump_output

        # readelf ile .debug_info tablosunda fonksiyon sembollerini de kontrol et
        info_res = subprocess.run(["readelf", "--debug-dump=info", out_bin], capture_output=True, text=True)
        assert info_res.returncode == 0, info_res.stderr
        info_output = info_res.stdout
        assert "calculate" in info_output or "ax_calculate" in info_output, f"readelf .debug_info çıktısında fonksiyon sembolü bulunamadı!\n{info_output}"
    finally:
        if os.path.exists(path):
            os.remove(path)
        if os.path.exists(out_bin):
            os.remove(out_bin)


def test_llvm_dwarf_emits_local_variables():
    src = """
    fn calc(a: int, b: int) -> int {
        let product = a * b
        return product
    }
    fn main() -> int {
        let result = calc(6, 7)
        print(result)
        return 0
    }
    """
    path = _write(src)
    try:
        res = _run_cli([str(AXIOM_BIN), "emit-llvm", "-g", path])
        assert res.returncode == 0, res.stdout + res.stderr
        ir = res.stdout
        assert "!DILocalVariable" in ir, "DILocalVariable metadata bulunamadi"
        assert "llvm.dbg.declare" in ir, "llvm.dbg.declare cagrisi bulunamadi"
        assert 'name: "product"' in ir
        assert 'name: "result"' in ir

        out_bin = path + ".bin"
        build = _run_cli([str(AXIOM_BIN), "build", "-g", "--backend=llvm", path, "-o", out_bin])
        assert build.returncode == 0, build.stdout + build.stderr
        try:
            info = subprocess.run(["readelf", "--debug-dump=info", out_bin], capture_output=True, text=True)
            assert info.returncode == 0
            assert "DW_TAG_variable" in info.stdout
            assert "product" in info.stdout or "result" in info.stdout
        finally:
            if os.path.exists(out_bin):
                os.remove(out_bin)
    finally:
        if os.path.exists(path):
            os.remove(path)
