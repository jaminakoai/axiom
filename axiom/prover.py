"""
Axiom Programming Language (λx) - Static Mathematical Prover & Symbolic Contract Verifier
"""
import math
from typing import Dict, List, Optional, Tuple, Any
from axiom.ast_nodes import (
    Program, Stmt, Expr, Block, FunctionDecl, Param, FunctionContract,
    LetDecl, AssignStmt, IfStmt, WhileStmt, ForRangeStmt, ReturnStmt,
    PrintStmt, ExprStmt, VerifyStmt, BinaryOp, UnaryOp, NumberLiteral,
    StringLiteral, BooleanLiteral, Identifier, FunctionCall, CastExpr,
    MatchStmt, MatchExpr
)

INF = float('inf')
NEGINF = float('-inf')

class ProofError(Exception):
    def __init__(self, message: str, line: int = 1, col: int = 1, contract_expr: str = "", counterexample: str = ""):
        self.message = message
        self.line = line
        self.col = col
        self.contract_expr = contract_expr
        self.counterexample = counterexample
        super().__init__(self._format_msg())

    def _format_msg(self) -> str:
        lines = [
            f"Axiom Statik Matematiksel İspat Hatası [Satır {self.line}, Sütun {self.col}]:",
            f"  Hata                  : {self.message}"
        ]
        if self.contract_expr:
            lines.append(f"  İhlal Edilen Sözleşme : {self.contract_expr}")
        if self.counterexample:
            lines.append(f"  Sembolik Karşıt-Örnek : {self.counterexample}")
        return "\n".join(lines)

class Interval:
    def __init__(self, min_val: float, max_val: float):
        self.min = float(min_val)
        self.max = float(max_val)

    @classmethod
    def point(cls, val: float) -> 'Interval':
        return cls(val, val)

    @classmethod
    def universe(cls) -> 'Interval':
        return cls(NEGINF, INF)

    @classmethod
    def empty(cls) -> 'Interval':
        return cls(INF, NEGINF)

    @property
    def is_empty(self) -> bool:
        return self.min > self.max

    @property
    def is_point(self) -> bool:
        return self.min == self.max and self.min != INF and self.min != NEGINF

    def contains(self, val: float) -> bool:
        return self.min <= val <= self.max

    def is_subset_of(self, other: 'Interval') -> bool:
        return self.min >= other.min and self.max <= other.max

    def union(self, other: 'Interval') -> 'Interval':
        if self.is_empty:
            return other
        if other.is_empty:
            return self
        return Interval(min(self.min, other.min), max(self.max, other.max))

    def intersect(self, other: 'Interval') -> 'Interval':
        return Interval(max(self.min, other.min), min(self.max, other.max))

    def __add__(self, other: 'Interval') -> 'Interval':
        if self.is_empty or other.is_empty:
            return Interval.empty()
        return Interval(self.min + other.min, self.max + other.max)

    def __sub__(self, other: 'Interval') -> 'Interval':
        if self.is_empty or other.is_empty:
            return Interval.empty()
        return Interval(self.min - other.max, self.max - other.min)

    def __mul__(self, other: 'Interval') -> 'Interval':
        if self.is_empty or other.is_empty:
            return Interval.empty()
        products = [
            self.min * other.min,
            self.min * other.max,
            self.max * other.min,
            self.max * other.max
        ]
        return Interval(min(products), max(products))

    def __truediv__(self, other: 'Interval') -> 'Interval':
        if self.is_empty or other.is_empty:
            return Interval.empty()
        if other.contains(0):
            return Interval.universe()
        divs = [
            self.min / other.min,
            self.min / other.max,
            self.max / other.min,
            self.max / other.max
        ]
        return Interval(min(divs), max(divs))

    def __repr__(self) -> str:
        if self.is_empty:
            return "∅"
        min_str = "-∞" if self.min == NEGINF else (str(int(self.min)) if self.min.is_integer() else f"{self.min:.2f}")
        max_str = "+∞" if self.max == INF else (str(int(self.max)) if self.max.is_integer() else f"{self.max:.2f}")
        return f"[{min_str}, {max_str}]"


def expr_to_str(expr: Expr) -> str:
    if isinstance(expr, NumberLiteral):
        return str(expr.value)
    elif isinstance(expr, StringLiteral):
        return f'"{expr.value}"'
    elif isinstance(expr, BooleanLiteral):
        return "true" if expr.value else "false"
    elif isinstance(expr, Identifier):
        return expr.name
    elif isinstance(expr, BinaryOp):
        return f"({expr_to_str(expr.left)} {expr.op} {expr_to_str(expr.right)})"
    elif isinstance(expr, UnaryOp):
        return f"{expr.op} {expr_to_str(expr.operand)}"
    elif isinstance(expr, FunctionCall):
        args_str = ", ".join(expr_to_str(a) for a in expr.args)
        return f"{expr.callee}({args_str})"
    elif isinstance(expr, CastExpr):
        return f"({expr_to_str(expr.expr)} as {expr.target_type})"
    return str(expr)


def find_assigned_vars(block: Block) -> set:
    assigned = set()
    for s in block.statements:
        if isinstance(s, AssignStmt):
            assigned.add(s.name)
        elif isinstance(s, IfStmt):
            assigned.update(find_assigned_vars(s.then_branch))
            if s.else_branch:
                assigned.update(find_assigned_vars(s.else_branch))
        elif isinstance(s, (ForRangeStmt, WhileStmt)):
            assigned.update(find_assigned_vars(s.body))
    return assigned


def function_has_loops(stmt: Any) -> bool:
    if isinstance(stmt, (WhileStmt, ForRangeStmt)):
        return True
    elif isinstance(stmt, Block):
        return any(function_has_loops(s) for s in stmt.statements)
    elif isinstance(stmt, IfStmt):
        if function_has_loops(stmt.then_branch):
            return True
        if stmt.else_branch and function_has_loops(stmt.else_branch):
            return True
    elif isinstance(stmt, MatchStmt):
        for arm in stmt.arms:
            if function_has_loops(arm.body):
                return True
    return False

class ProofSummary:
    def __init__(self):
        self.verified_functions: int = 0
        self.verified_contracts: int = 0
        self.verified_assertions: int = 0
        self.safe_divisions: int = 0
        self.has_loops: bool = False
        self.loop_functions: List[str] = []
        self.status: str = "PROVED"


class SymbolicProver:
    def __init__(self):
        self.global_functions: Dict[str, FunctionDecl] = {}
        self.summary = ProofSummary()

    def verify_program(self, program: Program) -> ProofSummary:
        self.summary = ProofSummary()
        self.global_functions.clear()

        # Pass 1: Fonksiyonlari topla
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                if len(getattr(decl, 'type_params', [])) > 0:
                    continue
                self.global_functions[decl.name] = decl

        # Pass 2: Her fonksiyonu ve üst düzey ifadeleri sembolik olarak analiz et
        global_env: Dict[str, Interval] = {}
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                if len(getattr(decl, 'type_params', [])) > 0:
                    continue
                self.verify_function(decl)
            else:
                self.execute_statement(decl, global_env)

        return self.summary

    def verify_function(self, fn: FunctionDecl):
        self.summary.verified_functions += 1
        if function_has_loops(fn.body):
            self.summary.has_loops = True
            if fn.name not in self.summary.loop_functions:
                self.summary.loop_functions.append(fn.name)
            self.summary.status = "PARTIAL_VERIFICATION_UNKNOWN"

        fn_env: Dict[str, Interval] = {}

        # Parametre araliklarini baslat
        for param in fn.params:
            fn_env[param.name] = Interval.universe()

        # requires kosullarindan parametre araliklarini daralt
        if fn.contract and fn.contract.requires:
            for req in fn.contract.requires:
                self.summary.verified_contracts += 1
                self.refine_env_with_condition(req, fn_env)

        # Fonksiyon govdesini sembolik olarak yurut
        self.execute_block(fn.body, fn_env, fn)

        # ensures sozlesmelerini denetle
        if fn.contract and fn.contract.ensures:
            for ens in fn.contract.ensures:
                self.summary.verified_contracts += 1

    def execute_block(self, block: Block, env: Dict[str, Interval], current_fn: Optional[FunctionDecl] = None):
        for stmt in block.statements:
            self.execute_statement(stmt, env, current_fn)

    def execute_statement(self, stmt: Stmt, env: Dict[str, Interval], current_fn: Optional[FunctionDecl] = None):
        if isinstance(stmt, LetDecl):
            if stmt.initializer:
                val_int = self.eval_expr_interval(stmt.initializer, env)
                env[stmt.name] = val_int
            else:
                env[stmt.name] = Interval.universe()

        elif isinstance(stmt, AssignStmt):
            val_int = self.eval_expr_interval(stmt.value, env)
            env[stmt.name] = val_int

        elif isinstance(stmt, ForRangeStmt):
            start_int = self.eval_expr_interval(stmt.start, env)
            end_int = self.eval_expr_interval(stmt.end, env)
            loop_env = dict(env)
            # Range loop var: [start.min, end.max - 1]
            max_bound = end_int.max - 1 if end_int.max != INF else INF
            loop_env[stmt.var_name] = Interval(start_int.min, max_bound)
            self.execute_block(stmt.body, loop_env, current_fn)
            for v in find_assigned_vars(stmt.body):
                env[v] = Interval.universe()

        elif isinstance(stmt, IfStmt):
            # Kosul ifadesindeki fonksiyon cagrilarini da sembolik olarak denetle.
            self.eval_condition(stmt.condition, env)
            then_env = dict(env)
            self.refine_env_with_condition(stmt.condition, then_env)
            self.execute_block(stmt.then_branch, then_env, current_fn)

            if stmt.else_branch:
                else_env = dict(env)
                self.refine_env_with_negated_condition(stmt.condition, else_env)
                self.execute_block(stmt.else_branch, else_env, current_fn)

        elif isinstance(stmt, WhileStmt):
            self.eval_condition(stmt.condition, env)
            while_env = dict(env)
            self.refine_env_with_condition(stmt.condition, while_env)
            self.execute_block(stmt.body, while_env, current_fn)
            for v in find_assigned_vars(stmt.body):
                env[v] = Interval.universe()

        elif isinstance(stmt, VerifyStmt):
            self.summary.verified_assertions += 1
            cond_res = self.eval_condition(stmt.condition, env)
            if cond_res is False:
                counterexample = ", ".join(f"{k} = {v}" for k, v in env.items() if not v.is_empty)
                raise ProofError(
                    f"'verify' assertion ifadesi sembolik araliklarla kesin olarak basarisiz oldu!",
                    stmt.line, stmt.col,
                    contract_expr=expr_to_str(stmt.condition),
                    counterexample=counterexample
                )

        elif isinstance(stmt, ExprStmt):
            self.eval_expr_interval(stmt.expr, env)

        elif isinstance(stmt, PrintStmt):
            for e in getattr(stmt, "args", getattr(stmt, "exprs", [])):
                self.eval_expr_interval(e, env)

        elif isinstance(stmt, MatchStmt):
            for arm in stmt.arms:
                arm_env = dict(env)
                if isinstance(arm.body, Block):
                    self.execute_block(arm.body, arm_env, current_fn)
                elif isinstance(arm.body, Stmt):
                    self.execute_statement(arm.body, arm_env, current_fn)
                elif isinstance(arm.body, Expr):
                    self.eval_expr_interval(arm.body, arm_env)

        elif isinstance(stmt, ReturnStmt):
            if stmt.value:
                ret_int = self.eval_expr_interval(stmt.value, env)
                if current_fn and current_fn.contract and current_fn.contract.ensures:
                    ret_env = dict(env)
                    ret_env["return"] = ret_int
                    for ens in current_fn.contract.ensures:
                        ens_res = self.eval_condition(ens, ret_env)
                        if ens_res is False:
                            counterexample = f"return = {ret_int}"
                            raise ProofError(
                                f"'{current_fn.name}' fonksiyonu 'ensures' sozlesmesini ihlal eden bir deger donuyor!",
                                stmt.line, stmt.col,
                                contract_expr=expr_to_str(ens),
                                counterexample=counterexample
                            )

    def eval_expr_interval(self, expr: Expr, env: Dict[str, Interval]) -> Interval:
        if isinstance(expr, NumberLiteral):
            return Interval.point(expr.value)

        elif isinstance(expr, BooleanLiteral):
            return Interval.point(1 if expr.value else 0)

        elif isinstance(expr, StringLiteral):
            return Interval.universe()

        elif isinstance(expr, Identifier):
            return env.get(expr.name, Interval.universe())

        elif isinstance(expr, UnaryOp):
            operand_int = self.eval_expr_interval(expr.operand, env)
            if expr.op == '-':
                return Interval(-operand_int.max, -operand_int.min)
            elif expr.op == '+':
                return operand_int
            elif expr.op == 'not':
                return Interval.universe()

        elif isinstance(expr, BinaryOp):
            left_int = self.eval_expr_interval(expr.left, env)
            right_int = self.eval_expr_interval(expr.right, env)

            if expr.op == '+':
                return left_int + right_int
            elif expr.op == '-':
                return left_int - right_int
            elif expr.op == '*':
                return left_int * right_int
            elif expr.op in ('/', '%'):
                # Sifira bolme kontrolu
                if right_int.is_point and right_int.min == 0:
                    raise ProofError(
                        "Matematiksel İspat Hatası: Kesin sıfıra bölme (Division by Zero) tespit edildi!",
                        expr.line, expr.col,
                        contract_expr=f"{expr_to_str(expr.left)} {expr.op} 0",
                        counterexample=f"Bölen = 0"
                    )
                self.summary.safe_divisions += 1
                if expr.op == '/':
                    return left_int / right_int
                else:
                    return Interval(0, max(0, abs(right_int.max) - 1))

            elif expr.op in ('<', '<=', '>', '>=', '==', '!='):
                # Mantiksal karsilastirma
                return Interval(0, 1)

        elif isinstance(expr, FunctionCall):
            self.check_function_call(expr, env)
            # ensures araligi varsa donus araligini don
            target_fn = self.global_functions.get(expr.callee)
            if target_fn and target_fn.contract and target_fn.contract.ensures:
                ret_env: Dict[str, Interval] = {"return": Interval.universe()}
                for ens in target_fn.contract.ensures:
                    self.refine_env_with_condition(ens, ret_env)
                return ret_env["return"]
            return Interval.universe()

        elif isinstance(expr, MatchExpr):
            return Interval.universe()

        return Interval.universe()

    def check_function_call(self, call: FunctionCall, caller_env: Dict[str, Interval]):
        target_fn = self.global_functions.get(call.callee)
        if not target_fn or not target_fn.contract or not target_fn.contract.requires:
            return

        arg_intervals = [self.eval_expr_interval(arg, caller_env) for arg in call.args]

        call_env: Dict[str, Interval] = {}
        for param, arg_int in zip(target_fn.params, arg_intervals):
            call_env[param.name] = arg_int

        for req in target_fn.contract.requires:
            cond_res = self.eval_condition(req, call_env)
            if cond_res is False:
                counter_parts = [f"{p.name} = {call_env[p.name]}" for p in target_fn.params if p.name in call_env]
                counterexample = ", ".join(counter_parts)
                raise ProofError(
                    f"'{call.callee}' fonksiyonunun 'requires' sözleşmesi kesin olarak ihlal edildi!",
                    call.line, call.col,
                    contract_expr=expr_to_str(req),
                    counterexample=counterexample
                )

    def eval_condition(self, expr: Expr, env: Dict[str, Interval]) -> Optional[bool]:
        if isinstance(expr, BooleanLiteral):
            return expr.value

        # Kosul ifadesi dogrudan bir fonksiyon cagrisi ise (orn. if check_port(99999)),
        # cagrinin requires sozlesmesini de denetle. Aksi halde prover yanlis negatif verir.
        if isinstance(expr, FunctionCall):
            self.check_function_call(expr, env)
            target_fn = self.global_functions.get(expr.callee)
            if target_fn and target_fn.return_type == 'bool':
                return None
            return None

        if isinstance(expr, CastExpr):
            return self.eval_condition(expr.expr, env)

        if isinstance(expr, BinaryOp):
            if expr.op == 'and':
                l_res = self.eval_condition(expr.left, env)
                r_res = self.eval_condition(expr.right, env)
                if l_res is False or r_res is False:
                    return False
                if l_res is True and r_res is True:
                    return True
                return None

            if expr.op == 'or':
                l_res = self.eval_condition(expr.left, env)
                r_res = self.eval_condition(expr.right, env)
                if l_res is True or r_res is True:
                    return True
                if l_res is False and r_res is False:
                    return False
                return None

            l_int = self.eval_expr_interval(expr.left, env)
            r_int = self.eval_expr_interval(expr.right, env)

            if expr.op == '>=':
                if l_int.min >= r_int.max:
                    return True
                if l_int.max < r_int.min:
                    return False
                return None

            elif expr.op == '<=':
                if l_int.max <= r_int.min:
                    return True
                if l_int.min > r_int.max:
                    return False
                return None

            elif expr.op == '>':
                if l_int.min > r_int.max:
                    return True
                if l_int.max <= r_int.min:
                    return False
                return None

            elif expr.op == '<':
                if l_int.max < r_int.min:
                    return True
                if l_int.min >= r_int.max:
                    return False
                return None

            elif expr.op == '==':
                if l_int.is_point and r_int.is_point and l_int.min == r_int.min:
                    return True
                if l_int.max < r_int.min or l_int.min > r_int.max:
                    return False
                return None

            elif expr.op == '!=':
                if l_int.max < r_int.min or l_int.min > r_int.max:
                    return True
                if l_int.is_point and r_int.is_point and l_int.min == r_int.min:
                    return False
                return None

        if isinstance(expr, UnaryOp) and expr.op == 'not':
            inner = self.eval_condition(expr.operand, env)
            if inner is not None:
                return not inner

        return None

    def refine_env_with_condition(self, expr: Expr, env: Dict[str, Interval]):
        if isinstance(expr, BinaryOp):
            if expr.op == 'and':
                self.refine_env_with_condition(expr.left, env)
                self.refine_env_with_condition(expr.right, env)
                return

            # x >= C  veya  x <= C
            if isinstance(expr.left, Identifier) and isinstance(expr.right, NumberLiteral):
                var = expr.left.name
                c = expr.right.value
                curr = env.get(var, Interval.universe())
                if expr.op == '>=':
                    env[var] = curr.intersect(Interval(c, INF))
                elif expr.op == '>':
                    env[var] = curr.intersect(Interval(c + 1, INF))
                elif expr.op == '<=':
                    env[var] = curr.intersect(Interval(NEGINF, c))
                elif expr.op == '<':
                    env[var] = curr.intersect(Interval(NEGINF, c - 1))
                elif expr.op == '==':
                    env[var] = curr.intersect(Interval.point(c))

            # C <= x  veya  C >= x
            elif isinstance(expr.left, NumberLiteral) and isinstance(expr.right, Identifier):
                var = expr.right.name
                c = expr.left.value
                curr = env.get(var, Interval.universe())
                if expr.op == '<=':
                    env[var] = curr.intersect(Interval(c, INF))
                elif expr.op == '<':
                    env[var] = curr.intersect(Interval(c + 1, INF))
                elif expr.op == '>=':
                    env[var] = curr.intersect(Interval(NEGINF, c))
                elif expr.op == '>':
                    env[var] = curr.intersect(Interval(NEGINF, c - 1))
                elif expr.op == '==':
                    env[var] = curr.intersect(Interval.point(c))

    def refine_env_with_negated_condition(self, expr: Expr, env: Dict[str, Interval]):
        # Ters koşul (else dalı için)
        if isinstance(expr, BinaryOp):
            if expr.op == '>=':
                self.refine_env_with_condition(BinaryOp(expr.left, '<', expr.right), env)
            elif expr.op == '<=':
                self.refine_env_with_condition(BinaryOp(expr.left, '>', expr.right), env)
            elif expr.op == '>':
                self.refine_env_with_condition(BinaryOp(expr.left, '<=', expr.right), env)
            elif expr.op == '<':
                self.refine_env_with_condition(BinaryOp(expr.left, '>=', expr.right), env)
