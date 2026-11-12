"""
Axiom Programming Language (λx) - AST Nodes
"""
from dataclasses import dataclass, field
from typing import List, Optional, Any

@dataclass
class ASTNode:
    line: int = 1
    col: int = 1

# --- Expressions ---

@dataclass
class Expr(ASTNode):
    inferred_type: Optional[str] = None

@dataclass
class NumberLiteral(Expr):
    value: Any = 0  # int or float
    is_float: bool = False

@dataclass
class StringLiteral(Expr):
    value: str = ""

@dataclass
class BooleanLiteral(Expr):
    value: bool = False

@dataclass
class Identifier(Expr):
    name: str = ""

@dataclass
class BinaryOp(Expr):
    left: Expr = field(default_factory=Expr)
    op: str = ""
    right: Expr = field(default_factory=Expr)

@dataclass
class UnaryOp(Expr):
    op: str = ""
    operand: Expr = field(default_factory=Expr)

@dataclass
class FunctionCall(Expr):
    callee: str = ""
    args: List[Expr] = field(default_factory=list)
    type_args: List[str] = field(default_factory=list)

@dataclass
class RangeExpr(Expr):
    start: Expr = field(default_factory=Expr)
    end: Expr = field(default_factory=Expr)
    inclusive: bool = False

@dataclass
class MemberAccess(Expr):
    object: Expr = field(default_factory=Expr)
    member: str = ""

@dataclass
class ArrayLiteral(Expr):
    elements: List[Expr] = field(default_factory=list)

@dataclass
class IndexAccess(Expr):
    array: Expr = field(default_factory=Expr)
    index: Expr = field(default_factory=Expr)

@dataclass
class StructFieldInit(ASTNode):
    field_name: str = ""
    value: Expr = field(default_factory=Expr)

@dataclass
class TryExpr(Expr):
    expr: Expr = field(default_factory=Expr)


@dataclass
class CastExpr(Expr):
    expr: Expr = field(default_factory=Expr)
    target_type: str = ""

@dataclass
class StructInit(Expr):
    struct_name: str = ""
    fields: List[StructFieldInit] = field(default_factory=list)
    type_args: List[str] = field(default_factory=list)

# --- Statements ---

@dataclass
class Stmt(ASTNode):
    pass

@dataclass
class ImportStmt(Stmt):
    path: str = ""

@dataclass
class Block(Stmt):
    statements: List[Stmt] = field(default_factory=list)

# --- Pattern Matching (Örüntü Eşleme) ---

@dataclass
class Pattern(ASTNode):
    pass

@dataclass
class WildcardPattern(Pattern):
    pass

@dataclass
class LiteralPattern(Pattern):
    literal: Expr = field(default_factory=Expr)

@dataclass
class IdentPattern(Pattern):
    name: str = ""

@dataclass
class MatchArm(ASTNode):
    pattern: Pattern = field(default_factory=Pattern)
    guard: Optional[Expr] = None
    body: Any = None  # Block, Expr, or Stmt

@dataclass
class MatchStmt(Stmt):
    subject: Expr = field(default_factory=Expr)
    arms: List[MatchArm] = field(default_factory=list)

@dataclass
class MatchExpr(Expr):
    subject: Expr = field(default_factory=Expr)
    arms: List[MatchArm] = field(default_factory=list)

@dataclass
class LetDecl(Stmt):
    name: str = ""
    is_mut: bool = False
    type_annotation: Optional[str] = None
    initializer: Optional[Expr] = None

@dataclass
class AssignStmt(Stmt):
    name: str = ""
    value: Expr = field(default_factory=Expr)
    target: Optional[Expr] = None

@dataclass
class IfStmt(Stmt):
    condition: Expr = field(default_factory=Expr)
    then_branch: Block = field(default_factory=Block)
    else_branch: Optional[Block] = None

@dataclass
class WhileStmt(Stmt):
    condition: Expr = field(default_factory=Expr)
    body: Block = field(default_factory=Block)
    invariants: List[Expr] = field(default_factory=list)

@dataclass
class ForRangeStmt(Stmt):
    var_name: str = ""
    start: Expr = field(default_factory=Expr)
    end: Expr = field(default_factory=Expr)
    body: Block = field(default_factory=Block)
    invariants: List[Expr] = field(default_factory=list)

ForStmt = ForRangeStmt

@dataclass
class DeferStmt(Stmt):
    stmt: Stmt = field(default_factory=Stmt)

@dataclass
class ReturnStmt(Stmt):
    value: Optional[Expr] = None

@dataclass
class PrintStmt(Stmt):
    args: List[Expr] = field(default_factory=list)

@dataclass
class ExprStmt(Stmt):
    expr: Expr = field(default_factory=Expr)

@dataclass
class VerifyStmt(Stmt):
    condition: Expr = field(default_factory=Expr)
    message: Optional[str] = None

@dataclass
class BreakStmt(Stmt):
    pass

@dataclass
class ContinueStmt(Stmt):
    pass

# --- Structs, Contracts & Declarations ---

@dataclass
class StructField(ASTNode):
    name: str = ""
    type_name: str = "int"

@dataclass
class StructDecl(Stmt):
    name: str = ""
    fields: List[StructField] = field(default_factory=list)
    type_params: List[str] = field(default_factory=list)
    doc: List[str] = field(default_factory=list)

@dataclass
class Param(ASTNode):
    name: str = ""
    type_name: str = "int"

@dataclass
class FunctionContract:
    requires: List[Expr] = field(default_factory=list)
    ensures: List[Expr] = field(default_factory=list)

@dataclass
class FunctionDecl(Stmt):
    name: str = ""
    params: List[Param] = field(default_factory=list)
    return_type: str = "void"
    contract: FunctionContract = field(default_factory=FunctionContract)
    body: Block = field(default_factory=Block)
    is_simd: bool = False
    doc: List[str] = field(default_factory=list)
    type_params: List[str] = field(default_factory=list)

@dataclass
class Program(ASTNode):
    declarations: List[Stmt] = field(default_factory=list)
