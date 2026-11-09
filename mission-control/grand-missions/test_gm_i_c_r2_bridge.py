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


@pytest.fixture(scope="module")
def inputs():
    control = v.load_yaml(v.CONTROL)
    brief = (v.REPO / control["brief"]).read_text(encoding="utf-8")
    return control, v.load_yaml(v.BASELINE_CONTROL), v.load_yaml(v.BASELINE_CREW), brief


def run(inputs, mutate=None, hosted_ic3_attestor=None):
    control, baseline, crew, brief = inputs
    control = copy.deepcopy(control)
    if mutate:
        mutate(control)
    return v.validate(control, baseline, crew, brief, hosted_ic3_attestor=hosted_ic3_attestor)


def test_current_overlay_passes(inputs):
    result = run(inputs)
    assert result["result"] == "PASS_GM_I_C_R2_OVERLAY"
    assert result["first_red"] == "IC3_AUTH"


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda c: c.update(authority_transfer=True), "authority transfer"),
        (lambda c: c["first_red"].update(gate="IC5_CONSUMER_B"), "first red"),
        (lambda c: c["waves"][1]["maps_to_gates"].append("IC10_NEW"), "unknown gate"),
        (lambda c: c["waves"][1]["crew"].append("Z99"), "outside the v0.1 roster"),
        (lambda c: c["waves"][3].update(state="PASS"), "PASS without a PR"),
        (lambda c: c["waves"][4].update(state="BLOCKED_ON_R2-W6"), "unknown or later wave"),
        (lambda c: c["runtime_workers_added"][0].update(is_crew=True), "must not be crew"),
        (lambda c: c["broker"]["functions"].update(FIX="AUTO_FIX_ON_CONFLICT"), "never fix"),
        (lambda c: c["explicit_nonclaims"].remove("R2_REOPEN_NE_IC3_PASS"), "missing non-claims"),
        (lambda c: c["rex_new"].append(dict(c["rex_new"][0])), "duplicate REX"),
        (lambda c: c["contracts"][1].update(disposition="NEW_NO_EXISTING_OWNER"), "profile the GMI package"),
        (lambda c: c["baseline"].update(home_base_sha="bc974acd"), "full 40-hex"),
    ],
)
def test_overlay_fails_closed(inputs, mutate, message):
    with pytest.raises(SystemExit) as exc:
        run(inputs, mutate)
    assert message in str(exc.value)


def test_wave_pass_needs_earlier_agent_waves_pass(inputs):
    def mutate(c):
        c["waves"][1].update(state="PASS", evidence={"pr": 1, "merge_sha": "a" * 40})

    with pytest.raises(SystemExit) as exc:
        run(inputs, mutate)
    assert "earlier R2-W0 not PASS" in str(exc.value)


def mark_pass_through(control, last_index):
    """Synthetic passed waves; evidence is deliberately not trusted IC3 proof."""
    for i in range(last_index + 1):
        control["waves"][i]["state"] = "PASS"
        control["waves"][i]["evidence"] = {"pr": 100 + i, "merge_sha": "a" * 40}


def test_hosted_w4_cannot_bypass_blocked_owner_ic3(inputs):
    def mutate(c):
        mark_pass_through(c, 2)
        c["waves"][4].update(state="PASS", evidence={"pr": 104, "merge_sha": "a" * 40})

    with pytest.raises(SystemExit, match="R2-W4 is PASS but dependency R2-W3 is not PASS"):
        run(inputs, mutate)


@pytest.mark.parametrize("started", ["PLANNED", "IN_PROGRESS", "BLOCKED_ON_OWNER"])
def test_started_wave_cannot_erase_unpassed_blocker(inputs, started):
    with pytest.raises(SystemExit, match="R2-W4 is .* but dependency R2-W3 is not PASS"):
        run(inputs, lambda c: c["waves"][4].update(state=started))


def test_dropping_depends_on_cannot_erase_pinned_blocker(inputs):
    def mutate(c):
        c["waves"][4].update(state="IN_PROGRESS", depends_on=[])

    with pytest.raises(SystemExit, match=r"R2-W4 drops pinned dependency \['R2-W3'\]"):
        run(inputs, mutate)


def test_depends_on_is_required(inputs):
    with pytest.raises(SystemExit, match="R2-W0 must declare depends_on"):
        run(inputs, lambda c: c["waves"][0].pop("depends_on"))


def test_blocked_state_must_name_a_declared_dependency(inputs):
    def mutate(c):
        c["waves"][5].update(state="BLOCKED_ON_R2-W3")

    with pytest.raises(SystemExit, match="not in its depends_on"):
        run(inputs, mutate)


def test_successor_can_start_once_its_blocker_passes(inputs):
    def mutate(c):
        mark_pass_through(c, 3)
        c["first_red"]["state"] = "IC3_DRIVE_READONLY_GT0_STEP_PASS"
        c["waves"][4]["state"] = "IN_PROGRESS"

    result = run(inputs, mutate, hosted_ic3_attestor=lambda _wave: True)
    assert result["waves"]["R2-W4"] == "IN_PROGRESS"


# --- Post-merge DoV receipt bound by R2-W2 evidence -------------------------------------------

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

    with pytest.raises(SystemExit, match="referenced receipt missing"):
        run(inputs, mutate)


def test_receipt_path_outside_mission_dir_fails(inputs):
    def mutate(c):
        c["waves"][2]["evidence"]["postmerge_dov_candidate"] = "mission-control/grand-missions/../../README.md"

    with pytest.raises(SystemExit, match="receipt outside"):
        run(inputs, mutate)


@pytest.mark.parametrize(
    "mutate_receipt, message",
    [
        (lambda r: r.update(wave="R2-W1"), "bound to wave R2-W1"),
        (lambda r: r.update(reopen_id="GM-I-C-R3"), "reopen_id mismatch"),
        (lambda r: r.update(authority_transfer=True), "transfers authority"),
        (lambda r: r["publication"].update(pr=41), "PR mismatch"),
        (lambda r: r["publication"].update(merge_sha="b" * 40), "merge SHA mismatch"),
        (lambda r: r["publication"].update(repository="GBOGEB/OTHER"), "publication repo mismatch"),
        (lambda r: r["validated_source"].update(commit_sha="c" * 40), "validated-source SHA mismatch"),
        (lambda r: r["validated_source"].update(contains_merge="d" * 40), "does not contain the merge"),
        (lambda r: r["hosted_postmerge_runs"].update(head_sha="e" * 40), "hosted-run head mismatch"),
        (lambda r: r["hosted_postmerge_runs"].update(runs=[]), "lists no hosted runs"),
        (lambda r: r["hosted_postmerge_runs"]["runs"][0].update(conclusion="failure"), "not success"),
        (lambda r: r["dogfood_against_real_repo"].update(head_sha="f" * 40), "dogfood head mismatch"),
        (lambda r: r.update(status="ADMITTED"), "not a CANDIDATE"),
    ],
)
def test_drifted_receipt_fails_closed(inputs, mutate_receipt, message):
    with pytest.raises(SystemExit) as exc:
        run_with_receipt(inputs, mutate_receipt)
    assert message in str(exc.value)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda c: c["waves"][2]["evidence"].update(postmerge_source_sha="a" * 40), "validated-source SHA mismatch"),
        (lambda c: c["waves"][2]["evidence"].update(merge_sha="a" * 40), "merge SHA mismatch"),
        (lambda c: c["waves"][2]["evidence"].pop("postmerge_source_sha"), "declared together"),
        (lambda c: c["waves"][2]["evidence"].update(merge_sha="3ee30f93"), "full 40-hex"),
        (lambda c: c["waves"][2]["evidence"].update(pr="40"), "PR must be an integer"),
    ],
)
def test_control_evidence_drift_fails_closed_while_in_progress(inputs, mutate, message):
    with pytest.raises(SystemExit) as exc:
        run_with_receipt(inputs, mutate=mutate)
    assert message in str(exc.value)


def test_ic3_pass_needs_external_hosted_attestor_not_yaml_fields(inputs):
    def mutate(c):
        mark_pass_through(c, 3)
        c["waves"][3]["evidence"].update(
            hosted_run_id=123, step_count=9, result="IC3_DRIVE_READONLY_GT0_STEP_PASS"
        )

    with pytest.raises(SystemExit, match="independently verified hosted"):
        run(inputs, mutate)
    with pytest.raises(SystemExit, match="independently verified hosted"):
        run(inputs, mutate, hosted_ic3_attestor=lambda _wave: "PASS")


def test_attested_ic3_cannot_contradict_withheld_first_red(inputs):
    def mutate(c):
        mark_pass_through(c, 3)

    with pytest.raises(SystemExit, match="contradicts withheld"):
        run(inputs, mutate, hosted_ic3_attestor=lambda _wave: True)


def test_first_red_cannot_claim_pass_without_attested_ic3(inputs):
    with pytest.raises(SystemExit, match="first red must stay WITHHELD"):
        run(inputs, lambda c: c["first_red"].update(state="IC3_DRIVE_READONLY_GT0_STEP_PASS"))


def test_explicit_trusted_attestor_can_support_future_ic3_transition(inputs):
    def mutate(c):
        mark_pass_through(c, 3)
        c["first_red"]["state"] = "IC3_DRIVE_READONLY_GT0_STEP_PASS"

    result = run(inputs, mutate, hosted_ic3_attestor=lambda _wave: True)
    assert result["waves"]["R2-W3"] == "PASS"
    assert result["first_red_state"] == "IC3_DRIVE_READONLY_GT0_STEP_PASS"
