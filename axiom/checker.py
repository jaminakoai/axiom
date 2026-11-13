"""
Axiom Programming Language (λx) - Semantic Analyzer & Contract Verifier
"""
from typing import Dict, List, Optional, Set, Tuple, Any
import copy
from axiom.ast_nodes import (
    Program, Stmt, Expr, Block, FunctionDecl, Param, FunctionContract,
    LetDecl, AssignStmt, IfStmt, WhileStmt, ForRangeStmt, ReturnStmt,
    PrintStmt, ExprStmt, VerifyStmt, BreakStmt, ContinueStmt, DeferStmt, BinaryOp, UnaryOp, NumberLiteral, TryExpr,
    StringLiteral, BooleanLiteral, Identifier, FunctionCall,
    StructDecl, StructField, StructInit, StructFieldInit, MemberAccess,
    ArrayLiteral, IndexAccess, ImportStmt, CastExpr,
    MatchStmt, MatchExpr, MatchArm, Pattern, WildcardPattern, LiteralPattern, IdentPattern
)

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

def mangle_type_arg(t: str) -> str:
    """Generic tip argumanini C tanimlayicisinda guvenli parcaya cevirir.

    'str[]' -> 'str_array', 'Box<int>' -> 'Box_int'. `mangle_type_name` dizi
    ekini korur (tip ifadesi icin dogru), ama monomorflasmis struct/function
    ADINDA '[]' gecersiz C tanimlayicisidir.
    """
    if not t:
        return t
    if t.endswith('[]'):
        return mangle_type_arg(t[:-2]) + '_array'
    return mangle_type_name(t)

def parse_generic_type_str(t: str) -> Tuple[str, List[str]]:
    if not t or '<' not in t:
        return t, []
    base = t[:t.index('<')].strip()
    args_str = t[t.index('<')+1:t.rindex('>')].strip()
    args = []
    depth = 0
    cur = []
    for ch in args_str:
        if ch == '<':
            depth += 1
            cur.append(ch)
        elif ch == '>':
            depth -= 1
            cur.append(ch)
        elif ch == ',' and depth == 0:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        args.append("".join(cur).strip())
    return base, args

class SemanticError(Exception):
    def __init__(self, message: str, line: int = 1, col: int = 1):
        super().__init__(f"Axiom Semantik Hatasi [Satir {line}, Sutun {col}]: {message}")
        self.line = line
        self.col = col

class Symbol:
    def __init__(self, name: str, type_name: str, is_mut: bool = False):
        self.name = name
        self.type_name = type_name
        self.is_mut = is_mut

class Scope:
    def __init__(self, parent: Optional['Scope'] = None,
                 is_function_scope: bool = False):
        self.parent = parent
        self.symbols: Dict[str, Symbol] = {}
        self.is_function_scope = is_function_scope

    def define(self, name: str, type_name: str, is_mut: bool = False):
        self.symbols[name] = Symbol(name, type_name, is_mut)

    def defined_here(self, name: str) -> bool:
        return name in self.symbols

    def lookup(self, name: str) -> Optional[Symbol]:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

BUILTIN_FUNCTIONS = {
    'tcp_connect': (['str', 'int'], 'int'),
    'tcp_send': (['int', 'str'], 'int'),
    'tcp_recv': (['int', 'int'], 'str'),
    'socket_close': (['int'], 'void'),
    'time_now_ms': ([], 'int'),
    'file_read': (['str'], 'str'),
    'file_write': (['str', 'str'], 'bool'),
    'file_exists': (['str'], 'bool'),
    'file_size': (['str'], 'int'),
    'is_directory': (['str'], 'bool'),
    'list_dir': (['str'], 'str'),
    'remove_file': (['str'], 'bool'),
    'rename_file': (['str', 'str'], 'bool'),
    'create_dir': (['str'], 'bool'),
    'os_exec': (['str'], 'int'),
    'os_exec_argv': (['str[]'], 'int'),
    'compile_c': (['str', 'str'], 'int'),
    'os_getenv': (['str'], 'str'),
    'str_contains': (['str', 'str'], 'bool'),
    'str_starts_with': (['str', 'str'], 'bool'),
    'str_ends_with': (['str', 'str'], 'bool'),
    'str_trim': (['str'], 'str'),
    'str_char_at': (['str', 'int'], 'str'),
    'str_sub': (['str', 'int', 'int'], 'str'),
    'str_len': (['str'], 'int'),
    'rt_str_len': (['str'], 'int'),
    'str_byte_len': (['str'], 'int'),
    'rt_str_byte_len': (['str'], 'int'),
    'rt_unicode_nfd': (['str'], 'str'),
    'rt_unicode_nfc': (['str'], 'str'),
    'rt_unicode_is_nfd': (['str'], 'bool'),
    'rt_unicode_is_nfc': (['str'], 'bool'),
    'rt_unicode_normalize': (['str', 'str'], 'str'),
    'rt_unicode_ucd_version': ([], 'str'),
    'rt_utf8_codepoint_count': (['str'], 'int'),
    'rt_str_grapheme_len': (['str'], 'int'),
    'rt_str_grapheme_at': (['str', 'int'], 'str'),
    'rt_str_to_upper_tr': (['str'], 'str'),
    'rt_str_to_lower_tr': (['str'], 'str'),
    'rt_simd_avx2_supported': ([], 'bool'),
    'str_char_code': (['str', 'int'], 'int'),
    'char_to_str': (['int'], 'str'),
    'str_index_of': (['str', 'str'], 'int'),
    'str_replace': (['str', 'str', 'str'], 'str'),
    'str_split': (['str', 'str'], 'str[]'),
    'str_join': (['str[]', 'str'], 'str'),
    'str_free': (['str'], 'void'),
    'str_owned_count': ([], 'int'),
    'json_parse': (['str'], 'int'),
    'json_free': (['int'], 'void'),
    'json_last_error': ([], 'str'),
    'json_type_of': (['int'], 'int'),
    'json_len': (['int'], 'int'),
    'json_at': (['int', 'int'], 'int'),
    'json_key_at': (['int', 'int'], 'str'),
    'json_get': (['int', 'str'], 'int'),
    'json_path': (['int', 'str'], 'int'),
    'json_node_str': (['int'], 'str'),
    'json_node_int': (['int'], 'int'),
    'json_node_float': (['int'], 'float'),
    'json_node_bool': (['int'], 'bool'),
    'json_node_is_null': (['int'], 'bool'),
    'tcp_recv_all': (['int', 'int'], 'str'),
    'tcp_set_timeout': (['int', 'int'], 'int'),
    'http_header_value': (['str', 'str'], 'str'),
    'http_chunked_decode': (['str'], 'str'),
    'rt_str_free': (['str'], 'void'),
    'array_create_int': (['int'], 'int[]'),
    'array_create_str': (['int'], 'str[]'),
    'array_push_int': (['int[]', 'int'], 'int[]'),
    'array_push_str': (['str[]', 'str'], 'str[]'),
    'str_to_int': (['str'], 'int'),
    'int_to_str': (['int'], 'str'),
    'math_abs': (['int'], 'int'),
    'math_min': (['int', 'int'], 'int'),
    'math_max': (['int', 'int'], 'int'),
    'math_pow': (['int', 'int'], 'int'),
    'thread_join': (['int'], 'int'),
    'mutex_init': ([], 'int'),
    'mutex_lock': (['int'], 'void'),
    'mutex_unlock': (['int'], 'void'),
    'atomic_init': (['int'], 'int'),
    'atomic_add': (['int', 'int'], 'int'),
    'atomic_get': (['int'], 'int'),
    'sleep_ms': (['int'], 'void'),
    'simd_add_i64': (['int[]', 'int[]'], 'int[]'),
    'simd_mul_i64': (['int[]', 'int[]'], 'int[]'),
    'simd_sub_i64': (['int[]', 'int[]'], 'int[]'),
    'simd_sum_i64': (['int[]'], 'int'),
    'simd_scan_match': (['int[]', 'int'], 'int'),
    # Packet 1 Builtins: Encoding, Crypto, URL, JSON
    'rt_base64_encode': (['str'], 'str'),
    'rt_base64_decode': (['str'], 'str'),
    'rt_hex_encode': (['str'], 'str'),
    'rt_hex_decode': (['str'], 'str'),
    'rt_hash_md5': (['str'], 'str'),
    'rt_hash_sha1': (['str'], 'str'),
    'rt_hash_sha256': (['str'], 'str'),
    'rt_crypto_random_hex': (['int'], 'str'),
    'rt_hmac_sha256': (['str', 'str'], 'str'),
    'rt_crypto_memcmp': (['str', 'str'], 'bool'),
    'crypto_memcmp': (['str', 'str'], 'bool'),
    'rt_url_encode': (['str'], 'str'),
    'rt_url_decode': (['str'], 'str'),
    'rt_url_parse_scheme': (['str'], 'str'),
    'rt_url_parse_host': (['str'], 'str'),
    'rt_url_parse_port': (['str'], 'int'),
    'rt_url_parse_path': (['str'], 'str'),
    'rt_url_parse_query': (['str'], 'str'),
    'rt_json_get_str': (['str', 'str'], 'str'),
    'rt_json_get_int': (['str', 'str'], 'int'),
    'rt_json_get_bool': (['str', 'str'], 'bool'),
    'rt_json_has_key': (['str', 'str'], 'bool'),
    'rt_json_build_object': (['str[]', 'str[]'], 'str'),
    # Packet 2 Builtins: DNS, UDP, HTTP Server, TLS, WebSocket
    'rt_dns_resolve_ipv4': (['str'], 'str'),
    'rt_dns_resolve_ipv6': (['str'], 'str'),
    'rt_dns_reverse_lookup': (['str'], 'str'),
    'rt_udp_socket': ([], 'int'),
    'rt_udp_bind': (['int'], 'int'),
    'rt_udp_sendto': (['int', 'str', 'int', 'str'], 'int'),
    'rt_udp_recvfrom': (['int', 'int'], 'str'),
    'rt_udp_close': (['int'], 'void'),
    'rt_http_server_create': (['int'], 'int'),
    'rt_http_server_accept': (['int'], 'int'),
    'rt_http_server_send_response': (['int', 'int', 'str', 'str'], 'void'),
    'rt_http_server_close': (['int'], 'void'),
    'rt_tls_connect': (['str', 'int'], 'int'),
    'rt_tls_send': (['int', 'str'], 'int'),
    'rt_tls_recv': (['int', 'int'], 'str'),
    'rt_tls_close': (['int'], 'void'),
    'rt_ws_connect': (['str', 'int', 'str'], 'int'),
    'rt_ws_send': (['int', 'str'], 'int'),
    'rt_ws_recv': (['int'], 'str'),
    'rt_ws_close': (['int'], 'void'),
    # Packet 3 Builtins: Binary Buffer, Process, Zlib, Regex, Map
    'rt_buf_create': (['int'], 'int'),
    'rt_buf_write_u8': (['int', 'int'], 'void'),
    'rt_buf_write_u16_be': (['int', 'int'], 'void'),
    'rt_buf_write_u16_le': (['int', 'int'], 'void'),
    'rt_buf_write_u32_be': (['int', 'int'], 'void'),
    'rt_buf_write_u32_le': (['int', 'int'], 'void'),
    'rt_buf_write_u64_be': (['int', 'int'], 'void'),
    'rt_buf_write_u64_le': (['int', 'int'], 'void'),
    'rt_buf_write_str': (['int', 'str'], 'void'),
    'rt_buf_to_hex': (['int'], 'str'),
    'rt_buf_to_str': (['int'], 'str'),
    'rt_buf_len': (['int'], 'int'),
    'rt_buf_from_hex': (['str'], 'int'),
    'rt_buf_read_u8': (['int', 'int'], 'int'),
    'rt_buf_read_u16_be': (['int', 'int'], 'int'),
    'rt_buf_read_u16_le': (['int', 'int'], 'int'),
    'rt_buf_read_u32_be': (['int', 'int'], 'int'),
    'rt_buf_read_u32_le': (['int', 'int'], 'int'),
    'rt_buf_read_u64_be': (['int', 'int'], 'int'),
    'rt_buf_read_u64_le': (['int', 'int'], 'int'),
    'rt_buf_free': (['int'], 'void'),
    'rt_process_exec_output': (['str'], 'str'),
    'rt_process_get_pid': ([], 'int'),
    'rt_process_kill': (['int', 'int'], 'int'),
    'rt_process_spawn_bg': (['str'], 'int'),
    'rt_gzip_compress': (['str'], 'str'),
    'rt_gzip_decompress': (['str'], 'str'),
    'rt_zlib_compress_str': (['str'], 'str'),
    'rt_zlib_decompress_str': (['str'], 'str'),
    'rt_regex_validate': (['str'], 'str'),
    'rt_regex_risk_level': (['str'], 'int'),
    'rt_regex_is_match': (['str', 'str'], 'bool'),
    'rt_regex_find': (['str', 'str'], 'str'),
    'rt_regex_replace': (['str', 'str', 'str'], 'str'),
    'rt_map_create': ([], 'int'),
    'rt_map_set': (['int', 'str', 'str'], 'void'),
    'rt_map_get': (['int', 'str'], 'str'),
    'rt_map_has': (['int', 'str'], 'bool'),
    'rt_map_delete': (['int', 'str'], 'bool'),
    'rt_map_len': (['int'], 'int'),
    'rt_map_free': (['int'], 'void'),
    # Packet 4 Builtins: Queue, Fuzzer, Date/Time, CSV, CLI Args
    'rt_queue_create': ([], 'int'),
    'rt_queue_push': (['int', 'str'], 'void'),
    'rt_queue_pop': (['int'], 'str'),
    'rt_queue_len': (['int'], 'int'),
    'rt_queue_is_empty': (['int'], 'bool'),
    'rt_queue_free': (['int'], 'void'),
    'rt_fuzz_replace_marker': (['str', 'str', 'str'], 'str'),
    'rt_fuzz_url_encode': (['str'], 'str'),
    'rt_fuzz_double_encode': (['str'], 'str'),
    'rt_fuzz_add_null_byte': (['str'], 'str'),
    'rt_wordlist_load': (['str'], 'int'),
    'rt_wordlist_count': (['int'], 'int'),
    'rt_wordlist_get': (['int', 'int'], 'str'),
    'rt_wordlist_free': (['int'], 'void'),
    'rt_date_format_tz': (['int', 'str', 'int'], 'str'),
    'rt_date_iso_tz': (['int', 'int'], 'str'),
    'rt_date_parse_iso': (['str'], 'int'),
    'rt_date_local_offset_minutes': ([], 'int'),
    'rt_date_now_iso': ([], 'str'),
    'rt_date_now_epoch': ([], 'int'),
    'rt_date_format_epoch': (['int', 'str'], 'str'),
    'rt_date_diff_seconds': (['int', 'int'], 'int'),
    'rt_csv_create': ([], 'int'),
    'rt_csv_add_row': (['int', 'str[]'], 'void'),
    'rt_csv_to_str': (['int'], 'str'),
    'rt_csv_save_file': (['int', 'str'], 'bool'),
    'rt_csv_free': (['int'], 'void'),
    'rt_cli_init_args': (['int', 'str[]'], 'void'),
    'rt_cli_set_args': (['str[]'], 'void'),
    'rt_cli_args_count': ([], 'int'),
    'rt_cli_args_get': (['int'], 'str'),
    'rt_cli_has_flag': (['str'], 'bool'),
    'rt_cli_get_option': (['str', 'str'], 'str'),
    'rt_cli_get_int_option': (['str', 'int'], 'int'),
    # Packet 5 Builtins: AES, JWT, HTML, Logger, Raw Socket & Ping
    'rt_aes256_cbc_encrypt': (['str', 'str', 'str'], 'str'),
    'rt_aes256_cbc_decrypt': (['str', 'str', 'str'], 'str'),
    'rt_aes128_cbc_encrypt': (['str', 'str', 'str'], 'str'),
    'rt_aes128_cbc_decrypt': (['str', 'str', 'str'], 'str'),
    'rt_jwt_create_hs256': (['str', 'str'], 'str'),
    'rt_jwt_verify_hs256': (['str', 'str'], 'bool'),
    'rt_jwt_get_header': (['str'], 'str'),
    'rt_jwt_get_payload': (['str'], 'str'),
    'rt_jwt_get_claim': (['str', 'str'], 'str'),
    'rt_html_escape': (['str'], 'str'),
    'rt_html_unescape': (['str'], 'str'),
    'rt_html_strip_tags': (['str'], 'str'),
    'rt_log_set_level': (['int'], 'void'),
    'rt_log_debug': (['str', 'str'], 'void'),
    'rt_log_info': (['str', 'str'], 'void'),
    'rt_log_warn': (['str', 'str'], 'void'),
    'rt_log_error': (['str', 'str'], 'void'),
    'rt_icmp_ping': (['str', 'int'], 'int'),
    'rt_tcp_ping': (['str', 'int', 'int'], 'int'),
    'rt_raw_checksum': (['str'], 'int'),
    # Phase 2: Red Team & Systems Engineering Builtins
    'exec_mem_run': (['str'], 'int'),
    'exec_mem_alloc': (['int'], 'int'),
    'exec_mem_protect': (['int', 'int', 'int'], 'bool'),
    'packet_craft_ip': (['str', 'str', 'int', 'int'], 'str'),
    'packet_craft_tcp': (['str', 'str', 'int', 'int', 'int', 'int'], 'str'),
    'packet_craft_udp': (['int', 'int', 'str'], 'str'),
    'diag_is_debugged': ([], 'bool'),
    'diag_is_virtualized': ([], 'bool'),
    'diag_set_dumpable': (['bool'], 'void'),
    'proc_search_pattern': (['int', 'str'], 'int'),
    'proc_get_maps': (['int'], 'str'),
    'rt_exec_mem_run': (['str'], 'int'),
    'rt_exec_mem_alloc': (['int'], 'int'),
    'rt_exec_mem_protect': (['int', 'int', 'int'], 'bool'),
    'rt_packet_craft_ip': (['str', 'str', 'int', 'int'], 'str'),
    'rt_packet_craft_tcp': (['str', 'str', 'int', 'int', 'int', 'int'], 'str'),
    'rt_packet_craft_udp': (['int', 'int', 'str'], 'str'),
    'rt_diag_is_debugged': ([], 'bool'),
    'rt_diag_is_virtualized': ([], 'bool'),
    'rt_diag_set_dumpable': (['bool'], 'void'),
    'rt_proc_search_pattern': (['int', 'str'], 'int'),
    'rt_proc_get_maps': (['int'], 'str'),
    # Phase 3: Blue Team & DFIR Builtins
    'pcap_create_writer': (['str'], 'int'),
    'pcap_write_packet': (['int', 'str'], 'bool'),
    'pcap_open_file': (['str'], 'int'),
    'pcap_next_packet': (['int'], 'str'),
    'pcap_packet_count': (['int'], 'int'),
    'pcap_close': (['int'], 'void'),
    'fim_hash_file': (['str'], 'str'),
    'forensics_get_ports': ([], 'str'),
    'forensics_get_processes': ([], 'str'),
    'forensics_get_modules': ([], 'str'),
    'rt_pcap_create_writer': (['str'], 'int'),
    'rt_pcap_write_packet': (['int', 'str'], 'bool'),
    'rt_pcap_open_file': (['str'], 'int'),
    'rt_pcap_next_packet': (['int'], 'str'),
    'rt_pcap_packet_count': (['int'], 'int'),
    'rt_pcap_close': (['int'], 'void'),
    'rt_fim_hash_file': (['str'], 'str'),
    'rt_forensics_get_ports': ([], 'str'),
    'rt_forensics_get_processes': ([], 'str'),
    'rt_forensics_get_modules': ([], 'str'),
    # Phase 4: AI & ML Tensor Builtins
    'tensor_create_2d': (['int', 'int'], 'int'),
    'tensor_set': (['int', 'int', 'int', 'float'], 'void'),
    'tensor_get': (['int', 'int', 'int'], 'float'),
    'tensor_rows': (['int'], 'int'),
    'tensor_cols': (['int'], 'int'),
    'tensor_matmul': (['int', 'int'], 'int'),
    'tensor_add': (['int', 'int'], 'int'),
    'tensor_transpose': (['int'], 'int'),
    'tensor_to_str': (['int'], 'str'),
    'tensor_free': (['int'], 'void'),
    'nn_relu': (['float'], 'float'),
    'nn_sigmoid': (['float'], 'float'),
    'nn_argmax': (['int'], 'int'),
    'dot_product': (['int', 'int'], 'float'),
    'rt_tensor_create_2d': (['int', 'int'], 'int'),
    'rt_tensor_set': (['int', 'int', 'int', 'float'], 'void'),
    'rt_tensor_get': (['int', 'int', 'int'], 'float'),
    'rt_tensor_rows': (['int'], 'int'),
    'rt_tensor_cols': (['int'], 'int'),
    'rt_tensor_matmul': (['int', 'int'], 'int'),
    'rt_tensor_add': (['int', 'int'], 'int'),
    'rt_tensor_transpose': (['int'], 'int'),
    'rt_tensor_to_str': (['int'], 'str'),
    'rt_tensor_free': (['int'], 'void'),
    'rt_nn_relu': (['float'], 'float'),
    'rt_nn_sigmoid': (['float'], 'float'),
    'rt_nn_argmax': (['int'], 'int'),
    'rt_dot_product': (['int', 'int'], 'float'),
    # Phase 4.2: Linux Epoll & Async Network Engine Builtins
    'rt_epoll_create': (['int'], 'int'),
    'rt_epoll_add': (['int', 'int', 'int'], 'int'),
    'rt_epoll_mod': (['int', 'int', 'int'], 'int'),
    'rt_epoll_del': (['int', 'int'], 'int'),
    'rt_epoll_wait': (['int', 'int'], 'int'),
    'rt_epoll_event_fd': (['int', 'int'], 'int'),
    'rt_epoll_event_events': (['int', 'int'], 'int'),
    'rt_epoll_close': (['int'], 'void'),
    'rt_net_set_nonblocking': (['int'], 'int'),
    'rt_tcp_server_nonblocking': (['int'], 'int'),
    'rt_tcp_accept_nonblocking': (['int'], 'int'),
    'rt_fd_write': (['int', 'str'], 'int'),
    'rt_fd_read': (['int', 'int'], 'str'),
    'rt_pipe_create': ([], 'int'),
    'rt_pipe_read_fd': (['int'], 'int'),
    'rt_pipe_write_fd': (['int'], 'int'),
    'rt_pipe_close': (['int'], 'void'),
    'rt_socketpair_create': ([], 'int'),
    'rt_socketpair_fd1': (['int'], 'int'),
    'rt_socketpair_fd2': (['int'], 'int'),
    'rt_socketpair_close': (['int'], 'void'),
    'rt_epoll_is_readable': (['int'], 'bool'),
    'rt_epoll_is_writable': (['int'], 'bool'),
    'rt_epoll_is_error': (['int'], 'bool'),
    'rt_epoll_is_hangup': (['int'], 'bool'),
    # Phase 4.3: Real YARA Byte & Wildcard Mask Pattern Engine
    'rt_ascii_case_find': (['str', 'str'], 'int'),
    'rt_yara_find_text': (['str', 'str', 'int', 'int', 'int'], 'int'),
    'rt_yara_count_text': (['str', 'str', 'int'], 'int'),
    'rt_yara_nth_text_offset': (['str', 'str', 'int', 'int'], 'int'),
    'rt_yara_nth_hex_wildcard': (['str', 'str', 'int'], 'int'),
    'rt_yara_count_hex_wildcard': (['str', 'str'], 'int'),
    'rt_yara_find_hex_wildcard': (['str', 'str', 'int', 'int'], 'int'),
    'rt_yara_find_hex_range': (['str', 'str', 'int', 'int'], 'int'),
    'rt_yara_find_hex_range_length': (['str', 'str', 'int'], 'int'),
    'rt_yara_find_hex_alternation': (['str', 'str', 'int', 'int'], 'int'),
    'rt_yara_hex_alternation_len': (['str'], 'int'),
    'rt_yara_find_hex_negation': (['str', 'str', 'int', 'int'], 'int'),
    'rt_yara_hex_negation_len': (['str'], 'int'),
    'rt_yara_count_hex_pattern': (['str', 'str'], 'int'),
    'rt_yara_find_hex_pattern': (['str', 'str', 'int', 'int'], 'int'),
    'rt_yara_hex_pattern_length_at': (['str', 'str', 'int'], 'int'),
    'rt_yara_nth_hex_pattern_offset': (['str', 'str', 'int'], 'int'),
    'rt_yara_nth_hex_pattern_length': (['str', 'str', 'int'], 'int'),
    'rt_yara_find_hex_wildcard_raw': (['str', 'int', 'str', 'int', 'int'], 'int'),
    'rt_yara_find_hex_stream': (['str', 'str'], 'int'),
    'rt_yara_pattern_len': (['str'], 'int'),
    'rt_yara_scan_buf_handle': (['int', 'str', 'int', 'int'], 'int'),
}

class TypeChecker:
    def __init__(self):
        self.global_structs: Dict[str, StructDecl] = {}
        self.global_functions: Dict[str, FunctionDecl] = {}
        self.function_overloads: Dict[str, List[FunctionDecl]] = {}
        self.generic_structs: Dict[str, StructDecl] = {}
        self.generic_functions: Dict[str, FunctionDecl] = {}
        self.monomorphized_structs: Dict[str, StructDecl] = {}
        self.monomorphized_functions: Dict[str, FunctionDecl] = {}
        self.current_scope: Scope = Scope()
        self.current_function: Optional[FunctionDecl] = None
        self.loop_depth: int = 0

    def check(self, program: Program):
        # Pass 1: Register all struct declarations and function signatures
        for decl in program.declarations:
            if isinstance(decl, StructDecl):
                if len(decl.type_params) > 0:
                    if decl.name in self.generic_structs:
                        raise SemanticError(f"'{decl.name}' generic struct yapisi zaten tanimlanmis.", decl.line, decl.col)
                    self.generic_structs[decl.name] = decl
                else:
                    if decl.name in self.global_structs:
                        raise SemanticError(f"'{decl.name}' struct yapisi zaten tanimlanmis.", decl.line, decl.col)
                    self.global_structs[decl.name] = decl
            elif isinstance(decl, FunctionDecl):
                if decl.name in BUILTIN_FUNCTIONS or decl.name in ('len', 'thread_create', 'array_push'):
                    raise SemanticError(f"'{decl.name}' yerlesik bir fonksiyondur ve yeniden tanimlanamaz.", decl.line, decl.col)
                if len(decl.type_params) > 0:
                    if decl.name in self.generic_functions:
                        raise SemanticError(f"'{decl.name}' generic fonksiyonu zaten tanimlanmis.", decl.line, decl.col)
                    self.generic_functions[decl.name] = decl
                else:
                    overload_list = self.function_overloads.setdefault(decl.name, [])
                    decl_sig = tuple(p.type_name for p in decl.params)
                    for ex in overload_list:
                        if tuple(p.type_name for p in ex.params) == decl_sig:
                            raise SemanticError(f"'{decl.name}' fonksiyonu zaten tanimlanmis veya yerlesik bir fonksiyondur.", decl.line, decl.col)
                    overload_list.append(decl)
                    if decl.name not in self.global_functions:
                        self.global_functions[decl.name] = decl

        # Pass 2: Type check bodies and statements
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                if len(decl.type_params) > 0:
                    continue
                self.check_function(decl)
            elif isinstance(decl, StructDecl):
                if len(decl.type_params) > 0:
                    continue
                # Struct fields validation
                field_names = set()
                for f in decl.fields:
                    if f.name in field_names:
                        raise SemanticError(f"'{decl.name}' struct yapisinda mukerrer alan: '{f.name}'", f.line, f.col)
                    field_names.add(f.name)
            else:
                self.check_statement(decl)

        # Pass 3: Replace generic templates with monomorphized instances in program.declarations
        new_decls = []
        for decl in program.declarations:
            if isinstance(decl, (StructDecl, FunctionDecl)) and len(getattr(decl, 'type_params', [])) > 0:
                continue
            new_decls.append(decl)
        for s in self.monomorphized_structs.values():
            if s not in new_decls:
                new_decls.insert(0, s)
        for f in self.monomorphized_functions.values():
            if f not in new_decls:
                new_decls.append(f)
        program.declarations = new_decls

    def check_function(self, fn: FunctionDecl):
        self.current_function = fn
        fn_scope = Scope(self.current_scope)
        self.current_scope = fn_scope

        # Define parameters
        for p in fn.params:
            if '<' in p.type_name:
                b_name, t_args = parse_generic_type_str(p.type_name)
                if b_name in self.generic_structs:
                    p.type_name = self.monomorphize_struct(b_name, t_args)
                else:
                    p.type_name = mangle_type_name(p.type_name)
            self.current_scope.define(p.name, p.type_name, is_mut=False)

        if '<' in fn.return_type:
            b_name, t_args = parse_generic_type_str(fn.return_type)
            if b_name in self.generic_structs:
                fn.return_type = self.monomorphize_struct(b_name, t_args)
            else:
                fn.return_type = mangle_type_name(fn.return_type)

        # Check contracts (requires & ensures)
        for req in fn.contract.requires:
            req_type = self.check_expression(req)
            if req_type != 'bool':
                raise SemanticError(f"'requires' on-kosul ifadesi bool olmalidir, '{req_type}' bulundu.", req.line, req.col)

        # For ensures, allow 'return' symbol matching fn.return_type
        if fn.return_type != 'void':
            self.current_scope.define("return", fn.return_type, is_mut=False)

        for ens in fn.contract.ensures:
            ens_type = self.check_expression(ens)
            if ens_type != 'bool':
                raise SemanticError(f"'ensures' son-kosul ifadesi bool olmalidir, '{ens_type}' bulundu.", ens.line, ens.col)

        # Check body
        self.check_block(fn.body)

        # Definite Return analizi: void olmayan fonksiyonlarda tüm dallarda return zorunlu
        if fn.return_type != 'void':
            if not self._definitely_returns(fn.body):
                raise SemanticError(f"Fonksiyon '{fn.name}' dondurme tipi '{fn.return_type}' olarak belirtilmis ancak tum kod dallarinda return bulunmuyor.", fn.line, fn.col)

        self.current_scope = self.current_scope.parent
        self.current_function = None

    def _definitely_returns(self, stmt: Any) -> bool:
        if isinstance(stmt, ReturnStmt):
            return True
        elif isinstance(stmt, Block):
            for s in stmt.statements:
                if self._definitely_returns(s):
                    return True
            return False
        elif isinstance(stmt, IfStmt):
            if stmt.else_branch is None:
                return False
            return self._definitely_returns(stmt.then_branch) and self._definitely_returns(stmt.else_branch)
        elif isinstance(stmt, MatchStmt):
            if not stmt.arms:
                return False
            return all(self._definitely_returns(arm.body) for arm in stmt.arms)
        elif isinstance(stmt, ExprStmt):
            return self._definitely_returns(stmt.expr)
        return False

    def check_block(self, block: Block):
        block_scope = Scope(self.current_scope)
        self.current_scope = block_scope
        for stmt in block.statements:
            self.check_statement(stmt)
        self.current_scope = self.current_scope.parent

    def _check_expr_in_scope(self, expr: Expr, scope: Scope) -> str:
        old_scope = self.current_scope
        self.current_scope = scope
        try:
            return self.check_expression(expr)
        finally:
            self.current_scope = old_scope

    def _check_pattern(self, pattern: Pattern, subj_type: str, scope: Scope):
        if isinstance(pattern, WildcardPattern):
            return
        elif isinstance(pattern, IdentPattern):
            scope.define(pattern.name, subj_type, is_mut=False)
        elif isinstance(pattern, LiteralPattern):
            lit_type = self._check_expr_in_scope(pattern.literal, scope)
            if lit_type != subj_type and not (subj_type == 'float' and lit_type == 'int'):
                raise SemanticError(
                    f"Match desen tipi '{lit_type}' hedef ifade tipi '{subj_type}' ile uyusmuyor.",
                    pattern.literal.line, pattern.literal.col
                )

    def _check_match_exhaustiveness(self, subject: Expr, subj_type: str, arms: List[MatchArm], line: int, col: int):
        # 1. Unconditional wildcard or ident pattern covers everything
        for arm in arms:
            if arm.guard is None:
                if isinstance(arm.pattern, (WildcardPattern, IdentPattern)):
                    return

        # 2. Bool exhaustiveness: must cover true and false
        if subj_type == 'bool':
            covered_true = False
            covered_false = False
            for arm in arms:
                if arm.guard is None and isinstance(arm.pattern, LiteralPattern):
                    if isinstance(arm.pattern.literal, BooleanLiteral):
                        if arm.pattern.literal.value is True:
                            covered_true = True
                        elif arm.pattern.literal.value is False:
                            covered_false = True
            if covered_true and covered_false:
                return
            raise SemanticError(
                "Tuketici olmayan match (non-exhaustive match): bool icin hem true hem false veya '_' kapsanmalidir.",
                line, col
            )

        # 3. For int, str, float or other types, infinite possibilities require wildcard
        raise SemanticError(
            f"Tuketici olmayan match (non-exhaustive match): '{subj_type}' icin tum degerler kapsanmadi, '_' (wildcard) gereklidir.",
            line, col
        )

    def check_match_stmt(self, stmt: MatchStmt):
        subj_type = self.check_expression(stmt.subject)
        self._check_match_exhaustiveness(stmt.subject, subj_type, stmt.arms, stmt.line, stmt.col)

        for arm in stmt.arms:
            arm_scope = Scope(self.current_scope)
            self._check_pattern(arm.pattern, subj_type, arm_scope)
            if arm.guard:
                guard_type = self._check_expr_in_scope(arm.guard, arm_scope)
                if guard_type != 'bool':
                    raise SemanticError(f"Match guard ifadesi 'bool' olmalidir, '{guard_type}' bulundu.", arm.guard.line, arm.guard.col)

            old_scope = self.current_scope
            self.current_scope = arm_scope
            try:
                if isinstance(arm.body, Block):
                    self.check_block(arm.body)
                elif isinstance(arm.body, Stmt):
                    self.check_statement(arm.body)
                elif isinstance(arm.body, Expr):
                    self.check_expression(arm.body)
            finally:
                self.current_scope = old_scope

    def check_match_expr(self, expr: MatchExpr) -> str:
        subj_type = self.check_expression(expr.subject)
        self._check_match_exhaustiveness(expr.subject, subj_type, expr.arms, expr.line, expr.col)

        arm_types = []
        for arm in expr.arms:
            arm_scope = Scope(self.current_scope)
            self._check_pattern(arm.pattern, subj_type, arm_scope)
            if arm.guard:
                guard_type = self._check_expr_in_scope(arm.guard, arm_scope)
                if guard_type != 'bool':
                    raise SemanticError(f"Match guard ifadesi 'bool' olmalidir, '{guard_type}' bulundu.", arm.guard.line, arm.guard.col)

            old_scope = self.current_scope
            self.current_scope = arm_scope
            try:
                if isinstance(arm.body, Block):
                    self.check_block(arm.body)
                    last_stmt = arm.body.statements[-1] if arm.body.statements else None
                    if isinstance(last_stmt, ExprStmt):
                        b_type = getattr(last_stmt.expr, 'inferred_type', 'void')
                    elif isinstance(last_stmt, ReturnStmt) and last_stmt.value:
                        b_type = getattr(last_stmt.value, 'inferred_type', 'void')
                    else:
                        b_type = 'void'
                elif isinstance(arm.body, Expr):
                    b_type = self.check_expression(arm.body)
                elif isinstance(arm.body, ExprStmt):
                    b_type = self.check_expression(arm.body.expr)
                else:
                    self.check_statement(arm.body)
                    b_type = 'void'
            finally:
                self.current_scope = old_scope
            arm_types.append(b_type)

        if not arm_types:
            expr.inferred_type = 'void'
            return 'void'

        first_t = arm_types[0]
        for i, t in enumerate(arm_types[1:], start=1):
            if t != first_t and not (first_t == 'float' and t == 'int'):
                raise SemanticError(
                    f"Match kollarinin donus tipleri uyumsuz: '{first_t}' vs '{t}'.",
                    expr.arms[i].line, expr.arms[i].col
                )
        expr.inferred_type = first_t
        return first_t

    def _substitute_type(self, type_str: str, type_map: Dict[str, str]) -> str:
        if not type_str:
            return type_str
        is_array = type_str.endswith('[]')
        base = type_str[:-2] if is_array else type_str

        if base in type_map:
            sub = type_map[base]
            return f"{sub}[]" if is_array else sub

        if '<' in base:
            g_base, g_args = parse_generic_type_str(base)
            sub_args = [self._substitute_type(a, type_map) for a in g_args]
            mangled = self.monomorphize_struct(g_base, sub_args)
            return f"{mangled}[]" if is_array else mangled

        return type_str

    def _unify_types(self, pattern: str, actual: str, type_params: List[str], type_map: Dict[str, str]):
        if pattern in type_params:
            if pattern in type_map and type_map[pattern] != actual:
                raise SemanticError(f"Tip parametresi '{pattern}' icin celiskili tipler cikarildi: '{type_map[pattern]}' ve '{actual}'.")
            type_map[pattern] = actual
            return

        if pattern.endswith('[]') and actual.endswith('[]'):
            self._unify_types(pattern[:-2], actual[:-2], type_params, type_map)
            return

        p_base, p_args = parse_generic_type_str(pattern)
        if p_args:
            a_base, a_args = parse_generic_type_str(actual)
            if not a_args and actual.startswith(p_base + "_"):
                suffix = actual[len(p_base) + 1:]
                a_args = suffix.split('_')
            if len(p_args) == len(a_args):
                for pa, aa in zip(p_args, a_args):
                    self._unify_types(pa, aa, type_params, type_map)

    def _substitute_body(self, node: Any, type_map: Dict[str, str]) -> Any:
        if isinstance(node, LetDecl):
            if node.type_annotation:
                node.type_annotation = self._substitute_type(node.type_annotation, type_map)
            if node.initializer:
                self._substitute_body(node.initializer, type_map)
        elif isinstance(node, Block):
            for s in node.statements:
                self._substitute_body(s, type_map)
        elif isinstance(node, IfStmt):
            self._substitute_body(node.condition, type_map)
            self._substitute_body(node.then_branch, type_map)
            if node.else_branch:
                self._substitute_body(node.else_branch, type_map)
        elif isinstance(node, WhileStmt):
            self._substitute_body(node.condition, type_map)
            self._substitute_body(node.body, type_map)
        elif isinstance(node, ForRangeStmt):
            self._substitute_body(node.start, type_map)
            self._substitute_body(node.end, type_map)
            self._substitute_body(node.body, type_map)
        elif isinstance(node, ReturnStmt):
            if node.value:
                self._substitute_body(node.value, type_map)
        elif isinstance(node, AssignStmt):
            self._substitute_body(node.value, type_map)
            if node.target:
                self._substitute_body(node.target, type_map)
        elif isinstance(node, ExprStmt):
            self._substitute_body(node.expr, type_map)
        elif isinstance(node, BinaryOp):
            self._substitute_body(node.left, type_map)
            self._substitute_body(node.right, type_map)
        elif isinstance(node, UnaryOp):
            self._substitute_body(node.operand, type_map)
        elif isinstance(node, FunctionCall):
            if node.type_args:
                node.type_args = [self._substitute_type(t, type_map) for t in node.type_args]
            for a in node.args:
                self._substitute_body(a, type_map)
        elif isinstance(node, StructInit):
            if node.type_args:
                node.type_args = [self._substitute_type(t, type_map) for t in node.type_args]
            if '<' in node.struct_name:
                b, args = parse_generic_type_str(node.struct_name)
                sub_args = [self._substitute_type(a, type_map) for a in args]
                node.struct_name = self.monomorphize_struct(b, sub_args)
            elif node.struct_name in self.generic_structs and node.type_args:
                node.struct_name = self.monomorphize_struct(node.struct_name, node.type_args)
                node.type_args = []
            for f in node.fields:
                self._substitute_body(f.value, type_map)
        elif isinstance(node, CastExpr):
            node.target_type = self._substitute_type(node.target_type, type_map)
            self._substitute_body(node.expr, type_map)
        elif isinstance(node, (MatchStmt, MatchExpr)):
            self._substitute_body(node.subject, type_map)
            for arm in node.arms:
                if arm.guard:
                    self._substitute_body(arm.guard, type_map)
                self._substitute_body(arm.body, type_map)
        return node

    def _result_shape(self, type_name: str):
        """Bir struct tipinin Result semantigi tasiyip tasimadigini dondurur.

        Kural: 'is_ok: bool', 'value: T', 'error: E' alanlarina sahip her struct
        Result olarak kabul edilir. Donus: (T, E) veya None.
        """
        if not type_name:
            return None
        decl = self.global_structs.get(type_name)
        if decl is None:
            return None
        fields = {f.name: f.type_name for f in decl.fields}
        if not {'is_ok', 'value', 'error'} <= set(fields):
            return None
        if fields['is_ok'] != 'bool':
            return None
        return (fields['value'], fields['error'])

    def monomorphize_struct(self, base_name: str, type_args: List[str]) -> str:
        if base_name not in self.generic_structs:
            if base_name in self.global_structs:
                return base_name
            raise SemanticError(f"Tanimlanmamis generic struct: '{base_name}'")
        template = self.generic_structs[base_name]
        if len(template.type_params) != len(type_args):
            raise SemanticError(
                f"'{base_name}' struct yapisi {len(template.type_params)} tip parametresi bekliyor, {len(type_args)} verildi.",
                template.line, template.col
            )
        clean_args = [mangle_type_arg(a) for a in type_args]
        mangled_name = f"{base_name}_{'_'.join(clean_args)}"
        if mangled_name in self.global_structs:
            return mangled_name

        type_map = dict(zip(template.type_params, type_args))
        concrete_fields = []
        for f in template.fields:
            c_t = self._substitute_type(f.type_name, type_map)
            c_t = mangle_type_name(c_t)
            concrete_fields.append(StructField(name=f.name, type_name=c_t, line=f.line, col=f.col))

        concrete_struct = StructDecl(
            name=mangled_name,
            fields=concrete_fields,
            type_params=[],
            line=template.line,
            col=template.col
        )
        self.global_structs[mangled_name] = concrete_struct
        self.monomorphized_structs[mangled_name] = concrete_struct
        return mangled_name

    def monomorphize_function(self, base_name: str, type_args: List[str]) -> str:
        if base_name not in self.generic_functions:
            if base_name in self.global_functions:
                return base_name
            raise SemanticError(f"Tanimlanmamis generic fonksiyon: '{base_name}'")
        template = self.generic_functions[base_name]
        if len(template.type_params) != len(type_args):
            raise SemanticError(
                f"'{base_name}' fonksiyonu {len(template.type_params)} tip parametresi bekliyor, {len(type_args)} verildi.",
                template.line, template.col
            )
        clean_args = [mangle_type_arg(a) for a in type_args]
        mangled_name = f"{base_name}_{'_'.join(clean_args)}"
        if mangled_name in self.global_functions:
            return mangled_name

        type_map = dict(zip(template.type_params, type_args))
        concrete_params = []
        for p in template.params:
            p_t = self._substitute_type(p.type_name, type_map)
            p_t = mangle_type_name(p_t)
            concrete_params.append(Param(name=p.name, type_name=p_t, line=p.line, col=p.col))
        concrete_ret = self._substitute_type(template.return_type, type_map)
        concrete_ret = mangle_type_name(concrete_ret)

        cloned_body = copy.deepcopy(template.body)
        self._substitute_body(cloned_body, type_map)
        cloned_contract = copy.deepcopy(template.contract)
        for req in cloned_contract.requires:
            self._substitute_body(req, type_map)
        for ens in cloned_contract.ensures:
            self._substitute_body(ens, type_map)

        concrete_fn = FunctionDecl(
            name=mangled_name,
            params=concrete_params,
            return_type=concrete_ret,
            contract=cloned_contract,
            body=cloned_body,
            is_simd=template.is_simd,
            type_params=[],
            line=template.line,
            col=template.col
        )
        self.global_functions[mangled_name] = concrete_fn
        self.monomorphized_functions[mangled_name] = concrete_fn

        # Type-check the monomorphized function body.
        # ONEMLI: check_function current_function/current_scope'u degistirir.
        # Ic ice monomorfizasyonda dis fonksiyonun baglami korunmalidir; aksi
        # halde cagiran fonksiyonun sonraki return ifadeleri denetlenmez.
        saved_fn = self.current_function
        saved_scope = self.current_scope
        try:
            self.check_function(concrete_fn)
        finally:
            self.current_function = saved_fn
            self.current_scope = saved_scope
        return mangled_name

    def _get_root_identifier(self, expr: Expr) -> Optional[Identifier]:
        if isinstance(expr, Identifier):
            return expr
        elif isinstance(expr, MemberAccess):
            return self._get_root_identifier(expr.object)
        elif isinstance(expr, IndexAccess):
            return self._get_root_identifier(expr.array)
        return None

    def check_statement(self, stmt: Stmt):
        if isinstance(stmt, (StructDecl, ImportStmt)):
            pass

        elif isinstance(stmt, Block):
            self.check_block(stmt)

        elif isinstance(stmt, LetDecl):
            if stmt.type_annotation and '<' in stmt.type_annotation:
                b_name, t_args = parse_generic_type_str(stmt.type_annotation)
                if b_name in self.generic_structs:
                    stmt.type_annotation = self.monomorphize_struct(b_name, t_args)
                else:
                    stmt.type_annotation = mangle_type_name(stmt.type_annotation)
            inferred = "void"
            if stmt.initializer:
                inferred = self.check_expression(stmt.initializer)
            actual_type = stmt.type_annotation or inferred
            if stmt.type_annotation and stmt.initializer and stmt.type_annotation != inferred:
                if stmt.type_annotation.endswith('[]') and isinstance(stmt.initializer, ArrayLiteral) and len(stmt.initializer.elements) == 0:
                    inferred = stmt.type_annotation
                    stmt.initializer.inferred_type = stmt.type_annotation
                elif not (stmt.type_annotation == 'float' and inferred == 'int'):
                    raise SemanticError(
                        f"Tip uyumsuzlugu: '{stmt.name}' degiskeni '{stmt.type_annotation}' olarak tanimlandi fakat '{inferred}' atandi.",
                        stmt.line, stmt.col
                    )
            if self.current_scope.defined_here(stmt.name):
                raise SemanticError(
                    f"'{stmt.name}' bu blokta zaten tanimli. Ayni blokta yeniden "
                    f"tanimlama (shadowing) desteklenmez; farkli bir ad kullanin "
                    f"veya onceki tanimi kaldirin.",
                    stmt.line, stmt.col
                )
            self.current_scope.define(stmt.name, actual_type, is_mut=stmt.is_mut)

        elif isinstance(stmt, AssignStmt):
            target = stmt.target
            if target is None:
                # Fallback to name
                sym = self.current_scope.lookup(stmt.name)
                if not sym:
                    raise SemanticError(f"Tanimlanmamis degiskene atama: '{stmt.name}'", stmt.line, stmt.col)
                if not sym.is_mut:
                    raise SemanticError(f"Degistirilemez (immutable) degiskene atama yapilamaz: '{stmt.name}'. 'let mut' kullanin.", stmt.line, stmt.col)
                val_type = self.check_expression(stmt.value)
                if sym.type_name != val_type and not (sym.type_name == 'float' and val_type == 'int'):
                    raise SemanticError(f"Tip uyumsuzlugu: '{sym.type_name}' tipindeki '{stmt.name}' degiskenine '{val_type}' atanamaz.", stmt.line, stmt.col)
            elif isinstance(target, Identifier):
                sym = self.current_scope.lookup(target.name)
                if not sym:
                    raise SemanticError(f"Tanimlanmamis degiskene atama: '{target.name}'", target.line, target.col)
                if not sym.is_mut:
                    raise SemanticError(f"Degistirilemez (immutable) degiskene atama yapilamaz: '{target.name}'. 'let mut' kullanin.", target.line, target.col)
                val_type = self.check_expression(stmt.value)
                if sym.type_name != val_type and not (sym.type_name == 'float' and val_type == 'int'):
                    raise SemanticError(f"Tip uyumsuzlugu: '{sym.type_name}' tipindeki '{target.name}' degiskenine '{val_type}' atanamaz.", target.line, target.col)
            else:
                # MemberAccess or IndexAccess target
                root_id = self._get_root_identifier(target)
                if root_id:
                    sym = self.current_scope.lookup(root_id.name)
                    if sym and not sym.is_mut:
                        raise SemanticError(f"Degistirilemez (immutable) nesneye atama yapilamaz: '{root_id.name}'. 'let mut' kullanin.", target.line, target.col)
                target_type = self.check_expression(target)
                val_type = self.check_expression(stmt.value)
                if target_type != val_type and not (target_type == 'float' and val_type == 'int'):
                    raise SemanticError(f"Tip uyumsuzlugu: '{target_type}' hedefine '{val_type}' degeri atanamaz.", stmt.line, stmt.col)

        elif isinstance(stmt, IfStmt):
            cond_type = self.check_expression(stmt.condition)
            if cond_type != 'bool':
                raise SemanticError(f"'if' kosulu bool olmalidir, '{cond_type}' bulundu.", stmt.line, stmt.col)
            self.check_block(stmt.then_branch)
            if stmt.else_branch:
                self.check_block(stmt.else_branch)

        elif isinstance(stmt, WhileStmt):
            cond_type = self.check_expression(stmt.condition)
            if cond_type != 'bool':
                raise SemanticError(f"'while' kosulu bool olmalidir, '{cond_type}' bulundu.", stmt.line, stmt.col)
            for inv in stmt.invariants:
                inv_type = self.check_expression(inv)
                if inv_type != 'bool':
                    raise SemanticError(f"'invariant' kosulu bool olmalidir, '{inv_type}' bulundu.", inv.line, inv.col)
            self.loop_depth += 1
            try:
                self.check_block(stmt.body)
            finally:
                self.loop_depth -= 1

        elif isinstance(stmt, ForRangeStmt):
            st_type = self.check_expression(stmt.start)
            end_type = self.check_expression(stmt.end)
            if st_type != 'int' or end_type != 'int':
                raise SemanticError("For araligi tam sayi (int..int) olmalidir.", stmt.line, stmt.col)
            loop_scope = Scope(self.current_scope)
            self.current_scope = loop_scope
            self.current_scope.define(stmt.var_name, 'int', is_mut=False)
            for inv in stmt.invariants:
                inv_type = self.check_expression(inv)
                if inv_type != 'bool':
                    raise SemanticError(f"'invariant' kosulu bool olmalidir, '{inv_type}' bulundu.", inv.line, inv.col)
            self.loop_depth += 1
            for s in stmt.body.statements:
                self.check_statement(s)
            self.loop_depth -= 1
            self.current_scope = self.current_scope.parent

        elif isinstance(stmt, ReturnStmt):
            if self.current_function:
                expected = self.current_function.return_type
                if stmt.value:
                    actual = self.check_expression(stmt.value)
                    if expected != actual and not (expected == 'float' and actual == 'int'):
                        raise SemanticError(f"Fonksiyon '{expected}' dondurmeli ancak '{actual}' donduruldu.", stmt.line, stmt.col)
                elif expected != 'void':
                    raise SemanticError(f"Fonksiyon '{expected}' dondurmeli ancak bos return yapildi.", stmt.line, stmt.col)

        elif isinstance(stmt, DeferStmt):
            if isinstance(stmt.stmt, Block):
                self.check_block(stmt.stmt)
            else:
                self.check_statement(stmt.stmt)

        elif isinstance(stmt, PrintStmt):
            for arg in stmt.args:
                self.check_expression(arg)

        elif isinstance(stmt, VerifyStmt):
            cond_type = self.check_expression(stmt.condition)
            if cond_type != 'bool':
                raise SemanticError(f"'verify' kosulu bool olmalidir, '{cond_type}' bulundu.", stmt.line, stmt.col)

        elif isinstance(stmt, (BreakStmt, ContinueStmt)):
            if self.loop_depth <= 0:
                kw = 'break' if isinstance(stmt, BreakStmt) else 'continue'
                raise SemanticError(
                    f"'{kw}' yalnizca bir dongu (while/for) icinde kullanilabilir.",
                    stmt.line, stmt.col
                )

        elif isinstance(stmt, MatchStmt):
            self.check_match_stmt(stmt)

        elif isinstance(stmt, ExprStmt):
            self.check_expression(stmt.expr)

    def check_expression(self, expr: Expr) -> str:
        if isinstance(expr, NumberLiteral):
            expr.inferred_type = 'float' if expr.is_float else 'int'
            return expr.inferred_type

        elif isinstance(expr, StringLiteral):
            expr.inferred_type = 'str'
            return 'str'

        elif isinstance(expr, BooleanLiteral):
            expr.inferred_type = 'bool'
            return 'bool'

        elif isinstance(expr, Identifier):
            sym = self.current_scope.lookup(expr.name)
            if not sym:
                raise SemanticError(f"Tanimlanmamis degisken: '{expr.name}'", expr.line, expr.col)
            expr.inferred_type = sym.type_name
            return sym.type_name

        elif isinstance(expr, BinaryOp):
            l_type = self.check_expression(expr.left)
            r_type = self.check_expression(expr.right)

            # Arithmetic ops
            if expr.op in ('+', '-', '*', '/', '%'):
                if l_type == 'str' and expr.op == '+' and r_type == 'str':
                    expr.inferred_type = 'str'
                    return 'str'
                if l_type in ('int', 'float') and r_type in ('int', 'float'):
                    if l_type == 'float' or r_type == 'float':
                        ret_type = 'float'
                    else:
                        ret_type = 'int'
                    expr.inferred_type = ret_type
                    return ret_type
                raise SemanticError(f"'{expr.op}' islemi '{l_type}' ve '{r_type}' arasinda gecersizdir.", expr.line, expr.col)

            # Comparisons
            elif expr.op in ('<', '<=', '>', '>='):
                if (l_type in ('int', 'float') and r_type in ('int', 'float')) or (l_type == 'str' and r_type == 'str'):
                    expr.inferred_type = 'bool'
                    return 'bool'
                raise SemanticError(f"'{expr.op}' karsilastirmasi uyumsuz tipler arasinda yapilamaz: '{l_type}' ve '{r_type}'.", expr.line, expr.col)

            elif expr.op in ('==', '!='):
                if l_type == r_type or (l_type in ('int', 'float') and r_type in ('int', 'float')):
                    expr.inferred_type = 'bool'
                    return 'bool'
                raise SemanticError(f"'{expr.op}' esitlik karsilastirmasi uyumsuz tipler arasinda yapilamaz: '{l_type}' ve '{r_type}'.", expr.line, expr.col)

            # Logicals
            elif expr.op in ('and', 'or'):
                if l_type != 'bool' or r_type != 'bool':
                    raise SemanticError(f"Mantiksal '{expr.op}' isleci yalnizca bool tiplerle kullanilabilir.", expr.line, expr.col)
                expr.inferred_type = 'bool'
                return 'bool'

        elif isinstance(expr, UnaryOp):
            operand_type = self.check_expression(expr.operand)
            if expr.op == 'not':
                if operand_type != 'bool':
                    raise SemanticError(f"'not' isleci bool bekler, '{operand_type}' bulundu.", expr.line, expr.col)
                expr.inferred_type = 'bool'
                return 'bool'
            elif expr.op in ('+', '-'):
                if operand_type not in ('int', 'float'):
                    raise SemanticError(f"'{expr.op}' sayisal tip bekler, '{operand_type}' bulundu.", expr.line, expr.col)
                expr.inferred_type = operand_type
                return operand_type

        elif isinstance(expr, TryExpr):
            inner_type = self.check_expression(expr.expr)
            result_struct = self._result_shape(inner_type)
            if result_struct is None:
                raise SemanticError(
                    f"'?' operatoru Result benzeri bir tip bekler (is_ok/value/error alanlari), "
                    f"'{inner_type}' verildi.",
                    expr.line, expr.col
                )
            value_t, error_t = result_struct

            if self.current_function is None:
                raise SemanticError("'?' yalnizca bir fonksiyon govdesinde kullanilabilir.", expr.line, expr.col)

            fn_ret = self.current_function.return_type
            fn_ret_shape = self._result_shape(fn_ret)
            if fn_ret_shape is None:
                raise SemanticError(
                    f"'?' kullanilan fonksiyon 'Result' dondurmeli; '{self.current_function.name}' "
                    f"'{fn_ret}' donduruyor.",
                    expr.line, expr.col
                )
            fn_value_t, fn_error_t = fn_ret_shape
            if error_t != fn_error_t:
                raise SemanticError(
                    f"'?' hata tipi uyusmuyor: ifade '{error_t}', fonksiyon '{fn_error_t}' donduruyor.",
                    expr.line, expr.col
                )

            expr.inferred_type = value_t
            expr.try_source_type = inner_type
            expr.try_target_type = fn_ret
            expr.try_value_type = value_t
            expr.try_error_type = error_t
            expr.try_target_value_type = fn_value_t
            return value_t

        elif isinstance(expr, CastExpr):
            inner_type = self.check_expression(expr.expr)
            target = expr.target_type
            if target == 'str':
                raise SemanticError(
                    "'as str' desteklenmez. Tamsayiyi metne cevirmek icin "
                    "'int_to_str(x)' kullanin.",
                    expr.line, expr.col
                )
            if target not in ('int', 'float', 'bool'):
                raise SemanticError(f"Gecersiz acik tip donusumu hedefi: '{target}'.", expr.line, expr.col)
            expr.inferred_type = target
            return target

        elif isinstance(expr, MatchExpr):
            return self.check_match_expr(expr)

        elif isinstance(expr, StructInit):
            s_name = expr.struct_name
            if '<' in s_name or expr.type_args or s_name in self.generic_structs:
                if '<' in s_name:
                    b_name, t_args = parse_generic_type_str(s_name)
                elif expr.type_args:
                    b_name = s_name
                    t_args = expr.type_args
                else:
                    b_name = s_name
                    template = self.generic_structs.get(b_name)
                    if not template:
                        raise SemanticError(f"Tanimlanmamis generic struct: '{b_name}'", expr.line, expr.col)
                    type_map = {}
                    field_types = {f.name: f.type_name for f in template.fields}
                    for fi in expr.fields:
                        fi_t = self.check_expression(fi.value)
                        if fi.field_name in field_types:
                            self._unify_types(field_types[fi.field_name], fi_t, template.type_params, type_map)
                    t_args = [type_map.get(tp) for tp in template.type_params]
                    if any(t is None for t in t_args):
                        raise SemanticError(f"'{b_name}' struct yapisi icin tip parametreleri cikarilamadi.", expr.line, expr.col)
                mangled = self.monomorphize_struct(b_name, t_args)
                expr.struct_name = mangled
                expr.type_args = []
                s_name = mangled

            if s_name not in self.global_structs:
                raise SemanticError(f"Tanimlanmamis struct yapisi: '{s_name}'", expr.line, expr.col)
            s_decl = self.global_structs[s_name]

            expected_fields = {f.name: f.type_name for f in s_decl.fields}
            provided_fields = {}

            for f_init in expr.fields:
                if f_init.field_name not in expected_fields:
                    raise SemanticError(f"'{s_name}' yapisinda '{f_init.field_name}' alani bulunmuyor.", f_init.line, f_init.col)
                val_t = self.check_expression(f_init.value)
                exp_t = expected_fields[f_init.field_name]
                if val_t != exp_t and not (exp_t == 'float' and val_t == 'int'):
                    raise SemanticError(f"'{s_name}.{f_init.field_name}' alani '{exp_t}' bekliyor, '{val_t}' verildi.", f_init.line, f_init.col)
                provided_fields[f_init.field_name] = val_t

            for exp_f in expected_fields:
                if exp_f not in provided_fields:
                    raise SemanticError(f"'{s_name}' baslatilirken '{exp_f}' alani eksik birakildi.", expr.line, expr.col)

            expr.inferred_type = s_name
            return s_name

        elif isinstance(expr, MemberAccess):
            obj_type = self.check_expression(expr.object)
            if obj_type not in self.global_structs:
                raise SemanticError(f"'{obj_type}' bir struct tipi degildir, '{expr.member}' alanina erisilemez.", expr.line, expr.col)
            s_decl = self.global_structs[obj_type]
            f_decl = next((f for f in s_decl.fields if f.name == expr.member), None)
            if not f_decl:
                raise SemanticError(f"'{obj_type}' struct yapisinda '{expr.member}' alani bulunmuyor.", expr.line, expr.col)
            expr.inferred_type = f_decl.type_name
            return f_decl.type_name

        elif isinstance(expr, ArrayLiteral):
            if not expr.elements:
                arr_t = "int[]"
            else:
                elem_types = [self.check_expression(e) for e in expr.elements]
                t0 = elem_types[0]
                for i, t in enumerate(elem_types[1:], start=1):
                    if t != t0 and not (t0 == 'float' and t == 'int'):
                        raise SemanticError(f"Dizi elemanlari ayni tipte olmalidir: '{t0}' bekleniyordu fakat '{t}' bulundu.", expr.elements[i].line, expr.elements[i].col)
                arr_t = f"{t0}[]"
            expr.inferred_type = arr_t
            return arr_t

        elif isinstance(expr, IndexAccess):
            arr_t = self.check_expression(expr.array)
            idx_t = self.check_expression(expr.index)
            if idx_t != 'int':
                raise SemanticError(f"Dizi indeksi 'int' olmalidir, '{idx_t}' bulundu.", expr.index.line, expr.index.col)
            if arr_t == 'str':
                expr.inferred_type = 'str'
                return 'str'
            if not arr_t.endswith('[]'):
                raise SemanticError(f"'{arr_t}' tipi indekslenemez. Yalnizca diziler ve metinler indekslenebilir.", expr.line, expr.col)
            elem_t = arr_t[:-2]
            expr.inferred_type = elem_t
            return elem_t

        elif isinstance(expr, FunctionCall):
            if expr.callee in self.generic_functions:
                template = self.generic_functions[expr.callee]
                if expr.type_args:
                    t_args = [self._substitute_type(t, {}) for t in expr.type_args]
                else:
                    type_map = {}
                    if len(expr.args) != len(template.params):
                        raise SemanticError(
                            f"'{expr.callee}' {len(template.params)} parametre bekliyor fakat {len(expr.args)} arguman verildi.",
                            expr.line, expr.col
                        )
                    for p, a in zip(template.params, expr.args):
                        a_t = self.check_expression(a)
                        self._unify_types(p.type_name, a_t, template.type_params, type_map)
                    t_args = [type_map.get(tp) for tp in template.type_params]
                    if any(t is None for t in t_args):
                        raise SemanticError(f"'{expr.callee}' fonksiyonu icin tip parametreleri cikarilamadi.", expr.line, expr.col)
                mangled = self.monomorphize_function(expr.callee, t_args)
                expr.callee = mangled
                expr.type_args = []
                target_fn = self.global_functions[mangled]
                arg_types = [self.check_expression(a) for a in expr.args]
                for i, (a_t, p) in enumerate(zip(arg_types, target_fn.params)):
                    if a_t != p.type_name and not (p.type_name == 'float' and a_t == 'int'):
                        raise SemanticError(
                            f"'{mangled}' cagrisinda '{p.name}' parametresi icin tip uyumsuzlugu: '{p.type_name}' bekleniyordu, '{a_t}' verildi.",
                            expr.args[i].line, expr.args[i].col
                        )
                expr.inferred_type = target_fn.return_type
                expr.resolved_function = target_fn
                return target_fn.return_type

            # Special builtin 'len'
            if expr.callee == 'len':
                if len(expr.args) != 1:
                    raise SemanticError(f"'len' fonksiyonu 1 arguman bekler, {len(expr.args)} verildi.", expr.line, expr.col)
                arg_t = self.check_expression(expr.args[0])
                if not (arg_t.endswith('[]') or arg_t == 'str'):
                    raise SemanticError(f"'len' fonksiyonu dizi veya str bekler, '{arg_t}' verildi.", expr.line, expr.col)
                expr.inferred_type = 'int'
                return 'int'

            # Special generic 'array_push'
            if expr.callee == 'array_push':
                if len(expr.args) != 2:
                    raise SemanticError(f"'array_push' fonksiyonu 2 arguman bekler (dizi, eleman), {len(expr.args)} verildi.", expr.line, expr.col)
                arr_t = self.check_expression(expr.args[0])
                if not arr_t.endswith('[]'):
                    raise SemanticError(f"'array_push' ilk arguman olarak dizi bekler, '{arr_t}' verildi.", expr.line, expr.col)
                elem_t = arr_t[:-2]
                val_t = self.check_expression(expr.args[1])
                if val_t != elem_t:
                    raise SemanticError(f"'array_push' tip uyumsuzlugu: '{elem_t}' bekleniyordu fakat '{val_t}' verildi.", expr.line, expr.col)
                expr.inferred_type = arr_t
                return arr_t

            # Special builtin 'thread_create'
            if expr.callee == 'thread_create':
                if len(expr.args) != 2:
                    raise SemanticError(f"'thread_create' 2 arguman bekler (fonksiyon_adi, arguman), {len(expr.args)} verildi.", expr.line, expr.col)
                fn_arg = expr.args[0]
                if not isinstance(fn_arg, Identifier):
                    raise SemanticError("'thread_create' ilk parametre olarak fonksiyon adi bekler.", fn_arg.line, fn_arg.col)
                target_fn = self.global_functions.get(fn_arg.name)
                if not target_fn:
                    raise SemanticError(f"'thread_create' icin tanimsiz fonksiyon: '{fn_arg.name}'", fn_arg.line, fn_arg.col)
                if len(target_fn.params) != 1 or target_fn.params[0].type_name != 'int':
                    raise SemanticError(f"Thread fonksiyonu '{fn_arg.name}' tek bir 'int' parametresi almalidir.", fn_arg.line, fn_arg.col)
                if target_fn.return_type not in ('void', 'int'):
                    raise SemanticError(f"Thread fonksiyonu '{fn_arg.name}' donus tipi 'void' veya 'int' olmalidir, '{target_fn.return_type}' bulundu.", fn_arg.line, fn_arg.col)
                val_t = self.check_expression(expr.args[1])
                if val_t != 'int':
                    raise SemanticError(f"'thread_create' ikinci parametresi 'int' olmalidir, '{val_t}' verildi.", expr.args[1].line, expr.args[1].col)
                expr.inferred_type = 'int'
                return 'int'

            # Other builtins
            if expr.callee in BUILTIN_FUNCTIONS:
                param_types, ret_type = BUILTIN_FUNCTIONS[expr.callee]
                if len(expr.args) != len(param_types):
                    raise SemanticError(f"'{expr.callee}' {len(param_types)} parametre bekler, {len(expr.args)} verildi.", expr.line, expr.col)
                for i, (arg, exp_t) in enumerate(zip(expr.args, param_types)):
                    act_t = self.check_expression(arg)
                    if act_t != exp_t and not (exp_t == 'float' and act_t == 'int'):
                        if exp_t.endswith('[]') and isinstance(arg, ArrayLiteral) and len(arg.elements) == 0:
                            arg.inferred_type = exp_t
                        else:
                            raise SemanticError(f"'{expr.callee}' cagrisinda {i+1}. parametre '{exp_t}' bekleniyordu, '{act_t}' verildi.", arg.line, arg.col)
                expr.inferred_type = ret_type
                return ret_type

            # User-defined functions
            candidates = self.function_overloads.get(expr.callee)
            if not candidates:
                if expr.callee in self.global_functions:
                    candidates = [self.global_functions[expr.callee]]
                else:
                    raise SemanticError(f"Bilinmeyen fonksiyon cagrisi: '{expr.callee}'", expr.line, expr.col)

            arg_types = [self.check_expression(a) for a in expr.args]

            matched = None
            for cand in candidates:
                if len(cand.params) != len(arg_types):
                    continue
                match = True
                for a_t, p in zip(arg_types, cand.params):
                    if a_t != p.type_name and not (p.type_name == 'float' and a_t == 'int'):
                        match = False
                        break
                if match:
                    matched = cand
                    break

            if not matched:
                if len(candidates) == 1:
                    fn_decl = candidates[0]
                    if len(expr.args) != len(fn_decl.params):
                        raise SemanticError(
                            f"'{expr.callee}' {len(fn_decl.params)} parametre bekliyor fakat {len(expr.args)} arguman verildi.",
                            expr.line, expr.col
                        )
                    for arg_expr, param in zip(expr.args, fn_decl.params):
                        act_t = getattr(arg_expr, 'inferred_type', None) or self.check_expression(arg_expr)
                        if act_t != param.type_name and not (param.type_name == 'float' and act_t == 'int'):
                            if param.type_name.endswith('[]') and isinstance(arg_expr, ArrayLiteral) and len(arg_expr.elements) == 0:
                                arg_expr.inferred_type = param.type_name
                            else:
                                raise SemanticError(
                                    f"'{expr.callee}' cagrisinda '{param.name}' parametresi icin tip uyumsuzlugu: '{param.type_name}' bekleniyordu, '{act_t}' verildi.",
                                    arg_expr.line, arg_expr.col
                                )
                else:
                    sig_str = ", ".join(arg_types)
                    raise SemanticError(
                        f"'{expr.callee}({sig_str})' cagrisi icin uygun imzaya sahip fonksiyon bulunamadi.",
                        expr.line, expr.col
                    )
                matched = candidates[0]

            expr.inferred_type = matched.return_type
            expr.resolved_function = matched
            return matched.return_type

        return "void"
