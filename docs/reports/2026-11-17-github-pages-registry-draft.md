# GitHub Pages registry yayın taslağı

## Kapsam

GitHub Pages üzerinde imzalı registry sunmaya yönelik, elle tetiklenen ve
yayın öncesi içeriği doğrulayan bir taslak eklendi. Taslak herhangi bir Pages
ayarını değiştirmez, otomatik olarak çalışmaz ve bu rapor itibarıyla registry
yayımlanmamıştır.

## Uygulama

- `axiom.registry_pages` registry kaynağını doğrular ve Pages artifact'ini
  oluşturur.
- Kaynak kökü ve alt ağacı normal dosya/dizinlerden oluşmalı; symlink ve özel
  dosyalar reddedilir. Beklenmeyen, eksik veya index'te yer almayan dosyalar
  reddedilir.
- Paket SHA-256 ve Ed25519 imzası, arşiv sınırları, manifest kimliği ve imzalı
  bağımlılık metadata'sı doğrulanır. Schema 2'de index imzası ve sona erme zamanı
  da doğrulanır.
- Yalnız açık PEM anahtarları doğrulama girdisi olarak kabul edilir. Anahtarlar
  Pages artifact'ine kopyalanmaz; workflow özel anahtar veya GitHub secret
  kullanmaz.
- Workflow yalnız `workflow_dispatch` ile, `master` üzerinde ve `publish`
  girdisi seçilince ilerler. Dört GitHub Action tam commit SHA'sına sabitlidir.
  `pages: write` ve `id-token: write` yalnız deploy job'ına verilir.

## Doğrulama

- `python -m py_compile axiom/registry_pages.py tests/test_registry_pages.py`
- `pytest -q --tb=short tests/test_registry_pages.py tests/test_registry_docs.py`
  — **13 passed** before adding the release-preflight integration.
- `pytest -q --tb=short tests/test_registry_pages.py tests/test_registry_docs.py
  tests/test_package_manager.py::test_sample_scan_report_signed_registry_release_preflight`
  — **14 passed** after connecting the real assemble output to the Pages builder.
- A clean temporary clone ran the sample through `axpm pack`, schema 2
  `axpm registry assemble`, then `axiom.registry_pages`; the build passed with
  an ephemeral package/index key pair. The generated Pages artifact contained
  `registry/<name>/<version>.tar.gz` and the signed index, and omitted both PEM
  public-key files.
- `python -m pytest -q -rs` — **1610 passed, 0 failed, 0 skipped** in 1396.94 s
  (bu raporun oluşturulduğu yerel çalışma ağacı).
- Commit `8d633b5` GitHub CI run
  [44008473602](https://github.com/jaminakoai/axiom/actions/runs/44008473602)
  **7/7 başarılı**: Python 3.10–3.13'ün her birinde 1583 geçti/27 ortam skip'i,
  55 doküman testi; ayrıca ASan/UBSan ve LLVM işleri geçti.
- Aynı commit'in native smoke run
  [44008473611](https://github.com/jaminakoai/axiom/actions/runs/44008473611)
  Linux, Windows ve macOS'ta **3/3 başarılı**.
- `git diff --check` — başarılı.

Regresyon testleri geçerli v1/v2 paket üretimini, başarısız paket ve index
imzalarını, hatalı SHA, süresi dolmuş v2 index'i, eksik imza, symlink ve
beklenmeyen dosyaları, açık anahtarların artifact dışında kalmasını ve workflow
tetikleme/izin/Action SHA şartlarını kapsar.

## Bulunan ve düzeltilen entegrasyon hatası

İlk gerçek paketleme provasında Pages doğrulayıcı arşivi
`<ad>/<sürüm>/<sürüm>.tar.gz` yolunda arıyordu. `axpm registry assemble` ve
RegistryClient'in gerçek URL düzeni `<ad>/<sürüm>.tar.gz` olduğundan validator
geçerli registry'yi reddetti. Yol düzeltildi ve release-preflight testi artık
aynı gerçek assemble çıktısını Pages builder'ından geçiriyor.

## Kalan yayın kapıları

- GitHub Pages ayarı hâlâ kapalı; `github-pages` environment için master dalı
  kısıtı ve reviewer kuralı ayrıca GitHub repository ayarlarında belirlenmeli.
- Varsayılan registry adresi ve resmi imza anahtarı saklama, rotasyon ve ilk
  bağlantı rollback politikası maintainer kararı bekliyor.
- Bir sürümlü örnek paketi gerçek host'a yayımlayıp temiz istemciyle indirme ve
  kurulum doğrulanmadan G4 kapanmış sayılmaz.
- Bağımsız kullanıcının yetkili dosya veya PCAP ile denemesi ve temizlenmiş
  geri bildirimi olmadan G3 kapanmaz.

İş akışı ve yerel komutlar için [Registry rehberine](../REGISTRY.md) bakın.
