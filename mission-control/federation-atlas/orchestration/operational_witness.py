#!/usr/bin/env python3
"""Additive Method Atlas operational witness. No remote dispatch or new SSOT."""
from __future__ import annotations
import argparse
import hashlib
import html
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "OPERATIONAL_SURFACES_v1.json"
G9 = "mission-control/gogreen/outcome_convergence/outcome_flight.py"
SAMPLE = "mission-control/gogreen/outcome_convergence/samples/native_full_window_20261017.json"
EXT = {".py":"PYTHON",".js":"JAVASCRIPT",".jsx":"JSX",".ts":"TYPESCRIPT",
       ".tsx":"TSX",".mjs":"JAVASCRIPT",".cjs":"JAVASCRIPT",
       ".ps1":"POWERSHELL",".sh":"SHELL",".json":"JSON_CONTRACT",
       ".toml":"TOML_CONTRACT",".yml":"YAML_CONTRACT",".yaml":"YAML_CONTRACT"}
CODE = {"PYTHON","JAVASCRIPT","JSX","TYPESCRIPT","TSX","POWERSHELL","SHELL"}
HISTORY = {"archive","archives","vendor","node_modules",".venv","recovered","generated"}
SOURCE_REF = re.compile(r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_./-]+\.(?:py|js|jsx|ts|tsx|mjs|cjs|sh|ps1|json|toml|ya?ml))(?=$|[\s\"'\\;])")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
COUNTS = {"total_native_runs":57,"native_terminal_success":46,
          "native_terminal_failure":10,"native_terminal_cancelled":1}


def canonical(value):
    return (json.dumps(value,indent=2,sort_keys=True,ensure_ascii=True)+"\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def source_head(root, expected):
    if not SHA40.fullmatch(expected or ""):
        raise ValueError("EXACT_SOURCE_HEAD_REQUIRED")
    p=subprocess.run(["git","-C",str(root),"rev-parse","HEAD"],
                     capture_output=True,text=True,timeout=10,check=False)
    if p.returncode or p.stdout.strip()!=expected:
        raise ValueError("CHECKOUT_HEAD_MISMATCH")
    return expected


def existing_atlas():
    path=HERE/"main.py"
    spec=importlib.util.spec_from_file_location("method_atlas_existing_inventory",path)
    if not spec or not spec.loader:
        raise ValueError("METHOD_ATLAS_OWNER_MISSING")
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod


def kind(path):
    parts=PurePosixPath(path).parts
    if any(x.casefold() in HISTORY for x in parts):
        return "HISTORICAL_OR_GENERATED"
    if "tests" in parts or "test" in parts or Path(path).name.startswith("test_"):
        return "TEST_SOURCE"
    if path.startswith(".github/workflows/"):
        return "WORKFLOW_DECLARATION"
    return ("EXECUTABLE_CANDIDATE" if EXT.get(Path(path).suffix) in CODE else
            "CONTRACT_OR_CONFIGURATION" if EXT.get(Path(path).suffix) else "OTHER")


def inventory(root, owner, registry):
    """Reuses Method Atlas source_files/inventory; adds literal direct links only."""
    import yaml
    paths=sorted(set(owner.source_files(root)))
    index=set(paths)
    native=owner.inventory(root)
    classes=Counter(kind(p) for p in paths)
    langs=Counter(EXT.get(Path(p).suffix,"OTHER") for p in paths)
    links=[]
    unresolved=0
    scheduled=[]
    for wf in native["workflows"]:
        if wf["errors"]:
            unresolved+=1
            continue
        definition=yaml.load((root/wf["path"]).read_bytes(),Loader=yaml.BaseLoader)
        triggers=definition.get("on") or {}
        if isinstance(triggers,dict) and "schedule" in triggers:
            scheduled.append({"workflow":wf["path"],"liveness":"UNOBSERVED",
                              "notification_owner":"UNCHANGED"})
        for jobname,job in (definition.get("jobs") or {}).items():
            if not isinstance(job,dict):
                unresolved+=1
                continue
            steps=list(job.get("steps") or [])
            if job.get("uses"):
                steps.append({"uses":job["uses"]})
            for i,step in enumerate(steps):
                if not isinstance(step,dict):
                    unresolved+=1
                    continue
                run=step.get("run") or ""
                uses=step.get("uses") or ""
                names=[m.group(1) for m in SOURCE_REF.finditer(run)]
                if uses.startswith("./"):
                    names.append(uses[2:].split("@",1)[0])
                for name in sorted(set(names)):
                    name=name.removeprefix("./")
                    if name in index:
                        links.append({"workflow":wf["path"],"job":str(jobname),
                                      "step":i,"target":name,"proof":"STATIC_ONLY"})
                    else:
                        unresolved+=1
                # GitHub expression paths cannot be resolved without actual runtime.
                if "$" + "{{" in run or "$" + "{{" in uses:
                    unresolved+=1
    links.sort(key=lambda x:(x["workflow"],x["job"],x["step"],x["target"]))
    execution={p for p in index if kind(p)=="EXECUTABLE_CANDIDATE"}
    direct={x["target"] for x in links if x["target"] in execution}
    return {"schema":"method-atlas.operational-inventory.v1",
            "scope":"TRACKED_SOURCE_STATIC_LINKS_NOT_ACTUAL_EXECUTION",
            "files":len(paths),"by_class":dict(sorted(classes.items())),
            "by_language":dict(sorted(langs.items())),
            "workflows":native["workflow_count"],"jobs":native["workflow_jobs"],
            "steps":native["workflow_steps"],"direct_links":links,
            "direct_link_count":len(links),"direct_executable_targets":len(direct),
            "not_directly_linked_executable_candidates":len(execution-direct),
            "unresolved_static_refs":unresolved,
            "watchers":[*scheduled],
            "peers":[{"repo":x["repo"],"role":x["role"],
                      "source_state":"LOCAL_STATIC_ONLY" if x["repo"]==registry["local_repo"]
                      else "EXTERNAL_NOT_ACCESSED", "actual_coverage_pct":None}
                     for x in registry["peers"]],
            "python_statement_coverage_pct":None,"python_branch_coverage_pct":None,
            "js_ts_coverage_pct":None,"whole_pipeline_coverage_pct":None,
            "json_yaml_toml":"CONSUMER_DECISION_BRANCH_AND_SCHEMA_COVERAGE",
            "unlinked_is_not_zero_coverage":True}


def execute(root,head,source,out):
    """Run the real G9 CLI, optionally measuring its runtime in its OWN cohort.

    The wrapper's unittest/CLI coverage is distinct from G9 production coverage.
    A trusted exact-head workflow may opt in through WITNESS_G9_COVERAGE_FILE.
    No uncontrolled source code or remote process is dispatched.
    """
    script=[str(root/G9),"--input",str(source),
            "--out",str(out),"--source-sha",head]
    output=os.environ.get("WITNESS_G9_COVERAGE_FILE")
    env=None
    if output:
        selected=Path(output).resolve()
        if selected==root or selected.is_relative_to(root):
            raise ValueError("G9_COVERAGE_OUTPUT_INSIDE_CHECKOUT")
        cmd=[sys.executable,"-m","coverage","run","-a","--branch",
             "--include=*/mission-control/gogreen/outcome_convergence/outcome_flight.py",
             *script]
        env={**os.environ,"COVERAGE_FILE":str(selected)}
    else:
        cmd=[sys.executable,*script]
    return subprocess.run(cmd,cwd=root,env=env,capture_output=True,
                          text=True,timeout=75,check=False)


def verify_artifacts(path,head):
    m=json.loads((path/"manifest.json").read_text())
    if m.get("source_sha")!=head or m.get("merge_authorized") is not False:
        raise ValueError("BAD_PRODUCTION_OUTPUT_MANIFEST")
    for name,sha in m["files"].items():
        if name!=Path(name).name or digest((path/name).read_bytes())!=sha:
            raise ValueError("OUTPUT_HASH_OR_PATH_INVALID")
    return json.loads((path/"metrics.json").read_text()),m


def actual_outcome_witness(root,head):
    raw=(root/SAMPLE).read_bytes()
    source=json.loads(raw)
    with tempfile.TemporaryDirectory(prefix="g9-real-command-proof-") as td:
        tmp=Path(td)
        a,b=tmp/"original",tmp/"repeat"
        if execute(root,head,root/SAMPLE,a).returncode or execute(root,head,root/SAMPLE,b).returncode:
            raise ValueError("PRODUCTION_ENTRYPOINT_DID_NOT_RUN")
        first,ma=verify_artifacts(a,head)
        again,mb=verify_artifacts(b,head)
        if any(first.get(k)!=v for k,v in COUNTS.items()):
            raise ValueError("G9_SOURCE_BOUND_57_RUN_DENOMINATOR_DRIFT")
        if first!=again or ma!=mb:
            raise ValueError("PRODUCTION_OUTPUT_NOT_IDEMPOTENT")
        changed=json.loads(json.dumps(source))
        row=next((r for c in changed["cohorts"] for r in c["runs"]
                  if r.get("conclusion")=="success"),None)
        if row is None:
            raise ValueError("MISSING_COUNTERFACTUAL_ROW")
        row["conclusion"]="failure"
        x=tmp/"changed.json"
        x.write_bytes(canonical(changed))
        c=tmp/"counterfactual"
        if execute(root,head,x,c).returncode:
            raise ValueError("CONTROLLED_VALID_INPUT_REJECTED")
        alter,_=verify_artifacts(c,head)
        if (alter["native_terminal_success"]!=first["native_terminal_success"]-1 or
                alter["native_terminal_failure"]!=first["native_terminal_failure"]+1):
            raise ValueError("NO_EXPECTED_INPUT_OUTPUT_SENSITIVITY")
        bad=json.loads(json.dumps(source))
        bad["cohorts"][0]["returned_count"]+=1
        y=tmp/"bad.json"
        y.write_bytes(canonical(bad))
        if execute(root,head,y,tmp/"bad").returncode==0:
            raise ValueError("INCOMPLETE_NATIVE_DENOMINATOR_FALSE_PASS")
        bad2=json.loads(json.dumps(source))
        bad2["cohorts"][0]["runs"][0]["run_started_at"]="2026-10-15T00:00:00Z"
        z=tmp/"out_of_order.json"
        z.write_bytes(canonical(bad2))
        if execute(root,head,z,tmp/"out_of_order").returncode==0:
            raise ValueError("OUT_OF_ORDER_NATIVE_CLOCK_FALSE_PASS")
        return {"schema":"method-atlas.operational-outcome-witness.v1",
                "entrypoint":G9,"input_path":SAMPLE,"input_sha256":digest(raw),
                "source_head":head,"baseline":{k:first[k] for k in COUNTS},
                "metrics_sha256":digest((a/"metrics.json").read_bytes()),
                "manifest_sha256":digest((a/"manifest.json").read_bytes()),
                "production_command_executed":True,
                "idempotent_repeat":True,
                "valid_counterfactual_changes_expected_outcome":True,
                "missing_population_rejected":True,
                "out_of_order_clock_rejected":True,
                "witness_scope":"HISTORICAL_FIXTURE_CONTROLLED_CAUSAL_SENSITIVITY",
                "actual_fleet_root_caused":False,"remote_dispatch":False,
                "engineering_credit_delta":0}


def visual(report):
    inv=report["inventory"];wit=report["witness"]
    rows="".join("<tr><td>"+html.escape(k)+"</td><td>"+str(v)+"</td></tr>"
                 for k,v in inv["by_class"].items())
    peer="".join("<tr><td>"+html.escape(p["repo"])+"</td><td>"+
                 html.escape(p["role"])+"</td><td>"+p["source_state"]+"</td></tr>"
                 for p in inv["peers"])
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Method Atlas | Operational Witness</title>
<style>body{{background:#1c0b2b;color:#f9f4fc;font:15px/1.55 Aptos,system-ui,sans-serif;max-width:1080px;margin:auto;padding:28px}}
h1{{font-size:2rem}}h2{{color:#f4bdeb}}code{{color:#f9c7ec;font-family:Consolas,monospace}}
.cards{{display:flex;flex-wrap:wrap;gap:12px}}article,details{{background:#341743;border:1px solid #9b6ab3;
border-radius:12px;padding:16px;margin:10px 0;flex:1;min-width:160px}}
strong{{display:block;font-size:1.7rem}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;border-bottom:1px solid #78578b;padding:8px}}
summary{{cursor:pointer}}small{{color:#e6c2ea}}</style>
<h1>Method Atlas · Operational Witness</h1>
<p>Source wiring is not runtime coverage. Controlled input/output sensitivity is not accepted causal-root repair.</p>
<div class="cards"><article>Tracked files<strong>{inv['files']}</strong></article>
<article>Workflow declarations<strong>{inv['workflows']}</strong></article>
<article>Direct declared links<strong>{inv['direct_link_count']}</strong></article>
<article>G9 cohort records<strong>{wit['baseline']['total_native_runs']}</strong></article></div>
<h2>Real production command: G9 outcome analysis</h2><article>
<p>Real outcome processor executed on a frozen historical source; repeated identically and run with a valid counterfactual and two invalid inputs.</p>
<strong>{wit['baseline']['native_terminal_success']} success · {wit['baseline']['native_terminal_failure']} failed · {wit['baseline']['native_terminal_cancelled']} cancelled</strong>
<p>Idempotence: PASS · Counterfactual response: PASS · Missing population: REJECTED · Out-of-order clock: REJECTED.</p></article>
<details><summary>Static source classes</summary><table>{rows}</table></details>
<details><summary>Federation source boundaries</summary><table><tr><th>Repo</th><th>Owner role</th><th>Evidence state</th></tr>{peer}</table></details>
<details><summary>Unknown, zero, peer and whole-pipeline coverage</summary>
<p>Line and branch percentages remain NULL without matched native instrumented populations.
Unlinked code is a candidate, not verified unused; YAML, JSON and TOML are contracts whose consumers need decision-branch coverage.
External repositories were not checked out, and an event trace does not certify whole-pipeline deployment.</p></details>
<footer><small>Exact source HEAD: <code>{report['head']}</code>. Read-only additive view; existing Method Atlas retains metric and publisher ownership.</small></footer></html>\n"""


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root",required=True,type=Path)
    ap.add_argument("--head",required=True)
    ap.add_argument("--out",required=True,type=Path)
    args=ap.parse_args(argv)
    root=args.root.resolve();out=args.out.resolve()
    if out==root or out.is_relative_to(root) or (out.exists() and any(out.iterdir())):
        raise ValueError("OUTPUT_MUST_BE_EMPTY_AND_OUTSIDE_REPOSITORY")
    source_head(root,args.head)
    registry=json.loads(REGISTRY.read_text(encoding="utf-8"))
    if registry.get("schema")!="method-atlas.operational-surface-registry.v1":
        raise ValueError("REGISTRY_SCHEMA_MISMATCH")
    inv=inventory(root,existing_atlas(),registry)
    outcome=actual_outcome_witness(root,args.head)
    report={"schema":"method-atlas.operational-witness.v1","head":args.head,
            "inventory":inv,"witness":outcome,
            "governance":{"merge_admission":"HOLD","dispatch_authorized":False,
                          "watch_notification_owner_changed":False,
                          "whole_fleet_coverage_qualified":False,"engineering_credit_delta":0}}
    out.mkdir(parents=True,exist_ok=True)
    (out/"operational_witness.json").write_bytes(canonical(report))
    (out/"index.html").write_text(visual(report),encoding="utf-8",newline="\n")
    (out/"causal_dag.mmd").write_text("""flowchart LR
    S[Historical source SHA] --> P[Execute existing G9 processor]
    P --> O[Metric and manifest hashes]
    S --> M[Controlled counterfactual]
    M --> P
    O --> V[Replay and negative oracle]
    V --> H[Independent owner HOLD]
""",encoding="utf-8",newline="\n")
    manifest={"schema":"method-atlas.operational-witness-manifest.v1",
              "head":args.head,"files":{name:digest((out/name).read_bytes()) for name in
                 ("operational_witness.json","index.html","causal_dag.mmd")},
              "dispatch":False,"merge_admission":"HOLD"}
    (out/"manifest.json").write_bytes(canonical(manifest))
    print(json.dumps({"status":"PASS_CONTROLLED_WITNESS_ONLY","head":args.head,
                      "direct_links":inv["direct_link_count"],
                      "outcomes":outcome["baseline"]},sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
