"""
Axiom - P2-10: hash map yeniden boyutlandirma ve cakisma testleri

Kapsam:
  - Temel islemler (set/get/has/delete/len/free)
  - Yeniden boyutlandirma (16 -> 1024+ bucket, 500+ kayit)
  - Cakisma zinciri (djb2 % 16 == 9 olan c1/c10 ayni bucket)
  - Uzerine yazma, bos anahtar, cok buyuk degerler
  - C + LLVM paritesi
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


BASIC = '''
import "std/collections/map"

fn main() -> int {
    let m = map_create()
    print("empty:", map_len(m))
    print("get_missing:[", map_get(m, "yok"), "]")
    print("has_missing:", map_has(m, "yok"))

    map_set(m, "a", "1")
    map_set(m, "b", "2")
    print("len2:", map_len(m), map_has(m, "a"), map_has(m, "z"))

    map_set(m, "a", "111")
    print("overwrite:", map_len(m), map_get(m, "a"))

    print("del:", map_delete(m, "b"), map_len(m), map_has(m, "b"))
    print("del_missing:", map_delete(m, "yok"))

    map_set(m, "", "bos_anahtar")
    print("empty_key:", map_has(m, ""), map_get(m, ""))

    map_free(m)
    print("done:", true)
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_basic_operations(backend, tmp_path):
    out = _run(BASIC, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "empty: 0",
        "get_missing:[  ]",
        "has_missing: false",
        "len2: 2 true false",
        "overwrite: 2 111",
        "del: true 1 false",
        "del_missing: false",
        "empty_key: true bos_anahtar",
        "done: true",
    ]


RESIZE = '''
import "std/collections/map"

fn main() -> int {
    let m = map_create()
    let mut i = 0
    while (i < 500) {
        map_set(m, "k" + int_to_str(i), "v" + int_to_str(i))
        i = i + 1
    }
    print("len:", map_len(m))
    print("first:", map_get(m, "k0"))
    print("mid:", map_get(m, "k250"))
    print("last:", map_get(m, "k499"))
    print("has_last:", map_has(m, "k499"))

    // Silme sonrasi arama hala dogru
    print("del:", map_delete(m, "k250"), map_has(m, "k250"), len(map_get(m, "k250")))
    print("len_after:", map_len(m))

    // Silinen anahtar yeniden eklenebilmeli
    map_set(m, "k250", "yeni")
    print("readd:", map_len(m), map_get(m, "k250"))
    map_free(m)
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_rehash_at_scale(backend, tmp_path):
    out = _run(RESIZE, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "len: 500",
        "first: v0",
        "mid: v250",
        "last: v499",
        "has_last: true",
        "del: true false 0",
        "len_after: 499",
        "readd: 500 yeni",
    ]


COLLISION = '''
import "std/collections/map"

fn main() -> int {
    // djb2("c1") % 16 == djb2("c10") % 16 == 9  -> ayni bucket
    let m = map_create()
    map_set(m, "c1", "bir")
    map_set(m, "c10", "on")
    print("len:", map_len(m))
    print("c1:", map_get(m, "c1"), "c10:", map_get(m, "c10"))

    // Zincirin ortasini sil; digerleri korunmali
    print("del:", map_delete(m, "c1"), map_get(m, "c10"), map_has(m, "c1"))

    // Cok sayida cakisan anahtar
    let mut i = 0
    while (i < 200) {
        map_set(m, "c" + int_to_str(i), int_to_str(i))
        i = i + 1
    }
    let mut ok = 0
    let mut j = 0
    while (j < 200) {
        let key = "c" + int_to_str(j)
        if map_get(m, key) == int_to_str(j) {
            ok = ok + 1
        }
        j = j + 1
    }
    print("all_found:", ok)
    map_free(m)
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_collision_chains(backend, tmp_path):
    out = _run(COLLISION, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "len: 2",
        "c1: bir c10: on",
        "del: true on false",
        "all_found: 200",
    ]


LONG_VALUES = '''
import "std/collections/map"

fn main() -> int {
    let m = map_create()
    let mut big = ""
    let mut i = 0
    while (i < 100) {
        big = big + "0123456789"
        i = i + 1
    }
    map_set(m, "big", big)
    print("len:", len(map_get(m, "big")))
    map_set(m, "big", "kisa")
    print("after:", map_get(m, "big"))
    map_free(m)
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_long_values_and_shrink(backend, tmp_path):
    out = _run(LONG_VALUES, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == ["len: 1000", "after: kisa"]
