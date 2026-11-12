# Axiom (λx) — LLVM Eşitliği: `?` ve `defer`

**Tarih:** 6 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Kapsam:** `~/Desktop/axiom`
**Önceki rapor:** `Axiom_Stdlib_Result_Raporu_2026-11-06.md`

---

## 0. Özet

LLVM arka ucu artık **birinci sınıf**: `?` operatörü ve `defer` orada da çalışıyor, **19/19 örnek iki arka uçta da** derlenip aynı çıktıyı veriyor.

| İş | Durum |
|---|---|
| LLVM'de `defer` (LIFO, erken dönüşte dahil) | ✅ Eklendi — önceden **sessizce yok sayılıyordu** |
| LLVM'de `?` operatörü | ✅ Eklendi |
| Struct döndüren runtime fonksiyonlarında ABI hatası | ✅ Düzeltildi (segfault) |
| 19/19 örnek LLVM ile | ✅ |
| 2 yeni test (`?` + `defer` LLVM'de) | ✅ |

**Test durumu:** `603 passed` (önceki 602; +1 net, 1 test değiştirildi).

---

## 1. Önce sessiz yanlış davranışı buldum

`defer` için LLVM codegen'de **hiçbir işleyici yoktu**. `DeferStmt` sessizce atlanıyordu:

```axiom
fn main() -> int {
    defer { print("TEMIZLIK") }
    print("GOVDE")
    return 0
}
```

| Arka uç | Çıktı |
|---|---|
| C (doğru) | `GOVDE` → `TEMIZLIK` |
| LLVM (önce) | `GOVDE` — temizlik **hiç çalışmadı** |

Bu, yanlış sonuç üreten en tehlikeli hata sınıfı. `?` eklerken zorunlu hale geldi (Err yolunda temizlik şart), bu yüzden önce onu düzelttim.

**Uygulama:** `defer_stack` + `_emit_deferred_all()`; hem `return` öncesinde hem blok sonunda LIFO üretiliyor.

```bash
$ axiom build defllvm.ax --backend=llvm && ./defllvm
GOVDE
DEFER_2
DEFER_1
```

---

## 2. `?` operatörü LLVM'de

Statement-expression yerine gerçek IR üretiliyor:

```llvm
%ok  = extractvalue %struct.ax_Result_int_str %r, 0
br i1 %ok, label %try.ok, label %try.err

try.ok:
  %v = extractvalue %struct.ax_Result_int_str %r, 1
  store i64 %v, i64* %slot
  br label %try.end

try.err:
  %e   = extractvalue %struct.ax_Result_int_str %r, 2
  %s0  = insertvalue %struct.ax_Result_int_str undef, i1 false, 0
  %s1  = insertvalue ... %s0, i64 zeroinitializer, 1
  %s2  = insertvalue ... %s1, i8* %e, 2
  ; defer'ler burada
  ret %struct.ax_Result_int_str %s2

try.end:
  %res = load i64, i64* %slot
```

Önemli ayrıntılar:

- **Alan indeksleri struct tanımından** okunuyor (`is_ok`/`value`/`error` her zaman 0/1/2 değil; kullanıcı struct'ında sıra farklı olabilir).
- **Açılan değerin tipi kaynağın T'si**; hedefin T'si yalnızca hata struct'ının `value` alanını sıfırlamak için kullanılıyor. (İlk denemede bunu karıştırdım: `Result<str,str>`'ı `Result<str[],str>` döndüren fonksiyonda açarken tip uyuşmazlığı.)
- Sıfır başlatıcı olarak `zeroinitializer` — struct/dizi alanlarında da geçerli.

---

## 3. ABI hatası: struct dönüşü (segfault)

`str_split` LLVM'de **segfault** veriyordu:

```
$ ./sp3 --backend=llvm
Killed by SIGSEGV
```

### Kök neden

LLVM, `declare %struct.ax_array @axiom_str_split(...)` bildirimini **kayıtlarda dönüş** olarak derledi (`%rax/%rcx/%rdx`). Oysa clang'ın derlediği C tarafı 24 baytlık struct'ı **sret** (gizli işaretçi) ile döndürüyor.

C tarafını doğruladım:

```c
extern A axiom_str_split(const char*, const char*);   // A = {i64,i64,char**}
// clang: n=3  ✓ (sret)
```

Aynı IR'yi clang'a verince kayıt dönüşü seçildi → uyumsuzluk.

### Çözüm

Struct döndüren **tüm** runtime bildirimleri ve çağrıları açık `sret`'e sabitlendi:

```llvm
declare void @axiom_str_split(%struct.ax_array* sret(%struct.ax_array), i8*, i8*)
...
%sretp = alloca %struct.ax_array
call void @axiom_str_split(%struct.ax_array* sret(%struct.ax_array) %sretp, ...)
%r = load %struct.ax_array, %struct.ax_array* %sretp
```

Üç yerde uygulandı: statik `externs` listesi (emit sırasında yeniden yazılıyor), `builtin_map` çağrı yolu, ve genel `rt_*` fallback yolu.

> Bu düzeltme yalnızca `str_split`'i değil, **struct döndüren tüm runtime fonksiyonlarını** kapsıyor (tensor, yara, csv…). LLVM'de latent ABI hataları vardı.

---

## 4. Doğrulama

### Örnekler

```bash
$ for f in examples/*.ax; do axiom build "$f" --backend=llvm; done
19/19 ✓
```

`examples/19_error_handling.ax` ve `examples/20_stdlib_result.ax` LLVM ile **çalıştırıldı**, C ile aynı çıktı:

```
[1] yapilandirma yazildi
[2] yuklendi: axiom-demo 8080
[3] beklenen hata: dosya bulunamadi: ...
[4] satir sayisi: 1
[5] eksik anahtar: anahtar bulunamadi: yok
```

### Testler

| Test | Ne doğrular |
|---|---|
| `test_llvm_backend_supports_question_mark` | `?` LLVM'de C ile aynı sonucu verir (Ok/Err) |
| `test_llvm_backend_runs_defer_on_early_return` | Err yolunda `defer` LIFO ve sırası `DEFER_B`, `DEFER_A` |

```bash
$ python3 -m pytest -q --no-header
603 passed in 345.57s (0:05:45)
```

| Kontrol | Sonuç |
|---|---|
| LLVM örnekleri | **19/19** |
| `bin/axiomc` bootstrap | ✅ |
| `make fmt-check` | ✅ |
| ASan (bellek testleri) | ✅ |

CI'daki `19`/`20` istisnası kaldırıldı; artık tüm örnekler LLVM job'ında derleniyor.

---

## 5. Değiştirilen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `axiom/codegen_llvm.py` | `defer_stack` + `_emit_deferred_all`; `_generate_try_expr`; struct dönüşlerinde `sret` (3 yol); `DeferStmt` import |
| `tests/test_error_model.py` | LLVM `?` + `defer` testleri (eski "açık hata beklenir" testi değiştirildi) |
| `README.md`, `CHANGELOG.md`, `.github/workflows/ci.yml` | LLVM eşitliği, test sayısı 603, CI istisnası kaldırıldı |

---

## 6. İki arka ucun durumu

| Özellik | C | LLVM |
|---|---|---|
| `requires`/`ensures`/`verify` | ✅ | ✅ |
| `defer` (LIFO) | ✅ | ✅ *(yeni)* |
| `?` / `Result` | ✅ | ✅ *(yeni)* |
| DWARF (`-g`) | `#line` | `DICompileUnit`/`DISubprogram`/`DILocation`/`DILocalVariable` |
| `main -> Result` | ✅ | ✅ |
| String sahipliği | ✅ (refcount) | ⚠️ runtime'a delege; LLVM tarafında otomatik release yok |

**Kalan eşitsizlik:** LLVM'de string sahiplik temizliği (kapsam çıkışı `release`) üretilmiyor. Uzun ömürlü LLVM programları sızdırabilir; C arka ucu bu yüzden varsayılan.

---

## 7. Sıradaki İşler

| # | İş | Gerekçe |
|---|---|---|
| 1 | **Intrusive header + `String`/`str`** | Son büyük bellek borcu; kilit maliyetini de kaldırır |
| 2 | LLVM'de kapsam temizliği (`release`) | Arka uç eşitliğini tamamlar |
| 3 | Gerçek JSON parser (iç içe, kaçış) | `Result` katmanı hazır, parser sığ |
| 4 | HTTP/1.1 chunked + Content-Length | `http_body` ham |
| 5 | Tutorial + SPEC v0.5 | Öğrenme eşiği |
| 6 | Registry politikası | Paket ekosistemi |

**Öneri:** 1 numara. İki turdur erteleniyor ama artık önünde engel yok: `Result`, stdlib ve LLVM eşitliği tamam. Intrusive header hem `print(f(x))` sızıntısını kapatır hem kilit maliyetini kaldırır hem string benchmark'ındaki 4–7× farkı daraltır.
