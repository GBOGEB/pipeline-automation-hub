#!/usr/bin/env python3
"""Master_Input pipeline runtime harness (#529 G09): run it, watch it, prove what it did.

Runs scripts/run_processing.py (the Master_Input document pipeline) exactly as a user would, and
records the ACTUAL runtime behaviour:
  * errors        exit code, uncaught exceptions with tracebacks (every Python process),
                  stderr error/warning lines
  * processes     every Python process spawned (argv, parent, wall time)  -> process DAG
  * functions     every repo function called, per process, with call counts and first-call order
                  (python asset names: file:qualname@line, file git O-ID)
  * outputs       files created / modified / deleted / unchanged vs the committed outputs,
                  each with SHA-256 and git object id (O-ID)
  * immutability  input files hashed before/after (must be identical: read + analyse, no change)
  * stray writes  any change in the repository outside the output directory
and writes receipt.json, SIPOC / DAG / SPINE Mermaid diagrams and a self-contained report.html with
name / SHA-256 / O-ID / tag toggle views.

Default is SANDBOXED: committed outputs are copied to a work dir and the pipeline writes there, so the
repository is not modified; --in-place writes into app/public/outputs like a real refresh.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TRACER = HERE / "tracer"
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".next", ".venv", "venv"}
SCHEMA = "pipeline.master_input.runtime_receipt.v1"


def digests(data: bytes):
    return hashlib.sha256(data).hexdigest(), hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def snapshot(root: Path, exclude: list[Path] = ()):
    root = root.resolve()
    ex = [e.resolve() for e in exclude]
    snap = {}
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        dirnames[:] = [n for n in dirnames if n not in SKIP_DIRS and not any((d / n).resolve() == e for e in ex)]
        for n in filenames:
            p = d / n
            if p.is_symlink() or not p.is_file():
                continue
            data = p.read_bytes()
            sha, oid = digests(data)
            snap[p.relative_to(root).as_posix()] = {"sha256": sha, "oid": oid, "bytes": len(data)}
    return snap


def diff(before: dict, after: dict):
    out = {"created": [], "modified": [], "deleted": [], "unchanged": []}
    for k in sorted(set(before) | set(after)):
        b, a = before.get(k), after.get(k)
        if b is None:
            out["created"].append({"path": k, **a})
        elif a is None:
            out["deleted"].append({"path": k, **b})
        elif a["sha256"] != b["sha256"]:
            out["modified"].append({"path": k, "before": b, "after": a, **a})
        else:
            out["unchanged"].append({"path": k, **a})
    return out


def json_change(before_path: Path, after_bytes: bytes):
    """Which top-level keys changed in a JSON file (shows e.g. timestamp-only refreshes)."""
    try:
        b = json.loads(before_path.read_bytes()) if before_path.exists() else None
        a = json.loads(after_bytes)
    except (ValueError, OSError):
        return None
    if not (isinstance(a, dict) and isinstance(b, dict)):
        return None
    keys = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    return keys[:12]


def consumers(repo: Path):
    """App routes/components that read pipeline outputs = SIPOC customers."""
    out = []
    for p in sorted((repo / "app").rglob("*.ts*")):
        if any(s in p.parts for s in SKIP_DIRS):
            continue
        t = p.read_text(errors="ignore")
        if re.search(r"outputs|master_input|digital_twins|processing_summary", t):
            out.append(p.relative_to(repo).as_posix())
    return out


def run(repo: Path, input_dir: Path, work: Path, in_place: bool, extra: list[str], python: str):
    started = datetime.now(timezone.utc)
    committed_out = repo / "app/public/outputs"
    out_dir = committed_out if in_place else work / "outputs"
    if not in_place:
        if out_dir.exists():
            shutil.rmtree(out_dir)
        shutil.copytree(committed_out, out_dir) if committed_out.exists() else out_dir.mkdir(parents=True)
    trace_dir = work / "trace"
    shutil.rmtree(trace_dir, ignore_errors=True)
    t0 = time.time()
    inp_before = snapshot(input_dir)
    out_before = snapshot(out_dir)
    repo_before = snapshot(repo, [work, committed_out] if in_place else [work])
    snap_s = round(time.time() - t0, 2)
    env = dict(os.environ, TRACE_ROOT=str(repo), TRACE_OUT=str(trace_dir),
               PYTHONPATH=os.pathsep.join([str(TRACER)] + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])))
    cmd = [python, str(repo / "scripts/run_processing.py"), "--input-dir", str(input_dir), "--output-dir", str(out_dir), *extra]
    t1 = time.time()
    p = subprocess.run(cmd, cwd=repo, env=env, capture_output=True, text=True)
    run_s = round(time.time() - t1, 2)
    t2 = time.time()
    inp_after = snapshot(input_dir)
    out_after = snapshot(out_dir)
    repo_after = snapshot(repo, [work, committed_out] if in_place else [work])
    after_s = round(time.time() - t2, 2)
    procs = sorted((json.loads(f.read_text()) for f in trace_dir.glob("proc-*.json")), key=lambda r: r["started"])
    out_diff = diff(out_before, out_after)
    for m in out_diff["modified"]:
        if m["path"].endswith(".json"):
            m["json_keys_changed"] = json_change(committed_out / m["path"] if not in_place else Path("/nonexistent"),
                                                 (out_dir / m["path"]).read_bytes())
    stray = diff(repo_before, repo_after)
    stray = {k: v for k, v in stray.items() if k != "unchanged"}
    oid_cache = {}

    def src_oid(rel):
        if rel not in oid_cache:
            f = repo / rel
            oid_cache[rel] = digests(f.read_bytes()) if f.is_file() else (None, None)
        return oid_cache[rel]
    for pr in procs:
        for fn in pr["functions"]:
            fn["file_sha256"], fn["file_oid"] = src_oid(fn["file"])
            fn["id"] = f"{(fn['file_oid'] or '?')[:12]}:{fn['line']}"
    err_lines = [l for l in (p.stderr or "").splitlines() if re.search(r"error|exception|traceback|warn|fail", l, re.I)]
    rec = {
        "schema": SCHEMA, "started_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo_head": subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
        "mode": "IN_PLACE" if in_place else "SANDBOX", "command": [Path(c).name if i == 0 else c for i, c in enumerate(cmd)],
        "python": sys.version.split()[0], "timings_s": {"snapshot_before": snap_s, "pipeline": run_s, "snapshot_after": after_s},
        "exit_code": p.returncode,
        "result": "PASS" if p.returncode == 0 and not any(pr["uncaught"] for pr in procs) else "FAIL",
        "errors": {"uncaught": [dict(e, pid=pr["pid"], process=" ".join(Path(a).name for a in pr["argv"][:2]))
                                for pr in procs for e in pr["uncaught"]],
                   "stderr_flagged": err_lines[-40:], "stderr_tail": (p.stderr or "")[-4000:]},
        "stdout_tail": (p.stdout or "")[-6000:],
        "input": {"dir": os.path.relpath(input_dir, repo), "files": len(inp_before),
                  "immutable": inp_before == inp_after, "changed": diff(inp_before, inp_after) if inp_before != inp_after else None,
                  "assets": [{"path": k, **v} for k, v in sorted(inp_before.items())]},
        "outputs": {"dir": "app/public/outputs" + ("" if in_place else " (sandbox copy)"),
                    "counts": {k: len(v) for k, v in out_diff.items()}, **{k: v for k, v in out_diff.items() if k != "unchanged"},
                    "unchanged_sample": out_diff["unchanged"][:20]},
        "stray_repo_writes": stray,
        "processes": [{"pid": pr["pid"], "ppid": pr["ppid"], "argv": [os.path.relpath(a, repo) if a.startswith(str(repo)) else a for a in pr["argv"]],
                       "seconds": pr["seconds"], "uncaught": len(pr["uncaught"]), "functions_called": len(pr["functions"]),
                       "calls_total": sum(f["calls"] for f in pr["functions"]), "functions": pr["functions"]} for pr in procs],
        "consumers": consumers(repo), "merge_authorized": False,
    }
    return rec


# ------------------------------------------------------------------ diagrams
def _id(s):
    return re.sub(r"[^A-Za-z0-9_]", "_", s)[:40]


def proc_label(pr):
    a = [x for x in pr["argv"] if x.endswith(".py")]
    return Path(a[0]).name if a else Path(pr["argv"][0]).name


def diagrams(rec):
    inputs = rec["input"]["assets"]
    exts = sorted({Path(a["path"]).suffix.lower() or "(none)" for a in inputs})
    outs = rec["outputs"]
    groups = {}
    for kind in ("created", "modified", "deleted"):
        for f in outs[kind]:
            g = f["path"].split("/")[0] if "/" in f["path"] else f["path"]
            groups.setdefault(g, {"created": 0, "modified": 0, "deleted": 0})[kind] += 1
    procs = rec["processes"]
    sipoc = ["flowchart LR",
             '  S["SUPPLIERS<br/>owner decks in Master_Input<br/>' + f'{rec["input"]["files"]} files ({", ".join(exts)})"]',
             '  I["INPUTS<br/>' + rec["input"]["dir"] + '<br/>immutable: ' + str(rec["input"]["immutable"]) + '"]',
             '  P["PROCESS<br/>' + "<br/>".join(proc_label(p) for p in procs) + '"]',
             '  O["OUTPUTS<br/>created ' + str(outs["counts"]["created"]) + " · modified " + str(outs["counts"]["modified"]) +
             " · deleted " + str(outs["counts"]["deleted"]) + " · unchanged " + str(outs["counts"]["unchanged"]) + '"]',
             '  C["CUSTOMERS<br/>' + "<br/>".join(c.replace("app/app/api/", "api/") for c in rec["consumers"][:8]) + '"]',
             "  S --> I --> P --> O --> C"]
    dag = ["flowchart TD", f'  IN[("Master_Input<br/>{rec["input"]["files"]} inputs")]']
    pids = {p["pid"] for p in procs}
    for p in procs:
        dag.append(f'  P{p["pid"]}["{proc_label(p)}<br/>{p["functions_called"]} functions · {p["calls_total"]} calls · {p["seconds"]} s"]')
    for p in procs:
        if p["ppid"] in pids:
            dag.append(f'  P{p["ppid"]} -->|spawns| P{p["pid"]}')
        else:
            dag.append(f'  IN --> P{p["pid"]}')
    leaf = [p for p in procs if not any(q["ppid"] == p["pid"] for q in procs)] or procs
    for g, c in sorted(groups.items()):
        dag.append(f'  O_{_id(g)}[/"{g}<br/>+{c["created"]} ~{c["modified"]} -{c["deleted"]}"/]')
        src = leaf[-1]["pid"] if leaf else None
        owner = next((p for p in procs if g in " ".join(p["argv"]) or ("recursive" in g and "Recursive" in proc_label(p))), None)
        dag.append(f'  P{(owner or leaf[0])["pid"] if procs else src} --> O_{_id(g)}')
    t = rec["timings_s"]
    spine = ["flowchart LR",
             f'  A["1 SNAPSHOT before<br/>{t["snapshot_before"]} s"] --> B["2 RUN run_processing.py<br/>{t["pipeline"]} s · exit {rec["exit_code"]}"]']
    prev = "B"
    for i, p in enumerate(procs[1:], 1):
        spine.append(f'  {prev} --> B{i}["2.{i} {proc_label(p)}<br/>{p["seconds"]} s"]')
        prev = f"B{i}"
    spine += [f'  {prev} --> C["3 SNAPSHOT after<br/>{t["snapshot_after"]} s"]',
              f'  C --> D["4 DIFF<br/>inputs immutable {rec["input"]["immutable"]}<br/>stray writes {sum(len(v) for v in rec["stray_repo_writes"].values())}"]',
              f'  D --> E["5 RECEIPT {rec["result"]}"]']
    return {"sipoc.mmd": "\n".join(sipoc) + "\n", "dag.mmd": "\n".join(dag) + "\n", "spine.mmd": "\n".join(spine) + "\n"}


# ------------------------------------------------------------------ report
E = lambda s: html.escape("" if s is None else str(s), quote=True)


def asset(name, sha, oid, tags):
    return (f'<span class="as" data-name="{E(name)}" data-sha="{E(sha)}" data-oid="{E(oid)}" data-tags="{E(" ".join(tags))}" '
            f'title="SHA-256 {E(sha)}&#10;O-ID {E(oid)}">{E(name)}</span>')


def report(rec, dia):
    o = rec["outputs"]
    rows_out = []
    for kind in ("created", "modified", "deleted"):
        for f in o[kind]:
            tags = ["OUTPUT", kind.upper(), Path(f["path"]).suffix.lstrip(".").upper() or "FILE"]
            extra = (" keys: " + ", ".join(f["json_keys_changed"])) if f.get("json_keys_changed") else ""
            rows_out.append(f'<tr data-k="{kind}"><td>{E(kind)}</td><td>{asset(f["path"], f["sha256"], f["oid"], tags)}</td>'
                            f'<td>{f["bytes"]:,}</td><td>{E(extra)}</td></tr>')
    rows_in = "".join(f'<tr><td>{asset(a["path"], a["sha256"], a["oid"], ["INPUT", Path(a["path"]).suffix.lstrip(".").upper(), "UNCHANGED" if rec["input"]["immutable"] else "CHECK"])}</td><td>{a["bytes"]:,}</td></tr>'
                      for a in rec["input"]["assets"])
    rows_fn = []
    for p in rec["processes"]:
        for f in p["functions"]:
            name = f'{f["file"]}:{f["qualname"]}'
            rows_fn.append(f'<tr><td>{E(proc_label(p))}</td><td>{asset(name, f["file_sha256"] or "", f["id"], ["FUNCTION", Path(f["file"]).stem, "calls=" + str(f["calls"])])}</td>'
                           f'<td>{f["line"]}</td><td>{f["calls"]}</td><td>{f["order"]}</td></tr>')
    procs = "".join(f'<tr><td>{p["pid"]}</td><td>{p["ppid"]}</td><td><code>{E(" ".join(p["argv"]))}</code></td><td>{p["seconds"]}</td>'
                    f'<td>{p["functions_called"]}</td><td>{p["calls_total"]:,}</td><td>{p["uncaught"]}</td></tr>' for p in rec["processes"])
    errs = rec["errors"]
    err_html = ("".join(f'<pre class="err">{E(e["process"])} pid {e["pid"]}: {E(e["type"])}: {E(e["message"])}\n{E(e["traceback"])}</pre>' for e in errs["uncaught"])
                + (f'<pre class="warn">{E(chr(10).join(errs["stderr_flagged"]))}</pre>' if errs["stderr_flagged"] else "")) or "<p>No uncaught exceptions; no flagged stderr lines.</p>"
    stray = rec["stray_repo_writes"]
    stray_n = sum(len(v) for v in stray.values())
    kpi = [("Result", rec["result"]), ("Exit code", rec["exit_code"]), ("Processes", len(rec["processes"])),
           ("Functions called", sum(p["functions_called"] for p in rec["processes"])),
           ("Inputs (immutable)", f'{rec["input"]["files"]} ({rec["input"]["immutable"]})'),
           ("Outputs created / modified / deleted", f'{o["counts"]["created"]} / {o["counts"]["modified"]} / {o["counts"]["deleted"]}'),
           ("Stray repo writes", stray_n), ("Pipeline time (s)", rec["timings_s"]["pipeline"])]
    mm = "".join(f'<section><h3>{E(t)}</h3><pre class="mermaid">{E(dia[f])}</pre></section>'
                 for t, f in (("SIPOC", "sipoc.mmd"), ("Process / output DAG", "dag.mmd"), ("Run SPINE", "spine.mmd")))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Master_Input pipeline runtime</title><style>
:root{{color-scheme:dark;--bg:#061713;--panel:#102b23;--hi:#183a30;--stroke:#345849;--text:#eefaf2;--muted:#acc7b8;--green:#7be0ad;--amber:#ffcc83;--red:#ff9999}}
body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 Inter,system-ui,sans-serif}}main{{max-width:1400px;margin:auto;padding:22px}}
h1{{font-size:28px;margin:6px 0}}h2{{margin-top:30px}}.muted{{color:var(--muted)}}a{{color:var(--green)}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}}.kpi{{background:var(--panel);border:1px solid var(--stroke);border-radius:12px;padding:12px}}.kpi b{{display:block;font-size:22px}}
.bar{{position:sticky;top:0;background:var(--bg);padding:10px 0;display:flex;gap:14px;flex-wrap:wrap;align-items:center;border-bottom:1px solid var(--stroke);z-index:2}}
.bar label{{white-space:nowrap}}input[type=search]{{background:var(--panel);color:var(--text);border:1px solid var(--stroke);border-radius:8px;padding:6px 9px;min-width:220px}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid var(--stroke);padding:6px 8px;text-align:left;vertical-align:top;font-size:12.5px}}th{{background:var(--hi);position:sticky;top:48px}}
.wrap{{overflow-x:auto;max-height:520px;border:1px solid var(--stroke);border-radius:10px}}.as{{font-family:ui-monospace,monospace;overflow-wrap:anywhere}}
.tag{{display:inline-block;font-size:10px;border:1px solid var(--stroke);border-radius:99px;padding:0 6px;margin:1px;color:var(--muted)}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--panel);padding:10px;border-radius:8px}}.err{{border-left:4px solid var(--red)}}.warn{{border-left:4px solid var(--amber)}}
section{{background:var(--panel);border:1px solid var(--stroke);border-radius:12px;padding:8px 14px;margin:10px 0}}.mermaid{{background:#fff;color:#111}}
</style></head><body><main>
<p class="muted">#529 G09 · Master_Input pipeline runtime harness · {E(rec["mode"])} · repo {E(rec["repo_head"][:12])} · {E(rec["started_utc"])} · Python {E(rec["python"])}</p>
<h1>What the Master_Input pipeline actually did</h1>
<div class="kpis">{"".join(f'<div class="kpi"><b>{E(v)}</b>{E(k)}</div>' for k, v in kpi)}</div>
<div class="bar" role="toolbar" aria-label="Asset label view"><strong>Label view:</strong>
<label><input type="radio" name="lv" value="name" checked> name (python / file)</label>
<label><input type="radio" name="lv" value="sha"> SHA-256</label><label><input type="radio" name="lv" value="oid"> O-ID (git object id)</label>
<label><input type="radio" name="lv" value="tags"> tags</label><label><input type="checkbox" id="short" checked> short ids</label>
<input type="search" id="q" placeholder="filter assets, functions, ids…" aria-label="Filter"></div>
<h2>Errors and failing execution</h2>{err_html}
<h2>Diagrams (generated from this run)</h2>{mm}
<h2>Processes ({len(rec["processes"])})</h2><div class="wrap"><table><tr><th>pid</th><th>parent</th><th>argv</th><th>s</th><th>functions</th><th>calls</th><th>uncaught</th></tr>{procs}</table></div>
<h2>Functions called ({len(rows_fn)})</h2><p class="muted">Repo functions only (stdlib/site-packages excluded). O-ID = git object id of the source file + first line.</p>
<div class="wrap"><table class="f"><tr><th>process</th><th>asset</th><th>line</th><th>calls</th><th>order</th></tr>{"".join(rows_fn)}</table></div>
<h2>Outputs: what changed</h2><p class="muted">{"Compared with the committed outputs (sandbox copy)" if rec["mode"] == "SANDBOX" else "Written in place"}. Unchanged: {o["counts"]["unchanged"]}.</p>
<div class="wrap"><table class="f"><tr><th>change</th><th>asset</th><th>bytes</th><th>detail</th></tr>{"".join(rows_out) or "<tr><td colspan=4>no output changes</td></tr>"}</table></div>
<h2>Inputs (read and analysed, must not change): immutable = {E(rec["input"]["immutable"])}</h2>
<div class="wrap"><table class="f"><tr><th>asset</th><th>bytes</th></tr>{rows_in}</table></div>
<h2>Stray repository writes: {stray_n}</h2><pre>{E(json.dumps({k: [x["path"] for x in v][:50] for k, v in stray.items()}, indent=1))}</pre>
<h2>stdout (tail)</h2><pre>{E(rec["stdout_tail"])}</pre>
</main>
<script>(function(){{var as=[].slice.call(document.querySelectorAll('.as'));
function render(){{var v=document.querySelector('input[name=lv]:checked').value,sh=document.getElementById('short').checked;
as.forEach(function(e){{var t=e.dataset[v]||'';if(v==='tags'){{e.innerHTML=t.split(' ').map(function(x){{return '<span class="tag">'+x.replace(/[<>&"]/g,'')+'</span>'}}).join('')+' '+e.dataset.name.replace(/[<>&"]/g,'');return}}
if((v==='sha'||v==='oid')&&sh)t=t.slice(0,v==='oid'?17:16);e.textContent=t||'—'}})}}
document.querySelectorAll('input[name=lv],#short').forEach(function(i){{i.addEventListener('change',render)}});
document.getElementById('q').addEventListener('input',function(){{var q=this.value.toLowerCase();document.querySelectorAll('table.f tr').forEach(function(tr,i){{if(!tr.querySelector('td'))return;
var e=tr.querySelector('.as'),s=tr.textContent+(e?' '+e.dataset.name+' '+e.dataset.sha+' '+e.dataset.oid+' '+e.dataset.tags:'');tr.hidden=q&&s.toLowerCase().indexOf(q)<0}})}});render();}})();</script>
<script type="module">try{{const m=await import('https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs');m.default.initialize({{startOnLoad:true,theme:'default'}});await m.default.run();}}catch(e){{}}</script>
</body></html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, default=REPO)
    ap.add_argument("--input-dir", type=Path)
    ap.add_argument("--work-dir", type=Path)
    ap.add_argument("--report-dir", type=Path, required=True)
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument("--excel-input")
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args(argv)
    repo = a.repo_root.resolve()
    inp = (a.input_dir or repo / "app/public/master_input").resolve()
    work = (a.work_dir or a.report_dir / "work").resolve()
    work.mkdir(parents=True, exist_ok=True)
    extra = ["--excel-input", a.excel_input] if a.excel_input else []
    rec = run(repo, inp, work, a.in_place, extra, a.python)
    dia = diagrams(rec)
    a.report_dir.mkdir(parents=True, exist_ok=True)
    (a.report_dir / "receipt.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for n, t in dia.items():
        (a.report_dir / n).write_text(t, encoding="utf-8")
    (a.report_dir / "DIAGRAMS.md").write_text("# Master_Input pipeline run: SIPOC, DAG, SPINE\n\n" + "".join(
        f"## {t}\n\n```mermaid\n{dia[f]}```\n\n" for t, f in (("SIPOC", "sipoc.mmd"), ("Process / output DAG", "dag.mmd"),
                                                         ("Run SPINE", "spine.mmd"))), encoding="utf-8")
    (a.report_dir / "report.html").write_text(report(rec, dia), encoding="utf-8")
    print(json.dumps({"result": rec["result"], "exit_code": rec["exit_code"], "processes": len(rec["processes"]),
                      "functions": sum(p["functions_called"] for p in rec["processes"]),
                      "outputs": rec["outputs"]["counts"], "inputs_immutable": rec["input"]["immutable"],
                      "stray_repo_writes": sum(len(v) for v in rec["stray_repo_writes"].values()),
                      "report": str(a.report_dir / "report.html")}))
    return 0 if rec["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
