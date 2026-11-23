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
  kapatılmıştır; bu, bağımsız kullanıcı doğrulaması değildir. Bağımsız kullanıcı
  denemesi isteğe bağlı ürün geri bildirimi olarak kalır ve `v1.0` teknik kapısı
  değildir. `v1.0` öncesi kamuya açık kararlı API envanteri, G4 dağıtım kapıları
  ve aşağıdaki uyumluluk politikasının release kontrollerine bağlanması gerekir.
- `v1.0` sonrasında belgelenmiş kararlı yüzeyler SemVer'i izler. Kırıcı kararlı
  API değişikliği major sürüm, geriye uyumlu düzeltme patch sürümü, ekleme minor
  sürümü gerektirir. Kararlı API kaldırılmadan önce en az iki sonraki minor
  sürüm boyunca kullanımdan kaldırılmış halde tutulur; kaldırma major sürümde
  yapılır. Güvenlik düzeltmesi istisnası release notlarında gerekçelendirilir.
- v1.0 öncesinde fixture biçimi, doğrulayıcı ve release kapısı hazırlanır; v1.0
  ile v1.1 kaynak/paket/şema fixture'ları yayımlanır. İki kararlı minor sürüm
  mevcut olduğunda, önceki iki minor sürümün fixture'ları ilk kez v1.2
  hazırlığında güncel araçlarla desteklenen C ve LLVM hedeflerinde CI'da
  derlenip çalıştırılır. Yalnız iki eski sürümün desteklenmesi anlamına gelmez.

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
  technical audit; this is not independent user validation. An independent
  user trial remains optional product feedback, not a technical `v1.0` gate.
  Before `v1.0`, publish the stable API inventory, satisfy G4 distribution
  gates, and wire the compatibility policy below into release checks.
- After `v1.0`, documented stable surfaces follow SemVer. Breaking stable API
  changes require a major release, backward-compatible fixes a patch release,
  and additions a minor release. Keep deprecated stable APIs for at least two
  later minor releases; remove them only in a major release. Explain any
  security-fix exception in the release notes.
- Before `v1.0`, prepare the fixture format, validator and release gate, then
  publish `v1.0` and `v1.1` source/package/schema fixtures. While preparing
  `v1.2`, enforce fixtures from the previous two minor releases with current
  tools on supported C and LLVM targets. This corpus starts only after those
  releases exist; it is not a promise to support only two old releases.

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
