"use strict";
/** W35 additive, read-only multi-DAG group/lasso/SIPOC/trigger/SPLINE/Mermaid adapter.
 * This script NEVER dispatches, mutates GitHub, invents runs, or awards approval.
 * All numerator/denominator and graph membership facts come from graph.json's
 * exact-head source-bound projection.
 */
(() => {
const dataNode=document.getElementById('source-model');
if(!dataNode)throw Error('W35_SOURCE_MODEL_NOT_EMBEDDED');
const m=JSON.parse(dataNode.textContent);
if(!m.groups||!m.mermaid||!m.group_topology)throw Error('W35_SOURCE_GROUPS_NOT_VERIFIED');
const bridge=window.SuperstitchBridge;
if(!bridge||typeof bridge.selectNode!=='function')throw Error('W35_PARENT_GRAPH_NOT_READY');
const nmap=new Map(m.nodes.map(n=>[n.id,n]));
const groups=new Map(m.groups.map(g=>[g.id,g]));
const rail=document.getElementById('group-rail');
const inspector=document.getElementById('group-inspector');
const linkedSummary=document.getElementById('linked-group-summary');
const linked=document.getElementById('linked-canvas');
const linkedNote=document.getElementById('view-mode-note');
const linkedMode=document.getElementById('view-mode');
const mermaidPre=document.getElementById('mermaid-code');
const mainSvg=document.querySelector('#graph-viewport svg');
const ns='http://www.w3.org/2000/svg';
let active=null, lassoEnabled=false, drag=null;
function elt(name,txt,cls){const x=document.createElement(name);if(txt!==undefined&&txt!==null)x.textContent=String(txt);if(cls)x.className=cls;return x}
function put(root,name,txt,cls){const x=elt(name,txt,cls);root.appendChild(x);return x}
function num(v){return Number.isFinite(v)?String(v):'UNKNOWN'}
function metricSet(g){
const obs=m.observations, counters=m.nodes.filter(n=>n.status==='ALIAS');
return g.metric_refs.map(id=>{
 if(id==='census')return {id,label:'Six-repository census',scope:'Historical canonical #531 population; not current breadth',covered:obs.historical_six_repo_breadth.observed,total:obs.historical_six_repo_breadth.eligible,cls:'HISTORICAL'};
 if(id==='authenticated')return {id,label:'CODEX → QPS receipt',scope:'Authenticated producer/consumer pair required',covered:obs.authenticated_codex_qps_pairs.observed,total:obs.authenticated_codex_qps_pairs.eligible,cls:'OWNER_DEFER'};
 if(id==='statements')return {id,label:'G3P statements',scope:'gg_MATH W33 · ONE module only',covered:obs.math_g3p_single_module.statements[0],total:obs.math_g3p_single_module.statements[1],cls:'HISTORICAL_NATIVE'};
 if(id==='branches')return {id,label:'G3P branches',scope:'gg_MATH W33 · SAME scope as statements',covered:obs.math_g3p_single_module.branches[0],total:obs.math_g3p_single_module.branches[1],cls:'HISTORICAL_NATIVE'};
 if(id==='alias_topology')return {id,label:'Shared canonical IDs',scope:'Layout topology only; no evidence/admission credit',covered:new Set(counters.map(n=>n.canonical_id)).size,total:3,cls:'TOPOLOGY_ONLY'};
 throw Error('W35_UNLISTED_METRIC_'+id)
})}
function receiptChip(group){const f=metricSet(group);if(!f.length)return 'PROOF UNKNOWN';if(f.length===1)return f[0].covered+'/'+f[0].total+' '+f[0].cls;if(f.length===2)return '2 scope-matched metrics';return f.length+' scoped facts'}
function svgRect(shape){const box=shape.querySelector('rect');if(!box)return null;return {x:+box.getAttribute('x'),y:+box.getAttribute('y'),w:+box.getAttribute('width'),h:+box.getAttribute('height')}}
const firstEdge=mainSvg.querySelector('.edge');
const hull=document.createElementNS(ns,'g');hull.id='w35-lasso-boundaries';hull.setAttribute('class','lasso-boundary');
if(firstEdge)mainSvg.insertBefore(hull,firstEdge);else mainSvg.appendChild(hull);
function nodeElement(id){return [...mainSvg.querySelectorAll('.graph-node')].find(x=>x.dataset.node===id)}
function groupedRects(g){
 const lanes=new Map();
 g.nodes.forEach(id=>{const shape=nodeElement(id);if(!shape)return;const b=svgRect(shape);if(!b)return;const lane=nmap.get(id)?.lane||'unknown';const arr=lanes.get(lane)||[];arr.push(b);lanes.set(lane,arr)});
 return [...lanes.entries()].map(([lane,arr])=>({lane,
  x:Math.max(182,Math.min(...arr.map(x=>x.x))-9),
  y:Math.min(...arr.map(x=>x.y))-9,
  right:Math.max(...arr.map(x=>x.x+x.w))+9,
  bottom:Math.max(...arr.map(x=>x.y+x.h))+9}));
}
function clearVisual(){
 hull.replaceChildren();
 mainSvg.querySelectorAll('.graph-node').forEach(x=>x.classList.remove('group-member','group-outside'));
 mainSvg.querySelectorAll('.edge').forEach(x=>x.classList.remove('group-edge','group-outside'));
}
function drawGroup(g){
 clearVisual();const members=new Set(g.nodes);
 const shapes=[...mainSvg.querySelectorAll('.graph-node')];
 shapes.forEach(x=>{x.classList.toggle('group-member',members.has(x.dataset.node));x.classList.toggle('group-outside',!members.has(x.dataset.node))});
 mainSvg.querySelectorAll('.edge').forEach(e=>{
   const a=members.has(e.dataset.from),b=members.has(e.dataset.to);
   e.classList.toggle('group-edge',a&&b);e.classList.toggle('group-outside',!(a&&b));
 });
 for(const b of groupedRects(g)){
  const rr=document.createElementNS(ns,'rect');
  rr.setAttribute('x',String(b.x));rr.setAttribute('y',String(b.y));
  rr.setAttribute('width',String(b.right-b.x));rr.setAttribute('height',String(b.bottom-b.y));
  rr.setAttribute('rx','15');rr.setAttribute('data-group-bound',g.id);hull.appendChild(rr);
  const title=document.createElementNS(ns,'text');title.setAttribute('x',String(b.x+9));
  title.setAttribute('y',String(Math.max(b.y+12,b.bottom-1)));title.textContent=g.label+' · '+b.lane.toUpperCase();hull.appendChild(title);
 }
}
function makeBurndown(parent,g){
 const box=put(parent,'div',null,'group-debt');put(box,'h3','Purple burndown · '+g.label);
 const mm=metricSet(g);
 if(!mm.length){put(box,'div','Measured gate numerators/denominators: UNKNOWN','debt-copy');put(box,'div',null,'unknown');
 put(box,'p','Defined nodes are topology, not native completions. No 0% bar is invented.','debt-copy');}
 for(const v of mm){
  if(!Number.isInteger(v.covered)||!Number.isInteger(v.total)||v.total<1||v.covered<0||v.covered>v.total)throw Error('W35_COVERAGE_SCOPE_INVALID');
  const r=put(box,'div',null,'kpi');put(r,'span',v.label);put(r,'strong',v.covered+'/'+v.total);
  const track=put(box,'div',null,'bar');track.setAttribute('role','progressbar');
  track.setAttribute('aria-label',v.label+' · '+v.cls);track.setAttribute('aria-valuemin','0');track.setAttribute('aria-valuemax',String(v.total));track.setAttribute('aria-valuenow',String(v.covered));
  const f=put(track,'div',null,'fill');f.style.width=String(Math.min(100,Math.max(0,100*v.covered/v.total)))+'%';
  put(box,'p',(v.total-v.covered)+' outstanding / not observed · '+v.cls+' · '+v.scope,'debt-copy');
 }
 return box
}
function updateDetail(g){
 inspector.replaceChildren();makeBurndown(inspector,g);
 put(inspector,'div',(g.explanation||'UI-only bounded source group'),'small');
 const topo=m.group_topology[g.id];
 if(topo)put(inspector,'div',topo.node_placements+' drawn placements · '+topo.internal_typed_edges+' internal typed edges · '+topo.alias_placements+' aliases · '+topo.touch_edges+' touch edges','small');
 const list=put(inspector,'ul',null,'group-sublist');
 g.nodes.forEach(id=>{
  const n=nmap.get(id);if(!n)return;const li=put(list,'li');const b=put(li,'button',n.label+' ↗');b.type='button';b.addEventListener('click',()=>bridge.selectNode(id));
  put(li,'span',' '+n.canonical_id+' / '+n.status,'small');
 });
 linkedSummary.replaceChildren();put(linkedSummary,'strong',g.label);put(linkedSummary,'p',g.explanation||'Selected on-screen group','small');
 const a=put(linkedSummary,'p',g.nodes.length+' placements; '+new Set(g.nodes.map(id=>nmap.get(id)?.canonical_id)).size+' canonical identities.','small');
 a.setAttribute('data-selection-count',String(g.nodes.length));
 if(!metricSet(g).length)put(linkedSummary,'p','Runtime work and worker-hours: UNKNOWN · selected topology only','small');
}
function renderGroupChild(g){
 const target=document.getElementById('group-child-view');target.replaceChildren();
 const clone=mainSvg.cloneNode(true);clone.id='group-child-svg';clone.removeAttribute('aria-hidden');
 clone.querySelector('#w35-lasso-boundaries')?.remove();
 const ids=new Set(g.nodes);
 clone.querySelectorAll('.graph-node').forEach(x=>{
  x.classList.remove('dim','related','selected','group-member','group-outside','hidden');
  if(!ids.has(x.dataset.node))x.remove();
  else{x.addEventListener('click',()=>bridge.selectNode(x.dataset.node));x.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();bridge.selectNode(x.dataset.node)}})}
 });
 clone.querySelectorAll('.edge').forEach(x=>{
  if(!ids.has(x.dataset.from)||!ids.has(x.dataset.to))x.remove();
  else x.classList.remove('hidden','dim','emphasis','group-outside','group-edge')
 });
 // Keep only lane labels for actually touched lanes. Reuse SVG positions.
 const bounds=groupedRects(g);
 if(bounds.length){const x0=Math.max(0,Math.min(...bounds.map(b=>b.x))-24),
 x1=Math.min(1430,Math.max(...bounds.map(b=>b.right))+25),
 y0=Math.max(0,Math.min(...bounds.map(b=>b.y))-20),
 y1=Math.min(610,Math.max(...bounds.map(b=>b.bottom))+20);
 clone.setAttribute('viewBox',`${x0} ${y0} ${Math.max(150,x1-x0)} ${Math.max(100,y1-y0)}`);
 clone.removeAttribute('width');clone.removeAttribute('height');}
 const desc=document.createElementNS(ns,'title');desc.textContent='Bounded child DAG for '+g.label+'; selected nodes source-only';clone.insertBefore(desc,clone.firstChild);
 target.appendChild(clone);
}
function updateMermaid(){
 let text='';const mode=linkedMode.value;
 if(mode==='sipoc')text=m.mermaid.sipoc;
 else if(mode==='trigger')text=m.mermaid.triggers;
 else if(active?.id&&m.mermaid.groups[active.id])text=m.mermaid.groups[active.id];
 else text=m.mermaid.dag;
 mermaidPre.textContent=text;
}
function modeSwitch(value){
 [...document.querySelectorAll('.linked-visual[data-view]')].forEach(el=>{el.hidden=el.dataset.view!==value});
 let msg={group:'Clickable bounded child DAG · original canonical node IDs',sipoc:'SIPOC five stages are an alternate source-oriented view of the DAG',trigger:'Only typed trigger, dependency and federation source edges; no dispatch proof',spline:'Historical N−1/N only; no extrapolated future value',mermaid:'Generated, editable Mermaid source; never a live engine'};
 linkedNote.textContent=msg[value]||'UNKNOWN_VIEW';
 updateMermaid();
}
function markChips(id){rail.querySelectorAll('button.group-chip').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.group===id)))}
function selectGroup(groupOrId){
 const g=typeof groupOrId==='string'?groups.get(groupOrId):groupOrId;
 if(!g)throw Error('UNKNOWN_LASSO_GROUP');
 active=g;
 const lens=document.getElementById('lens');const depth=document.getElementById('depth');
 if(lens.value!=='all'||depth.value!=='3'){lens.value='all';depth.value='3';bridge.applyFilters()}
 bridge.resetEmphasis();drawGroup(g);updateDetail(g);renderGroupChild(g);markChips(g.id);updateMermaid();
 document.getElementById('graph-viewport').classList.toggle('lasso-active',lassoEnabled);
 return g
}
for(const g of m.groups){
 const b=put(rail,'button',null,'group-chip');b.type='button';b.dataset.group=g.id;b.setAttribute('aria-pressed','false');
 b.setAttribute('aria-label','Bound the '+g.label+' DAG');put(b,'b',g.label);put(b,'span',receiptChip(g));
 b.addEventListener('click',()=>selectGroup(g.id));
}
// SVG lens with group ids comes from exact-source SIPOC columns.
linked.querySelectorAll('.sipoc-group').forEach(el=>{
 function pick(){selectGroup(el.dataset.group)};
 el.addEventListener('click',pick);el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick()}});
});
linked.querySelectorAll('#trigger-dag-view .graph-node').forEach(el=>{
 const fn=()=>{bridge.selectNode(el.dataset.node);const g=m.groups.find(g=>g.nodes.includes(el.dataset.node));if(g)selectGroup(g.id)};
 el.addEventListener('click',fn);el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();fn()}});
});
// Existing SIPOC table is generated by the W34 app before this extension runs.
const rowGroupMap=new Map(m.groups.filter(g=>g.sipoc_row!==null).map(g=>[g.sipoc_row,g.id]));
document.querySelectorAll('#sipoc-table tbody tr').forEach((tr,i)=>{
 tr.dataset.group=rowGroupMap.get(i)||'';tr.tabIndex=0;
 tr.setAttribute('aria-label','Select SIPOC process lane '+(i+1));
 tr.addEventListener('click',()=>{if(tr.dataset.group)selectGroup(tr.dataset.group)});
 tr.addEventListener('keydown',e=>{if(e.key==='Enter'&&tr.dataset.group){e.preventDefault();selectGroup(tr.dataset.group)}});
});
const triggerList=document.getElementById('trigger-edge-list');
put(triggerList,'h4','Typed source trigger/dependency interfaces');
m.edges.filter(e=>['TRIGGER','RETRIGGER','FEDERATION','DEPENDENCY'].includes(e.kind)).forEach(e=>{
 const b=put(triggerList,'button',`${e.kind} · ${e.from} → ${e.to} · ${e.binding}`);
 b.type='button';b.addEventListener('click',()=>{bridge.selectNode(e.to);const g=m.groups.find(g=>g.nodes.includes(e.to));if(g)selectGroup(g.id)})
});
linked.querySelectorAll('#spline-large-view [data-pulse]').forEach(el=>{
  function inspectPulse(){selectGroup('mc-control');
    const pulse=el.getAttribute('data-pulse');
    const msg=pulse==='N+1'?'N+1: UNKNOWN; no forward evidence or interpolated point':pulse+': HISTORICAL 6/42 source cells';
    put(linkedSummary,'p',msg,'small');linkedNote.textContent=msg;}
  el.addEventListener('click',inspectPulse);
  el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();inspectPulse()}});
});
linkedMode.addEventListener('change',e=>modeSwitch(e.target.value));
document.getElementById('mermaid-copy').addEventListener('click',async()=>{
 const b=document.getElementById('mermaid-copy');
 try{await navigator.clipboard.writeText(mermaidPre.textContent);b.textContent='Copied Mermaid'}
 catch(_){b.textContent='Select source text to copy'}
});
const lassoBtn=document.getElementById('lasso-enable');
lassoBtn.addEventListener('click',()=>{
 lassoEnabled=!lassoEnabled;lassoBtn.setAttribute('aria-pressed',String(lassoEnabled));lassoBtn.textContent=lassoEnabled?'Lasso region · ON':'Lasso region · off';
 document.getElementById('graph-viewport').classList.toggle('lasso-active',lassoEnabled);
});
document.getElementById('lasso-clear').addEventListener('click',()=>{
 active=null;clearVisual();bridge.resetEmphasis();inspector.replaceChildren();linkedSummary.textContent='Group lasso cleared; choose a bounded group for child DAG and source-scoped burndown.';markChips('');
});
function point(e){const p=mainSvg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;const ctm=mainSvg.getScreenCTM();return ctm?p.matrixTransform(ctm.inverse()):null}
function freehandStart(e){
 if(!lassoEnabled||e.button!==0||e.target.closest('.graph-node'))return;
 const p=point(e);if(!p)return;drag={start:p,last:p,id:e.pointerId};try{mainSvg.setPointerCapture(e.pointerId)}catch(_){/* capture optional */}
}
function freehandMove(e){
 if(!drag)return;const p=point(e);if(!p)return;drag.last=p;
 hull.querySelector('.temporary-lasso')?.remove();
 const r=document.createElementNS(ns,'rect');r.setAttribute('class','temporary-lasso');
 r.setAttribute('x',String(Math.min(drag.start.x,p.x)));r.setAttribute('y',String(Math.min(drag.start.y,p.y)));
 r.setAttribute('width',String(Math.abs(drag.start.x-p.x)));r.setAttribute('height',String(Math.abs(drag.start.y-p.y)));r.setAttribute('rx','5');hull.appendChild(r);
}
function freehandFinish(e){
 if(!drag)return;const p=point(e)||drag.last;const a=drag.start;drag=null;hull.querySelector('.temporary-lasso')?.remove();
 const x0=Math.min(a.x,p.x),x1=Math.max(a.x,p.x),y0=Math.min(a.y,p.y),y1=Math.max(a.y,p.y);
 if(x1-x0<20||y1-y0<15)return;
 const selected=[...mainSvg.querySelectorAll('.graph-node')].filter(x=>{
  const b=svgRect(x);if(!b)return false;
  const cx=b.x+b.w/2,cy=b.y+b.h/2;return cx>=x0&&cx<=x1&&cy>=y0&&cy<=y1
 }).map(x=>x.dataset.node);
 if(selected.length<2){linkedNote.textContent='Lasso contains fewer than two blocks · no source group created';return;}
 const g={id:'ui-lasso-only',label:'Local lasso · '+selected.length+' blocks',kind:'UI_ONLY',nodes:selected,metric_refs:[],
  explanation:'User-selected visual grouping only; this is not a new source-authored owner group, receipt, worker or native gate.'};
 selectGroup(g);
}
mainSvg.addEventListener('pointerdown',freehandStart);
mainSvg.addEventListener('pointermove',freehandMove);
mainSvg.addEventListener('pointerup',freehandFinish);
mainSvg.addEventListener('pointercancel',()=>{drag=null;hull.querySelector('.temporary-lasso')?.remove()});
// An initial bounded group is made visible without collapsing the full graph.
selectGroup('golden-thread');
modeSwitch('group');
window.SuperstitchW35={selectGroup,modeSwitch,metricSet,release:'SOURCE_ONLY_PROPOSED'};
})();
