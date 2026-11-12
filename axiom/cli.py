"""
Axiom Programming Language (λx) - Command Line Interface (CLI Driver)
"""
import sys
import os
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple, Set, Union

from axiom.lexer import Lexer, LexerError
from axiom.parser import Parser, ParserError
from axiom.checker import TypeChecker, SemanticError
from axiom.codegen_c import CCodeGenerator
from axiom.codegen_llvm import LLVMCodeGenerator
from axiom.resolver import ModuleResolver, ModuleError
from axiom.formatter import format_source
from axiom.prover import SymbolicProver, ProofError
from axiom.z3_prover import Z3Prover

CLR_RED = "\033[1;31m"
CLR_GREEN = "\033[1;32m"
CLR_YELLOW = "\033[1;33m"
CLR_CYAN = "\033[1;36m"
CLR_BOLD = "\033[1m"
CLR_RESET = "\033[0m"

def get_runtime_header_path() -> str:
    # Path to runtime.h inside axiom package
    base_dir = Path(__file__).resolve().parent
    header = base_dir / "runtime.h"
    return str(header)

def get_sanitizer_flags(args) -> List[str]:
    asan = getattr(args, 'asan', False)
    ubsan = getattr(args, 'ubsan', False)
    if asan and ubsan:
        return ["-fsanitize=address,undefined", "-g", "-fno-omit-frame-pointer"]
    elif asan:
        return ["-fsanitize=address,undefined", "-g", "-fno-omit-frame-pointer"]
    elif ubsan:
        return ["-fsanitize=undefined", "-g", "-fno-omit-frame-pointer"]
    return []


def get_platform_link_flags(target: Optional[str]) -> List[str]:
    """Hedef platforma gore baglama bayraklari.

    Windows (mingw): yalnizca ws2_32 — OpenSSL/zlib/dl/pthread yok.
    Bu durumda runtime ACIK HATA dondurur (platform.h / runtime.h icinde).
    """
    t = (target or "").lower().strip()
    if t in ("windows", "win", "win64", "mingw", "x86_64-windows",
             "x86_64-w64-mingw32") or "mingw" in t:
        return ["-lws2_32"]
    if "wasm" in t:
        return []
    return ["-lz", "-lssl", "-lcrypto", "-ldl", "-lm"]


def get_thread_flag(target: Optional[str]) -> List[str]:
    t = (target or "").lower().strip()
    if t in ("windows", "win", "win64", "mingw", "x86_64-windows",
             "x86_64-w64-mingw32") or "mingw" in t:
        return []
    if "wasm" in t:
        return []
    return ["-pthread"]

def get_target_compiler_flags(target: Optional[str], cc: str, sysroot: Optional[str] = None) -> Tuple[str, List[str]]:
    if not target:
        return cc, []
    t = target.lower().strip()
    if t in ("x86_64", "amd64", "x86_64-linux-gnu"):
        target_triple = "x86_64-linux-gnu"
    elif t in ("aarch64", "arm64", "aarch64-linux-gnu"):
        target_triple = "aarch64-linux-gnu"
    elif t in ("wasm32", "wasm", "wasm32-wasi"):
        target_triple = "wasm32-wasi"
    elif t in ("windows", "win", "win64", "mingw", "x86_64-windows", "x86_64-w64-mingw32"):
        # Windows: mingw-w64 araclari kullanilir (clang --target de olur ama
        # mingw sysroot'a ihtiyac duyar; kurulu cross-gcc en guvenilir yol).
        for cc_name in ("x86_64-w64-mingw32-gcc", "x86_64-w64-mingw32-clang"):
            if subprocess.run(["which", cc_name], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE).returncode == 0:
                return cc_name, ["-lws2_32"]
        return "x86_64-w64-mingw32-gcc", ["-lws2_32"]
    else:
        target_triple = target

    extra_flags: List[str] = []
    if sysroot:
        extra_flags.append(f"--sysroot={sysroot}")
    elif "wasm" in target_triple and "WASI_SDK_PATH" in os.environ:
        wasi_path = Path(os.environ["WASI_SDK_PATH"])
        if wasi_path.exists():
            wasi_sysroot = wasi_path / "share" / "wasi-sysroot"
            if wasi_sysroot.exists():
                extra_flags.append(f"--sysroot={wasi_sysroot}")

    # Clang multi-target destegi
    res = subprocess.run(["which", "clang"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode == 0:
        return "clang", [f"--target={target_triple}"] + extra_flags

    cross_gcc = f"{target_triple}-gcc"
    res_gcc = subprocess.run(["which", cross_gcc], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res_gcc.returncode == 0:
        return cross_gcc, extra_flags

    return cc, [f"--target={target_triple}"] + extra_flags


def validate_target_toolchain(target: str, cc: str, target_flags: List[str]) -> Tuple[bool, str]:
    """
    Hedef mimari için sistemde geçerli C derleyici toolchain ve sysroot başlıklarının
    bulunup bulunmadığını doğrular.
    """
    t = target.lower().strip()
    probe_src = "#include <stdio.h>\nint main(void) { return 0; }\n"
    cmd = [cc] + target_flags + ["-xc", "-", "-c", "-o", "/dev/null"]
    try:
        res = subprocess.run(cmd, input=probe_src.encode("utf-8"), capture_output=True, timeout=5)
        if res.returncode == 0:
            return True, ""
        err_detail = res.stderr.decode("utf-8", errors="replace").strip()
    except Exception as ex:
        err_detail = str(ex)

    if "wasm" in t:
        msg = (
            f"Hata: '{target}' hedefi için WASI SDK veya sysroot bulunamadı.\n"
            f"  Detay: {err_detail}\n"
            f"  Lütfen WASI SDK kurun (örn: WASI_SDK_PATH=/opt/wasi-sdk) veya derleyiciye --sysroot belirtin.\n"
            f"  (Not: WebAssembly/WASM hedefi harici sysroot gerektirir ve deneyseldir.)"
        )
    elif "aarch64" in t or "arm64" in t:
        msg = (
            f"Hata: '{target}' hedefi için cross-toolchain veya sysroot bulunamadı.\n"
            f"  Detay: {err_detail}\n"
            f"  Lütfen aarch64 cross-toolchain paketini kurun (örn: 'sudo apt install gcc-aarch64-linux-gnu libc6-dev-arm64-cross')\n"
            f"  veya derleyiciye --sysroot belirtin.\n"
            f"  (Not: ARM64/aarch64 çapraz derleme hedefi harici sysroot gerektirir ve deneyseldir.)"
        )
    else:
        msg = (
            f"Hata: '{target}' hedefi için C derleme toolchain veya sysroot doğrulanamadı.\n"
            f"  Detay: {err_detail}\n"
            f"  Lütfen hedef mimarinin toolchain ve sysroot paketlerini kurun veya --sysroot belirtin.\n"
            f"  (Not: Çapraz derleme hedefleri harici sysroot gerektirir ve deneyseldir.)"
        )
    return False, msg

def compile_axiom_source(
    source_text: str,
    source_path: str = "<stdin>",
    prove: bool = True,
    debug: bool = False,
    features: Optional[Union[str, List[str], Set[str]]] = None
) -> str:
    # 1. Lexing
    lexer = Lexer(source_text)
    tokens = lexer.tokenize()

    # 2. Parsing
    parser = Parser(tokens)
    program = parser.parse()

    # 2.5 Module Resolution
    resolver = ModuleResolver(base_file_path=source_path, features=features)
    program = resolver.resolve(program)

    # 3. Type & Contract Verification
    checker = TypeChecker()
    checker.check(program)

    # 3.5 Static Mathematical Proof & Symbolic Verification
    if prove:
        prover = SymbolicProver()
        prover.verify_program(program)

    # 4. C99 Code Generation
    runtime_path = get_runtime_header_path()
    codegen = CCodeGenerator(runtime_header_path=runtime_path, source_file=source_path, debug_symbols=debug)
    c_code = codegen.generate(program)
    return c_code

def find_c_compiler() -> str:
    for cc in ["clang", "gcc"]:
        res = subprocess.run(["which", cc], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0:
            return cc
    raise RuntimeError("Sistemde 'clang' veya 'gcc' C derleyicisi bulunamadi!")

def cmd_build(args):
    input_file = Path(args.file)
    if not input_file.exists():
        print(f"{CLR_RED}Hata:{CLR_RESET} '{input_file}' dosyasi bulunamadi.", file=sys.stderr)
        sys.exit(1)

    output_path = args.output or input_file.stem
    backend = getattr(args, 'backend', 'c')
    features = getattr(args, 'features', None)

    if backend == 'llvm':
        try:
            source_code = input_file.read_text(encoding="utf-8")
            lexer = Lexer(source_code)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            resolver = ModuleResolver(base_file_path=str(input_file), features=features)
            program = resolver.resolve(program)
            checker = TypeChecker()
            checker.check(program)
            prover = SymbolicProver()
            prover.verify_program(program)

            dbg_enabled = getattr(args, 'debug', False)
            codegen = LLVMCodeGenerator(
                debug=dbg_enabled,
                source_file=input_file.name,
                source_dir=str(input_file.parent.resolve())
            )
            llvm_ir = codegen.generate(program)
        except (LexerError, ParserError, SemanticError, ModuleError, ProofError, NotImplementedError) as e:
            print(f"{CLR_RED}{e}{CLR_RESET}", file=sys.stderr)
            sys.exit(1)

        runtime_c = str(Path(__file__).resolve().parent / "axiom_llvm_runtime.c")
        with tempfile.NamedTemporaryFile(suffix=".ll", mode="w", delete=False) as tf:
            tf.write(llvm_ir)
            ll_temp_file = tf.name

        try:
            opt_level = f"-O{args.opt}" if hasattr(args, 'opt') and args.opt else "-O3"
            sanitizer_flags = get_sanitizer_flags(args)
            dbg_flags = ["-g"] if getattr(args, 'debug', False) else []
            target = getattr(args, 'target', None)
            sysroot = getattr(args, 'sysroot', None)
            llvm_cc, target_flags = get_target_compiler_flags(target, "clang", sysroot=sysroot)
            if target:
                ok, err_msg = validate_target_toolchain(target, llvm_cc, target_flags)
                if not ok:
                    print(f"{CLR_RED}{err_msg}{CLR_RESET}", file=sys.stderr)
                    sys.exit(1)
            compile_cmd = ([llvm_cc, opt_level] + get_thread_flag(target) + target_flags
                           + sanitizer_flags + dbg_flags
                           + [ll_temp_file, runtime_c]
                           + get_platform_link_flags(target) + ["-o", output_path])
            res = subprocess.run(compile_cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"{CLR_RED}LLVM Derleme Hatasi:{CLR_RESET}\n{res.stderr}", file=sys.stderr)
                sys.exit(res.returncode)

            print(f"{CLR_GREEN}✓ Başarılı (LLVM IR Backend):{CLR_RESET} Bağımsız yerel ikili dosya üretildi -> {CLR_BOLD}{output_path}{CLR_RESET}")
            return
        finally:
            if os.path.exists(ll_temp_file):
                os.remove(ll_temp_file)

    is_debug = getattr(args, 'debug', False)
    target = getattr(args, 'target', None)
    sysroot = getattr(args, 'sysroot', None)

    try:
        source_code = input_file.read_text(encoding="utf-8")
        c_code = compile_axiom_source(source_code, str(input_file), debug=is_debug, features=features)
    except (LexerError, ParserError, SemanticError, ModuleError, ProofError, NotImplementedError) as e:
        print(f"{CLR_RED}{e}{CLR_RESET}", file=sys.stderr)
        sys.exit(1)

    cc = find_c_compiler()
    cc, target_flags = get_target_compiler_flags(target, cc, sysroot=sysroot)
    if target:
        ok, err_msg = validate_target_toolchain(target, cc, target_flags)
        if not ok:
            print(f"{CLR_RED}{err_msg}{CLR_RESET}", file=sys.stderr)
            sys.exit(1)

    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as tf:
        tf.write(c_code)
        c_temp_file = tf.name

    try:
        if is_debug:
            opt_level = "-O0"
            debug_flags = ["-g3", "-O0", "-fno-omit-frame-pointer"]
        else:
            opt_level = f"-O{args.opt}" if hasattr(args, 'opt') and args.opt else "-O3"
            debug_flags = []

        sanitizer_flags = get_sanitizer_flags(args)
        compile_cmd = ([cc, opt_level, "-Wall", "-Wextra"] + get_thread_flag(target)
                       + target_flags + debug_flags + sanitizer_flags + [c_temp_file]
                       + get_platform_link_flags(target) + ["-o", output_path])
        res = subprocess.run(compile_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"{CLR_RED}C Derleme Hatasi:{CLR_RESET}\n{res.stderr}", file=sys.stderr)
            sys.exit(res.returncode)

        print(f"{CLR_GREEN}✓ Başarılı:{CLR_RESET} Bağımsız yerel ikili dosya üretildi -> {CLR_BOLD}{output_path}{CLR_RESET}")
    finally:
        if os.path.exists(c_temp_file):
            os.remove(c_temp_file)

def cmd_run(args):
    input_file = Path(args.file)
    if not input_file.exists():
        print(f"{CLR_RED}Hata:{CLR_RESET} '{input_file}' dosyasi bulunamadi.", file=sys.stderr)
        sys.exit(1)

    is_debug = getattr(args, 'debug', False)
    features = getattr(args, 'features', None)
    try:
        source_code = input_file.read_text(encoding="utf-8")
        c_code = compile_axiom_source(source_code, str(input_file), debug=is_debug, features=features)
    except (LexerError, ParserError, SemanticError, ModuleError, ProofError, NotImplementedError) as e:
        print(f"{CLR_RED}{e}{CLR_RESET}", file=sys.stderr)
        sys.exit(1)

    cc = find_c_compiler()
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_f, \
         tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_f:
        c_path = c_f.name
        bin_path = bin_f.name
        c_f.write(c_code)

    try:
        sanitizer_flags = get_sanitizer_flags(args)
        if is_debug:
            opt_level = "-O0"
            debug_flags = ["-g3", "-O0", "-fno-omit-frame-pointer"]
        else:
            opt_level = "-O3"
            debug_flags = []
        compile_cmd = [cc, opt_level, "-pthread"] + debug_flags + sanitizer_flags + [c_path, "-lz", "-lssl", "-lcrypto", "-ldl", "-lm", "-o", bin_path]
        res = subprocess.run(compile_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"{CLR_RED}C Derleme Hatasi:{CLR_RESET}\n{res.stderr}", file=sys.stderr)
            sys.exit(res.returncode)

        # Execute binary directly
        run_res = subprocess.run([bin_path] + (args.extra_args or []))
        sys.exit(run_res.returncode)
    finally:
        if os.path.exists(c_path):
            os.remove(c_path)
        if os.path.exists(bin_path):
            os.remove(bin_path)

def cmd_check(args):
    input_file = Path(args.file)
    if not input_file.exists():
        print(f"{CLR_RED}Hata:{CLR_RESET} '{input_file}' dosyasi bulunamadi.", file=sys.stderr)
        sys.exit(1)

    features = getattr(args, 'features', None)
    try:
        source_code = input_file.read_text(encoding="utf-8")
        lexer = Lexer(source_code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        resolver = ModuleResolver(base_file_path=str(input_file), features=features)
        program = resolver.resolve(program)
        checker = TypeChecker()
        checker.check(program)
        if not getattr(args, 'no_prove', False):
            use_smt = getattr(args, 'smt', False) or getattr(args, 'all', False)
            use_symbolic = getattr(args, 'all', False) or not use_smt
            if use_symbolic:
                prover = SymbolicProver()
                summary = prover.verify_program(program)
                if summary.has_loops:
                    print(f"{CLR_YELLOW}⚠ Kısmi Doğrulama / Döngü Nedeniyle Kanıtlanamadı (Unknown):{CLR_RESET} '{input_file}'")
                    print(f"  • Döngü İçeren Fonksiyonlar    : {CLR_BOLD}{', '.join(summary.loop_functions)}{CLR_RESET}")
                    sys.exit(2)
            if use_smt:
                z3_prover = Z3Prover()
                summary = z3_prover.verify_program(program)
                if summary.has_loops:
                    print(f"{CLR_YELLOW}⚠ Kısmi Doğrulama / Döngü Nedeniyle Kanıtlanamadı (Unknown):{CLR_RESET} '{input_file}'")
                    print(f"  • Döngü İçeren Fonksiyonlar    : {CLR_BOLD}{', '.join(summary.loop_functions)}{CLR_RESET}")
                    sys.exit(2)
        mode = "SMT" if (getattr(args, 'smt', False) or getattr(args, 'all', False)) else "sembolik"
        print(f"{CLR_GREEN}✓ Doğrulama Başarılı ({mode}):{CLR_RESET} '{input_file}' sözdizimsel, tip ve sözleşme denetimlerinden geçti.")
    except (LexerError, ParserError, SemanticError, ModuleError, ProofError, NotImplementedError) as e:
        print(f"{CLR_RED}{e}{CLR_RESET}", file=sys.stderr)
        sys.exit(1)

def cmd_prove(args):
    input_file = Path(args.file)
    if not input_file.exists():
        print(f"{CLR_RED}Hata:{CLR_RESET} '{input_file}' dosyasi bulunamadi.", file=sys.stderr)
        sys.exit(1)

    features = getattr(args, 'features', None)
    try:
        source_code = input_file.read_text(encoding="utf-8")
        lexer = Lexer(source_code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        resolver = ModuleResolver(base_file_path=str(input_file), features=features)
        program = resolver.resolve(program)
        checker = TypeChecker()
        checker.check(program)

        if getattr(args, 'smt', False):
            z3_prover = Z3Prover()
            summary = z3_prover.verify_program(program)
            if summary.has_loops:
                print(f"{CLR_YELLOW}⚠ Kısmi Doğrulama / Döngü Nedeniyle Kanıtlanamadı (Unknown):{CLR_RESET} '{input_file}'")
                print(f"  • Uyarı                        : {CLR_YELLOW}Döngü (while/for) içeren fonksiyonlar için döngü invariantı olmaksızın kesin ispat yapılamaz.{CLR_RESET}")
                print(f"  • Döngü İçeren Fonksiyonlar    : {CLR_BOLD}{', '.join(summary.loop_functions)}{CLR_RESET}")
                print(f"  • Doğrulanan Fonksiyon Sayısı  : {CLR_BOLD}{summary.verified_functions}{CLR_RESET}")
                print(f"  • İspatlanan Sözleşme Sayısı   : {CLR_BOLD}{summary.verified_contracts}{CLR_RESET}")
                print(f"  • İspatlanan Teorem Sayısı     : {CLR_BOLD}{summary.proved_theorems}{CLR_RESET}")
                print(f"  • Z3 SMT Çözücü Durumu         : {CLR_YELLOW}UNKNOWN (Döngü Invariantı Eksik){CLR_RESET}")
                print(f"  • İspat Güvencesi              : {CLR_YELLOW}Kısmi Doğrulama / Döngü Nedeniyle Kanıtlanamadı (Unknown){CLR_RESET}")
                sys.exit(2)
            else:
                print(f"{CLR_GREEN}✓ Statik Matematiksel İspat Başarılı (Z3 SMT Motoru):{CLR_RESET} '{input_file}'")
                print(f"  • Doğrulanan Fonksiyon Sayısı  : {CLR_BOLD}{summary.verified_functions}{CLR_RESET}")
                print(f"  • İspatlanan Sözleşme Sayısı   : {CLR_BOLD}{summary.verified_contracts}{CLR_RESET}")
                print(f"  • İspatlanan Teorem Sayısı     : {CLR_BOLD}{summary.proved_theorems}{CLR_RESET}")
                print(f"  • Z3 SMT Çözücü Durumu         : {CLR_BOLD}UNSAT (Tüm Karşıt-Örnekler Çürütüldü){CLR_RESET}")
                print(f"  • Güvenli Bölme İşlemi (Div/0) : {CLR_BOLD}{summary.safe_divisions}{CLR_RESET}")
                print(f"  • Sözleşme İhlali veya Hata    : {CLR_GREEN}YOK (0 Hata - Kesin İspat){CLR_RESET}")
        else:
            prover = SymbolicProver()
            summary = prover.verify_program(program)
            if summary.has_loops:
                print(f"{CLR_YELLOW}⚠ Kısmi Doğrulama / Döngü Nedeniyle Kanıtlanamadı (Unknown):{CLR_RESET} '{input_file}'")
                print(f"  • Uyarı                        : {CLR_YELLOW}Döngü (while/for) içeren fonksiyonlar için döngü invariantı olmaksızın kesin ispat yapılamaz.{CLR_RESET}")
                print(f"  • Döngü İçeren Fonksiyonlar    : {CLR_BOLD}{', '.join(summary.loop_functions)}{CLR_RESET}")
                print(f"  • Doğrulanan Fonksiyon Sayısı  : {CLR_BOLD}{summary.verified_functions}{CLR_RESET}")
                print(f"  • İspatlanan Sözleşme Sayısı   : {CLR_BOLD}{summary.verified_contracts}{CLR_RESET}")
                print(f"  • Güvenli Bölme İşlemi (Div/0) : {CLR_BOLD}{summary.safe_divisions}{CLR_RESET}")
                print(f"  • İspat Güvencesi              : {CLR_YELLOW}Kısmi Doğrulama / Döngü Nedeniyle Kanıtlanamadı (Unknown){CLR_RESET}")
                sys.exit(2)
            else:
                print(f"{CLR_GREEN}✓ Statik Matematiksel İspat Başarılı:{CLR_RESET} '{input_file}'")
                print(f"  • Doğrulanan Fonksiyon Sayısı  : {CLR_BOLD}{summary.verified_functions}{CLR_RESET}")
                print(f"  • İspatlanan Sözleşme Sayısı   : {CLR_BOLD}{summary.verified_contracts}{CLR_RESET}")
                print(f"  • Güvenli Bölme İşlemi (Div/0) : {CLR_BOLD}{summary.safe_divisions}{CLR_RESET}")
                print(f"  • Sözleşme İhlali veya Hata    : {CLR_GREEN}YOK (0 Hata - Kesin İspat){CLR_RESET}")
    except (LexerError, ParserError, SemanticError, ModuleError, ProofError, NotImplementedError) as e:
        print(f"{CLR_RED}{e}{CLR_RESET}", file=sys.stderr)
        sys.exit(1)

def cmd_emit_smt(args):
    input_file = Path(args.file)
    if not input_file.exists():
        print(f"{CLR_RED}Hata:{CLR_RESET} '{input_file}' dosyasi bulunamadi.", file=sys.stderr)
        sys.exit(1)

    features = getattr(args, 'features', None)
    try:
        source_code = input_file.read_text(encoding="utf-8")
        lexer = Lexer(source_code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        resolver = ModuleResolver(base_file_path=str(input_file), features=features)
        program = resolver.resolve(program)
        checker = TypeChecker()
        checker.check(program)

        prover = Z3Prover()
        smt_code = prover.emit_smt2(program)
        if args.output:
            Path(args.output).write_text(smt_code, encoding="utf-8")
            print(f"{CLR_GREEN}✓ SMT-LIB2 Kodu Yazıldı:{CLR_RESET} -> {args.output}")
        else:
            print(smt_code)
    except (LexerError, ParserError, SemanticError, ModuleError, ProofError, NotImplementedError) as e:
        print(f"{CLR_RED}{e}{CLR_RESET}", file=sys.stderr)
        sys.exit(1)

def cmd_emit_llvm(args):
    input_file = Path(args.file)
    if not input_file.exists():
        print(f"{CLR_RED}Hata:{CLR_RESET} '{input_file}' dosyasi bulunamadi.", file=sys.stderr)
        sys.exit(1)

    features = getattr(args, 'features', None)
    try:
        source_code = input_file.read_text(encoding="utf-8")
        lexer = Lexer(source_code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        resolver = ModuleResolver(base_file_path=str(input_file), features=features)
        program = resolver.resolve(program)
        checker = TypeChecker()
        checker.check(program)

        dbg_enabled = getattr(args, 'debug', False)
        codegen = LLVMCodeGenerator(
            debug=dbg_enabled,
            source_file=input_file.name,
            source_dir=str(input_file.parent.resolve())
        )
        llvm_ir = codegen.generate(program)
        if args.output:
            Path(args.output).write_text(llvm_ir, encoding="utf-8")
            print(f"{CLR_GREEN}✓ LLVM IR Kodu Yazıldı:{CLR_RESET} -> {args.output}")
        else:
            print(llvm_ir)
    except (LexerError, ParserError, SemanticError, ModuleError, ProofError) as e:
        print(f"{CLR_RED}{e}{CLR_RESET}", file=sys.stderr)
        sys.exit(1)

def cmd_emit_c(args):
    input_file = Path(args.file)
    if not input_file.exists():
        print(f"{CLR_RED}Hata:{CLR_RESET} '{input_file}' dosyasi bulunamadi.", file=sys.stderr)
        sys.exit(1)

    features = getattr(args, 'features', None)
    try:
        source_code = input_file.read_text(encoding="utf-8")
        c_code = compile_axiom_source(source_code, str(input_file), features=features)
        if args.output:
            Path(args.output).write_text(c_code, encoding="utf-8")
            print(f"{CLR_GREEN}✓ C Kodu Yazıldı:{CLR_RESET} -> {args.output}")
        else:
            print(c_code)
    except (LexerError, ParserError, SemanticError, ModuleError, ProofError) as e:
        print(f"{CLR_RED}{e}{CLR_RESET}", file=sys.stderr)
        sys.exit(1)

def cmd_test(args):
    axiom_root = Path(__file__).resolve().parent.parent
    tests_dir = axiom_root / "tests"
    test_env = os.environ.copy()
    if getattr(args, 'asan', False):
        test_env["AXIOM_ASAN"] = "1"

    pytest_args = list(args.pytest_args or [])
    has_target = any(not a.startswith("-") for a in pytest_args)
    cmd = [sys.executable, "-m", "pytest"]
    if not has_target:
        cmd.append(str(tests_dir))
    cmd.extend(pytest_args)
    res = subprocess.run(cmd, cwd=str(axiom_root), env=test_env)
    sys.exit(res.returncode)

def cmd_init(args):
    project_name = args.project_name
    proj_dir = Path(project_name).resolve()
    if proj_dir.exists() and any(proj_dir.iterdir()):
        print(f"{CLR_RED}Hata:{CLR_RESET} '{project_name}' dizini zaten mevcut ve boş değil.", file=sys.stderr)
        sys.exit(1)

    proj_dir.mkdir(parents=True, exist_ok=True)
    src_dir = proj_dir / "src"
    src_dir.mkdir(exist_ok=True)

    # 1. axiom.toml
    toml_content = f"""[project]
name = "{project_name}"
version = "0.1.0"
description = "Axiom (λx) High-Performance Systems Project"
author = "Axiom Developer"

[build]
opt = 3
entry = "src/main.ax"
"""
    (proj_dir / "axiom.toml").write_text(toml_content, encoding="utf-8")

    # 2. src/main.ax
    main_ax_content = f"""// Axiom (λx) - {project_name} Main Entry Point

fn main() -> void {{
    let msg = "Hello from Axiom project '{project_name}'!"
    print(msg)
}}
"""
    (src_dir / "main.ax").write_text(main_ax_content, encoding="utf-8")

    # 3. README.md
    readme_content = f"""# {project_name}

An Axiom (λx) high-performance systems project.

## Çalıştırma (Run)
```bash
axiom run src/main.ax
```

## Derleme (Build)
```bash
axiom build src/main.ax -o {project_name}
./{project_name}
```

## Sözleşme ve Tip Denetimi (Check)
```bash
axiom check src/main.ax
```

## Kod Biçimlendirme (Fmt)
```bash
axiom fmt src/main.ax
```
"""
    (proj_dir / "README.md").write_text(readme_content, encoding="utf-8")

    # 4. .gitignore
    gitignore_content = f"""# Axiom derleme çıktıları
*.c
*.o
{project_name}
build/
dist/
.pytest_cache/
"""
    (proj_dir / ".gitignore").write_text(gitignore_content, encoding="utf-8")

    print(f"{CLR_GREEN}✓ Başarılı:{CLR_RESET} Yeni Axiom projesi '{CLR_BOLD}{project_name}{CLR_RESET}' oluşturuldu.")
    print("  Dosyalar:")
    print("    - axiom.toml")
    print("    - src/main.ax")
    print("    - README.md")
    print("    - .gitignore")
    print(f"\nBaşlamak için:")
    print(f"  cd {project_name}")
    print(f"  axiom run src/main.ax")

def cmd_doc(args):
    from axiom import docgen

    targets = args.paths or ["."]
    for t in targets:
        if not Path(t).exists():
            print(f"{CLR_RED}Hata:{CLR_RESET} '{t}' bulunamadi.", file=sys.stderr)
            sys.exit(1)

    modules = docgen.collect(targets)

    if args.json:
        text = docgen.render_json(modules)
        if args.output and args.output != "-":
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            print(f"{CLR_GREEN}✓{CLR_RESET} JSON yazildi: {out}")
        else:
            print(text)
        return

    out_dir = Path(args.output or "docs/api")
    out_dir.mkdir(parents=True, exist_ok=True)
    index = out_dir / "index.html"
    index.write_text(docgen.render_html(modules, title=args.title), encoding="utf-8")

    fn_count = sum(1 for m in modules for i in m.items if i.kind == "fn")
    struct_count = sum(1 for m in modules for i in m.items if i.kind == "struct")
    documented = sum(1 for m in modules for i in m.items if i.doc)
    skipped = sum(1 for m in modules if not m.items)

    print(f"{CLR_GREEN}✓{CLR_RESET} API dokumani: {index}")
    print(f"  {len(modules)} dosya, {fn_count} fn, {struct_count} struct, "
          f"{documented} belgeli")
    if skipped:
        print(f"  {CLR_YELLOW}!{CLR_RESET} {skipped} dosya atlandi (bos veya ayristirilamadi)")


def cmd_fmt(args):
    input_file = Path(args.file)
    if not input_file.exists():
        print(f"{CLR_RED}Hata:{CLR_RESET} '{input_file}' dosyasi bulunamadi.", file=sys.stderr)
        sys.exit(1)

    try:
        source_code = input_file.read_text(encoding="utf-8")
        formatted = format_source(source_code)
    except Exception as e:
        print(f"{CLR_RED}Formatlama Hatasi:{CLR_RESET} {e}", file=sys.stderr)
        sys.exit(1)

    if getattr(args, 'check', False):
        if source_code != formatted:
            print(f"{CLR_YELLOW}! Biçimlendirme gerekli:{CLR_RESET} '{input_file}' standart formatta değil.", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"{CLR_GREEN}✓ Doğrulandı:{CLR_RESET} '{input_file}' standart formatta.")
            return

    if source_code != formatted:
        input_file.write_text(formatted, encoding="utf-8")
        print(f"{CLR_GREEN}✓ Formatlandı:{CLR_RESET} '{input_file}'")
    else:
        print(f"{CLR_CYAN}- Zaten formatlı:{CLR_RESET} '{input_file}'")

def cmd_pkg(args):
    from axiom.package_manager import main as pkg_main
    raw_args = getattr(args, "pkg_args", [])
    if not raw_args:
        raw_args = ["--help"]
    pkg_main(raw_args)

def cmd_lsp(args):
    from axiom.lsp import main as lsp_main
    lsp_main()

class REPLSession:
    def __init__(self):
        self.declarations: List[str] = []
        self.statements: List[str] = []
        self.runtime_path = get_runtime_header_path()
        self.cc = find_c_compiler()

    def run_source(self, extra_stmts: List[str]) -> tuple[bool, str, str]:
        full_code = []
        for d in self.declarations:
            full_code.append(d)
        for s in self.statements:
            full_code.append(s)
        for s in extra_stmts:
            full_code.append(s)
        source = "\n".join(full_code)

        try:
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            resolver = ModuleResolver("<repl>")
            program = resolver.resolve(program)
            checker = TypeChecker()
            checker.check(program)
            codegen = CCodeGenerator(runtime_header_path=self.runtime_path)
            c_code = codegen.generate(program)
        except (LexerError, ParserError, SemanticError, ModuleError) as e:
            return False, "", str(e)

        with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as c_f, \
             tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as bin_f:
            c_path = c_f.name
            bin_path = bin_f.name
            c_f.write(c_code)

        try:
            compile_cmd = [self.cc, "-O0", "-pthread", c_path, "-lz", "-lssl", "-lcrypto", "-ldl", "-lm", "-o", bin_path]
            res = subprocess.run(compile_cmd, capture_output=True, text=True)
            if res.returncode != 0:
                return False, "", res.stderr

            run_res = subprocess.run([bin_path], capture_output=True, text=True, timeout=5)
            return True, run_res.stdout, run_res.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Zaman aşımı (Timeout: 5s)"
        except Exception as e:
            return False, "", str(e)
        finally:
            if os.path.exists(c_path):
                os.remove(c_path)
            if os.path.exists(bin_path):
                os.remove(bin_path)

    def evaluate(self, input_text: str) -> Optional[str]:
        stripped = input_text.strip()
        if not stripped:
            return None

        # Imports, structs, functions
        if stripped.startswith("import ") or stripped.startswith("struct ") or stripped.startswith("fn "):
            success, stdout, err = self.run_source([stripped])
            if not success:
                return f"{CLR_RED}Hata:{CLR_RESET} {err}"
            self.declarations.append(stripped)
            if stdout:
                return stdout.rstrip("\n")
            return None

        # Variable declarations
        if stripped.startswith("let "):
            success, stdout, err = self.run_source([stripped])
            if not success:
                return f"{CLR_RED}Hata:{CLR_RESET} {err}"
            self.statements.append(stripped)
            if stdout:
                return stdout.rstrip("\n")
            return None

        # Try evaluating as an expression wrapped in print(...)
        expr_cmd = f"print({stripped})"
        success, stdout, err = self.run_source([expr_cmd])
        if success:
            return stdout.rstrip("\n")

        # Try evaluating as a normal statement
        success, stdout, err = self.run_source([stripped])
        if success:
            if "=" in stripped and not any(op in stripped for op in ["==", "!=", "<=", ">="]):
                self.statements.append(stripped)
            if stdout:
                return stdout.rstrip("\n")
            return None
        else:
            return f"{CLR_RED}Hata:{CLR_RESET} {err}"

def cmd_repl(args):
    try:
        import readline
    except ImportError:
        pass

    session = REPLSession()
    print(f"{CLR_BOLD}Axiom (λx) v0.5.0-alpha - İnteraktif REPL{CLR_RESET}")
    print("Yardım için 'help', çıkış için 'exit' veya 'quit' yazın.\n")

    buffer: List[str] = []
    brace_depth = 0

    while True:
        prompt = "... " if brace_depth > 0 else "axiom> "
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\nÇıkılıyor...")
            break

        stripped = line.strip()
        if not buffer and stripped in ("exit", "quit"):
            print("Görüşmek üzere!")
            break

        if not buffer and stripped == "help":
            print(f"{CLR_CYAN}Axiom REPL Komutları:{CLR_RESET}")
            print("  exit / quit : REPL'den çıkar")
            print("  clear       : Oturum değişkenlerini ve tanımlarını sıfırlar")
            print("  help        : Bu yardım mesajını gösterir")
            print("  Örnekler:")
            print("    let x = 10")
            print("    x * 2 + 5")
            print("    file_write(\"test.txt\", \"Axiom REPL\")")
            print("    file_read(\"test.txt\")")
            continue

        if not buffer and stripped == "clear":
            session.declarations.clear()
            session.statements.clear()
            print(f"{CLR_GREEN}✓ Oturum geçmişi temizlendi.{CLR_RESET}")
            continue

        in_string = False
        escape = False
        for ch in line:
            if ch == '\\' and in_string:
                escape = not escape
                continue
            if ch == '"' and not escape:
                in_string = not in_string
            elif not in_string:
                if ch == '{':
                    brace_depth += 1
                elif ch == '}':
                    if brace_depth > 0:
                        brace_depth -= 1
            escape = False

        buffer.append(line)

        if brace_depth == 0:
            full_input = "\n".join(buffer)
            buffer.clear()
            out = session.evaluate(full_input)
            if out is not None:
                print(out)

def main():
    parser = argparse.ArgumentParser(
        prog="axiom",
        description=f"{CLR_BOLD}Axiom (λx){CLR_RESET} - Python Ergonomisi, C Hızı ve Rust Doğrulanabilirliği Sunan Sistem Dili"
    )
    parser.add_argument("-v", "--version", action="version", version="Axiom (λx) v0.5.0-alpha")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # run
    p_run = subparsers.add_parser("run", help="Axiom kaynak kodunu derle ve yerel olarak calistir")
    p_run.add_argument("file", help="Calistirilacak .ax dosyasi")
    p_run.add_argument("-g", "--debug", action="store_true", help="DWARF hata ayıklama sembolleri ile çalıştır")
    p_run.add_argument("--asan", action="store_true", help="AddressSanitizer (ASan) bellek korumasini etkinlestir")
    p_run.add_argument("--ubsan", action="store_true", help="UndefinedBehaviorSanitizer (UBSan) denetimini etkinlestir")
    p_run.add_argument("--features", help="Etkinleştirilecek özellikler (örn. 'offensive')")
    p_run.add_argument("extra_args", nargs="*", help="Program argumanlari")
    p_run.set_defaults(func=cmd_run)

    # build
    p_build = subparsers.add_parser("build", help="Axiom kodundan tek basina calisan yerel ikili dosya (ELF) derle")
    p_build.add_argument("file", help="Derlenecek .ax dosyasi")
    p_build.add_argument("-o", "--output", help="Cikti ikili dosya adi")
    p_build.add_argument("-O", "--opt", default="3", help="Optimizasyon seviyesi (0, 1, 2, 3)")
    p_build.add_argument("-g", "--debug", action="store_true", help="DWARF hata ayıklama sembolleri ile derle")
    p_build.add_argument("--target", help="Çapraz derleme hedefi: windows, x86_64-linux-gnu, aarch64-linux-gnu, wasm32-wasi")
    p_build.add_argument("--sysroot", help="Çapraz derleme için hedef sysroot dizini (örn. WASI SDK sysroot)")
    p_build.add_argument("--backend", choices=["c", "llvm"], default="c", help="Derleme arka ucu ('c' veya 'llvm')")
    p_build.add_argument("--asan", action="store_true", help="AddressSanitizer (ASan) bellek korumasini etkinlestir")
    p_build.add_argument("--ubsan", action="store_true", help="UndefinedBehaviorSanitizer (UBSan) denetimini etkinlestir")
    p_build.add_argument("--features", help="Etkinleştirilecek özellikler (örn. 'offensive')")
    p_build.set_defaults(func=cmd_build)

    # check
    p_check = subparsers.add_parser("check", help="Sözdizim, tip ve guvenlik sozlesmelerini dogrula")
    p_check.add_argument("file", help="Denetlenecek .ax dosyasi")
    p_check.add_argument("--no-prove", action="store_true", help="Biçimsel sözleşme (contract/prover) doğrulamasını atla")
    p_check.add_argument("--smt", action="store_true", help="Z3 SMT teorem ispat motorunu kullan")
    p_check.add_argument("--all", action="store_true", help="Sembolik ve Z3 SMT motorlarının ikisini de çalıştır")
    p_check.add_argument("--features", help="Etkinleştirilecek özellikler (örn. 'offensive')")
    p_check.set_defaults(func=cmd_check)

    # prove
    p_prove = subparsers.add_parser("prove", help="Statik matematiksel ispat ve sembolik sozlesme dogrulayici")
    p_prove.add_argument("file", help="Ispatlanacak .ax dosyasi")
    p_prove.add_argument("--smt", action="store_true", help="Z3 SMT teorem ispat motoru ile kanitla")
    p_prove.add_argument("--features", help="Etkinleştirilecek özellikler (örn. 'offensive')")
    p_prove.set_defaults(func=cmd_prove)

    # emit-c
    p_emit = subparsers.add_parser("emit-c", help="Uretilen optimize C99 kodunu incele")
    p_emit.add_argument("file", help="Incelenecek .ax dosyasi")
    p_emit.add_argument("-o", "--output", help="Kaydedilecek .c dosyasi")
    p_emit.add_argument("--features", help="Etkinleştirilecek özellikler (örn. 'offensive')")
    p_emit.set_defaults(func=cmd_emit_c)

    # emit-smt
    p_emit_smt = subparsers.add_parser("emit-smt", help="Standart SMT-LIB2 formatinda teorem ispat kodunu uret")
    p_emit_smt.add_argument("file", help="Incelenecek .ax dosyasi")
    p_emit_smt.add_argument("-o", "--output", help="Kaydedilecek .smt2 dosyasi")
    p_emit_smt.add_argument("--features", help="Etkinleştirilecek özellikler (örn. 'offensive')")
    p_emit_smt.set_defaults(func=cmd_emit_smt)

    # emit-llvm
    p_emit_llvm = subparsers.add_parser("emit-llvm", help="Uretilen LLVM IR (.ll) kodunu incele")
    p_emit_llvm.add_argument("file", help="Incelenecek .ax dosyasi")
    p_emit_llvm.add_argument("-o", "--output", help="Kaydedilecek .ll dosyasi")
    p_emit_llvm.add_argument("-g", "--debug", action="store_true", help="DWARF hata ayıklama sembolleri üret")
    p_emit_llvm.add_argument("--features", help="Etkinleştirilecek özellikler (örn. 'offensive')")
    p_emit_llvm.set_defaults(func=cmd_emit_llvm)

    # repl
    p_repl = subparsers.add_parser("repl", help="Etkilesimli Axiom kabugunu (REPL) baslat")
    p_repl.add_argument("--features", help="Etkinleştirilecek özellikler (örn. 'offensive')")
    p_repl.set_defaults(func=cmd_repl)

    # test
    p_test = subparsers.add_parser("test", help="Axiom test paketini (pytest) calistir")
    p_test.add_argument("--asan", action="store_true", help="AddressSanitizer aktif halde testleri calistir")
    p_test.add_argument("pytest_args", nargs=argparse.REMAINDER, help="pytest icin opsiyonel ek argumanlar")
    p_test.set_defaults(func=cmd_test)

    # init
    p_init = subparsers.add_parser("init", help="Yeni bir Axiom projesi iskeleti olusturur")
    p_init.add_argument("project_name", help="Olusturulacak projenin adi")
    p_init.set_defaults(func=cmd_init)

    # doc
    p_doc = subparsers.add_parser("doc", help="`///` doc comment'lerinden statik HTML/JSON API dokumani uret")
    p_doc.add_argument("paths", nargs="*", help="Dosya veya dizin (varsayilan: .)")
    p_doc.add_argument("-o", "--output", help="Cikti dizini (HTML icin, varsayilan docs/api) veya JSON dosyasi")
    p_doc.add_argument("--json", action="store_true", help="HTML yerine JSON uret ('-' = stdout)")
    p_doc.add_argument("--title", default="Axiom API", help="HTML sayfa basligi")
    p_doc.set_defaults(func=cmd_doc)

    # fmt
    p_fmt = subparsers.add_parser("fmt", help="Kaynak kodunu standart Axiom formatina gore bicimlendirir")
    p_fmt.add_argument("file", help="Bicimlendirilecek .ax dosyasi")
    p_fmt.add_argument("--check", action="store_true", help="Dosyayi degistirmeden formati kontrol eder")
    p_fmt.set_defaults(func=cmd_fmt)

    # pkg
    p_pkg = subparsers.add_parser("pkg", help="Axiom Paket Yöneticisi (axpm)")
    p_pkg.add_argument("pkg_args", nargs=argparse.REMAINDER, help="Paket yöneticisi argümanları (init, add, install, build, run, test)")
    p_pkg.set_defaults(func=cmd_pkg)

    # lsp
    p_lsp = subparsers.add_parser("lsp", help="Axiom Dil Sunucusunu (Language Server) başlatır")
    p_lsp.set_defaults(func=cmd_lsp)

    args, unknown = parser.parse_known_args()
    if getattr(args, "subcommand", None) == "pkg":
        if "pkg" in sys.argv:
            p_idx = sys.argv.index("pkg")
            args.pkg_args = list(sys.argv[p_idx + 1:])
    elif getattr(args, "subcommand", None) == "test":
        if "test" in sys.argv:
            t_idx = sys.argv.index("test")
            raw_args = list(sys.argv[t_idx + 1:])
            if "--asan" in raw_args:
                args.asan = True
                raw_args.remove("--asan")
            args.pytest_args = raw_args
        else:
            args.pytest_args = (getattr(args, "pytest_args", []) or []) + unknown
            if "--asan" in args.pytest_args:
                args.asan = True
                args.pytest_args.remove("--asan")
    elif unknown:
        parser.error(f"Tanimlanmayan argumanlar: {' '.join(unknown)}")
    args.func(args)

if __name__ == "__main__":
    main()
