#!/usr/bin/env python3
"""Native Chromium QA for W2's offline Plotly inlays and Pages custody."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

SCREENS=((1440,1000),(1280,800),(390,844))
ALLOW=("evidence.html","evidence.json","evidence-manifest.json")


def require(ok,reason):
    if not ok:
        raise AssertionError("MC_W2_BROWSER_QA_FAIL:" + reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(source, portal, expected_sha):
    source,portal=Path(source),Path(portal)
    d=json.loads((source/"evidence.json").read_text(encoding="utf-8"))
    manifest=json.loads((source/"evidence-manifest.json").read_text(encoding="utf-8"))
    root_manifest=json.loads((portal.parent/"site-manifest.json").read_text(encoding="utf-8"))
    require(d["source_head_sha"]==expected_sha
            and manifest["source_sha"]==expected_sha
            and root_manifest["source_git_sha"]==expected_sha,"exact source identity")
    require(manifest["merge_admission"]=="HOLD"
            and manifest["authority_transfer"] is False
            and manifest["security_waiver"] is False
            and manifest["gg_math_kernel_duplicated"] is False,"method governance")
    require(tuple(sorted(manifest["member_sha256"]))==("evidence.html","evidence.json"),
            "artifact member census")
    for name in ALLOW:
        require((portal/name).exists(),"Pages member missing "+name)
        require(sha(portal/name)==sha(source/name),"source-Pages mismatch "+name)
        require(root_manifest["public_files_sha256"]["mission-rebuild/"+name] ==
                sha(portal/name),"site-manifest hash mismatch "+name)
    for name,digest in manifest["member_sha256"].items():
        require(sha(source/name)==digest,"source manifest mismatch "+name)
    require(d["fleet"]["capacity_slots"] is None and
            d["unknown_burndown"]["coverage"]["covered_statements"] is None,
            "unknown promoted to measured")
    return d


def check(source, portal, expected_sha, screenshots):
    d=verify(source,portal,expected_sha)
    screenshots=Path(screenshots)
    screenshots.mkdir(parents=True,exist_ok=True)
    rows=[]
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        for width,height in SCREENS:
            page=browser.new_page(viewport={"width":width,"height":height},
                                  device_scale_factor=1)
            errors=[]
            page.on("console",lambda msg:errors.append("CONSOLE:"+msg.text) if msg.type=="error" else None)
            page.on("pageerror",lambda err:errors.append("PAGE:"+str(err)))
            page.goto((Path(portal)/"evidence.html").resolve().as_uri(),
                      wait_until="load",timeout=30000)
            page.locator(".inlay .js-plotly-plot").first.wait_for(timeout=30000)
            require(page.title()=="MISSION CONTROL W2 · gg_MATH evidence","title")
            require(page.locator("h1").count()==1,"primary heading")
            require(page.locator(".inlay .js-plotly-plot").count()==4,"four proper Plotly inlays")
            require(page.locator(".card[data-group]:visible").count()==4,"initial four cards")
            # A chart can spill over a sibling card while document scrollWidth
            # remains unchanged: test plotted geometry, not body overflow alone.
            page.wait_for_function("""() => [...document.querySelectorAll('.inlay .js-plotly-plot')]
               .length === 4 && [...document.querySelectorAll('.inlay .js-plotly-plot')]
               .every(p => p._fullLayout && p._fullLayout.width <=
               p.getBoundingClientRect().width + 1)""", timeout=15000)
            card_widths=page.evaluate("""() => [...document.querySelectorAll('.inlay .js-plotly-plot')]
               .map(p => ({plot_px:p._fullLayout.width,
                           card_px:p.getBoundingClientRect().width}))""")
            require(all(p["plot_px"]<=p["card_px"]+1 for p in card_widths),
                    "sibling card chart overflow")
            page.locator('[data-filter="statistics"]').click()
            require(page.locator(".card[data-group]:visible").count()==1,"method filter")
            page.locator('[data-filter="all"]').click()
            require(page.locator(".card[data-group]:visible").count()==4,"all filter reset")
            page.locator('[data-expand="queue"]').click()
            require(page.locator("#detail").evaluate("(e)=>e.open") is True,"Plotly modal open")
            page.locator("#expanded.js-plotly-plot").wait_for(timeout=10000)
            page.locator("#closeDialog").click()
            require(page.locator("#detail").evaluate("(e)=>e.open") is False,"modal closes")
            overflow=page.evaluate("document.documentElement.scrollWidth-window.innerWidth")
            require(overflow<=1,"body horizontal overflow at "+str(width))
            require(len(errors)==0,"browser errors: "+" | ".join(errors))
            img=screenshots/("w2-%dx%d.png"%(width,height))
            page.screenshot(path=str(img),full_page=True)
            require(img.stat().st_size>10000,"empty screenshot")
            rows.append({"viewport":str(width)+"x"+str(height),
                         "browser_errors":0,"body_overflow_px":max(0,overflow),
                         "plotly_inlays":4,"plotly_chart_geometry_px":card_widths,
                         "screenshot_bytes":img.stat().st_size,
                         "screenshot_sha256":sha(img)})
            page.close()
        browser.close()
    return {"schema":"missioncontrol.makeover.w2_browser_qa.v1",
            "source_sha":expected_sha,"evidence_class":d["evidence_class"],
            "viewport_receipts":rows,
            "checks":{"static_source_parity":"PASS","interactive_Plotly":"PASS",
                      "modal_and_filters":"PASS","responsive_overflow":"PASS",
                      "no_console_or_page_errors":"PASS"},
            "merge_admission":"HOLD","security_waiver":False,
            "actual_worker_hours":None,"six_sigma_attested":False}


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--portal",required=True)
    p.add_argument("--sha",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--screens",required=True)
    a=p.parse_args()
    result=check(a.source,a.portal,a.sha,a.screens)
    Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"W2_PLAYWRIGHT":"PASS","viewports":len(result["viewport_receipts"]),
                      "inlays_per_viewport":4,"sha":a.sha}))
