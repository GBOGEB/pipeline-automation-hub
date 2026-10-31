"""Coverage wave w10: mission-control/v2/handoff/closeout/cp_close.py (tmp_path data only)."""
import copy
import importlib.util
import json
import runpy
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "v2" / "handoff" / "closeout" / "cp_close.py"
_spec = importlib.util.spec_from_file_location("cw_w10_cp_close_mod", MOD_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

SHA = "a" * 40
SHA2 = "b" * 40
URL = "https://github.com/GBOGEB/pipeline-automation-hub/pull/1"


def intake():
    return {
        "schema": mod.SCHEMA, "privacy": "SANITIZED_SEMANTIC_ONLY",
        "session_alias": "CP-TEST-20261031", "capture_date": "2026-10-31",
        "capture_granularity": "DATE_ONLY", "capture_scope": "TEST_SCOPE",
        "source": {"repository": mod.OWNER, "default_branch": "master", "observed_main_sha": SHA},
        "merge_admission": "HOLD", "security_waiver": False, "authority_transfer": False,
        "complete_transcript_available": False, "total_chat_user_prompts": None,
        "total_chat_messages": None,
        "intents": [{"id": "SC-I001", "summary": "do it", "source_class": "USER_EXPLICIT_INTAKE",
                     "original_chat_message_id": None, "original_chat_timestamp": None,
                     "actions": ["SC-A001"]},
                    {"id": "SC-I002", "summary": "nothing", "source_class": "SOURCE_BOUND_REFERENCE",
                     "actions": []}],
        "actions": [{"id": "SC-A001", "priority": "P1", "state": "ACTIVE", "owner": "lane",
                     "summary": "s1", "done_when": "d1", "depends_on": [], "evidence_urls": [URL]},
                    {"id": "SC-A002", "priority": "P2", "state": "DONE", "owner": "lane",
                     "summary": "s2", "done_when": "d2", "depends_on": ["SC-A001"],
                     "evidence_urls": []}],
        "decisions": [{"name": "n", "rationale": "r", "disposition": "KEEP", "evidence_url": URL}],
        "insights": [{"observation": "o", "implication": "i", "evidence_url": URL}],
        "pr_snapshot": [{"number": 1, "state": "OPEN", "url": URL, "head_sha": SHA, "merge_sha": None},
                        {"number": 2, "state": "MERGED", "url": URL, "head_sha": SHA, "merge_sha": SHA2}],
        "external_issues": [{"url": URL, "owner_lane": "LANE"}],
        "metric_observations": [
            {"metric": "M1", "numerator": 1, "denominator": 2, "unit": "u", "population": "p",
             "evidence_class": "E", "source": URL},
            {"metric": "M2", "numerator": None, "denominator": None, "unit": "u", "population": "p",
             "evidence_class": "E", "source": URL}],
        "bd_focus": ["CPQ-001"],
    }


def queue(items=None, **over):
    d = {"schema": "missioncontrol.code_purple.bd_queue.v1", "authority_transfer": False,
         "items": items if items is not None else [
             {"id": "CPQ-001", "title": "t", "severity": "HIGH", "done_when": "dw",
              "control_when": "cw", "links": [URL],
              "history": [{"state": "HOLD", "flow": "F", "at": "2026-10-31", "evidence": URL}]},
             {"id": "CPQ-002", "title": "t2", "severity": "LOW", "done_when": "dw",
              "control_when": "cw", "links": [],
              "history": [{"state": "DONE", "flow": "F", "at": "2026-10-30", "evidence": URL}]}]}
    d.update(over)
    return d


def write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8", newline="\n")
    return path


def test_valid_intake_passes():
    mod.validate(intake())


def _bad(mutate, needle):
    d = intake()
    mutate(d)
    with pytest.raises(ValueError, match=needle):
        mod.validate(d)


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d.update(session_alias="x"), "session identity"),
    (lambda d: d.update(capture_granularity="HOUR"), "capture time precision"),
    (lambda d: d.update(capture_date="not-a-date"), "capture date"),
    (lambda d: d.pop("capture_date"), "capture date"),
    (lambda d: d.update(intents=None), "required array intents"),
    (lambda d: d.update(password="x"), "raw/private"),
    (lambda d: d["actions"][0].update(id=5), "action identities"),
    (lambda d: d["actions"][0].update(state="BOGUS"), "state/priority"),
    (lambda d: d["actions"][0].update(priority="P9"), "state/priority"),
    (lambda d: d["actions"][0].update(depends_on=["SC-A001"]), "orphan/self"),
    (lambda d: d["actions"][0].update(depends_on="SC-A002"), "orphan/self"),
    (lambda d: d["actions"][0].update(evidence_urls="x"), "evidence links"),
    (lambda d: d["actions"][0].update(depends_on=["SC-A002"]), "cycle"),
    (lambda d: d["intents"].append(copy.deepcopy(d["intents"][0])), "duplicate intents"),
    (lambda d: d["intents"][0].update(id="BAD"), "invalid intent"),
    (lambda d: d["intents"][0].update(summary=""), "invalid intent"),
    (lambda d: d["intents"][0].update(source_class="GUESS"), "intent source"),
    (lambda d: d["intents"][0].update(actions="SC-A001"), "intent to action"),
    (lambda d: d["intents"][0].update(original_chat_message_id="m1"), "unproven"),
    (lambda d: d["decisions"][0].update(evidence_url="https://evil.example/x"), "decision"),
    (lambda d: d["insights"][0].update(implication=""), "insight"),
    (lambda d: d["pr_snapshot"][0].update(number="1"), "PR type/state"),
    (lambda d: d["pr_snapshot"][0].update(state="DRAFT"), "PR type/state"),
    (lambda d: d["pr_snapshot"][0].update(head_sha="abc"), "PR head/link"),
    (lambda d: d["pr_snapshot"][0].update(url="http://github.com/GBOGEB/x"), "PR head/link"),
    (lambda d: d["pr_snapshot"][1].update(merge_sha=None), "merge SHA"),
    (lambda d: d["external_issues"][0].update(owner_lane=""), "owner-scoped"),
    (lambda d: d["metric_observations"][0].update(unit=""), "metric scope"),
    (lambda d: d["metric_observations"][0].update(numerator=None), "incomplete"),
    (lambda d: d["metric_observations"][0].update(denominator=0), "invalid metric"),
    (lambda d: d["metric_observations"][0].update(numerator="1"), "invalid metric"),
    (lambda d: d["metric_observations"][0].update(numerator=-1), "invalid metric"),
    (lambda d: d.update(bd_focus=["CPQ-001", "CPQ-001"]), "canonical BD keys"),
    (lambda d: d.update(bd_focus=["BD-1"]), "canonical BD keys"),
])
def test_validate_rejections(mutate, needle):
    _bad(mutate, needle)


def test_owner_url_rejects_userinfo():
    assert mod.owner_url(URL)
    assert not mod.owner_url("https://u:p@github.com/GBOGEB/x")
    assert not mod.owner_url("https://github.com/other/x")


def _msgs(tmp_path, messages, **extra):
    d = {"schema": "missioncontrol.user_supplied_messages.v1", "messages": messages}
    d.update(extra)
    return write(tmp_path / "m.json", d)


@pytest.mark.parametrize("payload", [
    {"schema": "wrong", "messages": [{"role": "user", "text": "x"}]},
    {"schema": "missioncontrol.user_supplied_messages.v1", "messages": []},
    {"schema": "missioncontrol.user_supplied_messages.v1", "messages": "x"},
])
def test_prompt_stats_shape_invalid(tmp_path, payload):
    with pytest.raises(ValueError, match="transcript shape"):
        mod.prompt_stats(write(tmp_path / "m.json", payload))


@pytest.mark.parametrize("message,needle", [
    ({"role": "robot", "text": "x"}, "bad supplied role"),
    ({"role": "user", "text": 5}, "bad supplied role"),
    ({"role": "user", "text": "x", "created_at": "yesterday"}, "bad time"),
    ({"role": "user", "text": "x", "created_at": "2026-10-31T10:00:00"}, "timezone"),
])
def test_prompt_stats_message_rejections(tmp_path, message, needle):
    with pytest.raises(ValueError, match=needle):
        mod.prompt_stats(_msgs(tmp_path, [message]))


def test_prompt_stats_p95_and_declared_complete(tmp_path):
    msgs = [{"role": "user", "text": " ".join(["w"] * (n + 1)),
             "created_at": "2026-10-31T%02d:00:00+00:00" % (n % 24)} for n in range(20)]
    msgs.append({"role": "tool", "text": "t", "created_at": "2026-10-31T00:30:00Z"})
    r = mod.prompt_stats(_msgs(tmp_path, msgs, declared_complete=True))
    assert r["sample_user_prompts"] == 20
    assert r["sample_tool_messages"] == 1
    assert r["sample_user_words_p95"] == 19
    assert r["timestamp_coverage"] is True
    assert r["duration_hours"] == 19.0
    assert r["completeness"] == "SUPPLIED_DECLARED_COMPLETE_NOT_PROVIDER_VERIFIED"


def test_prompt_stats_no_user_messages(tmp_path):
    r = mod.prompt_stats(_msgs(tmp_path, [{"role": "assistant", "text": "a"}]))
    assert r["sample_user_words_median"] is None
    assert r["completeness"] == "SUPPLIED_SUBSET_ONLY"


@pytest.mark.parametrize("q,keys,needle", [
    (queue(schema="other"), ["CPQ-001"], "canonical BD input"),
    (queue(authority_transfer=True), ["CPQ-001"], "canonical BD input"),
    (queue(), ["CPQ-404"], "invalid canonical BD focus"),
])
def test_bd_snapshot_rejections(tmp_path, q, keys, needle):
    with pytest.raises(ValueError, match=needle):
        mod.bd_snapshot(write(tmp_path / "q.json", q), keys)


def test_bd_snapshot_duplicate_ids(tmp_path):
    items = queue()["items"]
    with pytest.raises(ValueError, match="invalid canonical BD focus"):
        mod.bd_snapshot(write(tmp_path / "q.json", queue(items=items + [items[0]])), ["CPQ-001"])


def test_bd_snapshot_empty_history(tmp_path):
    items = queue()["items"]
    items[0]["history"] = []
    with pytest.raises(ValueError, match="no BD source history"):
        mod.bd_snapshot(write(tmp_path / "q.json", queue(items=items)), ["CPQ-001"])


def test_bd_snapshot_projection(tmp_path):
    r = mod.bd_snapshot(write(tmp_path / "q.json", queue()), ["CPQ-001"])
    assert r["global_item_count"] == 2
    assert r["global_lifecycle_counts"] == {"DONE": 1, "HOLD": 1}
    assert r["focus"][0]["state"] == "HOLD"


def _inputs(tmp_path):
    return write(tmp_path / "intake.json", intake()), write(tmp_path / "q.json", queue())


def test_build_render_and_check(tmp_path):
    ip, qp = _inputs(tmp_path)
    out = tmp_path / "out"
    r = mod.build(ip, qp, out, archive=tmp_path / "z" / "a.zip")
    assert r["artifact_count"] == 9
    assert r["status"] == "REVIEWABLE_NOT_MAIN_ADMITTED"
    narrative = (out / "LOSSLESS_HANDOVER.md").read_text(encoding="utf-8")
    assert "actions: NONE" in narrative
    assert "NO_EVIDENCE" in narrative
    assert "M2 UNKNOWN" in narrative and "M1 1/2" in narrative
    todo = (out / "TODO_BD_QUEUE.csv").read_text(encoding="utf-8")
    assert "SC-A001" in todo and "SC-A002" not in todo
    with zipfile.ZipFile(tmp_path / "z" / "a.zip") as z:
        assert len(z.namelist()) == 9
    assert mod.build(ip, qp, out, check=True)["manifest_sha256"] == r["manifest_sha256"]


def test_build_check_missing_dir(tmp_path):
    ip, qp = _inputs(tmp_path)
    with pytest.raises(ValueError, match="record directory missing"):
        mod.build(ip, qp, tmp_path / "absent", check=True)


def test_build_check_missing_member(tmp_path):
    ip, qp = _inputs(tmp_path)
    out = tmp_path / "out"
    mod.build(ip, qp, out)
    (out / "STATE.json").unlink()
    with pytest.raises(ValueError, match="drift STATE.json"):
        mod.build(ip, qp, out, check=True)


def test_main_prints_summary(tmp_path, capsys):
    ip, qp = _inputs(tmp_path)
    m = _msgs(tmp_path, [{"role": "user", "text": "hello there"}])
    mod.main(["--intake", str(ip), "--bd", str(qp), "--out", str(tmp_path / "o"),
              "--messages", str(m)])
    out = json.loads(capsys.readouterr().out)
    assert out["prompt_count"] == 1


def test_dunder_main_success(tmp_path, monkeypatch, capsys):
    ip, qp = _inputs(tmp_path)
    monkeypatch.setattr(sys, "argv", ["cp_close.py", "--intake", str(ip), "--bd", str(qp),
                                      "--out", str(tmp_path / "o")])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert json.loads(capsys.readouterr().out)["actions"] == 2


def test_dunder_main_fail_closed(tmp_path, monkeypatch, capsys):
    d = intake()
    d["privacy"] = "RAW"
    ip = write(tmp_path / "intake.json", d)
    qp = write(tmp_path / "q.json", queue())
    monkeypatch.setattr(sys, "argv", ["cp_close.py", "--intake", str(ip), "--bd", str(qp),
                                      "--out", str(tmp_path / "o")])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert exc.value.code == 2
    assert "CP_CLOSE_FAIL_CLOSED" in capsys.readouterr().err
