# Axiom (λx) — Sıradaki İşlerin Uygulanması Raporu

**Tarih:** 6 Kasım 2026
**Sürüm:** `v0.5.0-alpha`
**Kapsam:** `~/Desktop/axiom`
**Önceki rapor:** `Axiom_Kismi_Maddeler_Dogrulama_Raporu_2026-11-05.md`

---

## 0. Özet

Bu turda dört iş ele alındı. Üçü tamamlandı, biri **bilinçli olarak geri alındı** çünkü güvenli olmadığı testlerle kanıtlandı.

| İş | Durum |
|---|---|
| 1. Geçici (temporary) string temizliği | ⚠️ **Denendi, geri alındı** — self-hosted derleyicide use-after-free üretti |
| 2. `axpm verify` / `tree` / `remove` | ✅ **Tamamlandı** |
| 3. LLVM `DILocalVariable` (değişken düzeyi debug) | ✅ **Tamamlandı** |
| 4. Ofansif modül + bellek + DWARF doküman senkronu | ✅ **Güncellendi** |

**Test durumu:** `574 passed` (önceki 572; +2 yeni test).

**Dürüst not:** Geçici string temizliği, ifade düzeyinde kaçış analizini eksiksiz yapmadan uygulanamaz. Basit bir “ifade sonunda üretilen her string'i bırak” yaklaşımı, AST'ye/struct'a/dönüş değerine kaçan string'leri de serbest bırakıyor. Bunu bu turda somut olarak gördük ve geri aldık.

---

## 1. Geçici String Temizliği — Denendi ve Geri Alındı

### Ne yapıldı

- `runtime.h` içine `axiom_temp_mark()` / `axiom_temp_release(mark)` eklendi.
- Sahiplik kayıtlarına monoton artan `seq` alanı eklendi.
- `codegen_c.py` içinde `print`, `verify`, `let`, atama ve ifade ifadeleri için “işaret al → ifadeyi üret → işaretten sonra oluşan string'leri bırak” mantığı uygulandı.

### Sonuç

Tek başına küçük programlarda çalıştı:

```bash
# 5.000 kez geçici base64_encode
$ axiom run --asan tempfix.ax
OWNED: 0        # tablo şişmiyor, sızıntı yok
```

### Neden geri alındı

`bin/axiomc` (kendi kendine derlenen derleyici) **bozuldu**:

```bash
$ ./bin/axiomc run examples/01_hello.ax
/tmp/axiom_run_tmp.c:7:1: error: use of undeclared identifier 'nn'
ax_eeet(ax_eeet);
source file is not valid UTF-8
```

`axiomc emit-c` çıktısı ikili çöp üretti. Kök neden: `compiler/*.ax` yoğun şekilde `res_new(code, pos)` deseniyle **string'i AST düğümüne kaçırıyor**. Geçici temizlik, AST'de hâlâ referans verilen string'i serbest bıraktı → use-after-free.

Bu, tam olarak “tip düzeyinde sahiplik / intrusive header” modelinin neden gerekli olduğunu gösteriyor: kaçış yollarının tamamı (AST, struct alanı, dizi, dönüş değeri, `defer`, thread) kapatılmadan ifade bazlı temizlik güvenli değil.

### Geri alma doğrulaması

- `axiom/codegen_c.py` geçici temizlik kodu kaldırıldı.
- `bin/axiomc` yeniden derlendi, `examples/01_hello.ax` doğru çalışıyor.
- Tam test paketi: **572 → 574** (yeni testlerle) yeşil.

### Kalan durum (README’de dürüstçe yazılı)

- İsimli string değişkenleri, `file_read`/`str_split`/base64/hex/hash gibi üreticiler ve `array_push` sonuçları kapsam çıkışında temizleniyor.
- `print(f(x))` gibi **ifade içi geçici** string'ler sahiplik tablosunda kalıyor.
- Öneri: sonucu değişkene atayın veya `defer { str_free(x) }` kullanın.
- Kalıcı çözüm: sıradaki bölümde.

### Kalıcı çözüm önerisi (sıradaki iş)

1. **Intrusive header:** `malloc` edilen string'in başına `{refs, len, cap}` yaz; dönen pointer header'dan sonrası. Global tablo tamamen kalkar, LSan kör noktası kapanır.
2. **Tip düzeyi sahiplik:** `String` (sahipli) / `str` (ödünç) ayrımı; `String` atamada taşınır, kapsamda `drop` edilir. Kaçış analizi gerekmez.
3. O aşamada ifade bazlı geçici temizlik **otomatik olarak** doğru çalışır.

---

## 2. Paket Yöneticisi — ✅ Tamamlandı

### Eklenen komutlar

```bash
axpm verify   # axiom.lock checksum'larını yerel bağımlılıklarla karşılaştır
axpm tree     # bağımlılık ağacı + kilitli sürüm + checksum öneki
axpm remove <dep> [--purge]   # manifest + lock'tan kaldır, istenirse git dizinini sil
```

### Doğrulama

```bash
$ axpm tree
appx v0.1.0
  ├── libx 0.1.0 [path:../libx]
  │   └── checksum 5e2996ea41b5155d…

$ axpm verify
✓ Kilit doğrulaması başarılı: 1 paket

# Bağımlılık dosyası kurcalanınca:
$ echo "fn hacked() -> int { return 1 }" >> ../libx/src/lib.ax
$ axpm verify
✗ Kilit doğrulaması başarısız: 'libx' için SHA-256 uyumsuzluğu.
  Kilitli: 5e2996ea41b5155d…
  Gerçek : 06180ee86758abc6…
exit 1

$ axpm remove libx
✓ Bağımlılık kaldırıldı: 'libx'
```

### Test

`tests/test_package_manager.py::test_package_verify_tree_and_remove` eklendi:
- verify başarılı,
- tree çıktısı isim/checksum içeriyor,
- tamper tespiti,
- remove sonrası manifest ve lock temiz.

**Sonuç:** 12/12 paket yöneticisi testi geçiyor.

### Hâlâ açık

- Merkezi registry yok (açık hata veriyor).
- Semver çözümleme, transitive graph, imza doğrulama yok.
- `axpm update` yok.

---

## 3. LLVM `DILocalVariable` — ✅ Tamamlandı

### Ne eklendi

- `!DIBasicType` tanımları: `i64`, `double`, `bool`, `char*`.
- Her `let` için `!DILocalVariable(name, scope, file, line, type)`.
- Her değişken alloca'sından sonra `llvm.dbg.declare` çağrısı.
- `declare void @llvm.dbg.declare(metadata, metadata, metadata)`.

### Doğrulama

```bash
$ axiom emit-llvm -g prog.ax | grep -c DILocalVariable
2
$ axiom emit-llvm -g prog.ax | grep -c dbg.declare
3

$ axiom build -g --backend=llvm prog.ax -o prog && prog
V: 42

$ readelf --debug-dump=info prog
 <2><3f>: Abbrev Number: 3 (DW_TAG_variable)
    <44>   DW_AT_name : s
```

GDB/LLDB artık `print s` ile yerel değişkeni gösterebilir (optimizasyon seviyesine bağlı olarak).

### Test

`tests/test_llvm_dwarf.py::test_llvm_dwarf_emits_local_variables` eklendi:
- IR'de `!DILocalVariable`, `llvm.dbg.declare`, `name: "product"`, `name: "result"`,
- ikilide `DW_TAG_variable` ve değişken adı.

**Sonuç:** DWARF testleri 3/3 geçiyor.

---

## 4. Dokümantasyon Senkronu

`README.md` güncellendi:

- Test rozeti **574**.
- `axpm` maddesi: `verify/tree/remove` ve gerçek checksum doğrulaması.
- LLVM maddesi: `DILocalVariable` ve `readelf --debug-dump=info` ile değişken görüntüleme.
- Bellek modeli maddesi: geçici string sınırı açıkça yazılı (bu turda geri alınan iş).

---

## 5. Değiştirilen / Eklenen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `axiom/package_manager.py` | `verify()`, `tree()`, `remove_dependency()`, CLI komutları |
| `axiom/codegen_llvm.py` | `DILocalVariable`, `dbg.declare`, DIBasicType, `_current_loc_id` |
| `axiom/runtime.h` | JWT double-free düzeltmesi (`free` → `axiom_str_release`), b64url yardımcıları `static char*` |
| `axiom/codegen_c.py` | Geçici temizlik denemesi geri alındı (kararlı hâl) |
| `tests/test_package_manager.py` | +1 test (verify/tree/remove) |
| `tests/test_llvm_dwarf.py` | +1 test (DILocalVariable) |
| `README.md` | Rozet + 3 sınırlama maddesi güncellendi |

---

## 6. Yan Bulgu ve Düzeltme: JWT Double-Free

Geçici temizlik denenirken ortaya çıkan gerçek bir hata:

```
ERROR: AddressSanitizer: attempting double-free
  #1 axiom_jwt_create_hs256
```

**Neden:** `axiom_jwt_get_header` / `axiom_jwt_get_payload` artık sahiplik tablosuna kayıtlı string döndürüyor; `jwt_verify_hs256` ise bunları ham `free()` ile bırakıyordu. Ayrıca `axiom_internal_b64url_encode/decode` kendi içinde kayıt yapıp üst katmanın `free()` etmesi çift serbest bırakmaya yol açıyordu.

**Düzeltme:**
- `jwt_verify_hs256` içindeki `free(...)` çağrıları `axiom_str_release(...)` oldu.
- `axiom_internal_b64url_encode/decode` `static char*` yapıldı ve içeride kayıt yapmıyor; sahiplik üst katmanda.

**Doğrulama:**

```bash
$ axiom run --asan jwt.ax
TOKEN: eyJhbGciOiJIUzI1NiIs…
VALID: true
# ASan hatası yok
```

Bu düzeltme, sahiplik tablosunun tüm runtime'a yayılmasının yan etkilerini gösteriyor: ham `free()` çağrıları tek tek `axiom_str_release`'e çevrilmeli.

---

## 7. Test Sonuçları

```bash
$ python3 -m pytest -q --no-header
574 passed in 316.67s (0:05:16)
```

- Önceki: 572 → **+2 test**
- `test_package_manager.py`: 12/12
- `test_llvm_dwarf.py`: 3/3
- `test_memory_leak_deep.py`: 6/6
- `test_self_hosted.py`: 12/12
- `test_self_hosted_full_generics.py`: 5/5
- `test_offensive_feature_isolation.py`: 7/7
- `test_remaining_fixes.py`: 9/9

**Bootstrap:** `axiom build compiler/main.ax -o bin/axiomc` başarılı; `./bin/axiomc run examples/01_hello.ax` doğru.

---

## 8. Kalan İşler (öncelik sırası)

| # | İş | Neden |
|---|---|---|
| 1 | Intrusive header + `String`/`str` tip ayrımı | Geçici string sızıntısını ve LSan kör noktasını kökten çözer |
| 2 | Runtime `core` / `platform` ayrımı + WASI hedefi | Çapraz derleme ve WASM’ın ön koşulu |
| 3 | Registry politikası (git-only’yi tamamla veya gerçek registry) | `axpm` vaadi |
| 4 | Ham `free()` çağrılarını `axiom_str_release`’e tarama | Sahiplik tablosu tutarlılığı |
| 5 | AST tabanlı self-hosted derleyici | Tam generics ve sözleşme denetimi |

---

## 9. Sonuç

- **Yapılan ve doğrulanan:** `axpm verify/tree/remove`, LLVM `DILocalVariable`, JWT double-free düzeltmesi, doküman senkronu.
- **Denenip geri alınan:** ifade düzeyi geçici string temizliği. Gerekçe ve kanıt raporda; riskli kodu bırakmak yerine kararlı duruma dönüldü.
- **Test güvencesi:** 574 test, bootstrap dahil yeşil.

Proje hâlâ alfa; ancak bu turda eklenen üç özellik (paket doğrulama, değişken düzeyi debug, JWT bellek güvenliği) üretime yaklaşma yolunda somut ve testli kazanımlar.
