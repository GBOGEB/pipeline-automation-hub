#!/usr/bin/env python3
"""M3 source-bound browser QA. Visual proof only, never merge admission."""
from __future__ import annotations
import argparse
import hashlib
import json
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
SCREEN = [(1440, 1000), (1280, 800), (390, 844)]
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

def check(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    handler=lambda *args, **kwargs: Quiet(*args, directory=str(ROOT), **kwargs)
    server=ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread=threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url=f"http://127.0.0.1:{server.server_port}/docs/mission-control/m3/index.html"
    result={"schema":"missioncontrol.m3.browser_qa.v1",
            "observed_at_utc":datetime.now(timezone.utc).isoformat(),
            "source_sha":None,"viewports":[],"errors":[],
            "status":"FAIL","authority":"PRESENTATION_ONLY_NOT_GOVERNED_ADMISSION"}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                for width,height in SCREEN:
                    page=browser.new_page(viewport={"width":width,"height":height}, device_scale_factor=1)
                    errs=[]
                    page.on("pageerror",lambda ex:errs.append("PAGE: "+str(ex)))
                    page.on("console",lambda msg:errs.append("CONSOLE: "+msg.text) if msg.type=="error" else None)
                    page.goto(url,wait_until="networkidle",timeout=30000)
                    page.locator("#repoCount").wait_for(state="visible")
                    assert page.locator("#repoCount").inner_text()=="6", "repository count"
                    assert page.locator("#graphCount").inner_text()=="29 / 32", "node/edge count"
                    assert page.locator("#todoCount").inner_text()=="1/12", "TODO guard"
                    assert page.locator("#admission").inner_text().startswith("P0: HOLD"),"HOLD guard"
                    page.locator("#layer").select_option("repo")
                    page.locator("#search").fill("ABACUS")
                    assert page.locator("#nodeButtons button").count()>=1,"graph filter missing"
                    page.locator("#nodeButtons button").first.click()
                    assert "ABACUS" in page.locator("#selected").inner_text(),"inspector not responding"
                    page.locator("#search").fill("")
                    page.locator("#layer").select_option("orchestration")
                    page.locator("#reload").click()
                    assert page.locator("#repoCount").inner_text()=="6","reload changed source unexpectedly"
                    assert "flowchart LR" in page.locator("#mermaid").text_content(),"Mermaid unavailable"
                    overflow=page.evaluate("({scroll:document.documentElement.scrollWidth,viewport:window.innerWidth})")
                    assert overflow["scroll"]<=overflow["viewport"]+1,f"horizontal document overflow: {overflow}"
                    broken=[]
                    for href in page.locator("a[href]").evaluate_all("(els)=>els.map(a=>a.getAttribute('href'))"):
                        if href.startswith(("https://","http://","#","mailto:")):
                            continue
                        target=(ROOT/"docs/mission-control/m3"/unquote(urlparse(href).path)).resolve()
                        if not target.is_relative_to(ROOT) or not target.is_file():
                            broken.append(href)
                    assert not broken,"broken internal anchors: "+repr(broken)
                    images=page.locator("img").evaluate_all("(els)=>els.filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.src)")
                    assert not images,"broken images"
                    assert not errs,"console/page errors: "+repr(errs)
                    name=f"m3-{width}x{height}.png"
                    screenshot=out/name
                    page.screenshot(path=str(screenshot),full_page=True)
                    result["viewports"].append({"width":width,"height":height,
                        "horizontal_overflow":False,"broken_links":0,"broken_images":0,
                        "page_or_console_errors":0,"screenshot":name,
                        "screenshot_sha256":hashlib.sha256(screenshot.read_bytes()).hexdigest()})
                    page.close()
                # Isolated positive/negative overlay fixtures: no remote launch, no source mutation.
                state_bytes=(ROOT/"docs/mission-control/m3/state.json").read_bytes()
                sample={"schema":"missioncontrol.m3.telemetry_observation.v1",
                    "mode":"FIXTURE","observed_at_utc":"2026-10-17T18:48:12Z",
                    "source_identity":{"m3_state_sha256":hashlib.sha256(state_bytes).hexdigest()},
                    "authority":{"merge_admission":"HOLD","remote_mutation":False,
                        "security_waiver":False,"correctly_governed_main_merge_verified":False},
                    "freshness":{"census_age_hours":12,"census_stale_by_24h":False},
                    "run_observations":[{"repository":"GBOGEB/ABACUS","pr":2162,"conclusion":"failure",
                        "observed_jobs":13,"source_sha":"e053a4898fc74018b83092b0d2f8af2f4a909eb0",
                        "run_id":39056877380,"run_attempt":1,
                        "url":"https://github.com/GBOGEB/ABACUS/actions/runs/39056877380"}],
                    "crosswalk":[{"m3_id":"ABACUS"}]}
                browser_page=browser.new_page(viewport={"width":1280,"height":800})
                browser_page.route("**/telemetry.json?view=*",lambda route:
                    route.fulfill(status=200,content_type="application/json",body=json.dumps(sample)))
                browser_page.goto(url,wait_until="networkidle")
                assert "Observation:" in browser_page.locator("#liveTelemetry").inner_text(), "valid overlay withheld"
                result["overlay_positive_fixture"]=True
                browser_page.close()
                sample["source_identity"]["m3_state_sha256"]="0"*64
                bad_page=browser.new_page(viewport={"width":1280,"height":800})
                bad_page.route("**/telemetry.json?view=*",lambda route:
                    route.fulfill(status=200,content_type="application/json",body=json.dumps(sample)))
                bad_page.goto(url,wait_until="networkidle")
                assert "WITHHELD" in bad_page.locator("#liveTelemetry").inner_text(), "forged digest accepted"
                result["forged_overlay_rejected"]=True
                bad_page.close()
            finally:
                browser.close()
        result["status"]="PASS"
    except Exception as e:
        result["errors"].append(repr(e))
        raise
    finally:
        server.shutdown()
        (out/"browser_qa_receipt.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=Path("out/m3/browser"))
    args=p.parse_args()
    report=check(args.out)
    print(json.dumps({"status":report["status"],"viewports":len(report["viewports"]),"errors":report["errors"]}))
