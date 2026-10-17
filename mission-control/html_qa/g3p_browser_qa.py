#!/usr/bin/env python3
"""G3P responsive Playwright acceptance against exact HTML with controlled source fixtures.

This proves browser interactions and visual geometry, not native GitHub CI health,
source ancestry, successful deployment or engineering/merge admission.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORTS = (("desktop", 1440, 1000), ("laptop", 1280, 800), ("mobile", 390, 844))
WAVE_NAMES = ("CBD_GOLDEN_GRAPH_N3_20261017.json",
              "CBD_GOLDEN_GRAPH_N6_20261017.json",
              "CBD_GOLDEN_GRAPH_N9_20261017.json",
              "G3A_N10_N12_LEDGER_20261017.json")


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(value: bool, message: str, passes: list[str]):
    if not value:
        raise AssertionError(message)
    passes.append(message)


def mock_html(source: str, manifest: dict, ledgers: dict) -> str:
    """Inject same-shape read-only HTTP responses before the production script."""
    source_payload = json.dumps({"manifest": manifest, "ledgers": ledgers},
                                ensure_ascii=True).replace("</", "<\\/")
    init = """<script>
window.__qa={requests:[],failFile:null,forgedFile:null,manifestInvalid:false,scheduled:[]};
const __fixtures=__PAYLOAD__;
const __nativeSetInterval=window.setInterval.bind(window);
window.setInterval=function(callback,delay){window.__qa.scheduled.push(delay);return __nativeSetInterval(callback,delay)};
window.fetch=async function(url){
 const u=new URL(String(url),document.baseURI);
 const filename=u.pathname.split('/').pop();
 window.__qa.requests.push(filename);
 if(window.__qa.failFile===filename)return new Response('Unavailable',{status:503});
 if(filename==='G3P_LIVE_SOURCES_v1.json'){
  const m=structuredClone(__fixtures.manifest);
  if(window.__qa.manifestInvalid)m.authority_transfer=true;
  return new Response(JSON.stringify(m),{status:200,headers:{'content-type':'application/json'}});
 }
 const item=__fixtures.ledgers[filename];
 if(!item)return new Response('Unlisted file',{status:404});
 const receipt=structuredClone(item);
 if(window.__qa.forgedFile===filename)receipt.receipts[0].merge_admission='PASS';
 return new Response(JSON.stringify(receipt),{status:200,headers:{'content-type':'application/json'}});
};
</script>""".replace("__PAYLOAD__", source_payload)
    if "<script>" not in source:
        raise AssertionError("Production HTML has no inline application script")
    return source.replace("<head>", '<head><base href="https://gbogeb.github.io/pipeline-automation-hub/g3p/">', 1).replace("<script>", init + "<script>", 1)


def viewport_overlaps(page):
    ids = ("reload", "interval", "limit", "updated")
    entries = []
    for ident in ids:
        selector = page.locator("#" + ident)
        if not selector.is_visible():
            continue
        box = selector.bounding_box()
        if box:
            entries.append((ident, box))
    bad = []
    for i, (name_a, a) in enumerate(entries):
        for name_b, b in entries[i+1:]:
            overlap_x = max(0, min(a["x"]+a["width"], b["x"]+b["width"]) - max(a["x"], b["x"]))
            overlap_y = max(0, min(a["y"]+a["height"], b["y"]+b["height"]) - max(a["y"], b["y"]))
            if overlap_x*overlap_y > 6:
                bad.append((name_a, name_b, round(overlap_x*overlap_y, 2)))
    return bad


def inspect_links(page):
    links = page.locator("a")
    found = []
    for element in links.all():
        if not element.is_visible():
            continue
        href = element.get_attribute("href")
        target = element.get_attribute("target")
        rel = element.get_attribute("rel") or ""
        if not href:
            raise AssertionError("Visible link without href")
        if href.lower().startswith(("javascript:", "data:", "//")):
            raise AssertionError("Unsafe href " + href)
        if target == "_blank" and not {"noopener", "noreferrer"} <= set(rel.split()):
            raise AssertionError("Unsafe new-tab link " + href)
        found.append(href)
    return found


def exercise(page, label, w, h, output: Path, evidence: dict):
    checks = []
    page.wait_for_function("document.getElementById('pulses').textContent==='12'", timeout=12000)
    check(page.locator("#waves").inner_text() == "4", "four source waves", checks)
    check(page.locator("#edges").inner_text() == "11", "11 edges", checks)
    check(page.locator("#gaps").inner_text() == "3", "three explicit ancestry gaps", checks)
    check(page.locator("#table tr").count() == 12, "12 ledger rows", checks)
    check(page.locator("#graph g[role='button']").count() == 12, "12 accessible SVG pulse nodes", checks)
    check(page.locator("#graph line[stroke-dasharray='6 5']").count() == 3,
          "three cross-wave dashed edges", checks)
    check(page.locator("#tests").inner_text() == "154",
          "N12 local count 154, no native promotion", checks)
    check("HOLD" in page.locator("main").inner_text(), "merge admission HOLD", checks)
    check(page.locator("#status").inner_text().startswith("STRUCTURAL ONLY"),
          "live source is not independent authority", checks)

    widths = page.evaluate("({body:document.documentElement.scrollWidth, viewport:innerWidth})")
    check(widths["body"] <= widths["viewport"] + 2,
          "no body viewport horizontal overflow", checks)
    overlap = viewport_overlaps(page)
    check(not overlap, "toolbar elements do not overlap", checks)
    check(page.locator("h1").bounding_box()["width"] > 120, "heading readable", checks)

    links = inspect_links(page)
    check(any("/issues/604" in x for x in links), "Mission Control issue link", checks)
    check(any("/pull/632" in x for x in links), "PR review link", checks)
    check(any("G3P_LIVE_SOURCES_v1.json" in x for x in links), "manifest link", checks)

    # Trigger both pointer and keyboard graph interactions.
    page.locator("#graph g[role='button']").nth(5).click()
    check("N+6" in page.locator("#details").inner_text(), "SVG pointer selection", checks)
    source_link = page.locator("#nodeSource")
    check(source_link.is_visible() and source_link.get_attribute("href").startswith("https://github.com/"),
          "selected graph node binds a safe clickable source URL", checks)
    page.locator("#graph g[role='button']").nth(2).focus()
    page.keyboard.press("Enter")
    check("N+3" in page.locator("#details").inner_text(), "SVG keyboard selection", checks)

    for target, expected in (("6", 6), ("9", 9), ("12", 12)):
        page.locator("#limit").select_option(target)
        check(page.locator("#graph g[role='button']").count() == expected,
              "timeline selector N+"+target, checks)

    # Exercise every visible navigation anchor without leaving a QA browser.
    for anchor in page.locator("a:visible").all():
        target = anchor.get_attribute("href")
        page.evaluate("""a => {
          window.__qa.linkClicks=window.__qa.linkClicks||[];
          a.addEventListener('click', function(ev){ev.preventDefault();window.__qa.linkClicks.push(a.getAttribute('href'))},{once:true})
        }""", anchor.element_handle())
        anchor.click()
    check(page.evaluate("window.__qa.linkClicks.length") == len(inspect_links(page)),
          "all visible links respond to click", checks)

    count = page.evaluate("window.__qa.requests.length")
    page.locator("#reload").click()
    page.wait_for_function("n => window.__qa.requests.length >= n + 5", arg=count, timeout=8000)
    check(page.locator("#pulses").inner_text() == "12", "manual reload retains 12 valid pulses", checks)

    page.locator("#interval").select_option("60")
    check(page.evaluate("window.__qa.scheduled.at(-1)") == 60000,
          "1-minute periodic refresh scheduled", checks)
    page.locator("#interval").select_option("900")
    check(page.evaluate("window.__qa.scheduled.at(-1)") == 900000,
          "15-minute periodic refresh scheduled", checks)
    page.locator("#interval").select_option("0")
    check(page.locator("#interval").input_value() == "0", "manual-only refresh option", checks)

    screenshot = output / (label + ".png")
    page.screenshot(path=str(screenshot), full_page=True, animations="disabled")
    evidence["screenshots"].append({"viewport": label, "path": screenshot.name,
                                    "sha256": file_sha(screenshot),
                                    "width": w, "height": h})
    evidence["viewports"].append({"label": label, "size": [w, h], "checks": checks,
                                   "control_overlap": overlap, "link_count": len(links),
                                   "body_overflow_px": max(0, widths["body"]-widths["viewport"])})
    return len(checks)


def run(html_path: Path, manifest_path: Path, fixture_dir: Path, out: Path,
        executable: str | None):
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ledgers = {name:json.loads((fixture_dir/name).read_text(encoding="utf-8"))
               for name in WAVE_NAMES}
    assert manifest["schema"] == "missioncontrol.g3p.live_sources.v1"
    assert len(manifest["waves"]) == 4
    assert all(v["mission"]["repo"] == manifest["repository"] for v in ledgers.values())
    source = html_path.read_text(encoding="utf-8")
    page_html = mock_html(source, manifest, ledgers)
    report = {
        "schema":"missioncontrol.html_quality.playwright.v1",
        "scope":"G3P_LIVE_LEDGER",
        "evidence_level":"LOCAL_OR_NATIVE_EXACT_HEAD_BROWSER_QA_NOT_HOSTED_PROOF",
        "browser_fetch":"CONTROLLED_REAL_LEDGER_FIXTURES_NO_LIVE_NETWORK",
        "html_sha256":file_sha(html_path),
        "manifest_sha256":file_sha(manifest_path),
        "source_ledger_sha256":{n:file_sha(fixture_dir/n) for n in WAVE_NAMES},
        "native_source_head_claim":os.getenv("GITHUB_SHA","UNKNOWN"),
        "viewports":[], "screenshots":[], "errors":[], "checks_total":0,
        "merge_admission":"HOLD", "authority_transfer":False, "hosted_http_verified":False,
    }
    with sync_playwright() as playwright:
        engine = playwright.chromium
        browser = engine.launch(headless=True,
                                executable_path=executable if executable else None,
                                args=["--no-sandbox"])
        try:
            for label, w, h in VIEWPORTS:
                page = browser.new_page(viewport={"width":w, "height":h},
                                        device_scale_factor=1)
                errors = []
                page.on("pageerror", lambda err:errors.append("page:"+str(err)))
                page.on("console", lambda msg:errors.append("console:"+msg.text) if msg.type=="error" else None)
                page.set_content(page_html, wait_until="load", timeout=16000)
                report["checks_total"] += exercise(page,label,w,h,out,report)
                if errors:
                    raise AssertionError(label + ": JavaScript/console errors " + repr(errors))
                page.close()
            # Fault-injection gate: partial fetch, forged receipt, then invalid manifest.
            negative = browser.new_page(viewport={"width":1280,"height":800})
            negative.set_content(page_html, wait_until="load")
            negative.wait_for_function("document.getElementById('pulses').textContent==='12'")
            negative.evaluate("window.__qa.failFile='CBD_GOLDEN_GRAPH_N9_20261017.json'")
            negative.locator("#reload").click()
            negative.wait_for_function("document.getElementById('status').textContent.includes('PARTIAL')")
            check(negative.locator("#pulses").inner_text()=="6", "missing wave fails to N6 prefix",
                  report.setdefault("negative_checks",[]))
            check(negative.locator("#gaps").inner_text()=="1", "no invented downstream ancestry",
                  report["negative_checks"])
            negative.screenshot(path=str(out/"missing-source.png"), full_page=True)
            negative.evaluate("window.__qa.failFile=null;window.__qa.forgedFile='CBD_GOLDEN_GRAPH_N6_20261017.json'")
            negative.locator("#reload").click()
            negative.wait_for_function("document.getElementById('pulses').textContent==='3'")
            check("PARTIAL" in negative.locator("#status").inner_text(), "forged PASS rejected",
                  report["negative_checks"])
            negative.evaluate("window.__qa.forgedFile=null;window.__qa.manifestInvalid=true")
            negative.locator("#reload").click()
            negative.wait_for_function("document.getElementById('status').textContent.includes('FAILED/STALE')")
            check(negative.locator("#pulses").inner_text()=="3", "invalid manifest does not promote state",
                  report["negative_checks"])
            negative.screenshot(path=str(out/"forged-authority.png"), full_page=True)
            report["checks_total"] += len(report["negative_checks"])
            negative.close()
        finally:
            browser.close()
    report["status"] = "PASS" if not report["errors"] else "FAIL"
    (out/"qa-receipt.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--html",type=Path,required=True)
    ap.add_argument("--manifest",type=Path,required=True)
    ap.add_argument("--fixtures",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--executable",default=os.getenv("CHROMIUM_EXECUTABLE_PATH"))
    args=ap.parse_args()
    report=run(args.html,args.manifest,args.fixtures,args.out,args.executable)
    print(json.dumps({"status":report["status"],
                      "checks":report["checks_total"],
                      "viewports":len(report["viewports"]),
                      "screenshot_count":len(report["screenshots"])+2,
                      "evidence_level":report["evidence_level"],
                      "hosted_http_verified":False},sort_keys=True))


if __name__=="__main__":
    main()
