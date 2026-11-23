# G5 API contract audit / G5 API sözleşme denetimi

**Scope / Kapsam:** evidence inventory for the current `0.5.0-alpha` source.
This document is **not** the `v1.0` stable API allowlist and does not promote
any symbol to a compatibility promise. A test name or an inventory entry alone
does not prove a complete public contract.

**Kapsam:** mevcut `0.5.0-alpha` kaynağı için kanıt envanteri. Bu belge
`v1.0` kararlı API allowlist'i değildir ve hiçbir sembolü uyumluluk sözüne
dönüştürmez. Bir test adında ya da envanterde yer almak tek başına tam bir
kullanıcı sözleşmesini kanıtlamaz.

The policy is allowlist-based: an entry not explicitly selected for the
`v1.0` stable allowlist is not stable and carries no compatibility promise.
The 844-entry source inventory therefore does not need an artificial
stable/experimental/unsupported label on every entry. Only proposed stable
entries require full contract review; explicitly unsupported features should
be called out where users could reasonably expect them.

Politika allowlist temellidir: `v1.0` kararlı allowlist'ine açıkça alınmayan
girdi kararlı değildir ve uyumluluk sözü taşımaz. Bu nedenle 844 girdili kaynak
envanterinin her elemanına yapay bir stable/experimental/unsupported etiketi
vermek gerekmez. Tam sözleşme incelemesi yalnız kararlı olması önerilen
girdilerde yapılır; kullanıcıların makul biçimde bekleyebileceği desteklenmeyen
özellikler ayrıca belirtilir.

The generated [source API inventory](api/v0.5.0-alpha.json) contains 844
entries: 446 stdlib functions, 37 structs, 358 checker builtins and 3 special
builtin forms. They are all unclassified. The generator's drift check confirms
that the snapshot matches source; it does not audit semantics, ownership,
errors, backend behavior or user value.

Üretilen [kaynak API envanteri](api/v0.5.0-alpha.json) 844 girdi içerir:
446 stdlib fonksiyonu, 37 struct, checker içindeki 358 builtin ve 3 özel
builtin biçimi. Bunların tamamı sınıflandırılmamıştır. Envanter drift testi
yalnız snapshot'ın kaynakla aynı olduğunu doğrular; anlamı, sahipliği, hata
davranışını, backend davranışını veya kullanıcı değerini denetlemez.

## Evidence-backed slices / Kanıtı bulunan dilimler

| Surface | Source contract | Enforcing evidence | Remaining limits |
|---|---|---|---|
| `ResultInt`, `ResultStr`, `?` | Concrete result fields and early-return propagation | [`tests/test_error_model.py`](../tests/test_error_model.py): `test_stdlib_result_int_and_str_interoperate_with_question_mark`, `test_question_mark_runs_defer_on_early_return`; C/LLVM parametrization | Does not classify all `Result`-related builtins or promise generic `Result<T,E>` helper APIs |
| `OptionInt`, `OptionStr`, `OptionBool` | Constructors, unwrap/fallback and concrete option values | [`tests/test_error_model.py`](../tests/test_error_model.py): `test_stdlib_option_concrete_types_on_both_backends` | Does not establish a generic `Option<T>` API or classify all stdlib entries |
| `axiom-scan` report and exit behavior | Schema version 1; exactly one JSON object on stdout for machine reports/errors; exit 0/1/10 behavior; documented YARA subset | [`examples/21_axiom_scan.ax`](../examples/21_axiom_scan.ax), [`axiom-scan JSON Schema`](api/axiom-scan-report.schema.json), [`tests/test_axiom_scan.py`](../tests/test_axiom_scan.py): `test_scan_report_schema_and_target_hash`, `test_error_paths`, `test_error_path_is_structured_json`, `test_fail_on_match_is_opt_in`, `test_fail_on_match_llvm_parity`, and schema validation tests; parser/condition cases and backend parity are also covered | Schema is enforced against representative rules/scan/pcap/error reports; it does not by itself certify every report-producing branch or the full YARA language. Unknown fields are rejected, so a report-field change requires a schema-version increment |
| Manifest and lock | Manifest round trip; lock generation and tamper detection | [`tests/test_package_manager.py`](../tests/test_package_manager.py): `test_manifest_roundtrip`, `test_lockfile_generation_and_tamper_detection`; registry and package end-to-end tests | No complete versioned manifest/lock schema or exhaustive field migration contract |
| Registry trust and package resolution | SemVer selection, signatures, tamper/rollback, cache/archive restrictions | [`tests/test_registry.py`](../tests/test_registry.py), registry assembly cases in [`tests/test_package_manager.py`](../tests/test_package_manager.py) | Broad security evidence is not a complete user-visible CLI stdout/stderr/exit contract |
| LSP | Selected protocol methods and advertised capabilities | [`tests/test_lsp_full_features.py`](../tests/test_lsp_full_features.py), [`tests/test_lsp_server.py`](../tests/test_lsp_server.py) | Promise only capabilities directly asserted and documented; no blanket protocol conformance claim |
| Language semantics and ownership | Sampled syntax, type/error behavior, `verify`, selected string lifetime paths | [`tests/test_specification.py`](../tests/test_specification.py), [`tests/test_codegen_e2e.py`](../tests/test_codegen_e2e.py), [`tests/test_llvm_control_flow.py`](../tests/test_llvm_control_flow.py), [`tests/test_llvm_string_ownership.py`](../tests/test_llvm_string_ownership.py), [`tests/test_runtime_ownership_audit.py`](../tests/test_runtime_ownership_audit.py) | Grammar is not fully mechanically checked against the parser; all callable builtins and comprehensive C/LLVM ownership/error parity remain unclassified |
| CLI command inventory | Installed help commands and flags | [`tests/test_g5_versioning_consistency.py`](../tests/test_g5_versioning_consistency.py): `test_documented_cli_commands_and_flags_cover_installed_help` | Help presence is not an exit-code, stdout/stderr, option interaction or compatibility contract |

## Recommended scanner-first v1.0 candidate / Scanner-first v1.0 adayı

This is a scope proposal, not a stability promise. If the product centers on
offline DFIR triage, the user-facing contract to consider for the v1.0
allowlist is the `axiom-scan` executable: its `rules`/`scan`/`pcap` commands,
exit codes, report schema v1, exact documented YARA subset, whole-buffer hash
and byte-count semantics, and classic-PCAP per-packet behavior. It does not
automatically stabilize every compiler or stdlib function used internally to
build the example. The machine-readable, evidence-linked draft is
[`docs/api/v1.0-stability-candidate.json`](api/v1.0-stability-candidate.json);
its references are checked by `tests/test_api_stability_candidate.py`.

Bu kapsam önerisidir, kararlılık sözü değildir. Ürün çevrimdışı DFIR triyajına
odaklanacaksa v1.0 allowlist'i için incelenecek kullanıcı sözleşmesi
`axiom-scan` ikilisidir: `rules`/`scan`/`pcap` komutları, çıkış kodları, rapor
şeması v1, belgelenmiş YARA alt kümesinin kesin sınırları, tam buffer hash/byte
uzunluğu semantiği ve klasik PCAP kayıtlarının opak yakalanmış baytlarının
kayıt başına taranması. Bu karar, örneği derlemek için içeride kullanılan her
compiler veya stdlib fonksiyonunu otomatik olarak kararlı yapmaz.
Makinece okunabilir, kaynak ve test kanıtlarına bağlı taslak
[`docs/api/v1.0-stability-candidate.json`](api/v1.0-stability-candidate.json)
dosyasındadır; referanslarını `tests/test_api_stability_candidate.py` doğrular.

| Candidate behavior | Evidence to bind into the release allowlist |
|---|---|
| YARA rule structure, comments, typed metadata, integer bounds, tags and string escapes | [`tests/test_yara_parser_structure_differential.py`](../tests/test_yara_parser_structure_differential.py), [`tests/test_yara_parser_escapes.py`](../tests/test_yara_parser_escapes.py), [`tests/test_axiom_scan.py`](../tests/test_axiom_scan.py): `test_rule_meta_and_tags_are_returned_as_typed_json`, `test_metadata_x_escape_is_rejected`, `test_metadata_integer_digit_limits_and_signed_values`, `test_metadata_integer_values_over_digit_limits_fail_closed`, `test_comment_markers_inside_yara_text_are_preserved` |
| Boolean conditions, pattern groups, count/offset/length selectors, filesize and range conditions | [`tests/test_axiom_scan.py`](../tests/test_axiom_scan.py): `test_boolean_conditions_match_in_c_and_llvm`, `test_pattern_group_range_matches_in_c_and_llvm`, `test_positional_condition_reports_selected_occurrence_in_c_and_llvm`, `test_filesize_comparisons`, `test_pattern_occurrence_count_conditions`, `test_pattern_offset_conditions`; differential coverage in [`tests/test_yara_condition_differential.py`](../tests/test_yara_condition_differential.py), [`tests/test_yara_selector_differential.py`](../tests/test_yara_selector_differential.py) |
| Text modifiers, escape decoding and unsupported modifier rejection | [`tests/test_yara_modifiers.py`](../tests/test_yara_modifiers.py), [`tests/test_yara_parser_escapes.py`](../tests/test_yara_parser_escapes.py) |
| Hex wildcards, fixed/bounded jumps, alternation, negated bytes and occurrence selection | [`tests/test_yara_fixed_jumps.py`](../tests/test_yara_fixed_jumps.py), [`tests/test_yara_hex_ranges.py`](../tests/test_yara_hex_ranges.py), [`tests/test_yara_hex_range_differential.py`](../tests/test_yara_hex_range_differential.py), [`tests/test_yara_hex_typed_differential.py`](../tests/test_yara_hex_typed_differential.py), [`tests/test_yara_hex_alternation.py`](../tests/test_yara_hex_alternation.py), [`tests/test_yara_hex_negation.py`](../tests/test_yara_hex_negation.py) |
| Regex input safety and NUL-containing target behavior | [`tests/test_yara_regex_safety.py`](../tests/test_yara_regex_safety.py), [`tests/test_yara_text_buffer_edges.py`](../tests/test_yara_text_buffer_edges.py), [`tests/test_axiom_scan.py`](../tests/test_axiom_scan.py): `test_regex_scan_with_embedded_nul_is_structured_error_and_text_control` |
| Whole-file byte scanning, hash/byte-count correctness, report fields, CLI usage/help/version, exit codes and C/LLVM report parity | [`docs/api/axiom-scan-report.schema.json`](api/axiom-scan-report.schema.json), [`tests/test_axiom_scan.py`](../tests/test_axiom_scan.py): `test_scan_report_schema_and_target_hash`, `test_rules_and_pcap_reports_carry_schema`, `test_llvm_scanner_matches_c`, `test_cli_usage_errors_are_structured_and_match_c_llvm`, `test_help_and_version_are_plain_text_for_c_and_llvm`, `test_fail_on_match_is_opt_in`, `test_fail_on_match_llvm_parity`, `test_pcap_fail_on_match_is_opt_in_and_matches_c_llvm`, `test_error_path_is_structured_json` |
| Classic PCAP byte order/timestamp magic, opaque record scanning, ignored linktype, 65,535-byte cap, zero-length records, zero-based match indices, malformed-input errors, no cross-record matching and no stream reassembly | [`tests/test_axiom_scan.py`](../tests/test_axiom_scan.py): `test_scan_pcap_packet`, `test_scan_pcap_opposite_endian_classic_file`, `test_scan_pcap_nanosecond_timestamp_magic`, `test_scan_pcap_counts_empty_packet_and_continues`, `test_pcap_match_does_not_span_records`, `test_scan_pcap_ignores_linktype_and_scans_captured_bytes`, `test_scan_pcap_rejects_record_over_65535_bytes_even_with_large_snaplen`, `test_scan_pcap_malformed_or_truncated_records_fail_closed`, `test_scan_rejects_pcapng`, `test_pcap_fail_on_match_is_opt_in_and_matches_c_llvm`, `test_llvm_scanner_matches_c` |

The [fixed external YARA corpus](../tests/test_yara_corpus_compat.py) adds
reference-engine evidence for selected supported and explicitly rejected
features. It is intentionally a small sample, not proof of full YARA
compatibility. The entire table remains proposed until the product scope and
the exact supported grammar boundary are accepted for the stable release.

## Unclassified work / Sınıflandırılmamış işler

- No generated or manual artifact currently declares the final `v1.0` stable
  symbol allowlist. The inventory snapshot remains explicitly unclassified.
- All 358 checker builtins need contract review for return/error/sentinel
  behavior, ownership/lifetime, C/LLVM support, and applicable platform or
  thread-safety limits. Do not infer these properties from the signature.
- The 446 stdlib functions and 37 structs need individual stable/experimental/
  unsupported decisions or a carefully bounded module-level decision.
- CLI command exit codes and stdout/stderr behavior and complete manifest/lock
  schemas need explicit contracts and tests if they are included in the stable
  surface. The scanner report schema is published; representative production
  and rejection cases are tested, with full branch coverage still open.
- Language grammar, ownership/error behavior, and backend parity need review
  against the specification; sampled passing tests do not establish complete
  parity.
- No real `v1.0` or `v1.1` history fixture exists yet. The new fixture harness
  prepares future compatibility checks but is not historical evidence.
- A concrete user workflow still needs to guide any new language or stdlib
  feature. Existing test coverage does not establish product demand.

## Recommended allowlist record / Allowlist kaydı önerisi

Keep the mechanically generated source inventory separate from a manually
reviewed `v1.0` decision file. Each proposed stable entry should identify:

- exact symbol, grammar form, CLI command/option, or schema field;
- stability decision (`stable`, `experimental`, or `unsupported`);
- observable semantics and error/sentinel behavior;
- ownership/lifetime requirements and C/LLVM/platform/thread support;
- exact enforcing test node IDs and known limitations.

CI should validate references to inventory entries and test nodes, but must not
turn a signature, test mention, or generated snapshot into an automatic stable
API decision. Maintainer review owns that decision.
