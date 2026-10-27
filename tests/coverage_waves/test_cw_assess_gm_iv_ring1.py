"""Behavioural tests for mission-control/grand-missions/assess_gm_iv_ring1.py."""
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = MOD_DIR / "assess_gm_iv_ring1.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_assess_gm_iv_ring1", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ring1 = _load()

F01_SHA = "1" * 40
F02_SHA = "2" * 40
ACTION_OK = 'runs:\n  using: "composite"\n  steps:\n    - uses: actions/attest@abc\n'
README_OK = "This action is a thin Wrapper.\nnew implementations should use `actions/attest` instead.\n"
ENV_KEYS = ("GITHUB_REPOSITORY", "SOURCE_SHA", "GITHUB_SHA", "GITHUB_RUN_ID")


def _registry(gm_iv_state="ACTIVE_8_OF_8", gm_iv_children=None, gm_v_state="HELD", gm_v_children=None):
    return {
        "grand_missions": [
            {"id": "GM-IV", "state": gm_iv_state, "children": [] if gm_iv_children is None else gm_iv_children},
            {"id": "GM-V", "state": gm_v_state, "children": [] if gm_v_children is None else gm_v_children},
        ]
    }


def _ring(authority_transfer=False, children_bound=False):
    return {
        "authority_transfer": authority_transfer,
        "children_bound": children_bound,
        "frontiers": [
            {"slot": "GM-IV-F01", "repository": "GBOGEB/f01", "source_sha": F01_SHA},
            {"slot": "GM-IV-F02", "repository": "GBOGEB/f02", "source_sha": F02_SHA},
        ],
    }


def _f01(sha=F01_SHA, file_count=5, dirty=0):
    return {"repo": {"sha": sha, "dirty_file_count": dirty}, "census": {"file_count": file_count}}


def _inputs(tmp_path, f01, action, readme):
    f01_p = tmp_path / "f01.json"
    act_p = tmp_path / "action.yml"
    rd_p = tmp_path / "README.md"
    out_p = tmp_path / "out" / "receipt.json"
    out_p.parent.mkdir(exist_ok=True)
    f01_p.write_text(json.dumps(f01), encoding="utf-8")
    act_p.write_text(action, encoding="utf-8")
    rd_p.write_text(readme, encoding="utf-8")
    argv = ["assess_gm_iv_ring1.py", "--f01-receipt", str(f01_p), "--f02-action", str(act_p),
            "--f02-readme", str(rd_p), "--out", str(out_p)]
    return argv, out_p


def _run(tmp_path, monkeypatch, capsys, registry=None, ring=None, f01=None, action=ACTION_OK,
         readme=README_OK, env=None):
    reg_p = tmp_path / "registry.json"
    ring_p = tmp_path / "ring.json"
    reg_p.write_text(json.dumps(registry if registry is not None else _registry()), encoding="utf-8")
    ring_p.write_text(json.dumps(ring if ring is not None else _ring()), encoding="utf-8")
    monkeypatch.setattr(ring1, "REGISTRY", reg_p)
    monkeypatch.setattr(ring1, "RING", ring_p)
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    argv, out_p = _inputs(tmp_path, f01 if f01 is not None else _f01(), action, readme)
    monkeypatch.setattr(sys, "argv", argv)
    code = None
    try:
        ring1.main()
    except SystemExit as exc:
        code = exc.code
    receipt = json.loads(out_p.read_text(encoding="utf-8"))
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return code, receipt, summary


def _checks(receipt):
    return {c["check"]: c["result"] for c in receipt["checks"]}


def test_load_reads_json(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"a": [1, 2]}', encoding="utf-8")
    assert ring1.load(str(p)) == {"a": [1, 2]}


def test_all_pass_yields_pilot_and_reference(tmp_path, monkeypatch, capsys):
    code, receipt, summary = _run(tmp_path, monkeypatch, capsys)
    assert code is None
    assert receipt["result"] == "PASS"
    assert receipt["pilot_gate"] == "READY_F01_ONLY"
    assert receipt["dispositions"]["GM-IV-F01"]["disposition"] == "PILOT"
    assert receipt["dispositions"]["GM-IV-F01"]["next_crew"] == ["ENGINEER", "SMOKER", "QA"]
    assert receipt["dispositions"]["GM-IV-F01"]["repository"] == "GBOGEB/f01"
    assert receipt["dispositions"]["GM-IV-F02"]["disposition"] == "REFERENCE"
    assert receipt["dispositions"]["GM-IV-F02"]["source_sha"] == F02_SHA
    assert set(_checks(receipt).values()) == {"PASS"}
    assert receipt["repo"] == "LOCAL"
    assert receipt["source_sha"] == "UNKNOWN"
    assert receipt["run_id"] == "LOCAL"
    assert receipt["current_mission_state"] == "ACTIVE_8_OF_8"
    assert summary == {
        "result": "PASS", "pilot_gate": "READY_F01_ONLY", "current_mission_state": "ACTIVE_8_OF_8",
        "dispositions": {"GM-IV-F01": "PILOT", "GM-IV-F02": "REFERENCE"}, "source_sha": "UNKNOWN",
    }


def test_env_identity_uses_github_sha_when_no_source_sha(tmp_path, monkeypatch, capsys):
    _, receipt, _ = _run(tmp_path, monkeypatch, capsys, env={
        "GITHUB_REPOSITORY": "o/r", "GITHUB_SHA": "gsha", "GITHUB_RUN_ID": "77"})
    assert (receipt["repo"], receipt["source_sha"], receipt["run_id"]) == ("o/r", "gsha", "77")


def test_env_source_sha_overrides_github_sha(tmp_path, monkeypatch, capsys):
    _, receipt, _ = _run(tmp_path, monkeypatch, capsys, env={"SOURCE_SHA": "ssha", "GITHUB_SHA": "gsha"})
    assert receipt["source_sha"] == "ssha"


@pytest.mark.parametrize("f01", [
    _f01(sha="9" * 40),
    _f01(file_count=0),
    _f01(dirty=2),
    {},
])
def test_f01_failure_parks_and_withholds(tmp_path, monkeypatch, capsys, f01):
    code, receipt, summary = _run(tmp_path, monkeypatch, capsys, f01=f01)
    assert code == 1
    assert receipt["result"] == "FAIL"
    assert _checks(receipt)["04_f01_exact_runtime_receipt"] == "FAIL"
    d = receipt["dispositions"]["GM-IV-F01"]
    assert d["disposition"] == "PARK"
    assert d["reason"] == "bounded executable proof failed"
    assert d["next_crew"] == []
    assert receipt["pilot_gate"] == "WITHHELD"
    assert summary["dispositions"]["GM-IV-F01"] == "PARK"


@pytest.mark.parametrize("action,readme", [
    ('using: "node20"\nuses: actions/attest@abc\n', README_OK),
    ('using: "composite"\n', README_OK),
    (ACTION_OK, "new implementations should use `actions/attest`\n"),
    (ACTION_OK, "a wrapper only\n"),
])
def test_f02_wrapper_failure_parks(tmp_path, monkeypatch, capsys, action, readme):
    code, receipt, _ = _run(tmp_path, monkeypatch, capsys, action=action, readme=readme)
    assert code == 1
    assert _checks(receipt)["05_f02_wrapper_contract"] == "FAIL"
    assert receipt["dispositions"]["GM-IV-F02"]["disposition"] == "PARK"
    assert receipt["dispositions"]["GM-IV-F02"]["reason"] == "wrapper boundary not proven"
    # F01 still passes, but any failed check withholds the pilot gate.
    assert receipt["dispositions"]["GM-IV-F01"]["disposition"] == "PILOT"
    assert receipt["pilot_gate"] == "WITHHELD"


@pytest.mark.parametrize("state", [
    "STAGED_ACTIVE_RECON_2_OF_8", "STAGED_ACTIVE_PILOT_2_OF_8", "STAGED_ACTIVE_RECON_4_OF_8"])
def test_allowed_forward_stages_pass(tmp_path, monkeypatch, capsys, state):
    code, receipt, _ = _run(tmp_path, monkeypatch, capsys, registry=_registry(gm_iv_state=state))
    assert code is None
    assert receipt["current_mission_state"] == state


@pytest.mark.parametrize("registry,ring,check", [
    (_registry(gm_iv_state="DORMANT"), _ring(), "01_gm_iv_stage_not_regressed"),
    (_registry(gm_iv_children=["x"]), _ring(), "02_no_children_bound"),
    (_registry(gm_v_state="ACTIVE"), _ring(), "03_gm_v_held"),
    (_registry(gm_v_children=["y"]), _ring(), "03_gm_v_held"),
    (_registry(), _ring(authority_transfer=True), "06_no_authority_transfer"),
    (_registry(), _ring(children_bound=True), "06_no_authority_transfer"),
])
def test_governance_failures(tmp_path, monkeypatch, capsys, registry, ring, check):
    code, receipt, summary = _run(tmp_path, monkeypatch, capsys, registry=registry, ring=ring)
    assert code == 1
    failed = [n for n, r in _checks(receipt).items() if r == "FAIL"]
    assert failed == [check]
    assert receipt["pilot_gate"] == "WITHHELD"
    assert summary["result"] == "FAIL"
    assert receipt["authority_transfer"] is False
    assert receipt["gm_v_state"] == "HELD"


def test_real_committed_registry_and_ring_via_main_guard(tmp_path, monkeypatch):
    """Offline run of the script entry point against the committed registry and ring recon."""
    real_ring = json.loads((MOD_DIR / "GM_IV_RING1_RECON.json").read_text(encoding="utf-8"))
    sha = {f["slot"]: f["source_sha"] for f in real_ring["frontiers"]}["GM-IV-F01"]
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    argv, out_p = _inputs(tmp_path, _f01(sha=sha), ACTION_OK, README_OK)
    monkeypatch.setattr(sys, "argv", argv)
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    receipt = json.loads(out_p.read_text(encoding="utf-8"))
    assert receipt["result"] == "PASS"
    assert receipt["dispositions"]["GM-IV-F01"]["source_sha"] == sha
    assert receipt["current_mission_state"] in {
        "STAGED_ACTIVE_RECON_2_OF_8", "STAGED_ACTIVE_PILOT_2_OF_8", "STAGED_ACTIVE_RECON_4_OF_8", "ACTIVE_8_OF_8"}
