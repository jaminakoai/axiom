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
