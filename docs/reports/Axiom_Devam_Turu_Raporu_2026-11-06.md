# Axiom (λx) — Devam Turu Uygulama Raporu

**Tarih:** 6 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Kapsam:** `~/Desktop/axiom`
**Önceki rapor:** `Axiom_Sonraki_Isler_Uygulama_Raporu_2026-11-06.md`

---

## 0. Özet

Bu turda sahiplik tablosunun yan etkilerini denetledim, `axpm update` ekledim ve bellek modelinin sınırını regresyon testiyle sabitledim.

| İş | Durum |
|---|---|
| 1. Ham `free()` çağrılarının sahiplik tablosuyla çakışma denetimi | ✅ Denetlendi — kalan çakışma yok |
| 2. `axpm update` (git bağımlılıklarını yeniden çekme) | ✅ Tamamlandı |
| 3. Bellek modeli sınırı için regresyon testi (`str_owned_count`) | ✅ Eklendi |
| 4. Deneysel geçici-temizlik fonksiyonlarının işaretlenmesi | ✅ Açıkça "kullanılmıyor" notu |
| 5. Derleme artığının temizliği | ✅ `tmp5hc42psm` silindi |

**Test durumu:** `577 passed` (önceki 574; +3 yeni test).

---

## 1. Ham `free()` Denetimi

Sahiplik tablosu (`g_axiom_owned_tbl`) bir pointer'ı izliyorsa, o pointer'ın ham `free()` ile bırakılması tabloda sarkan kayıt bırakır ve sonraki `axiom_str_release` **double-free** üretir. Önceki turda JWT'de tam olarak bu olmuştu.

### Yapılan denetim

İki geçişli statik tarama:

1. **Dönüş tipi `ax_str` olan fonksiyonların sonucunu alıp `free()` eden yerler** — 0 bulgu (JWT düzeltmesinden sonra).
2. **Fonksiyon gövdesinde `ax_str` olarak tanımlanıp ham `free()` edilen değişkenler** — 0 bulgu.

```text
candidate double-free sites: 0
ax_str locals freed with raw free(): 0
```

### Neden konteynerler güvenli

`map`, `queue`, `wordlist`, `csv` gibi yapılar iç kopyaları `axiom_p3_strdup` ile **kayıtsız** olarak ayırıyor; bu yüzden `free()` doğru. Sahiplik tablosu yalnızca dil seviyesine dönen `ax_str` üreticilerini izliyor.

### Kural (bundan sonrası için)

> `ax_str` döndüren bir fonksiyonun sonucu asla `free()` ile bırakılmaz; `axiom_str_release` (veya dil seviyesinde `str_free`) kullanılır. Ham `malloc`/`strdup` ile ayrılan iç tamponlar `free()` ile bırakılır.

---

## 2. `axpm update`

### Davranış

```bash
axpm update              # tüm git bağımlılıklarını yeniden çeker
axpm update <dep>        # yalnızca belirtilen git bağımlılığını
```

- Git bağımlılık dizinini siler, `install()` üzerinden yeniden klonlar.
- `axiom.lock` yeni içerik checksum'larıyla yeniden yazılır.
- `path:` bağımlılıkları yalnızca checksum yeniden hesaplanarak güncellenir.
- Git olmayan bir bağımlılık adı verilirse açık `KeyError` mesajı.

### Doğrulama

```bash
$ axpm add guplib --git /tmp/opencode/guplib
$ axpm verify
✓ Kilit doğrulaması başarılı: 1 paket

# kütüphaneye yeni commit
$ axpm update
↻ 'guplib' yeniden çekiliyor…
✓ Bağımlılıklar kilitlendi: 1 paket
✓ Güncelleme tamamlandı: 1 git bağımlılığı

$ axpm verify
✓ Kilit doğrulaması başarılı: 1 paket
$ grep -c added .axiom/deps/guplib/src/lib.ax
1
```

Checksum'ın gerçekten değiştiği testte doğrulanıyor.

### Komut seti (güncel)

```text
init, add, install, update, verify, tree, remove, build, run, test
```

---

## 3. Bellek Modeli Sınırı için Regresyon Testi

Önceki rapor “geçici ifade string'leri sahiplik tablosunda kalır” diyordu. Bu davranışı **hem belgeleyen hem de isimli değişkenlerde tablonun şişmediğini garanti eden** bir test eklendi.

```axiom
let mut s = ""
while i < 2000 { s = s + "x"; i = i + 1 }
print(len(s))            // 2000
print(str_owned_count()) // 1
```

```python
def test_owned_string_table_stays_bounded_for_named_variables():
    ...
    assert owned <= 5
```

Bu, ileride intrusive header'a geçildiğinde de korunması gereken bir sözleşme: **isimli değişken sayısı kadar** kayıt olmalı, iterasyon sayısı kadar değil.

`str_owned_count()` tanılama builtin'i checker ve codegen'e kayıtlı.

---

## 4. Deneysel Kodun İşaretlenmesi

Geçen turda denenen ve geri alınan ifade-bazlı temizlik fonksiyonları (`axiom_temp_mark`, `axiom_temp_release`) runtime'da kaldı. Yanlışlıkla etkinleştirilmemesi için başına açık uyarı eklendi:

```c
/* NOT: Asagidaki iki fonksiyon deneysel ifade-bazli temizlik icin ayrilmistir.
 * Codegen tarafindan KULLANILMAZ: kacis analizi tamamlanmadan etkinlestirmek
 * use-after-free uretir. Intrusive-header + String/str tip ayrimi sonrasi
 * guvenle kullanilabilir. */
```

---

## 5. Temizlik

- Proje kökündeki `tmp5hc42psm` (16 KB ELF derleme artığı) silindi.
- README test rozeti **577** olarak güncellendi.
- README `axpm` maddesine `update` eklendi.
- Proje kökünde `.gitignore` hâlâ yok; sürüm kontrolüne geçilirse eklenmesi önerilir.

---

## 6. Test Sonuçları

```bash
$ python3 -m pytest -q --no-header
577 passed in 317.71s (0:05:17)
```

| Grup | Sonuç |
|---|---|
| `test_package_manager.py` | 14/14 (+2) |
| `test_remaining_fixes.py` | 10/10 (+1) |
| `test_llvm_dwarf.py` | 3/3 |
| `test_memory_leak_deep.py` | 6/6 |
| `test_self_hosted.py` | 12/12 |
| `test_self_hosted_full_generics.py` | 5/5 |
| `test_offensive_feature_isolation.py` | 7/7 |

**Bootstrap:** `axiom build compiler/main.ax -o bin/axiomc` başarılı; `./bin/axiomc run examples/01_hello.ax` doğru.

---

## 7. Değiştirilen / Eklenen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `axiom/package_manager.py` | `update()` metodu + `update` CLI komutu |
| `axiom/runtime.h` | Deneysel temp fonksiyonlarına uyarı notu |
| `tests/test_package_manager.py` | `test_package_update_refetches_git_dependency`, `test_package_update_rejects_non_git_dependency` |
| `tests/test_remaining_fixes.py` | `test_owned_string_table_stays_bounded_for_named_variables` |
| `README.md` | Rozet 577, `axpm update` |
| `tmp5hc42psm` | Silindi |

---

## 8. Kalan İşler (güncel)

| # | İş | Neden / Durum |
|---|---|---|
| 1 | **Intrusive header + `String`/`str` tip ayrımı** | Geçici string sızıntısını ve LSan kör noktasını kökten çözer; diğer her şeyin temeli |
| 2 | Runtime `core` / `platform` ayrımı + WASI | Çapraz derleme ve WASM'ın ön koşulu |
| 3 | Gerçek registry veya git-only politikanın resmileşmesi | `update/verify/tree` var; registry yok |
| 4 | AST tabanlı self-hosted derleyici | Tam generics/sözleşme denetimi |
| 5 | `.gitignore`, `pyproject.toml`, CI matrisi | Süreç olgunluğu |
| 6 | Benchmark paketi | “C/Rust kadar hızlı” iddiası ölçülmedi |

### Önerilen sıra

```
1 → 2 → 5 (paralel) → 3 → 4 → 6
```

`5` (git + CI + paketleme) düşük eforla yüksek değer üretir; `1` ise en büyük teknik borç.

---

## 9. Sonuç

- Sahiplik tablosu ile ham `free()` çakışması **kalmadı**; kural yazılı hâle getirildi.
- `axpm` artık `update` ile gerçekten yeniden çekiyor ve kilidi yeniliyor.
- Bellek modelinin bilinen sınırı **testle sabitlendi** (isimli değişkenlerde tablo şişmiyor).
- Deneysel, tehlikeli kod açıkça işaretlendi.
- Test sayısı 577, bootstrap dahil yeşil.

Proje hâlâ alfa. Ancak bu turda eklenenler “iddia” değil, **doğrulanmış davranış**: `update` gerçekten yeni commit'i getiriyor, `verify` kurcalamayı yakalıyor, tablo isimli değişkenlerde büyümüyor.
