"""
Axiom Programming Language (λx) - Z3 SMT Theorem Prover & Formal Verification Engine
"""
import sys
from typing import Dict, List, Optional, Tuple, Any
import z3

from axiom.ast_nodes import (
    Program, Stmt, Expr, Block, FunctionDecl, Param, FunctionContract,
    LetDecl, AssignStmt, IfStmt, WhileStmt, ForRangeStmt, ReturnStmt,
    PrintStmt, ExprStmt, VerifyStmt, BinaryOp, UnaryOp, NumberLiteral,
    StringLiteral, BooleanLiteral, Identifier, FunctionCall,
    ArrayLiteral, IndexAccess, StructInit, MemberAccess, CastExpr,
    MatchStmt, MatchExpr
)
from axiom.prover import ProofError, expr_to_str, function_has_loops, find_assigned_vars

def extract_all_loops(stmt: Any) -> List[Any]:
    loops = []
    if isinstance(stmt, (WhileStmt, ForRangeStmt)):
        loops.append(stmt)
    elif isinstance(stmt, Block):
        for s in stmt.statements:
            loops.extend(extract_all_loops(s))
    elif isinstance(stmt, IfStmt):
        loops.extend(extract_all_loops(stmt.then_branch))
        if stmt.else_branch:
            loops.extend(extract_all_loops(stmt.else_branch))
    elif isinstance(stmt, MatchStmt):
        for arm in stmt.arms:
            loops.extend(extract_all_loops(arm.body))
    return loops

class Z3ProofSummary:
    def __init__(self):
        self.verified_functions: int = 0
        self.verified_contracts: int = 0
        self.proved_theorems: int = 0
        self.safe_divisions: int = 0
        self.has_loops: bool = False
        self.loop_functions: List[str] = []
        self.status: str = "PROVED"
        self.details: List[str] = []

    def __repr__(self):
        return (f"<Z3ProofSummary: {self.verified_functions} funcs, "
                f"{self.verified_contracts} contracts, {self.proved_theorems} theorems>")

class ExecutionPath:
    def __init__(self, conditions: Optional[List[z3.ExprRef]] = None,
                 env: Optional[Dict[str, Any]] = None,
                 return_val: Optional[Any] = None,
                 has_returned: bool = False):
        self.conditions: List[z3.ExprRef] = list(conditions or [])
        self.env: Dict[str, Any] = dict(env or {})
        self.return_val: Optional[Any] = return_val
        self.has_returned: bool = has_returned

class Z3Prover:
    def __init__(self):
        self.functions: Dict[str, FunctionDecl] = {}
        self.summary = Z3ProofSummary()

    def create_z3_var(self, name: str, type_name: str) -> z3.ExprRef:
        if type_name == 'float':
            return z3.Real(name)
        elif type_name == 'bool':
            return z3.Bool(name)
        else:
            return z3.Int(name)

    def expr_to_z3(self, expr: Expr, env: Dict[str, Any], solver_for_checks: Optional[z3.Solver] = None,
                   path_conditions: Optional[List[z3.ExprRef]] = None) -> Any:
        if isinstance(expr, NumberLiteral):
            if expr.is_float or isinstance(expr.value, float):
                return z3.RealVal(float(expr.value))
            return z3.IntVal(int(expr.value))

        elif isinstance(expr, BooleanLiteral):
            return z3.BoolVal(bool(expr.value))

        elif isinstance(expr, StringLiteral):
            return z3.StringVal(str(expr.value))

        elif isinstance(expr, Identifier):
            if expr.name in env:
                return env[expr.name]
            # Unbound variable, default to int
            var = z3.Int(expr.name)
            env[expr.name] = var
            return var

        elif isinstance(expr, UnaryOp):
            operand = self.expr_to_z3(expr.operand, env, solver_for_checks, path_conditions)
            if expr.op == '-':
                return -operand
            elif expr.op in ('not', '!'):
                if z3.is_bool(operand):
                    return z3.Not(operand)
                return operand == 0
            raise ProofError(f"Desteklenmeyen tekil operator: {expr.op}", expr.line, expr.col)

        elif isinstance(expr, CastExpr):
            inner = self.expr_to_z3(expr.expr, env, solver_for_checks, path_conditions)
            if expr.target_type == 'float' and z3.is_int(inner):
                return z3.ToReal(inner)
            elif expr.target_type == 'int' and z3.is_real(inner):
                return z3.ToInt(inner)
            return inner

        elif isinstance(expr, BinaryOp):
            left = self.expr_to_z3(expr.left, env, solver_for_checks, path_conditions)
            right = self.expr_to_z3(expr.right, env, solver_for_checks, path_conditions)
            op = expr.op

            # Check division by zero if requested
            if op in ('/', '%') and solver_for_checks is not None:
                self._check_division_by_zero(right, solver_for_checks, path_conditions or [], expr)

            if op == '+':
                return left + right
            elif op == '-':
                return left - right
            elif op == '*':
                return left * right
            elif op == '/':
                return left / right
            elif op == '%':
                return left % right
            elif op in ('==', '==='):
                return left == right
            elif op in ('!=', '!=='):
                return left != right
            elif op == '<':
                return left < right
            elif op == '<=':
                return left <= right
            elif op == '>':
                return left > right
            elif op == '>=':
                return left >= right
            elif op in ('and', '&&'):
                b_left = left if z3.is_bool(left) else (left != 0)
                b_right = right if z3.is_bool(right) else (right != 0)
                return z3.And(b_left, b_right)
            elif op in ('or', '||'):
                b_left = left if z3.is_bool(left) else (left != 0)
                b_right = right if z3.is_bool(right) else (right != 0)
                return z3.Or(b_left, b_right)
            else:
                raise ProofError(f"Z3 ile desteklenmeyen ikili operator: {op}", expr.line, expr.col)

        elif isinstance(expr, FunctionCall):
            # Builtin math handling
            if expr.callee == 'math_abs' and len(expr.args) == 1:
                arg = self.expr_to_z3(expr.args[0], env, solver_for_checks, path_conditions)
                return z3.If(arg >= 0, arg, -arg)
            elif expr.callee == 'math_min' and len(expr.args) == 2:
                a1 = self.expr_to_z3(expr.args[0], env, solver_for_checks, path_conditions)
                a2 = self.expr_to_z3(expr.args[1], env, solver_for_checks, path_conditions)
                return z3.If(a1 <= a2, a1, a2)
            elif expr.callee == 'math_max' and len(expr.args) == 2:
                a1 = self.expr_to_z3(expr.args[0], env, solver_for_checks, path_conditions)
                a2 = self.expr_to_z3(expr.args[1], env, solver_for_checks, path_conditions)
                return z3.If(a1 >= a2, a1, a2)
            elif expr.callee == 'len' and len(expr.args) == 1:
                arg = expr.args[0]
                if isinstance(arg, ArrayLiteral):
                    return z3.IntVal(len(arg.elements))
                if isinstance(arg, Identifier) and f"len_{arg.name}" in env:
                    return env[f"len_{arg.name}"]
                res = z3.Int(f"len_{expr_to_str(arg)}")
                if path_conditions is not None:
                    path_conditions.append(res >= 0)
                elif solver_for_checks is not None:
                    solver_for_checks.add(res >= 0)
                return res
            elif expr.callee == 'simd_scan_match' and len(expr.args) == 2:
                arr_arg, target_arg = expr.args[0], expr.args[1]
                target_z3 = self.expr_to_z3(target_arg, env, solver_for_checks, path_conditions)
                elems = None
                if isinstance(arr_arg, Identifier) and f"elements_{arr_arg.name}" in env:
                    elems = env[f"elements_{arr_arg.name}"]
                elif isinstance(arr_arg, ArrayLiteral):
                    elems = [self.expr_to_z3(e, env, solver_for_checks, path_conditions) for e in arr_arg.elements]

                if elems is not None:
                    match_exprs = [z3.If(e == target_z3, z3.IntVal(1), z3.IntVal(0)) for e in elems]
                    if match_exprs:
                        return z3.Sum(*match_exprs) if len(match_exprs) > 1 else match_exprs[0]
                    return z3.IntVal(0)

                res = z3.Int(f"call_{expr.callee}_{expr.line}_{expr.col}")
                if path_conditions is not None:
                    path_conditions.append(res >= 0)
                elif solver_for_checks is not None:
                    solver_for_checks.add(res >= 0)
                return res

            elif expr.callee == 'simd_add_i64' and len(expr.args) == 2:
                a_arg, b_arg = expr.args[0], expr.args[1]
                elems_a = env.get(f"elements_{a_arg.name}") if isinstance(a_arg, Identifier) else None
                elems_b = env.get(f"elements_{b_arg.name}") if isinstance(b_arg, Identifier) else None
                if elems_a and elems_b:
                    min_len = min(len(elems_a), len(elems_b))
                    sum_elems = [elems_a[i] + elems_b[i] for i in range(min_len)]
                    ret_name = f"simd_res_{expr.line}_{expr.col}"
                    env[f"elements_{ret_name}"] = sum_elems
                    return z3.Int(ret_name)
                return z3.Int(f"call_{expr.callee}_{expr.line}_{expr.col}")

            elif expr.callee == 'simd_mul_i64' and len(expr.args) == 2:
                a_arg, b_arg = expr.args[0], expr.args[1]
                elems_a = env.get(f"elements_{a_arg.name}") if isinstance(a_arg, Identifier) else None
                elems_b = env.get(f"elements_{b_arg.name}") if isinstance(b_arg, Identifier) else None
                if elems_a and elems_b:
                    min_len = min(len(elems_a), len(elems_b))
                    mul_elems = [elems_a[i] * elems_b[i] for i in range(min_len)]
                    ret_name = f"simd_res_{expr.line}_{expr.col}"
                    env[f"elements_{ret_name}"] = mul_elems
                    return z3.Int(ret_name)
                return z3.Int(f"call_{expr.callee}_{expr.line}_{expr.col}")

            elif expr.callee == 'simd_sum_i64' and len(expr.args) == 1:
                arr_arg = expr.args[0]
                elems = None
                if isinstance(arr_arg, Identifier) and f"elements_{arr_arg.name}" in env:
                    elems = env[f"elements_{arr_arg.name}"]
                elif isinstance(arr_arg, FunctionCall):
                    callee_res = f"simd_res_{arr_arg.line}_{arr_arg.col}"
                    if f"elements_{callee_res}" in env:
                        elems = env[f"elements_{callee_res}"]

                if elems:
                    return z3.Sum(*elems) if len(elems) > 1 else elems[0]

                res = z3.Int(f"call_{expr.callee}_{expr.line}_{expr.col}")
                if path_conditions is not None:
                    path_conditions.append(res >= 0)
                elif solver_for_checks is not None:
                    solver_for_checks.add(res >= 0)
                return res
            elif expr.callee in self.functions:
                called_fn = self.functions[expr.callee]
                if solver_for_checks is not None:
                    self._check_call_contracts(called_fn, expr.args, env, solver_for_checks, path_conditions or [], expr)

                arg_vals = [self.expr_to_z3(a, env, solver_for_checks, path_conditions) for a in expr.args]
                call_env = {p.name: val for p, val in zip(called_fn.params, arg_vals)}

                # Propagate array info to call_env
                for p, a in zip(called_fn.params, expr.args):
                    if isinstance(a, Identifier) and f"len_{a.name}" in env:
                        call_env[f"len_{p.name}"] = env[f"len_{a.name}"]
                    elif isinstance(a, ArrayLiteral):
                        call_env[f"len_{p.name}"] = z3.IntVal(len(a.elements))
                    if isinstance(a, Identifier) and f"elements_{a.name}" in env:
                        call_env[f"elements_{p.name}"] = env[f"elements_{a.name}"]

                # If straight-line function (all lets, no branches):
                if all(isinstance(s, (LetDecl, ReturnStmt, ExprStmt)) for s in called_fn.body.statements):
                    sub_path = ExecutionPath(conditions=[], env=call_env, return_val=None, has_returned=False)
                    sub_paths = self._explore_paths(called_fn.body.statements, sub_path, solver_for_checks or z3.Solver(), called_fn)
                    if sub_paths and sub_paths[0].return_val is not None:
                        return sub_paths[0].return_val

                ret_name = f"call_{expr.callee}_{expr.line}_{expr.col}"
                ret_var = self.create_z3_var(ret_name, called_fn.return_type)
                if called_fn.contract and called_fn.contract.ensures and solver_for_checks is not None:
                    ens_env = dict(call_env)
                    ens_env['return'] = ret_var
                    for ens in called_fn.contract.ensures:
                        ens_z3 = self.expr_to_z3(ens, ens_env)
                        if z3.is_bool(ens_z3):
                            if path_conditions is not None:
                                path_conditions.append(ens_z3)
                            else:
                                solver_for_checks.add(ens_z3)
                return ret_var

            # Fallback fresh symbolic variable
            return z3.Int(f"call_{expr.callee}_{expr.line}_{expr.col}")

        elif isinstance(expr, IndexAccess):
            if isinstance(expr.array, Identifier) and isinstance(expr.index, NumberLiteral):
                idx = int(expr.index.value)
                if f"elements_{expr.array.name}" in env:
                    elems = env[f"elements_{expr.array.name}"]
                    if 0 <= idx < len(elems):
                        return elems[idx]
            return z3.Int(f"idx_{expr_to_str(expr.array)}_{expr.line}_{expr.col}")

        return z3.IntVal(0)

    def _check_division_by_zero(self, denom: Any, base_solver: z3.Solver,
                                path_conditions: List[z3.ExprRef], expr: Expr):
        s = z3.Solver()
        for a in base_solver.assertions():
            s.add(a)
        for pc in path_conditions:
            s.add(pc)
        s.add(denom == 0)

        if s.check() == z3.sat:
            m = s.model()
            ce_parts = [f"{d} = {m[d]}" for d in m.decls()]
            ce_str = ", ".join(ce_parts)
            raise ProofError(
                "Sıfıra bölme (division-by-zero) riski tespit edildi!",
                expr.line, expr.col,
                contract_expr=expr_to_str(expr),
                counterexample=ce_str
            )
        self.summary.safe_divisions += 1

    def _check_call_contracts(self, target_fn: FunctionDecl, args: List[Expr], env: Dict[str, Any],
                              base_solver: z3.Solver, path_conditions: List[z3.ExprRef], call_expr: Expr):
        if not target_fn.contract or not target_fn.contract.requires:
            return

        arg_vals = [self.expr_to_z3(a, env) for a in args]
        call_env: Dict[str, Any] = {}
        for p, aval in zip(target_fn.params, arg_vals):
            call_env[p.name] = aval
        for p, a in zip(target_fn.params, args):
            if isinstance(a, Identifier) and f"len_{a.name}" in env:
                call_env[f"len_{p.name}"] = env[f"len_{a.name}"]
            elif isinstance(a, ArrayLiteral):
                call_env[f"len_{p.name}"] = z3.IntVal(len(a.elements))
            if isinstance(a, Identifier) and f"elements_{a.name}" in env:
                call_env[f"elements_{p.name}"] = env[f"elements_{a.name}"]

        for req in target_fn.contract.requires:
            req_z3 = self.expr_to_z3(req, call_env)
            if not z3.is_bool(req_z3):
                req_z3 = (req_z3 != 0)

            s = z3.Solver()
            for a in base_solver.assertions():
                s.add(a)
            for pc in path_conditions:
                s.add(pc)
            s.add(z3.Not(req_z3))

            if s.check() == z3.sat:
                m = s.model()
                ce_parts = [f"{p.name} = {m.eval(call_env[p.name])}" for p in target_fn.params if p.name in call_env]
                ce_str = ", ".join(ce_parts)
                raise ProofError(
                    f"'{target_fn.name}' fonksiyon çağrısı ön koşulunu (requires) ihlal ediyor!",
                    call_expr.line, call_expr.col,
                    contract_expr=expr_to_str(req),
                    counterexample=ce_str
                )
            self.summary.verified_contracts += 1

    def _explore_paths(self, stmts: List[Stmt], path: ExecutionPath,
                       base_solver: z3.Solver, func: FunctionDecl) -> List[ExecutionPath]:
        if not stmts or path.has_returned:
            return [path]

        current_stmt = stmts[0]
        rest = stmts[1:]

        if isinstance(current_stmt, LetDecl):
            new_env = dict(path.env)
            if current_stmt.initializer:
                val = self.expr_to_z3(current_stmt.initializer, new_env, base_solver, path.conditions)
                new_env[current_stmt.name] = val
                if isinstance(current_stmt.initializer, ArrayLiteral):
                    elems = [self.expr_to_z3(e, new_env, base_solver, path.conditions) for e in current_stmt.initializer.elements]
                    new_env[f"elements_{current_stmt.name}"] = elems
                    new_env[f"len_{current_stmt.name}"] = z3.IntVal(len(elems))
                elif isinstance(current_stmt.initializer, FunctionCall):
                    ret_name = f"simd_res_{current_stmt.initializer.line}_{current_stmt.initializer.col}"
                    if f"elements_{ret_name}" in new_env:
                        new_env[f"elements_{current_stmt.name}"] = new_env[f"elements_{ret_name}"]
            else:
                new_env[current_stmt.name] = self.create_z3_var(current_stmt.name, current_stmt.type_annotation or 'int')
            new_path = ExecutionPath(path.conditions, new_env, path.return_val, path.has_returned)
            return self._explore_paths(rest, new_path, base_solver, func)

        elif isinstance(current_stmt, AssignStmt):
            new_env = dict(path.env)
            val = self.expr_to_z3(current_stmt.value, new_env, base_solver, path.conditions)
            new_env[current_stmt.name] = val
            new_path = ExecutionPath(path.conditions, new_env, path.return_val, path.has_returned)
            return self._explore_paths(rest, new_path, base_solver, func)

        elif isinstance(current_stmt, ReturnStmt):
            ret_val = None
            if current_stmt.value:
                ret_val = self.expr_to_z3(current_stmt.value, path.env, base_solver, path.conditions)
            new_path = ExecutionPath(path.conditions, path.env, ret_val, True)
            return [new_path]

        elif isinstance(current_stmt, VerifyStmt):
            cond_z3 = self.expr_to_z3(current_stmt.condition, path.env, base_solver, path.conditions)
            if not z3.is_bool(cond_z3):
                cond_z3 = (cond_z3 != 0)

            s = z3.Solver()
            for a in base_solver.assertions():
                s.add(a)
            for pc in path.conditions:
                s.add(pc)
            s.add(z3.Not(cond_z3))

            if s.check() == z3.sat:
                m = s.model()
                ce_parts = []
                for p in func.params:
                    if p.name in path.env:
                        ce_parts.append(f"{p.name} = {m.eval(path.env[p.name])}")
                ce_str = ", ".join(ce_parts)
                raise ProofError(
                    current_stmt.message or "Satır içi 'verify' doğrulaması başarısız oldu!",
                    current_stmt.line, current_stmt.col,
                    contract_expr=expr_to_str(current_stmt.condition),
                    counterexample=ce_str
                )
            self.summary.verified_contracts += 1
            return self._explore_paths(rest, path, base_solver, func)

        elif isinstance(current_stmt, IfStmt):
            cond_z3 = self.expr_to_z3(current_stmt.condition, path.env, base_solver, path.conditions)
            if not z3.is_bool(cond_z3):
                cond_z3 = (cond_z3 != 0)

            results: List[ExecutionPath] = []

            # Then branch
            then_conds = path.conditions + [cond_z3]
            then_path = ExecutionPath(then_conds, dict(path.env), path.return_val, path.has_returned)
            then_completed = self._explore_paths(current_stmt.then_branch.statements, then_path, base_solver, func)
            for p in then_completed:
                if p.has_returned:
                    results.append(p)
                else:
                    results.extend(self._explore_paths(rest, p, base_solver, func))

            # Else branch
            else_conds = path.conditions + [z3.Not(cond_z3)]
            else_path = ExecutionPath(else_conds, dict(path.env), path.return_val, path.has_returned)
            if current_stmt.else_branch:
                else_completed = self._explore_paths(current_stmt.else_branch.statements, else_path, base_solver, func)
                for p in else_completed:
                    if p.has_returned:
                        results.append(p)
                    else:
                        results.extend(self._explore_paths(rest, p, base_solver, func))
            else:
                results.extend(self._explore_paths(rest, else_path, base_solver, func))

            return results

        elif isinstance(current_stmt, (ExprStmt, PrintStmt)):
            if isinstance(current_stmt, ExprStmt):
                self.expr_to_z3(current_stmt.expr, path.env, base_solver, path.conditions)
            elif isinstance(current_stmt, PrintStmt):
                for e in getattr(current_stmt, 'args', getattr(current_stmt, 'exprs', [])):
                    self.expr_to_z3(e, path.env, base_solver, path.conditions)
            return self._explore_paths(rest, path, base_solver, func)

        return self._explore_paths(rest, path, base_solver, func)

    def _verify_function_with_loop_invariant(self, func: FunctionDecl, env: Dict[str, Any],
                                            param_vars: Dict[str, z3.ExprRef],
                                            preconditions: List[z3.ExprRef],
                                            precond_solver: z3.Solver):
        # Locate loop in top-level statements
        loop_idx = next(i for i, s in enumerate(func.body.statements) if isinstance(s, (WhileStmt, ForRangeStmt)))
        stmts_before = func.body.statements[:loop_idx]
        loop = func.body.statements[loop_idx]
        stmts_after = func.body.statements[loop_idx + 1:]

        # 1. Execute stmts_before symbolically
        initial_path = ExecutionPath(conditions=[], env=dict(env), return_val=None, has_returned=False)
        before_paths = self._explore_paths(stmts_before, initial_path, precond_solver, func)

        # For Range Stmt loop var init
        if isinstance(loop, ForRangeStmt):
            for bp in before_paths:
                start_val = self.expr_to_z3(loop.start, bp.env, precond_solver, bp.conditions)
                bp.env[loop.var_name] = start_val
            cond_expr = BinaryOp(left=Identifier(name=loop.var_name), op='<', right=loop.end)
            loop_body_stmts = loop.body.statements + [AssignStmt(name=loop.var_name, value=BinaryOp(left=Identifier(name=loop.var_name), op='+', right=NumberLiteral(value=1)))]
        else:
            cond_expr = loop.condition
            loop_body_stmts = loop.body.statements

        # Step 1: Base Case (Temel Adım)
        for bp in before_paths:
            for inv in loop.invariants:
                inv_z3 = self.expr_to_z3(inv, bp.env, precond_solver, bp.conditions)
                if not z3.is_bool(inv_z3):
                    inv_z3 = (inv_z3 != 0)

                s = z3.Solver()
                for pre in preconditions:
                    s.add(pre)
                for pc in bp.conditions:
                    s.add(pc)
                s.add(z3.Not(inv_z3))

                if s.check() == z3.sat:
                    m = s.model()
                    ce_parts = []
                    for p in func.params:
                        if p.name in param_vars:
                            ce_parts.append(f"{p.name} = {m.eval(param_vars[p.name])}")
                    for v_name, v_ref in bp.env.items():
                        if v_name not in param_vars and isinstance(v_ref, z3.ExprRef):
                            ce_parts.append(f"{v_name} = {m.eval(v_ref)}")
                    raise ProofError(
                        f"'{func.name}' fonksiyonu döngü invariantı temel adımda (döngü girişinde) sağlanamadı!",
                        loop.line, loop.col,
                        contract_expr=expr_to_str(inv),
                        counterexample=", ".join(ce_parts)
                    )
                self.summary.proved_theorems += 1

        # Step 2: Inductive Step (Tümevarım Adımı)
        modified_vars = find_assigned_vars(loop.body)
        if isinstance(loop, ForRangeStmt):
            modified_vars.add(loop.var_name)

        ind_env = dict(before_paths[0].env)
        for v in modified_vars:
            if v in ind_env and isinstance(ind_env[v], z3.ExprRef):
                sort = ind_env[v].sort()
                if sort == z3.RealSort():
                    ind_env[v] = z3.Real(f"{v}_ind")
                elif sort == z3.BoolSort():
                    ind_env[v] = z3.Bool(f"{v}_ind")
                else:
                    ind_env[v] = z3.Int(f"{v}_ind")
            else:
                ind_env[v] = z3.Int(f"{v}_ind")

        inv_terms = []
        for inv in loop.invariants:
            it = self.expr_to_z3(inv, ind_env, precond_solver)
            if not z3.is_bool(it):
                it = (it != 0)
            inv_terms.append(it)
        inv_before_z3 = z3.And(*inv_terms) if len(inv_terms) > 1 else inv_terms[0]

        cond_z3 = self.expr_to_z3(cond_expr, ind_env, precond_solver)
        if not z3.is_bool(cond_z3):
            cond_z3 = (cond_z3 != 0)

        ind_initial_path = ExecutionPath(conditions=[inv_before_z3, cond_z3], env=dict(ind_env), return_val=None, has_returned=False)
        body_paths = self._explore_paths(loop_body_stmts, ind_initial_path, precond_solver, func)

        for b_path in body_paths:
            for inv in loop.invariants:
                inv_after_z3 = self.expr_to_z3(inv, b_path.env, precond_solver, b_path.conditions)
                if not z3.is_bool(inv_after_z3):
                    inv_after_z3 = (inv_after_z3 != 0)

                s = z3.Solver()
                for pre in preconditions:
                    s.add(pre)
                for pc in b_path.conditions:
                    s.add(pc)
                s.add(z3.Not(inv_after_z3))

                if s.check() == z3.sat:
                    m = s.model()
                    ce_parts = []
                    for p in func.params:
                        if p.name in param_vars:
                            ce_parts.append(f"{p.name} = {m.eval(param_vars[p.name])}")
                    for v_name in modified_vars:
                        if v_name in ind_env and isinstance(ind_env[v_name], z3.ExprRef):
                            ce_parts.append(f"{v_name} = {m.eval(ind_env[v_name])}")
                    raise ProofError(
                        f"'{func.name}' fonksiyonu döngü invariantı tümevarım adımında (döngü gövdesi sonunda) korunamadı!",
                        loop.line, loop.col,
                        contract_expr=expr_to_str(inv),
                        counterexample=", ".join(ce_parts)
                    )
                self.summary.proved_theorems += 1

        # Step 3: Post-condition Step (Son Adım)
        exit_env = dict(ind_env)
        exit_inv_terms = []
        for inv in loop.invariants:
            it = self.expr_to_z3(inv, exit_env, precond_solver)
            if not z3.is_bool(it):
                it = (it != 0)
            exit_inv_terms.append(it)
        exit_inv_z3 = z3.And(*exit_inv_terms) if len(exit_inv_terms) > 1 else exit_inv_terms[0]

        exit_cond_z3 = self.expr_to_z3(cond_expr, exit_env, precond_solver)
        if not z3.is_bool(exit_cond_z3):
            exit_cond_z3 = (exit_cond_z3 != 0)

        exit_conditions = [exit_inv_z3, z3.Not(exit_cond_z3)]
        exit_initial_path = ExecutionPath(conditions=exit_conditions, env=dict(exit_env), return_val=None, has_returned=False)
        after_paths = self._explore_paths(stmts_after, exit_initial_path, precond_solver, func)

        if func.contract and func.contract.ensures:
            for ens in func.contract.ensures:
                for path in after_paths:
                    ens_env = dict(path.env)
                    if path.return_val is not None:
                        ens_env['return'] = path.return_val
                    elif 'return' not in ens_env:
                        ens_env['return'] = self.create_z3_var('return', func.return_type)

                    ens_z3 = self.expr_to_z3(ens, ens_env)
                    if not z3.is_bool(ens_z3):
                        ens_z3 = (ens_z3 != 0)

                    solver = z3.Solver()
                    for pre in preconditions:
                        solver.add(pre)
                    for pc in path.conditions:
                        solver.add(pc)
                    solver.add(z3.Not(ens_z3))

                    if solver.check() == z3.sat:
                        m = solver.model()
                        ce_parts = []
                        for p in func.params:
                            if p.name in param_vars:
                                ce_parts.append(f"{p.name} = {m.eval(param_vars[p.name])}")
                        for v_name in modified_vars:
                            if v_name in exit_env and isinstance(exit_env[v_name], z3.ExprRef):
                                ce_parts.append(f"{v_name} = {m.eval(exit_env[v_name])}")
                        if path.return_val is not None and isinstance(path.return_val, z3.ExprRef):
                            ce_parts.append(f"return = {m.eval(path.return_val)}")
                        raise ProofError(
                            f"'{func.name}' döngü sonrası fonksiyon son koşul sözleşmesi (ensures) ihlal edildi!",
                            func.line, func.col,
                            contract_expr=expr_to_str(ens),
                            counterexample=", ".join(ce_parts)
                        )
                    self.summary.proved_theorems += 1
                self.summary.verified_contracts += 1

        self.summary.details.append(f"'{func.name}' fonksiyonu döngü invariantı ile Floyd-Hoare tümevarımı üzerinden SESLİ VE KANITLANMIŞTIR (PROVEN).")
        self.summary.verified_functions += 1

    def verify_function(self, func: FunctionDecl):
        # 1. Initialize parameter variables in environment
        env: Dict[str, Any] = {}
        param_vars: Dict[str, z3.ExprRef] = {}
        for p in func.params:
            v = self.create_z3_var(p.name, p.type_name)
            env[p.name] = v
            param_vars[p.name] = v

        # 2. Build precondition solver
        precond_solver = z3.Solver()
        preconditions: List[z3.ExprRef] = []
        if func.contract and func.contract.requires:
            for req in func.contract.requires:
                r_z3 = self.expr_to_z3(req, env)
                if not z3.is_bool(r_z3):
                    r_z3 = (r_z3 != 0)
                preconditions.append(r_z3)
                precond_solver.add(r_z3)

        # Check if preconditions are self-consistent (satisfiable)
        if precond_solver.check() == z3.unsat:
            raise ProofError(
                f"'{func.name}' fonksiyonunun ön koşulları (requires) çelişkili (unsatisfiable)!",
                func.line, func.col
            )

        # Check for loops
        all_loops = extract_all_loops(func.body)
        if all_loops:
            has_unannotated_loop = any(len(loop.invariants) == 0 for loop in all_loops)
            if has_unannotated_loop:
                self.summary.has_loops = True
                if func.name not in self.summary.loop_functions:
                    self.summary.loop_functions.append(func.name)
                self.summary.status = "PARTIAL_VERIFICATION_UNKNOWN"
                self.summary.details.append(f"'{func.name}' fonksiyonu döngü (while/for) içerdiği için invariant olmaksızın kesin ispatlanamadı (UNKNOWN).")
                self.summary.verified_functions += 1
                return
            else:
                return self._verify_function_with_loop_invariant(func, env, param_vars, preconditions, precond_solver)

        # 3. Explore execution paths symbolically
        initial_path = ExecutionPath(conditions=[], env=env, return_val=None, has_returned=False)
        paths = self._explore_paths(func.body.statements, initial_path, precond_solver, func)

        # 4. Prove ensures (postconditions) for every path
        if func.contract and func.contract.ensures:
            for ens in func.contract.ensures:
                for path in paths:
                    ens_env = dict(path.env)
                    if path.return_val is not None:
                        ens_env['return'] = path.return_val
                    elif 'return' not in ens_env:
                        ens_env['return'] = self.create_z3_var('return', func.return_type)

                    ens_z3 = self.expr_to_z3(ens, ens_env)
                    if not z3.is_bool(ens_z3):
                        ens_z3 = (ens_z3 != 0)

                    solver = z3.Solver()
                    for pre in preconditions:
                        solver.add(pre)
                    for pc in path.conditions:
                        solver.add(pc)

                    # Theorem: (Preconditions and PathConditions) => ensures
                    # Disprove by asserting negation of ensures
                    solver.add(z3.Not(ens_z3))

                    res = solver.check()
                    if res == z3.sat:
                        model = solver.model()
                        ce_parts = []
                        for p in func.params:
                            if p.name in param_vars:
                                ce_parts.append(f"{p.name} = {model.eval(param_vars[p.name])}")
                        if path.return_val is not None:
                            ce_parts.append(f"return = {model.eval(path.return_val)}")
                        ce_str = ", ".join(ce_parts)

                        raise ProofError(
                            f"'{func.name}' fonksiyonunun son koşul sözleşmesi (ensures) ihlal edildi!",
                            func.line, func.col,
                            contract_expr=expr_to_str(ens),
                            counterexample=ce_str
                        )

                    self.summary.proved_theorems += 1
                self.summary.verified_contracts += 1

        self.summary.verified_functions += 1

    def verify_program(self, program: Program) -> Z3ProofSummary:
        # Index all functions
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                if len(getattr(decl, 'type_params', [])) > 0:
                    continue
                self.functions[decl.name] = decl

        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                if len(getattr(decl, 'type_params', [])) > 0:
                    continue
                self.verify_function(decl)

        return self.summary

    def emit_smt2(self, program: Program) -> str:
        """
        Export complete verification conditions in standard SMT-LIB2 format.
        """
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                self.functions[decl.name] = decl

        solver = z3.Solver()
        solver.set("smt.mbqi", True)

        for decl in program.declarations:
            if not isinstance(decl, FunctionDecl):
                continue
            func = decl
            env: Dict[str, Any] = {}
            for p in func.params:
                env[p.name] = self.create_z3_var(p.name, p.type_name)

            preconditions = []
            if func.contract and func.contract.requires:
                for req in func.contract.requires:
                    r_z3 = self.expr_to_z3(req, env)
                    if not z3.is_bool(r_z3):
                        r_z3 = (r_z3 != 0)
                    preconditions.append(r_z3)

            initial_path = ExecutionPath(conditions=[], env=env, return_val=None, has_returned=False)
            dummy_s = z3.Solver()
            for pre in preconditions:
                dummy_s.add(pre)
            paths = self._explore_paths(func.body.statements, initial_path, dummy_s, func)

            if func.contract and func.contract.ensures:
                for ens in func.contract.ensures:
                    for path in paths:
                        ens_env = dict(path.env)
                        if path.return_val is not None:
                            ens_env['return'] = path.return_val
                        elif 'return' not in ens_env:
                            ens_env['return'] = self.create_z3_var(f"ret_{func.name}", func.return_type)

                        ens_z3 = self.expr_to_z3(ens, ens_env)
                        if not z3.is_bool(ens_z3):
                            ens_z3 = (ens_z3 != 0)

                        antecedent_terms = preconditions + path.conditions
                        if antecedent_terms:
                            antecedent = z3.And(*antecedent_terms) if len(antecedent_terms) > 1 else antecedent_terms[0]
                            theorem = z3.Implies(antecedent, ens_z3)
                        else:
                            theorem = ens_z3

                        solver.add(theorem)

        smt2_str = solver.to_smt2()
        header = [
            "; ===================================================================",
            "; Axiom (λx) Standard SMT-LIB2 Verification Benchmark",
            "; Generated by Axiom Z3 SMT Theorem Prover",
            "; ===================================================================",
            "(set-logic ALL)",
            "(set-info :source |Axiom Formal Verification Engine|)",
            ""
        ]
        return "\n".join(header) + "\n" + smt2_str + "\n(check-sat)\n"
