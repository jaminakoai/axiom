# Axiom (λx) — Geliştirici Makefile
#
# Kullanım:
#   make test        Tüm test paketini çalıştır
#   make test-fast   Yalnızca hızlı birim testleri
#   make bootstrap   bin/axiomc'yi Axiom kaynağından yeniden derle
#   make ci          tools/ci_matrix.sh
#   make bench       Benchmark paketini çalıştır
#   make fmt         compiler/*.ax dosyalarını biçimlendir (yerinde)
#   make fmt-check   Biçimlendirmeyi değiştirmeden denetle
#   make clean       Üretilmiş dosyaları temizle

PY ?= python3
AXIOM := $(CURDIR)/bin/axiom
AXPMC := $(CURDIR)/bin/axiomc

.PHONY: all test test-fast bootstrap ci bench fmt fmt-check clean install-dev help

all: help

help:
	@echo "Hedefler: test test-fast bootstrap ci bench fmt fmt-check clean install-dev"

test:
	$(PY) -m pytest -q

test-fast:
	$(PY) -m pytest -q -x \
		tests/test_lexer.py tests/test_parser.py tests/test_checker.py \
		tests/test_stdlib.py tests/test_io.py tests/test_modules.py \
		tests/test_cli_tools.py tests/test_remaining_fixes.py

bootstrap:
	$(AXIOM) build compiler/main.ax -o bin/axiomc
	@./bin/axiomc --version

ci:
	bash tools/ci_matrix.sh

bench:
	$(PY) benchmarks/run_benchmarks.py

fmt:
	@for f in compiler/*.ax; do $(AXIOM) fmt "$$f" > /dev/null; done

fmt-check:
	@for f in compiler/*.ax; do $(AXIOM) fmt --check "$$f" || exit 1; done
	@echo "✓ Biçimlendirme geçerli"

clean:
	rm -rf .pytest_cache __pycache__ */__pycache__ */*/__pycache__
	rm -f *.ll *.smt2 a.out
	find . -maxdepth 1 -name 'tmp*' -type f -delete
	@echo "✓ Temizlendi"

install-dev:
	$(PY) -m pip install -e ".[dev]"
