# P1-03b — LLVM'de `axiom-scan` Yanlış Sonucu (Kök Neden Analizi)

**Tarih:** 8 Kasım 2026
**Görev:** `TODO.md` → P1-03b
**Durum:** ✅ Kapatıldı

---

## 1. Belirti

`axiom-scan` C ile doğru çalışırken LLVM ile **bozuk kural adları** üretiyordu:

| Arka uç | `rules[0].name` | `patterns[0]` |
|---|---|---|
| C | `Basit` | `str:abc` |
| LLVM | `strings:` | `conditi` |

Derleme başarılı, çalışma zamanında sessiz yanlış sonuç — en tehlikeli sınıf.

---

## 2. Kök neden — iki ayrı hata

### Hata 1: Literal ile başlatılan `str` izlenmiyordu

LLVM codegen'de `LetDecl` şunu yapıyordu:

```python
if t == 'i8*' and val_reg is not None:
    if not isinstance(stmt.initializer, StringLiteral):   # ← bu koşul
        if self._is_borrowed_str_expr(stmt.initializer):
            retain(...)
        self._mark_owned_str(stmt.name)
```

Literal ile başlatılan değişken **sahiplik kapsamına alınmıyordu**. Sonra:

```axiom
let mut rule_name = ""        # izlenmiyor
...
rule_name = name              # AssignStmt: stmt.name in str_var_scope? HAYIR
                              # → retain/release üretilmiyor
```

`name` bloğun sonunda serbest bırakılıyor, `rule_name` **dangling** kalıyor.
Sonradan okunan değer, yeniden kullanılan belleğin çöpü oluyor (`strings:`).

**Düzeltme:** TÜM `i8*` değişkenleri izlenir. Literal'e `release` zaten no-op
(oldstr sahiplik tablosunda değil), dolayısıyla güvenli.

### Hata 2: `array_push` str elemanı için referans almıyordu

```axiom
let p = parts[1]                 // ödünç
rule = yara_rule_add_pattern(rule, id, p)   // p diziye kopyalanıyor
```

`array_push` yalnızca pointer'ı kopyalıyordu. Kaynak kapsam kapanınca `parts`
(ve elemanları) serbest bırakılıyor → dizi öğesi dangle (`conditi`).

**Düzeltme:** `i8*` eleman diziye yazılırken `axiom_str_retain` çağrılır;
böylece dizi kendi referansını tutar, `array_str_free` de doğru bırakır.

---

## 3. Doğrulama

```bash
# C ve LLVM aynı JSON
$ ./axiom-scan scan sample.txt --rules rules.yar          # C
{"matches":[{"rule":"Suspicious_Powershell","pattern":"$a","offset":5,"length":15}]}
$ ./axiom-scan-llvm scan sample.txt --rules rules.yar     # LLVM
{"matches":[{"rule":"Suspicious_Powershell","pattern":"$a","offset":5,"length":15}]}
```

- `tests/test_axiom_scan.py` → 3 yeni test: **C ile LLVM çıktısı birebir eşit**
  (metin deseni, hex wildcard, kural sayısı).
- **20/20 örnek** artık LLVM ile derleniyor (CI istisnası kaldırıldı).

```
$ python3 -m pytest -q --no-header
763 passed in 472.78s
```

---

## 4. Ders

Bu hata iki tur boyunca görünmedi çünkü:
1. C arka ucu doğruydu → örnek "çalışıyor" görünüyordu.
2. `axiom-scan` testleri yalnızca C ile derliyordu.

**Kural (TODO'ya eklendi):** iki arka ucu olan her örnek için **parite testi**
zorunlu. Tek arka uçla yeşil test, sessiz yanlış sonucu gizler.
