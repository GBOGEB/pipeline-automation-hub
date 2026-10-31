"""Behavioural tests for mission-control/qps-triage-ultra/crew/measured/validate_exposure_pca_control.py.

The module validates at import time using paths derived from __file__, so each test
executes it with __file__ pointing into a synthetic tmp_path tree.
"""
import copy
import importlib.util
import itertools
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "qps-triage-ultra" / "crew" / "measured"
MOD_PATH = MOD_DIR / "validate_exposure_pca_control.py"
REAL_CONTROL_PATH = MOD_DIR / "history" / "CREW_EXPOSURE_PCA_CONTROL_RETURN_v1.json"
_counter = itertools.count()


def _exec(fake_file):
    spec = importlib.util.spec_from_file_location("cw_validate_exposure_pca_control_%d" % next(_counter), MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    if fake_file is not None:
        mod.__file__ = str(fake_file)
    with pytest.raises(SystemExit) as exc:
        spec.loader.exec_module(mod)
    return exc.value.code


def _components(ratios):
    return [{"component": "PC%d" % (i + 1), "explained_variance_ratio": r} for i, r in enumerate(ratios)]


def _control():
    return {
        "schema": "missioncontrol.crew_exposure_pca_control_return.v1",
        "status": "CONTROL_READY_MEASURED_REPEAT_SMALL_N",
        "authority_transfer": False,
        "competency_promotions": 0,
        "causal_interpretation_allowed": False,
        "sample_rank_cap": 3,
        "repeat_gate": {
            "exact_head_pass": True,
            "merged_master_pass": True,
            "bt_observed_pairs": 12,
            "bt_single_cell_wins": 8.0,
            "bt_paired_cell_wins": 4.0,
        },
        "evidence_runs": [
            {"source_sha": "a" * 40, "components": _components([0.6, 0.2, 0.1])},
            {"source_sha": "b" * 40, "components": _components([0.601, 0.2, 0.1])},
        ],
    }


def _registry():
    return {"grand_missions": [
        {"id": "GM-IV", "state": "STAGED_ACTIVE_RECON_2_OF_8", "children": [],
         "candidate_frontiers": ["GM-IV-F01", "GM-IV-F02"],
         "unfilled_frontier_slots": ["GM-IV-F03", "GM-IV-F04"]},
        {"id": "GM-V", "state": "HELD", "children": []},
    ]}


def _run(tmp_path, capsys, control=None, registry=None):
    measured = tmp_path / "mc" / "qps" / "crew" / "measured"
    (measured / "history").mkdir(parents=True)
    (tmp_path / "mc" / "grand-missions").mkdir(parents=True)
    (measured / "history" / "CREW_EXPOSURE_PCA_CONTROL_RETURN_v1.json").write_text(
        json.dumps(control or _control()), encoding="utf-8")
    (tmp_path / "mc" / "grand-missions" / "GRAND_MISSION_REGISTRY.json").write_text(
        json.dumps(registry or _registry()), encoding="utf-8")
    code = _exec(measured / "exposure_entry.py")
    return code, json.loads(capsys.readouterr().out)


def test_conforming_control_passes(tmp_path, capsys):
    code, out = _run(tmp_path, capsys)
    assert code == 0
    assert out["status"] == "PASS"
    assert out["errors"] == []
    assert out["max_explained_variance_repeat_delta"] == pytest.approx(0.001)
    assert out["sample_rank_cap"] == 3
    assert out["bt_observed_pairs"] == 12
    assert out["schema"] == "missioncontrol.crew_exposure_pca_control_validation.v1"
    assert (out["gm_iv_reconnaissance"], out["gm_iv_children"], out["gm_v"]) == ("2/8", 0, "HELD")


def _cm(fn):
    c = _control()
    fn(c)
    return c


def _rm(fn):
    r = _registry()
    fn(r)
    return r


def _gm(r, gid):
    return next(m for m in r["grand_missions"] if m["id"] == gid)


CONTROL_CASES = [
    (lambda c: c.update(schema="x"), ["schema"]),
    (lambda c: c.update(status="x"), ["control status"]),
    (lambda c: c.update(authority_transfer=True), ["authority transfer"]),
    (lambda c: c.update(competency_promotions=1), ["competency promotion"]),
    (lambda c: c.update(causal_interpretation_allowed=True), ["causal interpretation"]),
    (lambda c: c.update(sample_rank_cap=4), ["small-n rank cap"]),
    (lambda c: c["repeat_gate"].update(exact_head_pass=False), ["exact head pass"]),
    (lambda c: c["repeat_gate"].update(merged_master_pass=False), ["merged master pass"]),
    (lambda c: c["repeat_gate"].update(bt_observed_pairs=11), ["BT observed pairs"]),
    (lambda c: c["repeat_gate"].update(bt_single_cell_wins=7.0), ["BT single wins"]),
    (lambda c: c["repeat_gate"].update(bt_paired_cell_wins=5.0), ["BT paired wins"]),
    (lambda c: c["evidence_runs"].append(copy.deepcopy(c["evidence_runs"][1]) | {"source_sha": "c" * 40}),
     ["two control evidence runs", "distinct control SHAs"]),
    (lambda c: c["evidence_runs"][1].update(source_sha="a" * 40), ["distinct control SHAs"]),
    (lambda c: c["evidence_runs"][1].update(source_sha="abc"), ["40-char SHAs"]),
    (lambda c: c["evidence_runs"][1]["components"].append({"explained_variance_ratio": 0.0}),
     ["three components each"]),
    (lambda c: c["evidence_runs"][1]["components"][2].update(explained_variance_ratio=0.2),
     ["PCA explained-variance repeat drift below 0.01"]),
]


@pytest.mark.parametrize("mutate,errors", CONTROL_CASES)
def test_control_errors(tmp_path, capsys, mutate, errors):
    code, out = _run(tmp_path, capsys, control=_cm(mutate))
    assert code == 1
    assert out["status"] == "FAIL"
    assert out["errors"] == errors


REGISTRY_CASES = [
    (lambda r: _gm(r, "GM-IV").update(state="ACTIVE_8_OF_8"), ["GM-IV recon state"]),
    (lambda r: _gm(r, "GM-IV").update(children=["c"]), ["GM-IV zero children"]),
    (lambda r: _gm(r, "GM-IV").update(candidate_frontiers=["GM-IV-F01"]), ["GM-IV F01/F02 candidates only"]),
    (lambda r: _gm(r, "GM-IV").update(unfilled_frontier_slots=["GM-IV-F04"]), ["F03 unfilled"]),
    (lambda r: _gm(r, "GM-IV").update(unfilled_frontier_slots=["GM-IV-F03"]), ["F04 unfilled"]),
    (lambda r: _gm(r, "GM-V").update(state="ACTIVE"), ["GM-V held"]),
    (lambda r: _gm(r, "GM-V").update(children=["c"]), ["GM-V zero children"]),
]


@pytest.mark.parametrize("mutate,errors", REGISTRY_CASES)
def test_registry_errors(tmp_path, capsys, mutate, errors):
    code, out = _run(tmp_path, capsys, registry=_rm(mutate))
    assert code == 1
    assert out["errors"] == errors


def test_require_appends_only_on_false(tmp_path, capsys):
    _run(tmp_path, capsys)
    # Re-load to get a module object with a populated namespace for direct calls.
    measured = tmp_path / "mc" / "qps" / "crew" / "measured"
    spec = importlib.util.spec_from_file_location("cw_validate_exposure_pca_control_direct", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(measured / "exposure_entry.py")
    with pytest.raises(SystemExit):
        spec.loader.exec_module(mod)
    capsys.readouterr()
    mod.errors.clear()
    mod.require(True, "kept-out")
    mod.require(False, "kept-in")
    assert mod.errors == ["kept-in"]


def test_real_committed_data_current_outcome(capsys):
    """Committed control vs committed registry.

    The control return was frozen while GM-IV was at RECON 2/8; the registry has since
    promoted GM-IV (stage superseded), so the four GM-IV fleet-invariant checks now report
    FAIL while every control-return check still passes.
    """
    code = _exec(None)
    out = json.loads(capsys.readouterr().out)
    registry = json.loads((REPO_ROOT / "mission-control" / "grand-missions" / "GRAND_MISSION_REGISTRY.json")
                          .read_text(encoding="utf-8"))
    gm4 = next(m for m in registry["grand_missions"] if m["id"] == "GM-IV")
    control = json.loads(REAL_CONTROL_PATH.read_text(encoding="utf-8"))
    assert out["sample_rank_cap"] == control["sample_rank_cap"]
    assert out["max_explained_variance_repeat_delta"] < 0.01
    control_errors = {"schema", "control status", "authority transfer", "competency promotion",
                      "causal interpretation", "small-n rank cap", "PCA explained-variance repeat drift below 0.01"}
    assert not control_errors & set(out["errors"])
    if gm4["state"] == "STAGED_ACTIVE_RECON_2_OF_8":
        assert code == 0 and out["status"] == "PASS"
    else:
        assert code == 1
        assert out["status"] == "FAIL"
        assert "GM-IV recon state" in out["errors"]
