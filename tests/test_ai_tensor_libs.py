"""
Axiom Programming Language (λx) - FAZ 4: Yapay Zeka (AI/ML) & Tensör Motoru Testleri
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

def test_tensor_create_and_indexing():
    code = """
    import "std/ai/tensor.ax"

    fn main() -> int {
        let t: Tensor = tensor_new(2, 3);
        tensor_set_val(t, 0, 0, 1.5);
        tensor_set_val(t, 1, 2, 4.2);
        
        let v0: float = tensor_get_val(t, 0, 0);
        let v1: float = tensor_get_val(t, 1, 2);
        if (v0 > 1.4 and v0 < 1.6 and v1 > 4.1 and v1 < 4.3) {
            print("TENSOR_VALS_OK");
        }
        print("ROWS:", t.rows);
        print("COLS:", t.cols);
        tensor_destroy(t);
        return 0;
    }
    """
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "TENSOR_VALS_OK" in out
    assert "ROWS: 2" in out
    assert "COLS: 3" in out

def test_linalg_matmul_and_transpose():
    code = """
    import "std/ai/tensor.ax"
    import "std/ai/linalg.ax"

    fn main() -> int {
        // A: 2x2, B: 2x2
        // A = [[1, 2], [3, 4]]
        // B = [[2, 0], [1, 2]]
        // C = A x B = [[4, 4], [10, 8]]
        let a: Tensor = tensor_new(2, 2);
        tensor_set_val(a, 0, 0, 1.0);
        tensor_set_val(a, 0, 1, 2.0);
        tensor_set_val(a, 1, 0, 3.0);
        tensor_set_val(a, 1, 1, 4.0);

        let b: Tensor = tensor_new(2, 2);
        tensor_set_val(b, 0, 0, 2.0);
        tensor_set_val(b, 0, 1, 0.0);
        tensor_set_val(b, 1, 0, 1.0);
        tensor_set_val(b, 1, 1, 2.0);

        let c: Tensor = matmul(a, b);
        let c00: float = tensor_get_val(c, 0, 0);
        let c10: float = tensor_get_val(c, 1, 0);
        if (c00 == 4.0 and c10 == 10.0) {
            print("MATMUL_GEMM_OK");
        }

        let at: Tensor = mat_transpose(a);
        if (tensor_get_val(at, 0, 1) == 3.0 and tensor_get_val(at, 1, 0) == 2.0) {
            print("TRANSPOSE_OK");
        }

        let d: float = dot(a, b);
        // dot = 1*2 + 2*0 + 3*1 + 4*2 = 2 + 0 + 3 + 8 = 13.0
        if (d == 13.0) {
            print("DOT_PRODUCT_OK");
        }

        tensor_destroy(a);
        tensor_destroy(b);
        tensor_destroy(c);
        tensor_destroy(at);
        return 0;
    }
    """
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "MATMUL_GEMM_OK" in out
    assert "TRANSPOSE_OK" in out
    assert "DOT_PRODUCT_OK" in out

def test_autograd_graph_and_backprop():
    code = """
    import "std/ai/autograd.ax"

    fn main() -> int {
        let n: GradNode = autograd_create_node(10, true);
        let n2: GradNode = autograd_accumulate_grad(n, 0.75);
        if (n2.grad == 0.75) {
            print("AUTOGRAD_ACC_OK");
        }

        let d_relu: float = autograd_backward_relu(1.0, 0.5);
        let d_relu_zero: float = autograd_backward_relu(1.0, -0.5);
        if (d_relu == 1.0 and d_relu_zero == 0.0) {
            print("AUTOGRAD_RELU_OK");
        }

        let d_sig: float = autograd_backward_sigmoid(1.0, 0.5);
        // 1.0 * (0.5 * 0.5) = 0.25
        if (d_sig == 0.25) {
            print("AUTOGRAD_SIGMOID_OK");
        }
        return 0;
    }
    """
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "AUTOGRAD_ACC_OK" in out
    assert "AUTOGRAD_RELU_OK" in out
    assert "AUTOGRAD_SIGMOID_OK" in out

def test_nn_layers_and_activations():
    code = """
    import "std/ai/tensor.ax"
    import "std/ai/linalg.ax"
    import "std/ai/nn.ax"

    fn main() -> int {
        let x: Tensor = tensor_new(1, 2);
        tensor_set_val(x, 0, 0, 1.0);
        tensor_set_val(x, 0, 1, 2.0);

        let w: Tensor = tensor_new(2, 2);
        tensor_set_val(w, 0, 0, 0.5);
        tensor_set_val(w, 0, 1, -1.0);
        tensor_set_val(w, 1, 0, 1.5);
        tensor_set_val(w, 1, 1, 0.5);

        let b: Tensor = tensor_new(1, 2);
        tensor_set_val(b, 0, 0, 0.0);
        tensor_set_val(b, 0, 1, 0.0);

        let out: Tensor = linear_forward(x, w, b);
        // out[0] = 1*0.5 + 2*1.5 = 3.5
        // out[1] = 1*(-1.0) + 2*0.5 = 0.0
        let act: Tensor = tensor_apply_relu(out);
        if (tensor_get_val(act, 0, 0) == 3.5 and tensor_get_val(act, 0, 1) == 0.0) {
            print("NN_FORWARD_RELU_OK");
        }

        let target: Tensor = tensor_new(1, 2);
        tensor_set_val(target, 0, 0, 3.5);
        tensor_set_val(target, 0, 1, 0.0);
        let loss: float = mse_loss(act, target);
        if (loss == 0.0) {
            print("MSE_PERFECT_MATCH_OK");
        }

        tensor_destroy(x);
        tensor_destroy(w);
        tensor_destroy(b);
        tensor_destroy(out);
        tensor_destroy(act);
        tensor_destroy(target);
        return 0;
    }
    """
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "NN_FORWARD_RELU_OK" in out
    assert "MSE_PERFECT_MATCH_OK" in out

def test_ai_inference_classification():
    code = """
    import "std/ai/tensor.ax"
    import "std/ai/inference.ax"

    fn main() -> int {
        let logits: Tensor = tensor_new(1, 3);
        tensor_set_val(logits, 0, 0, 0.1);
        tensor_set_val(logits, 0, 1, 0.85);
        tensor_set_val(logits, 0, 2, 0.05);

        let top_idx: int = model_classify(logits);
        if (top_idx == 1) {
            print("CLASSIFY_ARGMAX_OK");
        }
        tensor_destroy(logits);
        return 0;
    }
    """
    ret, out, _ = run_axiom_code(code)
    assert ret == 0
    assert "CLASSIFY_ARGMAX_OK" in out

def test_ai_tensor_full_e2e_example():
    ex_path = Path(__file__).resolve().parent.parent / "examples/17_ai_tensor_neural_net.ax"
    assert ex_path.exists()
    source = ex_path.read_text(encoding="utf-8")
    ret, out, _ = run_axiom_code(source)
    assert ret == 0
    assert "FAZ 4: AI & ML TENSOR ENGINE & NEURAL NET" in out
    assert "GRADIENT_BACKWARD_OK" in out
    assert "MSE_LOSS_COMPUTED_OK" in out
    assert "TEBRIKLER! FAZ 4: AI & ML TENSOR ENGINE BASARIYLA CALISTI!" in out
