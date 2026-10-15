#!/usr/bin/env python3
"""Render a safe read-only CODE PURPLE sideload review interface from one typed snapshot.

No cluster access, secrets, GitHub mutation, engineering admission or Pages publishing.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "SIDELOAD_OPERATOR_CONTRACT_v1.json"
ALLOWED = {"DECLARED", "LOCAL_HASH_MATCH_ONLY", "NATIVE_METADATA_UNAUTHENTICATED", "K8S_API_UNVERIFIED", "WORKLOAD_UNVERIFIED"}

def validate(obj):
    if obj.get("schema") != "missioncontrol.code-purple.sideload-operator.v1":
        raise ValueError("unsupported schema")
    if obj.get("authority_transfer") is not False or obj.get("formal_credit_delta") != 0 or obj.get("engineering_credit_delta") != 0:
        raise ValueError("unauthorized promotion")
    if obj.get("role") != "READ_ONLY_FEDERATION_PROJECTION":
        raise ValueError("view cannot dispatch")
    if not set(obj.get("trust_levels", [])) == ALLOWED:
        raise ValueError("unexpected transport trust enum")
    lanes = obj.get("lanes", [])
    if len(lanes) != 4 or {x.get("id") for x in lanes} != {"QPS", "KEB", "DOW", "MC"}:
        raise ValueError("four named owner lanes required")
    if any(x.get("status") not in {"HOLD", "CANDIDATE", "OBSERVATION_ONLY"} for x in lanes):
        raise ValueError("source snapshot cannot claim accepted deployment")
    if any(not x.get("repo", "").startswith("GBOGEB/") or not x.get("ref") for x in lanes):
        raise ValueError("unbound source owner")
    defaults = obj.get("safe_defaults", {})
    if defaults.get("engineering_disposition") != "DEFER" or defaults.get("release") != "HOLD":
        raise ValueError("QPS authority gate bypass")
    if any(defaults.get(k) is not None for k in ("cluster_api_proven", "workload_proven", "edge_qualified", "authenticated_hops", "matched_coverage_gain")):
        raise ValueError("unverified proof turned into a number")
    stages = obj.get("promotion_gates", [])
    if [g.get("id") for g in stages] != ["S0","S1","S2","S3","S4","S5"]:
        raise ValueError("promotion stage sequence changed")
    if obj.get("source_contract", {}).get("schema") != "qps.federation.sideload.envelope.v1":
        raise ValueError("KEB contract identity changed")
    return True

def render(obj, telemetry=None):
    validate(obj)
    payload = json.dumps(obj, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    label = lambda s: html.escape(str(s), quote=True)
    cards = "".join(
        '<article class="lane" data-label="'+label(x["id"]+" "+x["label"]+" "+x["observed"])+'">'
        '<div class="small">'+label(x["id"])+' / '+label(x["status"])+'</div>'
        '<h2>'+label(x["label"])+'</h2><p>'+label(x["observed"])+'</p>'
        '<p>'+label(x["action"])+'</p><a rel="noopener noreferrer" target="_blank" href="https://github.com/'+label(x["repo"])+'/blob/HEAD/'+label(x["ref"])+'">Owner source</a></article>'
        for x in obj["lanes"])
    stages = "".join('<tr><td>'+label(g["id"])+'</td><td>'+label(g["name"])+'</td><td>'+label(g["proof"])+'</td><td>UNKNOWN / HOLD</td></tr>' for g in obj["promotion_gates"])
    page = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CODE PURPLE | Sideload Operator</title><style>
:root{color-scheme:dark;font-family:system-ui,Segoe UI,sans-serif;background:#101214;color:#f1f3f5}
body{max-width:1240px;margin:auto;padding:28px}h1{font-size:2rem;letter-spacing:-.03em}
.small,footer{color:#a5abb4;font-size:.82rem}nav{display:flex;flex-wrap:wrap;gap:10px;margin:25px 0}
nav button,input{background:#20252b;color:#f1f3f5;border:1px solid #505862;border-radius:8px;padding:10px}
button{cursor:pointer}button[aria-pressed=true]{background:#344861}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(225px,1fr));gap:13px}
.lane{border:1px solid #454951;border-radius:12px;padding:18px;background:#1a1f24;min-height:190px}
a{color:#9cd3fa}p{line-height:1.45}table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #434950;padding:12px}
h2{font-size:1.1rem}input{width:min(95%,350px)}.notice{border-left:3px solid #a6a9b0;padding:10px 18px;margin:16px 0;background:#1a1f24}
@media(max-width:650px){body{padding:14px}table{font-size:.75rem}td,th{padding:6px}}
</style></head><body><header><div class="small">MISSION CONTROL / READ-ONLY / SNAPSHOT: """+label(obj["source_snapshot"])+"""</div>
<h1>CODE PURPLE — Side-loading &amp; Kubernetes</h1>
<p>Four source owners, one transport vocabulary. No deployment or engineering ACCEPT implied.</p>
<div class="notice"><strong>Admission HOLD · QPS disposition DEFER</strong><p>Cluster API, workload, edge and artifact byte proof remain UNKNOWN unless linked native receipts are independently authenticated.</p></div></header>
<nav aria-label="Filter sources"><button type="button" data-filter="ALL" aria-pressed="true">All lanes</button>
<button type="button" data-filter="QPS" aria-pressed="false">QPS</button>
<button type="button" data-filter="KEB" aria-pressed="false">KEB</button>
<button type="button" data-filter="DOW" aria-pressed="false">DOW</button>
<button type="button" data-filter="MC" aria-pressed="false">MissionControl</button>
<input id="search" aria-label="Search source cards" placeholder="Search owner, blocker or lane"></nav>
<section class="cards" id="lanes" aria-label="Source owner lanes">"""+cards+"""</section>
<h2>Proof ladder (non-compensating)</h2><table><thead><tr><th>Stage</th><th>Gate</th><th>Required evidence</th><th>C2 proof state</th></tr></thead><tbody>"""+stages+"""</tbody></table>
<h2>Observability fields</h2><p>"""+label(" · ".join(obj["metrics"]))+"""</p>
<footer>Source-controlled projection only. Canonical transport remains CODEX, runtime DOW, child authority QPS. Versioned output is an Actions artifact candidate, not a Pages release.</footer>
<script id="source" type="application/json">"""+payload+"""</script>
<script>
const cards=[...document.querySelectorAll('.lane')];let selected='ALL';
function filter(){let text=document.getElementById('search').value.toLowerCase();cards.forEach(c=>{c.hidden=!(selected==='ALL'||c.dataset.label.startsWith(selected+' '))||!c.dataset.label.toLowerCase().includes(text)})}
document.getElementById('search').addEventListener('input',filter);
document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{selected=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));filter()}));
</script></body></html>"""

    if telemetry is None:
        return page
    if telemetry.get("schema") != "missioncontrol.sideload.w169.telemetry-projection.v1":
        raise ValueError("unsupported runtime telemetry schema")
    if telemetry.get("source_class") != "HISTORICAL_EXACT_SHA_NATIVE_ARTIFACT_LOCALLY_HASH_VERIFIED":
        raise ValueError("untrusted W169 runtime class")
    if telemetry.get("qps_disposition") != "DEFER" or telemetry.get("release") != "HOLD" or telemetry.get("authority_transfer") is not False:
        raise ValueError("runtime cannot grant engineering approval")
    row=telemetry.get("metrics", {})
    for field in ("request_p95_ms", "cold_start_p95_seconds", "restart_count"):
        if isinstance(row.get(field), bool) or not isinstance(row.get(field), (int, float)):
            raise ValueError("unverified runtime metric")
    if any(v is not None for v in telemetry.get("unbound", {}).values()):
        raise ValueError("unknown metric falsely promoted")
    section=(
        '<section aria-label="Native W169 observed telemetry" class="notice">'
        '<h2>W169 real Kubernetes: one exact-head run</h2>'
        '<p>Source: '+label(telemetry["source_sha"])+' · run '
        +label(telemetry["source_run_id"])+' / job '+label(telemetry["source_job_id"])
        +' / attempt '+label(telemetry["attempt"])+'</p>'
        '<p>Cluster API and workload: native success on this run, not QPS ACCEPT or edge deployment.</p>'
        '<p>Request p95: '+label(round(row["request_p95_ms"],2))+' ms · Cold-start p95: '
        +label(round(row["cold_start_p95_seconds"],2))+' s · Restarts: '+label(row["restart_count"])+'</p>'
        '<p>Fleet proof yield, queue p95, CPU/memory peaks, side-load rejection rate, '
        'first-red propagation and edge qualification: UNKNOWN (unbound evidence).</p>'
        '<a rel="noopener noreferrer" target="_blank" href="'+label(telemetry["source_url"])+'">W169 original native artifact</a>'
        '</section>'
    )
    return page.replace("<h2>Observability fields</h2>",section+"<h2>Observability fields</h2>")


def build(out, src=SOURCE, telemetry_path=None):
    obj=json.loads(Path(src).read_text(encoding="utf-8"))
    telemetry=json.loads(Path(telemetry_path).read_text(encoding="utf-8")) if telemetry_path else None
    page=render(obj, telemetry).encode("utf-8")
    out=Path(out);out.mkdir(parents=True, exist_ok=True)
    (out/"sideload-operator.html").write_bytes(page)
    sha=hashlib.sha256(page).hexdigest()
    receipt={"schema":"missioncontrol.code-purple.sideload-ui-receipt.v1","source_sha256":hashlib.sha256(Path(src).read_bytes()).hexdigest(),"html_sha256":sha,"source_class":"STATIC_SOURCE_DECLARATION","native_cluster_receipt":None,"admission":"HOLD","authority_transfer":False}
    (out/"sideload-operator-receipt.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return receipt

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True);p.add_argument("--source",default=str(SOURCE));p.add_argument("--telemetry")
    a=p.parse_args()
    print(json.dumps(build(a.out,a.source,a.telemetry),sort_keys=True))
