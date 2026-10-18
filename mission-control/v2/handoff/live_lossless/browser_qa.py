#!/usr/bin/env python3
"""Chromium functional + visual contract for Live Lossless on controlled GitHub API.

Every HTTP request for current PR and issue data is a known fixture. A green
browser is not an authenticated remote GitHub readback or a hosted Pages proof.
"""
import argparse
import hashlib
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

SIZES=(("desktop",1440,960),("laptop",1280,800),("mobile",390,844))
MAIN="b293c818ebf280e570392e398720ec22e1aa4566"
SHA="a"*40


class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*_args):
        return


class API:
    def __init__(self,snapshot):
        self.snapshot=snapshot
        self.failure=None
        self.calls=[]
    def __call__(self,route):
        path=urlparse(route.request.url).path
        self.calls.append(path)
        if self.failure=="ALL" or (self.failure=="ONE" and path.endswith("/pulls/642")):
            route.fulfill(status=503,headers={"Access-Control-Allow-Origin":"*","Content-Type":"application/json"},body='{"message":"fixture outage"}')
            return
        if path.endswith("/branches/master"):
            obj={"name":"master","commit":{"sha":self.snapshot["source"]["current_observed_main_sha"]}}
        elif "/pulls/" in path:
            n=int(path.rsplit("/",1)[1])
            found=next((x for x in self.snapshot["prs"] if x["number"]==n),None)
            if found is None:
                route.fulfill(status=404,body="not requested")
                return
            obj={"number":n,"head":{"sha":found["head"]},
                 "state":"closed" if found["state"]!="OPEN" else "open",
                 "merged_at":"2026-10-17T15:00:00Z" if found["state"]=="MERGED" else None,
                 "draft":found["draft"]}
        elif "/issues/" in path:
            n=int(path.rsplit("/",1)[1])
            found=next((x for x in self.snapshot["issues"] if x["number"]==n),None)
            if found is None:
                route.fulfill(status=404,body="not requested")
                return
            obj={"number":n,"state":found["state"]}
        else:
            route.fulfill(status=404,body="unapproved path")
            return
        route.fulfill(status=200,headers={"Access-Control-Allow-Origin":"*","Content-Type":"application/json"},body=json.dumps(obj))


def check(condition,why,log):
    if not condition:
        raise AssertionError(why)
    log.append(why)


def count_visible(page,selector):
    return page.locator(selector).evaluate_all("(els)=>els.filter(e=>getComputedStyle(e).display!=='none').length")


def test_viewport(browser,url,mode,w,h,snap,out,report):
    page=browser.new_page(viewport={"width":w,"height":h},device_scale_factor=1)
    api=API(snap)
    errors=[]
    page.on("pageerror",lambda error:errors.append(str(error)))
    page.route("https://api.github.com/**",api)
    page.goto(url,wait_until="load")
    page.locator('#feed-status').filter(has_text='LIVE_COMPLETE').wait_for(timeout=15000)
    log=[]
    check(page.locator("#metric-intents").inner_text()=="7","7 reconstructed intent rows",log)
    check(page.locator("#metric-actions").inner_text()=="11","11 tracked owned actions",log)
    check(page.locator("#metric-bd").inner_text()=="3","3 canonical BD rows",log)
    check(page.locator("#metric-prompts").inner_text()=="UNKNOWN","unknown original prompt total",log)
    check(page.locator("#metric-checks").inner_text()=="34/34","scoped exact-main test count",log)
    check("not admission" in page.locator("#feed-status").inner_text(),"no remote admission promotion",log)
    check(page.locator("#remote-head").inner_text()==MAIN,"observed main SHA readback",log)
    check(page.locator("#tab-overview").get_attribute("aria-selected")=="true","overview starts selected",log)
    check(page.locator("#work-state .state-bar-row").count()==4,"action lifecycle bar computed",log)
    check(page.locator("#source-timeline circle").count()==2,"two source-observation checkpoints",log)
    check(page.locator("#admission").inner_text()=="Admission: HOLD","admission invariant",log)

    geometry=page.evaluate("({width:document.documentElement.scrollWidth,viewport:window.innerWidth})")
    check(geometry["width"]<=geometry["viewport"]+2,"no unintended document horizontal overflow",log)
    check(not errors,"no page JavaScript exceptions",log)
    page.locator("#tab-intents").click()
    check(page.locator("#intent-cards details").count()==7,"historical and current intent details",log)
    check(page.locator("#subrequest-cards details").count()==6,"six nested subrequests",log)
    page.locator("#search").fill("SC-I007")
    check(count_visible(page,"#intent-cards details")==1,"search restricts intent cards",log)
    page.locator("#reset-filters").click()
    check(count_visible(page,"#intent-cards details")==7,"reset restores all intentions",log)
    page.locator("#expand-all").click()
    check(page.locator("#panel-intents details[open]").count()==13,"expand all visible",log)
    page.locator("#collapse-all").click()
    check(page.locator("#panel-intents details[open]").count()==0,"collapse all visible",log)
    page.locator("#subrequest-cards details").first.locator("summary").click()
    page.locator("#subrequest-cards .small-action").first.click()
    check(page.locator("#tab-actions").get_attribute("aria-selected")=="true","subrequest action deep link selects tab",log)
    check(page.locator("#action-cards details").count()==11,"all 11 action cards",log)
    check(page.locator("#bd-cards details").count()==3,"3 canonical BD cards",log)
    page.locator("#owner-filter").select_option("ALL")
    page.locator("#state-filter").select_option("HOLD")
    check(count_visible(page,"#action-cards details")==3,"HOLD state filter is effective",log)
    page.locator("#state-filter").select_option("ALL")
    check(count_visible(page,"#action-cards details")==11,"ALL restores actions",log)
    page.locator("#tab-evidence").click()
    check(page.locator("#pr-rows tr").count()==10,"all ten source PR rows",log)
    check(page.locator("#issue-rows tr").count()==2,"selected native issue rows",log)
    check(page.locator("#pr-rows").inner_text().count("MERGED")>=4,"live readback preserves merged PR statuses",log)
    page.locator("#tab-monikers").click()
    check(page.locator("#moniker-cards details").count()==6,"six versioned monikers",log)
    page.locator("#moniker-cards details").first.locator("summary").click()
    # CP.CLOSEOUT is an alias card; its instruction must bind to the canonical CP.CLOSE
    # producer (8b03321), never a second CP.CLOSEOUT(...) producer.
    first=snap["monikers"][0]["invocation"]
    check(first.startswith("CP.CLOSE(") and not first.startswith("CP.CLOSEOUT("),"alias binds to canonical CP.CLOSE",log)
    check(page.locator("#moniker-cards pre").first.inner_text()==first,"canonical moniker details",log)
    # Clipboard is explicitly user-triggered; failure is reported without false success.
    page.evaluate("""() => {
       Object.defineProperty(navigator,'clipboard',{configurable:true,value:{
         writeText:async s => {window.__copied=s}
       }});
    }""")
    page.locator("#moniker-cards .copy").first.click()
    check(page.locator("#moniker-cards .copy").first.get_attribute("data-copied")=="true","copy control action returns success",log)
    check(page.evaluate("window.__copied")==first,"copied instruction is canonical",log)
    page.locator("#tab-overview").focus()
    page.keyboard.press("ArrowRight")
    check(page.locator("#tab-intents").get_attribute("aria-selected")=="true","tab keyboard arrow navigation",log)
    page.locator("#tab-overview").click()
    if w<=420:
        check(page.locator(".tabs").evaluate("(e)=>getComputedStyle(e).position")=="static","mobile tab navigation does not occlude content",log)
    # Full screenshot is stable: reset viewport before capture.
    page.evaluate("window.scrollTo(0,0)")
    pic=out/(mode+".png")
    page.screenshot(path=str(pic),full_page=True,animations="disabled")
    report["screenshots"].append({"name":pic.name,"sha256":hashlib.sha256(pic.read_bytes()).hexdigest(),"viewport":[w,h]})
    if mode=="desktop":
        page.locator("#tab-monikers").click()
        moniker=out/"monikers-open.png"
        page.screenshot(path=str(moniker),full_page=True)
        report["screenshots"].append({"name":moniker.name,"sha256":hashlib.sha256(moniker.read_bytes()).hexdigest()})
    if mode=="mobile":
        page.locator("#tab-actions").click()
        actions=out/"actions-mobile.png"
        page.screenshot(path=str(actions),full_page=True)
        report["screenshots"].append({"name":actions.name,"sha256":hashlib.sha256(actions.read_bytes()).hexdigest()})

    # Remote partial/unavailable must not replace the source-bound immutable metrics.
    api.failure="ONE"
    page.locator("#refresh").click()
    page.locator('#feed-status').filter(has_text='LIVE_PARTIAL').wait_for(timeout=15000)
    check(page.locator("#metric-prompts").inner_text()=="UNKNOWN","partial API keeps null chat population",log)
    check(page.locator("#source-errors").is_visible(),"partial API shows explicit warning",log)
    api.failure="ALL"
    page.locator("#refresh").click()
    page.locator('#feed-status').filter(has_text='LIVE_UNAVAILABLE').wait_for(timeout=15000)
    check(page.locator("#metric-checks").inner_text()=="34/34","API outage never replaces matched native proof",log)
    check(page.locator("#remote-head").inner_text()==MAIN,"last independently retrieved browser main retained",log)
    outage=out/("api-failure-"+mode+".png")
    if mode=="desktop":
        page.screenshot(path=str(outage),full_page=True)
        report["screenshots"].append({"name":outage.name,"sha256":hashlib.sha256(outage.read_bytes()).hexdigest()})
    report["viewports"].append({"name":mode,"size":[w,h],"assertions":len(log),
                                "body_overflow_px":max(0,geometry["width"]-geometry["viewport"]),
                                "errors":errors,"checks":log,"mock_github_calls":len(api.calls)})
    page.close()


def run(source,out):
    out.mkdir(parents=True,exist_ok=True)
    snap=json.loads((source/"snapshot.json").read_text())
    http=ThreadingHTTPServer(("127.0.0.1",0),partial(Handler,directory=str(source)))
    thread=threading.Thread(target=http.serve_forever,daemon=True)
    thread.start()
    url="http://127.0.0.1:"+str(http.server_port)+"/index.html"
    receipt={"schema":"missioncontrol.live_lossless.browser_qa.v1",
             "evidence":"LOCAL_CHROMIUM_WITH_MOCKED_PUBLIC_GITHUB_RESPONSES",
             "source_snapshot_sha256":hashlib.sha256((source/"snapshot.json").read_bytes()).hexdigest(),
             "viewports":[],"screenshots":[],"hosted_public_url_verified":False,
             "github_remote_authenticated":False,"merge_admission":"HOLD","authority_transfer":False}
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True,args=["--no-sandbox"])
            try:
                for name,w,h in SIZES:
                    test_viewport(browser,url,name,w,h,snap,out,receipt)
                # Tampered static input must fail closed, never showing a fabricated number.
                page=browser.new_page()
                bad=dict(snap,authority_transfer=True)
                page.route("**/snapshot.json",lambda route:route.fulfill(status=200,content_type="application/json",body=json.dumps(bad)))
                page.route("https://api.github.com/**",lambda route:route.fulfill(status=503,body="blocked"))
                page.goto(url)
                page.locator('#feed-status').filter(has_text='SNAPSHOT_UNAVAILABLE').wait_for(timeout=15000)
                if page.locator("#metric-intents").inner_text()!="—":
                    raise AssertionError("invalid input promoted into KPI")
                page.screenshot(path=str(out/"rejected-fake-snapshot.png"),full_page=True)
                receipt["screenshots"].append({"name":"rejected-fake-snapshot.png",
                    "sha256":hashlib.sha256((out/"rejected-fake-snapshot.png").read_bytes()).hexdigest()})
                page.close()
                receipt["negative_tests"]={"forged_snapshot":"REJECTED","partial_api":"FAIL_CLOSED","unavailable_api":"NO_PROMOTION"}
            finally:
                browser.close()
    finally:
        http.shutdown();thread.join(timeout=5);http.server_close()
    receipt["checks_total"]=sum(x["assertions"] for x in receipt["viewports"])
    receipt["status"]="PASS"
    (out/"qa-receipt.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    return receipt


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--site",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    x=p.parse_args()
    report=run(x.site,x.out)
    print(json.dumps({"status":report["status"],"checks":report["checks_total"],
                      "screenshots":len(report["screenshots"]),"hosted_verified":False}))
