#!/usr/bin/env python3
"""Generate the source-level API inventory used by the G5 review."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "api" / "v0.5.0-alpha.json"
sys.path.insert(0, str(ROOT))


def _function_signature(declaration) -> dict[str, object]:
    return {
        "name": declaration.name,
        "type_parameters": list(declaration.type_params),
        "parameters": [
            {"name": parameter.name, "type": parameter.type_name}
            for parameter in declaration.params
        ],
        "returns": declaration.return_type,
        "requires_count": len(declaration.contract.requires),
        "ensures_count": len(declaration.contract.ensures),
        "documentation": list(declaration.doc),
    }


def _stdlib_inventory() -> list[dict[str, object]]:
    from axiom.ast_nodes import FunctionDecl, ImportStmt, StructDecl
    from axiom.lexer import Lexer
    from axiom.parser import Parser

    modules = []
    for path in sorted((ROOT / "std").rglob("*.ax")):
        program = Parser(Lexer(path.read_text(encoding="utf-8")).tokenize()).parse()
        functions = []
        structs = []
        imports = []
        for declaration in program.declarations:
            if isinstance(declaration, FunctionDecl):
                functions.append(_function_signature(declaration))
            elif isinstance(declaration, StructDecl):
                structs.append({
                    "name": declaration.name,
                    "type_parameters": list(declaration.type_params),
                    "fields": [
                        {"name": field.name, "type": field.type_name}
                        for field in declaration.fields
                    ],
                    "documentation": list(declaration.doc),
                })
            elif isinstance(declaration, ImportStmt):
                imports.append(declaration.path)
            else:
                raise TypeError(
                    f"unhandled top-level declaration {type(declaration).__name__} in {path}"
                )
        modules.append({
            "source": path.relative_to(ROOT).as_posix(),
            "imports": imports,
            "functions": functions,
            "structs": structs,
        })
    return modules


def _builtin_inventory() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    checker_path = ROOT / "axiom" / "checker.py"
    checker = ast.parse(checker_path.read_text(encoding="utf-8"))
    assignments = [
        node.value
        for node in checker.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "BUILTIN_FUNCTIONS"
            for target in node.targets
        )
    ]
    if len(assignments) != 1:
        raise ValueError("expected one BUILTIN_FUNCTIONS source mapping")
    builtin_map = ast.literal_eval(assignments[0])
    special_names = {
        node.test.comparators[0].value
        for node in ast.walk(checker)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Attribute)
        and node.test.left.attr == "callee"
        and len(node.test.comparators) == 1
        and isinstance(node.test.comparators[0], ast.Constant)
        and isinstance(node.test.comparators[0].value, str)
    }
    builtins = [
        {
            "name": name,
            "parameters": list(parameter_types),
            "returns": return_type,
            "classification": "unclassified_checker_builtin",
            "name_family": "rt_prefixed" if name.startswith("rt_") else "unprefixed",
        }
        for name, (parameter_types, return_type) in sorted(builtin_map.items())
    ]
    special_signatures = {
        "len": {
            "signature": "(str | T[]) -> int",
            "constraint": "exactly one argument; T[] is any array type",
        },
        "array_push": {
            "signature": "(T[], T) -> T[]",
            "constraint": "exactly two arguments; element type must match array element type",
        },
        "thread_create": {
            "signature": "(fn(int) -> void | int, int) -> int",
            "constraint": "first argument is a function identifier with one int parameter and void or int return",
        },
    }
    if special_names != set(special_signatures):
        raise ValueError(
            "special checker builtins changed; update their inventory and contract tests: "
            f"found={sorted(special_names)} expected={sorted(special_signatures)}"
        )
    special = [
        {
            "name": name,
            **signature,
            "classification": "unclassified_checker_special_builtin",
        }
        for name, signature in sorted(special_signatures.items())
    ]
    return builtins, special


def build_inventory() -> dict[str, object]:
    builtins, special = _builtin_inventory()
    return {
        "schema_version": 1,
        "source_version": "0.5.0-alpha",
        "status": "source_snapshot_not_a_stability_promise",
        "visibility_policy": (
            "Axiom has no enforced pub/export declarations; entries remain "
            "unclassified until explicitly designated stable in the G5 policy."
        ),
        "stdlib": _stdlib_inventory(),
        "compiler_builtins": builtins,
        "compiler_special_builtins": special,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true", help="write the inventory snapshot")
    action.add_argument("--check", action="store_true", help="fail if the snapshot is stale")
    args = parser.parse_args()
    expected = json.dumps(build_inventory(), ensure_ascii=False, indent=2) + "\n"
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(expected, encoding="utf-8")
        return 0
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != expected:
        print(f"API inventory is stale; run {Path(__file__).relative_to(ROOT)} --write", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
