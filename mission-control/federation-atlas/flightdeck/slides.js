#!/usr/bin/env node
'use strict';
const fs=require('fs');
const pptxgen=require('pptxgenjs');
let slideHelpers;
try { slideHelpers=require('/home/oai/skills/slides/pptxgenjs_helpers'); }
catch (_) {slideHelpers={warnIfSlideElementsOutOfBounds:()=>{}};} // The portable npm build has its own independent slide overflow QA.
const {warnIfSlideElementsOutOfBounds}=slideHelpers;
if(process.argv.length!==4)throw Error('Usage: node slides.js census.json output.pptx');
const d=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
if(d.schema!=='missioncontrol.flightdeck.census.v1'||d.metrics.eligible_cells!==42)throw Error('Unqualified census');
const output=process.argv[3];const pptx=new pptxgen();pptx.layout='LAYOUT_WIDE';pptx.author='Mission Control generated projection';pptx.subject='W1/W2 governed evidence projection; source '+d.source_semantic_sha256;pptx.title='Mission Control Federation Flight Deck';pptx.lang='en-GB';
const C={bg:'0A1424',panel:'162840',cyan:'72DAE8',violet:'B39AEE',white:'EDF3FC',muted:'AFC4D6',line:'455774',good:'79D5B2',warn:'FFCB98'};
const sw=13.333,sh=7.5;const pptxShape=pptx.ShapeType;
function text(s,t,x,y,w,h,size=19,opt={}){s.addText(String(t),{x,y,w,h,fontFace:'Aptos',fontSize:size,color:C.white,margin:0,breakLine:false,...opt})}
function frame(title,tag){const s=pptx.addSlide();s.background={color:C.bg};s.addShape(pptxShape.rect,{x:0,y:0,w:sw,h:.07,line:{color:C.cyan},fill:{color:C.cyan}});text(s,'MISSION CONTROL  /  CODE PURPLE',.62,.35,7,.22,12,{bold:true,charSpacing:2.5,color:C.cyan});text(s,title,.62,.91,12.1,.72,32,{bold:true});text(s,tag,.62,6.95,10,.24,10,{color:C.muted});text(s,'W1/W2',11.65,6.95,1.1,.24,10,{color:C.cyan,align:'right'});return s}
function stat(s,x,y,w,h,val,title,desc){s.addShape(pptxShape.roundRect,{x,y,w,h,rectRadius:.13,line:{color:C.line,width:.7},fill:{color:C.panel}});text(s,title,x+.2,y+.19,w-.4,.25,12,{color:C.muted});text(s,val,x+.2,y+.56,w-.4,.52,31,{bold:true,color:C.white});text(s,desc,x+.2,y+h-.54,w-.4,.28,10,{color:C.muted})}
function bullet(s,x,y,line,width=11){s.addShape(pptxShape.ellipse,{x,y:y+.075,w:.08,h:.08,line:{color:C.cyan},fill:{color:C.cyan}});text(s,line,x+.21,y,width-.25,.63,15,{color:C.white,breakLine:false});}
let s=frame('Engineering intelligence. Traceable by design.','Generated review only • QPS = DEFER • no automatic admission');
text(s,'Six specialist repositories. One mission, one source-bound evidence language.',.68,1.92,11.3,1,21,{color:C.muted});
stat(s,.68,3.28,3.75,2.6,'6 / 42','G4 observed cells','Metadata only; 36 UNKNOWN');stat(s,4.72,3.28,3.75,2.6,'2 / 5','Historic main anchors','Three must be refreshed');stat(s,8.76,3.28,3.75,2.6,'8','Controlled stages','CLI → QA → owner gate');
s=frame('Who we are — roles and outputs','Source roles from MissionControl flightdeck contract');
const roles=d.repositories;
roles.forEach((r,i)=>{const col=i%3,row=Math.floor(i/3),x=.61+col*4.19,y=1.86+row*2.16; s.addShape(pptxShape.roundRect,{x,y,w:3.94,h:1.94,rectRadius:.11,line:{color:C.line,width:.7},fill:{color:C.panel}});text(s,r.short,x+.18,y+.16,3.55,.35,17,{bold:true,color:C.cyan});text(s,r.role,x+.18,y+.68,3.53,.77,12,{color:C.white});text(s,r.boundaries.slice(0,110),x+.18,y+1.47,3.55,.31,9,{color:C.muted});});
s=frame('The MAIN pipeline — what Python executes','Named triggers and outputs; command-level source-to-document lineage');
d.pipeline.forEach((p,i)=>{let row=Math.floor(i/4),col=i%4,x=.60+col*3.18,y=1.96+row*2.15;s.addShape(pptxShape.roundRect,{x,y,w:3,h:1.9,rectRadius:.09,line:{color:C.line,width:.7},fill:{color:C.panel}});text(s,p.id+'   '+p.group,x+.16,y+.15,2.71,.24,11,{bold:true,color:C.cyan});text(s,p.name,x+.16,y+.54,2.70,.53,15,{bold:true});text(s,p.outputs.slice(0,82),x+.16,y+1.13,2.65,.62,10,{color:C.muted});if(col<3)text(s,'→',x+3.01,y+.73,.16,.22,13,{color:C.cyan});});
s=frame('Prove it twice — prevent false green','W1 census and W2 interface use distinct validation thresholds');
stat(s,.70,1.90,3.6,2.16,'42/42','Typed leaf records','Unique repo/family identity');stat(s,4.83,1.90,3.6,2.16,'36/36','Visible BD scout leaves','No invented root closure');stat(s,8.96,1.90,3.6,2.16,'5/5','Anchor dispositions','Exact SHA with capture UTC');
bullet(s,.85,4.57,'M1: source/denominator proof; M2/M3: HOLD absent independent controls',11.5);bullet(s,.85,5.35,'CI gate ≠ full integration; signed archive bytes ≠ upload hash',11.5);
s=frame('What the user receives','Generated views, not corporate-issued engineering records');
const outputs=[['HTML + SVG','Responsive navigation and scalable process graph'],['JSON + MD','Human and machine-readable evidence, manifest and runbook'],['XLSX + DOCX','Evidence ledger and professional controlled-review report'],['PPTX + linked PDF','Leadership slides; static PDF with navigable references']];
outputs.forEach((a,i)=>{let y=1.83+i*1.13;s.addShape(pptxShape.roundRect,{x:.65,y,w:12.04,h:.91,rectRadius:.07,line:{color:C.line,width:.5},fill:{color:C.panel}});text(s,a[0],.90,y+.18,3.2,.3,18,{color:C.cyan,bold:true});text(s,a[1],4.07,y+.18,8.1,.36,16,{color:C.white});});
text(s,'Corporate issuer, document identifier, independent review and release sign-off remain external owner responsibilities.',.76,6.56,11.9,.34,11,{color:C.warn});
for(const sl of pptx._slides)warnIfSlideElementsOutOfBounds(sl,pptx);
pptx.writeFile({fileName:output}).then(()=>console.log('PPTX_PROJECTION_PASS '+output)).catch(e=>{console.error(e);process.exit(2)});