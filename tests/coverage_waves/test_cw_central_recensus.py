"""Behavioural coverage for mission-control/federation-atlas/central/recensus.py.

Targets what test_code_health_recensus.py / test_code_health_issue_register.py
miss: the HTTP wrapper (faked urlopen), bare-module import fallback, guard
branches in collect(), the full issue-register path and main(). Never touches
the network.
"""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CENTRAL = REPO_ROOT / "mission-control" / "federation-atlas" / "central"
UTC = "2026-10-16T10:00:00Z"


def _load():
    if str(CENTRAL) not in sys.path:
        sys.path.insert(0, str(CENTRAL))
    spec = importlib.util.spec_from_file_location("cw_central_recensus", CENTRAL / "recensus.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rc = _load()


@pytest.fixture
def source():
    return rc.read_json(rc.REGISTRY)


def _issue_items(repo, state, count, start=1):
    return [{"number": i, "state": state, "title": "t%d" % i,
             "html_url": "https://github.com/%s/issues/%d" % (repo, i),
             "labels": [{"name": "bug"}], "created_at": "c", "updated_at": "u",
             "closed_at": None}
            for i in range(start, start + count)]


def make_getter(snapshot, *, issue_items=False, overrides=None):
    table = {r["id"]: r for r in snapshot["census"]["repositories"]}
    calls = []

    def get(path):
        calls.append(path)
        if overrides:
            for prefix, value in overrides.items():
                if prefix in path:
                    return value(path) if callable(value) else value
        if path.startswith("/search/issues?"):
            params = parse_qs(path.split("?", 1)[1])
            q = params["q"][0].split()
            repo = q[0].split(":", 1)[1]
            kind = q[1].split(":", 1)[1]
            state = q[2].split(":", 1)[1]
            reg = table[repo]["issue_register" if kind == "issue" else "pull_request_register"]
            count = reg[state]
            result = {"total_count": count, "incomplete_results": False}
            if issue_items and "page" in params:
                page = int(params["page"][0])
                offset = (page - 1) * 100
                n = max(0, min(100, count - offset))
                base = 1 if state == "open" else 100000
                result["items"] = _issue_items(repo, state, n, base + offset)
            return result
        parts = path.split("/")
        repo = parts[2] + "/" + parts[3]
        if parts[4] == "commits":
            return {"sha": table[repo]["source_sha"]}
        if parts[4] == "pulls":
            return {"number": int(parts[5]), "state": "open", "merged": False,
                    "draft": False, "head": {"sha": "b" * 40, "ref": "feat/x"},
                    "base": None}
        raise AssertionError("unexpected path " + path)

    get.calls = calls
    return get


# --- import fallback --------------------------------------------------------

def test_bare_load_uses_sibling_code_health_fallback():
    # Loaded without a parent package, the relative import fails and the
    # module falls back to the sibling top-level code_health module.
    assert rc.REGISTRY.name == "CODE_HEALTH_CENTRAL_v1.json"
    assert rc.validate.__module__ == "code_health"
    assert rc.SHA.fullmatch("a" * 40)


# --- github_get ---------------------------------------------------------------

class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def test_github_get_sends_read_only_headers_with_token(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        seen["headers"] = dict(request.header_items())
        seen["timeout"] = timeout
        return _Resp(b'{"sha": "x"}')

    monkeypatch.setattr(rc, "urlopen", fake_urlopen)
    out = rc.github_get("/repos/GBOGEB/ABACUS/commits/main", token="test-token")
    assert out == {"sha": "x"}
    assert seen["url"] == "https://api.github.com/repos/GBOGEB/ABACUS/commits/main"
    assert seen["method"] == "GET"
    assert seen["timeout"] == 20
    assert seen["headers"]["Authorization"] == "Bearer test-token"
    assert seen["headers"]["X-github-api-version"] == "2022-11-28"
    assert seen["headers"]["User-agent"] == "missioncontrol-code-health-census"


def test_github_get_search_path_without_token_has_no_auth(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["headers"] = dict(request.header_items())
        return _Resp(b'{"total_count": 3}')

    monkeypatch.setattr(rc, "urlopen", fake_urlopen)
    assert rc.github_get("/search/issues?q=x") == {"total_count": 3}
    assert "Authorization" not in seen["headers"]


@pytest.mark.parametrize("path", ["/search/code?q=x", "/user", "/repos/OTHER/x"])
def test_github_get_rejects_unapproved_paths_before_io(monkeypatch, path):
    monkeypatch.setattr(rc, "urlopen", lambda *a, **k: pytest.fail("network"))
    with pytest.raises(ValueError, match="^non-GitHub or mutating endpoint$"):
        rc.github_get(path)


# --- exact_count ----------------------------------------------------------------

def test_exact_count_rejects_non_dict_result():
    with pytest.raises(ValueError, match="^invalid GitHub search result$"):
        rc.exact_count(lambda p: [1], "GBOGEB/ABACUS", "issue", "open")


def test_exact_count_rejects_non_int_count_and_builds_query():
    paths = []

    def getter(p):
        paths.append(p)
        return {"total_count": "5"}

    with pytest.raises(ValueError, match="incomplete or invalid GitHub issue census"):
        rc.exact_count(getter, "GBOGEB/ABACUS", "pr", "closed")
    q = parse_qs(paths[0].split("?", 1)[1])
    assert q["q"] == ["repo:GBOGEB/ABACUS is:pr is:closed"]
    assert q["per_page"] == ["1"]


def test_exact_count_returns_count():
    assert rc.exact_count(lambda p: {"total_count": 0, "incomplete_results": False},
                          "GBOGEB/ABACUS", "issue", "closed") == 0


# --- retrieve_issue_register ----------------------------------------------------------

def _page(items, total):
    return {"total_count": total, "incomplete_results": False, "items": items}


def test_issue_register_rejects_non_dict_issue():
    with pytest.raises(ValueError, match="^invalid issue record$"):
        rc.retrieve_issue_register(lambda p: _page(["x"], 1), "GBOGEB/ABACUS", "open", 1)


def test_issue_register_rejects_non_list_labels():
    item = _issue_items("GBOGEB/ABACUS", "open", 1)[0]
    item["labels"] = "bug"
    with pytest.raises(ValueError, match="^invalid issue label population$"):
        rc.retrieve_issue_register(lambda p: _page([item], 1), "GBOGEB/ABACUS", "open", 1)


def test_issue_register_rejects_untyped_label():
    item = _issue_items("GBOGEB/ABACUS", "open", 1)[0]
    item["labels"] = [{"name": 7}]
    with pytest.raises(ValueError, match="^untyped issue labels$"):
        rc.retrieve_issue_register(lambda p: _page([item], 1), "GBOGEB/ABACUS", "open", 1)


def test_issue_register_zero_expected_queries_one_page():
    calls = []

    def getter(p):
        calls.append(p)
        return _page([], 0)

    assert rc.retrieve_issue_register(getter, "GBOGEB/ABACUS", "closed", 0) == []
    assert len(calls) == 1
    assert parse_qs(calls[0].split("?", 1)[1])["page"] == ["1"]


def test_issue_register_short_page_is_incomplete():
    items = _issue_items("GBOGEB/ABACUS", "open", 2)
    with pytest.raises(ValueError, match="^issue-register coverage incomplete$"):
        rc.retrieve_issue_register(lambda p: _page(items, 3), "GBOGEB/ABACUS", "open", 3)


# --- collect guards --------------------------------------------------------------------

def test_collect_rejects_too_many_repositories(monkeypatch, source):
    monkeypatch.setattr(rc, "validate", lambda s: None)
    snap = copy.deepcopy(source)
    snap["census"]["repositories"] = snap["census"]["repositories"] * 3
    assert len(snap["census"]["repositories"]) > rc.MAX_REPOS
    with pytest.raises(ValueError, match="^too many native repository lookups$"):
        rc.collect(snap, getter=make_getter(source), observed_at_utc=UTC)


def test_collect_rejects_foreign_repository(monkeypatch, source):
    monkeypatch.setattr(rc, "validate", lambda s: None)
    snap = copy.deepcopy(source)
    snap["census"]["repositories"][0]["id"] = "OTHER/repo"
    with pytest.raises(ValueError, match="^unsupported repository identity$"):
        rc.collect(snap, getter=make_getter(source), observed_at_utc=UTC)


def test_collect_rejects_non_dict_commit(source):
    getter = make_getter(source, overrides={"/commits/": ["not", "dict"]})
    with pytest.raises(ValueError, match="^invalid GitHub commit metadata$"):
        rc.collect(source, getter=getter, observed_at_utc=UTC)


def test_collect_rejects_non_dict_pull(source):
    getter = make_getter(source, overrides={"/pulls/": None})
    with pytest.raises(ValueError, match="^invalid native pull request$"):
        rc.collect(source, getter=getter, observed_at_utc=UTC)


def test_collect_rejects_empty_pr_ref(source):
    getter = make_getter(source, overrides={
        "/pulls/": lambda p: {"number": int(p.rsplit("/", 1)[1]),
                              "head": {"sha": "c" * 40, "ref": ""}}})
    with pytest.raises(ValueError, match="^PR head identity unavailable$"):
        rc.collect(source, getter=getter, observed_at_utc=UTC)


def test_collect_default_timestamp_is_utc_now(source):
    snap = rc.collect(source, getter=make_getter(source), include_pr_heads=False)
    stamp = snap["observed_at_utc"]
    assert stamp.endswith("+00:00")
    assert snap["issue_register_records"] is None
    assert snap["issue_register_observed"] is None
    assert snap["issue_register_full_population_verified"] is None


def test_collect_head_change_and_missing_base(source):
    first = source["census"]["repositories"][0]["id"]

    def commits(path):
        repo = "/".join(path.split("/")[2:4])
        if repo == first:
            return {"sha": "f" * 40}
        row = next(r for r in source["census"]["repositories"] if r["id"] == repo)
        return {"sha": row["source_sha"]}

    snap = rc.collect(source, getter=make_getter(source, overrides={"/commits/": commits}),
                      observed_at_utc=UTC)
    changed = {r["repo"]: r["head_changed"] for r in snap["repositories"]}
    assert changed[first] is True
    assert sum(changed.values()) == 1
    row = next(r for r in snap["repositories"] if r["repo"] == first)
    assert row["source"] == "https://github.com/%s/tree/%s" % (first, "f" * 40)
    assert all(p["base_branch"] is None for p in snap["scoped_pr_heads"])
    assert all(p["head_sha"] == "b" * 40 for p in snap["scoped_pr_heads"])
    assert len(snap["source_register_sha256"]) == 64


def test_collect_full_issue_register(source):
    getter = make_getter(source, issue_items=True)
    snap = rc.collect(source, getter=getter, observed_at_utc=UTC,
                      include_pr_heads=False, include_issue_register=True)
    totals = snap["totals"]
    assert snap["issue_register_observed"] == totals["open_issues"] + totals["closed_issues"]
    assert snap["issue_register_full_population_verified"] is True
    assert {r["state"] for r in snap["issue_register_records"]} <= {"open", "closed"}
    assert all(r["bd_root_id"] is None and r["accepted_root_closure"] is None
               for r in snap["issue_register_records"])
    assert snap["scoped_pr_heads"] == []


# --- main ---------------------------------------------------------------------------------

def _fake_github(source, store):
    getter = make_getter(source, issue_items=True)

    def fake(path, *, token=None):
        store.append(token)
        return getter(path)

    return fake


def test_main_writes_receipt_with_gh_token(monkeypatch, tmp_path, capsys, source):
    tokens = []
    monkeypatch.setattr(rc, "github_get", _fake_github(source, tokens))
    monkeypatch.setenv("GH_TOKEN", "gh-test-token")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    out = tmp_path / "nested" / "recensus.json"
    assert rc.main(["--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["admission"] == "HOLD"
    assert data["scoped_pr_heads_observed"] == sum(w["ref_type"] == "pr" for w in source["work"])
    assert data["issue_register_observed"] is None
    assert set(tokens) == {"gh-test-token"}
    printed = json.loads(capsys.readouterr().out)
    assert printed["repos"] == len(source["census"]["repositories"])
    assert printed["pr_heads"] == data["scoped_pr_heads_observed"]
    assert printed["issues_open"] == data["totals"]["open_issues"]
    assert printed["admission"] == "HOLD"


def test_main_skip_pr_heads_full_register_github_token(monkeypatch, tmp_path, capsys, source):
    tokens = []
    monkeypatch.setattr(rc, "github_get", _fake_github(source, tokens))
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    out = tmp_path / "r.json"
    monkeypatch.setattr(sys, "argv", ["recensus.py", "--out", str(out),
                                      "--skip-pr-heads", "--full-issue-register",
                                      "--source", str(rc.REGISTRY)])
    assert rc.main() == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["pr_heads"] == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert printed["issue_register_observed"] == data["totals"]["open_issues"] + data["totals"]["closed_issues"]
    assert set(tokens) == {"test-token"}
    assert out.read_text(encoding="utf-8").endswith("}\n")


def test_main_without_tokens_passes_none(monkeypatch, tmp_path, capsys, source):
    tokens = []
    monkeypatch.setattr(rc, "github_get", _fake_github(source, tokens))
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert rc.main(["--out", str(tmp_path / "o.json"), "--skip-pr-heads"]) == 0
    assert set(tokens) == {None}
