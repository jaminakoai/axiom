# G5.1 — Public API kararlılığı önerisi / Public API Stability Proposal

**Durum / Status:** Sorumlu incelemesi için taslak; 1.0 uyumluluk taahhüdü
onaylanmış değildir. / Maintainer review draft; no 1.0 compatibility promise
is approved.
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
| Dil sözdizimi ve anlamı / Language syntax and semantics | [`SPECIFICATION.md`](../SPECIFICATION.md), örnekler ve compiler testleri / examples and compiler tests | 1.0 için aday; sözdizimi, tip kuralları, sahiplik, sözleşmeler ve hatalar envanterlenmeli / Candidate for 1.0; inventory syntax, types, ownership, contracts and errors |
| Standart kütüphane / Standard library | `std/**/*.ax` ve modül testleri / module tests | 1.0 için aday; her modül sahiplik, hata ve platform sınırlarını belgelemeli / Candidate; document ownership, errors and platform limits |
| Compiler CLI ve makine çıktısı / Compiler CLI and machine output | `axiom --help`, `axiom/cli.py` | Komutlar, belgeli bayraklar, exit kodları ve yapılandırılmış çıktı aday; hata metninin birebir yazımı değil / Commands, documented flags, exit codes and structured output are candidates; exact diagnostic wording is not |
| Paket yöneticisi ve proje dosyaları / Package manager and project files | `axpm --help`, `axiom.toml`, `axiom.lock`, [`REGISTRY.md`](REGISTRY.md) | Manifest/kilit şeması ve registry protokolü için sürümlü geçiş kuralları gerekli / Versioned migration rules required |
| LSP | `axiom/lsp.py` ve editör davranışı / editor behavior | Protokol uyumu açık listelenmeli; Axiom'a özel yetenekler ayrıca sayılmalı / List protocol and Axiom-specific capabilities |
| `axiom-scan` arayüzü / `axiom-scan` interface | `examples/21_axiom_scan.ax`, README özellik matrisi ve rapor şeması / README matrix and report schema | CLI, desteklenen YARA alt kümesi, exit kodu ve JSON şeması aday; tam YARA ima edilmez / Candidate; does not imply full YARA |
| Native ABI ve üretilen çıktı / Native ABI and generated output | C/LLVM backend'leri ve runtime headers | Desteklenen FFI/ABI sözleşmesi olarak belgelenmedikçe iç ayrıntı / Internal unless explicitly promised |
| Deneysel hedefler ve özellikler / Experimental targets and features | README platform matrisi ve özellik dokümanları / README matrix and feature docs | Kararlılık sözü yok; deneysel etiketi ve ayrı test gerekir / No stability promise; label and test separately |

Bu ilk envanter yüzey seviyesindedir. `v1.0` öncesinde her kararlı aday için
sembol, gramer biçimi, alan, bayrak, exit kodu veya şema listesi ve bu sözü
zorlayan testler çıkarılmalı.

This is a surface-level inventory. Before `v1.0`, each stable candidate needs a
concrete list of symbols, grammar forms, fields, flags, exit codes or schemas,
plus tests that enforce the promise.

## Sorumlu onayı için politika taslağı / Proposed Policy for Maintainer Approval

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
5. **Ayrıca taahhüt edilmedikçe kapsam dışı:** compiler iç yapısı, üretilen C/LLVM
   IR, hata metinlerinin birebir yazımı, deneysel özellik/hedefler ve belgelenmemiş
   runtime header'ları.

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
5. **Not promised unless separately documented:** compiler internals, emitted C
   and LLVM IR, exact diagnostic text, experimental features/targets, and
   undocumented runtime headers.

“İki sürüm geriye uyumluluk” ifadesi, neyin iki sürüm saydığını belirtmiyor.
Bu taslak bunu **iki minor sürümlük kaldırma penceresi ve test fixture'ı** olarak
yorumlar; kararlı `1.x` API'sinin yalnız iki eski sürümünün desteklenmesi olarak
yorumlamaz. Sorumlu bu yorumu onaylamalı veya değiştirmeli.

“Two-release backward compatibility” is ambiguous unless it names the unit.
This draft interprets it as a **two-minor-release deprecation window and
compatibility test corpus**, not as support for only two old versions of the
stable `1.x` API. The maintainer should confirm or replace that interpretation.

## Açık sürüm kapıları / Current Release Gates

- G3 iç teknik denetimi bağımsız denetçi yerine kabul edildi; bağımsız kullanıcı
  doğrulaması değildir. [`VERSIONING.md`](VERSIONING.md) bunu hâlâ `v1.0` kapısı
  sayar; taslak bu şartı kaldırmaz. / G3's internal audit is not independent user
  validation. The current `v1.0` gate remains; this draft does not remove it.
- G4'ün ilk imzalı registry paketi yayımlandı ve kapandı. / G4's first signed
  registry package is published; the gate is complete.
- `v1.0` öncesi envanter gözden geçirilmeli, politika onaylanmalı ve kullanıcı
  doğrulaması kapısı korunmalı veya sorumlu tarafından değiştirilmelidir. /
  Review the inventory, approve the policy, and retain or explicitly change the
  user-validation gate before `v1.0`.

## G5.1 kabul listesi / G5.1 Acceptance Checklist

- [x] İlk public API yüzeylerini ve kapı durumunu kaydet. / Record initial API
  surfaces and gate status.
- [x] “İki sürüm” yorumu içeren politika taslağını hazırla. / Draft the policy
  and define what “two releases” means.
- [ ] Kararlı yüzey sınırını sorumlu onaylasın veya düzenlesin. / Maintainer
  approves or edits the stable-surface boundary.
- [ ] İki-sürüm politikasını ve CI yükümlülüğünü onayla. / Approve the promise
  and its CI obligation.
- [ ] `v1.0` hazırlığı iddia edilmeden önce kararı `VERSIONING.md`, iki README
  ve release kontrolleriyle eşleştir. / Reconcile with version docs, both
  READMEs and release checks before a `v1.0` readiness claim.
