#!/usr/bin/env python3
"""Chromium no-network standalone M3 acceptance (not Pages/admission)."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

VIEWPORTS = ((1440,1000),(1280,800),(390,844))
def main(html: Path, out: Path) -> None:
    raw=html.read_text("utf-8")
    out.mkdir(parents=True,exist_ok=True)
    report={"schema":"missioncontrol.m3.offline_browser_qa.v1",
            "source_html_sha256":hashlib.sha256(raw.encode()).hexdigest(),
            "observed_at_utc":datetime.now(timezone.utc).isoformat(),
            "viewports":[],"network_requests":0,"authority":"OFFLINE_ONLY_NOT_HOSTED_PAGES",
            "status":"FAIL","errors":[]}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                for w,h in VIEWPORTS:
                    page=browser.new_page(viewport={"width":w,"height":h})
                    errors=[]
                    attempted=[]
                    page.on("pageerror",lambda exc:errors.append(str(exc)))
                    page.on("console",lambda msg:errors.append(msg.text) if msg.type=="error" else None)
                    page.route("**/*",lambda route:(attempted.append(route.request.url),route.abort()))
                    page.set_content(raw,wait_until="load")
                    assert page.locator("#repoCount").inner_text()=="6","repo count"
                    assert page.locator("#graphCount").inner_text()=="29 / 32","graph count"
                    assert page.locator("#todoCount").inner_text()=="1/12","historical TODO scope"
                    assert "OFFLINE PINNED" in page.locator("#liveTelemetry").inner_text(),"embedded telemetry did not load"
                    assert "P0: HOLD" in page.locator("#admission").inner_text(),"authority failure"
                    page.locator("#layer").select_option("repo")
                    page.locator("#search").fill("ABACUS")
                    assert page.locator("#nodeButtons button").count()>=1,"graph search"
                    page.locator("#nodeButtons button").first.click()
                    assert "ABACUS" in page.locator("#selected").inner_text(),"node inspector"
                    page.locator("#reload").click()
                    assert page.locator("#repoCount").inner_text()=="6","offline reload must stay embedded"
                    assert page.locator("#liveTelemetry").inner_text().startswith("OFFLINE PINNED"),"offline reload fetched source"
                    overflow=page.evaluate("document.documentElement.scrollWidth-window.innerWidth")
                    assert overflow<=1,f"body horizontal overflow: {overflow}"
                    assert not errors,"browser runtime errors: "+repr(errors)
                    assert not attempted,"offline viewer attempted network: "+repr(attempted)
                    links=page.locator("nav a[href]").evaluate_all("(a)=>a.map(x=>x.getAttribute('href'))")
                    assert all(link.startswith("https://github.com/") for link in links),"broken offline nav link"
                    file=out/("m3-standalone-"+str(w)+".png")
                    page.screenshot(path=str(file),full_page=True)
                    report["viewports"].append({"width":w,"height":h,
                        "zero_horizontal_overflow":True,"zero_errors":True,
                        "source_fetched":False,"screenshot":file.name,
                        "screenshot_sha256":hashlib.sha256(file.read_bytes()).hexdigest()})
                    page.close()
            finally:browser.close()
        report["status"]="PASS"
    except Exception as err:
        report["errors"].append(str(err))
        raise
    finally:
        (out/"offline_browser_qa_receipt.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("M3 standalone no-network chromium PASS 3/3 widths")
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--html",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    main(a.html,a.out)
