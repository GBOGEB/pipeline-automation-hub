"""Behavioural tests for mission-control/grand-missions/validate_gm_iv_post_active8_repeat_control.py."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = MOD_DIR / "validate_gm_iv_post_active8_repeat_control.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_gm_iv_post_active8_repeat_control", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()

FIDS = ["GM-IV-F%02d" % i for i in range(1, 9)]
SHAS = {fid: ("%x" % (i + 1)) * 40 for i, fid in enumerate(FIDS)}


def _base():
    registry = {
        "authority_transfer": False,
        "grand_missions": [
            {"id": "GM-III", "state": "RECON_CONTROL"},
            {"id": "GM-IV", "state": "ACTIVE_8_OF_8", "activation_stage": "ACTIVE_8_OF_8", "children": []},
            {"id": "GM-V", "state": "HELD", "children": []},
        ],
    }
    active8 = {"frontier_evidence": {fid: {"repository": "org/" + fid, "target_sha": SHAS[fid]} for fid in FIDS}}
    contract = {
        "required_state": "ACTIVE_8_OF_8",
        "required_activation_stage": "ACTIVE_8_OF_8",
        "promotion_merge_sha": "9" * 40,
        "next_after_success": "NEXT_STEP",
    }
    fleet = {"authority_transfer": False, "validation_checks": [{"result": "PASS"}, {"result": "PASS"}], "validation_check_count": 2}
    capacity = {"structural_gate": "PASS", "gm_iv_state": "ACTIVE_8_OF_8", "gm_v_state": "HELD"}
    return {"registry": registry, "active8": active8, "contract": contract, "fleet": fleet, "capacity": capacity}


def _run(tmp_path, monkeypatch, docs, probe_overrides=None):
    paths = {}
    for name, doc in docs.items():
        p = tmp_path / (name + ".json")
        p.write_text(json.dumps(doc), encoding="utf-8")
        paths[name] = p
    monkeypatch.setattr(m, "REGISTRY", paths["registry"])
    monkeypatch.setattr(m, "ACTIVE8", paths["active8"])
    monkeypatch.setattr(m, "CONTRACT", paths["contract"])
    probe = tmp_path / "probe"
    for fid in FIDS:
        d = probe / fid
        d.mkdir(parents=True, exist_ok=True)
        sha, count = (probe_overrides or {}).get(fid, (SHAS[fid], "3"))
        (d / "HEAD_SHA").write_text(sha + "\n", encoding="utf-8")
        (d / "ENTRY_COUNT").write_text(count + "\n", encoding="utf-8")
    out = tmp_path / "o" / "receipt.json"
    monkeypatch.setattr(sys, "argv", [
        "prog", "--source-sha", "s" * 40, "--fleet-receipt", str(paths["fleet"]),
        "--capacity-receipt", str(paths["capacity"]), "--probe-root", str(probe), "--out", str(out),
    ])
    rc = m.main()
    return rc, out


def test_require_passes_and_fails():
    assert m.require(True, "x") is None
    with pytest.raises(SystemExit) as exc:
        m.require(False, "boom")
    assert str(exc.value) == "FAIL: boom"


def test_load_reads_json(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"a": 1}', encoding="utf-8")
    assert m.load(p) == {"a": 1}


def test_main_pass(tmp_path, monkeypatch, capsys):
    rc, out = _run(tmp_path, monkeypatch, _base())
    assert rc == 0
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["repeat_control_result"] == "PASS_POST_ACTIVE8_REPEAT_CONTROL"
    assert receipt["repeat_control_check_count"] == 10 + 16
    assert receipt["promotion_merge_sha"] == "9" * 40
    assert receipt["next_action"] == "NEXT_STEP"
    assert receipt["source_sha"] == "s" * 40
    f05 = receipt["frontier_runtime_probe_coverage"]["frontiers"]["GM-IV-F05"]
    assert f05 == {
        "repository": "org/GM-IV-F05",
        "expected_sha": SHAS["GM-IV-F05"],
        "observed_sha": SHAS["GM-IV-F05"],
        "entry_count": 3,
        "result": "PASS_EXACT_SHA_NONZERO_SURFACE",
    }
    assert all(c["result"] == "PASS" for c in receipt["repeat_control_checks"])
    assert receipt["repeat_control_checks"][0] == {"check": "canonical_active8_state", "result": "PASS", "detail": "ACTIVE_8_OF_8"}
    assert capsys.readouterr().out.splitlines() == [
        "PASS_GM_IV_POST_ACTIVE8_REPEAT_CONTROL",
        "DEFER_GM_V_MEASURED_CAPACITY",
    ]


def _gm(docs, gid):
    return next(g for g in docs["registry"]["grand_missions"] if g["id"] == gid)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda d: _gm(d, "GM-IV").update(state="RECON"), "FAIL: canonical_active8_state: RECON"),
        (lambda d: _gm(d, "GM-IV").update(activation_stage="X"), "FAIL: canonical_active8_stage: X"),
        (lambda d: _gm(d, "GM-IV").update(children=["c"]), "FAIL: gm_iv_zero_children: ['c']"),
        (lambda d: _gm(d, "GM-III").update(state="ACTIVE"), "FAIL: gm_iii_control_preserved: ACTIVE"),
        (lambda d: _gm(d, "GM-V").update(children=["c"]), "FAIL: gm_v_hard_hold: HELD"),
        (lambda d: d["registry"].update(authority_transfer=True), "FAIL: fleet_authority_zero: False"),
        (lambda d: d["fleet"].update(authority_transfer=None), "FAIL: fleet_authority_zero: False"),
        (lambda d: d["fleet"]["validation_checks"].append({"result": "FAIL"}), "FAIL: fleet_validator_repeat_pass: 2"),
        (lambda d: d["capacity"].update(structural_gate="DEFER"), "FAIL: capacity_structural_gate: DEFER"),
        (lambda d: d["capacity"].update(gm_iv_state="RECON"), "FAIL: capacity_current_active8: RECON"),
        (lambda d: d["capacity"].update(gm_v_state="ACTIVE"), "FAIL: capacity_gm_v_hold: ACTIVE"),
    ],
)
def test_main_fail_messages(tmp_path, monkeypatch, mutate, message):
    docs = _base()
    mutate(docs)
    with pytest.raises(SystemExit) as exc:
        _run(tmp_path, monkeypatch, docs)
    assert str(exc.value) == message
    assert not (tmp_path / "o" / "receipt.json").exists()


def test_main_empty_fleet_checks_pass(tmp_path, monkeypatch):
    docs = _base()
    del docs["fleet"]["validation_checks"]
    rc, _ = _run(tmp_path, monkeypatch, docs)
    assert rc == 0


def test_main_probe_sha_mismatch(tmp_path, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _run(tmp_path, monkeypatch, _base(), {"GM-IV-F03": ("0" * 40, "3")})
    assert str(exc.value) == "FAIL: GM-IV-F03_exact_sha: " + "0" * 40


def test_main_probe_zero_surface(tmp_path, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _run(tmp_path, monkeypatch, _base(), {"GM-IV-F08": (SHAS["GM-IV-F08"], "0")})
    assert str(exc.value) == "FAIL: GM-IV-F08_surface_gt0: 0"


def test_main_probe_non_integer_count(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        _run(tmp_path, monkeypatch, _base(), {"GM-IV-F01": (SHAS["GM-IV-F01"], "many")})


def test_main_real_committed_contracts(tmp_path, monkeypatch):
    # Offline check against the committed registry and contracts: probe receipts are
    # synthesised from the committed ACTIVE8 frontier evidence.
    registry = json.loads((MOD_DIR / "GRAND_MISSION_REGISTRY.json").read_text(encoding="utf-8"))
    active8 = json.loads((MOD_DIR / "GM_IV_ACTIVE8_GOVERNOR_CONTRACT.json").read_text(encoding="utf-8"))
    contract = json.loads((MOD_DIR / "GM_IV_POST_ACTIVE8_REPEAT_CONTROL_CONTRACT.json").read_text(encoding="utf-8"))
    probe = tmp_path / "probe"
    for fid in FIDS:
        d = probe / fid
        d.mkdir(parents=True)
        (d / "HEAD_SHA").write_text(active8["frontier_evidence"][fid]["target_sha"], encoding="utf-8")
        (d / "ENTRY_COUNT").write_text("1", encoding="utf-8")
    fleet = tmp_path / "fleet.json"
    fleet.write_text(json.dumps({"authority_transfer": False, "validation_checks": []}), encoding="utf-8")
    cap = tmp_path / "cap.json"
    cap.write_text(json.dumps({"structural_gate": "PASS", "gm_iv_state": "ACTIVE_8_OF_8", "gm_v_state": "HELD"}), encoding="utf-8")
    out = tmp_path / "out.json"
    monkeypatch.setattr(sys, "argv", [
        "prog", "--source-sha", "r", "--fleet-receipt", str(fleet), "--capacity-receipt", str(cap),
        "--probe-root", str(probe), "--out", str(out),
    ])
    assert m.main() == 0
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["canonical_state"] == registry_state(registry)
    assert receipt["next_action"] == contract["next_after_success"]


def registry_state(registry):
    return next(g for g in registry["grand_missions"] if g["id"] == "GM-IV")["state"]
