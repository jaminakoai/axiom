# Axiom P2-04 — English Documentation

**Tarih:** 8 Kasım 2026
**Görev:** `TODO.md` → P2-04
**Durum:** ✅ tamamlandı

---

## 1. Amaç

Ekosistem hedefi "global" (30+ yazar, 10+ dış PR/ay). İngilizce doküman olmadan
Türkçe olmayan bir geliştirici dile giremez. P2-04 bunun ön koşuluydu.

---

## 2. Teslim edilenler

| Belge | TR satır | EN satır | Başlık (TR/EN) | Blok (TR/EN) |
|---|---|---|---|---|
| `README.md` → `README.en.md` | 404 | 405 | aynı bölümler | — |
| `docs/TUTORIAL.md` → `docs/en/TUTORIAL.md` | 996 | 996 | 80 / 80 | 57 / 57 |
| `SPECIFICATION.md` → `docs/en/SPECIFICATION.md` | 691 | 691 | 76 / 76 | 19 / 19 |

> Satır sayıları birebir: çeviri özet değil, tam metin.

### 2.1 Karşılıklı bağlantılar

| Belge | Üst bilgi |
|---|---|
| `README.md` | 🌍 English → `README.en.md` |
| `docs/TUTORIAL.md` | 🌍 English → `docs/en/TUTORIAL.md` |
| `SPECIFICATION.md` | 🌍 English → `docs/en/SPECIFICATION.md` |
| `docs/en/TUTORIAL.md` | 🌍 Türkçe → `docs/TUTORIAL.md` |
| `docs/en/SPECIFICATION.md` | 🌍 Turkish → `SPECIFICATION.md` |

### 2.2 İçerik güncelliği

Çeviri sırasında README'lerin geride kaldığı görüldü ve düzeltildi:

| Konu | Önce | Sonra |
|---|---|---|
| Paket yöneticisi | "Registry henüz desteklenmez" | Registry v1: ed25519, semver, transitive, yanked, path-traversal |
| Namespace | yok | `@kapsam/paket` desteklenir |
| std modül sayısı | 35+ | 50+ (52 `.ax`) |
| CLI listesi | `doc` yok | `doc` eklendi |
| Registry test sayısı | 38 | 43 |

---

## 3. Çeviri kuralları (uygulanan)

1. **Kod = kod.** Tanımlayıcı, anahtar sözcük, string literal, sayı, yol, CLI
   komutu, EBNF üretimi **birebir**. Yalnızca yorumlar (`#`, `//`) çevrildi.
2. **Normatif dil RFC-2119'a eşlendi:** "zorunludur" → MUST, "önerilir" → SHOULD,
   "olmalıdır" → MUST.
3. **Örnek tanımlayıcılar korundu** (`sabit`, `sayac`, `kosul`) — kaynakla aynı;
   İngilizce metinde yabancı tanımlayıcı olarak okunur, davranış değişmez.
4. **Program çıktıları korundu** — REPL banner'ı ve çalışma zamanı mesajları
   gerçek çıktı olduğu için çevrilmedi.
5. **Şematik bloklar** (`{ ... }`, `if ... { ... }`) kasıtlı yer tutucu;
   derlenmez, dokunulmadı.

---

## 4. Doğrulama — `tests/test_docs_en.py` (9 test)

| Test | Ne yakalar |
|---|---|
| `test_english_docs_exist` | Eksik/boş çeviri |
| `test_english_structure_matches_turkish` | Bölüm veya kod bloğu kaybı (başlık seviyeleri birebir) |
| `test_english_is_actually_english` | Kopyalanmış Türkçe metin (<20 Türkçe harf) |
| `test_english_code_blocks_still_compile` | Çeviride bozulan kod (10 + 1 blok derlenir) |
| `test_english_tutorial_does_not_leak_internal_apis` | İç API sızıntısı |
| `test_readme_en_relative_links_resolve` | Kırık bağlantı |

`test_specification.py` ve `test_tutorial_examples.py` TR tarafı için zaten vardı;
CI artık dördünü birlikte çalıştırıyor.

### 4.1 Yer tutucu ayrımı

Şartnamede `fn main() -> Result<int, str> { ... }` gibi kasıtlı kısaltmalar var.
Test `^\s*\.\.\.\s*$` veya `{ ... }` desenini atlar — böylece "derlenemedi"
gürültüsü yerine gerçek regresyon yakalanır.

---

## 5. Durum

```bash
python3 -m pytest -q --no-header     # 806 passed
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **806** (+9) |
| TR tutorial blokları | 10/10 ✅ |
| EN tutorial blokları | 10/10 ✅ |
| EN spec blokları | 1/1 derlenebilir ✅ |
| LLVM örnekleri | 20/20 |
| `bin/axiomc` bootstrap | ✅ |
| `make fmt-check` | ✅ |

---

## 6. Sıradaki

| # | İş | Neden |
|---|---|---|
| 1 | **P2-05** tam LSP (references/rename/format) | Editör deneyimi olmadan dış katkı zor |
| 2 | **P1-05** ofansif sertleştirme | Faz 1 kapısı |
| 3 | **P1-06** DFIR akışı | Faz 1 kapısı |
| 4 | **P2-08/09** `Result` tabanlı dosya API, PCRE2/RE2 | Kütüphane derinliği |

> Not: Çeviri yapıldığı için `axiom doc` artık İngilizce `///` yorumlarından
> İngilizce API dokümanı üretebilir; ayrı bir iş gerekmiyor.
