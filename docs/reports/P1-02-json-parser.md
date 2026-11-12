# P1-02 — Gerçek JSON Parser (Uygulama Raporu)

**Tarih:** 7 Kasım 2026
**Görev:** `TODO.md` → P1-02
**Durum:** ✅ Tamamlandı (kabul kriterlerinin tamamı doğrulandı)

---

## 1. Sorun

Mevcut `json_get_*` **düz metin** arıyordu:

```c
const char* axiom_json_find_key(const char* json, const char* key) {
    // metinde "key" arar, sonra ':' sonrasını döner
}
```

Eksikler:
- İç içe nesneye erişim yok (`user.name` çalışmazdı)
- Dizi indeksleme yok
- `null` ile "anahtar yok" ayırt edilemiyordu (ikisi de `""`)
- `\uXXXX` Unicode kaçışı çözülmüyordu
- Tip ayrımı yok (`"5"` ile `5` aynı görünüyordu)
- Geçersiz JSON sessizce kabul ediliyordu

Sigma/YARA kural dosyaları ve `axiom-scan` bunlara ihtiyaç duyuyor.

---

## 2. Uygulama

`axiom/runtime.h` içine **recursive-descent parser** eklendi (~500 satır):

| Bileşen | Detay |
|---|---|
| Tip modeli | `AXJ_NULL / BOOL / NUM / STR / ARR / OBJ` |
| Bellek | DOM ağacı; `json_free(root)` tüm ağacı serbest bırakır, node'lar ödünç |
| Derinlik | `AXJ_MAX_DEPTH = 200` (stack taşması koruması) |
| String | `\n \r \t \b \f \/ \" \\` + `\uXXXX` + **surrogate pair** |
| Sayı | `strtod`; bilimsel gösterim; baştaki sıfır (`01`) reddi |
| Hata | Konumlu mesaj + thread-local `json_last_error()` |

### API

| Fonksiyon | İmza |
|---|---|
| `json_parse` | `(str) -> int` (0 = hata) |
| `json_last_error` | `() -> str` |
| `json_free` | `(int) -> void` |
| `json_path` | `(int, str) -> int` — `"a.b[0].c"` |
| `json_get` | `(int, str) -> int` — tek seviye |
| `json_at` | `(int, int) -> int` — dizi/nesne indeksi |
| `json_len` | `(int) -> int` |
| `json_key_at` | `(int, int) -> str` |
| `json_type_of` | `(int) -> int` (0..5) |
| `json_node_str/int/float/bool` | `(int) -> T` |
| `json_node_is_null` | `(int) -> bool` |

### `Result` katmanı (`std/encoding/json.ax`)

```axiom
let doc  = json_parse_result(text)?          // Err: "gecersiz JSON (konum 1)"
let name = json_str_at(doc, "user.name")?    // Err: "yol bulunamadi: ..."
let port = json_int_at(doc, "server.port")?
let tag0 = json_str_at(doc, "tags[0]")?
json_doc_free(doc)
```

Ek: `json_float_at`, `json_bool_at`, `json_has_path`, `json_is_null_at`, `json_len_at`.

---

## 3. Yol boyunca bulunan hata

**LLVM: `return <struct>` içinde string kaçışı**

```axiom
fn f(path: str) -> Result<str, str> {
    return result_err_str(mk(path))   // mk(path) sonucu struct'a giriyor
}
```

| Arka uç | Çıktı |
|---|---|
| C | `yol bulunamadi: user.missing` ✅ |
| LLVM (önce) | bozuk bayt (`�L`) ❌ |

Neden: LLVM codegen'de `_mark_escape` yalnızca `i8*` / `%struct.ax_array` dönüşlerinde çağrılıyordu. `Result<str,str>` (bir struct) dönüşünde çağrılmadığı için `path` blok sonunda serbest bırakılıyor, struct içindeki işaretçi dangling kalıyordu.

**Düzeltme:** her `return <ifade>` kaçış analizine giriyor (tek satır).

---

## 4. Doğrulama

```
$ python3 -m pytest -q tests/test_json_real_parser.py
14 passed

$ python3 -m pytest -q --no-header
706 passed in 458.74s
```

| Kabul kriteri | Sonuç |
|---|---|
| `{"a":{"b":[1,2,{"c":null}]}}` derin erişim | ✅ `json_path("a.b[2].c")` → null |
| `\u00e7` → `ç` | ✅ |
| Surrogate pair `\ud83d\ude00` → 😀 | ✅ |
| Geçersiz JSON → `Err` (panik yok) | ✅ 8 farklı bozuk girdi testi |
| `01` reddi | ✅ |
| 200 seviye derinlik sınırı | ✅ stack taşması yok |
| C + LLVM paritesi | ✅ 11 satırlık çıktı birebir |

Ek doğrulama: LLVM 19/19 örnek, `bin/axiomc` bootstrap, `make fmt-check`.

---

## 5. Değişen dosyalar

| Dosya | Değişiklik |
|---|---|
| `axiom/runtime.h` | JSON parser (~500 satır) + `json_last_error` |
| `axiom/checker.py` | 14 yeni builtin imzası |
| `axiom/codegen_c.py` | builtin eşlemeleri |
| `axiom/codegen_llvm.py` | declare + builtin eşlemeleri; `return` kaçış düzeltmesi |
| `std/encoding/json.ax` | `Result` tabanlı DOM API |
| `tests/test_json_real_parser.py` | **Yeni** — 14 test |
| `TODO.md`, `CHANGELOG.md`, `README.md` | P1-02 kapatıldı, test 706 |

---

## 6. Sıradaki

**P1-01 — HTTP/1.1** (chunked, Content-Length, redirect, timeout).
`axiom-scan` hem JSON'a hem HTTP'ye bağlı; JSON tamam, sırada HTTP var.
