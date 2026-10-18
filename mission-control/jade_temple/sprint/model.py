"""JADE_CASTE N+3: source-bound POINT RELEASE preparation projection.

Read-only, not a scheduler, remote worker, issuer, release gate or owner SSOT.
"""
from __future__ import annotations
import hashlib
import html
import json
import re
from collections import Counter, defaultdict

SCHEMA = "jade.temple.sprint.dag.v1"
SHA = re.compile(r"[0-9a-f]{40}\Z")
AXES = (
    ("source_coverage", "matched statement and branch arcs", "ABACUS / repo owner"),
    ("adversarial_penetration", "effective fault/oracle pairs", "native test owner"),
    ("cross_module_integration", "authenticated producer/consumer edges", "CODEX / source owners"),
    ("platform_runner_reach", "qualified OS/runtime cells", "GitHub native runner"),
    ("causal_defect_detection", "dispositioned reproducible causal roots", "EVERRED / BD owner"),
    ("navigation_integrity", "verified root/SPINE links", "JADE J1 owner"),
    ("hosted_asset_parity", "served exact-SHA HTTPS assets", "JADE J2 Pages owner"),
    ("governance_review", "effective protections and RED-canary gates", "JADE J3 admin"),
    ("supply_chain_dependencies", "verified pinned dependencies and SBOM", "repo package owner"),
    ("release_artifacts", "owner-authorized tag/assets and rollback", "JADE J5 release owner"),
    ("worker_pool_capacity", "known occupied/eligible slots", "local/Actions owner"),
    ("queue_latency", "observed queue-to-start timestamps", "GitHub Actions owner"),
    ("cache_reproducibility", "same-input validated local receipts", "local tester only"),
    ("issue_burndown", "owner-qualified closure / eligible owner actions", "source issue owner"),
    ("transport_lineage", "verified run/job/attempt to receiver", "CODEX / QPS owner"),
)
GATES = ("J0","J1","COVERAGE","ADVERSARIAL","INTEGRATION","RUNNERS","CAUSE",
         "SUPPLY","J2","J3","J4","J5")
PRIORITY = {"P0":0,"P1":1,"P2":2}

def demand(condition, message):
    if not condition:
        raise ValueError(message)

def canonical(obj):
    return (json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True)+"\n").encode("utf-8")

def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()

def validate(source, readback=None):
    demand(type(source) is dict and source.get("schema")=="jade.temple.repo_readiness.v1","BAD_SOURCE_SCHEMA")
    demand(source.get("admission")=="HOLD" and source.get("authority_transfer") is False,"AUTHORITY_TRANSFER")
    rows=source.get("rows")
    demand(type(rows) is list and len(rows)==21,"TOP21_DENOMINATOR")
    demand(len({r.get("repo") for r in rows})==21,"ROSTER_COLLISION")
    demand(len({r.get("rank") for r in rows})==21,"RANK_COLLISION")
    for r in rows:
        demand(type(r.get("repo")) is str and r["repo"].startswith("GBOGEB/"),"FOREIGN_OWNER")
        demand(type(r.get("head_readback")) is str and SHA.fullmatch(r["head_readback"]),"UNPINNED_HEAD")
        demand(r.get("priority") in PRIORITY and 1 <= r.get("rank",0) <= 21,"BAD_PRIORITY")
        demand(r.get("readiness",{}).get("inventory")=="J0_OBSERVED","J0_UNVERIFIED")
        demand(r.get("readiness",{}).get("point_release")=="UNQUALIFIED" and
               r.get("merge_admission")=="HOLD" and r.get("authority_transfer") is False,
               "FALSE_RELEASE_SUCCESS")
        demand(type(r.get("next_point_release_todo")) is str and r["next_point_release_todo"],"MISSING_ACTION")
    demand([sum(r["priority"]==p for r in rows) for p in ("P0","P1","P2")]==[5,9,7],"PRIORITY_DRIFT")
    if readback is not None:
        demand(type(readback) is dict and readback.get("schema")=="jade.temple.fleet_readback.v2"
               and readback.get("merge_admission")=="HOLD"
               and readback.get("authority_transfer") is False,"READBACK_AUTHORITY")
        newer=readback.get("rows")
        demand(type(newer) is list and len(newer)==21 and
               {r["repo"] for r in rows}=={r["repo"] for r in newer},"READBACK_COHORT")
        for r in newer:
            demand(type(r.get("current_head")) is str and SHA.fullmatch(r["current_head"]),"READBACK_HEAD")
            for field in ("owner_J1_navigation_qualified","owner_J2_pages_qualified",
                          "owner_J3_governance_qualified","owner_J4_exact_head_release_ci",
                          "owner_J5_point_release"):
                demand(r.get(field) in (None,False),"UNAUTHENTICATED_READINESS")
    return sorted(rows,key=lambda r:r["rank"])

def topo(nodes,edges):
    ids={n["id"] for n in nodes}
    demand(len(ids)==len(nodes),"DUPLICATE_NODE")
    incoming={u:0 for u in ids}
    children=defaultdict(set)
    for e in edges:
        u,v=e["from"],e["to"]
        demand(u in ids and v in ids and u!=v,"DANGLING_EDGE")
        demand(v not in children[u],"DUPLICATE_EDGE")
        children[u].add(v)
        incoming[v]+=1
    left=set(ids)
    layers=[]
    while left:
        ready=sorted(u for u in left if incoming[u]==0)
        demand(bool(ready),"EXECUTABLE_DAG_CYCLE")
        layers.append(ready)
        for u in ready:
            left.remove(u)
            for v in children[u]:
                incoming[v]-=1
    return layers

def build(source,readback=None):
    rows=validate(source,readback)
    newer={r["repo"]:r["current_head"] for r in readback["rows"]} if readback else {}
    nodes=[{"id":"portfolio:Top21","type":"COHORT","status":"DATED_HISTORICAL_CENSUS"}]
    edges=[]
    def link(a,b):
        edges.append({"from":a,"to":b,"kind":"REQUIRES","evidence":"DECLARED_ONLY"})
    for r in rows:
        repo=r["repo"]
        prefix=repo+"::"
        head=newer.get(repo,r["head_readback"])
        for stage in GATES:
            status=("J0_OBSERVED_HISTORICAL" if stage=="J0" else
                    "DEFERRED_OWNER" if stage in {"J2","J3","J4","J5"} else
                    "PROPOSED_UNVERIFIED")
            nodes.append({"id":prefix+stage,"repo":repo,"gate":stage,
                          "source_head":head,"priority":r["priority"],
                          "status":status,"executor_enabled":False,
                          "release_credit":0,"owner":r.get("owner_role"),
                          "origin":(r.get("candidate_issue_links") or
                                    ["https://github.com/"+repo])[0]})
        link("portfolio:Top21",prefix+"J0")
        for stage in ("J1","COVERAGE","ADVERSARIAL","INTEGRATION","RUNNERS","CAUSE","SUPPLY","J3"):
            link(prefix+"J0",prefix+stage)
        link(prefix+"J1",prefix+"J2")
        for stage in ("J1","COVERAGE","ADVERSARIAL","INTEGRATION","RUNNERS",
                      "CAUSE","SUPPLY","J2","J3"):
            link(prefix+stage,prefix+"J4")
        link(prefix+"J4",prefix+"J5")
    layers=topo(nodes,edges)
    children=defaultdict(set)
    for e in edges:children[e["from"]].add(e["to"])
    pressure={}
    for r in rows:
        u=r["repo"]+"::J0"
        seen=set()
        pending=list(children[u])
        while pending:
            v=pending.pop()
            if v in seen:continue
            seen.add(v)
            pending.extend(children[v])
        pressure[r["repo"]]={"direct_dependents":len(children[u]),
                             "reachable_unique":len(seen),
                             "verified_unlocks":None}
    metrics=[{"axis":axis,"unit":unit,"owner":owner,"numerator":None,
              "denominator":None,"measurement_state":"UNKNOWN_NOT_ZERO",
              "source_population":"MISSION_SELECTED_TOP21"}
             for axis,unit,owner in AXES]
    sipoc=[{"axis":axis,"supplier":owner,
            "input":"exact source SHA + eligible opportunity census",
            "process":"source census -> local preflight -> native proof -> independent review",
            "output":unit+" with explicit proof numerator/denominator",
            "customer":"JADE_CASTE projection and source-owning reviewer"}
           for axis,unit,owner in AXES]
    work=[{"repo":r["repo"],"priority":r["priority"],"source_sha":newer.get(r["repo"],r["head_readback"]),
           "owner_action":r["next_point_release_todo"],
           "origin_issue_links":r.get("candidate_issue_links",[]),
           "structural_downstream":pressure[r["repo"]]["reachable_unique"],
           "next_permission":"SOURCE_OWNER_ONLY","dispatch":"STAGED_NOT_TRIGGERED"}
          for r in rows]
    return {"schema":SCHEMA,"cohort":"MISSION_SELECTED_TOP21","point_release":"TARGET_NOT_ACHIEVED",
            "admission":"HOLD","authority_transfer":False,"security_waiver":False,
            "source_class":"NON_ATOMIC_HISTORICAL_AND_READONLY_N2",
            "readback_included":readback is not None,
            "graph":{"nodes":nodes,"edges":edges,"layers":layers},
            "pressure":pressure,"dimensions":metrics,"sipoc":sipoc,"work_orders":work,
            "summary":{"inventory_observed":{"numerator":21,"denominator":21},
                       "owner_action_candidates":21,
                       "priority_population":{"P0":5,"P1":9,"P2":7},
                       "verified_owner_closures":None,
                       "J1_to_J5_qualified":None,
                       "source_coverage":None,
                       "point_releases_qualified":None},
            "pools":{"local_python_planned":2,"local_python_observed":None,
                     "browser_observed":None,"native_runner_slots":None,
                     "owner_review_slots":None,"long_dependency_policy":"DEFER_NO_WORKER_SLOT",
                     "queue_p95_seconds":None,"dispatch_count":0}}

def mermaid(data):
    return """flowchart LR
  T[Mission-selected Top21] --> J0[J0 inventory]
  J0 --> J1[J1 navigation]
  J0 --> FIVE[Five independent engineering dimensions]
  J0 --> SUP[Supply chain]
  J0 --> J3[J3 governance]
  J1 --> J2[J2 hosted Pages]
  J1 --> J4{J4 qualified candidate?}
  FIVE --> J4
  SUP --> J4
  J2 --> J4
  J3 --> J4
  J4 -->|source owner only| J5[J5 POINT RELEASE target]
  LONG[Long external wait] -.->|defer no worker| J2
  LONG -.-> J3
"""

def stage_svg():
    """Human-scale owner-gate view; full 253-node DAG remains in receipt JSON."""
    return '''<div class="scroll" role="region" aria-label="JADE gated readiness DAG">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1110 300" width="1100" height="300" role="img" aria-label="Source census to owner point release, including deferred gate paths">
<defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7 Z" fill="#94b9da"/></marker></defs>
<g fill="none" stroke="#91b5d4" stroke-width="2" marker-end="url(#arrow)">
<path d="M153 153 H185"/><path d="M310 153 H340"/><path d="M255 120 V50 H340"/>
<path d="M255 120 V50 H600"/><path d="M255 177 V250 H505"/><path d="M465 153 H505"/>
<path d="M635 153 H775"/><path d="M570 82 V108 H835 V122"/>
<path d="M740 50 H835 V122"/><path d="M635 250 H835 V177"/>
<path d="M910 153 H950"/>
</g>
<g font-family="system-ui,Arial" font-size="12" text-anchor="middle">
<a href="#owners"><rect x="20" y="122" width="133" height="60" rx="8" fill="#1f3755" stroke="#62b3df"/><text x="86" y="147" fill="#eff8ff">Top21 source</text><text x="86" y="166" fill="#a9c2dc">Historical census</text></a>
<rect x="185" y="122" width="125" height="60" rx="8" fill="#173d39" stroke="#50aa8c"/><text x="247" y="147" fill="#eaf9f3">J0 INVENTORY</text><text x="247" y="167" fill="#8dd8bf">21 / 21 observed</text>
<a href="#dimensions"><rect x="340" y="122" width="125" height="60" rx="8" fill="#233147" stroke="#6195bd" stroke-dasharray="4 3"/><text x="402" y="147" fill="#f0f4fb">J1 NAVIGATION</text><text x="402" y="167" fill="#b4c6d8">Unverified</text></a>
<a href="#dimensions"><rect x="340" y="15" width="235" height="67" rx="8" fill="#322b51" stroke="#ab9de8" stroke-dasharray="4 3"/><text x="457" y="39" fill="#f0f0ff">5 ENGINEERING AXES</text><text x="457" y="58" fill="#cec2f7">Coverage · faults · integration</text><text x="457" y="73" fill="#cec2f7">Runners · first-red</text></a>
<rect x="600" y="15" width="140" height="67" rx="8" fill="#27384a" stroke="#81b1d6" stroke-dasharray="4 3"/><text x="670" y="43" fill="#f1f7ff">SUPPLY CHAIN</text><text x="670" y="62" fill="#bcd5e9">Proof pending</text>
<a href="#dimensions"><rect x="505" y="122" width="130" height="60" rx="8" fill="#43351d" stroke="#e4b869" stroke-dasharray="4 3"/><text x="570" y="148" fill="#fff5de">J2 HOSTED</text><text x="570" y="167" fill="#f5d399">Owner / deferred</text></a>
<a href="#dimensions"><rect x="505" y="220" width="130" height="60" rx="8" fill="#43351d" stroke="#e4b869" stroke-dasharray="4 3"/><text x="570" y="246" fill="#fff5de">J3 GOVERNANCE</text><text x="570" y="266" fill="#f5d399">Owner / deferred</text></a>
<rect x="775" y="122" width="135" height="60" rx="8" fill="#42352c" stroke="#e6b177"/><text x="842" y="147" fill="#fff4e8">J4 CANDIDATE</text><text x="842" y="167" fill="#f1c897">Not qualified</text>
<rect x="950" y="122" width="140" height="60" rx="8" fill="#452735" stroke="#e88caa"/><text x="1020" y="147" fill="#fff0f3">J5 POINT RELEASE</text><text x="1020" y="167" fill="#f8bdcc">TARGET · HOLD</text>
</g>
<text x="20" y="295" fill="#a8bad1" font-size="12">Solid = prerequisite · dashed border = proof pending · no remote worker dispatched</text>
</svg></div>'''


def render_html(data):
    card=lambda x,y:"<article><strong>"+html.escape(str(x))+"</strong><p>"+html.escape(str(y))+"</p></article>"
    cards="".join([card("21 / 21","Historical J0 inventory"),card("21","Owner TODOs"),
                   card(len(data["graph"]["nodes"]),"DAG nodes"),
                   card(len(data["graph"]["edges"]),"DAG edges"),
                   card("UNKNOWN","J4-ready"),card("HOLD","J5 point-release")])
    dims="".join("<tr><td>"+html.escape(x["axis"])+"</td><td>"+html.escape(x["unit"])+
                 "</td><td>UNKNOWN / UNKNOWN</td><td>"+html.escape(x["owner"])+"</td></tr>"
                 for x in data["dimensions"])
    work="".join("<tr><td>"+html.escape(r["priority"])+"</td><td><a href='https://github.com/"+
                 html.escape(r["repo"])+"'>"+html.escape(r["repo"])+"</a></td><td>"+
                 html.escape(r["owner_action"])+"</td><td>STAGE ONLY</td></tr>"
                 for r in data["work_orders"])
    css="""body{margin:0;background:#10192a;color:#ecf2fa;font:14px/1.5 system-ui,sans-serif}
    main{margin:auto;max-width:1370px;padding:22px}a{color:#9fd7fb}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
    article{background:#1b2a42;border:1px solid #334f68;border-radius:10px;padding:12px}
    strong{font-size:26px}article p{color:#b6c3d7}section{margin-top:22px}
    .scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:12px}
    td,th{border-bottom:1px solid #324660;text-align:left;padding:8px}
    th{color:#aacfe4}h1{font-size:25px}
    summary{cursor:pointer}details{background:#1a283e;padding:14px;border-radius:10px}
    """
    doc="<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
    doc+="<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'\">"
    doc+="<title>JADE_CASTE · Point-release sprint target</title><style>"+css+"</style></head><body><main>"
    doc+="<h1>JADE_TEMPLE · POINT RELEASE preparation</h1><p>Source-bound readiness projection, not a released outcome. No live GitHub connection.</p>"
    doc+="<div class='grid'>"+cards+"</div>"
    doc+="<section><h2>Gated DAG sequence · source to owner release</h2>"+stage_svg()+"<details><summary>Expand SIPOC, resource and dependency boundaries</summary><p>Local QA, source coverage, adversarial penetration, integration, platform reach, first-red, supply chain and hosted Pages are separate proof lanes. External approvals and long CI dependencies are deferred, not worker-occupied. Machine DAG and SIPOC are companion JSON files.</p></details></section>"
    doc+="<section><h2>Worker pools · queue pressure · caching</h2><div class=grid>"+card("2 planned","Local Python slots; not a measured native pool")+card("UNKNOWN","GitHub Actions free/occupied slots")+card("UNKNOWN","Native queue P95")+card("LOCAL ONLY","Content-hash cache never creates release credit")+"</div></section>"
    doc+="<section id="dimensions"><h2>15 independent dimensions</h2><div class='scroll'><table><tr><th>Dimension</th><th>Unit</th><th>Qualified N/D</th><th>Owner</th></tr>"+dims+"</table></div></section>"
    doc+="<section id="owners"><h2>Owner work-order queue — staged only</h2><div class='scroll'><table><tr><th>Priority</th><th>Repo</th><th>Required next action</th><th>Permission</th></tr>"+work+"</table></div></section>"
    doc+="<p>J0 source identity is not J1 quality. Cached local successes cannot replace native CI, HTTPS parity, security, reviewers or point-release approval.</p></main></body></html>\n"
    return doc
