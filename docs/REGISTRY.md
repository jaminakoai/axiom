# Axiom Registry v1 — Kullanım ve Protokol

**Durum:** uygulandı (P2-01)
**Modül:** `axiom/registry.py`
**Test:** `tests/test_registry.py` (43 test)

---

## 1. Neden

Registry olmadan:
- Dışarıdan paket çekilemez → dış katkı imkânsız
- Herkes kodu kopyala-yapıştır yapar → ekosistem oluşmaz
- Tedarik zinciri doğrulanamaz (imza yok, checksum içerik değil)

Registry v1 bunları çözer: **içerik-adresli depo + ed25519 imza + semver + transitive çözümleme**.

---

## 2. Yapılandırma

`axiom.toml` içinde:

```toml
[registry]
url = "https://registry.axiom-lang.org"
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
| Sahte paket (index ele geçirildi) | İmza tarball baytları üzerinden doğrulanır | `test_download_rejects_bad_signature` |
| İmzasız paket | Varsayılan **red**; `allow_unsigned` açıkça istenmeli | `test_download_rejects_unsigned_by_default` |
| Bozuk önbellek | Her isabette yeniden doğrulanır, bozuksa atılıp indirilir | `test_download_heals_corrupted_cache` |
| Arşivde `../` (path traversal) | Üyelere `resolve()` kontrolü, dışına çıkarsa red | `test_download_rejects_path_traversal` |
| Bağımlılık döngüsü | `visiting` yığını ile tespit | `test_resolve_detects_cycle` |
| Sürüm çakışması | Daha yüksek sürüm seçilir, kısıt yeniden doğrulanır | `test_resolve_*` |
| Yanked sürüm | Çözümlemede atlanır | `test_resolve_skips_yanked` |

**Kritik not:** Doğrulama *indirme sırasında* değil, **tam indirme sonrasında** yapılır ve
*önce doğrula, sonra aç* sırası korunur (`_fetch` → `verify_sha256` → imza → `extractall`).

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

1. **HTTPS imzası yok** — index.json'un kendisi imzalı değil; imza yalnızca tarball'da.
   Index MITM'e karşı TLS'e güveniyor. v2: imzalı index.
2. **Namespace yok** — düz isim alanı (`P2-02`).
3. **`yanked` dışında politika yok** (deprecation, advisory).
4. **Ayna/CDN yok**.
5. **`axpm update` registry paketlerini yeniden çözmez** (yalnızca git).

---

## 9. Sıradaki (P2-02, P2-03)

- **P2-02 Namespace** — `@kullanici/paket`; düz isim alanı 250 pakette çakışır.
- **P2-03 `///` doc comment + `axiom doc`** — API dokümanı olmayan pakete kimse güvenmez.
