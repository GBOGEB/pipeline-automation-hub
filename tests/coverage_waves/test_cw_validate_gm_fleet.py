"""Coverage wave: behavioural tests for mission-control/grand-missions/validate_gm_fleet.py.

Uses a synthetic, self-consistent input set in tmp_path (ROOT is monkeypatched)
so outcomes never depend on the committed registry stage.
"""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "grand-missions" / "validate_gm_fleet.py"


@pytest.fixture(scope="module")
def vgf(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("cw_validate_gm_fleet", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(tmp_path_factory.mktemp("cw_vgf") / "cw_vgf_loaded.py")
    spec.loader.exec_module(mod)
    return mod


REQUIRED_ROLES = ["SCOUT", "READER", "AMBASSADOR", "SCIENTIST", "ENGINEER", "SMOKER", "DOCTOR",
                  "DOCKMASTER", "QA", "ANALYST", "PM", "TM", "GOVERNOR", "ORCHESTRATOR"]
GM_IDS = ["GM-I", "GM-II", "GM-III", "GM-IV", "GM-V"]

RECON4 = {
    "source_sha": "c" * 40, "workflow_run_id": 5, "artifact_id": 6,
    "artifact_digest": "sha256:" + "d" * 64,
    "decision": "READY_FOR_SEPARATE_RECON_4_PROMOTION_PR",
    "post_merge_workflow_success_count": 3, "post_merge_workflow_total": 3,
}
ACTIVE8 = {
    "source_sha": "3943ae33eea2a4af6171b97517c19b79ed986fe8", "workflow_run_id": 35145656795,
    "artifact_id": 10467671042,
    "artifact_digest": "sha256:97d37b98334acbab0e1fec9bae56163e20fd5b9c2751be2495c52642bc6dd4cb",
    "decision": "READY_FOR_SEPARATE_ACTIVE_8_PROMOTION_PR", "result": "PASS",
}
F = ["GM-IV-F0%d" % i for i in range(1, 9)]


def shape(state):
    common = {"controlled_pilot_frontiers": [F[0], F[2]], "reference_frontiers": [F[1], F[3]]}
    if state == "HELD":
        return {"state": "HELD"}
    if state == "STAGED_ACTIVE_RECON_2_OF_8":
        return {"state": state, "activation_stage": "RECON_2_OF_8", "candidate_frontiers": F[:2],
                "unfilled_frontier_slots": F[2:]}
    if state == "STAGED_ACTIVE_PILOT_2_OF_8":
        return dict(common, state=state, activation_stage="PILOT_2_OF_8", candidate_frontiers=F[:4],
                    unfilled_frontier_slots=F[4:])
    if state == "STAGED_ACTIVE_RECON_4_OF_8":
        return dict(common, state=state, activation_stage="RECON_4_OF_8", candidate_frontiers=F[:4],
                    unfilled_frontier_slots=F[4:], recon_4_of_8_evidence=dict(RECON4))
    return dict(common, state=state, activation_stage="ACTIVE_8_OF_8", candidate_frontiers=list(F),
                new_candidate_recon_frontiers=F[4:], unfilled_frontier_slots=[], children=[],
                recon_4_of_8_evidence=dict(RECON4), active_8_of_8_evidence=dict(ACTIVE8))


def inputs():
    gm_iv = dict(shape("HELD"), id="GM-IV", frontier_count=8, children=[])
    return {
        "GRAND_MISSION_REGISTRY.json": {
            "grand_missions": [
                {"id": "GM-I", "frontier_count": 1, "children": []},
                {"id": "GM-II", "frontier_count": 2, "children": ["a", "b"]},
                {"id": "GM-III", "frontier_count": 4, "children": ["a", "b", "c", "d"]},
                gm_iv,
                {"id": "GM-V", "frontier_count": 16, "children": [], "state": "HELD"},
            ],
            "namespace": {"grand_mission_prefix": "GM-", "horizontal_mission_prefix": "HM-",
                          "local_mission_prefix": "LM-"},
        },
        "CREW_ROLE_REGISTRY.json": {"roles": [{"id": r} for r in REQUIRED_ROLES]},
        "CREW_STATE_MACHINE.json": {
            "states": ["IDLE", "ACTIVE", "RETURNED"],
            "allowed_transitions": [["IDLE", "ACTIVE"], ["ACTIVE", "RETURNED"]],
            "illegal_transitions": [["RETURNED", "ACTIVE"], ["IDLE", "GHOST"]],
        },
        "GM_GENEALOGY.json": {"missions": {
            "GM-I": {"observed_returned_workers": ["Scout_1", "Scout_2", "Scout_3", "Reader_1", "Reader_2"]},
            "GM-II": {"children": ["a", "b"]},
            "GM-III": {"frontiers": [1, 2, 3, 4]},
        }},
        "MISSION_CITY_GRAPH.json": {
            "nodes": [{"id": n} for n in GM_IDS + ["DOW", "KEB", "QPS", "RUNTIME_DOCK", "MISSION_CONTROL"]],
            "mission_states": {"GM-IV": "HELD"},
        },
        "CREW_REX_BIDIRECTIONAL_CONTRACT.json": {
            "verbs": {v: {} for v in ["LEARN", "IMPROVE", "UPDATE", "REPAIR", "ASSIMILATE", "PRUNE", "BRIDGE"]},
            "authority_transfer": False,
        },
        "FLEET_TELEMETRY_SCHEMA.json": {"pca_gate": {"evidence_class_required": "MEASURED", "minimum_comparable_rows": 3}},
        "FLEET_BT_EVIDENCE_SCHEMA.json": {"bt_gate": {"minimum_pairs": 2, "requires_connected_comparison_graph": True,
                                                      "forbid_synthetic_pair_credit": True}},
        "CREW_REX_LEDGER.json": {"events": [
            {"event_id": "e1", "direction": "CREW_TO_MC"},
            {"event_id": "e2", "direction": "MC_TO_CREW", "causal_parent": "e1"},
            {"event_id": "e3", "direction": "MC_TO_CREW"},
        ]},
        "VALIDATION_FIXTURES.json": {
            "crew_transitions": [
                {"from": "IDLE", "to": "ACTIVE", "expected": "ALLOW"},
                {"from": "RETURNED", "to": "ACTIVE", "expected": "REJECT"},
            ],
            "routing": [
                {"first_red": "HABITAT", "expected_roles": ["DOCKMASTER"], "forbidden_roles": ["DOCTOR"]},
                {"first_red": "APPLICATION", "expected_roles": ["DOCTOR", "ENGINEER"], "executed_steps": 2},
            ],
        },
    }


ENV_KEYS = ["SOURCE_SHA", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_REPOSITORY", "GITHUB_REF"]


@pytest.fixture
def env(vgf, tmp_path, monkeypatch):
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(vgf, "ROOT", tmp_path / "in")
    (tmp_path / "in").mkdir()
    data = inputs()

    def run(mutate=None):
        d = copy.deepcopy(data)
        if mutate:
            mutate(d)
        for name, obj in d.items():
            (tmp_path / "in" / name).write_text(json.dumps(obj), encoding="utf-8")
        out = tmp_path / "out" / "receipt.json"
        monkeypatch.setattr(sys, "argv", ["validate_gm_fleet.py", "--out", str(out)])
        vgf.main()
        return d, out

    return run


def fail_message(env, mutate):
    with pytest.raises(SystemExit) as info:
        env(mutate)
    return info.value.code


# --- module-level wiring --------------------------------------------------

def test_root_follows_module_file(vgf):
    assert vgf.ROOT == Path(vgf.__file__).resolve().parent
    assert vgf.ROOT.name.startswith("cw_vgf")


def test_load_reads_from_root(vgf, tmp_path, monkeypatch):
    monkeypatch.setattr(vgf, "ROOT", tmp_path)
    (tmp_path / "x.json").write_text('{"a": [1]}', encoding="utf-8")
    assert vgf.load("x.json") == {"a": [1]}


def test_require(vgf):
    assert vgf.require(True, "nope") is None
    with pytest.raises(SystemExit) as info:
        vgf.require(0, "boom")
    assert info.value.code == "FAIL: boom"


def test_canonical_digest_is_order_independent(vgf):
    import hashlib
    assert vgf.canonical_digest({"b": 1, "a": [2]}) == vgf.canonical_digest({"a": [2], "b": 1})
    assert vgf.canonical_digest({"a": 1}) == hashlib.sha256(b'{"a":1}').hexdigest()


# --- evidence validators --------------------------------------------------

def test_valid_recon4_evidence_accepts_good(vgf):
    assert vgf.valid_recon4_evidence(dict(RECON4)) is True


@pytest.mark.parametrize("patch", [
    {"source_sha": "c" * 39}, {"source_sha": 1}, {"workflow_run_id": 0}, {"workflow_run_id": "5"},
    {"artifact_id": -1}, {"artifact_id": None}, {"artifact_digest": "md5:" + "d" * 67},
    {"artifact_digest": "sha256:" + "d" * 63}, {"artifact_digest": 7}, {"decision": "NOPE"},
    {"post_merge_workflow_success_count": 2}, {"post_merge_workflow_total": 0, "post_merge_workflow_success_count": 0},
    {"post_merge_workflow_total": "3", "post_merge_workflow_success_count": "3"},
])
def test_valid_recon4_evidence_rejects(vgf, patch):
    assert not vgf.valid_recon4_evidence(dict(RECON4, **patch))


@pytest.mark.parametrize("item", [None, [], "x"])
def test_valid_recon4_evidence_rejects_non_dict(vgf, item):
    assert not vgf.valid_recon4_evidence(item)


def test_valid_active8_evidence(vgf):
    assert vgf.valid_active8_evidence(dict(ACTIVE8)) is True
    assert not vgf.valid_active8_evidence(None)
    for key in ACTIVE8:
        assert not vgf.valid_active8_evidence(dict(ACTIVE8, **{key: "other"})), key


# --- gm_iv_supported_shape ------------------------------------------------

@pytest.mark.parametrize("state", sorted([
    "HELD", "STAGED_ACTIVE_RECON_2_OF_8", "STAGED_ACTIVE_PILOT_2_OF_8", "STAGED_ACTIVE_RECON_4_OF_8", "ACTIVE_8_OF_8",
]))
def test_each_supported_state_accepts_exact_shape(vgf, state):
    assert state in vgf.SUPPORTED_GM_IV_STATES
    assert vgf.gm_iv_supported_shape(shape(state))


@pytest.mark.parametrize("state", ["ACTIVE_16_OF_16", "", None, "held"])
def test_unsupported_state_rejected(vgf, state):
    assert vgf.gm_iv_supported_shape({"state": state}) is False


@pytest.mark.parametrize("state,patch", [
    ("STAGED_ACTIVE_RECON_2_OF_8", {"activation_stage": "PILOT_2_OF_8"}),
    ("STAGED_ACTIVE_RECON_2_OF_8", {"candidate_frontiers": F[:3]}),
    ("STAGED_ACTIVE_RECON_2_OF_8", {"unfilled_frontier_slots": F[3:]}),
    ("STAGED_ACTIVE_PILOT_2_OF_8", {"controlled_pilot_frontiers": [F[0]]}),
    ("STAGED_ACTIVE_PILOT_2_OF_8", {"reference_frontiers": [F[3], F[1]]}),
    ("STAGED_ACTIVE_PILOT_2_OF_8", {"activation_stage": "RECON_4_OF_8"}),
    ("STAGED_ACTIVE_PILOT_2_OF_8", {"unfilled_frontier_slots": []}),
    ("STAGED_ACTIVE_RECON_4_OF_8", {"recon_4_of_8_evidence": None}),
    ("STAGED_ACTIVE_RECON_4_OF_8", {"candidate_frontiers": F}),
    ("ACTIVE_8_OF_8", {"active_8_of_8_evidence": dict(ACTIVE8, result="FAIL")}),
    ("ACTIVE_8_OF_8", {"recon_4_of_8_evidence": {}}),
    ("ACTIVE_8_OF_8", {"children": ["GM-IV-child"]}),
    ("ACTIVE_8_OF_8", {"unfilled_frontier_slots": [F[7]]}),
    ("ACTIVE_8_OF_8", {"new_candidate_recon_frontiers": F[4:7]}),
    ("ACTIVE_8_OF_8", {"activation_stage": "RECON_4_OF_8"}),
    ("ACTIVE_8_OF_8", {"reference_frontiers": []}),
])
def test_supported_state_with_wrong_shape_rejected(vgf, state, patch):
    assert not vgf.gm_iv_supported_shape(dict(shape(state), **patch))


def test_forward_states_requiring_governor_is_empty_set(vgf):
    assert vgf.FORWARD_GM_IV_STATES_REQUIRING_GOVERNOR == set()


# --- main: happy path -----------------------------------------------------

def test_main_pass_writes_receipt_with_local_defaults(vgf, env, capsys):
    data, out = env()
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["validation_check_count"] == 16
    assert [c["check"][:2] for c in receipt["validation_checks"]] == ["%02d" % i for i in range(1, 17)]
    assert all(c["result"] == "PASS" for c in receipt["validation_checks"])
    assert receipt["source_sha"] == "LOCAL_UNBOUND"
    assert receipt["run_id"] == "LOCAL" and receipt["ref"] == "LOCAL"
    assert receipt["repo"] == "GBOGEB/pipeline-automation-hub"
    assert receipt["authority_transfer"] is False
    keys = {"registry": "GRAND_MISSION_REGISTRY.json", "roles": "CREW_ROLE_REGISTRY.json",
            "machine": "CREW_STATE_MACHINE.json", "genealogy": "GM_GENEALOGY.json",
            "city": "MISSION_CITY_GRAPH.json", "bridge": "CREW_REX_BIDIRECTIONAL_CONTRACT.json",
            "telemetry": "FLEET_TELEMETRY_SCHEMA.json", "bt": "FLEET_BT_EVIDENCE_SCHEMA.json",
            "ledger": "CREW_REX_LEDGER.json", "fixtures": "VALIDATION_FIXTURES.json"}
    assert receipt["input_digest_sha256"] == vgf.canonical_digest({k: data[v] for k, v in keys.items()})
    checks = {c["check"]: c["detail"] for c in receipt["validation_checks"]}
    assert checks["08_gm_iv_8_exact_governed_shape_no_child_binding"] == "state=HELD frontier_count=8 children=0"
    assert checks["10_mission_city_graph"] == "nodes=10 gm_iv_state_sync=True"
    assert checks["03_crew_role_registry"] == "roles=14"
    assert checks["04_activation_return_state_machine"] == "fixtures=2"
    assert checks["14_crew_rex_bidirectional_ledger"] == "events=3"
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"result": "PASS_GM_FLEET_02B", "checks": 16, "source_sha": "LOCAL_UNBOUND",
                       "pca": receipt["pca_runtime_gate"], "bt": receipt["bt_runtime_gate"]}


def test_main_env_binding_source_sha_precedence(vgf, env, monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "g" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "77")
    monkeypatch.setenv("GITHUB_REPOSITORY", "GBOGEB/other")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/x")
    _, out = env()
    r = json.loads(out.read_text(encoding="utf-8"))
    assert (r["source_sha"], r["run_id"], r["repo"], r["ref"]) == ("g" * 40, "77", "GBOGEB/other", "refs/heads/x")
    monkeypatch.setenv("SOURCE_SHA", "s" * 40)
    _, out = env()
    assert json.loads(out.read_text(encoding="utf-8"))["source_sha"] == "s" * 40


@pytest.mark.parametrize("state", ["STAGED_ACTIVE_RECON_4_OF_8", "ACTIVE_8_OF_8"])
def test_main_passes_with_forward_gm_iv_state_synced_to_city(env, state):
    def mutate(d):
        reg = d["GRAND_MISSION_REGISTRY.json"]["grand_missions"]
        reg[3] = dict(shape(state), id="GM-IV", frontier_count=8, children=[])
        d["MISSION_CITY_GRAPH.json"]["mission_states"]["GM-IV"] = state
    _, out = env(mutate)
    checks = json.loads(out.read_text(encoding="utf-8"))["validation_checks"]
    assert checks[7]["detail"] == "state=" + state + " frontier_count=8 children=0"


# --- main: fail-closed paths ----------------------------------------------

def _reg(d):
    return d["GRAND_MISSION_REGISTRY.json"]["grand_missions"]


def test_fail_registry_order(env):
    msg = fail_message(env, lambda d: _reg(d).reverse())
    assert msg == "FAIL: 01_canonical_gm_registry: ['GM-V', 'GM-IV', 'GM-III', 'GM-II', 'GM-I']"


def test_fail_scaling_sequence(env):
    msg = fail_message(env, lambda d: _reg(d)[4].update(frontier_count=15))
    assert msg == "FAIL: 02_scaling_sequence: 1-2-4-8-16"


def test_fail_duplicate_role(env):
    msg = fail_message(env, lambda d: d["CREW_ROLE_REGISTRY.json"]["roles"].append({"id": "QA"}))
    assert msg == "FAIL: 03_crew_role_registry: roles=15"


def test_fail_missing_role(env):
    msg = fail_message(env, lambda d: d["CREW_ROLE_REGISTRY.json"]["roles"].pop())
    assert msg == "FAIL: 03_crew_role_registry: roles=13"


def test_fail_transition_fixture_mismatch(env):
    def mutate(d):
        d["VALIDATION_FIXTURES.json"]["crew_transitions"][0]["expected"] = "REJECT"
    assert fail_message(env, mutate) == "FAIL: transition fixture ('IDLE', 'ACTIVE') expected REJECT got ALLOW"


def test_fail_illegal_transition_in_allowed(env):
    def mutate(d):
        d["CREW_STATE_MACHINE.json"]["allowed_transitions"].append(["RETURNED", "ACTIVE"])
        d["VALIDATION_FIXTURES.json"]["crew_transitions"] = []
    assert fail_message(env, mutate) == "FAIL: illegal transition present in allowed list: ['RETURNED', 'ACTIVE']"


def test_illegal_transition_to_unknown_state_is_ignored(env):
    def mutate(d):
        d["CREW_STATE_MACHINE.json"]["allowed_transitions"].append(["IDLE", "GHOST"])
    _, out = env(mutate)
    assert out.exists()


def test_fail_gm_i_genealogy(env):
    msg = fail_message(env, lambda d: d["GM_GENEALOGY.json"]["missions"]["GM-I"]["observed_returned_workers"].pop())
    assert msg == "FAIL: 05_gm_i_genealogy: observed returned crew bound"


def test_fail_gm_ii_children(env):
    msg = fail_message(env, lambda d: _reg(d)[1]["children"].pop())
    assert msg == "FAIL: 06_gm_ii_two_child_genealogy: two children"


def test_fail_gm_iii_frontiers(env):
    msg = fail_message(env, lambda d: d["GM_GENEALOGY.json"]["missions"]["GM-III"]["frontiers"].pop())
    assert msg == "FAIL: 07_gm_iii_four_frontier_genealogy: four frontiers"


def test_fail_gm_iv_unsupported_state(env):
    def mutate(d):
        _reg(d)[3]["state"] = "ACTIVE_16_OF_16"
    assert fail_message(env, mutate) == "FAIL: 08_gm_iv_8_exact_governed_shape_no_child_binding: state=ACTIVE_16_OF_16 frontier_count=8 children=0"


def test_fail_gm_iv_child_binding(env):
    msg = fail_message(env, lambda d: _reg(d)[3]["children"].append("x"))
    assert msg.startswith("FAIL: 08_gm_iv_8_exact_governed_shape_no_child_binding: state=HELD")


def test_fail_gm_v_not_held(env):
    msg = fail_message(env, lambda d: _reg(d)[4].update(state="ACTIVE"))
    assert msg == "FAIL: 09_gm_v_held_16_no_fabrication: HELD/16 children=0"


def test_fail_city_state_desync(env):
    msg = fail_message(env, lambda d: d["MISSION_CITY_GRAPH.json"].pop("mission_states"))
    assert msg == "FAIL: 10_mission_city_graph: nodes=10 gm_iv_state_sync=False"


def test_fail_city_missing_node(env):
    msg = fail_message(env, lambda d: d["MISSION_CITY_GRAPH.json"]["nodes"].pop())
    assert msg == "FAIL: 10_mission_city_graph: nodes=9 gm_iv_state_sync=True"


def test_fail_namespace_collision(env):
    def mutate(d):
        d["GRAND_MISSION_REGISTRY.json"]["namespace"]["local_mission_prefix"] = "HM-"
    assert fail_message(env, mutate) == "FAIL: 11_namespace_disjointness: ['GM-', 'HM-', 'HM-']"


def test_fail_habitat_routing(env):
    def mutate(d):
        d["VALIDATION_FIXTURES.json"]["routing"][0]["forbidden_roles"] = []
    assert fail_message(env, mutate) == "FAIL: zero-step routing fixture malformed"


def test_fail_application_routing(env):
    def mutate(d):
        d["VALIDATION_FIXTURES.json"]["routing"][1]["executed_steps"] = 0
    assert fail_message(env, mutate) == "FAIL: application routing fixture malformed"


def test_fail_rex_authority_transfer(env):
    msg = fail_message(env, lambda d: d["CREW_REX_BIDIRECTIONAL_CONTRACT.json"].update(authority_transfer=True))
    assert msg == "FAIL: 13_bidirectional_rex_contract: learning loop bound"


def test_fail_rex_missing_verb(env):
    msg = fail_message(env, lambda d: d["CREW_REX_BIDIRECTIONAL_CONTRACT.json"]["verbs"].pop("PRUNE"))
    assert msg == "FAIL: 13_bidirectional_rex_contract: learning loop bound"


def test_fail_crew_report_without_return(env):
    def mutate(d):
        d["CREW_REX_LEDGER.json"]["events"].append({"event_id": "e9", "direction": "CREW_TO_MC"})
    assert fail_message(env, mutate) == "FAIL: crew report lacks Mission Control return: e9"


def test_fail_crew_report_answered_only_crew_side(env):
    def mutate(d):
        d["CREW_REX_LEDGER.json"]["events"][1]["direction"] = "CREW_TO_MC"
    # e1's only child is now crew-side, so e1 has no Mission Control return.
    assert fail_message(env, mutate) == "FAIL: crew report lacks Mission Control return: e1"


def test_fail_missing_causal_parent(env):
    def mutate(d):
        d["CREW_REX_LEDGER.json"]["events"].append({"event_id": "e4", "direction": "MC_TO_CREW", "causal_parent": "ghost"})
    assert fail_message(env, mutate) == "FAIL: missing causal parent ghost"


@pytest.mark.parametrize("gate", [{"evidence_class_required": "SYNTHETIC", "minimum_comparable_rows": 3},
                                  {"evidence_class_required": "MEASURED", "minimum_comparable_rows": 2}])
def test_fail_pca_gate(env, gate):
    msg = fail_message(env, lambda d: d["FLEET_TELEMETRY_SCHEMA.json"].update(pca_gate=gate))
    assert msg == "FAIL: 15_measured_fleet_telemetry_schema: future PCA fail-closed"


@pytest.mark.parametrize("patch", [{"minimum_pairs": 1}, {"requires_connected_comparison_graph": False},
                                   {"forbid_synthetic_pair_credit": False}])
def test_fail_bt_gate(env, patch):
    msg = fail_message(env, lambda d: d["FLEET_BT_EVIDENCE_SCHEMA.json"]["bt_gate"].update(patch))
    assert msg == "FAIL: 16_observed_pairwise_bt_schema: future BT fail-closed"


def test_fail_closed_writes_no_receipt(env, tmp_path):
    fail_message(env, lambda d: _reg(d).pop())
    assert not (tmp_path / "out").exists()


def test_main_requires_out(vgf, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["validate_gm_fleet.py"])
    with pytest.raises(SystemExit) as info:
        vgf.main()
    assert info.value.code == 2


# --- committed data: structural invariants only ---------------------------

def test_committed_gm_iv_state_is_classified_by_supported_set(vgf):
    reg = json.loads((MODULE_PATH.parent / "GRAND_MISSION_REGISTRY.json").read_text(encoding="utf-8"))
    gm_iv = next(m for m in reg["grand_missions"] if m["id"] == "GM-IV")
    result = vgf.gm_iv_supported_shape(gm_iv)
    assert isinstance(result, bool)
    if gm_iv.get("state") not in vgf.SUPPORTED_GM_IV_STATES:
        assert result is False
