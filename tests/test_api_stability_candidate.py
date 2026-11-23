"""Keep the v1.0 scanner stability proposal evidence-linked and non-binding."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATH = ROOT / "docs" / "api" / "v1.0-stability-candidate.json"


def _candidate():
    return json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))


def test_v1_candidate_remains_a_proposal_until_scope_is_accepted():
    candidate = _candidate()

    assert candidate["status"] == "proposal_pending_product_scope"
    assert candidate["target_release"] == "1.0.0"
    assert candidate["decision_rule"].endswith("not a compatibility promise.")
    assert candidate["candidate_surfaces"]
    assert all(
        surface["decision"] == "proposed-stable"
        for surface in candidate["candidate_surfaces"]
    )


def test_v1_candidate_evidence_paths_and_test_nodes_exist():
    candidate = _candidate()

    for surface in candidate["candidate_surfaces"]:
        evidence = surface["evidence"]
        for source in evidence["sources"]:
            assert (ROOT / source).is_file(), source

        for test_ref in evidence["tests"]:
            path, separator, node_id = test_ref.partition("::")
            test_path = ROOT / path
            assert test_path.is_file(), path
            if separator:
                tree = ast.parse(test_path.read_text(encoding="utf-8"), filename=path)
                function_names = {
                    node.name
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                assert node_id in function_names, test_ref


def test_scanner_candidate_records_documented_rule_and_pcap_limits():
    surface = _candidate()["candidate_surfaces"][0]
    yara = surface["yara_subset"]
    hex_patterns = yara["hex_patterns"]

    assert hex_patterns["fixed_jump"]["minimum"] == 1
    assert hex_patterns["fixed_jump"]["maximum"] == 64
    assert hex_patterns["bounded_jump"]["maximum_per_pattern"] == 1
    assert hex_patterns["bounded_jump"]["maximum_gap_width"] == 16
    assert hex_patterns["alternation"]["minimum_branches"] == 2
    assert hex_patterns["alternation"]["maximum_branches"] == 4
    assert hex_patterns["alternation"]["branches_equal_length"] is True
    assert hex_patterns["negation"]["maximum_per_pattern"] == 1
    assert hex_patterns["limits"]["maximum_encoded_pattern_bytes"] == 8192
    assert yara["conditions"]["selector_accounting"].startswith("Each selected pattern")
    assert yara["conditions"]["indexing"] == "Occurrence indices are 1-based; offsets are 0-based."
    assert yara["conditions"]["filesize"]["decimal_KB_bytes"] == 1024
    assert surface["input_contract"]["pcap"]["timestamp_resolution"] == ["microsecond", "nanosecond"]
    assert surface["input_contract"]["pcap"]["global_header"] == {
        "accepted_version": "2.4 only",
        "snaplen_minimum": 1,
    }
    assert surface["input_contract"]["pcap"]["stream_reassembly"] is False
    assert surface["input_contract"]["pcap"]["packet_count_includes_zero_length_records"] is True
    assert "rejected with a structured error report" in surface["input_contract"]["pcap"]["malformed_or_truncated_records"]
    assert surface["input_contract"]["pcap"]["matched_packet_index_base"] == 0
    assert surface["input_contract"]["pcap"]["maximum_captured_record_bytes"] == 65535
    assert "neither validated nor reported" in surface["input_contract"]["pcap"]["timestamp_handling"]
    assert "opaque bytes" in surface["input_contract"]["pcap"]["scan_unit"]
    assert "ignored" in surface["input_contract"]["pcap"]["linktype"]
    assert surface["input_contract"]["pcap"]["captured_record_length_must_not_exceed"] == [
        "global_snaplen",
        "original_record_length",
        "maximum_captured_record_bytes",
    ]
    assert "only records with at least one matching rule" in surface["input_contract"]["pcap"]["packets_array"]
    assert "rule-record pairs" in surface["input_contract"]["pcap"]["match_count"]
    assert surface["input_contract"]["resource_limits"]["maximum_file_scan_bytes"] is None
    assert surface["validated_platform_scope"]["full_file_and_pcap_scan"] == ["Linux x86_64"]
    assert "byte offset and length" in surface["yara_subset"]["regex"]
    assert "as opaque bytes" in surface["commands"]["pcap"]
    assert surface["yara_subset"]["metadata"]["integer_literals"] == {
        "optional_sign": "leading -",
        "decimal_max_digits": 18,
        "hex_prefixes": ["0x", "0X"],
        "hex_max_digits": 15,
    }
    assert surface["yara_subset"]["metadata"]["string_hex_byte_escape"] == "\\xNN is rejected"
    assert (
        "tests/test_axiom_scan.py::test_pcap_fail_on_match_is_opt_in_and_matches_c_llvm"
        in surface["evidence"]["tests"]
    )
    assert "tests/test_axiom_scan.py::test_cli_usage_errors_are_structured_and_match_c_llvm" in surface["evidence"]["tests"]
    assert "tests/test_axiom_scan.py::test_help_and_version_are_plain_text_for_c_and_llvm" in surface["evidence"]["tests"]
    assert "tests/test_axiom_scan.py::test_pcap_match_does_not_span_records" in surface["evidence"]["tests"]
    assert "tests/test_axiom_scan.py::test_regex_witness_reports_actual_byte_span_on_both_backends" in surface["evidence"]["tests"]

    schema = json.loads((ROOT / "docs/api/axiom-scan-report.schema.json").read_text(encoding="utf-8"))
    pcap_properties = schema["$defs"]["pcapReport"]["allOf"][1]["properties"]
    assert "Sparse list" in pcap_properties["packets"]["description"]
    assert "matching rule-record pairs" in pcap_properties["match_count"]["description"]


def test_readmes_document_metadata_integer_limits_in_both_languages():
    turkish = (ROOT / "README.md").read_text(encoding="utf-8")
    english = (ROOT / "README.en.md").read_text(encoding="utf-8")

    assert "18 onluk veya `0x`/`0X` ile 15 onaltılık basamak" in turkish
    assert "baştaki `-` isteğe bağlıdır" in turkish
    assert "18 decimal digits or 15 hexadecimal digits" in english
    assert "optional leading `-`" in english
