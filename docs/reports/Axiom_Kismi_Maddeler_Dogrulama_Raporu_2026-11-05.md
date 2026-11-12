# Axiom (λx) — Kısmi Maddeler Doğrulama Raporu

**Tarih:** 5 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Kapsam:** `~/Desktop/axiom`
**Yöntem:** Kaynak incelemesi + gerçek derleme/çalıştırma + ASan/LSan + tam test paketi
**Önceki rapor:** `Axiom_Kalanlar_Duzeltme_Raporu_2026-11-05.md`

---

## 0. Yönetici Özeti

Önceki turda “kısmi” bırakılan altı başlıktan **dördü gerçekten kapatıldı**:

| # | Başlık | Durum |
|---|---|---|
| A | Genel heap string sahipliği | 🟡 **Büyük ölçüde kapandı** (isimli değişkenler + üreticiler); geçici ifadelerde açık var |
| B | Ofansif modül izolasyonu | ✅ **Kapandı** (`--features offensive`) |
| C | Merkezi registry | ❌ **Yapılmadı** (hâlâ açık hata veriyor) |
| D | Çapraz derleme / WASM | ❌ **Yapılmadı** (platform katmanı yok) |
| E | LLVM DWARF | ✅ **Kapandı** (IR + ikili satır bilgisi) |
| F | Self-hosted tam generics | ✅ **Kapandı** (`Box<str>`, `Box<float>`, `Pair<T,U>`) |

Doğrulama sırasında **üç gerçek hata** bulundu ve düzeltildi:

1. `array_push` her eklemede eski tamponu sızdırıyordu → **1.000 eklemede 4 MB sızıntı**.
2. `base64_encode`, `hex_encode`, `hash_sha256`, `json_get_str` gibi **40 runtime üreticisi** sahiplik tablosuna kaydolmuyordu → döngüde sızıntı.
3. `str_split` dizi tamponu ve elemanları sahiplik takibine alınmıyordu.

Ayrıca sahiplik modelinin **ölçüm kör noktası** tespit edildi: global tablo, string'leri “erişilebilir” tuttuğu için **LeakSanitizer geçici sızıntıları görmüyor**. Bu, yeni bir testin yeşil geçmesinin sızıntı olmadığı anlamına gelmediğini gösteriyor.

**Test durumu:** `572 passed` (önceki 570; +2 array_push regresyon testi).

---

## 1. A — String Sahipliği

### Mevcut uygulama

- `axiom_owned_str_wrap` / `axiom_str_retain` / `axiom_str_release` ile refcount.
- Global tablo **O(1) hash tablosu** (önceki lineer arama yerine) — bu iyileştirme doğru yönde.
- `codegen_c.py` kapsam çıkışında isimli string değişkenlerini `axiom_str_owned_release` ile bırakıyor; kaçış (escape) analizi var.
- `file_read`, `str_split`, `str_replace`, `str_sub`, `str_trim`, `str_join` üreticileri kayıt ediyor.

### Doğrulanan (ASan/LSan)

| Senaryo | Sonuç |
|---|---|
| 1.000 kez `s = s + "..."` | ✅ Sızıntı yok, 13.000 karakter doğru |
| 1.000 kez `file_read` | ✅ Sızıntı yok |
| 1.000 kez `str_split` | ✅ Sızıntı yok |
| 1.000 kez `str_replace` | ✅ Sızıntı yok |
| 1.000 kez `str_trim`/`str_sub` | ✅ Sızıntı yok |
| Fonksiyondan string döndürme | ✅ Sızıntı yok |
| Struct alanında string | ✅ Sızıntı yok |
| Dizi literalinde string | ✅ Sızıntı yok |
| String ataması (`s = f(i)`) | ✅ Sızıntı yok |
| `str_free` iki kez | ✅ Double-free yok |
| 2 thread'de string birleştirme | ✅ Çökme yok, 400/400 |
| 20.000 iterasyon | ✅ ~1,1 sn, sızıntı yok |
| `os_getenv` döngüsü | ✅ Çökme yok (dış pointer serbest bırakılmıyor) |

### Bu turda bulunan ve düzeltilen hatalar

#### A-1: `array_push` sızıntısı

```axiom
let mut arr: str[] = []
while i < 1000 { arr = array_push(arr, "s" + int_to_str(i)); i = i + 1 }
```

**Önce:** `SUMMARY: AddressSanitizer: 4004000 byte(s) leaked in 1000 allocation(s).`

**Neden:** Makro her eklemede yeni tampon ayırıyor, eskisini bırakmıyordu. Literal tamponları serbest bırakmamak için “sahiplik kaydı” yoktu.

**Çözüm:** `runtime.h` içine heap dizi tampon kayıt defteri eklendi (`axiom_heap_buf_track/untrack/release_if_owned`). `array_push`, `array_create_*`, `array_clone_*`, `str_split` ve SIMD fonksiyonları tamponlarını kaydediyor; serbest bırakma yalnızca kayıtlı tamponlarda yapılıyor.

**Sonra:** ✅ Sızıntı yok (hem `str[]` hem `int[]` hem struct dizileri test edildi).

#### A-2: 40 runtime string üreticisi kayıt edilmiyordu

`base64_encode`, `hex_encode`, `hash_sha256`, `json_get_str`, `html_escape`, `jwt_get_claim`, `aes256_cbc_encrypt`, `zlib_compress_str`, `tls_recv`, `ws_recv`, `pcap_next_packet` vb. ham `malloc` sonucu döndürüyordu.

**Önce:** 500 iterasyonda `base64_encode` + `hex_encode` → 20.000 byte sızıntı.

**Çözüm:** Tüm `AXIOM_RUNTIME_FN ax_str` üreticileri dönüş değerlerini `axiom_owned_str_wrap(...)` ile kaydediyor. `axiom_owned_str_wrap` artık:
- literal/statik metni `dladdr` ile ayırt edip **kaydetmiyor** (serbest bırakma riski yok),
- zaten kayıtlı pointer'da refcount'u **sıfırlamıyor** (alias güvenliği).

**Sonra:** ✅ Sızıntı yok.

#### A-3: `str_split` dizi tamponu

Dizi tamponu kayıt defterine alınmadığı için `axiom_array_str_free` tarafından serbest bırakılamıyordu. Düzeltildi.

### Kalan açık: geçici (temporary) string'ler

```axiom
while i < 300 { print(base64_encode("tmp-payload")) }
```

Bu ifadede üretilen string hiçbir değişkene atanmadığı için kapsam temizliği üretilmiyor; **sahiplik tablosunda kalıyor**.

**Ölçüm kör noktası:** Global tablo pointer'ı “erişilebilir” tuttuğu için LSan bunu sızıntı olarak raporlamıyor. Doğrudan tablo sayacıyla kanıt:

```c
for (int i = 0; i < 10000; i++) axiom_base64_encode("tmp-payload");
printf("%zu\n", g_axiom_owned_tbl.count);
// → 10000
```

Yani **tablo büyüyor, bellek büyüyor, test yeşil kalıyor**. Bu, önceki raporda önerilen “intrusive header” veya “tip düzeyinde `String`/`str`” modelinin neden gerekli olduğunu doğruluyor.

**Öneri (sıradaki adım):** İfade düzeyinde geçici temizliği:
- `print`, `verify`, koşullar ve atama dışı ifadelerde string döndüren çağrıları `{ const char* _t = ...; use(_t); axiom_str_release(_t); }` biçiminde üret.
- Orta vadede intrusive header + tip düzeyi sahiplik.

Bu açık README’de “Bilinen Sınırlamalar → 5” olarak dürüstçe belirtildi.

---

## 2. B — Ofansif Modül İzolasyonu → ✅ KAPANDI

**Doğrulama:**

```bash
$ axiom check offensive.ax
Hata: 'std:security:shellcode' ofansif güvenlik modülüdür.
      Yalnızca izinli test ortamlarında '--features offensive' bayrağı ile derlenebilir.
exit 1

$ axiom check --features offensive offensive.ax
✓ Doğrulama Başarılı (sembolik)
exit 0
```

- `axiom/resolver.py` içinde `identify_offensive_module` + `parse_features`.
- `AXIOM_FEATURES=offensive` ortam değişkeni de destekleniyor.
- `run`, `prove`, `emit-c`, `emit-llvm`, `emit-smt`, `build`, `check`, `axpm build` bayrağı kabul ediyor.
- `examples/15_redteam_offensive_suite.ax` varsayılan reddediliyor, bayrakla geçiyor.
- 7 testlik `tests/test_offensive_feature_isolation.py` mevcut.

**Not:** Modüller fiziksel olarak hâlâ `std/` altında; derleme zamanı reddi tedarik zinciri açısından yeterli. Ayrı pakete taşımak opsiyonel.

---

## 3. C — Merkezi Registry → ❌ YAPILMADI

```bash
$ axpm add bar --version 1.2.3
$ axpm install
Hata: 'bar' merkezi registry bağımlılığı (1.2.3) henüz desteklenmiyor.
      Bağımlılığı --path veya --git ile tanımlayın.
```

- Registry indirme/çözümleme kodu yok (`urllib`, tarball, imza, semver çözümü yok).
- `axpm verify`, `axpm tree`, `axpm update` komutları yok; yalnızca `init/add/install/build/run/test`.
- Davranış dürüst: sahte başarı vermiyor, açık hata veriyor. Ancak “registry yapıldı” denemez.

**Öneri:** Ya git-only politikası resmileştirilsin (tag + içerik-adresli cache + `verify`), ya da gerçek registry protokolü (indirme → doğrula → atomik kur) uygulanmalı.

---

## 4. D — Çapraz Derleme / WASM → ❌ YAPILMADI

```bash
$ axiom build examples/01_hello.ax --target wasm32-wasi -o h.wasm
fatal error: 'bits/libc-header-start.h' file not found
... WASI SDK kurun ... (deneysel)

$ axiom build examples/01_hello.ax --target aarch64-linux-gnu -o h_arm
... aarch64 cross-toolchain kurun ... (deneysel)
```

- `runtime.h` hâlâ POSIX'e gömülü: `epoll`, `pthread`, `mmap`, `dlfcn`, `/proc`, `cpuid` koşulsuz.
- `AXIOM_PLATFORM_*` / `__wasi__` katmanı yok.
- `std/target/wasm.ax` hâlâ yalnızca sihirli sayı ve export metadata'sı tutuyor; gerçek WASM ikilisi üretmiyor.
- `--sysroot` ve ön denetim var; hata mesajı iyi. Ama işlev yok.

**Öneri:** `runtime/core.h` + `runtime/posix.c` + `runtime/wasi.c` ayrımı; `--target` ancak CI'da `wasmtime` ile çalıştırılabiliyorsa “destekleniyor” sayılmalı.

---

## 5. E — LLVM DWARF → ✅ KAPANDI

**Doğrulama:**

```bash
$ axiom emit-llvm -g prog.ax | grep '!dbg' | wc -l
28

$ grep -m2 'DICompileUnit\|DISubprogram' prog.ll
!0 = distinct !DICompileUnit(language: DW_LANG_C99, file: !4, producer: "Axiom Compiler v0.5.0", ...)
!8 = distinct !DISubprogram(name: "ax_calc", scope: !4, file: !4, line: 1, ...)

$ axiom build -g --backend=llvm prog.ax -o prog && readelf --debug-dump=line prog | grep prog.ax
  1  0  0  0  prog.ax
```

- `!DIFile`, `!DICompileUnit`, `!DISubprogram`, `!DILocation`, `!dbg` referansları üretiliyor.
- İkili `.debug_line` tablosu kaynak dosya adını içeriyor.
- 17 örnek programın tamamı `--backend=llvm` ile derleniyor (ofansif örnek `--features offensive` ile).
- 2 testlik `tests/test_llvm_dwarf.py` mevcut.

**Kalan:** `DILocalVariable` / `llvm.dbg.declare` yok; değişken izleme henüz mümkün değil. README’de belirtildi.

---

## 6. F — Self-Hosted Tam Generics → ✅ KAPANDI

**Doğrulama:**

```axiom
struct Box<T> { val: T }
struct Pair<T, U> { first: T, second: U }
let a: Box<str> = Box<str> { val: "merhaba" }
let b: Box<float> = Box<float> { val: 2.5 }
let p: Pair<int, str> = Pair<int, str> { first: 7, second: "x" }
print(a.val, b.val, p.first, p.second)
```

```bash
$ ./bin/axiomc build prog.ax -o prog && ./prog
merhaba 2.5 7 x
```

- `Box<str>`, `Box<float>`, `Pair<int,str>`, `Pair<float,int>`, aynı programda çoklu özelleştirme çalışıyor.
- Generic fonksiyon dönüş tipi (`fn wrap<T>(x:T) -> Box<T>`) çalışıyor ve `42` basıyor.
- 5 testlik `tests/test_self_hosted_full_generics.py` hem Python hem `axiomc` için çalışıyor.
- Tip hataları artık `-Werror=int-conversion`, `-Werror=return-type`, `-Werror=string-compare` vb. ile reddediliyor.

**Kalan:** `compiler/` hâlâ parser içinde C üretiyor; tam monomorflaştırma AST düzeyinde değil. Egzotik kombinasyonlarda (generic generic içinde, constraint) sınırlar olabilir.

---

## 7. Bu Turda Düzeltilen Diğer Bulgular

| Bulgu | Etki | Durum |
|---|---|---|
| `array_push` eski tamponu bırakmıyordu | 4 MB / 1.000 ekleme | ✅ Düzeltildi |
| 40 string üreticisi kayıtsızdı | base64/hex/hash döngülerinde sızıntı | ✅ Düzeltildi |
| `str_split` tamponu kayıtsızdı | split döngüsünde 40 KB / 1.000 | ✅ Düzeltildi |
| `axiom_owned_str_wrap` literali kaydedebiliyordu | literal `free` riski | ✅ `dladdr` koruması |
| `axiom_owned_str_wrap` alias refcount'u sıfırlıyordu | erken serbest bırakma riski | ✅ Mevcut refcount korunuyor |
| `os_getenv` sonucunun serbest bırakılması | çökme | ✅ Dış pointer'lar sahiplik dışı |

**Eklenen regresyon testleri (2):**
- `test_array_push_loop_has_no_leak_under_asan`
- `test_int_array_push_loop_has_no_leak_under_asan`

---

## 8. Test Sonuçları

```bash
$ python3 -m pytest -q --no-header
572 passed in 311.45s (0:05:11)
```

- Toplam: **572** (önceki 570)
- Yeni: 2 (array_push sızıntı testleri)
- Alt test grupları:
  - `test_memory_leak_deep.py`: 6/6
  - `test_llvm_dwarf.py`: 2/2
  - `test_self_hosted_full_generics.py`: 5/5
  - `test_offensive_feature_isolation.py`: 7/7
  - `test_remaining_fixes.py`: 9/9
  - `test_self_hosted.py`: 12/12

**Bootstrap:** `axiom build compiler/main.ax -o bin/axiomc` → başarılı; `./bin/axiomc run examples/01_hello.ax` → doğru çıktı.

---

## 9. Dokümantasyon Güncellemeleri

- `README.md`
  - Test rozeti **572**.
  - Bellek modeli maddesi güncellendi: kapsam temizliği kapsamı + geçici string sınırı.
  - LLVM arka ucu: DWARF’ın artık üretildiği, `DILocalVariable` eksikliği.
  - Ofansif modüller için `--features offensive` notu ve 7. sınırlama maddesi.
  - Self-hosted generic kapsamı genişletildi.
- `SPECIFICATION.md` bellek modeli ifadeleri gerçek davranışla hizalandı.

---

## 10. Genel Hüküm

**Kısmi maddelerden A, B, E, F kapandı; C ve D açık.**

- A’da isimli değişkenler ve yaygın üreticiler için sahiplik gerçekten çalışıyor; ancak **geçici ifadeler** ve **LSan kör noktası** nedeniyle “tam bellek güvenliği” hâlâ iddia edilemez.
- B, E, F somut ve testli.
- C ve D, önceki raporda önerilen mimari işler (registry politikası, platform katmanı) yapılmadan kapanmaz.

**Öncelikli sonraki adımlar:**
1. Geçici string temizliği (ifade düzeyi) + tablo şişmesini önleme.
2. Registry politikası: git-only’yi tamamla (`verify`, `tree`, cache) veya gerçek registry.
3. Runtime’ı core/platform olarak böl; WASM’ı gerçekten derleyip `wasmtime` ile test et.
4. `DILocalVariable` ile değişken düzeyi debug.
5. AST tabanlı self-hosted mimariye geçiş (uzun vade).

**Not:** Proje kökünde `tmp5hc42psm` adlı 16 KB’lık bir ELF artığı var (16:04). Derleme çıktısı gibi görünüyor; sürüm kontrolüne girmemeli. `.gitignore` ve temizlik önerilir.
