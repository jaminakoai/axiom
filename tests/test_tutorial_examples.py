"""
Axiom - Dokümantasyon kod bloklarının doğrulanması

`docs/TUTORIAL.md` içindeki çalıştırılabilir her `axiom` kod bloğu
(`fn main` içeren) derlenmelidir. Bu test, doküman ile dilin zamanla
ayrışmasını (doc rot) engeller.

Kapsam dışı:
  - Parçalı örnekler (yalnızca fonksiyon/struct/ifade gösteren bloklar)
  - Kasıtlı çok-dosyalı örnekler (main.ax + utils.ax): ayrı ele alınır
"""
import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
AXIOM = ROOT / "bin" / "axiom"
TUTORIAL = ROOT / "docs" / "TUTORIAL.md"

# Tek başına derlenemeyecek, kasıtlı olarak ayrı dosyalara bölünmüş örnekler.
# (Bunlar aşağıdaki ayrı testte birlikte doğrulanır.)
MULTI_FILE_MARKERS = ("import \"utils.ax\"",)


def _axiom_blocks():
    src = TUTORIAL.read_text(encoding="utf-8")
    return re.findall(r"```axiom\n(.*?)```", src, re.S)


def _runnable_blocks():
    out = []
    for idx, block in enumerate(_axiom_blocks(), start=1):
        if "fn main" not in block:
            continue
        if any(m in block for m in MULTI_FILE_MARKERS):
            continue
        out.append((idx, block))
    return out


def test_tutorial_exists_and_has_blocks():
    assert TUTORIAL.exists(), f"Rehber bulunamadı: {TUTORIAL}"
    blocks = _axiom_blocks()
    assert len(blocks) >= 20, f"Beklenenden az kod bloğu: {len(blocks)}"
    assert len(_runnable_blocks()) >= 8, "Çalıştırılabilir örnek sayısı beklenenden az"


@pytest.mark.parametrize("index,block", _runnable_blocks(), ids=lambda v: f"blok{v}" if isinstance(v, int) else "")
def test_tutorial_runnable_block_builds(index, block):
    with tempfile.NamedTemporaryFile("w", suffix=".ax", delete=False, encoding="utf-8") as f:
        f.write(block)
        src_path = f.name
    out_path = src_path + ".bin"
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        res = subprocess.run(
            [str(AXIOM), "build", src_path, "-o", out_path],
            capture_output=True, text=True, timeout=240, env=env,
        )
        assert res.returncode == 0, (
            f"TUTORIAL.md blok {index} derlenemedi:\n{res.stdout}\n{res.stderr}\n"
            f"--- kaynak ---\n{block}"
        )
    finally:
        os.remove(src_path)
        if os.path.exists(out_path):
            os.remove(out_path)


def test_tutorial_multi_file_example_builds(tmp_path):
    """Module bolumundeki iki blok birlikte calismali (utils.ax + main.ax)."""
    utils_src = """
struct ConfigReport {
    title: str,
    version: int
}

fn create_report(title: str, version: int) -> ConfigReport {
    return ConfigReport { title: title, version: version }
}
"""
    main_src = """
# main.ax
import "utils.ax"

fn main() -> int {
    let report = create_report("Sistem", 1)
    print(report.title, report.version)
    return 0
}
"""
    (tmp_path / "utils.ax").write_text(utils_src, encoding="utf-8")
    main_path = tmp_path / "main.ax"
    main_path.write_text(main_src, encoding="utf-8")
    out = tmp_path / "main.bin"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    build = subprocess.run(
        [str(AXIOM), "build", str(main_path), "-o", str(out)],
        capture_output=True, text=True, timeout=240, env=env,
    )
    assert build.returncode == 0, build.stdout + build.stderr

    run = subprocess.run([str(out)], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "Sistem 1" in run.stdout


def test_tutorial_does_not_leak_internal_apis():
    """Kullanıcı rehberi iç tanılama API'lerini içermemeli."""
    src = TUTORIAL.read_text(encoding="utf-8")
    for internal in ("str_owned_count", "axiom_temp_mark", "g_axiom", "_ax_tm"):
        assert internal not in src, f"Rehberde iç API sızmış: {internal}"
