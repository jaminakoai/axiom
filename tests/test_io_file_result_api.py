"""
Axiom - P2-08: `std/io/file` Result tabanli tam API

Kapsam:
  - Yeni yerlesikler: file_size, is_directory, list_dir, remove_file,
    rename_file, create_dir (C + LLVM)
  - Result sarmalayicilari: file_size_result, list_dir_result,
    remove_file_result, rename_file_result, create_dir_result,
    copy_file_result, dir_present
  - Mevcutlar: read_file, write_file, append_file, read_lines, file_present
  - Hata yollari Err doner (requires ile durdurmaz)
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"


def _run(src: str, workdir: Path, backend: str = "c"):
    f = workdir / "t.ax"
    f.write_text(src, encoding="utf-8")
    out = workdir / "t"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    args = [str(AXIOM), "build", str(f), "-o", str(out)]
    if backend == "llvm":
        args.insert(2, "--backend=llvm")
    res = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
    assert res.returncode == 0, res.stdout + res.stderr
    run = subprocess.run([str(out)], capture_output=True, text=True, timeout=60, cwd=str(workdir))
    return run


# ---------------------------------------------------------------------------
# Yerlesikler (builtin) — C + LLVM paritesi
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_file_builtins(backend, tmp_path):
    src = '''
fn main() -> int {
    let ok = file_write("data.txt", "hello world")
    print("write:", ok)
    print("size:", file_size("data.txt"))
    print("size_missing:", file_size("yok.txt"))
    print("isdir_dot:", is_directory("."))
    print("isdir_file:", is_directory("data.txt"))
    print("isdir_missing:", is_directory("yok"))

    let rename_ok = rename_file("data.txt", "renamed.txt")
    print("rename:", rename_ok, file_exists("renamed.txt"), file_exists("data.txt"))

    let mk = create_dir("a/b/c")
    print("mkdir:", mk, is_directory("a/b/c"), is_directory("a"))
    print("mkdir_again:", create_dir("a/b/c"))

    print("rm:", remove_file("renamed.txt"), file_exists("renamed.txt"))
    print("rm_missing:", remove_file("yok.txt"))
    return 0
}
'''
    out = _run(src, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "write: true",
        "size: 11",
        "size_missing: -1",
        "isdir_dot: true",
        "isdir_file: false",
        "isdir_missing: false",
        "rename: true true false",
        "mkdir: true true true",
        "mkdir_again: true",
        "rm: true false",
        "rm_missing: false",
    ]


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_list_dir_sorted_without_dot_entries(backend, tmp_path):
    for name in ("zebra.txt", "alpha.txt", "middle.txt"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    (tmp_path / "sub").mkdir()

    src = '''
fn main() -> int {
    let raw = list_dir(".")
    let parts = str_split(raw, "\\n")
    let mut i = 0
    while (i < len(parts)) {
        if len(str_trim(parts[i])) > 0 {
            print(parts[i])
        }
        i = i + 1
    }
    print("has_dot:", str_contains(raw, ".\\n"))
    print("missing:", len(list_dir("yok_dizin")))
    return 0
}
'''
    out = _run(src, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    lines = [l for l in out.stdout.splitlines() if l not in ("t", "t.ax")]
    assert lines[:4] == ["alpha.txt", "middle.txt", "sub", "zebra.txt"]
    assert lines[4:] == ["has_dot: false", "missing: 0"]


# ---------------------------------------------------------------------------
# Result katmani
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_result_api_happy_path(backend, tmp_path):
    src = '''
import "std/io/file"
import "std/core/error"

fn main() -> int {
    let mk = create_dir_result("work")
    print("mkdir:", mk.is_ok)

    let w = write_file("work/a.txt", "alpha\\nbeta\\n")
    print("write:", w.is_ok)

    let sz = file_size_result("work/a.txt")
    print("size:", sz.is_ok, sz.value)

    let l = read_lines("work/a.txt")
    print("lines:", l.is_ok, len(l.value), l.value[0])

    let af = append_file("work/a.txt", "gamma\\n")
    print("append:", af.is_ok, len(read_lines("work/a.txt").value))

    let cp = copy_file_result("work/a.txt", "work/b.txt")
    print("copy:", cp.is_ok, file_size_result("work/b.txt").value)

    let ls = list_dir_result("work")
    print("list:", ls.is_ok, len(ls.value), ls.value[0], ls.value[1])

    let rn = rename_file_result("work/b.txt", "work/c.txt")
    print("rename:", rn.is_ok, file_exists("work/c.txt"))

    let rm = remove_file_result("work/c.txt")
    print("remove:", rm.is_ok, file_exists("work/c.txt"))

    print("dir_present:", dir_present("work"), dir_present("yok"))
    return 0
}
'''
    out = _run(src, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "mkdir: true",
        "write: true",
        "size: true 11",
        "lines: true 3 alpha",
        "append: true 4",
        "copy: true 17",
        "list: true 2 a.txt b.txt",
        "rename: true true",
        "remove: true false",
        "dir_present: true false",
    ]


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_result_api_errors_do_not_abort(backend, tmp_path):
    """Veri hatalari Err doner; requires/verify ile program durmaz."""
    src = '''
import "std/io/file"
import "std/core/error"

fn main() -> int {
    let a = read_file("yok.txt")
    print("read_missing:", a.is_ok, str_contains(a.error, "bulunamadi"))

    let b = read_file("")
    print("read_empty:", b.is_ok, str_contains(b.error, "bos"))

    let c = file_size_result("yok.txt")
    print("size_missing:", c.is_ok, c.value)

    let d = list_dir_result("yok_dizin")
    print("list_missing:", d.is_ok, len(d.value))

    let e = remove_file_result("yok.txt")
    print("rm_missing:", e.is_ok)

    let f = rename_file_result("yok.txt", "x.txt")
    print("rn_missing:", f.is_ok)

    let g = write_file("", "x")
    print("write_empty:", g.is_ok)

    let h = copy_file_result("yok.txt", "x.txt")
    print("copy_missing:", h.is_ok)

    // Bos dosya mesru bir sonuctur
    let w = write_file("empty.txt", "")
    let r = read_file("empty.txt")
    print("empty_ok:", w.is_ok, r.is_ok, len(r.value))
    return 0
}
'''
    out = _run(src, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "read_missing: false true",
        "read_empty: false true",
        "size_missing: false 0",
        "list_missing: false 0",
        "rm_missing: false",
        "rn_missing: false",
        "write_empty: false",
        "copy_missing: false",
        "empty_ok: true true 0",
    ]


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_question_mark_propagates(backend, tmp_path):
    src = '''
import "std/io/file"
import "std/core/error"

fn lines_of(p: str) -> Result<int, str> {
    let l = read_lines(p)?
    return result_ok<int>(len(l))
}

fn main() -> int {
    let ok = lines_of("a.txt")
    print("ok:", ok.is_ok, ok.value)
    let bad = lines_of("yok.txt")
    print("bad:", bad.is_ok, str_contains(bad.error, "bulunamadi"))
    return 0
}
'''
    (tmp_path / "a.txt").write_text("1\n2\n3", encoding="utf-8")
    out = _run(src, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == ["ok: true 3", "bad: false true"]


# ---------------------------------------------------------------------------
# Kutuphane sozlesmesi
# ---------------------------------------------------------------------------

def test_no_requires_in_io_file():
    """Bu modul veri hatasi bekler; sozlesme ihlali uretmemeli."""
    src = (ROOT / "std" / "io" / "file.ax").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in src.splitlines()
        if line.strip().startswith("//") or not line.strip().startswith(("requires", "ensures", "verify"))
    )
    assert "requires " not in code
    assert "ensures " not in code
    assert "verify " not in code


def test_documented_functions_exist():
    """`axiom doc` ciktisi yeni API'yi gormeli."""
    res = subprocess.run(
        [str(AXIOM), "doc", str(ROOT / "std" / "io" / "file.ax"), "--json"],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert res.returncode == 0, res.stderr
    import json
    data = json.loads(res.stdout)
    names = {i["name"] for i in data["modules"][0]["items"]}
    for expected in ("read_file", "write_file", "append_file", "read_lines",
                     "file_size_result", "list_dir_result", "remove_file_result",
                     "rename_file_result", "create_dir_result", "copy_file_result",
                     "dir_present", "file_present"):
        assert expected in names, expected
    documented = [i for i in data["modules"][0]["items"] if i["doc"]]
    assert len(documented) >= 7
