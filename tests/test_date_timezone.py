"""
Axiom - P2-11: saat dilimi (sabit ofset) ve ISO 8601

Kapsam:
  - date_format_tz / date_iso_tz (ofsetli bicimlendirme)
  - date_parse_iso (Z, +HH:MM, -HH:MM, -HHMM; gecersiz -> Err)
  - date_offset_label, date_duration_label
  - date_local_offset_minutes (makineye bagli; aralik kontrolu)
  - Ofset siniri ±14:00
  - TR/EN; C + LLVM paritesi

KAPSAM SINIRI: IANA tz veritabani ve DST kural tablosu yoktur. Ofset
cagiran tarafindan dakika olarak verilir.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"

# 2026-11-09T00:00:00Z
T0 = 1794182400


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
    return subprocess.run([str(out)], capture_output=True, text=True, timeout=60)


FORMAT_SRC = f'''
import "std/time/date"

fn main() -> int {{
    let t = {T0}
    print("utc:", date_format_tz(t, "%Y-%m-%dT%H:%M:%SZ", 0))
    print("plus3:", date_format_tz(t, "%Y-%m-%d %H:%M", 180))
    print("minus5:", date_format_tz(t, "%Y-%m-%d %H:%M", -300))
    print("half:", date_format_tz(t, "%H:%M", -330))
    print("clamp_hi:", date_format_tz(t, "%Y-%m-%d %H:%M", 9999))
    print("clamp_lo:", date_format_tz(t, "%Y-%m-%d %H:%M", -9999))

    print("iso_utc:", date_iso_tz(t, 0))
    print("iso_p3:", date_iso_tz(t, 180))
    print("iso_m530:", date_iso_tz(t, -330))
    print("iso_p14:", date_iso_tz(t, 840))
    return 0
}}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_format_with_offsets(backend, tmp_path):
    out = _run(FORMAT_SRC, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "utc: 2026-11-09T00:00:00Z",
        "plus3: 2026-11-09 03:00",
        "minus5: 2026-11-08 19:00",
        "half: 18:30",
        "clamp_hi: 2026-11-09 14:00",
        "clamp_lo: 2026-11-08 10:00",
        "iso_utc: 2026-11-09T00:00:00Z",
        "iso_p3: 2026-11-09T03:00:00+03:00",
        "iso_m530: 2026-11-08T18:30:00-05:30",
        "iso_p14: 2026-11-09T14:00:00+14:00",
    ]


PARSE_SRC = f'''
import "std/time/date"

fn main() -> int {{
    let t = {T0}
    let p1 = date_parse_iso("2026-11-09T00:00:00Z")
    print("z:", p1.is_ok, p1.value == t)

    let p2 = date_parse_iso("2026-11-09T03:00:00+03:00")
    print("p3:", p2.is_ok, p2.value == t)

    let p3 = date_parse_iso("2026-11-08T19:00:00-05:00")
    print("m5:", p3.is_ok, p3.value == t)

    let p4 = date_parse_iso("2026-11-09T00:00:00")
    print("no_off:", p4.is_ok, p4.value == t)

    let p5 = date_parse_iso("2026-11-09 00:00:00")
    print("space:", p5.is_ok, p5.value == t)

    let bad1 = date_parse_iso("bozuk")
    print("bad1:", bad1.is_ok, len(bad1.error) > 0)

    let bad2 = date_parse_iso("2026-13-45T99:99:99Z")
    print("bad2:", bad2.is_ok)

    let bad3 = date_parse_iso("")
    print("bad3:", bad3.is_ok)

    // Roundtrip her ofset icin
    let mut ok = 0
    let mut off = -720
    while (off <= 840) {{
        let s = date_iso_tz(t, off)
        let back = date_parse_iso(s)
        if back.is_ok and back.value == t {{
            ok = ok + 1
        }}
        off = off + 30
    }}
    print("roundtrip:", ok)
    return 0
}}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_parse_iso(backend, tmp_path):
    out = _run(PARSE_SRC, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "z: true true",
        "p3: true true",
        "m5: true true",
        "no_off: true true",
        "space: true true",
        "bad1: false true",
        "bad2: false",
        "bad3: false",
        "roundtrip: 53",
    ]


LABEL_SRC = '''
import "std/time/date"

fn main() -> int {
    print("l0:", date_offset_label(0))
    print("l180:", date_offset_label(180))
    print("l_m330:", date_offset_label(-330))
    print("l_hi:", date_offset_label(9999))
    print("l_lo:", date_offset_label(-9999))

    print("d1:", date_duration_label(90061))
    print("d2:", date_duration_label(-3661))
    print("d3:", date_duration_label(45))
    print("d4:", date_duration_label(0))
    print("d5:", date_duration_label(59))
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_labels(backend, tmp_path):
    out = _run(LABEL_SRC, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == [
        "l0: +00:00",
        "l180: +03:00",
        "l_m330: -05:30",
        "l_hi: +14:00",
        "l_lo: -14:00",
        "d1: 1g 1sa 1dk 1sn",
        "d2: 1sa 1dk 1sn",
        "d3: 0dk 45sn",
        "d4: 0dk 0sn",
        "d5: 0dk 59sn",
    ]


LOCAL_SRC = '''
import "std/time/date"

fn main() -> int {
    let off = date_local_offset_minutes()
    print("in_range:", off >= -840 and off <= 840)
    let iso = date_iso_local(date_now_epoch())
    print("iso_len:", len(iso))
    print("has_t:", str_contains(iso, "T"))
    let parsed = date_parse_iso(iso)
    print("reparsed:", parsed.is_ok)
    return 0
}
'''


@pytest.mark.parametrize("backend", ["c", "llvm"])
def test_local_offset_is_sane(backend, tmp_path):
    out = _run(LOCAL_SRC, tmp_path, backend)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines()[0] == "in_range: true"
    assert out.stdout.splitlines()[2] == "has_t: true"
    assert out.stdout.splitlines()[3] == "reparsed: true"


def test_scope_is_documented():
    """IANA tz veritabani olmadigi modul basliginda acikca yazmali."""
    src = (ROOT / "std" / "time" / "date.ax").read_text(encoding="utf-8")
    head = src[:1200]
    assert "IANA" in head
    assert "DST" in head
    assert "sabit ofset" in head
