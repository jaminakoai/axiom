# Axiom (λx) — Self-Hosted Sözleşme Düzeltmesi

**Tarih:** 7 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Önceki rapor:** `Axiom_Result_Helpers_ve_SIMD_Raporu_2026-11-07.md`

---

## 0. Sonuç

Kalan düşük riskli maddeleri ölçerken **self-hosted derleyicide gerçek bir hata** bulundu: `ensures` içindeki `return` sembolü işlenmiyordu ve bozuk C üretiliyordu.

| Alan | Bulgu | Aksiyon |
|---|---|---|
| Formatter idempotency | ✅ Zaten doğru (fmt²=fmt, yorumlar korunuyor) | Sadece doğrulandı |
| Package manager dalları | ✅ Doğru hata veriyor | Sadece doğrulandı |
| **Self-hosted `ensures`** | ❌ **Bozuk C üretiyordu** | Düzeltildi |
| Self-hosted builtin haritası | ❌ 17 builtin eksikti | Düzeltildi |

**Test:** `685 passed` (önceki 677; +8).

---

## 1. Hata: `ensures return ...` bozuk C

### Belirti

```bash
$ ./bin/axiomc build examples/03_contracts.ax
/tmp/axiom_build_tmp.c:12:77: error: indirection requires pointer operand
    if (!((( * denominator) <= numerator))) { ... }
```

Kaynak:

```axiom
fn safe_divide(numerator: int, denominator: int) -> int
    requires denominator != 0
    ensures return * denominator <= numerator
```

Üretilen: `(( * denominator) <= numerator)` — `return` buharlaşmış.

`examples/04`'te daha açık:

```axiom
ensures return >= 0      →      ( >= 0)
```

### Kök neden

`compiler/parser.ax` içindeki `parse_primary` fonksiyonu **`return` token'ı için hiçbir dal içermiyordu**. Sonundaki genel fallback (`return res_new("", pos + 1)`) token'ı tüketip **boş string** üretiyordu. Sonra `parse_mul` bunu sol operand sanıp `( * denominator)` üretti.

Python derleyicisi bu durumu `return` sembolünü `ensures` kapsamına tanımlayarak çözüyor; self-hosted'de karşılığı yoktu.

### Düzeltme

Tek dal eklendi:

```axiom
// 'ensures' sozlesmesinde 'return', donen degeri temsil eder.
// codegen_wrap_ensures bunu __ax_ret degiskenine baglar.
if t.kind == "return" {
    return res_new("__ax_ret", pos + 1)
}
```

`codegen_wrap_ensures` zaten `__ax_ret` adını kullanıyor, değişiklik gerekmedi.

### Doğrulama

```bash
$ ./bin/axiomc build examples/03_contracts.ax && ./03
=== Axiom Formal Contract Dogrulama Testi ===
100 / 5 = 20
[PORT GECERLI] 80
...
Tum sozlesmeler (requires / ensures / verify) basariyla dogrulandi!
```

`ensures` ihlali de doğru yakalanıyor (exit 101).

---

## 2. Self-hosted builtin haritası: 17 eksik

`compiler/parser.ax` içindeki `map_builtin_func` ve `is_builtin_func` şunları tanımıyordu:

`simd_add_i64`, `simd_mul_i64`, `simd_sub_i64`, `simd_sum_i64`, `simd_scan_match`,
`math_abs`, `math_min`, `math_max`, `math_pow`,
`thread_create`, `thread_join`, `mutex_init`, `mutex_lock`, `mutex_unlock`,
`atomic_init`, `atomic_add`, `atomic_get`

Hepsi `axiom_<ad>`'a eşlendi. Ayrıca `is_builtin_func`'a `simd_`, `thread_`, `mutex_`, `atomic_` önekleri eklendi (aksi halde çağrı `ax_simd_...` olarak üretiliyordu).

**Etki:** Bu builtin'leri kullanan programlar artık self-hosted'de **isim çözümleme** aşamasını geçiyor. (Dizi dönüş tipleri hâlâ izlenmediği için `09` gibi örnekler başka bir nedenle derlenemiyor.)

---

## 3. Self-hosted kapsamı (dürüst tablo)

| Örnek | Durum |
|---|---|
| `01_hello`, `02_fibonacci`, `03_contracts`, `04_security_scan` | ✅ derlenir ve çalışır |
| `05_real_scanner` ve sonrası | ❌ derlenmez |

**Neden:** `axiomc` AST düzeyinde **tip çıkarımı yapmıyor**. `let a = builtin_dizi_donduren()` çağrısında değişkeni `ax_int` varsayıyor. Ayrıca generic `Result<T,E>` monomorflaştırması ve struct-array indeksleme yok.

Bu, README'de artık açıkça yazılı: *"generic `Result<T,E>`, struct-ağırlıklı ve stdlib import'lu örnekler AST düzeyinde tip çıkarımı gerektirdiği için henüz derlenemez."*

Tam eşitlik için gereken iş: `compiler/` içine tip çıkarımı geçişi — bu, intrusive header ile birlikte en büyük iki yapısal borçtan biri.

---

## 4. Eklenen dosya

`tests/test_selfhosted_contracts.py` — 8 test:

- 4 parametrik: desteklenen örnekler derlenir ve çalışır
- 1: `ensures return ...` doğru sonuç (`20 / 0 / 7`)
- 1: `ensures` ihlali → exit 101
- 1: üretilen C'de `__ax_ret >= 0` var, `( >= 0)` yok
- 1: `simd_*`/`thread_*` haritalama kaydı

---

## 5. Durum

```bash
$ python3 -m pytest -q --no-header
685 passed in 428.25s (0:07:08)
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **685** (+8) |
| LLVM örnekleri | 19/19 |
| `bin/axiomc` | 4/19 (dürüst kapsam) |
| `make fmt-check` | ✅ |

### Ajan önerileri — kalan

| # | Boşluk | Risk |
|---|---|---|
| 3 | LSP eksik metodları | Düşük |
| 8 | 240 builtin için doğrudan checker testi | Düşük |

Geriye yalnızca iki düşük riskli madde kaldı. **Yapısal borçlar** ise iki tane:
1. **Intrusive header + `String`/`str`** — bellek
2. **Self-hosted tip çıkarımı** — derleyici eşitliği

---

## 6. Gözlem

Bu turda da desen tekrarlandı: "kalan maddeler düşük riskli" diye başladım, ölçtüğümde **iki gerçek hata** çıktı. Özellikle `ensures return` hatası `examples/03`'ü tamamen kırıyordu — ama hiçbir test self-hosted ile bu örneği derlemiyordu, bu yüzden görünmüyordu.

Test-boşluk ajanının 9 numaralı önerisi (*"self-hosted `compiler/*.ax` kapsamı"*) tam da bunu işaret ediyordu. Haklıydı.
