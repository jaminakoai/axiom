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
  bağımlılık metadata'sı doğrulanır. Pages yayınında schema 2 zorunludur; index
  imzası, sona erme zamanı ve en çok 90 günlük geçerlilik doğrulanır. Eski,
  imzasız schema 1 index'i reddedilir.
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
- Re-ran the documented offline source-preparation commands in a clean clone of
  `18a364f` using temporary Ed25519 keys: `axpm pack` → schema 2 `assemble` →
  Pages validation passed. Artifact contained `.nojekyll`, `index.html`, the
  package tarball, `index.json`, and `index.json.sig`; it contained no key file.
  This verifies the procedure only; no temporary key or source snapshot was
  copied into the repository.
- `python -m pytest -q -rs` — **1610 passed, 0 failed, 0 skipped** in 1396.94 s
  (bu raporun oluşturulduğu yerel çalışma ağacı).
- Commit `586de93` GitHub CI run
  [44011843295](https://github.com/jaminakoai/axiom/actions/runs/44011843295)
  **7/7 başarılı**: Python 3.10–3.13'ün her birinde 1583 geçti/27 ortam skip'i,
  55 doküman testi; ayrıca ASan/UBSan ve LLVM işleri geçti.
- Aynı commit'in native smoke run
  [44011843309](https://github.com/jaminakoai/axiom/actions/runs/44011843309)
  Linux, Windows ve macOS'ta **3/3 başarılı**.
- `git diff --check` — başarılı.

Yayın doğrulayıcısı ayrıca schema 1 index'i açıkça reddeder. Hedefli doğrulama:
`tests/test_registry_pages.py`, `tests/test_registry_docs.py` ve gerçek assemble
çıktısı release-preflight testi — **15 passed**.

Offline `registry-site` hazırlama tarifi eklendikten sonra shell syntax kontrolü
ve temiz klondaki geçici anahtarlı pack/assemble/Pages provası tekrar geçti;
`tests/test_registry_docs.py`, `tests/test_registry_pages.py` ve onboarding docs
paketi **20 passed**.

Regresyon testleri v1/v2 registry biçimlerinin doğru kabul/ret davranışını,
başarısız paket ve index
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

- `registry-site/` yayın girdisi depoda henüz yoktur. `docs/REGISTRY.md`, mevcut
  onaylı offline paket/index anahtarlarıyla schema 2 snapshot üretip yerel
  validator'dan geçirme komutlarını belgeler; burada hiçbir anahtar üretilmedi
  veya yayın girdisi commit edilmedi.
- GitHub Pages ayarı hâlâ kapalı; `github-pages` environment için master dalı
  kısıtı ve reviewer kuralı ayrıca GitHub repository ayarlarında belirlenmeli.
- Varsayılan registry adresi ve resmi imza anahtarı saklama, rotasyon ve ilk
  bağlantı rollback politikası maintainer kararı bekliyor.
- Bir sürümlü örnek paketi gerçek host'a yayımlayıp temiz istemciyle indirme ve
  kurulum doğrulanmadan G4 kapanmış sayılmaz.
- Bağımsız kullanıcının yetkili dosya veya PCAP ile denemesi ve temizlenmiş
  geri bildirimi olmadan G3 kapanmaz.

İş akışı ve yerel komutlar için [Registry rehberine](../REGISTRY.md) bakın.
