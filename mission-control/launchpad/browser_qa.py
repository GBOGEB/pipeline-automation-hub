#!/usr/bin/env python3
"""Fail-closed, source SHA qualified MissionControl Chromium UI and negative QA."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

SIZES=(("desktop",1440,1000),("laptop",1280,800),("mobile",390,844))
REQ_CONTROL=("search","lane","graph-mode","edge-filter","reset","theme","graph-expand","graph-copy")
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def exact_head():
    try:return subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
    except (OSError,subprocess.CalledProcessError):return None
def check(condition,signal):
    if not condition:raise AssertionError(signal)
def links(page,root):
    found=[]
    for a in page.locator("a").all():
        if not a.is_visible():continue
        href=a.get_attribute("href") or ""
        check(not href.startswith(("javascript:","data:","//")),"MC_QA_UNSAFE_LINK")
        check(bool(href),"MC_QA_EMPTY_LINK")
        if href.startswith("https:"):
            check(href.startswith("https://github.com/GBOGEB/"),"MC_QA_UNTRUSTED_EXTERNAL_LINK")
            check(a.get_attribute("target")=="_blank" and
                  {"noopener","noreferrer"}<=set((a.get_attribute("rel") or "").split()),"MC_QA_TAB_ISOLATION")
        else:
            check(href in ("federation.mmd","SIPOC.md","snapshot.json","manifest.json"),"MC_QA_UNKNOWN_LOCAL_ROUTE")
            check((root/href).exists(),"MC_QA_BROKEN_LOCAL_ROUTE")
        found.append(href)
    return found
def geometry(page):
    return page.evaluate("""() => {
       let error=[],els=[...document.querySelectorAll('.panelgrid > .panel')];
       for(let i=0;i<els.length;i++){
         let a=els[i].getBoundingClientRect();
         if(a.height<50||a.width<100)error.push('COLLAPSED_'+i);
         for(let j=i+1;j<els.length;j++){
           let b=els[j].getBoundingClientRect();
           let dx=Math.max(0,Math.min(a.right,b.right)-Math.max(a.left,b.left));
           let dy=Math.max(0,Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top));
           if(dx*dy>30)error.push('OVERLAP_'+i+'_'+j);
         }
       }
       return {body:document.documentElement.scrollWidth,viewport:window.innerWidth,
               graph:document.getElementById('graph').getBoundingClientRect().width,
               errors:error};
    }""")
def run(html_path,manifest_path,out):
    html_path=Path(html_path);manifest_path=Path(manifest_path);out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    h=json.loads(manifest_path.read_text(encoding="utf-8"))
    check(h.get("schema")=="missioncontrol.launchpad.publication_manifest.v1","MC_QA_MANIFEST")
    check(h.get("merge_admission")=="HOLD" and h.get("authority_transfer") is False,"MC_QA_GOVERNANCE")
    check(digest(html_path)==h["files_sha256"]["index.html"],"MC_QA_HTML_DIGEST")
    expected=os.environ.get("MC_EXACT_HEAD")
    source=exact_head()
    if expected:check(source==expected==h["source_head_sha"],"MC_QA_EXACT_HEAD")
    html=html_path.read_text(encoding="utf-8")
    record={"schema":"missioncontrol.launchpad.visual_qa.v1","source_head":source,
            "exact_head_confirmed":bool(expected and source==expected),
            "run_id":os.environ.get("GITHUB_RUN_ID"),"run_attempt":os.environ.get("GITHUB_RUN_ATTEMPT"),
            "job_key":os.environ.get("GITHUB_JOB"),"html_sha256":digest(html_path),
            "manifest_sha256":digest(manifest_path),"viewports":[],"negative":[],"screenshots":[],
            "merge_admission":"HOLD","authority_transfer":False,"hosted_http_verified":False}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            for label,w,hh in SIZES:
                page=browser.new_page(viewport={"width":w,"height":hh},device_scale_factor=1)
                errors=[]
                page.on("pageerror",lambda e:errors.append(str(e)))
                page.on("console",lambda m:errors.append(m.text) if m.type=="error" else None)
                page.set_content(html,wait_until="load")
                check(page.title()=="MissionControl | Federation Navigator","MC_QA_TITLE")
                check(page.locator("h1").count()==1,"MC_QA_H1")
                check(all(page.locator("#"+i).count()==1 for i in REQ_CONTROL),"MC_QA_MISSING_CONTROL")
                check(page.locator("#repo-list article").count()==6,"MC_QA_REPO_DENOMINATOR")
                check(page.locator("#graph .node").count()==13,"MC_QA_NODE_DENOMINATOR")
                check(page.locator("#graph .graph-edge").count()==19,"MC_QA_EDGE_DENOMINATOR")
                check("CONTROL HOLD" in page.locator(".status").inner_text(),"MC_QA_FALSE_GO")
                check(page.locator("#receipt-count").inner_text()=="3 historical","MC_QA_FALSE_RECEIPT_COUNT")
                check("UNKNOWN" in page.locator("#execution").inner_text(),"MC_QA_FALSE_WORKER_COUNT")
                page.locator("#search").fill("CODEX")
                check(page.locator("#repo-list article").count()==1,"MC_QA_SEARCH")
                page.locator("#search").fill("")
                page.locator("#lane").select_option("ENGINEERING")
                check(page.locator("#repo-list article").count()==1 and
                      "classification needed" in page.locator("#repo-list").inner_text(),"MC_QA_QPS_SCOPE")
                page.locator("#reset").click()
                check(page.locator("#repo-list article").count()==6,"MC_QA_RESET")
                page.locator("#graph-mode").select_option("DEPENDS_ON")
                check(page.locator("#graph .graph-edge").count()==7,"MC_QA_DAG_EDGES")
                page.locator("#graph-mode").select_option("EVIDENCE")
                check(page.locator("#graph .graph-edge").count()==5,"MC_QA_EVIDENCE_EDGES")
                page.locator("#graph-mode").select_option("ALL")
                page.locator("#edge-filter").select_option("RECEIPT")
                check(page.locator("#edges-list .record").count()==3,"MC_QA_HISTORICAL_RECEIPTS")
                page.locator("#edge-filter").select_option("ALL")
                check(page.locator("#edges-list .record").count()==19,"MC_QA_EDGES_RESET")
                page.locator("#graph [data-node='codex']").focus()
                page.keyboard.press("Enter")
                check("CODEX / KEB" in page.locator("#node-detail").inner_text(),"MC_QA_NODE_INSPECTION")
                page.locator("#theme").click()
                check("light" in page.locator("body").get_attribute("class"),"MC_QA_THEME")
                page.locator("#theme").click()
                page.locator("#graph-expand").click()
                check("fullgraph" in page.locator("#federation-graph").get_attribute("class"),"MC_QA_FOCUS")
                page.keyboard.press("Escape")
                check("fullgraph" not in page.locator("#federation-graph").get_attribute("class"),"MC_QA_ESCAPE")
                page.locator("#graph-copy").click()
                check("Mermaid" in page.locator("#graph-copy").inner_text() or
                      "source link" in page.locator("#graph-copy").inner_text(),"MC_QA_EXPORT")
                path=out/(label+".png");page.screenshot(path=str(path),full_page=True,animations="disabled")
                geo=geometry(page);check(not geo["errors"],"MC_QA_OVERLAP "+str(geo["errors"]))
                check(geo["body"]<=geo["viewport"]+2,"MC_QA_BODY_OVERFLOW")
                hrefs=links(page,html_path.parent)
                check(len(hrefs)>=12,"MC_QA_LINK_DENOMINATOR")
                check(not errors,"MC_QA_SCRIPT_ERRORS "+str(errors[:4]))
                record["viewports"].append({"label":label,"width":w,"height":hh,
                     "body_overflow_px":max(0,geo["body"]-geo["viewport"]),
                     "overlap":[],"visible_link_count":len(hrefs),"result":"PASS"})
                record["screenshots"].append({"viewport":label,"file":path.name,"sha256":digest(path)})
                page.close()
            # Adversarial source corruption must produce a visible page error, never false-green.
            bads=[("FORGED_MERGE_GO",html.replace('"merge_admission":"HOLD"','"merge_admission":"GO"',1)),
                  ("FORGED_MUTATION",html.replace('"mutation_enabled":false','"mutation_enabled":true',1))]
            for signal,mutated in bads:
                check(mutated!=html,"MC_QA_SEED_NOT_APPLIED_"+signal)
                page=browser.new_page();errors=[];page.on("pageerror",lambda e:errors.append(str(e)))
                page.set_content(mutated,wait_until="load")
                check(any("CONTROL_GUARD_FAIL" in e for e in errors),"MC_QA_FALSE_GREEN_"+signal)
                record["negative"].append({"seed":signal,"result":"EXPECTED_FAIL"});page.close()
        finally:browser.close()
    check(len(record["viewports"])==3 and len(record["negative"])==2,"MC_QA_INCOMPLETE")
    (out/"visual_qa.json").write_text(json.dumps(record,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
    print("MISSIONCONTROL_LAUNCHPAD_BROWSER=PASS",len(record["viewports"]),"viewports, 2 seeded negatives, admission HOLD")
    return record
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--html",required=True);a.add_argument("--manifest",required=True);a.add_argument("--out",required=True)
    x=a.parse_args();run(x.html,x.manifest,x.out)
