"""Coverage wave w9: required_gate/gate.py edge paths (offline, fake GitHub API only)."""
import base64
import hashlib
import importlib.util
import io
import json
import runpy
import sys
import urllib.error
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "gogreen" / "required_gate"
MOD_PATH = MOD_DIR / "gate.py"
_spec = importlib.util.spec_from_file_location("cw_w9_required_gate_mod", MOD_PATH)
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)

SHA = "a" * 40
BASE = "b" * 40
REPO = "GBOGEB/pipeline-automation-hub"


def mini_repo(root, workflows):
    w = root / ".github" / "workflows"
    w.mkdir(parents=True, exist_ok=True)
    for name, text in workflows.items():
        (w / name).write_text(text, encoding="utf-8", newline="\n")
    return root


def write_ledger(root, entries):
    p = root / g.ADMISSION
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"schema": g.ADMISSION_SCHEMA, "entries": [{"path": k, "disposition": v} for k, v in entries.items()]}
    p.write_text(json.dumps(doc), encoding="utf-8", newline="\n")


def route_opener(route, calls=None):
    def opener(req, timeout):
        u = req.full_url
        if calls is not None:
            calls.append((req.get_method(), u))
        body = route(req, u)
        return io.BytesIO(json.dumps(body).encode())
    return opener


def fake_reader(route, calls=None, token=""):
    return g.Reader(REPO, token=token, opener=route_opener(route, calls))


# ---------------------------------------------------------------- triggers / fires_for_base

@pytest.mark.parametrize("text,key", [
    ("- just\n- a list\n", "parse_error"),
    ("on: 7\njobs: {}\n", None),
    ("on: [pull_request, push]\n", None),
    ("on: pull_request\n", None),
])
def test_triggers_shapes(tmp_path, text, key):
    p = tmp_path / "w.yml"
    p.write_text(text, encoding="utf-8", newline="\n")
    t = g.triggers(p)
    if key:
        assert t["parse_error"] == "workflow is not a mapping"
        assert g.fires_for_base(t, "master") == "workflow YAML does not parse"
    elif "7" in text:
        assert t["pull_request"] is False
        assert g.fires_for_base(t, "master") == "no pull_request trigger"
    else:
        assert t["pull_request"] is True
        assert g.fires_for_base(t, None) is None


def test_triggers_unreadable_file(tmp_path):
    t = g.triggers(tmp_path / "missing.yml")
    assert t["pull_request"] is False and t["parse_error"]


def test_branches_ignore_blocks_base():
    t = {"pull_request": True, "branches_ignore": ["master"]}
    assert "branches-ignore" in g.fires_for_base(t, "master")
    assert g.fires_for_base(t, "dev") is None


# ---------------------------------------------------------------- Reader

def test_reader_headers_with_token_and_bad_path():
    r = g.Reader(REPO, token="test-token", opener=lambda *a, **k: None)
    assert r._headers()["Authorization"] == "Bearer test-token"
    with pytest.raises(ValueError):
        r.get("/repos/other/repo/pulls")
    with pytest.raises(ValueError):
        r.get(f"/repos/{REPO}/../x")
    assert r.requests == 0


def test_reader_token_from_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    r = g.Reader(REPO, opener=lambda *a, **k: None)
    assert r.token == "test-token"


def test_head_runs_paginates_and_skips_pathless():
    def route(req, u):
        page = int(u.rsplit("page=", 1)[1])
        if page == 1:
            runs = [{"id": i, "path": ".github/workflows/a.yml@refs/pull/1"} for i in range(99)] + [{"id": 999}]
            return {"total_count": 101, "workflow_runs": runs}
        return {"total_count": 101, "workflow_runs": [{"id": 1000, "path": ".github/workflows/b.yml"}]}
    calls = []
    by = g.head_runs_by_workflow(fake_reader(route, calls), SHA)
    assert len(calls) == 2
    assert len(by[".github/workflows/a.yml"]) == 99
    assert len(by[".github/workflows/b.yml"]) == 1


# ---------------------------------------------------------------- load_policy

def test_load_policy_modes(tmp_path):
    assert g.load_policy(None, None, tmp_path, "bootstrap")["source"].startswith("bootstrap")
    with pytest.raises(ValueError):
        g.load_policy(None, "nope", tmp_path, "base")


def test_load_policy_reraises_non_404():
    def route(req, u):
        raise urllib.error.HTTPError(u, 500, "boom", {}, None)
    with pytest.raises(urllib.error.HTTPError):
        g.load_policy(fake_reader(route), BASE, Path("."), "base")


def test_load_policy_from_base_content():
    doc = {"schema": g.ADMISSION_SCHEMA, "entries": [{"path": ".github/workflows/a.yml", "disposition": g.EXCLUDED,
                                                      "reasons": ["X"]}]}
    def route(req, u):
        return {"content": base64.b64encode(json.dumps(doc).encode()).decode()}
    p = g.load_policy(fake_reader(route), BASE, Path("."), "base")
    assert p["entries"] == {".github/workflows/a.yml": g.EXCLUDED}
    assert p["reasons"][".github/workflows/a.yml"] == ["X"]


# ---------------------------------------------------------------- evaluate

def eval_route(files, run_seq):
    """PR files; head-run listings drawn from run_seq in order (last one repeats)."""
    state = {"i": 0}

    def route(req, u):
        if "/pulls/" in u:
            return [{"filename": f} for f in files] if "page=1" in u else []
        if "/actions/runs?head_sha=" in u:
            listing = run_seq[min(state["i"], len(run_seq) - 1)]
            state["i"] += 1
            runs = [dict(r, path=".github/workflows/" + n) for n, rs in listing.items() for r in rs]
            return {"total_count": len(runs), "workflow_runs": runs}
        raise AssertionError(u)
    return route


def test_evaluate_excluded_absent_and_polling(tmp_path):
    root = mini_repo(tmp_path, {
        "a.yml": "name: A\non:\n  pull_request:\n    paths: ['a/**']\n",
        "ex.yml": "name: EX\non: pull_request\n",
        "obs.yml": "name: OBS\non: pull_request\n",
    })
    policy = {"source": "test", "entries": {
        ".github/workflows/a.yml": g.ENFORCED,
        ".github/workflows/ex.yml": g.EXCLUDED,
        ".github/workflows/obs.yml": g.OBSERVED,
        ".github/workflows/gone.yml": g.ENFORCED},
        "reasons": {".github/workflows/ex.yml": ["DECLARED_EXCLUDE"]}}
    seq = [{}, {"a.yml": [{"status": "completed", "conclusion": "success", "id": 5}],
                "obs.yml": [{"status": "completed", "conclusion": "failure", "id": 6}]}]
    ticks = iter(range(100))
    slept = []
    rep = g.evaluate(fake_reader(eval_route(["a/x.py"], seq)), root, 1, SHA, 1000, poll_s=7,
                     clock=lambda: next(ticks), sleep=slept.append, policy=policy)
    assert slept == [7]
    assert rep["excluded"] == [{"workflow": ".github/workflows/ex.yml", "reasons": ["DECLARED_EXCLUDE"]}]
    gone = [x for x in rep["gates"] if x["workflow"] == ".github/workflows/gone.yml"][0]
    assert gone["reason"] == "workflow file absent in PR head" and gone["state"] == g.NA
    assert rep["verdict"] == g.PASS
    md = g.summary_markdown(rep)
    assert "OBS" in md and "| ENFORCED | A | PASS |" in md


def test_summary_skips_unmatched_observed():
    rep = {"verdict": g.PASS, "policy_source": "p", "changed_files": 0,
           "coverage": {"workflows_in_head": 1, "enforced": 0, "enforced_applicable": 0, "observed": 1,
                        "observed_applicable": 0, "unlisted": 0, "excluded": 0},
           "gates": [], "observed": [{"workflow": "w", "disposition": g.OBSERVED, "matched_files": [],
                                      "state": g.NA}]}
    md = g.summary_markdown(rep)
    assert "| OBSERVED" not in md


def test_run_link_without_attempt():
    assert g.run_link({"id": 3, "url": "u"}) == "[run 3](u)"
    assert g.run_link(None) == "—"


# ---------------------------------------------------------------- recheck names

def test_recheck_names_skips_missing_and_non_pr(tmp_path):
    root = mini_repo(tmp_path, {"push.yml": "name: P\non: push\n", "pr.yml": "on: pull_request\n"})
    policy = {"entries": {".github/workflows/push.yml": g.ENFORCED, ".github/workflows/pr.yml": g.ENFORCED,
                          ".github/workflows/missing.yml": g.ENFORCED, g.SELF: g.ENFORCED}}
    assert g.recheck_names(root, policy) == [".github/workflows/pr.yml"]


def test_declared_recheck_names_errors():
    with pytest.raises(ValueError, match="markers"):
        g.declared_recheck_names("nothing here\n")
    bad = f"{g.RECHECK_BEGIN}\n  junk\n{g.RECHECK_END}\n"
    with pytest.raises(ValueError, match="unexpected line"):
        g.declared_recheck_names(bad)


RECHECK_WF = ("name: R\non:\n  workflow_run:\n    workflows:\n      " + "# BEGIN recheck-names\n"
              "      - \"Old\"\n      # END recheck-names\n    types: [completed]\n")


def test_main_recheck_names_write_check(tmp_path, capsys):
    root = mini_repo(tmp_path, {"a.yml": "name: Alpha\non: pull_request\n",
                                "gogreen-required-gate-recheck.yml": RECHECK_WF})
    write_ledger(root, {".github/workflows/a.yml": g.ENFORCED})
    assert g.main(["recheck-names", "--root", str(root), "--check"]) == 1
    assert "out of sync" in capsys.readouterr().err
    assert g.main(["recheck-names", "--root", str(root), "--write", "--check"]) == 0
    assert capsys.readouterr().out.strip() == "Alpha"
    text = (root / g.RECHECK).read_text(encoding="utf-8")
    assert g.declared_recheck_names(text) == ["Alpha"]
    assert "types: [completed]" in text


# ---------------------------------------------------------------- receipts

def test_receipt_relevance_invalid_sha():
    out = g.receipt_recheck_relevance({}, sha="short", workflow_path=".github/workflows/a.yml")
    assert out["decision"] == g.RECHECK_UNKNOWN and out["reason"] == "invalid exact head SHA"


def make_artifact(report=None, encrypt=False, oversized=False):
    rep = report if report is not None else {"schema": "gogreen.required_gate.v2", "head_sha": SHA, "pr": 4,
                                             "verdict": g.FAIL, "merge_authorized": False, "gates": []}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        body = json.dumps(rep) + (" " * (g.MAX_RECHECK_RECEIPT_ZIP + 1) if oversized else "")
        z.writestr("required-gate.json", body)
    data = bytearray(buf.getvalue())
    if encrypt:  # set general-purpose bit 0 in both local and central headers
        for sig in (b"PK\x03\x04", b"PK\x01\x02"):
            i = data.find(sig)
            off = i + (6 if sig == b"PK\x03\x04" else 8)
            data[off] |= 1
    archive = bytes(data)
    md = {"id": 7, "name": "gogreen-required-gate-4-1", "expired": False,
          "url": f"https://api.github.com/repos/{REPO}/actions/artifacts/7",
          "digest": "sha256:" + hashlib.sha256(archive).hexdigest(),
          "workflow_run": {"id": 9, "head_sha": SHA}}
    return md, archive


def verify(md, archive, **kw):
    args = dict(repo=REPO, run_id=9, attempt=1, pr=4, sha=SHA)
    args.update(kw)
    return g.verify_recheck_artifact(md, archive, **args)


def test_verify_artifact_identity_rejections():
    md, archive = make_artifact()
    assert verify(md, archive)["decision"] == "VERIFIED_FAILED_RECEIPT"
    assert verify(md, archive, repo="bad repo")["reason"] == "invalid repository or exact source SHA"
    assert verify(md, archive, run_id=True)["reason"] == "invalid required run, attempt or PR identity"
    assert verify(md, archive, attempt=0)["reason"] == "invalid required run, attempt or PR identity"
    assert verify(dict(md, id=False), archive)["reason"] == "invalid artifact identity"
    assert verify(dict(md, id=-1), archive)["reason"] == "invalid artifact identity"


def test_verify_artifact_member_rejections():
    md, archive = make_artifact(oversized=True)
    assert verify(md, archive)["reason"] == "missing or oversized receipt member"
    md, archive = make_artifact(encrypt=True)
    assert verify(md, archive)["reason"] == "encrypted receipt not supported"


def test_verify_artifact_non_failed_report():
    rep = {"schema": "gogreen.required_gate.v2", "head_sha": SHA, "pr": 4, "verdict": g.PASS,
           "merge_authorized": False, "gates": []}
    md, archive = make_artifact(rep)
    assert verify(md, archive)["reason"] == "receipt is not a failed non-authoritative aggregator report"


# ---------------------------------------------------------------- main / main_recheck

def test_main_recheck_requires_repo(monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    with pytest.raises(SystemExit, match="--repo or GITHUB_REPOSITORY"):
        g.main(["recheck", "--sha", SHA])


def test_main_recheck_writes_step_summary(tmp_path, monkeypatch, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    run = {"id": 11, "status": "completed", "conclusion": "failure", "run_attempt": 1}

    def route(req, u):
        return {"workflow_runs": [run]}
    monkeypatch.setattr("urllib.request.urlopen", route_opener(route))
    assert g.main(["recheck", "--repo", REPO, "--sha", SHA, "--dry-run"]) == 0
    assert "recheck dry-run" in capsys.readouterr().out
    text = summary.read_text(encoding="utf-8")
    assert "re-check: **dry-run**" in text and "attempts/1" in text


def test_main_rejects_bad_sha():
    with pytest.raises(SystemExit, match="invalid head SHA"):
        g.main(["--repo", REPO, "--pr", "1", "--sha", "xyz"])


def test_main_prints_json_and_observed_warning(tmp_path, monkeypatch, capsys):
    root = mini_repo(tmp_path, {"a.yml": "name: A\non: pull_request\n", "b.yml": "name: B\non: pull_request\n",
                                "c.yml": "on: pull_request\n", "d.yml": "name: D\non: pull_request\n"})
    write_ledger(root, {".github/workflows/a.yml": g.ENFORCED, ".github/workflows/b.yml": g.OBSERVED,
                        ".github/workflows/c.yml": g.OBSERVED, ".github/workflows/d.yml": g.OBSERVED})
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    seq = [{"a.yml": [{"status": "completed", "conclusion": "success"}],
            "b.yml": [{"status": "completed", "conclusion": "failure", "id": 3}],
            "c.yml": [{"status": "completed", "conclusion": "failure"}],
            "d.yml": [{"status": "completed", "conclusion": "success"}]}]
    monkeypatch.setattr("urllib.request.urlopen", route_opener(eval_route(["x"], seq)))
    rc = g.main(["--repo", REPO, "--pr", "1", "--sha", SHA, "--root", str(root), "--policy", "head",
                 "--deadline-min", "0"])
    out = capsys.readouterr().out
    assert rc == 0
    assert '"schema": "gogreen.required_gate.v2"' in out
    assert ".github/workflows/a.yml: PASS (1 matched)" in out
    assert "::warning title=GOGREEN observed (not blocking) FAIL::B — https://github.com/" in out
    assert "::warning title=GOGREEN observed (not blocking) FAIL::.github/workflows/c.yml\n" in out
    assert "FAIL::D" not in out


def test_changed_files_pages_and_renames():
    def route(req, u):
        page = int(u.rsplit("page=", 1)[1])
        if page == 1:
            return [{"filename": f"f{i}"} for i in range(99)] + [{"filename": "new", "previous_filename": "old"}]
        return [{"filename": "last"}]
    calls = []
    files = g.changed_files(fake_reader(route, calls), 3)
    assert len(calls) == 2
    assert files[-3:] == ["new", "old", "last"]


def test_main_dunder_runs_recheck_receipt(tmp_path, monkeypatch, capsys):
    rep = tmp_path / "r.json"
    rep.write_text(json.dumps({}), encoding="utf-8", newline="\n")
    monkeypatch.setattr(sys, "argv", ["gate.py", "recheck-receipt", "--report", str(rep), "--sha", SHA,
                                      "--workflow", ".github/workflows/a.yml"])
    with pytest.raises(SystemExit) as e:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert e.value.code == 2
    assert '"decision": "UNKNOWN"' in capsys.readouterr().out
