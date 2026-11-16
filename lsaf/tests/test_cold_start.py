from pathlib import Path

from lsaf.compiler.cold_start import reconstruct_from_files

ROOT = Path(__file__).parents[2]


def test_repo_only_cold_start_is_deterministic_and_complete_enough():
    kwargs = {
        "cohort_path": ROOT / "lsaf/cohorts/2026-11-10_12/session-index.yaml",
        "graph_path": ROOT / "lsaf/state/p0_work_graph.yaml",
        "predictions_path": ROOT / "lsaf/predictions/pilot-seed.yaml",
    }
    one = reconstruct_from_files(**kwargs)
    two = reconstruct_from_files(**kwargs)
    assert one == two
    assert one["independent_qualification"] is False
    assert "EPIC-session-continuity" in one["active_epics"]
    assert "GBOGEB/pipeline-automation-hub" in one["repositories"]
    assert "CENSUS_SOURCE_1211" in one["ready"]
    assert "SESSION_ADAPTER" in one["blocked"]
    assert len(one["prediction_ids"]) == 5
    assert one["cycles"] == []


def test_cold_start_has_no_chat_only_dependency():
    result = reconstruct_from_files(
        cohort_path=ROOT / "lsaf/cohorts/2026-11-10_12/session-index.yaml",
        graph_path=ROOT / "lsaf/state/p0_work_graph.yaml",
        predictions_path=ROOT / "lsaf/predictions/pilot-seed.yaml",
    )
    assert result["active_epics"]
    assert result["next_predicates"]
    assert result["prediction_ids"]
