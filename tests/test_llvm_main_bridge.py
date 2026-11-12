"""
Axiom - LLVM `main() -> Result<int, str>` köprüsü (regresyon)

GERÇEK HATA (12 Kasım 2026, CI'da ortaya çıktı):
  LLVM arka ucu, `main` bir `Result` döndürdüğünde giriş köprüsünde

      define %struct.ax_Result_int_str @ax_main() { ... }
      define i32 @main(...) {
        call void @ax_main()          ; <-- tip uyuşmazlığı
        ret i32 0
      }

  üretiyordu. Sonuçlar:
    - clang 14 (Ubuntu 22.04 CI): sert derleme hatası
      "'@ax_main' defined with type '%struct... ()*' but expected 'void ()*'"
    - clang 21 (yerel): kabul ediyor ve **Err bilgisini sessizce düşürüyor**
      → `main -> Result` yazan program hatada exit 0 verebiliyordu.
  C arka ucunda aynı program doğru çalışıyordu (Err → stderr + exit 1), yani
  "iki arka uç eşit" ilkesi ihlal edilmişti.

DÜZELTME:
  Köprü artık `Result` yapısını doğrudan çağırır, `is_ok` alanını `extractvalue`
  ile okur, Err yolunda `error` alanını `axiom_eprint_error` ile stderr'e yazar
  ve 1 döndürür — C arka ucuyla birebir aynı davranış.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"

ERR_MAIN = '''import "std/core/error"

fn fail(n: int) -> Result<int, str> {
    return result_err_int("patladi: " + int_to_str(n))
}

fn main() -> Result<int, str> {
    print("calisiyor")
    let v = fail(7)?
    print("ULASILMAMALI", v)
    return result_ok<int>(0)
}
'''

OK_MAIN = '''import "std/core/error"

fn main() -> Result<int, str> {
    print("TAMAM")
    return result_ok<int>(0)
}
'''


def _emit_llvm(src: str) -> str:
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.ax"
        f.write_text(src, encoding="utf-8")
        out = Path(td) / "t.ll"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        res = subprocess.run(
            [str(AXIOM), "emit-llvm", str(f), "-o", str(out)],
            capture_output=True, text=True, timeout=300, env=env)
        assert res.returncode == 0, res.stdout + res.stderr
        return out.read_text(encoding="utf-8")


def _build_and_run(backend: str, src: str):
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.ax"
        f.write_text(src, encoding="utf-8")
        out = Path(td) / "t"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        args = [str(AXIOM), "build", str(f), "-o", str(out)]
        if backend == "llvm":
            args.insert(2, "--backend=llvm")
        b = subprocess.run(args, capture_output=True, text=True, timeout=600, env=env)
        assert b.returncode == 0, b.stdout + b.stderr
        return subprocess.run([str(out)], capture_output=True, text=True, timeout=120)


def test_llvm_main_bridge_does_not_call_struct_returning_main_as_void():
    """`call void @ax_main()` üretilmemeli (tip uyuşmazlığı)."""
    ir = _emit_llvm(ERR_MAIN)
    assert "call void @ax_main()" not in ir, (
        "LLVM köprüsü struct döndüren @ax_main'i void çağırıyor:\n"
        + "\n".join(ln for ln in ir.splitlines() if "ax_main" in ln))
    # Sözleşme: değer dönen çağrı + is_ok kontrolü
    assert "call %struct.ax_Result_int_str @ax_main()" in ir
    assert "extractvalue" in ir
    assert "@axiom_eprint_error" in ir


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_main_result_err_maps_to_exit_1(backend):
    """Err yolu: hata mesajı + exit 1, sonraki satır çalışmamalı."""
    r = _build_and_run(backend, ERR_MAIN)
    assert r.returncode == 1, f"{backend}: exit {r.returncode} (beklenen 1)\n{r.stdout}{r.stderr}"
    assert "ULASILMAMALI" not in r.stdout
    assert "patladi: 7" in (r.stdout + r.stderr)


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_main_result_ok_maps_to_exit_0(backend):
    r = _build_and_run(backend, OK_MAIN)
    assert r.returncode == 0, f"{backend}: exit {r.returncode}\n{r.stdout}{r.stderr}"
    assert "TAMAM" in r.stdout


def test_main_result_bridge_parity_between_backends():
    """C ve LLVM çıkış kodu + stderr iletisi aynı olmalı."""
    c = _build_and_run("c", ERR_MAIN)
    l = _build_and_run("llvm", ERR_MAIN)
    assert c.returncode == l.returncode == 1
    assert "patladi: 7" in c.stderr
    assert "patladi: 7" in l.stderr
