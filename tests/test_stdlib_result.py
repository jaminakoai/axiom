"""
Axiom - Result tabanli stdlib API testleri

Kapsam:
  - std/io/file       : read_file, write_file, append_file, read_lines
  - std/encoding/json : json_get_*_result
  - std/net/http      : http_get_result, http_status, http_body
  - std/crypto/tls    : https_get_result
  - std/os/process    : exec_output_result
  - result_err_with<T> ile struct tasiyan Result
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"


def _run(src: str, extra=None, timeout=240):
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            [str(AXIOM), "run", path] + (extra or []),
            capture_output=True, text=True, timeout=timeout, env=env,
        )
    finally:
        os.remove(path)


# --------------------------------------------------------------------------
# std/io/file
# --------------------------------------------------------------------------

def test_file_result_read_write_roundtrip(tmp_path):
    target = tmp_path / "data.txt"
    src = f"""
    import "std/core/error"
    import "std/io/file"

    fn main() -> int {{
        let w = write_file("{target}", "merhaba axiom")
        if not w.is_ok {{
            print("YAZMA_HATASI:", w.error)
            return 1
        }}
        let r = read_file("{target}")
        if not r.is_ok {{
            print("OKUMA_HATASI:", r.error)
            return 1
        }}
        print("ICERIK:", r.value)
        return 0
    }}
    """
    res = _run(src)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "ICERIK: merhaba axiom" in res.stdout
    assert target.read_text(encoding="utf-8") == "merhaba axiom"


def test_file_result_missing_file_returns_err_not_abort(tmp_path):
    missing = tmp_path / "yok.txt"
    src = f"""
    import "std/core/error"
    import "std/io/file"

    fn main() -> int {{
        let r = read_file("{missing}")
        print("IS_OK:", r.is_ok)
        print("ERR:", r.error)
        return 0
    }}
    """
    res = _run(src)
    # Kritik: Err donmeli, program cokmemeli (exit 0)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "IS_OK: false" in res.stdout
    assert "dosya bulunamadi" in res.stdout


def test_file_result_empty_path_is_err():
    src = """
    import "std/core/error"
    import "std/io/file"

    fn main() -> int {
        let r = read_file("")
        print("ERR:", r.error)
        return 0
    }
    """
    res = _run(src)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "bos dosya yolu" in res.stdout


def test_file_result_append_and_lines(tmp_path):
    target = tmp_path / "log.txt"
    src = f"""
    import "std/core/error"
    import "std/io/file"

    fn main() -> Result<int, str> {{
        write_file("{target}", "a\\nb")?
        append_file("{target}", "\\nc")?
        let lines = read_lines("{target}")?
        print("SATIR:", len(lines))
        print("ILK:", lines[0])
        return result_ok<int>(0)
    }}
    """
    res = _run(src)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "SATIR: 3" in res.stdout
    assert "ILK: a" in res.stdout


# --------------------------------------------------------------------------
# std/encoding/json
# --------------------------------------------------------------------------

def test_json_result_success_and_missing_key():
    src = """
    import "std/core/error"
    import "std/encoding/json"

    fn main() -> Result<int, str> {
        let doc = "{\\"name\\":\\"axiom\\",\\"port\\":8080,\\"debug\\":true}"

        let name = json_get_str_result(doc, "name")?
        let port = json_get_int_result(doc, "port")?
        let debug = json_get_bool_result(doc, "debug")?
        print("NAME:", name)
        print("PORT:", port)
        print("DEBUG:", debug)

        let missing = json_get_str_result(doc, "yok")
        print("MISS_OK:", missing.is_ok)
        print("MISS_ERR:", missing.error)

        let empty = json_get_int_result("", "x")
        print("EMPTY_ERR:", empty.error)
        return result_ok<int>(0)
    }
    """
    res = _run(src)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "NAME: axiom" in res.stdout
    assert "PORT: 8080" in res.stdout
    assert "DEBUG: true" in res.stdout
    assert "MISS_OK: false" in res.stdout
    assert "anahtar bulunamadi: yok" in res.stdout
    assert "bos json" in res.stdout


# --------------------------------------------------------------------------
# std/net/http
# --------------------------------------------------------------------------

def test_http_result_rejects_bad_port_without_abort():
    src = """
    import "std/core/error"
    import "std/net/http"

    fn main() -> int {
        let bad = http_get_result("127.0.0.1", 99999, "/")
        print("IS_OK:", bad.is_ok)
        print("ERR:", bad.error)

        let empty_host = http_get_result("", 80, "/")
        print("HOST_ERR:", empty_host.error)
        return 0
    }
    """
    res = _run(src)
    # Eski http_get sözleşme ihlaliyle çökerdi; Result sürümü Err dönmeli.
    assert res.returncode == 0, res.stdout + res.stderr
    assert "IS_OK: false" in res.stdout
    assert "gecersiz port: 99999" in res.stdout
    assert "bos host" in res.stdout


def test_http_status_and_body_parsing():
    src = """
    import "std/core/error"
    import "std/net/http"

    fn main() -> Result<int, str> {
        let resp = "HTTP/1.1 404 Not Found\\r\\nContent-Length: 3\\r\\n\\r\\nnope"
        let st = http_status(resp)?
        let body = http_body(resp)?
        print("STATUS:", st)
        print("BODY:", body)

        let bad = http_status("bozuk")
        print("BAD_ERR:", bad.error)
        return result_ok<int>(0)
    }
    """
    res = _run(src)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "STATUS: 404" in res.stdout
    assert "BODY: nope" in res.stdout
    assert "gecersiz HTTP yaniti" in res.stdout


# --------------------------------------------------------------------------
# std/crypto/tls + std/os/process
# --------------------------------------------------------------------------

def test_https_result_rejects_bad_port():
    src = """
    import "std/core/error"
    import "std/crypto/tls"

    fn main() -> int {
        let bad = https_get_result("example.com", 0, "/")
        print("ERR:", bad.error)
        return 0
    }
    """
    res = _run(src)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "gecersiz port: 0" in res.stdout


def test_exec_output_result_handles_empty_command():
    src = """
    import "std/core/error"
    import "std/os/process"

    fn main() -> int {
        let r = exec_output_result("")
        print("ERR:", r.error)

        let ok = exec_output_result("echo axiom-selftest")
        if ok.is_ok {
            print("OUT:", str_trim(ok.value))
        }
        return 0
    }
    """
    res = _run(src)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "bos komut" in res.stdout
    assert "OUT: axiom-selftest" in res.stdout


# --------------------------------------------------------------------------
# Genel Result davranışları
# --------------------------------------------------------------------------

def test_result_err_with_custom_struct_type():
    src = """
    import "std/core/error"

    struct Config { name: str, port: int }

    fn load(fail: bool) -> Result<Config, str> {
        if fail {
            return result_err_with<Config>("yapilandirma yok", Config { name: "", port: 0 })
        }
        return result_ok<Config>(Config { name: "ok", port: 1 })
    }

    fn main() -> Result<int, str> {
        let good = load(false)?
        print("GOOD:", good.name, good.port)
        let bad = load(true)
        print("BAD:", bad.error)
        return result_ok<int>(0)
    }
    """
    res = _run(src)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "GOOD: ok 1" in res.stdout
    assert "BAD: yapilandirma yok" in res.stdout


def test_result_stdlib_example_runs_clean_under_asan():
    res = _run(
        (ROOT / "examples" / "20_stdlib_result.ax").read_text(encoding="utf-8"),
        extra=["--asan"],
        timeout=300,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert "LeakSanitizer" not in (res.stdout + res.stderr)
    assert "[2] yuklendi: axiom-demo 8080" in res.stdout


# --------------------------------------------------------------------------
# main -> Result<int, str> giriş noktası
# --------------------------------------------------------------------------

def test_main_returning_result_maps_err_to_exit_1():
    src = """
    import "std/core/error"

    fn fail() -> Result<int, str> { return result_err_int("patladi") }

    fn main() -> Result<int, str> {
        let v = fail()?
        print("ULASILMAMALI")
        return result_ok<int>(v)
    }
    """
    res = _run(src)
    assert res.returncode == 1
    assert "ULASILMAMALI" not in res.stdout
    assert "patladi" in (res.stdout + res.stderr)


def test_main_returning_result_maps_ok_to_exit_0():
    src = """
    import "std/core/error"

    fn main() -> Result<int, str> {
        print("TAMAM")
        return result_ok<int>(99)
    }
    """
    res = _run(src)
    # Ok -> 0 (basari). Ozel cikis kodu icin `int` main kullanilir.
    assert res.returncode == 0, res.stdout + res.stderr
    assert "TAMAM" in res.stdout
