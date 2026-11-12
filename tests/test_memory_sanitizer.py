"""
Axiom Programming Language (λx) - Memory Safety & AddressSanitizer (ASan) Test Suite
FAZ 1.2 & 1.3: Zero-Leak, Zero-UAF, Double-Free Protection & ASan/UBSan Integration
"""
import os
import subprocess
import tempfile
from pathlib import Path
import pytest

AXIOM_ROOT = Path(__file__).resolve().parent.parent

from tests.support_env import require_asan
AXIOM_BIN = AXIOM_ROOT / "bin" / "axiom"
RUNTIME_H = AXIOM_ROOT / "axiom" / "runtime.h"

def compile_and_run_c(c_source: str, asan: bool = True, env_extra: dict = None) -> subprocess.CompletedProcess:
    """Helper to compile and run C code with ASan flags against runtime.h."""
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as cf, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bf:
        c_path = cf.name
        bin_path = bf.name
        cf.write(c_source)

    try:
        cmd = ["gcc", "-Wall", "-Wextra", "-pthread"]
        if asan:
            cmd += ["-fsanitize=address,undefined", "-g", "-fno-omit-frame-pointer"]
        cmd += [c_path, "-lz", "-lssl", "-lcrypto", "-ldl", "-lm", "-o", bin_path]

        comp_res = subprocess.run(cmd, capture_output=True, text=True)
        assert comp_res.returncode == 0, f"Compilation failed:\n{comp_res.stderr}"

        run_env = os.environ.copy()
        if asan:
            run_env["ASAN_OPTIONS"] = "detect_leaks=1:abort_on_error=1"
        if env_extra:
            run_env.update(env_extra)

        run_res = subprocess.run([bin_path], capture_output=True, text=True, env=run_env)
        return run_res
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)


def test_double_free_protection_macro():
    """Çift serbest bırakmayı (double-free) önleyen 'axiom_safe_free(ptr)' makrosunu doğrular."""
    c_code = f"""
#include "{RUNTIME_H}"
#include <assert.h>

int main() {{
    // 1. Standart pointer üzerinde double-free koruması
    void* ptr = malloc(128);
    assert(ptr != NULL);
    axiom_safe_free(ptr);
    assert(ptr == NULL);
    // İkinci çağrı çift serbest bırakma oluşturmamalı (ASan crash vermemeli)
    axiom_safe_free(ptr);
    assert(ptr == NULL);

    // 2. NULL pointer üzerinde güvenli çağrı
    void* null_ptr = NULL;
    axiom_safe_free(null_ptr);
    assert(null_ptr == NULL);

    printf("DOUBLE_FREE_MACRO_OK\\n");
    return 0;
}}
"""
    res = compile_and_run_c(c_code, asan=True)
    assert res.returncode == 0
    assert "DOUBLE_FREE_MACRO_OK" in res.stdout


@require_asan
def test_string_safe_free_under_asan():
    """axiom_str_free ve axiom_safe_str_free fonksiyon ve makrolarını doğrular."""
    c_code = f"""
#include "{RUNTIME_H}"
#include <assert.h>

int main() {{
    // 1. Dinamik metin oluşturma ve axiom_str_free
    char* s1 = axiom_safe_strdup("Axiom Safe String");
    assert(s1 != NULL);
    assert(strcmp(s1, "Axiom Safe String") == 0);
    axiom_str_free(s1);

    // 2. axiom_str_concat ve axiom_str_free (str icin dogru API)
    ax_str s2 = axiom_str_concat("Hello, ", "Axiom!");
    assert(s2 != NULL);
    assert(strcmp(s2, "Hello, Axiom!") == 0);
    axiom_str_free(s2);
    axiom_str_free(NULL); // NULL guvenligi

    // 2b. axiom_safe_free: HAM malloc isaretcisi icin (str degil)
    char* raw = (char*)malloc(8);
    assert(raw != NULL);
    memcpy(raw, "raw", 4);
    axiom_safe_free(raw);
    assert(raw == NULL);
    axiom_safe_free(raw); // Double free güvenliği

    // 3. NULL string serbest bırakma
    axiom_str_free(NULL);

    printf("STRING_SAFE_FREE_OK\\n");
    return 0;
}}
"""
    res = compile_and_run_c(c_code, asan=True)
    assert res.returncode == 0
    assert "STRING_SAFE_FREE_OK" in res.stdout


@require_asan
def test_array_safe_free_under_asan():
    """axiom_array_free ve tip bazlı dizi temizleyicilerini doğrular."""
    c_code = f"""
#include "{RUNTIME_H}"
#include <assert.h>

int main() {{
    // 1. Int dizisi
    ax_array_int int_arr = axiom_array_create_int(10);
    assert(int_arr.length == 10);
    assert(int_arr.data != NULL);
    axiom_array_free(int_arr);
    assert(int_arr.data == NULL);
    assert(int_arr.length == 0);
    // İkinci serbest bırakma güvenli olmalı
    axiom_array_free(int_arr);

    // 2. String dizisi
    ax_array_str str_arr = axiom_str_split("alpha,beta,gamma,delta", ",");
    assert(str_arr.length == 4);
    assert(str_arr.data != NULL);
    axiom_array_str_free(&str_arr);
    assert(str_arr.data == NULL);
    assert(str_arr.length == 0);
    // İkinci serbest bırakma güvenli olmalı
    axiom_array_str_free(&str_arr);

    printf("ARRAY_SAFE_FREE_OK\\n");
    return 0;
}}
"""
    res = compile_and_run_c(c_code, asan=True)
    assert res.returncode == 0
    assert "ARRAY_SAFE_FREE_OK" in res.stdout


def test_buffer_memory_lifecycle_and_uaf_defense():
    """AxiomByteBuffer bellek yaşam döngüsü, double-free ve UAF savunmasını ASan ile doğrular."""
    c_code = f"""
#include "{RUNTIME_H}"
#include <assert.h>

int main() {{
    // 1. Buffer oluşturma ve veri yazma/okuma
    ax_int h = axiom_buf_create(32);
    assert(h > 0);
    axiom_buf_write_u8(h, 0xAB);
    axiom_buf_write_u16_be(h, 0x1234);
    axiom_buf_write_u32_be(h, 0xDEADBEEF);
    axiom_buf_write_str(h, "SECURE_DATA");

    assert(axiom_buf_read_u8(h, 0) == 0xAB);
    assert(axiom_buf_read_u16_be(h, 1) == 0x1234);
    assert(axiom_buf_read_u32_be(h, 3) == (ax_int)0xDEADBEEF);

    ax_str hex = axiom_buf_to_hex(h);
    assert(hex != NULL && strlen(hex) > 0);
    axiom_str_free(hex);

    // 2. Güvenli serbest bırakma (Safe Free)
    axiom_buf_free(h);

    // 3. Çift Serbest Bırakma (Double-Free Koruması) - ASan çökmemeli!
    axiom_buf_free(h);

    // 4. Use-After-Free Savunması - Serbest bırakılan handle erişimi çökmeye neden olmamalı
    axiom_buf_write_u8(h, 0xFF);
    ax_int val = axiom_buf_read_u8(h, 0);
    assert(val == 0);

    printf("BUFFER_LIFECYCLE_OK\\n");
    return 0;
}}
"""
    res = compile_and_run_c(c_code, asan=True)
    assert res.returncode == 0
    assert "BUFFER_LIFECYCLE_OK" in res.stdout


def test_tensor_memory_lifecycle_and_uaf_defense():
    """AxiomTensor matris çarpımı, transpose, serbest bırakma ve UAF korumasını ASan ile doğrular."""
    c_code = f"""
#include "{RUNTIME_H}"
#include <assert.h>

int main() {{
    // 1. Tensör oluşturma ve doldurma
    ax_int t1 = axiom_tensor_create_2d(2, 3);
    ax_int t2 = axiom_tensor_create_2d(3, 2);
    assert(t1 > 0 && t2 > 0);

    axiom_tensor_set(t1, 0, 0, 1.0);
    axiom_tensor_set(t1, 0, 1, 2.0);
    axiom_tensor_set(t1, 0, 2, 3.0);
    axiom_tensor_set(t1, 1, 0, 4.0);
    axiom_tensor_set(t1, 1, 1, 5.0);
    axiom_tensor_set(t1, 1, 2, 6.0);

    axiom_tensor_set(t2, 0, 0, 7.0);
    axiom_tensor_set(t2, 0, 1, 8.0);
    axiom_tensor_set(t2, 1, 0, 9.0);
    axiom_tensor_set(t2, 1, 1, 1.0);
    axiom_tensor_set(t2, 2, 0, 2.0);
    axiom_tensor_set(t2, 2, 1, 3.0);

    // 2. Matris çarpımı (GEMM)
    ax_int t_res = axiom_tensor_matmul(t1, t2);
    assert(t_res > 0);
    assert(axiom_tensor_rows(t_res) == 2);
    assert(axiom_tensor_cols(t_res) == 2);

    // (1*7 + 2*9 + 3*2) = 7 + 18 + 6 = 31
    ax_float val_00 = axiom_tensor_get(t_res, 0, 0);
    assert(fabs(val_00 - 31.0) < 1e-6);

    // 3. Transpose
    ax_int t_tr = axiom_tensor_transpose(t1);
    assert(t_tr > 0);
    assert(axiom_tensor_rows(t_tr) == 3);
    assert(axiom_tensor_cols(t_tr) == 2);

    // 4. String formatlama ve temizleme
    ax_str s_repr = axiom_tensor_to_str(t_res);
    assert(s_repr != NULL && strlen(s_repr) > 0);
    axiom_str_free(s_repr);

    // 5. Serbest bırakma (Deallocation)
    axiom_tensor_free(t1);
    axiom_tensor_free(t2);
    axiom_tensor_free(t_res);
    axiom_tensor_free(t_tr);

    // 6. Çift serbest bırakma (Double-Free Koruması)
    axiom_tensor_free(t1);
    axiom_tensor_free(t2);

    // 7. Use-After-Free Savunması
    ax_float dummy = axiom_tensor_get(t1, 0, 0);
    assert(dummy == 0.0);
    axiom_tensor_set(t1, 0, 0, 99.0); // Sessizce engellenmeli

    printf("TENSOR_LIFECYCLE_OK\\n");
    return 0;
}}
"""
    res = compile_and_run_c(c_code, asan=True)
    assert res.returncode == 0
    assert "TENSOR_LIFECYCLE_OK" in res.stdout


@require_asan
def test_cli_build_and_run_with_asan(tmp_path):
    """'axiom build --asan' ve 'axiom run --asan' komutlarının AddressSanitizer ile derlenip çalıştığını doğrular."""
    ax_source = """
fn main() -> void {
    let s1 = "AddressSanitizer "
    let s2 = "Integration Clean!"
    let msg = s1 + s2
    print(msg)

    let mut sum = 0
    let mut i = 0
    while i < 10 {
        sum = sum + i
        i = i + 1
    }
    print("Sum: ", sum)
}
"""
    src_file = tmp_path / "asan_test.ax"
    bin_file = tmp_path / "asan_test.bin"
    src_file.write_text(ax_source, encoding="utf-8")

    # 1. axiom build --asan
    cmd_build = [str(AXIOM_BIN), "build", "--asan", str(src_file), "-o", str(bin_file)]
    build_res = subprocess.run(cmd_build, capture_output=True, text=True)
    assert build_res.returncode == 0, f"axiom build --asan failed: {build_res.stderr}"
    assert "Bağımsız yerel ikili dosya üretildi" in build_res.stdout
    assert bin_file.exists()

    # Üretilen ikilinin ASan ile koşulması
    run_env = os.environ.copy()
    run_env["ASAN_OPTIONS"] = "detect_leaks=1:abort_on_error=1"
    exec_res = subprocess.run([str(bin_file)], capture_output=True, text=True, env=run_env)
    assert exec_res.returncode == 0, f"Binary failed under ASan: {exec_res.stderr}"
    assert "AddressSanitizer Integration Clean!" in exec_res.stdout
    assert "45" in exec_res.stdout

    # 2. axiom run --asan
    cmd_run = [str(AXIOM_BIN), "run", "--asan", str(src_file)]
    run_res = subprocess.run(cmd_run, capture_output=True, text=True, env=run_env)
    assert run_res.returncode == 0, f"axiom run --asan failed: {run_res.stderr}"
    assert "AddressSanitizer Integration Clean!" in run_res.stdout
    assert "45" in run_res.stdout


def test_cli_build_with_ubsan(tmp_path):
    """'axiom build --ubsan' komutunun UndefinedBehaviorSanitizer ile derleme yaptığını doğrular."""
    ax_source = """
fn main() -> void {
    let a = 100
    let b = 200
    print("UBSan Test: ", a + b)
}
"""
    src_file = tmp_path / "ubsan_test.ax"
    bin_file = tmp_path / "ubsan_test.bin"
    src_file.write_text(ax_source, encoding="utf-8")

    cmd_build = [str(AXIOM_BIN), "build", "--ubsan", str(src_file), "-o", str(bin_file)]
    build_res = subprocess.run(cmd_build, capture_output=True, text=True)
    assert build_res.returncode == 0, f"axiom build --ubsan failed: {build_res.stderr}"
    assert bin_file.exists()

    exec_res = subprocess.run([str(bin_file)], capture_output=True, text=True)
    assert exec_res.returncode == 0
    assert "300" in exec_res.stdout


@require_asan
def test_cli_test_asan_flag():
    """'axiom test --asan' komutunun ortam değişkenine AXIOM_ASAN ilettiğini ve alt süreçte çalıştığını doğrular."""
    # Sadece bu test dosyasındaki basit bir birim testi koşarak doğrula
    cmd = [str(AXIOM_BIN), "test", "--asan", "-k", "test_double_free_protection_macro"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"axiom test --asan failed: {res.stderr}"
    assert "1 passed" in res.stdout or "passed in" in res.stdout


@require_asan
def test_axiom_source_tensor_and_buffer_under_asan(tmp_path):
    """Axiom dili seviyesinde buffer ve tensor işlemlerinin --asan ile sıfır kaçak ve sıfır hata ile çalıştığını doğrular."""
    ax_source = """
fn main() -> void {
    // 1. Buffer döngüsü
    let b = rt_buf_create(64)
    rt_buf_write_u32_be(b, 305419896)
    rt_buf_write_str(b, "AxiomASan")
    let v = rt_buf_read_u32_be(b, 0)
    print("Buffer Val: ", v)
    rt_buf_free(b)
    // Double free koruması Axiom seviyesinde
    rt_buf_free(b)

    // 2. Tensor döngüsü
    let t = tensor_create_2d(2, 2)
    tensor_set(t, 0, 0, 10.5)
    tensor_set(t, 1, 1, 20.5)
    let g = tensor_get(t, 0, 0)
    print("Tensor Get: ", g)
    tensor_free(t)
    // Double free koruması Axiom seviyesinde
    tensor_free(t)

    print("ALL_AXIOM_RESOURCES_FREED_CLEANLY")
}
"""
    src_file = tmp_path / "resources_test.ax"
    src_file.write_text(ax_source, encoding="utf-8")

    run_env = os.environ.copy()
    run_env["ASAN_OPTIONS"] = "detect_leaks=1:abort_on_error=1"

    cmd = [str(AXIOM_BIN), "run", "--asan", str(src_file)]
    res = subprocess.run(cmd, capture_output=True, text=True, env=run_env)
    assert res.returncode == 0, f"Run failed with ASan:\n{res.stderr}"
    assert "305419896" in res.stdout
    assert "10.5" in res.stdout
    assert "ALL_AXIOM_RESOURCES_FREED_CLEANLY" in res.stdout
