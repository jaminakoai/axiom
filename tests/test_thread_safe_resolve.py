"""
Axiom - Eşzamanlı `tcp_connect`: thread-safe çözümleme (regresyon)

GERÇEK HATA (12 Kasım 2026, CI'da aralıklı):
  `examples/08_multithreaded_scanner.ax` CI'da ara sıra SIGSEGV ile düştü
  (`exit -11`; `axiom run` üzerinden `245`). Aynı örnek yerelde kararlıydı —
  klasik yarış hatası belirtisi.

KÖK NEDEN:
  `axiom_tcp_connect` (ve `udp_sendto`, `icmp_ping`, `tcp_ping`) IPv4
  çözümlemesi için **`gethostbyname`** kullanıyordu. POSIX'te bu fonksiyon
  MT-Unsafe'tir: sonucu **statik bir tamponda** döndürür. Dört iş parçacığı
  aynı anda çağırınca `struct hostent` başka bir thread tarafından eziliyor,
  `h_length` bozuluyor ve `memcpy(&serv_addr.sin_addr.s_addr, server->h_addr,
  server->h_length)` taşarak segfault veriyordu.

DÜZELTME:
  `axiom_internal_resolve_ipv4()` eklendi: sayısal adreslerde `inet_pton`
  (DNS'e hiç gitmez), aksi hâlde thread-safe `getaddrinfo`. Dört çağrı yeri
  buna geçirildi.

KANIT (düzeltme öncesi/sonrası, 8 thread × 40 bağlantı, 25 koşu):
  eski runtime : 18/25 koşu segfault
  yeni runtime : 0/25 hata
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"

STRESS_SRC = '''
fn probe(port: int) -> int
    requires port >= 1 and port <= 65535
{
    let mut i = 0
    while i < 40 {
        let fd = tcp_connect("127.0.0.1", port)
        if fd >= 0 {
            socket_close(fd)
        }
        i = i + 1
    }
    return 0
}

fn main() -> int {
    let t1 = thread_create(probe, 80)
    let t2 = thread_create(probe, 443)
    let t3 = thread_create(probe, 22)
    let t4 = thread_create(probe, 8080)
    let t5 = thread_create(probe, 3306)
    let t6 = thread_create(probe, 5432)
    let t7 = thread_create(probe, 6379)
    let t8 = thread_create(probe, 9200)
    thread_join(t1)
    thread_join(t2)
    thread_join(t3)
    thread_join(t4)
    thread_join(t5)
    thread_join(t6)
    thread_join(t7)
    thread_join(t8)
    print("bitti")
    return 0
}
'''


def _build(src: str, backend: str = "c") -> Path:
    td = Path(tempfile.mkdtemp())
    f = td / "stress.ax"
    f.write_text(src, encoding="utf-8")
    out = td / "stress"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    args = [str(AXIOM), "build", str(f), "-o", str(out)]
    if backend == "llvm":
        args.insert(2, "--backend=llvm")
    res = subprocess.run(args, capture_output=True, text=True, timeout=600, env=env)
    assert res.returncode == 0, res.stdout + res.stderr
    return out


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_concurrent_tcp_connect_does_not_crash(backend):
    """8 thread × 40 eşzamanlı `tcp_connect`: segfault olmamalı."""
    exe = _build(STRESS_SRC, backend)
    runs = 10
    failures = []
    for i in range(runs):
        r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            failures.append((i, r.returncode, r.stderr[-400:]))

    assert not failures, (
        f"{backend}: {len(failures)}/{runs} koşu başarısız — eşzamanlı "
        f"tcp_connect hâlâ yarış içeriyor (gethostbyname MT-Unsafe):\n"
        + "\n".join(f"  run {i}: exit {rc}\n{err}" for i, rc, err in failures))


def test_runtime_does_not_use_thread_unsafe_gethostbyname():
    """Runtime'da çıplak `gethostbyname(` çağrısı kalmamalı.

    Yeni kod `getaddrinfo` (thread-safe) kullanan
    `axiom_internal_resolve_ipv4()` üzerinden gitmeli.
    """
    header = (ROOT / "axiom" / "runtime.h").read_text(encoding="utf-8")
    code_lines = [
        ln for ln in header.splitlines()
        if "gethostbyname(" in ln and not ln.lstrip().startswith(("*", "/*", "//"))
    ]
    assert not code_lines, (
        "runtime.h içinde thread-safe olmayan gethostbyname kullanımı var:\n"
        + "\n".join(code_lines))
    assert "axiom_internal_resolve_ipv4" in header
