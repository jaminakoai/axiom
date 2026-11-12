# Axiom (λx) — Overload ve CLI Hata Yolları Kilitlenmesi

**Tarih:** 7 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Önceki rapor:** `Axiom_Sartname_v05_ve_Sessiz_Hata_Avı_Raporu_2026-11-07.md`

---

## 0. Sonuç

Test-boşluk ajanının 1 ve 2 numaralı önerileri ele alındı. **Düzeltilecek hata bulunmadı** — her ikisi de doğru çalışıyordu. Bu yüzden ürün kodu değiştirilmedi; yalnızca davranışı kilitleyen **20 test** eklendi.

| Alan | Durum | Aksiyon |
|---|---|---|
| Overload çözümlemesi | ✅ Doğru (C + LLVM) | 7 test ile kilitlendi |
| CLI hata yolları | ✅ Doğru (exit 1 + mesaj) | 13 test ile kilitlendi |
| Ürün kodu değişikliği | — | **Yok** |

**Test:** `668 passed` (önceki 648; +20).

---

## 1. Overload — doğrulanan davranış

Üç codegen yolu da (C, LLVM, self-hosted) destekliyordu; hiç test yoktu. Doğrulanan senaryolar:

| Senaryo | C | LLVM |
|---|---|---|
| Parametre tipine göre (`int`/`str`) | `int:42` `str:abc` | aynı |
| Arity'ye göre (1 vs 2 argüman) | `one1` `two3` | aynı |
| 3'lü (`int`/`str`/`bool`) | `i` `s` `b` | aynı |
| `void` dönüş | `int 5` `str z` | aynı |
| Generic struct dönüşü (`Box<int>`/`Box<str>`) | `3 q` | aynı |
| Hatalı argüman tipi | derleme hatası | derleme hatası |
| Yinelenen imza | reddedilir | reddedilir |

Mangling her iki arka uçta da tutarlı: `ax_ovl_<ad>__<parametre tipleri>`.

---

## 2. CLI hata yolları — doğrulanan davranış

**Eksik dosya (8 komut):** `run`, `build`, `check`, `prove`, `emit-c`, `emit-llvm`, `emit-smt`, `fmt`

Her biri: `exit 1`, "bulunamadi" mesajı, **başarı mesajı basmıyor**.

**Diğer hata yolları:**

| Senaryo | Sonuç |
|---|---|
| Sözdizimi hatası (`let x =`) — `run`/`check`/`emit-c` | `exit ≠ 0`, hata mesajı |
| Olmayan modül import | `exit ≠ 0`, "modul" mesajı |
| Tip hatası (`let x: int = "abc"`) | `exit 1`, "tip uyumsuzlugu" |

---

## 3. Eklenen dosya

`tests/test_overload_and_cli_errors.py` — 20 test:

- 7 overload testi (5 pozitif parite + 2 negatif)
- 8 eksik-dosya testi (parametrik)
- 3 sözdizimi testi (parametrik)
- 1 modül testi
- 1 semantik test

Parite testleri aynı kaynağı **hem C hem LLVM** ile derleyip çıktıların birebir eşit olduğunu doğrular.

---

## 4. Neden ürün kodu değişmedi

Talimat “gereksiz kod yazma” olduğu için yalnızca **gerçek boşluk** olan yere dokundum. Overload ve CLI hata yolları zaten doğru davranıyordu; değişiklik yapmak regresyon riski eklerdi. Değer, davranışın **kilitlenmesinde**: bu iki alan bugüne kadar testsizdi, yani gelecekteki bir refactor sessizce bozabilirdi.

---

## 5. Durum

```bash
$ python3 -m pytest -q --no-header
668 passed in 405.24s (0:06:45)
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **668** (+20) |
| LLVM örnekleri | 19/19 |
| `bin/axiomc` bootstrap | ✅ |
| `make fmt-check` | ✅ |

### Ajan önerilerinden kalanlar

| # | Boşluk | Risk |
|---|---|---|
| 3 | LSP eksik metodları (`didSave`, `didClose`, `exit`, `-32601`, bozuk çerçeve) | Düşük |
| 4 | `std/core/error.ax`'in 8 test edilmeyen yardımcısı | Orta |
| 5 | Formatter idempotency | Düşük |
| 6 | `@simd` dekoratörü hiç test edilmiyor | Orta |
| 7 | Package manager `get_search_paths`, `remove --purge`, `tree` dalları | Düşük |
| 8 | 240 builtin için doğrudan checker tip testi | Düşük |
| 9 | Self-hosted `compiler/*.ax` test kapsamı | Orta |

En yüksek getirili sıradaki iş: **#4 ve #6** — ikisi de gerçek kod yolu, ikisi de testsiz, ikisi de ucuz. Intrusive header hâlâ en büyük teknik borç ama ayrı ve odaklı tur gerektiriyor.
