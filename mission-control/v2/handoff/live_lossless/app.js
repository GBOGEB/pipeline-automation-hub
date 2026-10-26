"use strict";
/* Live Lossless: read-only client projection. Never writes repo, BD, cookies or authentication. */
(function () {
  const API = "https://api.github.com/repos/GBOGEB/pipeline-automation-hub";
  const STATUS = {IN_PR:"In PR", HOLD:"Hold", TODO:"Todo", DEFER:"Defer", DONE:"Done", ACTIVE:"Active", CONTROL:"Control"};
  let snapshot=null, live={prs:{},issues:{},main:null}, clock=null, busy=false, diagnostics=[];
  const id = (name)=>document.getElementById(name);
  const set = (name,value)=>{id(name).textContent=value===null||value===undefined?"UNKNOWN":String(value)};
  const short=(sha)=>typeof sha==="string"&&/^[a-f0-9]{40}$/.test(sha)?sha.slice(0,10):"UNKNOWN";
  function assert(test,message){if(!test)throw Error(message)}
  function node(tag,cls,text){
    const v=document.createElement(tag);if(cls)v.className=cls;if(text!==undefined)v.textContent=String(text);return v;
  }
  function safeLink(url,label) {
    let u;
    try{u=new URL(url)}catch(_){return node("span","note","Unverified source link")}
    if(u.protocol!=="https:"||u.hostname!=="github.com"||!u.pathname.startsWith("/GBOGEB/")){
      return node("span","note","Unverified source link");
    }
    const a=node("a","",label);a.href=u.href;a.target="_blank";a.rel="noopener noreferrer";return a;
  }
  function clear(element){element.replaceChildren()}
  function detail(summary,subtext){
    const outer=node("details");const title=node("summary","",summary);
    if(subtext)title.append(node("small","",subtext));
    outer.append(title);const body=node("div","detail-body");outer.append(body);
    return {outer,body};
  }
  function labeled(text,value){
    const row=node("p");row.append(node("strong","",text+": "),node("span","",value===null?"UNKNOWN":value));return row;
  }
  function tags(parent,entries){
    entries.forEach(value=>parent.append(node("span","tag "+String(value).toLowerCase(),value)));
  }
  function renderStateBar(){
    const box=id("work-state");clear(box);
    const entries=Object.entries(snapshot.summary.action_states).sort((a,b)=>b[1]-a[1]);
    const total=snapshot.summary.tracked_actions;
    entries.forEach(([state,count])=>{
      const row=node("div","state-bar-row");const head=node("div","state-header");
      head.append(node("span","",STATUS[state]||state),node("strong","",count+" / "+total));
      const track=node("div","state-track");track.setAttribute("role","img");
      track.setAttribute("aria-label",state+": "+count+" of "+total+" captured actions");
      const fill=node("div","state-fill "+state.toLowerCase());fill.style.width=(count/total*100).toFixed(2)+"%";
      track.append(fill);row.append(head,track);box.append(row);
    });
  }
  function svgEl(tag,attrs,content){
    const e=document.createElementNS("http://www.w3.org/2000/svg",tag);
    for(const [key,value] of Object.entries(attrs))e.setAttribute(key,String(value));
    if(content!==undefined)e.textContent=String(content);
    return e;
  }
  function renderTimeline(){
    const svg=id("source-timeline");clear(svg);
    const a=snapshot.source.frozen_main_sha,b=snapshot.source.current_observed_main_sha;
    svg.append(svgEl("line",{x1:90,y1:56,x2:505,y2:56,stroke:"#7497ad","stroke-width":3,"stroke-dasharray":"8 6"}));
    svg.append(svgEl("circle",{cx:90,cy:56,r:12,fill:"#6a7d8e"}));
    svg.append(svgEl("circle",{cx:505,cy:56,r:12,fill:"#196b89"}));
    svg.append(svgEl("text",{x:90,y:25,fill:"#344c61","font-size":14,"text-anchor":"middle"},"Frozen N"));
    svg.append(svgEl("text",{x:505,y:25,fill:"#244e67","font-size":14,"text-anchor":"middle"},"Observed source"));
    svg.append(svgEl("text",{x:90,y:96,fill:"#344c61","font-size":13,"text-anchor":"middle"},short(a)));
    svg.append(svgEl("text",{x:505,y:96,fill:"#244e67","font-size":13,"text-anchor":"middle"},short(b)));
    svg.append(svgEl("text",{x:300,y:49,fill:"#587285","font-size":11,"text-anchor":"middle"},"GitHub checkpoint sequence"));
    set("clock-note","Dashed line = non-atomic observed checkpoint progression, not proven G3P pulse ancestry.");
  }
  function renderOverview(){
    const s=snapshot.summary;
    set("metric-intents",s.reconstructed_intents);set("metric-actions",s.tracked_actions);
    set("metric-bd",s.bd_focus);set("metric-prompts",s.full_chat_user_prompts);
    set("metric-checks",String(s.native_closeout_tests.k)+"/"+s.native_closeout_tests.d);
    set("metric-head",short(snapshot.source.current_observed_main_sha));
    set("metric-intent-detail",s.original_intents+" historical + "+s.current_new_intents+" continuation");
    set("metric-action-detail",s.original_actions+" historical + "+s.new_actions+" source-owned continuation");
    set("session-name",snapshot.session.alias);set("frozen-head",snapshot.source.frozen_main_sha);
    set("observed-head",snapshot.source.current_observed_main_sha);
    set("prompt-status","UNKNOWN / original transcript unavailable");
    set("accepted-status",s.n_accepted);set("coverage-status",s.global_code_coverage);
    set("snapshot-date",snapshot.snapshot_time.date+" ("+snapshot.snapshot_time.precision+")");
    set("provenance-summary","Frozen SHA-256 "+short(snapshot.provenance.frozen_manifest_sha256||"")+"; delta and GitHub overlay recorded separately. Client live readback is ephemeral until owner commits a new dated observation.");
    renderStateBar();renderTimeline();
  }
  function listLinks(body,urls){
    if(!Array.isArray(urls)||!urls.length){body.append(node("p","note","No source URI provided"));return}
    const row=node("p","source-link-list");
    urls.forEach((url,k)=>row.append(safeLink(url,"Source "+(k+1)+" ↗")));
    body.append(row);
  }
  function showActionLink(body,actionId){
    const btn=node("button","small-action","Inspect "+actionId);
    btn.type="button";
    btn.addEventListener("click",()=>{
      selectTab("actions");
      const item=id("action-"+actionId);
      if(item){item.open=true;item.scrollIntoView({block:"nearest"})}
    });
    body.append(btn);
  }
  function renderIntents(){
    const box=id("intent-cards"),subbox=id("subrequest-cards");clear(box);clear(subbox);
    snapshot.intents.forEach(intent=>{
      const d=detail(intent.id+" · "+intent.summary,intent.source_class+" · original message ID UNKNOWN");
      d.outer.classList.add("filterable");d.outer.dataset.search=(intent.id+" "+intent.summary+" "+intent.actions.join(" ")).toLowerCase();
      d.body.append(labeled("Preserved from",intent.id==="SC-I007"?"Current in-chat continuation":"Frozen source-bound historical checkpoint"));
      d.body.append(labeled("Source class",intent.source_class));
      d.body.append(node("p","note","Original timestamps and messages are unavailable, not inferred."));
      const p=node("div");tags(p,intent.actions);d.body.append(p);
      intent.actions.forEach(a=>showActionLink(d.body,a));
      box.append(d.outer);
    });
    snapshot.subrequests.forEach(sub=>{
      const d=detail(sub.id+" · "+sub.title,sub.tier);
      d.outer.classList.add("filterable");d.outer.dataset.search=(sub.title+" "+sub.detail+" "+sub.id).toLowerCase();
      d.body.append(node("p","",sub.detail));
      d.body.append(labeled("Evidence class",sub.tier));
      sub.actions.forEach(a=>showActionLink(d.body,a));
      subbox.append(d.outer);
    });
    filterIntents();
  }
  function laneFor(a){
    const body=(a.owner+" "+(a.evidence_urls||[]).join(" ")).toLowerCase();
    if(body.includes("abacus")||body.includes("dow"))return "DOW";
    if(body.includes("codex")||body.includes("keb"))return "KEB";
    if(body.includes("cryoplant-project")||body.includes("qps"))return "QPS";
    return "MC";
  }
  function renderActions(){
    const box=id("action-cards");clear(box);
    snapshot.actions.forEach(a=>{
      const d=detail(a.id+" · "+a.summary,a.priority+" / "+a.state+" / "+a.owner);
      d.outer.id="action-"+a.id;
      d.outer.classList.add("action-item");d.outer.dataset.state=a.state;d.outer.dataset.owner=laneFor(a);
      d.body.append(labeled("Definition of Done",a.done_when));
      d.body.append(labeled("Owner",a.owner));
      d.body.append(labeled("Status at capture",a.state));
      d.body.append(labeled("Depends on",a.depends_on.join(", ")||"none"));
      d.body.append(node("p","note","This is an owned action record, not an autonomous GitHub issue or a verified closeout."));
      listLinks(d.body,a.evidence_urls);
      box.append(d.outer);
    });
    filterActions();
    const bd=id("bd-cards");clear(bd);
    snapshot.bd_queue.focus.forEach(item=>{
      const d=detail(item.id+" · "+item.title,item.severity+" / "+item.state+" / "+item.flow+" · historical snapshot");
      d.body.append(labeled("Canonical BD state",item.state));
      d.body.append(labeled("Last history ordinal",item.at));
      d.body.append(labeled("Source evidence",item.source_evidence));
      d.body.append(labeled("Exit criterion",item.done_when));
      d.body.append(labeled("Control criterion",item.control_when));
      listLinks(d.body,item.links);
      bd.append(d.outer);
    });
  }
  function renderPRs(){
    const rows=id("pr-rows");clear(rows);
    const repo="https://github.com/GBOGEB/pipeline-automation-hub";
    snapshot.prs.forEach(pr=>{
      const livePR=live.prs[pr.number];const tr=node("tr");
      const cellNumber=node("td");cellNumber.append(safeLink(repo+"/pull/"+pr.number,"#"+pr.number));
      const cellFrozen=node("td","",pr.state+(pr.draft?" · draft":""));
      const cellLive=node("td","",livePR?livePR.state+(livePR.draft?" · draft":""):"NOT_CHECKED");
      const cellHead=node("td");cellHead.append(node("code","",short(livePR?livePR.head:pr.head)));
      const cellProof=node("td");cellProof.append(safeLink(repo+"/pull/"+pr.number,livePR?"GitHub readback ↗":"Frozen PR ↗"));
      tr.append(cellNumber,cellFrozen,cellLive,cellHead,cellProof);rows.append(tr);
    });
    const issues=id("issue-rows");clear(issues);
    snapshot.issues.forEach(issue=>{
      const current=live.issues[issue.number],tr=node("tr");
      const n=node("td");n.append(safeLink(repo+"/issues/"+issue.number,"#"+issue.number));
      const h=node("td","",issue.state.toUpperCase());
      const r=node("td","",current||"NOT_CHECKED");
      const proof=node("td");proof.append(safeLink(repo+"/issues/"+issue.number,"Source ↗"));
      tr.append(n,h,r,proof);issues.append(tr);
    });
  }
  function renderEvidence(){
    renderPRs();
    const metrics=id("metric-observations");clear(metrics);
    snapshot.metric_observations.forEach(m=>{
      const d=detail(m.metric+" · "+(m.numerator===null?"UNKNOWN":m.numerator+"/"+m.denominator)+" "+m.unit,m.population+" · "+m.evidence_class);
      d.body.append(labeled("Eligible population",m.population));
      d.body.append(labeled("Evidence scope",m.evidence_class));
      listLinks(d.body,[m.source]);metrics.append(d.outer);
    });
    const sources=id("source-links");clear(sources);
    const row=node("div","source-link-list");
    Object.entries(snapshot.source_links).forEach(([name,url])=>row.append(safeLink(url,name.replaceAll("_"," ")+" ↗")));
    sources.append(row);
    set("feed-diagnostics",JSON.stringify({
      scope:snapshot.source_class,frozen_main:snapshot.source.frozen_main_sha,
      observed_main:snapshot.source.current_observed_main_sha,
      live_main:live.main||null,
      live_validated_prs:Object.keys(live.prs).length,
      live_validated_issues:Object.keys(live.issues).length,
      recent_failures:diagnostics,
      authority_transfer:false,merge_admission:"INDEPENDENT_HOLD"
    },null,2));
  }
  function renderMonikers(){
    const box=id("moniker-cards");clear(box);
    snapshot.monikers.forEach(m=>{
      const d=detail(m.name+" · "+m.scope,m.details);
      d.body.append(node("pre","code-block",m.invocation));
      const copy=node("button","copy","Copy instruction");copy.type="button";
      copy.addEventListener("click",async()=>{
        try{
          if(!navigator.clipboard||!navigator.clipboard.writeText)throw Error("Clipboard not permitted");
          await navigator.clipboard.writeText(m.invocation);
          copy.textContent="Copied";copy.dataset.copied="true";
        }catch(_){copy.textContent="Copy unavailable — select instruction above";copy.dataset.copied="false"}
      });
      d.body.append(copy,safeLink(m.url,"Contract / owner ↗"));box.append(d.outer);
    });
    const links=id("resume-links");clear(links);
    Object.entries(snapshot.source_links).forEach(([key,url])=>links.append(safeLink(url,key.replaceAll("_"," ")+" ↗"),node("span","", "  ")));
  }
  function filterIntents(){
    const q=id("search").value.trim().toLowerCase();
    let shown=0;
    document.querySelectorAll(".filterable").forEach(e=>{
      const match=!q||e.dataset.search.includes(q);e.hidden=!match;if(match)shown++;
    });
    id("intent-empty").hidden=shown!==0;
  }
  function filterActions(){
    const owner=id("owner-filter").value,state=id("state-filter").value;
    document.querySelectorAll(".action-item").forEach(e=>{
      e.hidden=(owner!=="ALL"&&owner!==e.dataset.owner)||(state!=="ALL"&&state!==e.dataset.state);
    });
  }
  const TABS=["overview","intents","actions","evidence","monikers"];
  function selectTab(name){
    if(!TABS.includes(name))name="overview";
    for(const target of TABS){
      const button=id("tab-"+target),active=target===name;
      button.setAttribute("aria-selected",String(active));button.tabIndex=active?0:-1;
      id("panel-"+target).hidden=!active;
    }
    if(location.hash!=="#"+name)history.replaceState(null,"","#"+name);
  }
  function validateSnapshot(s){
    assert(s&&s.schema==="missioncontrol.live_lossless.dashboard.v1","snapshot schema unavailable");
    assert(s.authority_transfer===false&&s.security_waiver===false&&s.merge_admission==="INDEPENDENT_HOLD","unsafe source authority");
    assert(s.privacy==="SANITIZED_NOT_VERBATIM","source privacy");
    assert(s.summary.reconstructed_intents===s.intents.length&&s.summary.tracked_actions===s.actions.length,"summary population drift");
    assert(s.summary.full_chat_user_prompts===null&&s.session.full_chat_prompts===null,"unknown prompt count falsely filled");
    assert(s.source.repository==="GBOGEB/pipeline-automation-hub"||s.source.repository===undefined,"source owner");
    assert(/^[a-f0-9]{40}$/.test(s.source.current_observed_main_sha),"source SHA");
    assert(Array.isArray(s.prs)&&Array.isArray(s.monikers)&&Array.isArray(s.bd_queue.focus),"missing detail sources");
  }
  async function loadSnapshot(){
    const resp=await fetch("snapshot.json",{cache:"no-store"});
    if(!resp.ok)throw Error("snapshot.json HTTP "+resp.status);
    const data=await resp.json();validateSnapshot(data);snapshot=data;
    renderOverview();renderIntents();renderActions();renderEvidence();renderMonikers();
    selectTab(location.hash.slice(1)||"overview");
    id("feed-status").textContent="SNAPSHOT_LOADED · GitHub readback pending";
    return true;
  }
  async function requestOne(item){
    const path=item.kind==="MAIN"?"/branches/master":item.kind==="PR"?"/pulls/"+item.number:"/issues/"+item.number;
    const response=await fetch(API+path,{headers:{Accept:"application/vnd.github+json"},cache:"no-store"});
    if(!response.ok)throw Error(item.kind+" #"+(item.number||"main")+" HTTP "+response.status);
    const data=await response.json();
    if(item.kind==="MAIN"){
      assert(data.name==="master"&&/^[a-f0-9]{40}$/.test(data.commit?.sha||""),"remote main SHA identity");
      return {kind:item.kind,head:data.commit.sha};
    }
    assert(data.number===item.number,"remote number mismatch");
    if(item.kind==="PR"){
      assert(/^[a-f0-9]{40}$/.test(data.head?.sha||""),"remote PR head missing");
      assert(data.state==="open"||data.state==="closed","remote PR state");
      return {kind:"PR",number:item.number,head:data.head.sha,
        state:data.state==="open"?"OPEN":data.merged_at?"MERGED":"CLOSED_UNMERGED",draft:data.draft===true};
    }
    assert(data.state==="open"||data.state==="closed","remote issue state");
    return {kind:"ISSUE",number:item.number,state:data.state.toUpperCase()};
  }
  async function refreshGitHub(){
    if(busy||!snapshot)return;
    busy=true;id("refresh").disabled=true;
    id("feed-status").textContent="CHECKING_GITHUB · read-only";
    const config=snapshot.github_monitor;
    const targets=[{kind:"MAIN"}]
      .concat(config.pull_requests.map(n=>({kind:"PR",number:n})))
      .concat(config.issues.map(n=>({kind:"ISSUE",number:n})));
    const results=await Promise.allSettled(targets.map(requestOne));
    const next={prs:{...live.prs},issues:{...live.issues},main:live.main};
    const failures=[];let count=0;
    results.forEach((r,k)=>{
      if(r.status!=="fulfilled"){failures.push(targets[k].kind+" "+(targets[k].number||"main")+": "+String(r.reason));return}
      const value=r.value;count++;
      if(value.kind==="MAIN")next.main=value.head;
      else if(value.kind==="PR")next.prs[value.number]=value;
      else next.issues[value.number]=value.state;
    });
    live=next;diagnostics=failures;
    const status=count===targets.length?"LIVE_COMPLETE":count===0?"LIVE_UNAVAILABLE":"LIVE_PARTIAL";
    const indicator=id("feed-status");indicator.dataset.status=status;
    indicator.textContent=status+" · "+count+"/"+targets.length+" readbacks; not admission";
    set("remote-head",live.main);
    set("readback-time","Browser check (UTC): "+new Date().toISOString());
    if(live.main){
      const changed=live.main!==snapshot.source.current_observed_main_sha;
      id("metric-head").textContent=short(live.main)+(changed?" ↑":"");
      id("metric-head").title=changed?"New main observed; static snapshot requires next source-owned commit":"Matches frozen observed main";
    }
    renderPRs();renderEvidence();
    id("source-errors").hidden=failures.length===0;
    if(failures.length)id("source-errors").textContent="Read-only GitHub API partial/unavailable. Frozen evidence retained. "+failures.slice(0,2).join("; ");
    id("refresh").disabled=false;busy=false;
  }
  function init(){
    TABS.forEach((name,k)=>{
      const b=id("tab-"+name);
      b.addEventListener("click",()=>selectTab(name));
      b.addEventListener("keydown",e=>{
        let target=null;
        if(e.key==="ArrowRight")target=TABS[(k+1)%TABS.length];
        else if(e.key==="ArrowLeft")target=TABS[(k-1+TABS.length)%TABS.length];
        else if(e.key==="Home")target=TABS[0];
        else if(e.key==="End")target=TABS[TABS.length-1];
        if(target){e.preventDefault();selectTab(target);id("tab-"+target).focus()}
      });
    });
    id("search").addEventListener("input",filterIntents);
    id("reset-filters").addEventListener("click",()=>{id("search").value="";filterIntents()});
    id("expand-all").addEventListener("click",()=>document.querySelectorAll("#panel-intents details:not([hidden])").forEach(x=>x.open=true));
    id("collapse-all").addEventListener("click",()=>document.querySelectorAll("#panel-intents details:not([hidden])").forEach(x=>x.open=false));
    id("owner-filter").addEventListener("change",filterActions);
    id("state-filter").addEventListener("change",filterActions);
    id("refresh").addEventListener("click",refreshGitHub);
    id("interval").addEventListener("change",()=>{
      if(clock!==null){clearInterval(clock);clock=null}
      const minutes=Number(id("interval").value);
      if([15,60].includes(minutes))clock=setInterval(refreshGitHub,minutes*60*1000);
    });
    id("interval").dispatchEvent(new Event("change"));
    loadSnapshot().then(refreshGitHub).catch(e=>{
      id("feed-status").textContent="SNAPSHOT_UNAVAILABLE";
      id("source-errors").hidden=false;
      id("source-errors").textContent="Source validation failed closed: "+String(e);
      id("refresh").disabled=true;
    });
  }
  init();
})();
