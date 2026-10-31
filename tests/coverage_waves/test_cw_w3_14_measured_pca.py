"""Behavioural tests for mission-control/qps-triage-ultra/analytics/w3_14_measured_pca.py."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYTICS = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "analytics"
MODULE_PATH = ANALYTICS / "w3_14_measured_pca.py"
REAL_INPUT = ANALYTICS / "W3_13_MEASURED_PULSES.json"


def _load():
    spec = importlib.util.spec_from_file_location("cw_w3_14_measured_pca_mod", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pca = _load()
FEATURES = [
    "wall_seconds",
    "outcome_success",
    "defect_observed",
    "repair_present_in_head",
    "consumer_execution",
    "receipt_emitted",
]
SHA = "f" * 40


def _data(cols, n=None, evidence="MEASURED", policy=None):
    n = n if n is not None else len(next(iter(cols.values())))
    rows = []
    for i in range(n):
        row = {"evidence_class": evidence}
        for f in FEATURES:
            row[f] = cols.get(f, [1] * n)[i]
        rows.append(row)
    pol = {"synthetic_rows": 0, "expert_seeded_rows": 0, "user_mandated_rows": 0}
    pol.update(policy or {})
    return {"features": FEATURES, "rows": rows, "pca_input_policy": pol}


def _run(tmp_path, monkeypatch, data, out_name="out/receipt.json"):
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / out_name
    monkeypatch.setattr(
        sys, "argv", ["w3_14_measured_pca.py", "--input", str(inp), "--out", str(out), "--source-sha", SHA]
    )
    pca.main()
    return inp, out


# --- helpers -----------------------------------------------------------------

def test_mean_and_sample_std():
    assert pca.mean([1, 2, 3, 4]) == 2.5
    assert pca.sample_std([2, 4, 4, 4, 5, 5, 7, 9]) == pytest.approx(math.sqrt(32 / 7))
    assert pca.sample_std([3, 3, 3]) == 0.0


def test_jacobi_diagonalises_symmetric_matrix_sorted_desc():
    a = [[2.0, 1.0], [1.0, 2.0]]
    values, vectors = pca.jacobi_eigh(a)
    assert values == pytest.approx([3.0, 1.0])
    for lam, vec in zip(values, vectors):
        av = [sum(a[i][j] * vec[j] for j in range(2)) for i in range(2)]
        assert av == pytest.approx([lam * x for x in vec])
        assert sum(x * x for x in vec) == pytest.approx(1.0)
    assert a == [[2.0, 1.0], [1.0, 2.0]]


def test_jacobi_three_by_three_trace_preserved():
    a = [[4.0, 1.0, 0.5], [1.0, 3.0, 0.2], [0.5, 0.2, 1.0]]
    values, _ = pca.jacobi_eigh(a)
    assert sum(values) == pytest.approx(8.0)
    assert values == sorted(values, reverse=True)


def test_jacobi_one_by_one_and_diagonal():
    assert pca.jacobi_eigh([[5.0]]) == ([5.0], [[1.0]])
    values, vectors = pca.jacobi_eigh([[1.0, 0.0], [0.0, 4.0]])
    assert values == [4.0, 1.0]
    assert vectors == [[0.0, 1.0], [1.0, 0.0]]


def test_jacobi_raises_when_not_converged():
    with pytest.raises(RuntimeError, match="did not converge"):
        pca.jacobi_eigh([[2.0, 1.0], [1.0, 2.0]], max_iter=0)


# --- main: refusal paths ------------------------------------------------------

@pytest.mark.parametrize(
    "data, message",
    [
        (_data({"wall_seconds": [1, 2], "outcome_success": [0, 1]}), "measured floor is not satisfied"),
        (
            _data({"wall_seconds": [1, 2, 3], "outcome_success": [0, 1, 1]}, evidence="SYNTHETIC"),
            "refuses non-MEASURED",
        ),
        (
            _data({"wall_seconds": [1, 2, 3], "outcome_success": [0, 1, 1]}, policy={"expert_seeded_rows": 1}),
            "refuses synthetic/expert-seeded/user-mandated",
        ),
        (
            _data({"wall_seconds": [1, 2, 3], "outcome_success": [0, 1, 1]}, policy={"user_mandated_rows": None}),
            "refuses synthetic/expert-seeded/user-mandated",
        ),
        (_data({"wall_seconds": [1, 2, 3]}), "fewer than two varying measured features"),
    ],
)
def test_main_refuses_invalid_input(tmp_path, monkeypatch, data, message):
    with pytest.raises(ValueError, match=message):
        _run(tmp_path, monkeypatch, data)
    assert not (tmp_path / "out").exists()


# --- main: success paths ------------------------------------------------------

def test_main_flattened_pc1_focuses_pc2(tmp_path, monkeypatch, capsys):
    data = _data({"wall_seconds": [1, -1, 1, -1], "outcome_success": [1, 1, -1, -1]})
    inp, out = _run(tmp_path, monkeypatch, data)
    receipt = json.loads(out.read_text())
    assert json.loads(capsys.readouterr().out) == receipt
    assert receipt["input_sha256"] == hashlib.sha256(inp.read_bytes()).hexdigest()
    assert receipt["source_sha"] == SHA
    assert receipt["input_rows"] == 4
    assert receipt["features_active"] == ["wall_seconds", "outcome_success"]
    assert receipt["features_dropped_zero_variance"] == FEATURES[2:]
    assert [c["eigenvalue"] for c in receipt["components"]] == pytest.approx([1.0, 1.0])
    assert receipt["pc1_to_pc2_variance_ratio"] == pytest.approx(1.0)
    interp = receipt["pc1_flattening_interpretation"]
    assert interp["pc1_flattened_relative_to_pc2"] is True
    assert interp["navigation_focus"] == "PC2"
    assert interp["evidence_class"] == "INFERRED"
    assert all(a["basis_component"] == "PC2" for a in receipt["next_action_ranking"])
    assert receipt["authority_transfer"] is False


def test_main_correlated_features_focus_pc1(tmp_path, monkeypatch, capsys):
    data = _data({
        "wall_seconds": [1, 2, 3, 4, 5],
        "outcome_success": [1, 2, 3, 4, 6],
        "defect_observed": [5, 3, 4, 1, 2],
    })
    _, out = _run(tmp_path, monkeypatch, data)
    receipt = json.loads(out.read_text())
    comps = receipt["components"]
    assert [c["component"] for c in comps] == ["PC1", "PC2", "PC3"]
    assert sum(c["explained_variance_ratio"] for c in comps) == pytest.approx(1.0)
    assert receipt["pc1_to_pc2_variance_ratio"] > 1.2
    assert receipt["pc1_flattening_interpretation"]["navigation_focus"] == "PC1"
    ranking = receipt["next_action_ranking"]
    assert [r["rank"] for r in ranking] == [1, 2, 3]
    loads = [r["loading_abs"] for r in ranking]
    assert loads == sorted(loads, reverse=True)
    assert all(r["evidence_class"] == "INFERRED_FROM_MEASURED_PCA" for r in ranking)
    assert {r["feature"] for r in ranking} == {"wall_seconds", "outcome_success", "defect_observed"}


def test_main_perfectly_correlated_has_no_ratio(tmp_path, monkeypatch, capsys):
    data = _data({"wall_seconds": [1, 2, 3], "outcome_success": [2, 4, 6]})
    _, out = _run(tmp_path, monkeypatch, data)
    receipt = json.loads(out.read_text())
    assert receipt["components"][1]["eigenvalue"] == 0.0
    assert receipt["pc1_to_pc2_variance_ratio"] is None
    assert receipt["pc1_flattening_interpretation"]["pc1_flattened_relative_to_pc2"] is False
    assert receipt["pc1_flattening_interpretation"]["navigation_focus"] == "PC1"


def test_main_on_committed_w3_13_pulses(tmp_path, monkeypatch, capsys):
    inp = REAL_INPUT
    out = tmp_path / "real.json"
    monkeypatch.setattr(
        sys, "argv", ["w3_14_measured_pca.py", "--input", str(inp), "--out", str(out), "--source-sha", SHA]
    )
    pca.main()
    receipt = json.loads(out.read_text())
    assert receipt["schema"] == "qps-w3-14-measured-pca/v1"
    assert receipt["input_rows"] == 6
    assert receipt["input_sha256"] == hashlib.sha256(inp.read_bytes()).hexdigest()
    assert sorted(receipt["features_active"] + receipt["features_dropped_zero_variance"]) == sorted(FEATURES)
    assert sum(c["explained_variance_ratio"] for c in receipt["components"]) == pytest.approx(1.0)
    assert receipt["execution"] == {"steps_gt0": True, "outcome": "SUCCESS"}
