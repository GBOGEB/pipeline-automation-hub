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


def run(inputs, mutate=None):
    control, baseline, crew, brief = inputs
    control = copy.deepcopy(control)
    if mutate:
        mutate(control)
    return v.validate(control, baseline, crew, brief)


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
