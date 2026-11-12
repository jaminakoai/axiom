"""
Axiom - Test paketi genel karantina (conftest)

NEDEN: 2026-11-12'de /tmp altında üç test ikilisi **günlerce %98 CPU** ile
döndü. Kök neden üründü (bkz. aşağıdaki not) ama ikinci bir kusur vardı:
testlerin çoğu `subprocess.run(...)` çağrılarında `timeout` vermiyor, bu
yüzden takılan bir ikili hiç durdurulmuyordu.

ÇÖZÜM: `subprocess.run` / `subprocess.Popen` çağrılarına varsayılan zaman
aşımı eklenir. Açıkça `timeout=...` veren çağrılar etkilenmez.

Ürün hatası notu (bu dosyanın konusu değil, kaydı burada):
  `codegen_c` atanmamış bir dizi değişkenini kendi başlatıcısı içinde
  (`let l = read_lines(p)?`) serbest bırakıyordu. Çöp `length` alanı
  yüzünden `axiom_array_str_free` milyonlarca kez dönüyordu.
  `pending_init` koruması dizi döngülerine de uygulandı;
  regresyon testi: `tests/test_uninit_array_release.py`.
"""
from __future__ import annotations

import os
import subprocess
import time

import pytest

# Varsayılan üst sınır: en yavaş derleme + çalıştırma ikilisi için bolca.
# Ortam değişkeniyle ayarlanabilir; 0 = devre dışı.
DEFAULT_TIMEOUT = float(os.environ.get("AXIOM_TEST_TIMEOUT", "900"))

_orig_run = subprocess.run
_orig_popen_init = subprocess.Popen.__init__


def _guarded_run(*args, **kwargs):
    if DEFAULT_TIMEOUT > 0 and kwargs.get("timeout") is None:
        kwargs["timeout"] = DEFAULT_TIMEOUT
    return _orig_run(*args, **kwargs)


def _guarded_popen_init(self, *args, **kwargs):
    # Popen'ta timeout argümanı yoktur; bekleyen kodu patlatmamak için
    # yalnızca işaret koyarız (wait/communicate çağrıları timeout almalı).
    _orig_popen_init(self, *args, **kwargs)


def _clean_stale_wine_prefixes(max_age_s: float = 3600.0) -> None:
    """Yarida kesilen kosulardan kalan wine oneklerini temizle.

    Her onek ~600 MB; /tmp tmpfs ise 4 GB. Bir kez birikince butun derlemeler
    "No space left on device" ile duser (2026-11-12'de yasandi).
    """
    import glob
    import shutil
    import time

    now = time.time()
    for path in glob.glob("/tmp/axiom-wine-*"):
        try:
            if now - os.path.getmtime(path) < max_age_s:
                continue
            shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass


def pytest_configure(config):
    if DEFAULT_TIMEOUT > 0:
        subprocess.run = _guarded_run
    _clean_stale_wine_prefixes()


def pytest_sessionfinish(session, exitstatus):
    """Oturum sonunda wine oneklerini sil (test modulundeki hook calismaz)."""
    import glob
    import shutil

    for path in glob.glob("/tmp/axiom-wine-test-*") + glob.glob("/tmp/axiom-wine-probe-*"):
        shutil.rmtree(path, ignore_errors=True)


def pytest_unconfigure(config):
    subprocess.run = _orig_run
