"""
Axiom Programming Language (λx) - FAZ 4.2: Linux Epoll Tabanli Asenkron Ag Motoru Testleri
"""
import pytest
import subprocess
import tempfile
import os
import socket

from axiom.cli import compile_axiom_source, find_c_compiler

from tests.support_env import require_network

# epoll + pipe + socketpair: gercek soket altyapisi gerekir.
pytestmark = require_network

def run_axiom_code(code_str: str) -> tuple[int, str, str]:
    c_code = compile_axiom_source(code_str)
    cc = find_c_compiler()
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        cmd = [cc, "-O3", "-Wall", c_path, "-o", bin_path, "-lssl", "-lcrypto", "-lz", "-ldl", "-lm", "-pthread"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"C derleme hatasi:\n{res.stderr}"

        run_res = subprocess.run([bin_path], capture_output=True, text=True, timeout=10)
        return run_res.returncode, run_res.stdout, run_res.stderr
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

def test_epoll_lifecycle():
    code = """
    import "std/net/event_loop.ax"

    fn main() -> int {
        let loop: EpollEventLoop = event_loop_new();
        if (loop.epfd < 0) {
            print("EPOLL_INIT_FAIL");
            return 1;
        }

        let ready: int = event_loop_poll(loop, 20);
        if (ready == 0) {
            print("EPOLL_TIMEOUT_OK");
        }

        event_loop_close(loop);
        print("EPOLL_LIFECYCLE_SUCCESS");
        return 0;
    }
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Error: {err}"
    assert "EPOLL_TIMEOUT_OK" in out
    assert "EPOLL_LIFECYCLE_SUCCESS" in out

def test_epoll_pipe_data_transfer():
    code = """
    import "std/net/event_loop.ax"

    fn main() -> int {
        let loop: EpollEventLoop = event_loop_new();
        let kind: EventKind = event_kind_new();

        let p_handle: int = pipe_create();
        if (p_handle < 0) {
            print("PIPE_CREATE_FAIL");
            return 1;
        }

        let r_fd: int = pipe_read_fd(p_handle);
        let w_fd: int = pipe_write_fd(p_handle);

        let add_res: int = event_loop_add(loop, r_fd, kind.epoll_in);
        if (add_res != 0) {
            print("EPOLL_ADD_FAIL");
            return 2;
        }

        // Henuz veri yazilmadi: poll 0 olmali
        let ready_before: int = event_loop_poll(loop, 20);
        if (ready_before == 0) {
            print("READY_BEFORE_ZERO_OK");
        }

        // Pipe'a veri yazalim
        let written: int = fd_write(w_fd, "HELLO_EPOLL_PIPE");
        if (written <= 0) {
            print("WRITE_FAIL");
            return 3;
        }

        // Olay tetiklenmeli
        let ready_after: int = event_loop_poll(loop, 200);
        if (ready_after == 1) {
            print("READY_AFTER_ONE_OK");
        }

        let ev: EpollEvent = event_loop_get_event(loop, 0);
        if (ev.fd == r_fd and event_is_readable(ev.events)) {
            print("EVENT_FD_READABLE_OK");
        }

        let data: str = fd_read(r_fd, 64);
        print("READ_DATA:", data);
        if (data == "HELLO_EPOLL_PIPE") {
            print("PIPE_TRANSFER_VERIFIED");
        }

        pipe_close(p_handle);
        event_loop_close(loop);
        return 0;
    }
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Error: {err}"
    assert "READY_BEFORE_ZERO_OK" in out
    assert "READY_AFTER_ONE_OK" in out
    assert "EVENT_FD_READABLE_OK" in out
    assert "PIPE_TRANSFER_VERIFIED" in out

def test_epoll_socketpair_bidirectional_echo():
    code = """
    import "std/net/event_loop.ax"

    fn main() -> int {
        let loop: EpollEventLoop = event_loop_new();
        let kind: EventKind = event_kind_new();

        let sp_handle: int = socketpair_create();
        let fd1: int = socketpair_fd1(sp_handle);
        let fd2: int = socketpair_fd2(sp_handle);

        event_loop_add(loop, fd1, kind.epoll_in);
        event_loop_add(loop, fd2, kind.epoll_in);

        // fd2'den fd1'e yaz
        fd_write(fd2, "ASYNC_REACTOR_PING");

        let ready: int = event_loop_poll(loop, 200);
        if (ready >= 1) {
            print("SOCKETPAIR_POLL_OK");
        }

        let ev: EpollEvent = event_loop_get_event(loop, 0);
        if (ev.fd == fd1 and event_is_readable(ev.events)) {
            print("SOCKETPAIR_FD1_READABLE_OK");
        }

        let msg1: str = fd_read(fd1, 128);
        if (msg1 == "ASYNC_REACTOR_PING") {
            print("SOCKETPAIR_PING_OK");
        }

        // fd1'den fd2'ye geri echo yaz
        fd_write(fd1, "ASYNC_REACTOR_PONG");

        let ready2: int = event_loop_poll(loop, 200);
        if (ready2 >= 1) {
            let msg2: str = fd_read(fd2, 128);
            if (msg2 == "ASYNC_REACTOR_PONG") {
                print("SOCKETPAIR_PONG_OK");
            }
        }

        socketpair_close(sp_handle);
        event_loop_close(loop);
        return 0;
    }
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Error: {err}"
    assert "SOCKETPAIR_POLL_OK" in out
    assert "SOCKETPAIR_FD1_READABLE_OK" in out
    assert "SOCKETPAIR_PING_OK" in out
    assert "SOCKETPAIR_PONG_OK" in out

def test_epoll_mod_and_del():
    code = """
    import "std/net/event_loop.ax"

    fn main() -> int {
        let loop: EpollEventLoop = event_loop_new();
        let kind: EventKind = event_kind_new();
        let p_handle: int = pipe_create();
        let r_fd: int = pipe_read_fd(p_handle);
        let w_fd: int = pipe_write_fd(p_handle);

        event_loop_add(loop, r_fd, kind.epoll_in);
        // Silme testi
        let del_res: int = event_loop_del(loop, r_fd);
        if (del_res == 0) {
            print("DEL_OK");
        }

        // Silindikten sonra yazilsa da poll 0 donmeli
        fd_write(w_fd, "TEST_AFTER_DEL");
        let ready: int = event_loop_poll(loop, 50);
        if (ready == 0) {
            print("DEL_VERIFIED_ZERO_EVENTS");
        }

        pipe_close(p_handle);
        event_loop_close(loop);
        return 0;
    }
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Error: {err}"
    assert "DEL_OK" in out
    assert "DEL_VERIFIED_ZERO_EVENTS" in out

def test_epoll_multi_socket_reactor():
    code = """
    import "std/net/event_loop.ax"

    fn main() -> int {
        let loop: EpollEventLoop = event_loop_new_with_capacity(256);
        let kind: EventKind = event_kind_new();

        // 8 ayri socketpair olustur
        let h0: int = socketpair_create();
        let h1: int = socketpair_create();
        let h2: int = socketpair_create();
        let h3: int = socketpair_create();

        let r0: int = socketpair_fd1(h0);
        let r1: int = socketpair_fd1(h1);
        let r2: int = socketpair_fd1(h2);
        let r3: int = socketpair_fd1(h3);

        let w0: int = socketpair_fd2(h0);
        let w1: int = socketpair_fd2(h1);
        let w2: int = socketpair_fd2(h2);
        let w3: int = socketpair_fd2(h3);

        event_loop_add(loop, r0, kind.epoll_in);
        event_loop_add(loop, r1, kind.epoll_in);
        event_loop_add(loop, r2, kind.epoll_in);
        event_loop_add(loop, r3, kind.epoll_in);

        // Sadece cift numaralilara yaz (r0 ve r2)
        fd_write(w0, "DATA0");
        fd_write(w2, "DATA2");

        let ready: int = event_loop_poll(loop, 200);
        print("MULTI_READY:", ready);
        if (ready == 2) {
            print("MULTI_REACTOR_2_EVENTS_OK");
        }

        socketpair_close(h0);
        socketpair_close(h1);
        socketpair_close(h2);
        socketpair_close(h3);
        event_loop_close(loop);
        return 0;
    }
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Error: {err}"
    assert "MULTI_REACTOR_2_EVENTS_OK" in out

def test_epoll_nonblocking_tcp_server():
    # Uygun bir port bulalim
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()

    code = f"""
    import "std/net/event_loop.ax"

    fn main() -> int {{
        let port: int = {port};
        let server_fd: int = tcp_server_nonblocking(port);
        if (server_fd < 0) {{
            print("SERVER_BIND_FAIL");
            return 1;
        }}

        let loop: EpollEventLoop = event_loop_new();
        let kind: EventKind = event_kind_new();
        event_loop_add(loop, server_fd, kind.epoll_in);

        // Once baglanti yokken poll 0 olmali
        let ready_none: int = event_loop_poll(loop, 20);
        if (ready_none == 0) {{
            print("NO_CONN_ZERO_OK");
        }}

        // Non-blocking accept - henuz baglanti yok (-2 donmeli)
        let early_client: int = tcp_accept_nonblocking(server_fd);
        if (early_client == -2) {{
            print("EAGAIN_ACCEPT_OK");
        }}

        // Kendimiz baglanti acalim
        let client_sock: int = tcp_connect("127.0.0.1", port);
        if (client_sock < 0) {{
            print("TCP_CONNECT_FAIL");
            return 2;
        }}

        // Epoll artik server_fd'yi hazir gormeli
        let ready: int = event_loop_poll(loop, 500);
        if (ready == 1) {{
            print("SERVER_READY_FOR_ACCEPT");
        }}

        let accepted_fd: int = tcp_accept_nonblocking(server_fd);
        if (accepted_fd >= 0) {{
            print("ACCEPT_NONBLOCKING_SUCCESS");
        }}

        // Istemci veri gondersin
        tcp_send(client_sock, "REACTOR_REQUEST");

        // Accepted soket epoll'e eklensin
        event_loop_add(loop, accepted_fd, kind.epoll_in);
        let ready_client: int = event_loop_poll(loop, 500);
        if (ready_client >= 1) {{
            let req: str = fd_read(accepted_fd, 128);
            if (req == "REACTOR_REQUEST") {{
                print("SERVER_RECEIVED_DATA_OK");
            }}
        }}

        socket_close(client_sock);
        socket_close(accepted_fd);
        socket_close(server_fd);
        event_loop_close(loop);
        return 0;
    }}
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0, f"Error: {err}"
    assert "NO_CONN_ZERO_OK" in out
    assert "EAGAIN_ACCEPT_OK" in out
    assert "SERVER_READY_FOR_ACCEPT" in out
    assert "ACCEPT_NONBLOCKING_SUCCESS" in out
    assert "SERVER_RECEIVED_DATA_OK" in out
