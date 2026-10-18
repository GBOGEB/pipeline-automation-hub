#!/usr/bin/env python3
"""Three-viewport Playwright DoV for existing-publisher Global Convergence Hub."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

VIEWPORTS = (("desktop",1440,1000),("laptop",1280,800),("mobile",390,844))


def run(html_path, out_dir, head):
    from playwright.sync_api import sync_playwright
    html_path, out_dir = Path(html_path).resolve(), Path(out_dir)
    if not html_path.is_file() or len(head) != 40:
        raise ValueError("missing hub file or exact presentation head")
    out_dir.mkdir(parents=True,exist_ok=True)
    outputs=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
        for name,w,h in VIEWPORTS:
            page=browser.new_page(viewport={"width":w,"height":h},device_scale_factor=1)
            errors=[]
            page.on("pageerror",lambda exc:errors.append("PAGE:"+str(exc)))
            page.on("console",lambda msg:errors.append("CONSOLE:"+msg.text)
                    if msg.type=="error" else None)
            page.goto(html_path.as_uri(),wait_until="load",timeout=60000)
            page.wait_for_selector("#events-body tr",timeout=15000)
            assert page.title()=="CODE PURPLE | Global DoV Convergence Hub"
            assert page.locator("#head-sha").inner_text()==head
            baseline=page.locator("#events-body tr").count()
            assert baseline>=8,baseline
            assert "6/42" in page.locator("#kpi-grid").inner_text()
            assert "0/1" in page.locator("#kpi-grid").inner_text()
            assert "M1 PARTIAL" in page.locator("#kpi-grid").inner_text()
            assert "UNKNOWN" in page.locator("#kpi-grid").inner_text()
            page.locator("#family-filter").select_option("coverage")
            filtered=page.locator("#events-body tr").count()
            assert 1<=filtered<baseline,(filtered,baseline)
            page.locator("#case-search").fill("MATH-G3P-W32")
            assert page.locator("#events-body tr").count()==1
            assert "NONTERMINAL" in page.locator("#events-body").inner_text()
            page.locator("#clear-filters").click()
            assert page.locator("#events-body tr").count()==baseline
            geometry=page.evaluate("""() => ({
              width:document.documentElement.scrollWidth,
              inner:window.innerWidth,
              broken:Array.from(document.images).filter(i=>!i.complete||i.naturalWidth===0).length
            })""")
            assert geometry["width"]<=geometry["inner"]+1,geometry
            assert geometry["broken"]==0,geometry
            # No external network request is needed for the frozen first render.
            # Intercept GitHub GETs to confirm a status overlay cannot change DoV KPIs.
            before=page.locator("#kpi-grid").inner_text()
            def intercept(route):
                u=route.request.url
                if "/pulls/" in u:
                    payload={"head":{"sha":"b"*40},"state":"open","draft":True}
                else:
                    payload={"status":"completed","conclusion":"failure",
                             "run_attempt":1,"head_sha":"a"*40}
                route.fulfill(status=200,content_type="application/json",
                              body=json.dumps(payload))
            page.route("https://api.github.com/**",intercept)
            page.locator("#github-refresh").click()
            page.locator("#live-results .panel").first.wait_for(timeout=15000)
            page.wait_for_function("() => !document.getElementById('github-refresh').disabled",
                                   timeout=15000)
            assert page.locator("#kpi-grid").inner_text()==before
            assert "LIVE UNVERIFIED" in page.locator("#live-results").inner_text()
            assert "MISMATCH" in page.locator("#live-results").inner_text()
            page.locator("#reset-overlay").click()
            assert page.locator("#live-results .panel").count()==0
            assert page.locator("#kpi-grid").inner_text()==before
            page.screenshot(path=str(out_dir/(name+".png")),full_page=True,timeout=60000)
            assert not errors,errors
            outputs.append({"viewport":name,"width":w,"height":h,
                            "rendered_ledger_rows":baseline,
                            "filtered_coverage_rows":filtered,
                            "page_errors":len(errors),"broken_images":0,
                            "horizontal_overflow":0,
                            "mocked_github_overlay":"PASS_NO_PROOF_PROMOTION",
                            "screenshot":name+".png"})
            page.close()
        browser.close()
    report={"schema":"codepurple.convergence_hub.browser_qa.v1",
            "presentation_head":head,
            "html_sha256":hashlib.sha256(html_path.read_bytes()).hexdigest(),
            "source":"LOCAL_OR_EXACT_HEAD_RUNNER_ONLY",
            "authority_transfer":False,"merge_admission":"HOLD",
            "browser_get_native_attestation":False,
            "checks":outputs}
    (out_dir/"qa_receipt.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--html",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--head",required=True)
    a=p.parse_args()
    print(json.dumps(run(a.html,a.out,a.head),sort_keys=True))


if __name__=="__main__":
    main()
