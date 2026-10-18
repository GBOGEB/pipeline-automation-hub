"use strict";
(() => {
const m=JSON.parse(document.getElementById('source-model').textContent);
const byId=new Map(m.nodes.map(n=>[n.id,n]));
const ref=new Map(m.source_refs.map(s=>[s.id,s]));
const laneNames=new Map(m.lanes.map(l=>[l.id,l.title]));
const svg=document.querySelector('.graph-viewport svg');
const gn=[...svg.querySelectorAll('.graph-node')];
const ge=[...svg.querySelectorAll('.edge')];
const graphViewport=document.getElementById('graph-viewport');
const selected={id:null,expanded:false};
const E=(tag,text,cls)=>{const v=document.createElement(tag);if(text!==undefined)v.textContent=text;if(cls)v.className=cls;return v};
const div=(parent,text,cls)=>{const v=E('div',text,cls);parent.appendChild(v);return v};
const add=(parent,tag,text,cls)=>{const v=E(tag,text,cls);parent.appendChild(v);return v};
const unknown=v=>v===null||v===undefined?'UNKNOWN':String(v);
function referenceUrl(s){if(!s||s.classification.startsWith('PRIVATE_'))return null;return `https://github.com/${s.repo}/blob/${s.head}/${s.path}`;}
function focusNode(id){
  const n=svg.querySelector(`[data-node="${id}"]`);
  if(!n)return;
  n.scrollIntoView({block:'nearest',inline:'center',behavior:'smooth'});
  const nEdges=m.edges.filter(e=>e.from===id||e.to===id);
  const connected=new Set([id]);nEdges.forEach(e=>{connected.add(e.from);connected.add(e.to)});
  const canonical=byId.get(id).canonical_id;
  m.nodes.filter(x=>x.canonical_id===canonical).forEach(x=>connected.add(x.id));
  gn.forEach(x=>{x.classList.toggle('selected',x.dataset.node===id);x.classList.toggle('related',x.dataset.node!==id&&connected.has(x.dataset.node));x.classList.toggle('dim',!connected.has(x.dataset.node));});
  ge.forEach(x=>{const touches=connected.has(x.dataset.from)&&connected.has(x.dataset.to);x.classList.toggle('emphasis',touches);x.classList.toggle('dim',!touches)});
}
function resetEmphasis(){gn.forEach(x=>x.classList.remove('selected','related','dim'));ge.forEach(x=>x.classList.remove('emphasis','dim'));}
function selectNode(id, expand=true){
  const n=byId.get(id);if(!n)return;selected.id=id;selected.expanded=expand;focusNode(id);
  const d=document.getElementById('detail-inner');d.replaceChildren();
  const h=add(d,'h3',n.label);h.style.margin='3px 0';
  add(d,'span',n.status,'badge');div(d,n.detail,'small');
  const dl=add(d,'dl');dl.style.cssText='display:grid;grid-template-columns:72px 1fr;gap:6px;font-size:11px;margin-top:13px';
  [['Canonical',n.canonical_id],['Owner',laneNames.get(n.lane)],['Stage',n.phase],['Binding',n.status],['Source',n.source]].forEach(([k,v])=>{add(dl,'dt',k).style.color='#9eadca';add(dl,'dd',v).style.cssText='margin:0;overflow-wrap:anywhere'});
  div(d,n.description||'This is a typed source-model node, not a current runtime or acceptance receipt.','small');
  const siblings=m.nodes.filter(x=>x.canonical_id===n.canonical_id&&x.id!==id);
  if(siblings.length){add(d,'h4','Shared / duplicated placements');for(const s of siblings){const b=add(d,'button','↪ '+s.label);b.type='button';b.addEventListener('click',()=>selectNode(s.id))}}
  if(expand){add(d,'h4','Sub-process / owned depth');const ul=add(d,'ul');n.children.forEach(child=>add(ul,'li',child));
    add(d,'h4','Adjacent evidence / dependency edges');const list=add(d,'ul');m.edges.filter(e=>e.from===id||e.to===id).forEach(e=>add(list,'li',`${e.kind}: ${e.from} → ${e.to} [${e.binding}]`));}
  const actions=document.getElementById('detail-actions');actions.replaceChildren();
  const t=add(actions,'button',expand?'Collapse detail':'Expand detail');t.type='button';t.addEventListener('click',()=>selectNode(id,!expand));
  const u=referenceUrl(ref.get(n.source));if(u){const a=add(actions,'a','Source ↗');a.href=u;a.target='_blank';a.rel='noopener noreferrer'}
  const b=add(actions,'button','Show all');b.type='button';b.addEventListener('click',showAll);
}
function applyFilters(){
  const lane=document.getElementById('lens').value;
  const depth=Number(document.getElementById('depth').value);
  let active=new Set();
  for(const n of m.nodes){
    const keep=(lane==='all'||n.lane===lane|| (lane==='qps'&&n.id==='keb-receipt') || (lane==='dow'&&n.id==='qps-source'))&&n.level<=depth;
    const shape=gn.find(x=>x.dataset.node===n.id);if(shape)shape.classList.toggle('hidden',!keep);
    if(keep)active.add(n.id)
  }
  ge.forEach(x=>x.classList.toggle('hidden',!active.has(x.dataset.from)||!active.has(x.dataset.to)||
    (x.dataset.kind==='TOUCH'&&document.getElementById('touch-toggle').getAttribute('aria-pressed')!=='true')));
  resetEmphasis();
}
function showAll(){document.getElementById('lens').value='all';document.getElementById('depth').value='3';
  document.getElementById('touch-toggle').setAttribute('aria-pressed','true');document.getElementById('touch-toggle').textContent='Touches on';
  document.getElementById('labels-toggle').setAttribute('aria-pressed','true');document.getElementById('labels-toggle').textContent='Labels on';
  graphViewport.classList.remove('hide-labels');applyFilters();selected.id=null;
  document.getElementById('detail-inner').textContent='All DAGs uncollapsed. Select a block to inspect its owned depth and exact source identity.';
  document.getElementById('detail-actions').replaceChildren();graphViewport.scrollLeft=0;
}
for(const shape of gn){shape.addEventListener('click',()=>selectNode(shape.dataset.node));shape.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectNode(shape.dataset.node)}})}
['lens','depth'].forEach(id=>document.getElementById(id).addEventListener('change',applyFilters));
document.getElementById('show-all').addEventListener('click',showAll);
document.getElementById('focus-reset').addEventListener('click',()=>{resetEmphasis();graphViewport.scrollLeft=0;graphViewport.scrollTop=0;});
document.getElementById('touch-toggle').addEventListener('click',e=>{const pressed=e.currentTarget.getAttribute('aria-pressed')==='true';e.currentTarget.setAttribute('aria-pressed',String(!pressed));e.currentTarget.textContent=!pressed?'Touches on':'Touches off';applyFilters()});
document.getElementById('labels-toggle').addEventListener('click',e=>{const pressed=e.currentTarget.getAttribute('aria-pressed')==='true';e.currentTarget.setAttribute('aria-pressed',String(!pressed));e.currentTarget.textContent=!pressed?'Labels on':'Labels off';graphViewport.classList.toggle('hide-labels',pressed)});
document.getElementById('expand-all').addEventListener('click',()=>{const d=document.getElementById('detail-inner');d.replaceChildren();add(d,'h3','All canonical sub-processes · '+m.nodes.length+' placements');
  m.nodes.filter(n=>n.status!=='ALIAS').forEach(n=>{const details=add(d,'details');const sum=add(details,'summary',n.label);sum.style.cursor='pointer';const ul=add(details,'ul');n.children.forEach(c=>add(ul,'li',c));});
  document.getElementById('detail-actions').replaceChildren();});
const groups=new Map();m.nodes.forEach(n=>{const a=groups.get(n.canonical_id)||[];a.push(n);groups.set(n.canonical_id,a)});
const dup=[...groups].filter(([_,a])=>a.length>1);
const x=document.getElementById('duplicate-summary');add(x,'strong',`${m.nodes.length} drawn placements · ${groups.size} canonical identities · ${dup.length} repeated identities`);
const ul=add(x,'ul');dup.forEach(([id,items])=>add(ul,'li',`${id}: ${items.length} placements`));
const SIP=document.querySelector('#sipoc-table tbody');m.sipoc.forEach(row=>{const tr=add(SIP,'tr');['supplier','input','process','output','customer'].forEach(k=>add(tr,'td',row[k]))});
const matrix=document.getElementById('touch-matrix');const mt=matrix.querySelector('thead');const mr=add(mt,'tr');add(mr,'th','From ↓ / To →');m.lanes.forEach(l=>add(mr,'th',l.id.toUpperCase()));
for(const origin of m.lanes){const tr=add(matrix.querySelector('tbody'),'tr');add(tr,'th',origin.id.toUpperCase());for(const dest of m.lanes){const count=m.edges.filter(e=>byId.get(e.from).lane===origin.id&&byId.get(e.to).lane===dest.id).length;const td=add(tr,'td',count?String(count):'·');td.style.color=count?'#93c9ff':'#536582'}}
const activity=document.querySelector('#activity-table tbody');
const activityRows=[['ABACUS / DOW','DECLARED','No W34 run','Source definitions'],['CODEX / KEB','DECLARED','No W34 consumer receipt','Source definitions'],['MC #530','#530 ROLE','Canonical ZIP verifier','Not current run'],['MC #531','6/42 HISTORIC','Six-repo census','Prior report'],['MC #533','HISTORIC PASS','74/74 method cases','Prior exact head'],['gg_MATH / W33','HISTORIC PASS','172/172 · 84/84','Run 39170751291'],['QPS / child','OWNER HOLD','0/1 authenticated pairs','Private / DEFER'],['W34 Superstitch','PROPOSED','No native run yet','Local projection only']];
activityRows.forEach(row=>{const tr=add(activity,'tr');row.forEach((v,i)=>add(tr,'td',v))});
const stages=[['F0','Discover'],['F1','Preflight SHA'],['F2','Fast contracts'],['F3','Seeded matrix'],['F4','Local receipt'],['F5','Native PR'],['F6','Method proof'],['F7','Federate / HOLD']];
const fs=document.getElementById('flight-stages');stages.forEach(([step,desc])=>{const block=add(fs,'div',undefined,'flight-item');add(block,'strong',step);add(block,'span',desc)});
const glossary=m.glossary.terms.map(x=>[x.term,x.definition]);
const terms=document.getElementById('terms');glossary.forEach(([a,b])=>{const p=add(terms,'div',undefined,'term');add(p,'strong',a);add(p,'span',b)});
document.getElementById('snapshot-head').textContent=m.publication.presentation_head.slice(0,12)+'…';
showAll();
})();
