"""Wave 9 coverage tests for issue-expedition/triway_burndown.py.

Reaches the branches the unit suite leaves open: invalid timestamps, stray
chain references, title-derived priority, self/outside-scope edges, the
read-only GitHub collector (with a fake opener, never the network) and the CLI.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = REPO / "mission-control" / "qps-triage-ultra" / "issue-expedition" / "triway_burndown.py"

A = "GBOGEB/ABACUS"
B = "GBOGEB/pipeline-automation-hub"
T = "2026-10-26T03:00:00Z"


@pytest.fixture(scope="module")
def tb():
    spec = importlib.util.spec_from_file_location("cw_w9_triway_burndown", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def census(tb, issues=None, prs=None):
    issues = issues if issues is not None else [
        {"repo": A, "number": 1, "state": "open", "title": "[P3] parent", "labels": [],
         "body": "## DoD\n- [x] a\n- [ ] b\nsee #1 and GBOGEB/CODEX#9", "created_at": T, "updated_at": T},
        {"repo": A, "number": 2, "state": "open", "title": "child", "labels": [{"name": "misc"}],
         "body": "blocked by #1", "created_at": "2026-10-20T00:00:00Z", "updated_at": T},
    ]
    prs = prs if prs is not None else [
        {"repo": A, "number": 5, "state": "open", "body": "Fixes #1 and GBOGEB/CODEX#77", "head_sha": "d" * 40},
    ]
    return {
        "schema": tb.CENSUS, "observed_at": T, "authority_transfer": False, "formal_credit_delta": 0,
        "repositories": [A], "source_heads": {A: "a" * 40},
        "counts": {A: {"issues": len(issues), "prs": len(prs)}},
        "issues": issues, "pull_requests": prs,
    }


def test_invalid_timestamp(tb):
    with pytest.raises(ValueError, match="invalid timestamp"):
        tb.timestamp("not-a-date")


def test_stray_chain_reference_skipped(tb):
    refs = tb.references("see /#5 and #6", A)
    assert [r["target"] for r in refs] == [A + "#6"]


def test_priority_from_title(tb):
    assert tb.priority([], "[P3] thing") == ("P3", "ISSUE_TITLE")
    assert tb.priority([{"name": "nope"}], "plain") == ("UNKNOWN", "UNCLASSIFIED")


def test_project_self_and_outside_scope_edges(tb):
    report = tb.project(census(tb))
    parent = report["issues"][A + "#1"]
    assert parent["priority"] == "P3" and parent["priority_basis"] == "ISSUE_TITLE"
    # Self-reference produces no edge; the CODEX reference is outside the census scope.
    assert all(not (e["from"] == e["to"]) for e in report["edges"])
    assert "GBOGEB/CODEX#9" in parent["outside_scope_references"]
    # PR overlap only lands on in-scope targets.
    assert [o["kind"] for o in parent["open_pr_overlap"]] == ["PR_CLOSURE_CLAIM"]
    assert all(not e["verified"] for e in report["edges"])


def test_csv_view_structure(tb):
    text = tb.csv_view(tb.project(census(tb)))
    lines = text.strip().split("\n")
    assert lines[0].split(",")[0] == "ref"
    assert len(lines) == 3


# ---------------------------------------------------------------- GitHub collector

class FakeGitHub:
    def __init__(self, issue_pages=None, pull_pages=None, payload_override=None):
        self.issue_pages = issue_pages or [[]]
        self.pull_pages = pull_pages or [[]]
        self.payload_override = payload_override
        self.requests = []

    def __call__(self, req, timeout):
        self.requests.append(req)
        url = urlparse(req.full_url)
        assert url.netloc == "api.github.com"
        parts = url.path.split("/")
        if self.payload_override is not None:
            body = self.payload_override
        elif len(parts) == 4:
            body = {"default_branch": "main/x"}
        elif parts[4] == "commits":
            body = {"sha": "c" * 40}
        else:
            page = int(parse_qs(url.query)["page"][0])
            pages = self.issue_pages if parts[4] == "issues" else self.pull_pages
            body = pages[page - 1] if page <= len(pages) else []
        return io.BytesIO(json.dumps(body).encode("utf-8"))


def _issue(n, **kw):
    d = {"number": n, "state": "open", "title": None, "body": None, "created_at": T, "updated_at": T,
         "labels": [{"name": "P1"}]}
    d.update(kw)
    return d


def test_get_rejects_untrusted_path(tb):
    with pytest.raises(ValueError, match="untrusted"):
        tb._get("/repos/evil/x", None, FakeGitHub())


def test_collect_builds_census(tb):
    gh = FakeGitHub(
        issue_pages=[[_issue(i + 1) for i in range(100)], [_issue(101), _issue(102, pull_request={})]],
        pull_pages=[[{"number": 7, "state": "open", "body": None, "head": {"sha": "e" * 40}},
                     {"number": 8, "state": "open"}]],
    )
    c = tb.collect([A], token="test-token", opener=gh)
    assert c["schema"] == tb.CENSUS and c["authority_transfer"] is False
    assert c["source_heads"] == {A: "c" * 40}
    assert c["counts"][A] == {"issues": 101, "prs": 2}
    assert c["issues"][0]["title"] == "" and c["issues"][0]["labels"] == ["P1"]
    assert c["pull_requests"][1]["head_sha"] is None
    assert all(r.get_header("Authorization") == "Bearer test-token" for r in gh.requests)
    assert any("main%2Fx" in r.full_url for r in gh.requests)
    tb.validate(c)  # a collected census passes the projection's own validation


def test_collect_without_token_sends_no_auth(tb):
    gh = FakeGitHub()
    tb.collect([A], opener=gh)
    assert all(r.get_header("Authorization") is None for r in gh.requests)


def test_pages_exceeded(tb):
    gh = FakeGitHub(issue_pages=[[_issue(i) for i in range(1, 101)]] * 3)
    with pytest.raises(ValueError, match="pagination incomplete"):
        tb._pages(A, "issues", None, gh, 2)


def test_pages_bad_payload(tb):
    with pytest.raises(ValueError, match="bad page payload"):
        tb._pages(A, "issues", None, FakeGitHub(payload_override={"message": "x"}), 1)


@pytest.mark.parametrize("repos,max_pages,msg", [
    ([A], 0, "invalid max_pages"),
    ([], 1, "empty/duplicate"),
    ([A, A], 1, "empty/duplicate"),
    (["evil/x"], 1, "bad repository"),
])
def test_collect_guards(tb, repos, max_pages, msg):
    with pytest.raises(ValueError, match=msg):
        tb.collect(repos, opener=FakeGitHub(), max_pages=max_pages)


# ---------------------------------------------------------------- CLI

def test_main_input_previous_csv(tb, tmp_path, monkeypatch, capsys):
    c = census(tb)
    src = tmp_path / "census.json"
    src.write_text(json.dumps(c), encoding="utf-8")
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps(tb.project(c)), encoding="utf-8")
    out, csv_path = tmp_path / "out.json", tmp_path / "out.csv"
    monkeypatch.setattr(sys, "argv", ["triway", "--input", str(src), "--previous", str(prev),
                                      "--out", str(out), "--csv", str(csv_path)])
    tb.main()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema"] == tb.SCHEMA
    assert csv_path.read_text(encoding="utf-8").startswith("ref,")
    assert json.loads(capsys.readouterr().out) == report["metrics"]


def test_main_github_uses_token(tb, tmp_path, monkeypatch, capsys):
    seen = {}

    def fake_collect(repos, token=None):
        seen["repos"], seen["token"] = list(repos), token
        return census(tb)

    monkeypatch.setattr(tb, "collect", fake_collect)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    out = tmp_path / "o.json"
    monkeypatch.setattr(sys, "argv", ["triway", "--github", "--repos", A, "--out", str(out)])
    tb.main()
    assert seen == {"repos": [A], "token": "test-token"}
    assert out.is_file()
    assert isinstance(json.loads(capsys.readouterr().out), dict)
