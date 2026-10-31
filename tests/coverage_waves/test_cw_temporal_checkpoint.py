"""Coverage-wave behavioural tests for mission-control/golden-thread/temporal_checkpoint.py.

Targets what test_temporal_checkpoint.py / test_w57_observed_defer.py miss:
child-transaction validation errors, checkpoint argument validation,
verify_checkpoint failure modes, dump_json and the CLI entry point.
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

_spec = importlib.util.spec_from_file_location("cw_temporal_checkpoint", GT_DIR / "temporal_checkpoint.py")
tc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tc)
gt = tc.gt

D1 = "sha256:" + "1" * 64
D2 = "sha256:" + "2" * 64
D3 = "sha256:" + "3" * 64
REPO = "GBOGEB/cw-repo"
SHA = "a" * 40


def raw_event(event_id, payload=None, event_type="OBSERVED"):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": "2026-09-17T01:30:00Z",
        "recorded_at": "2026-09-17T01:30:00Z",
        "actor": "cw.test",
        "subject_ref": "occ:" + event_id,
        "authority_domain": "GBOGEB/child",
        "evidence_refs": [],
        "non_compensating_preserved": True,
        "payload": payload or {},
    }


def sealed(events):
    return gt.seal({"events": events})


def injection(key="inj-1", idem=D1, **over):
    v = {"injection_key": key, "child_repo": "GBOGEB/child", "source_digest": D2, "idempotency_key": idem}
    v.update(over)
    return {"child_injection": v}


def disposition(key="inj-1", result="ACCEPT", **over):
    v = {"injection_key": key, "disposition": result}
    v.update(over)
    return {"child_disposition": v}


# ------------------------------------------------------------------ helpers


def test_load_json_object_and_non_object(tmp_path):
    p = tmp_path / "a.json"
    p.write_text('{"k": 1}', encoding="utf-8")
    assert tc.load_json(p) == {"k": 1}
    q = tmp_path / "b.json"
    q.write_text("[]", encoding="utf-8")
    with pytest.raises(tc.TemporalGoldenThreadError, match="top-level JSON must be an object"):
        tc.load_json(q)


def test_require_string_rejects_blank_and_validate_digest_rejects_bad_shape():
    with pytest.raises(tc.TemporalGoldenThreadError, match="ctx: missing/invalid k"):
        tc.require_string({"k": "   "}, "k", "ctx")
    with pytest.raises(tc.TemporalGoldenThreadError, match="c: expected sha256:<64 hex> digest"):
        tc.validate_digest("sha256:abc", "c")
    tc.validate_digest(D1.upper().replace("SHA256", "sha256"), "c")


def test_dump_json_creates_parent_dirs_and_stdout(tmp_path, capsys):
    out = tmp_path / "deep" / "x.json"
    tc.dump_json({"b": 2, "a": 1}, out)
    assert out.read_text(encoding="utf-8") == '{\n  "a": 1,\n  "b": 2\n}\n'
    tc.dump_json({"z": 0}, None)
    assert capsys.readouterr().out == '{\n  "z": 0\n}\n'


# ------------------------------------------------------------------ scan_child_transactions


def test_scan_rejects_non_object_event_and_payload():
    with pytest.raises(tc.TemporalGoldenThreadError, match="ledger event must be an object"):
        tc.scan_child_transactions({"events": ["x"]})
    with pytest.raises(tc.TemporalGoldenThreadError, match="E1: payload must be an object"):
        tc.scan_child_transactions({"events": [{"event_id": "E1", "payload": "str"}]})


def test_scan_rejects_non_mapping_injection():
    with pytest.raises(tc.TemporalGoldenThreadError, match=r"\?: child_injection must be an object"):
        tc.scan_child_transactions({"events": [{"payload": {"child_injection": []}}]})


def test_scan_rejects_bad_injection_digest():
    led = {"events": [{"event_id": "E1", "payload": injection(source_digest="nope")}]}
    with pytest.raises(tc.TemporalGoldenThreadError, match=r"E1\.child_injection\.source_digest: expected"):
        tc.scan_child_transactions(led)


def test_scan_rejects_duplicate_injection_key_and_idempotency_key():
    led = {"events": [{"event_id": "E1", "payload": injection()},
                      {"event_id": "E2", "payload": injection()}]}
    with pytest.raises(tc.TemporalGoldenThreadError, match="E2: duplicate child injection_key inj-1"):
        tc.scan_child_transactions(led)
    led = {"events": [{"event_id": "E1", "payload": injection()},
                      {"event_id": "E2", "payload": injection(key="inj-2")}]}
    with pytest.raises(tc.TemporalGoldenThreadError,
                       match="E2: duplicate child obligation idempotency_key; first seen in E1"):
        tc.scan_child_transactions(led)


def test_scan_disposition_error_paths():
    base = {"event_id": "E1", "payload": injection()}
    cases = [
        (disposition(key="ghost"), "E2: child disposition references unknown injection_key ghost"),
        (disposition(result="maybe"), "E2: child disposition must be ACCEPT, REJECT or DEFER"),
        (disposition(result="reject", rejection_reason="r", authoritative_delta_applied=True),
         "E2: REJECT cannot set authoritative_delta_applied=true"),
        (disposition(result="DEFER", owner="o", reentry_trigger="t", authoritative_delta_applied=1),
         "E2: DEFER cannot set authoritative_delta_applied=true"),
        (disposition(result="DEFER", owner="o"), "E2: missing/invalid reentry_trigger"),
        (disposition(child_receipt_ref="r", authoritative_delta_applied=True,
                     accepted_authoritative_delta_digest="bad"),
         r"E2\.child_disposition\.accepted_authoritative_delta_digest: expected"),
    ]
    for disp, message in cases:
        led = {"events": [base, {"event_id": "E2", "payload": disp}]}
        with pytest.raises(tc.TemporalGoldenThreadError, match=message):
            tc.scan_child_transactions(led)


def test_scan_rejects_second_disposition():
    led = {"events": [{"event_id": "E1", "payload": injection()},
                      {"event_id": "E2", "payload": disposition(result="REJECT", rejection_reason="no")},
                      {"event_id": "E3", "payload": disposition(result="REJECT", rejection_reason="no")}]}
    with pytest.raises(tc.TemporalGoldenThreadError, match="E3: injection inj-1 already dispositioned by E2"):
        tc.scan_child_transactions(led)


def test_scan_summarises_mixed_dispositions():
    led = {"events": [
        {"event_id": "E1", "payload": injection("a", D1)},
        {"event_id": "E2", "payload": injection("b", D2)},
        {"event_id": "E3", "payload": injection("c", D3)},
        {"event_id": "E4", "payload": injection("d", "sha256:" + "4" * 64)},
        {"event_id": "E5", "payload": disposition("a", "accept", child_receipt_ref="rcpt")},
        {"event_id": "E6", "payload": disposition("b", "Reject", rejection_reason="why")},
        {"event_id": "E7", "payload": disposition("c", "defer", owner="own", reentry_trigger="trig")},
        {"event_id": "E8", "payload": None},
    ]}
    s = tc.scan_child_transactions(led)
    assert (s["injection_count"], s["disposition_count"]) == (4, 3)
    assert s["accepted_injection_keys"] == ["a"]
    assert s["rejected_injection_keys"] == ["b"]
    assert s["deferred_injection_keys"] == ["c"]
    assert s["unresolved_injection_keys"] == ["d"]
    assert s["accepted_authoritative_delta_count"] == 0
    assert s["dispositions"]["a"] == {"event_id": "E5", "injection_key": "a", "disposition": "ACCEPT",
                                      "authoritative_delta_applied": False, "child_receipt_ref": "rcpt"}
    assert s["dispositions"]["c"]["owner"] == "own"
    assert s["dispositions"]["b"]["rejection_reason"] == "why"


# ------------------------------------------------------------------ checkpoint_payload


@pytest.mark.parametrize("kwargs,message", [
    ({"base_semantic_generation_k": -1}, "base_semantic_generation_k must be >= 0"),
    ({"base_semantic_generation_k": "0"}, "base_semantic_generation_k must be >= 0"),
    ({"git_repo": "norepo"}, "git_repo must be owner/repo"),
    ({"git_repo": None}, "git_repo must be owner/repo"),
    ({"git_commit_sha": "xyz"}, "git_commit_sha must be 7-40 hexadecimal characters"),
    ({"ssot_digest": "sha256:zz"}, "ssot_digest: expected sha256:<64 hex> digest"),
])
def test_checkpoint_payload_argument_validation(kwargs, message):
    args = {"base_semantic_generation_k": 0, "ssot_digest": None, "git_repo": REPO, "git_commit_sha": SHA}
    args.update(kwargs)
    with pytest.raises(tc.TemporalGoldenThreadError, match=message):
        tc.checkpoint_payload(sealed([]), **args)


def test_checkpoint_requires_ssot_digest_when_k_advances():
    led = sealed([raw_event("E1", injection()),
                  raw_event("E2", disposition(child_receipt_ref="r", authoritative_delta_applied=True,
                                              accepted_authoritative_delta_digest=D3))])
    with pytest.raises(tc.TemporalGoldenThreadError,
                       match="authoritative ACCEPT exists but resulting ssot_digest was not supplied"):
        tc.checkpoint_payload(led, base_semantic_generation_k=2, ssot_digest=None, git_repo=REPO,
                              git_commit_sha=SHA)
    cp = tc.checkpoint_payload(led, base_semantic_generation_k=2, ssot_digest=D1, git_repo=REPO,
                               git_commit_sha=SHA)
    assert (cp["semantic_generation_k"], cp["event_sequence_e"], cp["engineering_ssot_changed"]) == (3, 2, True)
    assert cp["child_transaction_summary"]["accepted_authoritative_delta_digests"] == [D3]


# ------------------------------------------------------------------ verify_checkpoint


def _checkpoint(led):
    return tc.checkpoint_payload(led, base_semantic_generation_k=0, ssot_digest=None, git_repo=REPO,
                                 git_commit_sha=SHA, milestone="M1")


@pytest.mark.parametrize("mutate,message", [
    (lambda c: c.update(schema="other"), "checkpoint schema mismatch"),
    (lambda c: c.update(authority_transfer=None), "checkpoint authority_transfer must remain false"),
    (lambda c: c.update(git_anchor="x"), "checkpoint git_anchor must be an object"),
    # milestone is re-read from the checkpoint, so only the sealed digest disagrees
    (lambda c: c.update(milestone="M2"),
     "checkpoint does not reproduce from ledger; differing fields: checkpoint_digest$"),
    (lambda c: c.update(extra=1),
     "checkpoint does not reproduce from ledger; differing fields: extra"),
])
def test_verify_checkpoint_failures(mutate, message):
    led = sealed([raw_event("E1")])
    cp = _checkpoint(led)
    mutate(cp)
    with pytest.raises(tc.TemporalGoldenThreadError, match=message):
        tc.verify_checkpoint(led, cp)


def test_verify_checkpoint_detects_ledger_growth():
    led = sealed([raw_event("E1")])
    cp = _checkpoint(led)
    grown = sealed([raw_event("E1"), raw_event("E2")])
    with pytest.raises(tc.TemporalGoldenThreadError,
                       match="differing fields: checkpoint_digest, event_sequence_e, projection_digest, thread_digest"):
        tc.verify_checkpoint(grown, cp)


# ------------------------------------------------------------------ CLI


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_main_build_to_file_then_verify_stdout(tmp_path, capsys, monkeypatch):
    led = _write(tmp_path / "l.json", sealed([raw_event("E1")]))
    out = tmp_path / "out" / "cp.json"
    monkeypatch.setattr(sys, "argv", ["temporal_checkpoint.py", "build", str(led), "--base-k", "4",
                                      "--git-repo", REPO, "--git-commit-sha", "abc1234",
                                      "--milestone", "M", "--out", str(out)])
    assert tc.main() == 0
    cp = json.loads(out.read_text(encoding="utf-8"))
    assert (cp["semantic_generation_k"], cp["milestone"], cp["git_anchor"]["commit_sha"]) == (4, "M", "abc1234")
    assert tc.main(["verify", str(led), str(out)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "PASS"
    assert receipt["checkpoint_digest"] == cp["checkpoint_digest"]


def test_main_build_stdout(tmp_path, capsys):
    led = _write(tmp_path / "l.json", sealed([]))
    assert tc.main(["build", str(led), "--base-k", "0", "--git-repo", REPO, "--git-commit-sha", SHA,
                    "--ssot-digest", D1]) == 0
    assert json.loads(capsys.readouterr().out)["ssot_digest"] == D1


def test_main_fail_paths_return_2(tmp_path, capsys):
    led_doc = sealed([raw_event("E1")])
    led = _write(tmp_path / "l.json", led_doc)
    assert tc.main(["build", str(led), "--base-k", "0", "--git-repo", "bad", "--git-commit-sha", SHA]) == 2
    assert capsys.readouterr().err == "FAIL: git_repo must be owner/repo\n"

    broken = copy.deepcopy(led_doc)
    broken["head_event_digest"] = "sha256:00"
    bl = _write(tmp_path / "broken.json", broken)
    assert tc.main(["build", str(bl), "--base-k", "0", "--git-repo", REPO, "--git-commit-sha", SHA]) == 2
    assert capsys.readouterr().err == "FAIL: head digest mismatch\n"

    cp = _write(tmp_path / "cp.json", {"schema": tc.TEMPORAL_SCHEMA, "authority_transfer": False,
                                       "git_anchor": {"repository": REPO, "commit_sha": None}})
    assert tc.main(["verify", str(led), str(cp)]) == 2
    assert capsys.readouterr().err.startswith("FAIL: ")
