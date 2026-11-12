# P2-17 (kısmi) — Geçici String Sızıntıları

**Tarih:** 9 Kasım 2026
**Görev:** `TODO.md` → P2-17
**Durum:** ✅ bu turun kapsamı tamamlandı (intrusive-header refactor `P2-17b` olarak ertelendi)

---

## 1. Başlangıç: ölçüm

README'de "bilinen sınır" olarak yazılı olan iddia teste döküldü:

```axiom
fn make(s: str) -> str { return s + "-x" }

fn main() -> int {
    let base = str_owned_count()
    let mut i = 0
    while (i < 100) { print(make("b")); i = i + 1 }
    print("after_print:", str_owned_count() - base)
}
```

```
after_print: 100     ← her iterasyonda 1 string sızıyor
```

Yüz iterasyonda 100 string, yani sızıntı **doğrusal**. Uzun süre çalışan bir
tarayıcı/daemon için gerçek sorun.

## 2. Kök nedenler (üç ayrı hata)

### 2.1 `PrintStmt` hiç temizlik yapmıyordu

`let` ve atama yollarında `axiom_temp_mark()` / `axiom_temp_release_keep()`
çifti vardı; `print(...)` ve çıplak ifade deyimleri bu mekanizmayı
kullanmıyordu.

### 2.2 `axiom_temp_release_keep` "saklanan" değeri görünmez yapıyordu

Fonksiyon gövdesi `ret_val`'ı `keep` ile koruyor, ancak günlük kaydını
tamamen çıkarıyordu. Çağıran kapsam o değeri artık göremediği için:

```axiom
print(make("b"))   # make içinde keep edildi -> dış kapsam göremedi -> sızdı
```

Düzeltme: saklanan değer günlüğe **geri konur** (aynı `seq` ile). Dış kapsam
kendi `temp_release`'i ile bırakır. Adres yeniden kullanımı `seq` damgasıyla
ayrıştırıldığı için yanlış serbest bırakma olmaz.

### 2.3 `continue` / `break` kapsam temizliğini atlıyordu

Kapsam temizliği derleyici tarafından **blok sonuna** yazılıyor; `continue`
oraya hiç ulaşmıyor. Sonuç:

```axiom
while (i < 300) {
    let v = make("a")      # sahipli
    if len(v) > 0 { continue }   # v hiç bırakılmıyor
}
```

Ölçüm: `withconte: 300`.

## 3. Düzeltmeler

### 3.1 `PrintStmt` ve `ExprStmt` sarmalama (`codegen_c.py`)

```c
{
  ax_int _ax_tm1 = axiom_temp_mark();
  axiom_print_str(ax_make("b"));
  axiom_temp_release(_ax_tm1);
}
```

Yalnızca geçici üretebilecek ifadelerde sarmalanır
(`_expr_may_alloc_str`); literal/identifier gibi kesin üretmeyenlerde ek kod
yok. Gereksiz durumda bile `mark/release` zararsızdır (boş döngü).

### 3.2 `axiom_temp_release_keep` (runtime)

Saklanan değer, günlüğe geri itilir. Böylece **hem** `let v = f(x)` sahipliği
korunur **hem** `print(f(x))` dış kapsamda bırakılabilir hale gelir.

### 3.3 Kısmi döngü temizliği (`_capture_loop_cleanup`)

`break`/`continue` öncesi yalnızca **döngü gövdesine ait** kapsamlar temizlenir:

| Kapsam | Temizlenir? |
|---|---|
| Döngü gövdesinde tanımlı `str`/dizi | ✅ |
| Döngü gövdesindeki `defer` | ✅ (kapsam çıkışı) |
| Döngü dışında tanımlı değişken | ❌ dokunulmaz |

Döngü girişinde `(owned_str_depth, owned_array_depth, defer_depth)` işaretçisi
saklanır; temizlik bu derinlikten aşağısına uygulanır.

## 4. Doğrulama

| Senaryo | Önce | Sonra |
|---|---|---|
| `print(make(x))` × 500 | +500 | **0** |
| Çıplak `make(x)` × 500 | +500 | **0** |
| `continue` × 300 | +300 | **0** |
| `break` × 1 | +1 | **0** |
| İç içe döngü, dış değişken bozulması | — | **0** (bozulmuyor) |
| `defer` + `continue` × 5 | — | **5 kez çalışıyor** |
| ASan (C ve LLVM, 800 iterasyon) | — | **temiz** |

## 5. Testler — 15

`tests/test_temp_string_cleanup.py`:

| Grup | Kapsam |
|---|---|
| Sayısal büyüme (C) | `print`, çıplak ifade, `let`, iç içe çağrı zinciri |
| Davranış (C+LLVM) | Temizlik sonrası değerler doğru mu, dış kapsam korunuyor mu |
| `continue`/`break` (C) | Sızıntı yok |
| İç içe döngü (C+LLVM) | Dış değişken bozulmuyor |
| `defer` + `continue` (C+LLVM) | Kapsam çıkışı semantiği |
| ASan (C+LLVM) | Gerçek sızıntı yok |
| Belge | README'de eski sınır kalmadı |

## 6. Kapsam dışı bırakılan (dürüst kayıt)

**Intrusive header + `String`/`str` tip ayrımı** yapılmadı. Gerekçe:

- Mevcut refcount tablosu **alias güvenliğini zaten sağlıyor**; bu turda
  kanıtlanan sızıntılar tablo mekanizmasının değil, codegen'in eksik
  temizliğinden kaynaklanıyordu.
- Ayrım 82 fonksiyon / 277 çağrıya dokunur ve ABI değiştirir → tek başına tur.

`P2-17b` olarak TODO'da kayıtlı; faydası performans ve ABI netliği, güvenlik
değil.

## 7. Bilinen, kapsam dışı ASan bulguları (önceden vardı)

`examples/` ASan taraması 18/21 temiz. Üç istisna **bu değişiklikten önce de**
aynıydı (geri alınarak doğrulandı):

| Örnek | Bulgu | Neden |
|---|---|---|
| `10_packet1_security_suite.ax` | 89 B sızıntı (`base64_encode` sonucu) | Demo, `let` ile tutup bırakmıyor |
| `15_redteam_offensive_suite.ax` | SEGV (`axiom_exec_mem_run`) | ASan mmap'lenmiş shellcode çalıştıramaz |
| `21_axiom_scan.ax` | exit 1 | CLI alt komut istiyor (araç, sızıntı değil) |

## 8. Durum

```bash
python3 -m pytest -q --no-header
# 917 passed, 2 skipped in 681.25s
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **917** (+15) |
| C örnekleri | 21/21 |
| LLVM örnekleri | 21/21 |
| Bellek testleri (ASan dahil) | 40/40 |
| `make fmt-check` | ✅ |
| Bootstrap | ✅ |

## 9. Sıradaki

| # | İş | Not |
|---|---|---|
| 1 | **P2-18** self-hosted 4/21 → 8/21 | "Python'suz" iddiasını güçlendirir |
| 2 | P2-17b intrusive header | Teknik borç; güvenlik değil performans |
| 3 | Faz 3 hazırlığı | Sosyal/stratejik (paket, kullanıcı) |
