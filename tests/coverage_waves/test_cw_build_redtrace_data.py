"""Behavioural tests for mission-control/jade_temple/tools/build_redtrace_data.py.

Existing JADE tests read the committed federation snapshot and check that assemble() rejects an
authority-bearing report. These drive _short/project/assemble/main over synthetic
gogreen.red_trace.v1 reports in tmp_path. The committed data/RED_TRACE_FEDERATION_N8.json is never
written: main() always gets --out in tmp_path, or OUT is monkeypatched.
"""
import copy
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "mission-control" / "jade_temple" / "tools"
MOD_PATH = TOOLS / "build_redtrace_data.py"

# The module loads its sibling private_boundary.py by path from its own __file__ at import time, so it is
# loaded from its real location; its output constant OUT is monkeypatched wherever main() could use it.
_spec = importlib.util.spec_from_file_location("cw_build_redtrace_data_mod", MOD_PATH)
brd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(brd)

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


@pytest.fixture
def identity_pb(monkeypatch):
    monkeypatch.setattr(brd, "PB", types.SimpleNamespace(project=lambda d: d))


def wf(name, cls, current="RED", **extra):
    w = {"name": name, "path": ".github/workflows/" + name + ".yml", "class": cls, "current": current}
    w.update(extra)
    return w


def report(name, *, workflows=None, red=1, red_stale=0, runs=10, observed="2026-10-01T00:00:00Z",
           counts=None, truncated=None):
    window = {"runs": runs}
    if truncated is not None:
        window["truncated_workflows"] = truncated
    workflows = workflows if workflows is not None else [
        wf("ci", "GREEN_TO_RED", break_={}),
        wf("lint", "STABLE_GREEN", current="GREEN"),
    ]
    for w in workflows:
        if "break_" in w:
            w.pop("break_")
            w["break"] = {"first_red_sha": SHA_A, "first_red_run": 12345678901, "red_hours": 3,
                          "failing": [{"job": "test", "steps": ["pytest"]}]}
    return {
        "schema": "gogreen.red_trace.v1",
        "authority": {"merge_authorized": False},
        "repository": "GBOGEB/" + name,
        "branch": "main",
        "observed_at_utc": observed,
        "digest_sha256": "d-" + name,
        "workflows": workflows,
        "window": window,
        "counts": counts if counts is not None else {"GREEN_TO_RED": 1, "STABLE_GREEN": len(workflows) - 1},
        "currently_red": ["x"] * red,
        "currently_red_stale": ["x"] * red_stale,
        "shared_break_roots": ["root%d" % i for i in range(10)],
    }


def all_reports(**overrides):
    reps = {n: report(n) for n in brd.CORE}
    reps.update(overrides)
    return reps


# --- _short ----------------------------------------------------------------------------------

@pytest.mark.parametrize("value", [None, {}])
def test_short_of_empty_window_is_none(value):
    assert brd._short(value) is None


def test_short_keeps_only_whitelisted_keys_and_first_three_failures():
    t = {"last_green_sha": SHA_A, "first_red_sha": SHA_B, "red_hours": 5, "red_streak_runs": 2,
         "suspect_commit_count": 4, "noise": "drop me",
         "failing": [{"job": "j%d" % i, "steps": ["s1", "s2"]} for i in range(5)]}
    out = brd._short(t)
    assert out == {"last_green_sha": SHA_A, "first_red_sha": SHA_B, "red_hours": 5, "red_streak_runs": 2,
                   "suspect_commit_count": 4, "failing": ["j0: s1, s2", "j1: s1, s2", "j2: s1, s2"]}


def test_short_without_failing_key_gives_empty_list():
    assert brd._short({"recovery_sha": SHA_C}) == {"recovery_sha": SHA_C, "failing": []}


# --- project ---------------------------------------------------------------------------------

def test_project_window_source_priority_and_flags():
    workflows = [
        wf("a-break", "FLAKY", break_={}, red_episodes=[{"red_hours": 99}], flips=[1, 2, 3],
           stale=1, latest_age_days=4, pinned_historical_ids=[7], history_truncated=True),
        wf("b-episode", "EVERRED", red_episodes=[{"red_hours": 1}, {"red_hours": 2, "first_red_sha": SHA_B}]),
        wf("c-first", "GREEN_TO_RED", first_red={"sha": SHA_C, "run_id": 42, "at": "2026-09-30T00:00:00Z",
                                                   "red_hours": 7}),
        wf("d-none", "UNKNOWN_NO_TERMINAL", current=None, red_episodes=[]),
        wf("e-green", "STABLE_GREEN", current="GREEN"),
    ]
    rep = report("CODEX", workflows=workflows, truncated=2)
    p = brd.project(rep)
    rows = {w["name"]: w for w in p["non_green"]}
    assert "e-green" not in rows
    assert rows["a-break"]["window"]["first_red_sha"] == SHA_A
    assert rows["a-break"]["window"]["failing"] == ["test: pytest"]
    assert rows["a-break"]["flips"] == 3
    assert rows["a-break"]["stale"] is True and rows["a-break"]["pinned"] is True
    assert rows["a-break"]["history_truncated"] is True and rows["a-break"]["age_days"] == 4
    assert rows["b-episode"]["window"] == {"red_hours": 2, "first_red_sha": SHA_B, "failing": []}
    assert rows["b-episode"]["stale"] is False and rows["b-episode"]["pinned"] is False
    assert rows["b-episode"]["flips"] == 0 and rows["b-episode"]["age_days"] is None
    assert rows["c-first"]["window"] == {"first_red_sha": SHA_C, "first_red_run": 42,
                                         "first_red_at": "2026-09-30T00:00:00Z", "red_hours": 7, "failing": []}
    assert rows["d-none"]["window"] is None
    assert p["workflows_traced"] == 5
    assert p["truncated_workflows"] == 2
    assert p["shared_break_roots"] == ["root%d" % i for i in range(8)]
    assert p["source_digest"] == "d-CODEX"
    assert p["currently_red"] == 1 and p["currently_red_stale"] == 0


def test_project_sorts_red_first_then_class_order_then_name():
    workflows = [
        wf("z", "RED_TO_GREEN", current="GREEN"),
        wf("y", "MYSTERY", current="RED"),
        wf("x", "FLAKY", current="RED"),
        wf("w", "GREEN_TO_RED", current="RED"),
        wf("v", "EVERRED", current="RED"),
        wf("u", "EVERRED", current="RED"),
        wf("t", "UNKNOWN_NO_TERMINAL", current=None),
        wf("s", "GREEN_TO_RED", current="GREEN"),
    ]
    p = brd.project(report("CODEX", workflows=workflows))
    assert [w["name"] for w in p["non_green"]] == ["w", "u", "v", "x", "y", "s", "z", "t"]


def test_project_defaults_truncated_workflows_to_zero():
    assert brd.project(report("CODEX"))["truncated_workflows"] == 0


# --- assemble --------------------------------------------------------------------------------

def test_assemble_totals_classes_and_order(identity_pb):
    reps = all_reports()
    reps["ABACUS"] = report("ABACUS", red=3, red_stale=2, runs=7, observed="2026-10-05T00:00:00Z",
                            counts={"GREEN_TO_RED": 1, "EVERRED": 4})
    reps["gg_MATH"]["workflows"][0]["pinned_historical_ids"] = [1]
    data = brd.assemble(reps)
    assert data["schema"] == "jade.temple.redtrace_federation.v1"
    assert data["iteration"] == "N+8"
    assert [r["short"] for r in data["repositories"]] == brd.CORE
    assert [r["role"] for r in data["repositories"]] == [brd.ROLE[n] for n in brd.CORE]
    assert data["observed_at_utc"] == "2026-10-05T00:00:00Z"
    tot = data["totals"]
    assert tot["workflows"] == 10
    assert tot["runs"] == 47
    assert tot["red"] == 7 and tot["red_stale"] == 2 and tot["red_fresh"] == 5
    assert tot["classes"] == {"GREEN_TO_RED": 5, "STABLE_GREEN": 4, "EVERRED": 4}
    assert tot["pinned_red"] == 1
    assert data["authority"] == {"merge_authorized": False, "root_closure_credit": None, "admission": "HOLD"}


def test_assemble_digest_is_sha256_of_body_and_deterministic(identity_pb):
    data = brd.assemble(all_reports())
    body = {k: v for k, v in data.items() if k != "digest_sha256"}
    assert data["digest_sha256"] == hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    assert brd.assemble(all_reports()) == data


def test_assemble_pinned_green_workflow_is_not_pinned_red(identity_pb):
    reps = all_reports()
    reps["CODEX"]["workflows"][0].update(current="GREEN", pinned_historical_ids=[1])
    assert brd.assemble(reps)["totals"]["pinned_red"] == 0


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(schema="gogreen.red_trace.v0"),
    lambda r: r.pop("authority"),
    lambda r: r.update(authority={"merge_authorized": None}),
    lambda r: r.update(authority={"merge_authorized": True}),
], ids=["schema", "no_authority", "authority_none", "authority_true"])
def test_assemble_rejects_invalid_report_with_repo_name(identity_pb, mutate):
    reps = all_reports()
    mutate(reps["cryoplant-project"])
    with pytest.raises(ValueError, match="^cryoplant-project: invalid or authority-bearing red-trace report$"):
        brd.assemble(reps)


def test_assemble_requires_every_core_repo(identity_pb):
    reps = all_reports()
    del reps["gg_MATH"]
    with pytest.raises(KeyError):
        brd.assemble(reps)


def test_assemble_projects_private_repo_rows_through_boundary(monkeypatch):
    pb = importlib.util.spec_from_file_location("cw_brd_private_boundary", TOOLS / "private_boundary.py")
    pbm = importlib.util.module_from_spec(pb)
    pb.loader.exec_module(pbm)
    boundary = pbm.Boundary(repos=("GBOGEB/cryoplant-project",))
    monkeypatch.setattr(brd, "PB", types.SimpleNamespace(project=boundary.project))
    reps = all_reports()
    reps["CODEX"]["workflows"][0]["break"]["first_red_sha"] = SHA_B
    data = brd.assemble(reps)
    rows = {r["short"]: r for r in data["repositories"]}
    # the private repo's commit SHA is redacted wherever it occurs, so a public row reusing it is too
    assert rows["ABACUS"]["non_green"][0]["window"]["first_red_sha"] == pbm.MARK
    priv = rows["cryoplant-project"]["non_green"][0]["window"]
    pub = rows["CODEX"]["non_green"][0]["window"]
    assert priv["first_red_sha"] == pbm.MARK
    assert priv["first_red_run"] is None
    assert pub["first_red_sha"] == SHA_B
    assert pub["first_red_run"] == 12345678901
    # counts survive the projection
    assert rows["cryoplant-project"]["currently_red"] == 1
    body = {k: v for k, v in data.items() if k != "digest_sha256"}
    assert data["digest_sha256"] == hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


# --- main ------------------------------------------------------------------------------------

def _write_reports(base, reps):
    for name, rep in reps.items():
        d = base / name
        d.mkdir(parents=True)
        (d / "red_trace.json").write_text(json.dumps(rep), encoding="utf-8")


def test_main_writes_snapshot_and_prints_totals(tmp_path, identity_pb, capsys):
    _write_reports(tmp_path / "reports", all_reports())
    out = tmp_path / "fed.json"
    assert brd.main(["--reports", str(tmp_path / "reports"), "--out", str(out)]) is None
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n")
    data = json.loads(text)
    assert data == brd.assemble(all_reports())
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"status": "PASS", "totals": data["totals"]}


def test_main_default_out_is_module_constant(tmp_path, identity_pb, monkeypatch, capsys):
    _write_reports(tmp_path / "reports", all_reports())
    target = tmp_path / "default.json"
    monkeypatch.setattr(brd, "OUT", target)
    brd.main(["--reports", str(tmp_path / "reports")])
    assert json.loads(target.read_text(encoding="utf-8"))["iteration"] == "N+8"


def test_main_missing_report_raises(tmp_path, identity_pb):
    reps = all_reports()
    del reps["ABACUS"]
    _write_reports(tmp_path / "reports", reps)
    with pytest.raises(FileNotFoundError):
        brd.main(["--reports", str(tmp_path / "reports"), "--out", str(tmp_path / "o.json")])
    assert not (tmp_path / "o.json").exists()


def test_main_requires_reports_argument(capsys):
    with pytest.raises(SystemExit) as exc:
        brd.main([])
    assert exc.value.code == 2
    assert "--reports" in capsys.readouterr().err


def test_constants_bind_core_roles_and_default_output():
    assert set(brd.ROLE) == set(brd.CORE)
    assert len(brd.CORE) == len(set(brd.CORE)) == 5
    assert brd.OUT == brd.ROOT / "data" / "RED_TRACE_FEDERATION_N8.json"
    assert brd.ROOT == MOD_PATH.resolve().parents[1]
