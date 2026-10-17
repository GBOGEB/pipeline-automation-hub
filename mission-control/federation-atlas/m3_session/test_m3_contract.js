"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const root=path.resolve(__dirname,"../../../docs/mission-control/m3");
const d=JSON.parse(fs.readFileSync(path.join(root,"state.json"),"utf8"));
const html=fs.readFileSync(path.join(root,"index.html"),"utf8");
assert.equal(d.schema,"missioncontrol.m3.readonly_projection.v1");
assert.equal(d.authority.merge_admission,"HOLD");
assert.equal(d.authority.remote_mutation_enabled,false);
assert.equal(d.authority.security_waiver,false);
assert.equal(d.authority.governed_main_merge_verified,false);
for(const field of ["code_x_to_abacus_crew_launch","accepted_rex","root_open","root_closed","main_coverage_current","diff_coverage_current","pages_published"]) assert.equal(d.authority[field],null,field+" must not become false or zero");
assert.equal(d.repos.length,6);
assert.equal(new Set(d.repos.map(r=>r.id)).size,6);
for(const r of d.repos){assert.match(r.sha,/^[0-9a-f]{40}$/);assert.match(r.link,/^https:\/\/github\.com\/GBOGEB\//)}
assert.equal(new Set(d.nodes.map(n=>n.id)).size,d.nodes.length);
let ids=new Set(d.nodes.map(n=>n.id));for(const e of d.edges){assert.ok(ids.has(e.from)&&ids.has(e.to),"dangling graph edge");assert.ok(["DECLARED","RECEIPT","CONTROL_FEEDBACK_ONLY"].includes(e.binding))}
assert.equal(d.baselines.abacus_1860.completed,1);assert.equal(d.baselines.abacus_1860.total,12);
assert.equal(d.baselines.codex_977.completed,0);assert.equal(d.baselines.codex_977.total,7);
assert.equal(d.baselines.dashboard_1885.href_occurrences,53);
assert.equal(d.baselines.dashboard_1885.closed_duplicate_alert_tickets,6);
assert.equal(d.baselines.dashboard_1885.root_closed,false);
assert.equal(d.pulses.length,3);
assert.ok(d.pulses.every(p=>p.dispatch!=="LAUNCHED"));
for(const x of d.receipts){assert.match(x.source_sha,/^[0-9a-f]{40}$/);assert.ok(x.url.startsWith("https://github.com/"))}
assert.match(html,/<title>Mission Control M3/);assert.match(html,/<h1>Federated execution flightdeck<\/h1>/);
for(const key of ["graph","search","layer","repos","sipoc","selected","stages","pulses","receipts","admission","mermaid","source","reload","copyMermaid"])assert.ok(html.includes('id="'+key+'"'),"missing "+key);
assert.ok(!html.includes("<script src="));assert.ok(!html.includes("github_pat_"));assert.ok(!html.includes("window.location.reload()"));
console.log("PASS M3 readonly graph contract: "+d.nodes.length+" nodes / "+d.edges.length+" edges / "+d.repos.length+" repos");
