import pytest

from lsaf.compiler.dag import compile_dag
from lsaf.compiler.legacy import import_v1, roundtrip_v1
from lsaf.compiler.predict import append_outcome, make_prediction
from lsaf.compiler.project import project_all


def test_v1_import_preserves_full_payload():
    original = {
        "state": {"ready": ["A"], "unknown": None},
        "manifest": {"repo": "Hub", "authority_transfer": False},
        "handover": "handover text\n",
        "dropin": "drop-in text\n",
    }
    imported = import_v1(**original)
    assert roundtrip_v1(imported) == original
    assert imported["authority_transfer"] is False
    assert set(imported["source_hashes"]) == set(original)


def test_generated_projections_are_byte_stable_for_reordered_nodes():
    manifest = {
        "handover": {
            "repository": "GBOGEB/pipeline-automation-hub",
            "parent_issue": 1230,
            "pull_request": 1231,
            "branch": "feat/lsaf-session-genome-pilot",
            "authority_transfer": False,
        }
    }
    nodes = [
        {"id": "B", "requires": ["A"], "authority": "Hub", "evidence": "SOURCE"},
        {"id": "A", "requires": [], "authority": "Hub", "evidence": "SOURCE"},
    ]
    one = project_all(manifest, compile_dag(nodes))
    two = project_all(manifest, compile_dag(list(reversed(nodes))))
    assert one == two
    assert "DERIVED projection" in one["handover.md"]


def test_prediction_is_not_rewritten_when_outcome_arrives():
    receipt = make_prediction(
        "P-1", {"state": "SEMANTICALLY_BOUND"},
        made_at="2026-11-16T00:00:00Z",
        next_state="DEPENDENCY_ORDERED", confidence=0.7,
    )
    before_predicted = receipt["predicted"].copy()
    observed = append_outcome(
        receipt,
        {"observed_at": "2026-11-16T01:00:00Z", "next_state": "DEPENDENCY_ORDERED"},
    )
    assert receipt["outcome"] is None
    assert receipt["made_at"] == "2026-11-16T00:00:00Z"
    assert observed["predicted"] == before_predicted
    assert observed["score"]["top1_correct"] is True


def test_false_ready_is_scored():
    receipt = make_prediction(
        "P-2", {"state": "VERIFIED"},
        made_at="2026-11-16T00:00:00Z",
        next_state="EXECUTABLE", confidence=0.6,
    )
    observed = append_outcome(
        receipt,
        {"observed_at": "2026-11-16T01:00:00Z", "next_state": "BLOCKED"},
    )
    assert observed["score"]["false_ready"] is True


def test_outcome_requires_observed_at_and_next_state():
    receipt = make_prediction(
        "P-3", {"state": "VERIFIED"},
        made_at="2026-11-16T00:00:00Z",
        next_state="BLOCKED", confidence=0.5,
    )
    with pytest.raises(ValueError):
        append_outcome(receipt, {"next_state": "BLOCKED"})
    with pytest.raises(ValueError):
        append_outcome(receipt, {"observed_at": "2026-11-16T01:00:00Z"})
