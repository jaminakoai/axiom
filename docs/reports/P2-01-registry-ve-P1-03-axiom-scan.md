# P2-01 Registry v1 + P1-03 `axiom-scan` v0.1

**Tarih:** 8 Kasım 2026
**Görevler:** `TODO.md` → P2-01, P1-03
**Durum:** ✅ ikisi de tamamlandı (P1-03'te LLVM için ayrı görev açıldı)

---

## 1. P2-01 — Registry v1

### Ne vardı
`axpm add x --version 1.0` → **hata**: "merkezi registry henüz desteklenmiyor".
Yani ekosistem için tek engelleyici blok açıktı.

### Ne yapıldı
`axiom/registry.py` (~450 satır):

| Bileşen | Detay |
|---|---|
| Index | `<url>/index.json` — sürüm listesi, sha256, ed25519 imza, bağımlılıklar, `yanked` |
| Depo | içerik-adresli: `~/.axiom/cache/registry/sha256/<hash>/` |
| İmza | ed25519 detached, **openssl CLI** ile (yeni Python bağımlılığı yok) |
| Semver | `*`, kısmi (`1`, `1.2`), `=`, `^`, `~`, `>=`, `<=`, `>`, `<`, virgülle AND |
| Çözümleme | transitive, en yüksek uygun sürüm, döngü tespiti, sürüm çakışması |
| CLI | `axpm install`, `axpm search` yeni; `[registry]` manifest bölümü |

### Güvenlik — bulunan ve kapatılan açık

İlk uygulamada **önbellek isabeti doğrulamayı atlıyordu**: bozulmuş bir cache
sessizce kullanılırdı. Düzeltildi: tarball cache'te saklanıyor ve **her isabette
sha256 yeniden doğrulanıyor**; bozuksa atılıp yeniden indiriliyor.

| Tehdit | Karşı önlem | Test |
|---|---|---|
| Bozuk tarball | sha256, indirme **sonrası** | ✅ |
| Sahte paket | imza tarball baytları üzerinden | ✅ |
| İmzasız paket | varsayılan red | ✅ |
| Bozuk cache | yeniden doğrula + kendini onar | ✅ |
| `../` path traversal | arşiv üyesi `resolve()` kontrolü | ✅ |
| Döngü / yanked / çakışma | çözümleyicide | ✅ |

### Doğrulama
Gerçek `file://` registry + 3 sürümlü 2 paket ile uçtan uca:

```
$ axpm install
✓ Bağımlılıklar kilitlendi: 2 paket -> axiom.lock     # app-lib 0.3.0 + json-lib 1.2.0
$ axpm verify
✓ Kilit doğrulaması başarılı: 2 paket
$ axpm search json
json-lib 1.2.0 (2 sürüm)
```

`tests/test_registry.py` — **38 test**.

**Doküman:** `docs/REGISTRY.md`

---

## 2. P1-03 — `axiom-scan` v0.1

### Ne yapıldı

| Dosya | İçerik |
|---|---|
| `std/security/yara_rules.ax` | YARA kural **metni** ayrıştırıcı (`rule`/`strings:`/`condition:`) |
| `examples/21_axiom_scan.ax` | CLI: `rules`, `scan`, `pcap`; JSON çıktısı |

Desteklenen YARA alt kümesi: metin (`"..."`), hex wildcard (`{ 48 89 ?? 55 }`),
regex (`/.../`), koşullar `any of them` / `all of them` / `N of them`.
Çok satırlı `condition:` desteği var.

### Ölçüm

| Girdi | Süre | Hedef |
|---|---:|---|
| 1 MB | 0.008 s | — |
| 10 MB | 0.058 s | — |
| **103 MB** | **0.561 s** | < 2 s ✅ |

`ldd`: yalnızca `libz/libssl/libcrypto/libm/libc` — **libaxiom yok**, tek ikili.

### Yol boyunca bulunan 3 gerçek hata

1. **Girinti**: `strings:` / `condition:` satırları baştaki boşluk yüzünden
   tanınmıyordu → hiç desen eklenmiyordu.
2. **Çok satırlı `condition:`**: koşul alt satırdaydı, ayrıştırıcı yalnızca aynı
   satıra bakıyordu → tüm kurallar `any of them` oluyordu (`all` testi kırıldı).
3. **LLVM IR ters bölü**: kaçış dizisi olmayan `\` ham yazılıyordu →
   `c"\\00"` geçersiz sabit. İki ayrı escape bloğunda düzeltildi.

### Doğrulama

```
$ axiom-scan rules rules.yar
{"ok":true,"rules":3}
$ axiom-scan scan sample.txt --rules rules.yar
{"ok":true,"target":"...","scanned_bytes":26,
 "matches":[{"rule":"Suspicious_Powershell","pattern":"$a","offset":5,"length":15}]}
$ axiom-scan pcap test.pcap --rules rules.yar
{"ok":true,"pcap":"...","packets":[{"index":0,"rules":["Suspicious_Powershell"]}],
 "packet_count":1,"match_count":1}
```

Hata yolları: eksik dosya, `--rules` yok, bilinmeyen komut, kapatılmamış kural →
hepsi exit 1 + anlaşılır mesaj.

`tests/test_axiom_scan.py` — **13 test**.

---

## 3. Açılan yeni görev: P1-03b (dürüst sınır)

`axiom-scan` **LLVM arka ucunda yanlış sonuç** veriyor:

| Arka uç | Kural adları |
|---|---|
| C | `Suspicious_Powershell`, `Hex_Shellcode` ✅ |
| LLVM | `strings:`, `conditi` ❌ |

Derleme başarılı, çalışma zamanında `YaraRuleSet` bozuk. C varsayılan arka uç
olduğu için ürün çalışıyor; ama bu **sessiz yanlış sonuç** sınıfında, o yüzden
`[!]` (blocker) olarak TODO'ya yazıldı ve CI'da örnek yalnızca C ile derleniyor.

---

## 4. Durum

```bash
761 passed in 471.29s
```

| Kontrol | Sonuç |
|---|---|
| Toplam test | **761** (+51) |
| LLVM örnekleri | 19/19 (+21 hariç, P1-03b) |
| C örnekleri | 20/20 |
| `bin/axiomc` bootstrap | ✅ |
| `make fmt-check` | ✅ |

---

## 5. Sıradaki

| # | İş | Neden |
|---|---|---|
| 1 | **P1-03b** LLVM `axiom-scan` | Sessiz yanlış sonuç; LLVM eşitliği |
| 2 | **P1-04** kural motoru sağlamlaştırma | YARA/Sigma 14 fonksiyon testsiz |
| 3 | **P2-02** namespace | Düz isim alanı 250 pakette çakışır |
| 4 | **P2-03/04** `///` doc + İngilizce doküman | Paket yazarı için ön koşul |
