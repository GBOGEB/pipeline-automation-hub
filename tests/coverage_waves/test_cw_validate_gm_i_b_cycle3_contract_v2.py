"""Behavioural tests for mission-control/grand-missions/validate_gm_i_b_cycle3_contract_v2.py."""
import copy
import hashlib
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = MOD_DIR / "validate_gm_i_b_cycle3_contract_v2.py"
CONTRACT = MOD_DIR / "GM_I_B_CYCLE3_PROPAGATION_CONTRACT_v1.json"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_gm_i_b_cycle3_contract_v2", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v2 = _load()
REAL_CONTRACT = json.loads(CONTRACT.read_text(encoding="utf-8"))


def _atom(contract):
    src = contract["source_atom"]
    return {
        "keb_item_id": "KEB-ITEM-0002",
        "object_type": "KEB_KNOWLEDGE_ATOM",
        "source_digest": src["source_digest"],
        "authority_cap": src["authority_cap"],
        "independent_numeric_reproduction": {
            "receipt_sha256": src["cycle2_independent_receipt_sha256"],
            "result": "PASS_INDEPENDENT_C01_C07_7_OF_7",
        },
        "authority_guards": {"authority_transfer": False},
    }


def _run(tmp_path, monkeypatch, capsys, contract=None, atom=None, env_sha=None):
    contract = copy.deepcopy(REAL_CONTRACT) if contract is None else contract
    atom = _atom(REAL_CONTRACT) if atom is None else atom
    c_p = tmp_path / "contract.json"
    a_p = tmp_path / "atom.json"
    out_p = tmp_path / "nested" / "dir" / "receipt.json"
    c_p.write_text(json.dumps(contract), encoding="utf-8")
    a_p.write_text(json.dumps(atom), encoding="utf-8")
    if env_sha is None:
        monkeypatch.delenv("GITHUB_SHA", raising=False)
    else:
        monkeypatch.setenv("GITHUB_SHA", env_sha)
    monkeypatch.setattr(sys, "argv", ["v2", "--contract", str(c_p), "--atom", str(a_p), "--out", str(out_p)])
    rc = v2.main()
    out = json.loads(out_p.read_text(encoding="utf-8"))
    printed = json.loads(capsys.readouterr().out)
    assert printed == out
    return rc, out, contract, atom


def test_digest_is_canonical_sha256():
    x = {"b": 1, "a": [1, 2]}
    expected = hashlib.sha256(b'{"a":[1,2],"b":1}').hexdigest()
    assert v2.digest(x) == expected
    assert v2.digest({"a": [1, 2], "b": 1}) == expected


def test_real_contract_with_matching_atom_passes(tmp_path, monkeypatch, capsys):
    rc, out, contract, atom = _run(tmp_path, monkeypatch, capsys)
    assert rc == 0
    assert out["status"] == "PASS_CONTRACT_SELF_CHECK"
    assert all(out["checks"].values()) and len(out["checks"]) == 12
    assert out["next_action"] == "PROPAGATE_TO_T2_COOLPROP"
    assert out["source_head"] == "LOCAL_UNBOUND"
    assert out["kpi"]["propagation_targets_reached"] == 1
    assert out["kpi"]["propagation_coverage"] == pytest.approx(1 / 3)
    assert out["kpi"]["semantic_parity"] == 1.0
    assert out["kpi"]["reuse_ratio"] == 1.0
    assert out["kpi"]["authority_inversion_count"] == 0
    assert out["contract_sha256"] == v2.digest(contract)
    assert out["atom_sha256"] == v2.digest(atom)
    body = {k: v for k, v in out.items() if k != "receipt_sha256"}
    assert out["receipt_sha256"] == v2.digest(body)
    assert out["created_utc"].endswith("+00:00")
    assert out["authority_transfer"] is False and out["formal_credit_delta"] == 0


def test_github_sha_bound(tmp_path, monkeypatch, capsys):
    _, out, _, _ = _run(tmp_path, monkeypatch, capsys, env_sha="abc123")
    assert out["source_head"] == "abc123"


def _c(path, value):
    c = copy.deepcopy(REAL_CONTRACT)
    node = c
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return c


def _target(c, tid):
    return next(t for t in c["propagation_targets"] if t["id"] == tid)


def _c_target(tid, key, value):
    c = copy.deepcopy(REAL_CONTRACT)
    _target(c, tid)[key] = value
    return c


def _a(path, value):
    a = _atom(REAL_CONTRACT)
    node = a
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return a


@pytest.mark.parametrize("contract,atom,failed", [
    (_c(["mission"], "GM-I-A"), None, "cycle3"),
    (_c(["cycle"], 2), None, "cycle3"),
    (_c(["cycle_ordinal"], "3P#2"), None, "cycle3"),
    (None, _a(["keb_item_id"], "KEB-ITEM-0001"), "atom"),
    (None, _a(["object_type"], "OTHER"), "atom"),
    (None, _a(["source_digest"], "sha256:00"), "digest"),
    (None, _a(["authority_cap"], "A1"), "authority_cap"),
    (None, _a(["independent_numeric_reproduction", "receipt_sha256"], "0"), "cycle2"),
    (None, _a(["independent_numeric_reproduction", "result"], "FAIL"), "cycle2"),
    (_c(["semantic_invariants", "named_clocks"], ["k"]), None, "semantics"),
    (_c(["semantic_invariants", "extra"], True), None, "semantics"),
    (_c_target("T2_COOLPROP", "required_feature_dimension", 5), None, "feature_schema"),
    (_c_target("T2_COOLPROP", "required_feature_schema", [{"name": "T_K", "unit": "C"}]), None, "feature_schema"),
    (_c_target("T1_MISSIONCONTROL", "new_independent_math_implementation_allowed", True), None, "reuse_only"),
    (_c(["generalisation_rules", "consumer_may_implement_duplicate_pca_kernel"], True), None, "reuse_only"),
    (_c(["generalisation_rules", "consumer_may_change_mathematical_semantics"], True), None, "interpretation_guards"),
    (_c(["generalisation_rules", "feature_dimension_is_not_display_dimension"], False), None, "interpretation_guards"),
    (_c(["generalisation_rules", "schema_mapping_alone_is_not_a_pca_result"], False), None, "interpretation_guards"),
    (_c(["kpi_contract", "propagation_targets_total"], 2), None, "kpis"),
    (_c(["kpi_contract", "propagation_depth_target"], 1), None, "kpis"),
    (_c(["kpi_contract", "duplicate_implementation_count_target"], 1), None, "kpis"),
])
def test_single_red_check_defers(tmp_path, monkeypatch, capsys, contract, atom, failed):
    rc, out, _, _ = _run(tmp_path, monkeypatch, capsys, contract=contract, atom=atom)
    assert rc == 1
    assert [k for k, v in out["checks"].items() if not v] == [failed]
    assert out["status"] == "DEFER_CONTRACT_SELF_CHECK"
    assert out["next_action"] == "REPAIR_FIRST_RED"
    assert out["kpi"]["propagation_targets_reached"] == 0
    assert out["kpi"]["propagation_coverage"] == 0.0
    assert out["kpi"]["semantic_parity"] == 0.0
    assert out["kpi"]["reuse_ratio"] == 0.0
    assert out["kpi"]["authority_inversion_count"] == 0


def test_extra_target_breaks_target_set(tmp_path, monkeypatch, capsys):
    c = copy.deepcopy(REAL_CONTRACT)
    c["propagation_targets"].append({"id": "T4_EXTRA", "new_independent_math_implementation_allowed": False})
    rc, out, _, _ = _run(tmp_path, monkeypatch, capsys, contract=c)
    assert rc == 1
    assert [k for k, v in out["checks"].items() if not v] == ["targets"]


@pytest.mark.parametrize("contract,atom", [
    (_c(["authority_transfer"], True), None),
    (_c(["formal_credit_delta"], 1), None),
    (_c(["hard_gate_compensation_allowed"], True), None),
    (None, _a(["authority_guards", "authority_transfer"], True)),
])
def test_authority_failure_counts_inversion(tmp_path, monkeypatch, capsys, contract, atom):
    rc, out, _, _ = _run(tmp_path, monkeypatch, capsys, contract=contract, atom=atom)
    assert rc == 1
    assert [k for k, v in out["checks"].items() if not v] == ["authority"]
    assert out["kpi"]["authority_inversion_count"] == 1


def test_main_guard_exit_code(tmp_path, monkeypatch):
    c_p = tmp_path / "c.json"
    a_p = tmp_path / "a.json"
    c_p.write_text(json.dumps(REAL_CONTRACT), encoding="utf-8")
    a_p.write_text(json.dumps(_atom(REAL_CONTRACT)), encoding="utf-8")
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.setattr(sys, "argv", ["v2", "--contract", str(c_p), "--atom", str(a_p),
                                      "--out", str(tmp_path / "r.json")])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert exc.value.code == 0
