"""
Axiom Programming Language (λx) - Parser
"""
from typing import List, Optional
from axiom.lexer import Token
from axiom.ast_nodes import (
    Program, Stmt, Expr, Block, FunctionDecl, Param, FunctionContract,
    LetDecl, AssignStmt, IfStmt, WhileStmt, ForRangeStmt, ForStmt, ReturnStmt,
    PrintStmt, ExprStmt, VerifyStmt, BreakStmt, ContinueStmt, DeferStmt, BinaryOp, UnaryOp, NumberLiteral, TryExpr,
    StringLiteral, BooleanLiteral, Identifier, FunctionCall, RangeExpr,
    StructDecl, StructField, StructInit, StructFieldInit, MemberAccess,
    ArrayLiteral, IndexAccess, ImportStmt, CastExpr,
    MatchStmt, MatchExpr, MatchArm, Pattern, WildcardPattern, LiteralPattern, IdentPattern
)

class ParserError(Exception):
    def __init__(self, message: str, token: Token):
        super().__init__(f"Axiom Parse Hatasi [Satir {token.line}, Sutun {token.col}]: {message} (Mevcut token: {token.type} '{token.value}')")
        self.token = token

class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.depth = 0

    def current_token(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]

    def peek_token(self, offset: int = 1) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]

    def match(self, *expected_types: str) -> bool:
        return self.current_token().type in expected_types

    def consume(self, expected_type: str, err_msg: Optional[str] = None) -> Token:
        tok = self.current_token()
        if tok.type != expected_type:
            msg = err_msg or f"'{expected_type}' bekleniyordu fakat '{tok.type}' bulundu."
            raise ParserError(msg, tok)
        self.pos += 1
        return tok

    def optional_consume(self, expected_type: str) -> Optional[Token]:
        if self.match(expected_type):
            tok = self.current_token()
            self.pos += 1
            return tok
        return None

    # --- Type Parsing ---

    def parse_type(self) -> str:
        if self.match('TYPE'):
            base_type = self.consume('TYPE').value
        elif self.match('IDENT'):
            base_type = self.consume('IDENT').value
        else:
            tok = self.current_token()
            raise ParserError(f"Tip belirtimi (int, float, bool, str, void veya struct) bekleniyordu, '{tok.type}' bulundu.", tok)

        if self.match('LT'):
            self.consume('LT')
            type_args = []
            while True:
                type_args.append(self.parse_type())
                if self.optional_consume('COMMA'):
                    continue
                break
            self.consume('GT', "Kapatma '>' bekleniyordu.")
            base_type = f"{base_type}<{', '.join(type_args)}>"

        while self.match('LBRACKET') and self.peek_token().type == 'RBRACKET':
            self.consume('LBRACKET')
            self.consume('RBRACKET')
            base_type += "[]"

        return base_type

    # --- Entry point ---

    def _collect_docs(self) -> List[str]:
        """Ardisik DOC token'larini toplar (bos satir ayirir)."""
        docs: List[str] = []
        while self.match('DOC'):
            docs.append(self.consume('DOC').value)
        return docs

    def parse(self) -> Program:
        declarations: List[Stmt] = []
        while not self.match('EOF'):
            pending_docs = self._collect_docs()
            if self.match('EOF'):
                break

            if self.match('AT'):
                self.consume('AT')
                tag = self.consume('IDENT', "Dekorator etiketi bekleniyordu (ornek: @simd).").value
                is_simd = (tag == 'simd')
                fn_decl = self.parse_function_decl(is_simd=is_simd)
                fn_decl.doc = pending_docs
                declarations.append(fn_decl)
            elif self.match('IMPORT'):
                declarations.append(self.parse_import_stmt())
            elif self.match('STRUCT'):
                decl = self.parse_struct_decl()
                decl.doc = pending_docs
                declarations.append(decl)
            elif self.match('FN'):
                decl = self.parse_function_decl()
                decl.doc = pending_docs
                declarations.append(decl)
            else:
                declarations.append(self.parse_statement())
        return Program(declarations=declarations)

    def parse_import_stmt(self) -> ImportStmt:
        tok = self.consume('IMPORT')
        path_tok = self.consume('STRING', "İçe aktarılacak dosya yolu (string literal) bekleniyordu.")
        self.optional_consume('SEMICOLON')
        return ImportStmt(path=path_tok.value, line=tok.line, col=tok.col)

    # --- Struct Declarations ---

    def parse_struct_decl(self) -> StructDecl:
        tok = self.consume('STRUCT')
        name = self.consume('IDENT', "Struct adi (identifier) bekleniyordu.").value
        type_params: List[str] = []
        if self.match('LT'):
            self.consume('LT')
            while True:
                p_tok = self.consume('IDENT', "Tip parametresi (ornek: T) bekleniyordu.")
                type_params.append(p_tok.value)
                if self.optional_consume('COMMA'):
                    continue
                break
            self.consume('GT', "Tip parametreleri sonu '>' bekleniyordu.")

        self.consume('LBRACE', "'{' bekleniyordu.")
        fields: List[StructField] = []
        if not self.match('RBRACE'):
            while True:
                f_tok = self.consume('IDENT', "Alan adi bekleniyordu.")
                self.consume('COLON', "':' bekleniyordu.")
                f_type = self.parse_type()
                fields.append(StructField(name=f_tok.value, type_name=f_type, line=f_tok.line, col=f_tok.col))
                if self.optional_consume('COMMA'):
                    if self.match('RBRACE'):
                        break
                    continue
                break
        self.consume('RBRACE', "'}' bekleniyordu.")
        self.optional_consume('SEMICOLON')
        return StructDecl(name=name, fields=fields, type_params=type_params, line=tok.line, col=tok.col)

    # --- Functions and Contracts ---

    def parse_function_decl(self, is_simd: bool = False) -> FunctionDecl:
        fn_tok = self.consume('FN')
        name_tok = self.consume('IDENT', "Fonksiyon adi (identifier) bekleniyordu.")
        type_params: List[str] = []
        if self.match('LT'):
            self.consume('LT')
            while True:
                p_tok = self.consume('IDENT', "Tip parametresi (ornek: T) bekleniyordu.")
                type_params.append(p_tok.value)
                if self.optional_consume('COMMA'):
                    continue
                break
            self.consume('GT', "Tip parametreleri sonu '>' bekleniyordu.")

        self.consume('LPAREN', "'(' bekleniyordu.")

        params: List[Param] = []
        if not self.match('RPAREN'):
            while True:
                p_name = self.consume('IDENT', "Parametre adi bekleniyordu.").value
                p_type = "int"
                if self.optional_consume('COLON'):
                    p_type = self.parse_type()
                params.append(Param(name=p_name, type_name=p_type, line=fn_tok.line, col=fn_tok.col))
                if self.optional_consume('COMMA'):
                    continue
                break
        self.consume('RPAREN', "')' bekleniyordu.")

        return_type = "void"
        if self.optional_consume('ARROW'):
            return_type = self.parse_type()

        # Parse contracts: requires & ensures
        contract = FunctionContract()
        while self.match('REQUIRES', 'ENSURES'):
            if self.match('REQUIRES'):
                self.consume('REQUIRES')
                req_expr = self.parse_expression()
                contract.requires.append(req_expr)
            elif self.match('ENSURES'):
                self.consume('ENSURES')
                ens_expr = self.parse_expression()
                contract.ensures.append(ens_expr)

        body = self.parse_block()
        return FunctionDecl(
            name=name_tok.value,
            params=params,
            return_type=return_type,
            contract=contract,
            body=body,
            line=fn_tok.line,
            col=fn_tok.col,
            is_simd=is_simd,
            type_params=type_params
        )

    def parse_block(self) -> Block:
        tok = self.consume('LBRACE', "'{' blok baslangici bekleniyordu.")
        stmts: List[Stmt] = []
        while not self.match('RBRACE', 'EOF'):
            stmts.append(self.parse_statement())
        self.consume('RBRACE', "'}' blok sonlandiricisi bekleniyordu.")
        return Block(statements=stmts, line=tok.line, col=tok.col)

    # --- Statements ---

    def parse_statement(self) -> Stmt:
        self.depth += 1
        if self.depth > 40:
            tok = self.current_token()
            raise ParserError("Maksimum blok / ifade derinligi asildi (Stack overflow korumasi)", tok)
        try:
            return self._parse_statement_inner()
        finally:
            self.depth -= 1

    def _parse_statement_inner(self) -> Stmt:
        # Blok icindeki doc/free yorumlari deyim olarak yok sayilir.
        while self.match('DOC'):
            self.consume('DOC')

        tok = self.current_token()

        if self.match('LBRACE'):
            return self.parse_block()
        elif self.match('IMPORT'):
            return self.parse_import_stmt()
        elif self.match('STRUCT'):
            return self.parse_struct_decl()
        elif self.match('LET'):
            return self.parse_let_decl()
        elif self.match('IF'):
            return self.parse_if_stmt()
        elif self.match('WHILE'):
            return self.parse_while_stmt()
        elif self.match('FOR'):
            return self.parse_for_stmt()
        elif self.match('RETURN'):
            return self.parse_return_stmt()
        elif self.match('DEFER'):
            return self.parse_defer_stmt()
        elif self.match('PRINT'):
            return self.parse_print_stmt()
        elif self.match('VERIFY'):
            return self.parse_verify_stmt()
        elif self.match('MATCH'):
            return self.parse_match_stmt()
        elif self.match('BREAK'):
            tok = self.consume('BREAK')
            self.optional_consume('SEMICOLON')
            return BreakStmt(line=tok.line, col=tok.col)
        elif self.match('CONTINUE'):
            tok = self.consume('CONTINUE')
            self.optional_consume('SEMICOLON')
            return ContinueStmt(line=tok.line, col=tok.col)
        else:
            expr = self.parse_expression()
            if self.match('ASSIGN'):
                self.consume('ASSIGN')
                val = self.parse_expression()
                self.optional_consume('SEMICOLON')
                name = expr.name if isinstance(expr, Identifier) else ""
                return AssignStmt(name=name, value=val, target=expr, line=tok.line, col=tok.col)
            self.optional_consume('SEMICOLON')
            return ExprStmt(expr=expr, line=tok.line, col=tok.col)

    def parse_let_decl(self) -> LetDecl:
        tok = self.consume('LET')
        is_mut = False
        if self.match('MUT'):
            self.consume('MUT')
            is_mut = True

        name = self.consume('IDENT', "Degisken ismi bekleniyordu.").value
        type_annot = None
        if self.optional_consume('COLON'):
            type_annot = self.parse_type()

        init = None
        if self.optional_consume('ASSIGN'):
            init = self.parse_expression()

        self.optional_consume('SEMICOLON')
        return LetDecl(name=name, is_mut=is_mut, type_annotation=type_annot, initializer=init, line=tok.line, col=tok.col)

    def parse_if_stmt(self) -> IfStmt:
        tok = self.consume('IF')
        cond = self.parse_expression()
        then_b = self.parse_block()
        else_b = None
        if self.match('ELSE'):
            self.consume('ELSE')
            if self.match('IF'):
                else_if_stmt = self.parse_if_stmt()
                else_b = Block(statements=[else_if_stmt], line=else_if_stmt.line, col=else_if_stmt.col)
            else:
                else_b = self.parse_block()
        return IfStmt(condition=cond, then_branch=then_b, else_branch=else_b, line=tok.line, col=tok.col)

    def parse_while_stmt(self) -> WhileStmt:
        tok = self.consume('WHILE')
        cond = self.parse_expression()
        invariants = []
        while self.match('INVARIANT'):
            self.consume('INVARIANT')
            invariants.append(self.parse_expression())
            self.optional_consume('SEMICOLON')
        body = self.parse_block()
        return WhileStmt(condition=cond, body=body, invariants=invariants, line=tok.line, col=tok.col)

    def parse_for_stmt(self) -> ForRangeStmt:
        tok = self.consume('FOR')
        var_name = self.consume('IDENT', "Dongu degiskeni bekleniyordu.").value
        self.consume('IN', "'in' anahtar kelimesi bekleniyordu.")
        start_expr = self.parse_expression()
        self.consume('DOTDOT', "Aralik belirteci ('..') bekleniyordu.")
        end_expr = self.parse_expression()
        invariants = []
        while self.match('INVARIANT'):
            self.consume('INVARIANT')
            invariants.append(self.parse_expression())
            self.optional_consume('SEMICOLON')
        body = self.parse_block()
        return ForRangeStmt(var_name=var_name, start=start_expr, end=end_expr, body=body, invariants=invariants, line=tok.line, col=tok.col)

    def parse_return_stmt(self) -> ReturnStmt:
        tok = self.consume('RETURN')
        val = None
        if not self.match('SEMICOLON', 'RBRACE', 'EOF'):
            val = self.parse_expression()
        self.optional_consume('SEMICOLON')
        return ReturnStmt(value=val, line=tok.line, col=tok.col)

    def parse_defer_stmt(self) -> DeferStmt:
        tok = self.consume('DEFER')
        if self.match('LBRACE'):
            stmt = self.parse_block()
            self.optional_consume('SEMICOLON')
        else:
            stmt = self.parse_statement()
        return DeferStmt(stmt=stmt, line=tok.line, col=tok.col)

    def parse_print_stmt(self) -> PrintStmt:
        tok = self.consume('PRINT')
        self.consume('LPAREN')
        args = []
        if not self.match('RPAREN'):
            while True:
                args.append(self.parse_expression())
                if self.optional_consume('COMMA'):
                    continue
                break
        self.consume('RPAREN')
        self.optional_consume('SEMICOLON')
        return PrintStmt(args=args, line=tok.line, col=tok.col)

    def parse_verify_stmt(self) -> VerifyStmt:
        tok = self.consume('VERIFY')
        cond = self.parse_expression()
        msg = None
        if self.optional_consume('COMMA'):
            msg_tok = self.consume('STRING', "Dogrulama hata mesaji bir string olmalidir.")
            msg = msg_tok.value
        self.optional_consume('SEMICOLON')
        return VerifyStmt(condition=cond, message=msg, line=tok.line, col=tok.col)

    # --- Expressions (Precedence Climbing) ---

    def parse_expression(self) -> Expr:
        self.depth += 1
        if self.depth > 40:
            tok = self.current_token()
            raise ParserError("Maksimum AST / ifade derinligi asildi (Stack overflow korumasi)", tok)
        try:
            return self.parse_logical_or()
        finally:
            self.depth -= 1

    def parse_logical_or(self) -> Expr:
        expr = self.parse_logical_and()
        while self.match('OR'):
            op_tok = self.consume('OR')
            right = self.parse_logical_and()
            expr = BinaryOp(left=expr, op='or', right=right, line=op_tok.line, col=op_tok.col)
        return expr

    def parse_logical_and(self) -> Expr:
        expr = self.parse_equality()
        while self.match('AND'):
            op_tok = self.consume('AND')
            right = self.parse_equality()
            expr = BinaryOp(left=expr, op='and', right=right, line=op_tok.line, col=op_tok.col)
        return expr

    def parse_equality(self) -> Expr:
        expr = self.parse_comparison()
        while self.match('EQEQ', 'NOTEQ'):
            op_tok = self.current_token()
            self.pos += 1
            right = self.parse_comparison()
            expr = BinaryOp(left=expr, op=op_tok.value, right=right, line=op_tok.line, col=op_tok.col)
        return expr

    def parse_comparison(self) -> Expr:
        expr = self.parse_term()
        while self.match('LT', 'LTEQ', 'GT', 'GTEQ'):
            op_tok = self.current_token()
            self.pos += 1
            right = self.parse_term()
            expr = BinaryOp(left=expr, op=op_tok.value, right=right, line=op_tok.line, col=op_tok.col)
        return expr

    def parse_term(self) -> Expr:
        expr = self.parse_factor()
        while self.match('PLUS', 'MINUS'):
            op_tok = self.current_token()
            self.pos += 1
            right = self.parse_factor()
            expr = BinaryOp(left=expr, op=op_tok.value, right=right, line=op_tok.line, col=op_tok.col)
        return expr

    def parse_factor(self) -> Expr:
        expr = self.parse_unary()
        while self.match('STAR', 'SLASH', 'PERCENT'):
            op_tok = self.current_token()
            self.pos += 1
            right = self.parse_unary()
            expr = BinaryOp(left=expr, op=op_tok.value, right=right, line=op_tok.line, col=op_tok.col)
        return expr

    def parse_unary(self) -> Expr:
        if self.match('NOT', 'MINUS', 'PLUS'):
            op_tok = self.current_token()
            self.pos += 1
            operand = self.parse_unary()
            return UnaryOp(op=op_tok.value, operand=operand, line=op_tok.line, col=op_tok.col)
        return self.parse_cast()

    def parse_cast(self) -> Expr:
        expr = self.parse_postfix()
        while self.match('AS'):
            as_tok = self.consume('AS')
            target_type = self.parse_type()
            expr = CastExpr(expr=expr, target_type=target_type, line=as_tok.line, col=as_tok.col)
        return expr

    def parse_postfix(self) -> Expr:
        expr = self.parse_primary()
        while True:
            if self.match('DOT'):
                dot_tok = self.consume('DOT')
                member_tok = self.consume('IDENT', "Alan ismi bekleniyordu.")
                expr = MemberAccess(object=expr, member=member_tok.value, line=dot_tok.line, col=dot_tok.col)
            elif self.match('LBRACKET'):
                lb_tok = self.consume('LBRACKET')
                idx_expr = self.parse_expression()
                self.consume('RBRACKET', "Kapatma koseli parantezi ']' bekleniyordu.")
                expr = IndexAccess(array=expr, index=idx_expr, line=lb_tok.line, col=lb_tok.col)
            elif self.match('QUESTION'):
                q_tok = self.consume('QUESTION')
                expr = TryExpr(expr=expr, line=q_tok.line, col=q_tok.col)
            else:
                break
        return expr

    def _is_generic_instantiation(self) -> bool:
        if not (self.match('IDENT') and self.peek_token(1).type == 'LT'):
            return False
        idx = self.pos + 2
        depth = 1
        n = len(self.tokens)
        while idx < n and depth > 0:
            ttype = self.tokens[idx].type
            if ttype == 'LT':
                depth += 1
            elif ttype == 'GT':
                depth -= 1
            elif ttype in ('SEMICOLON', 'LBRACE', 'RBRACE', 'RPAREN', 'ASSIGN'):
                return False
            idx += 1
        if depth == 0 and idx < n:
            next_type = self.tokens[idx].type
            if next_type in ('LPAREN', 'LBRACE'):
                return True
        return False

    def parse_match_pattern(self) -> Pattern:
        tok = self.current_token()
        if self.match('UNDERSCORE') or (self.match('IDENT') and tok.value == '_'):
            self.consume(tok.type)
            return WildcardPattern(line=tok.line, col=tok.col)

        if self.match('MINUS') and self.peek_token(1).type in ('INT', 'FLOAT'):
            minus_tok = self.consume('MINUS')
            num_tok = self.consume(self.current_token().type)
            val = -float(num_tok.value) if num_tok.type == 'FLOAT' else -int(num_tok.value)
            lit = NumberLiteral(value=val, is_float=(num_tok.type == 'FLOAT'), line=minus_tok.line, col=minus_tok.col)
            return LiteralPattern(literal=lit, line=minus_tok.line, col=minus_tok.col)

        if self.match('INT'):
            num_tok = self.consume('INT')
            lit = NumberLiteral(value=int(num_tok.value), is_float=False, line=num_tok.line, col=num_tok.col)
            return LiteralPattern(literal=lit, line=tok.line, col=tok.col)

        if self.match('FLOAT'):
            num_tok = self.consume('FLOAT')
            lit = NumberLiteral(value=float(num_tok.value), is_float=True, line=num_tok.line, col=num_tok.col)
            return LiteralPattern(literal=lit, line=tok.line, col=tok.col)

        if self.match('STRING'):
            str_tok = self.consume('STRING')
            lit = StringLiteral(value=str_tok.value, line=str_tok.line, col=str_tok.col)
            return LiteralPattern(literal=lit, line=tok.line, col=tok.col)

        if self.match('TRUE'):
            b_tok = self.consume('TRUE')
            lit = BooleanLiteral(value=True, line=b_tok.line, col=b_tok.col)
            return LiteralPattern(literal=lit, line=tok.line, col=tok.col)

        if self.match('FALSE'):
            b_tok = self.consume('FALSE')
            lit = BooleanLiteral(value=False, line=b_tok.line, col=b_tok.col)
            return LiteralPattern(literal=lit, line=tok.line, col=tok.col)

        if self.match('IDENT'):
            id_tok = self.consume('IDENT')
            return IdentPattern(name=id_tok.value, line=id_tok.line, col=id_tok.col)

        raise ParserError(f"Gecersiz match deseni: {tok.type} '{tok.value}'", tok)

    def parse_match_arm(self, is_expr: bool = False) -> MatchArm:
        pat = self.parse_match_pattern()
        guard = None
        if self.match('IF'):
            self.consume('IF')
            guard = self.parse_expression()
        self.consume('FAT_ARROW', "Örüntü kolunda '=>' bekleniyordu.")
        if self.match('LBRACE'):
            body = self.parse_block()
        else:
            body = self.parse_expression()
        self.optional_consume('COMMA')
        self.optional_consume('SEMICOLON')
        return MatchArm(pattern=pat, guard=guard, body=body, line=pat.line, col=pat.col)

    def parse_match_stmt(self) -> MatchStmt:
        tok = self.consume('MATCH')
        subject = self.parse_expression()
        self.consume('LBRACE', "match sonrasi '{' bekleniyordu.")
        arms: List[MatchArm] = []
        while not self.match('RBRACE', 'EOF'):
            arms.append(self.parse_match_arm(is_expr=False))
        self.consume('RBRACE', "match sonlandirici '}' bekleniyordu.")
        self.optional_consume('SEMICOLON')
        return MatchStmt(subject=subject, arms=arms, line=tok.line, col=tok.col)

    def parse_match_expr(self) -> MatchExpr:
        tok = self.consume('MATCH')
        subject = self.parse_expression()
        self.consume('LBRACE', "match sonrasi '{' bekleniyordu.")
        arms: List[MatchArm] = []
        while not self.match('RBRACE', 'EOF'):
            arms.append(self.parse_match_arm(is_expr=True))
        self.consume('RBRACE', "match sonlandirici '}' bekleniyordu.")
        return MatchExpr(subject=subject, arms=arms, line=tok.line, col=tok.col)

    def parse_primary(self) -> Expr:
        tok = self.current_token()

        if self.match('MATCH'):
            return self.parse_match_expr()

        if self._is_generic_instantiation():
            tok = self.consume('IDENT')
            tok_val = tok.value
            self.consume('LT')
            type_args = []
            while True:
                type_args.append(self.parse_type())
                if self.optional_consume('COMMA'):
                    continue
                break
            self.consume('GT', "Tip argumanlari sonlandirici '>' bekleniyordu.")

            if self.match('LPAREN'):
                self.consume('LPAREN')
                args = []
                if not self.match('RPAREN'):
                    while True:
                        args.append(self.parse_expression())
                        if self.optional_consume('COMMA'):
                            continue
                        break
                self.consume('RPAREN')
                return FunctionCall(callee=tok_val, args=args, type_args=type_args, line=tok.line, col=tok.col)

            if self.match('LBRACE'):
                self.consume('LBRACE')
                field_inits = []
                if not self.match('RBRACE'):
                    while True:
                        f_name = self.consume('IDENT', "Alan adi bekleniyordu.").value
                        self.consume('COLON', "':' bekleniyordu.")
                        f_val = self.parse_expression()
                        field_inits.append(StructFieldInit(field_name=f_name, value=f_val, line=tok.line, col=tok.col))
                        if self.optional_consume('COMMA'):
                            if self.match('RBRACE'):
                                break
                            continue
                        break
                self.consume('RBRACE', "'}' bekleniyordu.")
                return StructInit(struct_name=tok_val, fields=field_inits, type_args=type_args, line=tok.line, col=tok.col)

        if self.match('INT'):
            self.consume('INT')
            return NumberLiteral(value=int(tok.value), is_float=False, line=tok.line, col=tok.col)

        if self.match('FLOAT'):
            self.consume('FLOAT')
            return NumberLiteral(value=float(tok.value), is_float=True, line=tok.line, col=tok.col)

        if self.match('STRING'):
            self.consume('STRING')
            return StringLiteral(value=tok.value, line=tok.line, col=tok.col)

        if self.match('TRUE'):
            self.consume('TRUE')
            return BooleanLiteral(value=True, line=tok.line, col=tok.col)

        if self.match('FALSE'):
            self.consume('FALSE')
            return BooleanLiteral(value=False, line=tok.line, col=tok.col)

        if self.match('LBRACKET'):
            self.consume('LBRACKET')
            elements = []
            if not self.match('RBRACKET'):
                while True:
                    elements.append(self.parse_expression())
                    if self.optional_consume('COMMA'):
                        if self.match('RBRACE') or self.match('RBRACKET'):
                            break
                        continue
                    break
            self.consume('RBRACKET', "Kapatma koseli parantezi ']' bekleniyordu.")
            return ArrayLiteral(elements=elements, line=tok.line, col=tok.col)

        if self.match('IDENT') or self.match('RETURN'):
            is_ret = self.match('RETURN')
            tok_val = self.consume(self.current_token().type).value

            # Check for FunctionCall
            if not is_ret and self.match('LPAREN'):
                self.consume('LPAREN')
                args = []
                if not self.match('RPAREN'):
                    while True:
                        args.append(self.parse_expression())
                        if self.optional_consume('COMMA'):
                            continue
                        break
                self.consume('RPAREN')
                return FunctionCall(callee=tok_val, args=args, line=tok.line, col=tok.col)

            # Check for StructInit: Point { x: 10, y: 20 }
            if not is_ret and self.match('LBRACE'):
                is_struct_init = False
                next_tok = self.peek_token(1)
                if next_tok.type == 'RBRACE':
                    is_struct_init = True
                elif next_tok.type == 'IDENT' and self.peek_token(2).type == 'COLON':
                    is_struct_init = True

                if is_struct_init:
                    self.consume('LBRACE')
                    field_inits = []
                    if not self.match('RBRACE'):
                        while True:
                            f_name = self.consume('IDENT', "Alan adi bekleniyordu.").value
                            self.consume('COLON', "':' bekleniyordu.")
                            f_val = self.parse_expression()
                            field_inits.append(StructFieldInit(field_name=f_name, value=f_val, line=tok.line, col=tok.col))
                            if self.optional_consume('COMMA'):
                                if self.match('RBRACE'):
                                    break
                                continue
                            break
                    self.consume('RBRACE', "'}' bekleniyordu.")
                    return StructInit(struct_name=tok_val, fields=field_inits, line=tok.line, col=tok.col)

            return Identifier(name=tok_val, line=tok.line, col=tok.col)

        if self.match('LPAREN'):
            self.consume('LPAREN')
            expr = self.parse_expression()
            self.consume('RPAREN', "Kapatma parantezi ')' bekleniyordu.")
            return expr

        raise ParserError("Beklenmeyen ifade (expression)", tok)
