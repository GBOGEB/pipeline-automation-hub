"""Behavioural tests for mission-control/historian/validate_fleet_open_issue_convergence.py."""
from __future__ import annotations

import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "mission-control" / "historian" / "validate_fleet_open_issue_convergence.py"


def _load():
    spec = importlib.util.spec_from_file_location("cw_validate_fleet_open_issue_convergence", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()

W260_TEXT = """schema: x
bd_queue:
  BD-260.1:
    state: DONE_CONTROL_WATCH
    role: a
  BD-260.2:
    state: DONE_CONTROL_WATCH
  BD-260.3:
    state: DONE_CONTROL_WATCH
  BD-260.4:
    state: DONE_CONTROL_WATCH
  BD-260.5:
    state: DONE_CONTROL_WATCH
  BD-260.6:
    state: NOT_REQUIRED_THIS_CYCLE_REENTER_ON_REAL_CONSUMER_NEED

observed_queue_metrics:
  total_bd_items: 6
  done_control_watch: 5
  active_prove: 0
  dependency_blocked: 0
  dormant_reentry: 1
  executable_frontier_width: 0
tail: end
"""

LM10_TEXT = """schema: lm10
state: W260_CONTROLLED_COMPLETE_REENTRY_GOVERNED
current_development_frontier:
  state: CONTROL_WATCH_ONLY
  provider_WIP_cap: 0
  bd260_6: NOT_REQUIRED_THIS_CYCLE_REENTER_ON_REAL_CONSUMER_NEED
other: x
"""

NESTED = {
    "bd_total": 6,
    "control_count": 5,
    "active_downstream_count": 0,
    "blocked_count": 0,
    "dormant_reentry_count": 1,
    "active_downstream_owner": None,
}


def _fleet_doc():
    # 7 repos; totals 94 open = 31 control + 0 active + 63 blocked.
    def row(control, blocked):
        return {"control": control, "active": [], "blocked": blocked, "open_issues": len(control) + len(blocked)}

    repos = {
        "GBOGEB/cryoplant-project": row(list(range(1590, 1600)), list(range(1, 46))),  # 10 + 45 = 55
        "GBOGEB/ABACUS": row(list(range(2000, 2005)), [1313] + list(range(1400, 1405))),  # 5 + 6
        "GBOGEB/gg_MATH": row(list(range(10, 15)), list(range(20, 24))),  # 5 + 4
        "GBOGEB/pipeline-automation-hub": row([129, 130, 131], list(range(500, 503))),  # 3 + 3
        "GBOGEB/r5": row([1, 2, 3], [4, 5]),  # 3 + 2
        "GBOGEB/r6": row([1, 2, 3], [4, 5]),  # 3 + 2
        "GBOGEB/r7": row([1, 2], [3]),  # 2 + 1
    }
    repos["GBOGEB/cryoplant-project"]["blocked_breakdown"] = {
        "external_source_decision_return": list(range(1, 33)),
    }
    repos["GBOGEB/gg_MATH"]["nested_queue"] = dict(NESTED)
    return {
        "schema": "missioncontrol.fleet_open_issue_convergence.v1",
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "repositories": repos,
        "fleet": {
            "open_issues": 94,
            "control": 31,
            "active": 0,
            "blocked": 63,
            "executable_frontier_width": 0,
            "control_share": 31 / 94,
            "active_share": 0,
            "blocked_share": 63 / 94,
        },
        "proof_integrity": {"prior_result": "FAIL", "new_bd_root": False},
        "active_frontiers": [],
    }


@pytest.fixture
def env(tmp_path, monkeypatch):
    p = tmp_path / "fleet.json"
    w = tmp_path / "w260.yaml"
    l = tmp_path / "lm10.yaml"
    p.write_text(json.dumps(_fleet_doc()), encoding="utf-8")
    w.write_text(W260_TEXT, encoding="utf-8")
    l.write_text(LM10_TEXT, encoding="utf-8")
    monkeypatch.setattr(m, "P", p)
    monkeypatch.setattr(m, "W260", w)
    monkeypatch.setattr(m, "LM10", l)
    return p, w, l


def _rewrite_json(p, mutate):
    d = json.loads(p.read_text(encoding="utf-8"))
    mutate(d)
    p.write_text(json.dumps(d), encoding="utf-8")


# --- helpers -------------------------------------------------------------


def test_section_stops_at_next_top_level_key():
    sec = m._section("a:\n  x: 1\n\n  y: 2\nb:\n  z: 3\n", "a:")
    assert sec == "  x: 1\n\n  y: 2"


def test_section_missing_heading_raises():
    with pytest.raises(AssertionError, match="missing YAML section: nope:"):
        m._section("a:\n  x: 1\n", "nope:")


def test_scalar_and_top_scalar():
    assert m._scalar("  k: v \n  j: w", "j") == "w"
    with pytest.raises(AssertionError, match="missing YAML scalar: q"):
        m._scalar("  k: v", "q")
    assert m._top_scalar("state: S\n  state: T", "state") == "S"
    with pytest.raises(AssertionError, match="missing top-level YAML scalar: q"):
        m._top_scalar("a: 1", "q")


def test_bd_states_parses_and_rejects_duplicates():
    states = m._bd_states(W260_TEXT)
    assert states["BD-260.1"] == "DONE_CONTROL_WATCH"
    assert len(states) == 6
    # an entry without a state line is skipped
    assert m._bd_states("bd_queue:\n  BD-1:\n    role: x\n") == {}
    dup = "bd_queue:\n  BD-1:\n    state: A\n  BD-1:\n    state: B\n"
    with pytest.raises(AssertionError):
        m._bd_states(dup)


def test_classify_bd_states_all_buckets_and_unknown():
    counts = m._classify_bd_states(
        {
            "a": "DONE_CONTROL_WATCH",
            "b": "ACTIVE_PROVE",
            "c": "DEPENDENCY_BLOCKED",
            "d": "NOT_REQUIRED_THIS_CYCLE_REENTER_ON_REAL_CONSUMER_NEED",
        }
    )
    assert counts == {"control": 1, "active": 1, "blocked": 1, "dormant": 1}
    with pytest.raises(AssertionError, match="unclassified"):
        m._classify_bd_states({"x": "WEIRD"})


def test_w260_projection_accepts_and_rejects():
    m._assert_w260_projection(W260_TEXT, dict(NESTED))
    bad = dict(NESTED, control_count=4)
    with pytest.raises(AssertionError):
        m._assert_w260_projection(W260_TEXT, bad)


# --- main / self-test ---------------------------------------------------


def test_main_passes_on_consistent_fixture(env, capsys):
    m.main()
    assert "PASS_FLEET_OPEN_ISSUE_CONVERGENCE_94_31_0_63" in capsys.readouterr().out


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema="other"),
        lambda d: d.update(authority_transfer=True),
        lambda d: d["repositories"].pop("GBOGEB/r7"),
        lambda d: d["repositories"]["GBOGEB/r7"].update(active=[1]),  # overlap with control
        lambda d: d["repositories"]["GBOGEB/r7"].update(open_issues=99),
        lambda d: d["fleet"].update(control=30),
        lambda d: d["repositories"]["GBOGEB/ABACUS"]["blocked"].remove(1313),
        lambda d: d.update(active_frontiers=["x"]),
        lambda d: d["repositories"]["GBOGEB/gg_MATH"]["nested_queue"].update(bd_total=7),
    ],
)
def test_main_rejects_drift(env, mutate):
    p, _, _ = env
    _rewrite_json(p, mutate)
    with pytest.raises((AssertionError, KeyError)):
        m.main()


def test_main_rejects_lm10_frontier_drift(env):
    _, _, l = env
    l.write_text(LM10_TEXT.replace("provider_WIP_cap: 0", "provider_WIP_cap: 1"), encoding="utf-8")
    with pytest.raises(AssertionError):
        m.main()


def test_self_test_detects_mutation(env, capsys):
    m._self_test()
    assert "PASS_FLEET_W260_CANONICAL_BD_MUTATION" in capsys.readouterr().out


def test_self_test_fails_when_validation_is_blind(env, monkeypatch):
    monkeypatch.setattr(m, "_assert_w260_projection", lambda text, nested: None)
    with pytest.raises(AssertionError, match="mutation escaped"):
        m._self_test()


def test_real_committed_data_via_cli(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(MODULE_PATH), "--self-test"])
    runpy.run_path(str(MODULE_PATH), run_name="__main__")
    monkeypatch.setattr(sys, "argv", [str(MODULE_PATH)])
    runpy.run_path(str(MODULE_PATH), run_name="__main__")
    out = capsys.readouterr().out
    assert "PASS_FLEET_W260_CANONICAL_BD_MUTATION" in out
    assert "PASS_FLEET_OPEN_ISSUE_CONVERGENCE_94_31_0_63" in out
