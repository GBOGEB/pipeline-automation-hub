#!/usr/bin/env python3
"""Read-only federation landing derived from canonical MissionControl registries.

No GitHub writes, no external network, no agent dispatch. Local/CI rendering only.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
from pathlib import Path

SCHEMA = "code-purple.federation.landing-projection.v1"
SHA = re.compile(r"^[a-f0-9]{40}$")
ROOT = Path(__file__).resolve().parents[1]

INPUTS = {
    "sipoc": "PROCESS_LANES_v1.json",
    "dag": "CODE_PURPLE_BEAMS_DAG_v1.json",
    "history": "FEDERATION_OBSERVED_PULSES_v1.json",
    "bd": "flightdeck/pulses/BD_CHAR_SFED_20261016_P2.json",
}
REPOS = [
    ("ABACUS / DOW", "ABACUS", "Source repair, CI, DMAIC", "docs/index.html"),
    ("CODEX / KEB", "CODEX", "Semantic contracts and federation governance", "docs/index.html"),
    ("QPS / Cryoplant", "cryoplant-project", "OCD/ADR engineering owner", "triage/code_purple/CODE_PURPLE_OPERATIONS.html"),
    ("MissionControl", "pipeline-automation-hub", "Orchestration and read-only projections", "docs/index.html"),
    ("gg_MATH", "gg_MATH", "Statistical provider, PCA and Bradley–Terry", "release/build_release.py"),
]


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def input_data(root=ROOT):
    data, hashes = {}, {}
    for key, rel in INPUTS.items():
        b = (Path(root) / rel).read_bytes()
        data[key] = json.loads(b)
        hashes[rel] = hashlib.sha256(b).hexdigest()
    return data, hashes


def validate(data):
    p, g, h, b = (data[k] for k in ("sipoc", "dag", "history", "bd"))
    require(p.get("schema") == "missioncontrol.federation_atlas.process_lanes.v1", "SIPOC schema drift")
    require(g.get("schema") == "missioncontrol.code_purple.beams_dag.v1", "DAG schema drift")
    require(p.get("observer_authority") == "READ_ONLY"
            and g.get("authority_transfer") is False
            and g.get("formal_credit_delta") == 0, "source authority drift")
    require({x["key"] for x in p["sipoc"]} == {"S", "I", "P", "O", "C"},
            "SIPOC members invalid")
    beams = g.get("beams", [])
    ids = {x["id"] for x in beams}
    require(ids and len(ids) == len(beams), "empty or duplicated beams")
    require(isinstance(p.get("lanes"), list) and p["lanes"], "empty process lanes")
    for e in g.get("edges", []):
        require(e.get("from") in ids and e.get("to") in ids and
                e.get("type") in ("FEEDBACK", "FEEDFORWARD"), "invalid edge")
    require("NEXT pulse" in g.get("edge_rule", ""), "feedback clock unqualified")
    require(h.get("schema") == "missioncontrol.federation.observed_pulses/v1", "history schema")
    require(b.get("schema") == "code-purple.bd-char.sfed-pulse.v1", "BD pulse schema")
    a = b.get("authority", {})
    require(a.get("merge_admission") == "HOLD" and a.get("security_waiver") is False
            and a.get("authority_transfer") is False and
            a.get("accepted_root_closed") is None, "BD authority inversion")
    return data


def _qps_waves(observations):
    groups = {}
    for row in observations:
        if row.get("repo") != "GBOGEB/cryoplant-project" or row.get("wave") != "QPS_WORMHOLE_COVERAGE":
            continue
        key = (row["wave"], row["pulse"])
        groups.setdefault(key, []).append(row)
    output = []
    for (wave, pulse), rows in sorted(groups.items(), key=lambda kv: kv[0][1]):
        denoms = {((r.get("line") or {}).get("eligible"), (r.get("branch") or {}).get("eligible")) for r in rows}
        nums = {((r.get("line") or {}).get("covered"), (r.get("branch") or {}).get("covered")) for r in rows}
        shas = {r["head_sha"] for r in rows}
        statuses = {r["status"] for r in rows}
        if len(denoms) != 1 or len(nums) != 1 or len(shas) != 1 or (None, None) in denoms:
            output.append({"wave": wave, "pulse": pulse, "comparable": False,
                           "reason": "population or source-version disagreement", "line": None, "branch": None})
            continue
        line, branch = next(iter(nums))
        line_d, branch_d = next(iter(denoms))
        output.append({"wave": wave, "pulse": pulse, "comparable": True,
                       "head_sha": next(iter(shas)), "line": {"covered": line, "eligible": line_d},
                       "branch": {"covered": branch, "eligible": branch_d},
                       "python_cohorts": sorted({str(r["python"]) for r in rows}),
                       "status": next(iter(statuses)) if len(statuses) == 1 else "MIXED",
                       "run_ids": sorted({r["run_id"] for r in rows}),
                       "scope": "HISTORICAL_QPS_WORMHOLE_TWO_FILES"})
    return output


def projection(data, input_hashes, exact_sha):
    validate(data)
    require(isinstance(exact_sha, str) and SHA.fullmatch(exact_sha), "exact checkout SHA absent")
    p, g, h, b = (data[k] for k in ("sipoc", "dag", "history", "bd"))
    stage_count = sum(len(l["stages"]) for l in p["lanes"])
    graph = {
        "nodes": [{"id": x["id"], "title": x["title"], "kind": x["kind"], "lane": x["lane"]}
                  for x in g["beams"]],
        "edges": [{"from": x["from"], "to": x["to"], "type": x["type"]} for x in g["edges"]],
        "edge_rule": g["edge_rule"],
    }
    c2 = b["matched_historical_coverage"]
    require(c2["before"]["eligible"] == c2["after"]["eligible"] and
            c2.get("current_main") is None, "coverage scope changed")
    return {
        "schema": SCHEMA, "exact_checkout_sha": exact_sha,
        "sources_sha256": input_hashes,
        "population": {"lanes": len(p["lanes"]), "stages": stage_count,
                       "beams": len(graph["nodes"]), "edges": len(graph["edges"]),
                       "repositories": len(REPOS)},
        "sipoc": p["sipoc"], "graph": graph,
        "history": {"qps_wormhole": _qps_waves(h["observations"]),
                    "c2_pr_matched_historical": c2,
                    "bd_pulse": b.get("pulse"),
                    "bd_current_main_uplift": None},
        "repos": [{"name": label, "slug": slug, "role": role, "source_page": page,
                   "repository_url": "https://github.com/GBOGEB/" + slug,
                   "source_page_url": "https://github.com/GBOGEB/" + slug + "/blob/"
                                      + ("master" if slug == "pipeline-automation-hub" else "main") + "/" + page,
                   "hosted_verified": None} for label, slug, role, page in REPOS],
        "admission": {"engineering": "QPS_OWNER_ONLY", "merge": "HOLD",
                      "security_waiver": False, "authority_transfer": False,
                      "worker_dispatch": "STAGED_NOT_LAUNCHED",
                      "native_cross_repo_chain": None, "current_main_coverage": None},
        "methodology": {
            "same_wave": "FEEDFORWARD only",
            "next_wave": "FEEDBACK(N) -> input(N+1)",
            "supplier_next": "Only a verified N-1 output accepted by the next owner may supply N",
            "customer": "Downstream owner of current N output, not assumed to authorize N+1",
        },
        "grade": "READ_ONLY_STATIC_PROJECTION_NOT_DEPLOY_RECEIPT",
    }


def esc(x):
    return html.escape(str(x), quote=True)


def render(d):
    pop, graph, history = d["population"], d["graph"], d["history"]
    repo_cards = []
    for r in d["repos"]:
        repo_cards.append('<article class="card"><div class="meta">SOURCE ONLY · HOSTED UNVERIFIED</div>'
                          '<h3>'+esc(r["name"])+'</h3><p>'+esc(r["role"])+'</p>'
                          '<p><a href="'+esc(r["repository_url"])+'">Repository</a> · '
                          '<a href="'+esc(r["source_page_url"])+'">Landing source</a></p></article>')
    beam_rows = []
    for n in graph["nodes"]:
        beam_rows.append('<button class="beam" type="button" data-beam="'+esc(n["id"])+'"><b>'
                         +esc(n["id"])+'</b><span>'+esc(n["title"])+'</span></button>')
    sipoc = ''.join('<article class="card"><h3>'+esc(x["key"])+' / '+esc(x["name"])+
                    '</h3><p>'+esc(x["detail"])+'</p><small>'+esc(x["constraint"])+
                    '</small></article>' for x in d["sipoc"])
    wave_rows = []
    for w in history["qps_wormhole"]:
        if w["comparable"]:
            c,e = w["line"]["covered"],w["line"]["eligible"]
            b,be = w["branch"]["covered"],w["branch"]["eligible"]
            wave_rows.append('<tr><th>Pulse '+str(w["pulse"])+'</th><td>'+str(c)+'/'+str(e)+
                             ' ('+f"{100*c/e:.1f}"+'%)</td><td>'+str(b)+'/'+str(be)+
                             ' ('+f"{100*b/be:.1f}"+'%)</td><td>'+esc(w["status"])+
                             '</td><td>'+esc(",".join(w["python_cohorts"]))+'</td></tr>')
        else:
            wave_rows.append('<tr><th>Pulse '+str(w["pulse"])+'</th><td colspan="4">NOT COMPARABLE</td></tr>')
    c2 = history["c2_pr_matched_historical"]
    numerator = c2["after"]["covered"]-c2["before"]["covered"]
    percent = 100*numerator/c2["before"]["eligible"]
    model = json.dumps(graph, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="dark">
<title>CODE PURPLE — Federation Home / recursive SIPOC</title>
<style>
:root{--bg:#0d1625;--ink:#edf4fc;--surface:#182940;--line:#36516d;--muted:#bdd0e1;--mint:#9de6d2;--amber:#eacb94;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,Segoe UI,sans-serif}
main{max-width:1260px;margin:auto;padding:28px 18px 70px}h1{font-size:clamp(28px,4vw,48px);line-height:1.1;margin:15px 0}h2{margin:32px 0 12px;font-size:23px}h3{margin:4px 0}
a{color:#9ddaff}nav{display:flex;flex-wrap:wrap;gap:13px}nav a{border-bottom:1px solid #6389aa;text-decoration:none;padding:4px}
.card{border:1px solid var(--line);background:var(--surface);border-radius:12px;padding:15px;min-width:0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(225px,1fr));gap:12px}.meta,small{font-size:12px;color:var(--muted)}
.hold{color:var(--amber);font-weight:700}.kpi{font-size:26px;font-weight:750;color:var(--mint)}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.stats>div{background:var(--surface);border:1px solid var(--line);padding:14px;border-radius:10px}
.controls{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:12px}select{background:var(--surface);color:var(--ink);border:1px solid var(--line);padding:8px;border-radius:6px}
.beams{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}
.beam{border:1px solid var(--line);background:var(--surface);color:var(--ink);padding:10px;text-align:left;border-radius:9px;cursor:pointer;min-height:85px;display:flex;flex-direction:column}
.beam b{color:var(--mint);font-size:18px}.beam span{font-size:12px}
.beam.active{outline:3px solid var(--mint)}.beam.neighbor{border-color:var(--mint)}.beam.dimmed{opacity:.35}
table{width:100%;border-collapse:collapse;min-width:580px}th,td{padding:10px;border-bottom:1px solid var(--line);text-align:left}
.scroller{overflow-x:auto}.muted{color:var(--muted)}.notice{border-left:4px solid var(--amber);padding:12px 17px;background:var(--surface)}
code{overflow-wrap:anywhere}ol li{margin:8px 0}
@media(max-width:800px){.stats{grid-template-columns:repeat(2,1fr)}.beams{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:380px){main{padding:14px 10px}.beams{grid-template-columns:1fr}}
</style></head><body><main>
<nav aria-label="Federation pages"><a href="../index.html">Mission Control home</a><a href="#fleet">Fleet</a><a href="#sipoc">SIPOC</a><a href="#neighbors">Neighbors</a><a href="#waves">Waves</a><a href="#controls">Controls</a></nav>
<header><div class="meta">GBOGEB · CODE PURPLE · W0 read-only derived view</div><h1>Federation neighborhood & recursive SIPOC</h1>
<p class="muted">Start at your repository. Explore immediate source/evidence neighbors, upstream supplier, downstream consumer, feedback into the next wave and what the historical measurement actually supports.</p>
<p class="notice"><b>Deployment and admission are separate.</b> This artifact is built from frozen source registries; repository Pages reachability, Crew launch and formal root closure are not established by these links.</p></header>
<div class="stats"><div><div class="kpi">'''+str(pop["lanes"])+'''</div><small>process lanes</small></div><div><div class="kpi">'''+str(pop["stages"])+'''</div><small>canonical stages</small></div><div><div class="kpi">'''+str(pop["beams"])+''' / '''+str(pop["edges"])+'''</div><small>beams / edges</small></div><div><div class="kpi">UNKNOWN</div><small>accepted roots closed</small></div></div>
<section id="fleet"><h2>Repository homes / publication routes</h2><div class="grid">'''+''.join(repo_cards)+'''</div></section>
<section id="sipoc"><h2>SIPOC — stage N consumes accepted N−1 output</h2><div class="grid">'''+sipoc+'''</div>
<p class="muted"><b>Handoff rule:</b> supplier S(N) may be an accepted output from N−1; customer C(N) is the next receiving owner. Handoff is not automatic promotion or transferred authority.</p></section>
<section id="neighbors"><h2>Recursive neighborhood (declared graph, not live workers)</h2>
<div class="controls"><label for="beam-choice">Beam <select id="beam-choice">'''+''.join('<option value="'+esc(n["id"])+'">'+esc(n["id"])+' '+esc(n["title"])+'</option>' for n in graph["nodes"])+'''</select></label>
<label for="radius">Radius <select id="radius"><option value="1">1 hop</option><option value="2">2 hops</option><option value="3">3 hops</option></select></label>
<span id="neighbor-count" class="meta" role="status">Source graph</span></div>
<div class="beams">'''+''.join(beam_rows)+'''</div><div class="card" style="margin-top:12px"><b>Declared incident edges</b><p id="edge-detail" class="muted">Select any beam.</p>
<p class="muted">FEEDFORWARD = same-pulse DAG. FEEDBACK = next-pulse edge, never a cycle within a single pulse. The viewer does not launch or schedule processes.</p></div></section>
<section id="waves"><h2>Historical wave statistics — bounded scopes</h2><p>QPS wormhole two-file historical cohort; Python 3.11/3.12 share each pulse source/denominator. Percentages describe the historical scope, not QPS whole-project coverage.</p>
<div class="scroller"><table><thead><tr><th>Wave</th><th>Line coverage</th><th>Branch coverage</th><th>Status</th><th>Python</th></tr></thead><tbody>'''+''.join(wave_rows)+'''</tbody></table></div>
<p>ABACUS C2 historical PR Ubuntu, matched statement scope: <b>'''+str(c2["before"]["covered"])+'''/'''+str(c2["before"]["eligible"])+''' → '''+str(c2["after"]["covered"])+'''/'''+str(c2["after"]["eligible"])+'''</b>; +'''+str(numerator)+''' covered, +'''+f"{percent:.2f}"+''' pp. Different repo, source and method; not plotted as one time series. Current main and current PR diff remain UNKNOWN.</p></section>
<section id="controls"><h2>Execution contract and next W0 decisions</h2><ol>
<li>READ / SCOUT: identify canonical repo/skill, exact source SHA and adjacent graph neighbors.</li>
<li>SEED / SIPOC: pin N−1 output and N input; no default permission inheritance.</li>
<li>LOCAL_STATIC / SELF_SMOKE: run narrow nonblocking cold probes; negative and adversarial tests.</li>
<li>CBD / MIP / DMAIC: disjoint path lease, one source mutation slice per root, source-bound before/after.</li>
<li>NATIVE_CI: qualified exact-head checks, reviewers, independent A10 and security gates.</li>
<li>MERGE / PUBLISH / RECURSE: terminal default-branch CI, authorized Pages deployment, HTTP digest readback and recurrence check.</li></ol>
<p><a href="snapshot.json">Derived JSON projection</a> · <a href="manifest.json">Source/hashes manifest</a> · <a href="https://github.com/GBOGEB/pipeline-automation-hub/blob/master/mission-control/federation-atlas/landing/LANDING_WAVE_PLAN_20261016.md">Evolving W0 plan</a></p>
<p class="meta">Exact checkout: <code>'''+esc(d["exact_checkout_sha"])+'''</code></p></section>
</main><script id="graph-data" type="application/json">'''+model+'''</script>
<script>
(function(){const data=JSON.parse(document.getElementById('graph-data').textContent);
const select=document.getElementById('beam-choice'),radius=document.getElementById('radius');
const btn=[...document.querySelectorAll('.beam')];
function draw(){let seen=new Set([select.value]),frontier=new Set([select.value]),neighbors=[];
for(let i=0;i<Number(radius.value);i++){let next=new Set();for(const e of data.edges){if(frontier.has(e.from))next.add(e.to);if(frontier.has(e.to))next.add(e.from);}
for(const k of next){seen.add(k);}frontier=next;}
for(const b of btn){const id=b.dataset.beam;b.classList.toggle('active',id===select.value);b.classList.toggle('neighbor',id!==select.value&&seen.has(id));b.classList.toggle('dimmed',!seen.has(id));}
for(const e of data.edges){if(e.from===select.value||e.to===select.value)neighbors.push(e.from+' → '+e.to+' ('+(e.type==='FEEDBACK'?'NEXT PULSE':'SAME PULSE')+')');}
document.getElementById('neighbor-count').textContent=seen.size+' of '+btn.length+' beams in '+radius.value+' hop(s)';
document.getElementById('edge-detail').textContent=neighbors.join(' · ')||'No incident edge declared';}
for(const b of btn)b.addEventListener('click',()=>{select.value=b.dataset.beam;draw();});
select.addEventListener('change',draw);radius.addEventListener('change',draw);draw();})();
</script></body></html>'''


def produce(out, exact_sha, root=ROOT):
    data, hashes = input_data(root)
    derived = projection(data, hashes, exact_sha)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(derived, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    (out/"snapshot.json").write_text(encoded, encoding="utf-8")
    page = render(derived)
    (out/"index.html").write_text(page, encoding="utf-8")
    receipt = {
        "schema": "code-purple.federation.landing-manifest.v1",
        "git_sha": exact_sha, "inputs_sha256": hashes,
        "artifact_sha256": {
            x: hashlib.sha256((out/x).read_bytes()).hexdigest()
            for x in ("snapshot.json", "index.html")
        },
        "admission": "HOLD", "hosted_verified": None,
        "evidence_grade": "EXACT_SHA_RENDER_CANDIDATE_NOT_PAGES_DEPLOY",
    }
    (out/"manifest.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--out", required=True)
    a.add_argument("--sha", required=True)
    x = a.parse_args()
    print(json.dumps(produce(x.out, x.sha), sort_keys=True))
