# Sürümleme ve Platform Desteği / Versioning and Platform Support

Bu belge Axiom `v0.x` dönemi için geçerli sürüm ve platform beyanını tanımlar.
Destek iddiaları doğrulanmış CI ve kullanıcı akışlarına dayanır.

## Türkçe

### Sürümleme (`v1.0` öncesi)

- Proje şu anda `0.5.0-alpha` aşamasındadır. `v1.0` öncesinde dil sözdizimi,
  standart kütüphane, CLI, paket manifesti/kilit biçimi ve rapor şeması kararlı
  API olarak taahhüt edilmez.
- `0.Y.Z` içinde `Y`, özellik veya uyumsuz değişiklik içeren sürümlerde artırılır;
  `Z`, geriye uyumlu hata düzeltmeleri içindir. Ön sürümler (`alpha`, `beta`,
  `rc`) üretim kararlılığı ya da uyumluluk garantisi vermez.
- Kırıcı değişiklikler changelog'da açıkça işaretlenir; README ve sürüm notları
  etkilenen sözdizimini, API'yi veya veri biçimini belirtir.
- `v1.0` yayımlanmış değildir. G3'ün iç teknik denetimi maintainer kararıyla
  kapatılmıştır; bu, bağımsız kullanıcı doğrulaması değildir. Mevcut politika,
  bağımsız kullanıcı doğrulamasını, G4 dağıtım kapılarını ve kamuya açık kararlı
  API envanterini `v1.0` ön koşulu sayar. G4 tamamlandı; G5 API envanteri ve
  uyumluluk politikası taslağı üzerinde çalışıyor. G5 hazırlıkları `v1.0`
  kararını tek başına onaylamaz.
- `v1.0` sonrasındaki iki sürüm geriye uyumluluk taahhüdü henüz verilmemiştir;
  bu politika 1.0 kararı öncesinde ayrıca belirlenmelidir.

### Doğrulanmış platform matrisi

| Platform | Doğrulanan kapsam | Sınır |
|---|---|---|
| Linux x86_64 | Python 3.10–3.13 tam CI paketi; yerel derleme ve `axiom-scan` | Belgelenmiş Linux sistem kütüphaneleri gerekir |
| Windows | Python 3.12 ile temiz kurulum ve native örnek derle/çalıştır smoke testi | Tam pytest paketi, `axiom-scan` ve elle kurulum doğrulanmadı |
| macOS | Python 3.12 ile temiz kurulum ve native örnek derle/çalıştır smoke testi | Tam pytest paketi, `axiom-scan` ve elle kurulum doğrulanmadı; CPU mimarisi için genel iddia yok |
| Linux ARM64 | Deneysel hedef | Yerel tam test veya `axiom-scan` doğrulaması yok |
| AArch64/WASM çapraz hedefleri | Deneysel | Harici toolchain ve sysroot gerekir; genel destek taahhüdü yok |

Platform kapsamı değiştikçe bu tablo, README'ler ve CI birlikte güncellenir.
Smoke testi tam test paketi veya ürün iş akışı doğrulaması olarak sunulmaz.

## English

### Versioning before `v1.0`

- Axiom is currently at `0.5.0-alpha`. Before `v1.0`, the language syntax,
  standard library, CLI, package manifest/lock format, and report schema are not
  promised as stable APIs.
- In `0.Y.Z`, increment `Y` for feature releases or releases with breaking
  changes; reserve `Z` for backward-compatible fixes. Pre-releases (`alpha`,
  `beta`, `rc`) carry no production-stability or compatibility guarantee.
- Mark breaking changes in the changelog and describe affected syntax, APIs, or
  data formats in the README and release notes.
- `v1.0` has not been released. The maintainer closed G3 with an internal
  technical audit; this is not independent user validation. The current policy
  keeps independent user validation, G4 distribution gates, and a public
  stable-API inventory as prerequisites for `v1.0`. G4 is complete; G5 is
  drafting the API inventory and compatibility policy. G5 preparation alone
  does not approve a `v1.0` decision.
- No two-release backward-compatibility promise has been made for post-`v1.0`;
  decide that policy separately before the 1.0 decision.

### Verified platform matrix

| Platform | Verified scope | Limit |
|---|---|---|
| Linux x86_64 | Full CI suite on Python 3.10–3.13; native build and `axiom-scan` | Documented Linux system libraries are required |
| Windows | Native example build/run and harmless `axiom-scan` sentinel smoke with Python 3.12 (run 44020276057) | Full pytest suite, real file/PCAP workflow, and manual install are unverified |
| macOS | Native example build/run and harmless `axiom-scan` sentinel smoke with Python 3.12 (run 44020276057) | Full pytest suite, real file/PCAP workflow, and manual install are unverified; no general CPU-architecture claim |
| Linux ARM64 | Experimental target | No native full-suite or `axiom-scan` verification |
| AArch64/WASM cross-targets | Experimental | Require an external toolchain and sysroot; no general support promise |

Update this table, both READMEs, and CI together when platform evidence changes.
The sentinel smoke is limited to the documented synthetic onboarding path; it
does not establish full-suite or real file/PCAP workflow support.
