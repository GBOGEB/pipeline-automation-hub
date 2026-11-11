"""Negative and positive cases for validate_gm_i_c_r2_bridge."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("validate_gm_i_c_r2_bridge", HERE / "validate_gm_i_c_r2_bridge.py")
v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v)

SYNTHETIC = "synthetic://"
_RECEIPTS: dict[str, dict] = {}


def loader(path):
    """Serve synthetic test receipts; everything else goes through the real loader."""
    if isinstance(path, str) and path.startswith(SYNTHETIC):
        return copy.deepcopy(_RECEIPTS[path])
    return v.load_repo_yaml(path)


@pytest.fixture(scope="module")
def inputs():
    control = v.load_yaml(v.CONTROL)
    brief = (v.REPO / control["brief"]).read_text(encoding="utf-8")
    return control, v.load_yaml(v.BASELINE_CONTROL), v.load_yaml(v.BASELINE_CREW), brief


def run(inputs, mutate=None, hosted_ic3_attestor=None, brief_extra=""):
    control, baseline, crew, brief = inputs
    control = copy.deepcopy(control)
    if mutate:
        mutate(control)
    return v.validate(
        control, baseline, crew, brief + brief_extra, hosted_ic3_attestor=hosted_ic3_attestor, receipt_loader=loader
    )


def rejects(inputs, mutate, message, **kw):
    with pytest.raises(v.Fail) as exc:
        run(inputs, mutate, **kw)
    assert message in str(exc.value), str(exc.value)
    assert str(exc.value).startswith("FAIL: ")


def make_pass(control, i, status="ADMITTED_BY_OWNER"):
    """A fully evidenced PASS: merged PR, P1-P3 pulses and an admitted post-merge receipt.

    The evidence is synthetic and is deliberately not IC3 proof: R2-W3 still needs the attestor.
    """
    wave = control["waves"][i]
    pr, merge, source = 100 + i, f"{i + 1:x}" * 40, "b" * 40
    path = f"{SYNTHETIC}{wave['id']}"
    wave["state"] = "PASS"
    wave["pulses"] = {"P1": f"{wave['repo']}#{pr}", "P2": "exact-head CI and review", "P3": path}
    wave["evidence"] = {"pr": pr, "merge_sha": merge, "postmerge_dov_candidate": path, "postmerge_source_sha": source}
    _RECEIPTS[path] = {
        "mission": "GM-I-C",
        "reopen_id": control["reopen_id"],
        "wave": wave["id"],
        "status": status,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "publication": {"repository": wave["repo"], "pr": pr, "merge_sha": merge},
        "validated_source": {"repository": wave["repo"], "commit_sha": source, "contains_merge": merge},
        "hosted_postmerge_runs": {"event": "push", "head_sha": source, "runs": [{"run_id": 1, "conclusion": "success"}]},
        "nonclaims": sorted(v.CANDIDATE_RECEIPT_NONCLAIMS),
    }
    return path


def mark_pass_through(control, last_index):
    for i in range(last_index + 1):
        make_pass(control, i)


def test_current_overlay_passes(inputs):
    result = run(inputs)
    assert result["result"] == "PASS_GM_I_C_R2_OVERLAY"
    assert result["first_red"] == "IC3_AUTH"


def test_cli_validates_repository_overlay():
    assert v.main([]) == 0


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda c: c.update(authority_transfer=True), "authority transfer"),
        (lambda c: c["first_red"].update(gate="IC5_CONSUMER_B"), "first red"),
        (lambda c: c["waves"][1]["crew"].append("Z99"), "outside the v0.1 roster"),
        (lambda c: c["waves"][3].update(state="PASS"), "PASS without a PR"),
        (lambda c: c["waves"][4].update(state="BLOCKED_ON_R2-W6"), "unknown or later wave"),
        (lambda c: c["runtime_workers_added"][0].update(is_crew=True), "must not be crew"),
        (lambda c: c["explicit_nonclaims"].remove("R2_REOPEN_NE_IC3_PASS"), "missing non-claims"),
        (lambda c: c["explicit_nonclaims"].remove("OFFLINE_RECEIPT_CROSSCHECK_NE_GITHUB_VERIFICATION"), "missing non-claims"),
        (lambda c: c["rex_new"].append(dict(c["rex_new"][0])), "duplicate REX"),
        (lambda c: c["contracts"][1].update(disposition="NEW_NO_EXISTING_OWNER"), "profile the GMI package"),
        (lambda c: c["baseline"].update(home_base_sha="bc974acd"), "baseline home_base_sha changed"),
    ],
)
def test_overlay_fails_closed(inputs, mutate, message):
    rejects(inputs, mutate, message)


# --- Pinned wave plan (review finding 1 and 5) ----------------------------------------------------

def test_ic3_gate_cannot_be_removed_from_owner_wave(inputs):
    """Reviewer reproduction: drop IC3_AUTH from W3, pass W0-W3 and start W4 without the attestor."""
    def mutate(c):
        mark_pass_through(c, 3)
        c["waves"][3]["maps_to_gates"] = ["IC2_BRIDGE"]
        c["waves"][4]["state"] = "IN_PROGRESS"

    rejects(inputs, mutate, "R2-W3 maps_to_gates changed from pinned ['IC3_AUTH']")


@pytest.mark.parametrize("gates", [[], ["IC3_AUTH", "IC2_BRIDGE"]])
def test_owner_wave_gates_are_exact(inputs, gates):
    rejects(inputs, lambda c: c["waves"][3].update(maps_to_gates=gates), "R2-W3 maps_to_gates changed")


@pytest.mark.parametrize(
    "index, key, value",
    [
        (3, "owner_action_required", False),
        (5, "owner_action_required", False),
        (0, "owner_action_required", True),
        (4, "repo", "GBOGEB/pipeline-automation-hub"),
        (1, "maps_to_gates", ["IC2_BRIDGE", "IC10_NEW"]),
    ],
)
def test_pinned_wave_fields_cannot_change(inputs, index, key, value):
    rejects(inputs, lambda c: c["waves"][index].update({key: value}), f"{key} changed from pinned")


def test_wave_set_cannot_be_truncated(inputs):
    rejects(inputs, lambda c: c.update(waves=c["waves"][:4]), "wave set must be exactly")


def test_wave_set_cannot_grow_a_hosted_wave_past_the_blocker(inputs):
    def mutate(c):
        extra = copy.deepcopy(c["waves"][4])
        extra.update(id="R2-W7", depends_on=[], state="IN_PROGRESS")
        c["waves"].append(extra)

    rejects(inputs, mutate, "wave set must be exactly", brief_extra=" R2-W7")


# --- PASS needs real evidence (review finding 2 and 3) --------------------------------------------

def test_pass_with_only_pr_and_sha_is_rejected(inputs):
    """Reviewer reproduction: W0 PASS on its real PR number and an arbitrary SHA, P2/P3 still PENDING."""
    def mutate(c):
        c["waves"][0].update(state="PASS", evidence={"pr": 1135, "merge_sha": "a" * 40})

    rejects(inputs, mutate, "R2-W0 PASS while pulse P2 is PENDING")


def test_pass_needs_bound_postmerge_receipt(inputs):
    def mutate(c):
        make_pass(c, 0)
        for key in ("postmerge_dov_candidate", "postmerge_source_sha"):
            c["waves"][0]["evidence"].pop(key)

    rejects(inputs, mutate, "R2-W0 PASS without a bound post-merge receipt")


def test_pass_needs_owner_admitted_receipt(inputs):
    rejects(inputs, lambda c: make_pass(c, 0, status="REJECTED_BY_OWNER"), "needs an owner-ADMITTED post-merge receipt")


def test_pass_p1_must_match_wave_repo_and_pr(inputs):
    def mutate(c):
        make_pass(c, 0)
        c["waves"][0]["pulses"]["P1"] = "GBOGEB/GEMINI#100"

    rejects(inputs, mutate, "P1 pulse GBOGEB/GEMINI#100 does not match")


def test_pass_receipt_must_belong_to_wave_repo(inputs):
    def mutate(c):
        path = make_pass(c, 0)
        _RECEIPTS[path]["publication"]["repository"] = "GBOGEB/GEMINI"

    rejects(inputs, mutate, "publication repo mismatch")


@pytest.mark.parametrize(
    "evidence, message",
    [
        ({"pr": True, "merge_sha": "a" * 40}, "PR must be an integer"),
        ({"pr": 100, "merge_sha": "a" * 40 + "\n"}, "full 40-hex"),
        ({"pr": 100, "merge_sha": "A" * 40}, "full 40-hex"),
    ],
)
def test_evidence_types_are_exact(inputs, evidence, message):
    rejects(inputs, lambda c: c["waves"][0].update(evidence=evidence), message)


def test_wave_pass_needs_earlier_waves_pass(inputs):
    rejects(inputs, lambda c: make_pass(c, 1), "R2-W1 PASS while earlier R2-W0 not PASS")


def test_fully_evidenced_waves_pass(inputs):
    result = run(inputs, lambda c: mark_pass_through(c, 2))
    assert [result["waves"][w] for w in ("R2-W0", "R2-W1", "R2-W2")] == ["PASS"] * 3
    assert result["waves"]["R2-W3"] == "BLOCKED_ON_OWNER"


# --- Dependencies ---------------------------------------------------------------------------------

def test_hosted_w4_cannot_bypass_blocked_owner_ic3(inputs):
    def mutate(c):
        mark_pass_through(c, 2)
        make_pass(c, 4)

    rejects(inputs, mutate, "R2-W4 is PASS but dependency R2-W3 is not PASS")


@pytest.mark.parametrize("started", ["PLANNED", "IN_PROGRESS", "BLOCKED_ON_OWNER"])
def test_started_wave_cannot_erase_unpassed_blocker(inputs, started):
    with pytest.raises(v.Fail, match="R2-W4 is .* but dependency R2-W3 is not PASS"):
        run(inputs, lambda c: c["waves"][4].update(state=started))


def test_dropping_depends_on_cannot_erase_pinned_blocker(inputs):
    def mutate(c):
        c["waves"][4].update(state="IN_PROGRESS", depends_on=[])

    with pytest.raises(v.Fail, match=r"R2-W4 drops pinned dependency \['R2-W3'\]"):
        run(inputs, mutate)


def test_depends_on_is_required(inputs):
    rejects(inputs, lambda c: c["waves"][0].pop("depends_on"), "R2-W0 must declare depends_on")


def test_blocked_state_must_name_a_declared_dependency(inputs):
    rejects(inputs, lambda c: c["waves"][5].update(state="BLOCKED_ON_R2-W3"), "not in its depends_on")


def test_successor_can_start_once_its_blocker_passes(inputs):
    def mutate(c):
        mark_pass_through(c, 3)
        c["first_red"]["state"] = "IC3_DRIVE_READONLY_GT0_STEP_PASS"
        c["waves"][4]["state"] = "IN_PROGRESS"

    result = run(inputs, mutate, hosted_ic3_attestor=lambda _wave: True)
    assert result["waves"]["R2-W4"] == "IN_PROGRESS"


# --- IC3 attestor ---------------------------------------------------------------------------------

def test_ic3_pass_needs_external_hosted_attestor_not_yaml_fields(inputs):
    def mutate(c):
        mark_pass_through(c, 3)
        c["waves"][3]["evidence"].update(hosted_run_id=123, step_count=9, result="IC3_DRIVE_READONLY_GT0_STEP_PASS")

    rejects(inputs, mutate, "independently verified hosted")
    rejects(inputs, mutate, "independently verified hosted", hosted_ic3_attestor=lambda _wave: "PASS")


def test_attested_ic3_cannot_contradict_withheld_first_red(inputs):
    rejects(inputs, lambda c: mark_pass_through(c, 3), "contradicts withheld", hosted_ic3_attestor=lambda _wave: True)


def test_first_red_cannot_claim_pass_without_attested_ic3(inputs):
    rejects(inputs, lambda c: c["first_red"].update(state="IC3_DRIVE_READONLY_GT0_STEP_PASS"), "first red must stay WITHHELD")


def test_explicit_trusted_attestor_can_support_future_ic3_transition(inputs):
    def mutate(c):
        mark_pass_through(c, 3)
        c["first_red"]["state"] = "IC3_DRIVE_READONLY_GT0_STEP_PASS"

    result = run(inputs, mutate, hosted_ic3_attestor=lambda _wave: True)
    assert result["waves"]["R2-W3"] == "PASS"
    assert result["first_red_state"] == "IC3_DRIVE_READONLY_GT0_STEP_PASS"


# --- Reserve crew need a named v0.1 trigger (review finding 4) ------------------------------------

def test_reserve_crew_without_trigger_is_rejected(inputs):
    rejects(inputs, lambda c: c["waves"][0]["crew"].extend(["U05", "S02"]), "R2-W0 wakes reserve crew S02 without a named trigger")


def test_reserve_trigger_must_be_a_v0_1_wake_on(inputs):
    rejects(inputs, lambda c: c["waves"][1]["reserve_wake"].update(S05="BECAUSE_WE_WANT_TO"), "not one of its v0.1 wake_on triggers")


def test_reserve_wake_cannot_name_crew_not_in_wave(inputs):
    rejects(inputs, lambda c: c["waves"][1]["reserve_wake"].update(U07="LINEAGE_HMI"), "names crew not woken in this wave")


# --- Authority and baseline are pinned (review finding 6 and 7) -----------------------------------

@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda c: c["broker"]["functions"].update(REVIEW="APPROVE_AND_MERGE_OWN_DRAFT_PRS"), "broker identity"),
        (lambda c: c["broker"]["functions"].update(FIX="AUTO_FIX_CONFLICTS_NEVER_ASK"), "broker identity"),
        (lambda c: c["broker"]["functions"].update(COMMIT="PUSH_MAIN_DIRECT_NEVER_DEFAULT_BRANCH_PR"), "broker identity"),
        (lambda c: c["broker"]["functions"].pop("HOLD"), "broker identity"),
        (lambda c: c["broker"].update(identity="OWNER_PAT"), "broker identity"),
        (lambda c: c["runtime_workers_added"][4].update(authority="ADMIN_RULESET_BYPASS_MERGE"), "BROKER_GITHUB_APP authority changed"),
        (lambda c: c["runtime_workers_added"].append({"id": "NEW_BOT", "authority": "NONE", "is_crew": False}), "not in the pinned set"),
        (lambda c: c["runtime_workers_added"].pop(), "runtime workers missing"),
        (lambda c: c["mission_control"].update(merge_authority="BROKER_GITHUB_APP"), "mission_control merge_authority changed"),
        (lambda c: c["mission_control"].update(governor="U04"), "mission_control governor changed"),
    ],
)
def test_authority_is_pinned(inputs, mutate, message):
    rejects(inputs, mutate, message)


@pytest.mark.parametrize(
    "key, value",
    [
        ("historical_control", "mission-control/grand-missions/GM_I_C_R2_BIDIRECTIONAL_BRIDGE_BRIEF_v1.md"),
        ("historical_crew", "mission-control/grand-missions/GM-I-C_CROSS_AGENT_DRIVE_FEDERATION_CONTROL_v0.1.yaml"),
        ("treatment", "OVERLAY_DO_NOT_REWRITE_EXCEPT_CREW_AND_FIRST_RED"),
        ("home_base_sha", "c" * 40),
        ("provider_main_sha_at_reopen", "d" * 40),
    ],
)
def test_baseline_is_pinned(inputs, key, value):
    rejects(inputs, lambda c: c["baseline"].update({key: value}), f"baseline {key} changed")


# --- Exact types (review finding 9) ---------------------------------------------------------------

@pytest.mark.parametrize("value", [False, 0.0, "0"])
def test_formal_credit_delta_is_integer_zero(inputs, value):
    rejects(inputs, lambda c: c.update(formal_credit_delta=value), "formal credit delta")


# --- Malformed input gives a clean FAIL, not a traceback (review finding 8) -----------------------

@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c["waves"][0].update(state=None),
        lambda c: c["waves"][0].pop("crew"),
        lambda c: c.pop("baseline"),
        lambda c: c["contracts"][1].update(id="renamed"),
        lambda c: c["waves"][0].update(pulses=["P1"]),
        lambda c: c.update(waves={"R2-W0": {}}),
        lambda c: c.pop("rex_new"),
    ],
)
def test_malformed_overlay_fails_cleanly(inputs, mutate):
    with pytest.raises(v.Fail) as exc:
        run(inputs, mutate)
    assert str(exc.value).startswith("FAIL: ")


# --- Post-merge DoV receipt bound by R2-W2 evidence -----------------------------------------------

def w2_receipt():
    ev = v.load_yaml(v.CONTROL)["waves"][2]["evidence"]
    return v.load_repo_yaml(ev["postmerge_dov_candidate"])


def run_with_receipt(inputs, mutate_receipt=None, mutate=None):
    receipt = copy.deepcopy(w2_receipt())
    if mutate_receipt:
        mutate_receipt(receipt)
    control, baseline, crew, brief = inputs
    control = copy.deepcopy(control)
    if mutate:
        mutate(control)
    return v.validate(control, baseline, crew, brief, receipt_loader=lambda _path: receipt)


def test_current_w2_receipt_cross_checks(inputs):
    assert run_with_receipt(inputs)["waves"]["R2-W2"] == "IN_PROGRESS"


def test_missing_referenced_receipt_fails(inputs):
    def mutate(c):
        c["waves"][2]["evidence"]["postmerge_dov_candidate"] = "mission-control/grand-missions/GM_I_C_R2_DOES_NOT_EXIST.yaml"

    rejects(inputs, mutate, "referenced receipt missing")


def test_receipt_path_outside_mission_dir_fails(inputs):
    def mutate(c):
        c["waves"][2]["evidence"]["postmerge_dov_candidate"] = "mission-control/grand-missions/../../README.md"

    rejects(inputs, mutate, "receipt outside")


@pytest.mark.parametrize(
    "mutate_receipt, message",
    [
        (lambda r: r.update(wave="R2-W1"), "bound to wave R2-W1"),
        (lambda r: r.update(reopen_id="GM-I-C-R3"), "reopen_id mismatch"),
        (lambda r: r.update(authority_transfer=True), "transfers authority"),
        (lambda r: r.update(formal_credit_delta=0.0), "claims credit"),
        (lambda r: r["publication"].update(pr=41), "PR mismatch"),
        (lambda r: r["publication"].update(pr=True), "PR mismatch"),
        (lambda r: r["publication"].update(merge_sha="b" * 40), "merge SHA mismatch"),
        (lambda r: r["publication"].update(repository="GBOGEB/OTHER"), "publication repo mismatch"),
        (lambda r: r["validated_source"].update(commit_sha="c" * 40), "validated-source SHA mismatch"),
        (lambda r: r["validated_source"].update(contains_merge="d" * 40), "does not contain the merge"),
        (lambda r: r["hosted_postmerge_runs"].update(event="pull_request"), "not push (post-merge) runs"),
        (lambda r: r["hosted_postmerge_runs"].update(head_sha="e" * 40), "hosted-run head mismatch"),
        (lambda r: r["hosted_postmerge_runs"].update(runs=[]), "lists no hosted runs"),
        (lambda r: r["hosted_postmerge_runs"]["runs"][0].update(conclusion="failure"), "not success"),
        (lambda r: r["hosted_postmerge_runs"]["runs"][0].update(run_id=True), "without a run id"),
        (lambda r: r["dogfood_against_real_repo"].update(head_sha="f" * 40), "dogfood head mismatch"),
        (lambda r: r.update(status="ADMITTED"), "not a CANDIDATE"),
        (lambda r: r.pop("nonclaims"), "has no nonclaims"),
        (lambda r: r["nonclaims"].remove("POSTMERGE_DOV_CANDIDATE_NE_OWNER_ADMISSION"), "missing nonclaims"),
        (lambda r: r["hosted_postmerge_runs"].update(runs={"a": 1}), "lists no hosted runs"),
        (lambda r: r.update(publication=[1]), "publication must be a mapping"),
    ],
)
def test_drifted_receipt_fails_closed(inputs, mutate_receipt, message):
    with pytest.raises(v.Fail) as exc:
        run_with_receipt(inputs, mutate_receipt)
    assert message in str(exc.value), str(exc.value)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda c: c["waves"][2]["evidence"].update(postmerge_source_sha="a" * 40), "validated-source SHA mismatch"),
        (lambda c: c["waves"][2]["evidence"].update(merge_sha="a" * 40), "merge SHA mismatch"),
        (lambda c: c["waves"][2]["evidence"].pop("postmerge_source_sha"), "declared together"),
        (lambda c: c["waves"][2]["evidence"].update(merge_sha="3ee30f93"), "full 40-hex"),
        (lambda c: c["waves"][2]["evidence"].update(pr="40"), "PR must be an integer"),
        (lambda c: c["waves"][2]["evidence"].update(pr=41), "P1 pulse GBOGEB/GEMINI#40 does not match"),
    ],
)
def test_control_evidence_drift_fails_closed_while_in_progress(inputs, mutate, message):
    with pytest.raises(v.Fail) as exc:
        run_with_receipt(inputs, mutate=mutate)
    assert message in str(exc.value), str(exc.value)
