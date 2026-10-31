"""Coverage wave w10: mission-control/golden-thread/session_hook/session_hook.py (tmp_path only)."""
import hashlib
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "golden-thread" / "session_hook" / "session_hook.py"
_spec = importlib.util.spec_from_file_location("cw_w10_session_hook_mod", MOD_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

SHA = "c" * 40
STAMP = "2026-10-31T09:00:00Z"
ALIAS = "CW_W10_SESSION_ALIAS"


def intent(n, parent=None, stamp=STAMP):
    item = {
        "intent_id": "CP-SESSION-20261031-%03d" % n, "logical_index": n,
        "parent_intent_id": parent,
        "source_class": "CURRENT_CONVERSATION_RECONSTRUCTED_USER_INTENT",
        "original_turn_id": None, "original_message_time_utc": None,
        "source_time_verification": "UNKNOWN", "capture_checkpoint_utc": stamp,
        "summary": "Sanitized intent summary number %d for coverage." % n,
        "owner_issue": "GBOGEB/pipeline-automation-hub#7",
        "action": {"action_id": "CP-ACTION-20261031-%03d" % n,
                   "owner_repo": "GBOGEB/pipeline-automation-hub", "owner_issue": 7,
                   "existing_pr": None, "status": "PLANNED_BEFORE_IMPLEMENTATION",
                   "summary": "Bounded action summary number %d here." % n,
                   "verified_native_receipt": None}}
    if parent is not None:
        item["relation_to_parent"] = "REFINES_WITHOUT_SUPERSEDING"
    return item


def intake(stamp=STAMP, intents=None):
    return {
        "schema": mod.SCHEMA, "session_alias": ALIAS, "session_alias_not_platform_id": True,
        "capture_mode": "MANUAL_SANITIZED_INTENT", "capture_checkpoint_utc": stamp,
        "original_turn_ids_accessible": False, "raw_transcript_exported": False,
        "privacy_boundary": "SANITIZED_SUMMARY_ONLY", "authority_transfer": False,
        "merge_authorized": False, "engineering_credit": 0, "qps_disposition": "DEFER",
        "existing_source_refs": [{"repository": "GBOGEB/pipeline-automation-hub",
                                  "path": "x.py", "blob_sha": "d" * 40}],
        "intent_events": intents if intents is not None else [
            intent(1, stamp=stamp), intent(2, "CP-SESSION-20261031-001", stamp=stamp)],
        "forecast_pre_registered": {"actual_native_adapter_result": None,
                                    "score": "PENDING_NATIVE_EXACT_HEAD"},
    }


def test_valid_intake():
    assert mod.validate(intake()) is True


def test_private_check_rejects_secret_like_strings():
    with pytest.raises(mod.SessionHookError, match="secret-like"):
        mod._private_check({"a": ["x" * 2501]})
    with pytest.raises(mod.SessionHookError, match="secret-like"):
        mod._private_check(["sk-proj-abc"])
    mod._private_check({"a": [1, None, "ok"]})


def _bad(mutate, needle):
    d = intake()
    mutate(d)
    with pytest.raises(mod.SessionHookError, match=needle):
        mod.validate(d)


def _ev(d, n=0):
    return d["intent_events"][n]


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d.update(schema="other"), "unsupported session intake schema"),
    (lambda d: d.update(privacy_boundary="RAW"), "manual sanitized ingress"),
    (lambda d: d.update(engineering_credit=False), "boundary: engineering_credit"),
    (lambda d: d.update(session_alias="short"), "pseudonymous session alias"),
    (lambda d: d.update(session_alias=5), "pseudonymous session alias"),
    (lambda d: d.update(capture_checkpoint_utc="2026-10-31T09:00:00+00:00"), "UTC capture"),
    (lambda d: d.update(capture_checkpoint_utc=None), "UTC capture"),
    (lambda d: d.update(intent_events=[]), "bounded nonempty"),
    (lambda d: d.update(intent_events="x"), "bounded nonempty"),
    (lambda d: d["intent_events"].__setitem__(0, "x"), "invalid intent id"),
    (lambda d: _ev(d).update(intent_id="BAD"), "invalid intent id"),
    (lambda d: _ev(d).update(logical_index=True), "logical sequence"),
    (lambda d: _ev(d).update(logical_index=2), "logical sequence"),
    (lambda d: _ev(d).update(capture_checkpoint_utc="2026-10-30T00:00:00Z"), "capture time mismatch"),
    (lambda d: _ev(d).update(source_time_verification="VERIFIED"), "not verified"),
    (lambda d: _ev(d).update(source_class="ATTESTED"), "reconstruction source class"),
    (lambda d: _ev(d).update(summary="short"), "bounded sanitized summary"),
    (lambda d: _ev(d).update(summary=None), "bounded sanitized summary"),
    (lambda d: _ev(d, 1).update(relation_to_parent="SUPERSEDES"), "silently supersede"),
    (lambda d: _ev(d).update(action=None), "stable action id"),
    (lambda d: _ev(d)["action"].update(action_id="X"), "stable action id"),
    (lambda d: _ev(d, 1)["action"].update(action_id="CP-ACTION-20261031-001"), "duplicate action id"),
    (lambda d: _ev(d)["action"].update(status="DONE"), "native verification"),
    (lambda d: _ev(d)["action"].update(verified_native_receipt="r"), "native verification"),
    (lambda d: _ev(d)["action"].update(owner_repo="other/x"), "existing owner identity"),
    (lambda d: _ev(d)["action"].update(owner_issue=0), "existing owner identity"),
    (lambda d: _ev(d)["action"].update(owner_issue="7"), "existing owner identity"),
    (lambda d: _ev(d).update(owner_issue="GBOGEB/pipeline-automation-hub#8"), "owner mismatch"),
    (lambda d: _ev(d)["action"].update(existing_pr=0), "invalid existing PR"),
    (lambda d: _ev(d)["action"].update(existing_pr="5"), "invalid existing PR"),
    (lambda d: _ev(d)["action"].update(summary="tiny"), "bounded action summary"),
    (lambda d: d.update(existing_source_refs=["x"]), "source owner invalid"),
    (lambda d: d["existing_source_refs"][0].update(repository="other/x"), "source owner invalid"),
    (lambda d: d["existing_source_refs"][0].update(path=None), "exact blob"),
    (lambda d: d.update(forecast_pre_registered=None), "forecast outcome"),
    (lambda d: d["forecast_pre_registered"].update(score="PASS"), "forecast outcome"),
])
def test_validate_rejections(mutate, needle):
    _bad(mutate, needle)


def test_existing_pr_positive_accepted_and_no_source_refs():
    d = intake()
    _ev(d)["action"]["existing_pr"] = 12
    del d["existing_source_refs"]
    assert mod.validate(d) is True


def test_projection_requires_exact_sha():
    d = intake()
    ledger = mod.build(d)
    with pytest.raises(mod.SessionHookError, match="exact source SHA"):
        mod.projection(d, ledger, "abc")


def test_emit_and_mermaid_refinement_edge(tmp_path):
    d = intake()
    ledger = mod.build(d)
    report = mod.emit(d, ledger, tmp_path / "out", SHA)
    assert report["intent_count"] == 2 and report["work_order_count"] == 2
    mmd = (tmp_path / "out" / "session_execution_dag.mmd").read_text(encoding="utf-8")
    assert "I1 -.->|refines| I2" in mmd
    receipt = json.loads((tmp_path / "out" / "session_receipt.json").read_text(encoding="utf-8"))
    assert set(receipt["files"]) == {"session_ledger.json", "session_projection.json",
                                     "session_execution_dag.mmd", "session_review.html"}


@pytest.mark.xfail(sys.platform == "win32", strict=True,
                   reason="production_defect: emit() write_text without newline='\\n' writes CRLF on Windows, so receipt sha256/bytes do not match the files on disk")
def test_receipt_digest_matches_bytes_on_disk(tmp_path):
    d = intake()
    mod.emit(d, mod.build(d), tmp_path, SHA)
    receipt = json.loads((tmp_path / "session_receipt.json").read_bytes())
    for name, info in receipt["files"].items():
        raw = (tmp_path / name).read_bytes()
        assert info["sha256"] == "sha256:" + hashlib.sha256(raw).hexdigest()
        assert info["bytes"] == len(raw)


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8", newline="\n")
    return path


def test_main_with_previous_ledger(tmp_path, monkeypatch, capsys):
    first = intake()
    prev = _write(tmp_path / "prev.json", mod.build(first))
    later = "2026-10-31T10:00:00Z"
    second = intake(later, [intent(1, stamp=later)])
    second["intent_events"][0]["intent_id"] = "CP-SESSION-20261031-003"
    second["intent_events"][0]["parent_intent_id"] = "CP-SESSION-20261031-002"
    second["intent_events"][0]["relation_to_parent"] = "REFINES_WITHOUT_SUPERSEDING"
    inp = _write(tmp_path / "in.json", second)
    monkeypatch.setattr(sys, "argv", ["session_hook.py", "--input", str(inp), "--out",
                                      str(tmp_path / "o"), "--source-sha", SHA,
                                      "--previous-ledger", str(prev)])
    mod.main()
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "SOURCE_BOUND_PROJECTION"
    assert out["intents"] == 1


def test_dunder_main_without_previous(tmp_path, monkeypatch, capsys):
    inp = _write(tmp_path / "in.json", intake())
    monkeypatch.setattr(sys, "argv", ["session_hook.py", "--input", str(inp), "--out",
                                      str(tmp_path / "o"), "--source-sha", SHA])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    out = json.loads(capsys.readouterr().out)
    assert out["intents"] == 2 and out["merge_authorized"] is False
