"""
Axiom Programming Language (λx) - C99 Native Code Generator
"""
import os
from typing import List, Optional
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

def _is_borrowed_str(expr) -> bool:
    from axiom.ast_nodes import Identifier, MemberAccess, IndexAccess
    return isinstance(expr, (Identifier, MemberAccess, IndexAccess))

def c_type_name(t_name: str) -> str:
    if not t_name:
        return 'ax_int'
    t_name = mangle_type_name(t_name)
    if t_name == 'int':
        return 'ax_int'
    if t_name == 'float':
        return 'ax_float'
    if t_name == 'bool':
        return 'ax_bool'
    if t_name == 'str':
        return 'ax_str'
    if t_name == 'void':
        return 'void'
    if t_name.endswith('[]'):
        elem_t = t_name[:-2]
        return f"ax_array_{elem_t}"
    return f"ax_{t_name}"

BUILTIN_MAP = {
    'tcp_connect': 'axiom_tcp_connect',
    'tcp_send': 'axiom_tcp_send',
    'tcp_recv': 'axiom_tcp_recv',
    'socket_close': 'axiom_socket_close',
    'time_now_ms': 'axiom_time_now_ms',
    'file_read': 'axiom_file_read',
    'file_write': 'axiom_file_write',
    'file_exists': 'axiom_file_exists',
    'file_size': 'axiom_file_size',
    'is_directory': 'axiom_is_directory',
    'list_dir': 'axiom_list_dir',
    'remove_file': 'axiom_remove_file',
    'rename_file': 'axiom_rename_file',
    'create_dir': 'axiom_create_dir',
    'os_exec': 'axiom_os_exec',
    'os_exec_argv': 'axiom_os_exec_argv',
    'compile_c': 'axiom_compile_c',
    'os_getenv': 'axiom_os_getenv',
    'str_contains': 'axiom_str_contains',
    'str_starts_with': 'axiom_str_starts_with',
    'str_ends_with': 'axiom_str_ends_with',
    'str_trim': 'axiom_str_trim',
    'str_char_at': 'axiom_str_char_at',
    'str_sub': 'axiom_str_sub',
    'str_len': 'axiom_str_len',
    'rt_str_len': 'axiom_str_len',
    'str_byte_len': 'axiom_str_byte_len',
    'rt_str_byte_len': 'axiom_str_byte_len',
    'utf8_codepoint_count': 'axiom_utf8_codepoint_count',
    'rt_unicode_nfd': 'axiom_unicode_nfd',
    'rt_unicode_nfc': 'axiom_unicode_nfc',
    'rt_unicode_is_nfd': 'axiom_unicode_is_nfd',
    'rt_unicode_is_nfc': 'axiom_unicode_is_nfc',
    'rt_unicode_normalize': 'axiom_unicode_normalize',
    'rt_unicode_ucd_version': 'axiom_unicode_ucd_version',
    'rt_utf8_codepoint_count': 'axiom_utf8_codepoint_count',
    'str_grapheme_len': 'axiom_str_grapheme_len',
    'rt_str_grapheme_len': 'axiom_str_grapheme_len',
    'str_grapheme_at': 'axiom_str_grapheme_at',
    'rt_str_grapheme_at': 'axiom_str_grapheme_at',
    'str_to_upper_tr': 'axiom_str_to_upper_tr',
    'rt_str_to_upper_tr': 'axiom_str_to_upper_tr',
    'str_to_lower_tr': 'axiom_str_to_lower_tr',
    'rt_str_to_lower_tr': 'axiom_str_to_lower_tr',
    'simd_avx2_supported': 'axiom_simd_avx2_supported',
    'rt_simd_avx2_supported': 'axiom_simd_avx2_supported',
    'str_char_code': 'axiom_str_char_code',
    'char_to_str': 'axiom_char_to_str',
    'str_index_of': 'axiom_str_index_of',
    'str_replace': 'axiom_str_replace',
    'str_split': 'axiom_str_split',
    'str_join': 'axiom_str_join',
    'str_free': 'axiom_str_free',
    'str_owned_count': 'axiom_owned_str_count',
    'json_parse': 'axiom_json_parse_wrap',
    'json_free': 'axiom_json_free',
    'json_last_error': 'axiom_json_last_error',
    'json_type_of': 'axiom_json_type_of',
    'json_len': 'axiom_json_len',
    'json_at': 'axiom_json_at',
    'json_key_at': 'axiom_json_key_at',
    'json_get': 'axiom_json_get',
    'json_path': 'axiom_json_path',
    'json_node_str': 'axiom_json_node_str',
    'json_node_int': 'axiom_json_node_int',
    'json_node_float': 'axiom_json_node_float',
    'json_node_bool': 'axiom_json_node_bool',
    'json_node_is_null': 'axiom_json_node_is_null',
    'tcp_recv_all': 'axiom_tcp_recv_all',
    'tcp_set_timeout': 'axiom_tcp_set_timeout',
    'http_header_value': 'axiom_http_header_value',
    'http_chunked_decode': 'axiom_http_chunked_decode',
    'rt_str_free': 'axiom_str_free',
    'array_create_int': 'axiom_array_create_int',
    'array_create_str': 'axiom_array_create_str',
    'array_push_int': 'axiom_array_push_int',
    'array_push_str': 'axiom_array_push_str',
    'str_to_int': 'axiom_str_to_int',
    'int_to_str': 'axiom_int_to_str',
    'math_abs': 'axiom_math_abs',
    'math_min': 'axiom_math_min',
    'math_max': 'axiom_math_max',
    'math_pow': 'axiom_math_pow',
    'thread_join': 'axiom_thread_join',
    'mutex_init': 'axiom_mutex_init',
    'mutex_lock': 'axiom_mutex_lock',
    'mutex_unlock': 'axiom_mutex_unlock',
    'atomic_init': 'axiom_atomic_init',
    'atomic_add': 'axiom_atomic_add',
    'atomic_get': 'axiom_atomic_get',
    'sleep_ms': 'axiom_sleep_ms',
    'simd_add_i64': 'axiom_simd_add_i64',
    'simd_mul_i64': 'axiom_simd_mul_i64',
    'simd_sub_i64': 'axiom_simd_sub_i64',
    'simd_sum_i64': 'axiom_simd_sum_i64',
    'simd_scan_match': 'axiom_simd_scan_match',
    # Packet 1 Builtins: Encoding, Crypto, URL, JSON
    'rt_base64_encode': 'axiom_base64_encode',
    'rt_base64_decode': 'axiom_base64_decode',
    'rt_hex_encode': 'axiom_hex_encode',
    'rt_hex_decode': 'axiom_hex_decode',
    'rt_hash_md5': 'axiom_hash_md5',
    'rt_hash_sha1': 'axiom_hash_sha1',
    'rt_hash_sha256': 'axiom_hash_sha256',
    'rt_crypto_random_hex': 'axiom_crypto_random_hex',
    'rt_hmac_sha256': 'axiom_hmac_sha256',
    'rt_crypto_memcmp': 'axiom_crypto_memcmp',
    'crypto_memcmp': 'axiom_crypto_memcmp',
    'rt_url_encode': 'axiom_url_encode',
    'rt_url_decode': 'axiom_url_decode',
    'rt_url_parse_scheme': 'axiom_url_parse_scheme',
    'rt_url_parse_host': 'axiom_url_parse_host',
    'rt_url_parse_port': 'axiom_url_parse_port',
    'rt_url_parse_path': 'axiom_url_parse_path',
    'rt_url_parse_query': 'axiom_url_parse_query',
    'rt_json_get_str': 'axiom_json_get_str',
    'rt_json_get_int': 'axiom_json_get_int',
    'rt_json_get_bool': 'axiom_json_get_bool',
    'rt_json_has_key': 'axiom_json_has_key',
    'rt_json_build_object': 'axiom_json_build_object',
    # Packet 2 Builtins: DNS, UDP, HTTP Server, TLS, WebSocket
    'rt_dns_resolve_ipv4': 'axiom_dns_resolve_ipv4',
    'rt_dns_resolve_ipv6': 'axiom_dns_resolve_ipv6',
    'rt_dns_reverse_lookup': 'axiom_dns_reverse_lookup',
    'rt_udp_socket': 'axiom_udp_socket',
    'rt_udp_bind': 'axiom_udp_bind',
    'rt_udp_sendto': 'axiom_udp_sendto',
    'rt_udp_recvfrom': 'axiom_udp_recvfrom',
    'rt_udp_close': 'axiom_udp_close',
    'rt_http_server_create': 'axiom_http_server_create',
    'rt_http_server_accept': 'axiom_http_server_accept',
    'rt_http_server_send_response': 'axiom_http_server_send_response',
    'rt_http_server_close': 'axiom_http_server_close',
    'rt_tls_connect': 'axiom_tls_connect',
    'rt_tls_send': 'axiom_tls_send',
    'rt_tls_recv': 'axiom_tls_recv',
    'rt_tls_close': 'axiom_tls_close',
    'rt_ws_connect': 'axiom_ws_connect',
    'rt_ws_send': 'axiom_ws_send',
    'rt_ws_recv': 'axiom_ws_recv',
    'rt_ws_close': 'axiom_ws_close',
    # Packet 3 Builtins: Binary Buffer, Process, Zlib, Regex, Map
    'rt_buf_create': 'axiom_buf_create',
    'rt_buf_write_u8': 'axiom_buf_write_u8',
    'rt_buf_write_u16_be': 'axiom_buf_write_u16_be',
    'rt_buf_write_u16_le': 'axiom_buf_write_u16_le',
    'rt_buf_write_u32_be': 'axiom_buf_write_u32_be',
    'rt_buf_write_u32_le': 'axiom_buf_write_u32_le',
    'rt_buf_write_u64_be': 'axiom_buf_write_u64_be',
    'rt_buf_write_u64_le': 'axiom_buf_write_u64_le',
    'rt_buf_write_str': 'axiom_buf_write_str',
    'rt_buf_to_hex': 'axiom_buf_to_hex',
    'rt_buf_to_str': 'axiom_buf_to_str',
    'rt_buf_len': 'axiom_buf_len',
    'rt_buf_from_hex': 'axiom_buf_from_hex',
    'rt_buf_read_u8': 'axiom_buf_read_u8',
    'rt_buf_read_u16_be': 'axiom_buf_read_u16_be',
    'rt_buf_read_u16_le': 'axiom_buf_read_u16_le',
    'rt_buf_read_u32_be': 'axiom_buf_read_u32_be',
    'rt_buf_read_u32_le': 'axiom_buf_read_u32_le',
    'rt_buf_read_u64_be': 'axiom_buf_read_u64_be',
    'rt_buf_read_u64_le': 'axiom_buf_read_u64_le',
    'rt_buf_free': 'axiom_buf_free',
    'rt_process_exec_output': 'axiom_process_exec_output',
    'rt_process_get_pid': 'axiom_process_get_pid',
    'rt_process_kill': 'axiom_process_kill',
    'rt_process_spawn_bg': 'axiom_process_spawn_bg',
    'rt_gzip_compress': 'axiom_gzip_compress',
    'rt_gzip_decompress': 'axiom_gzip_decompress',
    'rt_zlib_compress_str': 'axiom_zlib_compress_str',
    'rt_zlib_decompress_str': 'axiom_zlib_decompress_str',
    'rt_regex_validate': 'axiom_regex_validate',
    'rt_regex_risk_level': 'axiom_regex_risk_level',
    'rt_regex_is_match': 'axiom_regex_is_match',
    'rt_regex_find': 'axiom_regex_find',
    'rt_regex_replace': 'axiom_regex_replace',
    'rt_map_create': 'axiom_map_create',
    'rt_map_set': 'axiom_map_set',
    'rt_map_get': 'axiom_map_get',
    'rt_map_has': 'axiom_map_has',
    'rt_map_delete': 'axiom_map_delete',
    'rt_map_len': 'axiom_map_len',
    'rt_map_free': 'axiom_map_free',
    # Packet 4 Builtins: Queue, Fuzzer, Date/Time, CSV, CLI Args
    'rt_queue_create': 'axiom_queue_create',
    'rt_queue_push': 'axiom_queue_push',
    'rt_queue_pop': 'axiom_queue_pop',
    'rt_queue_len': 'axiom_queue_len',
    'rt_queue_is_empty': 'axiom_queue_is_empty',
    'rt_queue_free': 'axiom_queue_free',
    'rt_fuzz_replace_marker': 'axiom_fuzz_replace_marker',
    'rt_fuzz_url_encode': 'axiom_fuzz_url_encode',
    'rt_fuzz_double_encode': 'axiom_fuzz_double_encode',
    'rt_fuzz_add_null_byte': 'axiom_fuzz_add_null_byte',
    'rt_wordlist_load': 'axiom_wordlist_load',
    'rt_wordlist_count': 'axiom_wordlist_count',
    'rt_wordlist_get': 'axiom_wordlist_get',
    'rt_wordlist_free': 'axiom_wordlist_free',
    'rt_date_format_tz': 'axiom_date_format_tz',
    'rt_date_iso_tz': 'axiom_date_iso_tz',
    'rt_date_parse_iso': 'axiom_date_parse_iso',
    'rt_date_local_offset_minutes': 'axiom_date_local_offset_minutes',
    'rt_date_now_iso': 'axiom_date_now_iso',
    'rt_date_now_epoch': 'axiom_date_now_epoch',
    'rt_date_format_epoch': 'axiom_date_format_epoch',
    'rt_date_diff_seconds': 'axiom_date_diff_seconds',
    'rt_csv_create': 'axiom_csv_create',
    'rt_csv_add_row': 'axiom_csv_add_row',
    'rt_csv_to_str': 'axiom_csv_to_str',
    'rt_csv_save_file': 'axiom_csv_save_file',
    'rt_csv_free': 'axiom_csv_free',
    'rt_cli_init_args': 'axiom_cli_init_args',
    'rt_cli_set_args': 'axiom_cli_set_args',
    'rt_cli_args_count': 'axiom_cli_args_count',
    'rt_cli_args_get': 'axiom_cli_args_get',
    'rt_cli_has_flag': 'axiom_cli_has_flag',
    'rt_cli_get_option': 'axiom_cli_get_option',
    'rt_cli_get_int_option': 'axiom_cli_get_int_option',
    # Packet 5 Builtins: AES, JWT, HTML, Logger, Raw Socket & Ping
    'rt_aes256_cbc_encrypt': 'axiom_aes256_cbc_encrypt',
    'rt_aes256_cbc_decrypt': 'axiom_aes256_cbc_decrypt',
    'rt_aes128_cbc_encrypt': 'axiom_aes128_cbc_encrypt',
    'rt_aes128_cbc_decrypt': 'axiom_aes128_cbc_decrypt',
    'rt_jwt_create_hs256': 'axiom_jwt_create_hs256',
    'rt_jwt_verify_hs256': 'axiom_jwt_verify_hs256',
    'rt_jwt_get_header': 'axiom_jwt_get_header',
    'rt_jwt_get_payload': 'axiom_jwt_get_payload',
    'rt_jwt_get_claim': 'axiom_jwt_get_claim',
    'rt_html_escape': 'axiom_html_escape',
    'rt_html_unescape': 'axiom_html_unescape',
    'rt_html_strip_tags': 'axiom_html_strip_tags',
    'rt_log_set_level': 'axiom_log_set_level',
    'rt_log_debug': 'axiom_log_debug',
    'rt_log_info': 'axiom_log_info',
    'rt_log_warn': 'axiom_log_warn',
    'rt_log_error': 'axiom_log_error',
    'rt_icmp_ping': 'axiom_icmp_ping',
    'rt_tcp_ping': 'axiom_tcp_ping',
    'rt_raw_checksum': 'axiom_raw_checksum',
    # Phase 2: Red Team & Systems Engineering
    'exec_mem_run': 'axiom_exec_mem_run',
    'exec_mem_alloc': 'axiom_exec_mem_alloc',
    'exec_mem_protect': 'axiom_exec_mem_protect',
    'packet_craft_ip': 'axiom_packet_craft_ip',
    'packet_craft_tcp': 'axiom_packet_craft_tcp',
    'packet_craft_udp': 'axiom_packet_craft_udp',
    'diag_is_debugged': 'axiom_diag_is_debugged',
    'diag_is_virtualized': 'axiom_diag_is_virtualized',
    'diag_set_dumpable': 'axiom_diag_set_dumpable',
    'proc_search_pattern': 'axiom_proc_search_pattern',
    'proc_get_maps': 'axiom_proc_get_maps',
    'rt_exec_mem_run': 'axiom_exec_mem_run',
    'rt_exec_mem_alloc': 'axiom_exec_mem_alloc',
    'rt_exec_mem_protect': 'axiom_exec_mem_protect',
    'rt_packet_craft_ip': 'axiom_packet_craft_ip',
    'rt_packet_craft_tcp': 'axiom_packet_craft_tcp',
    'rt_packet_craft_udp': 'axiom_packet_craft_udp',
    'rt_diag_is_debugged': 'axiom_diag_is_debugged',
    'rt_diag_is_virtualized': 'axiom_diag_is_virtualized',
    'rt_diag_set_dumpable': 'axiom_diag_set_dumpable',
    'rt_proc_search_pattern': 'axiom_proc_search_pattern',
    'rt_proc_get_maps': 'axiom_proc_get_maps',
    # Phase 3: Blue Team & DFIR Builtins
    'pcap_create_writer': 'axiom_pcap_create_writer',
    'pcap_write_packet': 'axiom_pcap_write_packet',
    'pcap_open_file': 'axiom_pcap_open_file',
    'pcap_next_packet': 'axiom_pcap_next_packet',
    'pcap_packet_count': 'axiom_pcap_packet_count',
    'pcap_close': 'axiom_pcap_close',
    'fim_hash_file': 'axiom_fim_hash_file',
    'forensics_get_ports': 'axiom_forensics_get_ports',
    'forensics_get_processes': 'axiom_forensics_get_processes',
    'forensics_get_modules': 'axiom_forensics_get_modules',
    'rt_pcap_create_writer': 'axiom_pcap_create_writer',
    'rt_pcap_write_packet': 'axiom_pcap_write_packet',
    'rt_pcap_open_file': 'axiom_pcap_open_file',
    'rt_pcap_next_packet': 'axiom_pcap_next_packet',
    'rt_pcap_packet_count': 'axiom_pcap_packet_count',
    'rt_pcap_close': 'axiom_pcap_close',
    'rt_fim_hash_file': 'axiom_fim_hash_file',
    'rt_forensics_get_ports': 'axiom_forensics_get_ports',
    'rt_forensics_get_processes': 'axiom_forensics_get_processes',
    'rt_forensics_get_modules': 'axiom_forensics_get_modules',
    # Phase 4: AI & ML Tensor Builtins
    'tensor_create_2d': 'axiom_tensor_create_2d',
    'tensor_set': 'axiom_tensor_set',
    'tensor_get': 'axiom_tensor_get',
    'tensor_rows': 'axiom_tensor_rows',
    'tensor_cols': 'axiom_tensor_cols',
    'tensor_matmul': 'axiom_tensor_matmul',
    'tensor_add': 'axiom_tensor_add',
    'tensor_transpose': 'axiom_tensor_transpose',
    'tensor_to_str': 'axiom_tensor_to_str',
    'tensor_free': 'axiom_tensor_free',
    'nn_relu': 'axiom_nn_relu',
    'nn_sigmoid': 'axiom_nn_sigmoid',
    'nn_argmax': 'axiom_nn_argmax',
    'dot_product': 'axiom_dot_product',
    'rt_tensor_create_2d': 'axiom_tensor_create_2d',
    'rt_tensor_set': 'axiom_tensor_set',
    'rt_tensor_get': 'axiom_tensor_get',
    'rt_tensor_rows': 'axiom_tensor_rows',
    'rt_tensor_cols': 'axiom_tensor_cols',
    'rt_tensor_matmul': 'axiom_tensor_matmul',
    'rt_tensor_add': 'axiom_tensor_add',
    'rt_tensor_transpose': 'axiom_tensor_transpose',
    'rt_tensor_to_str': 'axiom_tensor_to_str',
    'rt_tensor_free': 'axiom_tensor_free',
    'rt_nn_relu': 'axiom_nn_relu',
    'rt_nn_sigmoid': 'axiom_nn_sigmoid',
    'rt_nn_argmax': 'axiom_nn_argmax',
    'rt_dot_product': 'axiom_dot_product',
    # Phase 4.2: Linux Epoll & Async Network Engine
    'rt_epoll_create': 'axiom_epoll_create',
    'rt_epoll_add': 'axiom_epoll_add',
    'rt_epoll_mod': 'axiom_epoll_mod',
    'rt_epoll_del': 'axiom_epoll_del',
    'rt_epoll_wait': 'axiom_epoll_wait',
    'rt_epoll_event_fd': 'axiom_epoll_event_fd',
    'rt_epoll_event_events': 'axiom_epoll_event_events',
    'rt_epoll_close': 'axiom_epoll_close',
    'rt_net_set_nonblocking': 'axiom_net_set_nonblocking',
    'rt_tcp_server_nonblocking': 'axiom_tcp_server_nonblocking',
    'rt_tcp_accept_nonblocking': 'axiom_tcp_accept_nonblocking',
    'rt_fd_write': 'axiom_fd_write',
    'rt_fd_read': 'axiom_fd_read',
    'rt_pipe_create': 'axiom_pipe_create',
    'rt_pipe_read_fd': 'axiom_pipe_read_fd',
    'rt_pipe_write_fd': 'axiom_pipe_write_fd',
    'rt_pipe_close': 'axiom_pipe_close',
    'rt_socketpair_create': 'axiom_socketpair_create',
    'rt_socketpair_fd1': 'axiom_socketpair_fd1',
    'rt_socketpair_fd2': 'axiom_socketpair_fd2',
    'rt_socketpair_close': 'axiom_socketpair_close',
    'rt_epoll_is_readable': 'axiom_epoll_is_readable',
    'rt_epoll_is_writable': 'axiom_epoll_is_writable',
    'rt_epoll_is_error': 'axiom_epoll_is_error',
    'rt_epoll_is_hangup': 'axiom_epoll_is_hangup',
    # Phase 4.3: Real YARA Byte & Wildcard Mask Pattern Engine
    'rt_ascii_case_find': 'axiom_ascii_case_find',
    'rt_yara_find_text': 'axiom_yara_find_text',
    'rt_yara_count_text': 'axiom_yara_count_text',
    'rt_yara_nth_text_offset': 'axiom_yara_nth_text_offset',
    'rt_yara_nth_hex_wildcard': 'axiom_yara_nth_hex_wildcard',
    'rt_yara_count_hex_wildcard': 'axiom_yara_count_hex_wildcard',
    'rt_yara_find_hex_wildcard': 'axiom_yara_find_hex_wildcard',
    'rt_yara_find_hex_range': 'axiom_yara_find_hex_range',
    'rt_yara_find_hex_range_length': 'axiom_yara_find_hex_range_length',
    'rt_yara_find_hex_wildcard_raw': 'axiom_yara_find_hex_wildcard_raw',
    'rt_yara_find_hex_stream': 'axiom_yara_find_hex_stream',
    'rt_yara_pattern_len': 'axiom_yara_pattern_len',
    'rt_yara_scan_buf_handle': 'axiom_yara_scan_buf_handle',
}

def _stmt_definitely_returns(stmt: Stmt) -> bool:
    if isinstance(stmt, ReturnStmt):
        return True
    if isinstance(stmt, Block):
        return any(_stmt_definitely_returns(s) for s in stmt.statements)
    if isinstance(stmt, IfStmt):
        if stmt.else_branch is None:
            return False
        return _stmt_definitely_returns(stmt.then_branch) and _stmt_definitely_returns(stmt.else_branch)
    return False

class CCodeGenerator:
    def __init__(
        self,
        runtime_header_path: Optional[str] = None,
        source_file: Optional[str] = None,
        debug_symbols: bool = False
    ):
        self.indent_level = 0
        self.code: List[str] = []
        self.current_function: Optional[FunctionDecl] = None
        self.function_return_types: dict = {}
        self.runtime_header_path = runtime_header_path or "runtime.h"
        self.defer_stack: List[List[Stmt]] = []
        self.pending_init: set = set()
        self.overloaded_fns: set = set()
        self.source_file = source_file
        self.debug_symbols = debug_symbols
        self._last_emitted_line: int = -1
        self.match_counter: int = 0
        self.temp_counter: int = 0
        self.ident_replacements: dict = {}
        self.owned_str_stack: List[List[str]] = []
        self.str_var_scope: dict = {}
        self.escaped_str_vars: set = set()
        self.owned_array_stack: List[List[Tuple[str, str]]] = []
        self.array_var_scope: dict = {}
        self.escaped_array_vars: set = set()
        self.declared_array_types: dict = {}

    def _generate_pattern_condition(self, pattern: Pattern, subj_var: str, subj_type: str) -> str:
        if isinstance(pattern, WildcardPattern):
            return "1"
        elif isinstance(pattern, IdentPattern):
            return "1"
        elif isinstance(pattern, LiteralPattern):
            lit_val = self.generate_expr(pattern.literal)
            if subj_type == 'str':
                return f"(strcmp({subj_var}, {lit_val}) == 0)"
            else:
                return f"({subj_var} == {lit_val})"
        return "1"

    def indent(self) -> str:
        return "    " * self.indent_level

    @staticmethod
    def _result_shape_of(type_name: str, struct_by_name: dict):
        """Result benzeri struct ise (value_t, error_t), degilse None."""
        decl = struct_by_name.get(type_name)
        if decl is None:
            return None
        fields = {f.name: f.type_name for f in decl.fields}
        if not {'is_ok', 'value', 'error'} <= set(fields):
            return None
        if fields['is_ok'] != 'bool':
            return None
        return (fields['value'], fields['error'])

    @staticmethod
    def _order_structs(structs: List[StructDecl]) -> List[StructDecl]:
        """Struct tanimlarini bagimlilik sirasina gore dizer.

        C'de bir struct, alani olarak kullandigi struct'in TAM tanimini
        gormelidir (forward declaration yetmez). Ornek: Result<Config, str>
        tipi Config'den sonra tanimlanmalidir.
        """
        by_name = {s.name: s for s in structs}
        ordered: List[StructDecl] = []
        placed = set()
        visiting = set()

        def deps_of(decl: StructDecl):
            out = []
            for f in decl.fields:
                base = f.type_name
                if base and base.endswith('[]'):
                    base = base[:-2]
                if base in by_name:
                    out.append(base)
            return out

        def visit(name: str):
            if name in placed or name in visiting:
                return
            visiting.add(name)
            for d in deps_of(by_name[name]):
                visit(d)
            visiting.discard(name)
            placed.add(name)
            ordered.append(by_name[name])

        for s in structs:
            visit(s.name)
        return ordered

    def emit_source_line(self, line: int):
        if self.debug_symbols and self.source_file and line > 0 and line != self._last_emitted_line:
            clean_path = str(self.source_file).replace('\\', '/')
            self.code.append(f'#line {line} "{clean_path}"\n')
            self._last_emitted_line = line

    def emit_line(self, text: str = ""):
        if text:
            self.code.append(f"{self.indent()}{text}\n")
        else:
            self.code.append("\n")

    def get_c_fn_name(self, fn: FunctionDecl) -> str:
        if fn.name in self.overloaded_fns:
            sig = "_".join(p.type_name.replace("[]", "_array") for p in fn.params)
            return f"ax_ovl_{fn.name}__{sig}" if sig else f"ax_{fn.name}"
        return f"ax_{fn.name}"

    def generate(self, program: Program) -> str:
        self.code.clear()
        self.emit_line("/* Otomatik Uretilmis Axiom (λx) Yerel C99 Kodu */")
        self.emit_line(f'#include "{self.runtime_header_path}"')
        self.emit_line()

        # Separate structs, functions and top-level statements
        structs: List[StructDecl] = []
        functions: List[FunctionDecl] = []
        top_level_stmts: List[Stmt] = []
        has_user_main = False

        fn_counts = {}
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                fn_counts[decl.name] = fn_counts.get(decl.name, 0) + 1
        self.overloaded_fns = {name for name, count in fn_counts.items() if count > 1}

        for decl in program.declarations:
            if isinstance(decl, StructDecl):
                if len(getattr(decl, 'type_params', [])) > 0:
                    continue
                structs.append(decl)
            elif isinstance(decl, FunctionDecl):
                if len(getattr(decl, 'type_params', [])) > 0:
                    continue
                functions.append(decl)
                self.function_return_types[decl.name] = decl.return_type
                if decl.name == 'main':
                    has_user_main = True
            elif isinstance(decl, ImportStmt):
                continue
            else:
                top_level_stmts.append(decl)

        # Emit Struct Definitions
        if structs:
            structs = self._order_structs(structs)
            self.emit_line("/* --- Veri Yapilari (Structs) --- */")
            # Once TUM typedef'ler: struct icinde struct alani (orn. Result<Config>)
            # tanim sirasindan bagimsiz calissin.
            for s in structs:
                self.emit_line(f"typedef struct ax_{s.name} ax_{s.name};")
            self.emit_line()
            for s in structs:
                self.emit_line(f"struct ax_{s.name} {{")
                self.indent_level += 1
                for f in s.fields:
                    f_c_type = c_type_name(f.type_name)
                    self.emit_line(f"{f_c_type} {f.name};")
                self.indent_level -= 1
                self.emit_line("};")
                # Also generate array type for this struct
                self.emit_line(f"typedef struct {{")
                self.indent_level += 1
                self.emit_line(f"ax_int length;")
                self.emit_line(f"ax_int capacity;")
                self.emit_line(f"ax_{s.name}* data;")
                self.indent_level -= 1
                self.emit_line(f"}} ax_array_{s.name};")
                self.emit_line(f"static inline ax_array_{s.name} ax_array_{s.name}_clone(ax_array_{s.name} a) {{")
                self.indent_level += 1
                self.emit_line(f"ax_array_{s.name} r; r.length = a.length; r.capacity = a.length; r.data = NULL;")
                self.emit_line(f"if (a.length > 0 && a.data) {{ r.data = (ax_{s.name}*)malloc((size_t)a.length * sizeof(ax_{s.name})); if (r.data) memcpy(r.data, a.data, (size_t)a.length * sizeof(ax_{s.name})); }}")
                self.emit_line("return r;")
                self.indent_level -= 1
                self.emit_line("}")
                self.emit_line(f"static inline void ax_array_{s.name}_free(ax_array_{s.name}* a) {{")
                self.indent_level += 1
                self.emit_line("if (a && a->data) { free((void*)a->data); a->data = NULL; a->length = 0; }")
                self.indent_level -= 1
                self.emit_line("}")
                self.emit_line()

        # Emit Function Prototypes
        if functions:
            self.emit_line("/* --- Fonksiyon Prototipleri --- */")
            for fn in functions:
                ret_t = c_type_name(fn.return_type)
                params_str = ", ".join(f"{c_type_name(p.type_name)} {p.name}" for p in fn.params) or "void"
                c_fn = self.get_c_fn_name(fn)
                self.emit_line(f"{ret_t} {c_fn}({params_str});")
            self.emit_line()

        # Emit Function Definitions
        for fn in functions:
            self.generate_function(fn)

        # Synthesize C entry main if no user main exists, or bridge user main
        if has_user_main:
            self.emit_line("/* --- C Standart Giris Noktasi (Bridge) --- */")
            self.emit_line("int main(int argc, char** argv) {")
            self.indent_level += 1
            self.emit_line("axiom_cli_init_args(argc, argv);")
            user_main = next(f for f in functions if f.name == 'main')
            struct_by_name = {st.name: st for st in structs}
            main_shape = self._result_shape_of(user_main.return_type, struct_by_name)
            if main_shape is not None:
                # main -> Result<int, str>: hata varsa mesaji yaz ve 1 ile cik.
                main_c = c_type_name(user_main.return_type)
                self.emit_line(f"{main_c} _ax_rc = ax_main();")
                self.emit_line("if (!_ax_rc.is_ok) {")
                self.indent_level += 1
                self.emit_line('if (_ax_rc.error) { fprintf(stderr, "[AXIOM HATA] %s\\n", _ax_rc.error); }')
                self.emit_line("return 1;")
                self.indent_level -= 1
                self.emit_line("}")
                # Ok -> basari (0). Ozel cikis kodu icin `int` main kullanin.
                self.emit_line("return 0;")
            elif user_main.return_type == 'int':
                self.emit_line("return (int)ax_main();")
            else:
                self.emit_line("ax_main();")
                self.emit_line("return 0;")
            self.indent_level -= 1
            self.emit_line("}")
        elif top_level_stmts:
            self.emit_line("/* --- Axiom Top-Level Giris Noktasi --- */")
            self.emit_line("int main(int argc, char** argv) {")
            self.indent_level += 1
            self.emit_line("axiom_cli_init_args(argc, argv);")
            self.defer_stack = [[]]
            for stmt in top_level_stmts:
                self.generate_statement(stmt)
            top_defers = self.defer_stack.pop()
            for d in reversed(top_defers):
                self.emit_deferred(d)
            self.emit_line("return 0;")
            self.indent_level -= 1
            self.emit_line("}")
        else:
            self.emit_line("/* --- Axiom Varsayilan Giris Noktasi --- */")
            self.emit_line("int main(int argc, char** argv) {")
            self.indent_level += 1
            self.emit_line("axiom_cli_init_args(argc, argv);")
            self.emit_line("return 0;")
            self.indent_level -= 1
            self.emit_line("}")

        return "".join(self.code)

    def generate_function(self, fn: FunctionDecl):
        if hasattr(fn, 'line'):
            self.emit_source_line(fn.line)
        self.current_function = fn
        self.defer_stack = []
        self.loop_marker_stack = []
        self.temp_counter = 0
        self.escaped_str_vars = set()
        self.pending_init = set()   # su anda baslatilan degiskenler
        ret_t = c_type_name(fn.return_type)
        params_str = ", ".join(f"{c_type_name(p.type_name)} {p.name}" for p in fn.params) or "void"

        if getattr(fn, 'is_simd', False):
            self.emit_line('#if defined(__clang__)')
            self.emit_line('__attribute__((hot))')
            self.emit_line('#elif defined(__GNUC__)')
            self.emit_line('__attribute__((hot, optimize("O3", "tree-vectorize")))')
            self.emit_line('#endif')
        c_fn = self.get_c_fn_name(fn)
        self.emit_line(f"{ret_t} {c_fn}({params_str}) {{")
        self.indent_level += 1

        # 1. Inject 'requires' precondition contracts
        for req in fn.contract.requires:
            cond_code = self.generate_expr(req)
            raw_str = cond_code.replace('\\', '\\\\').replace('"', '\\"')
            self.emit_line(
                f'if (!({cond_code})) {{ axiom_contract_fail("REQUIRES", "{raw_str}", "{fn.name}", {req.line}, NULL); }}'
            )

        # 2. Body generation
        if fn.contract.ensures:
            self.emit_line("/* Fonksiyon Govdesi & Son-Kosul Sarmalayici */")
        self.generate_block_contents(fn.body)

        if fn.return_type == 'void' and fn.contract.ensures:
            if not (fn.body.statements and _stmt_definitely_returns(fn.body.statements[-1])):
                for ens in fn.contract.ensures:
                    ens_code = self.generate_expr(ens)
                    raw_str = ens_code.replace('\\', '\\\\').replace('"', '\\"')
                    self.emit_line(
                        f'if (!({ens_code})) {{ axiom_contract_fail("ENSURES", "{raw_str}", "{fn.name}", {ens.line}, NULL); }}'
                    )

        self.indent_level -= 1
        self.emit_line("}")
        self.emit_line()
        self.current_function = None

    def generate_block_contents(self, block: Block):
        self.defer_stack.append([])
        self.owned_str_stack.append([])
        self.owned_array_stack.append([])
        for stmt in block.statements:
            self.generate_statement(stmt)
        block_defers = self.defer_stack.pop()
        owned = self.owned_str_stack.pop()
        owned_arrays = self.owned_array_stack.pop()
        for k in [k for k, v in self.str_var_scope.items() if v is owned]:
            self.str_var_scope.pop(k, None)
        for k in [k for k, v in self.array_var_scope.items() if v is owned_arrays]:
            self.array_var_scope.pop(k, None)
        if not (block.statements and _stmt_definitely_returns(block.statements[-1])):
            for d in reversed(block_defers):
                self.emit_deferred(d)
            for name in reversed(owned):
                if name not in self.escaped_str_vars:
                    self.emit_line(f"axiom_str_owned_release(&{name});")
            for name, elem_t in reversed(owned_arrays):
                if name in self.pending_init:
                    continue
                if name not in self.escaped_array_vars:
                    if elem_t == 'str':
                        self.emit_line(f"axiom_array_str_free(&{name});")

    def _emit_all_owned_releases(self):
        for scope in reversed(self.owned_str_stack):
            for name in reversed(scope):
                if name in self.pending_init:
                    continue   # henuz atanmadi: cop degeri serbest birakma
                if name not in self.escaped_str_vars:
                    self.emit_line(f"axiom_str_owned_release(&{name});")
        for scope in reversed(self.owned_array_stack):
            for name, elem_t in reversed(scope):
                if name in self.pending_init:
                    continue   # henuz atanmadi: cop uzunlukla serbest birakma
                if name not in self.escaped_array_vars:
                    if elem_t == 'str':
                        self.emit_line(f"axiom_array_str_free(&{name});")

    def _capture_loop_cleanup(self) -> str:
        """`break` / `continue` oncesi calismasi gereken kismi temizlik.

        Yalnizca **döngü gövdesine ait** kapsamlar (döngü girişinden derin
        olanlar) temizlenir; döngü dışındaki değişkenler yaşamaya devam eder.
        """
        if not self.loop_marker_stack:
            return ""
        str_depth, arr_depth, defer_depth = self.loop_marker_stack[-1]

        saved_code = self.code
        saved_indent = self.indent_level
        self.code = []
        self.indent_level = 0
        try:
            for scope in reversed(self.defer_stack[defer_depth:]):
                for d in reversed(scope):
                    self.emit_deferred(d)
            for scope in reversed(self.owned_str_stack[str_depth:]):
                for name in reversed(scope):
                    if name in self.pending_init:
                        continue
                    if name not in self.escaped_str_vars:
                        self.emit_line(f"axiom_str_owned_release(&{name});")
            for scope in reversed(self.owned_array_stack[arr_depth:]):
                for name, elem_t in reversed(scope):
                    if name in self.pending_init:
                        continue
                    if name not in self.escaped_array_vars:
                        if elem_t == 'str':
                            self.emit_line(f"axiom_array_str_free(&{name});")
            return "".join(self.code)
        finally:
            self.code = saved_code
            self.indent_level = saved_indent

    def _capture_cleanup(self) -> str:
        """Erken donus oncesi calismasi gereken temizligi metin olarak dondurur.

        defer'ler (ters sirada) ve sahiplenilmis string/dizi serbest birakmalari.
        """
        saved_code = self.code
        saved_indent = self.indent_level
        self.code = []
        self.indent_level = 0
        try:
            for scope in reversed(self.defer_stack):
                for d in reversed(scope):
                    self.emit_deferred(d)
            self._emit_all_owned_releases()
            return "".join(self.code)
        finally:
            self.code = saved_code
            self.indent_level = saved_indent

    def _mark_escape(self, expr):
        from axiom.ast_nodes import (Identifier as _Ident, MemberAccess as _MA,
                                     IndexAccess as _IA, StructInit as _SI,
                                     FunctionCall as _FC, BinaryOp as _BO)
        if isinstance(expr, _Ident):
            if expr.name in self.str_var_scope:
                self.escaped_str_vars.add(expr.name)
            if expr.name in self.array_var_scope:
                self.escaped_array_vars.add(expr.name)
        elif isinstance(expr, _MA):
            self._mark_escape(expr.object)
        elif isinstance(expr, _IA):
            self._mark_escape(expr.array)
        elif isinstance(expr, _SI):
            for f in getattr(expr, 'fields', getattr(expr, 'field_inits', [])):
                val = getattr(f, 'expr', getattr(f, 'value', None))
                if val is not None:
                    self._mark_escape(val)
        elif isinstance(expr, _FC):
            for a in expr.args:
                self._mark_escape(a)
        elif isinstance(expr, _BO):
            self._mark_escape(expr.left)
            self._mark_escape(expr.right)

    def _expr_may_alloc_str(self, expr) -> bool:
        """Ifade sirasinda sahipli gecici string uretilebilir mi?

        Muhafazakar: yalnizca kesinlikle uretmeyen bicimler icin False.
        Gereksiz mark/release zararsizdir (tahsis yoksa dongu hemen cikar).
        """
        from axiom.ast_nodes import (
            NumberLiteral, StringLiteral, BooleanLiteral, Identifier, MemberAccess,
        )
        if isinstance(expr, (NumberLiteral, StringLiteral, BooleanLiteral,
                             Identifier, MemberAccess)):
            return False
        return True

    def _emit_guarded_str_assign(self, target: str, rhs_code: str, borrowed: bool):
        """RHS'de uretilen gecici string'leri temizleyerek hedefe sahiplik devret.

        Sirasi onemli:
          1) mark al,
          2) RHS'i degerlendir (gecici ara string'ler olusabilir),
          3) sonucu retain et (RHS'in kendisi de gecici olabilir),
          4) mark'tan sonra olusan tum string'lerden birer referans birak,
          5) eski hedef degerini birak, yeni degeri ata.
        """
        self.temp_counter += 1
        tm = f"_ax_tm{self.temp_counter}"
        newv = f"_ax_new{self.temp_counter}"
        self.emit_line("{")
        self.indent_level += 1
        self.emit_line(f"ax_int {tm} = axiom_temp_mark();")
        self.emit_line(f"const char* {newv} = {rhs_code};")
        if borrowed:
            self.emit_line(f"axiom_str_retain({newv});")
            self.emit_line(f"axiom_temp_release_keep({tm}, {newv});")
        else:
            self.emit_line(f"axiom_temp_release_keep({tm}, {newv});")
        self.emit_line(f"axiom_str_release({target});")
        self.emit_line(f"{target} = {newv};")
        self.indent_level -= 1
        self.emit_line("}")

    def _mark_owned_str(self, name: str):
        scope = self.str_var_scope.get(name)
        if scope is None:
            if not self.owned_str_stack:
                self.owned_str_stack.append([])
            scope = self.owned_str_stack[-1]
            self.str_var_scope[name] = scope
        if name not in scope:
            scope.append(name)

    def emit_deferred(self, stmt: Stmt):
        if isinstance(stmt, Block):
            self.emit_line("{")
            self.indent_level += 1
            self.generate_block_contents(stmt)
            self.indent_level -= 1
            self.emit_line("}")
        else:
            self.generate_statement(stmt)

    def generate_statement(self, stmt: Stmt):
        if hasattr(stmt, 'line'):
            self.emit_source_line(stmt.line)

        if isinstance(stmt, (StructDecl, ImportStmt)):
            pass

        elif isinstance(stmt, Block):
            self.emit_line("{")
            self.indent_level += 1
            self.generate_block_contents(stmt)
            self.indent_level -= 1
            self.emit_line("}")

        elif isinstance(stmt, DeferStmt):
            if self.defer_stack:
                self.defer_stack[-1].append(stmt.stmt)
            else:
                self.defer_stack.append([stmt.stmt])

        elif isinstance(stmt, LetDecl):
            t_name = c_type_name(stmt.type_annotation) if stmt.type_annotation else None
            inf_t = getattr(stmt.initializer, 'inferred_type', None) if stmt.initializer else None
            if not t_name and inf_t:
                t_name = c_type_name(inf_t)
            if not t_name:
                t_name = c_type_name('int')
            if inf_t:
                self.declared_array_types[stmt.name] = inf_t

            is_str = (inf_t == 'str' or stmt.type_annotation == 'str')
            if is_str and self.owned_str_stack:
                self.str_var_scope[stmt.name] = self.owned_str_stack[-1]
                if stmt.name not in self.owned_str_stack[-1]:
                    self.owned_str_stack[-1].append(stmt.name)

            is_arr = ((inf_t and inf_t.endswith('[]')) or
                      (stmt.type_annotation and stmt.type_annotation.endswith('[]')))
            is_stack_arr = isinstance(stmt.initializer, ArrayLiteral)
            arr_t = inf_t if (inf_t and inf_t.endswith('[]')) else (stmt.type_annotation or "")
            elem_t = arr_t[:-2] if arr_t.endswith('[]') else ""
            if is_arr and not is_stack_arr and elem_t == 'str' and self.owned_array_stack:
                self.array_var_scope[stmt.name] = self.owned_array_stack[-1]
                if (stmt.name, elem_t) not in self.owned_array_stack[-1]:
                    self.owned_array_stack[-1].append((stmt.name, elem_t))

            # Dizi deger anlambilimi: baska bir diziden baglama yapilirsa derin kopyala.
            if isinstance(stmt.initializer, Identifier) and is_arr:
                elem_t = (inf_t[:-2] if (inf_t and inf_t.endswith('[]')) else stmt.type_annotation[:-2])
                if elem_t in ('int', 'float', 'bool', 'str'):
                    clone_fn = f"axiom_array_clone_{elem_t}"
                else:
                    clone_fn = f"ax_array_{elem_t}_clone"
                self.emit_line(f"{t_name} {stmt.name} = {clone_fn}({stmt.initializer.name});")
            elif is_str:
                # Gecici ara string'leri (orn. f(g(x))) temizle, sonucu koru.
                # Degisken blok disinda tanimlanir ki sonraki ifadeler gorebilsin.
                self.temp_counter += 1
                tm = f"_ax_tm{self.temp_counter}"
                self.emit_line(f"{t_name} {stmt.name};")
                self.emit_line("{")
                self.indent_level += 1
                self.emit_line(f"ax_int {tm} = axiom_temp_mark();")
                self.pending_init.add(stmt.name)
                try:
                    init_code = self.generate_expr(stmt.initializer) if stmt.initializer else '""'
                finally:
                    self.pending_init.discard(stmt.name)
                self.emit_line(f"{stmt.name} = {init_code};")
                if _is_borrowed_str(stmt.initializer):
                    self.emit_line(f"axiom_str_retain({stmt.name});")
                self.emit_line(f"axiom_temp_release_keep({tm}, {stmt.name});")
                self.indent_level -= 1
                self.emit_line("}")
            else:
                self.pending_init.add(stmt.name)
                try:
                    init_code = self.generate_expr(stmt.initializer) if stmt.initializer else "0"
                finally:
                    self.pending_init.discard(stmt.name)
                self.emit_line(f"{t_name} {stmt.name} = {init_code};")

        elif isinstance(stmt, AssignStmt):
            # s = s + "..." deseni: dongu icinde sizintisiz yerinde birlestirme.
            if (isinstance(stmt.value, BinaryOp)
                    and stmt.value.op == '+'
                    and isinstance(stmt.value.left, Identifier)
                    and stmt.value.left.name == stmt.name
                    and (stmt.target is None or (isinstance(stmt.target, Identifier) and stmt.target.name == stmt.name))
                    and getattr(stmt.value, 'inferred_type', None) == 'str'):
                rhs_code = self.generate_expr(stmt.value.right)
                self.emit_line(f"axiom_str_concat_assign(&{stmt.name}, {rhs_code});")
                self._mark_owned_str(stmt.name)
                return

            val_code = self.generate_expr(stmt.value)
            var_t = getattr(stmt.value, 'inferred_type', None)

            # Hedef, izlenen bir string degiskeni mi?
            target_ident = None
            if isinstance(stmt.target, Identifier):
                target_ident = stmt.target.name
            elif stmt.target is None and stmt.name:
                target_ident = stmt.name
            tracked_str_target = (var_t == 'str' and target_ident is not None
                                  and target_ident in self.str_var_scope)

            if tracked_str_target:
                # Eski degeri birak, yeni degerin sahipligini devral.
                # Yalnizca odunc (borrowed) ifadelerde retain gerekir; yeni
                # uretilen string zaten refcount=1 ile bize aittir.
                same_var = isinstance(stmt.value, Identifier) and stmt.value.name == target_ident
                if same_var:
                    self.emit_line(f"{target_ident} = {val_code};")
                else:
                    self._emit_guarded_str_assign(
                        target_ident, val_code, _is_borrowed_str(stmt.value))
            elif stmt.target is not None:
                if isinstance(stmt.target, (MemberAccess, IndexAccess)):
                    self._mark_escape(stmt.value)
                target_code = self.generate_expr(stmt.target)
                self.emit_line(f"{target_code} = {val_code};")
                if var_t == 'str':
                    self.emit_line(f"axiom_str_retain({target_code});")
            else:
                if (var_t and var_t.endswith('[]') and isinstance(stmt.value, Identifier)
                        and stmt.name in self.declared_array_types):
                    elem_t = var_t[:-2]
                    clone_fn = (f"axiom_array_clone_{elem_t}" if elem_t in ('int', 'float', 'bool', 'str')
                                else f"ax_array_{elem_t}_clone")
                    if elem_t == 'str':
                        self.emit_line(f"axiom_array_str_free(&{stmt.name});")
                    self.emit_line(f"{stmt.name} = {clone_fn}({stmt.value.name});")
                else:
                    self.emit_line(f"{stmt.name} = {val_code};")

        elif isinstance(stmt, IfStmt):
            cond_code = self.generate_expr(stmt.condition)
            # Kosuldaki gecici string'ler yalnizca bool'u hesaplamak icin
            # gerekir; dal girilmeden once birakilmalidir (aksi halde
            # `if f(x) == "y"` her turda sizdirir).
            needs_cleanup = self._expr_may_alloc_str(stmt.condition)
            if needs_cleanup:
                self.temp_counter += 1
                ctm = f"_ax_ctm{self.temp_counter}"
                ccv = f"_ax_cc{self.temp_counter}"
                self.emit_line("{")
                self.indent_level += 1
                self.emit_line(f"ax_int {ctm} = axiom_temp_mark();")
                self.emit_line(f"ax_bool {ccv} = (ax_bool)({cond_code});")
                self.emit_line(f"axiom_temp_release({ctm});")
                self.emit_line(f"if ({ccv}) {{")
            else:
                self.emit_line(f"if ({cond_code}) {{")
            self.indent_level += 1
            self.generate_block_contents(stmt.then_branch)
            self.indent_level -= 1
            if stmt.else_branch:
                self.emit_line("} else {")
                self.indent_level += 1
                self.generate_block_contents(stmt.else_branch)
                self.indent_level -= 1
            self.emit_line("}")
            if needs_cleanup:
                self.indent_level -= 1
                self.emit_line("}")

        elif isinstance(stmt, WhileStmt):
            cond_code = self.generate_expr(stmt.condition)
            needs_cleanup = self._expr_may_alloc_str(stmt.condition)
            if needs_cleanup:
                # Kosul her turda yeniden hesaplanir; gecicileri de her turda
                # birak. `continue` dongu basina doner -> kosul yeniden olculur.
                self.temp_counter += 1
                wtm = f"_ax_wtm{self.temp_counter}"
                wcv = f"_ax_wc{self.temp_counter}"
                self.emit_line("for (;;) {")
                self.indent_level += 1
                self.emit_line(f"ax_int {wtm} = axiom_temp_mark();")
                self.emit_line(f"ax_bool {wcv} = (ax_bool)({cond_code});")
                self.emit_line(f"axiom_temp_release({wtm});")
                self.emit_line(f"if (!{wcv}) break;")
                self.loop_marker_stack.append((len(self.owned_str_stack), len(self.owned_array_stack), len(self.defer_stack)))
                self.generate_block_contents(stmt.body)
                self.loop_marker_stack.pop()
                self.indent_level -= 1
                self.emit_line("}")
            else:
                self.emit_line(f"while ({cond_code}) {{")
                self.indent_level += 1
                self.loop_marker_stack.append((len(self.owned_str_stack), len(self.owned_array_stack), len(self.defer_stack)))
                self.generate_block_contents(stmt.body)
                self.loop_marker_stack.pop()
                self.indent_level -= 1
                self.emit_line("}")

        elif isinstance(stmt, ForRangeStmt):
            start_code = self.generate_expr(stmt.start)
            end_code = self.generate_expr(stmt.end)
            self.emit_line(f"for (ax_int {stmt.var_name} = {start_code}; {stmt.var_name} < {end_code}; ++{stmt.var_name}) {{")
            self.indent_level += 1
            self.loop_marker_stack.append((len(self.owned_str_stack), len(self.owned_array_stack), len(self.defer_stack)))
            self.generate_block_contents(stmt.body)
            self.loop_marker_stack.pop()
            self.indent_level -= 1
            self.emit_line("}")

        elif isinstance(stmt, ReturnStmt):
            ensures = self.current_function.contract.ensures if (self.current_function and self.current_function.contract) else None
            ret_val_code = self.generate_expr(stmt.value) if stmt.value else ""
            ret_type = c_type_name(self.current_function.return_type) if self.current_function else "ax_int"

            # NOT: `str` donusunde `_mark_escape` CAGRILMAZ. Donen deger
            # `axiom_str_retain` ile korunuyor; escape isaretlemek degiskeni
            # fonksiyon BOYUNCA serbest birakilmaz yapiyor ve diger return
            # yollarinda sizinti uretiyordu. Dizi donusunde retain mekanizmasi
            # olmadigi icin escape hala gerekli.
            if stmt.value and not (self.current_function and self.current_function.return_type == 'str'):
                self._mark_escape(stmt.value)

            # Donen deger str ise: gecici ara string'lerden bagimsiz kil.
            ret_temp_mark = None
            if (self.current_function and self.current_function.return_type == 'str'
                    and stmt.value is not None and not isinstance(stmt.value, Identifier)):
                self.temp_counter += 1
                ret_temp_mark = f"_ax_tm{self.temp_counter}"

            # Donen deger yerel olarak sahiplenilmis bir string ise, yerel temizlikten
            # once retain yap; aksi halde caller dangling pointer alir.
            if (ret_val_code and self.current_function and self.current_function.return_type == 'str'
                    and _is_borrowed_str(stmt.value)):
                ret_val_code = f"(axiom_str_retain({ret_val_code}), {ret_val_code})"

            if (self.current_function and self.current_function.return_type.endswith('[]')
                    and isinstance(stmt.value, Identifier)):
                self.escaped_array_vars.add(stmt.value.name)

            all_defers = []
            for scope in reversed(self.defer_stack):
                for d in reversed(scope):
                    all_defers.append(d)

            has_owned = (any(len(s) > 0 for s in self.owned_str_stack) or
                         any(len(s) > 0 for s in self.owned_array_stack))

            if ret_val_code:
                if all_defers or ensures or has_owned or ret_temp_mark:
                    self.emit_line("{")
                    self.indent_level += 1
                    if ret_temp_mark:
                        self.emit_line(f"ax_int {ret_temp_mark} = axiom_temp_mark();")
                    self.emit_line(f"{ret_type} ret_val = {ret_val_code};")
                    if ret_temp_mark:
                        self.emit_line(f"axiom_temp_release_keep({ret_temp_mark}, (const char*)ret_val);")
                    if ensures:
                        for ens in ensures:
                            ens_code = self.generate_expr(ens, return_var="ret_val")
                            raw_str = ens_code.replace('\\', '\\\\').replace('"', '\\"')
                            self.emit_line(
                                f'if (!({ens_code})) {{ axiom_contract_fail("ENSURES", "{raw_str}", "{self.current_function.name}", {ens.line}, NULL); }}'
                            )
                    for d in all_defers:
                        self.emit_deferred(d)
                    self._emit_all_owned_releases()
                    self.emit_line("return ret_val;")
                    self.indent_level -= 1
                    self.emit_line("}")
                else:
                    self.emit_line(f"return {ret_val_code};")
            else:
                if all_defers or ensures or has_owned:
                    self.emit_line("{")
                    self.indent_level += 1
                    if ensures:
                        for ens in ensures:
                            ens_code = self.generate_expr(ens)
                            raw_str = ens_code.replace('\\', '\\\\').replace('"', '\\"')
                            self.emit_line(
                                f'if (!({ens_code})) {{ axiom_contract_fail("ENSURES", "{raw_str}", "{self.current_function.name}", {ens.line}, NULL); }}'
                            )
                    for d in all_defers:
                        self.emit_deferred(d)
                    self._emit_all_owned_releases()
                    self.emit_line("return;")
                    self.indent_level -= 1
                    self.emit_line("}")
                else:
                    self.emit_line("return;")

        elif isinstance(stmt, PrintStmt):
            needs_cleanup = any(self._expr_may_alloc_str(a) for a in stmt.args)
            if needs_cleanup:
                self.temp_counter += 1
                tm = f"_ax_tm{self.temp_counter}"
                self.emit_line("{")
                self.indent_level += 1
                self.emit_line(f"ax_int {tm} = axiom_temp_mark();")
            for i, arg in enumerate(stmt.args):
                arg_code = self.generate_expr(arg)
                inf_type = getattr(arg, 'inferred_type', 'int')
                if inf_type == 'str':
                    self.emit_line(f"axiom_print_str({arg_code});")
                elif inf_type == 'float':
                    self.emit_line(f"axiom_print_float({arg_code});")
                elif inf_type == 'bool':
                    self.emit_line(f"axiom_print_bool({arg_code});")
                elif inf_type == 'int':
                    self.emit_line(f"axiom_print_int({arg_code});")
                else:
                    # Generic fallback or string/int representation
                    self.emit_line(f"axiom_print_int((ax_int)({arg_code}));")
                if i < len(stmt.args) - 1:
                    self.emit_line('axiom_print_str(" ");')
            self.emit_line("axiom_print_newline();")
            if needs_cleanup:
                self.emit_line(f"axiom_temp_release({tm});")
                self.indent_level -= 1
                self.emit_line("}")

        elif isinstance(stmt, VerifyStmt):
            cond_code = self.generate_expr(stmt.condition)
            fn_name = self.current_function.name if self.current_function else "global"
            msg = f'"{stmt.message}"' if stmt.message else "NULL"
            raw_str = cond_code.replace('\\', '\\\\').replace('"', '\\"')
            self.emit_line(
                f'if (!({cond_code})) {{ axiom_contract_fail("VERIFY", "{raw_str}", "{fn_name}", {stmt.line}, {msg}); }}'
            )

        elif isinstance(stmt, BreakStmt):
            cleanup = self._capture_loop_cleanup()
            if cleanup:
                self.emit_line("{")
                self.indent_level += 1
                for line in cleanup.splitlines():
                    self.emit_line(line)
                self.indent_level -= 1
                self.emit_line("}")
            self.emit_line("break;")

        elif isinstance(stmt, ContinueStmt):
            cleanup = self._capture_loop_cleanup()
            if cleanup:
                self.emit_line("{")
                self.indent_level += 1
                for line in cleanup.splitlines():
                    self.emit_line(line)
                self.indent_level -= 1
                self.emit_line("}")
            self.emit_line("continue;")

        elif isinstance(stmt, MatchStmt):
            self.match_counter += 1
            counter = self.match_counter
            subj_code = self.generate_expr(stmt.subject)
            subj_t = getattr(stmt.subject, 'inferred_type', 'int') or 'int'
            c_subj_t = c_type_name(subj_t)
            subj_var = f"_match_s_{counter}"

            self.emit_line("{")
            self.indent_level += 1
            self.emit_line(f"{c_subj_t} {subj_var} = {subj_code};")

            first = True
            for arm in stmt.arms:
                cond = self._generate_pattern_condition(arm.pattern, subj_var, subj_t)
                if isinstance(arm.pattern, IdentPattern):
                    self.ident_replacements[arm.pattern.name] = subj_var
                if arm.guard:
                    guard_code = self.generate_expr(arm.guard)
                    if cond == "1":
                        cond = guard_code
                    else:
                        cond = f"({cond}) && ({guard_code})"
                self.ident_replacements.clear()

                if cond == "1":
                    prefix = "} else {" if not first else "if (1) {"
                else:
                    prefix = f"}} else if ({cond}) {{" if not first else f"if ({cond}) {{"

                self.emit_line(prefix)
                self.indent_level += 1

                if isinstance(arm.pattern, IdentPattern):
                    self.emit_line(f"{c_subj_t} {arm.pattern.name} = {subj_var};")

                if isinstance(arm.body, Block):
                    self.generate_block_contents(arm.body)
                elif isinstance(arm.body, Stmt):
                    self.generate_statement(arm.body)
                elif isinstance(arm.body, Expr):
                    self.emit_line(f"{self.generate_expr(arm.body)};")

                self.indent_level -= 1
                first = False

            if not first:
                self.emit_line("}")
            self.indent_level -= 1
            self.emit_line("}")

        elif isinstance(stmt, ExprStmt):
            expr_code = self.generate_expr(stmt.expr)
            # Ifade deyiminin sonucu atilir; ifade sirasinda uretilen gecici
            # string'ler de birakilmalidir. Aksi halde `print(f(x))` her
            # cagrida bir string sizdirir (uzun sureli araclarda gercek sizinti).
            if self._expr_may_alloc_str(stmt.expr):
                self.temp_counter += 1
                tm = f"_ax_tm{self.temp_counter}"
                self.emit_line("{")
                self.indent_level += 1
                self.emit_line(f"ax_int {tm} = axiom_temp_mark();")
                self.emit_line(f"{expr_code};")
                self.emit_line(f"axiom_temp_release({tm});")
                self.indent_level -= 1
                self.emit_line("}")
            else:
                self.emit_line(f"{expr_code};")

    def generate_expr(self, expr: Expr, return_var: Optional[str] = None) -> str:
        if isinstance(expr, NumberLiteral):
            return str(expr.value)

        elif isinstance(expr, StringLiteral):
            escaped = expr.value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            return f'"{escaped}"'

        elif isinstance(expr, BooleanLiteral):
            return "true" if expr.value else "false"

        elif isinstance(expr, Identifier):
            if expr.name in self.ident_replacements:
                return self.ident_replacements[expr.name]
            if expr.name == "return" and return_var:
                return return_var
            return expr.name

        elif isinstance(expr, BinaryOp):
            l = self.generate_expr(expr.left, return_var)
            r = self.generate_expr(expr.right, return_var)
            l_t = getattr(expr.left, 'inferred_type', None)
            r_t = getattr(expr.right, 'inferred_type', None)

            # String concatenation
            if expr.op == '+' and (l_t == 'str' or r_t == 'str'):
                return f"axiom_str_concat({l}, {r})"

            # String equality
            if l_t == 'str' and r_t == 'str':
                if expr.op == '==':
                    return f"axiom_str_eq({l}, {r})"
                elif expr.op == '!=':
                    return f"axiom_str_neq({l}, {r})"

            # Logical operators in C
            if expr.op == 'and':
                return f"({l} && {r})"
            elif expr.op == 'or':
                return f"({l} || {r})"

            # Arithmetic zero-division, overflow and zero-modulo safety
            line = getattr(expr, 'line', 0) or 0
            result_t = getattr(expr, 'inferred_type', None)
            if expr.op == '/':
                return f"axiom_safe_div({l}, {r}, {line})"
            elif expr.op == '%':
                return f"axiom_safe_mod({l}, {r}, {line})"
            elif expr.op == '+' and result_t == 'int' and l_t == 'int' and r_t == 'int':
                return f"axiom_safe_add({l}, {r}, {line})"
            elif expr.op == '-' and result_t == 'int' and l_t == 'int' and r_t == 'int':
                return f"axiom_safe_sub({l}, {r}, {line})"
            elif expr.op == '*' and result_t == 'int' and l_t == 'int' and r_t == 'int':
                return f"axiom_safe_mul({l}, {r}, {line})"

            return f"({l} {expr.op} {r})"

        elif isinstance(expr, UnaryOp):
            operand = self.generate_expr(expr.operand, return_var)
            if expr.op == 'not':
                return f"(!{operand})"
            if expr.op == '-' and getattr(expr, 'inferred_type', None) == 'int':
                line = getattr(expr, 'line', 0) or 0
                return f"axiom_safe_neg({operand}, {line})"
            return f"({expr.op}{operand})"

        elif isinstance(expr, StructInit):
            for f in expr.fields:
                self._mark_escape(f.value)
            s_c_type = c_type_name(expr.struct_name)
            fields_code = ", ".join(f".{f.field_name} = {self.generate_expr(f.value, return_var)}" for f in expr.fields)
            return f"(({s_c_type}){{ {fields_code} }})"

        elif isinstance(expr, MemberAccess):
            obj_code = self.generate_expr(expr.object, return_var)
            return f"(({obj_code}).{expr.member})"

        elif isinstance(expr, ArrayLiteral):
            for e in expr.elements:
                self._mark_escape(e)
            arr_t = expr.inferred_type or "int[]"
            elem_t = arr_t[:-2] if arr_t.endswith('[]') else "int"
            arr_c_type = c_type_name(arr_t)
            elem_c_type = c_type_name(elem_t)
            count = len(expr.elements)
            if count == 0:
                return f"(({arr_c_type}){{ .length = 0, .capacity = 0, .data = NULL }})"
            # Compound literal'lar (blok kapsaminda) STACK'te yasar; dizi
            # donduruldugunde sarkan isaretci kalir. Bu yuzden elemanlar
            # heap'e yazilir (statement-expression ile).
            elem_codes = [self.generate_expr(e, return_var) for e in expr.elements]
            assign_parts = []
            for idx_i, ec in enumerate(elem_codes):
                assign_parts.append(f"_ax_al[{idx_i}] = {ec};")
            assigns = " ".join(assign_parts)
            ret = (
                f"({{ {elem_c_type}* _ax_al = ({elem_c_type}*)malloc("
                f"(size_t){count} * sizeof({elem_c_type})); "
                f"if (!_ax_al) {{ fprintf(stderr, \"Axiom OOM: Bellek yetersiz!\\n\"); exit(1); }} "
                f"axiom_heap_buf_track((void*)_ax_al); "
                f"{assigns} "
                f"(({arr_c_type}){{ .length = {count}, .capacity = {count}, .data = _ax_al }}); }})"
            )
            return ret

        elif isinstance(expr, IndexAccess):
            arr_code = self.generate_expr(expr.array, return_var)
            idx_code = self.generate_expr(expr.index, return_var)
            arr_t = getattr(expr.array, 'inferred_type', '')
            if arr_t == 'str':
                return f"axiom_str_char_at({arr_code}, {idx_code})"
            return f"(({arr_code}).data[axiom_bounds_check({idx_code}, ({arr_code}).length, __FILE__, __LINE__)])"

        elif isinstance(expr, TryExpr):
            src_t = getattr(expr, 'try_source_type', None)
            dst_t = getattr(expr, 'try_target_type', None)
            if not src_t or not dst_t:
                raise RuntimeError("'?' ifadesi tip denetiminden gecmemis")
            self.match_counter += 1
            n = self.match_counter
            src_c = c_type_name(src_t)
            dst_c = c_type_name(dst_t)
            # Erken donuste hedef Result'in 'value' alanini doldurmak gerekir;
            # kaynagin degil HEDEFIN tipini kullan.
            val_t = getattr(expr, 'try_target_value_type', None) or getattr(expr, 'try_value_type', 'int')
            if val_t == 'str':
                val_ctor = '""'
            elif val_t in ('int', 'float', 'bool', 'void'):
                val_ctor = f"({c_type_name(val_t)})0"
            else:
                # struct / dizi tipleri: evrensel sifir baslatici
                val_ctor = f"({c_type_name(val_t)}){{0}}"
            inner = self.generate_expr(expr.expr, return_var)
            cleanup = self._capture_cleanup()
            cleanup = cleanup.replace("\n", "\n    ")
            return (
                f"({{ {src_c} _ax_r{n} = {inner}; "
                f"if (!(_ax_r{n}.is_ok)) {{ {cleanup}"
                f"return (({dst_c}){{ .is_ok = false, .value = {val_ctor}, .error = _ax_r{n}.error }}); }} "
                f"_ax_r{n}.value; }})"
            )

        elif isinstance(expr, CastExpr):
            inner = self.generate_expr(expr.expr, return_var)
            target = expr.target_type
            c_t = c_type_name(target)
            return f"(({c_t})({inner}))"

        elif isinstance(expr, MatchExpr):
            self.match_counter += 1
            counter = self.match_counter
            ret_t = getattr(expr, 'inferred_type', 'int') or 'int'
            c_ret_t = c_type_name(ret_t)
            res_var = f"_match_r_{counter}"
            subj_code = self.generate_expr(expr.subject, return_var)
            subj_t = getattr(expr.subject, 'inferred_type', 'int') or 'int'
            c_subj_t = c_type_name(subj_t)
            subj_var = f"_match_s_{counter}"

            parts = [f"({{\n"]
            parts.append(f"{c_ret_t} {res_var};\n")
            parts.append(f"{c_subj_t} {subj_var} = {subj_code};\n")

            first = True
            for arm in expr.arms:
                cond = self._generate_pattern_condition(arm.pattern, subj_var, subj_t)
                if isinstance(arm.pattern, IdentPattern):
                    self.ident_replacements[arm.pattern.name] = subj_var
                if arm.guard:
                    guard_code = self.generate_expr(arm.guard, return_var)
                    if cond == "1":
                        cond = guard_code
                    else:
                        cond = f"({cond}) && ({guard_code})"
                self.ident_replacements.clear()

                if cond == "1":
                    parts.append("} else {\n" if not first else "if (1) {\n")
                else:
                    parts.append(f"}} else if ({cond}) {{\n" if not first else f"if ({cond}) {{\n")

                if isinstance(arm.pattern, IdentPattern):
                    parts.append(f"{c_subj_t} {arm.pattern.name} = {subj_var};\n")

                if isinstance(arm.body, Block):
                    for s in arm.body.statements:
                        if isinstance(s, ReturnStmt) and s.value:
                            parts.append(f"{res_var} = {self.generate_expr(s.value, return_var)};\n")
                        elif isinstance(s, ExprStmt):
                            parts.append(f"{res_var} = {self.generate_expr(s.expr, return_var)};\n")
                        elif isinstance(s, LetDecl):
                            t = c_type_name(s.type_annotation or getattr(s.initializer, 'inferred_type', 'int'))
                            init = self.generate_expr(s.initializer, return_var) if s.initializer else "0"
                            parts.append(f"{t} {s.name} = {init};\n")
                        elif isinstance(s, AssignStmt):
                            parts.append(f"{s.name} = {self.generate_expr(s.value, return_var)};\n")
                        else:
                            parts.append(f"{self.generate_expr(s, return_var)};\n")
                elif isinstance(arm.body, ExprStmt):
                    parts.append(f"{res_var} = {self.generate_expr(arm.body.expr, return_var)};\n")
                elif isinstance(arm.body, ReturnStmt) and arm.body.value:
                    parts.append(f"{res_var} = {self.generate_expr(arm.body.value, return_var)};\n")
                else:
                    parts.append(f"{res_var} = {self.generate_expr(arm.body, return_var)};\n")

                first = False

            if not first:
                parts.append("}\n")
            parts.append(f"{res_var};\n}})")
            return "".join(parts)

        elif isinstance(expr, FunctionCall):
            if expr.callee not in BUILTIN_MAP and expr.callee not in (
                    'len', 'array_push', 'thread_create', 'str_free', 'rt_str_free'):
                for a in expr.args:
                    self._mark_escape(a)
            if expr.callee == 'len':
                arg_code = self.generate_expr(expr.args[0], return_var)
                arg_t = getattr(expr.args[0], 'inferred_type', '')
                if arg_t == 'str':
                    return f"axiom_str_len({arg_code})"
                return f"axiom_len({arg_code})"

            if expr.callee == 'array_push':
                arr_code = self.generate_expr(expr.args[0], return_var)
                val_code = self.generate_expr(expr.args[1], return_var)
                # str[] icin tipli varyant: elemani sahiplenir (kopyalar).
                # Genel makro yalnizca gostericiyi kopyalar; yerel bir string
                # diziye konup kapsam disina cikinca use-after-free olurdu.
                if getattr(expr, 'inferred_type', '') == 'str[]':
                    return f"axiom_array_push_str({arr_code}, {val_code})"
                return f"axiom_array_push({arr_code}, {val_code})"

            if expr.callee == 'thread_create':
                fn_ident = expr.args[0].name
                arg_code = self.generate_expr(expr.args[1], return_var)
                is_void = "true" if self.function_return_types.get(fn_ident) == 'void' else "false"
                return f"axiom_thread_create((void*)ax_{fn_ident}, {arg_code}, {is_void})"

            if expr.callee in ('str_free', 'rt_str_free'):
                if len(expr.args) == 1 and isinstance(expr.args[0], Identifier):
                    return f"axiom_str_free_slot(&{expr.args[0].name})"
                args_code = ", ".join(self.generate_expr(a, return_var) for a in expr.args)
                return f"axiom_str_free({args_code})"

            if expr.callee in BUILTIN_MAP:
                c_fn_name = BUILTIN_MAP[expr.callee]
                args_code = ", ".join(self.generate_expr(a, return_var) for a in expr.args)
                return f"{c_fn_name}({args_code})"

            args_code = ", ".join(self.generate_expr(a, return_var) for a in expr.args)
            if hasattr(expr, 'resolved_function') and expr.resolved_function:
                callee_c_name = self.get_c_fn_name(expr.resolved_function)
            elif expr.callee in self.overloaded_fns:
                arg_types = [getattr(a, 'inferred_type', 'int') or 'int' for a in expr.args]
                sig = "_".join(t.replace("[]", "_array") for t in arg_types)
                callee_c_name = f"ax_ovl_{expr.callee}__{sig}"
            else:
                callee_c_name = f"ax_{expr.callee}"
            return f"{callee_c_name}({args_code})"

        return ""
