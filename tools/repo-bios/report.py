#!/usr/bin/env python3
"""Source-bound inventory; delegates workflow/Kahn semantics to existing JADE owners."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "mission-control/jade_temple/devops"))
import development
import lifecycle
import workflows

LANGUAGES = {
    ".py": "Python", ".r": "R", ".R": "R", ".js": "JavaScript",
    ".mjs": "JavaScript", ".cjs": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".sh": "Shell",
    ".ps1": "PowerShell", ".c": "C", ".h": "C/C++ header",
    ".cpp": "C++", ".rs": "Rust", ".go": "Go", ".swift": "Swift",
    ".java": "Java", ".jl": "Julia", ".sql": "SQL",
    ".yaml": "YAML", ".yml": "YAML", ".json": "JSON",
    ".html": "HTML", ".css": "CSS", ".md": "Markdown",
}
GENERATED = {"node_modules", "vendor", "dist", "build", "generated", "outputs"}


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def objects(root, entries):
    """One batch read; reject missing/truncated objects instead of counting zero."""
    wanted = sorted({e["blob_oid"] for e in entries if e["kind"] == "blob"})
    if not wanted:
        return {}
    body = subprocess.run(
        ["git", "-C", str(root), "cat-file", "--batch"],
        input=("\n".join(wanted) + "\n").encode(), check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    found, offset = {}, 0
    for oid in wanted:
        end = body.index(b"\n", offset)
        header = body[offset:end].split()
        if len(header) != 3 or header[0].decode() != oid or header[1] != b"blob":
            raise ValueError("missing or unexpected Git object")
        size = int(header[2])
        start = end + 1
        if start + size >= len(body) or body[start + size:start + size + 1] != b"\n":
            raise ValueError("truncated Git object")
        found[oid] = body[start:start + size]
        offset = start + size + 1
    return found


def source_link(repo, sha, path):
    return f"https://github.com/{repo}/blob/{sha}/{quote(path, safe='/')}"


def snapshot(repo, root, selected=(), metric_paths=()):
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise ValueError("repository must be owner/name")
    root = Path(root).resolve()
    if Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve() != root:
        raise ValueError("repository path must be its worktree root")
    sha = git(root, "rev-parse", "HEAD^{commit}").decode().strip()
    tree = git(root, "rev-parse", f"{sha}^{{tree}}").decode().strip()
    entries = []
    for record in git(root, "ls-tree", "-rlz", sha).split(b"\0"):
        if not record:
            continue
        header, rawpath = record.split(b"\t", 1)
        mode, kind, oid, size = header.decode().split()
        entries.append(dict(path=rawpath.decode(), mode=mode, kind=kind,
                            blob_oid=oid, bytes=int(size) if size != "-" else None))
    # Read only the text populations used by this report, not binary assets.
    read = [e for e in entries if e["mode"] != "120000" and
            PurePosixPath(e["path"]).suffix in LANGUAGES]
    blobs = objects(root, read) if read else {}
    language = {name: {"files": 0, "physical_loc": 0} for name in ("Python", "R")}
    dirs, counts = Counter(), Counter()
    rows, decisions, aht, wfs = [], [], [], []
    for e in entries:
        path = PurePosixPath(e["path"])
        dirs[path.parts[0] if len(path.parts) > 1 else "[root]"] += 1
        if e["kind"] != "blob" or e["mode"] == "120000":
            counts["submodules" if e["kind"] != "blob" else "symlinks"] += 1
            continue
        counts["regular_files"] += 1
        is_test = any(p in {"tests", "test", "__tests__"} for p in path.parts) or path.name.startswith("test_") or path.stem.endswith("_test")
        is_generated = bool(set(path.parts) & GENERATED)
        counts["test_path_files"] += int(is_test)
        counts["generated_vendor_path_files"] += int(is_generated)
        lang = LANGUAGES.get(path.suffix)
        loc, text = None, None
        if lang:
            data = blobs[e["blob_oid"]]
            try:
                if b"\0" in data:
                    raise UnicodeError("binary")
                text = data.decode("utf-8-sig")
                loc = len(text.splitlines())
                rec = language.setdefault(lang, {"files": 0, "physical_loc": 0})
                rec["files"] += 1
                rec["physical_loc"] += loc
            except UnicodeError:
                counts["mapped_non_utf8_or_binary_files"] += 1
        else:
            counts["unmapped_files"] += 1
        row = dict(e, language=lang, physical_loc=loc, test_path_heuristic=is_test,
                   generated_vendor_path_heuristic=is_generated,
                   source_url=source_link(repo, sha, e["path"]))
        rows.append(row)
        if re.search(r"(^|[/_-])(adr|adrs)([/_.-]|$)|architecture[-_]decision|/DR_", e["path"], re.I):
            decisions.append(dict(row, decision_status="UNKNOWN_PATH_CANDIDATE"))
        if re.search(r"(^|[/_-])aht([/_.-]|$)", e["path"], re.I):
            aht.append(dict(row, check_result="UNKNOWN"))
        if path.parent.as_posix() == ".github/workflows" and path.suffix in {".yaml", ".yml"}:
            if text is None:
                wfs.append({"path": e["path"], "parse_error": "NOT_UTF8_TEXT", "jobs": []})
                continue
            wf = workflows.parse(text, path=e["path"], blob_oid=e["blob_oid"], repo=repo)
            jobs = wf["jobs"]
            try:
                layers = lifecycle.topo_layers([j["id"] for j in jobs],
                    [(up, j["id"], "FEEDFORWARD") for j in jobs for up in j["needs"]])
                graph_error = None
            except ValueError as exc:
                layers, graph_error = None, str(exc)
            wfs.append(dict(path=e["path"], blob_oid=e["blob_oid"], source_url=row["source_url"],
                parse_error=wf.get("parse_error"), graph_error=graph_error, layers=layers,
                triggers=wf.get("triggers", []), jobs=[dict(id=j["id"],
                    oid=j["oid"], definition_sha256=j.get("def_sha256"),
                    upstream=j["needs"], downstream=sorted(k["id"] for k in jobs if j["id"] in k["needs"]),
                    condition=j.get("if"), runtime_state="UNKNOWN",
                    structural_frontier=not j["needs"], parse_error=j.get("parse_error")) for j in jobs]))
    bypath = {r["path"]: r for r in rows}
    missing = sorted(set(selected) - bypath.keys())
    if missing:
        raise ValueError(f"selected pipeline entries missing at {sha}: {missing}")
    selected_rows = [bypath[p] for p in sorted(set(selected))]
    pipeline_loc = (sum(r["physical_loc"] for r in selected_rows)
                    if selected_rows and all(r["physical_loc"] is not None for r in selected_rows) else None)
    as_is_metrics = []
    for path in sorted(set(metric_paths)):
        if path not in bypath:
            raise ValueError(f"metric source missing at {sha}: {path}")
        row = bypath[path]
        data = git(root, "cat-file", "blob", row["blob_oid"])
        as_is_metrics.append(dict(path=path, source_url=row["source_url"],
            blob_oid=row["blob_oid"], sha256=hashlib.sha256(data).hexdigest(),
            qualification="AS_IS_COMMITTED_VALUES_NOT_FRESH_RUNTIME_VERIFICATION",
            document=json.loads(data)))
    return dict(repository=repo, observed_at=datetime.now(timezone.utc).isoformat(),
        source_sha=sha, tree_oid=tree, counts=dict(counts), tracked_entries=len(entries),
        tracked_blob_bytes=sum(e["bytes"] or 0 for e in entries),
        languages=language, wireframe=dict(sorted(dirs.items())), workflows=wfs,
        workflow_count=len(wfs), job_count=sum(len(w["jobs"]) for w in wfs),
        adr_candidates=decisions, aht_candidates=aht, as_is_metrics=as_is_metrics,
        selected_pipeline_entries=selected_rows,
        selected_pipeline_entry_loc=pipeline_loc,
        runtime_kpis={"state": "UNKNOWN", "reason": "No qualified native observation window imported",
                      "owners": ["actions_metrics.py", "rolling5.py", "everred/harvest.py"]})


def markdown(doc):
    lines = ["# Repository statistics and dependency report", "",
        "Exact-commit source inventory; sequential observations, not an atomic fleet snapshot.",
        "Physical LOC includes comments and blanks. Runtime KPIs/readiness UNKNOWN.", "",
        "| Repository | Commit | Entries | Bytes | Python LOC | R LOC | Workflows | Jobs | Pipeline entry LOC |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in doc["repositories"]:
        lines.append(f"| {r['repository']} | `{r['source_sha']}` | {r['tracked_entries']} | {r['tracked_blob_bytes']} | {r['languages']['Python']['physical_loc']} | {r['languages']['R']['physical_loc']} | {r['workflow_count']} | {r['job_count']} | {r['selected_pipeline_entry_loc'] if r['selected_pipeline_entry_loc'] is not None else 'UNKNOWN'} |")
    lines += ["", "Full wireframe, language counts, ADR/AHT source candidates and workflow dependencies are in report.json and index.html.", ""]
    return "\n".join(lines)


def webpage(doc):
    data = json.dumps(doc, sort_keys=True).replace("<", "\\u003c")
    page = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Repository BIOS report</title><style>body{font:16px system-ui;max-width:1200px;margin:auto;padding:24px;background:#101727;color:#e6edf6}a{color:#a8ceff}input{padding:12px;width:90%;max-width:600px}section,details{border:1px solid #53617b;padding:14px;margin:14px 0;border-radius:8px}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;min-width:640px}td,th{min-width:90px;text-align:left;padding:8px;border-bottom:1px solid #53617b;overflow-wrap:anywhere}.scroll{overflow-x:auto}code{overflow-wrap:anywhere}</style>
<h1>Repository BIOS report</h1><p>Source inventory at recorded commits. Runtime readiness, hosted parity and native KPI results are UNKNOWN. Local report; potentially private. No automatic network requests.</p>
<label for="search">Filter repositories</label><br><input id="search" type="search" placeholder="Repository name"><main id="report"></main>
<script type="application/json" id="data">''' + data + r'''</script><script>
const data=JSON.parse(document.getElementById('data').textContent),main=document.getElementById('report');
function el(tag,text,parent){let n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(parent)parent.append(n);return n}
function table(headers,rows,parent){let wrap=el('div',undefined,parent);wrap.className='scroll';let t=el('table',undefined,wrap),h=el('tr',undefined,el('thead',undefined,t));headers.forEach(x=>el('th',x,h));let b=el('tbody',undefined,t);rows.forEach(row=>{let tr=el('tr',undefined,b);row.forEach(x=>el('td',String(x??'UNKNOWN'),tr))})}
function detail(title,parent){let d=el('details',undefined,parent);el('summary',title,d);return d}
function link(row,parent){let a=el('a',row.path,parent);a.href=row.source_url;a.rel='noreferrer';el('pre','blob OID: '+row.blob_oid,parent)}
function render(){main.replaceChildren();for(const r of data.repositories){if(!r.repository.toLowerCase().includes(document.getElementById('search').value.toLowerCase()))continue;let s=el('section',undefined,main);el('h2',r.repository,s);el('pre','Commit: '+r.source_sha+'\nTree OID: '+r.tree_oid+'\nObserved: '+r.observed_at,s);
table(['Entries','Bytes','Workflow files','Jobs','Selected pipeline entry LOC'],[[r.tracked_entries,r.tracked_blob_bytes,r.workflow_count,r.job_count,r.selected_pipeline_entry_loc]],s);
let l=detail('Languages: files and physical LOC',s);table(['Language','Files','Physical LOC'],Object.entries(r.languages).sort().map(([k,v])=>[k,v.files,v.physical_loc]),l);
let w=detail('Repository wireframe',s);table(['Directory','Tracked entries'],Object.entries(r.wireframe),w);
let f=detail('Workflow DAG / Kahn waves / upstream and downstream',s);for(const wf of r.workflows){let d=detail(wf.path,f);if(wf.source_url)link(wf,d);el('pre','Graph/parse: '+(wf.parse_error||wf.graph_error||'STRUCTURALLY_VALID')+'\nKahn waves: '+JSON.stringify(wf.layers)+'\nRuntime readiness: UNKNOWN',d);table(['Job','Upstream needs','Downstream','Source definition SHA256 / OID'],wf.jobs.map(j=>[j.id,j.upstream.join(', ')||'none declared',j.downstream.join(', ')||'none declared',(j.definition_sha256||'UNKNOWN')+' / '+j.oid]),d)}
for(const [key,title] of [['adr_candidates','ADR path candidates (decision status UNKNOWN)'],['aht_candidates','AHT source paths (check results UNKNOWN)']]){let d=detail(title+' — '+r[key].length,s);r[key].forEach(x=>link(x,d))}
let k=detail('As-is DMAIC / KPI source snapshots (freshness unqualified)',s);for(const m of r.as_is_metrics){let d=detail(m.path,k);link(m,d);el('p',m.qualification,d);el('pre',JSON.stringify(m.document,null,2),d)}
el('p','Current DMAIC/runtime KPI verification: UNKNOWN. Committed values above retain their original scope and observation window.',s)}}
document.getElementById('search').addEventListener('input',render);render();
</script></html>'''
    script = Path(__file__).with_name("development.js").read_text(encoding="utf-8")
    return page.replace("function render(){", script + "\nfunction render(){").replace(
        "let l=detail('Languages:", "renderDevelopment(r,s);let l=detail('Languages:")


def assignment(value):
    if "=" not in value:
        raise ValueError("expected OWNER/REPO=path")
    return value.split("=", 1)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", action="append", required=True)
    p.add_argument("--entry", action="append", default=[])
    p.add_argument("--metric", action="append", default=[], help="OWNER/REPO=committed.json; copy as-is")
    p.add_argument("--profiles", type=Path, help="explicit scope/purpose/ADR registry; optional")
    p.add_argument("--job-observations", type=Path, help="source-bound run/job metadata, never admission proof")
    p.add_argument("--max-age-seconds", type=int, default=86400)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    if args.job_observations and not args.profiles:
        p.error("job observations require explicit pipeline profiles")
    repos = [assignment(v) for v in args.repo]
    if len({n for n, _ in repos}) != len(repos):
        p.error("duplicate repository")
    entries = {}
    for value in args.entry:
        name, path = assignment(value)
        if name not in {n for n, _ in repos}:
            p.error("pipeline entry names an unscanned repository")
        entries.setdefault(name, []).append(path)
    metrics = {}
    for value in args.metric:
        name, path = assignment(value)
        if name not in {n for n, _ in repos}:
            p.error("metric source names an unscanned repository")
        metrics.setdefault(name, []).append(path)
    out = args.out.resolve()
    for _, path in repos:
        if out == Path(path).resolve() or Path(path).resolve() in out.parents:
            p.error("output must be outside every scanned worktree")
    doc = dict(schema="jade.repo-bios.source-report.v1", authority="SOURCE_INVENTORY_ONLY",
               merge_authorized=False, release_authorized=False,
               repositories=[snapshot(n, path, entries.get(n, []), metrics.get(n, [])) for n, path in repos])
    doc["generator"] = dict(commit=git(ROOT, "rev-parse", "HEAD^{commit}").decode().strip(),
        working_tree_dirty=bool(git(ROOT, "status", "--porcelain", "--", "tools/repo-bios")),
        files_sha256={name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                      for name in ("report.py", "development.py", "development.js")})
    if args.profiles:
        registry = json.loads(args.profiles.read_text(encoding="utf-8"))
        if registry.get("schema") != "jade.repo-bios.profiles.v1":
            p.error("unknown profile registry schema")
        observations = json.loads(args.job_observations.read_text(encoding="utf-8")) if args.job_observations else []
        if not isinstance(observations, list):
            p.error("job observations must be a list")
        roots = dict(repos)
        for snap in doc["repositories"]:
            profile = registry["repositories"].get(snap["repository"])
            if profile is None:
                p.error("no explicit profile for " + snap["repository"])
            development.extend(snap, profile, roots[snap["repository"]], git,
                               source_link, workflows, observations, max_age=args.max_age_seconds)
        doc["profile_registry_sha256"] = hashlib.sha256(args.profiles.read_bytes()).hexdigest()
    out.mkdir(parents=True, exist_ok=True)
    outputs = {"report.json": json.dumps(doc, indent=2, sort_keys=True) + "\n",
               "report.md": markdown(doc), "index.html": webpage(doc)}
    for name, body in outputs.items():
        (out / name).write_bytes(body.encode())
    (out / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(body.encode()).hexdigest()}  {name}\n" for name, body in sorted(outputs.items())), encoding="utf-8")
    print(markdown(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
