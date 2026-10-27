"""Behavioural tests for mission-control/qps-triage-ultra/crew/measured/enrich_allocation_with_exposure.py.

The module does all of its work at import time, reading and writing files next to
``__file__``. Each test loads the real source file by path but overrides the module's
``__file__`` with a path inside ``tmp_path`` before executing it, so every read and the
receipt write happen in ``tmp_path`` and never in the repository.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import math
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = (
    REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "measured"
    / "enrich_allocation_with_exposure.py"
)
_COUNTER = itertools.count()

EXPOSURE_FEATURES = [
    "mean_waiting_seconds",
    "mean_active_seconds",
    "mean_release_seconds",
    "mean_exposure_seconds",
]


def _policy() -> dict:
    gate = {
        "status_required": "CONTROL_ACCEPTED_THREE_PULSE",
        "minimum_distinct_runs": 2,
        "minimum_distinct_source_shas": 2,
    }
    pca_gate = dict(gate, minimum_distinct_runs=3, minimum_distinct_source_shas=3)
    return {
        "allocation_features": list(EXPOSURE_FEATURES),
        "allocation_eligibility_gate": gate,
        "pca_candidate_gate": pca_gate,
        "pca": {"candidate_features": list(EXPOSURE_FEATURES)},
    }


def _obs(crew: str, waiting: float, active: float, release: float, outcome: str = "ACCEPT") -> dict:
    return {
        "crew_id": crew,
        "outcome": outcome,
        "waiting_seconds": waiting,
        "active_seconds": active,
        "release_seconds": release,
        "exposure_seconds": waiting + active + release,
    }


def _control(runs: list[dict], **overrides) -> dict:
    doc = {
        "schema": "missioncontrol.crew_exposure_control_return.v1",
        "status": "CONTROL_ACCEPTED_THREE_PULSE",
        "repeat_gate": {
            "observed_distinct_runs": len(runs),
            "observed_distinct_source_shas": len({r["source_sha"] for r in runs}),
            "all_assignments_predeclared": True,
            "all_assignments_accepted": True,
            "all_exposure_identities_valid": True,
            "no_canary_rows": True,
            "no_estimated_or_post_hoc_time": True,
        },
        "authority_transfer": False,
        "child_binding": False,
        "frontier_binding": False,
        "competency_promotions": 0,
        "evidence_runs": runs,
    }
    doc.update(overrides)
    return doc


def _runs(n_runs: int, crews: dict[str, tuple[float, float, float]]) -> list[dict]:
    runs = []
    for i in range(n_runs):
        assignments = [_obs(c, w + i, a * (i + 1), r) for c, (w, a, r) in crews.items()]
        runs.append({"run_id": 1000 + i, "source_sha": "sha%d" % i, "assignments": assignments})
    return runs


def _alloc_row(crew: str, level: float) -> dict:
    return {"crew_id": crew, "demonstrated_level": level, "acceptance_rate": 1.0}


def _run_module(tmp_path: Path, control: dict, allocation: dict, min_rows: int = 3, min_varying: int = 2):
    (tmp_path / "history").mkdir(exist_ok=True)
    (tmp_path / "history" / "CREW_EXPOSURE_CONTROL_RETURN_v1.json").write_text(json.dumps(control), encoding="utf-8")
    (tmp_path / "CREW_EXPOSURE_FEATURE_POLICY_v1.json").write_text(json.dumps(_policy()), encoding="utf-8")
    (tmp_path / "MEASURED_ALLOCATION_POLICY_v1.json").write_text(
        json.dumps({"pca_gate": {"min_measured_rows": min_rows, "min_varying_features": min_varying}}),
        encoding="utf-8",
    )
    (tmp_path / "MEASURED_ALLOCATION_RECEIPT.json").write_text(json.dumps(allocation), encoding="utf-8")
    name = "cw_enrich_allocation_%d" % next(_COUNTER)
    spec = importlib.util.spec_from_file_location(name, TARGET)
    module = importlib.util.module_from_spec(spec)
    # Redirect ROOT (derived from __file__) into tmp_path; code objects still map to TARGET.
    # A different basename keeps coverage attributing lines to TARGET (co_filename).
    module.__file__ = str(tmp_path / "relocated_enrich_anchor.py")
    spec.loader.exec_module(module)
    receipt = json.loads((tmp_path / "MEASURED_ALLOCATION_RECEIPT.json").read_text(encoding="utf-8"))
    return module, receipt


CREWS4 = {"A": (1.0, 10.0, 2.0), "B": (5.0, 3.0, 4.0), "C": (2.0, 7.0, 9.0), "D": (8.0, 1.0, 1.0)}


def _ready(tmp_path: Path):
    allocation = {
        "rows": [_alloc_row("A", 1), _alloc_row("B", 3), _alloc_row("C", 2), _alloc_row("D", 5), _alloc_row("E", 4)],
        "pca": {"status": "DEFER_PREVIOUS"},
    }
    return _run_module(tmp_path, _control(_runs(3, CREWS4)), allocation)


def test_three_pulse_control_ingests_exposure_and_runs_pca(tmp_path, capsys):
    module, receipt = _ready(tmp_path)
    rows = {r["crew_id"]: r for r in receipt["rows"]}

    # crew without observations is marked ineligible and gets no means
    assert rows["E"]["exposure_control_eligible"] is False
    assert "mean_waiting_seconds" not in rows["E"]

    # crew A: waiting 1,2,3 ; active 10,20,30 ; release 2,2,2
    a = rows["A"]
    assert a["exposure_control_eligible"] is True
    assert a["mean_waiting_seconds"] == pytest.approx(2.0)
    assert a["mean_active_seconds"] == pytest.approx(20.0)
    assert a["mean_release_seconds"] == pytest.approx(2.0)
    assert a["mean_exposure_seconds"] == pytest.approx(24.0)
    assert a["exposure_distinct_runs"] == 3
    assert a["exposure_distinct_source_shas"] == 3
    assert a["exposure_evidence_class"] == "CONTROLLED_MEASURED_THREE_PULSE"

    ec = receipt["exposure_control"]
    assert ec["status"] == "CONTROLLED_PCA_CANDIDATE_FEATURES"
    assert ec["controlled_rows"] == 4
    assert ec["pca_candidate_eligible"] is True
    assert ec["pca_feature_ingest_status"] == "INGESTED_READY_SMALL_N"
    assert ec["varying_features"] == EXPOSURE_FEATURES
    assert ec["source_control_return"] == "CREW_EXPOSURE_CONTROL_RETURN_v1.json"
    assert ec["authority_transfer"] is False and ec["competency_promotions"] == 0

    pca = receipt["pca"]
    assert pca["status"] == "READY_MEASURED_SMALL_N"
    assert pca["model_scope"] == "CREW_ROW_ALLOCATION_WITH_CONTROLLED_EXPOSURE"
    assert pca["pre_exposure_status"] == "DEFER_PREVIOUS"
    assert receipt["pca_pre_exposure"] == {"status": "DEFER_PREVIOUS"}
    # acceptance_rate is constant and other base features are absent -> excluded
    assert "acceptance_rate" not in pca["features_used"]
    assert "demonstrated_level" in pca["features_used"]
    assert pca["measured_rows"] == 4
    assert pca["sample_rank_cap"] == 3
    assert 1 <= len(pca["components"]) <= 3
    eigs = [c["eigenvalue"] for c in pca["components"]]
    assert eigs == sorted(eigs, reverse=True)
    assert pca["explained_variance_total"] == pytest.approx(1.0)
    assert pca["components"][0]["component"] == "PC1"
    assert len(pca["components"][0]["dominant_features"]) == 3

    printed = json.loads(capsys.readouterr().out)
    assert printed["exposure_control"] == ec
    assert printed["crew_row_pca"]["status"] == "READY_MEASURED_SMALL_N"
    assert module.pca_candidate_eligible is True


def test_two_pulse_control_defers_pca_and_keeps_previous_model(tmp_path):
    allocation = {"rows": [_alloc_row("A", 1), _alloc_row("B", 2)], "pca": {"status": "OLD"}}
    _, receipt = _run_module(tmp_path, _control(_runs(2, CREWS4)), allocation)
    ec = receipt["exposure_control"]
    assert ec["status"] == "CONTROLLED_OPTIONAL_FEATURES"
    assert ec["pca_candidate_eligible"] is False
    assert ec["pca_feature_ingest_status"] == "DEFER_EXPOSURE_REPEAT_GATE"
    assert receipt["pca"] == {"status": "OLD"}
    assert receipt["pca_pre_exposure"] == {"status": "OLD"}


def test_missing_previous_pca_and_too_few_rows_defers(tmp_path):
    allocation = {"rows": [_alloc_row("A", 1), _alloc_row("B", 2)]}
    _, receipt = _run_module(tmp_path, _control(_runs(3, CREWS4)), allocation)
    assert receipt["pca"]["status"] == "DEFER_INSUFFICIENT_ELIGIBLE_MEASURED_ROWS"
    assert receipt["pca"]["components"] == []
    assert receipt["pca"]["pre_exposure_status"] is None
    assert receipt["pca_pre_exposure"] == {}
    assert receipt["exposure_control"]["pca_feature_ingest_status"] == "DEFER_INSUFFICIENT_ELIGIBLE_MEASURED_ROWS"


def test_identical_crews_defer_for_insufficient_variance(tmp_path):
    crews = {c: (1.0, 2.0, 3.0) for c in "ABC"}
    allocation = {"rows": [_alloc_row(c, 1) for c in "ABC"]}
    _, receipt = _run_module(tmp_path, _control(_runs(3, crews)), allocation)
    assert receipt["exposure_control"]["varying_features"] == []
    assert receipt["pca"]["status"] == "DEFER_INSUFFICIENT_MEASURED_VARIANCE"
    assert receipt["pca"]["varying_features"] == 0


@pytest.mark.parametrize(
    "override",
    [
        {"schema": "wrong.schema"},
        {"status": "PENDING"},
        {"authority_transfer": True},
        {"competency_promotions": 1},
    ],
)
def test_control_return_guard_assertions(tmp_path, override):
    control = _control(_runs(3, CREWS4), **override)
    with pytest.raises(AssertionError):
        _run_module(tmp_path, control, {"rows": []})


def test_non_accept_observation_is_rejected(tmp_path):
    runs = _runs(3, CREWS4)
    runs[1]["assignments"][0]["outcome"] = "REJECT"
    with pytest.raises(AssertionError):
        _run_module(tmp_path, _control(runs), {"rows": []})


def test_repeat_gate_below_minimum_is_rejected(tmp_path):
    control = _control(_runs(3, CREWS4))
    control["repeat_gate"]["observed_distinct_runs"] = 1
    with pytest.raises(AssertionError):
        _run_module(tmp_path, control, {"rows": []})


@pytest.fixture()
def mod(tmp_path):
    module, _ = _ready(tmp_path)
    return module


def test_jacobi_trivial_sizes(mod):
    assert mod.jacobi_eigen_symmetric([]) == ([], [])
    vals, vecs = mod.jacobi_eigen_symmetric([[4.0]])
    assert vals == [4.0] and vecs == [[1.0]]


def test_jacobi_diagonal_matrix_converges_immediately(mod):
    vals, vecs = mod.jacobi_eigen_symmetric([[3.0, 0.0], [0.0, 1.0]])
    assert vals == [3.0, 1.0]
    assert vecs == [[1.0, 0.0], [0.0, 1.0]]


def test_jacobi_2x2_known_eigenpairs(mod):
    matrix = [[2.0, 1.0], [1.0, 2.0]]
    vals, vecs = mod.jacobi_eigen_symmetric(matrix)
    assert sorted(vals) == pytest.approx([1.0, 3.0])
    for k, lam in enumerate(vals):
        col = [vecs[0][k], vecs[1][k]]
        mv = [sum(matrix[i][j] * col[j] for j in range(2)) for i in range(2)]
        assert mv == pytest.approx([lam * c for c in col])


def test_jacobi_3x3_and_iteration_cap(mod):
    matrix = [[4.0, 1.0, 2.0], [1.0, 3.0, 0.5], [2.0, 0.5, 5.0]]
    vals, _ = mod.jacobi_eigen_symmetric(matrix)
    assert sum(vals) == pytest.approx(12.0)
    # a single rotation: the loop exits by exhausting max_iter, the trace is preserved
    capped, _ = mod.jacobi_eigen_symmetric(matrix, max_iter=1)
    assert sum(capped) == pytest.approx(12.0)
    assert sorted(capped) != pytest.approx(sorted(vals))


def test_measured_pca_drops_degenerate_component(mod):
    # f2 = 2*f1 -> correlation 1, the second eigenvalue ~0 is skipped
    rows = [{"f1": 1.0, "f2": 2.0}, {"f1": 2.0, "f2": 4.0}, {"f1": 4.0, "f2": 8.0}]
    result = mod.measured_pca(rows, ["f1", "f2", "missing"])
    assert result["status"] == "READY_MEASURED_SMALL_N"
    assert result["features_used"] == ["f1", "f2"]
    assert result["candidate_feature_count"] == 3
    assert len(result["components"]) == 1
    pc1 = result["components"][0]
    assert pc1["eigenvalue"] == pytest.approx(2.0)
    assert pc1["explained_variance_ratio"] == pytest.approx(1.0)
    assert abs(pc1["loadings"]["f1"]) == pytest.approx(1 / math.sqrt(2))
