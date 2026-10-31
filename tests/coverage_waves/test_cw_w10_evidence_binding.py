"""Coverage wave w10: mission-control/grand-missions/evidence_binding.py (faked GitHub API only)."""
import importlib.util
import io
import json
import runpy
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "grand-missions" / "evidence_binding.py"
_spec = importlib.util.spec_from_file_location("cw_w10_evidence_binding_mod", MOD_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

REPO = "GBOGEB/pipeline-automation-hub"
GATE = "f" * 40
HEAD = "1" * 40


def _resp(obj):
    return io.BytesIO(json.dumps(obj).encode())


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ Reader


def test_reader_rejects_bad_repo():
    with pytest.raises(ValueError, match="invalid owner/repo"):
        mod.Reader("not a repo", token="test-token")
    with pytest.raises(ValueError, match="invalid owner/repo"):
        mod.Reader(None, token="test-token")


@pytest.mark.parametrize("path", ["/repos/other/x/runs", "/repos/%s/../secrets" % REPO])
def test_reader_rejects_unapproved_paths(path):
    with pytest.raises(ValueError, match="unapproved read path"):
        mod.Reader(REPO, token="test-token", opener=lambda *a, **k: None).get(path)


def test_reader_sends_bearer_token_and_env_fallback(monkeypatch):
    seen = {}

    def opener(req, timeout):
        seen["auth"] = req.get_header("Authorization")
        seen["timeout"] = timeout
        return _resp({"ok": 1})

    assert mod.Reader(REPO, token="test-token", opener=opener).get("/repos/%s/x" % REPO) == {"ok": 1}
    assert seen == {"auth": "Bearer test-token", "timeout": 20}
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "test-token")
    assert mod.Reader(REPO).token == "test-token"
    assert mod.Reader(REPO).opener is urllib.request.urlopen


# ------------------------------------------------------------------ resolve


class FakeApi:
    def __init__(self, runs, arts, ancestors=()):
        self.runs, self.arts, self.anc = runs, arts, set(ancestors)
        self.urls = []

    def __call__(self, req, timeout):
        u = req.full_url
        self.urls.append(u)
        if "/runs?" in u:
            return _resp({"workflow_runs": self.runs})
        if "/artifacts" in u:
            rid = int(u.split("/runs/")[1].split("/")[0])
            return _resp({"artifacts": self.arts.get(rid, [])})
        if "/compare/" in u:
            a = u.split("/compare/")[1].split("...")[0]
            return _resp({"status": "ahead" if a in self.anc else "behind"})
        raise AssertionError(u)


def _run(i, head, created, **kw):
    r = {"id": i, "head_sha": head, "event": "push", "status": "completed",
         "conclusion": "success", "created_at": created}
    r.update(kw)
    return r


def _art(i, head, prefix="p-"):
    return {"id": i, "name": prefix + head, "expired": False, "digest": "sha256:" + "a" * 64,
            "expires_at": "2026-12-01T00:00:00Z"}


def test_resolve_head_equal_to_gate_skips_compare_and_rejects_not_success():
    now = datetime(2026, 10, 31, tzinfo=timezone.utc)
    api = FakeApi([_run(2, GATE, "2026-10-30T00:00:00Z", conclusion="failure"),
                   _run(1, GATE, "2026-10-29T00:00:00Z")], {1: [_art(10, GATE)]})
    binding, run, art, arts = mod.resolve(mod.Reader(REPO, token="", opener=api), "p.yml", "p-", GATE, now=now)
    assert binding["run_id"] == 1
    assert binding["rejected_newer_candidates"] == [{"run_id": 2, "reason": "not success"}]
    assert not any("/compare/" in u for u in api.urls)


def test_resolve_no_runs_fails_closed():
    api = FakeApi([], {})
    with pytest.raises(mod.EvidenceError, match="NO_VALID_EVIDENCE"):
        mod.resolve(mod.Reader(REPO, token="", opener=api), "p.yml", "p-", GATE)


# ------------------------------------------------------------------ cron


def test_cron_bad_field_count():
    with pytest.raises(ValueError, match="bad cron"):
        mod.cron_period_days("* * *")


@pytest.mark.parametrize("expr,days", [
    ("0 0 * * 1-5", 3),
    ("0 0 * * 1-3,5", 3),
    ("0 0 * * 0", 7),
])
def test_cron_dow_ranges(expr, days):
    assert mod.cron_period_days(expr) == days


@pytest.mark.xfail(strict=True, reason="production_defect: cron dow range 6-7 keeps 7 unreduced, so 0 and 7 (both Sunday) yield a spurious 7-day gap")
def test_cron_dow_range_seven_is_sunday():
    # Saturday+Sunday: longest gap between firings is 6 days (Sun -> Sat).
    assert mod.cron_period_days("0 0 * * 0,6-7") == 6


# ------------------------------------------------------------------ census


def test_census_max_files_and_unreadable_file(tmp_path, monkeypatch):
    (tmp_path / "a.json").write_text('{"run_id": 333333333}', encoding="utf-8")
    (tmp_path / "b.json").write_text('{"run_id": 444444444}', encoding="utf-8")
    (tmp_path / "c.txt").write_text("ignored", encoding="utf-8")
    assert mod.census(tmp_path, REPO, max_files=1)["files_scanned"] == 1

    real = Path.read_text

    def flaky(self, *a, **k):
        if self.name == "a.json":
            raise OSError("locked")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", flaky)
    rep = mod.census(tmp_path, REPO)
    assert rep["files_scanned"] == 2
    assert [r["id"] for r in rep["rows"]] == ["444444444"]


def test_census_probes_run_and_artifact_without_expiry(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "g.yml").write_text("x actions/runs/555555555\ny actions/artifacts/666666666\n"
                              "z actions/runs/777777777\n", encoding="utf-8")
    (tmp_path / "rec.json").write_text('{"artifact_id": 888888888}', encoding="utf-8")

    def opener(req, timeout):
        u = req.full_url
        if u.endswith("/actions/runs/555555555"):
            return _resp({"created_at": "2026-10-01T00:00:00Z"})
        if u.endswith("/actions/runs/555555555/artifacts"):
            return _resp({"total_count": 2})
        if u.endswith("/actions/runs/777777777"):
            return _resp({"created_at": "2026-10-01T00:00:00Z"})
        if u.endswith("/actions/runs/777777777/artifacts"):
            return _resp({"total_count": 0})
        if u.endswith("/actions/artifacts/666666666"):
            return _resp({"expired": False})
        raise AssertionError(u)

    rep = mod.census(tmp_path, REPO, mod.Reader(REPO, token="", opener=opener))
    state = {r["id"]: r.get("state") for r in rep["rows"]}
    assert state == {"555555555": "LIVE", "666666666": "LIVE", "777777777": "DEAD", "888888888": None}
    art = next(r for r in rep["rows"] if r["id"] == "666666666")
    assert art["api"]["days_left"] is None
    assert rep["live_gate_pins_dead"] == 1


# ------------------------------------------------------------------ CLI


def _fake_urlopen(created):
    api = FakeApi([_run(9, HEAD, created)], {9: [_art(90, HEAD)]}, ancestors={HEAD})
    return api


def test_main_resolve_pass_writes_all_outputs(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    created = _iso(datetime.now(timezone.utc) - timedelta(days=1))
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(created))
    rc = mod.main(["resolve", "--repo", REPO, "--producer", "p.yml", "--artifact-prefix", "p-",
                   "--source-sha", GATE, "--run-out", str(tmp_path / "run.json"),
                   "--artifact-out", str(tmp_path / "art.json"),
                   "--artifacts-list-out", str(tmp_path / "list.json"),
                   "--binding-out", str(tmp_path / "bind.json")])
    assert rc == 0
    assert json.loads((tmp_path / "bind.json").read_text(encoding="utf-8"))["result"] == "PASS"
    assert json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))["id"] == 9
    assert json.loads((tmp_path / "art.json").read_text(encoding="utf-8"))["id"] == 90
    assert json.loads((tmp_path / "list.json").read_text(encoding="utf-8"))["total_count"] == 1
    assert "PASS_LATEST_VALID_EVIDENCE p.yml run=9" in capsys.readouterr().out


def test_main_resolve_pass_binding_only(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    created = _iso(datetime.now(timezone.utc) - timedelta(days=1))
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(created))
    rc = mod.main(["resolve", "--repo", REPO, "--producer", "p.yml", "--artifact-prefix", "p-",
                   "--source-sha", GATE, "--binding-out", str(tmp_path / "bind.json")])
    assert rc == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bind.json"]


@pytest.mark.parametrize("ok,rc", [(True, 0), (False, 1)])
def test_main_dag_check(tmp_path, monkeypatch, capsys, ok, rc):
    rep = {"schema": "s", "ok": ok, "problems": [] if ok else ["p"], "rows": []}
    seen = []
    monkeypatch.setattr(mod, "dag_check", lambda root: seen.append(root) or rep)
    out = tmp_path / "dag.json"
    assert mod.main(["dag-check", "--root", str(tmp_path), "--out", str(out)]) == rc
    assert seen == [tmp_path]
    assert json.loads(out.read_text(encoding="utf-8"))["ok"] is ok
    assert json.loads(capsys.readouterr().out)["ok"] is ok


def test_main_dag_check_without_out(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "dag_check", lambda root: {"ok": True, "problems": [], "rows": []})
    assert mod.main(["dag-check", "--root", str(tmp_path)]) == 0
    assert list(tmp_path.iterdir()) == []


def test_main_census_with_api(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    wf = tmp_path / "src" / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "g.yml").write_text("assert run['id']==999999999\n", encoding="utf-8")

    def opener(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "nf", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", opener)
    out = tmp_path / "census.json"
    assert mod.main(["census", "--root", str(tmp_path / "src"), "--repo", REPO, "--api",
                     "--out", str(out)]) == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["live_gate_pins_dead"] == 1
    assert rep["rows"][0]["api"] == {"resolved_kind": "id", "exists": False, "http_status": 404, "dead": True}
    assert json.loads(capsys.readouterr().out)["live_gate_pins"] == 1


def test_dunder_main_census_offline(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    out = tmp_path / "census.json"
    monkeypatch.setattr(sys, "argv", ["evidence_binding.py", "census", "--root", str(tmp_path / "src"),
                                      "--repo", REPO, "--out", str(out)])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert exc.value.code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["pins_total"] == 0
