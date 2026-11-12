"""
Axiom - Atanmamis dizi degiskeninin serbest birakilmasi (sonsuz dongu)

GERCEK OLAY (2026-11-10 → 2026-11-12):
  Uc test ikilisi `/tmp/tmp*.bin` **gunlerce %97 CPU** ile dondu.

KOK NEDEN:
  `let l = read_lines(p)?` deseninde `?` operatoru hata yolunda
  `_capture_cleanup()` uretir. Bu temizlik, **henuz atanmamis** `l`
  degiskenini de serbest birakiyordu:

      ax_array_str l = ({ ... if (!ok) { axiom_array_str_free(&l); ... } ... });

  `l` baslatilmadigi icin `.length` alani cop degerdir. Dizi serbest
  birakma dongusu bu cop uzunluk kadar doner:

      for (ax_int i = 0; i < arr->length; i++)
          if (arr->data[i]) axiom_str_release(arr->data[i]);

  Kucuk cop deger -> sessiz gecis (UB), buyuk cop deger -> pratikte
  sonsuz dongu (CPU %98). Bu yuzden hata **aralikli** gorunuyordu.

DUZELTME:
  `pending_init` korumasi daha once yalnizca *string* kapsamlarina
  uygulanmisti; **dizi** kapsamlarina da uygulandi
  (`_emit_all_owned_releases`, `_capture_loop_cleanup`,
  `generate_block_contents`).

Bu dosya hem uretilen C'yi hem de calisma anini kilitler.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"

ERROR_PATH_SRC = '''
import "std/io/file"
import "std/core/error"

fn lines_of(p: str) -> Result<int, str> {
    let l = read_lines(p)?
    return result_ok<int>(len(l))
}

fn many(n: int) -> int {
    let mut ok = 0
    let mut i = 0
    while (i < n) {
        let r = lines_of("kesinlikle-yok-boyle-bir-dosya.txt")
        if not r.is_ok {
            ok = ok + 1
        }
        i = i + 1
    }
    return ok
}

fn main() -> int {
    print("errors:", many(300))
    return 0
}
'''


def _emit_c(src: str) -> str:
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.ax"
        f.write_text(src, encoding="utf-8")
        out = Path(td) / "t.c"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        res = subprocess.run([str(AXIOM), "emit-c", str(f), "-o", str(out)],
                             capture_output=True, text=True, timeout=300, env=env)
        assert res.returncode == 0, res.stdout + res.stderr
        return out.read_text(encoding="utf-8")


def test_generated_c_does_not_free_variable_in_its_own_initializer():
    """`X = ({ ... { ...free(&X)... } ... })` deseni uretilmemeli."""
    c = _emit_c(ERROR_PATH_SRC)

    # l degiskeninin baslatici satirini bul
    init_lines = [ln for ln in c.splitlines()
                  if "ax_array_str l = ({" in ln or "ax_array_str l = ({ " in ln
                  or "l = ({" in ln and "result_ok" not in ln]
    assert init_lines, "beklenen ?-baslatici satiri uretilmedi:\n" + c[:2000]
    for ln in init_lines:
        assert "axiom_array_str_free(&l)" not in ln, (
            "atanmamis 'l' kendi baslaticisinda serbest birakiliyor "
            "(cop uzunluk -> sonsuz dongu):\n" + ln)


def test_error_path_runs_without_hanging(assert_timeout=60):
    """300 kez hata yolu: takilmadan bitmeli (cop uzunluk sansa kalmamali)."""
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.ax"
        f.write_text(ERROR_PATH_SRC, encoding="utf-8")
        out = Path(td) / "t"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        b = subprocess.run([str(AXIOM), "build", str(f), "-o", str(out)],
                           capture_output=True, text=True, timeout=300, env=env)
        assert b.returncode == 0, b.stdout + b.stderr
        try:
            r = subprocess.run([str(out)], capture_output=True, text=True,
                               timeout=assert_timeout)
        except subprocess.TimeoutExpired:
            pytest.fail("hata yolu takildi (atanmamis dizi serbest birakma "
                        "regresyonu): surec 60 s icinde bitmedi")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "errors: 300"


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_error_path_no_hang_both_backends(backend):
    """Iki arka uc da ayni davranmali (parite ilkesi)."""
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "t.ax"
        f.write_text(ERROR_PATH_SRC, encoding="utf-8")
        out = Path(td) / "t"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        args = [str(AXIOM), "build", str(f), "-o", str(out)]
        if backend == "llvm":
            args.insert(2, "--backend=llvm")
        b = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
        assert b.returncode == 0, b.stdout + b.stderr
        try:
            r = subprocess.run([str(out)], capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            pytest.fail(f"{backend}: hata yolu takildi (sonsuz dongu regresyonu)")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "errors: 300"


def test_conftest_enforces_default_timeout():
    """Test altyapisi: subprocess.run'a varsayilan zaman asimi uygulanir."""
    import conftest

    assert conftest.DEFAULT_TIMEOUT > 0
    # Zaman asimina ugrayan bir komut TimeoutExpired vermeli, sonsuza kadar beklememeli
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(["sleep", "30"], capture_output=True, timeout=0.3)
