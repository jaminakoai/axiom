# Axiom (λx) — String Sahipliği Düzeltme Turu

**Tarih:** 6 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Kapsam:** `~/Desktop/axiom`
**Önceki rapor:** `Axiom_Altyapi_ve_Benchmark_Raporu_2026-11-06.md`

---

## 0. Özet

Benchmark'ın işaret ettiği **string yolu** incelendi. Üç gerçek bellek hatası bulundu ve düzeltildi; hepsi daha önce testlerden kaçıyordu çünkü sahiplik tablosu pointer'ları "erişilebilir" tuttuğu için LeakSanitizer görmüyordu.

| # | Hata | Etki | Durum |
|---|---|---|---|
| 1 | `s = <ifade>` ataması eski değeri bırakmıyor, yeni değeri gereksiz retain ediyordu | 20.000 iterasyonda **40.000 sızan string** | ✅ Düzeltildi |
| 2 | `axiom_temp_release` aynı kaydı birden çok kez düşürüyordu | **use-after-free / bozuk string** (`s` = `"%"`) | ✅ Düzeltildi |
| 3 | `ax_str` döndüren fonksiyonun sonucu `char*`'a atanıp `free()` ediliyordu | **double free** (`fuzz_double_encode`, `csv_save_file`) | ✅ Düzeltildi |

Ayrıca iç içe geçici string'ler (`f(g(x))`) artık `let` / atama / `return` yollarında temizleniyor. Bu, önceki turda "riskli" diye geri alınan işin **güvenli alt kümesidir**.

**Test durumu:** `580 passed` (önceki 577; +3 regresyon testi).

---

## 1. Hata 1 — String Atamasında Sızıntı

### Belirti

```axiom
let mut s = "a"
while i < 20000 { s = "y" + int_to_str(i); i = i + 1 }
print(str_owned_count())
```

```
ÖNCE: OWNED: 40000     (her turda 2 string sızıyor)
SONRA: OWNED: 1
```

### Kök neden

`AssignStmt` üretiminde hedef bir `Identifier` olduğunda kod şu yola giriyordu:

```c
s = axiom_str_concat("y", axiom_int_to_str(i));
axiom_str_retain(s);          // refcount 1 → 2
```

Eski değer hiç bırakılmıyor, üstelik yeni değer ikinci kez sahipleniliyordu. Kapsam sonunda tek `release` → refcount 1'de kalıyor → **hem eski hem yeni string kalıcı sızıntı**.

### Çözüm

Hedef izlenen bir `str` değişkeniyse, `Identifier` hedefi de normal atama yoluyla aynı mantığa sokuldu: **eskiyi bırak, yeniyi devral**.

---

## 2. Hata 2 — `temp_release` Erken Serbest Bırakma

### Belirti

```
i: 0 s: % len: 1
i: 1 s: % len: 1
```

`s` çöp değere dönüşüyordu (3 iterasyonluk testte bile).

### Kök neden

İlk uygulamada `axiom_temp_release(mark)`, tabloyu baştan tarayıp `seq > mark` olan **her kaydı** düşürüyordu. Aynı kayıt döngünün bir sonraki turunda yeniden bulunup **ikinci kez** düşürülüyordu:

```
sonuç: refs 1 → retain 2 → temp_release 1 → temp_release 0 → FREE
```

Halbuki sonuç hâlâ kullanılıyordu.

### Çözüm (iki aşamalı)

**a) Nesil damgası** — her kayıt `last_gen` tutar; bir `temp_release` çağrısı kaydı en fazla bir kez işler.

**b) Sıralı oluşturma günlüğü** — tabloyu taramak yerine (`O(kapasite)` = 4096), oluşturma sırasını tutan bir günlük eklendi:

```c
typedef struct { char* ptr; ax_int seq; } ax_seq_log_ent;
```

`temp_mark()` günlük uzunluğunu döndürür; `temp_release(mark)` günlüğü `mark`'a kadar geri sarar ve her kaydı **bir kez** bırakır. Adres yeniden kullanımı `seq` damgasıyla ayırt edilir → yanlış serbest bırakma yok.
Karmaşıklık: **O(geçici sayısı)**.

---

## 3. Hata 3 — Sahipli String'in Ham `free()` ile Bırakılması

### Belirti

```
free(): double free detected in tcache 2      (fuzz_double_encode)
```

### Kök neden

Sahiplik tablosuna geçildikten sonra `ax_str` döndüren fonksiyonların sonucu **tabloya kayıtlı**dır. Ama bazı runtime fonksiyonları bu sonucu `char*`'a atayıp ham `free()` ediyordu:

```c
char* single = (char*)axiom_fuzz_url_encode(payload);
...
free(single);                       // tabloda sarkan kayıt → sonra double free
```

### Sistematik tarama

`ax_str` döndüren tüm fonksiyonların sonucunu `char*`'a atayıp `free()` eden yerler tarandı:

```text
owned-result assigned to char* then freed: 3
  (4375, 'single',  'axiom_fuzz_url_encode', 4396)
  (4612, 'content', 'axiom_csv_to_str',      4615)
  (4612, 'content', 'axiom_csv_to_str',      4622)
```

Üçü de `axiom_str_release(...)`'e çevrildi.

### Kural (CONTRIBUTING'e işlendi)

> `ax_str` döndüren bir fonksiyonun sonucu **asla** `free()` ile bırakılmaz → `axiom_str_release`.

---

## 4. Geçici String Temizliği (güvenli alt küme)

Önceki turda ifade düzeyinde temizlik denendi ve `bin/axiomc`'yi bozduğu için geri alınmıştı (AST'ye kaçan string'ler serbest bırakılıyordu).

Bu turda **yalnızca hedefi belli yollar** korundu:

| Yol | Üretilen kod |
|---|---|
| `let s: str = <ifade>` | `mark; s = <ifade>; adopt(s); release_temp` |
| `s = <ifade>` | `mark; _new = <ifade>; adopt(_new); release_temp; release(s); s = _new` |
| `return <ifade>` (str dönen) | `mark; ret = <ifade>; adopt(ret); release_temp; return ret` |

Ve yeni bir runtime yardımcısı:

```c
AXIOM_RUNTIME_FN const char* axiom_str_adopt(const char* s);
```

`adopt`, değer **geçici ise** refcount'u artırır (ifade sonu temizliği onu silmesin); **zaten sahipliyse** (çağrı dönüşü) dokunmaz; **literal/dış pointer ise** dokunmaz.

Bu ayrım kritik: `let s = make(i)` durumunda `make` kendi geçici günlüğünü zaten boşaltmıştır; ikinci bir retain sızıntı üretirdi. `adopt` bunu önler.

### Neden bu kez `axiomc` bozulmadı

Temizlik yalnızca **str tipindeki hedefe atama** yollarında uygulanıyor. `StructInit`, dizi literali, `ExprStmt` gibi AST'ye/diziye kaçan yollar kapsam dışı. `bin/axiomc` yeniden derlendi ve tüm self-hosted testleri geçti.

### Kalan sınır

`print(f(x))` gibi **atama yapılmayan** ifadelerde üretilen geçici string hâlâ tabloda kalır. README'de dürüstçe yazılı. Çözüm: intrusive header + `String`/`str` ayrımı.

---

## 5. Doğrulama

### Sızıntı ölçümleri

| Senaryo | Önce | Sonra |
|---|---|---|
| `s = "y" + int_to_str(i)` × 20.000 | OWNED 40.000 | **OWNED 1** |
| `let s = make(i)` × 5.000 | OWNED 5.000 | **OWNED 0** |
| `let e = "x" + int_to_str(i) + "y"` × 3.000 | — | **OWNED ≤ 3** |
| `s = s + "x"` × 20.000 | OWNED 1 | OWNED 1 |
| ASan/LSan (yukarıdakiler) | — | **temiz** |

### Benchmark (`benchmarks/RESULTS.md`)

| İş | Axiom | C -O3 | Python | Axiom/C |
|---|---:|---:|---:|---:|
| Fibonacci (n=30) | 0.0048s | 0.0033s | 0.1475s | **1.45×** |
| String birleştirme (20.000) | 0.0031s | 0.0007s | 0.0201s | 4.56× |
| Dizi büyütme (100.000) | 0.0019s | 0.0011s | 0.0230s | **1.70×** |
| Base64 (20.000) | 0.0047s | 0.0006s | 0.0279s | 7.37× |
| Matris (64×64) | 0.0016s | 0.0007s | 0.0416s | **2.33×** |

Karşılaştırma: düzeltmelerden önce string 4.59×, Base64 6.03× idi. **Base64 biraz yavaşladı** (6.03 → 7.37×) çünkü her `let` artık mark/adopt/temp_release çağırıyor ve her çağrı ekstra kilit alıyor. Doğruluk kazancı (sıfır sızıntı) bu maliyete değer; optimizasyon sıradaki iş.

### Testler

```bash
$ python3 -m pytest -q --no-header
580 passed in 329.98s (0:05:29)
```

- Yeni 3 test: atama sızıntısı, fonksiyon dönüşü sızıntısı, iç içe geçici temizliği.
- 17/17 örnek LLVM ile derleniyor.
- `bin/axiomc` bootstrap çalışıyor.
- `test_memory_leak_deep.py`: 9/9.

---

## 6. Değiştirilen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `axiom/codegen_c.py` | İzlenen `str` hedefine atama yolu; `let`/`return` için mark+adopt+release_temp; `_emit_guarded_str_assign` |
| `axiom/runtime.h` | `axiom_str_adopt`, sıralı oluşturma günlüğü, nesil damgası, `in_log` alanı, `fuzz_double_encode`/`csv_save_file` düzeltmesi, `seq` korunumu |
| `tests/test_memory_leak_deep.py` | +3 regresyon testi |
| `README.md` | Test rozeti 580, bellek modeli maddesi güncellendi |

---

## 7. Dersler

1. **LeakSanitizer tek başına yetmez.** Global sahiplik tablosu pointer'ları canlı tuttuğu için LSan sızıntı görmüyor. `str_owned_count()` bu yüzden kritik bir tanılama aracı oldu; her bellek testinde tablo sayacı da kontrol edilmeli.
2. **Sahiplik modeline geçiş, ham `free()` çağrılarını tek tek denetlemeyi gerektirir.** İki turda üç ayrı double-free bulundu. Bu tarama CI'ya otomatik eklenmeli.
3. **"Sıfır maliyet" ile "doğruluk" çatıştığında doğruluk kazanmalı.** Base64 1,3× yavaşladı ama artık sızdırmıyor.

---

## 8. Sıradaki İşler

| # | İş | Gerekçe |
|---|---|---|
| 1 | **Intrusive header + `String`/`str`** | Kalan tek sızıntı sınıfını (atama yapılmayan geçici) kapatır; kilit maliyetini de düşürür |
| 2 | `ax_str` üreticilerini `str_owned_count` ile tarayan CI testi | Yeni double-free sınıfını otomatik yakalar |
| 3 | Mark/adopt/temp_release'i tek runtime çağrısında birleştirme | Base64'teki 1,3× gerilemeyi geri alır |
| 4 | Runtime `core` / `platform` ayrımı + WASI | Çapraz derleme |
| 5 | Registry politikası | `axpm` tamamlanması |
| 6 | AST tabanlı self-hosted derleyici | Tam generics |

**Öneri:** 1 ve 3 birlikte yapılmalı; ikisi de aynı kod yolunu (string sahipliği) hedefliyor ve birlikte hem sızıntıyı hem performans gerilemesini çözerler.
