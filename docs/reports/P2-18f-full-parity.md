# P2-18f + P2-20 — Tam Parite ve Skip'lerin Kapatılması

**Tarih:** 10 Kasım 2026
**Görevler:** `TODO.md` → P2-18f, P2-20
**Durum:** ✅ **self-hosted 15/21 → 21/21** · **976 test, 0 skip**

---

## 1. Sonuç tablosu

| Arka uç | Derlenen | Parite (Python sürücüsüyle) |
|---|---|---|
| C | 21/21 | — (referans) |
| LLVM | 21/21 | — |
| **Self-hosted (`bin/axiomc`)** | **21/21** | **20/21 birebir** |

Redteam örneği (`15`) ayrı testte: çalışıyor, ama çıktısı **rastgele beacon**
içerdiği için birebir karşılaştırılamaz (yalnız derleme + çalışma doğrulanır).

```bash
python3 -m pytest -q --no-header
# 976 passed in 795.02s          <- 0 skipped
```

---

## 2. Düzeltilen 9 gerçek hata

### 2.1 Çoklu `requires` / `ensures` yutuluyordu

```axiom
fn pcap_record_packet(h: int, hex: str) -> bool
    requires h > 0
    requires len(hex) > 0        # <-- buradan sonrası kayboluyordu
{
```

Parser tek cümle varsayıyordu; ikinci `requires` "tanınmayan token" olarak
gövdeye sızıyor ve **sonraki fonksiyonun tamamı** önceki fonksiyonun içine
giriyordu. Belirti: `ax_pcap_open_reader` derlenmemiş ama çağrılıyor;
`pcap.ax`'teki 6 fonksiyonun 5'i bozuk.

Düzeltme: `while` döngüsü + `(a) && (b)` birleştirme.

### 2.2 `import "std:net:http.ax"` → `http.ax.ax`

```axiom
if not str_ends_with(resolved_mod_path, ".ax") { resolved_mod_path += ".ax" }
```

Uzantı zaten varsa tekrar eklenmemeli. Yoksa dosya bulunamaz ve **sessizce
atlanır** — `07_http_banner_grabber` bu yüzden `axiom_http_get` tanımsız diyordu.

### 2.3 `pcap_` / `fim_` / `forensics_` önekleri std sarmalayıcılarını gölgeliyordu

`map_builtin_func` bu önekleri doğrudan runtime'a eşliyordu:

```c
axiom_pcap_open_reader(...)   /* runtime'da YOK */
```

Oysa std'de `pcap_open_reader` adlı bir **sarmalayıcı** var ve içinde
`rt_pcap_open_file` çağırıyor. Kısa devre kaldırıldı; sarmalayıcı normal
fonksiyon olarak derleniyor.

### 2.4 Tip yayılımı yoktu (en geniş etki)

```c
/* önce */  ax_int p = ((paths).data[i]);      /* str dizisinden */
/* sonra */ ax_str p = ((paths).data[i]);
```

Codegen'e **sabit-nokta tip çıkarımı** eklendi:

| Aşama | Kaynak |
|---|---|
| Tohum | `str` ve `str[]` parametreleri |
| Tohum | struct'lardaki `str`/`str[]` alanları |
| Öğrenme (×4) | `ax_str X = ...;` ve `ax_int X = <bilinen str>;` |
| Düzeltme | `ax_int` → `ax_str` / `ax_array_str` |

Ek olarak iki harita:

- **`arrmap`**: struct dizi alanı → eleman tipi (`(rule).selections` →
  `SigmaFieldMatch`); struct dizi **parametreleri** de dahil.
- **`fnret`**: `T[]` döndüren fonksiyon → eleman tipi (`yara_ruleset_scan` →
  `YaraMatch`).

### 2.5 `__auto_type X = axiom_str_split(...)`

```c
__auto_type lines = axiom_str_split(text, "\n");
ax_int raw_line = ((lines).data[i]);     /* yanlış */
```

Dizi taban adı haritası (`strarrs`) eklendi: `str_split`/`list_dir` sonuçları
metin dizisi sayılır.

### 2.6 `main() -> Result<int, str>` desteği yoktu

```c
/* önce */  return (int)ax_main();     /* struct'tan int cast */
/* sonra */
__auto_type r = ax_main();
if (!r.is_ok) { fprintf(stderr, "[AXIOM HATA] %s\n", r.error); return 1; }
return (int)r.value;
```

Python sürücüsüyle aynı semantik: Ok → exit 0, Err → stderr + exit 1.

### 2.7 `rewrite_unknown_calls` `axiom_*` çağrılarını bozuyordu

Fonksiyon yalnız `ax_` önekini tanıyordu; `axiom_str_concat` gibi zaten doğru
çağrıları `ax_` sanıp `ax_str_concat`'a çeviriyordu. İki öneki birlikte
tarayacak şekilde yeniden yazıldı.

### 2.8 Struct dizi alanı elemanı ve `T[]` fonksiyon sonucu

`(rule).selections.data[i]` ve `yara_ruleset_scan(...).data[i]` `ax_int`
sanılıyordu. `arrmap`/`fnret`/`localmap` üçlüsü bunu çözdü.

### 2.9 Uyarı gürültüsü parite çıktısını kirletiyordu

`axiomc`, C derleyicisinin `-Wunused-variable` uyarılarını stderr'e yazıyordu;
`07` bu yüzden "farklı" görünüyordu. `-Wno-unused-*` eklendi.

---

## 3. P2-20 — Skip'ler kapatıldı

| Önce | Sonra |
|---|---|
| Redteam 17 test yalnız `AXIOM_ENABLE_REDTEAM=1` ile | **Varsayılan çalışır**; `AXIOM_SKIP_REDTEAM=1` ile atlanır |
| Self-hosted listesi 8 örnek | **20 örnek** (parite testiyle senkron) |
| `2 skipped` | **0 skipped** |

### Neden redteam artık varsayılan

Testler yalnızca bu süreç içinde sentetik shellcode çalıştırıyor; ağa trafik
gitmiyor, dosya sistemi değişmiyor. Önceki kapı aşırı temkinliydi ve gerçek
regresyonları gizleme riski taşıyordu (bu turda olduğu gibi: shellcode/c2
kodunda yapılan değişiklikler test edilmeden geçebilirdi).

İzole olmayan CI/ortam için kaçış kapısı korundu.

---

## 4. Test mimarisi

`tests/test_selfhosted_parity.py` (24 test):

| Test | Ne yapar |
|---|---|
| `test_selfhosted_matches_python_driver` (20 örnek) | Çıktı birebir karşılaştırma; farkta unified diff |
| `test_offensive_example_builds_with_flag` | Redteam `--features offensive` ile derlenir |
| `test_supported_list_is_accurate` | Liste şişirilemez |
| `test_compiling_but_wrong_is_not_counted` | Derleniyor-ama-yanlış regresyonu |
| `test_utf8_source_not_truncated` | Çok baytlı kaynak kesilmesi |

### Normalizasyon kuralları (kaçınılmaz farklar)

PID, ISO zaman damgası, epoch (sn/ms), `(ms)`/süre satırları, canlı sistem
envanteri sayıları (`count`, `listening_count`, `total`, `unique`, `lines`),
bellek adresleri, ANSI renk kodları.

---

## 5. Kalan durum

```bash
$ for f in examples/*.ax; do ./bin/axiomc build "$f"; done   # 21/21
$ python3 -m pytest -q                                      # 976 passed
```

| Kontrol | Sonuç |
|---|---|
| Test | **976** (+31), **0 skip** |
| C örnekleri | 21/21 |
| LLVM örnekleri | 21/21 |
| Self-hosted | **21/21** |
| `make fmt-check` | ✅ |
| Bootstrap | ✅ |

### Açık kalan (kod dışı veya ayrı tur)

| ID | İş | Not |
|---|---|---|
| P2-17b | Intrusive header + `String`/`str` ayrımı | Performans/ABI; güvenlik değil |
| P2-19 | Runtime `core`/`platform` + WASI | Windows kararına bağlı |
| Faz 3 | 1.0, platform, paket yayını, kullanıcı, fon | Kod dışı |
