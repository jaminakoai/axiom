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

# readelf'in DWARF okuması, **bizim ürettiğimiz** hatalardan değil, binutils'ten
# kaynaklanan uyarılar verebilir: binutils bug 28981'e göre readelf, clang'ın
# ürettiği DWARF'ta "Unrecognized form: 0x22/0x23" ve "Bogus end-of-siblings
# marker" uyarıları basıyor (Buildroot bunu belgeliyor; binutils 2.46'da temiz).
#
# Bu yüzden testi readelf'in çıkış koduna bağlamıyoruz; bunun yerine
#  1) .debug_line/.debug_info çıktısında **aranan içeriğin** bulunmasını,
#  2) varsa pyelftools ile **bağımsız yapısal** doğrulamayı (DIE ağacı)
# istiyoruz. Böylece gerçek bir bozulma hâlâ yakalanır, araç sürümü farkı
# testi düşürmez.


def _readelf_dump(section: str, binary: str) -> str:
    """readelf çıktısını döndürür; hiç çıktı üretemezse hata verir."""
    res = subprocess.run(["readelf", f"--debug-dump={section}", binary],
                         capture_output=True, text=True, timeout=120)
    if not res.stdout.strip():
        raise AssertionError(
            f"readelf --debug-dump={section} hiç çıktı üretmedi "
            f"(kod {res.returncode}):\n{res.stderr}")
    return res.stdout


def _dwarf_dies(binary: str):
    """pyelftools varsa .debug_info DIE ağacını döndürür (bağımsız doğrulama)."""
    pytest.importorskip("elftools", reason="pyelftools yok")
    from elftools.elf.elffile import ELFFile

    with open(binary, "rb") as fh:
        dw = ELFFile(fh).get_dwarf_info()
        out = []
        for cu in dw.iter_CUs():
            stack = [cu.get_top_DIE()]
            while stack:
                die = stack.pop()
                name = die.attributes.get("DW_AT_name")
                out.append((die.tag, name.value.decode("utf-8", "replace") if name else None))
                stack.extend(die.iter_children())
        return out

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
        dump_output = _readelf_dump("line", out_bin)

        assert base_name in dump_output, f"readelf .debug_line çıktısında '{base_name}' kaynak dosyası bulunamadı!\n{dump_output}"
        assert "The File Name Table" in dump_output or "Line Number Statements" in dump_output

        # readelf ile .debug_info tablosunda fonksiyon sembollerini de kontrol et
        info_output = _readelf_dump("info", out_bin)
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
            info_output = _readelf_dump("info", out_bin)
            assert "DW_TAG_variable" in info_output
            assert "product" in info_output or "result" in info_output
        finally:
            if os.path.exists(out_bin):
                os.remove(out_bin)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_dwarf_structure_is_valid_via_independent_parser():
    """readelf'ten bağımsız: DIE ağacı subprogram + yerel değişken içermeli.

    binutils 2.38 gibi eski readelf sürümleri clang DWARF'ında yanıltıcı
    uyarılar basabildiği için yapı burada bağımsız bir ayrıştırıcıyla
    (pyelftools) doğrulanır.
    """
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
    out_bin = path + ".bin"
    try:
        build = _run_cli([str(AXIOM_BIN), "build", "-g", "--backend=llvm", path, "-o", out_bin], timeout=600)
        assert build.returncode == 0, build.stdout + build.stderr

        dies = _dwarf_dies(out_bin)
        tags = [t for t, _ in dies]
        names = [n for _, n in dies if n]

        assert "DW_TAG_subprogram" in tags
        assert "DW_TAG_variable" in tags
        # Axiom kaynağından gelen semboller (runtime.h sembolleri ayrı CU'da)
        assert any(n in ("ax_calc", "calc") for n in names)
        assert "product" in names
        assert "result" in names
        # Kaynak dosya adı CU'da görünmeli
        assert any(n and n.endswith(".ax") for n in names)
    finally:
        for p in (path, out_bin):
            if os.path.exists(p):
                os.remove(p)
