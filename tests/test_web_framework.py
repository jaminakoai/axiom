"""
Axiom Programming Language (λx) - FAZ 5: Modern Web & Asenkron API Motoru Testleri
"""
import pytest
import subprocess
import tempfile
import os
from pathlib import Path

from axiom.cli import compile_axiom_source, find_c_compiler

def run_axiom_code(code_str: str) -> tuple[int, str, str]:
    c_code = compile_axiom_source(code_str)
    cc = find_c_compiler()
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_file, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_file:
        c_path = c_file.name
        bin_path = bin_file.name
        c_file.write(c_code)

    try:
        cmd = [cc, "-O3", "-Wall", c_path, "-o", bin_path, "-lssl", "-lcrypto", "-lz", "-ldl", "-lm", "-pthread"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"C derleme hatasi:\n{res.stderr}"

        run_res = subprocess.run([bin_path], capture_output=True, text=True, timeout=10)
        return run_res.returncode, run_res.stdout, run_res.stderr
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

def test_router_exact_and_parametric_matching():
    code = """
    import "std/web/router.ax"

    fn main() -> int {
        let mut router: Router = router_new();
        router = router_add(router, "GET", "/status", 101);
        router = router_add(router, "POST", "/users/:id", 102);

        let m1: RouteMatch = router_match(router, "GET", "/status");
        if (m1.matched and m1.handler_id == 101) {
            print("MATCH_EXACT_OK");
        }

        let m2: RouteMatch = router_match(router, "POST", "/users/9988");
        if (m2.matched and m2.handler_id == 102 and m2.param_key == "id" and m2.param_val == "9988") {
            print("MATCH_PARAMETRIC_OK");
        }

        let m3: RouteMatch = router_match(router, "GET", "/notfound");
        if (not m3.matched) {
            print("MATCH_NOT_FOUND_OK");
        }
        return 0;
    }
    """
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "MATCH_EXACT_OK" in out
    assert "MATCH_PARAMETRIC_OK" in out
    assert "MATCH_NOT_FOUND_OK" in out

def test_web_app_middleware_and_context():
    code = r"""
    import "std/web/app.ax"

    fn main() -> int {
        let mut ctx: Context = context_new("POST", "/api/data", "{\"msg\": \"hello\"}");
        ctx = cors_middleware(ctx, "https://trusted.domain");
        if (str_contains(ctx.cors_header, "https://trusted.domain")) {
            print("CORS_SET_OK");
        }

        let bad_auth: Context = auth_middleware(ctx, "TOKEN123", "BADTOKEN");
        if (not bad_auth.authorized and bad_auth.status_code == 401) {
            print("AUTH_REJECT_OK");
        }

        let good_auth: Context = auth_middleware(ctx, "TOKEN123", "TOKEN123");
        let json_ctx: Context = json_response(good_auth, 201, "{\"created\": true}");
        if (json_ctx.status_code == 201 and str_contains(json_ctx.response_body, "created")) {
            print("JSON_RESPONSE_OK");
        }
        return 0;
    }
    """
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "CORS_SET_OK" in out
    assert "AUTH_REJECT_OK" in out
    assert "JSON_RESPONSE_OK" in out

def test_template_engine_xss_protection():
    code = """
    import "std/web/template.ax"

    fn main() -> int {
        let tpl: str = "<html><body>Hello, {{name}}! Note: {{{note}}}</body></html>";
        let safe: str = template_render_var(tpl, "name", "<b>admin</b> & 'test'");
        let final_html: str = template_render_raw(safe, "note", "<em>approved</em>");

        if (str_contains(final_html, "&lt;b&gt;admin&lt;/b&gt; &amp; &#x27;test&#x27;")) {
            print("XSS_ESCAPED_OK");
        }
        if (str_contains(final_html, "<em>approved</em>")) {
            print("RAW_INTERPOLATION_OK");
        }
        return 0;
    }
    """
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "XSS_ESCAPED_OK" in out
    assert "RAW_INTERPOLATION_OK" in out

def test_wasm_target_module_builder():
    code = """
    import "std/target/wasm.ax"

    fn main() -> int {
        let mut m: WasmModule = wasm_module_new();
        m = wasm_add_export(m, "main", 0, 0);
        let hex: str = wasm_get_magic_hex();
        if (wasm_validate_magic_hex(hex)) {
            print("WASM_MAGIC_OK");
        }
        if (m.byte_count > 8) {
            print("WASM_EXPORT_COUNT_OK");
        }
        return 0;
    }
    """
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "WASM_MAGIC_OK" in out
    assert "WASM_EXPORT_COUNT_OK" in out

def test_web_full_e2e_example():
    ex_path = Path(__file__).resolve().parent.parent / "examples/18_web_api_framework.ax"
    assert ex_path.exists()
    source = ex_path.read_text(encoding="utf-8")
    ret, out, _ = run_axiom_code(source)
    assert ret == 0
    assert "FAZ 5: MODERN WEB & ASYNCHRONOUS API ENGINE" in out
    assert "STATIC_ROUTE_MATCH_OK" in out
    assert "PARAMETRIC_ROUTE_MATCH_OK" in out
    assert "AUTH_GUARD_ACCEPT_OK" in out
    assert "XSS_SANITIZATION_OK" in out
    assert "WASM_BINARY_MAGIC_VALIDATION_OK" in out
    assert "TEBRIKLER! FAZ 5: MODERN WEB & API MOTORU BASARIYLA CALISTI!" in out
