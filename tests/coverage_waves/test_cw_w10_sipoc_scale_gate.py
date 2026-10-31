"""Coverage wave w10: sipoc_scale_gate fail-closed inputs, pair reasons and CLI."""
import copy
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "gogreen" / "sipoc_scale_gate.py"
_spec = importlib.util.spec_from_file_location("cw_w10_sipoc_scale_gate_mod", MOD_PATH)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

SHA = "a" * 40
REPO = "GBOGEB/pipeline-automation-hub"
HEADS = {REPO: SHA}


def digest(n):
    return format(n, "064x")


def pair(i, pulse=0):
    base = 1000 * pulse + i
    proof = dict(run_id=base, attempt=1, job_id=base + 10, source_sha=SHA,
                 receipt_sha256=digest(base), status="completed", conclusion="success")
    check = dict(proof, run_id=base + 100, job_id=base + 110, receipt_sha256=digest(base + 100))
    return dict(id="PAIR-%d" % i, repo=REPO, source_sha=SHA, root_id=None,
                first_red_roots=[], lease_collision=False,
                worker=dict(actor="worker-%d" % i, mode="MUTATION_PROPOSAL",
                            mutation_paths=["features/%d.py" % i], native=proof),
                verifier=dict(actor="verifier-%d" % i, mode="NATIVE_PROVE", native=check))


def window(pulse_id, value):
    return dict(scope="JADE", denominator="executed-jobs", time_unit="seconds",
                repo_population="focus5", metric_key="queue_p95_seconds",
                count=10, value=value, pulse_id=pulse_id, source_heads=dict(HEADS))


def sample(target=4):
    return dict(schema=m.SCHEMA, authority_transfer=False, merge_authorized=False,
                dispatch_authorized=False, target_mutators=target, source_heads=dict(HEADS),
                pulses=[dict(pulse_id=n, pairs=[pair(1, n), pair(2, n)],
                             first_red_recurrences=0, security_findings=0,
                             independent_review=True) for n in (7, 8)],
                metrics=dict(owner=m.METRIC_OWNER, before=window(7, 240), after=window(8, 210)))


def reasons(obs):
    return m.assess(obs)["reasons"]


def _p(obs, idx=0, pulse=1):
    return obs["pulses"][pulse]["pairs"][idx]


def test_baseline_candidate():
    out = m.assess(sample())
    assert out["classification"] == "SCALE_CANDIDATE_EXTERNAL_GATE"
    assert out["target_mutators"] == 4
    assert out["verified_pair_evidence_records"] == 4


@pytest.mark.parametrize("mutate,msg", [
    (lambda o: "not-a-dict", "schema"),
    (lambda o: dict(o, schema="x"), "schema"),
    (lambda o: dict(o, merge_authorized=True), "authority"),
    (lambda o: dict(o, target_mutators=3), "target"),
    (lambda o: dict(o, target_mutators=True), "target"),
    (lambda o: dict(o, source_heads={}), "source census"),
    (lambda o: dict(o, source_heads={"bad repo": SHA}), "source census"),
    (lambda o: dict(o, source_heads={REPO: "A" * 40}), "source census"),
    (lambda o: dict(o, pulses=[]), "pulse population"),
    (lambda o: dict(o, pulses="x"), "pulse population"),
    (lambda o: dict(o, pulses=["x"]), "nonmonotonic"),
    (lambda o: dict(o, pulses=[dict(pulse_id=0)]), "nonmonotonic"),
    (lambda o: dict(o, pulses=[dict(pulse_id=2), dict(pulse_id=1)]), "nonmonotonic"),
    (lambda o: dict(o, pulses=[dict(pulse_id=1, source_heads={})]), "pulse source census"),
])
def test_fail_closed_inputs(mutate, msg):
    with pytest.raises(ValueError, match=msg):
        m.assess(mutate(sample()))


def test_unsafe_mutation_path_raises():
    obs = sample()
    _p(obs)["worker"]["mutation_paths"] = ["../escape"]
    with pytest.raises(ValueError, match="unsafe mutation path"):
        m.assess(obs)


@pytest.mark.parametrize("fn,reason", [
    (lambda o: o["pulses"][1].__setitem__("pairs", [pair(1)]), "TWO_WORKER_VERIFIER_PAIRS_REQUIRED"),
    (lambda o: o["pulses"][1]["pairs"].__setitem__(0, "x"), "INVALID_PAIR_ID"),
    (lambda o: _p(o).__setitem__("id", 5), "INVALID_PAIR_ID"),
    (lambda o: _p(o, 1).__setitem__("id", _p(o)["id"]), "DUPLICATE_PAIR_ID"),
    (lambda o: _p(o).__setitem__("repo", "other/repo"), "PAIR_SOURCE_SHA_MISMATCH"),
    (lambda o: _p(o).__setitem__("source_sha", "c" * 40), "PAIR_SOURCE_SHA_MISMATCH"),
    (lambda o: _p(o).__setitem__("worker", None), "INVALID_PAIR_ACTOR"),
    (lambda o: _p(o).__setitem__("verifier", []), "INVALID_PAIR_ACTOR"),
    (lambda o: _p(o)["worker"].__setitem__("actor", ""), "INDEPENDENT_VERIFIER_MISSING"),
    (lambda o: _p(o)["verifier"].pop("actor"), "INDEPENDENT_VERIFIER_MISSING"),
    (lambda o: _p(o)["worker"].__setitem__("native", None), "EXACT_HEAD_NATIVE_PAIR_PROOF_MISSING"),
    (lambda o: _p(o)["verifier"]["native"].__setitem__("attempt", 0), "EXACT_HEAD_NATIVE_PAIR_PROOF_MISSING"),
    (lambda o: _p(o)["verifier"]["native"].__setitem__("job_id", "1"), "EXACT_HEAD_NATIVE_PAIR_PROOF_MISSING"),
    (lambda o: _p(o)["verifier"]["native"].__setitem__("status", "queued"),
     "EXACT_HEAD_NATIVE_PAIR_PROOF_MISSING"),
    (lambda o: _p(o)["verifier"]["native"].__setitem__("receipt_sha256", 7),
     "EXACT_HEAD_NATIVE_PAIR_PROOF_MISSING"),
    (lambda o: _p(o)["verifier"]["native"].__setitem__(
        "receipt_sha256", _p(o)["worker"]["native"]["receipt_sha256"]), "NATIVE_RECEIPT_REUSED"),
    (lambda o: _p(o)["worker"].__setitem__("mode", "PROVE"), "INVALID_PAIR_MODE"),
    (lambda o: _p(o)["verifier"].__setitem__("mode", "X"), "INVALID_PAIR_MODE"),
    (lambda o: _p(o).__setitem__("first_red_roots", ["r1"]), "FIRST_RED_OR_LEASE_COLLISION"),
    (lambda o: _p(o).__setitem__("lease_collision", None), "FIRST_RED_OR_LEASE_COLLISION"),
    (lambda o: _p(o)["worker"].__setitem__("mutation_paths", []), "MISSING_MUTATION_LEASE"),
    (lambda o: _p(o)["worker"].__setitem__("mutation_paths", "a.py"), "MISSING_MUTATION_LEASE"),
    (lambda o: _p(o)["worker"].__setitem__("mutation_paths", ["a.py", "a.py"]), "DUPLICATE_MUTATION_LEASE"),
    (lambda o: _p(o, 1)["worker"].__setitem__("mutation_paths", ["features/1.py/sub"]),
     "OVERLAPPING_DISJOINT_WORKER_LEASES"),
    (lambda o: (_p(o).__setitem__("root_id", "R"), _p(o, 1).__setitem__("root_id", "R")),
     "OVERLAPPING_DISJOINT_WORKER_LEASES"),
    (lambda o: o["pulses"][1].__setitem__("security_findings", 1), "RECURRING_ROOT_OR_SECURITY_HOLD"),
    (lambda o: o["pulses"][1].__setitem__("first_red_recurrences", None), "RECURRING_ROOT_OR_SECURITY_HOLD"),
    (lambda o: o["pulses"][1].__setitem__("independent_review", "yes"), "PULSE_INDEPENDENT_REVIEW_MISSING"),
    (lambda o: o.__setitem__("metrics", None), "CANONICAL_METRIC_OWNER_MISSING"),
    (lambda o: o["metrics"].__setitem__("owner", "x"), "CANONICAL_METRIC_OWNER_MISSING"),
    (lambda o: o["metrics"].__setitem__("before", None), "COMPARABLE_METRIC_WINDOWS_MISSING"),
    (lambda o: o["metrics"].__setitem__("after", []), "COMPARABLE_METRIC_WINDOWS_MISSING"),
    (lambda o: o["metrics"]["after"].__setitem__("scope", "OTHER"), "METRIC_COHORT_NOT_COMPARABLE"),
    (lambda o: o["metrics"]["before"].__setitem__("scope", None), "METRIC_COHORT_NOT_COMPARABLE"),
    (lambda o: (o["metrics"]["before"].__setitem__("metric_key", "k"),
                o["metrics"]["after"].__setitem__("metric_key", "k")), "METRIC_COHORT_NOT_COMPARABLE"),
    (lambda o: o["metrics"]["before"].__setitem__("pulse_id", "7"), "METRIC_WINDOW_NOT_SOURCE_BOUND"),
    (lambda o: o["metrics"]["after"].__setitem__("pulse_id", 7.0), "METRIC_WINDOW_NOT_SOURCE_BOUND"),
    (lambda o: o["metrics"]["after"].__setitem__("pulse_id", 7), "METRIC_WINDOW_NOT_SOURCE_BOUND"),
    (lambda o: o["metrics"]["before"].__setitem__("pulse_id", 99), "METRIC_WINDOW_NOT_SOURCE_BOUND"),
    (lambda o: o["metrics"]["before"].__setitem__("pulse_id", 8), "METRIC_WINDOW_NOT_SOURCE_BOUND"),
    (lambda o: o["metrics"]["before"].__setitem__("source_heads", {}), "METRIC_WINDOW_NOT_SOURCE_BOUND"),
    (lambda o: o["metrics"]["after"].__setitem__("source_heads", {}), "METRIC_WINDOW_NOT_SOURCE_BOUND"),
    (lambda o: o["metrics"]["before"].__setitem__("count", 4), "QUEUE_METRIC_WITHHELD_OR_UNDERSAMPLED"),
    (lambda o: o["metrics"]["after"].__setitem__("count", 5.0), "QUEUE_METRIC_WITHHELD_OR_UNDERSAMPLED"),
    (lambda o: o["metrics"]["after"].__setitem__("value", "1"), "QUEUE_METRIC_WITHHELD_OR_UNDERSAMPLED"),
    (lambda o: o["metrics"]["after"].__setitem__("value", -1), "QUEUE_METRIC_WITHHELD_OR_UNDERSAMPLED"),
    (lambda o: o["metrics"]["after"].__setitem__("value", float("inf")),
     "QUEUE_METRIC_WITHHELD_OR_UNDERSAMPLED"),
    (lambda o: o["metrics"]["after"].__setitem__("value", 300.5), "QUEUE_P95_REGRESSION"),
])
def test_hold_reasons(fn, reason):
    obs = sample()
    fn(obs)
    got = reasons(obs)
    assert reason in got
    assert got == sorted(set(got))


def test_hold_downgrades_target():
    obs = sample()
    obs["pulses"][1]["independent_review"] = False
    out = m.assess(obs)
    assert out["classification"] == "HOLD"
    assert out["target_mutators"] == 2
    assert out["requested_mutators"] == 4


def test_target_four_needs_two_consecutive_pulses():
    obs = sample()
    obs["pulses"] = obs["pulses"][1:]
    assert "TWO_CONSECUTIVE_PULSES_REQUIRED" in reasons(obs)
    obs = sample()
    obs["pulses"][1]["pulse_id"] = 10
    obs["metrics"]["after"]["pulse_id"] = 10
    assert "PULSE_SEQUENCE_GAP" in reasons(obs)


def test_target_two_single_pulse_and_per_pulse_census():
    obs = sample(target=2)
    obs["pulses"] = obs["pulses"][1:]
    obs["pulses"][0]["source_heads"] = dict(HEADS)
    obs["metrics"]["before"]["pulse_id"] = 8
    rs = reasons(obs)
    assert "TWO_CONSECUTIVE_PULSES_REQUIRED" not in rs
    assert "METRIC_WINDOW_NOT_SOURCE_BOUND" in rs


def test_native_evidence_reused_across_pulses():
    obs = sample()
    _p(obs)["worker"]["native"] = copy.deepcopy(obs["pulses"][0]["pairs"][0]["worker"]["native"])
    assert "NATIVE_EVIDENCE_REUSED" in reasons(obs)


def test_same_pair_paths_do_not_count_as_overlap():
    obs = sample()
    _p(obs)["worker"]["mutation_paths"] = ["a/b.py", "a/b.py/c"]
    assert "OVERLAPPING_DISJOINT_WORKER_LEASES" not in reasons(obs)


def test_other_repo_leases_do_not_overlap():
    obs = sample()
    other = "GBOGEB/other"
    obs["source_heads"][other] = SHA
    for p in obs["pulses"]:
        p["pairs"][1]["repo"] = other
        p["pairs"][1]["worker"]["mutation_paths"] = ["features/1.py"]
    obs["metrics"]["before"]["source_heads"] = dict(obs["source_heads"])
    obs["metrics"]["after"]["source_heads"] = dict(obs["source_heads"])
    assert m.assess(obs)["classification"] == "SCALE_CANDIDATE_EXTERNAL_GATE"


@pytest.mark.parametrize("bad", ["", "/abs", "a\\b", "a//b", "./a", 3])
def test_path_overlap_rejects_unsafe(bad):
    with pytest.raises(ValueError):
        m._path_overlap(bad, "ok")


def test_path_overlap_casefold_and_prefix():
    assert m._path_overlap("A/B", "a/b")
    assert m._path_overlap("a", "a/b")
    assert m._path_overlap("a/b", "a")
    assert not m._path_overlap("ab", "a")


def test_main_exit_codes(tmp_path, capsys):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(sample()), encoding="utf-8")
    assert m.main([str(good)]) == 0
    assert json.loads(capsys.readouterr().out)["classification"] == "SCALE_CANDIDATE_EXTERNAL_GATE"
    obs = sample()
    obs["metrics"] = None
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(obs), encoding="utf-8")
    assert m.main([str(bad)]) == 2


def test_dunder_main(tmp_path, monkeypatch, capsys):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(sample()), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(MOD_PATH), str(good)])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert exc.value.code == 0
    assert "classification" in capsys.readouterr().out
