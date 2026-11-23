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
| Yerleşikler ve standart kütüphane / Built-ins and standard library | `SPECIFICATION.md` §13; `std/**/*.ax` and module tests | Şartname 86 yerleşik sayıyor; 53 std dosyasında `pub`/`export` yok. Semboller tek namespace'te olduğundan tek tek envanterlenmeden tüm modüller kararlı sayılmaz / Spec lists 86 built-ins; 53 std files have no `pub`/`export`. With a global namespace, modules are not stable wholesale without symbol inventory |
| Compiler CLI | `axiom/cli.py` | v0.5 alt komutları: `run`, `build`, `check`, `prove`, `emit-c`, `emit-smt`, `emit-llvm`, `repl`, `test`, `init`, `doc`, `fmt`, `pkg`, `lsp`. Belgeli seçenekler/çıkış kodları aday; tam seçenek envanteri `v1.0` öncesi çıkarılmalı / Listed commands; documented options/exit codes are candidates; enumerate all flags before `v1.0` |
| Paket yöneticisi / Package manager | `axiom/package_manager.py`, `axpm --help` | `init/add/install/verify/tree/remove/search/pack/registry assemble/update/build/run/test`; komut ve manifest flag/şema fixture'ları gerekli / Commands are implemented; command and manifest flag/schema fixtures are required |
| Manifest ve lock / Manifest and lock | `axiom.toml`, `axiom.lock`, [`REGISTRY.md`](REGISTRY.md) | Manifest: `name/version/authors/edition/entry/description/license`, `[package]` veya `[project]`, `[dependencies]`; lock: `version` ve paket başına `name/version/source/checksum/sha256/dependencies`. Şema/migration fixture'ı gerekli / Exact fields need versioned migration fixtures |
| Registry | [`REGISTRY.md`](REGISTRY.md), `axiom/registry.py` | Schema 1 imzasız geriye dönük okuma; schema 2 index `sequence/expires/packages`, paket `version/sha256/sig/dependencies/yanked`. Protokol ve anahtar değişim sözleşmesi aday / Schema 1 legacy read; schema 2 field inventory; protocol/key-rotation contract is a candidate |
| `axiom-scan` | `examples/21_axiom_scan.ax`, `tests/test_axiom_scan.py` | `rules`, `scan`, `pcap`; çıkış `0/10/1`; schema v1 scan: `target/target_sha256/scanned_bytes/match_count/matches[]`, match: `rule/tags/meta/pattern/offset/length`; PCAP: `pcap/pcap_sha256/packet_count/match_count/packets[]`. Belgeli YARA alt kümesi, tam YARA değil / Exact fields; documented YARA subset only |
| LSP | `axiom/lsp.py`, `tests/test_lsp_full_features.py` | Yalnız initialize'da ilan edilen tam sync, completion, hover, definition, references, rename, quickfix, formatting, semantic tokens, signature help; tüm LSP vaat edilmez / Only advertised capabilities are candidates; no blanket LSP claim |
| ABI ve üretilen çıktı / ABI and generated output | `SPECIFICATION.md` §15, C/LLVM backends | C ABI/FFI ancak hedef triple, çağrı kuralı, sahiplik ve bellek yerleşimi bütünüyle envanterlenirse kararlı olabilir; üretilen C/LLVM IR iç detaydır / ABI can stabilize only per fully specified target/calling convention/ownership/layout; emitted IR is internal |
| Deneysel hedefler / Experimental targets | [`VERSIONING.md`](VERSIONING.md), README platform tablosu | Linux ARM64/AArch64/WASM deneysel etiketleriyle kararlılık sözünün dışında / Experimental targets remain outside the stability promise |

Bu, kaynaklara bağlı ilk somut yüzey haritasıdır; henüz tüm fonksiyon imzaları,
CLI bayrakları veya test eşlemesi değildir. 53 `std/**/*.ax` dosyasında
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

This source-linked map is concrete but does not yet list every function
signature, grammar form, CLI flag, exit code, or test mapping. The 53
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
4. **Uyumluluk kanıtı:** CI önceki iki minor sürümde yayımlanmış örnek ve paket
   fixture'larını güncel compiler/package manager ile, desteklenen C ve LLVM
   backend'lerinde derleyip çalıştırsın. `axiom.toml`, `axiom.lock` ve
   `axiom-scan` JSON şeması için de fixture ekle.
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
4. **Compatibility evidence:** CI should compile and run the public example and
   package fixtures from the previous two minor releases against the current
   compiler/package manager, on both C and LLVM backends where supported.
   Add schema fixtures for `axiom.toml`, `axiom.lock` and `axiom-scan` JSON.
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
This does not mean supporting only two old versions of the stable `1.x` API.

## Açık sürüm kapıları / Current Release Gates

- G3 iç teknik denetimi maintainer kararıyla kapatıldı; bağımsız kullanıcı
  doğrulaması değildir. Dış kullanıcı denemesi isteğe bağlı ürün geri bildirimidir,
  `v1.0` teknik kapısı değildir. / G3's internal audit was closed at the
  maintainer's direction; it is not independent user validation. External user
  trials are optional product feedback, not a `v1.0` technical gate.
- G4'ün ilk imzalı registry paketi yayımlandı ve kapandı. / G4's first signed
  registry package is published; the gate is complete.
- `v1.0` öncesi her kararlı yüzeyin somut sembol/sözdizimi/şema envanteri
  çıkarılmalı ve önceki iki minor sürüm fixture kontrolü CI/release sürecine
  bağlanmalıdır. Bağımsız kullanıcı denemesi gönüllü ürün geri bildirimi olarak
  kalır; kullanıcı kanıtı varmış gibi raporlanmamalıdır. / Before `v1.0`, list
  concrete symbols, syntax and schemas for every stable surface and wire the
  previous-two-minor fixture check into CI/release. External trials remain
  optional feedback; do not claim user evidence that has not been submitted.

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
- [ ] Somut API envanterini ve iki-minor fixture CI/release kapısını v1.0
  readiness öncesi tamamla. / Complete the concrete API inventory and
  two-minor fixture CI/release gate before claiming v1.0 readiness.
