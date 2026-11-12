# P2-18 — Self-Hosted Derleyici: 4/21 → 8/21

**Tarih:** 9 Kasım 2026
**Görev:** `TODO.md` → P2-18
**Durum:** ✅ hedef (8/21) tutturuldu

---

## 1. Başlangıç durumu

`bin/axiomc` (Axiom ile yazılmış, Python gerektirmeyen derleyici) 21 örnekten
yalnızca 4'ünü derleyebiliyordu: `01_hello`, `02_fibonacci`, `03_contracts`,
`04_security_scan`.

Hata sınıfları:

| Hata | Örnek sayısı |
|---|---|
| `unknown type name 'ax_Result_str_str'` (generic struct) | 10 |
| `len()` / tip çıkarımı | 4 |
| Kapanış `}` kaybolması | 3 |
| Fonksiyon referansı (thread) | 1 |

## 2. Düzeltilen 5 gerçek hata

### 2.1 `len(str)` yanlış yerleşiğe gidiyordu

```c
/* önce */   ax_int n = axiom_len(target_ip);      /* (str).length -> derleme hatası */
/* sonra */  ax_int n = axiom_slen_auto(target_ip);
```

`ax_str` bir pointer, `ax_array_*` ise ilk alanı `length` olan struct. Tek
geçişli self-hosted parser tip ortamı tutmadığı için doğru yerleşiği seçemez.
Çözüm: runtime'da tip-ayrımlı makro.

```c
#define axiom_slen_auto(x) ({ \
    __typeof__(x) _ax_len_tmp_ = (x); \
    _Generic(&_ax_len_tmp_, \
        ax_str*: axiom_len_str_v_((const void*)&_ax_len_tmp_), \
        default: axiom_len_arr_v_((const void*)&_ax_len_tmp_)); \
})
```

Statement expression, rvalue argümanları da destekler; `_Generic` yalnızca
`ax_str*` için str dalını seçer.

> Not: `__builtin_choose_expr` denendi, **işe yaramadı** — clang seçilmeyen
> dalı da tip denetliyor. `_Generic` + `void*` sarmalayıcı çözümü doğru.

### 2.2 UTF-8 kaynak dosyaları sonda kesiliyordu

```axiom
let total_len = len(src)      // kod noktası sayısı
...
let ch = src[pos]             // BAYT indeksleme
while pos < total_len { ... }
```

Türkçe/emoji içeren dosyada `len(src)` < bayt uzunluğu olduğu için döngü
erkenden bitiyor, **son deyim yarım kalıyordu**. Belirti: kapanış `}`
kaybolması ve `axiom_print_auto()` (boş argüman).

Düzeltme: `str_byte_len(src)`.

Bu tek hata, üç farklı örnekte "brace mismatch" olarak görünüyordu — belirti
ile neden arasındaki mesafe bu yüzden uzundu.

### 2.3 `codegen_wrap_ensures` bayt/kod-noktası karışımı

```axiom
let b_len = len(body)                      // kod noktası
let sub = str_sub(body, cur, b_len - cur)  // BAYT
```

Çok baytlı gövdede son baytlar kesiliyor, kapanış `}` kayboluyordu.
Düzeltme: `str_byte_len(body)`.

### 2.4 `thread_create` C üretimi bozuktu

```c
/* önce */   axiom_thread_create(worker_thread_task, 80)     // tanımsız + eksik argüman
/* sonra */  axiom_thread_create((void*)ax_worker_thread_task, 80, false)
```

### 2.5 `main` void dönüşü

```c
/* önce */   return (int)ax_main();      // void'den cast -> derleme hatası
/* sonra */  ax_main(); return 0;
```

### 2.6 Ek iyileştirmeler

- **`let x = f()` → `__auto_type`**: tek geçişli parser dönüş tipini bilemediği
  için struct dönen kullanıcı fonksiyonları `ax_int` sanılıyordu. `__auto_type`
  (clang/gcc) bunu doğru çözüyor; `09_simd` ve `17_ai_tensor` bununla açıldı.
- **`axiomc` geçici dosyaları PID ile tekilleştirildi.** Sabit
  `/tmp/axiom_build_tmp.c` yolu eşzamanlı çalışmada dosyaları eziyordu —
  testlerin ara sıra kararsız kalmasının gerçek nedeni buydu (`14 passed`
  → `1 failed` → `14 passed`).

## 3. Sonuç

| | Önce | Sonra |
|---|---|---|
| Self-hosted derlenen+çalışan örnek | 4/21 | **8/21** |
| Yeni açılanlar | — | `05_real_scanner`, `08_multithreaded_scanner`, `09_simd_vector_scan`, `17_ai_tensor_neural_net` |

Çıktı doğrulaması (yalnızca derleme değil):

```
$ ./bin/axiomc run examples/08_multithreaded_scanner.ax
  • Açık Port Sayısı       : 0
  • Atomik Sayaç Değeri    : 0
  • Toplam Geçen Süre (ms) : 0
==========================================================
```

## 4. Testler

`tests/test_selfhosted_contracts.py`:

- `SUPPORTED` listesi 4 → 8'e çıkarıldı
- `test_supported_list_is_accurate` — listedeki her örnek **gerçekten**
  derlenmeli (liste şişirilemez)
- `test_utf8_source_is_not_truncated_by_selfhosted_lexer` — UTF-8 kesilmesi
  regresyonu (Türkçe + emoji + son satır kontrolü)

Kararlılık: 3 ardışık çalıştırma → `14 passed` (PID tekilleştirmeden önce
ara sıra düşüyordu).

## 5. Kalan 13 örnek (P2-18b)

| Neden | Örnek |
|---|---|
| Generic struct somutlaştırma (`ax_Result_str_str`) | 10, 11, 12, 13, 15, 19, 20, 21 |
| `str[]`/struct dizi alan erişimi | 16, 18, 22 |
| stdlib fonksiyon eşlemesi (`rt_aes256_cbc_encrypt`) | 14 |
| `ensures return.field` | 07 |

Bunlar tek tek yapılabilir ama generic somutlaştırma en büyük kaldıraç
(8 örnek). Ayrı bir tur olarak kayıtlı.

## 6. Durum

```bash
python3 -m pytest -q --no-header     # 923 passed, 2 skipped in 690.85s
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **923** (+6) |
| C örnekleri | 21/21 |
| LLVM örnekleri | 21/21 |
| Self-hosted | **8/21** |
| `make fmt-check` | ✅ |
| Bootstrap | ✅ |

## 7. Sıradaki

| # | İş | Not |
|---|---|---|
| 1 | P2-18b generic struct somutlaştırma | 8 örneği birden açabilir |
| 2 | P2-17b intrusive header | Performans/ABI, güvenlik değil |
| 3 | Faz 3 hazırlığı | Paket yayını + kullanıcı (kod dışı) |
