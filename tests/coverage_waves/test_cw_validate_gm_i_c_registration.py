"""Behavioural tests for mission-control/grand-missions/validate_gm_i_c_registration.py."""
from __future__ import annotations

import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "grand-missions" / "validate_gm_i_c_registration.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_gm_i_c_registration", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()

EVIDENCE = {
    "gemini_hooks_pr": 9,
    "gemini_hooks_merge_sha": m.PR9_MERGE,
    "drive_ingress_pr": 10,
    "drive_ingress_head_sha": m.PR10_HEAD,
    "drive_ingress_merge_sha": m.PR10_MERGE,
    "drive_ingress_hardening_pr": 11,
    "drive_ingress_hardening_head_sha": m.PR11_HEAD,
    "hosted_drive_pass": "WITHHELD_PENDING_RECEIPT",
}
FIRST_RED = "IC3_AUTH_REAL_HOSTED_GT0_STEP_DRIVE_INGRESS_PASS"
GATE_NAMES = ["REGISTER", "PROVIDER", "BRIDGE", "AUTH", "CONSUMER_A",
              "CONSUMER_B", "PARITY", "ROUNDTRIP", "ADVERSARIAL", "CONTROL"]


def _official():
    return {
        "canonical_grand_missions": [{"id": i} for i in m.CANONICAL_GM_IDS],
        "variants": [
            {"id": "GM-I-B"},
            {
                "id": "GM-I-C",
                "parent": "GM-I",
                "number": "1-C",
                "type": "GRAND_MISSION_VARIANT",
                "provider": "GBOGEB/GEMINI",
                "state": "ACTIVE_FIRST_RED",
                "authority_transfer": False,
                "formal_credit_delta": 0,
                "official_control": m.EXPECTED_CONTROL,
                "crew_allocation": m.EXPECTED_CREW,
                "first_red": FIRST_RED,
                "implementation_evidence": dict(EVIDENCE),
            },
        ],
    }


def _canonical():
    ic = {
        "id": "GM-I-C",
        "repository": "GBOGEB/GEMINI",
        "state": "ACTIVE_FIRST_RED",
        "provider_pr": 9,
        "provider_merge_sha": m.PR9_MERGE,
        "drive_ingress_pr": 10,
        "drive_ingress_exact_head_sha": m.PR10_HEAD,
        "drive_ingress_merge_sha": m.PR10_MERGE,
        "drive_ingress_hardening_pr": 11,
        "drive_ingress_hardening_exact_head_sha": m.PR11_HEAD,
        "hosted_drive_pass": EVIDENCE["hosted_drive_pass"],
        "official_control": m.EXPECTED_CONTROL,
        "crew_allocation": m.EXPECTED_CREW,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "first_red": FIRST_RED,
    }
    gms = []
    for gid in m.CANONICAL_GM_IDS:
        row = {"id": gid}
        if gid == "GM-I":
            row["variants"] = [{"id": "GM-I-A"}, {"id": "GM-I-B"}, ic]
        if gid == "GM-III":
            row["children"] = ["GBOGEB/GEMINI"]
        gms.append(row)
    return {"grand_missions": gms}


def _control():
    return {
        "mission_id": "GM-I-C",
        "parent": "GM-I",
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "first_red": {"gate": "IC3_AUTH", "owner": "S03_DOCKMASTER"},
        "provider_evidence": {
            "gemini_hooks_pr": {"pr": 9, "merge_sha": m.PR9_MERGE},
            "drive_ingress_pr": {"pr": 10, "exact_head_sha": m.PR10_HEAD, "merge_sha": m.PR10_MERGE},
            "drive_ingress_hardening_pr": {"pr": 11, "exact_head_sha": m.PR11_HEAD},
        },
        "mission_gates": [
            {"id": f"IC{i}_{n}", "current": {3: "FIRST_RED"}.get(i, "NOT_STARTED" if i in (5, 9) else "PASS")}
            for i, n in enumerate(GATE_NAMES)
        ],
    }


def _crew():
    return {
        "active_crew": [{"crew_id": c} for c in ["U01", "U02", "U04", "U06", "U08", "S01", "S03", "S06"]],
        "first_red_routing": {
            "zero_step_or_no_runner": {"owner": "S03", "forbidden_initial_roles": ["S02", "S05"]},
        },
        "scout_reader_policy": {
            "conceptual_roles": [
                {"crew_id": "C01", "control_eligible": False},
                {"crew_id": "C02", "control_eligible": False},
            ],
        },
        "runtime_workers": [
            {"id": w, "is_crew": False}
            for w in ["GOOGLE_WIF_PRINCIPAL", "GOOGLE_DRIVE_BRIDGE", "GITHUB_HOSTED_RUNNER",
                      "CHATGPT_DRIVE_CONSUMER", "SECOND_EXTERNAL_CONSUMER"]
        ],
    }


def _ic_official(d):
    return d["variants"][1]


def _ic_canonical(d):
    return d["grand_missions"][0]["variants"][2]


@pytest.fixture
def env(tmp_path, monkeypatch):
    paths = {
        "control": tmp_path / "control.yaml",
        "crew": tmp_path / "crew.yaml",
        "official": tmp_path / "official.yaml",
        "canonical": tmp_path / "canonical.json",
    }
    data = {"control": _control(), "crew": _crew(), "official": _official(), "canonical": _canonical()}

    def write():
        for k in ("control", "crew", "official"):
            paths[k].write_text(yaml.safe_dump(data[k]), encoding="utf-8")
        paths["canonical"].write_text(json.dumps(data["canonical"]), encoding="utf-8")

    write()
    monkeypatch.setattr(m, "MISSION_CONTROL", paths["control"])
    monkeypatch.setattr(m, "CREW", paths["crew"])
    monkeypatch.setattr(m, "OFFICIAL", paths["official"])
    monkeypatch.setattr(m, "CANONICAL", paths["canonical"])
    return data, write


def test_require_passes_and_fails():
    m.require(True, "unused")
    with pytest.raises(SystemExit, match="FAIL: boom"):
        m.require(False, "boom")


def test_load_helpers(tmp_path):
    y = tmp_path / "a.yaml"
    y.write_text("k: [1, 2]\n", encoding="utf-8")
    j = tmp_path / "a.json"
    j.write_text('{"k": 1}', encoding="utf-8")
    assert m.load_yaml(y) == {"k": [1, 2]}
    assert m.load_json(j) == {"k": 1}


def test_main_passes_and_reports(env, capsys):
    m.main()
    out = json.loads(capsys.readouterr().out)
    assert out["result"] == "PASS_GM_I_C_REGISTRATION"
    assert out["gate_count"] == 10
    assert out["active_crew_count"] == 8
    assert out["hosted_drive_pass"] == EVIDENCE["hosted_drive_pass"]
    assert out["first_red"] == FIRST_RED


def _set(getter, key, value):
    def mut(data):
        getter(data)[key] = value
    return mut


MUTATIONS = [
    ("official", lambda d: d["canonical_grand_missions"].pop(), "canonical GM namespace changed"),
    ("canonical", lambda d: d["grand_missions"].append({"id": "GM-VI"}), "canonical JSON GM namespace"),
    ("official", lambda d: d["variants"].pop(0), "GM-I-B disappeared"),
    ("official", lambda d: d["variants"].pop(1), "GM-I-C is not registered"),
    ("canonical", lambda d: d["grand_missions"][0]["variants"].pop(0), "canonical GM-I variants invalid"),
    ("official", _set(_ic_official, "parent", "GM-II"), "parent must remain GM-I"),
    ("official", _set(_ic_official, "provider", "X/Y"), "official provider drift"),
    ("official", _set(_ic_official, "authority_transfer", True), "authority transfer must remain false"),
    ("official", _set(_ic_official, "official_control", "x.yaml"), "official control path drift"),
    ("official", lambda d: _ic_official(d)["implementation_evidence"].update(hosted_drive_pass="PASS"),
     "hosted Drive PASS must remain withheld"),
    ("official", _set(_ic_official, "first_red", "OTHER"), "unexpected first red"),
    ("official", lambda d: _ic_official(d)["implementation_evidence"].update(drive_ingress_merge_sha="0" * 40),
     "PR10 merge drift"),
    ("canonical", _set(_ic_canonical, "state", "DONE"), "GM-I-C state mismatch"),
    ("canonical", _set(_ic_canonical, "drive_ingress_hardening_exact_head_sha", "x"), "canonical PR11 head mismatch"),
    ("canonical", _set(_ic_canonical, "formal_credit_delta", 1), "canonical GM-I-C formal credit weakened"),
    ("canonical", lambda d: d["grand_missions"][2].update(children=[]), "GM-III GEMINI frontier history"),
    ("control", _set(lambda d: d, "mission_id", "GM-I-D"), "control mission ID mismatch"),
    ("control", lambda d: d["first_red"].update(owner="S02"), "IC3 owner must remain Dockmaster"),
    ("control", lambda d: d["provider_evidence"]["drive_ingress_pr"].update(merge_sha="x"), "control PR10 merge mismatch"),
    ("control", lambda d: d["mission_gates"].reverse(), "gate order changed"),
    ("control", lambda d: d["mission_gates"][3].update(current="PASS"), "IC3 must remain first red"),
    ("control", lambda d: d["mission_gates"][9].update(current="PASS"), "CONTROL cannot be pre-credited"),
    ("crew", lambda d: d["active_crew"].append({"crew_id": "S02"}), "unexpected active crew"),
    ("crew", lambda d: d["first_red_routing"]["zero_step_or_no_runner"].update(owner="S02"), "zero-step must route"),
    ("crew", lambda d: d["first_red_routing"]["zero_step_or_no_runner"].update(forbidden_initial_roles=["S02"]),
     "zero-step guard weakened"),
    ("crew", lambda d: d["scout_reader_policy"]["conceptual_roles"][1].update(control_eligible=True),
     "conceptual Reader"),
    ("crew", lambda d: d["runtime_workers"][4].update(is_crew=True), "SECOND_EXTERNAL_CONSUMER must not be treated"),
]


@pytest.mark.parametrize("target,mutate,message", MUTATIONS, ids=[x[2] for x in MUTATIONS])
def test_main_fails_closed_on_drift(env, target, mutate, message):
    data, write = env
    mutate(data[target])
    write()
    with pytest.raises(SystemExit) as exc:
        m.main()
    assert message in str(exc.value)
    assert str(exc.value).startswith("FAIL: ")


def test_real_committed_registration_via_cli(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(MODULE_PATH)])
    runpy.run_path(str(MODULE_PATH), run_name="__main__")
    out = json.loads(capsys.readouterr().out)
    assert out["result"] == "PASS_GM_I_C_REGISTRATION"
    assert out["authority_transfer"] is False
