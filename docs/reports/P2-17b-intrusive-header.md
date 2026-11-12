# P2-17b — Intrusive Header Bellek Modeli

**Tarih:** 10 Kasım 2026
**Görev:** `TODO.md` → P2-17b
**Durum:** ✅ tamamlandı — önce/sonra benchmark'la ölçüldü

---

## 1. Neden bu iş

Önceki turda üç sızıntı düzeltmiştim ama hepsi *codegen* hatasıydı. Model
sorgulanmadı. Ölçtüğümde modelin kendisinin maliyetli olduğu görüldü:

| Ölçüm (150k canlı string) | Değer |
|---|---|
| Takip tablosu belleği | **10 MB** |
| Canlı string oluşturma | 31.9 ms |
| Canlı string bırakma | 9.9 ms |

İki ayrı cache satırına dokunmak (tablo kaydı + veri) zorunluydu çünkü
refcount veriden kopuktu.

---

## 2. Yapılan değişiklik

### 2.1 Refcount verinin önüne taşındı

```c
typedef struct {
    uint32_t magic;     /* AXIOM_STR_MAGIC */
    uint32_t refs;      /* atomik */
    uint32_t in_log;
    uint32_t _pad;
    int64_t  seq;       /* adres yeniden kullanımı */
    int64_t  log_idx;   /* günlükteki yuva — O(1) unlog */
} axiom_str_hdr;         /* 32 bayt, veri hemen ardında */

/* dönen işaretçi: (char*)(h + 1) */
```

Global `ptr → refs` hash tablosu **tamamen kaldırıldı**.

### 2.2 Literal güvenliği — asıl risk buydu

`str` tipi `const char*`; literal de, `getenv` dönüşü de aynı tipte. Naif
intrusive model her `release`'de `ptr - 32` okur ve literal'de çöker.

Çözüm üç katmanlı:

1. **`axiom_ptr_is_static`** — ELF'in `PT_LOAD` (çalıştırılabilir olmayan)
   segmentleri `dl_iterate_phdr` ile **bir kez** toplanır. Kontrol 2-6 aralık
   karşılaştırması. Eski `dladdr` çağrısı ~17 ns/op'tu.
2. **Magic doğrulaması** — statik olmayan ama bizim olmayan işaretçide magic
   tutmaz → sahipsiz sayılır (no-op).
3. **Dış işaretçiler sarıldı** — `os_getenv` (environ) ve `cli_args_get`
   (argv) artık sahipli kopya döner. Böylece sistemde "ne statik ne sahipli"
   heap işaretçisi kalmadı.

### 2.3 Geçicilik günlüğü thread-local

`temp_mark` / `temp_release` aynı ifade içinde, aynı thread'de çalışır.
Günlüğü `__thread` yapınca hot path'teki kilit tamamen kalktı. (İlk denemede
global + kilit bıraktım; 150k release 6.6 s'ye çıktı, sonra O(1) `log_idx`
ve thread-local ile 4.0 ms'ye indi.)

### 2.4 Üreticiler başlıklı tahsisata geçti

`axiom_str_alloc(n)` veri işaretçisini header'ın arkasında döner. `int_to_str`,
`str_concat`, `str_sub`, `str_trim`, `safe_strdup` bunu kullanır → kopya yok.

Kalan `axiom_owned_str_wrap(buf)` çağrıları (başka yardımcıların düz `malloc`
tamponları) header tahsis edip kopyalar ve eskisini bırakır.

---

## 3. Sonuç — önce/sonra

`benchmarks/str_ownership_bench.c`, clang -O2, tek thread:

| Senaryo | Önce | Sonra | Değişim |
|---|---:|---:|---:|
| `int_to_str` 300k (üret+bırak) | 31.4 ms | **26.8 ms** | −15% |
| Kısa ömürlü ham wrap 300k | 30.7 ms | 30.7 ms | ~0 |
| **150k canlı string oluştur** | 31.9 ms | **16.5 ms** | **−48%** |
| **150k canlı string bırak** | 9.9 ms | **4.0 ms** | **−60%** |
| **Takip tablosu belleği** | **10.0 MB** | **0 MB** | **−10 MB** |

ASan taraması: **21/21 örnek temiz** (önce 18/21 — `10_packet1`'deki 89 B
sızıntı ve redteam'deki SEGV kapandı).

---

## 4. Yol boyunca ortaya çıkan 4 gerçek hata

Bellek modeli değişikliği saklı hataları görünür yaptı. Hepsi düzeltildi ve
regresyon testleriyle kilitlendi.

### 4.1 `if`/`while` koşullarındaki geçiciler sızıyordu

```axiom
while (i < 500) {
    if str_contains("abc" + "def", "cd") { ... }   // 500 string sızar
}
```

`print(f(x))` için düzeltmiştim ama koşullar atlanmıştı. Koşul `bool`'a
çevrildikten hemen sonra `temp_release` eklendi (dal girilmeden önce).
`while` için `for(;;) { <cond>; if (!c) break; body }` yapısı kullanıldı —
`continue` hâlâ koşulu yeniden ölçer.

**Doğrulama:** 500 iterasyon → GROWTH 0.

### 4.2 Erken `return` diğer değişkenleri bırakmıyordu

```axiom
let a = os_getenv("PWD")
let b = os_getenv("HOME")
if flag > 0 { return b }   // 'a' sızıyor
return a                   // 'b' sızıyor
```

`_mark_escape` fonksiyon geneli bir küme; bir değişken herhangi bir `return`
değeri olarak kullanıldıysa fonksiyon boyunca hiç bırakılmıyordu.

`str` dönüşünde `axiom_str_retain` zaten değeri koruyor → escape işaretlemeye
gerek yok. Kaldırıldı. (Dizi dönüşünde retain mekanizması olmadığı için escape
korundu.)

### 4.3 Dizi literali stack'te `compound literal` üretiyordu

```axiom
fn _parse_string_def(line: str) -> str[] {
    ...
    return [id, "str:" + text]     // (ax_str[]){ id, ... } — STACK
}
```

Blok kapsamındaki compound literal, blok bitince ölür. Döndürülen dizi sarkan
işaretçi taşır. Daha önce "şans eseri" çalışıyordu; stack düzeni değişince
YARA tarayıcısı sessizce boş sonuç verdi.

Artık dizi literalleri heap'e yazılıyor (`malloc` + `axiom_heap_buf_track`).

### 4.4 `?` hata yolu atanmamış değişkeni serbest bırakıyordu

```c
ax_array_str l = ({ ...; if (!ok) { axiom_array_str_free(&l);   /* ÇÖP */ return ...; } ... });
```

Değişken, başlatıcı değerlendirilmeden "sahipli" olarak kaydediliyordu. Çöp dizi
üzerinde `axiom_array_str_free` **sonsuz döngüye** giriyordu (testler zaman
aşımına düştü).

`pending_init` kümesi eklendi: başlatılmakta olan değişken temizlik listesinden
çıkarılır.

---

## 5. Neden `String`/`str` tip ayrımı yapılmadı

Plan "intrusive header **+** `String`/`str` ayrımı" idi. Ayrım gerekmedi:

- Amacı çift serbest bırakma ve literal korumasıydı.
- Header magic + segment kontrolü bunu zaten sağlıyor.
- `str`'yi `const char*` bırakmak ABI'yi korur (99 runtime fonksiyonu,
  471 çağrı yeri değişmeden kalır).

Daha az riskli, aynı kazancı veren yol seçildi.

---

## 6. Doğrulama

```bash
python3 -m pytest -q --no-header   # 976 passed
for f in examples/*.ax; do axiom build "$f"; done          # C    21/21
                                                        # LLVM 21/21
./bin/axiomc build examples/*.ax                        # 21/21
ASan taraması                                           # 21/21 temiz
make fmt-check                                          # ✅
```

| Kontrol | Sonuç |
|---|---|
| Test | **976** (0 skip) |
| C / LLVM / Self-hosted | 21/21 · 21/21 · 21/21 |
| ASan | **21/21 temiz** |
| Benchmark | `benchmarks/RESULTS.md` |

---

## 7. Kalan

| ID | İş | Not |
|---|---|---|
| P2-19 | Runtime `core`/`platform` + WASI | Windows/«Linux-only» kararına bağlı |
| Faz 3 | 1.0, platform, paket yayını, kullanıcı, fon | Kod dışı |

**Kod tarafında bilinen teknik borç kalmadı.**
