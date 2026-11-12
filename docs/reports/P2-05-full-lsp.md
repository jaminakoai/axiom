# Axiom P2-05 — Tam LSP (Editor Experience)

**Tarih:** 8 Kasım 2026
**Görev:** `TODO.md` → P2-05
**Durum:** ✅ tamamlandı

---

## 1. Amaç

Ekosistemin ölçülebilir hedefi "10+ dış PR/ay". Dış katkı için editör deneyimi
zorunlu: tanıma gitme vardı, ama **tüm kullanımları görme, yeniden adlandırma,
biçimlendirme, renklendirme ve parametre ipucu** yoktu. P2-05 bunları ekler.

---

## 2. Eklenen metodlar

| LSP metodu | Davranış |
|---|---|
| `textDocument/references` | Bildirim + tüm kullanımlar; `context.includeDeclaration` desteği |
| `textDocument/prepareRename` | Sembol aralığı + `placeholder`; keyword/boşlukta `null` |
| `textDocument/rename` | Tüm oluşumlar tek `WorkspaceEdit`; geçersiz ad reddedilir |
| `textDocument/codeAction` | Quick fix: yazım düzeltmesi, `let mut` |
| `textDocument/formatting` | `format_source` tabanlı tek düzenleme |
| `textDocument/semanticTokens/full` | 12 tipli legend, delta kodlama |
| `textDocument/signatureHelp` | Yerel + builtin imza, aktif parametre |

`initialize` capabilities artık yedisini de duyurur:

```json
{
  "referencesProvider": true,
  "renameProvider": {"prepareProvider": true},
  "codeActionProvider": {"codeActionKinds": ["quickfix"]},
  "documentFormattingProvider": true,
  "semanticTokensProvider": {"legend": {...}, "full": true},
  "signatureHelpProvider": {"triggerCharacters": ["(", ","]}
}
```

---

## 3. Tasarım kararları

### 3.1 Kullanımlar = lexer token'ları

`references` ve `rename` metin araması **değil**, lexer token'ı kullanır:

```python
for tok in Lexer(text).tokenize():
    if tok.type == "IDENT" and tok.value == word: ...
```

Sonuç: yorum (`# ...`, `// ...`) ve string literal içindeki aynı kelime
**kendiliğinden** eşleşmez. Ayrı bir "yorum/string atla" mantığı yok — lexer
zaten onları ayrı token yapıyor.

Bildirim tespiti: bir `IDENT`'in önündeki token `FN`/`STRUCT`/`LET` ise
bildirimdir (`MUT` atlanır). `includeDeclaration=false` bunları çıkarır.

### 3.2 Semantic token tipleri

| Token | Tip |
|---|---|
| `DOC` | `comment` |
| `STRING` | `string` |
| `INT`, `FLOAT` | `number` |
| `TYPE` (`int`, `str`, ...) | `type` |
| `fn`/`let`/`if`/... | `keyword` |
| operatörler | `operator` |
| `IDENT` | AST'den: `function`/`struct`/`parameter`/`variable`/`property` |

AST'de bulunmayan tanımlayıcı `variable` olur. Delta kodlaması LSP standardı:
`[deltaLine, deltaStartChar, length, tokenType, modifiers]`.

### 3.3 Signature help

İmleçten geriye doğru parantez dengesi taranır, en içteki çağrının adı bulunur.
Aktif parametre `(` ile imleç arasındaki **üst düzey** virgül sayısıdır; string
ve iç içe parantezler sayılmaz. `print` keyword olduğu için imza yardımı
verilmez (dil düzeyinde özel form).

### 3.4 Quick fix'ler

| Tanılama | Düzeltme |
|---|---|
| `Bilinmeyen fonksiyon cagrisi: 'str_lenn'` | `difflib` ile en yakın builtin → `str_len` (aralık gerçek tanımlayıcıya daraltılır) |
| `Degistirilemez (immutable) degiskene atama...` | `let x` → `let mut x` |

Aralık daraltma önemli: checker tanılaması `col+15` genişliğinde olabiliyor;
düzeltme yalnızca tanımlayıcıyı değiştirmeli, satırın kalanını silmemeli.

### 3.5 Formatting

`axiom fmt` ile aynı `format_source`. Zaten biçimliyse **boş liste** döner
(gereksiz düzenleme göndermez).

---

## 4. Testler — `tests/test_lsp_full_features.py` (24 test)

| Grup | Kapsam |
|---|---|
| Capabilities | Yedi sağlayıcının duyurulması, legend sırası |
| References | Bildirim + çağrılar, `includeDeclaration=false`, yorum/string hariç |
| Rename | `prepareRename` aralığı, geçersiz ad/keyword reddi, tüm oluşumlar |
| Semantic tokens | %5 == 0, sıralı, çakışmasız, tip sınıflandırması |
| Signature help | Yerel, builtin, aktif parametre 0/1, çağrı dışı `null` |
| Code actions | `str_lenn`→`str_len`, `let mut`, temiz kodda boş |
| Formatting | Gerekli/gereksiz/boş belge |
| Protokol | Gerçek `bin/axiom-lsp` ile Content-Length çerçeveleme, 8 id |
| Hata | Bilinmeyen metod → `-32601` |

Mevcut 14 LSP testi de geçiyor (regresyon yok).

---

## 5. Durum

```bash
python3 -m pytest -q --no-header     # 830 passed
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **830** (+24) |
| LSP testleri | 38 (14 eski + 24 yeni) |
| LLVM örnekleri | 20/20 |
| `bin/axiomc` bootstrap | ✅ |
| `make fmt-check` | ✅ |

---

## 6. Sıradaki

| # | İş | Neden |
|---|---|---|
| 1 | **P1-05** ofansif sertleştirme | Faz 1 kapısı |
| 2 | **P1-06** DFIR akışı | Faz 1 kapısı |
| 3 | **P2-08/09** `Result` tabanlı dosya API, PCRE2/RE2 | Kütüphane derinliği |
| 4 | **P2-10/11** map, saat dilimi | Kütüphane tamlığı |

> Faz 1 kapısı için kalan iki iş P1-05 ve P1-06. İkisi bitince "güvenlik
> araçları" fazı kapanır ve ölçüm panosundaki Faz 1 satırları yeşile döner.
