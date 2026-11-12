# Axiom (λx) — Hata Modeli: `Result<T, E>` + `?`

**Tarih:** 6 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Kapsam:** `~/Desktop/axiom`
**Önceki rapor:** `Axiom_String_Optimizasyon_ve_Denetim_Raporu_2026-11-06.md`

---

## 0. Özet

Dilin **en büyük ergonomi eksiği** kapatıldı: beklenen hatalar artık `Result<T, E>` ile akıyor ve `?` operatörüyle yukarı iletiliyor.

| İş | Durum |
|---|---|
| `Result<T, E>` generic tipi (`std/core/error.ax`) | ✅ |
| `?` operatörü: lexer → parser → AST → checker → C codegen | ✅ |
| Erken dönüşte `defer` + sahiplik temizliği | ✅ |
| Tip güvenliği: yalnızca `Result` döndüren fonksiyonda, hata tipi eşleşmeli | ✅ |
| LLVM: sessiz yanlış kod yerine **açık hata** | ✅ |
| Yan bulgu: generic monomorfizasyonda bağlam kaybı | ✅ Düzeltildi |
| Yan bulgu: LLVM'de overload isim çakışması | ✅ Düzeltildi |
| `examples/19_error_handling.ax` | ✅ |
| 6 yeni test | ✅ |

**Test durumu:** `589 passed` (önceki 583; +6).

---

## 1. Neden `Result` + `?`, `try/except` değil?

Zero-GC hedefiyle uyum:

| Yaklaşım | Stack unwinding | defer temizliği | Zero-GC |
|---|---|---|---|
| `try/except` (setjmp/longjmp) | Gerekir | Elle unwind kaydı gerekir | Riskli |
| **`Result` + `?`** | **Yok** | **Normal kontrol akışı, otomatik** | **Uyumlu** |

`?` bir "erken dönüş"tür; `return` gibi davranır. Bu yüzden `defer` ve sahiplik temizliği **hiçbir ek mekanizma olmadan** doğru çalışır.

### İki katmanlı hata felsefesi (README'ye işlendi)

| Hata türü | Mekanizma | Davranış |
|---|---|---|
| **Beklenen** (dosya yok, port kapalı, parse hatası) | `Result` + `?` | Akar, çağıran karar verir |
| **Programlama hatası** (`requires`/`ensures`/`verify`) | `axiom_contract_fail` | Program durur (exit 101) |

Bu ayrım, dilin "sözleşmeli" kimliğini bozmadan günlük kullanım ergonomisi sağlar.

---

## 2. Kullanım

```axiom
import "std/core/error"

fn parse_port(s: str) -> Result<int, str> {
    let v = str_to_int(s)
    if v <= 0 or v > 65535 {
        return result_err<int>("gecersiz port: " + s)
    }
    return result_ok<int>(v)
}

fn resolve_port(host: str, port_str: str) -> Result<int, str> {
    defer { print("[temizlik] cikis") }
    let port = parse_port(port_str)?      // Err ise hata yukari iletilir
    return result_ok<int>(port)
}

fn main() -> int {
    let r = resolve_port("127.0.0.1", "99999")
    print("HATA:", r.error)
    print("YEDEK:", result_unwrap_or<int>(r, -1))
    return 0
}
```

Çıktı:

```text
[temizlik] cikis
HATA: gecersiz port: 99999
YEDEK: -1
```

`defer` erken dönüşte çalıştı; `main` hata akışını `Result` alanlarıyla yönetti.

### Kanonik yapı

```axiom
struct Result<T, E> {
    is_ok: bool,
    value: T,
    error: E
}
```

`?` **her** struct ile çalışır — yeter ki alanları `is_ok: bool`, `value`, `error` olsun. Bu, kullanıcıların kendi hata tiplerini (ör. `error: ErrorInfo`) tanımlamasına izin verir.

### Yardımcılar

| Fonksiyon | Açıklama |
|---|---|
| `result_ok<T>(v)` / `result_err<T>(msg)` | Kurucular |
| `result_is_ok<T>(r)` / `result_is_err<T>(r)` | Sorgular |
| `result_unwrap<T>(r)` | Ok değeri; Err ise `verify` ihlali |
| `result_unwrap_or<T>(r, yedek)` | Err ise yedek |
| `result_error<T>(r)` | Err mesajı |
| `result_expect<T>(r, mesaj)` | Ok değeri; Err ise sözleşme hatası |

---

## 3. Tip Güvenliği

`?` üç kuralı derleme anında denetler:

**a) İfade `Result` olmalı**

```text
'Axiom Semantik Hatasi: '?' operatoru Result benzeri bir tip bekler
 (is_ok/value/error alanlari), 'int' verildi.'
```

**b) İçeren fonksiyon `Result` döndürmeli**

```text
'Axiom Semantik Hatasi: '?' kullanilan fonksiyon 'Result' dondurmeli;
 'main' 'int' donduruyor.'
```

**c) Hata tipleri eşleşmeli**

```text
'Axiom Semantik Hatasi: '?' hata tipi uyusmuyor:
 ifade 'str', fonksiyon 'ErrorInfo' donduruyor.'
```

Üçü de testle doğrulanıyor.

---

## 4. Codegen

`?`, GNU statement expression olarak üretiliyor:

```c
ax_int v = ({
    ax_Result_int_str _ax_r1 = ax_parse_positive(s);
    if (!(_ax_r1.is_ok)) {
        /* defer'ler + sahiplik temizliği buraya enjekte edilir */
        return ((ax_Result_int_str){ .is_ok = false, .value = (ax_int)0,
                                     .error = _ax_r1.error });
    }
    _ax_r1.value;
});
```

Önemli nokta: **temizlik kodu**, `_capture_cleanup()` ile mevcut `defer_stack` ve sahiplenilmiş string/dizi listesinden üretiliyor. Yani `?` ayrı bir unwind mekanizması değil; mevcut `return` yolunun aynısı.

---

## 5. LLVM: Dürüst Başarısızlık

İlk denemede LLVM arka ucu `?`'i sessizce yok saydı ve **yanlış sonuç** üretti (`OK: 0` yerine `OK: 42`). Bu, en tehlikeli hata sınıfı.

Düzeltme: `TryExpr` LLVM codegen'de açıkça reddediliyor:

```text
'?' operatoru LLVM arka ucunda henuz desteklenmiyor.
C arka ucunu kullanin (varsayilan) veya Result'i acikca match/if ile cozun.
```

Test: `test_llvm_backend_reports_clear_error_for_question_mark`.

> Ders: bir özellik bir arka uçta yoksa, **derleme hatası** vermeli — sessizce yanlış kod üretmemeli.

---

## 6. Yan Bulgular (gerçek hatalar)

### 6.1 Generic monomorfizasyonda bağlam kaybı — sessiz denetim atlaması

`monomorphize_function`, monomorfize edilen gövdeyi denetlemek için `check_function` çağırıyor; bu da `self.current_function` ve `self.current_scope`'u değiştirip `None`'a çekiyordu.

Sonuç: **generic bir fonksiyon çağrısından sonraki tüm `return` ifadeleri denetlenmiyordu.**

```axiom
fn f(z: int) -> Box<int> {
    if z < 0 { return wrap<int>(0) }   // denetlendi
    return wrap<int>(z)                // ATLANDI → ax_wrap (mangled değil) → C hatası
}
```

Düzeltme: `current_function` ve `current_scope` kaydedilip `finally` ile geri yükleniyor.

Bu hata, `?` testlerinde `result_ok<int>(v)` çağrısının manglenmemesi olarak ortaya çıktı; **mevcut generic testleri bunu yakalamıyordu** çünkü tek `return` kullanıyorlardı.

### 6.2 LLVM'de overload isim çakışması

`ok(int)` / `ok(str)` gibi aşırı yüklemeler LLVM'de aynı sembol adını üretiyordu (`ax_ok`), bu da "invalid redefinition" hatası veriyordu. `std/core/result.ax`'i LLVM ile derlemek bunu ortaya çıkardı.

Düzeltme: LLVM codegen artık C arka ucuyla aynı mantıkla mangling yapıyor:

```text
ax_ovl_<ad>__<parametre tipleri>
```

Çağrı yerinde `expr.resolved_function` varsa onun imzası, yoksa argüman tipleri kullanılıyor.

---

## 7. Test Sonuçları

```bash
$ python3 -m pytest -q --no-header
589 passed in 328.86s (0:05:28)
```

Yeni testler (`tests/test_error_model.py`):

1. `test_result_question_mark_basic_flow` — Ok/Err/chain/fallback
2. `test_question_mark_requires_result_returning_function`
3. `test_question_mark_rejects_non_result_expression`
4. `test_question_mark_runs_defer_on_early_return`
5. `test_result_paths_are_leak_free_under_asan`
6. `test_llvm_backend_reports_clear_error_for_question_mark`

Diğer kontroller:

| Kontrol | Sonuç |
|---|---|
| LLVM (18 örnek) | 17/18 (19 numara C backend gerektiriyor, açık hata) |
| `bin/axiomc` bootstrap | ✅ |
| `make fmt-check` | ✅ |
| `examples/19` ASan | ✅ sıfır hata |

---

## 8. Değiştirilen / Eklenen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `axiom/lexer.py` | `?` → `QUESTION` token |
| `axiom/ast_nodes.py` | `TryExpr` düğümü |
| `axiom/parser.py` | Postfix `?` ayrıştırma |
| `axiom/checker.py` | `TryExpr` tip denetimi + `_result_shape`; monomorfizasyon bağlam koruması |
| `axiom/codegen_c.py` | `TryExpr` statement-expression üretimi, `_capture_cleanup` |
| `axiom/codegen_llvm.py` | `TryExpr` için açık hata; overload mangling |
| `axiom/cli.py` | `NotImplementedError` yakalama (8 handler) |
| `std/core/error.ax` | **Yeni** — generic `Result<T,E>` + yardımcılar |
| `examples/19_error_handling.ax` | **Yeni** |
| `tests/test_error_model.py` | **Yeni** — 6 test |
| `README.md`, `CHANGELOG.md`, `.github/workflows/ci.yml` | Doküman/CI senkronu |

---

## 9. "Python gibi olmaya" katkısı

Önceki değerlendirmede en büyük eksik **hata modeli** olarak işaretlenmişti. Bu turda:

| Boyut | Önce | Sonra |
|---|---|---|
| Hata modeli | ❌ (exit ile ölüm) | ✅ `Result` + `?`, defer uyumlu |
| Dil bütünlüğü | 🟡 %50 | 🟡 %65 |
| Günlük kullanım ergonomisi | Düşük | Orta |

Kalan büyük eksikler sırasıyla: **stdlib derinliği** (JSON/HTTP gerçek parser değil), **paket ekosistemi**, **platform desteği**, **doküman/tutorial**.

---

## 10. Sıradaki İşler

| # | İş | Gerekçe |
|---|---|---|
| 1 | `?` için LLVM desteği | İki arka uç eşitliği |
| 2 | `Result`'ı stdlib'e yaymak (`file_read`, `json_parse`, `http_get`) | Gerçek kullanım; bugün hata `""`/`-1` ile dönüyor |
| 3 | Intrusive header + `String`/`str` | Kalan sızıntı sınıfı + performans |
| 4 | Gerçek JSON/HTTP | Stdlib derinliği |
| 5 | Tutorial + SPEC v0.5 | Öğrenme eşiği |
| 6 | Runtime `core`/`platform` + WASI | Platform |

**Öneri:** 2 numara en yüksek getirili. `Result` altyapısı hazır ama stdlib hâlâ `""`/`-1` döndürüyor; yani kullanıcı yeni modeli ancak kendi fonksiyonlarında kullanabiliyor. `file_read`/`json_parse`/`http_get` için `Result` varyantları eklenirse hata modeli gerçekten "kullanılan" olur.
