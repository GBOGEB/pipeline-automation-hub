"""Coverage wave w9: gogreen/red_trace/red_trace.py edge paths (offline, fake GitHub API only)."""
import importlib.util
import io
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "gogreen" / "red_trace" / "red_trace.py"
_spec = importlib.util.spec_from_file_location("cw_w9_red_trace_mod", MOD_PATH)
rt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rt)

REPO = "GBOGEB/pipeline-automation-hub"
WF = ".github/workflows/a.yml"
S1, S2, S3, S4 = "1" * 40, "2" * 40, "3" * 40, "d" * 40


def opener_for(route, calls=None):
    def opener(req, timeout):
        u = req.full_url
        if calls is not None:
            calls.append(u)
        return io.BytesIO(json.dumps(route(u)).encode())
    return opener


def reader(route, calls=None):
    return rt.Reader(REPO, token="test-token", opener=opener_for(route, calls))


def run(sha, conclusion, at, rid, attempt=1, **kw):
    r = {"path": WF, "name": "A", "head_sha": sha, "conclusion": conclusion, "status": "completed",
         "created_at": at, "id": rid, "run_attempt": attempt, "event": "push"}
    r.update(kw)
    return r


# ---------------------------------------------------------------- collection guards

def test_list_workflows_requires_list():
    with pytest.raises(ValueError, match="workflows missing"):
        rt.list_workflows(reader(lambda u: {"workflows": None}))


def test_collect_requires_workflow_runs():
    def route(u):
        if "/actions/workflows?" in u:
            return {"total_count": 1, "workflows": [{"id": 1, "path": WF}]}
        return {"workflow_runs": "nope"}
    with pytest.raises(ValueError, match="workflow_runs missing"):
        rt.collect(reader(route), "master", 10)


def test_nondeterminism_skips_bad_sha_and_non_terminal():
    runs = [run("short", "success", "t1", 1), run(S1, "cancelled", "t2", 2), run(S1, "success", "t3", 3)]
    nd = rt.nondeterminism(runs)
    assert nd[WF]["same_head_disagreements"] == 0
    assert nd[WF]["nondeterministic"] is False


def test_outcomes_keeps_highest_rank():
    runs = [run(S1, "success", "2026-10-02T00:00:00Z", 1, attempt=2),
            run(S1, "failure", "2026-10-01T00:00:00Z", 2, attempt=1)]
    flows = rt.outcomes(runs)
    assert [x["conclusion"] for x in flows[WF]] == ["success"]


# ---------------------------------------------------------------- build + enrich

def enrich_route(u):
    if "/compare/" in u:
        return {"commits": [{"sha": S3, "commit": {"message": "fix the thing\nbody"}},
                            {"sha": S4, "commit": {"message": ""}}], "total_commits": 2}
    if "/jobs?" in u:
        return {"jobs": [{"name": "test", "conclusion": "failure",
                          "steps": [{"name": "pytest", "conclusion": "failure"}, {"name": "ok", "conclusion": "success"}]},
                         {"name": "lint", "conclusion": "success"}]}
    raise AssertionError(u)


def test_build_enriches_break_and_everred(tmp_path):
    runs = [run(S1, "success", "2026-10-01T00:00:00Z", 1), run(S2, "failure", "2026-10-02T00:00:00Z", 2),
            run(S1, "failure", "2026-10-01T00:00:00Z", 3, path=".github/workflows/b.yml", name="B"),
            run(S2, "cancelled", "2026-10-01T00:00:00Z", 4, path=".github/workflows/c.yml", name="C")]
    collected = {"runs": runs, "truncated": False}
    calls = []
    rep = rt.build(REPO, "master", collected, rt.outcomes(runs), enriched_reader=reader(enrich_route, calls),
                   observed_at="2026-10-03T00:00:00Z", root=tmp_path)
    by = {w["name"]: w for w in rep["workflows"]}
    br = by["A"]["break"]
    assert br["suspect_commit_count"] == 2
    assert [s["title"] for s in br["suspects"]] == ["fix the thing", ""]
    assert br["failing"] == [{"job": "test", "steps": ["pytest"]}]
    assert by["B"]["class"] == "EVERRED" and by["B"]["first_red"]["first_red_run"] == 3
    assert "suspects" not in by["B"]["first_red"] and by["B"]["first_red"]["failing"]
    assert by["C"]["class"] == "UNKNOWN_NO_TERMINAL" and "latest_age_days" not in by["C"]
    assert by["C"]["pinned_historical_ids"] == []
    assert sum("/compare/" in c for c in calls) == 1


# ---------------------------------------------------------------- merged-PR lane

def test_merged_prs_requires_list():
    with pytest.raises(ValueError, match="pulls missing"):
        rt.merged_prs(reader(lambda u: {"x": 1}), "master", 5)


def test_merged_prs_stops_after_ten_pages():
    calls = []

    def route(u):
        page = int(u.rsplit("page=", 1)[1])
        return [{"number": page * 1000 + i, "merged_at": f"2026-10-{page:02d}T00:00:00Z",
                 "head": {"sha": S1}} for i in range(100)]
    prs = rt.merged_prs(reader(route, calls), "master", 1000)
    assert len(calls) == 10
    assert len(prs) == 1000
    assert prs[0]["merged_at"] == "2026-10-10T00:00:00Z"


def test_head_runs_guards_and_pages():
    with pytest.raises(ValueError, match="workflow_runs missing"):
        rt.head_runs(reader(lambda u: {}), S1)

    def route(u):
        page = int(u.rsplit("page=", 1)[1])
        return {"total_count": 150, "workflow_runs": [{"id": i} for i in range(100 if page == 1 else 50)]}
    calls = []
    assert len(rt.head_runs(reader(route, calls), S1)) == 150
    assert len(calls) == 2


def test_at_merge_keeps_best_rank():
    runs = [{"path": WF, "created_at": "2026-10-01T00:00:02Z", "status": "completed", "conclusion": "success",
             "updated_at": "2026-10-01T00:00:03Z", "id": 2},
            {"path": WF, "created_at": "2026-10-01T00:00:01Z", "status": "completed", "conclusion": "failure",
             "updated_at": "2026-10-01T00:00:02Z", "id": 1}]
    out = rt.at_merge(runs, "2026-10-02T00:00:00Z")
    assert out[WF]["conclusion"] == "success" and out[WF]["run_id"] == 2


def test_build_pr_lane_pending_only_without_census():
    prs = [{"number": 7, "head_sha": S1, "merged_at": "2026-10-01T00:00:00Z", "title": "t",
            "runs": [{"path": WF, "name": "A", "created_at": "2026-09-30T23:59:00Z", "status": "in_progress",
                      "id": 3}]}]
    rep = rt.build_pr_lane(REPO, "master", {"prs": prs}, observed_at="2026-10-02T00:00:00Z")
    w = rep["workflows"][0]
    assert w["class"] == "UNKNOWN_NO_TERMINAL" and "latest_pr" not in w
    assert w["pending_at_merge_prs"] == [7]
    assert "census" not in rep
    md = rt.markdown_pr_lane(rep)
    assert "Coverage:" not in md
    assert "merged while a check was still pending: 1 PR(s)" in md


# ---------------------------------------------------------------- markdown windows

def md_report(workflows, counts):
    return {"repository": REPO, "branch": "master", "counts": counts,
            "window": {"runs": 1, "oldest_run_at": None, "truncated": False}, "workflows": workflows}


def test_markdown_window_variants():
    nd = {"nondeterministic": True}
    wfs = [
        {"class": "RED_TO_GREEN", "name": "Rec", "current": "GREEN",
         "red_episodes": [{"last_green_sha": S1, "first_red_sha": S2, "recovery_sha": S3, "red_hours": 1.5}]},
        {"class": "GREEN_TO_RED", "name": "Open", "current": "RED", "pinned_historical_ids": ["12345678"],
         "nondeterminism": nd, "break": {"last_green_sha": S1, "first_red_sha": S2}},
        {"class": "FLAKY", "name": "Start", "current": "GREEN",
         "red_episodes": [{"red_before_window": True, "first_red_sha": S2, "recovery_sha": S4}]},
        {"class": "EVERRED", "name": "Never", "current": "RED", "first_red": {"sha": S3, "run_id": 1}},
    ]
    md = rt.markdown(md_report(wfs, {"RED_TO_GREEN": 1, "GREEN_TO_RED": 1, "FLAKY": 1, "EVERRED": 1}))
    assert "→ ✓`33333333` (1.5 h)" in md
    assert "| Open | RED · 📌 pinned run/artifact · ↻ same-head disagreement/rerun | `11111111` → `22222222` |" in md
    assert "red at window start (`22222222`) → ✓`dddddddd`" in md
    assert "never green in window; first `33333333`" in md


# ---------------------------------------------------------------- CLI

def test_main_requires_repo(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    with pytest.raises(SystemExit, match="--repo required"):
        rt.main(["--out", str(tmp_path)])


def api_route(u):
    if "/actions/workflows?" in u:
        return {"total_count": 1, "workflows": [{"id": 1, "path": WF, "name": "A"}]}
    if "/actions/workflows/1/runs" in u:
        return {"total_count": 2, "workflow_runs": [run(S1, "success", "2026-10-01T00:00:00Z", 1),
                                                    run(S2, "failure", "2026-10-02T00:00:00Z", 2)]}
    if "/pulls?" in u:
        return [{"number": 5, "merged_at": "2026-10-02T01:00:00Z", "head": {"sha": S4}, "title": "t"}]
    if "/actions/runs?head_sha=" in u:
        return {"total_count": 1, "workflow_runs": [
            {"path": WF, "name": "A", "head_sha": S4, "created_at": "2026-10-02T00:00:00Z", "status": "completed",
             "conclusion": "failure", "updated_at": "2026-10-02T00:30:00Z", "id": 9, "run_attempt": 1}]}
    return enrich_route(u)


def test_main_collects_and_traces_pr_lane(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr("urllib.request.urlopen", opener_for(api_route))
    out = tmp_path / "out"
    rep = rt.main(["--repo", REPO, "--out", str(out), "--root", str(tmp_path), "--pr-lane", "3"])
    assert rep["counts"] == {"GREEN_TO_RED": 1}
    summary = json.loads(capsys.readouterr().out)
    assert summary["pr_lane"]["merged_prs"] == 1
    assert summary["pr_lane"]["merged_with_red"] == 1
    assert summary["pr_lane"]["requests"] == 2  # pulls + head runs; census reused from the master lane
    pr = json.loads((out / "red_trace_pr.json").read_text(encoding="utf-8"))
    assert pr["census"]["workflows_total"] == 1
    assert (out / "red_trace_pr.md").read_text(encoding="utf-8").startswith("### GOGREEN red-trace")


def test_dunder_main_offline(tmp_path, monkeypatch, capsys):
    runs = tmp_path / "runs.json"
    runs.write_text(json.dumps([run(S1, "success", "2026-10-01T00:00:00Z", 1)]), encoding="utf-8", newline="\n")
    out = tmp_path / "o"
    monkeypatch.setattr(sys, "argv", ["red_trace.py", "--repo", REPO, "--runs-json", str(runs), "--out", str(out),
                                      "--root", str(tmp_path), "--pr-lane", "2"])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert json.loads(capsys.readouterr().out)["counts"] == {"STABLE_GREEN": 1}
    assert not (out / "red_trace_pr.json").exists()
