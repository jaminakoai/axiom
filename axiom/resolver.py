"""
Axiom Programming Language (λx) - Module Resolver & Dependency Manager
"""
from pathlib import Path
from typing import List, Set, Optional, Union
import os
from axiom.ast_nodes import Program, Stmt, ImportStmt
from axiom.lexer import Lexer, LexerError
from axiom.parser import Parser, ParserError
from axiom.checker import SemanticError

class ModuleError(Exception):
    def __init__(self, message: str, line: int = 1, col: int = 1, file_path: Optional[str] = None):
        loc = f" [Dosya: {file_path}, Satir {line}, Sutun {col}]" if file_path else f" [Satir {line}, Sutun {col}]"
        super().__init__(f"Axiom Modül Hatasi{loc}: {message}")
        self.line = line
        self.col = col
        self.file_path = file_path

STD_DIR = (Path(__file__).resolve().parent.parent / "std").resolve()

OFFENSIVE_MODULES = {
    "security/shellcode": "std:security:shellcode",
    "net/c2": "std:net:c2",
    "security/evasion": "std:security:evasion",
    "security/memdump": "std:security:memdump",
    "net/packet_crafter": "std:net:packet_crafter",
}

def identify_offensive_module(mod_path_str: str, target_path: Optional[Path] = None) -> Optional[str]:
    norm = mod_path_str.replace(":", "/").replace("\\", "/")
    if norm.startswith("std/"):
        norm = norm[4:]
    if norm.endswith(".ax"):
        norm = norm[:-3]
    if norm in OFFENSIVE_MODULES:
        return OFFENSIVE_MODULES[norm]
    if target_path:
        try:
            rel = target_path.resolve().relative_to(STD_DIR)
            rel_str = str(rel).replace("\\", "/")
            if rel_str.endswith(".ax"):
                rel_str = rel_str[:-3]
            if rel_str in OFFENSIVE_MODULES:
                return OFFENSIVE_MODULES[rel_str]
        except Exception:
            pass
    return None

def parse_features(features: Optional[Union[str, List[str], Set[str]]] = None) -> Set[str]:
    result: Set[str] = set()
    env_feat = os.environ.get("AXIOM_FEATURES", "")
    if env_feat:
        for item in env_feat.replace(",", " ").split():
            if item.strip():
                result.add(item.strip())
    if features:
        if isinstance(features, str):
            for item in features.replace(",", " ").split():
                if item.strip():
                    result.add(item.strip())
        elif isinstance(features, (list, tuple, set)):
            for f in features:
                if isinstance(f, str):
                    for item in f.replace(",", " ").split():
                        if item.strip():
                            result.add(item.strip())
    return result

class ModuleResolver:
    def __init__(
        self,
        base_file_path: Optional[str] = None,
        search_paths: Optional[List[Path]] = None,
        features: Optional[Union[str, List[str], Set[str]]] = None
    ):
        if base_file_path and base_file_path != "<stdin>":
            p = Path(base_file_path).resolve()
            self.entry_file = p
            self.entry_dir = p.parent
        else:
            self.entry_file = None
            self.entry_dir = Path.cwd()

        self.features: Set[str] = parse_features(features)

        self.search_paths: List[Path] = [Path(sp).resolve() for sp in (search_paths or [])]
        self.dep_aliases: dict[str, Path] = {}
        # Otomatik olarak paket bağımlılık yollarını (.axiom/deps, deps, src) dahil et
        for parent in [self.entry_dir] + list(self.entry_dir.parents):
            toml_file = parent / "axiom.toml"
            if toml_file.exists():
                for candidate in [parent, parent / "src", parent / ".axiom" / "deps", parent / "deps"]:
                    if candidate.exists() and candidate not in self.search_paths:
                        self.search_paths.append(candidate)
                try:
                    import tomllib
                    toml_data = tomllib.loads(toml_file.read_text(encoding="utf-8"))
                    for dep_k, dep_v in toml_data.get("dependencies", {}).items():
                        if isinstance(dep_v, dict) and "path" in dep_v:
                            dp = (parent / dep_v["path"]).resolve()
                            self.dep_aliases[dep_k] = dp
                            if dp not in self.search_paths:
                                self.search_paths.append(dp)
                        elif isinstance(dep_v, dict) and "git" in dep_v:
                            dp = (parent / ".axiom" / "deps" / dep_k).resolve()
                            self.dep_aliases[dep_k] = dp
                            if dp not in self.search_paths:
                                self.search_paths.append(dp)
                except Exception:
                    pass
                break

    def resolve(self, entry_program: Program) -> Program:
        visited_files: Set[Path] = set()
        if self.entry_file:
            visited_files.add(self.entry_file)
        import_stack: List[Path] = []
        if self.entry_file:
            import_stack.append(self.entry_file)

        resolved_declarations = self._resolve_declarations(
            entry_program.declarations,
            self.entry_dir,
            import_stack,
            visited_files
        )
        return Program(declarations=resolved_declarations, line=entry_program.line, col=entry_program.col)

    def _resolve_declarations(
        self,
        declarations: List[Stmt],
        current_dir: Path,
        import_stack: List[Path],
        visited_files: Set[Path]
    ) -> List[Stmt]:
        new_declarations: List[Stmt] = []
        for stmt in declarations:
            if isinstance(stmt, ImportStmt):
                mod_path_str = stmt.path
                if mod_path_str.startswith("std:"):
                    rel = mod_path_str[4:].lstrip("/\\").replace(":", "/")
                    if not rel.endswith(".ax"):
                        rel += ".ax"
                    target_path = (STD_DIR / rel).resolve()
                elif mod_path_str.startswith("std/") or mod_path_str.startswith("std\\"):
                    rel = mod_path_str[4:]
                    if not rel.endswith(".ax"):
                        rel += ".ax"
                    target_path = (STD_DIR / rel).resolve()
                elif mod_path_str.startswith("@"):
                    # Namespace: "@kullanici/paket" -> deps dizininde "@kullanici__paket"
                    from axiom.package_manager import dep_dir_name, is_valid_dep_name
                    if not is_valid_dep_name(mod_path_str):
                        raise ModuleError(
                            f"Gecersiz paket adi: '{mod_path_str}' (beklenen @kullanici/paket)",
                            stmt.line, stmt.col, str(current_dir))
                    safe = dep_dir_name(mod_path_str)
                    target_path = (current_dir / safe).resolve()
                    if not target_path.is_file():
                        target_path = (current_dir / f"{safe}.ax").resolve()
                    if not target_path.is_file():
                        for sp in self.search_paths:
                            for sub in ("src/lib.ax", "lib.ax", "src/main.ax"):
                                cand = (sp / safe / sub).resolve()
                                if cand.is_file():
                                    target_path = cand
                                    break
                            if target_path.is_file():
                                break
                else:
                    target_path = (current_dir / mod_path_str).resolve()
                    if not target_path.is_file() and not mod_path_str.endswith(".ax"):
                        alt_path = (current_dir / f"{mod_path_str}.ax").resolve()
                        if alt_path.is_file():
                            target_path = alt_path

                if not target_path.is_file():
                    # 1. Tanımlı bağımlılık rumuzları (dep_aliases)
                    if mod_path_str in self.dep_aliases:
                        dep_dir = self.dep_aliases[mod_path_str]
                        for sub_entry in ["src/lib.ax", "lib.ax", "src/main.ax"]:
                            candidate = (dep_dir / sub_entry).resolve()
                            if candidate.is_file():
                                target_path = candidate
                                break

                    # 2. search_paths üzerinde ara (paketler ve bağımlılıklar için)
                    if not target_path.is_file():
                        for sp in self.search_paths:
                            c1 = (sp / mod_path_str).resolve()
                            if c1.is_file():
                                target_path = c1
                                break
                            c2 = (sp / f"{mod_path_str}.ax").resolve()
                            if c2.is_file():
                                target_path = c2
                                break
                            # Paket kütüphane girişleri: lib.ax veya main.ax
                            for sub_entry in ["src/lib.ax", "lib.ax", "src/main.ax"]:
                                c3 = (sp / mod_path_str / sub_entry).resolve()
                                if c3.is_file():
                                    target_path = c3
                                    break
                            if target_path.is_file():
                                break

                if not target_path.is_file():
                    cur_file_str = str(import_stack[-1]) if import_stack else str(current_dir)
                    raise ModuleError(
                        f"İçe aktarılacak modül dosyası bulunamadı: '{mod_path_str}' (Aranan konum: '{target_path}')",
                        stmt.line, stmt.col, cur_file_str
                    )

                # Ofansif güvenlik modülleri sert izolasyonu (--features offensive)
                offensive_mod = identify_offensive_module(mod_path_str, target_path)
                if offensive_mod and "offensive" not in self.features:
                    raise SemanticError(
                        f"Hata: '{offensive_mod}' ofansif güvenlik modülüdür. Yalnızca izinli test ortamlarında '--features offensive' bayrağı ile derlenebilir.",
                        stmt.line, stmt.col
                    )

                if target_path in import_stack:
                    chain = [str(p) for p in import_stack] + [str(target_path)]
                    chain_str = " -> ".join(chain)
                    raise ModuleError(
                        f"Döngüsel import (Circular Dependency) tespit edildi: {chain_str}",
                        stmt.line, stmt.col, str(import_stack[-1])
                    )

                if target_path in visited_files:
                    continue

                try:
                    source_code = target_path.read_text(encoding="utf-8")
                except Exception as e:
                    raise ModuleError(
                        f"Modül dosyası okunamadı: '{target_path}': {str(e)}",
                        stmt.line, stmt.col, str(import_stack[-1])
                    )

                sub_lexer = Lexer(source_code)
                sub_tokens = sub_lexer.tokenize()
                sub_parser = Parser(sub_tokens)
                sub_program = sub_parser.parse()

                import_stack.append(target_path)
                sub_resolved = self._resolve_declarations(
                    sub_program.declarations,
                    target_path.parent,
                    import_stack,
                    visited_files
                )
                import_stack.pop()
                visited_files.add(target_path)

                new_declarations.extend(sub_resolved)
            else:
                new_declarations.append(stmt)

        return new_declarations
