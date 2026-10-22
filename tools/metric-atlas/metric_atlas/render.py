"""Generate an offline, self-contained HTML metric dashboard without third-party JS."""
import html
import json
from pathlib import Path
from .analytics import analyze, simulate

STYLE=r'''
:root{--bg:#f5f7fb;--panel:#fff;--ink:#18263b;--muted:#6c778a;--border:#dce3ed;--blue:#176bcb;--teal:#008a7c;--orange:#d19028;--purple:#7354b5;--red:#b54b4b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink)}
header{background:#112947;color:white;padding:24px max(24px,calc((100vw - 1300px)/2));border-bottom:4px solid #2a9e94}
header h1{font-size:28px;margin:0 0 5px;letter-spacing:-.02em}header p{opacity:.85;margin:0;max-width:900px}
main{max-width:1300px;padding:24px;margin:auto}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.panel,.kpi{border:1px solid var(--border);background:var(--panel);border-radius:12px;padding:19px;margin-bottom:17px;box-shadow:0 2px 5px #243b4c08}
.kpi .big{font-size:30px;font-weight:750;letter-spacing:-.035em}.kpi small{display:block;color:var(--muted)}
h2{font-size:19px;margin:0 0 8px}h3{font-size:15px;margin:8px 0}.sub{color:var(--muted);font-size:13px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}select,input,button{font:inherit;padding:7px 10px;border:1px solid #b7c5d7;border-radius:7px;background:#fff;color:var(--ink)}
.controls{display:flex;flex-wrap:wrap;gap:16px;align-items:center;margin:12px 0}.controls label{font-size:13px;display:flex;align-items:center;gap:6px}
button{background:#eaf2ff;cursor:pointer}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:9px 8px;border-bottom:1px solid var(--border);vertical-align:top}th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#56647a}
.tag{display:inline-block;padding:2px 7px;border-radius:8px;background:#e9eff7;color:#465874;font-size:11px}
.tag.warn{background:#fff1d6;color:#77501f}.tag.good{background:#e1f4eb;color:#16694c}.tag.bad{background:#fce8e7;color:#9e2e2e}
.barbg{height:15px;width:100%;background:#edf0f5;border-radius:5px;overflow:hidden}.bar{height:100%;background:var(--blue)}.bar.missing{background:#adbac9}
.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:#536275}.dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:5px}
svg{display:block;width:100%;height:auto}svg text{font:12px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#59687a}.axis{stroke:#d0d8e4;stroke-width:1}.series{fill:none;stroke-width:3;stroke-linejoin:round}
.phase{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.step{border:1px solid #c6d3e2;background:#f0f6ff;border-radius:8px;padding:7px 9px;flex:1;min-width:110px;text-align:center}.arrow{color:#617087}
.notice{border-left:3px solid #b68b32;background:#fff8e6;padding:8px 11px;margin:10px 0;font-size:13px}
pre{white-space:pre-wrap;overflow:auto;background:#f1f5f9;border:1px solid var(--border);padding:12px;border-radius:8px}
footer{padding:18px 0 32px;color:var(--muted);font-size:12px}@media(max-width:950px){.grid{grid-template-columns:repeat(2,1fr)}.pair{grid-template-columns:1fr}}@media(max-width:550px){.grid{grid-template-columns:1fr}header h1{font-size:22px}}
'''

BODY=r'''
<header><h1>CODE PURPLE / GoGREEN — Metric Atlas</h1><p>Source-bound parallel evolution, historical wave lineage and N-indexed decision evidence. Offline, reproducible, read-only.</p></header>
<main>
<div class="grid" id="kpis"></div>
<section class="panel"><h2>1. Parallel branch and statement populations</h2><p class="sub">Separate numerator/denominator and scope. Grey = covered numerator UNKNOWN. Bar length denotes opportunity size (logarithmic option); fill denotes known coverage fraction.</p><div class="controls"><label><input type="checkbox" id="branchLog" checked> Logarithmic total-size scale</label><label><input type="checkbox" id="onlyBranches" checked> Branch opportunities only</label></div><div id="coverRows"></div></section>
<section class="pair"><div class="panel"><h2>2. Overlay: temporal N-index trajectories</h2><p class="sub">Align each cohort's latest observed event to N=0. Overlay means shape comparison, NOT interchangeable denominators.</p><div class="controls"><select id="seriesFamily"><option value="tests">Test count growth</option><option value="historical">Historical CODE PURPLE</option><option value="fingerprint">Recurring first-red fingerprint</option><option value="lint">Markdown failures</option></select><label><input type="checkbox" id="normalized" checked> Baseline=100</label><label><input type="checkbox" id="logY"> Log y</label></div><svg id="overlay" viewBox="0 0 620 320" role="img" aria-label="Normalized temporal trajectories"></svg><div id="chartLegend" class="legend"></div></div>
<div class="panel"><h2>3. Growth, velocity, acceleration, stability</h2><p class="sub">Finite differences measured per observed step; no wall-clock rate without timestamps. N20 requires 20 observations.</p><div id="rankings"></div><div class="notice"><b>Winner criteria:</b> test-growth percentage can be ranked within test-count cohorts. Yield (per runner-hour), maturity and stability winners remain UNKNOWN with missing denominators/history.</div></div></section>
<section class="pair"><div class="panel"><h2>4. Long-wave historical lineage</h2><p class="sub">Four native historical CODE PURPLE snapshots; backlog denominator doubled in the final observation while completed work stayed constant.</p><svg id="historicalSvg" viewBox="0 0 620 280"></svg><div id="historicalNotes"></div></div>
<div class="panel"><h2>5. N+i sensitivity playground</h2><p class="sub">Counterfactual linear continuation only; dashed future values are simulated, never CI, merge, or engineering credit.</p><div class="controls"><label>Series <select id="simulateSeries"><option value="MC:METHOD_ATLAS::tests_passed">Method Atlas tests</option><option value="ABACUS:PY312_SUITE::tests_passed">ABACUS Python 3.12 tests</option><option value="MC:QPS_CENSUS_CONTROLLER::tests_passed">QPS controller native tests</option><option value="MC:CODE_PURPLE_SERIES::bd_completed">Historic BD completed</option></select></label><label>Horizon <input id="horizon" type="range" min="1" max="5" value="3"><output id="horizonText">N+3</output></label></div><div id="simulation"></div><p class="sub">Use a rerun/testflight at a past SHA to convert scenarios to actual evidence. Historical replay must retain dependencies, test selection, runner image and commit provenance.</p></div></section>
<section class="panel"><h2>6. Convergence DAG / exact-head Golden Thread</h2><div class="phase"><span class="step">Observe repo + SHA</span><span class="arrow">→</span><span class="step">Native run / job / attempt</span><span class="arrow">→</span><span class="step">Artifact & first-red</span><span class="arrow">→</span><span class="step">Root attribution</span><span class="arrow">→</span><span class="step">Disjoint source repair</span><span class="arrow">→</span><span class="step">N+1 exact-head proof</span><span class="arrow">→</span><span class="step">Authorized admission</span><span class="arrow">→</span><span class="step">Post-merge CONTROL</span></div><p class="sub">Feedback: CONTROL → next census; recurrence → root reclassification; evidence mismatch → HOLD; simulation ≠ proof.</p></section>
<section class="panel"><h2>7. SIPOC / parallel federation roles</h2><table><thead><tr><th>Supplier</th><th>Input</th><th>Process</th><th>Output</th><th>Customer</th></tr></thead><tbody><tr><td>ABACUS/CODEX/QPS/gg_MATH</td><td>Native source SHA, tests and coverage</td><td>Extract scope-bound evidence</td><td>Receipt + first-red fingerprint</td><td>Mission Control census</td></tr><tr><td>CI runners</td><td>Run/attempt/job, artifact bytes</td><td>Verify identity and archive</td><td>Verified/UNKNOWN provenance</td><td>#530 ZIP verifier</td></tr><tr><td>Repo owner</td><td>Acceptance and root ID</td><td>Classify/repair/retest</td><td>Exact-head proof</td><td>Admission owner</td></tr><tr><td>Mission Control #531</td><td>Eligible repo list, observations</td><td>Produce breadth with denominator</td><td>Source-bound census</td><td>Federation dashboard</td></tr><tr><td>Mission Control #533</td><td>Canonical lane contract</td><td>Render Method Atlas</td><td>HTML / MMD / JSON viewer</td><td>Human analyst</td></tr><tr><td>Governance / human owner</td><td>Ruleset, review, security severity</td><td>Authorize or HOLD</td><td>Audit receipt and debt</td><td>GoGREEN CONTROL</td></tr></tbody></table></section>
<section class="pair"><div class="panel"><h2>8. Evidence and missingness census</h2><div id="missing"></div></div><div class="panel"><h2>9. Priority and readiness</h2><div id="priority"></div></div></section>
<section class="panel"><h2>10. Human / machine metric ledger</h2><p class="sub">Data are preserved under scope IDs and evidence classes. Export the source JSON and analysis JSON for MIP/DMAIC, gg_MATH and downstream plotting.</p><div id="ledgerTable"></div></section>
<footer>Offline view. No rulesets, security checks, workflow dispatch, or merges are modified. Historical artifact from native Method Atlas #533 is embedded in the distribution; current GitHub telemetry must be imported as fresh evidence, never guessed.</footer>
</main>
'''
JS=r'''
const DATA=__DATA__;
const ANALYSIS=__ANALYSIS__;
const $=id=>document.getElementById(id);
const num=(v,d=2)=>v==null?'UNKNOWN':Number(v).toLocaleString(undefined,{maximumFractionDigits:d});
const pct=(n,d)=>n==null||d==null?'UNKNOWN':(100*n/d).toFixed(2)+'%';
const esc=x=>String(x==null?'':x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const colors=['#176bcb','#008a7c','#7354b5','#d19028','#b54b4b','#78879c'];
const R=DATA.measurements;
function key(metric,scope){return R.filter(r=>r.metric===metric&&r.scope_id===scope).sort((a,b)=>a.step-b.step)}
const branchRecords=R.filter(r=>['branch_coverage','statement_coverage','changed_line_coverage'].includes(r.metric));
function renderKPIs(){const a=DATA.native_archive;const k=[['Measured scopes',new Set(R.map(r=>r.scope_id)).size,'Not equal to repositories'],['Historical #533 ZIP',num(a.bytes,0)+' B','ZIP integrity verified'],['Evolution steps',4,'Historical native series'],['N20 available','NO','Four history steps <20']];$('kpis').innerHTML=k.map(i=>`<div class="kpi"><small>${esc(i[0])}</small><div class="big">${esc(i[1])}</div><small>${esc(i[2])}</small></div>`).join('')}
function renderCoverage(){const only=$('onlyBranches').checked,log=$('branchLog').checked;
 const arr=branchRecords.filter(r=>(!only||r.metric==='branch_coverage')&&r.denominator).sort((a,b)=>b.denominator-a.denominator);
 const max=Math.max(...arr.map(r=>r.denominator));
 $('coverRows').innerHTML='<table><thead><tr><th>Population</th><th>Metric</th><th>Covered / opportunities</th><th>Scale / fraction</th><th>Evidence</th></tr></thead><tbody>'+arr.map(r=>{
   const width=100*(log?Math.log10(r.denominator+1)/Math.log10(max+1):r.denominator/max),
         fraction=r.numerator==null?0:100*r.numerator/r.denominator;
   return `<tr><td>${esc(r.label)}<br><span class="sub">${esc(r.scope_id)}</span></td><td>${esc(r.metric)}</td><td>${r.numerator==null?'UNKNOWN':num(r.numerator,0)} / ${num(r.denominator,0)}<br><b>${pct(r.numerator,r.denominator)}</b></td><td><div class="barbg" style="max-width:${width}%"><div class="bar ${r.numerator==null?'missing':''}" style="width:${r.numerator==null?100:fraction}%"></div></div><span class="sub">${num(r.denominator,0)} ${log?'log-sized':'linear-sized'}</span></td><td><span class="tag ${r.state==='OBSERVED_NATIVE'?'good':'warn'}">${esc(r.state)}</span></td></tr>`}).join('')+'</tbody></table>';
}
function plot(target,series,{normalized=false,log=false,viewHeight=320}={}){
 const svg=$(target),W=620,H=viewHeight,left=55,right=22,top=22,bottom=48;
 const clean=series.map(s=>({name:s.name,points:s.points.map(p=>({...p})).filter(p=>p.y!=null)})).filter(s=>s.points.length);
 if(!clean.length){svg.innerHTML='<text x="40" y="50">UNKNOWN: no valid points</text>';return}
 clean.forEach(s=>{const base=s.points[0]?.y;s.points.forEach(p=>{p.val=normalized?(base?100*p.y/base:null):p.y; if(log&&p.val!=null&&p.val<=0)p.val=null})});
 const pts=clean.flatMap(s=>s.points).filter(p=>p.val!=null);if(!pts.length){svg.innerHTML='<text x="40" y="50">No positive data for log scale</text>';return}
 let xmin=Math.min(...pts.map(p=>p.x)),xmax=Math.max(...pts.map(p=>p.x));if(xmin===xmax){xmin--;xmax++}
 let vals=pts.map(p=>log?Math.log10(p.val):p.val),lo=Math.min(...vals),hi=Math.max(...vals);if(lo===hi){lo-=1;hi+=1}const margin=(hi-lo)*.12;lo-=margin;hi+=margin;
 const xf=x=>left+(x-xmin)/(xmax-xmin)*(W-left-right),yf=y=>top+(hi-(log?Math.log10(y):y))/(hi-lo)*(H-top-bottom);
 let out='';for(let i=0;i<=4;i++){let y=top+i*(H-top-bottom)/4;let val=hi-i*(hi-lo)/4;out+=`<line class="axis" x1="${left}" x2="${W-right}" y1="${y}" y2="${y}"/><text x="${left-7}" y="${y+4}" text-anchor="end">${num(log?10**val:val,1)}</text>`}
 for(let x=Math.ceil(xmin);x<=Math.floor(xmax);x++){out+=`<text x="${xf(x)}" y="${H-14}" text-anchor="middle">${x===0?'N':x<0?'N'+x:'N+'+x}</text>`}
 clean.forEach((s,i)=>{const c=colors[i%colors.length],p=s.points.filter(p=>p.val!=null).map(p=>[xf(p.x),yf(p.val),p]);
 if(p.length>1)out+=`<polyline class="series" stroke="${c}" points="${p.map(p=>p[0]+','+p[1]).join(' ')}"/>`;
 p.forEach(([x,y,d])=>out+=`<circle cx="${x}" cy="${y}" r="5" fill="${c}"><title>${esc(s.name)} | N${d.x<0?d.x:'+'+d.x} | ${num(d.y,3)}</title></circle>`)});
 svg.innerHTML=out;
 return clean.map((s,i)=>`<span><span class="dot" style="background:${colors[i%colors.length]}"></span>${esc(s.name)}</span>`).join('');
}
function renderOverlay(){const type=$('seriesFamily').value,normalize=$('normalized').checked,log=$('logY').checked;
 let series=[];
 if(type==='tests')series=[['MC:METHOD_ATLAS','Method Atlas 53→74'],['ABACUS:PY312_SUITE','ABACUS Python 3.12 2243→2257'],['MC:QPS_CENSUS_CONTROLLER','QPS controller 39→48']].map(([sc,name])=>({name,points:key('tests_passed',sc).map(r=>({x:r.step,y:r.value}))}));
 if(type==='historical')series=[['bd_completed','Completed backlog items'],['bd_inventory','Backlog size']].map(([metric,name])=>({name,points:key(metric,'MC:CODE_PURPLE_SERIES').map(r=>({x:r.step-3,y:r.value}))}));
 if(type==='fingerprint')series=[{name:'Recurring Matplotlib PR fingerprint, NOT causal root ID',points:key('fingerprint_pr_occurrences','ABACUS:MATPLOTLIB_FAMILY').map(r=>({x:r.step,y:r.value}))}];
 if(type==='lint')series=[{name:'ABACUS Markdown errors, lower is better',points:key('markdown_failures','ABACUS:MD_LINT').map(r=>({x:r.step,y:r.value}))}];
 const legend=plot('overlay',series,{normalized:normalize,log});$('chartLegend').innerHTML=legend||'';
}
function renderHistory(){const s=[{name:'BD completed',points:key('bd_completed','MC:CODE_PURPLE_SERIES').map(r=>({x:r.step-3,y:r.value}))},{name:'BD inventory',points:key('bd_inventory','MC:CODE_PURPLE_SERIES').map(r=>({x:r.step-3,y:r.value}))}];plot('historicalSvg',s,{viewHeight:280});$('historicalNotes').innerHTML='<p class="sub">Historical sequences N−3 to N−0: completed <b>0→2→4→4</b>; inventory <b>9→9→9→18</b>. Completion fraction changes from 44.44% to 22.22% when the denominator doubles: avoid calling that a loss of completed items.</p>'}
function renderRank(){const hist=ANALYSIS.histories;const select=['MC:METHOD_ATLAS::tests_passed','ABACUS:PY312_SUITE::tests_passed','MC:QPS_CENSUS_CONTROLLER::tests_passed','MC:CODE_PURPLE_SERIES::bd_completed','ABACUS:MD_LINT::markdown_failures'];
 $('rankings').innerHTML='<table><thead><tr><th>Series</th><th>Change</th><th>Speed / pulse</th><th>Acceleration</th><th>N20</th></tr></thead><tbody>'+select.map(k=>{const x=hist[k];if(!x)return'';return `<tr><td>${esc(x.scope_id)}<br><small>${x.observations} points</small></td><td>${num(x.pct_change)}%</td><td>${num(x.slope_per_pulse)}</td><td>${num(x.acceleration_per_pulse2)}</td><td>${num(x.rolling_n20)}</td></tr>`}).join('')+'</tbody></table><p class="sub">Largest measured relative test-count growth: <b>'+esc(ANALYSIS.interpretation.rank_winner||'UNKNOWN')+'</b>. Test count is not coverage, throughput or functional value.</p>'}
function renderSimulation(){const key=$('simulateSeries').value, horizon=+$('horizon').value;$('horizonText').textContent='N+'+horizon;
 const h=ANALYSIS.histories[key];if(!h){$('simulation').textContent='UNKNOWN';return}
 let last=h.latest,vel=h.slope_per_pulse;
 if(vel==null){$('simulation').textContent='UNKNOWN - at least two points required';return}
 let future=Array.from({length:horizon},(_,i)=>({n:i+1,value:Math.max(0,last+(i+1)*vel)}));
 $('simulation').innerHTML='<table><tr><th>Event</th><th>Scenario value</th><th>Evidence</th></tr>'+future.map(x=>`<tr><td>N+${x.n}</td><td>${num(x.value)}</td><td><span class="tag warn">SIMULATED</span></td></tr>`).join('')+'</table><p class="sub">Assumption: latest finite-difference slope '+num(vel)+' per N persists. Confidence unquantified.</p>'}
function renderMissing(){let rows=[['Source-bound historical #533 ZIP','VERIFIED'],['Current 90-repo inventory','UNKNOWN'],['PCA complete independent rows','UNKNOWN'],['Bradley–Terry terminal pairs','UNKNOWN'],['Per-run runner-hours','UNKNOWN'],['Broader covered branch numerator','UNKNOWN'],['Effective GitHub ruleset matches','UNKNOWN'],['Scope-matched cross-head broad coverage uplift','UNKNOWN'],['Current QPS engineering acceptance','UNKNOWN']];
 $('missing').innerHTML='<table><thead><tr><th>Dimension</th><th>State</th></tr></thead><tbody>'+rows.map(r=>`<tr><td>${esc(r[0])}</td><td><span class="tag ${r[1]==='VERIFIED'?'good':'warn'}">${r[1]}</span></td></tr>`).join('')+'</tbody></table>'}
function renderPriority(){let rows=[['1','Canonical Python 3.10 compatibility','7 observed PR fingerprints','High plausible leverage; actual root closure unproven','GO_PROVE'],['2','ABACUS MD032 cleanup','1 remaining lint error','Low effort, narrower value','GO_EXECUTE'],['3','Direct CI for federated metric engine','Native job identity unavailable','Critical provenance/acceptance test','GO_PROVE'],['4','SIPOC/DAG fan-out','5 intended core repos','Needs source-head and owner mapping','HOLD_APPLY'],['5','PCA/BT maturity','Insufficient complete samples','Do not fit governed models','HOLD']];
 $('priority').innerHTML='<table><tr><th>Priority</th><th>Work</th><th>Evidence / size</th><th>Decision</th></tr>'+rows.map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}<br><small>${r[3]}</small></td><td><span class="tag ${r[4].startsWith('GO')?'good':'warn'}">${r[4]}</span></td></tr>`).join('')+'</table>'}
function renderLedger(){const sorted=R.slice().sort((a,b)=>a.scope_id.localeCompare(b.scope_id)||a.metric.localeCompare(b.metric)||a.step-b.step);
 $('ledgerTable').innerHTML='<div style="max-height:470px;overflow:auto"><table><thead><tr><th>Scope</th><th>Metric</th><th>N step</th><th>Value / denominator</th><th>Evidence</th></tr></thead><tbody>'+sorted.map(r=>`<tr><td>${esc(r.scope_id)}</td><td>${esc(r.metric)}</td><td>${r.step}</td><td>${r.numerator!=null?num(r.numerator):num(r.value)}${r.denominator!=null?' / '+num(r.denominator):''}</td><td><span class="tag ${r.state==='OBSERVED_NATIVE'?'good':'warn'}">${esc(r.state)}</span></td></tr>`).join('')+'</tbody></table></div>'}
renderKPIs();renderCoverage();renderOverlay();renderHistory();renderRank();renderSimulation();renderMissing();renderPriority();renderLedger();
$('branchLog').addEventListener('change',renderCoverage);$('onlyBranches').addEventListener('change',renderCoverage);
for(const id of ['seriesFamily','normalized','logY'])$(id).addEventListener('change',renderOverlay);
$('horizon').addEventListener('input',renderSimulation);$('simulateSeries').addEventListener('change',renderSimulation);
'''

def render_html(data):
    analysis=analyze(data)
    payload=json.dumps(data,ensure_ascii=True,separators=(',',':')).replace('<','\\u003c')
    metrics=json.dumps(analysis,ensure_ascii=True,separators=(',',':')).replace('<','\\u003c')
    # JS template constants are not external scripts and require no network connection.
    js=JS.replace('__DATA__',payload).replace('__ANALYSIS__',metrics)
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CODE PURPLE Metric Atlas</title><style>'+STYLE+'</style></head><body>'+BODY+'<script>'+js+'</script></body></html>'
