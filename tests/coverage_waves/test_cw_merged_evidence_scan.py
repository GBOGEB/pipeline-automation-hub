"""Coverage wave: behavioural tests for mission-control/gogreen/merged_evidence/scan.py.

Covers classify branches the native tests miss, the HTTP request helper, the
TOP21 execute loop, the evidence writer and main(). Network is always faked.
"""
import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "cw_merged_evidence_scan", REPO_ROOT / "mission-control" / "gogreen" / "merged_evidence" / "scan.py"
)
scan = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(scan)

H = "a" * 40
ROSTER = ["GBOGEB/repo%02d" % i for i in range(21)]


def pr(number=1, head=H, merged="2026-10-17T10:00:00Z"):
    return {"number": number, "title": "t%d" % number, "merged_at": merged,
            "head": {"sha": head}, "merge_commit_sha": "b" * 40}


def run(i=1, conclusion="success", head=H, status="completed", attempt=None, name="wf"):
    r = {"id": i, "head_sha": head, "status": status, "conclusion": conclusion, "name": name,
         "html_url": "https://example.invalid/run/%d" % i}
    if attempt is not None:
        r["run_attempt"] = attempt
    return r


# --- classify -------------------------------------------------------------

@pytest.mark.parametrize("conclusion", ["failure", "timed_out", "action_required", "startup_failure"])
def test_bad_conclusions_map_to_failure_debt(conclusion):
    out = scan.classify(pr(), [run(conclusion=conclusion)], 1)
    assert out["states"] == {"failure": 1}
    assert out["verdict"] == "MIXED_OR_RED"
    assert out["everred_candidates"][0]["classification"] == "failure"


def test_unknown_conclusion_is_red_and_debt_defaults_attempt_1():
    out = scan.classify(pr(), [run(i=7, conclusion="weird", name="build")], 1)
    assert out["states"] == {"unknown": 1}
    assert out["verdict"] == "MIXED_OR_RED"
    assert out["everred_candidates"] == [{
        "run_id": 7, "attempt": 1, "workflow": "build", "classification": "unknown",
        "first_red": "NOT_FETCHED", "source_head_sha": H,
        "url": "https://example.invalid/run/7", "root_closure_credit": 0,
    }]


@pytest.mark.parametrize("conclusion", ["neutral", "stale"])
def test_other_nonred_conclusions_are_partial_terminal(conclusion):
    out = scan.classify(pr(), [run(), run(i=2, conclusion=conclusion)], 2)
    assert out["states"] == {"success": 1, conclusion: 1}
    assert out["verdict"] == "PARTIAL_TERMINAL"
    assert out["everred_candidates"] == []


def test_pending_beats_partial_terminal_and_red_beats_pending():
    assert scan.classify(pr(), [run(conclusion="skipped"), run(i=2, status="in_progress", conclusion=None)], 2)["verdict"] == "PENDING"
    assert scan.classify(pr(), [run(status="queued"), run(i=2, conclusion="cancelled")], 2)["verdict"] == "MIXED_OR_RED"


def test_incomplete_page_wins_over_red():
    out = scan.classify(pr(), [run(conclusion="failure")], 5)
    assert out["verdict"] == "INCOMPLETE_PAGE"
    assert out["complete"] is False and out["api_total"] == 5 and out["run_count"] == 1


def test_classify_record_fields_and_no_authority():
    out = scan.classify(pr(number=42), [run()], 1)
    assert out["number"] == 42 and out["title"] == "t42"
    assert out["head_sha"] == H and out["merge_commit_sha"] == "b" * 40
    assert out["merged_at"] == "2026-10-17T10:00:00Z"
    assert out["merge_authorized"] is False and out["security_verified"] is False
    assert out["formal_root_closure_credit"] == 0


def test_duplicate_detected_with_implicit_attempt():
    with pytest.raises(ValueError, match="^duplicate native run/attempt$"):
        scan.classify(pr(), [run(), run(attempt=1)], 2)


def test_wrong_sha_message():
    with pytest.raises(ValueError, match="^run source SHA differs from merged PR head$"):
        scan.classify(pr(), [run(head="c" * 40)], 1)


@pytest.mark.parametrize("bad", [pr(merged=None), pr(head="abc")])
def test_unmerged_or_short_head_rejected(bad):
    with pytest.raises(AssertionError):
        scan.classify(bad, [], 0)


# --- request --------------------------------------------------------------

class FakeResp:
    def __init__(self, obj):
        self._raw = json.dumps(obj).encode()

    def read(self, *a):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_request_headers_and_json(monkeypatch):
    seen = {}

    def fake(req, timeout=None):
        seen["req"], seen["timeout"] = req, timeout
        return FakeResp({"x": [1]})

    monkeypatch.setattr(scan.urllib.request, "urlopen", fake)
    assert scan.request("https://api.github.com/repos/GBOGEB/a", "test-token", "/pulls") == {"x": [1]}
    req = seen["req"]
    assert req.full_url == "https://api.github.com/repos/GBOGEB/a/pulls"
    assert seen["timeout"] == 30
    h = dict(req.header_items())
    assert h["Authorization"] == "Bearer test-token"
    assert h["Accept"] == "application/vnd.github+json"
    assert h["User-agent"] == "GoGREEN-TOP21-Merged-Census"


# --- execute --------------------------------------------------------------

class FakeAPI:
    def __init__(self, pages=None, runs=None):
        self.pages = pages or {}
        self.runs = runs or {}
        self.calls = []

    def __call__(self, req, timeout=None):
        url = urlparse(req.full_url)
        parts = url.path.split("/")
        repo = parts[2] + "/" + parts[3]
        tail = "/".join(parts[4:])
        self.calls.append((repo, tail, url.query))
        if tail == "pulls":
            assert parse_qs(url.query) == {"state": ["closed"], "sort": ["updated"], "direction": ["desc"], "per_page": ["100"]}
            return FakeResp(self.pages.get(repo, []))
        if tail == "actions/runs":
            sha = parse_qs(url.query)["head_sha"][0]
            return FakeResp(self.runs.get(sha, {"total_count": 0, "workflow_runs": []}))
        raise AssertionError(req.full_url)


def _sha(n):
    return ("%040x" % n)


def test_execute_samples_merged_prs_up_to_limit(monkeypatch):
    s1, s2, s3 = _sha(1), _sha(2), _sha(3)
    api = FakeAPI(
        pages={"GBOGEB/repo00": [pr(1, s1, merged=None), pr(2, s2), pr(3, s3)]},
        runs={s2: {"total_count": 1, "workflow_runs": [run(head=s2, conclusion="failure")]},
              s3: {"total_count": 1, "workflow_runs": [run(head=s3)]}},
    )
    monkeypatch.setattr(scan.urllib.request, "urlopen", api)
    result = scan.execute(ROSTER, "test-token", 1)
    assert [r["repo"] for r in result] == ROSTER
    first = result[0]
    assert first["sampled"] == 1
    assert [p["number"] for p in first["merged_prs"]] == [2]
    assert first["merged_prs"][0]["verdict"] == "MIXED_OR_RED"
    assert first["closed_pr_page_may_be_truncated"] is False
    assert first["merged_prs"][0]["closed_pr_page_may_be_truncated"] is False
    assert all(r["sampled"] == 0 and r["merged_prs"] == [] for r in result[1:])
    # Only one runs lookup: the unmerged PR and the over-limit PR are never fetched.
    assert [c for c in api.calls if c[1] == "actions/runs"] == [("GBOGEB/repo00", "actions/runs", "head_sha=" + s2 + "&per_page=100")]

    result2 = scan.execute(ROSTER, "test-token", 2)
    assert [p["number"] for p in result2[0]["merged_prs"]] == [2, 3]


def test_execute_flags_truncated_page(monkeypatch):
    page = [pr(i, _sha(i)) for i in range(1, 101)]
    api = FakeAPI(pages={"GBOGEB/repo05": page})
    monkeypatch.setattr(scan.urllib.request, "urlopen", api)
    result = scan.execute(ROSTER, "test-token", 1)
    assert result[5]["closed_pr_page_may_be_truncated"] is True
    assert result[5]["merged_prs"][0]["closed_pr_page_may_be_truncated"] is True
    assert result[5]["merged_prs"][0]["verdict"] == "NO_RUN_EVIDENCE"
    assert result[4]["closed_pr_page_may_be_truncated"] is False


@pytest.mark.parametrize("roster", [ROSTER[:20], ROSTER[:20] + [ROSTER[0]], ROSTER + ["GBOGEB/extra"]])
def test_execute_roster_size_and_uniqueness(roster):
    with pytest.raises(ValueError, match="^TOP21 requires 21 unique owner/repo entries$"):
        scan.execute(roster, "test-token", 1)


def test_execute_rejects_foreign_repository(monkeypatch):
    api = FakeAPI()
    monkeypatch.setattr(scan.urllib.request, "urlopen", api)
    roster = ROSTER[:3] + ["evil/repo"] + ROSTER[4:]
    with pytest.raises(ValueError, match="^unexpected federation repository$"):
        scan.execute(roster, "test-token", 1)
    assert [c[0] for c in api.calls] == ROSTER[:3]


def test_execute_rejects_non_list_pr_page(monkeypatch):
    monkeypatch.setattr(scan.urllib.request, "urlopen", lambda req, timeout=None: FakeResp({"message": "Not Found"}))
    with pytest.raises(ValueError, match="^invalid PR API response$"):
        scan.execute(ROSTER, "test-token", 1)


def test_execute_rejects_missing_total_count(monkeypatch):
    api = FakeAPI(pages={"GBOGEB/repo00": [pr(1, _sha(9))]}, runs={_sha(9): {"workflow_runs": []}})
    monkeypatch.setattr(scan.urllib.request, "urlopen", api)
    with pytest.raises(ValueError, match="^missing run count$"):
        scan.execute(ROSTER, "test-token", 1)


def test_execute_missing_workflow_runs_defaults_empty(monkeypatch):
    api = FakeAPI(pages={"GBOGEB/repo00": [pr(1, _sha(9))]}, runs={_sha(9): {"total_count": 3}})
    monkeypatch.setattr(scan.urllib.request, "urlopen", api)
    rec = scan.execute(ROSTER, "test-token", 1)[0]["merged_prs"][0]
    assert rec["run_count"] == 0 and rec["verdict"] == "INCOMPLETE_PAGE"


# --- output ---------------------------------------------------------------

def _repos():
    red = scan.classify(pr(1, _sha(1)), [run(i=11, head=_sha(1), conclusion="failure", name="ci"),
                                         run(i=12, head=_sha(1), conclusion="cancelled", attempt=2, name="lint")], 2)
    green = scan.classify(pr(2, _sha(2)), [run(i=21, head=_sha(2))], 1)
    empty = scan.classify(pr(3, _sha(3)), [], 0)
    return [
        {"repo": "GBOGEB/a", "sampled": 2, "merged_prs": [red, green], "closed_pr_page_may_be_truncated": False},
        {"repo": "GBOGEB/b", "sampled": 1, "merged_prs": [empty], "closed_pr_page_may_be_truncated": False},
        {"repo": "GBOGEB/c", "sampled": 0, "merged_prs": [], "closed_pr_page_may_be_truncated": False},
    ]


def test_output_writes_snapshot_csvs_and_manifest(tmp_path):
    target = tmp_path / "deep" / "out"
    repos = _repos()
    stats = scan.output(repos, str(target))
    assert stats == {
        "schema": "gogreen.merged-top21.evidence.v1", "observed_prs": 3, "observed_repositories": 3,
        "run_associations": 3, "negative_run_associations": 2,
        "verdicts": {"MIXED_OR_RED": 1, "ALL_OBSERVED_SUCCESS": 1, "NO_RUN_EVIDENCE": 1},
        "global_success_rate": None, "formal_root_closures": 0,
        "historical_complete": False, "admission_authorized": False,
    }
    snap = json.loads((target / "snapshot.json").read_text(encoding="utf-8"))
    assert snap == {"stats": stats, "repositories": repos}
    with (target / "everred_candidates.csv").open(encoding="utf-8", newline="") as fh:
        debt = list(csv.DictReader(fh))
    assert [(d["repo"], d["pr"], d["run_id"], d["attempt"], d["workflow"], d["classification"]) for d in debt] == [
        ("GBOGEB/a", "1", "11", "1", "ci", "failure"),
        ("GBOGEB/a", "1", "12", "2", "lint", "cancelled"),
    ]
    with (target / "merged_pr_rollup.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["repository", "merged_pr", "source_head", "observed_runs", "status", "page_complete"]
    assert rows[1:] == [
        ["GBOGEB/a", "1", _sha(1), "2", "MIXED_OR_RED", "True"],
        ["GBOGEB/a", "2", _sha(2), "1", "ALL_OBSERVED_SUCCESS", "True"],
        ["GBOGEB/b", "3", _sha(3), "0", "NO_RUN_EVIDENCE", "True"],
    ]
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["merge_authorized"] is False
    assert manifest["file_sha256"] == {
        n: hashlib.sha256((target / n).read_bytes()).hexdigest()
        for n in ("snapshot.json", "everred_candidates.csv", "merged_pr_rollup.csv")
    }
    assert b"\r\n" not in (target / "snapshot.json").read_bytes()


def test_output_empty_repos(tmp_path):
    stats = scan.output([], str(tmp_path))
    assert stats["observed_prs"] == 0 and stats["verdicts"] == {} and stats["run_associations"] == 0
    assert (tmp_path / "everred_candidates.csv").read_text(encoding="utf-8").strip().startswith("repo,pr,run_id")


# --- main -----------------------------------------------------------------

def _argv(monkeypatch, roster_path, out, *extra):
    monkeypatch.setattr(sys, "argv", ["scan.py", "--roster", str(roster_path), "--out", str(out), *extra])


@pytest.mark.parametrize("limit", ["0", "11", "-1"])
def test_main_bounds_limit(monkeypatch, tmp_path, limit):
    _argv(monkeypatch, tmp_path / "r.json", tmp_path / "o", "--limit", limit)
    with pytest.raises(SystemExit) as info:
        scan.main()
    assert info.value.code == "bounded limit 1..10"


def test_main_requires_token(monkeypatch, tmp_path):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    _argv(monkeypatch, tmp_path / "r.json", tmp_path / "o")
    with pytest.raises(SystemExit) as info:
        scan.main()
    assert info.value.code == "authenticated read-only token required"


@pytest.mark.parametrize("env", ["GH_TOKEN", "GITHUB_TOKEN"])
def test_main_end_to_end(monkeypatch, tmp_path, capsys, env):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv(env, "test-token")
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps(ROSTER), encoding="utf-8")
    s = _sha(5)
    api = FakeAPI(pages={"GBOGEB/repo03": [pr(9, s)]}, runs={s: {"total_count": 1, "workflow_runs": [run(head=s)]}})
    seen_tokens = []

    def spy(req, timeout=None):
        seen_tokens.append(req.get_header("Authorization"))
        return api(req, timeout)

    monkeypatch.setattr(scan.urllib.request, "urlopen", spy)
    _argv(monkeypatch, roster, tmp_path / "out", "--limit", "10")
    scan.main()
    printed = json.loads(capsys.readouterr().out)
    assert printed["observed_prs"] == 1 and printed["observed_repositories"] == 21
    assert printed["verdicts"] == {"ALL_OBSERVED_SUCCESS": 1}
    assert set(seen_tokens) == {"Bearer test-token"}
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == [
        "everred_candidates.csv", "manifest.json", "merged_pr_rollup.csv", "snapshot.json"]
