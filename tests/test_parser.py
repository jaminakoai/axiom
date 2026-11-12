"""
Unit tests for Axiom Parser
"""
import pytest
from axiom.lexer import Lexer
from axiom.parser import Parser, ParserError
from axiom.ast_nodes import (
    Program, FunctionDecl, Param, FunctionContract, Block,
    LetDecl, AssignStmt, IfStmt, WhileStmt, ForRangeStmt,
    ReturnStmt, PrintStmt, VerifyStmt, BinaryOp, UnaryOp,
    NumberLiteral, StringLiteral, BooleanLiteral, Identifier, FunctionCall,
    StructDecl, StructInit, MemberAccess, ArrayLiteral, IndexAccess
)

def parse_source(source: str) -> Program:
    tokens = Lexer(source).tokenize()
    parser = Parser(tokens)
    return parser.parse()

def test_function_declaration_basic():
    source = """
    fn hello() {
        print("hello");
    }
    """
    prog = parse_source(source)
    assert len(prog.declarations) == 1
    fn = prog.declarations[0]
    assert isinstance(fn, FunctionDecl)
    assert fn.name == "hello"
    assert fn.return_type == "void"
    assert len(fn.params) == 0
    assert len(fn.body.statements) == 1
    assert isinstance(fn.body.statements[0], PrintStmt)

def test_function_with_params_and_return():
    source = """
    fn add(a: int, b: int) -> int {
        return a + b;
    }
    """
    prog = parse_source(source)
    fn = prog.declarations[0]
    assert isinstance(fn, FunctionDecl)
    assert fn.name == "add"
    assert fn.return_type == "int"
    assert len(fn.params) == 2
    assert fn.params[0].name == "a" and fn.params[0].type_name == "int"
    assert fn.params[1].name == "b" and fn.params[1].type_name == "int"
    ret = fn.body.statements[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, BinaryOp)
    assert ret.value.op == "+"

def test_contracts_requires_ensures():
    source = """
    fn divide(a: int, b: int) -> int
        requires b != 0
        requires a >= 0
        ensures return >= 0
    {
        return a / b;
    }
    """
    prog = parse_source(source)
    fn = prog.declarations[0]
    assert isinstance(fn, FunctionDecl)
    assert len(fn.contract.requires) == 2
    assert len(fn.contract.ensures) == 1

    # Check requires[0]: b != 0
    req0 = fn.contract.requires[0]
    assert isinstance(req0, BinaryOp)
    assert req0.op == "!="
    assert isinstance(req0.left, Identifier) and req0.left.name == "b"

    # Check ensures[0]: return >= 0
    ens0 = fn.contract.ensures[0]
    assert isinstance(ens0, BinaryOp)
    assert ens0.op == ">="
    assert isinstance(ens0.left, Identifier) and ens0.left.name == "return"

def test_let_statements():
    source = """
    let a = 10;
    let mut b: int = 20;
    let c: str;
    """
    prog = parse_source(source)
    assert len(prog.declarations) == 3

    d0 = prog.declarations[0]
    assert isinstance(d0, LetDecl)
    assert d0.name == "a"
    assert not d0.is_mut
    assert isinstance(d0.initializer, NumberLiteral) and d0.initializer.value == 10

    d1 = prog.declarations[1]
    assert isinstance(d1, LetDecl)
    assert d1.name == "b"
    assert d1.is_mut
    assert d1.type_annotation == "int"
    assert isinstance(d1.initializer, NumberLiteral) and d1.initializer.value == 20

    d2 = prog.declarations[2]
    assert isinstance(d2, LetDecl)
    assert d2.name == "c"
    assert d2.type_annotation == "str"
    assert d2.initializer is None

def test_assignment_statement():
    source = "x = 42;"
    prog = parse_source(source)
    stmt = prog.declarations[0]
    assert isinstance(stmt, AssignStmt)
    assert stmt.name == "x"
    assert isinstance(stmt.value, NumberLiteral) and stmt.value.value == 42

def test_if_else_chain():
    source = """
    if x > 10 {
        print("large");
    } else if x == 10 {
        print("ten");
    } else {
        print("small");
    }
    """
    prog = parse_source(source)
    if_stmt = prog.declarations[0]
    assert isinstance(if_stmt, IfStmt)
    assert isinstance(if_stmt.condition, BinaryOp)
    assert if_stmt.condition.op == ">"
    assert len(if_stmt.then_branch.statements) == 1

    # Else branch contains nested IfStmt
    else_block = if_stmt.else_branch
    assert else_block is not None
    nested_if = else_block.statements[0]
    assert isinstance(nested_if, IfStmt)
    assert nested_if.condition.op == "=="
    assert nested_if.else_branch is not None

def test_while_loop():
    source = """
    while i < 10 {
        i = i + 1;
    }
    """
    prog = parse_source(source)
    stmt = prog.declarations[0]
    assert isinstance(stmt, WhileStmt)
    assert isinstance(stmt.condition, BinaryOp)
    assert stmt.condition.op == "<"
    assert len(stmt.body.statements) == 1

def test_for_range_loop():
    source = """
    for i in 0..100 {
        print(i);
    }
    """
    prog = parse_source(source)
    stmt = prog.declarations[0]
    assert isinstance(stmt, ForRangeStmt)
    assert stmt.var_name == "i"
    assert isinstance(stmt.start, NumberLiteral) and stmt.start.value == 0
    assert isinstance(stmt.end, NumberLiteral) and stmt.end.value == 100
    assert len(stmt.body.statements) == 1

def test_verify_statement():
    source = """
    verify x > 0;
    verify y == 10, "y 10 olmalidir";
    """
    prog = parse_source(source)
    v1 = prog.declarations[0]
    v2 = prog.declarations[1]
    assert isinstance(v1, VerifyStmt)
    assert v1.message is None
    assert isinstance(v2, VerifyStmt)
    assert v2.message == "y 10 olmalidir"

def test_operator_precedence_arithmetic():
    # 2 + 3 * 4 should parse as 2 + (3 * 4)
    source = "let res = 2 + 3 * 4;"
    prog = parse_source(source)
    expr = prog.declarations[0].initializer
    assert isinstance(expr, BinaryOp)
    assert expr.op == "+"
    assert isinstance(expr.left, NumberLiteral) and expr.left.value == 2
    assert isinstance(expr.right, BinaryOp)
    assert expr.right.op == "*"

def test_operator_precedence_parentheses():
    # (2 + 3) * 4 should parse as ((2 + 3) * 4)
    source = "let res = (2 + 3) * 4;"
    prog = parse_source(source)
    expr = prog.declarations[0].initializer
    assert isinstance(expr, BinaryOp)
    assert expr.op == "*"
    assert isinstance(expr.left, BinaryOp)
    assert expr.left.op == "+"
    assert isinstance(expr.right, NumberLiteral) and expr.right.value == 4

def test_operator_precedence_logical():
    # a or b and c should parse as a or (b and c)
    source = "let res = a or b and c;"
    prog = parse_source(source)
    expr = prog.declarations[0].initializer
    assert isinstance(expr, BinaryOp)
    assert expr.op == "or"
    assert isinstance(expr.right, BinaryOp)
    assert expr.right.op == "and"

def test_unary_operations():
    source = "let x = -5; let y = not true;"
    prog = parse_source(source)
    u1 = prog.declarations[0].initializer
    assert isinstance(u1, UnaryOp)
    assert u1.op == "-"
    u2 = prog.declarations[1].initializer
    assert isinstance(u2, UnaryOp)
    assert u2.op == "not"

def test_function_call():
    source = "let z = calculate(1, 2 + 3, true);"
    prog = parse_source(source)
    call = prog.declarations[0].initializer
    assert isinstance(call, FunctionCall)
    assert call.callee == "calculate"
    assert len(call.args) == 3

def test_struct_declaration():
    source = """
    struct Point {
        x: int,
        y: int
    }
    """
    prog = parse_source(source)
    assert len(prog.declarations) == 1
    s = prog.declarations[0]
    assert isinstance(s, StructDecl)
    assert s.name == "Point"
    assert len(s.fields) == 2
    assert s.fields[0].name == "x" and s.fields[0].type_name == "int"
    assert s.fields[1].name == "y" and s.fields[1].type_name == "int"

def test_struct_instantiation_and_member_access():
    source = """
    let p = Point { x: 10, y: 20 };
    let px = p.x;
    """
    prog = parse_source(source)
    d0 = prog.declarations[0]
    assert isinstance(d0, LetDecl)
    assert isinstance(d0.initializer, StructInit)
    assert d0.initializer.struct_name == "Point"
    assert len(d0.initializer.fields) == 2
    assert d0.initializer.fields[0].field_name == "x"
    assert d0.initializer.fields[1].field_name == "y"

    d1 = prog.declarations[1]
    assert isinstance(d1, LetDecl)
    assert isinstance(d1.initializer, MemberAccess)
    assert isinstance(d1.initializer.object, Identifier) and d1.initializer.object.name == "p"
    assert d1.initializer.member == "x"

def test_array_literal_and_indexing():
    source = """
    let arr = [10, 20, 30];
    let first = arr[0];
    """
    prog = parse_source(source)
    d0 = prog.declarations[0]
    assert isinstance(d0, LetDecl)
    assert isinstance(d0.initializer, ArrayLiteral)
    assert len(d0.initializer.elements) == 3

    d1 = prog.declarations[1]
    assert isinstance(d1, LetDecl)
    assert isinstance(d1.initializer, IndexAccess)
    assert isinstance(d1.initializer.array, Identifier) and d1.initializer.array.name == "arr"
    assert isinstance(d1.initializer.index, NumberLiteral) and d1.initializer.index.value == 0

def test_array_type_in_param_and_return():
    source = """
    fn process(items: int[]) -> int[] {
        return items;
    }
    """
    prog = parse_source(source)
    fn = prog.declarations[0]
    assert isinstance(fn, FunctionDecl)
    assert fn.params[0].type_name == "int[]"
    assert fn.return_type == "int[]"

def test_syntax_error_missing_brace():
    source = "fn broken() {"
    with pytest.raises(ParserError):
        parse_source(source)

def test_syntax_error_invalid_let():
    source = "let = 10;"
    with pytest.raises(ParserError):
        parse_source(source)
