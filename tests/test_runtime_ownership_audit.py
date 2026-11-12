"""
Axiom - Runtime Sahiplik Denetimi (statik tarama)

Sahiplik tablosuna kayitli string'ler (ax_str donduren fonksiyonlarin sonuclari)
asla ham free() ile birakilmamalidir; aksi halde tabloda sarkan kayit kalir ve
sonraki axiom_str_release cift serbest birakmaya yol acar.

Bu test, runtime.h icinde bu deseni statik olarak arar. Boylece yeni bir
runtime fonksiyonu eklenirken ayni hata sinifi CI'da yakalanir.
"""
import re
from pathlib import Path

import pytest

RUNTIME = Path(__file__).resolve().parent.parent / "axiom" / "runtime.h"


def _ax_str_returning_functions(source: str) -> set[str]:
    pat = re.compile(r"AXIOM_RUNTIME_FN\s+ax_str\s+(\w+)\s*\([^;]*?\)\s*\{")
    return {m.group(1) for m in pat.finditer(source)}


def _owned_result_freed(source: str) -> list[tuple[int, str, str]]:
    """ax_str donduren fonksiyonun sonucunu char*'a atayip free() eden yerler."""
    owned = _ax_str_returning_functions(source)
    lines = source.split("\n")
    findings = []
    assign = re.compile(r"\s*(?:const\s+)?char\s*\*\s*(\w+)\s*=\s*(?:\([^)]*\)\s*)?(\w+)\s*\(")
    for i, line in enumerate(lines):
        m = assign.match(line)
        if not m or m.group(2) not in owned:
            continue
        var = m.group(1)
        for j in range(i, min(i + 80, len(lines))):
            if re.search(r"\bfree\s*\(\s*" + re.escape(var) + r"\s*\)", lines[j]):
                findings.append((i + 1, var, m.group(2)))
                break
    return findings


def test_runtime_owned_strings_are_not_freed_directly():
    source = RUNTIME.read_text(encoding="utf-8")
    findings = _owned_result_freed(source)
    assert not findings, (
        "ax_str donduren fonksiyonlarin sonucu ham free() ile birakiliyor "
        "(axiom_str_release kullanin):\n"
        + "\n".join(f"  satir {ln}: {var} = {fn}(...) -> free({var})" for ln, var, fn in findings)
    )


def test_scanner_detects_known_bad_pattern():
    """Tarayicinin kendisi calisiyor mu? Yapay ornekle dogrula."""
    bad = """
AXIOM_RUNTIME_FN ax_str axiom_demo_producer(const char* s) {
    return s;
}
AXIOM_RUNTIME_FN void axiom_demo_consumer(void) {
    char* tmp = (char*)axiom_demo_producer("x");
    free(tmp);
}
"""
    findings = _owned_result_freed(bad)
    assert len(findings) == 1
    assert findings[0][1] == "tmp"


def test_temp_release_keep_is_used_in_generated_code(tmp_path):
    """Codegen mark/adopt/release'i tek cagrida birlestirmeli (performans)."""
    import subprocess
    from pathlib import Path as P

    axiom_bin = P(__file__).resolve().parent.parent / "bin" / "axiom"
    src = tmp_path / "t.ax"
    src.write_text(
        'import "std:encoding:base64"\n'
        "fn main() -> int {\n"
        '    let e = base64_encode("payload")\n'
        "    print(len(e))\n"
        "    return 0\n"
        "}\n",
        encoding="utf-8",
    )
    res = subprocess.run([str(axiom_bin), "emit-c", str(src)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    c = res.stdout
    assert "axiom_temp_release_keep" in c
    # Eski (daha yavas) ikili cagri yolu uretilmemeli
    assert "axiom_str_adopt(" not in c
