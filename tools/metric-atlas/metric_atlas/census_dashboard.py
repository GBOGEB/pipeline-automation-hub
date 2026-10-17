"""Offline source-bound QPS census dashboard (standard library only)."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from .census import SCHEMA


def cohort(ledger, scope):
    points = sorted(
        (x for x in ledger.get("measurements", [])
         if x.get("scope_id") == scope and x.get("metric") == "tests_passed"
         and x.get("state") != "SIMULATED" and type(x.get("value")) in (int, float)),
        key=lambda x: x["step"],
    )
    if not points:
        return {"scope": scope, "baseline": None, "latest": None,
                "delta": None, "index": None}
    first, last = points[0]["value"], points[-1]["value"]
    return {"scope": scope, "baseline": first, "latest": last,
            "delta": last-first if len(points) >= 2 else None,
            "index": round(last/first*100, 3) if first > 0 else None,
            "points": len(points)}


def render(manifest, rollup, ledger):
    if manifest.get("schema") != SCHEMA or rollup.get("schema") != "qps-metric-rollup/v1":
        raise ValueError("bad census source schemas")
    if manifest.get("wave") != rollup.get("wave"):
        raise ValueError("manifest/rollup wave mismatch")
    counts = [cohort(ledger, "MC:METHOD_ATLAS"), cohort(ledger, "ABACUS:PY312_SUITE")]
    counts[0]["label"], counts[1]["label"] = "Method Atlas", "ABACUS Python 3.12"
    series = json.dumps(counts, separators=(",", ":")).replace("<", "\\u003c")
    lanes = rollup["lanes"]
    rows = "".join(
        "<tr><td><strong>{}</strong></td><td><code>{}</code></td><td>{}</td><td>{}</td></tr>".format(
            html.escape(r["repo"]), html.escape(r["head_sha"][:12] if r["head_sha"] else "UNKNOWN"),
            html.escape("RECEIVED" if r["routes_received"] else (
                "HOLD_SOURCE_HEAD_UNKNOWN" if r["head_sha"] is None else "PLANNED_NOT_DISPATCHED")),
            html.escape(", ".join(r["routes_received"]) or "none")
        ) for r in lanes
    )
    kpis = [("Eligible producers", manifest.get("eligible_repos", 3)),
            ("Source heads accessible", manifest.get("dispatchable_repos", 0)),
            ("Private/source unknown", manifest.get("unknown_head_repos", 0)),
            ("Observed receiver repos", rollup.get("observed_repos", 0)),
            ("Native receiver job receipts", rollup.get("native_job_receipts", 0)),
            ("Measured test/coverage uplift", "UNKNOWN")]
    cards = "".join('<div class="kpi"><b>{}</b><span>{}</span></div>'.format(
        html.escape(str(val)), html.escape(label)) for label,val in kpis)
    return """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>QPS TRIAGE Metric Census</title><style>
:root{--navy:#15304d;--ink:#1c3046;--sub:#6e7e90;--edge:#d9e1ec;--paper:#f5f7fa;--ok:#167768;--bar:#276aca}
*{box-sizing:border-box}body{margin:0;background:var(--paper);font:15px/1.5 system-ui,sans-serif;color:var(--ink)}
header{background:var(--navy);color:white;padding:26px max(22px,calc((100vw - 1220px)/2))}header h1{margin:0;font-size:27px}header p{opacity:.88;margin:5px 0 0}
main{max-width:1220px;margin:auto;padding:22px}.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.kpi,.panel{border:1px solid var(--edge);background:white;border-radius:11px;padding:17px;margin-bottom:16px}
.kpi b{display:block;font-size:29px}.kpi span,.sub{color:var(--sub);font-size:13px}h2{font-size:19px;margin:0 0 10px}
table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid var(--edge);padding:9px;text-align:left;font-size:13px}
th{text-transform:uppercase;color:var(--sub);font-size:11px}code{font-size:12px}.flow{display:flex;flex-wrap:wrap;align-items:center;gap:9px}.flow span{background:#ebf3fd;border:1px solid #d2e2f9;border-radius:7px;padding:10px 8px;flex:1;text-align:center;min-width:120px}
.flow em{color:#7c8da0}button{background:#eaf2fa;border:1px solid #a7baca;border-radius:6px;padding:7px 11px;margin:0 6px 8px 0;cursor:pointer}
.barline{display:flex;gap:12px;align-items:center;margin:13px 0}.barline .label{width:180px;font-size:13px}.barline .track{flex:1;background:#e8eef7;border-radius:5px;height:24px;overflow:hidden}.barline .fill{height:24px;background:var(--bar);border-radius:5px}.barline small{width:100px;text-align:right}
.notice{border-left:3px solid #bf8841;background:#fffbf2;padding:10px 14px;font-size:13px}footer{padding:30px;color:var(--sub);font-size:12px}
@media(max-width:720px){.kpis{grid-template-columns:repeat(2,1fr)}.barline .label{width:120px}}
</style><header><h1>QPS TRIAGE · Federation Metric Atlas</h1><p>Wave __WAVE__ · Disjoint evidence, normalized test growth and source-bound execution · read-only</p></header><main>
<section class="kpis">__CARDS__</section>
<section class="panel"><h2>1. Cross-repo canonical census</h2><p class="sub">The eligible denominator remains 3 even when a private head is inaccessible. A planned request is not a received job or an executed test.</p>
<table><tr><th>Producer</th><th>Source head</th><th>Census state</th><th>Observed routes</th></tr>__ROWS__</table></section>
<section class="panel"><h2>2. Two independent test scales</h2><p class="sub">Choose an honest comparison: current stock, marginal passing-test growth, or cohort-normalized index. N denotes each cohort's latest observation, not the same GitHub commit.</p>
<button onclick="plot('stock')">Current stock</button><button onclick="plot('delta')">Absolute Δ tests</button><button onclick="plot('relative')">Normalized index, baseline = 100</button>
<div id="bars"></div><div class="notice">These are prior source-reported longitudinal measurements, not new N1 receiver test executions. A large stock does not necessarily imply the highest marginal progress, coverage or yield.</div></section>
<section class="panel"><h2>3. DAG / bounded triggered fan-out</h2><div class="flow"><span>Mission Control census N</span><em>→</em><span>Pin exact repo heads</span><em>→</em><span>Two disjoint jobs per source</span><em>→</em><span>Source-bound receipts</span><em>→</em><span>Roll-up and root attribution</span><em>→</em><span>Owner decision N+1</span></div>
<p class="sub">Current mode: plan and dry-run only. Live event dispatch requires owner input on master and separately authorized token. GitHub checks and test file counts are not functional test results.</p></section>
<section class="panel"><h2>4. SIPOC / owner boundaries</h2><table><tr><th>Supplier</th><th>Input</th><th>Process</th><th>Output</th><th>Customer</th></tr>
<tr><td>QPS TRIAGE / owners</td><td>Immutable SHA and route</td><td>Validate request</td><td>Bounded census job</td><td>Repository CI</td></tr>
<tr><td>ABACUS, CODEX, QPS</td><td>GitHub run/job/attempt, source tree</td><td>Collect read-only check and test-file census</td><td>Metadata receipts</td><td>Metric Atlas</td></tr>
<tr><td>Mission Control #530</td><td>Native artifact ZIP</td><td>Verify byte integrity</td><td>Verified receipt/UNKNOWN</td><td>Federation ledger</td></tr>
<tr><td>Domain owners</td><td>Security/root/coverage evidence</td><td>Accept/HOLD</td><td>Governed next pulse</td><td>GoGREEN CONTROL</td></tr></table></section>
<footer>No waiver, merge credit, engineering acceptance or fabricated cross-repository coverage. #530 ZIP verifier, #531 six-repo breadth producer, #533 viewer remain separate.</footer></main><script>
const cohorts=__SERIES__;
function plot(mode){const vals=cohorts.map(x=>mode==='stock'?x.latest:mode==='delta'?x.delta:x.index);const max=Math.max(1,...vals.filter(v=>v!==null&&v>0));
const el=document.getElementById('bars');el.innerHTML=cohorts.map((c,i)=>{const v=vals[i],frac=v===null?0:100*v/max;
return '<div class="barline"><div class="label">'+c.label+'</div><div class="track"><div class="fill" style="width:'+frac+'%;background:'+(i?'#008c84':'#286fbd')+'"></div></div><small>'+(v===null?'UNKNOWN':Number(v).toLocaleString(undefined,{maximumFractionDigits:2}))+(mode==='relative'?' / 100':'')+'</small></div>'}).join('')}
plot('relative');</script></html>""".replace("__WAVE__", html.escape(manifest["wave"])) \
        .replace("__CARDS__", cards).replace("__ROWS__", rows).replace("__SERIES__", series)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--rollup", type=Path, required=True)
    p.add_argument("--ledger", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    output = render(json.loads(args.manifest.read_text()),
                    json.loads(args.rollup.read_text()),
                    json.loads(args.ledger.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    print("Wrote offline QPS N dashboard", args.output)


if __name__ == "__main__":
    main()