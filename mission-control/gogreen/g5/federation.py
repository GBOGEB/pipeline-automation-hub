"""GOGREEN G5: fail-closed fleet census, typed federation and N+2 pulse planning.

This is a read-only off-line producer. A workflow success is not a real worker
launch, an accepted REX return, a reproducible debugger session, a PCA fit,
or a QPS owner decision. Historical SHAs are intentionally not current heads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

SCHEMA = "gogreen.g5.federation-intake.v1"
OUT_SCHEMA = "gogreen.g5.rollup.v1"
GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
STATES = {"OPEN_DRAFT", "OPEN_READY", "MERGED", "CLOSED_UNMERGED"}
ROLES = {"MISSION_CONTROL", "MIP", "DMAIC", "PCA", "REX", "LDAB", "LLDB", "CENSUS", "3PSTAR", "QPS_TRIAGE", "MYCELIUM", "GOLDEN_THREAD"}
EVIDENCE = {"DECLARED", "PRODUCER_NATIVE", "CONSUMER_NATIVE", "RECIPIENT_ACCEPTED"}

def _int(value, name, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError(f"{name}: integer must be {'positive' if positive else 'nonnegative'}")
    return value

def _sha(value, name):
    if not isinstance(value, str) or not GIT_SHA.fullmatch(value):
        raise ValueError(f"{name}: exact lower-case 40-char source SHA required")
    return value

def validate(intake):
    if not isinstance(intake, dict) or intake.get("schema") != SCHEMA:
        raise ValueError("G5 schema mismatch")
    if any(intake.get(k) is not False for k in ("authority_transfer", "dispatch_authorized", "merge_authorized", "security_waiver")):
        raise ValueError("cross-repository authority claim prohibited")
    if intake.get("qps_disposition") != "DEFER":
        raise ValueError("QPS engineering ACCEPT/REJECT cannot be imported")
    if not isinstance(intake.get("snapshot_at"), str):
        raise ValueError("snapshot timestamp required")
    timestamp = datetime.fromisoformat(intake["snapshot_at"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("snapshot timestamp must be timezone aware")
    if not isinstance(intake.get("repos"), list) or len(intake["repos"]) != 6:
        raise ValueError("fixed six-repository census required")
    names = set()
    for repo in intake["repos"]:
        if not isinstance(repo, dict):
            raise ValueError("invalid repository record")
        name = repo.get("repository")
        if not isinstance(name, str) or not name.startswith("GBOGEB/") or name in names:
            raise ValueError("invalid or duplicated repo")
        names.add(name)
        _sha(repo.get("catalog_sha"), "catalog_sha")
        families = repo.get("target_families")
        if not isinstance(families, list) or not families or len(set(families)) != len(families):
            raise ValueError("invalid repo-family scope")
        if repo.get("source_kind") not in {"MAIN_SNAPSHOT", "PR_HEAD_SNAPSHOT"}:
            raise ValueError("historical source kind required")
    if sum(len(repo["target_families"]) for repo in intake["repos"]) != 42:
        raise ValueError("42-cell denominator drift")
    if not isinstance(intake.get("pr_observations"), list):
        raise ValueError("PR observation list required")
    seen_pr = set()
    for pr in intake["pr_observations"]:
        if pr.get("repository") not in names:
            raise ValueError("PR outside declared federation")
        if pr.get("status") not in STATES:
            raise ValueError("invalid PR state")
        _sha(pr.get("head_sha"), "PR head")
        _int(pr.get("pr"), "PR number", positive=True)
        key = (pr["repository"], pr["pr"])
        if key in seen_pr:
            raise ValueError("duplicate PR record")
        seen_pr.add(key)
        _int(pr.get("workflow_sample_size"), "workflow sample size")
        counts = pr.get("workflow_conclusions")
        if not isinstance(counts, dict) or set(counts) != {"success", "failure", "cancelled", "skipped", "nonterminal"}:
            raise ValueError("invalid workflow conclusion census")
        for k,v in counts.items():
            _int(v, k)
        if sum(counts.values()) != pr["workflow_sample_size"]:
            raise ValueError("workflow counts do not reconcile")
        if pr.get("observed_head_is_current") is not False:
            raise ValueError("historical PR head cannot assert live-currentness")
        if pr.get("accepted_rex_return") is not False or pr.get("qps_accepted") is not False:
            raise ValueError("self-accepted worker / QPS authority")
    nodes = intake.get("nodes")
    edges = intake.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list) or not nodes:
        raise ValueError("DAG nodes and edges required")
    node_names = set()
    for node in nodes:
        identity = node.get("id")
        if not isinstance(identity, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", identity) or identity in node_names:
            raise ValueError("node ID invalid or duplicated")
        node_names.add(identity)
        if node.get("repository") not in names or node.get("role") not in ROLES:
            raise ValueError("unrecognized node owner/role")
        _sha(node.get("source_sha"), "node source")
        matching = next(r for r in intake["repos"] if r["repository"] == node["repository"])
        if node["source_sha"] != matching["catalog_sha"]:
            raise ValueError("node source must equal catalog historical reference")
    seen_edge = set()
    for edge in edges:
        src, dst = edge.get("source"), edge.get("target")
        if src not in node_names or dst not in node_names or src == dst:
            raise ValueError("invalid federation edge")
        if (src,dst) in seen_edge:
            raise ValueError("duplicate federation edge")
        seen_edge.add((src,dst))
        if edge.get("level") not in EVIDENCE:
            raise ValueError("unrecognized evidence level")
        if edge["level"] != "DECLARED":
            if edge["level"] == "RECIPIENT_ACCEPTED":
                raise ValueError("QPS owner authority cannot be imported by Mission Control")
            raise ValueError("native federation edge requires real receipt and independent byte verifier (G5 unsupported)")
        elif edge.get("receipt") is not None:
            raise ValueError("declared edge cannot carry a fake receipt")
    from collections import defaultdict
    adj=defaultdict(list)
    for edge in edges:
        adj[edge["source"]].append(edge["target"])
    stack, visited = set(), set()
    def dfs(v):
        if v in stack:
            raise ValueError("federation DAG cycle")
        if v in visited:
            return
        stack.add(v)
        for nxt in adj[v]:
            dfs(nxt)
        stack.remove(v)
        visited.add(v)
    for v in sorted(node_names):
        dfs(v)
    return intake

def calculate(g0, g1, intake, *, max_parallel=2, max_packets=12, per_repo=1):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from spine import build
    validate(intake)
    for label, value in (("max_parallel",max_parallel),("max_packets",max_packets),("per_repo",per_repo)):
        if type(value) is not int or not 1 <= value <= 16:
            raise ValueError(f"unsafe {label}")
    if g0.get("repositories") != g1.get("repositories"):
        raise ValueError("G0 and G1 catalogs are not scope matched")
    base_rows = {(x["repository"],x["run_id"],x["run_attempt"],x["job_id"]):x for x in g0["observations"]}
    after_rows = {(x["repository"],x["run_id"],x["run_attempt"],x["job_id"]):x for x in g1["observations"]}
    if any(after_rows.get(k) != v for k,v in base_rows.items()):
        raise ValueError("historical G0 observations have changed")
    a,_,_=build(g0)
    b,_,_=build(g1)
    if a["breadth"]["catalog_repo_family_cells"] != b["breadth"]["catalog_repo_family_cells"]:
        raise ValueError("invalid matched denominator")
    if {(r["repository"],r["head_sha"],tuple(r["target_families"])) for r in g1["repositories"]} != {(r["repository"],r["catalog_sha"],tuple(r["target_families"])) for r in intake["repos"]}:
        raise ValueError("federation role source not bound to fixed original population")
    total=b["breadth"]["catalog_repo_family_cells"]
    observed0=a["breadth"]["observed_cells"]
    observed1=b["breadth"]["observed_cells"]
    seen={(r["repository"],r["family"]) for r in b["observations"]}
    queued=[]
    for r in intake["repos"]:
        for f in r["target_families"]:
            if (r["repository"],f) not in seen:
                queued.append({"repository":r["repository"],"family":f,"catalog_sha":r["catalog_sha"]})
    priority={"security":0,"coverage":1,"artifact":2,"runtime":3,"ci_contract":4,"federation":5,"qps_triage":6,"math_model":7}
    queued.sort(key=lambda x:(priority[x["family"]],x["repository"]))
    plan=[]
    owners=Counter()
    for packet in queued:
        if len(plan)>=max_packets:
            break
        if owners[packet["repository"]] >= per_repo:
            continue
        owners[packet["repository"]]+=1
        plan.append({**packet,"owner":"GOGREEN_READONLY","mutation_paths":[],"dispatch_authorized":False})
    stages=Counter(edge["level"] for edge in intake["edges"])
    blockers=[]
    for pr in intake["pr_observations"]:
        if pr["status"] == "OPEN_DRAFT":
            blockers.append({"repository":pr["repository"],"pr":pr["pr"],"reason":"DRAFT_ADMISSION_HOLD"})
        if pr["workflow_conclusions"]["failure"] or pr["workflow_conclusions"]["nonterminal"]:
            blockers.append({"repository":pr["repository"],"pr":pr["pr"],"reason":"NON_GREEN_OR_NONTERMINAL_CURRENT_SNAPSHOT"})
    return {"schema":OUT_SCHEMA,"snapshot_at":intake["snapshot_at"],
            "population":{"repositories":len(intake["repos"]),"target_cells":total,
                "G0_observed":observed0,"G1_observed":observed1,
                "G1_unobserved":total-observed1,"breadth_delta_pp":round(100*(observed1-observed0)/total,4)},
            "depth":{"declared_nodes":len(intake["nodes"]),"declared_edges":len(intake["edges"]),
                "native_executed_edges":sum(stages[s] for s in ("PRODUCER_NATIVE","CONSUMER_NATIVE","RECIPIENT_ACCEPTED")),
                "consumer_native_edges":stages["CONSUMER_NATIVE"],"recipient_accepted_edges":stages["RECIPIENT_ACCEPTED"],
                "real_ldab_lldb_receipt_count":None,"pca_fit_evidence":None,"3pstar_maturity":None},
            "fan_out":{"packets_staged":len(plan),"still_unplanned":len(queued)-len(plan),
                "max_parallel":max_parallel,"max_packets":max_packets,"per_repo":per_repo,
                "packets":plan,"actual_dispatched":0,"worker_capacity":None},
            "wave_states":{"current_pr_snapshots":intake["pr_observations"],"blockers":blockers},
            "dmaic":{"define":"SIX_REPO_42_CELL_FROZEN_SCOPE","measure":"SOURCE_SHA_RUN_JOB_PROVENANCE",
                 "analyze":"SHARED_ROOTS_NOT_INFERRED_FROM_WORKFLOW_COUNTS","improve":"DISJOINT_PASSIVE_SCOUTS_STAGED",
                 "control":"SEPARATE_ADMISSION_AND_RECURRENCE"},
            "methods":{"MIP":"SOURCE_BOUND_PENDING_INDIVIDUAL_REPLAY","REX":"NO_ACCEPTED_RETURN_IN_THIS_CENSUS",
                "LDAB_LLDB":"SESSION_SOURCE_AND_DEBUGGER_RECEIPTS_NOT_JOINED",
                "PCA":"NOT_ESTIMABLE_UNTIL_COMPARABLE_MULTIVARIATE_MATRIX",
                "3PSTAR":"CANDIDATE_ONLY_NO_STATISTICAL_TRIAL","QPS_TRIAGE":"DEFER"},
            "n_plus_2":[{"horizon":"N+1","target":"NATIVE_G5_UNIT_TESTS_AND_ARTIFACT_SOURCE_BOUND","prediction_class":"TESTABLE_NOT_YET_OBSERVED","probability":None},
                        {"horizon":"N+2","target":"FIRST_CROSS_REPO_TYPED_RECEIPT_REPLAY","prediction_class":"DEPENDENT_ON_AUTHENTICATED_RECEIPTS","probability":None}],
            "authority_transfer":False,"dispatch_authorized":False,"merge_authorized":False,
            "security_waiver":False,"qps_disposition":"DEFER","global_root_closure":None}

def emit(result, out):
    out.mkdir(parents=True, exist_ok=True)
    evidence=json.dumps(result,sort_keys=True,indent=2,ensure_ascii=True).encode()+b"\n"
    digest=hashlib.sha256(evidence).hexdigest()
    (out/"federation_census.json").write_bytes(evidence)
    (out/"federation_census.sha256").write_text(digest+"\n",encoding="ascii")
    rows=["# GOGREEN G5 source-bound federation pulse", "",
          "| Metric | G0 | G1 imported |", "|---|---:|---:|",
          f"| Observed repo-family cells | {result['population']['G0_observed']}/{result['population']['target_cells']} | {result['population']['G1_observed']}/{result['population']['target_cells']} |", "",
          f"Planned links: {result['depth']['declared_edges']}; native consumer edges: {result['depth']['consumer_native_edges']}; recipient-accepted links: {result['depth']['recipient_accepted_edges']}.",
          f"Passive packets staged: {result['fan_out']['packets_staged']}; no remote dispatch or merge authority.",
          "", "PCA and 3P* claims are held for missing comparable data. QPS remains DEFER.",
          "", "SHA-256: "+digest, ""]
    (out/"federation_pulse.md").write_text("\n".join(rows),encoding="utf-8")
    return digest

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--g0',type=Path,required=True)
    p.add_argument('--g1',type=Path,required=True)
    p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--max-parallel',type=int,default=2)
    p.add_argument('--max-packets',type=int,default=12)
    a=p.parse_args()
    result=calculate(json.loads(a.g0.read_text()),json.loads(a.g1.read_text()),json.loads(a.snapshot.read_text()),max_parallel=a.max_parallel,max_packets=a.max_packets)
    emit(result,a.out)
    print(json.dumps({'G0':result['population']['G0_observed'],'G1':result['population']['G1_observed'], 'declared_edges':result['depth']['declared_edges'],'native_edges':result['depth']['native_executed_edges'],'packets_staged':result['fan_out']['packets_staged']}))

if __name__=='__main__':
    main()
