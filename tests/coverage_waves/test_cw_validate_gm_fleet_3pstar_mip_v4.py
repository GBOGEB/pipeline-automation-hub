"""Behavioural tests for mission-control/grand-missions/validate_gm_fleet_3pstar_mip_v4.py."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GM_DIR = REPO_ROOT / "mission-control" / "grand-missions"
MOD_PATH = GM_DIR / "validate_gm_fleet_3pstar_mip_v4.py"
CTRL = "GM_FLEET_3PSTAR_MIP_20260919T0738_v4.json"
DASH = "GM_FLEET_DASHBOARD_V11_DATA.json"
REG = "GRAND_MISSION_REGISTRY.json"
HTML = "dashboard/GM_FLEET_CONTROL_DASHBOARD_v11.html"
OUTPUTS = ["out/a.json", "out/b.md"]


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_gm_fleet_3pstar_mip_v4", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mod():
    return _load()


def _inputs():
    data = {n: json.loads((GM_DIR / n).read_text(encoding="utf-8")) for n in (CTRL, DASH, REG)}
    # Point the Perpetuate outputs at synthetic files created in tmp_path.
    data[CTRL]["mip"]["Perpetuate"]["outputs"] = list(OUTPUTS)
    data["html"] = (GM_DIR / HTML).read_text(encoding="utf-8")
    return data


def _write_env(tmp_path, data, make_outputs=True):
    repo = tmp_path / "repo"
    root = repo / "gm"
    (root / "dashboard").mkdir(parents=True)
    for name in (CTRL, DASH, REG):
        (root / name).write_text(json.dumps(data[name]), encoding="utf-8")
    (root / HTML).write_text(data["html"], encoding="utf-8")
    if make_outputs:
        for rel in OUTPUTS:
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")
    return repo, root


def _run(mod, monkeypatch, tmp_path, data, make_outputs=True):
    repo, root = _write_env(tmp_path, data, make_outputs)
    monkeypatch.setattr(mod, "ROOT", root)
    monkeypatch.setattr(mod, "REPO", repo)
    out = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--source-sha", "s1", "--out", str(out)])
    rc = mod.main()
    return rc, json.loads(out.read_text(encoding="utf-8"))


def test_load_reads_relative_to_root(mod, monkeypatch, tmp_path):
    (tmp_path / "a.json").write_text("[1, 2]", encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    assert mod.load("a.json") == [1, 2]


def test_pass_receipt(mod, monkeypatch, tmp_path, capsys):
    rc, receipt = _run(mod, monkeypatch, tmp_path, _inputs())
    assert rc == 0
    assert receipt["result"] == "PASS_GM_FLEET_3PSTAR_MIP_V4"
    assert receipt["check_count"] == 15
    assert all(receipt["checks"].values())
    assert receipt["source_sha"] == "s1"
    assert receipt["gm_iv_state"] == "ACTIVE_8_OF_8"
    assert receipt["gm_v_state"] == "HELD"
    assert receipt["gm_iv_children"] == [] and receipt["gm_v_children"] == []
    assert receipt["rank0"] == "GBOGEB/cryoplant-project#923"
    assert receipt["authority_transfer"] is False
    assert json.loads(capsys.readouterr().out) == receipt


def _set(name, path, value):
    def apply(data):
        obj = data[name]
        for k in path[:-1]:
            obj = obj[k]
        obj[path[-1]] = value
    return apply


def _gm(mid, key, value):
    def apply(data):
        for m in data[REG]["grand_missions"]:
            if m["id"] == mid:
                m[key] = value
    return apply


def _html_replace(old, new):
    def apply(data):
        assert old in data["html"]
        data["html"] = data["html"].replace(old, new)
    return apply


def _html_append(text):
    def apply(data):
        data["html"] += text
    return apply


def _scout_rank(data):
    data[DASH]["planes"]["reconnaissance"]["scout_c_depth_board"][0]["comparative_rank"] = 1


def _bd_steps(data):
    data[DASH]["planes"]["global_bd"]["freshest_bound_child_probe"]["attempts"][0]["steps"] = 2


@pytest.mark.parametrize(
    "mutate, failing",
    [
        (_set(CTRL, ["three_pr", "Refresh", "qps_issue_923"], "CLOSED"), "01_refresh_exact"),
        (_set(CTRL, ["three_pr", "Probe", "qps_probe_was_retriggered"], True), "02_probe_zero_step_no_rerun"),
        (_set(CTRL, ["three_pr", "Rank", "no_blind_rerun"], False), "03_rank_first_red"),
        (_set(CTRL, ["mip", "Innovate", "result"], "PASS"), "04_mip_sequential"),
        (_gm("GM-IV", "children", ["x"]), "05_active8_no_children"),
        (_scout_rank, "06_scout_c_depth_exact"),
        (_set(DASH, ["planes", "canonical_admission", "gm_v_launch_authorized"], True), "07_gmv_held"),
        (_set(DASH, ["planes", "analytics", "bt", "observed_pairs"], 11), "08_analytics_nonpromotional"),
        (_bd_steps, "09_bd_plane"),
        (_set(CTRL, ["three_p3"], "AUTHORIZED"), "10_3pc_hold"),
        (_set(CTRL, ["engineering_credit_delta"], 1), "11_authority_zero"),
        (_html_replace("Global BD", "Global XX"), "12_html_planes"),
        (_html_append("<script>el.innerHTML=1</script>"), "13_safe_dom_rendering"),
        (_set(DASH, ["quality_fixforward", "repair"], "OTHER"), "14_quality_fixforward_bound"),
    ],
)
def test_each_check_fails_independently(mod, monkeypatch, tmp_path, mutate, failing):
    data = _inputs()
    mutate(data)
    rc, receipt = _run(mod, monkeypatch, tmp_path, data)
    assert rc == 1
    assert receipt["result"] == "FAIL_GM_FLEET_3PSTAR_MIP_V4"
    assert [k for k, v in receipt["checks"].items() if not v] == [failing]


def test_missing_perpetuate_output_fails_check_15(mod, monkeypatch, tmp_path):
    rc, receipt = _run(mod, monkeypatch, tmp_path, _inputs(), make_outputs=False)
    assert rc == 1
    assert [k for k, v in receipt["checks"].items() if not v] == ["15_perpetuate_outputs"]


def test_real_committed_data_current_outcome(mod, monkeypatch, tmp_path):
    # Checks 1-14 hold on the committed data. Check 15 depends on whether every
    # Perpetuate output listed in the committed v4 control is present in the
    # tree, so derive the expected outcome from the tree instead of pinning it.
    ctrl = json.loads((GM_DIR / CTRL).read_text(encoding="utf-8"))
    outputs = ctrl["mip"]["Perpetuate"]["outputs"]
    all_present = all((REPO_ROOT / p).is_file() for p in outputs)
    out = tmp_path / "real.json"
    monkeypatch.setattr(sys, "argv", ["prog", "--source-sha", "real", "--out", str(out)])
    rc = mod.main()
    receipt = json.loads(out.read_text(encoding="utf-8"))
    failing = [k for k, v in receipt["checks"].items() if not v]
    if all_present:
        assert rc == 0
        assert receipt["result"] == "PASS_GM_FLEET_3PSTAR_MIP_V4"
        assert failing == []
    else:
        assert rc == 1
        assert failing == ["15_perpetuate_outputs"]
