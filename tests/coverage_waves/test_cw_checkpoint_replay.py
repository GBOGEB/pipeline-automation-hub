"""Coverage-wave behavioural tests for mission-control/golden-thread/checkpoint_replay.py.

Uses a synthetic sealed ledger (built in-test) so that every manifest branch
(source SHA binding, gate manifest rows, root attachment) is exercised, and
drives each checkpoint verification failure plus the CLI.
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

_spec = importlib.util.spec_from_file_location("cw_checkpoint_replay", GT_DIR / "checkpoint_replay.py")
cpr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpr)
gt = cpr.gt
GTE = gt.GoldenThreadError


def _event(i, event_type, subject, **extra):
    e = {
        "event_id": f"EV-{i:04d}",
        "event_type": event_type,
        "occurred_at": f"2026-09-01T00:{i:02d}:00Z",
        "recorded_at": f"2026-09-01T00:{i:02d}:30Z",
        "actor": "cw.tester",
        "subject_ref": subject,
        "authority_domain": "GBOGEB/cw",
        "evidence_refs": [f"ref-{i}"],
        "non_compensating_preserved": True,
        "payload": {},
    }
    e.update(extra)
    return e


def make_ledger(n=8):
    events = [
        _event(1, "OBSERVED", "occ-1", source_sha="abcdef1"),
        _event(2, "ROOT_CREATED", "root-1"),
        _event(3, "ATTACHED_TO_ROOT", "occ-1", from_ref="occ-1", to_ref="root-1"),
        _event(
            4,
            "NON_COMPENSATING_GATE_SET",
            "root-1",
            payload={"blocking_predicate": "tests_green", "reentry_trigger": "red"},
        ),
    ]
    for i in range(5, n + 1):
        events.append(_event(i, "OBSERVED", f"occ-{i}", source_snapshot_digest=gt.digest({"i": i})))
    return gt.seal({"events": events})


@pytest.fixture()
def ledger():
    return make_ledger()


def reseal(cp):
    cp = copy.deepcopy(cp)
    cp.pop("checkpoint_digest", None)
    cp["checkpoint_digest"] = gt.digest(cp)
    return cp


# ---------------------------------------------------------------- manifests


def test_source_manifest_carries_optional_source_bindings(ledger):
    manifest = cpr._source_manifest(ledger["events"])
    assert manifest[0] == {
        "event_id": "EV-0001",
        "event_digest": ledger["events"][0]["this_event_digest"],
        "source_sha": "abcdef1",
    }
    assert set(manifest[1]) == {"event_id", "event_digest"}
    assert manifest[4]["source_snapshot_digest"] == gt.digest({"i": 5})


def test_gate_and_authority_manifests_from_projection(ledger):
    projection = gt.rebuild(ledger)
    gates = cpr._gate_manifest(projection)
    assert gates == [
        {
            "family": "roots",
            "ref": "root-1",
            "non_compensating": True,
            "blocking_predicate": "tests_green",
            "reentry_trigger": "red",
        }
    ]
    authority = cpr._authority_manifest(projection)
    assert [(r["family"], r["ref"]) for r in authority] == sorted((r["family"], r["ref"]) for r in authority)
    assert {"family": "occurrences", "ref": "occ-1", "authority_domain": "GBOGEB/cw", "root_authority": None} in authority


def test_finalize_projection_metrics_and_empty_head():
    projection = gt.projection()
    out = cpr._finalize_projection(projection, [], None)
    assert out["boundary"] == "CURRENT"
    assert out["head_event_digest"] == gt.GENESIS
    assert out["metrics"]["lineage_retention_coverage"] == 1.0
    assert out["projection_digest"] == cpr._projection_digest(out)


def test_finalize_projection_counts_orphans_and_unknown(ledger):
    projection = gt.projection()
    for e in ledger["events"]:
        gt.apply(projection, e)
    projection["occurrences"]["occ-5"]["historian_state"] = "UNKNOWN_NEEDS_READER"
    projection["occurrences"]["occ-6"]["routing_disposition"] = "EVIDENCE_ONLY"
    out = cpr._finalize_projection(projection, ledger["events"], "EV-0008")
    m = out["metrics"]
    # occ-1 attached to root; occ-6 terminal disposition; occ-5,7,8 orphan.
    assert m["orphan_occurrences"] == ["occ-5", "occ-7", "occ-8"]
    assert m["unknown_needs_reader"] == ["occ-5"]
    assert m["lineage_retention_coverage"] == round(2 / 5, 6)
    assert out["boundary"] == "EV-0008"


# ---------------------------------------------------------------- create


def test_create_checkpoint_binds_ledger_state(ledger):
    cp = cpr.create_checkpoint(ledger, "EV-0004", "CP-4", created_at="2026-09-02T00:00:00Z")
    assert cp["through_event_seq"] == 4
    assert cp["through_event_id"] == "EV-0004"
    assert cp["created_at"] == "2026-09-02T00:00:00Z"
    assert cp["projection_snapshot"]["events_applied"][-1] == "EV-0004"
    assert cp["gate_digest"] == gt.digest(cpr._gate_manifest(cp["projection_snapshot"]))
    assert cpr.verify_checkpoint(ledger, cp)["status"] == "PASS"


def test_create_checkpoint_default_created_at_is_utc_z(ledger):
    cp = cpr.create_checkpoint(ledger, None, "CP-now")
    assert cp["created_at"].endswith("Z")
    assert "+00:00" not in cp["created_at"]
    assert cp["through_event_seq"] == len(ledger["events"])


def test_create_checkpoint_rejects_empty_boundary(ledger):
    with pytest.raises(GTE, match="^checkpoint boundary resolves to no events$"):
        cpr.create_checkpoint(ledger, "2020-01-01T00:00:00Z", "CP-0")


# ---------------------------------------------------------------- verify failures


@pytest.fixture()
def cp(ledger):
    return cpr.create_checkpoint(ledger, "EV-0005", "CP-5", created_at="2026-09-02T00:00:00Z")


def test_verify_rejects_schema(ledger, cp):
    cp["schema"] = "x"
    with pytest.raises(GTE, match="^checkpoint schema mismatch$"):
        cpr.verify_checkpoint(ledger, cp)


def test_verify_rejects_authority_transfer(ledger, cp):
    cp["authority_transfer"] = True
    with pytest.raises(GTE, match="authority_transfer must remain false"):
        cpr.verify_checkpoint(ledger, cp)


def test_verify_rejects_digest(ledger, cp):
    cp["created_at"] = "2026-09-03T00:00:00Z"
    with pytest.raises(GTE, match="^checkpoint digest mismatch$"):
        cpr.verify_checkpoint(ledger, cp)


def test_verify_rejects_unknown_through_event(ledger, cp):
    cp["through_event_id"] = "EV-9999"
    with pytest.raises(GTE, match="through_event_id not unique in ledger"):
        cpr.verify_checkpoint(ledger, reseal(cp))


def test_verify_rejects_seq_mismatch(ledger, cp):
    cp["through_event_seq"] = 4
    with pytest.raises(GTE, match="through_event_seq mismatch"):
        cpr.verify_checkpoint(ledger, reseal(cp))


def test_verify_rejects_through_digest_mismatch(ledger, cp):
    cp["through_event_digest"] = "sha256:" + "0" * 64
    with pytest.raises(GTE, match="through_event_digest mismatch"):
        cpr.verify_checkpoint(ledger, reseal(cp))


def test_verify_rejects_missing_snapshot(ledger, cp):
    cp["projection_snapshot"] = None
    with pytest.raises(GTE, match="projection_snapshot missing"):
        cpr.verify_checkpoint(ledger, reseal(cp))


def test_verify_rejects_projection_binding(ledger, cp):
    cp["projection_digest"] = "sha256:" + "1" * 64
    with pytest.raises(GTE, match="projection digest binding mismatch"):
        cpr.verify_checkpoint(ledger, reseal(cp))


def test_verify_rejects_tampered_snapshot(ledger, cp):
    cp["projection_snapshot"]["occurrences"]["occ-1"]["title"] = "injected"
    with pytest.raises(GTE, match="projection snapshot tampered"):
        cpr.verify_checkpoint(ledger, reseal(cp))


def _rebind_snapshot(cp):
    snap = cp["projection_snapshot"]
    snap["projection_digest"] = cpr._projection_digest(snap)
    cp["projection_digest"] = snap["projection_digest"]
    return reseal(cp)


def test_verify_rejects_snapshot_not_terminating_at_through(ledger, cp):
    cp["projection_snapshot"]["events_applied"] = cp["projection_snapshot"]["events_applied"][:-1]
    with pytest.raises(GTE, match="does not terminate at through_event_id"):
        cpr.verify_checkpoint(ledger, _rebind_snapshot(cp))


def test_verify_rejects_empty_events_applied(ledger, cp):
    cp["projection_snapshot"]["events_applied"] = []
    with pytest.raises(GTE, match="does not terminate at through_event_id"):
        cpr.verify_checkpoint(ledger, _rebind_snapshot(cp))


def test_verify_rejects_source_manifest(ledger, cp):
    cp["source_manifest_digest"] = "sha256:" + "2" * 64
    with pytest.raises(GTE, match="source manifest digest mismatch"):
        cpr.verify_checkpoint(ledger, reseal(cp))


def test_verify_rejects_authority_manifest(ledger, cp):
    cp["projection_snapshot"]["occurrences"]["occ-1"]["root_authority"] = "someone"
    with pytest.raises(GTE, match="checkpoint authority digest mismatch"):
        cpr.verify_checkpoint(ledger, _rebind_snapshot(cp))


def test_verify_rejects_gate_manifest(ledger, cp):
    cp["projection_snapshot"]["roots"]["root-1"]["reentry_trigger"] = "changed"
    with pytest.raises(GTE, match="checkpoint gate digest mismatch"):
        cpr.verify_checkpoint(ledger, _rebind_snapshot(cp))


# ---------------------------------------------------------------- replay


def test_replay_from_checkpoint_matches_genesis_rebuild(ledger, cp):
    replayed = cpr.replay_from_checkpoint(ledger, cp, "EV-0007")
    assert replayed["projection_digest"] == gt.rebuild(ledger, "EV-0007")["projection_digest"]
    eq = cpr.verify_replay_equivalence(ledger, cp)
    assert eq["status"] == "PASS"
    assert eq["tail_event_count"] == 3
    assert eq["target_boundary"] == "CURRENT"


def test_replay_rejects_boundary_before_checkpoint(ledger, cp):
    with pytest.raises(GTE, match="predates or excludes checkpoint"):
        cpr.replay_from_checkpoint(ledger, cp, "EV-0003")


# ---------------------------------------------------------------- CLI


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_main_create_verify_replay_equivalence(tmp_path, ledger, capsys):
    lp = _write(tmp_path / "ledger.json", ledger)
    cpp = tmp_path / "cp.json"
    assert cpr.main(["create", str(lp), "EV-0004", "CP-4", "--created-at", "2026-09-02T00:00:00Z", "--out", str(cpp)]) == 0
    created = json.loads(cpp.read_text(encoding="utf-8"))
    assert created["checkpoint_id"] == "CP-4"
    assert created["created_at"] == "2026-09-02T00:00:00Z"

    assert cpr.main(["verify", str(lp), str(cpp)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"

    rp = tmp_path / "replay.json"
    assert cpr.main(["replay", str(lp), str(cpp), "--as-of", "EV-0006", "--out", str(rp)]) == 0
    replay = json.loads(rp.read_text(encoding="utf-8"))
    assert replay["boundary"] == "EV-0006"
    assert replay["events_applied"][-1] == "EV-0006"

    assert cpr.main(["verify-equivalence", str(lp), str(cpp), "--as-of", "EV-0006"]) == 0
    eq = json.loads(capsys.readouterr().out)
    assert eq["status"] == "PASS"
    assert eq["tail_event_count"] == 2


def test_main_create_to_stdout_and_replay_to_stdout(tmp_path, ledger, capsys):
    lp = _write(tmp_path / "ledger.json", ledger)
    assert cpr.main(["create", str(lp), "EV-0002", "CP-2", "--created-at", "2026-09-02T00:00:00Z"]) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["through_event_id"] == "EV-0002"
    cpp = _write(tmp_path / "cp.json", created)
    assert cpr.main(["replay", str(lp), str(cpp)]) == 0
    assert json.loads(capsys.readouterr().out)["boundary"] == "CURRENT"


def test_main_returns_2_on_golden_thread_error(tmp_path, ledger, capsys, monkeypatch):
    lp = _write(tmp_path / "ledger.json", ledger)
    cp = cpr.create_checkpoint(ledger, "EV-0004", "CP-4", created_at="2026-09-02T00:00:00Z")
    cp["schema"] = "bogus"
    cpp = _write(tmp_path / "cp.json", cp)
    monkeypatch.setattr(sys, "argv", ["checkpoint_replay.py", "verify", str(lp), str(cpp)])
    assert cpr.main() == 2
    assert capsys.readouterr().err.strip() == "FAIL: checkpoint schema mismatch"


def test_main_returns_2_when_replay_boundary_predates(tmp_path, ledger, capsys):
    lp = _write(tmp_path / "ledger.json", ledger)
    cpp = _write(tmp_path / "cp.json", cpr.create_checkpoint(ledger, "EV-0005", "CP-5", created_at="2026-09-02T00:00:00Z"))
    assert cpr.main(["verify-equivalence", str(lp), str(cpp), "--as-of", "EV-0002"]) == 2
    assert "predates or excludes checkpoint" in capsys.readouterr().err
