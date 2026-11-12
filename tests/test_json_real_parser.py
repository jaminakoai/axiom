"""
Axiom - Gerçek JSON parser (P1-02)

Eski `json_get_*` düz metin arıyordu: iç içe erişim, dizi, null, Unicode
kaçışı ve tip ayrımı yoktu. Bu testler recursive-descent parser'ı kapsar.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"


def _run(src: str, backend: str = "c"):
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    out = path + ".bin"
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        args = [str(AXIOM), "build", path, "-o", out]
        if backend == "llvm":
            args.insert(2, "--backend=llvm")
        b = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
        assert b.returncode == 0, b.stdout + b.stderr
        return subprocess.run([out], capture_output=True, text=True, timeout=120)
    finally:
        os.remove(path)
        if os.path.exists(out):
            os.remove(out)


BASIC = r'''
import "std/core/error"
import "std/encoding/json"

fn main() -> Result<int, str> {
    let text = "{\"user\":{\"name\":\"ada\",\"age\":36},\"tags\":[\"red\",\"blue\"],\"meta\":{\"score\":9.5,\"nil\":null}}"
    let doc = json_parse_result(text)?

    print("name:", json_str_at(doc, "user.name")?)
    print("age:", json_int_at(doc, "user.age")?)
    print("tag0:", json_str_at(doc, "tags[0]")?)
    print("score:", json_float_at(doc, "meta.score")?)
    print("tagslen:", json_len_at(doc, "tags"))
    print("nil:", json_is_null_at(doc, "meta.nil"))
    print("has:", json_has_path(doc, "meta"))

    let missing = json_str_at(doc, "user.missing")
    print("missing_ok:", missing.is_ok)
    print("missing_err:", missing.error)

    let wrong = json_int_at(doc, "user.name")
    print("wrong_err:", wrong.error)

    json_doc_free(doc)

    let broken = json_parse_result("{oops")
    print("broken_err:", broken.error)
    return result_ok<int>(0)
}
'''

EXPECTED = [
    "name: ada",
    "age: 36",
    "tag0: red",
    "score: 9.5",
    "tagslen: 2",
    "nil: true",
    "has: true",
    "missing_ok: false",
    "missing_err: yol bulunamadi: user.missing",
    "wrong_err: sayi degil: user.name",
    "broken_err: gecersiz JSON (konum 1)",
]


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_json_parser_core(backend):
    out = _run(BASIC, backend)
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.splitlines() == EXPECTED


def test_json_unicode_and_surrogate_pair():
    src = r'''
fn main() -> int {
    let t = "{\"a\":\"caf\\u00e9\",\"b\":\"\\ud83d\\ude00\",\"c\":\"tab\\there\"}"
    let h = json_parse(t)
    if h == 0 { print("ERR:", json_last_error()) return 1 }
    print("a:", json_node_str(json_get(h, "a")))
    print("b:", json_node_str(json_get(h, "b")))
    print("c_len:", len(json_node_str(json_get(h, "c"))))
    json_free(h)
    return 0
}
'''
    out = _run(src)
    assert out.returncode == 0, out.stderr
    lines = out.stdout.splitlines()
    assert lines[0] == "a: café"
    assert lines[1] == "b: 😀"
    assert lines[2] == "c_len: 8"


def test_json_numbers_and_booleans():
    src = r'''
fn main() -> int {
    let h = json_parse("{\"i\":-42,\"f\":1.5e3,\"t\":true,\"n\":false}")
    print(json_node_int(json_get(h, "i")))
    print(json_node_float(json_get(h, "f")))
    print(json_node_bool(json_get(h, "t")))
    print(json_node_bool(json_get(h, "n")))
    json_free(h)
    return 0
}
'''
    out = _run(src)
    assert out.stdout.splitlines() == ["-42", "1500", "true", "false"]


@pytest.mark.parametrize("bad", [
    "{",
    "[1,",
    '{"a" 1}',
    '{"a":}',
    "{} extra",
    '"unterminated',
    '{"a":"\\q"}',
    '{"a":01}',
])
def test_json_invalid_inputs_return_zero_with_error(bad):
    src = f'''
fn main() -> int {{
    let h = json_parse("{bad.replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}")
    print("h:", h)
    if h != 0 {{
        json_free(h)
        print("BEKLENMEZ")
    }}
    print("err_len:", len(json_last_error()))
    return 0
}}
'''
    out = _run(src)
    assert out.returncode == 0, out.stderr
    assert "h: 0" in out.stdout, f"gecersiz girdi kabul edildi: {bad!r}"
    assert "BEKLENMEZ" not in out.stdout
    # hata mesaji bos olmamali
    err_line = [l for l in out.stdout.splitlines() if l.startswith("err_len:")][0]
    assert int(err_line.split(":")[1]) > 0


def test_json_deep_nesting_is_bounded():
    """200 seviyeden derin iç içe yapı reddedilmeli (stack taşması yok)."""
    depth = 260
    text = '{\\"a\\":' * depth + "1" + "}" * depth
    src = f'''
fn main() -> int {{
    let h = json_parse("{text}")
    print("h0:", h == 0)
    if h != 0 {{ json_free(h) }}
    return 0
}}
'''
    out = _run(src)
    assert out.returncode == 0, out.stderr
    assert "h0: true" in out.stdout


def test_json_array_iteration():
    src = r'''
import "std/core/error"
import "std/encoding/json"
fn main() -> Result<int, str> {
    let doc = json_parse_result("{\"ports\":[22,80,443]}")?
    let arr = json_path(doc, "ports")
    let mut i = 0
    let mut sum = 0
    while i < json_len(arr) {
        sum = sum + json_node_int(json_at(arr, i))
        i = i + 1
    }
    print("sum:", sum)
    print("n:", json_len(arr))
    json_doc_free(doc)
    return result_ok<int>(0)
}
'''
    out = _run(src)
    assert out.stdout.splitlines() == ["sum: 545", "n: 3"]
