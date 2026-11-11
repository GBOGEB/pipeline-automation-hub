"""GM-I-C R2 read-only DAG/matrix canaries using existing owner validators.

No duplicate Kahn scheduler, no FPC controller, no hosted WIF claims. These
checks run on the stacked R2-W0 PR branch, not on unmerged master alone.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def owner():
    validator = _load(HERE / "validate_gm_i_c_r2_bridge.py", "gmic_r2_validator_canary")
    lifecycle = _load(REPO / "mission-control/jade_temple/devops/lifecycle.py", "gmic_jade_owner_kahn")
    control = validator.load_yaml(validator.CONTROL)
    brief = (validator.REPO / control["brief"]).read_text(encoding="utf-8")
    return validator, lifecycle, control, validator.load_yaml(validator.BASELINE_CONTROL), validator.load_yaml(validator.BASELINE_CREW), brief


def _evaluate(owner, mutator=None, attestor=None):
    validator, _, original, baseline, crew, brief = owner
    control = copy.deepcopy(original)
    if mutator:
        mutator(control)
    return validator.validate(control, baseline, crew, brief, hosted_ic3_attestor=attestor)


def _claim_pass(control, index):
    control["waves"][index]["state"] = "PASS"
    control["waves"][index]["evidence"] = {"pr": 4000 + index, "merge_sha": "a" * 40}


def test_source_contract_stays_owner_only_and_withheld(owner):
    validator, _, control, *_ = owner
    assert [w["id"] for w in control["waves"]] == [f"R2-W{i}" for i in range(7)]
    assert control["waves"][3]["owner_action_required"] is True
    assert control["waves"][3]["state"] == "BLOCKED_ON_OWNER"
    assert control["first_red"]["state"].startswith("WITHHELD")
    assert _evaluate(owner)["authority_transfer"] is False


def test_owner_kahn_mandatory_series_has_no_false_parallelism(owner):
    _, lifecycle, control, *_ = owner
    ids = [w["id"] for w in control["waves"]]
    edges = [(a, b, "FEEDFORWARD") for a, b in zip(ids, ids[1:])]
    assert lifecycle.topo_layers(ids, edges) == [[x] for x in ids]


def test_owner_kahn_allows_true_disjoint_work_but_blocks_join(owner):
    lifecycle = owner[1]
    nodes = ["CAPTURE", "GEMINI_TEST", "HUB_TEST", "DRIVE_RECEIPT", "JOIN"]
    edges = [("CAPTURE", n, "FEEDFORWARD") for n in nodes[1:4]]
    edges += [(n, "JOIN", "FEEDFORWARD") for n in nodes[1:4]]
    assert lifecycle.topo_layers(nodes, edges) == [
        ["CAPTURE"], ["DRIVE_RECEIPT", "GEMINI_TEST", "HUB_TEST"], ["JOIN"]
    ]


@pytest.mark.parametrize("edges,pattern", [
    ([("A", "UNKNOWN", "FEEDFORWARD")], "unknown edge endpoint"),
    ([("A", "B", "FEEDFORWARD"), ("B", "A", "FEEDFORWARD")], "cycle"),
])
def test_owner_kahn_rejects_invalid_dependencies(owner, edges, pattern):
    with pytest.raises(ValueError, match=pattern):
        owner[1].topo_layers(["A", "B"], edges)


@pytest.mark.parametrize("later", [4, 5, 6])
def test_later_waves_cannot_pass_blocked_ic3(owner, later):
    def mutate(c):
        for n in (0, 1, 2):
            _claim_pass(c, n)
        _claim_pass(c, later)
    with pytest.raises(SystemExit, match="PASS while earlier R2-W3 not PASS"):
        _evaluate(owner, mutate)


@pytest.mark.parametrize("attested", [None, "PASS", {"result": "PASS"}, 1])
def test_owner_gate_rejects_synthetic_ic3_attestors(owner, attested):
    def mutate(c):
        for n in range(4):
            _claim_pass(c, n)
    with pytest.raises(SystemExit, match="independently verified hosted"):
        _evaluate(owner, mutate, attestor=(None if attested is None else lambda _: attested))


def test_true_attestor_still_cannot_contradict_withheld_first_red(owner):
    def mutate(c):
        for n in range(4):
            _claim_pass(c, n)
    with pytest.raises(SystemExit, match="contradicts withheld"):
        _evaluate(owner, mutate, attestor=lambda _: True)


def test_first_red_pass_cannot_be_declared_by_yaml_alone(owner):
    def mutate(c):
        c["first_red"]["state"] = "IC3_DRIVE_READONLY_GT0_STEP_PASS"
    with pytest.raises(SystemExit, match="first red must stay WITHHELD"):
        _evaluate(owner, mutate)
