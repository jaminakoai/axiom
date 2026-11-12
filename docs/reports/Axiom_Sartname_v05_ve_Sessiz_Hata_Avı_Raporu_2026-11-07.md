# Axiom (λx) — Şartname v0.5, LLVM Kontrol Akışı ve Sessiz Hata Avı

**Tarih:** 7 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Kapsam:** `~/Desktop/axiom`
**Önceki rapor:** `Axiom_Tutorial_ve_Dogrulama_Raporu_2026-11-06.md`

---

## 0. Özet

İki ajan paralel çalıştırıldı. Test-boşluk ajanı **kritik bir sessiz hata** buldu: LLVM'de `break`/`continue` hiç uygulanmamış — hata vermeden yanlış sonuç üretiyordu. Şartname ajanı token limitine takıldı; şartnameyi kendim yazdım ve **4 gerçek hata** daha ortaya çıkardı.

| İş | Durum |
|---|---|
| LLVM `break`/`continue` | ✅ Düzeltildi (C `S:12` vs LLVM `S:55` idi) |
| `SPECIFICATION.md` v0.5 (689 satır, 19 bölüm) | ✅ Yazıldı |
| Aynı blokta `let` yeniden tanımı | ✅ Artık net hata (C'de bozuktu) |
| `as str` | ✅ Artık reddediliyor (çöp kod üretiyordu) |
| Döngü dışında `break`/`continue` | ✅ Artık derleme hatası |
| `0x10` / `1_000` / `1e9` hataları | ✅ Anlaşılır `LexerError` |
| LLVM'de `str[]` dizi temizliği | ✅ Tamamlandı |
| 26 yeni test | ✅ |

**Test durumu:** `648 passed` (önceki 622; +26).

---

## 1. Ajanlar ve sonuçları

| Ajan | Görev | Sonuç |
|---|---|---|
| `explore` | Test kapsamı boşluk analizi | ✅ **Çok değerli**: 10 öncelikli boşluk, en kritiği LLVM `break`/`continue` |
| `general` | `SPECIFICATION.md` v0.5 | ❌ Günlük token limiti aşıldı — iş tarafımdan yapıldı |

Test ajanı 290 builtin'i, 50 stdlib modülünü, CLI komutlarını ve dil özelliklerini taradı. En önemli bulgusu:

> **`break`/`continue` LLVM codegen'de hiç yok** (`codegen_llvm.py`'de `BreakStmt` dalı bulunmuyor). Sessiz yanlış kod riski.

Doğruladım:

```axiom
while i < 10 {
    i = i + 1
    if i == 3 { continue }
    if i == 6 { break }
    s = s + i
}
```

| Arka uç | Çıktı |
|---|---|
| C | `S: 12` ✅ |
| LLVM (önce) | `S: 55` ❌ — hata mesajı yok |

---

## 2. LLVM `break`/`continue`

**Uygulama:** `loop_stack` (devam/çıkış etiket çiftleri).

| Yapı | `continue` hedefi | `break` hedefi |
|---|---|---|
| `while` | koşul bloğu | döngü sonu |
| `for` | **artırma bloğu** (yeni `for_inc` etiketi) | döngü sonu |

Ek olarak, çıkıştan önce **o anda açık olan en iç bloğun** `defer`'ları ve sahipli kaynakları bırakılıyor. Fonksiyon düzeyindeki `defer`'lar çalışmıyor (doğru: döngüden çıkmak fonksiyondan çıkmak değil).

Doğrulama (C ile birebir):

| Senaryo | C | LLVM |
|---|---|---|
| `while` break/continue | `S: 12` | `S: 12` |
| `for` break/continue | `FOR: 19` | `FOR: 19` |
| iç içe döngü | `NEST: 6` | `NEST: 6` |
| break + string temizliği | `2|2|SON: 3` | `2|2|SON: 3` |

---

## 3. Şartname v0.5

Ajan tamamlayamadığı için kendim yazdım: **689 satır, 19 bölüm**.

| # | Bölüm |
|---|---|
| 1 | Kapsam ve terminoloji (zorunlu/önerilir/tanımsız) |
| 2 | Tasarım ilkeleri |
| 3 | Sözcüksel yapı (26 anahtar kelime, operatör öncelik tablosu) |
| 4 | Tipler (yerleşik, bileşik, çıkarım, `as`) |
| 5 | Değişkenler ve kapsam |
| 6 | İfadeler (aritmetik koruma, `match`, `?`) |
| 7 | Deyimler (`defer`, `break`/`continue`, `verify`) |
| 8 | Fonksiyonlar ve sözleşmeler |
| 9 | Hata modeli (`Result`, `?` kuralları, `main -> Result`) |
| 10 | Bellek modeli (değer anlambilimi, sahiplik, kaçış) |
| 11 | Modüller (+ ofansif izolasyon) |
| 12 | Eşzamanlılık |
| 13 | **86 builtin kataloğu** (7 kategori) |
| 14 | Derleme hattı (ASCII diyagram) |
| 15 | Çalışma zamanı ve ABI (sret, çıkış kodları) |
| 16 | Tanımlı / tanımsız davranış |
| 17 | Uyumluluk ve sürümleme |
| 18 | EBNF özeti |
| 19 | Bilinen sınırlamalar |

Şartname yazarken **kodla karşılaştırarak** doğruladım — ve 4 hata çıktı.

---

## 4. Şartname yazarken bulunan 4 gerçek hata

### 4.1 Aynı blokta `let` yeniden tanımı → bozuk C kodu

Şartnameye "gölgeleme desteklenmez" yazacaktım; kontrol ettim, **checker kabul ediyordu** ama C'de:

```text
error: redefinition of 'x'
```

Yani checker geçiyor, derleme patlıyor. **Düzeltme:** checker aynı blokta yeniden tanımı net bir mesajla reddediyor; iç blokta gölgeleme serbest (bu zaten doğru çalışıyordu).

### 4.2 `as str` → çöp kod

Checker `as str`'i kabul ediyordu; C'de `((ax_str)(5))` yani geçersiz işaretçi üretiyordu.

**Düzeltme:** reddediliyor, mesaj `int_to_str(x)` öneriyor.

### 4.3 Döngü dışında `break`/`continue` → kabul ediliyordu

C arka ucu döngü dışında `break` için geçersiz C üretir; checker hiç denetlemiyordu.

**Düzeltme:** `loop_depth` sayacı; döngü dışında derleme hatası.

### 4.4 `0x10` / `1_000` / `1e9` → şaşırtıcı hata

```text
$ axiom check hex.ax
Axiom Semantik Hatasi: Tanimlanmamis degisken: 'x10'
```

Kullanıcı `0x10` yazmış, "tanımsız değişken" hatası alıyor. Lexer sayıyı `0` + `x10` diye ayırıyordu.

**Düzeltme:** üç literalin hepsi için açık `LexerError`:

```text
LexerError: Desteklenmeyen sayi bicimi: '0x...'. Axiom yalnizca ondalik ...
LexerError: Sayilarda alt cizgi ayirici desteklenmiyor ('1_000' gecersiz).
LexerError: Bilimsel gosterim desteklenmiyor: '1e...'.
```

---

## 5. LLVM `str[]` dizi temizliği

C'de `axiom_array_str_free` üretiliyordu, LLVM'de hiçbir şey. Eklendi:

```llvm
declare void @axiom_array_str_free(%struct.ax_array*)
...
call void @axiom_array_str_free(%struct.ax_array* %var.parts)
```

- Yalnızca **heap'te ayrılmış** diziler izlenir (dizi literalleri stack'te, bırakılmaz).
- `int[]`/`float[]`/`bool[]`/`str[]` için doğru free fonksiyonu seçiliyor.
- Atamada eski dizi önce bırakılıyor.
- Kaçış analizi dizileri de kapsıyor.

Doğrulama: 200 iterasyonda `str_split` → LLVM+ASan ve C+ASan **sıfır sızıntı**, `T: 600` aynı.

---

## 6. Testler

| Dosya | Test | Kapsam |
|---|---|---|
| `test_llvm_control_flow.py` | 7 | `break`/`continue` (while/for/iç içe/kapsam), `verify`, `as` paritesi |
| `test_specification.py` | 17 | anahtar kelime/tip listesi kodla eşleşmesi, gölgeleme, `as str`, exit 101/102, dizi değer semantiği, desteklenmeyen literaller |
| `test_llvm_string_ownership.py` | +2 | `str[]` temizliği, döngüde sızıntısızlık |

```bash
$ python3 -m pytest -q --no-header
648 passed in 388.39s (0:06:28)
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **648** (+26) |
| LLVM örnekleri | 19/19 |
| `bin/axiomc` bootstrap | ✅ |
| `make fmt-check` | ✅ |
| ASan (C ve LLVM, 200/20.000 iterasyon) | ✅ sıfır sızıntı |

---

## 7. Değiştirilen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `SPECIFICATION.md` | **Yeniden yazıldı** — v0.5, 689 satır, 19 bölüm |
| `axiom/codegen_llvm.py` | `loop_stack`, `break`/`continue`, `str[]` sahiplik temizliği, dizi kaçış analizi |
| `axiom/checker.py` | `loop_depth`, aynı blok yeniden tanım reddi, `as str` reddi |
| `axiom/lexer.py` | `0x`/`0b`/`0o`/`1_000`/`1e9` için açık hata |
| `tests/test_llvm_control_flow.py` | **Yeni** — 7 test |
| `tests/test_specification.py` | **Yeni** — 17 test |
| `tests/test_llvm_string_ownership.py` | +2 test |
| `README.md`, `CHANGELOG.md`, `.github/workflows/ci.yml` | Senkron |

---

## 8. Ajan raporundan kalan boşluklar (öncelik sırası)

Test ajanı 10 öneri verdi; bu turda **1, 4 (kısmi), 5 (kısmi)** ele alındı. Kalanlar:

| # | Boşluk | Risk |
|---|---|---|
| 1 | Geçerli overload testleri (aynı ad, farklı tipler) | Orta — üç codegen'de de yol var, test yok |
| 2 | CLI hata yolu matrisi (dosya yok, sözdizimi hatası, olmayan modül) | Orta |
| 3 | LSP eksik metodları (`didSave`, `didClose`, `exit`, `-32601`, bozuk çerçeve) | Düşük |
| 4 | `std/core/error.ax`'in 8 test edilmeyen yardımcısı | Orta |
| 5 | Formatter idempotency (`fmt(fmt(x)) == fmt(x)`) | Düşük |
| 6 | `@simd` dekoratörü hiç test edilmiyor (`examples/09` koşmuyor) | Orta |
| 7 | Package manager `get_search_paths`, `remove --purge`, `tree` dalları | Düşük |
| 8 | 240 builtin için doğrudan checker tip testi | Düşük |
| 9 | Self-hosted `compiler/*.ax` hiç test edilmiyor (bootstrap hariç) | Orta |

---

## 9. Durum

| Boyut | Durum |
|---|---|
| **Dokümantasyon** | ✅ Rehber (994 satır) + Şartname (689 satır), ikisi de CI'da test ediliyor |
| **LLVM paritesi** | ✅ Kontrol akışı, `defer`, `?`, string ve dizi temizliği |
| **Sessiz hata** | ✅ Bu turda 5 sınıf kapatıldı |
| **Bellek** | ⚠️ Geçici ifade string'leri hâlâ tabloda kalabiliyor |
| **Ekosistem** | ⚠️ Registry yok, WASM deneysel |

**Ders:** Bu turun en değerli çıktısı özellik değil, **sessiz hataların bulunması**. LLVM `break`/`continue`, aynı blok gölgeleme, `as str` — üçü de "derleme geçiyor, sonuç yanlış" sınıfındaydı. Test-boşluk ajanı olmasaydı `break`/`continue` fark edilmeyecekti.

**Öneri:** Sıradaki turda **overload testleri + CLI hata yolu matrisi**. İkisi de ucuz ve aynı "sessiz hata" sınıfını hedefliyor. Intrusive header hâlâ en büyük teknik borç ama riskli; ayrı ve odaklı bir tur hak ediyor.
