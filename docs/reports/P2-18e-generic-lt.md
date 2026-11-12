# P2-18e — `x < y` Generic Çakışması ve Struct Dizi `capacity`

**Tarih:** 9 Kasım 2026
**Görev:** `TODO.md` → P2-18e
**Durum:** ✅ self-hosted **12/21 → 15/21** — Faz 1 hedefinin (8/21) iki katı

---

## 1. Sonuç

| | P2-18c | P2-18d | **P2-18e** |
|---|---|---|---|
| Self-hosted | 11/21 | 12/21 | **15/21** |
| Yeni | 12, 14, 19 | 13 | **11, 18, 20** |

Üç örnek de yalnızca derlenmiyor — Python sürücüsüyle **birebir aynı çıktıyı**
veriyor (parite testi).

---

## 2. En kritik hata: `x < y` generic sanılıyordu

### Belirti

```c
/* kaynak */  if size < 0 { return result_err_int("...") }
/* üretilen */ if (axiom_size(size)) { }
```

Gövde tamamen kayboluyor, sonraki fonksiyona atlıyor. Tanılama çok zordu
çünkü hata başka satırda "expected '}'" olarak görünüyordu.

### Kök neden

`parse_primary` içindeki generic taraması:

```axiom
if next_t.kind == "<" {
    while scan < len(toks) and not match_k(toks, scan, ">"):
        ...
```

`size < 0 { return result_ok<int>(size) }` dizisinde `<` gördükten sonra
`>` arıyor — ve **sonraki ifadedeki** `result_ok<int>`in `>`ını buluyor.
Sonra `after_t == "("` olduğu için "generic fonksiyon çağrısı" sanıp
`ax_size(...)` üretiyor.

### Neden önceden görünmedi

İzole testlerde (`if size < 0 { return 2 }`) sonraki ifadede `>` yoktu; hata
yalnızca bir **generic çağrı** aynı kapsamda olduğunda tetikleniyordu.
`19` çalışıyordu çünkü orada `result_ok<int>` başka fonksiyondaydı.

### Düzeltme

Tarama artık bir **ifade sınırına** çarparsa vazgeçer:

```axiom
if g_k == ";" or g_k == "{" or g_k == "}" or g_k == "(" or g_k == ")"
   or g_k == "EOF" or g_k == "ARROW" or g_k == "=" or g_k == "+"
   or g_k == "-" or g_k == "*" or g_k == "/" or g_k == "==" or g_k == "!=":
    is_generic_like = false
    break
```

---

## 3. Struct dizi tipinde `capacity` yoktu

```c
/* önce */  typedef struct { ax_int length; ax_Route* data; } ax_array_Route;
/* sonra */ typedef struct { ax_int length; ax_int capacity; ax_Route* data; } ax_array_Route;
```

`axiom_array_push` makrosu `.capacity` kullanıyor; struct dizisi olan her
program derlenemiyordu. Alan eklendi (runtime `ax_array_*` ile aynı düzen).
Bu tek satır `18_web_api_framework`'ı açtı.

---

## 4. `result_err_with<T>` argüman ayrımı

```c
/* önce */  ((ax_Result_float_str){ .is_ok = false, .value = (path), 0.0), .error = ... })
/* sonra */  ((ax_Result_float_str){ .is_ok = false, .value = (0.0), .error = (axiom_str_concat("sayi degil: ", path)) })
```

Naif `str_index_of(args_code, ", ")` **iç içe çağrının** virgülünü ayırıcı
sanıyordu. `split_top_level_args` eklendi: parantez/köşeli parantez derinliği
sayılır, string içindeki virgüller atlanır.

## 5. `result_ok<float>`

`float` tipi `int` dalına düşüyordu (`Result<float,str>` beklenirken
`Result<int,str>` dönüyordu). Artık `float` için de struct literali.

---

## 6. Kalan 6 örnek

| Örnek | Engel | Not |
|---|---|---|
| `07` | `ensures return.field >= 0` | Alan erişimli ensures |
| `10` | `str[]` alan erişimi (`ax_array_int` ↔ `ax_array_str`) | Tip çıkarımı |
| `16` | `str[]` alan + struct dizi eleman erişimi | Aynı sınıf |
| `21` | `pcap_open_reader` benzeri eşleme eksik | Kolay |
| `22` | generic struct literal artığı (`((ax_Result_T_E){...})`) | Orta |
| `15` | tip listesi parametreleri (redteam, kapılı) | Düşük öncelik |

Tahmin: `21` + `22` bir sonraki turda açılabilir (17/21).

---

## 7. Durum

```bash
python3 -m pytest -q --no-header   # 945 passed, 2 skipped
bin/axiomc → 15/21    C → 21/21    LLVM → 21/21
```

| Kontrol | Sonuç |
|---|---|
| Test | **945** (+4) |
| Self-hosted | **15/21** (hedef 8/21) |
| Parite testi | 15 örnek, 17 test |
| `make fmt-check` | ✅ |
| Bootstrap | ✅ |
