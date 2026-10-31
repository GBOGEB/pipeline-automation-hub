"""Coverage wave w10: rf_matrix_wave DAG/matrix validation, goal readback, replay and CLI."""
import copy
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "jade_temple" / "tools" / "rf_matrix_wave.py"
_spec = importlib.util.spec_from_file_location("cw_w10_rf_matrix_wave_mod", MOD_PATH)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

SHA = "a" * 40
_MATRIX = json.loads(M.CONTRACT.read_text(encoding="utf-8"))
_DAG = json.loads(M.BUNDLES.read_text(encoding="utf-8"))


def data():
    return copy.deepcopy(_MATRIX), copy.deepcopy(_DAG)


def receipt(run_id=100, result="success", population=2):
    return {"head_sha": SHA, "run_id": run_id, "attempt": 1, "result": result,
            "test_population": population, "digest": "f" * 64}


def obs(**changes):
    goal = _MATRIX["goal"]
    base = {"metric": goal["metric"], "metric_owner": M.METRIC_OWNER, "source_sha": SHA,
            "sample_method": goal["sample_method"], "value": 0.1,
            "sample_n": goal["minimum_sample"], "observed_at": "2099-01-01T00:00:00Z",
            "receipt_sha256": "e" * 64}
    base.update(changes)
    return base


def journal(*waves):
    return {"schema": "jade.devops.rf-journal.v1", "source_sha": SHA, "waves": list(waves)}


def first_wave_ids():
    matrix, dag = data()
    return [x["id"] for x in M.project(matrix, dag, SHA)["matrix"]["on"]]


def test_real_contract_shape():
    nodes, links = M.dag_index(copy.deepcopy(_DAG))
    assert set(nodes) == {"B%02d" % i for i in range(10)}
    assert all(len(x) == 3 for x in links)


# ---- dag_index -----------------------------------------------------------

def _first_feedforward(dag):
    return next(e for e in dag["edges"] if e["kind"] == "FEEDFORWARD")


@pytest.mark.parametrize("mutate,msg", [
    (lambda d: d.__setitem__("schema", "x"), "design-only"),
    (lambda d: d.__setitem__("record_type", "live"), "design-only"),
    (lambda d: d.__setitem__("nodes", {}), "nodes or edges"),
    (lambda d: d.__setitem__("edges", None), "nodes or edges"),
    (lambda d: d["nodes"].append("junk"), "bundle identity"),
    (lambda d: d["nodes"][0].__setitem__("id", "wrong"), "bundle identity"),
    (lambda d: d["nodes"][0].__setitem__("sipoc", []), "SIPOC incomplete"),
    (lambda d: d["nodes"][0]["sipoc"].__setitem__("output", []), "SIPOC incomplete"),
    (lambda d: d["nodes"][0]["sipoc"].__setitem__("output", "x"), "SIPOC incomplete"),
    (lambda d: d["nodes"][0].__setitem__("devops_stage", ""), "stage/source anchor"),
    (lambda d: d["nodes"][0].pop("example_workflow"), "stage/source anchor"),
    (lambda d: _first_feedforward(d).__setitem__("kind", "SIDEWAYS"), "unknown edge type"),
    (lambda d: _first_feedforward(d).__setitem__("from", "ci-spine:bundle:B99"), "dangling"),
    (lambda d: _first_feedforward(d).__setitem__("to", "nowhere"), "dangling"),
    (lambda d: d["edges"].append({"from": "ci-spine:bundle:B08", "to": "ci-spine:bundle:B00",
                                  "kind": "FEEDBACK_NEXT_PULSE"}), "temporal feedback"),
])
def test_dag_index_fail_closed(mutate, msg):
    _, dag = data()
    mutate(dag)
    with pytest.raises(ValueError, match=msg):
        M.dag_index(dag)


def test_reaches_paths():
    links = [("a", "b", "FEEDFORWARD"), ("b", "c", "FEEDFORWARD"), ("c", "a", "FEEDBACK_NEXT_PULSE"),
             ("b", "a", "FEEDFORWARD")]
    assert M._reaches("x", "x", links)
    assert M._reaches("a", "c", links)
    assert not M._reaches("c", "a", links)
    assert not M._reaches("a", "zzz", links)


# ---- validate_matrix -----------------------------------------------------

@pytest.mark.parametrize("mutate,msg", [
    (lambda m: m.__setitem__("schema", "x"), "advisory RF contract"),
    (lambda m: m.__setitem__("authority", "DISPATCH"), "advisory RF contract"),
    (lambda m: m.__setitem__("lanes", []), "lane count"),
    (lambda m: m.__setitem__("lanes", {"a": 1}), "lane count"),
    (lambda m: m.__setitem__("lanes", m["lanes"] * 3), "lane count"),
    (lambda m: m["lanes"].append("junk"), "lane IDs"),
    (lambda m: m["lanes"][0].__setitem__("id", ""), "lane IDs"),
    (lambda m: m["lanes"][0].__setitem__("id", 7), "lane IDs"),
    (lambda m: m["lanes"][1].__setitem__("id", m["lanes"][0]["id"]), "lane IDs"),
    (lambda m: m["lanes"][0].__setitem__("bundle", "B99"), "unknown B00..B09"),
    (lambda m: m["lanes"][0].__setitem__("phase", "PX"), "phase/crew"),
    (lambda m: m["lanes"][0].__setitem__("crew", "PILOT"), "phase/crew"),
    (lambda m: m["lanes"][0].__setitem__("t0_ref", 5), "T0 receipt"),
    (lambda m: m["lanes"][0].__setitem__("t0_ref", "  "), "T0 receipt"),
    (lambda m: m["lanes"][0].__setitem__("t0_ref", "../x"), "T0 receipt"),
    (lambda m: m["lanes"][0].__setitem__("depends_on", "P1"), "unregistered dependency"),
    (lambda m: m["lanes"][0].__setitem__("depends_on", ["NOPE"]), "unregistered dependency"),
    (lambda m: m.__setitem__("goal", None), "goal lacks"),
    (lambda m: m["goal"].__setitem__("metric_owner", "x"), "goal lacks"),
    (lambda m: m["goal"].__setitem__("comparison", "equal"), "goal lacks"),
    (lambda m: m["goal"].__setitem__("target", "0.2"), "goal lacks"),
    (lambda m: m["goal"].__setitem__("target", True), "goal lacks"),
    (lambda m: m["goal"].__setitem__("target", 1.5), "goal lacks"),
    (lambda m: m["goal"].__setitem__("minimum_sample", 0), "goal lacks"),
    (lambda m: m["goal"].__setitem__("minimum_sample", "1"), "goal lacks"),
    (lambda m: m["goal"].__setitem__("metric", ""), "goal lacks"),
    (lambda m: m["goal"].pop("sample_method"), "goal lacks"),
])
def test_validate_matrix_fail_closed(mutate, msg):
    matrix, dag = data()
    mutate(matrix)
    with pytest.raises(ValueError, match=msg):
        M.validate_matrix(matrix, dag, SHA)


@pytest.mark.parametrize("sha", [None, "A" * 40, "a" * 39])
def test_validate_matrix_requires_exact_sha(sha):
    matrix, dag = data()
    with pytest.raises(ValueError, match="source_sha"):
        M.validate_matrix(matrix, dag, sha)


@pytest.mark.parametrize("change", [
    {"head_sha": "b" * 40}, {"run_id": True}, {"run_id": 0}, {"run_id": "1"},
    {"attempt": 0}, {"attempt": None}, {"result": "failure"},
    {"test_population": 0}, {"test_population": "3"}, {"digest": "g" * 64},
])
def test_done_receipt_shape(change):
    matrix, dag = data()
    lane = matrix["lanes"][0]
    lane["state"] = "DONE"
    lane["execution_receipt"] = dict(receipt(), **change)
    with pytest.raises(ValueError, match="execution receipt"):
        M.validate_matrix(matrix, dag, SHA)


def test_validate_matrix_defaults_for_optional_lane_fields():
    matrix, dag = data()
    for key in ("depends_on", "write_pr", "touch_paths", "cluster"):
        matrix["lanes"][0].pop(key, None)
    _, steps = M.validate_matrix(matrix, dag, SHA)
    assert steps[0]["depends_on"] == []
    assert steps[0]["write_pr"] is False
    assert steps[0]["touch_paths"] == []


def test_goal_target_bounds_accept_int():
    matrix, dag = data()
    matrix["goal"]["target"] = 0
    matrix["goal"]["comparison"] = "at_least"
    M.validate_matrix(matrix, dag, SHA)


# ---- goal_readback -------------------------------------------------------

GOAL = _MATRIX["goal"]


@pytest.mark.parametrize("observation", [None, [], "x"])
def test_goal_unknown_without_observation(observation):
    out = M.goal_readback(GOAL, observation, SHA)
    assert out["status"] == "UNKNOWN" and "reason" not in out


@pytest.mark.parametrize("change", [
    {"metric": "other"}, {"metric_owner": "x"}, {"source_sha": "b" * 40}, {"sample_method": "x"},
])
def test_goal_wrong_cohort(change):
    assert M.goal_readback(GOAL, obs(**change), SHA)["reason"] == "WRONG_SOURCE_OR_COHORT"


@pytest.mark.parametrize("change", [
    {"sample_n": True}, {"sample_n": "1000"}, {"sample_n": 1}, {"value": "0.1"},
    {"value": False}, {"value": float("inf")}, {"value": 1.5}, {"value": -0.1},
    {"receipt_sha256": None},
])
def test_goal_malformed_evidence(change):
    out = M.goal_readback(GOAL, obs(**change), SHA)
    assert out["reason"] == "INSUFFICIENT_OR_MALFORMED_EVIDENCE"


@pytest.mark.parametrize("change,goal_change", [
    ({"observed_at": None}, None),
    ({"observed_at": "not-a-date"}, None),
    ({"observed_at": "2099-01-01T00:00:00"}, None),
    ({"observed_at": "2000-01-01T00:00:00Z"}, None),
    ({}, {"t0": {}}),
    ({}, {"t0": {"observed_at": "2026-10-28T14:50:00"}}),
])
def test_goal_time_guard(change, goal_change):
    goal = dict(GOAL, **(goal_change or {}))
    observation = obs(**change)
    if change.get("observed_at", "") is None:
        observation.pop("observed_at")
    assert M.goal_readback(goal, observation, SHA)["reason"] == "STALE_OR_UNKNOWN_TIME"


@pytest.mark.parametrize("comparison,value,status", [
    ("at_most", 0.1, "TARGET_REACHED_UNVERIFIED"),
    ("at_most", 0.9, "TARGET_NOT_YET_REACHED"),
    ("at_least", 0.9, "TARGET_REACHED_UNVERIFIED"),
    ("at_least", 0.1, "TARGET_NOT_YET_REACHED"),
])
def test_goal_comparison(comparison, value, status):
    goal = dict(GOAL, comparison=comparison)
    out = M.goal_readback(goal, obs(value=value), SHA)
    assert out["status"] == status
    assert out["admission"] == "HOLD"
    assert out["sample_n"] == GOAL["minimum_sample"]


# ---- project / replay ----------------------------------------------------

def test_project_annotates_all_categories():
    matrix, dag = data()
    out = M.project(matrix, dag, SHA, open_stack=5)
    for cat in ("on", "off", "held"):
        for item in out["matrix"][cat]:
            assert {"bundle", "devops_stage", "sipoc"} <= set(item)
    assert out["authority"]["dispatch_performed"] is False


@pytest.mark.parametrize("max_waves", [0, 9, True, "3"])
def test_replay_rejects_bad_budget(max_waves):
    matrix, dag = data()
    with pytest.raises(ValueError, match="max_waves"):
        M.replay_until_goal(matrix, dag, SHA, journal(), max_waves=max_waves)


@pytest.mark.parametrize("j", [
    None, {"schema": "x", "source_sha": SHA, "waves": []},
    {"schema": "jade.devops.rf-journal.v1", "source_sha": SHA, "waves": "x"},
    {"schema": "jade.devops.rf-journal.v1", "source_sha": SHA, "waves": [{}] * 3},
])
def test_replay_rejects_bad_journal(j):
    matrix, dag = data()
    with pytest.raises(ValueError, match="journal"):
        M.replay_until_goal(matrix, dag, SHA, j, max_waves=2)


def test_replay_does_not_mutate_caller():
    matrix, dag = data()
    before = json.dumps(matrix, sort_keys=True)
    rows = [{"id": n, "receipt": receipt(100 + i)} for i, n in enumerate(first_wave_ids())]
    M.replay_until_goal(matrix, dag, SHA, journal({"results": rows}), max_waves=2)
    assert json.dumps(matrix, sort_keys=True) == before


def test_replay_stalls_when_nothing_is_on():
    matrix, dag = data()
    for i, lane in enumerate(matrix["lanes"]):
        lane["state"] = "DONE"
        lane["execution_receipt"] = receipt(500 + i)
    r = M.replay_until_goal(matrix, dag, SHA, journal())
    assert r["state"] == "STALLED_OR_HOLD"
    assert r["wave_count"] == 1
    assert r["history"][0]["candidate_ids"] == []


def test_replay_empty_results_waits():
    matrix, dag = data()
    r = M.replay_until_goal(matrix, dag, SHA, journal({"results": []}), max_waves=3)
    assert r["state"] == "WAIT_FOR_WAVE_EVIDENCE"
    assert r["wave_count"] == 1


@pytest.mark.xfail(strict=True, raises=AttributeError,
                   reason="production_defect: non-dict journal wave raises AttributeError at "
                          "rf_matrix_wave.py:245, not the fail-closed ValueError")
def test_replay_non_dict_wave_fails_closed_with_value_error():
    matrix, dag = data()
    with pytest.raises(ValueError):
        M.replay_until_goal(matrix, dag, SHA, journal("junk"), max_waves=2)


@pytest.mark.parametrize("wave,msg", [
    ({"results": None}, "explicit results list"),
    ({"results": ["x"]}, "not a result object"),
    ({"results": [{"id": "P0_BASELINE_READER", "receipt": None}]}, "missing execution receipt"),
])
def test_replay_rejects_bad_results(wave, msg):
    matrix, dag = data()
    with pytest.raises(ValueError, match=msg):
        M.replay_until_goal(matrix, dag, SHA, journal(wave))


@pytest.mark.parametrize("change", [
    {"head_sha": "b" * 40}, {"run_id": "1"}, {"run_id": False}, {"run_id": 0},
    {"attempt": "1"}, {"attempt": 0}, {"digest": "x"}, {"result": "cancelled"},
])
def test_replay_rejects_malformed_receipt(change):
    matrix, dag = data()
    row = {"id": "P0_BASELINE_READER", "receipt": dict(receipt(), **change)}
    with pytest.raises(ValueError, match="malformed or cross-head"):
        M.replay_until_goal(matrix, dag, SHA, journal({"results": [row]}))


@pytest.mark.parametrize("population", [0, None, "2"])
def test_replay_success_needs_tests(population):
    matrix, dag = data()
    row = {"id": "P0_BASELINE_READER", "receipt": receipt(population=population)}
    with pytest.raises(ValueError, match="nonzero tests"):
        M.replay_until_goal(matrix, dag, SHA, journal({"results": [row]}))


def test_replay_failure_without_population_is_recorded():
    matrix, dag = data()
    row = {"id": "P0_BASELINE_READER", "receipt": receipt(result="failure", population=None)}
    r = M.replay_until_goal(matrix, dag, SHA, journal({"results": [row]}), max_waves=2)
    assert r["history"][0]["asserted_failed"] == ["P0_BASELINE_READER"]
    assert r["state"] == "WAIT_FOR_WAVE_EVIDENCE"
    assert r["wave_count"] == 2


def test_replay_continues_across_multiple_waves():
    matrix, dag = data()
    ids = first_wave_ids()
    w1 = {"results": [{"id": n, "receipt": receipt(100 + i)} for i, n in enumerate(ids)],
          "observation": obs(value=0.9)}
    r = M.replay_until_goal(matrix, dag, SHA, journal(w1), max_waves=3)
    assert r["history"][0]["goal"]["action"] == "CONTINUE_RF_WAVES"
    assert r["wave_count"] == 2
    assert r["state"] == "WAIT_FOR_WAVE_EVIDENCE"


# ---- CLI -----------------------------------------------------------------

def test_main_prints_projection(capsys):
    assert M.main(["--source-sha", SHA]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["schema"] == "jade.devops.rf-matrix-projection.v1"


def test_main_observation_and_journal(tmp_path):
    o = tmp_path / "obs.json"
    o.write_text(json.dumps(obs(value=0.1)), encoding="utf-8")
    out = tmp_path / "nested" / "p.json"
    assert M.main(["--source-sha", SHA, "--observation", str(o), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["goal"]["status"] == "TARGET_REACHED_UNVERIFIED"
    j = tmp_path / "j.json"
    j.write_text(json.dumps(journal()), encoding="utf-8")
    out2 = tmp_path / "r.json"
    assert M.main(["--source-sha", SHA, "--journal", str(j), "--out", str(out2),
                   "--max-parallel", "4", "--per-cluster", "1", "--open-stack", "1"]) == 0
    assert json.loads(out2.read_text(encoding="utf-8"))["schema"] == "jade.devops.rf-replay.v1"


def test_dunder_main(tmp_path, monkeypatch, capsys):
    out = tmp_path / "x.json"
    monkeypatch.setattr(sys, "argv", [str(MOD_PATH), "--source-sha", SHA, "--out", str(out)])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert exc.value.code == 0
    assert out.exists()
