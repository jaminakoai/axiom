"""
Axiom (λx) - Dokümantasyon Üreteci (`axiom doc`)

`///` doc comment'lerini toplar; statik HTML (veya JSON) üretir.

Kullanım:
    axiom doc src/                  # src/ altındaki tüm .ax
    axiom doc main.ax -o docs/api
    axiom doc std/ --json           # makine okunur çıktı
"""
from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from axiom.ast_nodes import (
    FunctionDecl, StructDecl, Param, Program,
)
from axiom.lexer import Lexer, LexerError
from axiom.parser import Parser, ParserError


@dataclass
class DocItem:
    kind: str                     # "fn" | "struct"
    name: str
    signature: str
    doc: List[str]
    line: int
    fields: List[Dict[str, str]] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    ensures: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """İlk paragraf (listeler için tek satır)."""
        for line in self.doc:
            t = line.strip()
            if t and not t.startswith("#"):
                return t
        return ""


@dataclass
class DocModule:
    path: str
    items: List[DocItem] = field(default_factory=list)


def _expr_text(expr) -> str:
    """AST ifadesini kaba ama okunur bir metne çevirir (yalnız gösterim)."""
    from axiom.ast_nodes import (
        BinaryOp, UnaryOp, NumberLiteral, StringLiteral, BooleanLiteral,
        Identifier, FunctionCall, MemberAccess, IndexAccess, CastExpr,
    )
    if isinstance(expr, NumberLiteral):
        return str(int(expr.value)) if isinstance(expr.value, int) else str(expr.value)
    if isinstance(expr, StringLiteral):
        return json.dumps(expr.value, ensure_ascii=False)
    if isinstance(expr, BooleanLiteral):
        return "true" if expr.value else "false"
    if isinstance(expr, Identifier):
        return expr.name
    if isinstance(expr, CastExpr):
        return f"{_expr_text(expr.expr)} as {expr.target_type}"
    if isinstance(expr, UnaryOp):
        return f"{expr.op}{_expr_text(expr.operand)}" if expr.op in ("-", "+", "!") else f"{expr.op} {_expr_text(expr.operand)}"
    if isinstance(expr, BinaryOp):
        return f"{_expr_text(expr.left)} {expr.op} {_expr_text(expr.right)}"
    if isinstance(expr, FunctionCall):
        return f"{expr.callee}({', '.join(_expr_text(a) for a in expr.args)})"
    if isinstance(expr, MemberAccess):
        return f"{_expr_text(expr.object)}.{expr.member}"
    if isinstance(expr, IndexAccess):
        return f"{_expr_text(expr.array)}[{_expr_text(expr.index)}]"
    return "?"


def _signature(fn: FunctionDecl) -> str:
    params = ", ".join(f"{p.name}: {p.type_name}" for p in fn.params)
    tps = f"<{', '.join(fn.type_params)}>" if getattr(fn, "type_params", None) else ""
    prefix = "@simd " if getattr(fn, "is_simd", False) else ""
    return f"{prefix}fn {fn.name}{tps}({params}) -> {fn.return_type}"


def extract_module(path: Path, source: Optional[str] = None) -> DocModule:
    text = source if source is not None else path.read_text(encoding="utf-8")
    program: Program = Parser(Lexer(text).tokenize()).parse()
    mod = DocModule(path=str(path))
    for decl in program.declarations:
        if isinstance(decl, FunctionDecl):
            mod.items.append(DocItem(
                kind="fn",
                name=decl.name,
                signature=_signature(decl),
                doc=list(getattr(decl, "doc", []) or []),
                line=decl.line,
                requires=[_expr_text(r) for r in decl.contract.requires],
                ensures=[_expr_text(e) for e in decl.contract.ensures],
            ))
        elif isinstance(decl, StructDecl):
            mod.items.append(DocItem(
                kind="struct",
                name=decl.name,
                signature=f"struct {decl.name}" + (
                    f"<{', '.join(decl.type_params)}>" if decl.type_params else ""),
                doc=list(getattr(decl, "doc", []) or []),
                line=decl.line,
                fields=[{"name": f.name, "type": f.type_name} for f in decl.fields],
            ))
    return mod


def collect(targets: List[str]) -> List[DocModule]:
    files: List[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.ax")))
        elif p.is_file():
            files.append(p)
    modules: List[DocModule] = []
    for f in files:
        try:
            modules.append(extract_module(f))
        except (LexerError, ParserError) as e:
            # Bozuk dosya tüm üretimi düşürmesin; atla ve devam et.
            modules.append(DocModule(path=str(f)))
    return modules


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

_CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--muted:#666;--border:#e2e2e2;--code:#f5f5f5;--accent:#0a58ca}
*{box-sizing:border-box}
body{margin:0;font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:var(--fg);background:var(--bg)}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--border);padding:12px 24px;z-index:10}
header h1{margin:0;font-size:18px}
header .sub{color:var(--muted);font-size:13px}
main{display:grid;grid-template-columns:260px 1fr;max-width:1200px;margin:0 auto}
nav{padding:24px;border-right:1px solid var(--border);position:sticky;top:56px;height:calc(100vh - 56px);overflow:auto;font-size:14px}
nav h2{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:18px 0 6px}
nav a{display:block;color:var(--fg);text-decoration:none;padding:2px 0}
nav a:hover{color:var(--accent)}
section{padding:24px 32px;min-width:0}
h2.mod{font-size:20px;margin:32px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--border)}
.item{border:1px solid var(--border);border-radius:8px;padding:16px;margin:0 0 16px}
.item h3{margin:0 0 8px;font-size:16px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.badge{font-size:11px;text-transform:uppercase;letter-spacing:.04em;border-radius:999px;padding:2px 8px;background:var(--code);color:var(--muted);margin-right:8px}
pre,code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}
pre{background:var(--code);padding:10px 12px;border-radius:6px;overflow:auto;margin:8px 0}
.doc p{margin:6px 0}
.muted{color:var(--muted)}
.contract{font-size:13px;margin:6px 0}
.contract span{color:var(--muted)}
td,th{text-align:left;padding:4px 10px 4px 0;font-size:14px;vertical-align:top}
@media(max-width:800px){main{grid-template-columns:1fr}nav{display:none}}
"""


def _doc_html(lines: List[str]) -> str:
    """Basit markdown: paragraf, `#` başlık, `-` liste, `` ` `` kod."""
    if not lines:
        return ""
    out: List[str] = []
    in_list = False
    in_code = False
    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                out.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            out.append(html.escape(line))
            continue

        if not stripped:
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        if stripped.startswith("#"):
            if in_list:
                out.append("</ul>")
                in_list = False
            level = min(6, len(stripped) - len(stripped.lstrip("#")) + 2)
            out.append(f"<h{level}>{html.escape(stripped.lstrip('#').strip())}</h{level}>")
            continue
        if stripped.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{html.escape(stripped[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        out.append(f"<p>{html.escape(stripped)}</p>")

    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def render_html(modules: List[DocModule], title: str = "Axiom API") -> str:
    nav: List[str] = []
    body: List[str] = []

    for mod in modules:
        if not mod.items:
            continue
        anchor_mod = "mod-" + html.escape(mod.path).replace("/", "-").replace(".", "-")
        nav.append(f'<h2>{html.escape(mod.path)}</h2>')
        body.append(f'<h2 class="mod" id="{anchor_mod}">{html.escape(mod.path)}</h2>')

        for item in mod.items:
            anchor = anchor_mod + "-" + html.escape(item.name)
            label = "struct" if item.kind == "struct" else "fn"
            nav.append(f'<a href="#{anchor}">{html.escape(item.name)}</a>')

            parts = [f'<div class="item" id="{anchor}">']
            parts.append(
                f'<h3><span class="badge">{label}</span>{html.escape(item.signature)}</h3>'
            )
            if item.doc:
                parts.append(f'<div class="doc">{_doc_html(item.doc)}</div>')
            else:
                parts.append('<p class="muted">Bu öğe için `///` doc comment yok.</p>')

            if item.kind == "struct" and item.fields:
                parts.append("<table><tr><th>Alan</th><th>Tip</th></tr>")
                for f in item.fields:
                    parts.append(f'<tr><td><code>{html.escape(f["name"])}</code></td>'
                                 f'<td><code>{html.escape(f["type"])}</code></td></tr>')
                parts.append("</table>")

            if item.requires:
                parts.append('<div class="contract"><span>requires:</span> '
                             + "; ".join(f"<code>{html.escape(r)}</code>" for r in item.requires)
                             + "</div>")
            if item.ensures:
                parts.append('<div class="contract"><span>ensures:</span> '
                             + "; ".join(f"<code>{html.escape(e)}</code>" for e in item.ensures)
                             + "</div>")
            parts.append("</div>")
            body.append("\n".join(parts))

    if not body:
        body.append("<p class='muted'>Hiç belgelenmiş öğe bulunamadı.</p>")

    return f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>{_CSS}</style></head>
<body>
<header><h1>{html.escape(title)}</h1>
<div class="sub">Axiom (λx) API — <code>///</code> doc comment'lerinden üretildi</div></header>
<main>
<nav>{''.join(nav)}</nav>
<section>{''.join(body)}</section>
</main>
</body></html>
"""


def render_json(modules: List[DocModule]) -> str:
    data: Dict[str, Any] = {"modules": []}
    for m in modules:
        data["modules"].append({
            "path": m.path,
            "items": [
                {
                    "kind": i.kind,
                    "name": i.name,
                    "signature": i.signature,
                    "doc": i.doc,
                    "summary": i.summary(),
                    "line": i.line,
                    "fields": i.fields,
                    "requires": i.requires,
                    "ensures": i.ensures,
                }
                for i in m.items
            ],
        })
    return json.dumps(data, ensure_ascii=False, indent=2)
