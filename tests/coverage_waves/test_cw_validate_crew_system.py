"""Behavioural tests for mission-control/qps-triage-ultra/crew/validate_crew_system.py main().

The existing crew test only covers conceptual_control_allowed(); these drive main() over
synthetic registry/matrix/REX/policy documents written to tmp_path.
"""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "validate_crew_system.py"

DIMS = [
    "discovery", "deep_reading", "architecture", "planning", "build_repair", "runtime_execution",
    "evidence_provenance", "analysis_pca_bt", "operations_control", "rex_learning",
]
LIFECYCLE = ["NEED_SIGNAL", "CONCEPTUAL", "TRIAL", "PARTIAL", "OBSERVED", "CONTROL_ELIGIBLE", "MERGED_PRUNED_RETURNED"]


def _vector(value=3, basis="OBSERVED_RUN"):
    vec = {d: value for d in DIMS}
    vec["basis"] = basis
    return vec


def valid_docs():
    registry = {
        "authority_transfer": False,
        "required_fields": ["crew_id", "roles", "maturity"],
        "crew": [
            {
                "crew_id": "S01", "roles": ["AMBASSADOR"], "maturity": "OBSERVED",
                "source_refs": ["a.md"], "last_evidence_sha": "abc1234",
                "competency_vector": _vector(), "control_eligibility": "ELIGIBLE",
            },
            {
                "crew_id": "C01", "roles": ["SCOUT"], "maturity": "CONCEPTUAL",
                "control_eligibility": "NOT_ELIGIBLE",
                "authority": {"promote": False, "control": "BOUNDED_AFTER_PROMOTION"},
                "last_evidence_sha": None, "competency_vector": _vector(0, "DECLARED"),
            },
            {
                "crew_id": "P01", "roles": ["BUILDER"], "maturity": "PARTIAL",
                "source_refs": ["b.md"], "last_evidence_sha": "def5678",
                "competency_vector": _vector(6),
            },
        ],
    }
    matrix = {
        "dimensions": {d: {} for d in DIMS},
        "scale": {f"L{i}": "level" for i in range(7)},
        "evidence_classes": {"OBSERVED_RUN": {}, "DECLARED": {}},
    }
    rex = {"entries": [
        {"rex_id": f"REX-{n:03d}", "primary_roles": ["S01"], "affected_competencies": ["discovery"]}
        for n in range(1, 7)
    ]}
    policy = {
        "candidate_roles_seeded_now": [{"crew_id": "C01"}],
        "ambassador_rule": {"crew_id": "S01"},
        "lifecycle": [{"state": s} for s in LIFECYCLE],
    }
    return {"registry": registry, "matrix": matrix, "rex": rex, "policy": policy}


@pytest.fixture
def vcs(tmp_path):
    """Load the module with __file__ redirected so REGISTRY/MATRIX/REX/POLICY resolve in tmp_path."""
    spec = importlib.util.spec_from_file_location("cw_validate_crew_system_mod", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(tmp_path / "cw_vcs_relocated.py")
    spec.loader.exec_module(mod)
    assert mod.HERE == tmp_path.resolve()
    return mod


def run_main(mod, docs, capsys):
    targets = {"registry": mod.REGISTRY, "matrix": mod.MATRIX, "rex": mod.REX, "policy": mod.POLICY}
    for key, path in targets.items():
        path.write_text(json.dumps(docs[key]), encoding="utf-8")
    rc = mod.main()
    out = json.loads(capsys.readouterr().out)
    return rc, out


def test_constants_resolve_relative_to_module_dir(vcs, tmp_path):
    base = tmp_path.resolve()
    assert vcs.REGISTRY == base / "CREW_REGISTRY_v1.json"
    assert vcs.MATRIX == base / "COMPETENCY_MATRIX_v1.json"
    assert vcs.REX == base / "REX_LEARNING_LEDGER_v1.json"
    assert vcs.POLICY == base / "ROLE_DEVELOPMENT_POLICY_v1.json"
    assert vcs.EXPECTED_SCALE == {"L0", "L1", "L2", "L3", "L4", "L5", "L6"}
    assert vcs.DIMENSIONS == set(DIMS)


def test_load_reads_utf8_json(vcs, tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"k": "é"}, ensure_ascii=False), encoding="utf-8")
    assert vcs.load(p) == {"k": "é"}


def test_require_appends_only_on_false(vcs):
    errors = []
    vcs.require(True, "no", errors)
    vcs.require(False, "yes", errors)
    assert errors == ["yes"]


def test_valid_system_passes_with_summary(vcs, capsys):
    rc, out = run_main(vcs, valid_docs(), capsys)
    assert rc == 0
    assert out == {
        "status": "PASS_CREW_SYSTEM",
        "crew_count": 3,
        "maturity_counts": {"OBSERVED": 1, "CONCEPTUAL": 1, "PARTIAL": 1},
        "rex_count": 6,
        "candidate_role_count": 1,
        "competency_scale": ["L0", "L1", "L2", "L3", "L4", "L5", "L6"],
        "ambassador": "S01_OBSERVED",
        "authority_transfer": False,
    }


def test_conceptual_false_control_also_passes(vcs, capsys):
    docs = valid_docs()
    docs["registry"]["crew"][1]["authority"]["control"] = False
    rc, out = run_main(vcs, docs, capsys)
    assert rc == 0
    assert out["status"] == "PASS_CREW_SYSTEM"


def _crew(docs, crew_id):
    return next(m for m in docs["registry"]["crew"] if m["crew_id"] == crew_id)


def _m_authority(d):
    d["registry"]["authority_transfer"] = True


def _m_missing_field(d):
    del _crew(d, "P01")["roles"]


def _m_missing_dim(d):
    del _crew(d, "P01")["competency_vector"]["planning"]


def _m_out_of_range(d):
    _crew(d, "S01")["competency_vector"]["discovery"] = 7


def _m_float_level(d):
    _crew(d, "S01")["competency_vector"]["architecture"] = 2.0


def _m_no_basis(d):
    _crew(d, "S01")["competency_vector"]["basis"] = ""


def _m_conceptual_eligible(d):
    _crew(d, "C01")["control_eligibility"] = "ELIGIBLE"


def _m_conceptual_promote(d):
    _crew(d, "C01")["authority"]["promote"] = True


def _m_conceptual_control_true(d):
    _crew(d, "C01")["authority"]["control"] = "CONTROL"


def _m_conceptual_sha(d):
    _crew(d, "C01")["last_evidence_sha"] = "deadbeef"


def _m_partial_no_refs(d):
    _crew(d, "P01")["source_refs"] = []


def _m_partial_no_sha(d):
    _crew(d, "P01")["last_evidence_sha"] = ""


def _m_unknown_maturity(d):
    _crew(d, "P01")["maturity"] = "LEGEND"


def _m_dup_id(d):
    d["registry"]["crew"].append(copy.deepcopy(_crew(d, "P01")))


def _m_s01_role(d):
    _crew(d, "S01")["roles"] = ["SCOUT"]


def _m_matrix_dims(d):
    d["matrix"]["dimensions"]["extra"] = {}


def _m_scale(d):
    del d["matrix"]["scale"]["L3"]


def _m_basis_unknown(d):
    _crew(d, "P01")["competency_vector"]["basis"] = "VIBES"


def _m_rex_no_id(d):
    d["rex"]["entries"].append({"primary_roles": [], "affected_competencies": []})


def _m_rex_dup(d):
    d["rex"]["entries"].append({"rex_id": "REX-002"})


def _m_rex_unknown_crew(d):
    d["rex"]["entries"][0]["primary_roles"] = ["Z99"]


def _m_rex_unknown_dim(d):
    d["rex"]["entries"][1]["affected_competencies"] = ["telepathy"]


def _m_rex_gap(d):
    d["rex"]["entries"] = [e for e in d["rex"]["entries"] if e["rex_id"] != "REX-004"]


def _m_candidates(d):
    d["policy"]["candidate_roles_seeded_now"].append({"crew_id": "P01"})


def _m_ambassador_rule(d):
    d["policy"]["ambassador_rule"] = {"crew_id": "S02"}


def _m_lifecycle(d):
    d["policy"]["lifecycle"].reverse()


CASES = [
    (_m_authority, "authority_transfer must remain false"),
    (_m_missing_field, "P01: missing required fields ['roles']"),
    (_m_missing_dim, "P01: competency vector missing dimensions"),
    (_m_out_of_range, "S01: discovery must be integer 0..6"),
    (_m_float_level, "S01: architecture must be integer 0..6"),
    (_m_no_basis, "S01: competency basis required"),
    (_m_conceptual_eligible, "C01: future bounded CONTROL declaration requires current NOT_ELIGIBLE state"),
    (_m_conceptual_promote, "C01: conceptual role cannot promote"),
    (_m_conceptual_control_true, "C01: conceptual role cannot hold current CONTROL authority"),
    (_m_conceptual_sha, "C01: conceptual role must not fabricate evidence SHA"),
    (_m_partial_no_refs, "P01: observed/partial role needs source_refs"),
    (_m_partial_no_sha, "P01: observed/partial role needs evidence SHA"),
    (_m_unknown_maturity, "P01: unknown maturity 'LEGEND'"),
    (_m_dup_id, "crew_id values must be unique"),
    (_m_s01_role, "S01 must carry AMBASSADOR role"),
    (_m_matrix_dims, "matrix dimensions must exactly match validator dimensions"),
    (_m_scale, "competency scale must be exactly L0..L6; observed=['L0', 'L1', 'L2', 'L4', 'L5', 'L6']"),
    (_m_basis_unknown, "P01: unknown competency evidence basis 'VIBES'"),
    (_m_rex_no_id, "REX entry missing rex_id"),
    (_m_rex_dup, "duplicate REX id REX-002"),
    (_m_rex_unknown_crew, "REX-001: unknown crew reference Z99"),
    (_m_rex_unknown_dim, "REX-002: unknown competency telepathy"),
    (_m_rex_gap, "REX-001 through REX-006 must be represented"),
    (_m_candidates, "candidate role policy must exactly match conceptual registry members"),
    (_m_ambassador_rule, "ambassador policy must bind S01"),
    (_m_lifecycle, "role lifecycle state machine order changed unexpectedly"),
]


@pytest.mark.parametrize("mutate,message", CASES, ids=[c[0].__name__ for c in CASES])
def test_each_violation_fails_with_exact_message(vcs, capsys, mutate, message):
    docs = valid_docs()
    mutate(docs)
    rc, out = run_main(vcs, docs, capsys)
    assert rc == 1
    assert out["status"] == "FAIL_CREW_SYSTEM"
    assert message in out["errors"]
    assert out["error_count"] == len(out["errors"])


def test_conceptual_eligible_reports_both_conceptual_messages(vcs, capsys):
    docs = valid_docs()
    _m_conceptual_eligible(docs)
    rc, out = run_main(vcs, docs, capsys)
    assert rc == 1
    assert out["errors"] == [
        "C01: conceptual role cannot be CONTROL eligible",
        "C01: future bounded CONTROL declaration requires current NOT_ELIGIBLE state",
    ]


def test_conceptual_false_control_with_eligible_skips_future_marker_check(vcs, capsys):
    docs = valid_docs()
    c01 = _crew(docs, "C01")
    c01["authority"]["control"] = False
    c01["control_eligibility"] = "ELIGIBLE"
    rc, out = run_main(vcs, docs, capsys)
    assert rc == 1
    assert out["errors"] == ["C01: conceptual role cannot be CONTROL eligible"]


def test_missing_ambassador_and_crew_id_placeholder(vcs, capsys):
    docs = valid_docs()
    s01 = _crew(docs, "S01")
    del s01["crew_id"]
    rc, out = run_main(vcs, docs, capsys)
    assert rc == 1
    assert "<missing>: missing required fields ['crew_id']" in out["errors"]
    assert "Ambassador S01 must exist" in out["errors"]
    assert "S01 must carry AMBASSADOR role" not in out["errors"]
    assert "None: unknown competency evidence basis" not in " ".join(out["errors"])


def test_ambassador_must_remain_observed(vcs, capsys):
    docs = valid_docs()
    _crew(docs, "S01")["maturity"] = "PARTIAL"
    rc, out = run_main(vcs, docs, capsys)
    assert rc == 1
    assert out["errors"] == ["Ambassador must remain OBSERVED"]


def test_empty_documents_collect_all_structural_errors(vcs, capsys):
    rc, out = run_main(vcs, {"registry": {}, "matrix": {}, "rex": {}, "policy": {}}, capsys)
    assert rc == 1
    assert out["errors"] == [
        "authority_transfer must remain false",
        "crew registry must not be empty",
        "Ambassador S01 must exist",
        "matrix dimensions must exactly match validator dimensions",
        "competency scale must be exactly L0..L6; observed=[]",
        "REX-001 through REX-006 must be represented",
        "ambassador policy must bind S01",
        "role lifecycle state machine order changed unexpectedly",
    ]


def test_missing_input_file_raises(vcs):
    with pytest.raises(FileNotFoundError):
        vcs.main()


def test_main_guard_exits_with_main_status(tmp_path, capsys):
    """Executed as __main__ (with __file__ in tmp_path), the script exits with main()'s status."""
    docs = valid_docs()
    names = {
        "registry": "CREW_REGISTRY_v1.json", "matrix": "COMPETENCY_MATRIX_v1.json",
        "rex": "REX_LEARNING_LEDGER_v1.json", "policy": "ROLE_DEVELOPMENT_POLICY_v1.json",
    }
    for key, name in names.items():
        (tmp_path / name).write_text(json.dumps(docs[key]), encoding="utf-8")
    code = compile(MOD_PATH.read_text(encoding="utf-8"), str(MOD_PATH), "exec")
    glb = {"__name__": "__main__", "__file__": str(tmp_path / "cw_vcs_main.py")}
    with pytest.raises(SystemExit) as exc:
        exec(code, glb)
    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS_CREW_SYSTEM"
