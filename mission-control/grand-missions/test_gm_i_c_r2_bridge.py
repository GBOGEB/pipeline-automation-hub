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

    with pytest.raises(SystemExit, match="R2-W4 PASS while earlier R2-W3 not PASS"):
        run(inputs, mutate)


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
