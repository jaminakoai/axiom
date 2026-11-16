"""Host-platform compiler discovery and native linker flags."""

from axiom import cli


def test_native_windows_uses_windows_libraries_and_no_pthread(monkeypatch):
    monkeypatch.setattr(cli.sys, "platform", "win32")

    assert cli.get_platform_link_flags(None) == ["-lws2_32"]
    assert cli.get_thread_flag(None) == []


def test_native_macos_uses_system_runtime_without_libdl(monkeypatch):
    monkeypatch.setattr(cli.sys, "platform", "darwin")

    assert cli.get_platform_link_flags(None) == ["-lz"]
    assert cli.get_thread_flag(None) == ["-pthread"]


def test_linux_and_explicit_target_flags_remain_unchanged(monkeypatch):
    monkeypatch.setattr(cli.sys, "platform", "linux")

    assert cli.get_platform_link_flags(None) == ["-lz", "-lssl", "-lcrypto", "-ldl", "-lm"]
    assert cli.get_thread_flag(None) == ["-pthread"]
    assert cli.get_platform_link_flags("windows") == ["-lws2_32"]
    assert cli.get_thread_flag("windows") == []


def test_find_c_compiler_uses_portable_path_lookup(monkeypatch):
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/tools/clang" if name == "clang" else None)

    assert cli.find_c_compiler() == "clang"


def test_target_probe_uses_host_null_device(monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    ok, message = cli.validate_target_toolchain("aarch64-linux-gnu", "clang", ["--target=aarch64-linux-gnu"])

    assert ok
    assert message == ""
    assert seen["command"][-1] == cli.os.devnull
