"""Behavioural tests for mission-control/grand-missions/validate_gm_i_b_cycle3_propagation_proof.py."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = MOD_DIR / "validate_gm_i_b_cycle3_propagation_proof.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_gm_i_b_cycle3_propagation_proof", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()

TESTED_HEAD = "b2f6fc4e8760c3d6fe608f6673e4a4155e116233"
RECEIPT_SHA = "713e4ba99bd1aff7240e4f1e02956d45073ace20ac09c05d7cd9af310a4796b8"
SCHEMA_SHA = "24b193bb17ce6f9cb717e8f7a31b54eb2e8f451edf7b83869dd9854ea95f8a93"
MATRIX_SHA = "ae21df40120eaba36a84140e2b6dc9e305ee3b6d1784b60d0686666516dabef5"
# The real CoolProp feature matrix lives in another repository; this sentinel
# matrix is mapped to the pinned digest by a canonical_sha wrapper (see fixture).
SENTINEL_MATRIX = [["sentinel", 1, 2, 3, 4, 5]]


def _semantics():
    return {
        "component_assignment_precedes_sign_alignment": True,
        "raw_pca_loading_sign_is_not_physical_direction": True,
        "attenuation_toward_parity_is_distinct_from_direction_reversal": True,
        "small_eigengap_requires_subspace_context": True,
        "temporal_state_adjacency_does_not_require_equal_wall_time_or_exposure_age_steps": True,
        "named_clocks": list(m.CLOCKS),
    }


def _docs():
    kpi_contract = {
        "propagation_coverage_target": 1.0,
        "semantic_parity_target": 1.0,
        "reuse_ratio_target": 1.0,
        "duplicate_implementation_count_target": 0,
        "child_disposition_coverage_target": 1.0,
        "propagation_depth_target": 2,
        "authority_inversion_count_target": 0,
    }
    contract = {
        "mission": "GM-I-B",
        "cycle": 3,
        "source_atom": {"keb_item_id": "KEB-ITEM-0002", "merge_sha": m.ATOM_MERGE},
        "semantic_invariants": _semantics(),
        "propagation_targets": [
            {
                "id": "T1_MISSIONCONTROL",
                "required_disposition": "PASS_CONTRACT_SELF_CHECK",
                "new_independent_math_implementation_allowed": False,
            },
            {
                "id": "T2_COOLPROP",
                "required_disposition": "ACCEPT_SCHEMA_ADAPTER_ONLY",
                "required_feature_dimension": 6,
                "required_feature_schema": copy.deepcopy(m.EXPECTED_FEATURES),
            },
            {"id": "T3_QPS_TRIAGE", "required_disposition": "ACCEPT_DIAGNOSTIC_PROPAGATION_ONLY"},
        ],
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "hard_gate_compensation_allowed": False,
        "kpi_contract": kpi_contract,
    }
    atom = {
        "keb_item_id": "KEB-ITEM-0002",
        "knowledge_claims": {
            "component_assignment_precedes_sign_alignment": True,
            "raw_pca_loading_sign_is_not_physical_direction": True,
            "attenuation_toward_parity_is_distinct_from_direction_reversal": True,
            "small_eigengap_requires_subspace_context": True,
            "temporal_state_adjacency_does_not_require_equal_wall_time_or_exposure_age_steps": True,
            "named_clocks_preserved": list(m.CLOCKS),
        },
    }
    cool = {
        "status": "ACCEPT_SCHEMA_ADAPTER_ONLY",
        "missioncontrol_contract": {"merge_sha": m.CONTRACT_MERGE},
        "source_atom": {"keb_item_id": "KEB-ITEM-0002"},
        "feature_dimension": 6,
        "feature_schema": copy.deepcopy(m.EXPECTED_FEATURES),
        "feature_matrix": copy.deepcopy(SENTINEL_MATRIX),
        "semantic_invariants": _semantics(),
        "generalisation": {
            "computes_pca": False,
            "imports_gg_MATH": False,
            "imports_ABACUS_temporal_PCA": False,
            "duplicate_implementation_count": 0,
        },
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "engineering_authority_created": False,
        "hard_gate_compensation_allowed": False,
        "coolprop_transaction": {"tested_exact_head": TESTED_HEAD, "runtime_receipt_sha256": RECEIPT_SHA},
    }
    qps = {
        "status": "ACCEPT_DIAGNOSTIC_PROPAGATION_ONLY",
        "missioncontrol_contract": {"merge_sha": m.CONTRACT_MERGE},
        "source_atom": {"merge_sha": m.ATOM_MERGE},
        "coolprop_child": {
            "attestation_merge_sha": m.COOLPROP_MERGE,
            "attestation_git_blob_sha1": m.COOLPROP_BLOB,
            "tested_exact_head": TESTED_HEAD,
            "runtime_receipt_sha256": RECEIPT_SHA,
        },
        "feature_contract": {
            "schema_canonical_sha256": SCHEMA_SHA,
            "feature_matrix_canonical_sha256": MATRIX_SHA,
            "schema": copy.deepcopy(m.EXPECTED_FEATURES),
        },
        "semantic_invariants": _semantics(),
        "qps_consumption_guards": {
            "computes_pca": False,
            "duplicates_gg_MATH_kernel": False,
            "duplicates_ABACUS_independent_challenge": False,
            "issue_923_compensation_allowed": False,
        },
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "hard_gate_compensation_allowed": False,
        "runtime_gold_credit_delta": 0,
        "engineering_acceptance_created": False,
    }
    return {"contract": contract, "atom": atom, "coolprop": cool, "qps": qps}


@pytest.fixture
def patched_sha(monkeypatch):
    real = m.canonical_sha

    def fake(value):
        if value == SENTINEL_MATRIX:
            return MATRIX_SHA
        return real(value)

    monkeypatch.setattr(m, "canonical_sha", fake)
    return real


def _run(tmp_path, monkeypatch, docs, head=None):
    argv = ["prog"]
    for name, doc in docs.items():
        p = tmp_path / (name + ".json")
        p.write_text(json.dumps(doc), encoding="utf-8")
        argv += ["--" + name, str(p)]
    out = tmp_path / "nested" / "proof.json"
    argv += ["--out", str(out)]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.delenv("EXACT_HEAD", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    if head is not None:
        monkeypatch.setenv("EXACT_HEAD", head)
    rc = m.main()
    return rc, json.loads(out.read_text(encoding="utf-8"))


def test_canonical_sha_is_key_order_independent():
    assert m.canonical_sha({"a": 1, "b": 2}) == m.canonical_sha({"b": 2, "a": 1})
    assert m.canonical_sha(m.EXPECTED_FEATURES) == SCHEMA_SHA


def test_invariant_matches_named_clocks_and_booleans():
    ref = _semantics()
    assert m.invariant_matches(ref, _semantics(), "named_clocks") is True
    bad = _semantics()
    bad["named_clocks"] = ["k"]
    assert m.invariant_matches(ref, bad, "named_clocks") is False
    # Both equal but not the canonical clock list still fails.
    assert m.invariant_matches({"named_clocks": ["k"]}, {"named_clocks": ["k"]}, "named_clocks") is False
    key = "small_eigengap_requires_subspace_context"
    assert m.invariant_matches(ref, ref, key) is True
    assert m.invariant_matches(ref, {key: 1}, key) is False
    assert m.invariant_matches({}, ref, key) is False


def test_atom_semantics_maps_named_clocks_preserved():
    sem = m.atom_semantics(_docs()["atom"])
    assert sem == _semantics()
    with pytest.raises(KeyError):
        m.atom_semantics({"knowledge_claims": {}})


def test_main_full_pass(tmp_path, monkeypatch, capsys, patched_sha):
    rc, proof = _run(tmp_path, monkeypatch, _docs(), head="f" * 40)
    assert rc == 0
    assert proof["status"] == "PASS_3P3_PROPAGATION_PROOF"
    assert proof["cycle3_state_candidate"] == "CONTROL"
    assert proof["source_head"] == "f" * 40
    assert proof["next_action"] == "COMMIT_EXACT_PROVEN_HEAD_AND_BIND_POSTMERGE_CONTROL"
    assert proof["3p3"] == {
        "Preserve_or_Pin": "PASS",
        "Propagate_or_Penetrate": "PASS",
        "Prove_or_Promote": "PASS_KNOWLEDGE_DIAGNOSTIC_CONTROL_ONLY",
    }
    kpi = proof["kpi"]
    assert kpi["semantic_parity"] == {"numerator": 18, "denominator": 18, "value": 1.0, "target": 1.0}
    assert kpi["propagation_coverage"]["value"] == 1.0
    assert kpi["propagation_depth"] == {"value": 2, "target_min": 2}
    assert kpi["duplicate_implementation_count"]["value"] == 0
    assert kpi["authority_inversion_count"]["value"] == 0
    assert proof["feature_schema_canonical_sha256"] == SCHEMA_SHA
    assert proof["feature_matrix_canonical_sha256"] == MATRIX_SHA
    body = {k: v for k, v in proof.items() if k != "proof_sha256"}
    assert proof["proof_sha256"] == patched_sha(body)
    assert json.loads(capsys.readouterr().out)["status"] == "PASS_3P3_PROPAGATION_PROOF"


def test_source_head_falls_back_to_github_sha_then_local(tmp_path, monkeypatch, patched_sha):
    _, proof = _run(tmp_path, monkeypatch, _docs())
    assert proof["source_head"] == "LOCAL_UNBOUND"
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setattr(sys, "argv", sys.argv)
    m.main()
    proof = json.loads((tmp_path / "nested" / "proof.json").read_text(encoding="utf-8"))
    assert proof["source_head"] == "a" * 40


def test_unpatched_matrix_digest_defers(tmp_path, monkeypatch, capsys):
    # Without the pinned real CoolProp matrix the digest gate defers.
    rc, proof = _run(tmp_path, monkeypatch, _docs())
    assert rc == 1
    assert proof["status"] == "DEFER_3P3_PROPAGATION_PROOF"
    assert proof["cycle3_state_candidate"] == "NOT_CONTROL"
    assert proof["next_action"] == "REPAIR_FIRST_RED_ONLY"
    assert proof["3p3"]["Prove_or_Promote"] == "DEFER"
    # T3 reach depends on the qps matrix digest matching the computed one.
    assert proof["target_reach"]["T3_QPS_TRIAGE"] is False
    assert proof["kpi"]["propagation_depth"]["value"] == 1


def test_t2_failure_reduces_depth_and_reach(tmp_path, monkeypatch, patched_sha):
    docs = _docs()
    docs["coolprop"]["feature_dimension"] = 5
    rc, proof = _run(tmp_path, monkeypatch, docs)
    assert rc == 1
    assert proof["target_reach"] == {"T1_MISSIONCONTROL": True, "T2_COOLPROP": False, "T3_QPS_TRIAGE": True}
    assert proof["kpi"]["propagation_coverage"]["numerator"] == 2
    assert proof["kpi"]["propagation_depth"]["value"] == 1
    assert proof["3p3"]["Propagate_or_Penetrate"] == "DEFER"


def test_atom_semantic_drift_breaks_t1_and_preserve(tmp_path, monkeypatch, patched_sha):
    docs = _docs()
    docs["atom"]["knowledge_claims"]["named_clocks_preserved"] = ["k", "t"]
    rc, proof = _run(tmp_path, monkeypatch, docs)
    assert rc == 1
    assert proof["source_semantic_parity"]["named_clocks"] is False
    assert proof["target_reach"]["T1_MISSIONCONTROL"] is False
    assert proof["3p3"]["Preserve_or_Pin"] == "DEFER"
    # T2/T3 still reached -> depth stays 2.
    assert proof["kpi"]["propagation_depth"]["value"] == 2


def test_depth_zero_when_nothing_reached(tmp_path, monkeypatch, patched_sha):
    docs = _docs()
    docs["contract"]["mission"] = "GM-X"
    docs["coolprop"]["status"] = "REJECT"
    rc, proof = _run(tmp_path, monkeypatch, docs)
    assert rc == 1
    assert proof["kpi"]["propagation_depth"]["value"] == 0
    assert proof["child_dispositions"] == {"T2_COOLPROP": False, "T3_QPS_TRIAGE": True}
    assert proof["kpi"]["child_disposition_coverage"]["value"] == 0.5


def test_target_semantic_drift_counts_parity(tmp_path, monkeypatch, patched_sha):
    docs = _docs()
    docs["qps"]["semantic_invariants"]["small_eigengap_requires_subspace_context"] = False
    rc, proof = _run(tmp_path, monkeypatch, docs)
    assert rc == 1
    assert proof["semantic_results"]["T3_QPS_TRIAGE"]["small_eigengap_requires_subspace_context"] is False
    assert proof["kpi"]["semantic_parity"]["numerator"] == 17


def test_reuse_and_duplicate_counts(tmp_path, monkeypatch, patched_sha):
    docs = _docs()
    docs["contract"]["propagation_targets"][0]["new_independent_math_implementation_allowed"] = True
    docs["coolprop"]["generalisation"]["duplicate_implementation_count"] = 2
    docs["qps"]["qps_consumption_guards"]["computes_pca"] = True
    rc, proof = _run(tmp_path, monkeypatch, docs)
    assert rc == 1
    assert proof["reuse_checks"] == {"T1_MISSIONCONTROL": False, "T2_COOLPROP": False, "T3_QPS_TRIAGE": False}
    assert proof["kpi"]["reuse_ratio"]["numerator"] == 0
    assert proof["kpi"]["duplicate_implementation_count"]["value"] == 3


def test_authority_inversions_counted(tmp_path, monkeypatch, patched_sha):
    docs = _docs()
    docs["contract"]["authority_transfer"] = True
    docs["coolprop"]["engineering_authority_created"] = True
    docs["qps"]["qps_consumption_guards"]["issue_923_compensation_allowed"] = True
    rc, proof = _run(tmp_path, monkeypatch, docs)
    assert rc == 1
    assert proof["kpi"]["authority_inversion_count"]["value"] == 3
    assert not any(proof["authority_checks"].values())


def test_source_identity_mismatch_defers(tmp_path, monkeypatch, patched_sha):
    docs = _docs()
    docs["coolprop"]["coolprop_transaction"]["runtime_receipt_sha256"] = "0" * 64
    docs["contract"]["source_atom"]["merge_sha"] = "1" * 40
    rc, proof = _run(tmp_path, monkeypatch, docs)
    assert rc == 1
    sic = proof["source_identity_checks"]
    assert sic["coolprop_runtime_receipt"] is False
    assert sic["contract_merge"] is False
    assert sic["coolprop_runtime_identity"] is True
    assert proof["3p3"]["Preserve_or_Pin"] == "DEFER"


def test_missing_input_key_raises(tmp_path, monkeypatch):
    docs = _docs()
    del docs["qps"]["semantic_invariants"]
    with pytest.raises(KeyError):
        _run(tmp_path, monkeypatch, docs)


def test_missing_required_arg_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog", "--contract", "x"])
    with pytest.raises(SystemExit) as exc:
        m.main()
    assert exc.value.code == 2
