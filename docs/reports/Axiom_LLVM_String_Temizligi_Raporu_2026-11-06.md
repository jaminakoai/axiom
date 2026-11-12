# Axiom (λx) — LLVM String Temizliği ve Ajan Turları

**Tarih:** 6 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Kapsam:** `~/Desktop/axiom`
**Önceki rapor:** `Axiom_LLVM_Esitligi_Raporu_2026-11-06.md`

---

## 0. Özet

İki arka uç arasındaki **son bilinen eşitsizlik** kapatıldı: LLVM artık string kapsam temizliği üretiyor. Ayrıca keşif ajanlarıyla intrusive-header geçişi için tam harita çıkarıldı ve bir doküman ajanı kullanıcı rehberi yazıyor.

| İş | Durum |
|---|---|
| LLVM'de string kapsam temizliği (döngü, if/else, return) | ✅ |
| Kaçış analizi (struct alanı, dizi, çağrı argümanı, return) | ✅ |
| LLVM'de `retain`/`release`/`owned_release` bildirimleri | ✅ |
| 6 yeni LLVM sahiplik testi | ✅ |
| Intrusive-header geçiş haritası (ajan) | ✅ Rapor alındı, uygulama ayrı tura |
| `docs/TUTORIAL.md` (ajan, arka planda) | ⏳ |

**Test durumu:** `609 passed` (önceki 603; +6).

---

## 1. Ajan kullanımı

| Ajan | Görev | Çıktı |
|---|---|---|
| `explore` | `ax_str` sahiplik temas noktaları haritası | 82 `ax_str` fonksiyonu, 277 `wrap` çağrısı, codegen üretim satırları, test eşikleri |
| `explore` | LLVM string temizliği boşluğu analizi | C'deki kapsam altyapısının satır haritası + LLVM için minimal değişiklik planı |
| `general` (arka plan) | `docs/TUTORIAL.md` kullanıcı rehberi | Devam ediyor |

İlk iki rapor doğrudan uygulamaya girdi: LLVM temizliğinde hangi metotların karşılığı gerektiği ve hangi kaçış noktalarının korunması gerektiği buradan çıktı.

---

## 2. Neden intrusive header bu turda yapılmadı

Keşif raporu net bir tablo verdi:

- **82** adet `ax_str` döndüren runtime fonksiyonu
- **277** `axiom_owned_str_wrap(...)` çağrısı
- 51 yerde global tablo (`g_axiom_owned_tbl`) referansı
- 16 fonksiyonda `malloc`/`strdup` + `free` çifti (header'a geçerken yeniden yazılmalı)
- `axiom_temp_release_keep` gibi mekanizmalar **numaralandırma** için günlüğe bağlı; header tek başına yetmiyor

Bu, tek oturumda güvenle yapılabilecek bir değişiklik değil: alias hataları sessizce use-after-free'ye dönüşür. Bir sonraki tura ayrıldı ve haritası hazır.

---

## 3. LLVM string kapsam temizliği

### Önce

```axiom
fn main() -> int {
    let s = "a" + "b"
    print(s)
    return 0
}
```

LLVM IR'de `axiom_str_concat` çağrılıyor, sonuç `alloca`'ya yazılıyor ve **hiç bırakılmıyordu**. `axiom_str_release` ne bildiriliyordu ne çağrılıyordu.

### Sonra

IR artık şunları içeriyor:

```llvm
declare void @axiom_str_retain(i8*)
declare void @axiom_str_release(i8*)
declare void @axiom_str_owned_release(i8**)

; ... let s = "a" + "b"
%concat = call i8* @axiom_str_concat(i8* %a, i8* %b)
%var.s = alloca i8*, align 8
store i8* %concat, i8** %var.s, align 8
; ... kapsam sonu
call void @axiom_str_owned_release(i8** %var.s)
```

### Kapsam noktaları

| Yer | Davranış |
|---|---|
| Fonksiyon gövdesi | Kapsam açılır, çıkışta release |
| `while` gövdesi | Her turda release (back-edge'den önce) |
| `for` gövdesi | Her turda release (artırma öncesi) |
| `if` / `else` dalları | Dal sonunda, merge'e gitmeden release |
| Erken `return` | Tüm açık kapsamlar release edilir |

### Kaçış analizi (kritik)

Release etmek use-after-free üretebileceği için şu durumlarda değişken "kaçar" sayılır ve **bırakılmaz**:

- Fonksiyon çağrısına argüman (`show(s)`)
- Struct alanına atama / struct init (`P { name: s }`)
- Dizi elemanına atama / dizi literali
- `return` edilen değer (ayrıca caller için `retain`)

Bu, C arka ucundaki `_mark_escape` ile aynı semantik.

### Doğrulama örnekleri

```axiom
// Alias: b = a, sonra c = a + "-x"
let a = "hello" + "world"
let b = a
let mut c = a
c = c + "-x"
print(a)   // helloworld  (bozulmuyor)
```

```axiom
// Struct alanı ve çağrı argümanı kaçar
let p = build(7)
print(p.name, p.n)     // item7 7
print(show(s))          // 6
print(s)                // abcdef
```

```axiom
// Erken dönüşte defer + release
fn choose(flag: bool) -> str {
    if flag { let s = "yes" + "!"; return s }
    let t = "no" + "?"; return t
}
```

Hepsi C arka ucuyla **birebir aynı** çıktıyı veriyor.

---

## 4. Testler

`tests/test_llvm_string_ownership.py` (6 test):

| Test | Ne doğrular |
|---|---|
| `test_llvm_emits_scope_release_calls` | IR'de `axiom_str_owned_release` bildirimi ve çağrısı |
| `test_llvm_loop_body_releases_each_iteration` | Döngü gövdesinde back-edge öncesi release |
| `test_llvm_string_loop_matches_c_output` | C ile aynı sonuç (`T: 1090`) |
| `test_llvm_string_alias_is_not_double_released` | `b = a` alias'ı bozmuyor |
| `test_llvm_returned_string_survives_caller` | Dönen string çağıranda geçerli |
| `test_llvm_escaped_string_in_struct_and_call_arg` | Struct/argüman kaçışı güvenli |

```bash
$ python3 -m pytest -q --no-header
609 passed in 354.69s (0:05:54)
```

| Kontrol | Sonuç |
|---|---|
| LLVM örnekleri | 19/19 |
| LLVM + `--asan` (20.000 iterasyon) | sıfır hata |
| C + `--asan` (aynı program) | sıfır hata |
| `bin/axiomc` bootstrap | ✅ |
| `make fmt-check` | ✅ |

---

## 5. Benchmark (değişmedi)

| İş | Axiom | C -O3 | Python | Axiom/C |
|---|---:|---:|---:|---:|
| Fibonacci (n=30) | 0.0050s | 0.0033s | 0.1476s | **1.51×** |
| String birleştirme (20.000) | 0.0031s | 0.0007s | 0.0201s | 4.58× |
| Dizi büyütme (100.000) | 0.0018s | 0.0011s | 0.0228s | **1.67×** |
| Base64 (20.000) | 0.0041s | 0.0007s | 0.0277s | 6.34× |
| Matris (64×64) | 0.0015s | 0.0007s | 0.0441s | **2.18×** |

LLVM temizliği C arka ucunu etkilemedi (ölçümler aynı).

---

## 6. Değiştirilen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `axiom/codegen_llvm.py` | String sahiplik kapsamları, kaçış analizi, `retain`/`release`/`owned_release` bildirim ve çağrıları, döngü/dal/return temizliği |
| `tests/test_llvm_string_ownership.py` | **Yeni** — 6 test |
| `README.md`, `CHANGELOG.md` | LLVM string temizliği, test sayısı 609 |
| `docs/TUTORIAL.md` | Ajan tarafından yazılıyor (bu turun sonunda) |

---

## 7. İki arka ucun güncel durumu

| Özellik | C | LLVM |
|---|---|---|
| `requires`/`ensures`/`verify` | ✅ | ✅ |
| `defer` (LIFO) | ✅ | ✅ |
| `?` / `Result` | ✅ | ✅ |
| `main -> Result` | ✅ | ✅ |
| String kapsam temizliği | ✅ | ✅ *(bu tur)* |
| String dizi (`str[]`) temizliği | ✅ | ⚠️ henüz yok |
| Diğer geçici ifade string'leri | ⚠️ (`print(f(x))`) | ⚠️ |
| DWARF (`-g`) | `#line` | tam metadata |

**Kalan eşitsizlik:** LLVM'de `str[]` (dizi) sahiplik temizliği yok. C'de `axiom_array_str_free` üretiliyor. Ayrıca her iki arka uçta `print(f(x))` gibi atama yapılmayan geçici string'ler tabloda kalıyor.

---

## 8. Sıradaki İşler

| # | İş | Not |
|---|---|---|
| 1 | **Intrusive header + `String`/`str`** | Harita hazır (82 fonksiyon, 277 çağrı). Kalan tek büyük bellek borcu; `print(f(x))` sızıntısını ve kilit maliyetini kapatır |
| 2 | LLVM'de `str[]` temizliği | C ile tam eşitlik |
| 3 | Gerçek JSON parser | `Result` katmanı hazır, parser sığ |
| 4 | HTTP/1.1 chunked + Content-Length | `http_body` ham |
| 5 | Registry politikası | Paket ekosistemi |
| 6 | `docs/TUTORIAL.md` gözden geçirme | Ajan çıktısı doğrulanacak |

**Öneri:** 1 numara. Artık önünde hiçbir engel yok ve haritası çıkarıldı; ancak alias güvenliği için ayrı, odaklı bir tur gerektiriyor.
