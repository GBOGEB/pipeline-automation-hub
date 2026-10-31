"""Coverage wave r9: public_census_pull (offline, no network)."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "v2" / "handoff" / "closeout"
MOD_PATH = MOD_DIR / "public_census_pull.py"
if str(MOD_DIR) not in sys.path:
    sys.path.insert(0, str(MOD_DIR))
_spec = importlib.util.spec_from_file_location("cw_r9_public_census_pull_mod", MOD_PATH)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

CLOCK = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
SHA = "b" * 40


def stamp(days):
    return (CLOCK - timedelta(days=days)).isoformat().replace("+00:00", "Z")


def make_fetch(issues=None, *, count=None, pr_count=3, branch=None, repo_over=None,
               page_count_shift=False):
    """Fake GitHub GET. issues: list of issue dicts served 100 per page."""
    if issues is None:
        issues = [{"number": 1, "created_at": stamp(1)}]
    calls = []

    def fetch(path):
        calls.append(path)
        if path.startswith("/search/issues?"):
            qs = parse_qs(urlsplit(path).query)
            q = qs["q"][0]
            page = int(qs["page"][0])
            if "is:pr" in q:
                assert qs["per_page"] == ["1"]
                return {"total_count": pr_count, "items": [], "incomplete_results": False}
            total = len(issues) if count is None else count
            if page_count_shift and page > 1:
                total += 1
            chunk = [dict(i) for i in issues[(page - 1) * 100: page * 100]]
            return {"total_count": total, "items": chunk, "incomplete_results": False}
        if "/branches/" in path:
            if branch is not None:
                return dict(branch)
            return {"commit": {"sha": SHA}, "protected": True}
        repo = path.split("/repos/", 1)[1]
        out = {"full_name": repo, "default_branch": dict(m.PUBLIC)[repo], "private": False}
        if repo_over:
            out.update(repo_over)
        return out

    return fetch, calls


# ---------------- get_json ----------------

class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
        return False


@pytest.mark.parametrize("path", ["noslash", "/x://y", "/a//b"])
def test_get_json_rejects_unsafe_paths(path):
    with pytest.raises(ValueError, match="unsafe"):
        m.get_json(path)


def test_get_json_without_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    seen = {}

    def fake_urlopen(req, timeout):
        seen["req"], seen["timeout"] = req, timeout
        return FakeResp(b'{"ok": 1}')

    monkeypatch.setattr(m, "urlopen", fake_urlopen)
    assert m.get_json("/repos/x/y") == {"ok": 1}
    req = seen["req"]
    assert req.full_url == "https://api.github.com/repos/x/y"
    assert req.get_method() == "GET"
    assert seen["timeout"] == 20
    assert req.get_header("Authorization") is None
    assert req.get_header("X-github-api-version") == "2022-11-28"


def test_get_json_with_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok123")
    seen = {}

    def fake_urlopen(req, timeout):
        seen["req"] = req
        return FakeResp(b'{"a": [1]}')

    monkeypatch.setattr(m, "urlopen", fake_urlopen)
    assert m.get_json("/x") == {"a": [1]}
    assert seen["req"].get_header("Authorization") == "Bearer tok123"


def test_get_json_non_dict_rejected(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(m, "urlopen", lambda req, timeout: FakeResp(b"[1, 2]"))
    with pytest.raises(ValueError, match="invalid API response"):
        m.get_json("/x")


# ---------------- search ----------------

def test_search_ok_and_query():
    seen = []

    def fetch(p):
        seen.append(p)
        return {"total_count": 2, "items": [1, 2], "incomplete_results": False}

    assert m.search(fetch, "o/r", "issue", page=3, per_page=7) == (2, [1, 2])
    qs = parse_qs(urlsplit(seen[0]).query)
    assert qs == {"q": ["repo:o/r is:open is:issue"], "per_page": ["7"], "page": ["3"]}


@pytest.mark.parametrize("res", [
    {"total_count": True, "items": [], "incomplete_results": False},
    {"total_count": "1", "items": [], "incomplete_results": False},
    {"total_count": -1, "items": [], "incomplete_results": False},
    {"total_count": 0, "items": {}, "incomplete_results": False},
    {"total_count": 0, "items": [], "incomplete_results": True},
    {"total_count": 0, "items": []},
])
def test_search_rejects_incomplete(res):
    with pytest.raises(ValueError, match="incomplete GitHub search"):
        m.search(lambda p: res, "o/r", "issue")


# ---------------- collect ----------------

def test_collect_happy_bins_and_shape():
    issues = [
        {"number": 1, "created_at": stamp(0)},
        {"number": 2, "created_at": stamp(6.9)},
        {"number": 3, "created_at": stamp(7)},
        {"number": 4, "created_at": stamp(13.9)},
        {"number": 5, "created_at": stamp(14)},
        {"number": 6, "created_at": stamp(29.9)},
        {"number": 7, "created_at": stamp(30)},
        {"number": 8, "created_at": "2020-01-01T00:00:00+00:00"},
    ]
    fetch, calls = make_fetch(issues, pr_count=2)
    d = m.collect(fetch, CLOCK)
    assert d["schema"] == "missioncontrol.public_census_get_only.v1"
    assert d["observed_utc"] == "2026-10-18T12:00:00Z"
    assert len(d["repositories"]) == 4
    row = d["repositories"][0]
    assert row["age_bins_0_6_7_13_14_29_30plus"] == [2, 2, 2, 2]
    assert row["protected_rest"] is True
    assert row["head_sha"] == SHA
    assert row["open_prs"] == 2
    assert d["age_bins"] == [8, 8, 8, 8]
    assert d["ordinary_open_issues"] == 32
    assert d["open_prs"] == 8
    assert d["snapshot_atomic"] is False
    assert d["restricted_child_sources"] == "WITHHELD"
    assert d["security_waiver"] is False
    # 4 repos x (repo, branch, issue search, pr search)
    assert len(calls) == 16


def test_collect_protected_non_bool_is_none():
    fetch, _ = make_fetch(branch={"commit": {"sha": SHA}, "protected": "yes"})
    d = m.collect(fetch, CLOCK)
    assert all(r["protected_rest"] is None for r in d["repositories"])


def test_collect_zero_issues():
    fetch, calls = make_fetch([], pr_count=0)
    d = m.collect(fetch, CLOCK)
    assert d["ordinary_open_issues"] == 0 and d["age_bins"] == [0, 0, 0, 0]
    assert sum(1 for c in calls if c.startswith("/search")) == 8


def test_collect_paginates():
    issues = [{"number": i, "created_at": stamp(1)} for i in range(1, 251)]
    fetch, calls = make_fetch(issues)
    d = m.collect(fetch, CLOCK)
    assert d["repositories"][0]["ordinary_open_issues"] == 250
    pages = [parse_qs(urlsplit(c).query)["page"][0] for c in calls[:6] if c.startswith("/search")]
    assert pages == ["1", "2", "3", "1"]


def test_collect_default_clock_used():
    fetch, _ = make_fetch([])
    d = m.collect(fetch)
    assert d["observed_utc"].endswith("Z")
    parsed = datetime.fromisoformat(d["observed_utc"].replace("Z", "+00:00"))
    assert parsed.tzinfo is not None


@pytest.mark.parametrize("over", [
    {"full_name": "other/repo"},
    {"private": None},
    {"private": True},
    {"default_branch": "dev"},
])
def test_collect_rejects_repo_metadata(over):
    fetch, _ = make_fetch(repo_over=over)
    with pytest.raises(ValueError, match="private, stale"):
        m.collect(fetch, CLOCK)


@pytest.mark.parametrize("branch", [{}, {"commit": {}}, {"commit": {"sha": 5}},
                                    {"commit": {"sha": "A" * 40}}])
def test_collect_rejects_bad_sha(branch):
    fetch, _ = make_fetch(branch=branch)
    with pytest.raises(ValueError, match="exact source SHA"):
        m.collect(fetch, CLOCK)


def test_collect_rejects_over_cap():
    fetch, _ = make_fetch([], count=1001)
    with pytest.raises(ValueError, match="1000 cap"):
        m.collect(fetch, CLOCK)


def test_collect_rejects_shifting_denominator():
    issues = [{"number": i, "created_at": stamp(1)} for i in range(1, 102)]
    fetch, _ = make_fetch(issues, page_count_shift=True)
    with pytest.raises(ValueError, match="pagination changed"):
        m.collect(fetch, CLOCK)


def test_collect_rejects_non_int_number():
    fetch, _ = make_fetch([{"number": "1", "created_at": stamp(1)}])
    with pytest.raises(ValueError, match="PR/duplicate"):
        m.collect(fetch, CLOCK)


def test_collect_rejects_missing_timestamp():
    fetch, _ = make_fetch([{"number": 1}])
    with pytest.raises(ValueError, match="missing issue timestamp"):
        m.collect(fetch, CLOCK)


def test_collect_rejects_future_issue():
    fetch, _ = make_fetch([{"number": 1, "created_at": "2026-10-19T00:00:00Z"}])
    with pytest.raises(ValueError, match="future issue"):
        m.collect(fetch, CLOCK)


# ---------------- main ----------------

def test_main_success(monkeypatch, tmp_path, capsys):
    out = tmp_path / "deep" / "census.json"
    fetch, _ = make_fetch([{"number": 1, "created_at": stamp(2)}], pr_count=1)
    real = m.collect
    monkeypatch.setattr(m, "collect", lambda: real(fetch, CLOCK))
    monkeypatch.setattr(sys, "argv", ["prog", "--out", str(out)])
    assert m.main() == 0
    raw = out.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    assert data["ordinary_open_issues"] == 4
    assert raw.endswith(b"}\n") and b"\r\n" not in raw
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"admission": "HOLD", "issues": 4, "prs": 4, "repos": 4}


@pytest.mark.parametrize("exc", [ValueError("x"), OSError("x"), RuntimeError("x"),
                                 KeyError("x"), TypeError("x")])
def test_main_hold_on_error(monkeypatch, tmp_path, capsys, exc):
    def boom():
        raise exc

    monkeypatch.setattr(m, "collect", boom)
    monkeypatch.setattr(sys, "argv", ["prog", "--out", str(tmp_path / "c.json")])
    assert m.main() == 2
    err = capsys.readouterr().err
    assert "CENSUS_PULL_HOLD" in err and type(exc).__name__ in err
    assert not (tmp_path / "c.json").exists()


def test_main_requires_out(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog"])
    with pytest.raises(SystemExit) as ei:
        m.main()
    assert ei.value.code == 2


def test_dunder_main_guard_exits_before_network(monkeypatch, capsys):
    import runpy

    monkeypatch.setattr(sys, "argv", ["public_census_pull.py"])
    with pytest.raises(SystemExit) as ei:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert ei.value.code == 2
    assert "--out" in capsys.readouterr().err
