"""Behavioural tests for mission-control/grand-missions/validate_gm_i_c_3pr_mip.py."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GM_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MODULE_PATH = GM_DIR / "validate_gm_i_c_3pr_mip.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cw_validate_gm_i_c_3pr_mip", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod():
    return _load_module()


def _real_packet():
    return json.loads((GM_DIR / "GM_I_C_3PR_MIP_IC3_CONTROL_v1.json").read_text(encoding="utf-8"))


def _real_current():
    return yaml.safe_load((GM_DIR / "GM_I_C_CURRENT_v1.yaml").read_text(encoding="utf-8"))


def _install(mod, monkeypatch, tmp_path, packet, current):
    p = tmp_path / "packet.json"
    c = tmp_path / "current.yaml"
    p.write_text(json.dumps(packet), encoding="utf-8")
    c.write_text(yaml.safe_dump(current), encoding="utf-8")
    monkeypatch.setattr(mod, "PACKET", p)
    monkeypatch.setattr(mod, "CURRENT", c)


def test_require(mod):
    assert mod.require(True, "x") is None
    with pytest.raises(SystemExit) as exc:
        mod.require(False, "bad thing")
    assert str(exc.value) == "FAIL: bad thing"


def test_real_committed_data_passes(mod, capsys):
    assert mod.main() == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["result"] == "PASS_GM_I_C_3PR_MIP_CONTROL"
    assert receipt["global_parent_merge_sha"] == mod.EXPECTED_PARENT_MERGE
    assert receipt["next_predicate"] == "IC3_EXTERNAL_IDENTITY_CONFIGURATION"
    assert receipt["authority_transfer"] is False


def test_receipt_reflects_packet_live_refresh(mod, tmp_path, monkeypatch, capsys):
    packet, current = _real_packet(), _real_current()
    packet["live_refresh"]["provider_sha"] = "f" * 40
    current["provider_current"]["sha"] = "f" * 40
    packet["live_refresh"]["drive_root_id"] = "ROOT-X"
    current["bridge_current"]["drive_root_id"] = "ROOT-X"
    packet["live_refresh"]["drive_manual_connector_direct_children"] = 5
    _install(mod, monkeypatch, tmp_path, packet, current)
    monkeypatch.setattr(sys, "argv", ["v"])
    assert mod.main() == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["provider_sha"] == "f" * 40
    assert receipt["drive_root_id"] == "ROOT-X"
    assert receipt["manual_drive_children"] == 5


def _p(*path_and_value):
    *path, value = path_and_value

    def fn(packet, current):
        node = packet
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    return fn


def _c(*path_and_value):
    *path, value = path_and_value

    def fn(packet, current):
        node = current
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    return fn


def _rank_first(packet, current):
    packet["three_pr"]["Rank"]["ranked_next_predicates"][0]["id"] = "OTHER"


def _layers(packet, current):
    packet["mip"]["Innovate"]["proof_layers"].reverse()


def _unwithhold(name):
    def fn(packet, current):
        packet["explicitly_not_executed"] = [x for x in packet["explicitly_not_executed"] if x != name]
    return fn


def _drop_nonclaim(name):
    def fn(packet, current):
        current["explicit_nonclaims"] = [x for x in current["explicit_nonclaims"] if x != name]
    return fn


CASES = [
    (_p("mission", "GM-I-B"), "packet mission mismatch"),
    (_p("state", "DONE"), "unexpected packet state"),
    (_p("authority_transfer", True), "authority transfer must remain false"),
    (_p("formal_credit_delta", 1), "formal credit delta must remain zero"),
    (_p("hard_gate_compensation_allowed", True), "hard-gate compensation must remain forbidden"),
    (_p("parent_method_control", "method", "X"), "global method parent mismatch"),
    (_p("parent_method_control", "pr", 1), "global parent PR mismatch"),
    (_p("parent_method_control", "merge_sha", "0"), "global parent merge mismatch"),
    (_p("parent_method_control", "exact_proven_head_sha", "0"), "global parent head mismatch"),
    (_p("parent_method_control", "relationship", "DUP"), "local/global authority relationship drift"),
    (_p("live_refresh", "missioncontrol_sha", "0"), "live MissionControl SHA is not the admitted parent"),
    (_p("three_pr", "Refresh", "result", "FAIL"), "3PR Refresh not complete"),
    (_p("three_pr", "Probe", "result", "FAIL"), "3PR Probe not complete"),
    (_p("three_pr", "Rank", "result", "FAIL"), "3PR Rank not complete"),
    (_rank_first, "wrong ranked first predicate"),
    (_p("three_pr", "Rank", "application_repair_rank", "SELECTED"), "application repair was incorrectly selected"),
    (_p("mip", "Modernize", "result", "FAIL"), "MIP Modernize not complete"),
    (_p("mip", "Perpetuate", "result", "FAIL"), "MIP Perpetuate not complete"),
    (_layers, "proof-layer order drift"),
    (_p("kpi_baseline", "application_hardening_merged", False), "merged hardening baseline lost"),
    (_p("kpi_baseline", "manual_drive_root_positive_enumeration", False), "manual root observation lost"),
    (_p("kpi_baseline", "external_auth_issue_open", False), "external auth issue must remain open at this control point"),
    (_p("kpi_baseline", "hosted_ic3_pass_observed", True), "IC3 hosted PASS must remain withheld"),
    (_p("kpi_baseline", "ic3_credit", 1), "IC3 credit must remain zero"),
    (_p("kpi_baseline", "authority_inversion_count", 1), "authority inversion detected"),
    (_p("kpi_baseline", "duplicate_auth_implementation_count", 2), "duplicate auth implementation detected"),
    (_unwithhold("3PC_EXTERNAL_AUTH_TRANSACTION"), "3PC must remain uncredited"),
    (_unwithhold("3P3_CROSS_AGENT_PROPAGATION_PROOF"), "3P3 must remain uncredited"),
    (_c("mission_id", "GM-I-B"), "current pointer mission mismatch"),
    (_c("authority_transfer", True), "current pointer authority transfer weakened"),
    (_c("formal_credit_delta", 1), "current pointer formal credit weakened"),
    (_c("global_method_parent", "pr", 1), "current pointer parent PR mismatch"),
    (_c("global_method_parent", "merge_sha", "0"), "current pointer parent merge mismatch"),
    (_c("global_method_parent", "exact_proven_head_sha", "0"), "current pointer parent head mismatch"),
    (_c("global_method_parent", "relationship", "DUP"), "current pointer relationship drift"),
    (_c("provider_current", "sha", "0"), "provider SHA mismatch"),
    (_c("provider_current", "hardening_pr_state", "OPEN"), "PR11 must be recorded merged"),
    (_c("bridge_current", "drive_root_id", "other"), "Drive root mismatch"),
    (_c("bridge_current", "manual_connector_direct_children", 2), "manual Drive observation count drift"),
    (_c("first_red", "gate", "IC4"), "first red moved without proof"),
    (_drop_nonclaim("NO_3PC_CREDIT"), "3PC nonclaim missing"),
    (_drop_nonclaim("NO_3P3_CREDIT"), "3P3 nonclaim missing"),
]


@pytest.mark.parametrize("mutation,message", CASES)
def test_drift_is_rejected(mod, tmp_path, monkeypatch, capsys, mutation, message):
    packet, current = _real_packet(), _real_current()
    mutation(packet, current)
    _install(mod, monkeypatch, tmp_path, packet, current)
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert str(exc.value) == "FAIL: " + message
    assert capsys.readouterr().out == ""


def test_missing_packet_key_raises_keyerror(mod, tmp_path, monkeypatch):
    packet, current = _real_packet(), _real_current()
    del packet["mip"]
    _install(mod, monkeypatch, tmp_path, packet, current)
    with pytest.raises(KeyError):
        mod.main()
