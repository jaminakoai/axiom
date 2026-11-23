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
    assert surface["input_contract"]["pcap"]["stream_reassembly"] is False
