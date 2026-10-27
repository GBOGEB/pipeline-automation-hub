"""Behavioural tests for mission-control/v2/validate_mission_control_v2.py."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "v2" / "validate_mission_control_v2.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_mission_control_v2_mod", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vm = _load()

_REAL_BUNDLE = {k: vm.load(v) for k, v in vm.FILES.items()}


@pytest.fixture
def bundle():
    return copy.deepcopy(_REAL_BUNDLE)


@pytest.fixture
def rooted(tmp_path, monkeypatch):
    """Point ROOT at tmp_path holding every CURRENT pointer target (registries stay real)."""
    for rel in _REAL_BUNDLE["current"]["canonical"].values():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", encoding="utf-8")
    monkeypatch.setattr(vm, "ROOT", tmp_path)
    return tmp_path


def _evo(b):
    return next(r for r in b["status"]["missions"] if r.get("mission_id") == "MC-EVO-02")


# ---------------------------------------------------------------- YAML helpers

def test_yaml_list_ids_parses_sections_and_skips_noise(tmp_path):
    p = tmp_path / "reg.yaml"
    p.write_text(
        "# header comment\n"
        "\n"
        "canonical_grand_missions:\n"
        "  - id: GM-A\n"
        "  - {id: 'GM-B', name: x}\n"
        "  - name: no-id-here\n"
        "  - id: \"\"\n"
        "    - id: NESTED-IGNORED\n"
        "  # indented comment\n"
        "other:\n"
        "  - id: OUTSIDE\n"
        "scalar_line_no_colon\n"
        "  - id: AFTER-SCALAR\n"
        "variants:\n"
        "  - id: \"V-1\",\n",
        encoding="utf-8",
    )
    ids = vm.yaml_list_ids(p, {"canonical_grand_missions", "variants"})
    assert ids == {"GM-A", "GM-B", "V-1"}


def test_yaml_mapping_keys_filters_invalid_keys(tmp_path):
    p = tmp_path / "legacy.yaml"
    p.write_text(
        "active_missions:\n"
        "  MC-1:\n"
        "    nested: value\n"
        "  bad key!: x\n"
        "  no_colon_line\n"
        "  ok.key_2-x: y\n"
        "expansion:\n"
        "  EXP-9: {}\n"
        "ignored:\n"
        "  IGN: 1\n",
        encoding="utf-8",
    )
    assert vm.yaml_mapping_keys(p, vm.LEGACY_REGISTER_SECTIONS) == {"MC-1", "ok.key_2-x", "EXP-9"}


def test_clean_yaml_scalar():
    assert vm._clean_yaml_scalar(" 'abc'},") == "abc"
    assert vm._clean_yaml_scalar(' "x" ') == "x"


def test_source_mission_ids_union(tmp_path, monkeypatch):
    off = tmp_path / "off.yaml"
    off.write_text("variants:\n  - id: V-1\n", encoding="utf-8")
    leg = tmp_path / "leg.yaml"
    leg.write_text("expansion:\n  E-1: {}\n", encoding="utf-8")
    monkeypatch.setattr(vm, "OFFICIAL_REGISTER", off)
    monkeypatch.setattr(vm, "LEGACY_REGISTER", leg)
    assert vm.source_mission_ids() == {"V-1", "E-1"} | vm.EXPLICIT_CONTROL_MISSION_IDS


def test_real_registries_bind_18_missions():
    ids = vm.source_mission_ids()
    assert len(ids) == 18
    assert vm.EXPLICIT_CONTROL_MISSION_IDS <= ids


# ---------------------------------------------------------------- validate_bundle

def test_real_bundle_valid_when_pointer_targets_exist(bundle, rooted):
    assert vm.validate_bundle(bundle) == []


def test_missing_pointer_targets_reported(bundle, tmp_path, monkeypatch):
    monkeypatch.setattr(vm, "ROOT", tmp_path)
    errors = vm.validate_bundle(bundle)
    n = len(bundle["current"]["canonical"])
    assert len(errors) == n
    assert all(e.startswith("CURRENT pointer missing target:") for e in errors)
    assert any(".github/workflows/mission-control-v2-contract.yml" in e for e in errors)


def test_self_test_passes_on_real_bundle(bundle, rooted):
    vm.self_test(bundle)


def test_self_test_raises_if_validator_blind(bundle, monkeypatch):
    monkeypatch.setattr(vm, "validate_bundle", lambda b: [])
    with pytest.raises(AssertionError, match="MC collision"):
        vm.self_test(bundle)


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda b: b["glossary"]["reservations"]["MC"].update(canonical_meaning="X"), "MC must be reserved"),
        (lambda b: b["glossary"]["reservations"]["MONTE_CARLO"].update(forbidden_new_token="MCS"), "Monte Carlo bare MC"),
        (lambda b: b["glossary"]["reservations"]["MONTE_CARLO"].update(permitted_machine_tokens=["MC"]), "Monte Carlo tokens drift"),
        (lambda b: b["glossary"]["reservations"]["COV"].update(canonical_status="ACTIVE"), "bare COV must be deprecated"),
        (lambda b: b["glossary"].update(coverage_maturity={"MCOV-0": {}}), "MCOV levels"),
        (lambda b: b["methods"]["profiles"]["3PR"].update(phases=["X"]), "3PR drift"),
        (lambda b: b["methods"]["profiles"].update(G3P={}), "G3P incorrectly promoted"),
        (lambda b: b["methods"]["supervisor"].update(phases=[]), "DMAIC phase order drift"),
        (lambda b: b["contract"].update(required_dimensions=["status"]), "telemetry dimensions drift"),
        (lambda b: b["contract"]["g3p_optional_receipt"].update(authority_transfer=True), "G3P receipt cannot transfer"),
        (lambda b: b["status"]["census_scope"].update(sources=[]), "official mission register missing"),
        (lambda b: b["status"]["census_scope"].update(normalized_rows=0), "census normalized_rows mismatch"),
        (lambda b: b["plan"]["dmaic"]["DEFINE"].update(state="OPEN"), "DMAIC DEFINE not frozen"),
        (lambda b: b["closure_receipt"].update(schema="x"), "postmerge control receipt schema"),
        (lambda b: b["closure_receipt"]["exact_head_proof"].update(codex_review="NO"), "receipt review drift"),
        (lambda b: b["current"]["control_closure"].update(merge="0"), "CURRENT merge drift"),
        (lambda b: b["current"].update(engineering_credit_delta=1), "CURRENT engineering_credit_delta=0"),
        (lambda b: b["plan"].update(formal_credit_delta=2), "plan formal_credit_delta=0"),
    ],
)
def test_single_drift_is_detected(bundle, rooted, mutate, expected):
    mutate(bundle)
    errors = vm.validate_bundle(bundle)
    assert any(expected in e for e in errors), errors


def test_collision_matrix_duplicate_and_mapping_drift(bundle, rooted):
    rows = bundle["glossary"]["cross_domain_collision_matrix"]
    dup_token = rows[0]["token"]
    rows.append(copy.deepcopy(rows[0]))
    rows[1]["bare_new_use"] = "ANYTHING"
    errors = vm.validate_bundle(bundle)
    assert "cross-domain collision matrix contains duplicate token rows" in errors
    # duplicated token is skipped (continue) rather than compared
    assert "cross-domain collision matrix mapping drift: " + dup_token not in errors
    assert "cross-domain collision matrix mapping drift: " + rows[1]["token"] in errors


def test_collision_matrix_missing_token(bundle, rooted):
    bundle["glossary"]["cross_domain_collision_matrix"] = [
        r for r in bundle["glossary"]["cross_domain_collision_matrix"] if r["token"] != "PC1"
    ]
    assert "cross-domain collision matrix token set drift" in vm.validate_bundle(bundle)


def test_mission_row_level_checks(bundle, rooted):
    row = bundle["status"]["missions"][0]
    mid = row["mission_id"]
    row.pop("crew")
    row["coverage"]["maturity"] = "MCOV-9"
    row["progress"]["value"] = 1.5
    row["health"]["signal"] = "PURPLE"
    row["lifecycle"]["state"] = "NOPE"
    row["metrics"]["custom"] = []
    row["authority_transfer"] = True
    errors = vm.validate_bundle(bundle)
    for fragment in ["missing dimensions ['crew']", "invalid MCOV", "progress outside 0..1",
                     "health invalid", "lifecycle invalid", "metrics.custom must be an object",
                     "unexpected authority transfer"]:
        assert mid + ": " + fragment in errors, fragment


def test_core_metric_checks(bundle, rooted):
    rows = bundle["status"]["missions"]
    rows[0]["metrics"]["core"] = "not-a-dict"
    rows[1]["metrics"]["core"]["bespoke_metric"] = 1
    first_required = sorted(bundle["contract"]["metrics"]["required_core"])[0]
    rows[2]["metrics"]["core"].pop(first_required)
    errors = vm.validate_bundle(bundle)
    assert rows[0]["mission_id"] + ": metrics.core must be an object" in errors
    assert any(e.startswith(rows[1]["mission_id"] + ": mission-specific metrics") for e in errors)
    assert any(e.startswith(rows[2]["mission_id"] + ": missing required core metrics") for e in errors)


def test_progress_none_is_allowed(bundle, rooted):
    bundle["status"]["missions"][0]["progress"]["value"] = None
    assert vm.validate_bundle(bundle) == []


def test_duplicate_and_drifting_census_ids(bundle, rooted):
    bundle["status"]["missions"].append(copy.deepcopy(bundle["status"]["missions"][0]))
    bundle["status"]["missions"][-1]["mission_id"] = "EXTRA-1"
    bundle["status"]["missions"].append(copy.deepcopy(bundle["status"]["missions"][0]))
    errors = vm.validate_bundle(bundle)
    assert "duplicate mission_id in current census" in errors
    assert any("drift from bound registries" in e and "EXTRA-1" in e for e in errors)


def test_non_terminal_control_skips_terminal_checks(bundle, rooted):
    bundle["plan"]["dmaic"]["CONTROL"]["state"] = "CONTROL_LOOP_ACTIVE"
    bundle["current"]["status"] = "ACTIVE_V2"
    bundle["closure_receipt"] = {}
    assert vm.validate_bundle(bundle) == []


def test_invalid_control_state(bundle, rooted):
    bundle["plan"]["dmaic"]["CONTROL"]["state"] = "BOGUS"
    errors = vm.validate_bundle(bundle)
    assert "DMAIC CONTROL state invalid" in errors
    assert "terminal CONTROL plan/CURRENT state mismatch" in errors
    assert "terminal CONTROL requires plan and CURRENT to agree on adoption-ready state" in errors


def test_terminal_cardinality_failures(bundle, rooted):
    bundle["plan"]["dmaic"]["CONTROL"]["events"] = []
    bundle["plan"]["sprint_plan"] = []
    bundle["status"]["missions"] = [r for r in bundle["status"]["missions"] if r["mission_id"] != "MC-EVO-02"]
    errors = vm.validate_bundle(bundle)
    assert "terminal CONTROL requires exactly one MC-CONTROL-003 event" in errors
    assert "terminal CONTROL requires exactly one MC-S2 sprint" in errors
    assert "terminal CONTROL requires exactly one MC-EVO-02 row" in errors


def test_terminal_event_and_todo_drift(bundle, rooted):
    event = next(e for e in bundle["plan"]["dmaic"]["CONTROL"]["events"] if e.get("id") == "MC-CONTROL-003")
    event["result"] = "OPEN"
    event["review"] = "NONE"
    evo = _evo(bundle)
    evo["todo"]["items"][0]["priority"] = "P9"
    evo["metrics"]["custom"]["control_reentry_count"] = 3
    s2 = next(s for s in bundle["plan"]["sprint_plan"] if s.get("sprint_id") == "MC-S2")
    s2["waves"] = s2["waves"][:-1]
    errors = vm.validate_bundle(bundle)
    for msg in ["terminal CONTROL event result drift", "terminal CONTROL event review drift",
                "terminal CONTROL MC-EVO-02 TODO priority drift", "terminal CONTROL MC-EVO-02 reentry count drift",
                "terminal CONTROL MC-S2 wave set drift"]:
        assert msg in errors


def test_terminal_todo_count(bundle, rooted):
    evo = _evo(bundle)
    evo["todo"]["items"].append({"todo_id": "MORE"})
    errors = vm.validate_bundle(bundle)
    assert "terminal CONTROL requires exactly one MC-EVO-02 terminal TODO" in errors
    assert "terminal CONTROL MC-EVO-02 TODO id drift" not in errors


# ---------------------------------------------------------------- main()

def _run_main(monkeypatch, capsys, argv):
    monkeypatch.setattr(sys, "argv", ["validate_mission_control_v2.py"] + argv)
    with pytest.raises(SystemExit) as exc:
        vm.main()
    return exc.value.code, json.loads(capsys.readouterr().out)


def test_main_pass_emits_receipt(rooted, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MC_SOURCE_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    out_file = tmp_path / "receipt.json"
    code, receipt = _run_main(monkeypatch, capsys, ["--self-test", "--emit-receipt", str(out_file)])
    assert code == 0
    assert receipt["result"] == "PASS"
    assert receipt["source_sha"] == "a" * 40
    assert receipt["mission_rows"] == 18
    assert set(receipt["checks"].values()) == {"PASS"}
    assert receipt["authority_transfer"] is False
    assert json.loads(out_file.read_text(encoding="utf-8")) == receipt


def test_main_falls_back_to_github_sha(rooted, monkeypatch, capsys):
    monkeypatch.delenv("MC_SOURCE_SHA", raising=False)
    monkeypatch.setenv("GITHUB_SHA", "c" * 40)
    code, receipt = _run_main(monkeypatch, capsys, [])
    assert code == 0
    assert receipt["source_sha"] == "c" * 40


def test_main_fail_flags_current_pointer(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MC_SOURCE_SHA", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.setattr(vm, "ROOT", tmp_path)
    code, receipt = _run_main(monkeypatch, capsys, [])
    assert code == 1
    assert receipt["result"] == "FAIL"
    assert receipt["source_sha"] is None
    assert receipt["checks"]["current_pointer"] == "FAIL"
    assert receipt["checks"]["namespace_MC"] == "PASS"
    assert not (tmp_path / "receipt.json").exists()


def test_main_check_classification(tmp_path, monkeypatch, capsys):
    bad = copy.deepcopy(_REAL_BUNDLE)
    bad["glossary"]["reservations"]["MC"]["canonical_meaning"] = "MONTE_CARLO"
    bad["methods"]["mip"]["admission"] = "MANDATORY"
    files = {}
    for key, doc in bad.items():
        p = tmp_path / (key + ".json")
        p.write_text(json.dumps(doc), encoding="utf-8")
        files[key] = p
    monkeypatch.setattr(vm, "FILES", files)
    monkeypatch.setattr(vm, "ROOT", tmp_path)
    code, receipt = _run_main(monkeypatch, capsys, [])
    assert code == 1
    assert receipt["checks"]["namespace_MC"] == "FAIL"
    assert receipt["checks"]["method_profiles"] == "FAIL"
    assert receipt["checks"]["mcov_levels"] == "PASS"
