"""
Axiom Programming Language (λx) - LLVM IR Direct Code Generator
"""
import sys
import re
from typing import Dict, List, Optional, Tuple, Any
from axiom.ast_nodes import (
    Program, Stmt, Expr, Block, FunctionDecl, Param, FunctionContract,
    LetDecl, AssignStmt, IfStmt, WhileStmt, ForRangeStmt, ReturnStmt,
    PrintStmt, ExprStmt, VerifyStmt, BinaryOp, UnaryOp, NumberLiteral, TryExpr, DeferStmt,
    BreakStmt, ContinueStmt,
    StringLiteral, BooleanLiteral, Identifier, FunctionCall,
    StructDecl, StructField, StructInit, StructFieldInit, MemberAccess,
    ArrayLiteral, IndexAccess, ImportStmt, CastExpr,
    MatchStmt, MatchExpr, MatchArm, Pattern, WildcardPattern, LiteralPattern, IdentPattern
)

LLVM_TYPE_MAP = {
    'int': 'i64',
    'float': 'double',
    'bool': 'i1',
    'str': 'i8*',
    'void': 'void',
}

def mangle_type_name(t: str) -> str:
    if not t or '<' not in t:
        return t
    if t.endswith('[]'):
        return mangle_type_name(t[:-2]) + '[]'
    res = t.replace(' ', '')
    res = res.replace('<', '_').replace('>', '')
    res = res.replace(',', '_')
    res = res.replace('[]', '_array')
    return res

def llvm_type(t_name: str) -> str:
    if not t_name:
        return 'i64'
    t_name = mangle_type_name(t_name)
    if t_name in LLVM_TYPE_MAP:
        return LLVM_TYPE_MAP[t_name]
    if t_name.endswith('[]'):
        return '%struct.ax_array'
    return f"%struct.ax_{t_name}"

def _sanitize_for_symbol(t: str) -> str:
    return (t.replace('%struct.', 's_').replace('%', '')
             .replace('*', 'ptr').replace(' ', '')
             .replace('[', '_').replace(']', ''))


def llvm_fn_symbol(fn_name: str, param_types: list, overloaded: bool) -> str:
    if not overloaded:
        return f"ax_{fn_name}"
    sig = "_".join(_sanitize_for_symbol(t) for t in param_types)
    return f"ax_ovl_{fn_name}__{sig}" if sig else f"ax_{fn_name}"


PTR_ABI_SYMBOLS = {
    '@axiom_simd_add_i64_ptr', '@axiom_simd_mul_i64_ptr',
    '@axiom_simd_sub_i64_ptr', '@axiom_simd_sum_i64_ptr',
    '@axiom_simd_scan_match_ptr', '@axiom_os_exec_argv_ptr',
    '@axiom_json_build_object_ptr', '@axiom_csv_add_row_ptr',
    '@axiom_str_join_ptr',
    '@axiom_cli_set_args_ptr',
}


def _llvm_escape_bytes(val: str) -> str:
    """Lexer tarafindan cozulmus bir metni LLVM IR string sabitine cevirir.

    ONEMLI: `val` zaten cozulmustur ('\\n' -> newline, '\\"' -> '"').
    Bu yuzden ters bolu dizileri TEKRAR yorumlanmaz; yoksa '\\"' verisi
    tek bir '"' karakterine donusur (sessiz veri kaybi).
    """
    out = []
    for c in val:
        if c == '"':
            out.append(r'\22')
        elif c == '\n':
            out.append(r'\0A')
        elif c == '\r':
            out.append(r'\0D')
        elif c == '\t':
            out.append(r'\09')
        elif c == '\\':
            out.append(r'\5C')
        elif c == '\0':
            out.append(r'\00')
        else:
            out.append(c)
    out.append(r'\00')
    return "".join(out)


class LLVMCodeGenerator:
    def __init__(self, debug: bool = False, source_file: str = "axiom_source.ax", source_dir: str = "."):
        self.code: List[str] = []
        self.strings: Dict[str, Tuple[str, int]] = {}
        self.str_counter: int = 0
        self.reg_counter: int = 0
        self.label_counter: int = 0
        self.variables: Dict[str, Tuple[str, str]] = {}  # name -> (llvm_type, pointer_reg)
        self.current_function: Optional[FunctionDecl] = None
        self.function_types: Dict[str, Tuple[List[str], str]] = {}
        self.struct_defs: Dict[str, StructDecl] = {}
        self.block_terminated: bool = False

        # DWARF Debug Info Support
        self.debug: bool = debug
        self.source_file: str = source_file
        self.source_dir: str = source_dir
        self.current_line: int = 1
        self.current_col: int = 1
        self.current_scope_id: Optional[int] = None
        self.meta_counter: int = 12  # 0..7 module/DI, 8..11 basic types
        self.loc_cache: Dict[Tuple[int, int, int], int] = {}
        self.loc_entries: Dict[int, Tuple[int, int, int]] = {}
        self.subprograms: List[Tuple[int, str, int]] = []
        self.local_vars: List[Tuple[int, str, int, int, int]] = []

    def _current_loc_id(self) -> int:
        key = (self.current_line, self.current_col, self.current_scope_id)
        if key not in self.loc_cache:
            loc_id = self.meta_counter
            self.meta_counter += 1
            self.loc_cache[key] = loc_id
            self.loc_entries[loc_id] = key
            return loc_id
        return self.loc_cache[key]

    def new_reg(self, prefix: str = "t") -> str:
        self.reg_counter += 1
        return f"%{prefix}.{self.reg_counter}"

    def new_label(self, prefix: str = "L") -> str:
        self.label_counter += 1
        return f"{prefix}.{self.label_counter}"

    def emit(self, line: str):
        if not self.block_terminated or line.strip().endswith(':') or line.strip() == '}':
            self.code.append(line)

    def emit_instr(self, instr: str, line: Optional[int] = None, col: Optional[int] = None):
        if not self.block_terminated:
            if self.debug and self.current_scope_id is not None:
                l = line if line is not None else self.current_line
                c = col if col is not None else self.current_col
                key = (l, c, self.current_scope_id)
                if key in self.loc_cache:
                    loc_id = self.loc_cache[key]
                else:
                    loc_id = self.meta_counter
                    self.meta_counter += 1
                    self.loc_cache[key] = loc_id
                    self.loc_entries[loc_id] = (l, c, self.current_scope_id)
                self.code.append(f"    {instr}, !dbg !{loc_id}")
            else:
                self.code.append(f"    {instr}")

    def add_string_literal(self, val: str) -> Tuple[str, int]:
        if val in self.strings:
            return self.strings[val]

        name = f"@.str.{self.str_counter}"
        self.str_counter += 1

        content = _llvm_escape_bytes(val)
        import re
        s_norm = re.sub(r'\\[0-9A-Fa-f]{2}', 'X', content)
        actual_len = len(s_norm.encode('utf-8'))

        self.strings[val] = (name, actual_len)
        return (name, actual_len)

    def generate(self, program: Program) -> str:
        self.code.clear()
        self.strings.clear()
        self.str_counter = 0
        self.reg_counter = 0
        self.label_counter = 0
        self.function_return_types: dict = {}
        self.overloaded_fns: set = set()
        self.defer_stack: List[List[Stmt]] = []
        self.owned_str_stack: List[List[str]] = []
        self.str_var_scope: dict = {}
        self.escaped_str_vars: set = set()
        self.owned_array_stack: List[List[str]] = []
        self.array_var_scope: dict = {}
        self.escaped_array_vars: set = set()
        self.array_elem_types: dict = {}
        self.loop_stack: List[Tuple[str, str]] = []
        self.pending_decls: List[str] = []
        self.header_len: int = 0

        # Scan structs and functions
        functions: List[FunctionDecl] = []
        top_stmts: List[Stmt] = []
        has_user_main = False

        name_counts: Dict[str, int] = {}
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl) and len(getattr(decl, 'type_params', [])) == 0:
                name_counts[decl.name] = name_counts.get(decl.name, 0) + 1
        self.overloaded_fns = {n for n, c in name_counts.items() if c > 1}

        for decl in program.declarations:
            if isinstance(decl, StructDecl):
                if len(getattr(decl, 'type_params', [])) > 0:
                    continue
                self.struct_defs[decl.name] = decl
            elif isinstance(decl, FunctionDecl):
                if len(getattr(decl, 'type_params', [])) > 0:
                    continue
                functions.append(decl)
                param_types = [llvm_type(p.type_name) for p in decl.params]
                ret_t = llvm_type(decl.return_type)
                self.function_types[decl.name] = (param_types, ret_t)
                self.function_return_types[decl.name] = decl.return_type
                if decl.name == 'main':
                    has_user_main = True
            elif not isinstance(decl, ImportStmt):
                top_stmts.append(decl)

        # 1. Module Header
        source_fn = self.source_file if self.source_file else "axiom_source.ax"
        header = [
            '; ModuleID = "axiom_module"',
            f'source_filename = "{source_fn}"',
            'target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"',
            'target triple = "x86_64-pc-linux-gnu"',
            '',
            '; @simd fonksiyonlari icin AVX2/FMA hedef ozellikleri',
            'attributes #0 = { "target-features"="+avx2,+fma" }',
            '',
            '; Generic Axiom Array Struct',
            '%struct.ax_array = type { i64, i64, i64* }',
            ''
        ]
        self.code.extend(header)

        # @simd fonksiyonu yoksa attribute grubunu bosalt (olu tanim birakma).
        has_simd = any(getattr(f, 'is_simd', False) for f in functions)
        if not has_simd:
            header = [h for h in header if not h.startswith('attributes #0')]

        # 2. Struct Declarations
        struct_decls = []
        if self.struct_defs:
            struct_decls.append('; User Struct Definitions')
            for name, s_decl in self.struct_defs.items():
                fields_str = ", ".join(llvm_type(f.type_name) for f in s_decl.fields)
                struct_decls.append(f"%struct.ax_{name} = type {{ {fields_str} }}")
            struct_decls.append('')

        # Pre-seed standard print format strings
        self.add_string_literal("%ld\n")
        self.add_string_literal("%ld ")
        self.add_string_literal("%g\n")
        self.add_string_literal("%g ")
        self.add_string_literal("%s\n")
        self.add_string_literal("%s ")
        self.add_string_literal("true\n")
        self.add_string_literal("false\n")
        self.add_string_literal("true ")
        self.add_string_literal("false ")
        self.add_string_literal("\n")
        self.add_string_literal("\n[AXIOM GUVENLIK IHLALI] Sozlesme ihlali!\n")

        # 3. Functions
        func_bodies: List[str] = []
        for fn in functions:
            fn_ir = self.generate_function(fn)
            func_bodies.append(fn_ir)

        # 4. Main Entry Point
        entry_ir = self.generate_main_entry(has_user_main, top_stmts)

        # 5. Global String Constants
        str_decls = ['; Global String Constants']
        for val, (name, length) in self.strings.items():
            content = _llvm_escape_bytes(val)
            str_decls.append(f'{name} = private unnamed_addr constant [{length} x i8] c"{content}", align 1')
        str_decls.append('')

        # 6. External Declarations
        externs = [
            '; External Declarations',
            'declare i32 @printf(i8*, ...)',
            'declare i32 @puts(i8*)',
            'declare i8* @malloc(i64)',
            'declare void @free(i8*)',
            'declare void @llvm.dbg.declare(metadata, metadata, metadata)',
            'declare i8* @memcpy(i8*, i8*, i64)',
            'declare i64 @strlen(i8*)',
            'declare void @exit(i32)',
            'declare i64 @axiom_tcp_connect(i8*, i64)',
            'declare i64 @axiom_tcp_send(i64, i8*)',
            'declare i8* @axiom_tcp_recv(i64, i64)',
            'declare void @axiom_socket_close(i64)',
            'declare i64 @axiom_time_now_ms()',
            'declare i8* @axiom_file_read(i8*)',
            'declare i1 @axiom_file_write(i8*, i8*)',
            'declare i1 @axiom_file_exists(i8*)',
            'declare i64 @axiom_file_size(i8*)',
            'declare i1 @axiom_is_directory(i8*)',
            'declare i8* @axiom_list_dir(i8*)',
            'declare i1 @axiom_remove_file(i8*)',
            'declare i1 @axiom_rename_file(i8*, i8*)',
            'declare i1 @axiom_create_dir(i8*)',
            'declare i64 @axiom_os_exec(i8*)',
            'declare i64 @axiom_os_exec_argv_ptr(%struct.ax_array*)',
            'declare i64 @axiom_bounds_check(i64, i64, i8*, i64)',
            'declare i8* @axiom_os_getenv(i8*)',
            'declare i1 @axiom_str_contains(i8*, i8*)',
            'declare i1 @axiom_str_starts_with(i8*, i8*)',
            'declare i1 @axiom_str_ends_with(i8*, i8*)',
            'declare i8* @axiom_str_trim(i8*)',
            'declare i64 @axiom_str_len(i8*)',
            'declare i64 @axiom_str_byte_len(i8*)',
            'declare i64 @axiom_str_to_int(i8*)',
            'declare i8* @axiom_int_to_str(i64)',
            'declare i64 @axiom_math_abs(i64)',
            'declare i64 @axiom_math_min(i64, i64)',
            'declare i64 @axiom_math_max(i64, i64)',
            'declare i64 @axiom_math_pow(i64, i64)',
            'declare i64 @axiom_thread_create(i8*, i64, i1)',
            'declare i64 @axiom_thread_join(i64)',
            'declare i64 @axiom_mutex_init()',
            'declare void @axiom_mutex_lock(i64)',
            'declare void @axiom_mutex_unlock(i64)',
            'declare i64 @axiom_atomic_init(i64)',
            'declare i64 @axiom_atomic_add(i64, i64)',
            'declare i64 @axiom_atomic_get(i64)',
            'declare void @axiom_sleep_ms(i64)',
            'declare void @axiom_contract_fail(i8*, i8*, i8*, i32, i8*)',
            'declare void @axiom_str_free(i8*)',
            'declare void @axiom_str_retain(i8*)',
            'declare void @axiom_str_release(i8*)',
            'declare void @axiom_str_owned_release(i8**)',
            'declare void @axiom_array_str_free(%struct.ax_array*)',
            'declare void @axiom_array_int_free(%struct.ax_array*)',
            'declare void @axiom_array_float_free(%struct.ax_array*)',
            'declare void @axiom_array_bool_free(%struct.ax_array*)',
            'declare i8* @axiom_str_concat(i8*, i8*)',
            'declare i1 @axiom_str_eq(i8*, i8*)',
            'declare i1 @axiom_str_neq(i8*, i8*)',
            'declare i8* @axiom_str_join_ptr(%struct.ax_array*, i8*)',
            'declare void @axiom_simd_add_i64_ptr(%struct.ax_array*, %struct.ax_array*, %struct.ax_array*)',
            'declare void @axiom_simd_mul_i64_ptr(%struct.ax_array*, %struct.ax_array*, %struct.ax_array*)',
            'declare void @axiom_simd_sub_i64_ptr(%struct.ax_array*, %struct.ax_array*, %struct.ax_array*)',
            'declare i64 @axiom_simd_sum_i64_ptr(%struct.ax_array*)',
            'declare i64 @axiom_simd_scan_match_ptr(%struct.ax_array*, i64)',
            'declare i8* @axiom_base64_encode(i8*)',
            'declare i8* @axiom_base64_decode(i8*)',
            'declare i8* @axiom_hex_encode(i8*)',
            'declare i8* @axiom_hex_decode(i8*)',
            'declare i8* @axiom_hash_md5(i8*)',
            'declare i8* @axiom_hash_sha1(i8*)',
            'declare i8* @axiom_hash_sha256(i8*)',
            'declare i8* @axiom_url_encode(i8*)',
            'declare i8* @axiom_url_decode(i8*)',
            'declare i8* @axiom_url_parse_scheme(i8*)',
            'declare i8* @axiom_url_parse_host(i8*)',
            'declare i64 @axiom_url_parse_port(i8*)',
            'declare i8* @axiom_url_parse_path(i8*)',
            'declare i8* @axiom_url_parse_query(i8*)',
            'declare i8* @axiom_json_get_str(i8*, i8*)',
            'declare i64 @axiom_json_get_int(i8*, i8*)',
            'declare i1 @axiom_json_get_bool(i8*, i8*)',
            'declare i1 @axiom_json_has_key(i8*, i8*)',
            'declare i8* @axiom_json_build_object_ptr(%struct.ax_array*, %struct.ax_array*)',
            'declare i64 @axiom_json_parse_wrap(i8*)',
            'declare void @axiom_json_free(i64)',
            'declare i8* @axiom_json_last_error()',
            'declare i64 @axiom_json_type_of(i64)',
            'declare i64 @axiom_json_len(i64)',
            'declare i64 @axiom_json_at(i64, i64)',
            'declare i8* @axiom_json_key_at(i64, i64)',
            'declare i64 @axiom_json_get(i64, i8*)',
            'declare i64 @axiom_json_path(i64, i8*)',
            'declare i8* @axiom_json_node_str(i64)',
            'declare i64 @axiom_json_node_int(i64)',
            'declare double @axiom_json_node_float(i64)',
            'declare i1 @axiom_json_node_bool(i64)',
            'declare i1 @axiom_json_node_is_null(i64)',
            'declare i8* @axiom_tcp_recv_all(i64, i64)',
            'declare i64 @axiom_tcp_set_timeout(i64, i64)',
            'declare i8* @axiom_http_header_value(i8*, i8*)',
            'declare i8* @axiom_http_chunked_decode(i8*)',
            '; Packet 2 Builtin Declarations',
            'declare i8* @axiom_dns_resolve_ipv4(i8*)',
            'declare i8* @axiom_dns_resolve_ipv6(i8*)',
            'declare i8* @axiom_dns_reverse_lookup(i8*)',
            'declare i64 @axiom_udp_socket()',
            'declare i64 @axiom_udp_bind(i64)',
            'declare i64 @axiom_udp_sendto(i64, i8*, i64, i8*)',
            'declare i8* @axiom_udp_recvfrom(i64, i64)',
            'declare void @axiom_udp_close(i64)',
            'declare i64 @axiom_http_server_create(i64)',
            'declare i64 @axiom_http_server_accept(i64)',
            'declare void @axiom_http_server_send_response(i64, i64, i8*, i8*)',
            'declare void @axiom_http_server_close(i64)',
            'declare i64 @axiom_tls_connect(i8*, i64)',
            'declare i64 @axiom_tls_send(i64, i8*)',
            'declare i8* @axiom_tls_recv(i64, i64)',
            'declare void @axiom_tls_close(i64)',
            'declare i64 @axiom_ws_connect(i8*, i64, i8*)',
            'declare i64 @axiom_ws_send(i64, i8*)',
            'declare i8* @axiom_ws_recv(i64)',
            'declare void @axiom_ws_close(i64)',
            # Packet 3 Builtins: Binary Buffer, Process, Zlib, Regex, Map
            'declare i64 @axiom_buf_create(i64)',
            'declare void @axiom_buf_write_u8(i64, i64)',
            'declare void @axiom_buf_write_u16_be(i64, i64)',
            'declare void @axiom_buf_write_u16_le(i64, i64)',
            'declare void @axiom_buf_write_u32_be(i64, i64)',
            'declare void @axiom_buf_write_u32_le(i64, i64)',
            'declare void @axiom_buf_write_u64_be(i64, i64)',
            'declare void @axiom_buf_write_u64_le(i64, i64)',
            'declare void @axiom_buf_write_str(i64, i8*)',
            'declare i8* @axiom_buf_to_hex(i64)',
            'declare i8* @axiom_buf_to_str(i64)',
            'declare i64 @axiom_buf_len(i64)',
            'declare i64 @axiom_buf_from_hex(i8*)',
            'declare i64 @axiom_buf_read_u8(i64, i64)',
            'declare i64 @axiom_buf_read_u16_be(i64, i64)',
            'declare i64 @axiom_buf_read_u16_le(i64, i64)',
            'declare i64 @axiom_buf_read_u32_be(i64, i64)',
            'declare i64 @axiom_buf_read_u32_le(i64, i64)',
            'declare i64 @axiom_buf_read_u64_be(i64, i64)',
            'declare i64 @axiom_buf_read_u64_le(i64, i64)',
            'declare void @axiom_buf_free(i64)',
            'declare i8* @axiom_process_exec_output(i8*)',
            'declare i64 @axiom_process_get_pid()',
            'declare i64 @axiom_process_kill(i64, i64)',
            'declare i64 @axiom_process_spawn_bg(i8*)',
            'declare i8* @axiom_gzip_compress(i8*)',
            'declare i8* @axiom_gzip_decompress(i8*)',
            'declare i8* @axiom_zlib_compress_str(i8*)',
            'declare i8* @axiom_zlib_decompress_str(i8*)',
            'declare i8* @axiom_regex_validate(i8*)',
            'declare i64 @axiom_regex_risk_level(i8*)',
            'declare i1 @axiom_regex_is_match(i8*, i8*)',
            'declare i8* @axiom_regex_find(i8*, i8*)',
            'declare i8* @axiom_regex_replace(i8*, i8*, i8*)',
            'declare i64 @axiom_map_create()',
            'declare void @axiom_map_set(i64, i8*, i8*)',
            'declare i8* @axiom_map_get(i64, i8*)',
            'declare i1 @axiom_map_has(i64, i8*)',
            'declare i1 @axiom_map_delete(i64, i8*)',
            'declare i64 @axiom_map_len(i64)',
            'declare void @axiom_map_free(i64)',
            # Packet 4 Builtins: Queue, Fuzzer, Date/Time, CSV, CLI Args
            'declare i64 @axiom_queue_create()',
            'declare void @axiom_queue_push(i64, i8*)',
            'declare i8* @axiom_queue_pop(i64)',
            'declare i64 @axiom_queue_len(i64)',
            'declare i1 @axiom_queue_is_empty(i64)',
            'declare void @axiom_queue_free(i64)',
            'declare i8* @axiom_fuzz_replace_marker(i8*, i8*, i8*)',
            'declare i8* @axiom_fuzz_url_encode(i8*)',
            'declare i8* @axiom_fuzz_double_encode(i8*)',
            'declare i8* @axiom_fuzz_add_null_byte(i8*)',
            'declare i64 @axiom_wordlist_load(i8*)',
            'declare i64 @axiom_wordlist_count(i64)',
            'declare i8* @axiom_wordlist_get(i64, i64)',
            'declare void @axiom_wordlist_free(i64)',
            'declare i8* @axiom_date_format_tz(i64, i8*, i64)',
            'declare i8* @axiom_date_iso_tz(i64, i64)',
            'declare i64 @axiom_date_parse_iso(i8*)',
            'declare i64 @axiom_date_local_offset_minutes()',
            'declare i8* @axiom_date_now_iso()',
            'declare i64 @axiom_date_now_epoch()',
            'declare i8* @axiom_date_format_epoch(i64, i8*)',
            'declare i64 @axiom_date_diff_seconds(i64, i64)',
            'declare i64 @axiom_csv_create()',
            'declare void @axiom_csv_add_row_ptr(i64, %struct.ax_array*)',
            'declare i8* @axiom_csv_to_str(i64)',
            'declare i1 @axiom_csv_save_file(i64, i8*)',
            'declare void @axiom_csv_free(i64)',
            'declare void @axiom_cli_init_args(i32, i8**)',
            'declare void @axiom_eprint_error(i8*)',
            'declare void @axiom_cli_set_args_ptr(%struct.ax_array*)',
            'declare i64 @axiom_cli_args_count()',
            'declare i8* @axiom_cli_args_get(i64)',
            'declare i1 @axiom_cli_has_flag(i8*)',
            'declare i8* @axiom_cli_get_option(i8*, i8*)',
            'declare i64 @axiom_cli_get_int_option(i8*, i64)',
            '; Packet 5 Builtins: AES, JWT, HTML, Logger, Raw Socket & Ping',
            'declare i8* @axiom_aes256_cbc_encrypt(i8*, i8*, i8*)',
            'declare i8* @axiom_aes256_cbc_decrypt(i8*, i8*, i8*)',
            'declare i8* @axiom_aes128_cbc_encrypt(i8*, i8*, i8*)',
            'declare i8* @axiom_aes128_cbc_decrypt(i8*, i8*, i8*)',
            'declare i8* @axiom_jwt_create_hs256(i8*, i8*)',
            'declare i1 @axiom_jwt_verify_hs256(i8*, i8*)',
            'declare i8* @axiom_jwt_get_header(i8*)',
            'declare i8* @axiom_jwt_get_payload(i8*)',
            'declare i8* @axiom_jwt_get_claim(i8*, i8*)',
            'declare i8* @axiom_html_escape(i8*)',
            'declare i8* @axiom_html_unescape(i8*)',
            'declare i8* @axiom_html_strip_tags(i8*)',
            'declare void @axiom_log_set_level(i64)',
            'declare void @axiom_log_debug(i8*, i8*)',
            'declare void @axiom_log_info(i8*, i8*)',
            'declare void @axiom_log_warn(i8*, i8*)',
            'declare void @axiom_log_error(i8*, i8*)',
            'declare i64 @axiom_icmp_ping(i8*, i64)',
            'declare i64 @axiom_tcp_ping(i8*, i64, i64)',
            'declare i64 @axiom_raw_checksum(i8*)',
            # Phase 2 Builtins
            'declare i64 @axiom_exec_mem_run(i8*)',
            'declare i64 @axiom_exec_mem_alloc(i64)',
            'declare i1 @axiom_exec_mem_protect(i64, i64, i64)',
            'declare i8* @axiom_packet_craft_ip(i8*, i8*, i64, i64)',
            'declare i8* @axiom_packet_craft_tcp(i8*, i8*, i64, i64, i64, i64)',
            'declare i8* @axiom_packet_craft_udp(i64, i64, i8*)',
            'declare i1 @axiom_diag_is_debugged()',
            'declare i1 @axiom_diag_is_virtualized()',
            'declare void @axiom_diag_set_dumpable(i1)',
            'declare i64 @axiom_proc_search_pattern(i64, i8*)',
            'declare i8* @axiom_proc_get_maps(i64)',
            # Phase 3 Declarations
            'declare i64 @axiom_pcap_create_writer(i8*)',
            'declare i1 @axiom_pcap_write_packet(i64, i8*)',
            'declare i64 @axiom_pcap_open_file(i8*)',
            'declare i8* @axiom_pcap_next_packet(i64)',
            'declare i64 @axiom_pcap_packet_count(i64)',
            'declare void @axiom_pcap_close(i64)',
            'declare i8* @axiom_fim_hash_file(i8*)',
            'declare i8* @axiom_forensics_get_ports()',
            'declare i8* @axiom_forensics_get_processes()',
            'declare i8* @axiom_forensics_get_modules()',
            # Phase 4 Declarations
            'declare i64 @axiom_tensor_create_2d(i64, i64)',
            'declare void @axiom_tensor_set(i64, i64, i64, double)',
            'declare double @axiom_tensor_get(i64, i64, i64)',
            'declare i64 @axiom_tensor_rows(i64)',
            'declare i64 @axiom_tensor_cols(i64)',
            'declare i64 @axiom_tensor_matmul(i64, i64)',
            'declare i64 @axiom_tensor_add(i64, i64)',
            'declare i64 @axiom_tensor_transpose(i64)',
            'declare i8* @axiom_tensor_to_str(i64)',
            'declare void @axiom_tensor_free(i64)',
            'declare double @axiom_nn_relu(double)',
            'declare double @axiom_nn_sigmoid(double)',
            'declare i64 @axiom_nn_argmax(i64)',
            'declare double @axiom_dot_product(i64, i64)',
            'declare i64 @axiom_epoll_create(i64)',
            'declare i64 @axiom_epoll_add(i64, i64, i64)',
            'declare i64 @axiom_epoll_mod(i64, i64, i64)',
            'declare i64 @axiom_epoll_del(i64, i64)',
            'declare i64 @axiom_epoll_wait(i64, i64)',
            'declare i64 @axiom_epoll_event_fd(i64, i64)',
            'declare i64 @axiom_epoll_event_events(i64, i64)',
            'declare void @axiom_epoll_close(i64)',
            'declare i64 @axiom_net_set_nonblocking(i64)',
            'declare i64 @axiom_tcp_server_nonblocking(i64)',
            'declare i64 @axiom_tcp_accept_nonblocking(i64)',
            'declare i64 @axiom_fd_write(i64, i8*)',
            'declare i8* @axiom_fd_read(i64, i64)',
            'declare i64 @axiom_pipe_create()',
            'declare i64 @axiom_pipe_read_fd(i64)',
            'declare i64 @axiom_pipe_write_fd(i64)',
            'declare void @axiom_pipe_close(i64)',
            'declare i64 @axiom_socketpair_create()',
            'declare i64 @axiom_socketpair_fd1(i64)',
            'declare i64 @axiom_socketpair_fd2(i64)',
            'declare void @axiom_socketpair_close(i64)',
            'declare i1 @axiom_epoll_is_readable(i64)',
            'declare i1 @axiom_epoll_is_writable(i64)',
            'declare i1 @axiom_epoll_is_error(i64)',
            'declare i1 @axiom_epoll_is_hangup(i64)',
            # Phase 4.3: Real YARA Byte & Wildcard Mask Pattern Engine
            'declare i64 @axiom_ascii_case_find(i8*, i8*)',
            'declare i64 @axiom_yara_find_hex_wildcard(i8*, i8*, i64, i64)',
            'declare i64 @axiom_yara_find_hex_wildcard_raw(i8*, i64, i8*, i64, i64)',
            'declare i64 @axiom_yara_find_hex_stream(i8*, i8*)',
            'declare i64 @axiom_yara_pattern_len(i8*)',
            'declare i64 @axiom_yara_scan_buf_handle(i64, i8*, i64, i64)',
            ''
        ]

        # Combine all sections
        metadata_sections = []
        if self.debug:
            metadata_sections.append('; DWARF Debug Metadata')
            metadata_sections.append('!llvm.dbg.cu = !{!0}')
            metadata_sections.append('!llvm.module.flags = !{!1, !2}')
            metadata_sections.append('!llvm.ident = !{!3}')
            metadata_sections.append('')
            metadata_sections.append('!0 = distinct !DICompileUnit(language: DW_LANG_C99, file: !4, producer: "Axiom Compiler v0.5.0", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, enums: !5)')
            metadata_sections.append('!1 = !{i32 2, !"Dwarf Version", i32 4}')
            metadata_sections.append('!2 = !{i32 2, !"Debug Info Version", i32 3}')
            metadata_sections.append('!3 = !{!"Axiom Compiler v0.5.0"}')
            metadata_sections.append(f'!4 = !DIFile(filename: "{self.source_file}", directory: "{self.source_dir}")')
            metadata_sections.append('!5 = !{}')
            metadata_sections.append('!6 = !DISubroutineType(types: !7)')
            metadata_sections.append('!7 = !{null}')
            metadata_sections.append('!8 = !DIBasicType(name: "long int", size: 64, encoding: DW_ATE_signed)')
            metadata_sections.append('!9 = !DIBasicType(name: "double", size: 64, encoding: DW_ATE_float)')
            metadata_sections.append('!10 = !DIBasicType(name: "bool", size: 8, encoding: DW_ATE_boolean)')
            metadata_sections.append('!11 = !DIBasicType(name: "char*", size: 64, encoding: DW_ATE_address)')
            for sp_id, fn_name, sp_line in self.subprograms:
                metadata_sections.append(
                    f'!{sp_id} = distinct !DISubprogram(name: "{fn_name}", scope: !4, file: !4, line: {sp_line}, type: !6, scopeLine: {sp_line}, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !0)'
                )
            for var_id, var_name, var_line, scope_id, type_id in self.local_vars:
                metadata_sections.append(
                    f'!{var_id} = !DILocalVariable(name: "{var_name}", scope: !{scope_id}, file: !4, line: {var_line}, type: !{type_id})'
                )
            for loc_id, (l, c, scope_id) in self.loc_entries.items():
                metadata_sections.append(
                    f'!{loc_id} = !DILocation(line: {l}, column: {c}, scope: !{scope_id})'
                )
            metadata_sections.append('')

        # Struct donduren C fonksiyonlari icin ABI'yi ACIKCA belirt.
        # LLVM bazi durumlarda struct donusunu kayitlarda yapar; clang ile
        # derlenen C tarafi >16 bayt struct'lari sret ile dondurur. Bu
        # uyumsuzluk segfault'a yol acar; bildirimi ve cagriyi sret'e sabitle.
        struct_ret_decl = re.compile(
            r'^declare\s+(%struct\.\w+)\s+@(\w+)\((.*)\)$')
        rewritten_externs = []
        for line in externs:
            m = struct_ret_decl.match(line)
            if m and '@' + m.group(2) not in PTR_ABI_SYMBOLS:
                ty, fname, args = m.group(1), m.group(2), m.group(3)
                if args:
                    rewritten_externs.append(f"declare void @{fname}({ty}* sret({ty}), {args})")
                else:
                    rewritten_externs.append(f"declare void @{fname}({ty}* sret({ty}))")
            else:
                rewritten_externs.append(line)
        externs = rewritten_externs

        final_sections = [
            "\n".join(header),
            "\n".join(struct_decls),
            "\n".join(str_decls),
            "\n".join(externs),
            "\n".join(self.pending_decls),
            "\n".join(func_bodies),
            entry_ir,
            "\n".join(metadata_sections)
        ]
        return "\n".join(final_sections)

    def generate_function(self, fn: FunctionDecl) -> str:
        self.current_function = fn
        self.variables.clear()
        self.reg_counter = 0
        self.block_terminated = False
        self.defer_stack = []
        self.owned_str_stack = [[]]
        self.str_var_scope = {}
        self.escaped_str_vars = set()
        self.owned_array_stack = [[]]
        self.array_var_scope = {}
        self.escaped_array_vars = set()
        self.array_elem_types = {}
        self.loop_stack = []
        saved_code = self.code
        self.code = []

        fn_line = getattr(fn, 'line', 1) or 1
        self.current_line = fn_line
        self.current_col = 1

        dbg_fn_attr = ""
        if self.debug:
            sp_id = self.meta_counter
            self.meta_counter += 1
            self.current_scope_id = sp_id
            self.subprograms.append((sp_id, f"ax_{fn.name}", fn_line))
            dbg_fn_attr = f" !dbg !{sp_id}"

        ret_t = llvm_type(fn.return_type)
        param_list = []
        for p in fn.params:
            pt = llvm_type(p.type_name)
            param_list.append(f"{pt} %param.{p.name}")
        sym_name = llvm_fn_symbol(
            fn.name,
            [llvm_type(p.type_name) for p in fn.params],
            fn.name in self.overloaded_fns,
        )
        params_str = ", ".join(param_list)

        simd_attr = ' #0' if getattr(fn, 'is_simd', False) else ''
        self.emit(f"define {ret_t} @{sym_name}({params_str}){simd_attr}{dbg_fn_attr} {{")
        self.emit("entry:")

        # Allocate space for parameters and copy
        for p in fn.params:
            pt = llvm_type(p.type_name)
            ptr = self.new_reg(f"ptr.{p.name}")
            self.emit_instr(f"{ptr} = alloca {pt}, align 8")
            self.emit_instr(f"store {pt} %param.{p.name}, {pt}* {ptr}, align 8")
            self.variables[p.name] = (pt, ptr)

        # Requires contracts
        for req in fn.contract.requires:
            cond_ty, cond_reg = self.generate_expr(req)
            then_lbl = self.new_label("req_ok")
            fail_lbl = self.new_label("req_fail")
            self.emit_instr(f"br i1 {cond_reg}, label %{then_lbl}, label %{fail_lbl}")
            self.emit(f"{fail_lbl}:")
            err_ptr, _ = self.get_string_ptr("\n[AXIOM GUVENLIK IHLALI] Sozlesme ihlali!\n")
            self.emit_instr(f"call i32 @puts(i8* {err_ptr})")
            self.emit_instr("call void @exit(i32 101)")
            self.emit_instr("unreachable")
            self.emit(f"{then_lbl}:")

        # Function body
        self._push_str_scope()
        for stmt in fn.body.statements:
            self.generate_stmt(stmt)
        if not self.block_terminated:
            self._pop_str_scope()

        # Default return if not terminated
        if not self.block_terminated:
            self._emit_deferred_all()
            if fn.return_type == 'void' and fn.contract and fn.contract.ensures:
                for ens in fn.contract.ensures:
                    cond_ty, cond_reg = self.generate_expr(ens)
                    then_lbl = self.new_label("ens_ok")
                    fail_lbl = self.new_label("ens_fail")
                    self.emit_instr(f"br i1 {cond_reg}, label %{then_lbl}, label %{fail_lbl}")
                    self.emit(f"{fail_lbl}:")
                    err_ptr, _ = self.get_string_ptr("\n[AXIOM GUVENLIK IHLALI] Sozlesme ihlali!\n")
                    self.emit_instr(f"call i32 @puts(i8* {err_ptr})")
                    self.emit_instr("call void @exit(i32 101)")
                    self.emit_instr("unreachable")
                    self.emit(f"{then_lbl}:")

            if ret_t == 'void':
                self.emit_instr("ret void")
            elif ret_t == 'i64':
                self.emit_instr("ret i64 0")
            elif ret_t == 'double':
                self.emit_instr("ret double 0.0")
            elif ret_t == 'i1':
                self.emit_instr("ret i1 0")
            elif ret_t == 'i8*':
                null_ptr = self.new_reg("null")
                self.emit_instr(f"{null_ptr} = inttoptr i64 0 to i8*")
                self.emit_instr(f"ret i8* {null_ptr}")
            else:
                self.emit_instr("unreachable")
            self.block_terminated = True

        self.emit("}")
        self.emit("")
        fn_code = "\n".join(self.code)
        self.code = saved_code
        return fn_code

    def _struct_main_bridge_is_result(self, ret_t: str):
        """Struct donduren `main` bir Result mi? (is_ok/error alanlari var mi?)"""
        base = ret_t.replace('%struct.', '')
        if base.startswith('ax_'):
            base = base[3:]
        decl = self.struct_defs.get(base)
        if decl is None:
            return None
        names = [f.name for f in decl.fields]
        if 'is_ok' in names and 'error' in names:
            return (names.index('is_ok'), names.index('error'))
        return None

    def _emit_struct_main_bridge(self, ret_t: str):
        """`main() -> Result<..>` icin giris koprusu.

        Sozlesme (C arka ucuyla birebir):
          Ok  -> exit 0
          Err -> hata mesaji stderr'e, exit 1
        """
        idx = self._struct_main_bridge_is_result(ret_t)
        if idx is None:
            # Result olmayan struct main: degeri yok say, basari say.
            tmp = self.new_reg("mainrc")
            self.emit_instr(f"{tmp} = call {ret_t} @ax_main()")
            self.emit_instr("ret i32 0")
            return

        ok_i, err_i = idx
        rc = self.new_reg("mainrc")
        self.emit_instr(f"{rc} = call {ret_t} @ax_main()")
        ok_v = self.new_reg("mainok")
        self.emit_instr(f"{ok_v} = extractvalue {ret_t} {rc}, {ok_i}")
        ok_lbl = self.new_label("main_ok")
        err_lbl = self.new_label("main_err")
        self.emit_instr(f"br i1 {ok_v}, label %{ok_lbl}, label %{err_lbl}")

        self.emit(f"{err_lbl}:")
        self.block_terminated = False
        err_v = self.new_reg("mainerr")
        self.emit_instr(f"{err_v} = extractvalue {ret_t} {rc}, {err_i}")
        self.emit_instr(f"call void @axiom_eprint_error(i8* {err_v})")
        self.emit_instr("ret i32 1")

        self.emit(f"{ok_lbl}:")
        self.block_terminated = False
        self.emit_instr("ret i32 0")

    def generate_main_entry(self, has_user_main: bool, top_stmts: List[Stmt]) -> str:
        saved_code = self.code
        self.code = []
        self.variables.clear()
        self.reg_counter = 0
        self.block_terminated = False

        dbg_main_attr = ""
        if self.debug:
            sp_id = self.meta_counter
            self.meta_counter += 1
            self.current_scope_id = sp_id
            self.subprograms.append((sp_id, "main", 1))
            self.current_line = 1
            self.current_col = 1
            dbg_main_attr = f" !dbg !{sp_id}"

        self.emit(f"define i32 @main(i32 %argc, i8** %argv){dbg_main_attr} {{")
        self.emit("entry:")
        self.emit_instr("call void @axiom_cli_init_args(i32 %argc, i8** %argv)")

        if has_user_main:
            user_main_ret = self.function_types.get('main', ([], 'void'))[1]
            if user_main_ret == 'i64':
                ret_val = self.new_reg("ret")
                self.emit_instr(f"{ret_val} = call i64 @ax_main()")
                trunc_val = self.new_reg("trunc")
                self.emit_instr(f"{trunc_val} = trunc i64 {ret_val} to i32")
                self.emit_instr(f"ret i32 {trunc_val}")
            elif user_main_ret.startswith('%struct.'):
                # `main() -> Result<int, str>`: C arka ucuyla ayni sozlesme.
                # Onceki kod `call void @ax_main()` uretiyordu; tip uyusmazligi
                # clang 14'te derleme hatasi, clang 21'te SESSIZ yanlis sonuc
                # (Err dusurulur, exit 0) veriyordu. Bkz. P1-03c raporu §9.
                self._emit_struct_main_bridge(user_main_ret)
            else:
                self.emit_instr("call void @ax_main()")
                self.emit_instr("ret i32 0")
        elif top_stmts:
            for stmt in top_stmts:
                self.generate_stmt(stmt)
            if not self.block_terminated:
                self.emit_instr("ret i32 0")
        else:
            self.emit_instr("ret i32 0")

        self.emit("}")
        self.emit("")
        main_code = "\n".join(self.code)
        self.code = saved_code
        return main_code

    def get_string_ptr(self, val: str) -> Tuple[str, int]:
        name, length = self.add_string_literal(val)
        ptr = self.new_reg("str_ptr")
        self.emit_instr(f"{ptr} = getelementptr inbounds [{length} x i8], [{length} x i8]* {name}, i64 0, i64 0")
        return ptr, length

    # --- String sahiplik kapsamlari (C arka ucuyla ayni semantik) ---

    def _push_str_scope(self):
        self.owned_str_stack.append([])
        self.owned_array_stack.append([])

    def _mark_owned_str(self, name: str):
        if not self.owned_str_stack:
            self.owned_str_stack.append([])
        scope = self.str_var_scope.get(name)
        if scope is None:
            scope = self.owned_str_stack[-1]
            self.str_var_scope[name] = scope
        if name not in scope:
            scope.append(name)

    def _emit_release_for(self, name: str):
        if name in self.escaped_str_vars:
            return
        entry = self.variables.get(name)
        if not entry:
            return
        t, ptr = entry
        if t == 'i8*':
            self.emit_instr(f"call void @axiom_str_owned_release(i8** {ptr})")

    def _emit_array_release_for(self, name: str):
        """Heap'te ayrilmis diziyi (ve str[] ise elemanlarini) birak."""
        if name in self.escaped_array_vars:
            return
        entry = self.variables.get(name)
        if not entry:
            return
        t, ptr = entry
        if t != '%struct.ax_array':
            return
        elem_t = self.array_elem_types.get(name, 'int')
        free_fn = {
            'str': '@axiom_array_str_free',
            'int': '@axiom_array_int_free',
            'float': '@axiom_array_float_free',
            'bool': '@axiom_array_bool_free',
        }.get(elem_t)
        if free_fn:
            self.emit_instr(f"call void {free_fn}(%struct.ax_array* {ptr})")

    def _pop_str_scope(self):
        """Acik kapsami kapat; sahiplenilmis string ve dizileri birak."""
        if not self.owned_str_stack:
            return
        owned = self.owned_str_stack.pop()
        owned_arrays = self.owned_array_stack.pop() if self.owned_array_stack else []
        for name in [n for n, sc in self.str_var_scope.items() if sc is owned]:
            self.str_var_scope.pop(name, None)
        for name in [n for n, sc in self.array_var_scope.items() if sc is owned_arrays]:
            self.array_var_scope.pop(name, None)
        for name in reversed(owned):
            self._emit_release_for(name)
        for name in reversed(owned_arrays):
            self._emit_array_release_for(name)

    def _emit_all_str_releases(self):
        """Tum acik kapsamlardaki sahipli string ve dizileri ters sirada birak."""
        for scope in reversed(self.owned_str_stack):
            for name in reversed(scope):
                self._emit_release_for(name)
        for scope in reversed(self.owned_array_stack):
            for name in reversed(scope):
                self._emit_array_release_for(name)

    def _emit_current_scope_releases(self):
        """break/continue oncesi yalnizca EN IC kapsamin temizligi.

        owned_release/array_free cagrilari isaretciyi NULL'a cektigi icin
        ayni degiskenin sonradan tekrar birakilmasi zararsizdir (no-op).
        """
        if self.owned_str_stack:
            for name in reversed(self.owned_str_stack[-1]):
                self._emit_release_for(name)
        if self.owned_array_stack:
            for name in reversed(self.owned_array_stack[-1]):
                self._emit_array_release_for(name)

    def _mark_owned_array(self, name: str, elem_t: str):
        if not self.owned_array_stack:
            self.owned_array_stack.append([])
        scope = self.array_var_scope.get(name)
        if scope is None:
            scope = self.owned_array_stack[-1]
            self.array_var_scope[name] = scope
        if name not in scope:
            scope.append(name)
        self.array_elem_types[name] = elem_t

    def _mark_escape(self, expr):
        """Bir ifadede gecen sahipli string degiskenlerini 'kacar' olarak isaretle.

        Kacan deger kapsam sonunda serbest BIRAKILMAZ; aksi halde
        use-after-free olur (struct alani, dizi elemani, cagri argumani).
        """
        from axiom.ast_nodes import (Identifier as _Id, MemberAccess as _MA,
                                     IndexAccess as _IA, StructInit as _SI,
                                     FunctionCall as _FC, BinaryOp as _BO,
                                     ArrayLiteral as _AL)
        if isinstance(expr, _Id):
            if expr.name in self.str_var_scope:
                self.escaped_str_vars.add(expr.name)
            if expr.name in self.array_var_scope:
                self.escaped_array_vars.add(expr.name)
        elif isinstance(expr, _MA):
            self._mark_escape(expr.object)
        elif isinstance(expr, _IA):
            self._mark_escape(expr.array)
        elif isinstance(expr, _SI):
            for f in getattr(expr, 'fields', []):
                self._mark_escape(f.value)
        elif isinstance(expr, _AL):
            for e in getattr(expr, 'elements', []):
                self._mark_escape(e)
        elif isinstance(expr, _FC):
            if expr.callee not in ('len', 'array_push', 'str_free', 'rt_str_free'):
                for a in expr.args:
                    self._mark_escape(a)
        elif isinstance(expr, _BO):
            self._mark_escape(expr.left)
            self._mark_escape(expr.right)

    def _is_borrowed_str_expr(self, expr) -> bool:
        from axiom.ast_nodes import Identifier as _Id, MemberAccess as _MA, IndexAccess as _IA
        return isinstance(expr, (_Id, _MA, _IA))

    def _emit_deferred_all(self):
        """Tum bekleyen defer'lari ters sirada (LIFO) uretir."""
        for scope in reversed(self.defer_stack):
            for d in reversed(scope):
                if isinstance(d, Block):
                    for inner in d.statements:
                        self.generate_stmt(inner)
                else:
                    self.generate_stmt(d)

    def generate_stmt(self, stmt: Stmt):
        if self.block_terminated:
            return

        if isinstance(stmt, (BreakStmt, ContinueStmt)):
            if not self.loop_stack:
                raise RuntimeError(
                    f"'break'/'continue' dongu disinda kullanilamaz (satir {getattr(stmt, 'line', '?')})"
                )
            cont_lbl, break_lbl = self.loop_stack[-1]
            target = break_lbl if isinstance(stmt, BreakStmt) else cont_lbl
            # Yalnizca EN IC blogun defer'lari calisir; fonksiyon duzeyindekiler
            # donguden cikista degil, fonksiyondan cikista calisir.
            if self.defer_stack:
                for d in reversed(self.defer_stack[-1]):
                    if isinstance(d, Block):
                        for inner in d.statements:
                            self.generate_stmt(inner)
                    else:
                        self.generate_stmt(d)
            self._emit_current_scope_releases()
            self.emit_instr(f"br label %{target}")
            self.block_terminated = True
            return

        if isinstance(stmt, DeferStmt):
            body = stmt.stmt
            if self.defer_stack:
                self.defer_stack[-1].append(body)
            else:
                self.defer_stack.append([body])
            return

        if hasattr(stmt, 'line') and stmt.line:
            self.current_line = stmt.line
        if hasattr(stmt, 'column') and stmt.column:
            self.current_col = stmt.column
        elif hasattr(stmt, 'col') and stmt.col:
            self.current_col = stmt.col

        if isinstance(stmt, LetDecl):
            target_t = llvm_type(stmt.type_annotation) if stmt.type_annotation else None
            if stmt.initializer:
                val_t, val_reg = self.generate_expr(stmt.initializer)
                if target_t and target_t != val_t:
                    if target_t == 'double' and val_t == 'i64':
                        conv = self.new_reg("sitofp")
                        self.emit_instr(f"{conv} = sitofp i64 {val_reg} to double")
                        val_reg = conv
                        val_t = 'double'
                    elif target_t == 'i64' and val_t == 'double':
                        conv = self.new_reg("fptosi")
                        self.emit_instr(f"{conv} = fptosi double {val_reg} to i64")
                        val_reg = conv
                        val_t = 'i64'
                    elif target_t == 'i8*' and val_t == 'i64':
                        conv = self.new_reg("inttoptr")
                        self.emit_instr(f"{conv} = inttoptr i64 {val_reg} to i8*")
                        val_reg = conv
                        val_t = 'i8*'
                    elif target_t == 'i64' and val_t == 'i8*':
                        conv = self.new_reg("ptrtoint")
                        self.emit_instr(f"{conv} = ptrtoint i8* {val_reg} to i64")
                        val_reg = conv
                        val_t = 'i64'
                t = target_t if target_t else val_t
            else:
                t = target_t or 'i64'
                val_reg = None

            ptr = self.new_reg(f"var.{stmt.name}")
            self.emit_instr(f"{ptr} = alloca {t}, align 8")
            self.variables[stmt.name] = (t, ptr)
            if val_reg is not None:
                self.emit_instr(f"store {t} {val_reg}, {t}* {ptr}, align 8")

            # Sahiplik: TUM str degiskenleri izlenir (literal ile baslasa bile).
            # Izlenmeyen bir degiskene sonradan atama yapilirsa retain/release
            # uretilmez ve dangling pointer olusur. Literal'e release zaten no-op.
            if t == 'i8*' and val_reg is not None:
                if self._is_borrowed_str_expr(stmt.initializer):
                    self.emit_instr(f"call void @axiom_str_retain(i8* {val_reg})")
                self._mark_owned_str(stmt.name)

            # Dizi sahipligi: yalnizca heap'te ayrilmis diziler (literal degil).
            if t == '%struct.ax_array' and val_reg is not None:
                from axiom.ast_nodes import ArrayLiteral as _AL
                ann = stmt.type_annotation or ''
                inf = getattr(stmt.initializer, 'inferred_type', None) or ann
                elem_t = inf[:-2] if inf.endswith('[]') else 'int'
                if not isinstance(stmt.initializer, _AL):
                    if self._is_borrowed_str_expr(stmt.initializer):
                        # Alias: ayni tamponu iki degisken gostermesin diye
                        # kopyalamak yerine sahipligi paylasmiyoruz; escape say.
                        self.escaped_array_vars.add(stmt.name)
                    else:
                        self._mark_owned_array(stmt.name, elem_t)

            if self.debug and self.current_scope_id is not None:
                basic = {'i64': 8, 'double': 9, 'i1': 10, 'i8*': 11}
                type_id = basic.get(t, 8)
                var_id = self.meta_counter
                self.meta_counter += 1
                self.local_vars.append((var_id, stmt.name, getattr(stmt, 'line', self.current_line), self.current_scope_id, type_id))
                self.code.append(
                    f"    call void @llvm.dbg.declare(metadata {t}* {ptr}, metadata !{var_id}, metadata !DIExpression()), !dbg !{self._current_loc_id()}"
                )

        elif isinstance(stmt, AssignStmt):
            if ((stmt.name in self.str_var_scope or stmt.name in self.array_var_scope)
                    and not (isinstance(stmt.value, Identifier) and stmt.value.name == stmt.name)):
                self._mark_escape(stmt.value)
            val_t, val_reg = self.generate_expr(stmt.value)
            if stmt.name in self.variables:
                t, ptr = self.variables[stmt.name]
                if t == 'double' and val_t == 'i64':
                    conv = self.new_reg("sitofp")
                    self.emit_instr(f"{conv} = sitofp i64 {val_reg} to double")
                    val_reg = conv
                    val_t = 'double'
                elif t == 'i64' and val_t == 'double':
                    conv = self.new_reg("fptosi")
                    self.emit_instr(f"{conv} = fptosi double {val_reg} to i64")
                    val_reg = conv
                    val_t = 'i64'

                if t == 'i8*' and stmt.name in self.str_var_scope:
                    same_var = isinstance(stmt.value, Identifier) and stmt.value.name == stmt.name
                    if not same_var:
                        if self._is_borrowed_str_expr(stmt.value):
                            self.emit_instr(f"call void @axiom_str_retain(i8* {val_reg})")
                        old_val = self.new_reg("oldstr")
                        self.emit_instr(f"{old_val} = load i8*, i8** {ptr}, align 8")
                        self.emit_instr(f"call void @axiom_str_release(i8* {old_val})")
                if t == '%struct.ax_array' and stmt.name in self.array_var_scope:
                    same_arr = isinstance(stmt.value, Identifier) and stmt.value.name == stmt.name
                    if not same_arr:
                        old_arr = self.new_reg("oldarr")
                        self.emit_instr(f"{old_arr} = load %struct.ax_array, %struct.ax_array* {ptr}, align 8")
                        slot = self.new_reg("oldarrp")
                        self.emit_instr(f"{slot} = alloca %struct.ax_array, align 8")
                        self.emit_instr(f"store %struct.ax_array {old_arr}, %struct.ax_array* {slot}, align 8")
                        elem_t = self.array_elem_types.get(stmt.name, 'int')
                        free_fn = {
                            'str': '@axiom_array_str_free',
                            'int': '@axiom_array_int_free',
                            'float': '@axiom_array_float_free',
                            'bool': '@axiom_array_bool_free',
                        }.get(elem_t)
                        if free_fn:
                            self.emit_instr(f"call void {free_fn}(%struct.ax_array* {slot})")
                self.emit_instr(f"store {t} {val_reg}, {t}* {ptr}, align 8")
            elif isinstance(stmt.target, IndexAccess):
                # Array element store
                arr_t, arr_reg = self.generate_expr(stmt.target.array)
                idx_t, idx_reg = self.generate_expr(stmt.target.index)
                len_reg = self.new_reg("arr_len")
                self.emit_instr(f"{len_reg} = extractvalue %struct.ax_array {arr_reg}, 0")
                checked_idx = self.new_reg("checked_idx")
                self.emit_instr(f"{checked_idx} = call i64 @axiom_bounds_check(i64 {idx_reg}, i64 {len_reg}, i8* null, i64 0)")
                # extract data pointer from array struct
                data_ptr = self.new_reg("arr_data")
                self.emit_instr(f"{data_ptr} = extractvalue %struct.ax_array {arr_reg}, 2")
                elem_ptr = self.new_reg("elem_ptr")
                self.emit_instr(f"{elem_ptr} = getelementptr inbounds i64, i64* {data_ptr}, i64 {checked_idx}")
                self.emit_instr(f"store i64 {val_reg}, i64* {elem_ptr}, align 8")

        elif isinstance(stmt, ReturnStmt):
            ret_target_t = llvm_type(self.current_function.return_type) if (self.current_function and self.current_function.return_type) else None
            val_t = None
            val_reg = None
            if stmt.value:
                val_t, val_reg = self.generate_expr(stmt.value)
                if ret_target_t and ret_target_t != val_t:
                    if ret_target_t == 'double' and val_t == 'i64':
                        conv = self.new_reg("sitofp")
                        self.emit_instr(f"{conv} = sitofp i64 {val_reg} to double")
                        val_reg = conv
                        val_t = 'double'
                    elif ret_target_t == 'i64' and val_t == 'double':
                        conv = self.new_reg("fptosi")
                        self.emit_instr(f"{conv} = fptosi double {val_reg} to i64")
                        val_reg = conv
                        val_t = 'i64'

            # Ensures contract checks
            if self.current_function and self.current_function.contract and self.current_function.contract.ensures:
                prev_return_var = self.variables.get('return')
                if val_reg is not None:
                    ret_slot = self.new_reg("ret_slot")
                    self.emit_instr(f"{ret_slot} = alloca {val_t}, align 8")
                    self.emit_instr(f"store {val_t} {val_reg}, {val_t}* {ret_slot}, align 8")
                    self.variables['return'] = (val_t, ret_slot)

                for ens in self.current_function.contract.ensures:
                    cond_ty, cond_reg = self.generate_expr(ens)
                    then_lbl = self.new_label("ens_ok")
                    fail_lbl = self.new_label("ens_fail")
                    self.emit_instr(f"br i1 {cond_reg}, label %{then_lbl}, label %{fail_lbl}")
                    self.emit(f"{fail_lbl}:")
                    err_ptr, _ = self.get_string_ptr("\n[AXIOM GUVENLIK IHLALI] Sozlesme ihlali!\n")
                    self.emit_instr(f"call i32 @puts(i8* {err_ptr})")
                    self.emit_instr("call void @exit(i32 101)")
                    self.emit_instr("unreachable")
                    self.emit(f"{then_lbl}:")

                if prev_return_var is not None:
                    self.variables['return'] = prev_return_var
                else:
                    self.variables.pop('return', None)

            # Donen deger sahipli bir str degiskeni ise caller icin retain et.
            if (ret_target_t == 'i8*' and val_reg is not None
                    and isinstance(stmt.value, Identifier)
                    and stmt.value.name in self.str_var_scope):
                self.emit_instr(f"call void @axiom_str_retain(i8* {val_reg})")
            elif stmt.value is not None:
                # Donen ifade bir struct/Result icine string tasiyabilir
                # (orn. `return result_err_str(pre)`). Bu durumda `pre`
                # kacar; blok sonunda birakilirsa dangling pointer olur.
                self._mark_escape(stmt.value)

            self._emit_deferred_all()
            if val_reg is not None:
                self._emit_all_str_releases()
            if val_reg is not None:
                self.emit_instr(f"ret {val_t} {val_reg}")
            else:
                self.emit_instr("ret void")
            self.block_terminated = True

        elif isinstance(stmt, PrintStmt):
            for i, arg in enumerate(stmt.args):
                is_last = (i == len(stmt.args) - 1)
                t, val = self.generate_expr(arg)

                if t == 'i64':
                    fmt_str = "%ld\n" if is_last else "%ld "
                    fmt_ptr, _ = self.get_string_ptr(fmt_str)
                    call_res = self.new_reg("pcall")
                    self.emit_instr(f"{call_res} = call i32 (i8*, ...) @printf(i8* {fmt_ptr}, i64 {val})")
                elif t == 'double':
                    fmt_str = "%g\n" if is_last else "%g "
                    fmt_ptr, _ = self.get_string_ptr(fmt_str)
                    call_res = self.new_reg("pcall")
                    self.emit_instr(f"{call_res} = call i32 (i8*, ...) @printf(i8* {fmt_ptr}, double {val})")
                elif t == 'i1':
                    true_str = "true\n" if is_last else "true "
                    false_str = "false\n" if is_last else "false "
                    true_ptr, _ = self.get_string_ptr(true_str)
                    false_ptr, _ = self.get_string_ptr(false_str)
                    chosen_ptr = self.new_reg("bool_str")
                    self.emit_instr(f"{chosen_ptr} = select i1 {val}, i8* {true_ptr}, i8* {false_ptr}")
                    call_res = self.new_reg("pcall")
                    self.emit_instr(f"{call_res} = call i32 (i8*, ...) @printf(i8* {chosen_ptr})")
                elif t == 'i8*':
                    fmt_str = "%s\n" if is_last else "%s "
                    fmt_ptr, _ = self.get_string_ptr(fmt_str)
                    call_res = self.new_reg("pcall")
                    self.emit_instr(f"{call_res} = call i32 (i8*, ...) @printf(i8* {fmt_ptr}, i8* {val})")
                elif t == '%struct.ax_array':
                    len_val = self.new_reg("arr_len")
                    self.emit_instr(f"{len_val} = extractvalue %struct.ax_array {val}, 0")
                    fmt_ptr, _ = self.get_string_ptr("<array length=%ld>\n")
                    call_res = self.new_reg("pcall")
                    self.emit_instr(f"{call_res} = call i32 (i8*, ...) @printf(i8* {fmt_ptr}, i64 {len_val})")

            if not stmt.args:
                nl_ptr, _ = self.get_string_ptr("\n")
                call_res = self.new_reg("pcall")
                self.emit_instr(f"{call_res} = call i32 (i8*, ...) @printf(i8* {nl_ptr})")

        elif isinstance(stmt, VerifyStmt):
            cond_t, cond_reg = self.generate_expr(stmt.condition)
            ok_lbl = self.new_label("verify_ok")
            fail_lbl = self.new_label("verify_fail")
            self.emit_instr(f"br i1 {cond_reg}, label %{ok_lbl}, label %{fail_lbl}")

            self.emit(f"{fail_lbl}:")
            err_ptr, _ = self.get_string_ptr("\n[AXIOM GUVENLIK IHLALI] 'verify' sozlesmesi ihlal edildi!\n")
            self.emit_instr(f"call i32 @puts(i8* {err_ptr})")
            self.emit_instr("call void @exit(i32 101)")
            self.emit_instr("unreachable")

            self.emit(f"{ok_lbl}:")

        elif isinstance(stmt, IfStmt):
            cond_t, cond_reg = self.generate_expr(stmt.condition)
            then_lbl = self.new_label("then")
            else_lbl = self.new_label("else")
            merge_lbl = self.new_label("merge")

            has_else = (stmt.else_branch is not None)
            target_else = else_lbl if has_else else merge_lbl

            self.emit_instr(f"br i1 {cond_reg}, label %{then_lbl}, label %{target_else}")

            # Then
            self.emit(f"{then_lbl}:")
            self.block_terminated = False
            self._push_str_scope()
            for s in stmt.then_branch.statements:
                self.generate_stmt(s)
            if not self.block_terminated:
                self._pop_str_scope()
                self.emit_instr(f"br label %{merge_lbl}")
            else:
                self.owned_str_stack.pop()
            then_terminated = self.block_terminated

            # Else
            else_terminated = False
            if has_else:
                self.emit(f"{else_lbl}:")
                self.block_terminated = False
                self._push_str_scope()
                for s in stmt.else_branch.statements:
                    self.generate_stmt(s)
                if not self.block_terminated:
                    self._pop_str_scope()
                    self.emit_instr(f"br label %{merge_lbl}")
                else:
                    self.owned_str_stack.pop()
                else_terminated = self.block_terminated

            # Merge
            if not has_else:
                self.emit(f"{merge_lbl}:")
                self.block_terminated = False
            elif not (then_terminated and else_terminated):
                self.emit(f"{merge_lbl}:")
                self.block_terminated = False
            else:
                self.block_terminated = True

        elif isinstance(stmt, WhileStmt):
            cond_lbl = self.new_label("while_cond")
            body_lbl = self.new_label("while_body")
            end_lbl = self.new_label("while_end")

            self.emit_instr(f"br label %{cond_lbl}")
            self.emit(f"{cond_lbl}:")
            self.block_terminated = False
            cond_t, cond_reg = self.generate_expr(stmt.condition)
            self.emit_instr(f"br i1 {cond_reg}, label %{body_lbl}, label %{end_lbl}")

            self.emit(f"{body_lbl}:")
            self.block_terminated = False
            self._push_str_scope()
            self.loop_stack.append((cond_lbl, end_lbl))
            for s in stmt.body.statements:
                self.generate_stmt(s)
            self.loop_stack.pop()
            if not self.block_terminated:
                self._pop_str_scope()
                self.emit_instr(f"br label %{cond_lbl}")
            else:
                self.owned_str_stack.pop()
                if self.owned_array_stack:
                    self.owned_array_stack.pop()

            self.emit(f"{end_lbl}:")
            self.block_terminated = False

        elif isinstance(stmt, ForRangeStmt):
            # Allocate loop var
            var_ptr = self.new_reg(f"for.{stmt.var_name}")
            self.emit_instr(f"{var_ptr} = alloca i64, align 8")
            self.variables[stmt.var_name] = ('i64', var_ptr)

            start_t, start_reg = self.generate_expr(stmt.start)
            end_t, end_reg = self.generate_expr(stmt.end)
            self.emit_instr(f"store i64 {start_reg}, i64* {var_ptr}, align 8")

            cond_lbl = self.new_label("for_cond")
            body_lbl = self.new_label("for_body")
            end_lbl = self.new_label("for_end")

            self.emit_instr(f"br label %{cond_lbl}")
            self.emit(f"{cond_lbl}:")
            self.block_terminated = False
            cur_val = self.new_reg("cur_i")
            self.emit_instr(f"{cur_val} = load i64, i64* {var_ptr}, align 8")
            cmp_res = self.new_reg("cmp")
            self.emit_instr(f"{cmp_res} = icmp slt i64 {cur_val}, {end_reg}")
            self.emit_instr(f"br i1 {cmp_res}, label %{body_lbl}, label %{end_lbl}")

            cont_lbl = self.new_label("for_inc")
            self.emit(f"{body_lbl}:")
            self.block_terminated = False
            self._push_str_scope()
            self.loop_stack.append((cont_lbl, end_lbl))
            for s in stmt.body.statements:
                self.generate_stmt(s)
            self.loop_stack.pop()
            if not self.block_terminated:
                self._pop_str_scope()
                self.emit_instr(f"br label %{cont_lbl}")
            else:
                self.owned_str_stack.pop()
                if self.owned_array_stack:
                    self.owned_array_stack.pop()

            self.emit(f"{cont_lbl}:")
            self.block_terminated = False
            next_val = self.new_reg("next_i")
            self.emit_instr(f"{next_val} = add i64 {cur_val}, 1")
            self.emit_instr(f"store i64 {next_val}, i64* {var_ptr}, align 8")
            self.emit_instr(f"br label %{cond_lbl}")

            self.emit(f"{end_lbl}:")
            self.block_terminated = False

        elif isinstance(stmt, MatchStmt):
            subj_t, subj_val = self.generate_expr(stmt.subject)
            end_lbl = self.new_label("match.end")

            for arm in stmt.arms:
                arm_body_lbl = self.new_label("match.arm")
                next_arm_lbl = self.new_label("match.next")

                if isinstance(arm.pattern, (WildcardPattern, IdentPattern)):
                    cond_val = "1"
                elif isinstance(arm.pattern, LiteralPattern):
                    lit_t, lit_val = self.generate_expr(arm.pattern.literal)
                    cmp_reg = self.new_reg("match_cmp")
                    if subj_t == 'double':
                        self.emit_instr(f"{cmp_reg} = fcmp oeq double {subj_val}, {lit_val}")
                    elif subj_t == 'i8*':
                        strcmp_res = self.new_reg("scmp")
                        self.emit_instr(f"{strcmp_res} = call i32 @strcmp(i8* {subj_val}, i8* {lit_val})")
                        self.emit_instr(f"{cmp_reg} = icmp eq i32 {strcmp_res}, 0")
                    else:
                        self.emit_instr(f"{cmp_reg} = icmp eq {subj_t} {subj_val}, {lit_val}")
                    cond_val = cmp_reg

                if arm.guard:
                    guard_t, guard_val = self.generate_expr(arm.guard)
                    if cond_val == "1":
                        cond_val = guard_val
                    else:
                        and_reg = self.new_reg("guard_and")
                        self.emit_instr(f"{and_reg} = and i1 {cond_val}, {guard_val}")
                        cond_val = and_reg

                if cond_val == "1":
                    self.emit_instr(f"br label %{arm_body_lbl}")
                else:
                    self.emit_instr(f"br i1 {cond_val}, label %{arm_body_lbl}, label %{next_arm_lbl}")

                self.emit(f"{arm_body_lbl}:")
                self.block_terminated = False

                if isinstance(arm.pattern, IdentPattern):
                    var_ptr = self.new_reg(f"var.{arm.pattern.name}")
                    self.emit_instr(f"{var_ptr} = alloca {subj_t}, align 8")
                    self.emit_instr(f"store {subj_t} {subj_val}, {subj_t}* {var_ptr}, align 8")
                    self.variables[arm.pattern.name] = (subj_t, var_ptr)

                if isinstance(arm.body, Block):
                    for s in arm.body.statements:
                        self.generate_stmt(s)
                elif isinstance(arm.body, Stmt):
                    self.generate_stmt(arm.body)
                elif isinstance(arm.body, Expr):
                    self.generate_expr(arm.body)

                if not self.block_terminated:
                    self.emit_instr(f"br label %{end_lbl}")

                self.emit(f"{next_arm_lbl}:")
                self.block_terminated = False

            if not self.block_terminated:
                self.emit_instr(f"br label %{end_lbl}")

            self.emit(f"{end_lbl}:")
            self.block_terminated = False

        elif isinstance(stmt, ExprStmt):
            self.generate_expr(stmt.expr)

    def _struct_field_indices(self, type_name: str):
        """Struct tipinin (is_ok, value, error) alan indekslerini dondurur.

        Alan sirasi kullanici struct'inda farkli olabilecegi icin LLVM IR'de
        sabit indeks kullanmak yanlistir.
        """
        base = type_name
        decl = self.struct_defs.get(base)
        if decl is None:
            return None
        names = [f.name for f in decl.fields]
        try:
            return (names.index('is_ok'), names.index('value'), names.index('error'))
        except ValueError:
            return None

    def _generate_try_expr(self, expr: TryExpr) -> Tuple[str, str]:
        """`?` operatou: Ok ise degeri acar, Err ise ust fonksiyona iletir."""
        src_t = getattr(expr, 'try_source_type', None)
        dst_t = getattr(expr, 'try_target_type', None)
        if not src_t or not dst_t:
            raise RuntimeError("'?' ifadesi tip denetiminden gecmemis")

        idx = self._struct_field_indices(src_t)
        dst_idx = self._struct_field_indices(dst_t)
        if idx is None or dst_idx is None:
            raise NotImplementedError(
                f"'?' LLVM arka ucunda yalnizca struct Result tipleriyle calisir "
                f"('{src_t}' / '{dst_t}')."
            )
        ok_i, val_i, err_i = idx
        d_ok_i, d_val_i, d_err_i = dst_idx

        src_ll = llvm_type(src_t)
        dst_ll = llvm_type(dst_t)
        # Acalan deger KAYNAGIN T'sidir; hedefin T'si yalnizca hata struct'inin
        # 'value' alanini sifirlamak icin kullanilir.
        val_ll = llvm_type(getattr(expr, 'try_value_type', 'int'))
        dst_val_ll = llvm_type(getattr(expr, 'try_target_value_type', None)
                               or getattr(expr, 'try_value_type', 'int'))

        inner_t, inner_reg = self.generate_expr(expr.expr)
        if inner_t != src_ll:
            raise RuntimeError(f"'?' ic ifade tipi uyusmuyor: {inner_t} != {src_ll}")

        slot = self.new_reg("try_val")
        self.emit_instr(f"{slot} = alloca {val_ll}, align 8")
        self.emit_instr(f"store {val_ll} zeroinitializer, {val_ll}* {slot}, align 8")

        is_ok = self.new_reg("try_ok")
        self.emit_instr(f"{is_ok} = extractvalue {src_ll} {inner_reg}, {ok_i}")

        ok_lbl = self.new_label("try.ok")
        err_lbl = self.new_label("try.err")
        end_lbl = self.new_label("try.end")
        self.emit_instr(f"br i1 {is_ok}, label %{ok_lbl}, label %{err_lbl}")

        # --- Ok dali ---
        self.emit(f"{ok_lbl}:")
        self.block_terminated = False
        ok_val = self.new_reg("try_v")
        self.emit_instr(f"{ok_val} = extractvalue {src_ll} {inner_reg}, {val_i}")
        self.emit_instr(f"store {val_ll} {ok_val}, {val_ll}* {slot}, align 8")
        self.emit_instr(f"br label %{end_lbl}")

        # --- Err dali: hedef Result'i insa et ve dondur ---
        self.emit(f"{err_lbl}:")
        self.block_terminated = False
        err_val = self.new_reg("try_err")
        self.emit_instr(f"{err_val} = extractvalue {src_ll} {inner_reg}, {err_i}")

        acc = self.new_reg("try_s0")
        self.emit_instr(f"{acc} = insertvalue {dst_ll} undef, i1 false, {d_ok_i}")
        acc2 = self.new_reg("try_s1")
        self.emit_instr(f"{acc2} = insertvalue {dst_ll} {acc}, {dst_val_ll} zeroinitializer, {d_val_i}")
        acc3 = self.new_reg("try_s2")
        err_t_ll = llvm_type(self.struct_defs[dst_t].fields[d_err_i].type_name)
        self.emit_instr(f"{acc3} = insertvalue {dst_ll} {acc2}, {err_t_ll} {err_val}, {d_err_i}")
        self._emit_deferred_all()
        self.emit_instr(f"ret {dst_ll} {acc3}")
        self.block_terminated = True

        # --- Birlesme ---
        self.emit(f"{end_lbl}:")
        self.block_terminated = False
        res = self.new_reg("try_res")
        self.emit_instr(f"{res} = load {val_ll}, {val_ll}* {slot}, align 8")
        return (val_ll, res)

    def generate_expr(self, expr: Expr) -> Tuple[str, str]:
        if hasattr(expr, 'line') and expr.line:
            self.current_line = expr.line
        if hasattr(expr, 'column') and expr.column:
            self.current_col = expr.column
        elif hasattr(expr, 'col') and expr.col:
            self.current_col = expr.col

        if isinstance(expr, TryExpr):
            return self._generate_try_expr(expr)

        if isinstance(expr, NumberLiteral):
            if expr.is_float or isinstance(expr.value, float):
                return ('double', str(float(expr.value)))
            return ('i64', str(int(expr.value)))

        elif isinstance(expr, BooleanLiteral):
            return ('i1', '1' if expr.value else '0')

        elif isinstance(expr, StringLiteral):
            ptr, _ = self.get_string_ptr(expr.value)
            return ('i8*', ptr)

        elif isinstance(expr, Identifier):
            if expr.name in self.variables:
                t, ptr = self.variables[expr.name]
                reg = self.new_reg(expr.name)
                self.emit_instr(f"{reg} = load {t}, {t}* {ptr}, align 8")
                return (t, reg)
            return ('i64', '0')

        elif isinstance(expr, UnaryOp):
            t, op_reg = self.generate_expr(expr.operand)
            if expr.op == '-':
                reg = self.new_reg("neg")
                if t == 'double':
                    self.emit_instr(f"{reg} = fsub double 0.0, {op_reg}")
                else:
                    self.emit_instr(f"{reg} = sub i64 0, {op_reg}")
                return (t, reg)
            elif expr.op in ('not', '!'):
                reg = self.new_reg("not")
                self.emit_instr(f"{reg} = xor i1 {op_reg}, 1")
                return ('i1', reg)

        elif isinstance(expr, CastExpr):
            src_t, reg = self.generate_expr(expr.expr)
            dst_t = llvm_type(expr.target_type)
            if src_t == dst_t:
                return (dst_t, reg)
            cast_reg = self.new_reg("cast")
            if src_t == 'double' and dst_t == 'i64':
                self.emit_instr(f"{cast_reg} = fptosi double {reg} to i64")
            elif src_t == 'i64' and dst_t == 'double':
                self.emit_instr(f"{cast_reg} = sitofp i64 {reg} to double")
            elif src_t == 'i1' and dst_t == 'i64':
                self.emit_instr(f"{cast_reg} = zext i1 {reg} to i64")
            elif src_t == 'i64' and dst_t == 'i1':
                self.emit_instr(f"{cast_reg} = icmp ne i64 {reg}, 0")
            else:
                return (src_t, reg)
            return (dst_t, cast_reg)

        elif isinstance(expr, BinaryOp):
            left_t, left_reg = self.generate_expr(expr.left)
            right_t, right_reg = self.generate_expr(expr.right)
            op = expr.op

            # Boolean logic
            if op in ('and', '&&'):
                reg = self.new_reg("and")
                self.emit_instr(f"{reg} = and i1 {left_reg}, {right_reg}")
                return ('i1', reg)
            elif op in ('or', '||'):
                reg = self.new_reg("or")
                self.emit_instr(f"{reg} = or i1 {left_reg}, {right_reg}")
                return ('i1', reg)

            # String equality
            if left_t == 'i8*' and right_t == 'i8*':
                if op in ('==', '==='):
                    reg = self.new_reg("streq")
                    self.emit_instr(f"{reg} = call i1 @axiom_str_eq(i8* {left_reg}, i8* {right_reg})")
                    return ('i1', reg)
                elif op in ('!=', '!=='):
                    reg = self.new_reg("strneq")
                    self.emit_instr(f"{reg} = call i1 @axiom_str_neq(i8* {left_reg}, i8* {right_reg})")
                    return ('i1', reg)
                elif op == '+':
                    reg = self.new_reg("concat")
                    self.emit_instr(f"{reg} = call i8* @axiom_str_concat(i8* {left_reg}, i8* {right_reg})")
                    return ('i8*', reg)

            # Floating point arithmetic
            if left_t == 'double' or right_t == 'double':
                if left_t == 'i64':
                    conv_reg = self.new_reg("sitofp")
                    self.emit_instr(f"{conv_reg} = sitofp i64 {left_reg} to double")
                    left_reg = conv_reg
                    left_t = 'double'
                elif left_t == 'i1':
                    conv_reg = self.new_reg("uitofp")
                    self.emit_instr(f"{conv_reg} = uitofp i1 {left_reg} to double")
                    left_reg = conv_reg
                    left_t = 'double'

                if right_t == 'i64':
                    conv_reg = self.new_reg("sitofp")
                    self.emit_instr(f"{conv_reg} = sitofp i64 {right_reg} to double")
                    right_reg = conv_reg
                    right_t = 'double'
                elif right_t == 'i1':
                    conv_reg = self.new_reg("uitofp")
                    self.emit_instr(f"{conv_reg} = uitofp i1 {right_reg} to double")
                    right_reg = conv_reg
                    right_t = 'double'

                op_map = {'+': 'fadd', '-': 'fsub', '*': 'fmul', '/': 'fdiv'}
                if op in op_map:
                    reg = self.new_reg("fop")
                    self.emit_instr(f"{reg} = {op_map[op]} double {left_reg}, {right_reg}")
                    return ('double', reg)
                cmp_map = {'<': 'olt', '<=': 'ole', '>': 'ogt', '>=': 'oge', '==': 'oeq', '!=': 'one'}
                if op in cmp_map:
                    reg = self.new_reg("fcmp")
                    self.emit_instr(f"{reg} = fcmp {cmp_map[op]} double {left_reg}, {right_reg}")
                    return ('i1', reg)

            # Integer arithmetic & comparisons
            arith_map = {'+': 'add', '-': 'sub', '*': 'mul', '/': 'sdiv', '%': 'srem'}
            if op in arith_map:
                reg = self.new_reg("iop")
                self.emit_instr(f"{reg} = {arith_map[op]} i64 {left_reg}, {right_reg}")
                return ('i64', reg)

            cmp_map = {'<': 'slt', '<=': 'sle', '>': 'sgt', '>=': 'sge', '==': 'eq', '!=': 'ne'}
            if op in cmp_map:
                reg = self.new_reg("icmp")
                t = 'i1' if (left_t == 'i1' and right_t == 'i1') else 'i64'
                self.emit_instr(f"{reg} = icmp {cmp_map[op]} {t} {left_reg}, {right_reg}")
                return ('i1', reg)

        elif isinstance(expr, FunctionCall):
            # array_push(arr, elem) -> yeni %struct.ax_array (LLVM icinde satir ici)
            if expr.callee == 'array_push' and len(expr.args) == 2:
                arr_t, arr_reg = self.generate_expr(expr.args[0])
                elem_t, elem_reg = self.generate_expr(expr.args[1])
                if arr_t != '%struct.ax_array':
                    return (arr_t, arr_reg)

                idx_t = self.new_reg("apush_len")
                self.emit_instr(f"{idx_t} = extractvalue %struct.ax_array {arr_reg}, 0")
                data_t = self.new_reg("apush_data")
                self.emit_instr(f"{data_t} = extractvalue %struct.ax_array {arr_reg}, 2")
                new_len = self.new_reg("apush_nlen")
                self.emit_instr(f"{new_len} = add i64 {idx_t}, 1")

                scalar_size = {'i64': 8, 'double': 8, 'i8*': 8, 'i1': 1}.get(elem_t)
                if scalar_size is not None:
                    elem_size = str(scalar_size)
                else:
                    # struct veya bilinmeyen tip: sizeof'u GEP null ile hesapla
                    sz_ptr = self.new_reg("apush_szptr")
                    self.emit_instr(f"{sz_ptr} = getelementptr {elem_t}, {elem_t}* null, i64 1")
                    elem_size_reg = self.new_reg("apush_sz")
                    self.emit_instr(f"{elem_size_reg} = ptrtoint {elem_t}* {sz_ptr} to i64")
                    elem_size = elem_size_reg

                total = self.new_reg("apush_total")
                self.emit_instr(f"{total} = mul i64 {new_len}, {elem_size}")
                new_i8 = self.new_reg("apush_buf")
                self.emit_instr(f"{new_i8} = call i8* @malloc(i64 {total})")
                old_bytes = self.new_reg("apush_oldbytes")
                self.emit_instr(f"{old_bytes} = mul i64 {idx_t}, {elem_size}")
                old_i8 = self.new_reg("apush_oldi8")
                self.emit_instr(f"{old_i8} = bitcast i64* {data_t} to i8*")
                self.emit_instr(f"call i8* @memcpy(i8* {new_i8}, i8* {old_i8}, i64 {old_bytes})")
                # str elemani diziye konurken bir referans DAHA alinmali;
                # aksi halde kaynak kapsam kapaninca dizi ogesi dangle kalir.
                if elem_t == 'i8*':
                    self.emit_instr(f"call void @axiom_str_retain(i8* {elem_reg})")
                typed_base = self.new_reg("apush_base")
                self.emit_instr(f"{typed_base} = bitcast i8* {new_i8} to {elem_t}*")
                elem_ptr = self.new_reg("apush_eptr")
                self.emit_instr(f"{elem_ptr} = getelementptr {elem_t}, {elem_t}* {typed_base}, i64 {idx_t}")
                self.emit_instr(f"store {elem_t} {elem_reg}, {elem_t}* {elem_ptr}, align 8")
                new_data_i64 = self.new_reg("apush_data64")
                self.emit_instr(f"{new_data_i64} = bitcast {elem_t}* {typed_base} to i64*")
                r0 = self.new_reg("apush_r0")
                self.emit_instr(f"{r0} = insertvalue %struct.ax_array undef, i64 {new_len}, 0")
                rc = self.new_reg("apush_rc")
                self.emit_instr(f"{rc} = insertvalue %struct.ax_array {r0}, i64 {new_len}, 1")
                r1 = self.new_reg("apush_r1")
                self.emit_instr(f"{r1} = insertvalue %struct.ax_array {rc}, i64* {new_data_i64}, 2")
                return ('%struct.ax_array', r1)

            # thread_create(fn, arg) -> i64 @axiom_thread_create(i8*, i64, i1)
            if expr.callee == 'thread_create' and len(expr.args) == 2 and isinstance(expr.args[0], Identifier):
                fn_name = expr.args[0].name
                arg_t, arg_reg = self.generate_expr(expr.args[1])
                if arg_t != 'i64':
                    cvt = self.new_reg("thr_arg")
                    if arg_t == 'double':
                        self.emit_instr(f"{cvt} = fptosi double {arg_reg} to i64")
                    elif arg_t == 'i1':
                        self.emit_instr(f"{cvt} = zext i1 {arg_reg} to i64")
                    else:
                        self.emit_instr(f"{cvt} = ptrtoint i8* {arg_reg} to i64")
                    arg_reg = cvt
                ret_ty = self.function_return_types.get(fn_name, 'int')
                if ret_ty == 'void':
                    fn_ptr = self.new_reg("thr_fn")
                    self.emit_instr(f"{fn_ptr} = bitcast void (i64)* @{llvm_fn_symbol(fn_name, ['i64'], fn_name in self.overloaded_fns)} to i8*")
                    thr = self.new_reg("thr")
                    self.emit_instr(f"{thr} = call i64 @axiom_thread_create(i8* {fn_ptr}, i64 {arg_reg}, i1 true)")
                else:
                    fn_ptr = self.new_reg("thr_fn")
                    self.emit_instr(f"{fn_ptr} = bitcast i64 (i64)* @{llvm_fn_symbol(fn_name, ['i64'], fn_name in self.overloaded_fns)} to i8*")
                    thr = self.new_reg("thr")
                    self.emit_instr(f"{thr} = call i64 @axiom_thread_create(i8* {fn_ptr}, i64 {arg_reg}, i1 false)")
                return ('i64', thr)

            # Builtin len(...)
            if expr.callee == 'len' and len(expr.args) == 1:
                t, arg_reg = self.generate_expr(expr.args[0])
                len_reg = self.new_reg("len")
                if t == 'i8*':
                    self.emit_instr(f"{len_reg} = call i64 @axiom_str_len(i8* {arg_reg})")
                    return ('i64', len_reg)
                else:
                    self.emit_instr(f"{len_reg} = extractvalue %struct.ax_array {arg_reg}, 0")
                    return ('i64', len_reg)

            # Evaluate args
            arg_vals = []
            for a in expr.args:
                at, areg = self.generate_expr(a)
                arg_vals.append((at, areg))

            args_str = ", ".join(f"{t} {r}" for t, r in arg_vals)

            # Check builtins
            builtin_map = {
                'tcp_connect': ('i64', '@axiom_tcp_connect'),
                'tcp_send': ('i64', '@axiom_tcp_send'),
                'tcp_recv': ('i8*', '@axiom_tcp_recv'),
                'socket_close': ('void', '@axiom_socket_close'),
                'time_now_ms': ('i64', '@axiom_time_now_ms'),
                'file_read': ('i8*', '@axiom_file_read'),
                'file_write': ('i1', '@axiom_file_write'),
                'file_exists': ('i1', '@axiom_file_exists'),
                'file_size': ('i64', '@axiom_file_size'),
                'is_directory': ('i1', '@axiom_is_directory'),
                'list_dir': ('i8*', '@axiom_list_dir'),
                'remove_file': ('i1', '@axiom_remove_file'),
                'rename_file': ('i1', '@axiom_rename_file'),
                'create_dir': ('i1', '@axiom_create_dir'),
                'os_exec': ('i64', '@axiom_os_exec'),
                'os_exec_argv': ('i64', '@axiom_os_exec_argv_ptr'),
                'rt_os_exec_argv': ('i64', '@axiom_os_exec_argv'),
                'os_getenv': ('i8*', '@axiom_os_getenv'),
                'str_contains': ('i1', '@axiom_str_contains'),
                'str_starts_with': ('i1', '@axiom_str_starts_with'),
                'str_ends_with': ('i1', '@axiom_str_ends_with'),
                'str_trim': ('i8*', '@axiom_str_trim'),
                'str_join': ('i8*', '@axiom_str_join_ptr'),
                'rt_str_join': ('i8*', '@axiom_str_join_ptr'),
                'str_len': ('i64', '@axiom_str_len'),
                'rt_str_len': ('i64', '@axiom_str_len'),
                'str_byte_len': ('i64', '@axiom_str_byte_len'),
                'rt_str_byte_len': ('i64', '@axiom_str_byte_len'),
                'str_to_int': ('i64', '@axiom_str_to_int'),
                'int_to_str': ('i8*', '@axiom_int_to_str'),
                'math_abs': ('i64', '@axiom_math_abs'),
                'math_min': ('i64', '@axiom_math_min'),
                'math_max': ('i64', '@axiom_math_max'),
                'math_pow': ('i64', '@axiom_math_pow'),
                'thread_join': ('i64', '@axiom_thread_join'),
                'mutex_init': ('i64', '@axiom_mutex_init'),
                'mutex_lock': ('void', '@axiom_mutex_lock'),
                'mutex_unlock': ('void', '@axiom_mutex_unlock'),
                'atomic_init': ('i64', '@axiom_atomic_init'),
                'atomic_add': ('i64', '@axiom_atomic_add'),
                'atomic_get': ('i64', '@axiom_atomic_get'),
                'sleep_ms': ('void', '@axiom_sleep_ms'),
                'simd_add_i64': ('%struct.ax_array', '@axiom_simd_add_i64_ptr'),
                'simd_mul_i64': ('%struct.ax_array', '@axiom_simd_mul_i64_ptr'),
                'simd_sub_i64': ('%struct.ax_array', '@axiom_simd_sub_i64_ptr'),
                'simd_sum_i64': ('i64', '@axiom_simd_sum_i64_ptr'),
                'simd_scan_match': ('i64', '@axiom_simd_scan_match_ptr'),
                'rt_base64_encode': ('i8*', '@axiom_base64_encode'),
                'rt_base64_decode': ('i8*', '@axiom_base64_decode'),
                'rt_hex_encode': ('i8*', '@axiom_hex_encode'),
                'rt_hex_decode': ('i8*', '@axiom_hex_decode'),
                'rt_hash_md5': ('i8*', '@axiom_hash_md5'),
                'rt_hash_sha1': ('i8*', '@axiom_hash_sha1'),
                'rt_hash_sha256': ('i8*', '@axiom_hash_sha256'),
                'rt_url_encode': ('i8*', '@axiom_url_encode'),
                'rt_url_decode': ('i8*', '@axiom_url_decode'),
                'rt_url_parse_scheme': ('i8*', '@axiom_url_parse_scheme'),
                'rt_url_parse_host': ('i8*', '@axiom_url_parse_host'),
                'rt_url_parse_port': ('i64', '@axiom_url_parse_port'),
                'rt_url_parse_path': ('i8*', '@axiom_url_parse_path'),
                'rt_url_parse_query': ('i8*', '@axiom_url_parse_query'),
                'rt_json_get_str': ('i8*', '@axiom_json_get_str'),
                'rt_json_get_int': ('i64', '@axiom_json_get_int'),
                'rt_json_get_bool': ('i1', '@axiom_json_get_bool'),
                'rt_json_has_key': ('i1', '@axiom_json_has_key'),
                'rt_json_build_object': ('i8*', '@axiom_json_build_object_ptr'),
                'json_parse': ('i64', '@axiom_json_parse_wrap'),
                'json_free': ('void', '@axiom_json_free'),
                'json_last_error': ('i8*', '@axiom_json_last_error'),
                'json_type_of': ('i64', '@axiom_json_type_of'),
                'json_len': ('i64', '@axiom_json_len'),
                'json_at': ('i64', '@axiom_json_at'),
                'json_key_at': ('i8*', '@axiom_json_key_at'),
                'json_get': ('i64', '@axiom_json_get'),
                'json_path': ('i64', '@axiom_json_path'),
                'json_node_str': ('i8*', '@axiom_json_node_str'),
                'json_node_int': ('i64', '@axiom_json_node_int'),
                'json_node_float': ('double', '@axiom_json_node_float'),
                'json_node_bool': ('i1', '@axiom_json_node_bool'),
                'json_node_is_null': ('i1', '@axiom_json_node_is_null'),
                'tcp_recv_all': ('i8*', '@axiom_tcp_recv_all'),
                'tcp_set_timeout': ('i64', '@axiom_tcp_set_timeout'),
                'http_header_value': ('i8*', '@axiom_http_header_value'),
                'http_chunked_decode': ('i8*', '@axiom_http_chunked_decode'),
                # Packet 2 Builtins: DNS, UDP, HTTP Server, TLS, WebSocket
                'rt_dns_resolve_ipv4': ('i8*', '@axiom_dns_resolve_ipv4'),
                'rt_dns_resolve_ipv6': ('i8*', '@axiom_dns_resolve_ipv6'),
                'rt_dns_reverse_lookup': ('i8*', '@axiom_dns_reverse_lookup'),
                'rt_udp_socket': ('i64', '@axiom_udp_socket'),
                'rt_udp_bind': ('i64', '@axiom_udp_bind'),
                'rt_udp_sendto': ('i64', '@axiom_udp_sendto'),
                'rt_udp_recvfrom': ('i8*', '@axiom_udp_recvfrom'),
                'rt_udp_close': ('void', '@axiom_udp_close'),
                'rt_http_server_create': ('i64', '@axiom_http_server_create'),
                'rt_http_server_accept': ('i64', '@axiom_http_server_accept'),
                'rt_http_server_send_response': ('void', '@axiom_http_server_send_response'),
                'rt_http_server_close': ('void', '@axiom_http_server_close'),
                'rt_tls_connect': ('i64', '@axiom_tls_connect'),
                'rt_tls_send': ('i64', '@axiom_tls_send'),
                'rt_tls_recv': ('i8*', '@axiom_tls_recv'),
                'rt_tls_close': ('void', '@axiom_tls_close'),
                'rt_ws_connect': ('i64', '@axiom_ws_connect'),
                'rt_ws_send': ('i64', '@axiom_ws_send'),
                'rt_ws_recv': ('i8*', '@axiom_ws_recv'),
                'rt_ws_close': ('void', '@axiom_ws_close'),
                # Packet 3 Builtins: Binary Buffer, Process, Zlib, Regex, Map
                'rt_buf_create': ('i64', '@axiom_buf_create'),
                'rt_buf_write_u8': ('void', '@axiom_buf_write_u8'),
                'rt_buf_write_u16_be': ('void', '@axiom_buf_write_u16_be'),
                'rt_buf_write_u16_le': ('void', '@axiom_buf_write_u16_le'),
                'rt_buf_write_u32_be': ('void', '@axiom_buf_write_u32_be'),
                'rt_buf_write_u32_le': ('void', '@axiom_buf_write_u32_le'),
                'rt_buf_write_u64_be': ('void', '@axiom_buf_write_u64_be'),
                'rt_buf_write_u64_le': ('void', '@axiom_buf_write_u64_le'),
                'rt_buf_write_str': ('void', '@axiom_buf_write_str'),
                'rt_buf_to_hex': ('i8*', '@axiom_buf_to_hex'),
                'rt_buf_to_str': ('i8*', '@axiom_buf_to_str'),
                'rt_buf_len': ('i64', '@axiom_buf_len'),
                'rt_buf_from_hex': ('i64', '@axiom_buf_from_hex'),
                'rt_buf_read_u8': ('i64', '@axiom_buf_read_u8'),
                'rt_buf_read_u16_be': ('i64', '@axiom_buf_read_u16_be'),
                'rt_buf_read_u16_le': ('i64', '@axiom_buf_read_u16_le'),
                'rt_buf_read_u32_be': ('i64', '@axiom_buf_read_u32_be'),
                'rt_buf_read_u32_le': ('i64', '@axiom_buf_read_u32_le'),
                'rt_buf_read_u64_be': ('i64', '@axiom_buf_read_u64_be'),
                'rt_buf_read_u64_le': ('i64', '@axiom_buf_read_u64_le'),
                'rt_buf_free': ('void', '@axiom_buf_free'),
                'str_free': ('void', '@axiom_str_free'),
                'rt_str_free': ('void', '@axiom_str_free'),
                'rt_process_exec_output': ('i8*', '@axiom_process_exec_output'),
                'rt_process_get_pid': ('i64', '@axiom_process_get_pid'),
                'rt_process_kill': ('i64', '@axiom_process_kill'),
                'rt_process_spawn_bg': ('i64', '@axiom_process_spawn_bg'),
                'rt_gzip_compress': ('i8*', '@axiom_gzip_compress'),
                'rt_gzip_decompress': ('i8*', '@axiom_gzip_decompress'),
                'rt_zlib_compress_str': ('i8*', '@axiom_zlib_compress_str'),
                'rt_zlib_decompress_str': ('i8*', '@axiom_zlib_decompress_str'),
                'rt_regex_validate': ('i8*', '@axiom_regex_validate'),
                'rt_regex_risk_level': ('i64', '@axiom_regex_risk_level'),
                'rt_regex_is_match': ('i1', '@axiom_regex_is_match'),
                'rt_regex_find': ('i8*', '@axiom_regex_find'),
                'rt_regex_replace': ('i8*', '@axiom_regex_replace'),
                'rt_map_create': ('i64', '@axiom_map_create'),
                'rt_map_set': ('void', '@axiom_map_set'),
                'rt_map_get': ('i8*', '@axiom_map_get'),
                'rt_map_has': ('i1', '@axiom_map_has'),
                'rt_map_delete': ('i1', '@axiom_map_delete'),
                'rt_map_len': ('i64', '@axiom_map_len'),
                'rt_map_free': ('void', '@axiom_map_free'),
                # Packet 4 Builtins: Queue, Fuzzer, Date/Time, CSV, CLI Args
                'rt_queue_create': ('i64', '@axiom_queue_create'),
                'rt_queue_push': ('void', '@axiom_queue_push'),
                'rt_queue_pop': ('i8*', '@axiom_queue_pop'),
                'rt_queue_len': ('i64', '@axiom_queue_len'),
                'rt_queue_is_empty': ('i1', '@axiom_queue_is_empty'),
                'rt_queue_free': ('void', '@axiom_queue_free'),
                'rt_fuzz_replace_marker': ('i8*', '@axiom_fuzz_replace_marker'),
                'rt_fuzz_url_encode': ('i8*', '@axiom_fuzz_url_encode'),
                'rt_fuzz_double_encode': ('i8*', '@axiom_fuzz_double_encode'),
                'rt_fuzz_add_null_byte': ('i8*', '@axiom_fuzz_add_null_byte'),
                'rt_wordlist_load': ('i64', '@axiom_wordlist_load'),
                'rt_wordlist_count': ('i64', '@axiom_wordlist_count'),
                'rt_wordlist_get': ('i8*', '@axiom_wordlist_get'),
                'rt_wordlist_free': ('void', '@axiom_wordlist_free'),
                'rt_date_format_tz': ('i8*', '@axiom_date_format_tz'),
                'rt_date_iso_tz': ('i8*', '@axiom_date_iso_tz'),
                'rt_date_parse_iso': ('i64', '@axiom_date_parse_iso'),
                'rt_date_local_offset_minutes': ('i64', '@axiom_date_local_offset_minutes'),
                'rt_date_now_iso': ('i8*', '@axiom_date_now_iso'),
                'rt_date_now_epoch': ('i64', '@axiom_date_now_epoch'),
                'rt_date_format_epoch': ('i8*', '@axiom_date_format_epoch'),
                'rt_date_diff_seconds': ('i64', '@axiom_date_diff_seconds'),
                'rt_csv_create': ('i64', '@axiom_csv_create'),
                'rt_csv_add_row': ('void', '@axiom_csv_add_row_ptr'),
                'rt_csv_to_str': ('i8*', '@axiom_csv_to_str'),
                'rt_csv_save_file': ('i1', '@axiom_csv_save_file'),
                'rt_csv_free': ('void', '@axiom_csv_free'),
                'rt_cli_init_args': ('void', '@axiom_cli_init_args'),
                'rt_cli_set_args': ('void', '@axiom_cli_set_args_ptr'),
                'rt_cli_args_count': ('i64', '@axiom_cli_args_count'),
                'rt_cli_args_get': ('i8*', '@axiom_cli_args_get'),
                'rt_cli_has_flag': ('i1', '@axiom_cli_has_flag'),
                'rt_cli_get_option': ('i8*', '@axiom_cli_get_option'),
                'rt_cli_get_int_option': ('i64', '@axiom_cli_get_int_option'),
                # Packet 5 Builtins: AES, JWT, HTML, Logger, Raw Socket & Ping
                'rt_aes256_cbc_encrypt': ('i8*', '@axiom_aes256_cbc_encrypt'),
                'rt_aes256_cbc_decrypt': ('i8*', '@axiom_aes256_cbc_decrypt'),
                'rt_aes128_cbc_encrypt': ('i8*', '@axiom_aes128_cbc_encrypt'),
                'rt_aes128_cbc_decrypt': ('i8*', '@axiom_aes128_cbc_decrypt'),
                'rt_jwt_create_hs256': ('i8*', '@axiom_jwt_create_hs256'),
                'rt_jwt_verify_hs256': ('i1', '@axiom_jwt_verify_hs256'),
                'rt_jwt_get_header': ('i8*', '@axiom_jwt_get_header'),
                'rt_jwt_get_payload': ('i8*', '@axiom_jwt_get_payload'),
                'rt_jwt_get_claim': ('i8*', '@axiom_jwt_get_claim'),
                'rt_html_escape': ('i8*', '@axiom_html_escape'),
                'rt_html_unescape': ('i8*', '@axiom_html_unescape'),
                'rt_html_strip_tags': ('i8*', '@axiom_html_strip_tags'),
                'rt_log_set_level': ('void', '@axiom_log_set_level'),
                'rt_log_debug': ('void', '@axiom_log_debug'),
                'rt_log_info': ('void', '@axiom_log_info'),
                'rt_log_warn': ('void', '@axiom_log_warn'),
                'rt_log_error': ('void', '@axiom_log_error'),
                'rt_icmp_ping': ('i64', '@axiom_icmp_ping'),
                'rt_tcp_ping': ('i64', '@axiom_tcp_ping'),
                'rt_raw_checksum': ('i64', '@axiom_raw_checksum'),
                # Phase 2 Builtins
                'exec_mem_run': ('i64', '@axiom_exec_mem_run'),
                'exec_mem_alloc': ('i64', '@axiom_exec_mem_alloc'),
                'exec_mem_protect': ('i1', '@axiom_exec_mem_protect'),
                'packet_craft_ip': ('i8*', '@axiom_packet_craft_ip'),
                'packet_craft_tcp': ('i8*', '@axiom_packet_craft_tcp'),
                'packet_craft_udp': ('i8*', '@axiom_packet_craft_udp'),
                'diag_is_debugged': ('i1', '@axiom_diag_is_debugged'),
                'diag_is_virtualized': ('i1', '@axiom_diag_is_virtualized'),
                'diag_set_dumpable': ('void', '@axiom_diag_set_dumpable'),
                'proc_search_pattern': ('i64', '@axiom_proc_search_pattern'),
                'proc_get_maps': ('i8*', '@axiom_proc_get_maps'),
                'rt_exec_mem_run': ('i64', '@axiom_exec_mem_run'),
                'rt_exec_mem_alloc': ('i64', '@axiom_exec_mem_alloc'),
                'rt_exec_mem_protect': ('i1', '@axiom_exec_mem_protect'),
                'rt_packet_craft_ip': ('i8*', '@axiom_packet_craft_ip'),
                'rt_packet_craft_tcp': ('i8*', '@axiom_packet_craft_tcp'),
                'rt_packet_craft_udp': ('i8*', '@axiom_packet_craft_udp'),
                'rt_diag_is_debugged': ('i1', '@axiom_diag_is_debugged'),
                'rt_diag_is_virtualized': ('i1', '@axiom_diag_is_virtualized'),
                'rt_diag_set_dumpable': ('void', '@axiom_diag_set_dumpable'),
                'rt_proc_search_pattern': ('i64', '@axiom_proc_search_pattern'),
                'rt_proc_get_maps': ('i8*', '@axiom_proc_get_maps'),
                # Phase 3 Builtins
                'pcap_create_writer': ('i64', '@axiom_pcap_create_writer'),
                'pcap_write_packet': ('i1', '@axiom_pcap_write_packet'),
                'pcap_open_file': ('i64', '@axiom_pcap_open_file'),
                'pcap_next_packet': ('i8*', '@axiom_pcap_next_packet'),
                'pcap_packet_count': ('i64', '@axiom_pcap_packet_count'),
                'pcap_close': ('void', '@axiom_pcap_close'),
                'fim_hash_file': ('i8*', '@axiom_fim_hash_file'),
                'forensics_get_ports': ('i8*', '@axiom_forensics_get_ports'),
                'forensics_get_processes': ('i8*', '@axiom_forensics_get_processes'),
                'forensics_get_modules': ('i8*', '@axiom_forensics_get_modules'),
                'rt_pcap_create_writer': ('i64', '@axiom_pcap_create_writer'),
                'rt_pcap_write_packet': ('i1', '@axiom_pcap_write_packet'),
                'rt_pcap_open_file': ('i64', '@axiom_pcap_open_file'),
                'rt_pcap_next_packet': ('i8*', '@axiom_pcap_next_packet'),
                'rt_pcap_packet_count': ('i64', '@axiom_pcap_packet_count'),
                'rt_pcap_close': ('void', '@axiom_pcap_close'),
                'rt_fim_hash_file': ('i8*', '@axiom_fim_hash_file'),
                'rt_forensics_get_ports': ('i8*', '@axiom_forensics_get_ports'),
                'rt_forensics_get_processes': ('i8*', '@axiom_forensics_get_processes'),
                'rt_forensics_get_modules': ('i8*', '@axiom_forensics_get_modules'),
                # Phase 4 Builtins
                'tensor_create_2d': ('i64', '@axiom_tensor_create_2d'),
                'tensor_set': ('void', '@axiom_tensor_set'),
                'tensor_get': ('double', '@axiom_tensor_get'),
                'tensor_rows': ('i64', '@axiom_tensor_rows'),
                'tensor_cols': ('i64', '@axiom_tensor_cols'),
                'tensor_matmul': ('i64', '@axiom_tensor_matmul'),
                'tensor_add': ('i64', '@axiom_tensor_add'),
                'tensor_transpose': ('i64', '@axiom_tensor_transpose'),
                'tensor_to_str': ('i8*', '@axiom_tensor_to_str'),
                'tensor_free': ('void', '@axiom_tensor_free'),
                'nn_relu': ('double', '@axiom_nn_relu'),
                'nn_sigmoid': ('double', '@axiom_nn_sigmoid'),
                'nn_argmax': ('i64', '@axiom_nn_argmax'),
                'dot_product': ('double', '@axiom_dot_product'),
                'rt_tensor_create_2d': ('i64', '@axiom_tensor_create_2d'),
                'rt_tensor_set': ('void', '@axiom_tensor_set'),
                'rt_tensor_get': ('double', '@axiom_tensor_get'),
                'rt_tensor_rows': ('i64', '@axiom_tensor_rows'),
                'rt_tensor_cols': ('i64', '@axiom_tensor_cols'),
                'rt_tensor_matmul': ('i64', '@axiom_tensor_matmul'),
                'rt_tensor_add': ('i64', '@axiom_tensor_add'),
                'rt_tensor_transpose': ('i64', '@axiom_tensor_transpose'),
                'rt_tensor_to_str': ('i8*', '@axiom_tensor_to_str'),
                'rt_tensor_free': ('void', '@axiom_tensor_free'),
                'rt_nn_relu': ('double', '@axiom_nn_relu'),
                'rt_nn_sigmoid': ('double', '@axiom_nn_sigmoid'),
                'rt_nn_argmax': ('i64', '@axiom_nn_argmax'),
                'rt_dot_product': ('double', '@axiom_dot_product'),
                'rt_epoll_create': ('i64', '@axiom_epoll_create'),
                'rt_epoll_add': ('i64', '@axiom_epoll_add'),
                'rt_epoll_mod': ('i64', '@axiom_epoll_mod'),
                'rt_epoll_del': ('i64', '@axiom_epoll_del'),
                'rt_epoll_wait': ('i64', '@axiom_epoll_wait'),
                'rt_epoll_event_fd': ('i64', '@axiom_epoll_event_fd'),
                'rt_epoll_event_events': ('i64', '@axiom_epoll_event_events'),
                'rt_epoll_close': ('void', '@axiom_epoll_close'),
                'rt_net_set_nonblocking': ('i64', '@axiom_net_set_nonblocking'),
                'rt_tcp_server_nonblocking': ('i64', '@axiom_tcp_server_nonblocking'),
                'rt_tcp_accept_nonblocking': ('i64', '@axiom_tcp_accept_nonblocking'),
                'rt_fd_write': ('i64', '@axiom_fd_write'),
                'rt_fd_read': ('i8*', '@axiom_fd_read'),
                'rt_pipe_create': ('i64', '@axiom_pipe_create'),
                'rt_pipe_read_fd': ('i64', '@axiom_pipe_read_fd'),
                'rt_pipe_write_fd': ('i64', '@axiom_pipe_write_fd'),
                'rt_pipe_close': ('void', '@axiom_pipe_close'),
                'rt_socketpair_create': ('i64', '@axiom_socketpair_create'),
                'rt_socketpair_fd1': ('i64', '@axiom_socketpair_fd1'),
                'rt_socketpair_fd2': ('i64', '@axiom_socketpair_fd2'),
                'rt_socketpair_close': ('void', '@axiom_socketpair_close'),
                'rt_epoll_is_readable': ('i1', '@axiom_epoll_is_readable'),
                'rt_epoll_is_writable': ('i1', '@axiom_epoll_is_writable'),
                'rt_epoll_is_error': ('i1', '@axiom_epoll_is_error'),
                'rt_epoll_is_hangup': ('i1', '@axiom_epoll_is_hangup'),
                # Phase 4.3: Real YARA Byte & Wildcard Mask Pattern Engine
                'rt_ascii_case_find': ('i64', '@axiom_ascii_case_find'),
                'rt_yara_find_hex_wildcard': ('i64', '@axiom_yara_find_hex_wildcard'),
                'rt_yara_find_hex_wildcard_raw': ('i64', '@axiom_yara_find_hex_wildcard_raw'),
                'rt_yara_find_hex_stream': ('i64', '@axiom_yara_find_hex_stream'),
                'rt_yara_pattern_len': ('i64', '@axiom_yara_pattern_len'),
                'rt_yara_scan_buf_handle': ('i64', '@axiom_yara_scan_buf_handle'),
            }

            if expr.callee in builtin_map:
                ret_t, fn_sym = builtin_map[expr.callee]

                # 24 bayttan buyuk struct'lari degerle gecirmek SysV ABI ile
                # uyumsuzluk uretebiliyor. Dizi parametreli runtime fonksiyonlari
                # pointer tabanli sarmalayicilar uzerinden cagrilir.
                if fn_sym in PTR_ABI_SYMBOLS:
                    ptr_args = []
                    for at, areg in arg_vals:
                        if at == '%struct.ax_array':
                            slot = self.new_reg("ap")
                            self.emit_instr(f"{slot} = alloca %struct.ax_array, align 8")
                            self.emit_instr(f"store %struct.ax_array {areg}, %struct.ax_array* {slot}, align 8")
                            ptr_args.append(f"%struct.ax_array* {slot}")
                        else:
                            ptr_args.append(f"{at} {areg}")
                    if ret_t == '%struct.ax_array':
                        out_slot = self.new_reg("apout")
                        self.emit_instr(f"{out_slot} = alloca %struct.ax_array, align 8")
                        call_args = f"%struct.ax_array* {out_slot}, " + ", ".join(ptr_args)
                        self.emit_instr(f"call void {fn_sym}({call_args})")
                        res_reg = self.new_reg("apres")
                        self.emit_instr(f"{res_reg} = load %struct.ax_array, %struct.ax_array* {out_slot}, align 8")
                        return (ret_t, res_reg)
                    if ret_t == 'void':
                        self.emit_instr(f"call void {fn_sym}({', '.join(ptr_args)})")
                        return ('void', '')
                    res_reg = self.new_reg("bcall")
                    self.emit_instr(f"{res_reg} = call {ret_t} {fn_sym}({', '.join(ptr_args)})")
                    return (ret_t, res_reg)

                if ret_t == 'void':
                    self.emit_instr(f"call void {fn_sym}({args_str})")
                    return ('void', '')

                res_reg = self.new_reg("bcall")
                self.emit_instr(f"{res_reg} = call {ret_t} {fn_sym}({args_str})")
                return (ret_t, res_reg)

            # Genel runtime fallback: rt_foo -> @axiom_foo, donus tipi checker'dan.
            if expr.callee not in self.function_types:
                if expr.callee.startswith('rt_'):
                    fn_sym = '@axiom_' + expr.callee[3:]
                else:
                    fn_sym = '@axiom_' + expr.callee
                inf = getattr(expr, 'inferred_type', None)
                if inf == 'void' or inf is None:
                    param_types = ", ".join(t for t, _ in arg_vals) or ''
                    decl = f"declare void {fn_sym}({param_types})"
                    if decl not in self.pending_decls:
                        self.pending_decls.append(decl)
                    self.emit_instr(f"call void {fn_sym}({args_str})")
                    return ('void', '')
                ret_t = llvm_type(inf)
                param_types = ", ".join(t for t, _ in arg_vals) or ''

                # Struct donduren runtime fonksiyonlari: sret sozlesmesi.
                if ret_t.startswith('%struct.'):
                    if param_types:
                        decl = f"declare void {fn_sym}({ret_t}* sret({ret_t}), {param_types})"
                    else:
                        decl = f"declare void {fn_sym}({ret_t}* sret({ret_t}))"
                    if decl not in self.pending_decls:
                        self.pending_decls.append(decl)
                    slot = self.new_reg("sretp")
                    self.emit_instr(f"{slot} = alloca {ret_t}, align 8")
                    if args_str:
                        self.emit_instr(
                            f"call void {fn_sym}({ret_t}* sret({ret_t}) {slot}, {args_str})")
                    else:
                        self.emit_instr(f"call void {fn_sym}({ret_t}* sret({ret_t}) {slot})")
                    res_reg = self.new_reg("sretv")
                    self.emit_instr(f"{res_reg} = load {ret_t}, {ret_t}* {slot}, align 8")
                    return (ret_t, res_reg)

                decl = f"declare {ret_t} {fn_sym}({param_types})"
                if decl not in self.pending_decls:
                    self.pending_decls.append(decl)
                res_reg = self.new_reg("rtcall")
                self.emit_instr(f"{res_reg} = call {ret_t} {fn_sym}({args_str})")
                return (ret_t, res_reg)

            # User function call (overload-aware)
            resolved = getattr(expr, 'resolved_function', None)
            if resolved is not None:
                call_sym = llvm_fn_symbol(
                    resolved.name,
                    [llvm_type(p.type_name) for p in resolved.params],
                    resolved.name in self.overloaded_fns,
                )
                ret_t = llvm_type(resolved.return_type)
            elif expr.callee in self.overloaded_fns:
                arg_ll = [t for t, _ in arg_vals]
                call_sym = llvm_fn_symbol(expr.callee, arg_ll, True)
                ret_t = self.function_types.get(expr.callee, ([], 'void'))[1]
            else:
                call_sym = f"ax_{expr.callee}"
                ret_t = self.function_types.get(expr.callee, ([], 'void'))[1]

            if ret_t == 'void':
                self.emit_instr(f"call void @{call_sym}({args_str})")
                return ('void', '')
            res_reg = self.new_reg("call")
            self.emit_instr(f"{res_reg} = call {ret_t} @{call_sym}({args_str})")
            return (ret_t, res_reg)

        elif isinstance(expr, ArrayLiteral):
            n = len(expr.elements)
            # Allocate memory for array elements
            bytes_count = n * 8
            raw_ptr = self.new_reg("raw_buf")
            self.emit_instr(f"{raw_ptr} = call i8* @malloc(i64 {bytes_count})")
            typed_buf = self.new_reg("typed_buf")
            self.emit_instr(f"{typed_buf} = bitcast i8* {raw_ptr} to i64*")

            # Store elements
            for idx, elem in enumerate(expr.elements):
                elem_t, elem_reg = self.generate_expr(elem)
                if elem_t == 'i8*' or elem_t.endswith('*'):
                    cast_reg = self.new_reg("p2i")
                    self.emit_instr(f"{cast_reg} = ptrtoint {elem_t} {elem_reg} to i64")
                    elem_reg = cast_reg
                elif elem_t == 'i1':
                    cast_reg = self.new_reg("zext")
                    self.emit_instr(f"{cast_reg} = zext i1 {elem_reg} to i64")
                    elem_reg = cast_reg
                elif elem_t == 'double':
                    cast_reg = self.new_reg("bitcast")
                    self.emit_instr(f"{cast_reg} = bitcast double {elem_reg} to i64")
                    elem_reg = cast_reg

                elem_gep = self.new_reg(f"arr_e_{idx}")
                self.emit_instr(f"{elem_gep} = getelementptr inbounds i64, i64* {typed_buf}, i64 {idx}")
                self.emit_instr(f"store i64 {elem_reg}, i64* {elem_gep}, align 8")

            # Construct %struct.ax_array value
            arr0 = self.new_reg("arr_v0")
            self.emit_instr(f"{arr0} = insertvalue %struct.ax_array undef, i64 {n}, 0")
            arrc = self.new_reg("arr_vc")
            self.emit_instr(f"{arrc} = insertvalue %struct.ax_array {arr0}, i64 0, 1")
            arr1 = self.new_reg("arr_v1")
            self.emit_instr(f"{arr1} = insertvalue %struct.ax_array {arrc}, i64* {typed_buf}, 2")
            return ('%struct.ax_array', arr1)

        elif isinstance(expr, IndexAccess):
            arr_t, arr_reg = self.generate_expr(expr.array)
            idx_t, idx_reg = self.generate_expr(expr.index)
            len_reg = self.new_reg("arr_len")
            self.emit_instr(f"{len_reg} = extractvalue %struct.ax_array {arr_reg}, 0")
            checked_idx = self.new_reg("checked_idx")
            self.emit_instr(f"{checked_idx} = call i64 @axiom_bounds_check(i64 {idx_reg}, i64 {len_reg}, i8* null, i64 0)")
            data_ptr = self.new_reg("arr_data")
            self.emit_instr(f"{data_ptr} = extractvalue %struct.ax_array {arr_reg}, 2")

            arr_inf = getattr(expr.array, 'inferred_type', None) or getattr(expr, 'inferred_type', None)
            elem_ll = 'i64'
            if arr_inf and arr_inf.endswith('[]'):
                elem_ll = llvm_type(arr_inf[:-2])

            if elem_ll == 'i64':
                elem_gep = self.new_reg("elem_ptr")
                self.emit_instr(f"{elem_gep} = getelementptr inbounds i64, i64* {data_ptr}, i64 {checked_idx}")
                elem_val = self.new_reg("elem_val")
                self.emit_instr(f"{elem_val} = load i64, i64* {elem_gep}, align 8")
                return ('i64', elem_val)

            typed_ptr = self.new_reg("elem_tptr")
            self.emit_instr(f"{typed_ptr} = bitcast i64* {data_ptr} to {elem_ll}*")
            elem_gep = self.new_reg("elem_ptr")
            self.emit_instr(f"{elem_gep} = getelementptr inbounds {elem_ll}, {elem_ll}* {typed_ptr}, i64 {checked_idx}")
            elem_val = self.new_reg("elem_val")
            self.emit_instr(f"{elem_val} = load {elem_ll}, {elem_ll}* {elem_gep}, align 8")
            return (elem_ll, elem_val)

        elif isinstance(expr, StructInit):
            s_name = expr.struct_name
            s_type = f"%struct.ax_{s_name}"
            s_ptr = self.new_reg("s_init")
            self.emit_instr(f"{s_ptr} = alloca {s_type}, align 8")
            s_decl = self.struct_defs.get(s_name)
            if s_decl:
                field_map = {f.name: (idx, llvm_type(f.type_name)) for idx, f in enumerate(s_decl.fields)}
                for f_init in expr.fields:
                    if f_init.field_name in field_map:
                        f_idx, f_llvm_t = field_map[f_init.field_name]
                        f_val_t, f_val_reg = self.generate_expr(f_init.value)
                        gep = self.new_reg(f"f_{f_init.field_name}")
                        self.emit_instr(f"{gep} = getelementptr inbounds {s_type}, {s_type}* {s_ptr}, i32 0, i32 {f_idx}")
                        self.emit_instr(f"store {f_llvm_t} {f_val_reg}, {f_llvm_t}* {gep}, align 8")
            loaded_reg = self.new_reg("s_val")
            self.emit_instr(f"{loaded_reg} = load {s_type}, {s_type}* {s_ptr}, align 8")
            return (s_type, loaded_reg)

        elif isinstance(expr, MemberAccess):
            obj_t, obj_reg = self.generate_expr(expr.object)
            if obj_t.startswith("%struct.ax_"):
                s_name = obj_t[len("%struct.ax_"):]
                s_decl = self.struct_defs.get(s_name)
                if s_decl:
                    for idx, f in enumerate(s_decl.fields):
                        if f.name == expr.member:
                            f_llvm_t = llvm_type(f.type_name)
                            res_reg = self.new_reg(f"m_{expr.member}")
                            self.emit_instr(f"{res_reg} = extractvalue {obj_t} {obj_reg}, {idx}")
                            return (f_llvm_t, res_reg)

        elif isinstance(expr, MatchExpr):
            ret_t = llvm_type(getattr(expr, 'inferred_type', 'int'))
            subj_t, subj_val = self.generate_expr(expr.subject)
            res_ptr = self.new_reg("match_res")
            self.emit_instr(f"{res_ptr} = alloca {ret_t}, align 8")
            end_lbl = self.new_label("match.end")

            for arm in expr.arms:
                arm_body_lbl = self.new_label("match.arm")
                next_arm_lbl = self.new_label("match.next")

                if isinstance(arm.pattern, (WildcardPattern, IdentPattern)):
                    cond_val = "1"
                elif isinstance(arm.pattern, LiteralPattern):
                    lit_t, lit_val = self.generate_expr(arm.pattern.literal)
                    cmp_reg = self.new_reg("match_cmp")
                    if subj_t == 'double':
                        self.emit_instr(f"{cmp_reg} = fcmp oeq double {subj_val}, {lit_val}")
                    elif subj_t == 'i8*':
                        strcmp_res = self.new_reg("scmp")
                        self.emit_instr(f"{strcmp_res} = call i32 @strcmp(i8* {subj_val}, i8* {lit_val})")
                        self.emit_instr(f"{cmp_reg} = icmp eq i32 {strcmp_res}, 0")
                    else:
                        self.emit_instr(f"{cmp_reg} = icmp eq {subj_t} {subj_val}, {lit_val}")
                    cond_val = cmp_reg

                if arm.guard:
                    guard_t, guard_val = self.generate_expr(arm.guard)
                    if cond_val == "1":
                        cond_val = guard_val
                    else:
                        and_reg = self.new_reg("guard_and")
                        self.emit_instr(f"{and_reg} = and i1 {cond_val}, {guard_val}")
                        cond_val = and_reg

                if cond_val == "1":
                    self.emit_instr(f"br label %{arm_body_lbl}")
                else:
                    self.emit_instr(f"br i1 {cond_val}, label %{arm_body_lbl}, label %{next_arm_lbl}")

                self.emit(f"{arm_body_lbl}:")
                self.block_terminated = False

                if isinstance(arm.pattern, IdentPattern):
                    var_ptr = self.new_reg(f"var.{arm.pattern.name}")
                    self.emit_instr(f"{var_ptr} = alloca {subj_t}, align 8")
                    self.emit_instr(f"store {subj_t} {subj_val}, {subj_t}* {var_ptr}, align 8")
                    self.variables[arm.pattern.name] = (subj_t, var_ptr)

                if isinstance(arm.body, Expr):
                    val_t, val_reg = self.generate_expr(arm.body)
                    self.emit_instr(f"store {ret_t} {val_reg}, {ret_t}* {res_ptr}, align 8")
                elif isinstance(arm.body, ExprStmt):
                    val_t, val_reg = self.generate_expr(arm.body.expr)
                    self.emit_instr(f"store {ret_t} {val_reg}, {ret_t}* {res_ptr}, align 8")
                elif isinstance(arm.body, Block):
                    for s in arm.body.statements:
                        self.generate_stmt(s)

                if not self.block_terminated:
                    self.emit_instr(f"br label %{end_lbl}")

                self.emit(f"{next_arm_lbl}:")
                self.block_terminated = False

            if not self.block_terminated:
                self.emit_instr(f"br label %{end_lbl}")

            self.emit(f"{end_lbl}:")
            self.block_terminated = False

            final_val = self.new_reg("match_final")
            self.emit_instr(f"{final_val} = load {ret_t}, {ret_t}* {res_ptr}, align 8")
            return (ret_t, final_val)

        return ('i64', '0')
