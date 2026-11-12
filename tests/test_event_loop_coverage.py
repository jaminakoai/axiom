"""
Axiom - P2-14: `std/net/event_loop` kalan fonksiyonlar

`tests/test_async_epoll.py` (6 test) zaten lifecycle, pipe, socketpair,
mod/del, multi-socket reactor ve nonblocking TCP sunucusunu kapsıyordu.
Bu dosya **kapsanmayan 7 fonksiyonu** ve bit düzeyi kenar durumları ekler:

  - event_is_writable / event_is_error / event_is_hangup
  - event_loop_mod (EPOLLIN -> EPOLLIN|EPOLLOUT)
  - event_loop_event_fd / event_loop_event_events (get_event'in parçaları)
  - net_set_nonblocking
  - EPOLLHUP (diğer uç kapanınca)
  - EventKind sabitleri

Tümü C + LLVM paritesiyle.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"


def _run(src: str, tmp_path: Path, backend: str = "c"):
    f = tmp_path / "t.ax"
    f.write_text(src, encoding="utf-8")
    out = tmp_path / "t"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    args = [str(AXIOM), "build", str(f), "-o", str(out)]
    if backend == "llvm":
        args.insert(2, "--backend=llvm")
    res = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
    assert res.returncode == 0, res.stdout + res.stderr
    return subprocess.run([str(out)], capture_output=True, text=True, timeout=120)


BITS = '''
import "std/net/event_loop"

fn main() -> int {
    let k = event_kind_new()
    print("kind:", k.epoll_in, k.epoll_out, k.epoll_err, k.epoll_hup)

    print("r_in:", event_is_readable(k.epoll_in))
    print("r_out:", event_is_readable(k.epoll_out))
    print("w_out:", event_is_writable(k.epoll_out))
    print("w_in:", event_is_writable(k.epoll_in))
    print("e_err:", event_is_error(k.epoll_err))
    print("e_in:", event_is_error(k.epoll_in))
    print("h_hup:", event_is_hangup(k.epoll_hup))
    print("h_in:", event_is_hangup(k.epoll_in))

    // Birlesik maskeler
    let rin_err = k.epoll_in + k.epoll_err
    print("combo:", event_is_readable(rin_err), event_is_error(rin_err), event_is_hangup(rin_err))

    // Sifir/negatif maske hicbir sey dondurmemeli
    print("zero:", event_is_readable(0), event_is_writable(0), event_is_error(0), event_is_hangup(0))
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_event_bit_helpers(backend, tmp_path):
    out = _run(BITS, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "kind: 1 4 8 16",
        "r_in: true",
        "r_out: false",
        "w_out: true",
        "w_in: false",
        "e_err: true",
        "e_in: false",
        "h_hup: true",
        "h_in: false",
        "combo: true true false",
        "zero: false false false false",
    ]


MOD_SRC = '''
import "std/net/event_loop"

fn main() -> int {
    let k = event_kind_new()
    let loop = event_loop_new()
    // socketpair: her iki ucu da okunabilir/yazilabilir -> EPOLLOUT de tetiklenir
    let h = socketpair_create()
    let fd1 = socketpair_fd1(h)
    let fd2 = socketpair_fd2(h)

    print("add_in:", event_loop_add(loop, fd1, k.epoll_in) == 0)

    let mask = k.epoll_in + k.epoll_out
    print("mod:", event_loop_mod(loop, fd1, mask) == 0)

    fd_write(fd2, "x")
    let cnt = event_loop_poll(loop, 500)
    print("polled:", cnt >= 1)

    let ev = event_loop_event_events(loop, 0)
    print("mask_has_in:", event_is_readable(ev))
    print("mask_has_out:", event_is_writable(ev))
    print("fd_matches:", event_loop_event_fd(loop, 0) == fd1)

    // get_event ile parca fonksiyonlari ayni sonucu vermeli
    let e = event_loop_get_event(loop, 0)
    print("get_eq:", e.fd == fd1, e.events == ev)

    event_loop_del(loop, fd1)
    socketpair_close(h)
    event_loop_close(loop)
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_mod_and_event_accessors(backend, tmp_path):
    out = _run(MOD_SRC, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "add_in: true",
        "mod: true",
        "polled: true",
        "mask_has_in: true",
        "mask_has_out: true",
        "fd_matches: true",
        "get_eq: true true",
    ]


HUP_SRC = '''
import "std/net/event_loop"

fn main() -> int {
    let k = event_kind_new()
    let loop = event_loop_new()
    let h = socketpair_create()
    let fd1 = socketpair_fd1(h)
    let fd2 = socketpair_fd2(h)

    event_loop_add(loop, fd1, k.epoll_in)

    // YALNIZCA karsi ucu kapat -> fd1'de EPOLLHUP / EOF uretir.
    // socketpair_close(handle) iki ucu birden kapatir; o zaman epoll
    // fd'yi otomatik duser ve olay uretmez.
    socket_close(fd2)

    let cnt = event_loop_poll(loop, 500)
    print("polled:", cnt >= 1)
    if cnt >= 1 {
        let ev = event_loop_event_events(loop, 0)
        // hangup veya error beklenir; en azindan olay uretilmis olmali
        print("signalled:", event_is_hangup(ev) or event_is_error(ev) or event_is_readable(ev))
        print("read_eof:", len(fd_read(fd1, 64)))
    }
    event_loop_close(loop)
    socketpair_close(h)
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_peer_close_signals_event(backend, tmp_path):
    out = _run(HUP_SRC, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    lines = out.stdout.splitlines()
    assert lines[0] == "polled: true"
    assert lines[1] == "signalled: true"


NB_SRC = '''
import "std/net/event_loop"

fn main() -> int {
    let h = pipe_create()
    let rfd = pipe_read_fd(h)
    let wfd = pipe_write_fd(h)

    print("set_r:", net_set_nonblocking(rfd) == 0)
    print("set_w:", net_set_nonblocking(wfd) == 0)

    // Bos pipe'tan nonblocking okuma bos donmeli, kilitlenmemeli
    print("empty_read:", len(fd_read(rfd, 16)))

    fd_write(wfd, "abc")
    print("data_read:", fd_read(rfd, 16))

    // Gecersiz fd hata dondurmeli
    print("bad_fd:", net_set_nonblocking(-1) != 0)

    pipe_close(h)
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_net_set_nonblocking(backend, tmp_path):
    out = _run(NB_SRC, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "set_r: true",
        "set_w: true",
        "empty_read: 0",
        "data_read: abc",
        "bad_fd: true",
    ]


CAPACITY_SRC = '''
import "std/net/event_loop"

fn main() -> int {
    let small = event_loop_new_with_capacity(8)
    print("small_ok:", small.epfd > 0, small.max_events)

    let k = event_kind_new()
    let h = pipe_create()
    let rfd = pipe_read_fd(h)
    let wfd = pipe_write_fd(h)
    event_loop_add(small, rfd, k.epoll_in)
    fd_write(wfd, "z")

    let cnt = event_loop_poll(small, 500)
    print("capacity_respected:", cnt >= 1 and cnt <= 8)

    pipe_close(h)
    event_loop_close(small)
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_capacity_is_used(backend, tmp_path):
    out = _run(CAPACITY_SRC, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == ["small_ok: true 8", "capacity_respected: true"]


def test_every_public_function_is_covered():
    """Modüldeki her `fn` en az bir kez test kodunda geçmeli."""
    import re

    mod = (ROOT / "std" / "net" / "event_loop.ax").read_text(encoding="utf-8")
    fns = re.findall(r"^fn (\w+)\(", mod, re.M)
    assert len(fns) >= 28

    corpus = ""
    for name in ("test_async_epoll.py", "test_event_loop_coverage.py"):
        corpus += (ROOT / "tests" / name).read_text(encoding="utf-8")

    missing = [fn for fn in fns if not re.search(rf"\b{re.escape(fn)}\s*\(", corpus)]
    assert not missing, f"Kapsanmayan fonksiyonlar: {missing}"
