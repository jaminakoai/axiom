# GitHub Actions — Node 24 action güncellemesi

**Tarih:** 17 Kasım 2026  
**Commit:** `2b73fea0fbb2026c4a37fe014aeacd1c3b239960`  
**Durum:** CI ve Linux/Windows/macOS platform smoke doğrulandı.

## Değişiklik

Önceki tam CI loglarında `actions/checkout@v4` ve
`actions/setup-python@v5` için Node.js 20 deprecation uyarısı görülüyordu.
Workflow'lar resmî, Node.js 24 kullanan sürümlere geçirildi ve mutable tag yerine
tam commit SHA'larına sabitlendi:

- `actions/checkout` `v7.0.1` —
  [`3d3c42e5aac5ba805825da76410c181273ba90b1`](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1)
- `actions/setup-python` `v7.1.0` —
  [`6d4fd22b20465ccc0f7354476588e8df7c9ca0e0`](https://github.com/actions/setup-python/commit/6d4fd22b20465ccc0f7354476588e8df7c9ca0e0)

Bu sürümlerin Node.js 24 geçişi için resmî açıklamalar:
[checkout v5/v6 Node 24 bilgisi](https://github.com/actions/checkout/blob/main/README.md),
[setup-python v6 Node 24 değişikliği](https://github.com/actions/setup-python/releases/tag/v6.0.0)
ve [setup-python v7 sürüm notları](https://github.com/actions/setup-python/releases/tag/v7.1.0).
`setup-python` v7'de kaldırılmış `pip-install` girdisi bu depoda kullanılmıyor.
`checkout` v7'nin özel fork engeli `pull_request_target`/`workflow_run`
olaylarıyla ilgilidir; mevcut CI yalnızca `push` ve `pull_request` kullanır.

Güncellenen dosyalar `.github/workflows/ci.yml`,
`.github/workflows/platform-smoke.yml` ve manuel `.github/workflows/publish-registry-pages.yml`.

## Doğrulama

- [Tam CI run 44026041380](https://github.com/jaminakoai/axiom/actions/runs/44026041380): **7/7 başarılı**.
- Python 3.10, 3.11, 3.12 ve 3.13'ün her birinde **1587 geçti / 27 skip**;
  sabitlenmiş YARA differential testi **29 geçti**, doküman blokları **55 geçti**.
- Biçimlendirme, LLVM/DWARF ve ASan/UBSan job'ları başarılı.
- [Native platform smoke run 44026041510](https://github.com/jaminakoai/axiom/actions/runs/44026041510): Linux, Windows ve macOS **3/3 başarılı**.
- İki run'ın loglarında `Node.js 20 is deprecated` sayısı ayrı ayrı **0**.
- Üç workflow yerel YAML parser'ıyla ayrıştırıldı; `git diff --check` geçti.

## Bulgular ve sınırlar

Değişiklik uygulama kodunu etkilemedi ve iki doğrulama run'ında hata çıkmadı.
GitHub Pages publish workflow'u manuel olduğu, Pages ve registry kaynağı henüz
hazır olmadığı için uçtan uca yayın workflow'u çalıştırılmadı. Pages workflow'u
aynı SHA-sabitli checkout action'ını kullanıyor; fakat yayın akışı ayrıca
G4'teki maintainer kararlarına bağlıdır.

## Sıradaki iş

G3 için bağımsız gerçek kullanıcı denemesi; G4 için registry URL'si, imza anahtarı
işletimi ve Pages yayın hazırlığı gerekiyor.
