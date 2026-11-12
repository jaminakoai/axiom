"""
Axiom - Red Team modül sertleştirme (P1-05)

==============================================================================
YASAL VE ETİK UYARI / LEGAL & ETHICAL DISCLAIMER:
YALNIZCA YASAL İZİNLİ VE ETİK TEST ORTAMLARINDA KULLANIM İÇİNDİR.
YETKİSİZ SİSTEMLERDE KULLANIMI YASALARA AYKIRIDIR.
==============================================================================

Varsayılan `pytest` çalıştırmasında bu dosya **atlanır**. Ofansif kod
çalıştırıldığı için açık onay gerekir:

    python3 -m pytest -q tests/test_redteam_hardening.py   # varsayilan
    AXIOM_SKIP_REDTEAM=1 python3 -m pytest -q ...          # atlamak icin

Kapsam:
  - shellcode_allocate_rwx / shellcode_protect (mmap + mprotect)
  - c2_crypto_random_hex (CSPRNG, uzunluk, tekrarsızlık)
  - c2_hmac_sha256 (determinizm, anahtar/veri duyarlılığı, sabit zamanlı karşılaştırma)
  - `requires` ihlalinin derleme anında yakalanması (prover)
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

# Ofansif testler artik VARSAYILAN olarak calisir: yalnizca bu surecte
# (fork/exec ile) sentetik shellcode calistirilir, disariya trafik gitmez.
# Izole olmayan ortamlarda AXIOM_SKIP_REDTEAM=1 ile atlanabilir.
if os.environ.get("AXIOM_SKIP_REDTEAM") == "1":
    pytest.skip(
        "AXIOM_SKIP_REDTEAM=1: ofansif testler atlandi.",
        allow_module_level=True,
    )

from axiom.cli import compile_axiom_source, find_c_compiler
from axiom.prover import ProofError

ROOT = Path(__file__).resolve().parent.parent


def _run(code: str, features=("offensive",)) -> subprocess.CompletedProcess:
    c_code = compile_axiom_source(code, features=list(features))
    cc = find_c_compiler()
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_f, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as b_f:
        c_path, bin_path = c_f.name, b_f.name
        c_f.write(c_code)
    try:
        build = subprocess.run(
            [cc, "-O2", "-Wall", c_path, "-o", bin_path,
             "-lssl", "-lcrypto", "-lz", "-ldl", "-pthread"],
            capture_output=True, text=True,
        )
        assert build.returncode == 0, build.stderr
        return subprocess.run([bin_path], capture_output=True, text=True, timeout=30)
    finally:
        for p in (c_path, bin_path):
            if os.path.exists(p):
                os.remove(p)


def _lines(code: str) -> list:
    res = _run(code)
    assert res.returncode == 0, res.stderr
    return res.stdout.splitlines()


# ---------------------------------------------------------------------------
# shellcode: mmap / mprotect
# ---------------------------------------------------------------------------

def test_shellcode_allocate_rwx_returns_mapped_pointer():
    out = _lines('''
import "std/security/shellcode"
fn main() -> int {
    let p = shellcode_allocate_rwx(4096)
    print("nonzero:", p > 0)
    // İki tahsis farklı adres dönmeli
    let q = shellcode_allocate_rwx(4096)
    print("distinct:", p != q)
    return 0
}
''')
    assert out == ["nonzero: true", "distinct: true"]


def test_shellcode_protect_rw_and_rwx():
    out = _lines('''
import "std/security/shellcode"
fn main() -> int {
    let p = shellcode_allocate_rwx(4096)
    print("rw:", shellcode_protect(p, 4096, 3))    # PROT_READ|PROT_WRITE
    print("rwx:", shellcode_protect(p, 4096, 7))   # PROT_READ|PROT_WRITE|PROT_EXEC
    print("ro:", shellcode_protect(p, 4096, 1))    # PROT_READ
    return 0
}
''')
    assert out == ["rw: true", "rwx: true", "ro: true"]


def test_shellcode_protect_rejects_null_pointer_at_compile_time():
    """`requires ptr > 0` ihlali (NULL) daha derlemede yakalanmalı."""
    code = '''
import "std/security/shellcode"
fn main() -> int {
    let ok = shellcode_protect(0, 16, 7)
    return 0
}
'''
    with pytest.raises(ProofError) as exc:
        compile_axiom_source(code, features=["offensive"])
    assert "ptr > 0" in str(exc.value)


def test_shellcode_protect_rejects_zero_size_at_compile_time():
    """`requires size > 0` ihlali prover tarafından derleme anında yakalanmalı."""
    code = '''
import "std/security/shellcode"
fn main() -> int {
    let p = shellcode_allocate_rwx(16)
    let ok = shellcode_protect(p, 0, 7)
    return 0
}
'''
    with pytest.raises(ProofError) as exc:
        compile_axiom_source(code, features=["offensive"])
    msg = str(exc.value)
    assert "requires" in msg and "ihlal" in msg.lower()


# ---------------------------------------------------------------------------
# C2: CSPRNG + HMAC
# ---------------------------------------------------------------------------

def test_c2_crypto_random_hex_length_and_uniqueness():
    out = _lines('''
import "std/net/c2"
fn main() -> int {
    let a = c2_crypto_random_hex(8)
    let b = c2_crypto_random_hex(16)
    print("len8:", str_len(a))
    print("len16:", str_len(b))
    print("zero:", str_len(c2_crypto_random_hex(0)))

    // 32 kez üret: hepsi farklı olmalı (CSPRNG çakışması pratikte imkânsız)
    let mut distinct = 0
    let mut seen = ""
    let mut i = 0
    while (i < 32) {
        let r = c2_crypto_random_hex(16)
        if not str_contains(seen, r) {
            distinct = distinct + 1
            seen = seen + r + ","
        }
        i = i + 1
    }
    print("distinct32:", distinct)
    return 0
}
''')
    assert out == ["len8: 16", "len16: 32", "zero: 0", "distinct32: 32"]


def test_c2_crypto_random_hex_is_hex():
    out = _lines('''
import "std/net/c2"
fn main() -> int {
    let r = c2_crypto_random_hex(32)
    print("only_hex:", rt_regex_is_match("^[0-9a-f]+$", r))
    return 0
}
''')
    assert out == ["only_hex: true"]


def test_c2_hmac_sha256_deterministic_and_sensitive():
    out = _lines('''
import "std/net/c2"
fn main() -> int {
    let a = c2_hmac_sha256("0123456789abcdef", "message")
    let b = c2_hmac_sha256("0123456789abcdef", "message")
    let c = c2_hmac_sha256("0123456789abcdef", "messagf")
    let d = c2_hmac_sha256("fedcba9876543210", "message")
    print("len:", str_len(a))
    print("deterministic:", a == b)
    print("data_sensitive:", a != c)
    print("key_sensitive:", a != d)
    return 0
}
''')
    assert out == [
        "len: 64",
        "deterministic: true",
        "data_sensitive: true",
        "key_sensitive: true",
    ]


def test_c2_hmac_matches_known_vector():
    """RFC 4231 test case 2: key='Jefe', data='what do ya want for nothing?'."""
    out = _lines('''
import "std/net/c2"
fn main() -> int {
    let mac = c2_hmac_sha256("Jefe", "what do ya want for nothing?")
    print(mac)
    return 0
}
''')
    assert out == ["5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843"]


def test_c2_crypto_memcmp_constant_time_semantics():
    out = _lines('''
import "std/net/c2"
fn main() -> int {
    let a = c2_hmac_sha256("k", "a")
    let b = c2_hmac_sha256("k", "a")
    let c = c2_hmac_sha256("k", "b")
    print("eq:", c2_crypto_memcmp(a, b))
    print("ne:", c2_crypto_memcmp(a, c))
    print("diff_len:", c2_crypto_memcmp("abc", "abcd"))
    print("empty:", c2_crypto_memcmp("", ""))
    return 0
}
''')
    assert out == ["eq: true", "ne: false", "diff_len: false", "empty: true"]


# ---------------------------------------------------------------------------
# Beacon (HMAC'ın gerçek kullanımı)
# ---------------------------------------------------------------------------

def test_c2_beacon_roundtrip_and_tamper_detection():
    out = _lines('''
import "std/net/c2"
fn main() -> int {
    let beacon = c2_generate_beacon("agent-1", "0123456789abcdef", "status=ok")
    let decoded = c2_parse_beacon(beacon, "0123456789abcdef")
    print("roundtrip:", decoded)
    // Yanlış anahtar ile çözülemez
    print("wrong_key_len:", str_len(c2_parse_beacon(beacon, "wrong-key-000000")))
    // Bozulmuş beacon reddedilir
    print("garbage_len:", str_len(c2_parse_beacon("bozuk|veri", "0123456789abcdef")))
    return 0
}
''')
    assert out[0] == "roundtrip: status=ok"
    assert out[1] == "wrong_key_len: 0"
    assert out[2] == "garbage_len: 0"
