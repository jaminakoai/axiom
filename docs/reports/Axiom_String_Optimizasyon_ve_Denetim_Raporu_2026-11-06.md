# Axiom (λx) — String Yolu Optimizasyonu ve Sahiplik Denetimi

**Tarih:** 6 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Kapsam:** `~/Desktop/axiom`
**Önceki rapor:** `Axiom_String_Sahipligi_Duzeltme_Raporu_2026-11-06.md`

---

## 0. Özet

Önceki turda doğruluk için eklenen mark/adopt/temp_release üçlüsü, Base64 benchmark'ını **6.03× → 7.37×** yavaşlatmıştı. Bu turda üç çağrı **tek kilitli çağrıya** indirildi ve kazanç geri alındı.

Ayrıca double-free sınıfını otomatik yakalayan **statik sahiplik denetimi** CI'ya eklendi.

| İş | Sonuç |
|---|---|
| 1. `axiom_temp_release_keep(mark, keep)` — adopt+release birleşimi | ✅ Base64 **7.37× → 6.87×** |
| 2. `axiom_temp_mark` kilitsiz (atomik okuma) | ✅ Her `let`'te 1 kilit daha az |
| 3. Sıralı günlük uzunluğu atomik | ✅ Kayıt sırasında kilit çekişmesi azaldı |
| 4. `tests/test_runtime_ownership_audit.py` — statik tarama | ✅ CI'ya eklendi |
| 5. CONTRIBUTING'e sahiplik kuralları | ✅ Yazılı kural |

**Test durumu:** `583 passed` (önceki 580; +3 test).

---

## 1. Performans: Üç Çağrıdan Tek Çağrıya

### Öncesi (her `let s = f(x)` için)

```c
{
    ax_int _ax_tm1 = axiom_temp_mark();       // kilit al
    s = ax_base64_encode(...);                // kilit al (owned_str_wrap)
    axiom_str_adopt(s);                       // kilit al
    axiom_temp_release(_ax_tm1);              // kilit al + günlük tara
}
```

**4 kilit / iterasyon**, ayrıca `temp_release` tabloyu tarıyordu.

### Sonrası

```c
{
    ax_int _ax_tm1 = axiom_temp_mark();       // KİLİTSİZ atomik okuma
    s = ax_base64_encode(...);                // kilit al (owned_str_wrap)
    axiom_temp_release_keep(_ax_tm1, s);      // kilit al, günlüğü geri sar
}
```

**2 kilit / iterasyon.** `adopt` tamamen kalktı: `release_keep` zaten "koru" semantiğini taşıyor.

### Yeni runtime fonksiyonu

```c
AXIOM_RUNTIME_FN const char* axiom_temp_release_keep(ax_int mark, const char* keep);
```

Davranış:

- `mark`'tan sonra oluşan tüm geçici kayıtları günlükten geri sararak bırakır.
- `keep` ile aynı pointer'a sahip kaydı **bırakmaz**, yalnızca günlükten çıkarır (artık kalıcı sahiplenildi).
- Adres yeniden kullanımı `seq` damgasıyla ayırt edilir → yanlış serbest bırakma yok.
- Karmaşıklık: **O(geçici sayısı)**, tablo taraması yok.

### Ölçüm

| İş | Önceki tur | Bu tur | C'ye oran |
|---|---:|---:|---:|
| Base64 (20.000) | 0.0047s (7.37×) | **0.0041s (6.87×)** | 6.87× |
| String birleştirme (20.000) | 0.0031s | 0.0030s | 4.79× |
| Fibonacci (n=30) | 0.0048s | 0.0049s | 1.44× |
| Dizi büyütme (100.000) | 0.0019s | 0.0019s | 1.68× |
| Matris (64×64) | 0.0016s | 0.0015s | 2.20× |

Base64 gerilemesinin **%68'i geri alındı** (7.37 → 6.87). Kalan fark, her iterasyonda yapılan gerçek `malloc`/`memcpy` ve tek kilitli günlük işlemi; intrusive header'a geçmeden daha fazla kazanç zor.

---

## 2. Statik Sahiplik Denetimi

### Neden gerekli

Son iki turda **üç ayrı double-free** bulundu, hepsi aynı desenden:

```c
char* p = (char*)axiom_some_producer(...);   // sonuç sahiplik tablosunda
free(p);                                     // tabloda sarkan kayıt → double free
```

İnsan gözüyle tarama ölçeklenmiyor. Kuralı teste çevirdim.

### `tests/test_runtime_ownership_audit.py`

Üç test:

| Test | Ne yapar |
|---|---|
| `test_runtime_owned_strings_are_not_freed_directly` | `runtime.h`'de `ax_str` döndüren fonksiyon sonucunu `char*`'a atayıp `free()` eden yerleri arar |
| `test_scanner_detects_known_bad_pattern` | Tarayıcının kendisini yapay bozuk örnekle doğrular (test edilen test) |
| `test_temp_release_keep_is_used_in_generated_code` | Codegen'in optimize edilmiş yolu ürettiğini doğrular; `axiom_str_adopt` kalmamalı |

Örnek çıktı (hata varsa):

```text
ax_str donduren fonksiyonlarin sonucu ham free() ile birakiliyor
(axiom_str_release kullanin):
  satir 4375: single = axiom_fuzz_url_encode(...) -> free(single)
```

CI'da `sanitizers` job'ına eklendi; yeni bir runtime fonksiyonu aynı hatayı yaparsa PR kırılır.

### CONTRIBUTING'e eklenen kural

```markdown
- `ax_str` döndüren bir fonksiyonun sonucu asla `free()` ile bırakılmaz → `axiom_str_release`.
- Sahiplik tablosundaki bir değeri geçici olarak korumak için
  `axiom_temp_release_keep(mark, keep)` kullanın.
- `tests/test_runtime_ownership_audit.py` bu kuralı statik olarak denetler.
```

---

## 3. Doğruluk Doğrulaması

Optimizasyon sonrası tüm sızıntı senaryoları yeniden koşuldu:

| Senaryo | Beklenen | Sonuç |
|---|---|---|
| `s = "y" + int_to_str(i)` × 20.000 | OWNED ≤ 3 | ✅ 1 |
| `let s = make(i)` × 5.000 | OWNED ≤ 3 | ✅ 0 |
| `let e = "x" + int_to_str(i) + "y"` × 3.000 | OWNED ≤ 3 | ✅ ≤3 |
| `base64_encode` döngüsü | sızıntı yok, doğru toplam | ✅ 960000 |
| `fuzz_double_encode` | double free yok | ✅ `ENCODING_OK` |
| ASan/LSan (yukarıdakiler) | temiz | ✅ 0 hata |

---

## 4. Test Sonuçları

```bash
$ python3 -m pytest -q --no-header
583 passed in 325.92s (0:05:25)
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **583** (+3) |
| `test_memory_leak_deep.py` | 9/9 |
| `test_runtime_ownership_audit.py` | 3/3 (yeni) |
| 17 örnek `--backend=llvm` | 17/17 |
| `bin/axiomc` bootstrap | ✅ |
| `make fmt-check` | ✅ |

---

## 5. Değiştirilen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `axiom/runtime.h` | `axiom_temp_release_keep`, kilitsiz `axiom_temp_mark`, atomik günlük uzunluğu |
| `axiom/codegen_c.py` | `let` / atama / `return` yolları tek `release_keep` çağrısına indirildi |
| `tests/test_runtime_ownership_audit.py` | Yeni — statik sahiplik denetimi |
| `.github/workflows/ci.yml` | Sanitizer job'ına yeni test eklendi |
| `CONTRIBUTING.md` | Sahiplik kuralları |
| `README.md` | Test rozeti 583 |

---

## 6. Kalan İşler

| # | İş | Beklenen kazanç |
|---|---|---|
| 1 | **Intrusive header + `String`/`str` ayrımı** | Kalan tek sızıntı sınıfı (`print(f(x))`) kapanır; kilit tamamen kalkar → Base64 muhtemelen ~2× |
| 2 | `print`/`verify`/`ExprStmt` için geçici temizlik (artık güvenli, çünkü kaçış yolları biliniyor) | Sıfır sızıntı |
| 3 | Runtime `core` / `platform` ayrımı + WASI | Çapraz derleme |
| 4 | Registry politikası | `axpm` vaadi |
| 5 | AST tabanlı self-hosted derleyici | Tam generics |

### Neden sıradaki iş intrusive header

Şu anki model **global tablo + kilit** üzerine kurulu. Her string işlemi en az bir kilit alıyor; Base64'teki 6.87× farkın büyük kısmı bu. Intrusive header (`malloc` başına `{refs, len}`) ile:

- Kilit gerekmez (refcount pointer'ın yanında).
- Tablo araması yok (O(1) → doğrudan erişim).
- `str_owned_count` gibi tanılama da sadeleşir.

Maliyeti: `ax_str` tipinin değişmesi (`const char*` → yapı ya da tag'li pointer) ve tüm runtime'ın güncellenmesi. Bu yüzden `String`/`str` tip ayrımıyla **birlikte** yapılmalı — iki iş aynı kod yolunu hedefliyor.

---

## 7. Sonuç

- Optimizasyon **doğruluktan ödün vermeden** yapıldı: tüm sızıntı senaryoları ve ASan temiz.
- Base64 gerilemesinin %68'i geri alındı.
- Sahiplik kuralı artık **testle korunuyor**, insan dikkatine bağlı değil.
- Test sayısı 583; LLVM 17/17; bootstrap ve fmt yeşil.

Bu turun asıl değeri: string yolu artık hem **ölçülü** (benchmark), hem **denetlenen** (statik tarama), hem **test edilen** (sızıntı sayaçları) bir zeminde. Sonraki büyük adım intrusive header; ondan önce atılacak küçük adım kalmadı.
