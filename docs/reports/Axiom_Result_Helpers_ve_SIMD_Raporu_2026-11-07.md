# Axiom (λx) — Result Yardımcıları ve `@simd` Kapsamı

**Tarih:** 7 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Önceki rapor:** `Axiom_Overload_ve_CLI_Kilit_Raporu_2026-11-07.md`

---

## 0. Sonuç

Ajanın kalan iki orta-riskli önerisi ele alındı:

| Alan | Durum | Aksiyon |
|---|---|---|
| `std/core/error` yardımcıları (8 fonksiyon) | ✅ Doğru çalışıyor | 4 test ile kilitlendi |
| `@simd` dekoratörü | ⚠️ **LLVM'de etkisizdi** | Düzeltildi + 5 test |

**Tek gerçek hata:** `@simd` LLVM IR'de `#0` attribute grubuna işaret ediyordu ama o grup **hiç tanımlanmamıştı** — clang sessizce yok sayıyordu. Yani `@simd` LLVM'de hiçbir şey yapmıyordu.

**Test:** `677 passed` (önceki 668; +9).

---

## 1. `std/core/error` yardımcıları

Ajan 12 fonksiyonun 8'inin testsiz olduğunu bildirmişti. Doğruladım — **hepsi doğru çalışıyor**, C ve LLVM birebir aynı:

| Fonksiyon | Doğrulanan davranış |
|---|---|
| `result_is_ok` / `result_is_err` | Ok → `true/false`, Err → `false/true` |
| `result_unwrap` | Ok → değer; Err → **exit 101** |
| `result_unwrap_or` | Err → yedek |
| `result_error` | Err → mesaj; Ok → **exit 101** |
| `result_expect` | Ok → değer; Err → **exit 101** |
| `result_err_str` / `result_err_bool` / `result_err_strs` | Doğru tip + boş değer (`str[]` → uzunluk 0) |
| `result_err_with<T>` | Kullanıcı struct'ı ile |

Yanlış varyant çağrıları (unwrap(Err), expect(Err), error(Ok)) **her iki arka uçta** `exit 101` veriyor — sözleşme ihlali olarak doğru.

Kod değişikliği gerekmedi.

---

## 2. `@simd` — gerçek eksik

### Belirti

`examples/09_simd_vector_scan.ax` C'de doğru çalışıyordu ve C kodu vectorization ipucu içeriyordu:

```c
__attribute__((hot, optimize("O3", "tree-vectorize")))
```

LLVM IR'de ise:

```llvm
define i64 @ax_parallel_signature_score(...) #0 {
```

Ama `attributes #0` **hiçbir yerde tanımlı değildi**:

```bash
$ grep -c "attributes #0" prog.ll
0
```

clang bunu tolere etti (derleme başarılı, program doğru çalıştı) ama `#0` hiçbir anlam taşımadığı için **`@simd` LLVM'de etkisizdi**.

### Düzeltme

Tek satır — tanım eklendi:

```llvm
attributes #0 = { "target-features"="+avx2,+fma" }
```

Ayrıca `@simd` fonksiyonu yoksa grup tamamen kaldırılıyor (ölü tanım bırakmamak için):

```python
has_simd = any(getattr(f, 'is_simd', False) for f in functions)
if not has_simd:
    header = [h for h in header if not h.startswith('attributes #0')]
```

### Doğrulama

| Kontrol | Sonuç |
|---|---|
| `@simd` fonksiyon → `#0` | ✅ `define i64 @ax_scale(i64 %param.x) #0` |
| Normal fonksiyon → `#0` yok | ✅ |
| `@simd` olmayan program → grup yok | ✅ |
| `examples/09` C ve LLVM | ✅ ikisi de çalışıyor |
| Parite (`T: 22`) | ✅ birebir |

---

## 3. Eklenen dosya

`tests/test_error_helpers_and_simd.py` — 9 test:

- 1 parite testi (tüm Result yardımcıları, C + LLVM)
- 3 negatif test (yanlış varyant → exit 101, iki arka uç)
- 1 `@simd` parite testi
- 1 C vectorization ipucu testi
- 1 LLVM `target-features` testi
- 1 "ölü attribute yok" testi
- 1 `examples/09` iki arka uç testi

---

## 4. Durum

```bash
$ python3 -m pytest -q --no-header
677 passed in 423.44s (0:07:03)
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **677** (+9) |
| LLVM örnekleri | 19/19 |
| `bin/axiomc` bootstrap | ✅ |
| `make fmt-check` | ✅ |

### Ajan önerileri — kalan

| # | Boşluk | Risk |
|---|---|---|
| 3 | LSP eksik metodları | Düşük |
| 5 | Formatter idempotency | Düşük |
| 7 | Package manager dalları | Düşük |
| 8 | 240 builtin için doğrudan checker testi | Düşük |
| 9 | Self-hosted `compiler/*.ax` kapsamı | Orta |

Bu beşi düşük riskli ve dar; toplu halde tek turda kapatılabilir. **Intrusive header** ise ayrı, odaklı ve yüksek riskli bir tur hak ediyor — 82 fonksiyon ve 277 çağrı noktası, alias güvenliği gerektiriyor.

---

## 5. Gözlem

Bu turda da desen aynı: **test yazmak için bakmak, gerçek hatayı buluyor.** `@simd` iki turdur "çalışıyor" görünüyordu çünkü program doğru sonuç veriyordu — ama optimizasyon ipucu LLVM'de hiç uygulanmıyordu. Sessiz etkisizlik, sessiz yanlışlığın bir alt türü.
