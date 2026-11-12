"""
Unit & Integration Tests for Axiom Module and Import System
"""
import pytest
from pathlib import Path
import tempfile
import subprocess
import os

from axiom.lexer import Lexer
from axiom.parser import Parser, ParserError
from axiom.ast_nodes import ImportStmt, Program
from axiom.resolver import ModuleResolver, ModuleError
from axiom.checker import TypeChecker
from axiom.codegen_c import CCodeGenerator
from axiom.cli import compile_axiom_source, find_c_compiler, get_runtime_header_path

def test_lexer_import_keyword():
    lexer = Lexer('import "foo.ax"')
    tokens = lexer.tokenize()
    assert tokens[0].type == 'IMPORT'
    assert tokens[0].value == 'import'
    assert tokens[1].type == 'STRING'
    assert tokens[1].value == 'foo.ax'

def test_parser_import_statement():
    source = 'import "math/vector.ax";\nimport "utils.ax"'
    lexer = Lexer(source)
    parser = Parser(lexer.tokenize())
    prog = parser.parse()
    assert len(prog.declarations) == 2
    assert isinstance(prog.declarations[0], ImportStmt)
    assert prog.declarations[0].path == "math/vector.ax"
    assert isinstance(prog.declarations[1], ImportStmt)
    assert prog.declarations[1].path == "utils.ax"

def test_single_module_resolution(tmp_path):
    mod_b = tmp_path / "mod_b.ax"
    mod_b.write_text("fn get_magic() -> int { return 42 }\n", encoding="utf-8")

    main_file = tmp_path / "main.ax"
    main_file.write_text('import "mod_b.ax"\nlet res = get_magic()\n', encoding="utf-8")

    lexer = Lexer(main_file.read_text())
    parser = Parser(lexer.tokenize())
    ast = parser.parse()

    resolver = ModuleResolver(str(main_file))
    resolved_ast = resolver.resolve(ast)

    # Should contain get_magic function and let res
    decl_types = [type(d).__name__ for d in resolved_ast.declarations]
    assert "FunctionDecl" in decl_types
    assert "LetDecl" in decl_types
    assert "ImportStmt" not in decl_types

    # Type checker should pass
    checker = TypeChecker()
    checker.check(resolved_ast)

def test_nested_module_resolution(tmp_path):
    # A -> B -> C
    mod_c = tmp_path / "c.ax"
    mod_c.write_text("fn base_val() -> int { return 10 }\n", encoding="utf-8")

    mod_b = tmp_path / "b.ax"
    mod_b.write_text('import "c.ax"\nfn step_val() -> int { return base_val() * 2 }\n', encoding="utf-8")

    mod_a = tmp_path / "a.ax"
    mod_a.write_text('import "b.ax"\nfn final_val() -> int { return step_val() + 3 }\n', encoding="utf-8")

    lexer = Lexer(mod_a.read_text())
    parser = Parser(lexer.tokenize())
    ast = parser.parse()

    resolver = ModuleResolver(str(mod_a))
    resolved_ast = resolver.resolve(ast)

    fn_names = [d.name for d in resolved_ast.declarations if hasattr(d, 'name')]
    assert "base_val" in fn_names
    assert "step_val" in fn_names
    assert "final_val" in fn_names

    checker = TypeChecker()
    checker.check(resolved_ast)

def test_circular_dependency_direct(tmp_path):
    # A -> B -> A
    mod_a = tmp_path / "a.ax"
    mod_b = tmp_path / "b.ax"

    mod_a.write_text('import "b.ax"\n', encoding="utf-8")
    mod_b.write_text('import "a.ax"\n', encoding="utf-8")

    lexer = Lexer(mod_a.read_text())
    parser = Parser(lexer.tokenize())
    ast = parser.parse()

    resolver = ModuleResolver(str(mod_a))
    with pytest.raises(ModuleError) as exc_info:
        resolver.resolve(ast)
    assert "Döngüsel import" in str(exc_info.value)

def test_circular_dependency_self(tmp_path):
    mod_self = tmp_path / "self_loop.ax"
    mod_self.write_text('import "self_loop.ax"\n', encoding="utf-8")

    lexer = Lexer(mod_self.read_text())
    parser = Parser(lexer.tokenize())
    ast = parser.parse()

    resolver = ModuleResolver(str(mod_self))
    with pytest.raises(ModuleError) as exc_info:
        resolver.resolve(ast)
    assert "Döngüsel import" in str(exc_info.value)

def test_missing_module_error(tmp_path):
    main_file = tmp_path / "main.ax"
    main_file.write_text('import "non_existent_module.ax"\n', encoding="utf-8")

    lexer = Lexer(main_file.read_text())
    parser = Parser(lexer.tokenize())
    ast = parser.parse()

    resolver = ModuleResolver(str(main_file))
    with pytest.raises(ModuleError) as exc_info:
        resolver.resolve(ast)
    assert "bulunamadı" in str(exc_info.value)

def test_diamond_dependency_deduplication(tmp_path):
    # Main imports Left and Right; both import Core
    core = tmp_path / "core.ax"
    core.write_text("struct Point { x: int, y: int }\nfn origin() -> Point { return Point { x: 0, y: 0 } }\n", encoding="utf-8")

    left = tmp_path / "left.ax"
    left.write_text('import "core.ax"\nfn left_pt() -> Point { return origin() }\n', encoding="utf-8")

    right = tmp_path / "right.ax"
    right.write_text('import "core.ax"\nfn right_pt() -> Point { return origin() }\n', encoding="utf-8")

    main_f = tmp_path / "main.ax"
    main_f.write_text('import "left.ax"\nimport "right.ax"\nfn main() -> int { return origin().x }\n', encoding="utf-8")

    c_code = compile_axiom_source(main_f.read_text(), str(main_f))
    assert "struct ax_Point" in c_code
    # Struct and origin function should only be defined once
    assert c_code.count("struct ax_Point {") == 1
    assert c_code.count("ax_Point ax_origin(") == 2  # 1 prototype + 1 definition

def test_subfolder_module_relative_import(tmp_path):
    sub = tmp_path / "lib" / "math"
    sub.mkdir(parents=True)
    mod_math = sub / "calc.ax"
    mod_math.write_text("fn cube(x: int) -> int { return x * x * x }\n", encoding="utf-8")

    main_f = tmp_path / "main.ax"
    main_f.write_text('import "lib/math/calc.ax"\nfn main() -> int { return cube(3) }\n', encoding="utf-8")

    c_code = compile_axiom_source(main_f.read_text(), str(main_f))
    assert "ax_cube" in c_code

def test_multi_module_e2e_execution(tmp_path):
    helper = tmp_path / "helper.ax"
    helper.write_text("""
struct UserRecord {
    id: int,
    active: bool
}

fn build_user(id: int) -> UserRecord {
    return UserRecord { id: id, active: true }
}
""", encoding="utf-8")

    main_f = tmp_path / "main.ax"
    main_f.write_text("""
import "helper.ax"

fn main() -> int {
    let u = build_user(101)
    if u.active {
        print("USER_ID:", u.id)
    }
    return 0
}
""", encoding="utf-8")

    c_code = compile_axiom_source(main_f.read_text(), str(main_f))
    cc = find_c_compiler()
    c_file = tmp_path / "out.c"
    bin_file = tmp_path / "out.bin"
    c_file.write_text(c_code, encoding="utf-8")

    res = subprocess.run([cc, "-O2", str(c_file), "-o", str(bin_file)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr

    run_res = subprocess.run([str(bin_file)], capture_output=True, text=True)
    assert run_res.returncode == 0
    assert "USER_ID: 101" in run_res.stdout
