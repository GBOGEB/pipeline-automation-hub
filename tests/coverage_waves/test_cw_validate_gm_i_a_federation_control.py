"""Behavioural tests for mission-control/grand-missions/validate_gm_i_a_federation_control.py."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GM_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = GM_DIR / "validate_gm_i_a_federation_control.py"
PROVIDER = "47cc8dced9278d50714ac39ef0a2edab7458c6a0"
ATTEST = "132ff84a3502f5ce39d4698fa772e98f7e8fba8e52587e698e8ea419197e1398"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_gm_i_a_federation_control", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod():
    return _load()


def _control(dow_state="PASS", dow_credit=1, keb_state="PASS", keb_credit=1, pass_n=2, wait_n=0):
    return {
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "provider": {"source_head_sha": PROVIDER},
        "attestation": {"content_sha256": ATTEST},
        "federation_bridges": [
            {"id": "GM-I-A-BRIDGE-DOW", "consumer_repo": "GBOGEB/ABACUS", "compensates_other_bridge": False,
             "downstream_credit": dow_credit, "runtime_state": dow_state},
            {"id": "GM-I-A-BRIDGE-KEB", "consumer_repo": "GBOGEB/CODEX", "compensates_other_bridge": False,
             "downstream_credit": keb_credit, "runtime_state": keb_state},
        ],
        "fanout": {"registered_consumers": 2, "runtime_pass_consumers": pass_n, "runtime_wait_consumers": wait_n},
        "authority_guards": ["BRIDGE_RESULTS_ARE_NON_COMPENSATING"],
    }


def _topology(dow_credit=1, keb_credit=1):
    return {
        "provider": {"attestation_sha256": ATTEST, "state": "PASS"},
        "edges": [
            {"id": "DOW", "to": "GBOGEB/ABACUS", "credit": dow_credit},
            {"id": "KEB", "to": "GBOGEB/CODEX", "credit": keb_credit},
        ],
    }


def _run(mod, monkeypatch, tmp_path, control, topology):
    c = tmp_path / "control.yaml"
    t = tmp_path / "topology.json"
    # JSON is valid YAML, so the control file can be written as JSON.
    c.write_text(json.dumps(control), encoding="utf-8")
    t.write_text(json.dumps(topology), encoding="utf-8")
    out = tmp_path / "receipts" / "sentinel.json"
    monkeypatch.setattr(mod, "CONTROL", c)
    monkeypatch.setattr(mod, "TOPOLOGY", t)
    monkeypatch.setattr(mod, "OUT", out)
    mod.main()
    return json.loads(out.read_text())


def test_all_bridges_pass(mod, monkeypatch, tmp_path):
    r = _run(mod, monkeypatch, tmp_path, _control(), _topology())
    assert r["status"] == "PASS"
    assert (r["runtime_pass_edges"], r["runtime_wait_edges"], r["runtime_red_edges"]) == (2, 0, 0)
    assert r["registered_edges"] == 2
    assert r["authority_transfer"] is False and r["formal_credit_delta"] == 0
    assert "DOW_AND_KEB_DISTINCT" in r["invariants"]


def test_wait_and_red_bridges_are_counted(mod, monkeypatch, tmp_path):
    control = _control(dow_state="WAIT_RUNNER", dow_credit=0, keb_state="FAILURE", keb_credit=0, pass_n=0, wait_n=1)
    r = _run(mod, monkeypatch, tmp_path, control, _topology(0, 0))
    assert (r["runtime_pass_edges"], r["runtime_wait_edges"], r["runtime_red_edges"]) == (0, 1, 1)


@pytest.mark.parametrize("state", ["QUEUED", "BLOCKED"])
def test_other_waiting_states(mod, monkeypatch, tmp_path, state):
    control = _control(dow_state=state, dow_credit=0, pass_n=1, wait_n=1)
    r = _run(mod, monkeypatch, tmp_path, control, _topology(0, 1))
    assert r["runtime_wait_edges"] == 1 and r["runtime_pass_edges"] == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c, t: c.__setitem__("authority_transfer", True),
        lambda c, t: c.__setitem__("formal_credit_delta", 1),
        lambda c, t: c["provider"].__setitem__("source_head_sha", "0" * 40),
        lambda c, t: c["attestation"].__setitem__("content_sha256", "0"),
        lambda c, t: t["provider"].__setitem__("attestation_sha256", "0"),
        lambda c, t: t["provider"].__setitem__("state", "FAIL"),
        lambda c, t: c["federation_bridges"].pop(),
        lambda c, t: t["edges"][1].__setitem__("id", "XYZ"),
        lambda c, t: c["federation_bridges"][0].__setitem__("consumer_repo", "GBOGEB/OTHER"),
        lambda c, t: t["edges"][0].__setitem__("to", "GBOGEB/OTHER"),
        lambda c, t: c["federation_bridges"][0].__setitem__("compensates_other_bridge", True),
        lambda c, t: t["edges"][0].__setitem__("credit", 5),
        lambda c, t: c["fanout"].__setitem__("registered_consumers", 3),
        lambda c, t: c["fanout"].__setitem__("runtime_pass_consumers", 1),
        lambda c, t: c["fanout"].__setitem__("runtime_wait_consumers", 1),
        lambda c, t: c.__setitem__("authority_guards", []),
    ],
)
def test_invariant_violations_raise(mod, monkeypatch, tmp_path, mutate):
    c, t = _control(), _topology()
    mutate(c, t)
    with pytest.raises(AssertionError):
        _run(mod, monkeypatch, tmp_path, c, t)
    assert not (tmp_path / "receipts" / "sentinel.json").exists()


def test_pass_state_with_zero_credit_raises(mod, monkeypatch, tmp_path):
    with pytest.raises(AssertionError):
        _run(mod, monkeypatch, tmp_path, _control(dow_credit=0), _topology(0, 1))


def test_wait_state_with_credit_raises(mod, monkeypatch, tmp_path):
    with pytest.raises(AssertionError):
        _run(mod, monkeypatch, tmp_path, _control(dow_state="QUEUED", pass_n=1, wait_n=1), _topology())


def test_red_state_with_credit_raises(mod, monkeypatch, tmp_path):
    with pytest.raises(AssertionError):
        _run(mod, monkeypatch, tmp_path, _control(dow_state="FAILURE", pass_n=1), _topology())


def test_real_committed_control_and_topology(mod, monkeypatch, tmp_path):
    out = tmp_path / "real" / "receipt.json"
    monkeypatch.setattr(mod, "OUT", out)
    mod.main()
    r = json.loads(out.read_text())
    assert r["status"] == "PASS"
    assert r["runtime_pass_edges"] == 2 and r["runtime_red_edges"] == 0
