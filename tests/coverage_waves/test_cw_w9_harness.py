"""Coverage wave 9: mission-control/pipeline_runtime/harness.py.

The pipeline subprocess and ``git rev-parse`` are faked: no real process is
launched. The fake writes tracer proc-*.json records into TRACE_OUT and
changes files in the output directory, exactly as the real tracer would.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "mission-control" / "pipeline_runtime" / "harness.py"
_spec = importlib.util.spec_from_file_location("cw_w9_harness_mod", MOD_PATH)
h = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = h
_spec.loader.exec_module(h)

HEAD = "c" * 40


def _arg(cmd, flag):
    return Path(cmd[cmd.index(flag) + 1])


def _proc(pid, ppid, argv, started, functions=(), uncaught=()):
    return {"pid": pid, "ppid": ppid, "argv": argv, "started": started, "seconds": 0.5,
            "functions": [dict(f) for f in functions], "uncaught": [dict(u) for u in uncaught]}


def _fn(file, qualname, line, calls, order):
    return {"file": file, "qualname": qualname, "line": line, "calls": calls, "order": order}


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "scripts").mkdir(parents=True)
    (r / "scripts" / "run_processing.py").write_text("print('x')\n", encoding="utf-8")
    (r / "scripts" / "child.py").write_text("def analyse():\n    pass\n", encoding="utf-8")
    inp = r / "app" / "public" / "master_input"
    inp.mkdir(parents=True)
    (inp / "a.pptx").write_bytes(b"PK\x03\x04aaaa")
    (inp / "b.pptx").write_bytes(b"PK\x03\x04bbbb")
    out = r / "app" / "public" / "outputs"
    (out / "twins").mkdir(parents=True)
    (out / "twins" / "a.json").write_text('{"old": true, "same": 1}', encoding="utf-8")
    (out / "notes.json").write_text("not json", encoding="utf-8")
    (out / "list.json").write_text("[1]", encoding="utf-8")
    (out / "stale.txt").write_text("unchanged", encoding="utf-8")
    (out / "gone.txt").write_text("to delete", encoding="utf-8")
    (out / "mod.txt").write_text("v1", encoding="utf-8")
    (r / "node_modules").mkdir()
    (r / "node_modules" / "skip.js").write_text("x", encoding="utf-8")
    app = r / "app" / "app" / "api" / "twins"
    app.mkdir(parents=True)
    (app / "route.ts").write_text("read('outputs/twins')", encoding="utf-8")
    (r / "app" / "app" / "page.tsx").write_text("export default 1", encoding="utf-8")
    (r / "app" / "node_modules").mkdir()
    (r / "app" / "node_modules" / "dep.ts").write_text("outputs", encoding="utf-8")
    return r


@pytest.fixture
def fake_run(monkeypatch, repo):
    state = {"calls": [], "rc": 0, "stderr": "", "procs": None, "mutate_input": False,
             "stray": False, "tamper_out": True}

    def run(cmd, cwd=None, env=None, capture_output=False, text=False, **kw):
        state["calls"].append({"cmd": list(cmd), "env": env})
        if cmd[0] == "git":
            return subprocess.CompletedProcess(cmd, 0, stdout=HEAD + "\n", stderr="")
        out, inp = _arg(cmd, "--output-dir"), _arg(cmd, "--input-dir")
        trace = Path(env["TRACE_OUT"])
        trace.mkdir(parents=True, exist_ok=True)
        if state["tamper_out"]:
            (out / "twins" / "a.json").write_text('{"old": false, "same": 1, "new": 2}', encoding="utf-8")
            (out / "twins" / "b.json").write_text('{"b": 1}', encoding="utf-8")
            (out / "notes.json").write_text("still not json!", encoding="utf-8")
            (out / "list.json").write_text("[2]", encoding="utf-8")
            (out / "recursive_build.txt").write_text("r", encoding="utf-8")
            (out / "gone.txt").unlink()
            (out / "mod.txt").write_text("v2", encoding="utf-8")
        if state["mutate_input"]:
            (inp / "a.pptx").write_bytes(b"tampered")
        if state["stray"]:
            (repo / "stray.txt").write_text("stray", encoding="utf-8")
        procs = state["procs"]
        if procs is None:
            parent_argv = [sys.executable, str(repo / "scripts" / "run_processing.py"), "--output-dir", str(out)]
            child_argv = ["python", str(repo / "scripts" / "child.py"), "twins"]
            rec_argv = ["python", "/elsewhere/RecursiveBuild.py"]
            procs = [
                _proc(200, 100, child_argv, 2.0,
                      functions=[_fn("scripts/child.py", "analyse", 1, 2, 1),
                                 _fn("scripts/child.py", "write", 3, 1, 2),
                                 _fn("scripts/missing.py", "ghost", 9, 1, 3)]),
                _proc(100, 1, parent_argv, 1.0,
                      functions=[_fn("scripts/run_processing.py", "main", 1, 1, 1)]),
                _proc(300, 100, rec_argv, 3.0),
            ]
        for p in procs:
            (trace / ("proc-%d.json" % p["pid"])).write_text(json.dumps(p), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, state["rc"], stdout="processed 2 files\n", stderr=state["stderr"])

    monkeypatch.setattr(h.subprocess, "run", run)
    return state


def _main(tmp_path, repo, *extra):
    rep = tmp_path / "rep"
    rc = h.main(["--repo-root", str(repo), "--report-dir", str(rep), "--python", "py-test", *extra])
    return rc, json.loads((rep / "receipt.json").read_text(encoding="utf-8")), rep


# ------------------------------------------------------------------ pure helpers
def test_digests_match_git_blob_identity():
    sha, oid = h.digests(b"hello\n")
    assert len(sha) == 64
    assert oid == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_snapshot_skips_excluded_symlinked_and_skip_dirs(tmp_path):
    root = tmp_path / "root"
    (root / "keep").mkdir(parents=True)
    (root / "keep" / "f.txt").write_text("x", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref", encoding="utf-8")
    (root / "excluded").mkdir()
    (root / "excluded" / "e.txt").write_text("e", encoding="utf-8")
    try:
        os.symlink(root / "keep" / "f.txt", root / "link.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this host")
    snap = h.snapshot(root, [root / "excluded"])
    assert set(snap) == {"keep/f.txt"}
    assert snap["keep/f.txt"]["bytes"] == 1


def test_diff_classifies_all_four_kinds():
    a = {"sha256": "1", "oid": "o", "bytes": 1}
    b = {"sha256": "2", "oid": "p", "bytes": 2}
    d = h.diff({"same": a, "mod": a, "del": a}, {"same": a, "mod": b, "new": b})
    assert [x["path"] for x in d["created"]] == ["new"]
    assert [x["path"] for x in d["deleted"]] == ["del"]
    assert d["modified"][0]["before"] == a and d["modified"][0]["sha256"] == "2"
    assert [x["path"] for x in d["unchanged"]] == ["same"]


def test_json_change_variants(tmp_path):
    before = tmp_path / "b.json"
    before.write_text('{"a": 1, "b": 2}', encoding="utf-8")
    assert h.json_change(before, b'{"a": 1, "b": 3, "c": 0}') == ["b", "c"]
    assert h.json_change(tmp_path / "missing.json", b"{}") is None
    assert h.json_change(before, b"not json") is None
    assert h.json_change(before, b"[1, 2]") is None


def test_consumers_skips_dependency_dirs(repo):
    assert h.consumers(repo) == ["app/app/api/twins/route.ts"]


def test_id_and_proc_label():
    assert h._id("a-b/c.d") == "a_b_c_d"
    assert h._id("x" * 60) == "x" * 40
    assert h.proc_label({"argv": ["/usr/bin/python", "/r/scripts/run.py", "--x"]}) == "run.py"
    assert h.proc_label({"argv": ["/usr/bin/python3", "-c", "pass"]}) == "python3"


def test_asset_escapes_markup():
    out = h.asset('<x "y">', "s&", "o", ["T1", "T2"])
    assert "&lt;x &quot;y&quot;&gt;" in out
    assert 'data-tags="T1 T2"' in out
    assert h.E(None) == ""


# ------------------------------------------------------------------ run + main (faked process)
def test_sandbox_main_receipt_and_reports(tmp_path, repo, fake_run, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/existing/pp")
    committed = repo / "app" / "public" / "outputs"
    before = h.snapshot(committed)
    work = tmp_path / "rep" / "work"
    (work / "outputs").mkdir(parents=True)
    (work / "outputs" / "leftover.txt").write_text("old sandbox", encoding="utf-8")
    rc, r, rep = _main(tmp_path, repo, "--excel-input", "book.xlsx")
    assert rc == 0 and r["result"] == "PASS" and r["mode"] == "SANDBOX"
    assert h.snapshot(committed) == before
    pipe = fake_run["calls"][0]
    assert pipe["cmd"][-2:] == ["--excel-input", "book.xlsx"]
    assert pipe["env"]["PYTHONPATH"].split(os.pathsep) == [str(h.TRACER), "/existing/pp"]
    assert pipe["env"]["TRACE_ROOT"] == str(repo.resolve())
    assert r["command"][0] == "py-test"
    assert r["repo_head"] == HEAD
    assert [p["pid"] for p in r["processes"]] == [100, 200, 300]
    child = r["processes"][1]
    assert child["argv"][1] == os.path.join("scripts", "child.py")
    assert child["calls_total"] == 4 and child["functions_called"] == 3
    fns = {f["qualname"]: f for f in child["functions"]}
    assert len(fns["analyse"]["file_oid"]) == 40
    assert fns["analyse"]["file_oid"] == fns["write"]["file_oid"]
    assert fns["ghost"]["file_oid"] is None and fns["ghost"]["id"] == "?:9"
    o = r["outputs"]
    assert o["counts"] == {"created": 2, "modified": 4, "deleted": 1, "unchanged": 1}
    mod = {m["path"]: m for m in o["modified"]}
    assert mod["twins/a.json"]["json_keys_changed"] == ["new", "old"]
    assert mod["notes.json"]["json_keys_changed"] is None
    assert mod["list.json"]["json_keys_changed"] is None
    assert "json_keys_changed" not in mod["mod.txt"]
    assert "leftover.txt" not in {x["path"] for x in o["created"]}
    assert r["input"]["immutable"] is True and r["input"]["changed"] is None
    assert r["stray_repo_writes"] == {"created": [], "modified": [], "deleted": []}
    assert r["consumers"] == ["app/app/api/twins/route.ts"]
    assert r["errors"]["uncaught"] == [] and r["merge_authorized"] is False
    for name in ("report.html", "sipoc.mmd", "dag.mmd", "spine.mmd", "DIAGRAMS.md"):
        assert (rep / name).stat().st_size > 0
    dag = (rep / "dag.mmd").read_text(encoding="utf-8")
    assert "P100 -->|spawns| P200" in dag and "IN --> P100" in dag
    assert "P200 --> O_twins" in dag
    assert "P300 --> O_recursive_build_txt" in dag
    assert "P200 --> O_gone_txt" in dag
    spine = (rep / "spine.mmd").read_text(encoding="utf-8")
    assert "B2" in spine and "5 RECEIPT PASS" in spine
    page = (rep / "report.html").read_text(encoding="utf-8")
    assert "No uncaught exceptions" in page
    assert "keys: new, old" in page
    assert "Compared with the committed outputs" in page


def test_sandbox_without_committed_outputs_and_failure(tmp_path, repo, fake_run, monkeypatch):
    import shutil
    shutil.rmtree(repo / "app" / "public" / "outputs")
    monkeypatch.delenv("PYTHONPATH", raising=False)
    fake_run["tamper_out"] = False
    fake_run["mutate_input"] = True
    fake_run["stray"] = True
    fake_run["rc"] = 0
    fake_run["stderr"] = "INFO fine\nWARNING disk\nTraceback boom\n"
    fake_run["procs"] = [_proc(7, 1, ["python", "-c", "x"], 1.0,
                               uncaught=[{"type": "RuntimeError", "message": "deliberate <fail>",
                                          "traceback": "Traceback\n  child"}])]
    rc, r, rep = _main(tmp_path, repo)
    assert rc == 1 and r["result"] == "FAIL"
    assert fake_run["calls"][0]["env"]["PYTHONPATH"] == str(h.TRACER)
    assert r["errors"]["uncaught"][0]["process"] == "python -c"
    assert r["errors"]["stderr_flagged"] == ["WARNING disk", "Traceback boom"]
    assert r["input"]["immutable"] is False
    assert [x["path"] for x in r["input"]["changed"]["modified"]] == ["a.pptx"]
    assert [x["path"] for x in r["stray_repo_writes"]["created"]] == ["stray.txt"]
    assert r["outputs"]["counts"]["created"] == 0
    page = (rep / "report.html").read_text(encoding="utf-8")
    assert "deliberate &lt;fail&gt;" in page and 'class="warn"' in page
    assert "no output changes" in page


def test_nonzero_exit_fails_even_without_uncaught(tmp_path, repo, fake_run):
    fake_run["rc"] = 3
    fake_run["procs"] = []
    rc, r, rep = _main(tmp_path, repo, "--input-dir", str(repo / "app" / "public" / "master_input"))
    assert rc == 1 and r["exit_code"] == 3 and r["processes"] == []
    dag = (rep / "dag.mmd").read_text(encoding="utf-8")
    assert "PNone --> O_twins" in dag


def test_in_place_mode_writes_committed_outputs(tmp_path, repo, fake_run):
    rc, r, rep = _main(tmp_path, repo, "--in-place", "--work-dir", str(tmp_path / "w"))
    assert r["mode"] == "IN_PLACE"
    assert (repo / "app" / "public" / "outputs" / "twins" / "b.json").exists()
    mod = {m["path"]: m for m in r["outputs"]["modified"]}
    assert mod["twins/a.json"]["json_keys_changed"] is None
    assert r["outputs"]["dir"] == "app/public/outputs"
    assert "Written in place" in (rep / "report.html").read_text(encoding="utf-8")


def test_diagrams_and_report_on_handcrafted_record():
    rec = {
        "input": {"assets": [{"path": "a.pptx", "sha256": "s", "oid": "o", "bytes": 1},
                             {"path": "noext", "sha256": "s", "oid": "o", "bytes": 2}],
                  "files": 2, "dir": "in", "immutable": False},
        "outputs": {"created": [{"path": "top", "sha256": "s", "oid": "o", "bytes": 3}],
                    "modified": [], "deleted": [],
                    "counts": {"created": 1, "modified": 0, "deleted": 0, "unchanged": 0}},
        "processes": [{"pid": 1, "ppid": 2, "argv": ["p", "a.py"], "seconds": 1, "functions_called": 0,
                       "calls_total": 0, "uncaught": 0, "functions": []}],
        "consumers": ["app/app/api/x.ts"], "timings_s": {"snapshot_before": 0, "pipeline": 1, "snapshot_after": 0},
        "exit_code": 0, "stray_repo_writes": {"created": [{"path": "s"}]}, "result": "PASS",
        "errors": {"uncaught": [], "stderr_flagged": []}, "mode": "SANDBOX", "repo_head": "", "started_utc": "t",
        "python": "3", "stdout_tail": "",
    }
    dia = h.diagrams(rec)
    assert "((none), .pptx)" in dia["sipoc.mmd"] and "api/x.ts" in dia["sipoc.mmd"]
    assert "P1 --> O_top" in dia["dag.mmd"]
    assert "stray writes 1" in dia["spine.mmd"]
    page = h.report(rec, dia)
    assert "CHECK" in page and "FILE" in page
