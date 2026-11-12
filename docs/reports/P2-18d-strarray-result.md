# P2-18d — Dizi Literali Tipi, `?` Dönüşü ve `result_ok<T>`

**Tarih:** 9 Kasım 2026
**Görev:** `TODO.md` → P2-18d
**Durum:** 🟡 kısmi — self-hosted **11/21 → 12/21** (hedef 15/21)

---

## 1. Dürüst özet

Hedef 15/21 idi, ulaşılan **12/21**. Ama düzeltilen 4 hata, kalan 9 örneğin
bir kısmının önündeki gerçek engellerdi ve ikisi genel sınıf hatalarıydı
(her dizi literali, her `?` kullanımı).

---

## 2. Düzeltilen 4 gerçek hata

### 2.1 Her dizi literali `int[]` üretiliyordu

```c
/* önce */  ((ax_array_int){ .length = 7, .data = (ax_int[]){ "axiom_fuzzer", "--target", ... } })
/* sonra */ ((ax_array_str){ .length = 7, .data = (ax_str[]){ "axiom_fuzzer", "--target", ... } })
```

Elemanlar metin literal olduğu halde `int[]` üretildiği için C derlemesi
başarısızdı. Artık **tüm elemanlar metinse** `ax_array_str`/`ax_str[]`.
Boş dizide açık tip (`let e: str[] = []`) kullanılır.

### 2.2 `str[]` bekleyen çağrı bağlamı

```axiom
csv_add_row(report, ["TIMESTAMP", "TARGET_URL", "RESULT"])
```

Dizi literalinde elemanlar `__auto_type` değişkenler olabiliyor; `is_str_expr`
onları tanımaz. Bu yüzden çağrı bağlamı da kullanılır: `csv_add_row`,
`cli_set_args`, `os_exec_argv`, `json_build_object` gibi `str[]` alan
yerleşiklerde literal metin dizisine çevrilir (`expects_str_array`).

### 2.3 `?` farklı Result tipleri arasında taşınamıyordu

```axiom
fn read_lines(path: str) -> Result<str[], str> {
    let content = read_file(path)?    # Result<str,str>
    ...
}
```

Err durumunda `Result<str,str>` döndürülüyordu; fonksiyonun tipi
`Result<str[],str>` — C'de struct'lar farklı, derleme hatası.

Çözüm: parser yer tutucu bırakır, `parse_function` gerçek tipi doldurur.

```c
if (!(content_ax_try_684).is_ok) {
    <kapsam defer'leri>
    ax_Result_str_array_str __ax_err;
    memset(&__ax_err, 0, sizeof(__ax_err));   /* ax_array_str: {0,NULL} */
    __ax_err.is_ok = false;
    __ax_err.error = content_ax_try_684.error;
    return __ax_err;
}
```

`memset` sıfırlaması `ax_array_str` için geçerli boş dizidir (length=0,
data=NULL), `str` için NULL'dır.

### 2.4 `result_ok<T>` bilinmeyen T

```axiom
return result_ok<Config>(Config { name: name, port: port })
```

`Config` için hazır makro yok; parser `int` örneği üretiyordu. Artık her T için
doğrudan struct literali:

```c
((ax_Result_Config_str){ .is_ok = true, .value = (...), .error = "" })
```

Aynısı `result_err_with<T>` için de (msg ve empty ayrıştırılarak).

### 2.5 Yan bulgu: `axiom_str_split` `str` sanılıyordu

`is_str_expr("axiom_str_split(...)")` → `axiom_str_` öneki nedeniyle `true`.
Ama `str_split` **dizi** döner. Sonuç: `ax_str lines = axiom_str_split(...)`
geçersiz C. İstisna eklendi.

---

## 3. Parite testi kararlılığı

`test_selfhosted_matches_python_driver` tam pakette ara sıra düşüyordu (~%5).
Neden: `08_multithreaded_scanner` "Geçen Süre (ms)" satırı koşulara göre
0/1 ms farklı.

Normalizasyona iki kural eklendi: `(ms)` içeren satırlar ve "süre" içeren
satırlar tamamen `MS_LINE`/`SURE_LINE` ile değiştirilir. 8 ardışık tam paket
çalıştırması temiz.

---

## 4. Sonuç

| | P2-18 | P2-18b | P2-18c | **P2-18d** |
|---|---|---|---|---|
| Self-hosted | 8/21 | 8/21 | 11/21 | **12/21** |
| Yeni | 05,08,09,17 | — | 12,14,19 | **13** |

```bash
python3 -m pytest -q --no-header   # 941 passed, 2 skipped
bin/axiomc → 12/21    C → 21/21    LLVM → 21/21
```

---

## 5. Kalan 9 örnek ve engelleri

| Örnek | Engel | Zorluk |
|---|---|---|
| `07` | `ensures return.field >= 0` | Orta |
| `10`, `21` | `str[]` alan erişimi | Orta |
| `11` | `axiom_tls_id` (struct alanı değişken) | Orta |
| `16` | `ax_array_YaraRule.capacity` | Kolay? |
| `18` | `ax_array_Route.capacity` | Kolay? |
| `20` | `if size < 0` → `ax_size(...)` (generic sanma) | **Kolay, yüksek etki** |
| `22` | `((ax_Result_T_E){...})` çöp satır | Orta |

### 5.1 En değerli tek düzeltme

**`x < y` karşılaştırmasının generic sanılması.** `if size < 0` ifadesi
`size<0>` gibi ayrıştırılıp `ax_size(...)` üretiyor. Bu tek hata `20`'yi
tek başına kapatabilir ve generic algılamayı sağlamlaştırır.

Doğru düzeltme: generic dalına girmeden önce `>` token'ından sonra `(` veya
`{` gelip gelmediğini kontrol etmek (şu an `match_k(toks, scan, ">")` var ama
görünüşe göre bir yol daha var).

---

## 6. Sıradaki

| # | İş | Beklenti |
|---|---|---|
| 1 | **P2-18e** `x < y` generic-çakışması | `20` + sağlamlık |
| 2 | Struct dizi alanında `.capacity` | `16`, `18` |
| 3 | `ensures return.field` | `07` |
| 4 | P2-17b intrusive header / Faz 3 | — |
