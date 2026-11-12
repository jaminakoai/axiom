"""
Axiom - `///` doc comment ve `axiom doc` ureteci (P2-03)

Kapsam:
  - lexer DOC token
  - parser'in doc'lari dogru bildirime baglamasi
  - docgen.extract_module / collect / render_html / render_json
  - CLI `axiom doc` ugur ve hata yollari
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AXIOM = ROOT / "bin" / "axiom"

from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.ast_nodes import FunctionDecl, StructDecl
from axiom import docgen

SOURCE = '''\
/// Kullanici yapisi.
/// Ikinci satir.
struct User {
    name: str,
    age: int
}

/// Iki sayiyi toplar.
///
/// # Parametreler
/// - a: birinci sayi
/// - b: ikinci sayi
fn add(a: int, b: int) -> int
    requires a >= 0
    ensures return >= a
{
    return a + b
}

fn undocumented() -> int {
    return 0
}
'''


# ---------------------------------------------------------------------------
# Lexer / parser
# ---------------------------------------------------------------------------

def test_lexer_emits_doc_tokens():
    tokens = Lexer("/// bir\n/// iki\nfn f() -> int { return 0 }\n").tokenize()
    docs = [t.value for t in tokens if t.type == "DOC"]
    assert docs == ["bir", "iki"]
    assert any(t.type == "FN" for t in tokens)


def test_lexer_distinguishes_doc_from_plain_comment():
    tokens = Lexer("// normal\n/// doc\nfn f() -> int { return 0 }\n").tokenize()
    assert [t.value for t in tokens if t.type == "DOC"] == ["doc"]


def test_parser_binds_docs_to_following_declaration_only():
    program = Parser(Lexer(SOURCE).tokenize()).parse()
    by_name = {d.name: d for d in program.declarations if hasattr(d, "name")}

    user = by_name["User"]
    assert isinstance(user, StructDecl)
    assert user.doc == ["Kullanici yapisi.", "Ikinci satir."]

    add = by_name["add"]
    assert isinstance(add, FunctionDecl)
    assert add.doc[0] == "Iki sayiyi toplar."
    assert "# Parametreler" in add.doc
    assert add.doc[-1] == "- b: ikinci sayi"

    # Dokumani olmayan bildirime onceki doc sizmamali
    assert by_name["undocumented"].doc == []


def test_parser_ignores_doc_inside_block():
    src = "fn f() -> int {\n  /// blok ici yorum\n  let x = 1\n  return x\n}\n"
    program = Parser(Lexer(src).tokenize()).parse()
    assert program.declarations[0].doc == []


def test_doc_token_does_not_break_formatting():
    from axiom.formatter import format_source

    assert format_source(SOURCE) == SOURCE


# ---------------------------------------------------------------------------
# docgen
# ---------------------------------------------------------------------------

def test_extract_module_signatures_fields_and_contracts(tmp_path):
    p = tmp_path / "mod.ax"
    p.write_text(SOURCE, encoding="utf-8")
    mod = docgen.extract_module(p)

    assert mod.path == str(p)
    items = {i.name: i for i in mod.items}
    assert items["User"].kind == "struct"
    assert items["User"].signature == "struct User"
    assert items["User"].fields == [
        {"name": "name", "type": "str"},
        {"name": "age", "type": "int"},
    ]
    assert items["add"].signature == "fn add(a: int, b: int) -> int"
    assert items["add"].requires == ["a >= 0"]
    assert items["add"].ensures == ["return >= a"]
    assert items["add"].summary() == "Iki sayiyi toplar."
    assert items["undocumented"].doc == []


def test_summary_skips_headings():
    item = docgen.DocItem(kind="fn", name="f", signature="fn f() -> int",
                          doc=["# Baslik", "Aciklama."], line=1)
    assert item.summary() == "Aciklama."


def test_render_html_escapes_and_includes_docs():
    mod = docgen.DocModule(path="m.ax", items=[
        docgen.DocItem(
            kind="fn", name="f", signature='fn f(s: str) -> int',
            doc=["<script>alert(1)</script>", "", "# Baslik", "- madde"],
            line=1, requires=["s == \"a\" && 1 < 2"],
        )
    ])
    out = docgen.render_html([mod], title="Test <API>")
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out
    assert "Test &lt;API&gt;" in out
    assert "<h3>Baslik</h3>" in out
    assert "<li>madde</li>" in out
    assert "requires:" in out
    assert 'id="mod-m-ax-f"' in out


def test_render_html_marks_undocumented():
    mod = docgen.DocModule(path="m.ax", items=[
        docgen.DocItem(kind="fn", name="f", signature="fn f() -> int", doc=[], line=1)
    ])
    out = docgen.render_html([mod])
    assert "doc comment yok" in out


def test_render_html_empty_module_list():
    out = docgen.render_html([], title="Bos")
    assert "Bos" in out
    assert "bulunamadı" in out


def test_render_json_shape(tmp_path):
    p = tmp_path / "mod.ax"
    p.write_text(SOURCE, encoding="utf-8")
    data = json.loads(docgen.render_json([docgen.collect([str(p)])[0]]))
    assert data["modules"][0]["path"] == str(p)
    item = data["modules"][0]["items"][0]
    for key in ("kind", "name", "signature", "doc", "summary", "line",
                "fields", "requires", "ensures"):
        assert key in item


def test_collect_walks_dirs_and_skips_broken_files(tmp_path):
    (tmp_path / "a.ax").write_text("/// A\nfn a() -> int { return 1 }\n", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.ax").write_text("/// B\nstruct B { x: int }\n", encoding="utf-8")
    (sub / "broken.ax").write_text("fn ??? {", encoding="utf-8")

    mods = docgen.collect([str(tmp_path)])
    names = {i.name for m in mods for i in m.items}
    assert names == {"a", "B"}
    assert len(mods) == 3  # bozuk dosya da modul olarak sayilir (bos)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli(*args, cwd=None):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run([str(AXIOM), *args], capture_output=True, text=True,
                          env=env, cwd=cwd, timeout=120)


def test_cli_doc_generates_html(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "mod.ax").write_text(SOURCE, encoding="utf-8")
    out = tmp_path / "out"

    res = _cli("doc", str(src), "-o", str(out), "--title", "Benim API")
    assert res.returncode == 0, res.stdout + res.stderr
    index = out / "index.html"
    assert index.exists()
    html = index.read_text(encoding="utf-8")
    assert "Benim API" in html
    assert "Kullanici yapisi." in html
    assert "fn add(a: int, b: int) -&gt; int" in html


def test_cli_doc_json_to_stdout(tmp_path):
    f = tmp_path / "mod.ax"
    f.write_text(SOURCE, encoding="utf-8")
    res = _cli("doc", str(f), "--json")
    assert res.returncode == 0, res.stdout + res.stderr
    data = json.loads(res.stdout)
    assert any(i["name"] == "add" for i in data["modules"][0]["items"])


def test_cli_doc_missing_path_fails(tmp_path):
    res = _cli("doc", str(tmp_path / "yok"))
    assert res.returncode != 0
    assert "bulunamadi" in (res.stdout + res.stderr)


def test_repo_std_generates_docs():
    """Kabul kriteri: `axiom doc std/` calisir ve belgeli oge uretir."""
    res = _cli("doc", str(ROOT / "std"), "--json")
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    documented = [i for m in data["modules"] for i in m["items"] if i["doc"]]
    assert len(documented) >= 20
    names = {i["name"] for m in data["modules"] for i in m["items"]}
    assert {"yara_scan_single_pattern", "sigma_eval_op"} <= names
