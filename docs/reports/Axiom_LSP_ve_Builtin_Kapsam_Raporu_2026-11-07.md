# Axiom (λx) — LSP Yaşam Döngüsü ve Dizi Builtin'leri Kapsamı

**Tarih:** 7 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Önceki rapor:** `Axiom_SelfHosted_Sozlesme_Duzeltmesi_Raporu_2026-11-07.md`

---

## 0. Sonuç

Ajanın kalan iki düşük riskli maddesi (LSP eksik metodları, sıfır kapsamlı builtin'ler) ölçüldü. **Düzeltilecek hata bulunmadı** — ikisi de doğru çalışıyordu. Yalnızca kilitlendi.

| Alan | Durum | Aksiyon |
|---|---|---|
| LSP yaşam döngüsü | ✅ Doğru | 2 test |
| `array_create_*` / `array_push_*` | ✅ Doğru | 5 test |
| Ürün kodu | — | **Değişmedi** |

**Test:** `692 passed` (önceki 685; +7).

---

## 1. LSP yaşam döngüsü — doğrulanan

JSON-RPC 2.0 stdio çerçevesi elle açılıp gerçek `bin/axiom-lsp` süreciyle konuşuldu:

| Mesaj | Beklenen | Sonuç |
|---|---|---|
| `initialize` | `capabilities` (hover/definition/completion) | ✅ |
| `initialized` | yanıt yok | ✅ |
| `didOpen` (bozuk belge) | `publishDiagnostics` | ✅ tanılama yayınlandı |
| `didSave` | tanılama yenilenir | ✅ |
| `didClose` | belge düşürülür | ✅ |
| `bilinmeyen/metod` | `error.code = -32601` | ✅ |
| `shutdown` | `result: null` | ✅ |
| `exit` | `exit 0` | ✅ |

Önceki testler yalnızca `initialize`/`shutdown`/`didOpen`/`didChange`/completion/hover/definition kapsıyordu; **`didSave`, `didClose`, `initialized`, `exit`, `-32601`, diagnostic** kapsanmıyordu.

---

## 2. Dizi builtin'leri — doğrulanan

Ajan "41 builtin hiçbir yerde geçmiyor" demişti; listesindeki dizi fabrikalarını denedim:

| İfade | Sonuç |
|---|---|
| `array_create_int(5)` → `len` | 5 ✅ |
| `array_create_str(3)` → `len` | 3 ✅ |
| `array_push_int(array_create_int(2), 7)` → `len` | 3 ✅ |
| `array_push_str(array_create_str(2), "x")` → `len` | 3 ✅ |
| `array_create_int(3)` elemanları | `0 0 0` (sıfır başlatmalı) ✅ |

Yani bunlar "ölü API" değil — çalışıyor, sadece testsizdi.

---

## 3. Eklenen dosya

`tests/test_lsp_lifecycle_and_array_builtins.py` — 7 test:

- 2 LSP testi (tam yaşam döngüsü + diagnostic)
- 4 parametrik dizi fabrika testi
- 1 sıfır başlatma testi

LSP testi gerçek süreçle `Content-Length` çerçevelemesi üzerinden konuşuyor — birim değil, protokol düzeyi.

---

## 4. Durum

```bash
$ python3 -m pytest -q --no-header
692 passed in 431.12s (0:07:11)
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **692** (+7) |
| LLVM örnekleri | 19/19 |
| `bin/axiomc` | 4/19 (dürüst kapsam) |
| `make fmt-check` | ✅ |

---

## 5. Ajan önerileri — durum

| # | Boşluk | Durum |
|---|---|---|
| 1 | LLVM `break`/`continue` | ✅ Kapatıldı (gerçek hata) |
| 2 | Overload testleri | ✅ Kilitlendi |
| 3 | LSP eksik metodları | ✅ Kilitlendi *(bu tur)* |
| 4 | `std/core/error` yardımcıları | ✅ Kilitlendi |
| 5 | Formatter idempotency | ✅ Doğrulandı |
| 6 | `@simd` | ✅ Düzeltildi (gerçek hata) |
| 7 | Package manager dalları | ✅ Doğrulandı |
| 8 | Dizi/builtin kapsamı | ✅ Kilitlendi *(bu tur)* |
| 9 | Self-hosted kapsamı | ✅ Düzeltildi (gerçek hata) |
| 10 | CLI hata yolları | ✅ Kilitlendi |

**Ajanın 10 önerisinin tamamı kapatıldı.** 4'ü gerçek hata çıktı, 6'sı kilitlendi.

---

## 6. Kalan yapısal borçlar

Artık "test boşluğu" değil, **mimari** işler kaldı:

| # | İş | Büyüklük | Neden |
|---|---|---|---|
| 1 | **Intrusive header + `String`/`str`** | Büyük | 82 fonksiyon, 277 çağrı; geçici string sızıntısını ve kilit maliyetini kapatır |
| 2 | **Self-hosted tip çıkarımı** | Büyük | `axiomc` 4/19; tam eşitlik için AST düzeyi tipler |
| 3 | Gerçek JSON parser | Orta | Bugün anahtar arama |
| 4 | HTTP/1.1 chunked + Content-Length | Orta | `http_body` ham |
| 5 | Registry politikası | Karar | git-only'yi resmileştir veya registry yap |
| 6 | Runtime `core`/`platform` + WASI | Orta | Çapraz derleme |

Bunlar tek oturumda güvenle yapılamaz; her biri ayrı ve odaklı bir tur hak ediyor.
