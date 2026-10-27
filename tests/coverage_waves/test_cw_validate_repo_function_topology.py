"""Behavioural tests for mission-control/qps-triage-ultra/topology/validate_repo_function_topology.py."""
import copy
import importlib.util
import runpy
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "topology"
MOD_PATH = MOD_DIR / "validate_repo_function_topology.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_repo_function_topology", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


topo = _load()
REAL = yaml.safe_load((MOD_DIR / "QPS_REPO_FUNCTION_TOPOLOGY_v1.yaml").read_text(encoding="utf-8"))


def _repo(data, name):
    return next(e for e in data["repositories"] if e["repo"] == name)


def _run(tmp_path, monkeypatch, data):
    p = tmp_path / "topology.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(topo, "TOPOLOGY", p)
    return topo.main()


def test_require_passes_and_raises():
    topo.require(True, "unused")
    with pytest.raises(AssertionError, match="^boom$"):
        topo.require(False, "boom")


def test_real_committed_topology_passes(capsys):
    assert topo.main() == 0
    out = capsys.readouterr().out
    n = len(REAL["repositories"])
    assert out == f"PASS repo-function topology: {n} repositories; authority_transfer=false; H4 W2 HOLD preserved\n"


def test_synthetic_copy_passes(tmp_path, monkeypatch, capsys):
    assert _run(tmp_path, monkeypatch, copy.deepcopy(REAL)) == 0
    assert capsys.readouterr().out.startswith("PASS repo-function topology:")


def _m(fn):
    d = copy.deepcopy(REAL)
    fn(d)
    return d


def _set(*path_value):
    *path, value = path_value

    def fn(d):
        node = d
        for k in path[:-1]:
            node = node[k]
        node[path[-1]] = value
    return fn


def _repo_set(name, key, value):
    def fn(d):
        _repo(d, name)[key] = value
    return fn


def _drop_repo(name):
    def fn(d):
        d["repositories"] = [e for e in d["repositories"] if e["repo"] != name]
    return fn


def _dup_repo(d):
    d["repositories"].append(copy.deepcopy(d["repositories"][0]))


def _add_child(d):
    d["repositories"].append({"repo": "GBOGEB/x", "state": "ACTIVE_USED", "function": "QPS_CHILD_AUTHORITY"})


def _drop_prohibition(item):
    def fn(d):
        e = _repo(d, "GBOGEB/Q_engineering_tools")
        e["prohibitions"] = [p for p in e["prohibitions"] if p != item]
    return fn


def _reserve_without_trigger(state):
    def fn(d):
        d["repositories"].append({"repo": "GBOGEB/r", "state": state, "function": "F"})
    return fn


CASES = [
    (_set("schema", "x"), "unexpected schema"),
    (_set("mission", "H3"), "wrong mission owner"),
    (_set("authority_transfer", True), "authority transfer must remain false"),
    (_set("formal_credit_delta", "engineering", 1), "topology routing must create zero formal credit"),
    (_dup_repo, "repository entries must be unique"),
    (_drop_repo("GBOGEB/CODEX"), "missing required topology repo: GBOGEB/CODEX"),
    (_repo_set("GBOGEB/ABACUS", "state", "DORMANT_CANDIDATE"), "unexpected state for GBOGEB/ABACUS"),
    (_repo_set("GBOGEB/gg_MATH", "function", "X"), "unexpected function for GBOGEB/gg_MATH"),
    (_add_child, "exactly one QPS child authority is allowed"),
    (_drop_prohibition("cannot_compensate_cryoplant_issue_923"), "execution carrier must not compensate #923"),
    (_drop_prohibition("cannot_promote_QPS_source_authority"), "execution carrier must not promote source authority"),
    (_reserve_without_trigger("CONDITIONAL_RESERVE"), "GBOGEB/r needs an explicit activation trigger"),
    (_reserve_without_trigger("DORMANT_CANDIDATE"), "GBOGEB/r needs an explicit activation trigger"),
    (_repo_set("GBOGEB/stale", "exploit_next", ["x"]), "maintenance-only repo GBOGEB/stale must have no exploit allocation"),
    (_set("routing_selector", "engineering_source_disposition", "x"), "engineering route drift"),
    (_set("routing_selector", "semantics_provenance", "x"), "semantic route drift"),
    (_set("routing_selector", "independent_measurement_runtime_QA", "x"), "measurement route drift"),
    (_set("routing_selector", "exact_payload_execution_when_authority_repo_runtime_blocked", "x"),
     "runtime-carrier route drift"),
    (_set("routing_selector", "generic_math_provider", "x"), "math-provider route drift"),
    (_set("routing_selector", "orchestration_triage_topology", "x"), "orchestration route drift"),
    (_set("current_gate", "h4_w2_3pc_mip_i", "PASS"), "H4 W2 must remain fail-closed"),
    (_set("current_gate", "h4_w3_3p3_mip_p", "PASS"), "H4 W3 must remain gated by W2"),
    (_set("current_gate", "independent_non_h4_progress", "m08_mip2_seed", "X"), "M08 seed state drift"),
    (_set("current_gate", "post_mip2d_once_only", "chain", ["GBOGEB/CODEX"]), "3P3 chain drift"),
    (_set("current_gate", "post_mip2d_once_only", "terminal_rule", "CONTINUE"), "3P3 must terminate in STOP/CONTROL"),
]


@pytest.mark.parametrize("mutate,message", CASES)
def test_fail_closed_messages(tmp_path, monkeypatch, mutate, message):
    with pytest.raises(AssertionError) as exc:
        _run(tmp_path, monkeypatch, _m(mutate))
    assert str(exc.value) == message


def test_maintenance_only_without_exploit_key_passes(tmp_path, monkeypatch):
    d = copy.deepcopy(REAL)
    _repo(d, "GBOGEB/stale").pop("exploit_next", None)
    assert _run(tmp_path, monkeypatch, d) == 0


def test_main_guard_pass_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith("PASS repo-function topology:")


@pytest.mark.parametrize("payload,message", [
    ({"schema": "nope"}, "FAIL repo-function topology: unexpected schema\n"),
    ({"schema": "qps-triage-ultra/repo-function-topology/1.0"}, "FAIL repo-function topology: 'mission'\n"),
])
def test_main_guard_failure_reports_to_stderr(monkeypatch, capsys, payload, message):
    # runpy re-imports yaml from sys.modules, so patching safe_load feeds the guard a bad document.
    monkeypatch.setattr(yaml, "safe_load", lambda _text: payload)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert exc.value.code == 1
    assert capsys.readouterr().err == message
