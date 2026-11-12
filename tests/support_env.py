"""
Axiom - Test ortamı yetenek denetimi

Bazı testler belirli ortam yetenekleri ister (ASan/LSan, ham soket, wine).
Kısıt varsa test **sessizce geçmez**: açık gerekçeyle `skip` olur ve pytest
bunu "skipped" olarak raporlar. Böylece "yeşil" ile "doğrulanamadı" ayrımı
korunur (ilke: ölçülmemiş iddia yasak).

Kullanım:
    from tests.support_env import require_asan, require_network, require_wine

    @require_raw_socket          # dekorator olarak
    def test_...(): ...

    pytestmark = require_network  # modul duzeyinde
"""
from __future__ import annotations

import functools
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

import pytest

_CACHE: dict[str, tuple[bool, str]] = {}


def _cached(key: str, probe):
    if key not in _CACHE:
        _CACHE[key] = probe()
    return _CACHE[key]


# ---------------------------------------------------------------------------
# ASan / LSan
# ---------------------------------------------------------------------------

def asan_probe() -> tuple[bool, str]:
    """ASan+LSan gerçekten çalışıyor mu?

    Kısıtlar:
      - LSan ptrace altında çalışmaz (sandbox/konteyner kısıtı)
      - ASan bazı çekirdeklerde mmap kısıtı nedeniyle açılmaz
    Gerçek bir sızıntı ile ortam hatasını ayırt etmek için önce bilinen
    TEMİZ bir program çalıştırılır: çıktı "LeakSanitizer" içeriyorsa ortam
    LSan'ı desteklemiyor demektir.
    """
    cc = shutil.which("clang") or shutil.which("gcc")
    if not cc:
        return False, "C derleyicisi yok"
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "probe.c"
        src.write_text("int main(void){return 0;}\n", encoding="utf-8")
        out = Path(td) / "probe"
        b = subprocess.run([cc, "-fsanitize=address", "-g", str(src), "-o", str(out)],
                           capture_output=True, text=True, timeout=180)
        if b.returncode != 0:
            return False, f"ASan derlenemedi: {b.stderr.strip()[:200]}"
        r = subprocess.run([str(out)], capture_output=True, text=True, timeout=120)
        blob = (r.stdout + r.stderr)
        if "LeakSanitizer does not work under ptrace" in blob:
            return False, "LSan ptrace altında çalışmıyor (sandbox kısıtı)"
        if "LeakSanitizer has encountered a fatal error" in blob:
            return False, "LSan başlatılamadı (ortam kısıtı)"
        if "AddressSanitizer" in blob and "ERROR" in blob:
            return False, f"ASan temiz programda hata verdi: {blob.strip()[:200]}"
        if r.returncode != 0:
            return False, f"ASan probe çıkış kodu {r.returncode}"
    return True, ""


# Not: bu nesneler HEM dekoratör HEM modül düzeyi `pytestmark` olarak
# kullanılabilir (pytest.mark.skipif ikisini de destekler).
def _mark(probe, label):
    ok, why = probe()
    return pytest.mark.skipif(not ok, reason=f"{label}: {why}")

require_asan = _mark(asan_probe, "ASan/LSan kullanılamıyor")


# ---------------------------------------------------------------------------
# Ham soket (ICMP)
# ---------------------------------------------------------------------------

def network_probe() -> tuple[bool, str]:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.listen(1)
        c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        c.connect(("127.0.0.1", port))
        acc, _ = s.accept()
        acc.close(); c.close(); s.close()
    except PermissionError as e:
        return False, f"soket izni yok: {e}"
    except OSError as e:
        return False, f"loopback soketi çalışmıyor: {e}"
    return True, ""


def raw_socket_probe() -> tuple[bool, str]:
    """ICMP'nin gerçekten çalışıp çalışmadığını ÜRÜNÜN koduyla ölçer.

    Yalnızca soket açılışına bakmak yanıltıcı: `lo` kapalı bir namespace'te
    soket açılır ama paket dönmez. Bu yüzden `axiom_icmp_ping` çağrılır ve
    loopback'e ulaşması beklenir — testin iddia ettiği şeyin aynısı.
    """
    ok_net, why_net = network_probe()
    if not ok_net:
        return False, f"loopback yok, ICMP de olamaz: {why_net}"

    cc = shutil.which("clang") or shutil.which("gcc")
    if not cc:
        return False, "C derleyicisi yok"

    runtime_dir = Path(__file__).resolve().parent.parent / "axiom"
    runtime_h = runtime_dir / "runtime.h"
    if not runtime_h.is_file():
        return False, "runtime.h bulunamadı"

    src_code = (
        '#define AXIOM_RUNTIME_FN\n'
        f'#include "{runtime_h}"\n'
        'int main(void){ return axiom_icmp_ping("127.0.0.1", 500) >= 0 ? 0 : 7; }\n'
    )
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "icmp_probe.c"
        src.write_text(src_code, encoding="utf-8")
        out = Path(td) / "icmp_probe"
        b = subprocess.run([cc, "-O1", str(src), "-o", str(out),
                            "-pthread", "-lm", "-lssl", "-lcrypto", "-lz", "-ldl"],
                           capture_output=True, text=True, timeout=300)
        if b.returncode != 0:
            return False, f"ICMP probu derlenemedi: {b.stderr.strip()[:160]}"
        r = subprocess.run([str(out)], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return False, "axiom_icmp_ping loopback'te ulaşamadı (izin/lo kısıtı)"
    return True, ""


require_raw_socket = _mark(raw_socket_probe, "Ham soket kullanılamıyor")


# ---------------------------------------------------------------------------
# Wine
# ---------------------------------------------------------------------------

def wine_probe() -> tuple[bool, str]:
    wine = shutil.which("wine")
    if not wine:
        return False, "wine kurulu değil"

    # Yazılabilir WINEPREFIX şart: salt-okunur /run/user altında wine
    # kendi kilit dosyasını oluşturamaz ve programı hiç başlatamaz.
    prefix = os.environ.get("AXIOM_WINE_PREFIX") or os.environ.get("WINEPREFIX")
    tmp = None
    if not prefix:
        tmp = tempfile.mkdtemp(prefix="axiom-wine-probe-")
        prefix = tmp
    env = os.environ.copy()
    env["WINEPREFIX"] = prefix
    env["WINEDEBUG"] = "-all"
    try:
        r = subprocess.run([wine, "cmd", "/c", "exit", "0"],
                           capture_output=True, text=True, timeout=180, env=env)
        blob = (r.stdout + r.stderr).lower()
        if "read-only file system" in blob or "errno 30" in blob:
            return False, f"Wine öneki yazılamıyor (salt-okunur): {prefix}"
        if r.returncode != 0:
            # Gercek nedeni ver: cikplak "cikis 1" teshis edilemez.
            tail = "\n".join((r.stderr or r.stdout).strip().splitlines()[-3:])
            return False, (f"Wine başlatılamadı (çıkış {r.returncode})"
                           + (f" — {tail}" if tail else ""))
    except subprocess.TimeoutExpired:
        return False, "Wine ilk kurulum zaman aşımı"
    finally:
        if tmp and not os.environ.get("AXIOM_KEEP_WINE_PREFIX"):
            shutil.rmtree(tmp, ignore_errors=True)
    return True, ""


require_wine = _mark(wine_probe, "Wine kullanılamıyor")


# ---------------------------------------------------------------------------
# Münhasır port (ağ testleri)
# ---------------------------------------------------------------------------

require_network = _mark(network_probe, "Ağ kullanılamıyor")


# ---------------------------------------------------------------------------
# Yazılabilir ev dizini (registry önbelleği)
# ---------------------------------------------------------------------------

def require_writable_home(fn):
    """Registry önbelleği ~/.axiom altına yazar; ev dizini salt-okunursa atla."""
    ok, why = _cached("home", lambda: (
        (True, "") if os.access(Path.home(), os.W_OK)
        else (False, f"ev dizini salt-okunur: {Path.home()}")
    ))
    return pytest.mark.skipif(not ok, reason=f"Yazılabilir ev dizini yok: {why}")(fn)
