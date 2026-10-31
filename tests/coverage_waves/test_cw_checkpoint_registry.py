"""Coverage-wave behavioural tests for mission-control/golden-thread/checkpoint_registry.py.

Exercises cadence-policy validation, every registry verification failure,
cadence/selection edge cases and the CLI on a synthetic sealed ledger.
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

_spec = importlib.util.spec_from_file_location("cw_checkpoint_registry", GT_DIR / "checkpoint_registry.py")
cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cr)
gt = cr.gt
cpr = cr.cpr
CRE = cr.CheckpointRegistryError


def _event(i, subject=None):
    return {
        "event_id": f"EV-{i:04d}",
        "event_type": "OBSERVED",
        "occurred_at": f"2026-09-01T00:{i:02d}:00Z",
        "recorded_at": f"2026-09-01T00:{i:02d}:30Z",
        "actor": "cw.tester",
        "subject_ref": subject or f"occ-{i}",
        "authority_domain": "GBOGEB/cw",
        "evidence_refs": [],
        "non_compensating_preserved": True,
        "payload": {},
    }


def make_ledger(n=10, first_subject=None):
    events = [_event(i) for i in range(1, n + 1)]
    if first_subject:
        events[0]["subject_ref"] = first_subject
    return gt.seal({"events": events})


@pytest.fixture()
def ledger():
    return make_ledger()


@pytest.fixture()
def policy():
    return cr.cadence_policy(every_n_events=3)


def _cp(ledger, boundary, cid):
    return cpr.create_checkpoint(ledger, boundary, cid, created_at="2026-09-02T00:00:00Z")


@pytest.fixture()
def populated(ledger, policy):
    reg = cr.empty_registry(ledger, policy)
    reg, _ = cr.register_checkpoint(reg, ledger, policy, _cp(ledger, "EV-0003", "CP-3"), trigger="GENESIS")
    reg, _ = cr.register_checkpoint(reg, ledger, policy, _cp(ledger, "EV-0006", "CP-6"), trigger="EVENT_INTERVAL")
    return reg


def reseal(reg):
    return cr._seal_registry(reg)


def redescribe(entry):
    entry.pop("descriptor_digest", None)
    entry["descriptor_digest"] = gt.digest(entry)
    return entry


# ---------------------------------------------------------------- policy


def test_cadence_policy_defaults_sorted_and_verifies():
    policy = cr.cadence_policy()
    assert policy["every_n_events"] == 10
    assert policy["milestone_triggers"] == sorted(cr.DEFAULT_TRIGGERS)
    assert cr.verify_policy(policy) == {
        "status": "PASS",
        "policy_digest": policy["policy_digest"],
        "authority_transfer": False,
    }


def test_cadence_policy_dedupes_custom_triggers():
    assert cr.cadence_policy(2, ["B", "A", "B"])["milestone_triggers"] == ["A", "B"]


@pytest.mark.parametrize("n", [0, -1, "3", 2.5])
def test_cadence_policy_rejects_bad_interval(n):
    with pytest.raises(CRE, match="^every_n_events must be >= 1$"):
        cr.cadence_policy(n)


def test_cadence_policy_rejects_empty_trigger():
    with pytest.raises(CRE, match="^checkpoint triggers must be non-empty strings$"):
        cr.cadence_policy(1, ["OK", ""])


def _resealed_policy(**changes):
    p = cr.cadence_policy(3)
    p.update(changes)
    p.pop("policy_digest")
    p["policy_digest"] = gt.digest(p)
    return p


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"schema": "x"}, "cadence policy schema mismatch"),
        ({"authority_transfer": True}, "cadence policy authority_transfer must remain false"),
        ({"wall_clock_cadence_authoritative": True}, "wall-clock cadence may not be authoritative"),
        ({"visual_fidelity_credit": True}, "checkpoint policy may not grant visual fidelity credit"),
        ({"every_n_events": 0}, "cadence policy every_n_events invalid"),
        ({"every_n_events": "4"}, "cadence policy every_n_events invalid"),
        ({"milestone_triggers": ["B", "A"]}, "cadence policy milestone_triggers must be sorted unique list"),
        ({"milestone_triggers": "A"}, "cadence policy milestone_triggers must be sorted unique list"),
    ],
)
def test_verify_policy_rejections(changes, message):
    with pytest.raises(CRE, match="^" + message + "$"):
        cr.verify_policy(_resealed_policy(**changes))


def test_verify_policy_rejects_digest_mismatch():
    p = cr.cadence_policy(3)
    p["policy_digest"] = "sha256:" + "0" * 64
    with pytest.raises(CRE, match="^cadence policy digest mismatch$"):
        cr.verify_policy(p)


# ---------------------------------------------------------------- anchor / descriptor


def test_lineage_anchor_for_empty_ledger_uses_genesis():
    empty = gt.seal({"events": []})
    assert cr.lineage_anchor(empty) == gt.digest({"genesis": gt.GENESIS, "projection_schema_version": 1})
    reg = cr.empty_registry(empty, cr.cadence_policy(1))
    assert reg["entries"] == []
    assert cr.verify_registry(reg, empty, cr.cadence_policy(1))["latest_through_event_seq"] == 0


def test_lineage_anchor_depends_on_first_event(ledger):
    other = make_ledger(first_subject="occ-other")
    assert cr.lineage_anchor(ledger) != cr.lineage_anchor(other)
    # Appending events does not move the anchor.
    assert cr.lineage_anchor(ledger) == cr.lineage_anchor(make_ledger(12))


def test_checkpoint_descriptor_requires_trigger(ledger, policy):
    with pytest.raises(CRE, match="^checkpoint trigger required$"):
        cr.checkpoint_descriptor(_cp(ledger, "EV-0002", "CP-2"), trigger="", policy=policy)


def test_checkpoint_descriptor_binds_fields(ledger, policy):
    cp = _cp(ledger, "EV-0002", "CP-2")
    d = cr.checkpoint_descriptor(cp, trigger="T", policy=policy, checkpoint_ref="r.json", parent_checkpoint_digest="p")
    assert d["checkpoint_ref"] == "r.json"
    assert d["parent_checkpoint_digest"] == "p"
    assert d["cadence_policy_digest"] == policy["policy_digest"]
    assert "projection_snapshot" not in d
    body = dict(d)
    assert body.pop("descriptor_digest") == gt.digest(body)


# ---------------------------------------------------------------- verify_registry


def test_verify_registry_pass_summary(populated, ledger, policy):
    result = cr.verify_registry(populated, ledger, policy)
    assert result["checkpoint_count"] == 2
    assert result["latest_through_event_seq"] == 6
    assert populated["entries"][1]["parent_checkpoint_digest"] == populated["entries"][0]["checkpoint_digest"]


@pytest.mark.parametrize(
    "key, value, message",
    [
        ("schema", "x", "checkpoint registry schema mismatch"),
        ("authority_transfer", None, "checkpoint registry authority_transfer must remain false"),
        ("lineage_anchor_digest", "sha256:" + "0" * 64, "checkpoint registry lineage anchor mismatch"),
        ("projection_schema_version", 2, "checkpoint registry projection schema mismatch"),
        ("cadence_policy_digest", "sha256:" + "0" * 64, "checkpoint registry cadence policy mismatch"),
        ("entries", {}, "checkpoint registry entries must be a list"),
    ],
)
def test_verify_registry_top_level_rejections(populated, ledger, policy, key, value, message):
    reg = copy.deepcopy(populated)
    reg[key] = value
    with pytest.raises(CRE, match="^" + message + "$"):
        cr.verify_registry(reseal(reg), ledger, policy)


def test_verify_registry_rejects_unsealed_tamper(populated, ledger, policy):
    reg = copy.deepcopy(populated)
    reg["entries"] = reg["entries"][:1]
    with pytest.raises(CRE, match="^checkpoint registry digest mismatch$"):
        cr.verify_registry(reg, ledger, policy)


def test_verify_registry_rejects_other_ledger_and_policy(populated, ledger, policy):
    with pytest.raises(CRE, match="lineage anchor mismatch"):
        cr.verify_registry(populated, make_ledger(first_subject="occ-x"), policy)
    with pytest.raises(CRE, match="cadence policy mismatch"):
        cr.verify_registry(populated, ledger, cr.cadence_policy(5))


def test_verify_registry_rejects_non_object_entry(populated, ledger, policy):
    reg = copy.deepcopy(populated)
    reg["entries"][0] = "nope"
    with pytest.raises(CRE, match="^checkpoint registry entry must be an object$"):
        cr.verify_registry(reseal(reg), ledger, policy)


def _entry_case(populated, index, **changes):
    reg = copy.deepcopy(populated)
    reg["entries"][index].update(changes)
    redescribe(reg["entries"][index])
    return reseal(reg)


def test_verify_registry_rejects_entry_authority_transfer(populated, ledger, policy):
    reg = _entry_case(populated, 0, authority_transfer=True)
    with pytest.raises(CRE, match="entry authority_transfer must remain false"):
        cr.verify_registry(reg, ledger, policy)


def test_verify_registry_rejects_descriptor_digest(populated, ledger, policy):
    reg = copy.deepcopy(populated)
    reg["entries"][0]["trigger"] = "EDITED"
    with pytest.raises(CRE, match="^checkpoint descriptor digest mismatch$"):
        cr.verify_registry(reseal(reg), ledger, policy)


def test_verify_registry_rejects_entry_policy(populated, ledger, policy):
    reg = _entry_case(populated, 0, cadence_policy_digest="sha256:" + "3" * 64)
    with pytest.raises(CRE, match="^checkpoint descriptor policy mismatch$"):
        cr.verify_registry(reg, ledger, policy)


def test_verify_registry_rejects_duplicate_identity(populated, ledger, policy):
    reg = _entry_case(populated, 1, checkpoint_id="CP-3")
    with pytest.raises(CRE, match="^duplicate checkpoint registry identity$"):
        cr.verify_registry(reg, ledger, policy)


@pytest.mark.parametrize("seq", [3, 2, 11, "6", None])
def test_verify_registry_rejects_bad_sequence(populated, ledger, policy, seq):
    reg = _entry_case(populated, 1, through_event_seq=seq)
    with pytest.raises(CRE, match="strictly increasing and in-ledger"):
        cr.verify_registry(reg, ledger, policy)


def test_verify_registry_rejects_event_id_mismatch(populated, ledger, policy):
    reg = _entry_case(populated, 1, through_event_id="EV-0005")
    with pytest.raises(CRE, match="^checkpoint registry event id mismatch$"):
        cr.verify_registry(reg, ledger, policy)


def test_verify_registry_rejects_event_digest_mismatch(populated, ledger, policy):
    reg = _entry_case(populated, 1, through_event_digest="sha256:" + "4" * 64)
    with pytest.raises(CRE, match="^checkpoint registry event digest mismatch$"):
        cr.verify_registry(reg, ledger, policy)


def test_verify_registry_rejects_entry_projection_schema(populated, ledger, policy):
    reg = _entry_case(populated, 1, projection_schema_version=2)
    with pytest.raises(CRE, match="^checkpoint descriptor projection schema mismatch$"):
        cr.verify_registry(reg, ledger, policy)


def test_verify_registry_rejects_parent_chain(populated, ledger, policy):
    reg = _entry_case(populated, 1, parent_checkpoint_digest=None)
    with pytest.raises(CRE, match="^checkpoint parent chain mismatch$"):
        cr.verify_registry(reg, ledger, policy)


# ---------------------------------------------------------------- cadence_decision


def test_cadence_rejects_target_with_no_events(ledger, policy):
    reg = cr.empty_registry(ledger, policy)
    with pytest.raises(CRE, match="^cadence target resolves to no events$"):
        cr.cadence_decision(reg, ledger, policy, boundary="2020-01-01T00:00:00Z")


def test_cadence_already_checkpointed(populated, ledger, policy):
    d = cr.cadence_decision(populated, ledger, policy, boundary="EV-0006")
    assert d == {
        "status": "NOT_DUE",
        "reason": "ALREADY_CHECKPOINTED",
        "target_event_seq": 6,
        "events_since_latest": 0,
        "authority_transfer": False,
    }


def test_cadence_target_predates_latest(populated, ledger, policy):
    d = cr.cadence_decision(populated, ledger, policy, boundary="EV-0004")
    assert d["status"] == "NOT_DUE"
    assert d["reason"] == "TARGET_PREDATES_LATEST_REGISTERED"
    assert d["events_since_latest"] == -2


def test_cadence_unknown_trigger_falls_through_to_interval(populated, ledger, policy):
    d = cr.cadence_decision(populated, ledger, policy, boundary="EV-0007", trigger="NOT_A_MILESTONE")
    assert d["status"] == "NOT_DUE"
    assert d["reason"] == "CADENCE_NOT_REACHED"
    assert d["trigger"] == "NOT_A_MILESTONE"
    d = cr.cadence_decision(populated, ledger, policy, boundary="EV-0009", trigger="NOT_A_MILESTONE")
    assert (d["status"], d["reason"], d["events_since_latest"]) == ("DUE", "EVENT_INTERVAL", 3)


# ---------------------------------------------------------------- register / select


def test_register_conflicting_checkpoint_at_same_boundary(populated, ledger, policy):
    other = cpr.create_checkpoint(ledger, "EV-0006", "CP-6b", created_at="2026-09-05T00:00:00Z")
    with pytest.raises(CRE, match="^same checkpoint boundary has conflicting checkpoint digest$"):
        cr.register_checkpoint(populated, ledger, policy, other, trigger="X")


def test_register_returns_parent_and_descriptor(populated, ledger, policy):
    cp9 = _cp(ledger, "EV-0009", "CP-9")
    reg, receipt = cr.register_checkpoint(populated, ledger, policy, cp9, trigger="RELEASE_BOUNDARY", checkpoint_ref="x")
    assert receipt["status"] == "REGISTERED"
    assert receipt["parent_checkpoint_digest"] == populated["entries"][-1]["checkpoint_digest"]
    assert receipt["descriptor_digest"] == reg["entries"][-1]["descriptor_digest"]
    assert reg["entries"][-1]["checkpoint_ref"] == "x"
    assert len(populated["entries"]) == 2


def test_register_rejects_unverifiable_checkpoint(populated, ledger, policy):
    cp9 = _cp(ledger, "EV-0009", "CP-9")
    cp9["checkpoint_digest"] = "sha256:" + "0" * 64
    with pytest.raises(gt.GoldenThreadError, match="checkpoint digest mismatch"):
        cr.register_checkpoint(populated, ledger, policy, cp9, trigger="T")


def test_select_genesis_required_before_first_checkpoint(populated, ledger, policy):
    s = cr.select_checkpoint(populated, ledger, policy, boundary="EV-0002")
    assert s == {
        "status": "GENESIS_REQUIRED",
        "target_event_seq": 2,
        "checkpoint": None,
        "authority_transfer": False,
    }


def test_select_picks_newest_compatible(populated, ledger, policy):
    s = cr.select_checkpoint(populated, ledger, policy, boundary="EV-0005")
    assert s["checkpoint"]["checkpoint_id"] == "CP-3"
    assert s["tail_event_count"] == 2


# ---------------------------------------------------------------- CLI


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_main_new_writes_policy_and_registry(tmp_path, ledger):
    lp = _write(tmp_path / "ledger.json", ledger)
    out = tmp_path / "new.json"
    assert cr.main(["new", str(lp), "--every-n-events", "4", "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["policy"]["every_n_events"] == 4
    assert data["registry"]["cadence_policy_digest"] == data["policy"]["policy_digest"]
    assert data["registry"]["lineage_anchor_digest"] == cr.lineage_anchor(ledger)


def test_main_verify_and_select(tmp_path, ledger, policy, populated, capsys):
    lp = _write(tmp_path / "ledger.json", ledger)
    rp = _write(tmp_path / "reg.json", populated)
    pp = _write(tmp_path / "policy.json", policy)
    assert cr.main(["verify", str(lp), str(rp), str(pp)]) == 0
    assert json.loads(capsys.readouterr().out)["checkpoint_count"] == 2
    assert cr.main(["select", str(lp), str(rp), str(pp), "--as-of", "EV-0008"]) == 0
    sel = json.loads(capsys.readouterr().out)
    assert sel["status"] == "CHECKPOINT_SELECTED"
    assert sel["checkpoint"]["checkpoint_id"] == "CP-6"
    assert cr.main(["select", str(lp), str(rp), str(pp), "--as-of", "EV-0001"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "GENESIS_REQUIRED"


def test_main_returns_2_on_non_object_json(tmp_path, capsys, monkeypatch):
    lp = _write(tmp_path / "ledger.json", [1, 2])
    monkeypatch.setattr(sys, "argv", ["checkpoint_registry.py", "new", str(lp), "--out", str(tmp_path / "o.json")])
    assert cr.main() == 2
    err = capsys.readouterr().err
    assert err.startswith("FAIL: ")
    assert "top-level JSON must be an object" in err
    assert not (tmp_path / "o.json").exists()


def test_main_returns_2_on_verification_failure(tmp_path, ledger, populated, capsys):
    lp = _write(tmp_path / "ledger.json", ledger)
    rp = _write(tmp_path / "reg.json", populated)
    pp = _write(tmp_path / "policy.json", cr.cadence_policy(7))
    assert cr.main(["verify", str(lp), str(rp), str(pp)]) == 2
    assert capsys.readouterr().err.strip() == "FAIL: checkpoint registry cadence policy mismatch"


def test_dump_to_stdout(capsys):
    cr._dump({"b": 1, "a": 2})
    out = capsys.readouterr().out
    assert out.index('"a"') < out.index('"b"')
