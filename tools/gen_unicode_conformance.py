#!/usr/bin/env python3
"""
Axiom Unicode konformans altın dosyası üreteci.

NEDEN: `tests/test_unicode_normalization.py` normalleştirme sonuçlarını eskiden
çalışan Python yorumlayıcısının `unicodedata` modülüne karşı doğruluyordu.
Ama tablolar sabit bir UCD sürümünden üretilir (bkz. `gen_unicode_tables.py`);
yorumlayıcının sürümü farklıysa (Python 3.10/3.11 → Unicode 14.0.0) test
anlamsız biçimde karşılaştırma yapıyordu.

ÇÖZÜM: Beklenen değerler bir kez üretilip depoya yazılır
(`tests/data/unicode_conformance.json`). Test artık yorumlayıcıdan bağımsızdır
ve tablo sürümü değişmedikçe deterministiktir.

Kullanım:
    python3 tools/gen_unicode_conformance.py > tests/data/unicode_conformance.json
"""
import json
import os
import sys
import unicodedata as u

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_unicode_tables as gen  # noqa: E402

from unicode_corpus import CORPUS  # noqa: E402


def main() -> None:
    gen.check_ucd_version()
    cases = []
    for desc, text in CORPUS:
        cases.append({
            "desc": desc,
            "text": text,
            "nfd": u.normalize("NFD", text).encode("utf-8").hex(),
            "nfc": u.normalize("NFC", text).encode("utf-8").hex(),
            "is_nfc": text == u.normalize("NFC", text),
            "is_nfd": text == u.normalize("NFD", text),
        })
    doc = {
        "ucd_version": gen.PINNED_UCD_VERSION,
        "generator": "tools/gen_unicode_conformance.py",
        "cases": cases,
    }
    json.dump(doc, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
