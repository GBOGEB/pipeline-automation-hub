"""Behavioural tests for mission-control/grand-missions/validate_gm_i_b_and_launch_control.py."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GM_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MODULE_PATH = GM_DIR / "validate_gm_i_b_and_launch_control.py"
INPUTS = (
    "GRAND_MISSION_REGISTRY.json",
    "GM_FLEET_IMMINENT_LAUNCH_CONTROL_v1.json",
    "GM_IV_F05_F06_BOUNDED_PULSE_CONTRACT.json",
)


def _load_module():
    spec = importlib.util.spec_from_file_location("cw_validate_gm_i_b_and_launch_control", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod():
    return _load_module()


@pytest.fixture
def data_root(tmp_path, mod, monkeypatch):
    root = tmp_path / "gm"
    root.mkdir()
    for name in INPUTS:
        shutil.copyfile(GM_DIR / name, root / name)
    monkeypatch.setattr(mod, "ROOT", root)
    return root


def _run(mod, monkeypatch, out):
    monkeypatch.setattr(sys, "argv", ["validate", "--out", str(out)])
    mod.main()


def _mutate(root, name, fn):
    path = root / name
    doc = json.loads(path.read_text(encoding="utf-8"))
    fn(doc)
    path.write_text(json.dumps(doc), encoding="utf-8")


def _variant(doc, vid):
    gm1 = next(m for m in doc["grand_missions"] if m["id"] == "GM-I")
    return next(v for v in gm1["variants"] if v["id"] == vid)


def _gm(doc, gid):
    return next(m for m in doc["grand_missions"] if m["id"] == gid)


def test_require_passes_and_fails(mod):
    assert mod.require(True, "never") is None
    with pytest.raises(SystemExit) as exc:
        mod.require(False, "boom")
    assert str(exc.value) == "FAIL: boom"


def test_load_reads_json_relative_to_root(mod, tmp_path, monkeypatch):
    (tmp_path / "x.json").write_text('{"a": 1}', encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    assert mod.load("x.json") == {"a": 1}


def test_main_requires_out(mod, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["validate"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 2


def test_real_committed_data_passes(mod, data_root, tmp_path, monkeypatch, capsys):
    out = tmp_path / "nested" / "receipt.json"
    _run(mod, monkeypatch, out)
    assert capsys.readouterr().out.strip() == "PASS_GM_I_B_AND_IMMINENT_LAUNCH_CONTROL"
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["result"] == "PASS_GM_I_B_AND_IMMINENT_LAUNCH_CONTROL"
    assert receipt["checks"]["authority_transfer"] is False
    assert receipt["checks"]["formal_credit_delta"] == 0
    assert receipt["checks"]["gm_v_held"] is True
    assert out.read_text(encoding="utf-8").endswith("\n")


def _drop_gm_v(doc):
    doc["grand_missions"] = doc["grand_missions"][:4]


def _bad_frontier_counts(doc):
    _gm(doc, "GM-V")["frontier_count"] = 32


def _drop_ic(doc):
    gm1 = _gm(doc, "GM-I")
    gm1["variants"] = [v for v in gm1["variants"] if v["id"] != "GM-I-C"]


def _set(vid, key, value):
    def fn(doc):
        _variant(doc, vid)[key] = value
    return fn


def _closure(key, value):
    def fn(doc):
        _variant(doc, "GM-I-B")["keb_closure"][key] = value
    return fn


def _gm_set(gid, key, value):
    def fn(doc):
        _gm(doc, gid)[key] = value
    return fn


REGISTRY_CASES = [
    (_drop_gm_v, "canonical ids changed"),
    (_bad_frontier_counts, "scaling sequence changed"),
    (_drop_ic, "GM-I variants invalid"),
    (_set("GM-I-B", "repository", "x/y"), "I-B provider repo drift"),
    (_set("GM-I-B", "state", "ACTIVE"), "I-B CONTROL posture drift"),
    (_set("GM-I-B", "provider_merge_sha", "0" * 40), "I-B merge SHA drift"),
    (_set("GM-I-B", "exact_federation_head_sha", "0" * 40), "I-B exact federation head drift"),
    (_set("GM-I-B", "original_provider_receipt_digest", "sha256:0"), "I-B provider receipt digest drift"),
    (_closure("abacus_pr", 1), "I-B DOW closure drift"),
    (_closure("codex_atom_id", "KEB-ITEM-9999"), "I-B KEB atom drift"),
    (_closure("state", "OPEN"), "I-B KEB closure drift"),
    (_set("GM-I-B", "authority_transfer", True), "I-B authority guard failed"),
    (_set("GM-I-C", "repository", "x/y"), "I-C provider repo drift"),
    (_set("GM-I-C", "state", "DONE"), "I-C pre-proof state drift"),
    (_set("GM-I-C", "formal_credit_delta", 1), "I-C authority guard failed"),
    (_gm_set("GM-II", "state", "ACTIVE"), "GM-II sentinel state drift"),
    (_gm_set("GM-III", "state", "ACTIVE"), "GM-III state drift"),
    (_gm_set("GM-III", "children", []), "GM-III GEMINI frontier history was rewritten"),
    (_gm_set("GM-IV", "activation_stage", "RECON_4_OF_8"), "GM-IV ACTIVE8 state drift"),
    (_gm_set("GM-IV", "candidate_frontiers", ["GM-IV-F01"]), "GM-IV eight-frontier shape drift"),
    (_gm_set("GM-IV", "children", ["x"]), "GM-IV slot/child drift"),
    (_gm_set("GM-IV", "active_8_of_8_evidence", {}), "GM-IV ACTIVE8 evidence drift"),
    (_gm_set("GM-V", "state", "ACTIVE"), "GM-V hold violated"),
]


@pytest.mark.parametrize("mutation,message", REGISTRY_CASES)
def test_registry_drift_fails(mod, data_root, tmp_path, monkeypatch, mutation, message):
    _mutate(data_root, "GRAND_MISSION_REGISTRY.json", mutation)
    out = tmp_path / "receipt.json"
    with pytest.raises(SystemExit) as exc:
        _run(mod, monkeypatch, out)
    assert str(exc.value).startswith("FAIL: " + message)
    assert not out.exists()


def _pulse(key, value):
    def fn(doc):
        doc[key] = value
    return fn


@pytest.mark.parametrize(
    "mutation,message",
    [
        (_pulse("canonical_state_must_remain", "ACTIVE_8_OF_8"), "historical F05/F06 pulse contract drift"),
        (_pulse("promotion_allowed_by_this_pulse", True), "historical F05/F06 pulse promotion flag drift"),
    ],
)
def test_pulse_contract_drift_fails(mod, data_root, tmp_path, monkeypatch, mutation, message):
    _mutate(data_root, "GM_IV_F05_F06_BOUNDED_PULSE_CONTRACT.json", mutation)
    with pytest.raises(SystemExit) as exc:
        _run(mod, monkeypatch, tmp_path / "r.json")
    assert str(exc.value) == "FAIL: " + message


def _order(idx, key, value):
    def fn(doc):
        doc["launch_order"][idx][key] = value
    return fn


def _post(path, value):
    def fn(doc):
        node = doc["launch_order"][4]["post_promotion_dov"]
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    return fn


def _reorder(doc):
    doc["launch_order"][0]["order"] = 9


LAUNCH_CASES = [
    (_reorder, "launch ordering drift"),
    (_order(1, "state", "PENDING"), "I-B closure/sync drift"),
    (_order(2, "state", "IDLE"), "I-B sentinel drift"),
    (_order(3, "id", "OTHER"), "GM-IV historical pulse drift"),
    (_order(4, "state", "PENDING"), "ACTIVE8 post-control state drift"),
    (_post(["repeat_control", "result"], "FAIL"), "ACTIVE8 repeat CONTROL evidence drift"),
    (_post(["runtime_capability_capacity", "result"], "FAIL"), "ACTIVE8 runtime capability capacity drift"),
    (_post(["runtime_capability_capacity", "scope"], "CONCURRENCY"), "capacity scope drift"),
    (_post(["operational_availability"], "AVAILABLE"), "operational availability gate drift"),
    (_post(["gm_v_launch_authorized"], True), "GM-V launch must remain unauthorized"),
    (_order(5, "policy", "always_on"), "sentinel policy drift"),
    (_order(6, "state", "LAUNCHED"), "GM-V launch-order hold drift"),
    (_order(6, "current_first_red", "NONE"), "GM-V first red drift"),
]


@pytest.mark.parametrize("mutation,message", LAUNCH_CASES)
def test_launch_control_drift_fails(mod, data_root, tmp_path, monkeypatch, mutation, message):
    _mutate(data_root, "GM_FLEET_IMMINENT_LAUNCH_CONTROL_v1.json", mutation)
    with pytest.raises(SystemExit) as exc:
        _run(mod, monkeypatch, tmp_path / "r.json")
    assert str(exc.value) == "FAIL: " + message


def test_missing_input_file_raises(mod, data_root, tmp_path, monkeypatch):
    (data_root / "GM_IV_F05_F06_BOUNDED_PULSE_CONTRACT.json").unlink()
    with pytest.raises(FileNotFoundError):
        _run(mod, monkeypatch, tmp_path / "r.json")
