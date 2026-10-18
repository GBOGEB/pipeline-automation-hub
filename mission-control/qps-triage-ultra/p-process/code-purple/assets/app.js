// Code Purple page behaviour: rendering, hover cards, tabs, live census refresh, downloads.
// Reads the model from assets/model.js (loaded first).
(function(){
"use strict";
const {PH,KIND,LANE,STATUS,EKIND,NODES,EDGES,STAGES,LSTATES,TRIGGERS,WIRED,TEL_RECORDED,TEL_EXAMPLE} = globalThis.CP_MODEL;
function renderLifecycle(){
 const M=k=>`<marker id="l-${k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="m-${k}" d="M0,0 L10,5 L0,10 z"/></marker>`;
 let s=`<svg viewBox="0 0 1000 340" role="img" aria-label="Lifecycle state machine with numbered triggers" style="min-width:760px"><defs>${Object.keys(EKIND).map(M).join("")}</defs>`;
 TRIGGERS.forEach(t=>{s+=`<path class="edge e-${t.k}" d="${t.d}" marker-end="url(#l-${t.k})"/>`});
 LSTATES.forEach(st=>{const w=130,h=46,cls=st.k==="dec"?"n-dec":"n-"+st.k;
  s+=`<g class="node static ${cls}"><rect class="b" x="${st.x}" y="${st.y}" width="${w}" height="${h}" rx="9"/><text class="t" x="${st.x+w/2}" y="${st.y+20}" style="font-size:13px">${esc(st.label)}</text><text class="s" x="${st.x+w/2}" y="${st.y+36}" style="font-size:10.5px">${esc(st.sub)}</text></g>`});
 TRIGGERS.forEach(t=>{const mid=t.lab?{x:t.lx,y:t.ly}:null;
  const tw=(t.id.length*6.6+10);let x,y;
  if(mid){const lw=textW([t.id+" "+t.lab]);s+=`<g class="elab ${t.k}"><rect x="${mid.x-lw/2}" y="${mid.y-8.5}" width="${lw}" height="17" rx="8"/><text x="${mid.x}" y="${mid.y+3.5}"><tspan font-weight="600">${t.id}</tspan> ${esc(t.lab)}</text></g>`}
  else{const m=t.d.match(/M(\d+),(\d+) L(\d+),(\d+)/);x=(+m[1]+ +m[3])/2;y=(+m[2]+ +m[4])/2;
   s+=`<g class="elab ${t.k}"><rect x="${x-tw/2}" y="${y-22}" width="${tw}" height="15" rx="7"/><text x="${x}" y="${y-11}" style="font-size:9.5px">${t.id}</text></g>`}
 });
 s+=`</svg>`;
 $("#lifeSvg").innerHTML=s;
 $("#trigT").innerHTML=`<thead><tr><th>ID</th><th>From → to</th><th>Trigger event</th><th>Guard</th><th>Action and evidence</th><th>Nodes</th><th>Wired today</th></tr></thead><tbody>`+
  TRIGGERS.map(t=>{const F=LSTATES.find(x=>x.id===t.f).label,T=LSTATES.find(x=>x.id===t.t).label;
   const wc=t.w==="wired"?"ok":t.w==="partial"?"partial":t.w==="manual"?"hold":"proposed";
   return `<tr style="cursor:default"><td class="idb">${t.id}</td><td style="white-space:nowrap">${esc(F)} → ${esc(T)}</td><td>${esc(t.ev)}</td><td style="font-size:12.5px">${esc(t.guard)}</td><td>${esc(t.act)}</td><td><div class="refs">${t.nodes.map(refBtn).join("")}</div></td><td><span class="${wc==="proposed"?"wired proposed":"st-pill "+wc}">${WIRED[t.w]}</span><div class="muted" style="font-size:12px;margin-top:4px;max-width:32ch">${esc(t.wn)}</div></td></tr>`}).join("")+`</tbody>`;
}
/* ================= TELEMETRY ================= */
let TEL_LOADED=null;

/* ================= STATE / HELPERS ================= */
const S={mode:"role",src:"recorded",sel:{type:"node",id:"N09"},trace:null,live:true};
const byId=Object.fromEntries(NODES.map(n=>[n.id,n]));
const eById=Object.fromEntries(EDGES.map(e=>[e.id,e]));
const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const tel=()=>S.src==="example"?TEL_EXAMPLE:S.src==="loaded"&&TEL_LOADED?TEL_LOADED:TEL_RECORDED;
const nt=id=>(tel().nodes||{})[id]||null;
function agg(runs){const a={att:0,pass:0,fail:0,neu:0,pend:0};(runs||[]).forEach(r=>{a.att+=+r.attempts||0;a.pass+=+r.pass||0;a.fail+=+r.fail||0;a.neu+=+r.neutral||0;a.pend+=+r.pending||0});
 const dec=a.pass+a.fail;a.rate=dec?a.pass/dec:null;a.done=a.att?(a.pass+a.fail+a.neu)/a.att:null;return a}
const pct=v=>v==null?"—":Math.round(v*100)+"%";
const ins=id=>EDGES.filter(e=>e.t===id), outs=id=>EDGES.filter(e=>e.f===id);
function rateClass(r){return r==null?"s-none":r>=.9?"s-ok":r>=.5?"s-hold":"s-block"}
function nodeClass(n){if(S.mode==="status")return "s-"+n.status;if(S.mode==="rate")return rateClass(agg(nt(n.id)?.runs).rate);return "n-"+n.kind}
function rbar(a){if(!a.att)return '<div class="rbar"></div>';const w=v=>(v/a.att*100).toFixed(2)+"%";
 return `<div class="rbar" title="${a.pass} pass · ${a.fail} fail · ${a.neu} neutral · ${a.pend} pending"><span class="p" style="width:${w(a.pass)}"></span><span class="f" style="width:${w(a.fail)}"></span><span class="n" style="width:${w(a.neu)}"></span><span class="q" style="width:${w(a.pend)}"></span></div>`}
function pchip(label,v){const c=v==null?"none":v;return `<span class="pchip ${esc(c)}">${esc(label)}: ${esc(v??"—")}</span>`}
const refBtn=id=>`<button class="ref" data-ref="${id}">${id}</button>`;

/* ================= GRAPH ================= */
function textW(lines){return Math.max(...lines.map(l=>[...l].length))*6.35+14}
function renderGraph(){
 const M=k=>`<marker id="a-${k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="m-${k}" d="M0,0 L10,5 L0,10 z"/></marker>`;
 let s=`<svg id="g" viewBox="0 0 1000 1120" role="img" aria-label="Code Purple execution pulse graph"><defs>${Object.keys(EKIND).map(M).join("")}</defs>`;
 s+=`<rect class="lane-bg" x="20" y="44" width="320" height="1062" rx="10"/><rect class="lane-bg" x="360" y="44" width="320" height="1062" rx="10"/><rect class="lane-bg" x="700" y="44" width="280" height="1062" rx="10"/>`;
 s+=`<text class="lane-t" x="34" y="32">EVIDENCE · HOLD</text><text class="lane-t" x="374" y="32">ADMISSION SPINE</text><text class="lane-t" x="714" y="32">REPAIR LOOP</text>`;
 EDGES.forEach(e=>{s+=`<path class="edge e-${e.k}" data-eid="${e.id}" data-f="${e.f}" data-t="${e.t}" d="${e.d}" marker-end="url(#a-${e.k})"/>`});
 EDGES.forEach(e=>{if(!e.lab)return;const w=textW(e.lab),h=e.lab.length*17;const tr=e.rot?` transform="rotate(${e.rot} ${e.lx} ${e.ly})"`:"";
  s+=`<g class="elab ${e.k}" data-f="${e.f}" data-t="${e.t}"${tr}><rect x="${e.lx-w/2}" y="${e.ly-h/2}" width="${w}" height="${h}" rx="8"/>`;
  e.lab.forEach((l,i)=>{s+=`<text x="${e.lx}" y="${e.ly-h/2+12.5+i*14}">${esc(l)}</text>`});s+=`</g>`});
 EDGES.forEach(e=>{s+=`<path class="hitp" data-eid="${e.id}" d="${e.d}"><title>${e.id} · ${e.f} → ${e.t} · ${esc(e.m)}</title></path>`});
 NODES.forEach(n=>{s+=nodeSVG(n)});
 if(S.live) s+=`<g>
  <polygon class="ring" points="520,726 676,780 520,834 364,780"/>
  <g class="callout"><line x1="716" y1="760" x2="664" y2="780"/><rect class="cb" x="716" y="700" width="262" height="150" rx="8"/>
   <text class="ct" x="730" y="720">ABACUS #1858 · HEAD e7616e62</text><text class="cv" x="730" y="740">PR Feedback Gate: FAILURE</text>
   <rect class="seg-pass" x="730" y="750" width="213.2" height="10"/><rect class="seg-fail" x="943.2" y="750" width="14.4" height="10"/><rect class="seg-neu" x="957.6" y="750" width="2.4" height="10"/>
   <text x="730" y="778">87 pass · 2 red so far · 8 running</text>
   <text x="730" y="796">threads resolved · #1878 #1879 opened</text><text x="730" y="814">Codex code + security review pending</text>
   <text x="730" y="838" style="font-size:11px;opacity:.85">all remaining reds also fail on main</text></g>
  <rect class="ring rep" x="373" y="939" width="294" height="70" rx="14"/>
  <g class="callout rep"><line x1="716" y1="960" x2="668" y2="974"/><rect class="cb" x="716" y="880" width="262" height="160" rx="8"/>
   <text class="ct" x="730" y="900">CODEX #984 · MERGED 12:16 CEST</text><text class="cv" x="730" y="920">Merged with 4 red checks</text>
   <rect class="seg-pass" x="730" y="930" width="214.4" height="10"/><rect class="seg-fail" x="944.4" y="930" width="15.6" height="10"/>
   <text x="730" y="958">ruff · governance-gate ×2 · validate</text>
   <text x="730" y="976">main 768c9e35: 38 pass · 2 fail</text><text x="730" y="994">(validate, scheduled osv-scan)</text>
   <text x="730" y="1018" style="font-size:11px;opacity:.85">CODEX main has no required-check ruleset</text><text x="730" y="1032" style="font-size:11px;opacity:.85">main now 6edf28b7: 9 pass · 8 skipped</text></g></g>`;
 s+=`</svg>`;
 $("#canvas").innerHTML=s;
 const svg=$("#g");
 svg.querySelectorAll(".node").forEach(g=>{
  const id=g.dataset.id;
  g.addEventListener("click",()=>select("node",id));
  g.addEventListener("keydown",ev=>{if(ev.key==="Enter"||ev.key===" "){ev.preventDefault();select("node",id)}});
  g.addEventListener("focus",()=>{const r=g.getBoundingClientRect();showCard(id,r.right+8,r.top)});
  g.addEventListener("blur",hideCard);
  g.querySelectorAll(".hot").forEach(h=>{h.addEventListener("mouseenter",ev=>showCard(id,ev.clientX+14,ev.clientY+14));h.addEventListener("mousemove",ev=>placeCard(ev.clientX+14,ev.clientY+14));h.addEventListener("mouseleave",hideCard)});
 });
 svg.querySelectorAll(".hitp").forEach(p=>p.addEventListener("click",()=>select("edge",p.dataset.eid)));
 applyTrace();applySel();
}
function hot(x,y,w,h,label,tx,ty,cls){return `<g class="hot"><rect class="hit" x="${x-3}" y="${y-3}" width="${w+6}" height="${h+6}"/>${cls?`<rect class="${cls}" x="${x}" y="${y}" width="${w}" height="${h}" rx="3"/>`:""}<text class="${cls?"tgt":"nid"}" x="${tx}" y="${ty}">${label}</text></g>`}
function nodeSVG(n){
 const a=agg(nt(n.id)?.runs);
 let s=`<g class="node ${nodeClass(n)}" data-id="${n.id}" tabindex="0" role="button" aria-label="${n.id} ${esc(n.label)}">`;
 if(n.shape==="diamond"){
  const {cx,cy,hw,hh}=n;
  s+=`<polygon class="b" points="${cx},${cy-hh} ${cx+hw},${cy} ${cx},${cy+hh} ${cx-hw},${cy}"/>`;
  s+=`<text class="t" x="${cx}" y="${cy-4}">${esc(n.lines[0])}</text><text class="t" x="${cx}" y="${cy+13}">${esc(n.lines[1])}</text>`;
  s+=hot(cx-14,cy-36,28,14,n.id,cx,cy-25,null).replace('class="nid"','class="nid" style="text-anchor:middle"');
  const tx=Math.round(cx+hw*.62),ty=cy-hh+4;
  s+=hot(tx-10,ty,20,16,n.phase,tx,ty+12,"tg");
  if(a.att){s+=barSVG(a,cx-40,cy+20,80)}
 }else{
  const {x,y,w,h}=n,cx=x+w/2,ty=n.ty??(h===56?23:26);
  s+=`<rect class="b" x="${x}" y="${y}" width="${w}" height="${h}" rx="10"/>`;
  if(n.kind==="evid") s+=`<rect class="inr" x="${x+6}" y="${y+6}" width="${w-12}" height="${h-12}" rx="7"/>`;
  s+=`<text class="t" x="${cx}" y="${y+ty}">${esc(n.label)}</text>`;
  (n.sub||[]).forEach((l,i)=>{s+=`<text class="s" x="${cx}" y="${y+ty+19+i*18}">${esc(l)}</text>`});
  if(n.chips) n.chips.forEach((c,i)=>{const cxp=x+11+i*66;s+=`<g class="chip"><rect x="${cxp}" y="${y+56}" width="60" height="26" rx="5"/><text x="${cxp+30}" y="${y+73}">${esc(c)}</text></g>`});
  if(n.note) s+=`<text class="s" x="${cx}" y="${y+104}">${esc(n.note)}</text>`;
  if(n.receipt) s+=`<circle class="rcpt" cx="${x+16}" cy="${y+h-14}" r="6"/>`;
  const ix=n.kind==="evid"?x+14:x+10,iy=n.kind==="evid"?y+20:y+16;
  s+=hot(ix,iy-10,26,12,n.id,ix,iy,null);
  s+=hot(x+w-26,y+6,20,16,n.phase,x+w-16,y+18,"tg");
  if(a.att) s+=barSVG(a,x+28,y+h-6,w-56);
 }
 return s+`</g>`;
}
function barSVG(a,x,y,w){let s=`<rect class="nbar-bg" x="${x}" y="${y}" width="${w}" height="3" rx="1.5"/>`,cur=x;
 [["pass","seg-pass"],["fail","seg-fail"],["neu","seg-neu"],["pend","seg-pend"]].forEach(([k,c])=>{const ww=a[k]/a.att*w;if(ww>0){s+=`<rect class="${c}" x="${cur.toFixed(1)}" y="${y}" width="${ww.toFixed(1)}" height="3"/>`;cur+=ww}});return s}

/* ================= CARD + DETAIL ================= */
function telBlock(id,full){
 const n=byId[id],t=nt(id),a=agg(t?.runs),pc=t?.preconfig||{};
 let h=`<div class="secl">Preconfig</div><div class="pc">${pchip("stage",pc.stage)}${pchip("test",pc.test)}${pchip("debug",pc.debug)}</div>`;
 h+=`<div class="secl">Actions</div><ol class="acts">${n.actions.map(x=>`<li>${esc(x)}</li>`).join("")}</ol>`;
 if(a.att){
  h+=`<div class="ratebox"><span class="rate">${pct(a.rate)}</span><div>${rbar(a)}<div class="muted" style="font-size:12px;margin-top:3px">${a.pass} pass · ${a.fail} fail · ${a.neu} neutral · ${a.pend} pending of ${a.att} attempts</div></div></div>`;
  h+=`<table class="runs"><thead><tr><th>Run</th><th>Att</th><th>✓</th><th>✗</th><th>Pend</th><th>Pass</th></tr></thead><tbody>`+
   t.runs.map(r=>{const ra=agg([r]);return `<tr><td>${esc(r.name)}</td><td>${ra.att}</td><td>${ra.pass}</td><td>${ra.fail}</td><td>${ra.pend+ra.neu}</td><td>${pct(ra.rate)}</td></tr>`}).join("")+`</tbody></table>`;
 }else h+=`<div class="secl">Runs</div><div class="empty" style="padding:2px 0">No runs recorded for this source.</div>`;
 const errs=t?.errors||[];
 if(errs.length) h+=`<div class="errline"><b class="mono">${esc(errs[errs.length-1].code)}</b> ${esc(errs[errs.length-1].msg)}</div>`;
 if(full&&t?.logs?.length) h+=`<div class="secl">Logs</div><ul class="feed" style="max-height:160px">${t.logs.map(logLi).join("")}</ul>`;
 const rt=Object.assign({},tel().runtime||{},t?.runtime||{});const v=tel().vcs||{};
 h+=`<div class="secl">Runtime · VCS</div><div class="mono" style="font-size:11.5px;overflow-wrap:anywhere">py ${esc(rt.python??"not reported")} · ${esc((v.head||"").slice(0,8)||"—")} on ${esc(v.branch||"—")}</div>`;
 return h;
}
function logLi(l,node){return `<li><span class="ts">${esc(l.ts||"")}</span><span class="lvl ${esc(l.level)}">${esc(l.level)}</span><span class="mono" style="font-size:11px">${esc(node||"")}</span><span>${esc(l.msg)}</span></li>`}
const hc=$("#hc");
function showCard(id,x,y){const n=byId[id];
 hc.innerHTML=`<div class="hh"><span class="mono">${id}</span><b>${esc(n.label)}</b><span class="mono muted" style="font-size:11px">${PH[n.phase]} · ${KIND[n.kind]}</span></div>${telBlock(id,false)}`;
 hc.hidden=false;placeCard(x,y)}
function placeCard(x,y){const r=hc.getBoundingClientRect();const vw=innerWidth,vh=innerHeight;
 if(x+r.width>vw-8)x=Math.max(8,x-r.width-28);if(y+r.height>vh-8)y=Math.max(8,vh-r.height-8);hc.style.left=x+"px";hc.style.top=y+"px"}
function hideCard(){hc.hidden=true}

function select(type,id){S.sel={type,id};renderDetail();applySel()}
function applySel(){const svg=$("#g");if(!svg)return;
 svg.querySelectorAll(".node").forEach(g=>g.classList.toggle("sel",S.sel.type==="node"&&g.dataset.id===S.sel.id));
 svg.querySelectorAll(".edge").forEach(p=>p.classList.toggle("esel",S.sel.type==="edge"&&p.dataset.eid===S.sel.id))}
function renderDetail(){
 const d=$("#detail");
 if(S.sel.type==="edge"){const e=eById[S.sel.id];
  d.innerHTML=`<div class="eyebrow">Selected edge</div><h2 style="margin-top:4px">${e.id} · ${e.f} → ${e.t}</h2>
  <dl class="kv"><dt>Type</dt><dd>${EKIND[e.k]}</dd><dt>From</dt><dd>${refBtn(e.f)} ${esc(byId[e.f].label)}</dd><dt>To</dt><dd>${refBtn(e.t)} ${esc(byId[e.t].label)}</dd><dt>Label</dt><dd>${esc(e.lab?e.lab.join(" "):"—")}</dd><dt>Meaning</dt><dd>${esc(e.m)}</dd></dl>`;
 }else{const n=byId[S.sel.id];
  const io=list=>list.length?list.map(e=>`${refBtn(e.f===n.id?e.t:e.f)} <span class="mono muted" style="font-size:11px">${e.id}</span>`).join(" "):"—";
  d.innerHTML=`<div class="eyebrow">Selected node · ${n.id}</div><h2 style="margin-top:4px">${esc(n.label)}</h2>
  <div class="pc" style="margin-top:6px"><span class="st-pill ${n.status}">${STATUS[n.status]}</span><span class="pchip">${KIND[n.kind]}</span><span class="pchip">${PH[n.phase]}</span></div>
  <dl class="kv"><dt>Does</dt><dd>${esc(n.does)}</dd><dt>Owner lane</dt><dd>${esc(n.owner)}</dd><dt>Artefact</dt><dd class="mono">${esc(n.artefact)}</dd><dt>Inputs</dt><dd>${io(ins(n.id))}</dd><dt>Outputs</dt><dd>${io(outs(n.id))}</dd><dt>Evidence</dt><dd>${esc(n.evidence)}</dd><dt>State now</dt><dd>${esc(n.state)}</dd></dl>
  ${telBlock(n.id,true)}
  <div style="margin-top:12px"><button class="btn small" id="trN">Trace neighbours</button></div>`;
  $("#trN").addEventListener("click",()=>trace([n.id,...ins(n.id).map(e=>e.f),...outs(n.id).map(e=>e.t)]));
 }
}
function trace(ids){S.trace=ids;applyTrace();if(ids){const first=ids[0];if(byId[first])select("node",first)}}
function applyTrace(){const svg=$("#g");if(!svg)return;const ids=S.trace;
 $("#clear").hidden=!ids;
 if(!ids){svg.classList.remove("dimmed");svg.querySelectorAll(".hl").forEach(e=>e.classList.remove("hl"));document.querySelectorAll("#steps button").forEach(b=>b.setAttribute("aria-pressed","false"));return}
 svg.classList.add("dimmed");
 svg.querySelectorAll(".node").forEach(n=>n.classList.toggle("hl",ids.includes(n.dataset.id)));
 svg.querySelectorAll(".edge,.elab").forEach(e=>e.classList.toggle("hl",ids.includes(e.dataset.f)&&ids.includes(e.dataset.t)));
}

/* ================= LEGEND ================= */
function renderLegend(){
 let h=`<div class="sub">${S.mode==="role"?"Node roles":S.mode==="status"?"Implementation status":"Pass rate of decisive runs"}</div>`;
 const row=(cls,t)=>`<div class="lg"><span class="sw ${cls}"></span><span>${t}</span></div>`;
 if(S.mode==="role") h+=row("auth","Authority · resolves or owns state")+row("proc","Process · checks and verification")+`<div class="lg"><span class="sw dec"></span><span>Gate · binary decision</span></div>`+row("rep","Repair · isolated change")+row("pass","Admitted path · merge and proof")+row("hold","Hold · blocked, logged, retried")+row("evid","Evidence store · REX and KEB");
 else if(S.mode==="status") h+=Object.entries(STATUS).map(([k,v])=>row(k,v)).join("");
 else h+=row("ok","90% or more")+row("hold","50–89%")+row("block","Below 50%")+row("none","No decisive runs");
 h+=`<div class="sub">Edge types</div>`+Object.entries(EKIND).map(([k,v])=>`<div class="lg"><svg><line x1="0" y1="7" x2="44" y2="7" class="e-${k}"/></svg><span>${v}</span></div>`).join("");
 h+=`<div class="sub">Markers</div>
 <div class="lg"><span class="phases"><span>C</span></span><span>DMAIC phase · hover for card</span></div>
 <div class="lg"><span class="mono" style="font-size:11px">N09</span><span>Node ID · hover for card</span></div>
 <div class="lg"><svg><rect x="0" y="5" width="20" height="3" class="seg-pass"/><rect x="20" y="5" width="8" height="3" class="seg-fail"/><rect x="28" y="5" width="16" height="3" class="seg-pend"/></svg><span>Run bar: pass · fail · pending</span></div>
 <div class="lg"><svg><circle cx="22" cy="7" r="6" class="rcpt"/></svg><span>Emits an exact-commit receipt</span></div>
 <div class="lg"><svg><rect x="2" y="0" width="40" height="14" rx="4" class="ring" style="animation:none"/></svg><span>Where a tracked PR is now</span></div>
 <div class="phases" style="margin-top:2px">${Object.entries(PH).map(([k,v])=>`<span>${k} ${v}</span>`).join("")}</div>`;
 $("#legend").innerHTML=h;
}

/* ================= CENSUS ================= */
function renderCensus(){
 const T=tel();const all=agg(NODES.flatMap(n=>nt(n.id)?.runs||[]));
 const errs=NODES.flatMap(n=>(nt(n.id)?.errors||[]).map(e=>({...e,node:n.id})));
 const k=(cls,l,v,s)=>`<div class="kpi ${cls}"><span class="eyebrow">${l}</span><b>${v}</b><span class="muted" style="font-size:12px">${s}</span></div>`;
 $("#kpis").innerHTML=k("proc","Attempts",all.att,`iteration ${esc(T.iteration)}`)+k("pass","Passed",all.pass,"decisive green")+k("rep","Failed",all.fail,"decisive red")+k("hold","Pending",all.pend+all.neu,`${all.neu} neutral`)+k("pass","Pass rate",pct(all.rate),"of decisive runs")+k("evid","Errors",errs.length,`${(T.rex||[]).length} REX lessons`);
 const v=T.vcs||{},r=T.runtime||{};const dd=(a,b)=>`<dt>${a}</dt><dd>${esc(b??"not reported")}</dd>`;
 $("#vcs").innerHTML=dd("repo",v.repo)+dd("branch",v.branch)+dd("head",v.head)+dd("base",v.base)+dd("dirty tree",v.dirty==null?null:String(v.dirty))+dd("generated",T.generated_at);
 const overrides=NODES.filter(n=>nt(n.id)?.runtime?.python).map(n=>`${n.id}: py ${nt(n.id).runtime.python}`).join(" · ");
 $("#rt").innerHTML=dd("python",r.python)+dd("implementation",r.implementation)+dd("platform",r.platform)+dd("container",r.container)+dd("debug default",r.debug)+dd("per-node",overrides||null);
 // node census
 $("#censusT").innerHTML=`<thead><tr><th>ID</th><th>Node</th><th>Stage</th><th>Test</th><th>Debug</th><th class="num">Att</th><th class="num">✓</th><th class="num">✗</th><th class="num">Pend</th><th class="num">Pass</th><th style="min-width:90px">Runs</th><th>Last error</th></tr></thead><tbody>`+
 NODES.map(n=>{const t=nt(n.id),a=agg(t?.runs),pc=t?.preconfig||{},le=(t?.errors||[]).slice(-1)[0];
  const ch=v=>`<span class="pchip ${esc(v??"none")}">${esc(v??"—")}</span>`;
  return `<tr data-ref="${n.id}"><td class="idb">${n.id}</td><td>${esc(n.label)}</td><td>${ch(pc.stage)}</td><td>${ch(pc.test)}</td><td>${ch(pc.debug)}</td><td class="num">${a.att||"—"}</td><td class="num">${a.att?a.pass:"—"}</td><td class="num">${a.att?a.fail:"—"}</td><td class="num">${a.att?a.pend+a.neu:"—"}</td><td class="num">${pct(a.rate)}</td><td>${rbar(a)}</td><td style="font-size:12.5px">${le?`<span class="mono">${esc(le.code)}</span> ${esc(le.msg)}`:"—"}</td></tr>`}).join("")+`</tbody>`;
 // logs
 const lv=$("#lvlF").value;
 const logs=NODES.flatMap(n=>(nt(n.id)?.logs||[]).map(l=>({...l,node:n.id}))).filter(l=>!lv||l.level===lv).sort((a,b)=>String(b.ts).localeCompare(String(a.ts)));
 $("#logs").innerHTML=logs.length?logs.map(l=>logLi(l,l.node)).join(""):`<li class="empty" style="display:block">No log entries for this filter.</li>`;
 $("#errT").innerHTML=errs.length?`<thead><tr><th>Time</th><th>Node</th><th>Code</th><th>Message</th><th>REX</th></tr></thead><tbody>${errs.map(e=>`<tr data-ref="${e.node}"><td class="mono">${esc(e.ts)}</td><td class="idb">${e.node}</td><td class="mono">${esc(e.code)}</td><td>${esc(e.msg)}</td><td class="mono">${esc(e.rex||"—")}</td></tr>`).join("")}</tbody>`:`<tbody><tr><td class="empty">No errors recorded for this source.</td></tr></tbody>`;
 const rex=T.rex||[];
 $("#rexT").innerHTML=rex.length?`<thead><tr><th>ID</th><th>Node</th><th>Lesson</th><th class="num">Seen</th></tr></thead><tbody>${rex.map(x=>`<tr data-ref="${esc(x.node)}"><td class="mono">${esc(x.id)}</td><td class="idb">${esc(x.node)}</td><td>${esc(x.title)}</td><td class="num">${esc(x.recurrence)}</td></tr>`).join("")}</tbody>`:`<tbody><tr><td class="empty">No REX lessons captured yet. Capture starts once controls execute.</td></tr></tbody>`;
}

/* ================= REFERENCE ================= */
function renderReference(){
 renderLifecycle();
 $("#stages").innerHTML=STAGES.map(st=>`<li class="stage"><div><div class="no">${st.n}</div><div class="phl">${PH[st.ph]}</div></div><div class="stage-b"><div class="stage-h"><h3 style="font-size:16px">${esc(st.name)}</h3><div class="refs">${st.nodes.map(id=>`<button class="ref" data-ref="${id}">${id} · ${esc(byId[id].label)}</button>`).join("")}</div></div>
 <div class="eae"><div><b>Entry</b><ul>${st.entry.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></div><div><b>Actions</b><ul>${st.acts.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></div><div><b>Exit</b><ul>${st.exit.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></div></div></div></li>`).join("");
 renderNodeTable();
 const sw=k=>{const m={flow:"var(--e-flow)",yes:"var(--pass-s)",fail:"var(--rep-s)",hold:"var(--hold-s)",evid:"var(--evid-s)",rec:"var(--accent)"};return `<span class="kind-dot" style="border-color:${m[k]};background:${m[k]}"></span>`};
 $("#edgeT").innerHTML=`<thead><tr><th>ID</th><th>From</th><th>To</th><th>Type</th><th>Label</th><th>Meaning</th></tr></thead><tbody>`+
  EDGES.map(e=>`<tr data-edge="${e.id}"><td class="idb">${e.id}</td><td>${refBtn(e.f)} ${esc(byId[e.f].label)}</td><td>${refBtn(e.t)} ${esc(byId[e.t].label)}</td><td style="white-space:nowrap">${sw(e.k)}${EKIND[e.k]}</td><td class="mono" style="font-size:12px">${esc(e.lab?e.lab.join(" "):"—")}</td><td>${esc(e.m)}</td></tr>`).join("")+`</tbody>`;
 $("#mer").textContent=toMermaid();
 $("#mjson").textContent=modelJSON();
}
function renderNodeTable(){
 const q=$("#nq").value.trim().toLowerCase(),ph=$("#nph").value,ln=$("#nlane").value;
 const rows=NODES.filter(n=>(!ph||n.phase===ph)&&(!ln||n.lane===ln)&&(!q||[n.id,n.label,n.owner,n.artefact,n.does].join(" ").toLowerCase().includes(q)));
 $("#ncount").textContent=`${rows.length} of ${NODES.length} nodes`;
 const sw=k=>`<span class="kind-dot" style="background:var(--${k==="dec"?"dec":k});border-color:var(--${k==="dec"?"accent":k+"-s"})"></span>`;
 $("#nodeT").innerHTML=`<thead><tr><th>ID</th><th>Node</th><th>Type</th><th>Phase</th><th>Lane</th><th>In</th><th>Out</th><th>Artefact</th><th>Evidence</th><th>Status</th><th class="num">Pass</th></tr></thead><tbody>`+
  (rows.length?rows.map(n=>`<tr data-ref="${n.id}"><td class="idb">${n.id}</td><td class="ncell"><b style="font-weight:600">${esc(n.label)}</b><div class="muted" style="font-size:12px;max-width:34ch">${esc(n.does)}</div></td><td style="white-space:nowrap">${sw(n.kind)}${KIND[n.kind]}</td><td>${PH[n.phase]}</td><td style="white-space:nowrap">${LANE[n.lane]}</td>
  <td><div class="refs">${ins(n.id).map(e=>refBtn(e.f)).join("")||"—"}</div></td><td><div class="refs">${outs(n.id).map(e=>refBtn(e.t)).join("")||"—"}</div></td><td class="mono" style="font-size:12px;max-width:26ch">${esc(n.artefact)}</td><td style="font-size:12.5px">${esc(n.evidence)}</td><td><span class="st-pill ${n.status}">${STATUS[n.status]}</span></td><td class="num">${pct(agg(nt(n.id)?.runs).rate)}</td></tr>`).join(""):`<tr><td colspan="11" class="empty">No nodes match. Clear the filters to see all ${NODES.length}.</td></tr>`)+`</tbody>`;
}
function toMermaid(){
 const q=s=>String(s).replace(/"/g,"'");
 const shape=n=>{const t=q(`${n.id} · ${n.label}`);return n.kind==="dec"?`{"${t}"}`:n.kind==="evid"?`[("${t}")]`:n.id==="N15"?`(["${t}"])`:`["${t}"]`};
 const L=["flowchart TD"];
 Object.entries(LANE).forEach(([k,v])=>{L.push(`  subgraph L_${k}["${v}"]`);NODES.filter(n=>n.lane===k).forEach(n=>L.push(`    ${n.id}${shape(n)}:::${n.kind}`));L.push("  end")});
 const arrow={evid:"-.->",hold:"-.->",rec:"==>"};
 EDGES.forEach(e=>L.push(`  ${e.f} ${arrow[e.k]||"-->"}${e.lab?`|"${q(e.lab.join(" "))}"|`:""} ${e.t}`));
 const cd={auth:"fill:#56287a,color:#fff,stroke:#3f1c5c",proc:"fill:#eee7f7,color:#452366,stroke:#9879b8",dec:"fill:#fff,color:#1c1626,stroke:#5a2a86,stroke-dasharray:5 3",rep:"fill:#fce6eb,color:#8f2747,stroke:#cf5f7d",pass:"fill:#dff4e9,color:#145c43,stroke:#3f9b6c",hold:"fill:#fff1d9,color:#7c5118,stroke:#c98f2e",evid:"fill:#def1f2,color:#135458,stroke:#2f8f95"};
 Object.entries(cd).forEach(([k,v])=>L.push(`  classDef ${k} ${v}`));
 const ls={yes:"stroke:#3f9b6c,stroke-width:2px",fail:"stroke:#cf5f7d,stroke-width:2px",hold:"stroke:#c98f2e,stroke-width:2px,stroke-dasharray:6 4",evid:"stroke:#2f8f95,stroke-dasharray:2 4",rec:"stroke:#5a2a86,stroke-width:3px"};
 Object.entries(ls).forEach(([k,v])=>{const idx=EDGES.map((e,i)=>e.k===k?i:-1).filter(i=>i>=0);if(idx.length)L.push(`  linkStyle ${idx.join(",")} ${v}`)});
 return L.join("\n");
}
function modelJSON(){return JSON.stringify({model:"code-purple.pulse/v1",nodes:NODES.map(({x,y,w,h,cx,cy,hw,hh,ty,lines,chips,note,receipt,...r})=>r),edges:EDGES.map(({d,lx,ly,rot,...r})=>({...r,lab:r.lab?r.lab.join(" "):null})),stages:STAGES},null,2)}
function schemaText(){return JSON.stringify({schema:"code-purple.census/v1",iteration:1,generated_at:"2026-10-16T09:00:00+02:00",
 vcs:{repo:"GBOGEB/CODEX",branch:"<branch>",head:"<40-char sha>",base:"main@<sha>",dirty:false},
 runtime:{python:"3.11.9",implementation:"CPython",platform:"linux-x86_64",container:"<image or devcontainer>",debug:"off | on | trace"},
 rex:[{id:"REX-…",node:"N04",title:"<reusable lesson>",recurrence:1}],
 nodes:{N04:{preconfig:{stage:"pass | fail | pending | none",test:"pass | fail | pending | none",debug:"off | on | trace"},runtime:{python:"3.12.4"},
  runs:[{name:"ruff",attempts:3,pass:2,fail:1,neutral:0,pending:0,ms:1800}],
  errors:[{ts:"<iso>",code:"RUF100",msg:"<message>",rex:"REX-…"}],
  logs:[{ts:"<iso>",level:"ERROR | WARN | INFO | DEBUG",msg:"<message>"}]}}},null,2)}

/* ================= WIRING ================= */
const tabs=[...document.querySelectorAll("[role=tab]")];
function openTab(id){tabs.forEach(t=>{const on=t.getAttribute("aria-controls")===id;t.setAttribute("aria-selected",on);document.getElementById(t.getAttribute("aria-controls")).hidden=!on});hideCard();try{localStorage.setItem("cp-tab",id)}catch(e){}}
tabs.forEach(t=>t.addEventListener("click",()=>openTab(t.getAttribute("aria-controls"))));
function goNode(id){openTab("pulse");trace([id,...ins(id).map(e=>e.f),...outs(id).map(e=>e.t)]);$("#pulse").scrollIntoView({behavior:"smooth",block:"start"})}
document.addEventListener("click",ev=>{
 const r=ev.target.closest("[data-ref]");if(r&&byId[r.dataset.ref]){ev.stopPropagation();if(r.closest("#detail")){select("node",r.dataset.ref);return}goNode(r.dataset.ref);return}
 const e=ev.target.closest("tr[data-edge]");if(e){openTab("pulse");const ed=eById[e.dataset.edge];S.trace=[ed.f,ed.t];applyTrace();select("edge",ed.id);$("#pulse").scrollIntoView({behavior:"smooth",block:"start"})}
});
document.querySelectorAll("#steps button").forEach(b=>b.addEventListener("click",()=>{const was=b.getAttribute("aria-pressed")==="true";S.trace=null;applyTrace();if(!was){openTab("pulse");trace(b.dataset.hl.split(","));b.setAttribute("aria-pressed","true")}}));
document.querySelectorAll(".jump").forEach(b=>b.addEventListener("click",()=>{openTab("pulse");trace(b.dataset.hl.split(","));$("#pulse").scrollIntoView({behavior:"smooth",block:"start"})}));
$("#clear").addEventListener("click",()=>{S.trace=null;applyTrace()});
$("#live").addEventListener("change",ev=>{S.live=ev.target.checked;renderGraph()});
document.querySelectorAll("#modeSeg button").forEach(b=>b.addEventListener("click",()=>{S.mode=b.dataset.mode;document.querySelectorAll("#modeSeg button").forEach(x=>x.setAttribute("aria-pressed",x===b));renderGraph();renderLegend()}));
function setSrc(src){S.src=src;document.querySelectorAll("#srcSeg button").forEach(x=>x.setAttribute("aria-pressed",x.dataset.src===src));
 const ex=src==="example";$("#exBanner1").classList.toggle("on",ex);$("#exBanner2").classList.toggle("on",ex);
 $("#srcNote").textContent=src==="recorded"?"GitHub API readback at 17:16 CEST. A snapshot: the page does not refresh itself.":src==="example"?"Illustrative numbers to show the layout. Not real runs.":`Loaded: iteration ${TEL_LOADED?.iteration??"?"}, ${Object.keys(TEL_LOADED?.nodes||{}).length} nodes.`;
 renderAll()}
document.querySelectorAll("#srcSeg button").forEach(b=>b.addEventListener("click",()=>{if(!b.disabled)setSrc(b.dataset.src)}));
$("#fileIn").addEventListener("change",ev=>{const f=ev.target.files[0];if(!f)return;const rd=new FileReader();
 rd.onload=()=>{try{const j=JSON.parse(rd.result);if(!j||typeof j!=="object"||!j.nodes)throw new Error("missing a nodes object");
   const unknown=Object.keys(j.nodes).filter(k=>!byId[k]);TEL_LOADED=j;const b=$('#srcSeg [data-src="loaded"]');b.hidden=false;b.disabled=false;setSrc("loaded");
   if(unknown.length)$("#srcNote").textContent+=` Ignored unknown node IDs: ${unknown.join(", ")}.`;
  }catch(err){$("#srcNote").textContent=`Could not load ${f.name}: ${err.message}. Expected the code-purple.census/v1 shape (see Census tab).`}
  ev.target.value=""};rd.readAsText(f)});
$("#lvlF").addEventListener("change",renderCensus);
["#nq","#nph","#nlane"].forEach(s=>$(s).addEventListener("input",renderNodeTable));
function copy(btn,text){const done=()=>{const o=btn.textContent;btn.textContent="Copied";setTimeout(()=>btn.textContent=o,1400)};
 try{navigator.clipboard.writeText(text).then(done,()=>fallback())}catch(e){fallback()}
 function fallback(){const pre=btn.closest(".card").querySelector("pre");const r=document.createRange();r.selectNodeContents(pre);const sel=getSelection();sel.removeAllRanges();sel.addRange(r);btn.textContent="Selected · press Ctrl+C";setTimeout(()=>btn.textContent="Copy",2000)}}
$("#cpMer").addEventListener("click",ev=>copy(ev.currentTarget,toMermaid()));
$("#cpJson").addEventListener("click",ev=>copy(ev.currentTarget,modelJSON()));
$("#cpSchema").addEventListener("click",ev=>copy(ev.currentTarget,schemaText()));
$("#schema").textContent=schemaText();
addEventListener("scroll",hideCard,{passive:true});


(async()=>{try{if(!window.claude||!claude.use)return;const dl=await claude.use("downloads");if(!dl)return;const pl=document.getElementById("pdfLinks");if(pl)pl.hidden=true;
 const d=$("#deckBtn");d.hidden=false;d.addEventListener("click",async()=>{const o=d.textContent;d.textContent="Preparing…";
  try{const r=await fetch("Code-Purple-deck.pdf");if(!r.ok)throw new Error("missing");await dl.save({filename:"Code-Purple-deck.pdf",data:await r.blob()});d.textContent="Saved";}
  catch(e){d.textContent=e&&e.code==="declined"?o:"Deck unavailable";}setTimeout(()=>d.textContent=o,2000)});
 const b=$("#pdfBtn");b.hidden=false;
 b.addEventListener("click",async()=>{const o=b.textContent;b.textContent="Preparing…";
  try{const r=await fetch("code-purple.pdf");if(!r.ok)throw new Error("PDF not found");const blob=await r.blob();await dl.save({filename:"Code-Purple-2026-10-12.pdf",data:blob});b.textContent="Saved";}
  catch(e){b.textContent=e&&e.code==="declined"?o:"PDF unavailable";}
  setTimeout(()=>b.textContent=o,2000)})}catch(e){}})();
addEventListener("beforeprint",()=>document.querySelectorAll("details").forEach(d=>d.open=true));

/* ===== live census (kit/census.json, republished by each readback) ===== */
const fmtT=iso=>{try{return new Date(iso).toLocaleString("en-GB",{timeZone:"Europe/Brussels",day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"})+" CEST"}catch(e){return iso}};
const pillHTML=(txt,kind,href)=>{const st=kind==="ok"?'background:var(--pass);border-color:var(--pass-s);color:var(--pass-ink)':kind==="hold"?'background:var(--hold);border-color:var(--hold-s);color:var(--hold-ink)':kind==="lift"?'background:var(--pass-s);border-color:var(--pass-s);color:#fff':kind==="rep"?'background:var(--rep);border-color:var(--rep-s);color:var(--rep-ink)':'';
 return href?`<a class="pill" style="${st}" href="${href}">${esc(txt)}</a>`:`<span class="pill" style="${st}">${esc(txt)}</span>`};
async function loadCensus(manual){
 const note=$("#liveNote");
 try{
  const r=await fetch("kit/census.json?ts="+Date.now(),{cache:"no-store"});if(!r.ok)throw new Error("census not found ("+r.status+")");
  const c=await r.json();
  let h=pillHTML(c.lifted?"LIFTED":"NOT LIFTED",c.lifted?"lift":"rep");
  h+=pillHTML("read back "+fmtT(c.generated_at),"");
  (c.prs||[]).filter(p=>["unblocker","debt-ratchet"].includes(p.role)).forEach(p=>{h+=pillHTML(`${p.repo.split("/")[1]} #${p.number} · ${p.merged?"merged":p.state}`,p.merged?"ok":"hold",`https://github.com/${p.repo}/pull/${p.number}`)});
  Object.entries(c.repos||{}).forEach(([n,v])=>{const red=(v.nightly&&v.nightly.reds||[]).length;h+=pillHTML(`${n.split("/")[1]}: ${v.open_prs} open PRs${red?` · ${red} inherited reds nightly`:""}`,red?"hold":"")});
  if(c.merges_since_unblock!=null)h+=pillHTML(`${c.merges_since_unblock} merges since unblock`,"ok");
  $("#liveRow").innerHTML=h;
  if($("#liftBody")&&c.lift)$("#liftBody").innerHTML=c.lift.map(x=>`<tr><td class="idb">${esc(x.id)}</td><td>${esc(x.text)}</td><td><span class="st-pill ${x.ok?"ok":"block"}">${x.ok?"yes":"no"}</span></td><td>${esc(x.evidence)}</td></tr>`).join("");
  note.textContent=(manual?"Refreshed. ":"")+"Census "+fmtT(c.generated_at)+". New data appears when a readback is published.";
 }catch(e){note.textContent="Showing the built-in snapshot; "+e.message+"."}
}
$("#refreshBtn").addEventListener("click",()=>loadCensus(true));
loadCensus(false);
/* re-read the published census every 5 minutes while visible, and when the tab comes back */
setInterval(()=>{if(!document.hidden)loadCensus(false)},300000);
document.addEventListener("visibilitychange",()=>{if(!document.hidden)loadCensus(false)});
function renderAll(){renderGraph();renderLegend();renderDetail();renderCensus();renderReference()}
renderAll();
const hash=(location.hash||"").slice(1);let start="pulse";
if(tabs.some(t=>t.getAttribute("aria-controls")===hash))start=hash;else{try{const s=localStorage.getItem("cp-tab");if(s&&document.getElementById(s))start=s}catch(e){}}
openTab(start);
})();
