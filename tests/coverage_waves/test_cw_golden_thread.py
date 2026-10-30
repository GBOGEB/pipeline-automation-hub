"""Coverage-wave behavioural tests for mission-control/golden-thread/golden_thread.py.

Targets what the in-directory golden-thread tests leave uncovered: event shape
validation errors, ledger verification failure modes, projection branches for
every lineage event type, boundary selection by SHA/timestamp, root expansion
and the CLI entry point (including the FAIL path).
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GT_DIR = REPO_ROOT / "mission-control" / "golden-thread"
if str(GT_DIR) not in sys.path:
    sys.path.insert(0, str(GT_DIR))

_spec = importlib.util.spec_from_file_location("cw_golden_thread_main", GT_DIR / "golden_thread.py")
gt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gt)


def ev(event_id, event_type, subject_ref, *, occurred="2026-09-17T01:00:00Z", recorded=None,
       payload=None, from_ref=None, to_ref=None, **extra):
    e = {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred,
        "recorded_at": recorded or occurred,
        "actor": "cw.test",
        "subject_ref": subject_ref,
        "authority_domain": "GBOGEB/cw",
        "evidence_refs": [],
        "non_compensating_preserved": True,
        "payload": payload or {},
    }
    if from_ref is not None:
        e["from_ref"] = from_ref
    if to_ref is not None:
        e["to_ref"] = to_ref
    e.update(extra)
    return e


def sealed(events):
    return gt.seal({"events": events})


def lineage_ledger():
    return sealed([
        ev("E1", "OBSERVED", "occ:1", occurred="2026-09-17T01:00:00Z", evidence_refs=["ev:a", "ev:a"],
           payload={"source_sha": "abcdef1"}),
        ev("E2", "ROOT_CREATED", "root:R", occurred="2026-09-17T02:00:00Z"),
        ev("E3", "ATTACHED_TO_ROOT", "occ:1", from_ref="occ:1", to_ref="root:R",
           occurred="2026-09-17T03:00:00Z"),
        ev("E4", "WORK_ORDER_CREATED", "wo:1", from_ref="occ:1", occurred="2026-09-17T04:00:00Z",
           source_sha="1234567"),
        ev("E5", "EVIDENCE_ADDED", "evd:1", to_ref="wo:1", payload={"evidence": {"kind": "log"}},
           occurred="2026-09-17T05:00:00Z"),
        ev("E6", "CAMPAIGN_ATTACHED", "wo:1", to_ref="camp:C", occurred="2026-09-17T06:00:00Z"),
        ev("E7", "MERGED_INTO", "root:R", from_ref="root:OLD", to_ref="root:R",
           occurred="2026-09-17T07:00:00Z"),
        ev("E8", "SPLIT_FROM", "root:X", from_ref="root:X", to_ref="root:Y",
           occurred="2026-09-17T08:00:00Z"),
        ev("E9", "WORK_ORDER_CREATED", "wo:orphan", occurred="2026-09-17T09:00:00Z"),
        ev("E10", "WORK_ORDER_CREATED", "wo:ghost", from_ref="nowhere", occurred="2026-09-17T10:00:00Z"),
        ev("E11", "EVIDENCE_ADDED", "evd:loose", occurred="2026-09-17T11:00:00Z"),
        ev("E12", "CAMPAIGN_ATTACHED", "occ:other", from_ref="occ:other", to_ref="camp:D",
           occurred="2026-09-17T12:00:00Z"),
    ])


# ------------------------------------------------------------------ primitives


def test_ts_normalises_zulu_and_offsets_to_utc():
    assert gt.ts("2026-09-17T03:00:00+02:00").isoformat() == "2026-09-17T01:00:00+00:00"
    assert gt._utc("2026-09-17T01:00:00Z") == "2026-09-17T01:00:00Z"


def test_ts_rejects_garbage_and_naive_values():
    with pytest.raises(gt.GoldenThreadError, match="invalid timestamp nope"):
        gt.ts("nope")
    with pytest.raises(gt.GoldenThreadError, match="timestamp must be timezone-aware: 2026-09-17T01:00:00"):
        gt.ts("2026-09-17T01:00:00")


def test_load_accepts_object_and_rejects_list(tmp_path):
    ok = tmp_path / "ok.json"
    ok.write_text('{"a": 1}', encoding="utf-8")
    assert gt.load(ok) == {"a": 1}
    bad = tmp_path / "bad.json"
    bad.write_text("[1]", encoding="utf-8")
    with pytest.raises(gt.GoldenThreadError, match="ledger must be object"):
        gt.load(bad)


def test_dump_writes_file_or_stdout(tmp_path, capsys):
    out = tmp_path / "o.json"
    gt.dump({"b": 1, "a": "é"}, out)
    assert out.read_text(encoding="utf-8") == '{\n  "a": "é",\n  "b": 1\n}\n'
    gt.dump({"x": 1})
    assert capsys.readouterr().out == '{\n  "x": 1\n}\n'


def test_event_digest_ignores_its_own_digest_field():
    d = gt.event_digest({"a": 1})
    assert gt.event_digest({"a": 1, "this_event_digest": "whatever"}) == d
    assert d.startswith("sha256:") and len(d) == 71


# ------------------------------------------------------------------ shape checks


@pytest.mark.parametrize("mutate,message", [
    (lambda e: e.pop("event_type"), "event E1 missing event_type"),
    (lambda e: e.update(event_type="NOPE"), "bad event_type NOPE"),
    (lambda e: e.pop("occurred_at"), "event E1 missing occurred_at"),
    (lambda e: e.update(recorded_at="bogus"), "invalid timestamp bogus"),
    (lambda e: e.update(actor=5), "actor must be string"),
    (lambda e: e.update(subject_ref=None), "subject_ref must be string"),
    (lambda e: e.update(evidence_refs="x"), "evidence_refs must be list"),
    (lambda e: e.update(non_compensating_preserved="yes"), "non_compensating_preserved must be bool"),
])
def test_seal_rejects_malformed_events(mutate, message):
    e = ev("E1", "OBSERVED", "occ:1")
    mutate(e)
    with pytest.raises(gt.GoldenThreadError, match=message):
        gt.seal({"events": [e]})


def test_missing_event_id_reports_question_mark():
    e = ev("E1", "OBSERVED", "occ:1")
    del e["event_id"]
    with pytest.raises(gt.GoldenThreadError, match=r"event \? missing event_id"):
        gt.seal({"events": [e]})


def test_check_shape_requires_projection_schema_version_one():
    with pytest.raises(gt.GoldenThreadError, match="projection_schema_version must be 1"):
        gt.check_shape(ev("E1", "OBSERVED", "occ:1"))


def test_bootstrap_requires_reconstruction_fields_and_valid_timestamps():
    e = ev("E1", "BOOTSTRAP_RECONSTRUCTED", "occ:1", observed_source_timestamp="2026-01-01T00:00:00Z",
           reconstruction_timestamp="2026-02-01T00:00:00Z")
    with pytest.raises(gt.GoldenThreadError, match="event E1 missing reconstruction_method"):
        gt.seal({"events": [copy.deepcopy(e)]})
    e["reconstruction_method"] = "git-log"
    e["observed_source_timestamp"] = "2026-01-01T00:00:00"
    with pytest.raises(gt.GoldenThreadError, match="timezone-aware"):
        gt.seal({"events": [e]})


def test_seal_sets_control_defaults_and_empty_head_is_genesis():
    assert gt.seal({}) == {"schema": gt.LEDGER_SCHEMA, "projection_schema_version": 1,
                           "authority_transfer": False, "head_event_digest": gt.GENESIS}


# ------------------------------------------------------------------ verify failures


def test_verify_rejects_control_fields():
    good = sealed([ev("E1", "OBSERVED", "occ:1")])
    for key, value in (("schema", "x"), ("projection_schema_version", 2), ("authority_transfer", True)):
        bad = copy.deepcopy(good)
        bad[key] = value
        with pytest.raises(gt.GoldenThreadError, match="ledger control fields invalid"):
            gt.verify(bad)


def test_verify_rejects_non_list_events():
    led = sealed([])
    led["events"] = {}
    with pytest.raises(gt.GoldenThreadError, match="events must be list"):
        gt.verify(led)


def test_verify_detects_seq_duplicate_chain_digest_and_head_tampering():
    good = sealed([ev("E1", "OBSERVED", "occ:1"), ev("E2", "OBSERVED", "occ:2")])
    assert gt.verify(good)["event_count"] == 2

    bad = copy.deepcopy(good)
    bad["events"][1]["seq"] = 5
    with pytest.raises(gt.GoldenThreadError, match="seq mismatch E2"):
        gt.verify(bad)

    bad = copy.deepcopy(good)
    bad["events"][1]["event_id"] = "E1"
    with pytest.raises(gt.GoldenThreadError, match="duplicate event_id E1"):
        gt.verify(bad)

    bad = copy.deepcopy(good)
    bad["events"][1]["previous_event_digest"] = "sha256:00"
    with pytest.raises(gt.GoldenThreadError, match="chain mismatch E2"):
        gt.verify(bad)

    bad = copy.deepcopy(good)
    bad["events"][0]["actor"] = "tamperer"
    with pytest.raises(gt.GoldenThreadError, match="digest mismatch E1"):
        gt.verify(bad)

    bad = copy.deepcopy(good)
    bad["head_event_digest"] = "sha256:00"
    with pytest.raises(gt.GoldenThreadError, match="head digest mismatch"):
        gt.verify(bad)


# ------------------------------------------------------------------ projection branches


def test_rebuild_projects_lineage_edges_and_buckets():
    p = gt.rebuild(lineage_ledger())
    assert p["occurrences"]["occ:1"]["evidence_refs"] == ["ev:a"]
    assert p["occurrences"]["occ:1"]["root_ref"] == "root:R"
    assert p["occurrences"]["occ:1"]["work_order_refs"] == ["wo:1"]
    assert p["roots"]["root:R"]["occurrence_refs"] == ["occ:1"]
    assert p["work_orders"]["wo:1"]["parent_ref"] == "occ:1"
    assert p["work_orders"]["wo:1"]["evidence_refs"] == ["evd:1"]
    assert p["work_orders"]["wo:orphan"]["parent_ref"] is None
    assert p["evidence"]["evd:1"]["kind"] == "log"
    assert "evd:loose" in p["evidence"]
    assert p["campaigns"]["camp:C"]["member_refs"] == ["wo:1"]
    assert p["campaigns"]["camp:D"]["member_refs"] == ["occ:other"]
    types = [e["type"] for e in p["lineage_edges"]]
    assert types == ["ATTACHED_TO_ROOT", "WORK_ORDER_CREATED", "EVIDENCE_ADDED", "CAMPAIGN_ATTACHED",
                     "MERGED_INTO", "SPLIT_FROM", "WORK_ORDER_CREATED", "WORK_ORDER_CREATED",
                     "EVIDENCE_ADDED", "CAMPAIGN_ATTACHED"]
    assert p["metrics"]["orphan_occurrence_count"] == 0
    assert p["metrics"]["lineage_retention_coverage"] == 1.0
    assert p["boundary"] == "CURRENT"


def test_rebuild_empty_ledger_has_genesis_head_and_full_coverage():
    p = gt.rebuild(sealed([]))
    assert p["head_event_digest"] == gt.GENESIS
    assert p["metrics"]["event_count"] == 0
    assert p["metrics"]["lineage_retention_coverage"] == 1.0


@pytest.mark.parametrize("etype", ["ATTACHED_TO_ROOT", "MERGED_INTO", "SPLIT_FROM", "SUPERSEDED_BY"])
def test_edge_events_require_from_and_to(etype):
    led = sealed([ev("E1", etype, "x", from_ref="a")])
    with pytest.raises(gt.GoldenThreadError, match=f"{etype} requires from_ref/to_ref"):
        gt.rebuild(led)


def test_state_transitions_and_gates():
    led = sealed([
        ev("E1", "OBSERVED", "occ:1", payload={"object_type": "root"}),
        ev("E2", "STATE_CHANGED", "occ:1", payload={"state": "BLOCKED"}),
        ev("E3", "AUTHORITY_BOUNDARY_ASSERTED", "occ:1", payload={"authority_domain": "GBOGEB/other"}),
        ev("E4", "AUTHORITY_BOUNDARY_ASSERTED", "missing"),
        ev("E5", "NON_COMPENSATING_GATE_SET", "occ:1",
           payload={"blocking_predicate": "bp", "reentry_trigger": "rt"}),
        ev("E6", "NON_COMPENSATING_GATE_SET", "missing"),
        ev("E7", "CONTROL_PROMOTED", "occ:2"),
        ev("E8", "INVALIDATED", "occ:3"),
        ev("E9", "REOPENED", "occ:3"),
        ev("E10", "REOPENED", "wo:z", payload={"object_type": "work_order", "state": "PAUSED"}),
        ev("E11", "RETIREMENT_CANDIDATE", "occ:2", payload={"victory_predicate": "vp"}),
        ev("E12", "CLASSIFIED", "occ:new",
           payload={"object_type": "occurrence", "routing_disposition": "INVALIDATED",
                    "historian_state": "UNKNOWN_NEEDS_READER", "note": "n"}),
        ev("E13", "CLASSIFIED", "occ:2", payload={"bd_state": "UNKNOWN_NEEDS_READER"}),
        ev("E14", "SUPERSEDED_BY", "occ:2", from_ref="occ:2", to_ref="occ:3"),
    ])
    p = gt.rebuild(led)
    r = p["roots"]["occ:1"]
    assert r["state"] == "BLOCKED"
    assert r["authority_domain"] == "GBOGEB/other"
    assert (r["non_compensating"], r["blocking_predicate"], r["reentry_trigger"]) == (True, "bp", "rt")
    o2 = p["occurrences"]["occ:2"]
    assert o2["state"] == "CONTROL"
    assert (o2["retirement_candidate"], o2["retirement_withheld"], o2["retirement_predicate"]) == (True, True, "vp")
    assert p["occurrences"]["occ:3"]["state"] == "ACTIVE"
    assert p["work_orders"]["wo:z"]["state"] == "PAUSED"
    new = p["occurrences"]["occ:new"]
    assert new["classification_history"] == [{"event_id": "E12", "routing_disposition": "INVALIDATED",
                                              "historian_state": "UNKNOWN_NEEDS_READER", "note": "n"}]
    assert "missing" not in p["occurrences"] and "missing" not in p["roots"]
    m = p["metrics"]
    # occ:2 and occ:3 have no root and no terminal disposition; occ:new is terminal.
    assert m["orphan_occurrences"] == ["occ:2", "occ:3"]
    assert m["unknown_needs_reader"] == ["occ:2", "occ:new"]
    assert m["lineage_retention_coverage"] == round(1 / 3, 6)
    assert p["events_applied"][-1] == "E14"


def test_bootstrap_event_records_reconstruction_metadata():
    led = sealed([ev("E1", "BOOTSTRAP_RECONSTRUCTED", "occ:1", observed_source_timestamp="2026-01-01T00:00:00Z",
                     reconstruction_timestamp="2026-02-01T00:00:00Z", reconstruction_method="git-log")])
    o = gt.rebuild(led)["occurrences"]["occ:1"]
    assert o["bootstrap"] == {"observed_source_timestamp": "2026-01-01T00:00:00Z",
                              "reconstruction_timestamp": "2026-02-01T00:00:00Z",
                              "reconstruction_method": "git-log"}
    assert o["first_event_id"] == o["last_event_id"] == "E1"


# ------------------------------------------------------------------ boundary selection


def test_select_by_event_id_sha_and_timestamp():
    led = lineage_ledger()
    assert [e["event_id"] for e in gt.select(led, "E2")] == ["E1", "E2"]
    assert [e["event_id"] for e in gt.select(led, "abcdef1")] == ["E1"]
    assert [e["event_id"] for e in gt.select(led, "1234567")] == ["E1", "E2", "E3", "E4"]
    assert len(gt.select(led, "2026-09-17T03:30:00Z")) == 3
    assert gt.select(led, None) is led["events"]


def test_select_unknown_sha_raises():
    with pytest.raises(gt.GoldenThreadError, match="no event binds source SHA deadbeef"):
        gt.select(lineage_ledger(), "deadbeef")


def test_rebuild_as_of_labels_boundary():
    led = lineage_ledger()
    p = gt.rebuild(led, "E3")
    assert p["boundary"] == "E3"
    assert p["metrics"]["event_count"] == 3
    assert p["head_event_digest"] == led["events"][2]["this_event_digest"]


# ------------------------------------------------------------------ expand / diff


def test_expand_root_collects_reachable_lineage():
    out = gt.expand_root(lineage_ledger(), "root:R")
    assert list(out["occurrences"]) == ["occ:1"]
    assert list(out["work_orders"]) == ["wo:1"]
    assert list(out["evidence"]) == ["evd:1"]
    assert list(out["campaigns"]) == ["camp:C"]
    assert [e["event_id"] for e in out["lineage_edges"]] == ["E3", "E4", "E5", "E6", "E7"]
    assert out["recovery_metrics"] == {"occurrence_recovery_count": 1, "evidence_recovery_count": 1,
                                       "root_recovery_count": 1, "lineage_edge_count": 5}
    assert out["boundary"] == "CURRENT"
    body = {k: v for k, v in out.items() if k != "expansion_digest"}
    assert out["expansion_digest"] == gt.digest(body)


def test_expand_root_unknown_root_raises():
    with pytest.raises(gt.GoldenThreadError, match="root not found: root:none"):
        gt.expand_root(lineage_ledger(), "root:none")


def test_diff_boundaries_reports_added_events_and_metric_delta():
    d = gt.diff_boundaries(lineage_ledger(), "E1", "E3")
    assert [x["event_id"] for x in d["events_added"]] == ["E2", "E3"]
    assert d["events_added"][1]["from_ref"] == "occ:1"
    assert d["metric_delta"]["root_count"] == 1
    assert d["metric_delta"]["orphan_occurrence_count"] == -1


def test_diff_known_at_rejects_reverse_windows():
    with pytest.raises(gt.GoldenThreadError, match="known-at windows must be chronological"):
        gt.diff_known_at(lineage_ledger(), "2026-09-18T00:00:00Z", "2026-09-17T00:00:00Z")


# ------------------------------------------------------------------ CLI


def _write(tmp_path, name, value):
    p = tmp_path / name
    p.write_text(json.dumps(value), encoding="utf-8")
    return p


def test_main_seal_then_verify_via_files(tmp_path):
    raw = _write(tmp_path, "raw.json", {"events": [ev("E1", "OBSERVED", "occ:1")]})
    out = tmp_path / "sealed.json"
    assert gt.main(["seal", str(raw), "--out", str(out)]) == 0
    sealed_doc = json.loads(out.read_text(encoding="utf-8"))
    assert sealed_doc["events"][0]["seq"] == 1
    vout = tmp_path / "v.json"
    assert gt.main(["verify", str(out), "--out", str(vout)]) == 0
    assert json.loads(vout.read_text(encoding="utf-8"))["status"] == "PASS"


@pytest.mark.parametrize("argv_tail,key,expected", [
    (["rebuild-current"], "boundary", "CURRENT"),
    (["rebuild-as-of", "E2"], "boundary", "E2"),
    (["expand-root", "root:R", "--as-of", "E3"], "boundary", "E3"),
    (["diff", "E1", "E2"], "schema", "missioncontrol.golden_thread_diff.v1"),
    (["rebuild-known-at", "2026-09-17T02:30:00Z", "--occurred-by", "2026-09-17T02:00:00Z"],
     "boundary", "BITEMPORAL_READ_ONLY"),
    (["diff-known-at", "2026-09-17T01:00:00Z", "2026-09-17T03:00:00Z"],
     "schema", "missioncontrol.golden_thread_known_diff.v1"),
])
def test_main_subcommands_write_stdout(tmp_path, capsys, monkeypatch, argv_tail, key, expected):
    led = _write(tmp_path, "l.json", lineage_ledger())
    argv = [argv_tail[0], str(led)] + argv_tail[1:]
    monkeypatch.setattr(sys, "argv", ["golden_thread.py"] + argv)
    assert gt.main() == 0
    assert json.loads(capsys.readouterr().out)[key] == expected


def test_main_reports_fail_and_exit_2(tmp_path, capsys):
    bad = _write(tmp_path, "l.json", ["not", "object"])
    assert gt.main(["verify", str(bad)]) == 2
    assert capsys.readouterr().err == "FAIL: ledger must be object\n"
