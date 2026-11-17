# G4 — Güncel signed registry release preflight

**Tarih:** 17 Kasım 2026  
**Denetlenen commit:** `7f14d0b`  
**Sonuç:** Yerel imzalı örnek paket/Pages preflight'ı geçti; resmi yayın yapılmadı.

## Çalıştırılan testler

```bash
python -m pytest -q --tb=short \
  tests/test_package_manager.py::test_sample_scan_report_signed_registry_release_preflight \
  tests/test_registry_pages.py \
  tests/test_registry_docs.py
```

```text
16 passed in 3.06s
```

Release preflight testi `axiom-scan-report` örneğini geçici Git monorepo'ya
kopyalayıp commit ediyor; test scope'unda üretilmiş geçici Ed25519 paket ve
index anahtarlarıyla `axpm pack` ve schema 2 registry assemble çalıştırıyor.
Paket SHA-256, imza ve index girdisi doğrulanıyor; sonra oluşturulan aynı v2
registry ağacı `build_pages_site` ile Pages artifact'ine dönüştürülüyor.
Pages builder testleri ayrıca v1/unsigned index, bozuk veya eksik imza, süresi
dolmuş index, index'te olmayan dosyalar ve symlink girdilerinin reddedildiğini;
workflow'un manuel onay istediğini ve action SHA'larının sabit olduğunu kapsıyor.

## Bulgular ve sınırlar

Bu turda preflight veya Pages validator hatası bulunmadı. Test anahtarları ve
registry geçici test dizininde üretildi; gerçek anahtar kullanılmadı. Repo
kökünde `registry-site/` kaynağı yok, GitHub Pages etkin değil ve bu turda hiçbir
dosya dışarı yüklenmedi. Dolayısıyla bu sonuç G4 kabul kapısını kapatmaz ve
örnek paket yayımlandı anlamına gelmez.

Resmi yayın öncesi maintainer hâlâ canonical registry URL'sini, üretim imza
anahtarının saklama/rotasyon modelini, GitHub Pages ayarını ve environment
korumasını kararlaştırmalıdır. Hazır öneriler TODO ve önceki kullanıcı
seçimlerinde kayıtlıdır.
