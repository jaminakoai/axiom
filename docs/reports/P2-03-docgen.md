# Axiom P2-03 — `///` Doc Comment + `axiom doc`

**Tarih:** 8 Kasım 2026
**Görev:** `TODO.md` → P2-03
**Durum:** ✅ tamamlandı

---

## 1. Ne yapıldı

Dile API dokümantasyonu altyapısı eklendi: kaynak içindeki `///` yorumları
derleyici tarafından tanınır, AST'de bildirime bağlanır ve `axiom doc` komutuyla
statik HTML/JSON olarak üretilir.

### 1.1 Lexer

`///` artık normal yorum değil, `DOC` token'ı:

```axiom
/// Iki sayiyi toplar.
fn add(a: int, b: int) -> int {
    return a + b
}
```

- `///` → `DOC` (satır metni, baştaki tek boşluk kırpılır)
- `//` ve `#` → eskisi gibi yok sayılır
- `////` de `DOC` olarak okunur (içerik `/` ile başlar)

### 1.2 AST + parser

| Alan | Tip |
|---|---|
| `FunctionDecl.doc` | `List[str]` |
| `StructDecl.doc` | `List[str]` |

- Ardışık `DOC` token'ları tek bildirime bağlanır.
- Doc, **yalnızca hemen izleyen** bildirime gider; sonraki bildirime sızmaz.
- Blok içindeki `///` yorumları deyim olarak yok sayılır (hata vermez).
- `@simd` gibi dekoratörlerde doc yine fonksiyona bağlanır.

### 1.3 `axiom doc`

```bash
axiom doc std/                       # → docs/api/index.html
axiom doc src/ -o build/api          # özel çıktı dizini
axiom doc main.ax --json             # stdout'a JSON
axiom doc main.ax --json -o api.json
axiom doc std/ --title "Axiom std"
```

| Özellik | Davranış |
|---|---|
| HTML | Tek dosya, bağımlılıksız; sol navigasyon + sağ içerik |
| JSON | `modules[].items[]`: `kind/name/signature/doc/summary/line/fields/requires/ensures` |
| Markdown | `#` başlık, `-` liste, ``` kod bloğu, paragraf |
| Güvenlik | Tüm metin HTML-escape edilir (XSS yok) |
| Dayanıklılık | Ayrıştırılamayan dosya atlanır, üretim durmaz |
| Kapsam | Dizinler özyinelemeli (`*.ax`) |

### 1.4 std/ belgelendi

`std/security/yara.ax` ve `std/security/sigma.ax` gerçek `///` doc comment'leri
ile belgelendi:

| Modül | Belgelenen öğe |
|---|---|
| `std/security/yara.ax` | 3 struct + 18 fonksiyon |
| `std/security/sigma.ax` | 5 struct + 21 fonksiyon |

`axiom doc std/` → **52 dosya, 353 fn, 29 struct, 47 belgeli öğe**.

---

## 2. Testler

`tests/test_docgen.py` — **16 test**:

| Grup | Kapsam |
|---|---|
| Lexer | `DOC` token, `//` ile ayrımı |
| Parser | doc bağlama, sızma yok, blok içi yorum, `@simd` |
| docgen | imza/alan/sözleşme çıkarımı, `summary` |
| HTML | escape, başlık/liste/kod, belgesiz işareti, boş liste |
| JSON | şema alanları |
| collect | dizin gezinme, bozuk dosya atlama |
| CLI | HTML üretimi, `--json` stdout, olmayan yol hatası |
| CI | gerçek `std/` üzerinde ≥20 belgeli öğe |

Ek olarak biçimlendirici `///` yorumlarını koruyor
(`test_doc_token_does_not_break_formatting`).

---

## 3. Doğrulama

```bash
python3 -m pytest -q --no-header     # 797 passed
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **797** (+16) |
| LLVM örnekleri | 20/20 |
| `bin/axiomc` bootstrap | ✅ |
| `make fmt-check` | ✅ |
| `axiom doc std/` | ✅ 47 belgeli öğe |

---

## 4. Sıradaki

| # | İş | Neden |
|---|---|---|
| 1 | **P2-04** İngilizce doküman | Global erişim; EN kod blokları CI'da derlenmeli |
| 2 | **P2-05** tam LSP (references/rename/format) | Editör deneyimi |
| 3 | **P1-05/06** ofansif sertleştirme + DFIR akışı | Faz 1 kapısı |

> Not: `axiom doc`, P2-04'te İngilizce `///` yorumları yazıldığında ek iş
> gerektirmeden İngilizce API dokümanı üretir.
