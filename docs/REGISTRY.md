# Axiom Registry v1 — Kullanım ve Protokol

**Durum:** uygulandı (P2-01)
**Modül:** `axiom/registry.py`
**Test:** `tests/test_registry.py` (59 test)

---

## 1. Neden

Registry olmadan:
- Dışarıdan paket çekilemez → dış katkı imkânsız
- Herkes kodu kopyala-yapıştır yapar → ekosistem oluşmaz
- Tedarik zinciri doğrulanamaz (imza yok, checksum içerik değil)

Registry v1 bunları çözer: **içerik-adresli depo + ed25519 imza + semver + transitive çözümleme**.

---

## 2. Yapılandırma

> **Yayın durumu:** `registry.axiom-lang.org` henüz dağıtılmamıştır ve şu anda
> çalışan bir registry adresi değildir. İstemcideki `DEFAULT_REGISTRY` değeri
> geçici hedef olarak bu alan adını gösterir. Registry adresi açıkça
> yapılandırılmadan `axpm add`, `install` veya `search` komutlarının bu adreste
> çalışmasını beklemeyin. Resmî hosting ve imza anahtarı işletimi hazır değildir.

`axiom.toml` içinde:

```toml
[registry]
url = "https://registry.axiom-lang.org" # henüz dağıtılmadı; aktif adres değildir
public_key = """
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAG...
-----END PUBLIC KEY-----
"""
# allow_unsigned = false        # varsayılan: imzasız paket REDDEDİLİR
```

Ortam değişkenleri (öncelikli):

| Değişken | Etki |
|---|---|
| `AXIOM_REGISTRY` | Registry URL'ini ezer |
| `AXIOM_REGISTRY_KEY` | Açık anahtarı ezer (PEM) |
| `AXIOM_ALLOW_UNSIGNED=1` | İmzasız paketlere izin verir |
| `AXIOM_CACHE_DIR` | Önbellek kökü (`<dir>/registry`) |

### Yerel `file://` registry ile uçtan uca deneme

Aşağıdaki akış, mevcut `packages/axiom-scan-report` örneğini geçici bir Ed25519
anahtarıyla imzalar, statik registry dizini oluşturur ve ayrı bir tüketici
projesine kurup test eder. Bash veya Zsh ile Linux/macOS üzerinde çalışır.
Paketleme, temiz ve commit edilmiş bir Git çalışma ağacı ister. Özel anahtar
yalnızca bu yerel deneme içindir; yayımlama anahtarı olarak kullanmayın.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
DEMO_ROOT="$(mktemp -d)"
AXPM="$REPO_ROOT/bin/axpm"

openssl genpkey -algorithm ED25519 -out "$DEMO_ROOT/demo-private.pem"
openssl pkey -in "$DEMO_ROOT/demo-private.pem" -pubout \
  -out "$DEMO_ROOT/demo-public.pem"

(cd "$REPO_ROOT/packages/axiom-scan-report" && \
  "$AXPM" pack --signing-key "$DEMO_ROOT/demo-private.pem" \
    --output "$DEMO_ROOT/packed")

"$AXPM" registry assemble --from "$DEMO_ROOT/packed" \
  --output "$DEMO_ROOT/registry" \
  --public-key "$DEMO_ROOT/demo-public.pem"

export AXIOM_REGISTRY="$(python3 -c \
  'from pathlib import Path; import sys; print(Path(sys.argv[1]).as_uri())' \
  "$DEMO_ROOT/registry")"
export AXIOM_REGISTRY_KEY="$(cat "$DEMO_ROOT/demo-public.pem")"

CONSUMER="$DEMO_ROOT/consumer"
"$AXPM" init "$CONSUMER"
(
  cd "$CONSUMER"
  "$AXPM" add axiom-scan-report --version 0.1.0
  "$AXPM" install
  mkdir -p tests
  cat > tests/test_registry.ax <<'AXIOM'
import "axiom-scan-report"

fn main() -> void {
    verify report_label(0, 0) == "no_findings"
    verify report_label(3, 1) == "high_severity_findings"
}
AXIOM
  "$AXPM" test
)
```

Başarılı son adım yeni tüketici iskeletinin örnek testiyle birlikte
`2/2 test başarılı` çıktısını verir. `DEMO_ROOT` altındaki
anahtar ve registry geçicidir. Bu yerel deneme internete yükleme yapmaz,
resmî paket yayımlamaz ve `index.json` için imza üretmez.

---

## 3. Kullanım

```bash
axpm add net-util --version "^0.3"
axpm install          # indirir, doğrular, açar, kilitler
axpm search json      # registry'de ara
axpm tree             # bağımlılık ağacı
axpm verify           # kilit vs. yerel içerik
```

`axiom.lock` her paket için `name`, `version`, `source = "registry:<ver>"`,
`checksum` (dizin içeriği), `sha256` (tarball) ve `dependencies` yazar.

### İmzalı paket hazırlama

`axpm pack --signing-key /secure/path/registry-ed25519.pem --output /tmp/registry`
komutu temiz Git deposunun kökündeki veya bir alt dizinindeki paket için commit
edilmiş normal dosyalardan deterministik tarball ve `<sürüm>.index-entry.json`
üretir. Depodaki izlenen hiçbir dosya değişmemiş olmalıdır. `axiom.lock`, build çıktıları,
yaygın özel anahtar biçimleri ve `.env` dosyaları pakete alınmaz; symlink ve
özel Git girdileri reddedilir. Giriş dosyası Git tarafından izlenmeli ve commit
edilmiş olmalıdır. İmza anahtarı depo dışında tutulmalıdır; şifreli anahtar için
`AXIOM_REGISTRY_SIGNING_PASSPHRASE` kullanılabilir.

Bu komut dosyaları registry'ye yüklemez veya `index.json`'ı değiştirmez.
Çıktıdaki tarball registry paket yoluna taşınmalı ve index entry, registry
yöneticisinin onayladığı index'e eklenmelidir. Otomatik `publish` veya resmi
paket yayın altyapısı henüz yoktur.

### Yerel statik Registry dizini oluşturma

Bir veya daha fazla doğrulanmış `axpm pack` çıktısını Registry v1'in beklediği
dosya düzenine çevirmek için:

```bash
axpm registry assemble \
  --from /tmp/packed-artifacts \
  --output /tmp/registry-static \
  --public-key /secure/path/registry-ed25519.pub.pem
```

Komut her arşivin SHA-256 ve Ed25519 imzasını, paket içindeki `axiom.toml`
metadata'sını ve güvenli tar yollarını kontrol eder; başarılı olursa statik
`index.json` ile `<paket>/<sürüm>.tar.gz` ağacını atomik olarak üretir. Çıktı
yolu yeni veya boş olmalıdır. Komut ağ kullanmaz, yükleme yapmaz, özel anahtar
almaz ve `index.json`'ı imzalamaz. Üretilen dizin **yayınlanmış veya index'i
imzalı bir registry değildir**; hosting, index bütünlüğü ve üretim anahtarı
işletimi ayrıca çözülmelidir.

---

## 4. Depo biçimi

```
<url>/index.json
<url>/<paket>/<sürüm>.tar.gz
```

`index.json`:

```json
{
  "schema": 1,
  "packages": {
    "net-util": [
      {
        "version": "0.3.0",
        "sha256": "<tarball sha256>",
        "sig": "<base64 ed25519 imza>",
        "dependencies": { "json-util": "^1.0" },
        "yanked": false
      }
    ]
  }
}
```

- `sig`, **tarball baytları** üzerinden ed25519 detached imzadır.
- `yanked: true` sürümler çözümlemede atlanır.

---

## 5. Semver

| Yazım | Anlam |
|---|---|
| `*` | herhangi |
| `1`, `1.2`, `1.2.3` | o seviyede eşleşme (kısmi) |
| `=1.2.3` | tam |
| `^1.0` | `>=1.0.0 <2.0.0` |
| `^0.3` | `>=0.3.0 <0.4.0` |
| `~1.2` | `>=1.2.0 <1.3.0` |
| `>=1.0,<2.0` | AND birleşimi |

Ön sürümler (`1.0.0-rc1`) kararlı sürümden **küçük** sayılır.

---

## 6. Güvenlik garantileri

| Tehdit | Karşı önlem | Test |
|---|---|---|
| Bozuk/ele geçirilmiş tarball | sha256 **indirme sonrası** doğrulanır | `test_download_rejects_tampered_tarball` |
| Index paketi başka ad/sürüm altında gösterirse | İmzalı manifest adı/sürümü ve bağımlılıkları index kaydıyla eşleşmelidir | `test_download_rejects_unsigned_index_metadata_mismatch`, `test_axpm_install_rejects_signed_package_relabelled_by_index` |
| İmzasız paket | Varsayılan **red**; `allow_unsigned` açıkça istenmeli | `test_download_rejects_unsigned_by_default` |
| Bozuk önbellek | Her isabette tarball SHA-256, güncel imza/unsigned politikası ve açılmış dosya içerikleri yeniden doğrulanır; bozuksa önbellek atılıp yenilenir | `test_download_heals_corrupted_cache`, `test_download_heals_modified_extracted_cache`, `test_cached_download_rejects_bad_signature`, `test_cached_unsigned_download_rechecks_unsigned_policy` |
| Arşiv path traversal ve link kaçışı | Bütün üyeler önceden doğrulanır; yalnız normal dosya/dizin açılır, symlink/hardlink ve özel dosyalar reddedilir | `test_download_rejects_path_traversal`, `test_download_rejects_archive_links_before_extracting_children`, `test_download_rejects_windows_style_archive_paths` |
| Bağımlılık döngüsü | `visiting` yığını ile tespit | `test_resolve_detects_cycle` |
| Sürüm çakışması | Daha yüksek sürüm seçilir, kısıt yeniden doğrulanır | `test_resolve_*` |
| Yanked sürüm | Çözümlemede atlanır | `test_resolve_skips_yanked` |

**Index güven sınırı:** `index.json` Registry v1'de imzalanmaz. Paket imzası
arşiv içeriğini ve manifesti doğrular; istemci manifestin adını, sürümünü ve
bağımlılıklarını index girdisiyle karşılaştırır. Ancak imzasız index'te `yanked`
değeri değiştirilebilir, kayıtlar silinebilir veya aynı kimlikteki eski ama
geçerli imzalı bir paket tekrar sunulabilir. Bu nedenle Registry v1 index'i
rollback/freshness korumalı ya da kurcalamaya karşı kanıtlı değildir. İmzalı
index formatı ve anahtar rotasyonu resmi yayın öncesi kararlaştırılmalıdır.

**Kritik not:** Tarball'ın SHA-256 ve imzası doğrulanmadan arşiv açılmaz; güvenli
üye kontrollerinden sonra çıkarılan imzalı manifesto index metadata'sıyla
karşılaştırılır.

---

## 7. Çözümleme modeli

```
kök bağımlılıklar
   └─ her biri için: aralığa uyan EN YÜKSEK, yanked olmayan sürüm
        └─ onun bağımlılıkları (transitive), döngü tespitiyle
```

- Tek sürüm politikası: aynı paketin iki farklı sürümü istenirse daha yükseği seçilir;
  kısıtı ihlal ediyorsa açık hata.
- Lockfile deterministik: paketler ada göre sıralı.

---

## 8. Bilinen sınırlar (v1)

1. **İmzalı index/freshness yok** — `index.json` imzalanmaz. TLS taşıma sırasında
   koruma sağlayabilir, ancak index değişikliği, yank/entry silme ve eski geçerli
   pakete rollback için kriptografik kanıt sağlamaz. v2: imzalı index ve rollback
   politikası.
2. **Namespace yok** — düz isim alanı (`P2-02`).
3. **`yanked` dışında politika yok** (deprecation, advisory).
4. **Ayna/CDN yok**.
5. **`axpm update` registry paketlerini yeniden çözmez** (yalnızca git).

---

## 9. Sıradaki (P2-02, P2-03)

- **P2-02 Namespace** — `@kullanici/paket`; düz isim alanı 250 pakette çakışır.
- **P2-03 `///` doc comment + `axiom doc`** — API dokümanı olmayan pakete kimse güvenmez.
