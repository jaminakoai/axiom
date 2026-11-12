#!/usr/bin/env python3
"""
Axiom Unicode tablosu üreteci.

Python'un `unicodedata` modülü (Unicode Character Database) otoritatif kaynaktır.
Bu script ondan **kanonik** (compatibility olmayan) ayrıştırma, birleştirici
sınıf (ccc) ve kanonik birleştirme tablolarını üretir.

Hangul (U+AC00..U+D7A3) tabloya yazılmaz; algoritmik olarak işlenir
(Unicode Standard §3.12).

Kullanım:
    python3 tools/gen_unicode_tables.py > axiom/unicode_tables.h

SÜRÜM SABİTLEMESİ
------------------
Tablo sürümü Python yorumlayıcısının `unicodedata` sürümüne bağlıdır. Farklı
Python sürümleri farklı UCD sürümü getirdiği için (3.10/3.11 = 14.0.0,
3.12/3.13 = 15.1.0) "hangi makinede üretildi" tabloyu sessizce değiştirirdi.
Bu yüzden sürüm burada **sabitlenmiştir**; uyuşmazlıkta üretici durur.
Bilinçli olarak farklı sürüm üretmek için: `ALLOW_UCD_MISMATCH=1`.
"""
import os
import sys
import unicodedata as u

# Tek doğruluk kaynağı: tablo sürümü. Testler de bunu okur.
PINNED_UCD_VERSION = "15.1.0"

S_BASE, L_BASE, V_BASE, T_BASE = 0xAC00, 0x1100, 0x1161, 0x11A7
L_COUNT, V_COUNT, T_COUNT = 19, 21, 28
N_COUNT = V_COUNT * T_COUNT
S_COUNT = L_COUNT * N_COUNT


def is_hangul_syllable(cp: int) -> bool:
    return S_BASE <= cp < S_BASE + S_COUNT


def check_ucd_version() -> None:
    """Yorumlayıcının UCD sürümü sabitlenen sürümle aynı mı?"""
    actual = u.unidata_version
    if actual == PINNED_UCD_VERSION:
        return
    msg = (
        "HATA: unicodedata sürümü uyuşmuyor.\n"
        f"  sabitlenen : {PINNED_UCD_VERSION}\n"
        f"  yorumlayıcı: {actual} (Python {sys.version.split()[0]})\n"
        "Tablo sessizce farklı UCD sürümünden üretilmesin diye durduruldu.\n"
        "Bilinçli farklı sürüm için ALLOW_UCD_MISMATCH=1 verin."
    )
    if os.environ.get("ALLOW_UCD_MISMATCH") == "1":
        print("UYARI: " + msg.replace("\n", " | "), file=sys.stderr)
        return
    raise SystemExit(msg)


def main() -> None:
    check_ucd_version()
    decomp = []   # (cp, a, b) — b == 0 ise tek parça
    ccc = []      # (cp, class)
    comp = []     # (a, b, cp)

    # 1. Kanonik ayrıştırmalar (Hangul hariç)
    for cp in range(0x110000):
        if is_hangul_syllable(cp):
            continue
        d = u.decomposition(chr(cp))
        if not d or d.startswith('<'):
            continue
        parts = [int(x, 16) for x in d.split()]
        if len(parts) == 1:
            decomp.append((cp, parts[0], 0))
        elif len(parts) == 2:
            decomp.append((cp, parts[0], parts[1]))
        else:
            raise SystemExit(f"Beklenmeyen ayrıştırma uzunluğu: {cp:04X} {parts}")

    # 2. Birleştirici sınıflar
    for cp in range(0x110000):
        c = u.combining(chr(cp))
        if c:
            ccc.append((cp, c))

    # 3. Kanonik birleştirme çiftleri
    #    NFC(a+b) == cp olan (a,b) çiftleri; tek adımlı ayrıştırmadan türetilir.
    #    Unicode'un "Full_Composition_Exclusion" kümesi otomatik dışarıda kalır,
    #    çünkü o karakterler tek başına ayrışmaz.
    excluded = set()
    for cp in range(0x110000):
        if u.normalize("NFC", u.normalize("NFD", chr(cp))) != chr(cp):
            excluded.add(cp)

    for cp, a, b in decomp:
        if b == 0:
            continue
        if cp in excluded:
            continue
        # Yalnızca gerçekten NFC ile geri dönen çiftleri al
        if u.normalize("NFC", chr(a) + chr(b)) == chr(cp):
            comp.append((a, b, cp))

    comp.sort()

    out = sys.stdout
    out.write("/*\n")
    out.write(" * Axiom Unicode tabloları — OTOMATİK ÜRETİLDİ, ELLE DÜZENLEMEYİN.\n")
    out.write(" * Kaynak: Python unicodedata %s (Unicode Character Database)\n" % u.unidata_version)
    out.write(" * Üretici: tools/gen_unicode_tables.py\n")
    out.write(" *\n")
    out.write(" * Kapsam: kanonik ayrıştırma (compatibility hariç), birleştirici\n")
    out.write(" * sınıflar ve kanonik birleştirme çiftleri. Hangul algoritmiktir.\n")
    out.write(" */\n\n")
    out.write("#ifndef AXIOM_UNICODE_TABLES_H\n#define AXIOM_UNICODE_TABLES_H\n\n")
    out.write('#define AXIOM_UCD_VERSION "%s"\n\n' % u.unidata_version)

    out.write("typedef struct { uint32_t cp; uint32_t a; uint32_t b; } axiom_ucd_decomp_t;\n")
    out.write("typedef struct { uint32_t cp; uint8_t ccc; } axiom_ucd_ccc_t;\n")
    out.write("typedef struct { uint32_t a; uint32_t b; uint32_t cp; } axiom_ucd_comp_t;\n\n")

    out.write("static const axiom_ucd_decomp_t axiom_ucd_decomp[] = {\n")
    for cp, a, b in decomp:
        out.write("  {0x%04X,0x%04X,0x%04X},\n" % (cp, a, b))
    out.write("};\n")
    out.write("#define AXIOM_UCD_DECOMP_COUNT %d\n\n" % len(decomp))

    out.write("static const axiom_ucd_ccc_t axiom_ucd_ccc[] = {\n")
    for cp, c in ccc:
        out.write("  {0x%04X,%d},\n" % (cp, c))
    out.write("};\n")
    out.write("#define AXIOM_UCD_CCC_COUNT %d\n\n" % len(ccc))

    out.write("static const axiom_ucd_comp_t axiom_ucd_comp[] = {\n")
    for a, b, cp in comp:
        out.write("  {0x%04X,0x%04X,0x%04X},\n" % (a, b, cp))
    out.write("};\n")
    out.write("#define AXIOM_UCD_COMP_COUNT %d\n\n" % len(comp))

    out.write("#define AXIOM_UCD_HANGUL_S_BASE 0x%04X\n" % S_BASE)
    out.write("#define AXIOM_UCD_HANGUL_L_BASE 0x%04X\n" % L_BASE)
    out.write("#define AXIOM_UCD_HANGUL_V_BASE 0x%04X\n" % V_BASE)
    out.write("#define AXIOM_UCD_HANGUL_T_BASE 0x%04X\n" % T_BASE)
    out.write("#define AXIOM_UCD_HANGUL_L_COUNT %d\n" % L_COUNT)
    out.write("#define AXIOM_UCD_HANGUL_V_COUNT %d\n" % V_COUNT)
    out.write("#define AXIOM_UCD_HANGUL_T_COUNT %d\n" % T_COUNT)
    out.write("#define AXIOM_UCD_HANGUL_N_COUNT %d\n" % N_COUNT)
    out.write("#define AXIOM_UCD_HANGUL_S_COUNT %d\n" % S_COUNT)

    out.write("\n#endif /* AXIOM_UNICODE_TABLES_H */\n")


if __name__ == "__main__":
    main()
