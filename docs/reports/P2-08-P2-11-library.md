# P2-08 / P2-09 / P2-10 / P2-11 — Kütüphane Derinleştirme

**Tarih:** 9 Kasım 2026
**Görevler:** `TODO.md` → P2-08, P2-09, P2-10, P2-11
**Durum:** ✅ dördü de tamamlandı

---

## 1. P2-08 — `std/io/file` tam `Result` API

### 1.1 Yeni yerleşikler (C + LLVM, aynı semantik)

| Fonksiyon | Davranış |
|---|---|
| `file_size(path) -> int` | Bayt boyutu; yok/dizin ise `-1` |
| `is_directory(path) -> bool` | `stat` + `S_ISDIR` |
| `list_dir(path) -> str` | Satır satır, **sıralı**, `.`/`..` hariç |
| `remove_file(path) -> bool` | Dosya veya **boş** dizin |
| `rename_file(from, to) -> bool` | `rename(2)` |
| `create_dir(path) -> bool` | `mkdir -p` semantiği, `EEXIST` → `true` |

### 1.2 `Result` sarmalayıcıları

| Fonksiyon | Hata durumu |
|---|---|
| `file_size_result` | boş yol / yok / normal dosya değil |
| `list_dir_result` | boş yol / dizin yok |
| `remove_file_result` | boş yol / yok / dolu dizin |
| `rename_file_result` | boş yol / kaynak yok / izin |
| `create_dir_result` | boş yol / oluşturulamadı |
| `copy_file_result` | boş yol / kaynak yok / yazılamadı |
| `dir_present` | hata üretmez (`false`) |

**Tasarım kuralı korundu:** bu modülde `requires`/`ensures`/`verify` yok —
veri hatası beklenen bir sonuçtur, program hatası değil. `test_no_requires_in_io_file`
bunu kilitler.

### 1.3 Belgelenmiş kısıt

`copy_file_result` metin tabanlıdır (`file_read`/`file_write` NUL sonlandırmalı).
İçinde NUL baytı olan ikili dosyalar için uygun değildir — doc comment'te yazılı.

### 1.4 Testler — 12

| Grup | Kapsam |
|---|---|
| Yerleşikler | Boyut, dizin, sıralı listeleme, rename, mkdir -p, silme |
| Mutlu yol | Tüm `*_result` fonksiyonları |
| Hata yolu | 8 farklı `Err` senaryosu; program **durmuyor** |
| `?` akışı | `read_lines` → `Result<int, str>` zinciri |
| Sözleşme | `requires`/`verify` yokluğu |
| `axiom doc` | Yeni API dokümanda görünüyor |

---

## 2. P2-09 — `std/text/regex` ReDoS kapısı

### 2.1 Neden PCRE2/RE2 değil

Sistemde `libpcre2-8.so.0` var ama **başlık dosyası yok** (`libpcre2-dev` kurulu
değil); derleme bağımlılığı eklemek kurulumu kırardı. glibc POSIX ERE zaten
geri izleme yapmayan NFA'dır. Bu yüzden **kaynak sınırları** ile sertleştirildi.

### 2.2 Sınırlar

| Kontrol | Sınır | Örnek |
|---|---|---|
| Desen uzunluğu | 4096 bayt | — |
| Parantez derinliği | 32 | `((((...))))` |
| `{n,m}` tekrar | 1024 | `a{1,99999}` |
| İç içe niceleyici | reddedilir | `(a+)+`, `(a*)*`, `(a|a)*` |

`regex_risk_level` → `0` güvenli, `2` reddedilir.

### 2.3 Sessiz kaçırma yerine `Err`

Eski API geçersiz desende `false`/`""` dönüyordu — bir tespit kuralında bu
"eşleşmedi" demektir; **sessiz kaçırma**. Yeni `*_result` API'si `Err` döner:

| Fonksiyon | Dönüş |
|---|---|
| `regex_validate(pattern)` | `""` geçerli, aksi halde neden |
| `regex_is_match_result` | `Ok(bool)` / `Err` |
| `regex_find_result` | `Ok(eslesme)` — eşleşmemek `Ok("")` |
| `regex_replace_result` | `Ok(yeni metin)` / `Err` |
| `regex_compile_result` | Kurulum doğrulaması |
| `regex_escape` | Literal arama için kaçış |

### 2.4 Testler — 9

6 ReDoS kalıbı, 5 geçerli desen, 4 hata yolu, escape (meta + ters bölü),
eski API'nin değişmediği, C+LLVM paritesi.

---

## 3. P2-10 — `std/collections/map`

**Kod değişikliği gerekmedi.** Uygulama zaten doğruydu (djb2, zincirleme
çakışma, yük faktörü 3/4'te ikiye katlama, `free`). Eksik olan **kanıttı**.

| Test | Ne doğrular |
|---|---|
| Temel | set/get/has/delete/len, üzerine yazma, boş anahtar |
| Ölçek | 500 kayıt → rehash zinciri; hepsi erişilebilir |
| Çakışma | `djb2 % 16 == 9` olan `c1`/`c10`/`c19` aynı bucket; silme zinciri bozmuyor |
| Uzun değer | 1000 baytlık değer, sonra kısa değerle değiştirme |

Testler — 8, C + LLVM paritesi.

---

## 4. P2-11 — `std/time/date` saat dilimi

### 4.1 Tasarım: sabit ofset (bilinçli sınır)

IANA tz veritabanı ve DST kural tablosu **yok**. Ofset dakika olarak verilir
(`UTC+03:00` → `180`), ±14:00 ile sınırlı. Gerekçe: veritabanı bağımlılığı
olmadan deterministik sonuç; intranet/sunucu araçları için yeterli.
Yerel makinenin o anki ofseti (DST dahil) `date_local_offset_minutes()` ile
alınabilir.

Bu sınır hem modül başlığında hem `test_scope_is_documented` testinde yazılı —
"yapılmadı" değil, "kapsam dışı" olarak.

### 4.2 API

| Fonksiyon | Örnek |
|---|---|
| `date_format_tz(epoch, fmt, off)` | `2026-11-09 03:00` |
| `date_iso_tz(epoch, off)` | `2026-11-09T03:00:00+03:00` |
| `date_parse_iso(text)` | `Z`, `+03:00`, `-0530`, ofsetsiz → `Result<int,str>` |
| `date_local_offset_minutes()` | `180` |
| `date_offset_label(off)` | `+03:00` |
| `date_duration_label(sec)` | `1g 1sa 1dk 1sn` |

### 4.3 Testler — 9

Formatlama (UTC/±/yarım saat/kırpma), ayrıştırma (5 biçim + 3 hata),
**53 ofset roundtrip** (−12:00 … +14:00, 30 dk adım), etiketler, yerel ofset
akıl sağlığı, kapsam belgesi.

---

## 5. Durum

```bash
python3 -m pytest -q --no-header     # 875 passed, 2 skipped in 592.40s
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **875** (+38) |
| Stdlib | 52 dosya / **377** fonksiyon / 3.881 satır |
| C örnekleri | 21/21 |
| LLVM örnekleri | 21/21 |
| `make fmt-check` | ✅ |
| `axiom doc std/` | 73 belgeli öğe |
| Bootstrap | ✅ |

---

## 6. Sıradaki

| # | İş | Not |
|---|---|---|
| 1 | **P2-14** `std/net/event_loop` epoll testleri | 7 fonksiyon testsiz |
| 2 | **P2-15** `std/text/unicode` NFC/NFD | Gerçek normalizasyon tablosu gerekir |
| 3 | **P2-16** `std/target/wasm` encoder | P3 |
| 4 | **P3** referans iş yükleri | Faz 3 hedefi |

> Kalan P0/P1 etiketli kütüphane işi yok. P2-12/13 (yara/sigma) P1-04'te
> kapatılmıştı; bu turda dört P1 işi birden kapandı.
