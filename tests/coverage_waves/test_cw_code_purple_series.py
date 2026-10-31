"""Behavioural tests for mission-control/federation-atlas/code_purple_series.py.

The existing suite (test_code_purple.py) checks the committed queue/series.  These
tests drive the schema-subset validator, queue/series semantics, metric
computation, append and the CLI against a synthetic tree in tmp_path.  The real
schemas are read (structural input only); QUEUE/SERIES/BEAMS/ROOT are redirected.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = REPO / "mission-control" / "federation-atlas" / "code_purple_series.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_code_purple_series_mod", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cps = _load()
SHA = "c" * 40


# ---------------------------------------------------------------- fixtures
def item(ident="CPQ-001", beam="B1", deps=(), critical=False, history=None):
    return {"id": ident, "finding": "F1", "title": "A synthetic item", "severity": "P2", "beam": beam,
            "critical_path": critical, "repos": ["GBOGEB/example"], "links": [], "depends_on": list(deps),
            "done_when": "tests pass", "control_when": "two pulses",
            "history": history or [{"at": "W1.C1.I0.S0", "state": "TODO", "flow": "READY", "evidence": "filed here"}]}


def queue_doc():
    return {"schema": "missioncontrol.code_purple.bd_queue.v1", "authority_transfer": False,
            "formal_credit_delta": 0, "engineering_credit_delta": 0,
            "lifecycle": ["TODO", "ACTIVE", "DONE", "CONTROL", "SUPERSEDED", "INVALIDATED", "UNKNOWN_NEEDS_READER"],
            "open_states": ["TODO", "ACTIVE", "UNKNOWN_NEEDS_READER"],
            "flows": ["READY", "IN_PR", "BLOCKED", "HOLD", "RETURN_OWNER", "LINKED", "NONE"],
            "items": [
                item("CPQ-001", critical=True, history=[
                    {"at": "W1.C1.I0.S0", "state": "TODO", "flow": "READY", "evidence": "filed here"},
                    {"at": "W1.C1.I1.S0", "state": "DONE", "flow": "NONE", "evidence": "merged pr"}]),
                item("CPQ-002", deps=["CPQ-001"], critical=True, history=[
                    {"at": "W1.C1.I0.S0", "state": "ACTIVE", "flow": "BLOCKED", "evidence": "filed here"}]),
                item("CPQ-003", history=[
                    {"at": "W1.C1.I1.S0", "state": "TODO", "flow": "IN_PR", "evidence": "filed late"}]),
            ]}


def contract(**cur_overrides):
    cur = {"top7_classified_observed": 7, "top7_green_control_observed": 5, "top7_unclassified_observed": 0,
           "mission_era_full_dmaic_iterations": 3, "abacus": {"d1": {"state": "PASS"}},
           "top7_proof_debt_two_pulse_nonincreasing": True, "max_unchanged_root_auto_repeat_after_control": 0,
           "top14_classified_observed": 10, "top14_green_control_observed": None, "top14_unclassified_observed": 4,
           "top14_proof_debt_observed": 9, "mission_era_distinct_repos_full_dmaic": 2,
           "recurrent_controls_with_distinct_source_repeat": 0,
           "top14_two_pulse_net_semantic_delta_le_zero": False, "top14_two_pulse_proof_yield_nondegrading": None}
    cur.update(cur_overrides)
    return {"current": cur,
            "promotion_gates": {
                "top7_to_top14": {"classified_min": 7, "green_control_min": 5, "unclassified_max": 0,
                                  "full_dmaic_iterations_min": 3, "abacus_d1_requires": "PASS",
                                  "unchanged_root_auto_repeat_max": 0, "recursive_control_handoff_min": 1},
                "top14_to_top21": {"classified_min": 14, "green_control_min": 10, "unclassified_max": 0,
                                   "proof_debt_max": 3, "full_dmaic_iterations_distinct_repos_min": 3,
                                   "recurrent_control_distinct_source_repeat_min": 1,
                                   "unchanged_root_auto_repeat_max": 0, "recursive_control_handoff_min": 2}},
            "iteration_evolution": {"recursive_control_handoff_count": 1, "iteration_chain_integrity": True,
                                    "complete_iteration_count": 4, "current_level": "E2_RECURSIVE"}}


def write_json(path: Path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """Synthetic repository tree plus redirected module constants."""
    root = tmp_path / "repo"
    write_json(root / cps.CONTRACT, contract())
    write_json(root / cps.COVERAGE, {"rows": [{"state": "MEASURED_LOCAL"}, {"state": "MEASURED"}, {"state": "UNKNOWN"}]})
    write_json(root / cps.TOPOLOGY, {"edges": [{"state": "PASS", "receipt_sha256": "a" * 64},
                                               {"state": "PASS"}, {"state": "FAIL", "receipt_sha256": "b" * 64}]})
    graph = root / cps.GRAPH
    graph.parent.mkdir(parents=True, exist_ok=True)
    graph.write_text("edges:\n  - {binding: RECEIPT}\n  - {binding: DECLARED}\n  - {binding: DECLARED}\n",
                     encoding="utf-8")
    (root / ".github" / "workflows").mkdir(parents=True)
    tools = tmp_path / "tools"
    (tools / "scripts").mkdir(parents=True)
    (tools / "scripts" / "zero_test_gate_audit.py").write_text(
        "from pathlib import Path\n"
        "def audit(root):\n"
        "    n = len(list((Path(root) / '.github' / 'workflows').glob('*.yml')))\n"
        "    return {'summary': {'zero_test_gates': n}}\n", encoding="utf-8")
    monkeypatch.setattr(cps, "ROOT", tools)
    data = tmp_path / "data"
    monkeypatch.setattr(cps, "QUEUE", write_json(data / "queue.json", queue_doc()))
    monkeypatch.setattr(cps, "SERIES", data / "series.json")
    monkeypatch.setattr(cps, "BEAMS", write_json(data / "beams.json", {"beams": [{"id": "B1"}, {"id": "B2"}]}))
    return root


# ---------------------------------------------------------------- validator
def test_validate_const_enum_and_type_errors():
    schema = {"type": "object", "properties": {"a": {"const": 1}, "b": {"enum": ["x"]}, "c": {"type": "integer"},
                                               "d": {"type": ["number", "null"]}}}
    assert cps.validate({"a": 2, "b": "y", "c": True, "d": 1.5}, schema) == [
        "$.a: expected 1", "$.b: 'y' not in ['x']", "$.c: expected type ['integer']"]
    assert cps.validate({"d": None}, schema) == []
    assert cps.validate([], schema) == ["$: expected type ['object']"]


def test_validate_strings_objects_and_arrays():
    schema = {"type": "object", "required": ["s", "l"], "additionalProperties": False,
              "properties": {"s": {"type": "string", "pattern": "^ok", "minLength": 4},
                             "l": {"type": "array", "minItems": 2, "items": {"type": "string"}}}}
    errs = cps.validate({"s": "no", "l": [3], "x": 1}, schema)
    assert errs == ["$.s: 'no' does not match ^ok", "$.s: shorter than 4", "$.l: fewer than 2 items",
                    "$.l[0]: expected type ['string']", "$: unexpected x"]
    assert cps.validate({}, schema) == ["$: missing s", "$: missing l"]
    assert cps.validate({"s": "okay", "l": ["a", "b"]}, schema) == []


def test_validate_follows_refs_and_array_without_items():
    schema = {"$ref": "#/$defs/row", "$defs": {"row": {"type": "array", "minItems": 1}}}
    assert cps.validate([], schema) == ["$: fewer than 1 items"]
    assert cps.validate([1, "x"], schema) == []


# ---------------------------------------------------------------- queue
def test_synthetic_queue_is_valid(tree):
    assert cps.check_queue(queue_doc()) == []


def test_queue_schema_errors_short_circuit_semantics(tree):
    q = queue_doc()
    q["items"][0]["beam"] = "B9"  # would be a semantic error
    q["formal_credit_delta"] = 1
    assert cps.check_queue(q) == ["$.formal_credit_delta: expected 0"]


def test_queue_semantic_errors(tree):
    q = queue_doc()
    q["items"].append(copy.deepcopy(q["items"][2]))
    q["items"][0]["beam"] = "B9"
    q["items"][1]["depends_on"] = ["CPQ-999"]
    q["items"][2]["history"].append(dict(q["items"][2]["history"][0]))
    errs = cps.check_queue(q)
    assert errs == ["duplicate queue ids", "CPQ-001: unknown beam B9", "CPQ-002: unknown dependency CPQ-999",
                    "CPQ-003: history keys must be strictly increasing"]


def test_queue_metrics_replay_state_at_key():
    q = queue_doc()
    early = cps.queue_metrics(q, "W1.C1.I0.S0")
    assert (early["bd_total"], early["bd_open"], early["bd_complete"], early["bd_critical_open"]) == (2, 2, 0, 2)
    assert (early["bd_ready"], early["bd_in_pr"], early["bd_blocked_or_held"]) == (1, 0, 1)
    late = cps.queue_metrics(q, "W1.C1.I1.S0")
    assert (late["bd_total"], late["bd_open"], late["bd_complete"], late["bd_critical_open"]) == (3, 2, 1, 1)
    assert late["bd_state_done"] == 1 and late["bd_state_todo"] == 1 and late["bd_in_pr"] == 1


def test_key_tuple_rejects_bad_key_with_message():
    with pytest.raises(cps.SeriesError, match=r"bad series key 'W1\.C1'; expected W<n>"):
        cps.key_tuple("W1.C1")
    assert cps.key_tuple("W10.C2.I3.S4") == (10, 2, 3, 4)


# ---------------------------------------------------------------- gate ledger / metrics
def test_gate_ledger_pass_fail_unknown():
    ledger = cps.gate_ledger(contract())
    assert [r["state"] for r in ledger["top7_to_top14"]] == ["PASS"] * 9
    states = {r["label"]: r["state"] for r in ledger["top14_to_top21"]}
    assert states["TOP14 green CONTROL"] == "UNKNOWN"
    assert states["Proof yield non-degrading, 2 pulses"] == "UNKNOWN"
    assert states["TOP14 classified"] == "FAIL" and states["TOP14 proof debt"] == "FAIL"
    assert states["Iteration chain integrity"] == "PASS"
    assert states["Recursive CONTROL handoffs"] == "FAIL"


def test_compute_metrics_on_complete_tree(tree):
    (tree / ".github" / "workflows" / "a.yml").write_text("on: push\n", encoding="utf-8")
    m = cps.compute_metrics(tree, queue_doc(), "W1.C1.I1.S0")
    assert (m["top14_gate_pass"], m["top14_gate_fail"], m["top14_gate_unknown"]) == (9, 0, 0)
    assert (m["top21_gate_pass"], m["top21_gate_fail"], m["top21_gate_unknown"]) == (2, 7, 2)
    assert m["dmaic_evolution_level"] == 2 and m["dmaic_complete_iterations"] == 4
    assert (m["coverage_rows_measured"], m["coverage_rows_total"]) == (2, 3)
    assert m["receipt_edges"] == 1
    assert (m["graph_edges_receipt"], m["graph_edges_declared"]) == (1, 2)
    assert m["zero_test_gates"] == 1
    assert m["bd_total"] == 3


def test_compute_metrics_unbound_inputs_are_null(tree):
    (tree / cps.COVERAGE).unlink()
    (tree / cps.GRAPH).unlink()
    (tree / ".github" / "workflows").rmdir()
    doc = contract()
    doc["iteration_evolution"]["current_level"] = "E9_UNKNOWN"
    write_json(tree / cps.CONTRACT, doc)
    m = cps.compute_metrics(tree, queue_doc(), "W1.C1.I0.S0")
    assert m["coverage_rows_measured"] is None and m["coverage_rows_total"] is None
    assert m["graph_edges_receipt"] is None and m["graph_edges_declared"] is None
    assert m["zero_test_gates"] is None
    assert m["dmaic_evolution_level"] is None


def test_graph_edge_without_binding_is_unbound(tree):
    (tree / cps.GRAPH).write_text("edges:\n  - {binding: RECEIPT}\n  - {from: a}\n", encoding="utf-8")
    assert cps._graph_bindings(tree) == (None, None)


def test_delta_numeric_and_binding_changes():
    assert cps.delta(None, {"a": 1}) == {}
    prev = {"a": 1, "b": None, "c": 5, "d": True, "e": 3}
    cur = {"a": 4, "b": 2, "c": None, "d": False, "e": 3, "f": None}
    assert cps.delta(prev, cur) == {"a": 3, "b": "BOUND", "c": "UNBOUND"}


# ---------------------------------------------------------------- series
def series_with(entries):
    return {"schema": "missioncontrol.code_purple.iteration_series.v1", "index": "WAVE.CYCLE.ITERATION.SUB",
            "authority_transfer": False, "entries": entries}


def entry(key, metrics, prev=None, tree="PR_HEAD"):
    return {"key": key, "closes": "SUB", "label": "closed a step", "tree": tree,
            "evidence_class": "PROVISIONAL_PR_HEAD" if tree == "PR_HEAD" else "MEASURED", "refs": [],
            "metrics": metrics, "delta": cps.delta(prev["metrics"] if prev else None, metrics),
            "prev_digest": cps.digest(prev) if prev else None}


def test_check_series_schema_error_short_circuits(tree):
    doc = series_with([])
    assert cps.check_series(doc) == ["$.entries: fewer than 1 items"]


def test_check_series_order_and_provisional_rules(tree):
    first = entry("W1.C1.I1.S0", {"x": 1}, tree=SHA)
    second = entry("W1.C1.I0.S0", {"x": 2}, prev=first)
    third = entry("W1.C1.I2.S0", {"x": 2}, prev=second, tree=SHA)
    assert cps.check_series(series_with([first, second, third])) == [
        "series keys must be strictly increasing", "W1.C1.I0.S0: only the latest entry may be PROVISIONAL_PR_HEAD"]
    third["delta"] = {"x": 7}
    assert "W1.C1.I2.S0: stored delta does not match metrics" in cps.check_series(series_with([first, second, third]))


def test_check_series_detects_broken_hash_chain(tree):
    first = entry("W1.C1.I0.S0", {"x": 1}, tree=SHA)
    second = entry("W1.C1.I1.S0", {"x": 1}, prev=first)
    assert cps.check_series(series_with([first, second])) == []
    first["label"] = "rewritten history"
    assert cps.check_series(series_with([first, second])) == [
        "W1.C1.I1.S0: prev_digest broken (append-only chain)"]


# ---------------------------------------------------------------- append / run_check
def test_append_creates_series_and_chains_entries(tree):
    first = cps.append(tree, "W1.C1.I0.S0", "SUB", "first closed step", SHA, ["ref-1"])
    assert first["prev_digest"] is None and first["delta"] == {} and first["evidence_class"] == "MEASURED"
    doc = json.loads(cps.SERIES.read_text(encoding="utf-8"))
    assert doc["schema"] == "missioncontrol.code_purple.iteration_series.v1" and len(doc["entries"]) == 1
    second = cps.append(tree, "W1.C1.I1.S0", "ITERATION", "second closed step", "PR_HEAD", [])
    assert second["evidence_class"] == "PROVISIONAL_PR_HEAD"
    assert second["prev_digest"] == cps.digest(first)
    assert second["delta"] == {"bd_total": 1, "bd_complete": 1, "bd_critical_open": -1, "bd_ready": -1,
                               "bd_in_pr": 1, "bd_state_done": 1}
    assert cps.check_series(json.loads(cps.SERIES.read_text(encoding="utf-8"))) == []


def test_append_refreshes_only_provisional_entry_with_same_key(tree):
    cps.append(tree, "W1.C1.I0.S0", "SUB", "first closed step", SHA, [])
    cps.append(tree, "W1.C1.I1.S0", "SUB", "provisional step", "PR_HEAD", [])
    cps.append(tree, "W1.C1.I1.S0", "SUB", "refreshed step", "PR_HEAD", [])
    entries = json.loads(cps.SERIES.read_text(encoding="utf-8"))["entries"]
    assert [e["label"] for e in entries] == ["first closed step", "refreshed step"]
    with pytest.raises(cps.SeriesError, match=r"^key W1\.C1\.I0\.S5 must be after W1\.C1\.I1\.S0$"):
        cps.append(tree, "W1.C1.I0.S5", "SUB", "out of order", "PR_HEAD", [])
    cps.append(tree, "W1.C1.I2.S0", "SUB", "measured step", SHA, [])
    with pytest.raises(cps.SeriesError, match="must be after"):
        cps.append(tree, "W1.C1.I2.S0", "SUB", "same key measured", "PR_HEAD", [])


def test_run_check_pass_drift_and_beyond_latest(tree):
    cps.append(tree, "W1.C1.I1.S0", "SUB", "closed iteration", SHA, [])
    assert cps.run_check(tree) == (0, [])
    write_json(tree / cps.TOPOLOGY, {"edges": []})
    code, errs = cps.run_check(tree)
    assert code == 1 and errs[0].startswith("metrics changed without a series entry: receipt_edges 1->0. Append one")


def test_run_check_history_beyond_latest_key(tree):
    cps.append(tree, "W1.C1.I0.S0", "SUB", "early closed step", SHA, [])
    code, errs = cps.run_check(tree)
    assert code == 1 and errs == ["CPQ-001: history row beyond latest series key W1.C1.I0.S0",
                                  "CPQ-003: history row beyond latest series key W1.C1.I0.S0"]


def test_run_check_incomplete_when_audit_not_computable(tree):
    cps.append(tree, "W1.C1.I1.S0", "SUB", "closed iteration", SHA, [])
    (tree / ".github" / "workflows").rmdir()
    assert cps.run_check(tree) == (2, ["INCOMPLETE: audit or graph bindings not computable on this tree"])


def test_run_check_reports_structural_errors_first(tree):
    write_json(cps.SERIES, series_with([]))
    assert cps.run_check(tree) == (1, ["$.entries: fewer than 1 items"])


# ---------------------------------------------------------------- CLI
def test_main_append_show_and_check(tree, monkeypatch, capsys):
    assert cps.main(["append", "--key", "W1.C1.I1.S0", "--closes", "ITERATION", "--label", "closed iteration",
                     "--root", str(tree), "--tree", SHA, "--ref", "r1", "--ref", "r2"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"key": "W1.C1.I1.S0", "delta": {}}
    assert json.loads(cps.SERIES.read_text(encoding="utf-8"))["entries"][0]["refs"] == ["r1", "r2"]
    assert cps.main(["show", "--key", "W1.C1.I0.S0", "--root", str(tree)]) == 0
    assert json.loads(capsys.readouterr().out)["bd_total"] == 2
    # `check` always measures the module ROOT; point it at the synthetic tree.
    real_run_check = cps.run_check
    monkeypatch.setattr(cps, "run_check", lambda: real_run_check(tree))
    assert cps.main(["check"]) == 0
    assert capsys.readouterr().out.strip() == "CODE_PURPLE_SERIES PASS latest=W1.C1.I1.S0"


def test_main_check_prefixes_fail_and_incomplete(tree, monkeypatch, capsys):
    monkeypatch.setattr(cps, "run_check", lambda: (1, ["one", "two"]))
    assert cps.main(["check"]) == 1
    assert capsys.readouterr().out.splitlines() == ["FAIL: one", "FAIL: two"]
    monkeypatch.setattr(cps, "run_check", lambda: (2, ["not computable"]))
    assert cps.main(["check"]) == 2
    assert capsys.readouterr().out.splitlines() == ["INCOMPLETE: not computable"]


def test_main_append_out_of_order_reports_fail(tree, capsys):
    cps.append(tree, "W1.C1.I1.S0", "SUB", "closed iteration", SHA, [])
    capsys.readouterr()
    assert cps.main(["append", "--key", "W1.C1.I0.S0", "--closes", "SUB", "--label", "too early",
                     "--root", str(tree)]) == 1
    assert capsys.readouterr().out.strip() == "FAIL: key W1.C1.I0.S0 must be after W1.C1.I1.S0"


def test_main_rejects_unknown_closes_level(tree, capsys):
    with pytest.raises(SystemExit) as exc:
        cps.main(["append", "--key", "W1.C1.I0.S0", "--closes", "DAY", "--label", "x", "--root", str(tree)])
    assert exc.value.code == 2
    assert "invalid choice: 'DAY'" in capsys.readouterr().err
