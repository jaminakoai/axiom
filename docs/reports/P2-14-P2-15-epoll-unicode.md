# P2-14 / P2-15 — Epoll Kapsamı ve Unicode Normalleştirme

**Tarih:** 9 Kasım 2026
**Görevler:** `TODO.md` → P2-14, P2-15
**Durum:** ✅ ikisi de tamamlandı — **Faz 1 test hedefi (900) aşıldı**

---

## 1. P2-14 — `std/net/event_loop` kapsamı

### 1.1 Durum tespiti

`tests/test_async_epoll.py` 6 test ile lifecycle, pipe veri akışı, socketpair
iki yönlü echo, mod/del, çok soketli reactor ve nonblocking TCP sunucusunu
kapsıyordu. Fonksiyon bazında karşılaştırınca **7 fonksiyon kapsanmamıştı**.

### 1.2 Eklenen kapsam

| Fonksiyon | Test edilen davranış |
|---|---|
| `event_is_writable` | `EPOLLOUT` (4) → true, `EPOLLIN` → false |
| `event_is_error` | `EPOLLERR` (8) → true, kombinasyon |
| `event_is_hangup` | `EPOLLHUP` (16) → true |
| `event_loop_mod` | `EPOLLIN` → `EPOLLIN\|EPOLLOUT` geçişi |
| `event_loop_event_fd` | `get_event().fd` ile aynı |
| `event_loop_event_events` | `get_event().events` ile aynı |
| `net_set_nonblocking` | Pipe uçları, boş okuma, geçersiz fd |

Ek senaryolar: **EPOLLHUP** (karşı uç `close` edilince), `EventKind` sabitleri,
sıfır maskesi, `event_loop_new_with_capacity(8)` sınırı.

**Kod değişikliği gerekmedi** — yedi fonksiyon da doğru çalışıyordu; eksik
olan kanıttı.

### 1.3 Bekçi testi

`test_every_public_function_is_covered` modüldeki 28 `fn`'i regex ile toplar ve
her birinin en az bir test dosyasında geçtiğini doğrular. Yeni bir fonksiyon
eklenip test edilmezse bu test kırmızıya döner.

### 1.4 Testler — 11

---

## 2. P2-15 — Unicode NFC/NFD

### 2.1 Neden tablo üretimi

Unicode normalleştirme, ~2.000 ayrıştırma kuralı ve ~900 birleştirici sınıf
gerektirir. Elle yazmak hem hata üretir hem bakımı imkânsızdır. Bu yüzden
tablolar **Unicode Character Database'den üretilir**:

```
python3 tools/gen_unicode_tables.py > axiom/unicode_tables.h
```

| Tablo | Kayıt |
|---|---|
| Kanonik ayrıştırma | 2.061 |
| Birleştirici sınıf (ccc) | 922 |
| Kanonik birleştirme çifti | 941 |
| Hangul | 11.172 hece — **algoritmik**, tabloda yok |

Kaynak: Python `unicodedata` 15.1.0 (UCD). Başlık dosyası "OTOMATİK ÜRETİLDİ"
uyarısı taşır; `test_tables_are_generated_not_handwritten` bunu kilitler.

### 2.2 API

| Fonksiyon | Davranış |
|---|---|
| `unicode_nfd(s)` | Kanonik ayrıştırma + kanonik sıralama |
| `unicode_nfc(s)` | NFD + kanonik birleştirme (D117) + Hangul |
| `unicode_is_nfc(s)` / `unicode_is_nfd(s)` | Biçim sorgusu |
| `unicode_normalize(s, form)` | `"NFC"` / `"NFD"` seçici |
| `unicode_normalize_result(s, form)` | Desteklenmeyen biçimde **Err** |
| `unicode_canonical_eq(a, b)` | NFC'ye getirip karşılaştırır |
| `unicode_ucd_version()` | `"15.1.0"` |

### 2.3 Dürüst sınır: NFKC/NFKD yok

Compatibility ayrıştırma tablosu (≈3.700 ek kayıt + etiket mantığı) gömülü
değil. **Sessizce yanlış sonuç vermek yerine** `unicode_normalize_result`
açık hata döner:

```
"desteklenmeyen normalleştirme biçimi: 'NFKC' (yalnızca NFC ve NFD; NFKC/NFKD
 gömülü tablo gerektirir)"
```

`unicode_normalize(s, "NOPE")` ise boş metin döner (eski API uyumu). Hangi
davranışın beklendiği doc comment'te yazılı.

### 2.4 Konformans testi — en önemli kısım

28 metinlik korpus (ASCII, boş, é ayrışmış/birleşik, Türkçe İ/ı, Yunanca tonos,
Kiril, çoklu birleştirici sıralaması, Hangul LV/LVT/jamo, emoji, astral düzlem,
Vietnamca) **Python `unicodedata` ile birebir** karşılaştırılır:

| Kontrol | Karşılaştırma |
|---|---|
| NFD | hex çıktı == `ucd.normalize("NFD", s)` |
| NFC | hex çıktı == `ucd.normalize("NFC", s)` |
| `is_nfc` | == `s == NFC(s)` |
| `is_nfd` | == `s == NFD(s)` |

Ayrıca: **11.172 Hangul hecesinin tamamı** NFC sabit + NFD/NFC roundtrip;
idempotans (NFC(NFC(x)) == NFC(x)); bozuk UTF-8'de çökmeme.

### 2.5 Bulunan 2 gerçek hata

**Hata 1 — Hangul LVT ayrıştırması eksikti**

```c
*a = L;  *b = (t == 0) ? V : (T_BASE + t);   // yanlış: V kayıp
```

`한` (U+D55C) → `(L, T)` = 2 kod noktası üretiyordu; doğrusu 3. Test
`hangul_nfd_cp: 2` gösterdi. Düzeltme: LVT → `((LV hecesi), T)`, özyineleme
LV'yi `L + V`'ye ayırır.

| | Önce | Sonra |
|---|---|---|
| `한` NFD kod noktası | 2 | **3** |
| Roundtrip | ❌ | ✅ |

**Hata 2 — `char_to_str` geçersiz UTF-8 üretiyordu**

```c
if (code < 0 || code > 255) return "";
buf[0] = (char)code;   // 0x80..0xFF tek bayt = geçersiz UTF-8
```

`str` tipi UTF-8 sözleşmesi taşıdığı halde `char_to_str(233)` (é) tek bayt
`0xE9` yazıyordu. Artık her kod noktası doğru UTF-8 dizisine kodlanır;
surrogate (`0xD800..0xDFFF`) ve aralık dışı değerler boş döner.

**Yan etki:** `tests/test_yara_sigma_coverage.py` bu fonksiyonu **ham bayt**
üretmek için kullanıyordu. Ham bayt için doğru araç `std/io/binary`'nin
`buf_*` API'sidir; test ona geçirildi. Bu, tip sözleşmesinin doğru yere
oturmasıdır — `str` UTF-8'tir, bayt dizisi `buf`'tır.

### 2.6 Testler — 16

---

## 3. Durum

```bash
python3 -m pytest -q --no-header
# 902 passed, 2 skipped in 654.20s
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **902** (+27) — **Faz 1 hedefi 900 aşıldı** |
| Stdlib | 52 dosya / **385** fonksiyon / 3.946 satır |
| C örnekleri | 21/21 |
| LLVM örnekleri | 21/21 |
| `make fmt-check` | ✅ |
| `axiom doc std/` | 81 belgeli öğe |
| Bootstrap | ✅ |
| UCD konformansı | 28 metin × 4 kontrol × 2 backend — birebir |

---

## 4. Faz 2 durumu

| Alan | Durum |
|---|---|
| Kütüphane derinliği (P2-06…P2-15) | ✅ tümü kapandı |
| Ekosistem altyapısı (registry, namespace, doc, LSP, EN docs) | ✅ |
| **Yayınlanmış paket sayısı** | **0** ← tek kalan |

Faz 2'nin kod tarafı bitti. Kalan iş sosyal: paket yazmak, yayınlamak,
kullanıcı bulmak. Bu, TODO'nun 6. ve 7. bölümlerindeki Faz 3 metrikleri.

### 4.1 Kalan yapısal borçlar (planlı, tek seferde yapılmaz)

| ID | İş | Neden erteleniyor |
|---|---|---|
| P2-16 | WASM encoder | Faz 3 metriklerine bağlı |
| P2-17 | Intrusive header + `String`/`str` ayrımı | 82 fonksiyon / 277 çağrı; alias güvenliği riski |
| P2-18 | Self-hosted tip çıkarımı (4/21 → 8/21) | Dil kararlılığından sonra |
| P2-19 | Runtime `core`/`platform` + WASI | Çapraz derleme; Windows kararına bağlı |

---

## 5. Sıradaki

Kod tarafında **P1/P2 etiketli açık iş kalmadı**. Sıradaki üç seçenek:

| # | İş | Tür |
|---|---|---|
| 1 | **P2-17** `String`/`str` intrusive header | En büyük teknik borç; tek tur |
| 2 | **P2-18** self-hosted 4/21 → 8/21 | "Python'suz" iddiasını güçlendirir |
| 3 | **Faz 3 hazırlığı** — referans iş yükü + kullanıcı | Sosyal/stratejik |

Öneri: önce **P2-17** (teknik borcun en risklisi, erken yapılmalı), sonra
**P2-18**. Faz 3 sosyal adımları kod dışı olduğu için ayrı yürür.
