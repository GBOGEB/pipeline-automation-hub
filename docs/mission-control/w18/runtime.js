/* CODE PURPLE W18: read-only views of one frozen, signed-by-hash snapshot. */
(() => {
'use strict';
const masterNode = document.getElementById('source-master');
if (!masterNode) return;
const M = JSON.parse(masterNode.textContent);
const mode = document.body.dataset.mode || 'dashboard';
let activeView = mode;
let devopsOn = false;
let activeContext = null;
const MASTER_SHA = document.querySelector('meta[name=master-sha256]').content;
const PR_URL = 'https://github.com/GBOGEB/pipeline-automation-hub/pull/670';
const FILE_ROOT = 'docs/mission-control/w18/';
const DEFAULT_TARGETS = [
 ['Global issue controller #153','https://github.com/GBOGEB/pipeline-automation-hub/issues/153'],
 ['Canonical BD/REX #85','https://github.com/GBOGEB/pipeline-automation-hub/issues/85'],
 ['Local BD queue #358','https://github.com/GBOGEB/pipeline-automation-hub/issues/358'],
 ['ABACUS admission #1860','https://github.com/GBOGEB/ABACUS/issues/1860']
];
const toSlug = (s) => String(s).toLowerCase().replace(/[^a-z0-9-]+/g,'-').replace(/^-+|-+$/g,'').slice(0,70);
function isGithub(url) {return typeof url==='string' && /^https:\/\/github\.com\/GBOGEB\/[a-zA-Z0-9_.-]+\/(issues|pull)\/\d+(?:[?#][^\s]*)?$/.test(url);}
function getFile() {return mode==='dashboard'?'index.html':mode==='cards'?'cards.html':'deck.html';}
function getRelativeLink(key, view=activeView) {
 if (mode==='cards') return 'cards.html#'+encodeURIComponent(key);
 if (mode==='deck') return 'deck.html#slide-'+String(key).replace(/[^0-9]/g,'').padStart(2,'0');
 return 'index.html#'+view+'@'+encodeURIComponent(key);
}
function locate(node,key,title,source) {
 const view=activeView;
 const loc='CP-W18/'+view+'/'+key;
 node.dataset.locationId=loc;
 node.dataset.locationKey=key;
 node.dataset.locationView=view;
 if (!node.id) node.id='loc-'+toSlug(view+'-'+key);
 const btn=E('button','devops-hook-btn','Comment / copy');btn.type='button';
 btn.setAttribute('aria-label','DevOps location comment for '+title);
 btn.addEventListener('click',(ev)=>{ev.stopPropagation();openDevops({key,view,loc,title,source:source||M.authorities.global_issue_controller});});
 const bar=add(E('span','devops-hook-actions'),btn);
 if (node.tagName==='TR') {
   const last=node.lastElementChild;
   if(last)last.append(bar);
 } else node.append(bar);
 return node;
}
function safeFeedback(value) {return String(value||'').trim().slice(0,4000);}
function selectedTarget() {return $('devops-target').value;}
function commentText() {
 if (!activeContext)return '';
 const ctx=activeContext;
 const path=getFile();
 const target=selectedTarget();
 const relative=getRelativeLink(ctx.key,ctx.view);
 const mark='CP-W18:'+ctx.view+'/'+ctx.key;
 return [
   '### CODE PURPLE W18 UI/BD feedback — '+ctx.title,
   '',
   '- Location ID: `'+mark+'`',
   '- Frozen master: `'+M.slug+'`',
   '- Source digest (SHA-256): `'+MASTER_SHA+'`',
   '- Local/hosted route (host not yet verified): `'+FILE_ROOT+relative+'`',
   '- GitHub review PR: '+PR_URL,
   '- Canonical target: '+target,
   '- Linked engineering evidence: '+(isGithub(ctx.source)?ctx.source:'UNKNOWN'),
   '- Recursive authorities: '+M.authorities.global_issue_controller+' → '+M.authorities.bd_ssot+' → '+M.authorities.local_queue,
   '- Evidence class: FROZEN_COMMUNICATION_PROJECTION (not a native gate)',
   '',
   '**Observed at this location:** '+(safeFeedback($('devops-observed').value)||'[describe observation]'),
   '',
   '**Expected / proposed improvement:** '+(safeFeedback($('devops-expected').value)||'[describe desired change]'),
   '',
   '**Next verifiable action:** '+(safeFeedback($('devops-next').value)||'[owner and completion evidence]'),
   '',
   '**Additional source / attempt / run / artifact:** '+(safeFeedback($('devops-evidence').value)||'[exact URL or unknown]'),
   '',
   'DoV: REQUESTED / NOT VALIDATED. This draft does not close a BD root, waive A10, or grant merge admission.'
 ].join('\n');
}
function refreshComment() {if(activeContext)$('devops-output').value=commentText();}
async function copyWithFallback(text) {
 const out=$('devops-output');out.value=text;
 let success=false;
 try { if(navigator.clipboard && navigator.clipboard.writeText) {await navigator.clipboard.writeText(text);success=true;} } catch (_) {}
 if (!success) {out.focus();out.select();try{success=!!document.execCommand('copy')}catch(_) {}}
 $('devops-feedback').textContent=success?'Copied. Paste into the intended GitHub issue.':'Text selected — use Ctrl+C / Copy manually.';
 return success;
}
function openDevops(ctx) {
 activeContext=ctx;
 $('devops-heading').textContent=ctx.title;
 $('devops-locator').textContent=ctx.loc;
 const sel=$('devops-target');sel.replaceChildren();
 const opts=[...DEFAULT_TARGETS];
 if(isGithub(ctx.source) && !opts.some(x=>x[1]===ctx.source))opts.unshift(['Current engineering leaf',ctx.source]);
 opts.forEach(([label,url])=>{const o=E('option','',label);o.value=url;sel.append(o);});
 for(const id of ['devops-observed','devops-expected','devops-next','devops-evidence'])$(id).value='';
 $('devops-feedback').textContent='Draft only — nothing is posted automatically.';
 refreshComment();
 const modal=$('devops-dialog');if(!modal.open)modal.showModal();
}
function initDevops() {
 const toggle=$('devops-toggle');
 toggle.onclick=()=>{devopsOn=!devopsOn;document.body.dataset.devops=devopsOn?'on':'off';toggle.setAttribute('aria-pressed',String(devopsOn));toggle.textContent='DevOps hooks: '+(devopsOn?'ON':'OFF');};
 $('devops-close').onclick=()=>$('devops-dialog').close();
 for(const id of ['devops-observed','devops-expected','devops-next','devops-evidence','devops-target'])$(id).addEventListener('input',refreshComment);
 $('devops-copy-location').onclick=()=>{
  if(!activeContext)return;
  const x=activeContext;
  const relative=FILE_ROOT+getRelativeLink(x.key,x.view);
  const data=['Locator: CP-W18:'+x.view+'/'+x.key,'Path: '+relative,'Master SHA-256: '+MASTER_SHA,'PR: '+PR_URL,'Canonical: '+selectedTarget()].join('\n');
  copyWithFallback(data);
 };
 $('devops-copy-comment').onclick=()=>copyWithFallback(commentText());
 $('devops-open-issue').onclick=()=>{const url=selectedTarget();if(isGithub(url))window.open(url,'_blank','noopener,noreferrer');};
}

const $ = (id) => document.getElementById(id);
const E = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = String(text);
  return e;
};
const add = (p, ...kids) => { kids.flat().filter(Boolean).forEach(x => p.append(x)); return p; };
const whole = (n) => new Intl.NumberFormat('en-US').format(n);
const unknown = (v, suffix='') => v === null || v === undefined ? 'UNKNOWN' : String(v) + suffix;
const pct = (n,d) => (n === null || d === null || !d) ? 'UNKNOWN' : (100*n/d).toFixed(2) + '%';
const link = (url, label) => {
  const a = E('a','source-link',label || 'Evidence');
  if (typeof url==='string' && /^https:\/\/github\.com\/GBOGEB\/[A-Za-z0-9_.\-/]+(?:[?#][^\s]*)?$/.test(url)) {
    a.href=url; a.target='_blank'; a.rel='noopener noreferrer';
  } else { a.textContent='SOURCE UNAVAILABLE'; }
  return a;
};
const pill = (state) => E('span','tag '+String(state).replace(/[^A-Za-z0-9_]/g,''),state);
const panel = (title,locKey=null,source=null) => {
 const node=add(E('section','panel'), E('h2','',title));
 return locate(node,locKey||'panel-'+toSlug(title),title,source||M.authorities.global_issue_controller);
};
const note = (t) => E('p','hint',t);
const metric = (label,value,desc,good=false) => {
  const p=E('article','metric'),v=E('strong',good?'ok':'',value);
  add(p,v,E('span','',label),E('small','',desc));
  return locate(p,'kpi-'+toSlug(label),label,M.authorities.global_issue_controller);
};
const metricGrid = (items) => add(E('div','metric-grid'),items);
const h3 = (t) => E('h3','',t);
const para = (t) => E('p','',t);
const foot = (label,url) => add(E('div','card-footer'),link(url,label));
const statusCount = (arr,s) => arr.filter(x=>x.state===s).length;
const table = (head,rows) => {
  const wrap=E('div','tablewrap'),t=E('table'),thead=E('thead'),tr=E('tr');
  head.forEach(x=>add(tr,E('th','',x)));add(thead,tr);add(t,thead);
  const tb=E('tbody');
  rows.forEach(row=>{const r=E('tr');row.forEach(cell=>{const c=E('td');if(cell instanceof Node)c.append(cell);else c.textContent=unknown(cell);r.append(c)});tb.append(r)});
  add(t,tb);return add(wrap,t);
};
function repoBars() {
  const box=E('div');
  const max=Math.max(...M.census.repos.map(x=>x.open));
  for (const x of M.census.repos) {
    const w=E('div','barwrap'),lbl=E('div','barlabel');
    add(lbl,E('span','',x.name),E('strong','count',whole(x.open)));
    const track=E('div','track'),bar=E('span');bar.style.width=(100*x.open/max).toFixed(2)+'%';
    add(w,lbl,add(track,bar));box.append(w);
  }
  return box;
}
function issuePlot() {
  const host=E('div','plot-fallback');host.id='issue-plot';
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 580 195');svg.setAttribute('role','img');
  svg.setAttribute('aria-label','Two distinct GitHub search observations 153 and 142, not a statistically estimated slope');
  svg.style.width='100%';svg.style.height='195px';
  const NS='http://www.w3.org/2000/svg';
  const shape=(tag,attrs,text)=>{const e=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,String(v)));if(text)e.textContent=text;svg.append(e);return e};
  [130,140,150,160].forEach(y=>{const py=170-(y-130)*4.5;shape('line',{x1:58,x2:540,y1:py,y2:py,stroke:'#55708b','stroke-dasharray':'3,5'});shape('text',{x:14,y:py+4,fill:'#bdcbe0','font-size':11},String(y));});
  const a=170-(153-130)*4.5,b=170-(142-130)*4.5;
  shape('line',{x1:135,y1:a,x2:444,y2:b,stroke:'#93b5fc','stroke-width':3,'stroke-dasharray':'7,5'});
  [[135,a,'153','First census'],[444,b,'142','Latest readback']].forEach(([x,y,v,t])=>{
    shape('circle',{cx:x,cy:y,r:7,fill:'#6ee2c9'});shape('text',{x:x-21,y:y-16,fill:'#ffffff','font-size':16,'font-weight':700},v);
    shape('text',{x:x-57,y:186,fill:'#bfd0e8','font-size':12},t);
  });host.append(svg);return locate(host,'figure-two-point-issue-count','Historical fleet issue-count chart',M.authorities.global_issue_controller);
}
function loadOptionalPlotly() {
  if (!document.querySelector('#issue-plot')) return;
  const host=$('issue-plot');
  if (!host) return;
  if (window.Plotly && window.Plotly.newPlot) {
    host.classList.remove('plot-fallback');host.classList.add('plot');host.replaceChildren();
    window.Plotly.newPlot(host,[{type:'scatter',mode:'lines+markers+text',x:['First census','Latest readback'],y:[153,142],text:['153','142'],textposition:'top center',line:{color:'#93b5fc',dash:'dot'},marker:{color:'#6ee2c9',size:14}}],{
      paper_bgcolor:'#14253d',plot_bgcolor:'#14253d',font:{color:'#e6edfb',size:12},
      margin:{l:48,r:20,t:24,b:58},xaxis:{title:'Two observations, not a stable rate',showgrid:false},
      yaxis:{title:'Open issues',range:[130,160],dtick:10,gridcolor:'#36516c'},showlegend:false
    },{displayModeBar:false,responsive:true});
  }
}
function schedulePlotlyUpgrade() {
  if(mode!=='dashboard')return;
  const js=document.createElement('script');js.async=true;
  js.src='https://cdn.plot.ly/plotly-2.35.2.min.js';
  js.onload=loadOptionalPlotly;
  js.onerror=()=>{};document.head.append(js);
}
function overview() {
  const root=E('div'),c=M.census, cov=M.coverage.four_module;
  add(root,metricGrid([
    metric('Open GBOGEB/* issues',whole(c.latest_observed_open),'Nine repositories; source search complete'),
    metric('Net open issue change',String(c.net_change),'153 to 142; external concurrent actions',true),
    metric('W16 eligible branch coverage',pct(cov.covered,cov.eligible),`${cov.covered}/${cov.eligible} matched W16 obligations`,true),
    metric('Admission',M.controls.merge_admission,'A10, review, required CI unresolved')
  ]));
  const g=E('div','rowgrid'),a=panel('Fleet by repository'),b=panel('Two-source-count comparison');
  a.append(repoBars());add(b,issuePlot(),note('Dashed connector joins observations only. No queue velocity, p95 or statistical equivalence has been established.'));
  add(g,a,b);root.append(g);
  const p=panel('Evidence and classification');
  add(p,para('11 observed issue closures = 9 monitoring duplicates + 2 completed DAB work items. This controller did not execute those closures; root closure credit remains zero.'),
     para('Canonical B0 PASS is not historical B9 changed-line >=80% proof. Current W16 four-module branch reach 231/444 and Python 3.12 five-file reach 336/560 belong to different cohorts.'),
     add(E('div','evidence-actions'),
        add(E('a','action-link','Open global BD register — 8 actionable leaves ↗')),
        add(E('a','source-link','Open canonical global issue #153 ↗'))));
  const leaf=p.querySelector('.evidence-actions .action-link');leaf.href='cards.html#bd-register';
  const origin=p.querySelector('.evidence-actions .source-link');origin.href=M.authorities.global_issue_controller;origin.target='_blank';origin.rel='noopener noreferrer';
  const jump=E('button','jump-bd','Jump to BD queue here');jump.type='button';
  jump.onclick=()=>{location.hash='bd@bd-register';};p.querySelector('.evidence-actions').append(jump);
  root.append(p);
  return root;
}
function makeDecisionTable(items,kind) {
  const rows=items.map(x=>kind==='dod' ?
    [x.id,x.title,pill(x.state),x.completion,add(E('div'),para(x.detail),link(x.evidence,'Evidence'))]:
    [x.id,x.domain,pill(x.state),x.accept,add(E('div'),para(x.observed),link(x.evidence,'Receipt'))]);
  const t=table(kind==='dod'?['ID','This session DOD','Evidence state','Completion','Proof / edge']:['ID','Global DOV domain','Verdict','Exit / acceptance test','Observed / source'],rows);
  const tr=t.querySelectorAll('tbody tr');
  items.forEach((x,i)=>locate(tr[i],x.id,kind.toUpperCase()+' '+x.id+' — '+(x.title||x.domain),x.evidence));
  return t;
}
function dod() {
  const root=E('div');
  add(root,metricGrid([
    metric('Session DOD verified',String(statusCount(M.session_dod,'VERIFIED'))+'/'+M.session_dod.length,'Only verified rows, not all intents',true),
    metric('In engineering PR / local proof','2','No main merge acceptance'),
    metric('Owner or native holds','3','Security and CI non-compensating'),
    metric('Original chat prompts','UNKNOWN','No complete transcript population')
  ]),makeDecisionTable(M.session_dod,'dod'));return root;
}
function dov() {
  const root=E('div'),r=M.global_dov;
  add(root,metricGrid([
    metric('Global DOV PASS',`${statusCount(r,'PASS')}/${r.length}`,'Two checks verified; not programme completion',true),
    metric('DOV PARTIAL',String(statusCount(r,'PARTIAL')),'Evidence scope or qualification unfinished'),
    metric('DOV HOLD',String(statusCount(r,'HOLD')),'Non-compensating blockers'),
    metric('Six Sigma / PCA / BT','NOT QUALIFIED','No valid capability or ranking inference')
  ]),makeDecisionTable(r,'dov'));return root;
}
function bdCard(x){
  const a=E('article','card');
  const top=E('div','card-head'),lh=E('div');add(lh,E('span','eyebrow',x.id+' / '+x.priority),h3(x.title));
  add(top,lh,pill(x.state));add(a,top);
  add(a,E('p','',x.owner),para('Root: '+x.root),para('Next: '+x.next));
  const details=E('details'),summary=E('summary','', 'Acceptance condition and dependency');
  add(details,summary,para(x.exit),para('Dependencies: '+(x.dependencies.length?x.dependencies.join(', '):'no additional owner edges declared')));
  add(a,details,foot('Source / PR / issue',x.source));
  return locate(a,x.id,x.title,x.source);
}
function bd(){
  const root=E('div'),filter=E('div','filterbar');
  const input=E('input');input.type='search';input.placeholder='Filter owner, root, issue or next action';input.setAttribute('aria-label','Filter BD queue');
  const sel=E('select');sel.setAttribute('aria-label','Filter BD priority');
  ['ALL','P0','P1','P2'].forEach(s=>{const o=E('option','',s);o.value=s;sel.add(o)});
  const cnt=E('span','muted'),list=E('div','cards');
  const render=()=>{const q=input.value.toLowerCase(),pr=sel.value;const valid=M.bd_queue.filter(x=>(pr==='ALL'||x.priority===pr)&& JSON.stringify(x).toLowerCase().includes(q));
    list.replaceChildren(...valid.map(bdCard));cnt.textContent=valid.length+' / '+M.bd_queue.length+' controlled work packets';};
  input.addEventListener('input',render);sel.addEventListener('change',render);
  const hierarchy=panel('Recursive global register → root owners → BD leaves','bd-register');
  hierarchy.id='bd-register';
  const intro=para('Global #153 is the source-dated fleet census; #85 is the unique BD/REX root controller; #358 is the local execution queue. The eight W18 packets below are a governed communication projection, not all 142 root dispositions.');
  const row=E('div','evidence-actions');
  add(row,link(M.authorities.global_issue_controller,'Fleet controller #153'),link(M.authorities.bd_ssot,'Root owner #85'),link(M.authorities.local_queue,'Local queue #358'));
  add(hierarchy,intro,row);
  add(filter,input,sel,cnt);add(root,hierarchy,filter,list);render();return root;
}
function recursiveFocus() {
 const root=E('div');
 const p=panel('W17 → W18 recursive TODO and BD golden thread');
 const t=E('div','recursive-stages');
 const stages=[
  {title:'Fleet / 153 → 143 → 142',detail:'Chronological issue-census readbacks, not equivalent independent rate samples.',url:M.authorities.global_issue_controller},
  {title:'Mission Control root authority / #85',detail:'BD/REX owner mapping, no double-credit from duplicate notifications.',url:M.authorities.bd_ssot},
  {title:'Local mission queue / #358',detail:'Runner capacity, source-owner edges and evidence returns.',url:M.authorities.local_queue},
  {title:'Engineering admission / ABACUS #1860',detail:'B0, B9, security, review, governance, Python, coverage each retain their own gate.',url:M.authorities.admission_controller}
 ];
 stages.forEach((x,i)=>{
  const node=add(E('article','recursive-stage'),h3(x.title),para(x.detail),link(x.url,'Open authority'));
  locate(node,'authority-'+(i+1),x.title,x.url);
  t.append(node);
 });
 add(p,t);root.append(p);
 const r=panel('W17 historical native outcomes — do not overwrite');
 add(r,metricGrid([
   metric('W17 historical successes',M.ci.w16_historical_workflow_rollup.success,'On pinned W16 historical head, nonterminal'),
   metric('W17 historical failures',M.ci.w16_historical_workflow_rollup.failure,'First-red ownership retained'),
   metric('W17 historical queued',M.ci.w16_historical_workflow_rollup.queued,'Not assumed to be terminal'),
   metric('Current-epoch baseline',pct(M.coverage.four_module.covered,M.coverage.four_module.eligible),'231/444; 157 tests passing')
  ]),note('Chronology: 153 first census → 143 intermediate → 142 latest frozen readback. Nine duplicate dashboard notifications and two DAB worker investigations closed by concurrent lanes. Distinct-root CONTROL credit = 0. Historical 200/446 N14 and 231/444 W16 have different source epochs.'));
 root.append(r);
 const todo=panel('Next three source-gated pulses / parent TODO');
 const leaves=[
  ['P0','A10 owner approval','BD-W18-01'],
  ['P1','Python 3.10 and requirement test contract','BD-W18-02'],
  ['P1','Cross-interpreter matrix and Ariana secure XML dependency','BD-W18-03'],
  ['P1','Main workflow classification / governed inventory','BD-W18-05'],
  ['P2','Dashboard broken-links + native health and B9 80% changed-line proof','BD-W18-07'],
  ['P2','All 142 issues need root classification, not just eight packets','BD-W18-08']
 ];
 const tb=table(['Priority','Unresolved edge / completion criterion','Actionable packet'],leaves.map(([priority,desc,id])=>{
  const a=E('a','action-link','Open '+id+' ↗');a.href='index.html#bd@'+id;return [priority,desc,a];
 }));
 add(todo,tb,note('Three governed actions: N+1 security/TOML/Python qualification; N+2 shared Ariana dependency and source-owner repair; N+3 B9/coverage and queue-timing comparison. Do not scale tests or assign statistical CONTROL until receipts are comparable and gates pass.'));
 root.append(todo);return root;
}
function telemetry() {
  const root=E('div'),box=M.coverage,ci=M.ci;
  const p=panel('Native W16 source-bound measurements');
  const rows=[
    ['Four modules, branch obligations',box.four_module.covered,box.four_module.eligible,pct(box.four_module.covered,box.four_module.eligible)],
    ['Five-file Python 3.12 control',box.five_file_py312.covered,box.five_file_py312.eligible,pct(box.five_file_py312.covered,box.five_file_py312.eligible)],
    ['Phase 8 unchanged production blob',box.phase8_same_blob.after_covered,box.phase8_same_blob.eligible,'+33 reached arcs vs prior same blob'],
    ['B9 changed-line current head',null,null,'UNKNOWN - old 80% threshold unproven'],
    ['Queue p95 seconds',null,null,'UNKNOWN - no clock population'],
    ['Actual W16 improvement in testflight duration',null,null,'UNKNOWN - no matched run timings']
  ];
  add(p,table(['Signal','Numerator','Denominator','Measured interpretation'],rows));root.append(p);
  const g=E('div','rowgrid'),a=panel('Historical W16 runs'),b=panel('Current first-red signatures');
  add(a,para(`At historical exact source ${ci.w16_historical_head.slice(0,12)}: ${ci.w16_historical_workflow_rollup.success} success, ${ci.w16_historical_workflow_rollup.failure} failure and ${ci.w16_historical_workflow_rollup.queued} queued out of ${ci.w16_historical_workflow_rollup.denominator} recorded workflow runs. This is not a terminal current-head total.`),
      link('https://github.com/GBOGEB/ABACUS/actions/runs/'+box.native_run,'W16 157-test receipt'));
  add(b,para('Python requirement unit fixture: '+ci.py_matrix_first_red),
      para('Ariana: '+ci.dashboard_b0_first_red),
      para('Security/A10: '+ci.a10_first_red),
      foot('Python first-red run','https://github.com/GBOGEB/ABACUS/actions/runs/'+ci.py_matrix_first_red_run));
  add(g,a,b);root.append(g);return root;
}
function lineage() {
  const root=E('div'),p=panel('One master; multiple controlled renditions');
  const nodes=E('div','dagnodes');['GitHub read-only receipts','Source epoch + evidence contract','W18 snapshot.json','Dashboard / cards / HTML deck','Print/PPTX candidate','Review + native / Pages proof'].forEach((s,i)=>{
  if(i>0)nodes.append(E('div','arrow','>'));
  const node=add(E('div'),E('strong','',s));
  locate(node,'dag-'+String(i+1),s,M.authorities.bd_ssot);
  nodes.append(node);
});
  add(p,nodes,para('One slug and exact SHA-256 embedded in each derived HTML. Existing Mission Control BD authority #85 and CP.CLOSE lossless remain authoritative. The W18 master is only a communication projection.'),
    foot('Original CP.HANDOFF / CP.RESUME contract',M.authorities.existing_handover));root.append(p);
  const q=panel('Method validity: DMAIC / MIP / gg_MATH');
  for (const [a,b] of [
    ['DEFINE / MEASURE','Fleet issue semantics, same search, native branch opportunities and unit denominators established.'],
    ['ANALYZE','Separated nine monitoring duplicates, two worker completions, B9 vs B0 and two independent Python first-red families.'],
    ['IMPROVE','W16 same-blob Phase 8 gains +33 arcs; human security and current-head matrix repair still prevent admission.'],
    ['CONTROL','NOT YET: requires distinct-source regression proof and independent comparable repeats, not a two-point issue slope.'],
    ['PCA / BT / Six Sigma','NOT QUALIFIED. No independent paired BT outcomes, multivariate stable PCA population, or DPMO opportunity population.']
  ]) { const div=E('div','method');add(div,E('strong','',a),para(b));q.append(div);}
  root.append(q);return root;
}
function pageInit() {
  const views={overview,dod,dov,bd,recursiveFocus,telemetry,lineage};
  const holder=$('content');
  const nav=$('view-nav');
  Object.entries({overview:'Overview',dod:'Session DOD',dov:'Global DOV',bd:'BD queue',recursiveFocus:'Recursive TODO',telemetry:'Telemetry',lineage:'Master lineage'}).forEach(([id,label])=>{
    const b=E('button','',label);b.type='button';b.dataset.view=id;b.setAttribute('aria-selected',id==='overview'?'true':'false');
    nav.append(b);
  });
  function activate(id,focus) {
    const current=views[id]?id:'overview';
    activeView=current;
    const button=nav.querySelector('button[data-view="'+current+'"]');
    nav.querySelectorAll('button').forEach(x=>x.setAttribute('aria-selected',String(x===button)));
    holder.replaceChildren(views[current]());
    if(current==='overview')loadOptionalPlotly();
    if(focus)requestAnimationFrame(()=>{
      const target=[...holder.querySelectorAll('[data-location-key]')].find(x=>x.dataset.locationKey===focus);
      if(target){target.classList.add('locator-highlight');target.scrollIntoView({block:'center'});}
    });
  }
  function parseRoute() {
    const hash=decodeURIComponent(location.hash.slice(1));
    const at=hash.indexOf('@');
    const view=at>=0?hash.slice(0,at):hash;
    const focus=at>=0?hash.slice(at+1):null;
    activate(views[view]?view:'overview',focus);
  }
  nav.addEventListener('click',ev=>{
    const b=ev.target.closest('button[data-view]');if(!b)return;
    const route='#'+b.dataset.view;
    if(location.hash===route)parseRoute(); else location.hash=route;
  });
  window.addEventListener('hashchange',parseRoute);
  parseRoute();
  schedulePlotlyUpgrade();
}
function cardsInit() {
  const c=$('content');
  activeView='bd';
  c.replaceChildren(metricGrid([
     metric('BD work packets',M.bd_queue.length,'Five P1/P2 source-owned; one P0 human gate'),
     metric('Open issues',M.census.latest_observed_open,'Project-wide issue surface'),
     metric('Root closures credited',M.controls.formal_root_closure_credit_this_wave,'This communication wave only'),
     metric('Queue telemetry','UNKNOWN','No exact job p95')
  ]),bd());
  function jumpToLeaf() {
    const hash=decodeURIComponent(location.hash.slice(1));
    if(hash)requestAnimationFrame(()=>{
      const target=hash==='bd-register' ? $('bd-register') : [...c.querySelectorAll('[data-location-key]')].find(x=>x.dataset.locationKey===hash);
      if(target){target.classList.add('locator-highlight');target.scrollIntoView({block:'center'});}
    });
  }
  window.addEventListener('hashchange',jumpToLeaf);
  jumpToLeaf();
}
function slide(key,heading,items,details='') {
  activeView='deck';
  const s=E('section','slide'),top=E('div');
  add(top,E('div','eyebrow','CODE PURPLE / '+M.slug.toUpperCase()+' / '+key),E('h2','',heading));s.append(top);
  const content=E('div');items.flat().forEach(i=>content.append(i));s.append(content);
  const f=E('div','slide-footer');add(f,E('span','',details||'Read-only communication; no admission credit'),E('span','',M.presentation.publication.toUpperCase()));s.append(f);
  locate(s,'slide-'+key,heading,M.authorities.global_issue_controller);
  return s;
}
function deckInit() {
  const c=$('slides'),m=M.census,v=M.coverage.four_module;
  const first=slide('01','Fleet recovery: movement is real, CONTROL is not',[metricGrid([
      metric('Open issues',m.latest_observed_open,'Initial census 153'),
      metric('Net change',String(m.net_change),'Eleven issue transitions',true),
      metric('Root closure credit',M.controls.formal_root_closure_credit_this_wave,'Controller does not invent causal credit')
  ]),para('Nine dashboard notifications closed as duplicates; two DAB worker deliverables completed. All underlying source-admission obligations retained.')],'Executive / portfolio');
  const second=slide('02','Two-ended issue pressure: nine repositories',[repoBars(),para('Counts are a frozen, complete issue search. They are not nine independent PCA observations.')],'Portfolio / Mission Control');
  const third=slide('03','W16 native branch baseline, not global coverage',[metricGrid([
     metric('Four-module branches',pct(v.covered,v.eligible),`${v.covered}/${v.eligible} measured`),
     metric('Tests passing',M.coverage.tests_pass,'Exact source run '+M.coverage.native_run),
     metric('Phase 8 new reached arcs','+33','Same source blob, test cohort change')
  ]),para('Historical N14 200/446 is a different source epoch. A successful canonical B0 cannot imply B9 >=80% changed-line proof.')],'Source owner / test engineers');
  const fourth=slide('04','The first-red fault tree has distinct roots',[
    add(E('div','dagnodes'),...[['A10 HUMAN','generated report'],['PYTHON','specifier mismatch'],['ARIANA','missing defusedxml'],['B9','changed-line gate']].map(([a,b],i)=>locate(add(E('div'),E('strong','',a),E('small','',b)),'fault-'+String(i+1),a,M.authorities.admission_controller))),
    para('Each branch has its own required exact-head native proof. Do not mask or waive another branch.')
  ],'Engineering root triage');
  const fifth=slide('05','DOD is delivery; DOV is acceptance',[metricGrid([
    metric('DOD verified',statusCount(M.session_dod,'VERIFIED')+'/'+M.session_dod.length,'Session deliverable evidence'),
    metric('DOV PASS',statusCount(M.global_dov,'PASS')+'/'+M.global_dov.length,'Global verification only'),
    metric('DOV HOLD',statusCount(M.global_dov,'HOLD'),'Independent blockers remain')
  ]),para('Statistical CONTROL, PCA, Bradley-Terry and Six Sigma cannot be promoted from two mixed-epoch observations.')],'Review board / ownership');
  const sixth=slide('06','Next governed W18+3 execution',[...M.bd_queue.slice(0,5).map(x=>{
    const d=E('div','method');add(d,E('strong','',x.id+' - '+x.title),para(x.next));return d;
  })],'Controller / owner return conditions');
  const slides=[first,second,third,fourth,fifth,sixth];slides.forEach(s=>c.append(s));
  const prev=$('prev'),next=$('next'),indicator=$('slide-index');let active=0;
  const show=(i)=>{active=Math.max(0,Math.min(i,slides.length-1));slides.forEach((s,j)=>s.classList.toggle('active',j===active));indicator.textContent=(active+1)+' / '+slides.length;prev.disabled=active===0;next.disabled=active===slides.length-1;
    const hash='#slide-'+String(active+1).padStart(2,'0');if(location.hash!==hash)history.replaceState(null,'',hash);
  };
  prev.onclick=()=>show(active-1);next.onclick=()=>show(active+1);
  document.addEventListener('keydown',ev=>{if(['ArrowRight','PageDown'].includes(ev.key))show(active+1);else if(['ArrowLeft','PageUp'].includes(ev.key))show(active-1);});
  window.addEventListener('hashchange',()=>{const found=location.hash.match(/^#slide-(\d+)$/);if(found)show(Number(found[1])-1);});
  const query=location.hash.match(/^#slide-(\d+)$/);show(query?Number(query[1])-1:0);
}
initDevops();
$('master-hash').textContent=MASTER_SHA.slice(0,16)+'...';
if(mode==='dashboard')pageInit();if(mode==='cards')cardsInit();if(mode==='deck')deckInit();
})();
