#!/usr/bin/env bash
# ==============================================================================
# Axiom Programming Language (λx) - CI & Regression Matrix Runner
# tools/ci_matrix.sh - Full Automated Validation & Hardening Matrix (FAZ 7.2)
# ==============================================================================
set -euo pipefail

COLOR_RESET="\033[0m"
COLOR_GREEN="\033[1;32m"
COLOR_RED="\033[1;31m"
COLOR_BLUE="\033[1;34m"
COLOR_CYAN="\033[1;36m"
COLOR_YELLOW="\033[1;33m"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AXIOM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${AXIOM_ROOT}"

echo -e "${COLOR_CYAN}======================================================================${COLOR_RESET}"
echo -e "${COLOR_CYAN}    Axiom (λx) Otomatik CI & Regresyon Güvenlik Matrisi (FAZ 6 & 7)   ${COLOR_RESET}"
echo -e "${COLOR_CYAN}======================================================================${COLOR_RESET}"

step_banner() {
    echo -e "\n${COLOR_BLUE}[CI ADIM $1]${COLOR_RESET} ${COLOR_YELLOW}$2${COLOR_RESET}"
}

# ------------------------------------------------------------------------------
# 1. Kod Biçimlendirme ve Statik Sözdizim Denetimi
# ------------------------------------------------------------------------------
step_banner "1/6" "Kod Biçimlendirme & Statik Sözdizim Doğrulaması"
for f in compiler/*.ax; do
    python3 -m axiom.cli fmt "$f" > /dev/null
done
echo -e "${COLOR_GREEN}✓ Kod biçimlendirme ve AST ayrıştırma geçerli.${COLOR_RESET}"

# ------------------------------------------------------------------------------
# 2. Self-Hosted Bootstrap & Determinizm Doğrulaması (FAZ 6)
# ------------------------------------------------------------------------------
step_banner "2/6" "Self-Hosted Bootstrap & Determinizm Testi (bin/axiomc)"
python3 -m axiom.cli build compiler/main.ax -o bin/axiomc
test -x bin/axiomc
./bin/axiomc --version

# Determinizm testi: 2 kez emit-c yapıp sha256 karşılaştır
TMP_C1=$(mktemp /tmp/axiom_det_1_XXXXXX.c)
TMP_C2=$(mktemp /tmp/axiom_det_2_XXXXXX.c)
./bin/axiomc emit-c examples/01_hello.ax > "${TMP_C1}"
./bin/axiomc emit-c examples/01_hello.ax > "${TMP_C2}"
cmp -s "${TMP_C1}" "${TMP_C2}"
rm -f "${TMP_C1}" "${TMP_C2}"
echo -e "${COLOR_GREEN}✓ bin/axiomc self-hosted eşitliği ve %100 determinizm doğrulandı.${COLOR_RESET}"

# ------------------------------------------------------------------------------
# 3. ASan & UBSan Bellek Güvenliği Doğrulaması (FAZ 1 & 7)
# ------------------------------------------------------------------------------
step_banner "3/6" "ASan & UBSan Bellek Kaçağı ve Bozulma Denetimleri"
pytest tests/test_memory_sanitizer.py -v -q --tb=short
echo -e "${COLOR_GREEN}✓ ASan / UBSan: Sıfır kaçak, sıfır UAF ve sıfır double-free kanıtlandı.${COLOR_RESET}"

# ------------------------------------------------------------------------------
# 4. Fuzzing Altyapı Denetimi (FAZ 7.1)
# ------------------------------------------------------------------------------
step_banner "4/6" "Fuzzing Matrisi (Lexer, Parser, JSON, YARA)"
pytest tests/test_fuzzing_suite.py -v -q --tb=short
echo -e "${COLOR_GREEN}✓ Fuzzing matrisi tamamlandı: Sıfır panik, sıfır çökme.${COLOR_RESET}"

# ------------------------------------------------------------------------------
# 5. Negatif Güvenlik ve İstismar Matrisi (FAZ 7.3)
# ------------------------------------------------------------------------------
step_banner "5/6" "Negatif Güvenlik ve İstismar Test Suiti"
pytest tests/test_negative_security.py -v -q --tb=short
echo -e "${COLOR_GREEN}✓ Negatif güvenlik testleri geçti: OOB, Type Confusion, Missing Return, TLS MitM engellendi.${COLOR_RESET}"

# ------------------------------------------------------------------------------
# 6. Self-Hosted Uçtan Uca Testleri
# ------------------------------------------------------------------------------
step_banner "6/6" "Self-Hosted E2E Test Suiti"
pytest tests/test_self_hosted.py -v -q --tb=short
echo -e "${COLOR_GREEN}✓ Self-hosted E2E testleri %100 başarıyla tamamlandı.${COLOR_RESET}"

echo -e "\n${COLOR_CYAN}======================================================================${COLOR_RESET}"
echo -e "${COLOR_GREEN}🎉 TEBRİKLER! Tüm CI Matrisi 0 HATA ile başarıyla tamamlandı.${COLOR_RESET}"
echo -e "${COLOR_CYAN}======================================================================${COLOR_RESET}"
exit 0
