"""
Axiom Programming Language (λx) - FAZ 4.1: Donanımsal AVX2/FMA SIMD Tensör GEMM Testleri
"""
import pytest
import subprocess
import tempfile
import os

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

        run_res = subprocess.run([bin_path], capture_output=True, text=True, timeout=20)
        return run_res.returncode, run_res.stdout, run_res.stderr
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

def test_avx2_simd_hardware_detection():
    code = """
    import "std/text/unicode.ax"

    fn main() -> int {
        let avx2: bool = is_avx2_supported();
        if (avx2) {
            print("AVX2_SIMD_HARDWARE_ACTIVE");
        } else {
            print("AVX2_SIMD_FALLBACK_ACTIVE");
        }
        return 0;
    }
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0
    assert "AVX2_SIMD_HARDWARE_ACTIVE" in out or "AVX2_SIMD_FALLBACK_ACTIVE" in out

def test_avx2_gemm_small_matrix():
    code = """
    import "std/ai/tensor.ax"
    import "std/ai/linalg.ax"

    fn main() -> int {
        // A = [[1.5, 2.0], [3.0, 4.5]]
        // B = [[2.0, -1.0], [0.5, 3.0]]
        // C = A x B = [[1.5*2 + 2*0.5, 1.5*(-1) + 2*3], [3*2 + 4.5*0.5, 3*(-1) + 4.5*3]]
        // C = [[4.0, 4.5], [8.25, 10.5]]
        let a: Tensor = tensor_new(2, 2);
        tensor_set_val(a, 0, 0, 1.5);
        tensor_set_val(a, 0, 1, 2.0);
        tensor_set_val(a, 1, 0, 3.0);
        tensor_set_val(a, 1, 1, 4.5);

        let b: Tensor = tensor_new(2, 2);
        tensor_set_val(b, 0, 0, 2.0);
        tensor_set_val(b, 0, 1, -1.0);
        tensor_set_val(b, 1, 0, 0.5);
        tensor_set_val(b, 1, 1, 3.0);

        let c: Tensor = matmul(a, b);
        let c00: float = tensor_get_val(c, 0, 0);
        let c01: float = tensor_get_val(c, 0, 1);
        let c10: float = tensor_get_val(c, 1, 0);
        let c11: float = tensor_get_val(c, 1, 1);

        if (c00 == 4.0 and c01 == 4.5 and c10 == 8.25 and c11 == 10.5) {
            print("SMALL_GEMM_OK");
        }

        tensor_destroy(a);
        tensor_destroy(b);
        tensor_destroy(c);
        return 0;
    }
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0
    assert "SMALL_GEMM_OK" in out

def test_avx2_gemm_rectangular_and_unaligned():
    # 3x5 * 5x4 = 3x4 matris (vektör genişliği 4 olduğundan 3 ve 5 sınırları zorlar)
    code = """
    import "std/ai/tensor.ax"
    import "std/ai/linalg.ax"

    fn main() -> int {
        let a: Tensor = tensor_new(3, 5);
        let b: Tensor = tensor_new(5, 4);

        let mut i: int = 0;
        while (i < 3) {
            let mut k: int = 0;
            while (k < 5) {
                tensor_set_val(a, i, k, 1.0);
                k = k + 1;
            }
            i = i + 1;
        }

        let mut k2: int = 0;
        while (k2 < 5) {
            let mut j: int = 0;
            while (j < 4) {
                tensor_set_val(b, k2, j, 2.0);
                j = j + 1;
            }
            k2 = k2 + 1;
        }

        let c: Tensor = matmul(a, b);
        // Her eleman 5 * (1.0 * 2.0) = 10.0 olmalı
        let c00: float = tensor_get_val(c, 0, 0);
        let c23: float = tensor_get_val(c, 2, 3);

        if (c.rows == 3 and c.cols == 4 and c00 == 10.0 and c23 == 10.0) {
            print("UNALIGNED_RECTANGULAR_GEMM_OK");
        }

        tensor_destroy(a);
        tensor_destroy(b);
        tensor_destroy(c);
        return 0;
    }
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0
    assert "UNALIGNED_RECTANGULAR_GEMM_OK" in out

def test_avx2_gemm_cache_blocked_large_matrix():
    # 64x64 matris çarpımı (Cache block boyutu 64'ü ve SIMD unrolling 16'yı tam test eder)
    code = """
    import "std/ai/tensor.ax"
    import "std/ai/linalg.ax"

    fn main() -> int {
        let n: int = 64;
        let a: Tensor = tensor_new(n, n);
        let b: Tensor = tensor_new(n, n);

        // A = Identity (Birim matris)
        let mut i: int = 0;
        while (i < n) {
            tensor_set_val(a, i, i, 1.0);
            let mut j: int = 0;
            while (j < n) {
                let v: float = 2.5;
                tensor_set_val(b, i, j, v);
                j = j + 1;
            }
            i = i + 1;
        }

        // C = A x B = I x B = B
        let c: Tensor = matmul(a, b);

        let mut pass: bool = true;
        let mut r: int = 0;
        while (r < n) {
            let mut col: int = 0;
            while (col < n) {
                let expected: float = 2.5;
                let actual: float = tensor_get_val(c, r, col);
                if (actual != expected) {
                    pass = false;
                }
                col = col + 1;
            }
            r = r + 1;
        }

        if (pass) {
            print("LARGE_CACHE_BLOCKED_GEMM_OK");
        }

        tensor_destroy(a);
        tensor_destroy(b);
        tensor_destroy(c);
        return 0;
    }
    """
    ret, out, err = run_axiom_code(code)
    assert ret == 0
    assert "LARGE_CACHE_BLOCKED_GEMM_OK" in out
