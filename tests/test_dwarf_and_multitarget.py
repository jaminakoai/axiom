"""
Axiom Programming Language (λx) - DWARF Debug Symbols & Multi-Target Tests
Faz 5.3 & Faz 5.4 Kapsamlı Test Suiti:
- DWARF #line direktiflerinin C kodunda doğru satır ve dosya referanslarıyla üretilmesi
- `axiom build -g` ve `axiom run -g` ile DWARF hata ayıklama sembollü ELF ikili dosyası üretimi
- `readelf --debug-dump=line` ile Axiom kaynak (.ax) dosyasının ve satır tablolarının doğrulanması
- `get_target_compiler_flags` mimari hedef çözücüsü (x86_64, aarch64, wasm32)
- Çoklu mimari hedef parametresi (`--target`) ile derleme testleri
"""

import os
import subprocess
from pathlib import Path
import pytest

from axiom.cli import compile_axiom_source, get_target_compiler_flags, find_c_compiler
from axiom.codegen_c import CCodeGenerator

AXIOM_BIN = Path(__file__).resolve().parent.parent / "bin" / "axiom"


def test_dwarf_line_directives_in_c_code():
    source_code = """fn calculate(x: int) -> int {
    let y = x * 10
    return y + 5
}

fn main() -> void {
    let res = calculate(2)
    print("Res:", res)
}
"""
    source_path = "/home/test/sample.ax"
    c_code = compile_axiom_source(source_code, source_path=source_path, debug=True)

    # 1. C kodunda #line direktifleri bulunmalı
    assert f'#line 1 "{source_path}"' in c_code or f'#line 2 "{source_path}"' in c_code
    assert f'"{source_path}"' in c_code
    assert "#line" in c_code

    # 2. debug=False iken #line direktifleri üretilmemeli
    c_code_nodebug = compile_axiom_source(source_code, source_path=source_path, debug=False)
    assert "#line" not in c_code_nodebug


def test_dwarf_elf_binary_and_readelf(tmp_path):
    source = """fn worker(n: int) -> int {
    let mut acc = 0
    let mut i = 0
    while i < n {
        acc = acc + i
        i = i + 1
    }
    return acc
}

fn main() -> void {
    let total = worker(5)
    print("Total:", total)
}
"""
    source_file = tmp_path / "worker.ax"
    source_file.write_text(source, encoding="utf-8")
    out_bin = tmp_path / "worker_debug_bin"

    # 1. -g ile derleme
    cmd = [str(AXIOM_BIN), "build", "-g", str(source_file), "-o", str(out_bin)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert out_bin.exists()

    # 2. readelf veya objdump ile ELF DWARF tablosunda worker.ax varlığını doğrula
    readelf_res = subprocess.run(
        ["readelf", "--debug-dump=line", str(out_bin)],
        capture_output=True,
        text=True
    )
    if readelf_res.returncode == 0:
        assert "worker.ax" in readelf_res.stdout
    else:
        # Fallback objdump
        objdump_res = subprocess.run(
            ["objdump", "-g", str(out_bin)],
            capture_output=True,
            text=True
        )
        assert "worker.ax" in objdump_res.stdout

    # 3. Çalıştırma testi
    run_res = subprocess.run([str(out_bin)], capture_output=True, text=True)
    assert run_res.returncode == 0
    assert "Total: 10" in run_res.stdout


def test_axiom_run_with_debug_flag(tmp_path):
    source = """fn main() -> void {
    let msg = "Debug calisiyor"
    print(msg)
}
"""
    src_file = tmp_path / "debug_run.ax"
    src_file.write_text(source, encoding="utf-8")

    cmd = [str(AXIOM_BIN), "run", "-g", str(src_file)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Debug calisiyor" in res.stdout


def test_multitarget_resolution_flags():
    cc = find_c_compiler()

    # x86_64 hedefi
    target_cc, flags = get_target_compiler_flags("x86_64", cc)
    assert any("x86_64-linux-gnu" in f for f in flags) or "x86_64" in target_cc

    # aarch64 hedefi
    target_cc2, flags2 = get_target_compiler_flags("aarch64", cc)
    assert any("aarch64-linux-gnu" in f for f in flags2) or "aarch64" in target_cc2

    # wasm32 hedefi
    target_cc3, flags3 = get_target_compiler_flags("wasm32-wasi", cc)
    assert any("wasm32-wasi" in f for f in flags3)


def test_multitarget_build_x86_64(tmp_path):
    source = """fn main() -> void {
    print("Multi-Target x86_64 OK")
}
"""
    src_file = tmp_path / "mt_test.ax"
    src_file.write_text(source, encoding="utf-8")
    out_bin = tmp_path / "mt_x86_bin"

    cmd = [
        str(AXIOM_BIN), "build",
        "--target", "x86_64-linux-gnu",
        str(src_file),
        "-o", str(out_bin)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert out_bin.exists()

    run_res = subprocess.run([str(out_bin)], capture_output=True, text=True)
    assert run_res.returncode == 0
    assert "Multi-Target x86_64 OK" in run_res.stdout


def test_multitarget_missing_sysroot_guidance_wasm(tmp_path):
    src_file = tmp_path / "wasm_test.ax"
    src_file.write_text("fn main() -> void { print(\"wasm\"); }\n", encoding="utf-8")
    out_bin = tmp_path / "out.wasm"

    cmd = [
        str(AXIOM_BIN), "build",
        "--target", "wasm32-wasi",
        str(src_file),
        "-o", str(out_bin)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode != 0
    assert "Hata: 'wasm32-wasi' hedefi için WASI SDK veya sysroot bulunamadı" in res.stderr
    assert "WASI SDK kurun" in res.stderr or "--sysroot" in res.stderr


def test_multitarget_missing_sysroot_guidance_aarch64(tmp_path):
    src_file = tmp_path / "arm_test.ax"
    src_file.write_text("fn main() -> void { print(\"arm\"); }\n", encoding="utf-8")
    out_bin = tmp_path / "out_arm.bin"

    cmd = [
        str(AXIOM_BIN), "build",
        "--target", "aarch64",
        str(src_file),
        "-o", str(out_bin)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode != 0
    assert "Hata: 'aarch64' hedefi için cross-toolchain veya sysroot bulunamadı" in res.stderr
    assert "cross-toolchain" in res.stderr or "--sysroot" in res.stderr

