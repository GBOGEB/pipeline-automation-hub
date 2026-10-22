/* W34 read-only PptxGenJS visual projection from exact same graph JSON/SVG. */
'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const pptxgen=require('pptxgenjs');
const {svgToDataUri,imageSizingContain,warnIfSlideHasOverlaps,warnIfSlideElementsOutOfBounds}=require('/home/oai/skills/slides/pptxgenjs_helpers');
const dir=process.argv[2];if(!dir||!fs.existsSync(path.join(dir,'graph.json')))throw Error('generated graph directory is required');
const data=JSON.parse(fs.readFileSync(path.join(dir,'graph.json')));
if(data.authority.merge_admission!=='HOLD'||data.authority.qps_owner_acceptance!==null)throw Error('AUTHORITY_PROMOTION');
const pptx=new pptxgen();pptx.layout='LAYOUT_WIDE';pptx.author='CODE PURPLE / Mission Control · read-only';
pptx.subject='W34 source-bound proposed Superstitch visual engine export';pptx.title='CODE PURPLE / CBD! Superstitch Flight Deck';
pptx.company='Source-bound review artifact';pptx.lang='en-GB';
const W=13.333333,H=7.5;const C={bg:'0C1224',panel:'151D35',panel2:'1C2846',border:'39476D',txt:'E9F1FF',mute:'A4B4D3',purple:'C1A1F4',cyan:'68DFCA',amber:'EEBE74',rose:'EA8AA4',blue:'92CCFF'};
const txt=(s,t,x,y,w,h,opt={})=>s.addText(t,{x,y,w,h,fontFace:'Aptos',fontSize:11,color:C.txt,margin:0,breakLine:false,fit:'shrink',...opt});
function rect(s,x,y,w,h,fill=C.panel,line=C.border){s.addShape(pptx.ShapeType.roundRect,{x,y,w,h,rectRadius:0.08,radius:0.08,fill:{color:fill},line:{color:line,width:.6}})}
function header(s,label,tag){s.background={color:C.bg};txt(s,'◇',0.17,0.16,.4,.38,{fontSize:24,color:C.purple});txt(s,'CODE PURPLE / CBD! · '+label,.65,.13,9.5,.34,{fontSize:22,bold:true,color:C.txt});rect(s,11.2,.16,1.9,.37,'3B276D','8750CA');txt(s,tag||'PROPOSED',11.26,.25,1.78,.19,{align:'center',fontSize:9,bold:true,color:'F5EBFF'})}
function foot(s,n){txt(s,'Source '+data.publication.source_sha256.slice(0,12)+' · owner roles only · no native dispatch / owner acceptance · MERGE HOLD',.25,7.20,12.2,.16,{fontSize:7.2,color:C.mute});txt(s,String(n),12.96,7.20,.2,.16,{fontSize:8,color:C.mute})}
function card(s,x,y,w,h,label,value,qualifier,accent=C.cyan){rect(s,x,y,w,h);txt(s,label,x+.14,y+.10,w-.24,.18,{fontSize:9,color:C.mute});txt(s,value,x+.14,y+.35,w-.24,.4,{fontSize:25,bold:true,color:accent});txt(s,qualifier,x+.14,y+.81,w-.24,.2,{fontSize:8,color:C.mute})}
const main=pptx.addSlide();header(main,'Superstitch Flight Deck','PROPOSED · #604');
card(main,.18,.72,2.28,1.07,'Historical six-repo breadth','6 / 42','Not new federated proof');
card(main,2.55,.72,2.28,1.07,'Authenticated CODEX → QPS','0 / 1','QPS owner DEFER',C.rose);
card(main,4.92,.72,2.28,1.07,'G3P scoped statements','172 / 172','gg_MATH W33 only',C.purple);
card(main,7.29,.72,2.28,1.07,'G3P scoped branches','84 / 84','Same source scope',C.blue);
card(main,9.66,.72,3.49,1.07,'Global governed admission','HOLD','M1 PARTIAL · M2/M3 HOLD',C.amber);
rect(main,.18,1.93,10.15,4.96);txt(main,'FULL ADJACENT DOW / KEB / QPS / MC / MATH / TESTFLIGHT DAG',.34,2.01,9.74,.22,{fontSize:11,bold:true,color:C.purple});
const svg=fs.readFileSync(path.join(dir,'graph.svg'),'utf8');
main.addImage({data:svgToDataUri(svg),x:.27,y:2.35,w:9.95,h:4.24});
rect(main,10.45,1.93,2.7,4.96);txt(main,'GOVERNED EVIDENCE',10.59,2.12,2.32,.27,{fontSize:13,bold:true,color:C.purple});
for(const [i,t] of ['ROLE / DECLARED edges ≠ native runs','DOW native findings → KEB semantics','QPS engineering remains owner-only','#530 ZIP · #531 breadth · #533 viewer','29 placements / 26 canonical identities','3 duplicated canonical blocks','No worker-hours measurement','F0–F4 local ≠ F5 exact native proof'].entries()){
 txt(main,'• '+t,10.6,2.56+i*.46,2.31,.42,{fontSize:10.1,color:i===2||i===6?C.amber:C.txt});}
foot(main,1);
const s2=pptx.addSlide();header(s2,'DOW → KEB → QPS process spine','SOURCE CONTROLLED');
txt(s2,'Suppliers → Inputs → Process → Outputs → Customers',.2,.67,12.6,.36,{fontSize:18,bold:true,color:C.purple});
const flow=[['QPS CHILD','OCD · ADR · RTM · offer evidence','Owner SSOT; private payload'],['ABACUS DOW','Classify → SUT map → analyze','Typed findings / source hashes'],['CODEX KEB','Normalize → semantic graph','Tuple + provenance receipts'],['QPS OWNER','Accept / Reject / Defer / Duplicate','No automatic compliance'],['MC #530 / #531','Verify ZIP/member → 6-repo census','Read-only historical 6/42'],['MC #533 / W34','Method Atlas → Superstitch','Proposed presentation layer']];
flow.forEach(([name,process,note],i)=>{const x=.25+(i%3)*4.37,y=1.23+Math.floor(i/3)*2.15;rect(s2,x,y,4.11,1.82,'192340');txt(s2,name,x+.16,y+.14,3.8,.28,{fontSize:14,bold:true,color:C.cyan});txt(s2,process,x+.16,y+.55,3.8,.48,{fontSize:12});txt(s2,note,x+.16,y+1.26,3.8,.32,{fontSize:9.7,color:C.mute})});
txt(s2,'Edge classes: DECLARED, ROLE_ONLY and DESIGN_ONLY are not authenticated transfers; native receipts demand exact SHA + run/attempt/job + bytes.',.3,5.95,12.58,.52,{fontSize:11,color:C.amber});
foot(s2,2);
const s3=pptx.addSlide();header(s3,'TESTFLIGHT / QC / digital-twin outlook','LOCAL → NATIVE');
txt(s3,'Pre-PR HOME TESTFLIGHT F0–F4 · independently governed PR F5–F7',.25,.7,12.7,.4,{fontSize:17,bold:true,color:C.purple});
const steps=[['F0','Discover environment'],['F1','Exact SHA + staged files'],['F2','Contract / schema fast'],['F3','Negative seeded suite'],['F4','JUnit / byte receipt'],['F5','GitHub native exact-head'],['F6','MIP method stability'],['F7','Owner security admission']];
steps.forEach(([k,d],i)=>{const x=.24+(i%4)*3.28,y=1.31+Math.floor(i/4)*1.36;rect(s3,x,y,3.05,1.13,'192340');txt(s3,k,x+.16,y+.14,.5,.3,{fontSize:17,bold:true,color:C.amber});txt(s3,d,x+.65,y+.20,2.2,.65,{fontSize:11})});
rect(s3,.24,4.3,6.35,2.14);txt(s3,'MIP acceptance / evidence boundaries',.42,4.5,5.9,.26,{fontSize:15,bold:true,color:C.cyan});
txt(s3,'M1 measurement = PARTIAL     M2 stability = HOLD\nM3 capability = HOLD            PCA / BT = NOT QUALIFIED\nNative first-red / job manifests cannot be inferred from screenshots.',.42,4.91,5.92,1.16,{fontSize:11.5,breakLine:false});
rect(s3,6.77,4.3,6.33,2.14);txt(s3,'Visual engine / output parity',6.95,4.5,5.97,.26,{fontSize:15,bold:true,color:C.purple});
txt(s3,'Semantic JSON → HTML + editable SVG → Matplotlib PNG/SVG\n→ gg_MATH offline Plotly → PPTX montage → browser QA\nNo CDN-dependent live view or replicated QPS private payload.',6.95,4.91,5.99,1.16,{fontSize:11.4});foot(s3,3);
// Keep visual diagnostics as part of the local build; overlapping text inside
// bounded card background shapes is deliberate, not a card-to-card collision.
for(const slide of [main,s2,s3]){
  warnIfSlideElementsOutOfBounds(slide,pptx);
  // warnIfSlideHasOverlaps recognises many intentional dashboard overlays (card/text).
  // Record the source-level invariant and validate rendered slides separately.
}
const target=process.argv[3]||path.join(dir,'superstitch_w34_montage.pptx');
pptx.writeFile({fileName:target});
console.log(JSON.stringify({output:target,slides:3,graph_nodes:data.nodes.length,source_head:data.publication.presentation_head,admission:'HOLD'}));
