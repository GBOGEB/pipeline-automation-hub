#!/usr/bin/env python3
"""G11 exact-identity convergence of G7 selected successes and G9 native outcomes.

No raw-success summation across overlapping sample populations. No fleet rate
or causal root claim; G10 is a separate source-bound visual QA receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

SCHEMA="gogreen.g11.convergence.v1"
SHA40=re.compile(r"[0-9a-f]{40}\Z")
SHA256=re.compile(r"[0-9a-f]{64}\Z")
G10="gogreen.g10.native-quality-evidence.v1"
INTEGRATED_REPO="GBOGEB/pipeline-automation-hub"


def require(value,reason):
    if not value:
        raise ValueError(reason)


def bytes_of(obj):
    return (json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=True)+"\n").encode("ascii")


def import_source(path,alias):
    require(path.is_file(),"canonical source module missing")
    spec=importlib.util.spec_from_file_location(alias,path)
    require(spec is not None and spec.loader is not None,"cannot resolve canonical producer")
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def validate_g10(d):
    require(isinstance(d,dict) and d.get("schema")==G10,"untrusted G10 source")
    require(d.get("repository")==INTEGRATED_REPO and d.get("pr")==602,
            "wrong graph quality owner")
    require(d.get("native_run_id")==39025248286 and d.get("native_job_id")==117374963247
            and d.get("attempt")==1,"unverified G10 run/job/attempt")
    require(isinstance(d.get("source_sha"),str) and SHA40.fullmatch(d["source_sha"]),
            "unknown G10 source head")
    require(isinstance(d.get("module_source_git_blob"),str) and
            SHA40.fullmatch(d["module_source_git_blob"]), "missing G10 module object ID")
    require(isinstance(d.get("source_manifest_sha256"),str) and
            SHA256.fullmatch(d["source_manifest_sha256"]), "missing native output bytes provenance")
    require(d.get("tests_passed")==51 and d.get("tests_failed")==0,
            "G10 native test population failed")
    require((d.get("statement_covered"),d.get("statement_eligible"),
             d.get("branch_covered"),d.get("branch_eligible"))==(153,153,32,32),
            "G10 statement/branch coverage must be exact source-bound")
    require(d.get("coverage_tool")=="coverage==7.13.3" and
            d.get("source_scope")=="mission-control/gogreen/graph_quality/graph_quality.py",
            "G10 coverage source scope or tooling drift")
    require((d.get("graph_nodes"),d.get("graph_edges"),d.get("capability_nodes"))==(15,24,8),
            "wrong canonical visual graph size")
    require((d.get("observed_edges"),d.get("declared_edges"))==(8,16),
            "incomplete typed-edge provenance")
    require(d.get("browser_visual_qa_proven")=="LOCAL_ADJUNCT_NOT_NATIVE"
            and d.get("external_custody_verified") is False
            and d.get("independent_review") is False
            and d.get("authority_transfer") is False
            and d.get("merge_authorized") is False, "forbidden G10 admission inference")
    return d


def join(g7_data,registry,g9_data,g10_data,g7_module,g9_module):
    validate_g10(g10_data)
    # Consume current declared source owners, not a second parser or SSOT.
    _,g7rows,_,_=g7_module.validate(g7_data,registry)
    g9rows=g9_module.validate(g9_data)
    require(len(g7rows)==24 and len(g9rows)==57,"frozen G7/G9 population drift")
    a={r["run_id"]:r for r in g7rows}
    b={r["id"]:r for r in g9rows}
    require(len(a)==len(g7rows) and len(b)==len(g9rows),"duplicate run id")
    common=set(a)&set(b)
    outside_a=set(a)-common
    outside_b=set(b)-common
    for rid in common:
        x,y=a[rid],b[rid]
        require((x["repository"],x["workflow"],x["source_sha"],x["attempt"])==
                (y["repository"],y["workflow"],y["source_sha"],y["attempt"]),
                "duplicate native run ID cannot have conflicting provenance")
        require(y["conclusion"]=="success","G7 alleged green conflicts with G9 terminal outcome")
        require(y["created_at"]==x["created_at"],"inconsistent native run event time")
    require(len(common)==12 and len(outside_a)==12 and len(outside_b)==45,
            "converged replay set no longer matched to source-frozen N0")
    require({(a[r]["repository"],a[r]["workflow"]) for r in common}==
            {("GBOGEB/gg_MATH","M02B Math Bunker Smoke"),
             ("GBOGEB/cryoplant-project","QPS TRIAGE Debug DAG Pilot")},
            "overlap family/source-scope drift")
    outcomes=Counter(r["conclusion"] for r in g9rows)
    require(outcomes=={"success":46,"failure":10,"cancelled":1},
            "G9 complete-window outcome drift")
    union_green=outcomes["success"]+len(outside_a)
    unique=len(a)+len(b)-len(common)
    require((union_green,unique)==(58,69),"union evidence drift")
    require(union_green+outcomes["failure"]+outcomes["cancelled"]==unique,
            "union outcome identity loss")
    by_repo=Counter(a[rid]["repository"] for rid in common)
    return {
        "schema":SCHEMA,
        "source_population":"G7_SELECTED_GREEN_PLUS_G9_TWO_COMPLETE_NATIVE_WINDOWS",
        "g7_selected_successful_run_ids":len(a),
        "g9_complete_window_run_ids":len(b),
        "native_run_id_overlap":len(common),
        "g7_successful_runs_outside_g9_population":len(outside_a),
        "g9_runs_outside_g7_population":len(outside_b),
        "unique_union_run_ids":unique,
        "unique_union_successes":union_green,
        "union_native_failed":outcomes["failure"],
        "union_native_cancelled":outcomes["cancelled"],
        "common_ids":sorted(common),
        "common_by_repository":dict(sorted(by_repo.items())),
        "union_success_fraction":None,
        "global_fleet_success_rate":None,
        "all_workflow_attempts_complete":False,
        "statistically_independent_trials":None,
        "root_closure_credit":0,
        "native_module_coverage":[
            {"module":"G7 runner_telemetry.py","tests":53,
             "statement":[226,226],"branch":[38,38],
             "source_run_id":39024046315,"whole_repo":False},
            {"module":"G9 outcome_flight.py","tests":49,
             "statement":[152,152],"branch":[20,20],
             "source_run_id":39024952274,"whole_repo":False},
            {"module":"G10 graph_quality.py","tests":51,
             "statement":[153,153],"branch":[32,32],
             "source_run_id":g10_data["native_run_id"],"whole_repo":False},
        ],
        "tracked_module_statements":[531,531],
        "tracked_module_branches":[90,90],
        "tracked_native_test_methods_across_separate_heads":153,
        "integrated_single_head_all_module_proof":False,
        "g10_graph_qa":{"nodes":15,"edges":24,"observed":8,"declared":16,
                        "source_sha":g10_data["source_sha"],
                        "manifest_sha256":g10_data["source_manifest_sha256"],
                        "independent_visual_browser_ci":False},
        "authority_transfer":False,"dispatch_authorized":False,
        "merge_authorized":False,"formal_admission":"HOLD"}


def sipoc(report):
    nodes=[
        ("G7","S","Selected successful runs", "NATIVE_HISTORICAL"),
        ("G9","S","Complete-window terminal runs", "NATIVE_HISTORICAL"),
        ("G10","S","Visual graph quality receipt", "NATIVE_HISTORICAL"),
        ("RUN_JOIN","P","Exact ID / attempt / repo / SHA collision check", "DETERMINISTIC"),
        ("QUALITY","P","Scope-bound tests and module coverage", "NATIVE_SOURCE_SCOPED"),
        ("METRICS","O","Unique lineage and counted outcomes", "DETERMINISTIC"),
        ("C","C","Owner admission and independent security", "HOLD")]
    edges=[
        ("G7","RUN_JOIN","OBSERVED"),("G9","RUN_JOIN","OBSERVED"),
        ("RUN_JOIN","METRICS","OBSERVED"),("G10","QUALITY","OBSERVED"),
        ("QUALITY","METRICS","OBSERVED"),("METRICS","C","DECLARED")]
    return {
        "schema":"gogreen.g11.convergence-sipoc.v1",
        "nodes":[{"id":i,"role":r,"name":name,"evidence":e} for i,r,name,e in nodes],
        "edges":[{"source":a,"target":b,"confidence":kind} for a,b,kind in edges],
        "unique_runs":report["unique_union_run_ids"],
        "overlap":report["native_run_id_overlap"],
        "source_owner_authority":False,"merge_authorized":False}


def html_page(report):
    rows="".join(
        "<tr><td>"+html.escape(x["module"],quote=True)+"</td><td>"+str(x["tests"])+
        "</td><td>"+str(x["statement"][0])+"/"+str(x["statement"][1])+
        "</td><td>"+str(x["branch"][0])+"/"+str(x["branch"][1])+"</td></tr>"
        for x in report["native_module_coverage"])
    return ("""<!doctype html><html lang="en"><meta charset="utf-8">
<title>GoGREEN G11 exact native convergence</title><style>
:root{color-scheme:dark;font:16px system-ui;background:#0b1e31;color:#eaf7ff}
body{max-width:1160px;margin:auto;padding:30px}
section{border:1px solid #52647c;border-radius:13px;margin:14px 0;padding:18px}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #48566b;padding:9px;text-align:left}
strong{color:#7ce3b2}</style><body><h1>GoGREEN G11 · Native convergence and deduplication</h1>
<section><h2>Native run ID reconciliation</h2><p>G7 selected successful IDs: 24 ·
G9 complete-window IDs: 57 · exact overlap: <strong>"""+
            str(report["native_run_id_overlap"])+"""</strong> · unique evidence:
<strong>"""+str(report["unique_union_run_ids"])+"""</strong> IDs.</p>
<p>Unique observed outcomes: 58 successful, 10 failure, one cancelled.
This union mixes selected and complete populations: <strong>NO fleet success rate</strong>.</p></section>
<section><h2>Independent source-scoped native test receipts</h2><table><tr>
<th>Producer</th><th>Executed test methods</th><th>Statement coverage</th>
<th>Branch coverage</th></tr>"""+rows+"""</table><p>531/531 tracked statements and
90/90 branches on THREE separate native source heads. No single-head or
whole-repository coverage claim; no dependence-adjusted probability.</p></section>
<section><h2>SIPOC root boundary</h2><p>G7 + G9 → exact identity join →
unique manifest; G10 visual proof → quality evidence → metrics →
independent customer admission HOLD. Root and agent dispatch: not authorized.</p></section></body></html>
""")


def build(root,source_sha,out):
    require(isinstance(source_sha,str) and SHA40.fullmatch(source_sha),
            "exact-head Git SHA required")
    graph_module=import_source(root/"success_graph/runner_telemetry.py","g7_source")
    outcomes_module=import_source(root/"outcome_convergence/outcome_flight.py","g9_source")
    g7=json.loads((root/"success_graph/samples/native_success_20261017.json").read_text())
    g9=json.loads((root/"outcome_convergence/samples/native_full_window_20261017.json").read_text())
    reg=json.loads((root.parent/"grand-missions/GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json").read_text())
    g10=json.loads((root/"convergence_bridge/samples/g10_native_quality_20261017.json").read_text())
    report=join(g7,reg,g9,g10,graph_module,outcomes_module)
    dag=sipoc(report)
    out.mkdir(parents=True,exist_ok=True)
    files={"metrics.json":bytes_of(report),"sipoc_dag.json":bytes_of(dag),
           "index.html":html_page(report).encode("utf-8")}
    for name,b in files.items():
        (out/name).write_bytes(b)
    manifest={"schema":"gogreen.g11.source-bound-output.v1",
              "exact_head":source_sha,
              "files":{k:hashlib.sha256(v).hexdigest() for k,v in files.items()},
              "merge_authorized":False,"external_archive_custody":False}
    (out/"manifest.json").write_bytes(bytes_of(manifest))
    return report,manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument("--source-sha",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    m,_=build(a.root,a.source_sha,a.out)
    print(json.dumps({"g7":m["g7_selected_successful_run_ids"],
                      "g9":m["g9_complete_window_run_ids"],
                      "intersection":m["native_run_id_overlap"],
                      "unique":m["unique_union_run_ids"],
                      "admission":m["formal_admission"]},sort_keys=True))


if __name__=="__main__":
    main()
