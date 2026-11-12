"""
Axiom Programming Language (λx) - Offensive Feature Isolation Tests
Verifies strict isolation of offensive security modules behind `--features offensive` flag
and AXIOM_FEATURES environment variable.
"""
import os
import subprocess
import tempfile
import pytest
from pathlib import Path

from axiom.cli import compile_axiom_source
from axiom.checker import SemanticError

OFFENSIVE_IMPORT_CASES = [
    ("std:security:shellcode", 'import "std:security:shellcode"\nfn main() -> int { return 0; }'),
    ("std/security/shellcode", 'import "std/security/shellcode"\nfn main() -> int { return 0; }'),
    ("std:net:c2", 'import "std:net:c2"\nfn main() -> int { return 0; }'),
    ("std:security:evasion", 'import "std:security:evasion"\nfn main() -> int { return 0; }'),
    ("std:security:memdump", 'import "std:security:memdump"\nfn main() -> int { return 0; }'),
    ("std:net:packet_crafter", 'import "std:net:packet_crafter"\nfn main() -> int { return 0; }'),
]


@pytest.mark.parametrize("mod_name,code", OFFENSIVE_IMPORT_CASES)
def test_offensive_module_rejected_without_flag_in_compile_source(mod_name, code, monkeypatch):
    monkeypatch.delenv("AXIOM_FEATURES", raising=False)
    with pytest.raises(SemanticError) as excinfo:
        compile_axiom_source(code, features=None)
    err = str(excinfo.value)
    assert "ofansif güvenlik modülüdür" in err
    assert "--features offensive" in err
    assert "Hata:" in err


@pytest.mark.parametrize("mod_name,code", OFFENSIVE_IMPORT_CASES)
def test_offensive_module_allowed_with_explicit_features_param(mod_name, code, monkeypatch):
    monkeypatch.delenv("AXIOM_FEATURES", raising=False)
    c_code = compile_axiom_source(code, features=["offensive"])
    assert "ax_main" in c_code or "main" in c_code


@pytest.mark.parametrize("mod_name,code", OFFENSIVE_IMPORT_CASES)
def test_offensive_module_allowed_via_env_var(mod_name, code, monkeypatch):
    monkeypatch.setenv("AXIOM_FEATURES", "offensive")
    c_code = compile_axiom_source(code)
    assert "ax_main" in c_code or "main" in c_code


def _get_test_env():
    env = os.environ.copy()
    repo_root = str(Path(__file__).parent.parent.resolve())
    env["PYTHONPATH"] = f"{repo_root}:{env.get('PYTHONPATH', '')}"
    return env


def test_cli_build_rejected_without_feature(monkeypatch):
    monkeypatch.delenv("AXIOM_FEATURES", raising=False)
    with tempfile.NamedTemporaryFile(suffix=".ax", mode="w", delete=False) as f:
        f.write('import "std:security:shellcode"\nfn main() -> int { return 0; }\n')
        src_path = f.name
    try:
        cmd = ["python3", "-m", "axiom.cli", "build", src_path]
        res = subprocess.run(cmd, capture_output=True, text=True, env=_get_test_env())
        assert res.returncode != 0
        assert "ofansif güvenlik modülüdür" in res.stderr
        assert "--features offensive" in res.stderr
    finally:
        if os.path.exists(src_path):
            os.remove(src_path)


def test_cli_build_succeeds_with_feature_flag(monkeypatch):
    monkeypatch.delenv("AXIOM_FEATURES", raising=False)
    with tempfile.NamedTemporaryFile(suffix=".ax", mode="w", delete=False) as f, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as out:
        f.write('import "std:security:evasion"\nfn main() -> int { return 0; }\n')
        src_path = f.name
        out_bin = out.name
    try:
        cmd = ["python3", "-m", "axiom.cli", "build", src_path, "--features", "offensive", "-o", out_bin]
        res = subprocess.run(cmd, capture_output=True, text=True, env=_get_test_env())
        assert res.returncode == 0, res.stderr
        assert os.path.exists(out_bin)
    finally:
        if os.path.exists(src_path):
            os.remove(src_path)
        if os.path.exists(out_bin):
            os.remove(out_bin)


def test_cli_check_rejected_without_feature(monkeypatch):
    monkeypatch.delenv("AXIOM_FEATURES", raising=False)
    with tempfile.NamedTemporaryFile(suffix=".ax", mode="w", delete=False) as f:
        f.write('import "std:net:c2"\nfn main() -> int { return 0; }\n')
        src_path = f.name
    try:
        cmd = ["python3", "-m", "axiom.cli", "check", src_path]
        res = subprocess.run(cmd, capture_output=True, text=True, env=_get_test_env())
        assert res.returncode != 0
        assert "ofansif güvenlik modülüdür" in res.stderr
    finally:
        if os.path.exists(src_path):
            os.remove(src_path)


def test_cli_check_succeeds_with_features(monkeypatch):
    monkeypatch.delenv("AXIOM_FEATURES", raising=False)
    with tempfile.NamedTemporaryFile(suffix=".ax", mode="w", delete=False) as f:
        f.write('import "std:net:c2"\nfn main() -> int { return 0; }\n')
        src_path = f.name
    try:
        cmd = ["python3", "-m", "axiom.cli", "check", src_path, "--features", "offensive"]
        res = subprocess.run(cmd, capture_output=True, text=True, env=_get_test_env())
        assert res.returncode == 0, res.stderr
        assert "Doğrulama Başarılı" in res.stdout
    finally:
        if os.path.exists(src_path):
            os.remove(src_path)
