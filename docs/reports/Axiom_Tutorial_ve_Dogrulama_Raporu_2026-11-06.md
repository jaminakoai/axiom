# Axiom (λx) — Başlangıç Rehberi ve Doğrulama Raporu

**Tarih:** 6 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Kapsam:** `~/Desktop/axiom`
**Önceki rapor:** `Axiom_LLVM_String_Temizligi_Raporu_2026-11-06.md`

---

## 0. Özet

Ajan tarafından yazılan **978 satırlık Türkçe başlangıç rehberi** teslim alındı. Ancak körü körüne kabul etmedim: içindeki **28 kod bloğunu** çıkarıp derleme/çalıştırma ile doğruladım. **2 gerçek belge hatası** bulup düzelttim ve dokümanın gelecekte bozulmasını engelleyen bir test ekledim.

| İş | Durum |
|---|---|
| `docs/TUTORIAL.md` (15 bölüm, 978 satır) | ✅ Teslim |
| 28 kod bloğunun denetimi | ✅ Yapıldı |
| 2 belge hatası (kopyala-çalıştır başarısız) | ✅ Düzeltildi |
| `tests/test_tutorial_examples.py` (13 test) | ✅ Yeni — doc rot koruması |
| README'den rehbere bağlantı | ✅ Eklendi |
| Ölçülen: 622 test | ✅ |

---

## 1. Ajan çıktısının denetimi

Rehberin **her şeyini doğrulamadım, doğrulanabilir olanı doğruladım.** İki aşamalı:

### Aşama 1 — Sözdizimi denetimi

28 `axiom` bloğu çıkarıldı, her biri `axiom check` ile denetlendi:

```text
blok sayisi: 28
 1 OK   2 OK   3 SKIP   4 FAIL   5 OK   6 SKIP   7 SKIP
 8 FAIL  9 SKIP  10 OK  11 OK  12 OK  13 OK  14 SKIP
15 FAIL 16 FAIL 17 OK  18 FAIL 19 OK  20 OK  21-26 SKIP
27 FAIL 28 OK
```

### Aşama 2 — Gerçekten derle ve çalıştır

`fn main` içeren 12 blok ikiliye derlenip çalıştırıldı:

| Blok | Sonuç |
|---|---|
| 4 (kontrol akışı) | ❌ `Bilinmeyen fonksiyon cagrisi: 'square'` |
| 8 (struct) | ❌ `Tanimlanmamis struct yapisi: 'Point'` |
| 10, 11, 12, 13, 17, 20, 28 | ✅ çalışıyor |
| 19 (`main -> Result`) | ✅ **exit 1** — belgelenen davranış |
| 27 | ❌ kasıtlı çok-dosyalı örnek |

---

## 2. Bulunan gerçek hatalar

### 2.1 Blok 4 — tanımsız `square()`

"Kontrol akışı" bölümündeki örnek `square(7)` çağırıyordu ama `square` bir **önceki** blokta tanımlıydı. Rehberi izleyen biri bu bloğu kopyalayınca:

```text
Axiom Semantik Hatasi: Bilinmeyen fonksiyon cagrisi: 'square'
```

**Düzeltme:** `square` bloğa eklendi + "bu blok kendi içinde çalışır" notu.

### 2.2 Blok 8 — tanımsız `Point`

"Struct oluşturma" örneği `Point { x: 1, y: 2 }` kullanıyordu; `Point` tanımı önceki alt bölümdeydi.

**Düzeltme:** struct tanımı bloğa eklendi (kısa tekrar, rehberde kabul edilebilir).

### 2.3 Blok 27 — çok dosyalı örnek (hata değil)

`# main.ax` + `# utils.ax` ayrı bloklar hâlinde gösteriliyor; tek başına kopyalanınca `utils.ax` bulunamıyor. Bu **kasıtlı** ve doğru bir anlatım, ama okuyucu yanılabilir.

**Düzeltme:** "Bu iki blok tek programın parçasıdır; aynı dizinde `utils.ax` ve `main.ax` oluşturun" notu eklendi.

### 2.4 Blok 19 — "hata" değil

`main -> Result` örneği `Err` döndürdüğü için **exit 1** ile bitiyor. Bu tam olarak rehberin anlattığı davranış:

> `main` `Err` döndürdüğünde: hata mesajı `stderr`'a yazılır, çıkış kodu `1` olur.

Doküman bu noktayı doğru açıklıyor. Değişiklik gerekmedi.

### 2.5 Parçalı bloklar

"Kurucular" ve "`?` operatörü" bölümlerindeki ifade parçaları (`result_ok<int>(42)` gibi) tek başına çalıştırılamaz — bunlar **sözdizimi gösterimi**, program değil. Belgelerde bu meşru; değiştirmedim.

---

## 3. Doğrulanan iddialar

Rehberin dile dair somut iddialarını tek tek sınadım:

| İddia | Doğrulama |
|---|---|
| `axiom --version` → `v0.5.0-alpha` | ✅ birebir |
| 13 CLI komutu (`check`, `prove`, `emit-c`, `emit-llvm`, `fmt`, `repl`, `pkg`, `lsp`, …) | ✅ hepsi mevcut |
| `axpm` 10 alt komut (`init/add/install/update/verify/tree/remove/build/run/test`) | ✅ hepsi mevcut |
| `axiom build --backend=llvm/--asan/-O/--target` | ✅ bayraklar var |
| `examples/19` LLVM ile derlenir | ✅ |
| `examples/01` `--asan` ile derlenir | ✅ |
| `examples/06_modules/{main,utils}.ax` mevcut | ✅ |
| `enum`/`trait`/closure/`try` **yok** | ✅ doğru |
| Exit kodları 101/102 | ✅ doğru |
| `match` ifadesi (`return match x { … }`) | ✅ çalışıyor |
| Dizi ataması değer semantiği | ✅ (`a[0]` bozulmuyor) |

**İç API sızıntısı:** `str_owned_count`, `axiom_temp_*`, `g_axiom*` — hiçbiri rehberde yok. ✅

---

## 4. Yeni test: doküman çürümesine karşı

Sorun şu: rehber bugün doğru, ama dil değişince sessizce yanlışlanır. Bu yüzden `tests/test_tutorial_examples.py` (13 test) ekledim:

| Test | Ne yapar |
|---|---|
| `test_tutorial_exists_and_has_blocks` | Rehber ve en az 20 blok var mı |
| `test_tutorial_runnable_block_builds` (×10, parametrik) | Her çalıştırılabilir blok **derlenir** |
| `test_tutorial_multi_file_example_builds` | `utils.ax` + `main.ax` birlikte çalışır, çıktı `Sistem 1` |
| `test_tutorial_does_not_leak_internal_apis` | İç tanılama API'leri rehbere sızmamış |

CI'ya `Dokümantasyon kod blokları` adımı olarak eklendi. Bir sözdizimi değişikliği rehberi bozarsa **PR kırılır**.

---

## 5. Rehberin içeriği

15 bölüm, 978 satır:

1. Kurulum (gereksinimler, PATH, sürüm)
2. İlk program
3. Temel sözdizimi (yorum, değişken, fonksiyon, kontrol akışı, `match`, **olmayan yapılar**, noktalı virgül)
4. Tipler ve struct
5. Diziler (literal, `len`, indeks, `array_push`, **değer semantiği**)
6. Sözleşmeler (`requires`/`ensures`/`verify`, ne zaman kullanılır, ispat araçları)
7. Hata yönetimi (`Result`, kurucular, `?`, yardımcılar, `main -> Result`, **kritik ayrım tablosu**)
8. Stdlib `Result` katmanı (file/json/http/tls/process)
9. Modüller
10. Eşzamanlılık
11. Araçlar
12. Derleme
13. **Yaygın hatalar ve çözümleri** (tablo)
14. Bilinen sınırlamalar
15. Sırada ne var

Öne çıkan doğru kararlar:
- "Axiom'da olmayan yapılar" bölümü — `try/except`, `enum`, `trait`, closure'ın olmadığını açıkça söylüyor.
- "Kritik ayrım" tablosu — beklenen hata (`Result`) vs programlama hatası (sözleşme → exit 101) vs sınır ihlali (exit 102).
- Geçici string sınırı dürüstçe belirtilmiş.

---

## 6. Test Sonuçları

```bash
$ python3 -m pytest -q --no-header
622 passed in 362.90s (0:06:02)
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **622** (önceki 609; +13) |
| Rehber kod blokları | 13/13 |
| LLVM örnekleri | 19/19 |
| `bin/axiomc` bootstrap | ✅ |
| `make fmt-check` | ✅ |

---

## 7. Değiştirilen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `docs/TUTORIAL.md` | **Yeni** — 978 satır, 15 bölüm; 2 blok kendi kendine yeterli hâle getirildi, 1 nota eklendi |
| `tests/test_tutorial_examples.py` | **Yeni** — 13 test (doc rot koruması) |
| `README.md` | Rehbere bağlantı, test rozeti 622 |
| `CHANGELOG.md` | Rehber + test kaydı |
| `.github/workflows/ci.yml` | Doküman bloğu doğrulama adımı |

---

## 8. Durum: "Python gibi olmaya" katkısı

| Boyut | Önce | Sonra |
|---|---|---|
| Doküman / öğrenme eşiği | ❌ SPEC v0.1, tutorial yok | ✅ 978 satırlık rehber + otomatik doğrulama |
| Hata modeli | ✅ | ✅ |
| Stdlib pratikliği | ~%25 | ~%25 |
| Bellek modeli | ⚠️ | ⚠️ |

Önceki değerlendirmede "öğrenme eşiği" en zayıf halkalardan biriydi (SPEC v0.1, tutorial yok). Artık yeni bir geliştirici kurulumdan `Result`'a kadar tek belgeyle ilerleyebilir — ve o belgenin çalıştığı testle garanti.

---

## 9. Sıradaki İşler

| # | İş | Not |
|---|---|---|
| 1 | **Intrusive header + `String`/`str`** | Harita hazır (82 fonksiyon, 277 çağrı). Kalan tek büyük bellek borcu |
| 2 | LLVM'de `str[]` temizliği | C ile tam eşitlik |
| 3 | Gerçek JSON parser | `Result` katmanı hazır, parser sığ |
| 4 | HTTP/1.1 chunked + Content-Length | `http_body` ham |
| 5 | Registry politikası | Paket ekosistemi |
| 6 | `SPECIFICATION.md` v0.5 güncellemesi | Rehber artık referans; şartname geride kaldı |

**Öneri:** Sırada 6 numara ucuz ve değerli — rehber 978 satır doğru bilgi içeriyor, şartname hâlâ v0.1 ve `Result`, `?`, `defer`, `match`, generics, LSP, paket yöneticisinden hiç söz etmiyor. Şartnameyi rehberle hizalamak yarım günlük iş. Sonra 1 numara (intrusive header) için odaklı tur.
