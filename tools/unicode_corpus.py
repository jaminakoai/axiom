"""
Axiom Unicode konformans korpusu (tek dogruluk kaynagi).

Hem testler (`tests/test_unicode_normalization.py`) hem altin dosya ureteci
(`tools/gen_unicode_conformance.py`) bu listeyi kullanir; boylece ikisi
birbirinden ayrisamaz.
"""

# Konformans korpusu: (aciklama, metin)
CORPUS = [
    ("ascii", "hello"),
    ("bos", ""),
    ("nfc-e-acute", "\u00e9"),                      # é
    ("nfd-e-acute", "e\u0301"),                     # e + combining acute
    ("nfc-A-ring", "\u00c5"),                       # Å
    ("nfd-A-ring", "A\u030a"),
    ("turkish-I-dot", "\u0130"),                    # İ
    ("turkish-i-dotless", "\u0131"),                # ı
    ("turkish-word", "\u0130stanbul \u011f\u00fc\u015fi\u00f6\u00e7"),
    ("greek-tonos", "\u03ac"),                      # ά
    ("greek-decomp", "\u03b1\u0301"),
    ("cyrillic", "\u0439"),                         # й
    ("cyrillic-decomp", "\u0438\u0306"),
    ("order-dot-below-circumflex", "a\u0323\u0302"),
    ("order-circumflex-dot-below", "a\u0302\u0323"),
    ("q-dot-above-dot-below", "q\u0307\u0323"),
    ("triple-stack", "o\u0308\u0304\u0323"),
    ("hangul-LV", "\uac00"),                        # 가
    ("hangul-LVT", "\ud55c"),                       # 한
    ("hangul-jamo", "\u1100\u1161"),                # L + V
    ("hangul-jamo-T", "\u1100\u1161\u11a8"),
    ("hangul-mixed", "\ud55c\uad6d\uc5b4"),
    ("emoji", "\U0001f600\U0001f44d"),
    ("math-astral", "\U0001d518"),
    ("combining-only", "\u0301\u0302"),
    ("latin-ext", "\u01ea\u0323"),                  # Ǫ + dot below
    ("vietnamese", "\u1ec7"),                       # ệ
    ("multi-word", "Cafe\u0301 na\u00efve \u00c5ngstr\u00f6m"),
]
