"""Behavioural tests for mission-control/grand-missions/analytics/gm_i_a_multiclock_analyze.py."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET = REPO_ROOT / "mission-control" / "grand-missions" / "analytics" / "gm_i_a_multiclock_analyze.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_gm_i_a_multiclock_analyze", TARGET)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mc = _load()

QUEUE = ["heavy_queue_seconds", "fast_queue_seconds", "dow_queue_seconds", "keb_queue_seconds"]
WORK = ["build_seconds", "test_seconds", "lint_seconds", "deploy_seconds", "scan_seconds"]
FEATURES = QUEUE + WORK


def _row(pid: str, values: list[float]) -> dict:
    row = {"pulse_id": pid, "evidence_class": "MEASURED"}
    row.update(dict(zip(FEATURES, values)))
    return row


def _doc(rows: list[dict], features: list[str] | None = None, bt_min: int = 3) -> dict:
    return {
        "mission": "GM-I-A",
        "features": list(FEATURES if features is None else features),
        "rows": rows,
        "bt_gate": {"minimum_repeat_pulses": bt_min},
    }


def _run(tmp_path: Path, monkeypatch, doc: dict, extra_args: list[str] | None = None) -> dict:
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(doc), encoding="utf-8")
    out = tmp_path / "out.json"
    argv = [
        "prog", "--input", str(inp), "--out", str(out),
        "--pairs-out", str(tmp_path / "pairs.json"), "--csv-out", str(tmp_path / "rows.csv"),
    ] + (extra_args or [])
    monkeypatch.setattr(sys, "argv", argv)
    assert mc.main() == 0
    return json.loads(out.read_text(encoding="utf-8"))


def _rotations(n: int) -> list[dict]:
    base = [float(v) for v in range(1, 10)]
    rows = []
    for i in range(n):
        k = i % 9
        rows.append(_row("p%02d" % i, base[k:] + base[:k]))
    return rows


# ---------------------------------------------------------------- helpers


def test_strongly_connected_cases():
    assert mc.strongly_connected([], []) is False
    assert mc.strongly_connected(["a"], []) is True
    assert mc.strongly_connected(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")]) is True
    assert mc.strongly_connected(["a", "b", "c"], [("a", "b"), ("b", "c")]) is False
    # forward reachable but not backward from root
    assert mc.strongly_connected(["a", "b"], [("a", "b")]) is False


def test_bidirectional_pairs_counts_unordered_pairs_once():
    edges = [("a", "b"), ("b", "a"), ("a", "b"), ("b", "c"), ("c", "a"), ("a", "c")]
    assert mc.bidirectional_pairs(edges) == 2
    assert mc.bidirectional_pairs([]) == 0
    assert mc.bidirectional_pairs([("x", "y")]) == 0


# ---------------------------------------------------------------- main happy paths


def test_single_pulse_defers_and_writes_all_outputs(tmp_path, monkeypatch, capsys):
    # queue features 10,20,30,40 ; work 1..5 ; one tie between dow and lint (30 vs 30)
    values = [10.0, 20.0, 30.0, 40.0, 1.0, 2.0, 30.0, 4.0, 5.0]
    doc = _doc([_row("p1", values)])
    ds = tmp_path / "dataset.json"
    res = _run(tmp_path, monkeypatch, doc, ["--dataset-out", str(ds)])

    assert res["schema"] == "missioncontrol.gm_i_a.multiclock_readiness.v2"
    assert res["mission"] == "GM-I-A"
    assert res["measured_pulses"] == 1
    assert res["feature_count_p"] == 9
    assert res["p_over_n"] == 9.0
    assert res["pca"]["status"] == "DEFER_INSUFFICIENT_COMPARABLE_MEASURED_PULSES"
    assert res["pca"]["minimum_rows_required"] == 27
    assert res["pca"]["rows_remaining_to_minimum"] == 26
    assert res["pca"]["varying_features"] == []
    assert res["pca"]["covariance_rank_upper_bound"] == 0
    bt = res["bt_reverse_pressure"]
    assert bt["status"] == "DEFER_NO_FINITE_MLE_REPEAT_STRUCTURE"
    assert bt["pair_records"] == 36
    assert bt["strict_pair_records"] == 35
    assert bt["repeat_pulses_remaining"] == 2
    assert bt["directed_win_graph_strongly_connected"] is False
    assert bt["bidirectional_pair_count"] == 0
    assert bt["unordered_pair_count"] == 36

    lat = res["latest_pulse_descriptive_pressure"]
    total = sum(values)
    assert lat["pulse_id"] == "p1"
    assert lat["selected_clock_seconds"] == total
    assert lat["queue_seconds"] == 100.0
    assert lat["nonqueue_seconds"] == total - 100.0
    assert lat["queue_fraction"] == pytest.approx(100.0 / total)
    assert lat["queue_to_nonqueue_ratio"] == pytest.approx(100.0 / (total - 100.0))
    assert lat["order"][0] == {"feature": "keb_queue_seconds", "seconds": 40.0}
    assert [s["family"] for s in lat["shares"][:1]] == ["QUEUE"]
    hhi = sum((v / total) ** 2 for v in values)
    assert lat["pressure_hhi"] == pytest.approx(hhi)
    assert lat["effective_clock_count"] == pytest.approx(1 / hhi)
    assert lat["top4_fraction"] == pytest.approx((40.0 + 30.0 + 30.0 + 20.0) / total)
    assert res["improvement_interpretation"]["queue_exposure_dominates"] is True

    pairs = json.loads((tmp_path / "pairs.json").read_text(encoding="utf-8"))
    ties = [c for c in pairs["comparisons"] if c["outcome"] == "TIE"]
    assert len(ties) == 1 and ties[0]["winner"] is None and ties[0]["loser"] is None
    first = pairs["comparisons"][0]
    assert (first["feature_a"], first["feature_b"], first["outcome"], first["winner"]) == (
        "heavy_queue_seconds", "fast_queue_seconds", "B_GT_A", "fast_queue_seconds")
    assert any(c["outcome"] == "A_GT_B" for c in pairs["comparisons"])

    with (tmp_path / "rows.csv").open(encoding="utf-8", newline="") as fh:
        csv_rows = list(csv.DictReader(fh))
    assert csv_rows[0]["pulse_id"] == "p1"
    assert float(csv_rows[0]["keb_queue_seconds"]) == 40.0
    assert "evidence_class" not in csv_rows[0]

    raw = ds.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == res["dataset_sha256"]
    assert json.loads(raw)["rows"][0]["pulse_id"] == "p1"
    assert json.loads(capsys.readouterr().out) == res


def test_repeated_rotations_make_pca_and_bt_ready(tmp_path, monkeypatch):
    rows = _rotations(27)
    res = _run(tmp_path, monkeypatch, _doc(rows))
    assert res["pca"]["status"] == "READY_FOR_GG_MATH_PROVIDER_FIT"
    assert res["pca"]["rows_remaining_to_minimum"] == 0
    assert res["pca"]["varying_features"] == FEATURES
    assert res["pca"]["covariance_rank_upper_bound"] == 9
    bt = res["bt_reverse_pressure"]
    assert bt["status"] == "READY_FOR_GG_MATH_PROVIDER_FIT"
    assert bt["directed_win_graph_strongly_connected"] is True
    assert bt["bidirectional_pair_count"] == 36
    assert bt["repeat_pulses_remaining"] == 0
    assert not (tmp_path / "dataset.json").exists()


def test_strong_graph_but_too_few_pulses_defers_bt(tmp_path, monkeypatch):
    res = _run(tmp_path, monkeypatch, _doc(_rotations(9), bt_min=10))
    assert res["bt_reverse_pressure"]["directed_win_graph_strongly_connected"] is True
    assert res["bt_reverse_pressure"]["status"] == "DEFER_NO_FINITE_MLE_REPEAT_STRUCTURE"
    assert res["bt_reverse_pressure"]["repeat_pulses_remaining"] == 1


@pytest.mark.parametrize("wrapped", [True, False])
def test_append_row_is_added_as_latest_pulse(tmp_path, monkeypatch, wrapped):
    extra_row = _row("p2", [0.0, 0.0, 0.0, 0.0, 5.0, 5.0, 5.0, 5.0, 5.0])
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps({"row": extra_row} if wrapped else extra_row), encoding="utf-8")
    doc = _doc([_row("p1", [float(v) for v in range(1, 10)])])
    res = _run(tmp_path, monkeypatch, doc, ["--append-row", str(extra), "--dataset-out", str(tmp_path / "d.json")])
    assert res["measured_pulses"] == 2
    lat = res["latest_pulse_descriptive_pressure"]
    assert lat["pulse_id"] == "p2"
    assert lat["queue_seconds"] == 0.0
    assert lat["queue_fraction"] == 0.0
    assert lat["effective_clock_count"] == pytest.approx(5.0)
    assert res["improvement_interpretation"]["queue_exposure_dominates"] is False
    dataset = json.loads((tmp_path / "d.json").read_text(encoding="utf-8"))
    assert [r["pulse_id"] for r in dataset["rows"]] == ["p1", "p2"]


def test_all_zero_pulse_yields_null_ratios(tmp_path, monkeypatch):
    res = _run(tmp_path, monkeypatch, _doc([_row("z", [0.0] * 9)]))
    lat = res["latest_pulse_descriptive_pressure"]
    assert lat["selected_clock_seconds"] == 0.0
    assert all(s["share"] is None for s in lat["shares"])
    assert lat["queue_fraction"] is None
    assert lat["queue_to_nonqueue_ratio"] is None
    assert lat["pressure_hhi"] == 0.0
    assert lat["effective_clock_count"] is None
    assert lat["top4_fraction"] is None
    assert res["improvement_interpretation"]["queue_exposure_dominates"] is False
    assert res["bt_reverse_pressure"]["strict_pair_records"] == 0


def test_script_entrypoint_exits_zero(tmp_path, monkeypatch, capsys):
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(_doc([_row("p1", [float(v) for v in range(1, 10)])])), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "prog", "--input", str(inp), "--out", str(tmp_path / "o.json"),
        "--pairs-out", str(tmp_path / "p.json"), "--csv-out", str(tmp_path / "c.csv"),
    ])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(TARGET), run_name="__main__")
    assert exc.value.code == 0
    assert (tmp_path / "o.json").exists()


# ---------------------------------------------------------------- error paths

GOOD = [float(v) for v in range(1, 10)]


def _bad_row(**changes) -> dict:
    row = _row("p1", GOOD)
    row.update(changes)
    return row


@pytest.mark.parametrize(
    "doc, message",
    [
        (_doc([_row("p1", GOOD)], features=FEATURES[:8]), "nine unique multi-clock features"),
        (_doc([_row("p1", GOOD)], features=FEATURES[:8] + [FEATURES[0]]), "nine unique multi-clock features"),
        (_doc([_row("p1", GOOD)], features=FEATURES[1:] + ["other_seconds"]), "queue clock family incomplete"),
        (_doc([_bad_row(pulse_id="")]), "missing or duplicate pulse_id"),
        (_doc([_row("p1", GOOD), _row("p1", GOOD)]), "missing or duplicate pulse_id"),
        (_doc([_bad_row(evidence_class="ESTIMATED")]), "non-MEASURED row"),
        (_doc([_bad_row(build_seconds="12")]), "nonnumeric feature build_seconds in p1"),
        (_doc([_bad_row(build_seconds=True)]), "nonnumeric feature build_seconds in p1"),
        (_doc([_bad_row(scan_seconds=-1.0)]), "invalid duration scan_seconds in p1"),
        (_doc([_bad_row(scan_seconds=float("inf"))]), "invalid duration scan_seconds in p1"),
    ],
)
def test_validation_failures(tmp_path, monkeypatch, doc, message):
    with pytest.raises(SystemExit, match=message):
        _run(tmp_path, monkeypatch, doc)
    assert not (tmp_path / "out.json").exists()


def test_missing_required_argument_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prog", "--input", str(tmp_path / "x.json")])
    with pytest.raises(SystemExit) as exc:
        mc.main()
    assert exc.value.code == 2
    assert "--out" in capsys.readouterr().err
