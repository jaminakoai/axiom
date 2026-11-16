# axiom-scan-report

## Türkçe

Tarama sayaçlarını kararlı rapor etiketlerine dönüştürmek için küçük Axiom
yardımcıları.

`report_label(total_matches, high_severity_matches)` şu değerlerden birini
döndürür: `no_findings`, `findings`, `high_severity_findings`. Sözleşmeler
sayaçların negatif olmamasını ve yüksek önem dereceli bulguların toplamı
aşmamasını ister.

Bu işlev yalnızca sayıları etiketler; dosya incelemez, YARA kuralı yorumlamaz,
risk puanı vermez ve dosyanın güvenli olduğunu söylemez. Paket kaynak örneğidir;
kamuya açık registry'de yayımlanmamıştır.

## English

Small Axiom helpers for turning scan counts into stable report labels.

`report_label(total_matches, high_severity_matches)` returns one of
`no_findings`, `findings`, or `high_severity_findings`. Its contracts require
non-negative counts and `high_severity_matches <= total_matches`.

The helper only formats counts. It does not inspect files, interpret YARA
rules, assign risk, or say that a file is safe.

The package is included as a source example in the Axiom repository. It has not
been published to a public registry.
