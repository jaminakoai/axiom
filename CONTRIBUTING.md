# Axiom'a Katkı

Teşekkürler! Bu belge, projenin alfa dönemindeki katkı kurallarını özetler.

## Geliştirme ortamı

```bash
# Sistem bağımlılıkları (Debian/Ubuntu)
sudo apt install clang libssl-dev zlib1g-dev python3 python3-pip git

# Python bağımlılıkları
make install-dev            # pip install -e ".[dev]"

# CLI'ı PATH'e almak istemiyorsanız doğrudan kullanın:
./bin/axiom --version
```

## Günlük komutlar

| Komut | Açıklama |
|---|---|
| `make test` | Tüm test paketi (~5 dk) |
| `make test-fast` | Hızlı birim testleri (~30 sn) |
| `make bootstrap` | `bin/axiomc`'yi Axiom kaynağından derle |
| `make ci` | `tools/ci_matrix.sh` |
| `make fmt` / `make fmt-check` | Biçimlendir / denetle |
| `make clean` | Üretilmiş dosyaları sil |

## Değişiklik gönderme

1. Konuya özel dal açın: `feat/…`, `fix/…`, `docs/…`
2. **Test ekleyin.** Hata düzeltiyorsanız hatayı yeniden üreten test olmadan PR kabul edilmez.
3. `make test` ve `make fmt-check` yeşil olmalı.
4. Commit mesajı: `alan: kısa açıklama` (örn. `prover: koşul içi çağrı denetimi`)
5. PR açıklamasında:
   - Ne değişti
   - Neden
   - Nasıl doğrulandı (komut + çıktı)

## Kod kuralları

### Python (`axiom/*.py`)
- Python 3.10+ uyumluluğu (walrus, match kullanmayın).
- Genel `except Exception` yalnızca sınır katmanlarında ve loglayarak.
- Yeni builtin eklerken **üç yeri** güncelleyin:
  1. `axiom/checker.py` → `BUILTIN_FUNCTIONS`
  2. `axiom/codegen_c.py` → `BUILTIN_MAP`
  3. `axiom/codegen_llvm.py` → builtin tablosu + `declare`
- Runtime fonksiyonları `AXIOM_RUNTIME_FN` ile işaretlenmeli (LLVM köprüsü için şart).

### Axiom (`compiler/*.ax`, `std/**/*.ax`, `examples/*.ax`)
- `make fmt` sonrası diff temiz olmalı.
- Standart kütüphane modülleri `fn` seviyesinde `requires` ile ön koşul belirtmeli (mümkünse).
- Ofansif modüller yalnızca `std/security/*` ve `std/net/{c2,packet_crafter}.ax` altında; başlıkta yasal uyarı zorunlu.

### Bellek kuralları (kritik)
- `ax_str` döndüren bir fonksiyonun sonucu **asla** ham `free()` ile bırakılmaz → `axiom_str_release`.
- İç tamponlar (`malloc`/`strdup` ile ayrılan, dil seviyesine dönmeyen) `free()` ile bırakılır.
- Dizi tamponları `axiom_heap_buf_track` ile kaydedilmeli; serbest bırakma `axiom_heap_buf_release_if_owned` üzerinden.
- Yeni bir string üreticisi eklerken dönüşü `axiom_owned_str_wrap(...)` ile sarın.
- Sahiplik tablosundaki bir değeri geçici olarak korumak için `axiom_temp_release_keep(mark, keep)` kullanın
  (`axiom_str_adopt` + `axiom_temp_release` ikilisinin tek kilitli hâli).
- `tests/test_runtime_ownership_audit.py` bu kuralı statik olarak denetler; CI'da otomatik çalışır.

## Test kuralları

- Her yeni özellik için en az bir **uçtan uca** test (Axiom kaynağı → C → binary → çıktı).
- Bellek ile ilgili değişikliklerde `--asan` altında test.
- Yeni bir hata sınıfı için **negatif** test (hata bekleniyorsa `returncode != 0` doğrulanmalı).
- Testler geçici dizin (`tmp_path`) kullanmalı; repoya çıktı bırakmamalı.

## Sürüm ve doküman

- Kullanıcıya görünen değişiklikleri `CHANGELOG.md` → `[Unreleased]` altına ekleyin.
- Davranış değişikliği varsa `README.md` “Bilinen Sınırlamalar” ve `SPECIFICATION.md` güncellenmeli.
- İddia ile kod çelişiyorsa **kod değil, iddia düzeltilir** (veya özellik tamamlanır).

## Lisans

Katkılar MIT lisansı altındadır (`LICENSE`).

## Raporlar

Her geliştirme turunun raporu **`docs/reports/`** altına yazılır — başka bir
yere değil. Dosya adı `docs/reports/<GÖREV>-<kısa-ad>.md` biçimindedir ve
`docs/reports/README.md` dizinine tarih sırasıyla eklenir.

Rapor içeriği: ne yapıldı · bulunan gerçek hatalar · doğrulama komutları ve
çıktıları · dürüst sınırlar · sıradaki iş.
