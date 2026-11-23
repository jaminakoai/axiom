# G5.1 — Public API kararlılığı ve uyumluluk politikası / Public API Stability and Compatibility Policy

**Durum / Status:** G5 çalışma politikası olarak benimsendi; `v1.0` öncesinde
somut API envanteri ve CI/release kontrolleri tamamlanmalı. Bu karar `v1.0`
yayımlamaz. / Adopted as the G5 working policy; concrete API inventory and
CI/release checks remain before `v1.0`. This does not release `v1.0`.
**Sürüm / Version:** `0.5.0-alpha`.

Bu, ilk G5 işidir: dili genişletmeden veya `v1.0` sözü vermeden önce Axiom
kullanıcılarının hangi yüzeylere güvenebileceğini tanımlamak. Mevcut `v1.0`
kapıları açıkken G5 hazırlığı sürebilir; bu belge kapıları kapatmaz.

This is the first G5 work item: define what Axiom users can depend on before
expanding the language or making a `v1.0` commitment. G5 can proceed while the
existing `v1.0` release gates are unresolved. This document does not itself
close those gates.

## İlk public API envanteri / Initial Public-Surface Inventory

| Yüzey / Surface | Kaynak / Source | İlk değerlendirme / Initial treatment |
|---|---|---|
| Dil sözdizimi ve anlamı / Language syntax and semantics | [`SPECIFICATION.md`](../SPECIFICATION.md) §§3–12, 18–19; C/LLVM parity tests | v1.0 adayı: anahtar sözcük/tip kataloğu, operatör önceliği, türler, kapsam, fonksiyon/sözleşmeler, hata ve sahiplik semantiği; kapsam dışı yapılar açık kalır / Candidate: keyword/type catalog, precedence, types, scope, functions/contracts, errors and ownership; unsupported forms stay explicit |
| Yerleşikler ve standart kütüphane / Built-ins and standard library | [`docs/api/v0.5.0-alpha.json`](api/v0.5.0-alpha.json), `axiom/checker.py`, `std/**/*.ax` | Checker: kaynak koddan çağrılabilir 111 `rt_*` dışı + 248 `rt_*` önekli imza, kararlılıkları sınıflandırılmadı; stdlib: 446 fonksiyon, 37 struct / Checker: 111 callable non-`rt_*` + 248 `rt_*`-prefixed signatures, stability unclassified; stdlib: 446 functions, 37 structs. 53 dosyada `pub`/`export` yok; davranış ve kararlı allowlist hâlâ sınıflandırılmalı / No `pub`/`export`; behavior and stable allowlist still need classification |
| Compiler CLI | `axiom/cli.py`, installed `--help` | v0.5 komut ve flag snapshot'ı her komutun help çıktısına karşı test ediliyor; exit code/pozisyonel argüman sözleşmeleri hâlâ açık / v0.5 command/flag snapshot is checked per command against installed help; exit-code and positional-argument contracts remain open |
| Paket yöneticisi / Package manager | `axiom/package_manager.py`, `axpm --help` | `init/add/install/verify/tree/remove/search/pack/registry assemble/update/build/run/test`; komut ve manifest flag/şema fixture'ları gerekli / Commands are implemented; command and manifest flag/schema fixtures are required |
| Manifest ve lock / Manifest and lock | `axiom.toml`, `axiom.lock`, [`REGISTRY.md`](REGISTRY.md) | Manifest: `name/version/authors/edition/entry/description/license`, `[package]` veya `[project]`, `[dependencies]`; lock: `version` ve paket başına `name/version/source/checksum/sha256/dependencies`. Şema/migration fixture'ı gerekli / Exact fields need versioned migration fixtures |
| Registry | [`REGISTRY.md`](REGISTRY.md), `axiom/registry.py` | Schema 1 imzasız geriye dönük okuma; schema 2 index `sequence/expires/packages`, paket `version/sha256/sig/dependencies/yanked`. Protokol ve anahtar değişim sözleşmesi aday / Schema 1 legacy read; schema 2 field inventory; protocol/key-rotation contract is a candidate |
| `axiom-scan` | `examples/21_axiom_scan.ax`, `tests/test_axiom_scan.py`, [JSON Schema](api/axiom-scan-report.schema.json) | `rules`, `scan`, `pcap`; exit `0/10/1`; schema-v1 success/error reports; exact documented YARA subset; whole-buffer hash/length and classic-PCAP per-frame semantics. Evidence-linked non-binding [v1.0 candidate](api/v1.0-stability-candidate.json) is pending product-scope confirmation / `rules`, `scan`, `pcap`; çıkış `0/10/1`; schema v1 başarı/hata raporları; belgeli YARA alt kümesi; tam buffer hash/uzunluk ve klasik PCAP paket davranışı. Kanıt bağlantılı [v1.0 adayı](api/v1.0-stability-candidate.json) bağlayıcı değildir ve ürün odağı kararını bekler. |
| LSP | `axiom/lsp.py`, `tests/test_lsp_full_features.py` | Yalnız initialize'da ilan edilen tam sync, completion, hover, definition, references, rename, quickfix, formatting, semantic tokens, signature help; tüm LSP vaat edilmez / Only advertised capabilities are candidates; no blanket LSP claim |
| ABI ve üretilen çıktı / ABI and generated output | `SPECIFICATION.md` §15, C/LLVM backends | C ABI/FFI ancak hedef triple, çağrı kuralı, sahiplik ve bellek yerleşimi bütünüyle envanterlenirse kararlı olabilir; üretilen C/LLVM IR iç detaydır / ABI can stabilize only per fully specified target/calling convention/ownership/layout; emitted IR is internal |
| Deneysel hedefler / Experimental targets | [`VERSIONING.md`](VERSIONING.md), README platform tablosu | Linux ARM64/AArch64/WASM deneysel etiketleriyle kararlılık sözünün dışında / Experimental targets remain outside the stability promise |

### v0.5 CLI seçenekleri anlık envanteri / CLI option snapshot

Bu seçenekler kurulu `axiom <komut> --help` ve `axpm <komut> --help`
çıktılarıyla karşılaştırıldı. Herhangi bir `v1.0` kararlılık sözü için bunlar
ve çıkış kodları CI sözleşme testlerine bağlanmalı.

The options below were compared with installed `axiom <command> --help` and
`axpm <command> --help`. Bind these forms and exit codes to CI contract tests
before making a `v1.0` stability promise.

| Komut / Command | v0.5 seçenekleri / Options |
|---|---|
| `axiom` | `-h/--help`, `-v/--version` |
| `axpm` | `-h/--help`, `-v/--version` |
| `axiom run` | `file`, `-g/--debug`, `--asan`, `--ubsan`, `--features`, `extra_args...` |
| `axiom build` | `file`, `-o/--output`, `-O/--opt`, `-g/--debug`, `--target`, `--sysroot`, `--backend {c,llvm}`, `--asan`, `--ubsan`, `--features` |
| `axiom check` | `file`, `--no-prove`, `--smt`, `--all`, `--features` |
| `axiom prove` | `file`, `--smt`, `--features` |
| `axiom emit-c` | `file`, `-o/--output`, `--features` |
| `axiom emit-smt` | `file`, `-o/--output`, `--features` |
| `axiom emit-llvm` | `file`, `-o/--output`, `-g/--debug`, `--features` |
| `axiom repl` | `--features` |
| `axiom test` | `--asan`, `pytest_args...` |
| `axiom init` | `project_name` |
| `axiom doc` | `paths...`, `-o/--output`, `--json`, `--title` |
| `axiom fmt` | `file`, `--check` |
| `axiom pkg` | `axpm` argument passthrough |
| `axiom lsp` | no command-specific options |
| `axpm init` | `[path]`, `--name`, `--lib` |
| `axpm add` | dependency, `--path`, `--git`, `--rev`, `--version` |
| `axpm install` | no command-specific options |
| `axpm verify` | no command-specific options |
| `axpm tree` | no command-specific options |
| `axpm remove` | `dependency`, `--purge` |
| `axpm search` | optional `query` |
| `axpm update` | optional `dependency` |
| `axpm pack` | required `--signing-key`, optional `--output` |
| `axpm registry` | subcommand group; no command-specific options |
| `axpm registry assemble` | required `--from`, `--output`, `--public-key`; optional `--index-signing-key`, `--index-sequence`, `--index-expires` |
| `axpm build` | `--release`, `-g/--debug`, `--target`, `--sysroot`, `-o/--output`, `--features` |
| `axpm run` | optional extra args; `-g/--debug`, `--features` |
| `axpm test` | optional extra args; `--features` |

CLI tablosu komut/flag snapshot'ıdır; exit code'ları veya her seçenek için ayrı
komut-sözleşme testlerini kapsamaz. 53 `std/**/*.ax` dosyasında
`pub`/`export` bildirimi yok ve semboller global isim alanını kullanıyor; bu
nedenle yalnız tek tek envanterlenen semboller kararlı API sayılmalı.

Dil şartnamesindeki `Result<T, E>` yapısal sözleşmedir (`is_ok`, `value`,
`error` alanları). `std/core/result.ax` aynı alanları sunan `ResultInt` ve
`ResultStr` kolaylık tipleri sağlar; bu tek başına çelişki değildir.
[`test_stdlib_result_int_and_str_interoperate_with_question_mark`](../tests/test_error_model.py)
regresyonu bunların `?` ile C/LLVM uyumluluğunu doğrular. `Option` şartnamede
genel tip olarak tanımlı değildir; stdlib'in `OptionInt`, `OptionStr` ve
`OptionBool` türleri, constructor/unwrap/fallback davranışıyla
[`test_stdlib_option_concrete_types_on_both_backends`](../tests/test_error_model.py)
tarafından iki backend'de doğrulanır. Her tür kararlı API envanterinde ayrı
listelenmelidir.

Derleyici kaynak denetimi önemli bir envanter açığı buldu: `axiom/checker.py`
`BUILTIN_FUNCTIONS` içinde 359 imza tutuyor; bunların 111'i `rt_*` dışı,
248'i `rt_*` önekli. Checker bu isimlerin tümünü Axiom kaynak kodundan
çağrılabilir kılıyor; `rt_*` burada gizli API anlamına gelmiyor. `len`,
`thread_create` ve `array_push` ayrıca özel durumlarla kabul ediliyor.
Şartnamenin eski 86 sayısı yanlıştı ve düzeltildi. Bu 359 imzanın kararlılık,
hata/sentinel, sahiplik ve C/LLVM davranışı tek tek sınıflandırılmalı.
Özellikle hata/sentinel, sahiplik ve C/LLVM backend davranışları imza listesinden
çıkarılamaz.

The generated source snapshot [`docs/api/v0.5.0-alpha.json`](api/v0.5.0-alpha.json)
lists every parsed stdlib function signature, struct field, module import, and
compiler builtin signature. `tools/generate_api_inventory.py --check` verifies
that snapshot against the current lexer/parser AST and checker source. It is a
source inventory only: entries are explicitly unclassified and are not stable
API promises. Behavior, error/ownership semantics, backend support, grammar,
CLI exit codes and the eventual stable allowlist still need review. The 53
`std/**/*.ax` files have no `pub`/`export` declarations, and symbols share a
global namespace, so only individually inventoried symbols should be treated
as stable.

The language specification defines `Result<T, E>` structurally (`is_ok`,
`value`, and `error` fields). `std/core/result.ax` provides convenience types
`ResultInt` and `ResultStr` with those fields; this is not inherently a
contradiction. The regression
`test_stdlib_result_int_and_str_interoperate_with_question_mark` in
`tests/test_error_model.py` confirms their `?` interoperability on C and LLVM.
The specification does not define a generic `Option`; the concrete stdlib
`OptionInt`, `OptionStr`, and `OptionBool` constructors, unwrap and fallback
behavior are verified on both backends by
`test_stdlib_option_concrete_types_on_both_backends` in
`tests/test_error_model.py`. List each type individually in the stable API
inventory.

A compiler-source audit found an important inventory gap: `axiom/checker.py`
contains 359 `BUILTIN_FUNCTIONS` signatures: 111 non-`rt_*` and 248 `rt_*`
prefixed names. The checker accepts all of them from Axiom source; the prefix
does not make them private. `len`, `thread_create` and `array_push` are accepted
through three special cases. The specification's former count of 86 was wrong
and has been corrected. Classify all 359 by stability and document their
error/sentinel, ownership and C/LLVM behavior before promising stability.

Before `v1.0`, enumerate each stable symbol, grammar form, CLI flag, exit code
and schema field, tie each promise to enforcing tests, and define the stable
boundary for each stdlib symbol. This initial inventory does not close those
gates or promise all 53 stdlib files wholesale.

## G5 uyumluluk politikası / G5 Compatibility Policy

1. **`v1.0` öncesi:** mevcut alpha politikasını koru. Dil, stdlib, CLI, manifest,
   lockfile ve rapordaki kırıcı değişikliklere izin ver; `CHANGELOG.md` ve geçiş
   notlarında açıkça belirt.
2. **`1.x` sürümleri:** SemVer uygula. Eklemeler minor, geriye uyumlu düzeltmeler
   patch, kararlı API'yi bozan değişiklikler major sürüm gerektirsin.
3. **Kullanımdan kaldırma:** kararlı API'yi release notlarında duyur ve en az
   sonraki iki minor sürüm boyunca tut; yalnız major sürümde kaldır. Güvenlik
   düzeltmeleri açık gerekçeyle istisna olabilir.
4. **Uyumluluk kanıtı:** `v1.0` öncesinde fixture biçimini, doğrulayıcıyı ve
   release kapısını hazırla; `v1.0` kaynak/paket/şema fixture'larını yayımla.
   İki kararlı minor yayımlandığında (ilk kez `v1.2` hazırlanırken) önceki iki
   minor sürümün örnek/paket fixture'larını güncel compiler/package manager
   ile desteklenen C ve LLVM backend'lerinde derleyip çalıştır. `axiom.toml`,
   `axiom.lock` ve `axiom-scan` JSON şemaları için de fixture kullan.
5. **Kararlı yüzey:** yalnız v1.0 public API envanterinde açıkça listelenen
   sözdizimi/anlam, tek tek stdlib sembolleri ve hata sözleşmeleri, CLI
   seçenekleri/çıkış kodları/yapılandırılmış çıktılar, manifest/lock şemaları,
   registry protokolü, axiom-scan'ın belgelenmiş YARA alt kümesi ve rapor şeması.
   LSP'de desteklenen protokol ve ilan edilen yetenekler listelenir. `std/`
   modülünde bulunmak tek başına kararlılık sözü değildir.
6. **Kapsam dışı:** compiler iç yapısı, üretilen C/LLVM IR, hata metinlerinin
   birebir yazımı, deneysel özellik/hedefler ve belgelenmemiş runtime header'ları.

1. **Before `v1.0`:** keep the current alpha policy. Breaking language, stdlib,
   CLI, manifest, lockfile and report changes are allowed, but must be called
   out in `CHANGELOG.md` and migration notes.
2. **`1.x` release numbers:** use SemVer. Additive stable API changes are minor
   releases; backward-compatible fixes are patches; breaking stable API changes
   require a major release.
3. **Deprecation:** announce a stable API's deprecation in release notes and
   keep it through at least two later minor releases. Remove it only in a major
   release. Security fixes may need an exceptional removal with a clear notice.
4. **Compatibility evidence:** Before `v1.0`, prepare the fixture format,
   validator and release gate, then publish the `v1.0` source/package/schema
   fixtures. Once two stable minor releases exist (first while preparing
   `v1.2`), CI should compile and run the previous two minor releases' public
   examples and packages against the current compiler/package manager, on both
   C and LLVM backends where supported. Include `axiom.toml`, `axiom.lock` and
   `axiom-scan` JSON schema fixtures.
5. **Stable surface:** only syntax/semantics, individual stdlib symbols and
   error contracts, CLI options/exit codes/structured output, manifest/lock
   schemas, registry protocol, and `axiom-scan`'s documented YARA subset/report
   schema explicitly listed in the `v1.0` public API inventory. List supported
   LSP protocol behavior and advertised capabilities. A symbol's presence in
   `std/` alone does not promise stability.
6. **Out of scope:** compiler internals, emitted C/LLVM IR, exact diagnostic
   wording, experimental features/targets, and undocumented runtime headers.

“İki sürüm geriye uyumluluk” ifadesindeki sürüm birimi artık nettir: **iki
sonraki minor sürümlük kaldırma penceresi ve önceki iki minor sürüm için test
fixture'ı**. Bu, kararlı `1.x` API'sinin yalnız iki eski sürümünün desteklenmesi
anlamına gelmez.

The unit in “two-release backward compatibility” is **a two-later-minor
deprecation window and a test corpus from the previous two minor releases**.
The corpus starts when those `1.x` releases exist: establish the `v1.0` and
`v1.1` baselines, then first enforce both while preparing `v1.2`. This does not
mean supporting only two old versions of the stable `1.x` API.

## Açık sürüm kapıları / Current Release Gates

- G3 iç teknik denetimi maintainer kararıyla kapatıldı; bağımsız kullanıcı
  doğrulaması değildir. Dış kullanıcı denemesi isteğe bağlı ürün geri bildirimidir,
  `v1.0` teknik kapısı değildir. / G3's internal audit was closed at the
  maintainer's direction; it is not independent user validation. External user
  trials are optional product feedback, not a `v1.0` technical gate.
- G4'ün ilk imzalı registry paketi yayımlandı ve kapandı. / G4's first signed
  registry package is published; the gate is complete.
- `v1.0` öncesi her kararlı yüzeyin somut sembol/sözdizimi/şema envanteri,
  fixture biçimi/doğrulayıcısı ve release kapısı hazırlanmalıdır. `v1.0` ve
  `v1.1` fixture'ları yayımlandıktan sonra önceki iki minor sürüm kontrolü ilk
  kez `v1.2` hazırlığında çalıştırılır. Bağımsız kullanıcı denemesi gönüllü ürün geri bildirimi olarak
  kalır; kullanıcı kanıtı varmış gibi raporlanmamalıdır. / Before `v1.0`, list
  concrete symbols, syntax and schemas for every stable surface and prepare the
  fixture format, validator and release gate. Publish `v1.0` and `v1.1` fixtures;
  first enforce previous-two-minor compatibility while preparing `v1.2`. External
  trials remain optional feedback; do not claim user evidence that has not been
  submitted.

## G5.1 kabul listesi / G5.1 Acceptance Checklist

- [x] İlk public API yüzeylerini ve kapı durumunu kaydet. / Record initial API
  surfaces and gate status.
- [x] Uyumluluk politikasını ve “iki sürüm” tanımını kaydet. / Record the
  compatibility policy and define what “two releases” means.
- [x] Kararlı yüzey sınırını ve SemVer/kaldırma penceresi politikasını belirle. /
  Define the stable-surface boundary and SemVer/deprecation policy.
- [x] “İki sürüm”ün iki sonraki minor sürüm olduğunu ve fixture CI yükümlülüğünü
  belirt. / Define “two releases” as two later minor releases and specify CI fixtures.
- [x] Bağımsız kullanıcı denemesinin v1.0 teknik kapısı olmadığı kararını
  VERSIONING ve doğrulama rehberiyle eşleştir. / Align VERSIONING and validation
  guidance with the decision that user trials are not a v1.0 technical gate.
- [x] Kaynak tabanlı API inventory generator ve snapshot drift testi ekle;
  fixture manifest şeması, yönergesi, doğrulayıcısı ve stable-tag CI kapısını
  hazırla. Bunlar gerçek eski sürüm davranış kanıtı değildir.
  / Add the source-based API inventory generator and snapshot drift check;
  prepare the fixture manifest schema, guide, validator and stable-tag CI gate.
  These do not constitute historical behavior evidence.
- [x] Mevcut test/source kanıtını API yüzeylerine göre kaydet ve kanıtı
  kararlılık ilanından ayrı tut. / Record current test/source evidence by API
  surface and keep it separate from stability declarations.
- [x] `axiom-scan` rules/scan/pcap/structured-error JSON Schema'sını yayımla ve
  rapor testlerini şemaya göre doğrula. / Publish the `axiom-scan` JSON Schema
  for rules/scan/pcap/structured-error reports and validate report tests against it.
- [x] Scanner-first v1.0 kapsamı için kaynak/test kanıtlarına bağlı ama
  bağlayıcı olmayan aday allowlist hazırla ve referanslarını CI'da doğrula. /
  Prepare a non-binding, evidence-linked scanner-first v1.0 candidate allowlist
  and validate its references in CI.
- [ ] v1.0 stable allowlist'ine seçilen her sembol/gramer/komut/şema alanı için
  semantics, errors/sentinels, ownership/lifetime, C/LLVM, platform/thread
  constraints ve enforcement testlerini listele. Allowlist dışındaki girdiler
  stable değildir; tüm 845 girdiye ayrı etiket vermek gerekmez. / For every
  symbol/syntax/command/schema field selected into the v1.0 stable allowlist,
  record semantics, errors/sentinels, ownership/lifetime, C/LLVM,
  platform/thread constraints and enforcing tests. Entries outside the
  allowlist are not stable; all 845 entries need not be separately labeled.
- [ ] v1.0 öncesinde stable allowlist ve CLI/manifest/lock şemalarını
  yayımla. v1.0 ve v1.1 gerçek release fixture'ları henüz yok; yayımlandıktan
  sonra v1.2 hazırlığında önceki iki-minor koşumunu doğrula. / Publish the
  stable allowlist and CLI/manifest/lock/scanner schemas before v1.0. Real
  v1.0/v1.1 fixtures do not exist yet; validate the previous-two-minor run
  while preparing v1.2 once they are published.
  / Publish the stable API allowlist and behavior/ownership/backend contracts
  before v1.0. Real v1.0/v1.1 release fixtures do not exist yet; validate the
  previous-two-minor run while preparing v1.2 after they are published.
