#!/usr/bin/env python3
"""Source-parity and three-viewport Chromium QA of MACH-II Mission City.
Proof stays browser/local to the pinned checked-out head; never dispatches.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError as e:
    raise SystemExit("Install Python playwright and chromium on QA runner") from e

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
HTML = ROOT / "mission-control/federation-atlas/landing/MISSION_CONTROL_MACHII_N13.html"
MANIFEST = HERE / "MACHII_MISSION_MANIFEST.json"
GRAPH = HERE / "MACHII_MYCELIUM_GRAPH.json"


def sha(f: Path) -> str:
    return hashlib.sha256(f.read_bytes()).hexdigest()


def must(cond: bool, name: str):
    if not cond:
        raise AssertionError(name)


def main() -> None:
    out=Path(sys.argv[1]) if len(sys.argv)>1 else Path("/tmp/mc-mach2-browser")
    out.mkdir(parents=True,exist_ok=True)
    m=json.loads(MANIFEST.read_text(encoding="utf-8"))
    g=json.loads(GRAPH.read_text(encoding="utf-8"))
    must(m["authority_transfer"] is False and g["dispatch_authorized"] is False,"authority")
    receipt={"schema":"missioncontrol.mach2.browser_qa.v1",
             "head_sha":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
             "html_sha256":sha(HTML),"manifest_sha256":sha(MANIFEST),
             "graph_sha256":sha(GRAPH),"viewports":[],"checks":[],
             "authority_transfer":False,"engineering_acceptance":False}
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        try:
            for label,w,h in (("desktop",1440,950),("laptop",1280,800),("mobile",390,844)):
                page=browser.new_page(viewport={"width":w,"height":h},device_scale_factor=1)
                errors=[]
                page.on("pageerror",lambda e: errors.append(str(e)))
                page.goto(HTML.as_uri(),wait_until="load")
                must(page.locator("[data-tab]").count()==6,"6 tabs "+label)
                must(page.locator("[data-pane]").count()==6,"6 panels "+label)
                inline=page.evaluate("JSON.parse(document.querySelector('#model').textContent)")
                must(inline["missions"]==m["missions"],"manifest projection drift "+label)
                must(inline["graph"]==g["projection_receipt"],"typed graph projection drift "+label)
                must(page.locator("#missionCards .card").count()==5,"GM cards "+label)
                page.locator('button[aria-label="Read MACH-II instructions"]').count()
                page.locator('button').filter(has_text="Read MACH-II instructions").first.click()
                must("GM-I" in page.locator("#missionDetail").inner_text(),"mission brief "+label)
                page.locator("#missionSearch").fill("GM-V")
                must(page.locator("#missionCards .card").count()==1,"GM-V filter "+label)
                page.locator("#missionSearch").fill("")
                page.locator('button[data-tab="mip"]').click()
                must(page.locator("#mipCards .card").count()==3,"MIP axes "+label)
                page.locator("#mipSelect").select_option("GM-IV")
                must("GM-IV" in page.locator("#mipSelect").input_value(),"select MIP "+label)
                page.locator('button[data-tab="graphs"]').click()
                page.locator("#graphDAG").click()
                must(not page.locator("#execGraph").evaluate("e=>e.classList.contains('hidden')"),"DAG view "+label)
                page.locator("#graphCycle").click()
                must(not page.locator("#cyclicGraph").evaluate("e=>e.classList.contains('hidden')"),"cycle view "+label)
                page.locator('button[data-tab="stats"]').click()
                page.locator("#nTrials").fill("1000000")
                page.locator("#nDefects").fill("0")
                must("DPMO" in page.locator("#dpmoValue").inner_text(),"sigma output "+label)
                must("not certified" in page.locator("#sigmaVerdict").inner_text().lower(),"sigma hold "+label)
                page.locator('button[data-tab="hepak"]').click()
                must(page.locator('a[href*="/pull/1952"]').count()>=1,"QPS owner link "+label)
                page.locator('button[data-tab="control"]').click()
                must("SIPOC" in page.locator('[data-pane="control"] h2').inner_text(),"SIPOC "+label)
                overflow=page.evaluate("Math.max(0,document.documentElement.scrollWidth-innerWidth)")
                must(overflow<=1,"horizontal overflow "+label+":"+str(overflow))
                must(not errors,"JS exceptions "+label+":"+str(errors))
                page.locator('button[data-tab="missions"]').click()
                png=out/(label+".png")
                page.screenshot(path=str(png),full_page=True)
                receipt["viewports"].append({"label":label,"size":[w,h],"overflow":overflow,
                                              "js_errors":len(errors),"png":png.name,
                                              "png_sha256":sha(png),"interactive":"PASS"})
                page.close()
        finally:
            browser.close()
    receipt["checks"]=["SOURCE_JSON_PARITY","MYCELIUM_GRAPH_PARITY","SIX_TABS","GM_FIVE",
                       "MIP_THREE_PER_MISSION","CYCLIC_AND_DAG_MODES",
                       "SIX_SIGMA_SCENARIO_NO_CERTIFICATION","HEPAK_QPS_LINK",
                       "SIPOC","NO_JS_ERRORS","NO_GLOBAL_OVERFLOW"]
    receipt["result"]="PASS_BROWSER_VISUAL_NOT_ENGINEERING_ADMISSION"
    (out/"qa_receipt.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"result":receipt["result"],"viewport_count":len(receipt["viewports"]),
                      "checks":len(receipt["checks"])}))


if __name__=="__main__":
    main()
