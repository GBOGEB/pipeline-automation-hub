/** CP W18 briefing deck: single frozen snapshot.json input, presentation only. */
'use strict';
const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
const pptxgen=require('pptxgenjs');
const HELPER_PATH=process.env.PPTXGENJS_HELPERS || '/home/oai/skills/slides/pptxgenjs_helpers';
const {autoFontSize,warnIfSlideHasOverlaps,warnIfSlideElementsOutOfBounds}=require(HELPER_PATH);
const BASE=__dirname;
const raw=fs.readFileSync(path.join(BASE,'snapshot.json'));
const data=JSON.parse(raw.toString('utf8'));
const sha=crypto.createHash('sha256').update(raw).digest('hex');
if(data.schema!=='code-purple.communication-master.v1'||data.controls.merge_admission!=='HOLD')throw Error('unqualified master');
if(data.census.repos.reduce((s,r)=>s+r.open,0)!==data.census.latest_observed_open)throw Error('census denominator');
const out=process.argv[2]||path.join(BASE,'CP_W18_FLEET_DOV_20261017.pptx');
const P=new pptxgen();P.layout='LAYOUT_WIDE';P.author='CODE PURPLE / Mission Control';P.subject='Source-bound frozen communication projection, not formal admission';P.title=data.title;
P.company='Mission Control';P.lang='en-US';P.theme={headFontFace:'Aptos Display',bodyFontFace:'Aptos',lang:'en-US'};
const C={bg:'0B1525',panel:'14253D',pane2:'1B2E49',line:'354C66',white:'EFF6FE',muted:'B7C9DD',mint:'69DFC4',blue:'93B5FC',gold:'F5CA83',red:'FB9898'};
const SW=13.333,SH=7.5;
const ST=P.ShapeType;
function t(slide,txt,x,y,w,h,opt={}){slide.addText(String(txt),{x,y,w,h,margin:0.03,fontFace:'Aptos',fontSize:16,color:C.white,breakLine:false,valign:'mid',...opt});}
function fit(slide,txt,x,y,w,h,size=20,opt={}){slide.addText(String(txt),{...autoFontSize(txt,'Aptos',{x,y,w,h,fontSize:size,minFontSize:10,maxFontSize:size,mode:'shrink'}),fontFace:'Aptos',color:C.white,margin:0.02,valign:'mid',...opt});}
function box(slide,x,y,w,h,fill=C.panel){slide.addShape(ST.roundRect,{x,y,w,h,rectRadius:0.12,line:{color:C.line,width:0.7},fill:{color:fill},radius:0.11});}
function rect(slide,x,y,w,h,fill){slide.addShape(ST.rect,{x,y,w,h,line:{color:fill,transparency:100},fill:{color:fill}});}
function rule(slide,y){rect(slide,0.57,y,12.18,0.012,C.line);}
function notes(slide,...links){const rows=['[Sources]','Master: snapshot.json (sha256 '+sha+')',...links.map(u=>'Reference: '+u),'[/Sources]','All source claims are scoped and non-compensating.'];try{slide.addNotes(rows.join('\n'))}catch(e){console.warn('note unavailable',String(e))}}
function base(section,title,no,subtitle=''){
 const s=P.addSlide();s.background={color:C.bg};
 t(s,'MISSION CONTROL  /  CODE PURPLE  /  W18',0.62,0.28,7.8,0.3,{fontSize:9.8,color:C.mint,bold:true,charSpacing:1.1});
 box(s,10.75,0.23,1.97,0.35,'4D363D');t(s,'ADMISSION  HOLD',10.9,0.255,1.66,0.27,{fontSize:10.5,bold:true,color:'FFE0DD',align:'center'});
 fit(s,title,0.60,0.75,12.0,0.8,30,{bold:true});
 if(subtitle)t(s,subtitle,0.62,1.55,12,0.38,{fontSize:12,color:C.muted});
 rule(s,6.94);t(s,'SLUG '+data.slug+'   |   MASTER '+sha.slice(0,16)+'...',0.63,7.04,9.6,0.25,{fontSize:8,color:C.muted});
 t(s,String(no).padStart(2,'0')+' / 08',11.68,7.04,1.08,0.25,{fontSize:9,color:C.muted,align:'right'});
 return s;
}
function card(slide,x,y,w,h,value,label,detail,accent=C.white){box(slide,x,y,w,h);fit(slide,value,x+0.18,y+0.16,w-0.34,0.68,38,{bold:true,color:accent});fit(slide,label,x+0.18,y+1.05,w-0.34,0.4,16,{bold:true});fit(slide,detail,x+0.18,y+1.51,w-0.34,h-1.65,11,{color:C.muted});}
function para(slide,text,x,y,w,h,size=15,color=C.white){fit(slide,text,x,y,w,h,size,{color,valign:'top'});}
function statusPill(slide,text,x,y,w,color=C.gold){box(slide,x,y,w,0.37,C.pane2);fit(slide,text,x+0.08,y+0.04,w-0.16,0.28,10,{bold:true,color});}
function bulletRows(slide,lines,x,y,w,rowH=0.49,size=13){lines.forEach((line,i)=>{rect(slide,x,y+i*rowH+0.17,0.065,0.065,C.mint);fit(slide,line,x+0.22,y+i*rowH,w-0.21,rowH,size,{valign:'mid'})});}
// 1: executive.
{
 const s=base('overview','Global BD wave: issue reduction vs actual engineering proof',1,'Frozen non-atomic GitHub issue readbacks, 17 October 2026');
 card(s,0.62,2.10,3.82,2.55,String(data.census.latest_observed_open),'Open issues','Nine repositories; source query complete');
 card(s,4.75,2.10,3.82,2.55,String(data.census.net_change),'Net open-issue change','153 to 142 across concurrent owner lanes',C.mint);
 card(s,8.89,2.10,3.82,2.55,'0','Root closures credited','This controller wave did not grant causal credit',C.gold);
 box(s,0.62,4.93,12.09,1.30,C.pane2);para(s,'Closure classes: 9 historical dashboard notifications marked duplicate, plus 2 completed DAB investigation/tooling tasks. Every unresolved source, security and owner gate remains traceable.',0.88,5.16,11.56,0.86,17);
 notes(s,data.authorities.global_issue_controller,data.authorities.bd_ssot);
}
// 2: portfolio.
{
 const s=base('portfolio','Nine repositories: explicit current issue denominators',2,'All bars start at zero; category count is not a causal root count');
 const max=56;data.census.repos.forEach((r,i)=>{const y=1.95+i*.47;fit(s,r.name,0.65,y,3.0,.29,13,{color:C.muted});
  if(r.open<max)rect(s,3.82,y+0.06,7.92,.16,'263C58');rect(s,3.82,y+0.06,7.92*r.open/max,.16,i===0?C.mint:C.blue);
  t(s,String(r.open),11.95,y-.01,.60,.28,{fontSize:14,bold:true,align:'right'});
 });
 notes(s,data.authorities.global_issue_controller);
}
// 3: W16.
{
 const s=base('engineering','W16 measured branches: one valid source epoch',3,'B0 canonical proof is not B9 changed-line 80% proof');
 const four=data.coverage.four_module,five=data.coverage.five_file_py312;
 card(s,.64,2.1,3.78,2.53,four.covered+'/'+four.eligible,'Four-module branch coverage',(100*four.covered/four.eligible).toFixed(2)+'% of current W16 obligations',C.mint);
 card(s,4.74,2.1,3.78,2.53,five.covered+'/'+five.eligible,'Five-file Python 3.12','Separate 560-eligible control scope',C.blue);
 card(s,8.84,2.1,3.78,2.53,'+33','Phase 8 reached arcs','30 to 63 / 118 on identical production blob',C.gold);
 box(s,.64,4.9,11.98,1.35,C.pane2);
 para(s,'Native 157 tests PASS (run 39050945097). Historical N14 = 200/446 is a different Phase 4 source epoch, so there is NO comparable N14-to-W16 slope. B9 current eligible-line fraction remains UNKNOWN.',.86,5.1,11.53,.98,16);
 notes(s,'https://github.com/GBOGEB/ABACUS/actions/runs/39050945097','https://github.com/GBOGEB/ABACUS/issues/1866');
}
// 4: blockers.
{
 const s=base('engineering','First-red DAG: independent gates, one shared propagated symptom',4,'Keep root ownership disjoint and exact-head identifiers in every receipt');
 const blocks=[
  ['A10 / HUMAN',data.ci.a10_first_red,'https://github.com/GBOGEB/ABACUS/issues/1996',C.red],
  ['PYTHON MARKERS','Four normalisation assertions per compatibility job','https://github.com/GBOGEB/ABACUS/actions/runs/39056628120',C.gold],
  ['ARIANA','defusedxml missing during test collection','https://github.com/GBOGEB/ABACUS/actions/runs/39056967085',C.gold],
  ['B9 DIFF','Historical changed-line score failed 80% floor','https://github.com/GBOGEB/ABACUS/issues/1866',C.blue]
 ];
 blocks.forEach(([name,desc,url,color],i)=>{const x=.62+i*3.09;box(s,x,2.05,2.82,3.67);t(s,name,x+.16,2.28,2.46,.48,{fontSize:14.5,bold:true,color});fit(s,desc,x+.16,2.97,2.49,1.64,17,{valign:'top'});t(s,'RECEIPT-BOUND',x+.15,5.22,2.48,.29,{fontSize:10,color:C.muted})});
 notes(s,...blocks.map(x=>x[2]));
}
// 5: DOD.
{
 const s=base('session','Current-session DOD: verified delivery vs unfinished work',5,'Delivery is not native acceptance, security review or guarded main promotion');
 const rows=data.session_dod;
 card(s,.63,1.95,3.76,2.10,rows.filter(x=>x.state==='VERIFIED').length+'/'+rows.length,'DOD verified','Source/issue proof accepted',C.mint);
 card(s,4.78,1.95,3.76,2.10,'2','Candidate/local rendition work','Source/presentation proof is not hosted release',C.gold);
 card(s,8.9,1.95,3.76,2.10,'UNKNOWN','Conversation raw prompt count','No full export; do not invent total',C.blue);
 const positions=rows.map(x=>[x.id,x.completion]);positions.forEach(([id,status],i)=>{const col=i%2,row=Math.floor(i/2),x=.66+col*6.12,y=4.45+row*.47;
  t(s,id,x,y,.94,.28,{fontSize:12,bold:true,color:C.blue});fit(s,status,x+1.0,y,4.88,.28,12,{color:status==='DONE'?C.mint:status==='HOLD'?C.red:C.gold});});
 notes(s,data.authorities.global_issue_controller,data.authorities.existing_handover);
}
// 6: global DOV.
{
 const s=base('verification','Global DOV: eight non-compensating verification domains',6,'Two PASS, three PARTIAL, three HOLD - never an averaged admission score');
 const list=data.global_dov;
 card(s,.64,2.02,3.76,1.68,'2 / 8','PASS','Census completeness and issue lifecycle evidence',C.mint);
 card(s,4.78,2.02,3.76,1.68,'3 / 8','PARTIAL','Dedup, test coverage and communication handoff',C.gold);
 card(s,8.9,2.02,3.76,1.68,'3 / 8','HOLD','Runtime, security/admission and statistical CONTROL',C.red);
 list.forEach((x,i)=>{const x0=i%2===0?.64:6.81,y=4.05+Math.floor(i/2)*.57;
   box(s,x0,y,5.78,.47,C.panel);t(s,x.id,x0+.13,y+.09,1.15,.28,{fontSize:10.5,color:C.blue,bold:true});
   fit(s,x.domain,x0+1.29,y+.07,3.40,.31,12);fit(s,x.state,x0+4.84,y+.09,.72,.29,10.4,{bold:true,color:x.state==='PASS'?C.mint:x.state==='HOLD'?C.red:C.gold,align:'right'});
 });
 notes(s,data.authorities.global_issue_controller,data.authorities.admission_controller);
}
// 7: BD leaf cards.
{
 const s=base('queue','Eight bounded BD packets, with explicit source-owner action',7,'Single existing root authority; no redundant issue IDs minted');
 data.bd_queue.forEach((q,i)=>{const col=i%2,row=Math.floor(i/2),x=.63+col*6.12,y=1.95+row*1.17;
  box(s,x,y,5.82,1.01,C.panel);
  t(s,q.priority,x+.13,y+.15,.55,.26,{fontSize:11,bold:true,color:q.priority==='P0'?C.red:C.gold});
  fit(s,q.title,x+.73,y+.09,4.84,.37,13.6,{bold:true});
  fit(s,q.state+'   |   '+q.owner,x+.73,y+.52,4.84,.28,10.3,{color:C.muted});
 });
 notes(s,...data.bd_queue.slice(0,6).map(x=>x.source));
}
// 8: next wave & method validity.
{
 const s=base('next','Next governed N-to-N+3: repair, reprove, then qualify',8,'Asymptote and Six Sigma require a defect-opportunity population, not a screenshot');
 const blocks=[
  ['N+1 / TRIAGE','Hold independent A10; requalify #2156 coverage[toml] and #2161 marker contract'],
  ['N+2 / ROOT','Source-own shared defusedxml first-red; retest #2164 matched dashboard population'],
  ['N+3 / CONTROL','Recollect B9 eligible changed lines and independent same-source repeats; measure queue/run p95']
 ];
 blocks.forEach(([title,detail],i)=>{const y=1.98+i*1.28;box(s,.65,y,11.95,1.06,i===0?C.pane2:C.panel);
   t(s,title,.87,y+.18,2.25,.3,{fontSize:15,bold:true,color:C.mint});fit(s,detail,3.18,y+.13,9.08,.73,15,{valign:'mid'});
 });
 box(s,.65,6.0,11.95,.56,C.pane2);fit(s,'PCA: NOT QUALIFIED    |    BT pairs: 0    |    Six Sigma opportunity denominator: UNKNOWN    |    Admission: HOLD',.84,6.1,11.58,.33,13,{bold:true,color:C.gold});
 notes(s,...data.bd_queue.slice(0,5).map(x=>x.source),'https://github.com/GBOGEB/gg_MATH/issues/27');
}
// Validate geometry: decorative contained panels and their text are intentionally layered.
for(const [i,slide] of P._slides.entries()){
 try{warnIfSlideHasOverlaps(slide,P);warnIfSlideElementsOutOfBounds(slide,P)}catch(err){console.error('slide geometry '+(i+1),err);throw err}
}
P.writeFile({fileName:out}).then(()=>console.log('PPTX_RENDERED',out,'slides',P._slides.length,'master_sha256',sha)).catch(e=>{console.error(e);process.exitCode=1});
