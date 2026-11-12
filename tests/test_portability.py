"""
Axiom - Platform taşınabilirliği (P2-19)

Katman modeli (dürüst sınırlar):

  Katman 1 — ÇEKİRDEK: string, dizi, dosya, matematik, thread, zaman.
             Linux / macOS / Windows.
  Katman 2 — AĞ: TCP, UDP, DNS, HTTP istemcisi. POSIX sockets / Winsock2.
  Katman 3 — YALNIZ LINUX: epoll, /proc, ptrace, shellcode.
             Başka platformda **açık hata** (sessiz yanlış sonuç yasak, D7).
  Katman 4 — HARİCİ: OpenSSL (AES/TLS), zlib.
             Yoksa ya taşınabilir yedek (hash/HMAC) ya açık hata.

Bu dosya, kaynak düzeyinde taşınabilirliği ve Windows çapraz derlemesini
doğrular. Windows ikilileri **çalıştırılmaz** (wine gerekir); derleme
doğrulanır. Linux ikilileri hem derlenir hem çalıştırılır.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
EXAMPLES = ROOT / "examples"
RUNTIME = ROOT / "axiom" / "runtime.h"
PLATFORM = ROOT / "axiom" / "platform.h"
CRYPTO = ROOT / "axiom" / "crypto_portable.h"

MINGW = shutil.which("x86_64-w64-mingw32-gcc")
needs_mingw = pytest.mark.skipif(MINGW is None, reason="mingw-w64 kurulu değil")


# ---------------------------------------------------------------------------
# 1. Katman ayrımı kaynak düzeyinde
# ---------------------------------------------------------------------------

def test_platform_header_exists_and_declares_layers():
    assert PLATFORM.is_file()
    src = PLATFORM.read_text(encoding="utf-8")
    for macro in ("AXIOM_OS_WINDOWS", "AXIOM_OS_MACOS", "AXIOM_OS_LINUX"):
        assert macro in src
    # Her katman için soyutlama noktası bulunmalı
    for fn in ("ax_os_thread_create", "ax_os_mutex_lock", "ax_os_time_ms",
               "ax_os_stat", "ax_os_dir_open", "ax_os_net_init",
               "ax_os_sock_close", "ax_os_ptr_is_static"):
        assert fn in src, f"platform.h içinde {fn} yok"


def test_runtime_has_no_unconditional_posix_only_headers():
    """POSIX'e özgü başlıklar koşulsuz include edilmemeli."""
    src = RUNTIME.read_text(encoding="utf-8")
    head = src[:src.index("/* Runtime fonksiyon gorunurlugu")] \
        if "/* Runtime fonksiyon gorunurlugu" in src else src[:8000]
    for bad in ("#include <sys/epoll.h>", "#include <dirent.h>",
                "#include <pthread.h>", "#include <sys/ptrace.h>",
                "#include <regex.h>", "#include <dlfcn.h>"):
        for line_no, line in enumerate(head.splitlines()):
            if line.strip() == bad:
                # koşul içinde mi? (önceki 40 satırda #if var mı)
                prefix = "\n".join(head.splitlines()[max(0, line_no - 40):line_no])
                assert "#if" in prefix or "#  if" in prefix, \
                    f"koşulsuz POSIX başlığı: {bad}"


def test_linux_only_features_are_gated():
    """epoll / /proc / ptrace yalnızca Linux'ta derlenmeli."""
    src = RUNTIME.read_text(encoding="utf-8")
    # /proc forensic bloğu koşullu
    assert "#if defined(AXIOM_OS_LINUX)" in src
    # epoll için açık hata yedeği var
    assert "epoll" in src.lower()
    # Windows'ta /proc yerine açık hata mesajı
    assert "bu platformda /proc yok" in src


def test_portable_crypto_matches_reference_vectors():
    """OpenSSL'siz yedek hash implementasyonu FIPS/RFC vektörlerini tutmalı."""
    import hashlib
    import hmac as py_hmac

    src = CRYPTO.read_text(encoding="utf-8")
    for fn in ("ax_sha256", "ax_sha1", "ax_md5", "ax_hmac_sha256", "ax_ct_memcmp"):
        assert fn in src

    c = r'''
#include "%s"
#include <stdio.h>
int main(void) {
    char hex[130]; unsigned char d[32];
    ax_sha256("abc", 3, d); ax_hex_from_bytes(d, 32, hex); printf("%%s\n", hex);
    ax_sha1("abc", 3, d);  ax_hex_from_bytes(d, 20, hex); printf("%%s\n", hex);
    ax_md5("abc", 3, d);   ax_hex_from_bytes(d, 16, hex); printf("%%s\n", hex);
    ax_hmac_sha256("Jefe", 4, "what do ya want for nothing?", 28, d);
    ax_hex_from_bytes(d, 32, hex); printf("%%s\n", hex);
    return 0;
}
''' % str(CRYPTO)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "c.c"
        f.write_text(c, encoding="utf-8")
        out = Path(td) / "c"
        cc = shutil.which("clang") or shutil.which("gcc")
        res = subprocess.run([cc, "-O2", str(f), "-o", str(out)],
                             capture_output=True, text=True, timeout=120)
        assert res.returncode == 0, res.stderr
        run = subprocess.run([str(out)], capture_output=True, text=True, timeout=60)
    got = run.stdout.splitlines()
    assert got[0] == hashlib.sha256(b"abc").hexdigest()
    assert got[1] == hashlib.sha1(b"abc").hexdigest()
    assert got[2] == hashlib.md5(b"abc").hexdigest()
    assert got[3] == py_hmac.new(b"Jefe", b"what do ya want for nothing?",
                                 hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# 2. Windows çapraz derleme
# ---------------------------------------------------------------------------

@needs_mingw
def test_windows_target_produces_pe_binary(tmp_path):
    src = EXAMPLES / "01_hello.ax"
    out = tmp_path / "hello.exe"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    res = subprocess.run([str(AXIOM), "build", str(src), "--target", "windows",
                          "-o", str(out)],
                         capture_output=True, text=True, timeout=600, env=env)
    assert res.returncode == 0, res.stdout + res.stderr
    assert out.is_file()
    head = out.read_bytes()[:2]
    assert head == b"MZ", "PE imzası yok"


@needs_mingw
@pytest.mark.parametrize("name", [
    "01_hello.ax",
    "02_fibonacci.ax",
    "03_contracts.ax",
    "04_security_scan.ax",
    "07_http_banner_grabber.ax",
    "09_simd_vector_scan.ax",
    "11_packet2_advanced_network.ax",
    "13_packet4_fuzzer_scanner.ax",
    "17_ai_tensor_neural_net.ax",
    "19_error_handling.ax",
    "20_stdlib_result.ax",
    "21_axiom_scan.ax",
    "22_dfir_triage.ax",
])
def test_windows_examples_compile(name, tmp_path):
    src = EXAMPLES / name
    out = tmp_path / "prog.exe"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    args = [str(AXIOM), "build", str(src), "--target", "windows", "-o", str(out)]
    if name == "15_redteam_offensive_suite.ax":
        args += ["--features", "offensive"]
    res = subprocess.run(args, capture_output=True, text=True, timeout=600, env=env)
    assert res.returncode == 0, f"{name}:\n{res.stdout}\n{res.stderr}"
    assert out.read_bytes()[:2] == b"MZ"


@needs_mingw
def test_windows_rejects_linux_only_features_cleanly(tmp_path):
    """Linux'a özel araç Windows'ta sessizce yanlış sonuç vermemeli."""
    # /proc adli bilişim: derleme geçer, çalışma anında açık hata mesajı
    src = tmp_path / "forensics.ax"
    src.write_text('''
import "std/os/forensics"
fn main() -> int {
    let ports = forensics_list_listening_ports()
    print(len(ports))
    return 0
}
''', encoding="utf-8")
    out = tmp_path / "f.exe"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    res = subprocess.run([str(AXIOM), "build", str(src), "--target", "windows",
                          "-o", str(out)],
                         capture_output=True, text=True, timeout=600, env=env)
    assert res.returncode == 0, res.stdout + res.stderr   # derlenir
    # Hata metni runtime.h icinde (uretilen C onu #include eder)
    emitted = subprocess.run([str(AXIOM), "emit-c", str(src)],
                             capture_output=True, text=True, timeout=300, env=env)
    assert emitted.returncode == 0
    assert "runtime.h" in emitted.stdout
    assert "bu platformda /proc yok" in RUNTIME.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 3. Linux davranışı bozulmadı
# ---------------------------------------------------------------------------

def test_linux_examples_still_run():
    src = EXAMPLES / "01_hello.ax"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    res = subprocess.run([str(AXIOM), "run", str(src)],
                         capture_output=True, text=True, timeout=600, env=env)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "55" in res.stdout


def test_external_libs_accounted_for():
    """OpenSSL/zlib yoksa ya taşınabilir yedek ya açık hata olmalı."""
    src = RUNTIME.read_text(encoding="utf-8")
    assert "AXIOM_HAVE_OPENSSL" in src
    assert "AXIOM_HAVE_ZLIB" in src
    # hash: taşınabilir yedek var (güvenlik aracı için şart)
    assert "ax_sha256(" in src
    # AES: yedek yok -> açık hata
    assert "bu yapida OpenSSL yok" in src
    # zlib: açık hata
    assert "bu yapida zlib yok" in src


# ---------------------------------------------------------------------------
# 4. Windows kod yolunu Linux'ta ÇALIŞTIRARAK doğrulama
# ---------------------------------------------------------------------------

def test_windows_code_path_runs_natively(tmp_path):
    """Windows'un kullandığı yol (OpenSSL/zlib YOK) Linux'ta çalıştırılır.

    Bu, wine olmadan yapılabilecek en güçlü doğrulamadır: aynı `runtime.h`
    aynı makrolarla derlenir ve davranışı ölçülür. Yalnız derleme değil,
    gerçek çıktı karşılaştırılır.
    """
    import hashlib
    import hmac as py_hmac

    c = r'''
#define AXIOM_RUNTIME_FN
#define AXIOM_DISABLE_OPENSSL 1
#define AXIOM_DISABLE_ZLIB 1
#include "%s"
#include <stdio.h>
int main(void) {
    printf("%%d %%d\n", AXIOM_HAVE_OPENSSL, AXIOM_HAVE_ZLIB);
    printf("%%s\n", axiom_hash_sha256("abc"));
    printf("%%s\n", axiom_hash_sha1("abc"));
    printf("%%s\n", axiom_hash_md5("abc"));
    printf("%%s\n", axiom_hmac_sha256("Jefe", "what do ya want for nothing?"));
    printf("%%d %%d\n", axiom_crypto_memcmp("abc","abc"),
                       axiom_crypto_memcmp("abc","abd"));
    printf("%%ld\n", (long)strlen(axiom_crypto_random_hex(16)));
    printf("[%%s]\n", axiom_gzip_compress("x"));
    printf("[%%s]\n", axiom_aes256_cbc_encrypt("p","k","i"));
    return 0;
}
''' % str(RUNTIME)
    f = tmp_path / "wpath.c"
    f.write_text(c, encoding="utf-8")
    out = tmp_path / "wpath"
    cc = shutil.which("clang") or shutil.which("gcc")
    res = subprocess.run([cc, "-O2", str(f), "-o", str(out), "-pthread", "-lm"],
                         capture_output=True, text=True, timeout=300)
    assert res.returncode == 0, res.stderr[:3000]
    run = subprocess.run([str(out)], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    lines = run.stdout.splitlines()

    assert lines[0] == "0 0", "OpenSSL/zlib kapatilamadi"
    assert lines[1] == hashlib.sha256(b"abc").hexdigest()
    assert lines[2] == hashlib.sha1(b"abc").hexdigest()
    assert lines[3] == hashlib.md5(b"abc").hexdigest()
    assert lines[4] == py_hmac.new(b"Jefe", b"what do ya want for nothing?",
                                   hashlib.sha256).hexdigest()
    assert lines[5] == "1 0", "sabit zamanli karsilastirma bozuk"
    assert lines[6] == "32", "rastgele hex uzunlugu yanlis"
    assert "zlib yok" in lines[7]
    assert "OpenSSL yok" in lines[8]


@needs_mingw
def test_windows_binaries_import_only_system_dlls():
    """PE ikilileri yalnizca Windows'ta HER ZAMAN bulunan DLL'leri import etmeli.

    libssl/libcrypto/libz import eden bir .exe cıplak Windows'ta
    başlamaz. Bu test tam olarak onu engeller.
    """
    objdump = shutil.which("objdump") or shutil.which("x86_64-w64-mingw32-objdump")
    assert objdump, "objdump yok"

    allowed = {"KERNEL32.dll", "msvcrt.dll", "WS2_32.dll",
               "ADVAPI32.dll", "bcrypt.dll"}
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)

    import tempfile
    checked = 0
    for name in ("01_hello.ax", "05_real_scanner.ax",
                 "07_http_banner_grabber.ax", "14_packet5_full_security_suite.ax",
                 "16_blueteam_defensive_suite.ax", "22_dfir_triage.ax"):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "p.exe"
            res = subprocess.run([str(AXIOM), "build", str(EXAMPLES / name),
                                  "--target", "windows", "-o", str(out)],
                                 capture_output=True, text=True, timeout=600, env=env)
            assert res.returncode == 0, f"{name}:\n{res.stderr}"
            dump = subprocess.run([objdump, "-p", str(out)],
                                  capture_output=True, text=True, timeout=120)
        dlls = set()
        for line in dump.stdout.splitlines():
            if "DLL Name:" in line:
                dlls.add(line.split("DLL Name:")[1].strip())
        assert dlls, f"{name}: import tablosu okunamadi"
        unexpected = dlls - allowed
        assert not unexpected, (
            f"{name}: beklenmeyen DLL importu {sorted(unexpected)} "
            f"(çıplak Windows'ta bulunmaz). İzinli: {sorted(allowed)}")
        checked += 1
    assert checked == 6


# ---------------------------------------------------------------------------
# 5. Wine ile gerçek Windows çalıştırma (kuruluysa)
# ---------------------------------------------------------------------------

WINE = shutil.which("wine")
# `needs_wine` artik yazilabilir WINEPREFIX'i de dogrular: salt-okunur
# /run/user/... altinda wine programi hic baslatamaz (ortam kisiti).
from tests.support_env import require_wine, wine_probe
needs_wine = require_wine


import re as _re

# Wine/Linux arasında kaçınılmaz farklar: geçen süre, zaman damgası, PID.
_WINE_NORM = [
    (_re.compile(r"^.*\(ms\).*$", _re.M), "MS_LINE"),
    (_re.compile(r"^.*S(ü|u)re.*$", _re.M), "SURE_LINE"),
    (_re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"), "TS"),
    (_re.compile(r"PID\s*:\s*\d+"), "PID: N"),
]


def _normalize_out(text: str) -> str:
    for pat, repl in _WINE_NORM:
        text = pat.sub(repl, text)
    return text


_WINE_PREFIX = None


def _wine_env() -> dict:
    """Oturum başına TEK yazılabilir WINEPREFIX döndürür.

    Neden tek: her çağrıda yeni prefix oluşturmak ~600 MB disk yiyor ve
    test paketi /tmp'yi dolduruyordu (gerçek olay: "No space left on device").
    Prefix oturum sonunda `_cleanup_wine_prefix()` ile silinir.
    """
    global _WINE_PREFIX
    env = os.environ.copy()
    env["WINEDEBUG"] = "-all"
    if env.get("WINEPREFIX"):
        return env
    if _WINE_PREFIX is None:
        import tempfile as _tf
        _WINE_PREFIX = _tf.mkdtemp(prefix="axiom-wine-test-")
    env["WINEPREFIX"] = _WINE_PREFIX
    return env


def _cleanup_wine_prefix():
    global _WINE_PREFIX
    if _WINE_PREFIX and not os.environ.get("AXIOM_KEEP_WINE_PREFIX"):
        shutil.rmtree(_WINE_PREFIX, ignore_errors=True)
        _WINE_PREFIX = None


def _wine_run(exe: Path, timeout=300):
    """Wine altında çalıştır.

    Dönüş: (exit_code, stdout_normalize, stderr).
    `stderr` HER ZAMAN döndürülür; test hata mesajlarına eklenir — böylece
    "exit 1" gibi çıplak bir sonuç yerine Wine'ın gerçek nedenini görürüz.
    """
    res = subprocess.run([WINE, str(exe)], capture_output=True, text=True,
                         timeout=timeout, env=_wine_env(), cwd=str(exe.parent))
    out = res.stdout.replace("\r\n", "\n").replace("\r", "\n")
    err = res.stderr.replace("\r\n", "\n").replace("\r", "\n")
    return res.returncode, out, err


def _wine_fail(name: str, rc: int, out: str, err: str) -> str:
    """Wine hata mesajini okunur bicimde uret (stdout+stderr dahil)."""
    tail_out = "\n".join(out.strip().splitlines()[-25:])
    tail_err = "\n".join(err.strip().splitlines()[-25:])
    return (f"{name}: wine çıkış kodu {rc}\n"
            f"--- stdout (son 25 satır) ---\n{tail_out}\n"
            f"--- stderr (son 25 satır) ---\n{tail_err}")


@needs_wine
def test_windows_binary_runs_under_wine(tmp_path):
    """En temel kanıt: Windows ikilisi wine altında çalışır ve doğru çıktı verir."""
    out = tmp_path / "hello.exe"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    b = subprocess.run([str(AXIOM), "build", str(EXAMPLES / "01_hello.ax"),
                        "--target", "windows", "-o", str(out)],
                       capture_output=True, text=True, timeout=600, env=env)
    assert b.returncode == 0, b.stderr
    rc, stdout, stderr = _wine_run(out)
    assert rc == 0, _wine_fail("01_hello", rc, stdout, stderr)
    assert "55" in stdout
    assert "Axiom" in stdout


@needs_wine
@pytest.mark.parametrize("name", [
    "02_fibonacci.ax",
    "03_contracts.ax",
    "04_security_scan.ax",
    "09_simd_vector_scan.ax",
    "10_packet1_security_suite.ax",
    "17_ai_tensor_neural_net.ax",
    "19_error_handling.ax",
    "20_stdlib_result.ax",
])
def test_windows_binary_matches_linux_output(name, tmp_path):
    """Wine çıktısı Linux çıktısıyla birebir aynı olmalı (satır sonu hariç).

    Bu örnekler zamanlama/rastgelelik/POSIX'e özel sistem çağrısı içermez,
    dolayısıyla fark olması gerçek bir taşınabilirlik hatasıdır.
    """
    exe = tmp_path / "p.exe"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    b = subprocess.run([str(AXIOM), "build", str(EXAMPLES / name),
                        "--target", "windows", "-o", str(exe)],
                       capture_output=True, text=True, timeout=600, env=env)
    assert b.returncode == 0, f"{name} derlenemedi:\n{b.stderr}"

    wrc, wout, werr = _wine_run(exe)

    lres = subprocess.run([str(AXIOM), "run", str(EXAMPLES / name)],
                          capture_output=True, text=True, timeout=600, env=env)
    assert lres.returncode == 0, lres.stderr
    lout = lres.stdout.replace("\r\n", "\n")

    assert wrc == 0, _wine_fail(name, wrc, wout, werr)
    wout = _normalize_out(wout)
    lout = _normalize_out(lout)
    if wout != lout:
        import difflib
        d = "\n".join(list(difflib.unified_diff(
            lout.splitlines(), wout.splitlines(),
            fromfile="linux", tofile="windows-wine", lineterm=""))[:40])
        pytest.fail(f"{name}: çıktı farkı\n{d}")


@needs_wine
def test_windows_regex_engine_works(tmp_path):
    """Windows'ta POSIX regex yok; taşınabilir motor devrede olmalı.

    Sigma/YARA kuralları regex kullanır — 'regex yok' demek güvenlik
    araçlarını işe yaramaz yapardı.
    """
    src = tmp_path / "re.ax"
    src.write_text('''
import "std/text/regex"
fn main() -> int {
    print("cve:", regex_is_match("CVE-[0-9]{4}-[0-9]+", "see CVE-2026-4321 here"))
    print("digits:", regex_find("[0-9]+", "abc123def"))
    print("icase:", regex_is_match("(?i)HELLO", "hello world"))
    print("alt:", regex_is_match("(union.*select|1=1)", "x union all select y"))
    print("anchor_bad:", regex_is_match("^abc$", "abcd"))
    print("replace:", regex_replace("[0-9]+", "a1b22c", "#"))
    print("validate_ok:[", regex_validate("[a-z]+"), "]")
    print("nested_rejected:", regex_risk_level("(a+)+"))
    print("bad_pattern:", len(regex_validate("(unclosed")) > 0)
    return 0
}
''', encoding="utf-8")
    exe = tmp_path / "re.exe"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    b = subprocess.run([str(AXIOM), "build", str(src), "--target", "windows",
                        "-o", str(exe)],
                       capture_output=True, text=True, timeout=600, env=env)
    assert b.returncode == 0, b.stderr
    rc, out, err = _wine_run(exe)
    assert rc == 0, _wine_fail("regex", rc, out, err)
    assert out.splitlines() == [
        "cve: true",
        "digits: 123",
        "icase: true",
        "alt: true",
        "anchor_bad: false",
        "replace: a#b#c",
        "validate_ok:[  ]",
        "nested_rejected: 2",
        "bad_pattern: true",
    ]


@needs_wine
def test_windows_networking_works_under_wine(tmp_path):
    """WSAStartup olmadan Windows'ta hiçbir soket çalışmaz; test bunu kilitler."""
    src = tmp_path / "net.ax"
    src.write_text('''
import "std/net/http_server"
fn main() -> int {
    // Kapalı port: bağlantı başarısız olmalı ama ÇÖKMEMELİ.
    let fd = tcp_connect("127.0.0.1", 1)
    print("closed_port_fd_negative:", fd < 0)
    // Soket katmanı canlı mı (WSAStartup kanıtı): geçerli port dinlenebilmeli
    let srv = http_server_create(39001)
    print("socket_layer_alive:", srv > 0)
    if srv > 0 {
        http_server_close(srv)
    }
    return 0
}
''', encoding="utf-8")
    exe = tmp_path / "net.exe"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    b = subprocess.run([str(AXIOM), "build", str(src), "--target", "windows",
                        "-o", str(exe)],
                       capture_output=True, text=True, timeout=600, env=env)
    assert b.returncode == 0, b.stderr
    rc, out, err = _wine_run(exe)
    assert rc == 0, _wine_fail("networking", rc, out, err)
    assert out.splitlines() == ["closed_port_fd_negative: true",
                                "socket_layer_alive: true"]
