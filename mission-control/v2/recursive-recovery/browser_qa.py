#!/usr/bin/env python3
"""Exact-head Playwright HMI QA: data parity, 3 viewports, all tabs and controls."""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    raise SystemExit("Playwright required: python -m pip install playwright; python -m playwright install chromium")

ROOT = Path(__file__).resolve().parents[3]
HMI = ROOT / "mission-control/federation-atlas/landing/MISSION_CONTROL_RECURSIVE_MISSIONS_N12.html"
MODEL = Path(__file__).resolve().parent / "N12_HMI_SOURCE_PROJECTION.json"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts/mission-city-n12-qa"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure(x, why):
    if not x:
        raise AssertionError(why)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads(MODEL.read_text(encoding="utf-8"))
    ensure(reference["authority_transfer"] is False and reference["merge_admission"] == "HOLD",
           "projection authority mismatch")
    receipt = {"schema": "missioncontrol.n12.browser_qa_receipt.v1",
               "source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "model_sha256": sha(MODEL), "html_sha256": sha(HMI),
               "viewports": [], "checks": [], "authority_transfer": False,
               "engineering_approval": False, "admission": "HOLD"}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width, height, label in [(1440, 900, "desktop"), (1280, 800, "laptop"), (390, 844, "mobile")]:
                page = browser.new_page(viewport={"width": width, "height": height},
                                        device_scale_factor=1)
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(HMI.as_uri(), wait_until="load")
                ensure(page.locator("h1").count() == 1, label + ": missing title")
                ensure(page.locator('[data-tab]').count() == 6, label + ": expected 6 tabs")
                ensure(page.locator('[data-pane]').count() == 6, label + ": expected 6 panels")
                inline = page.evaluate("JSON.parse(document.querySelector('#model').textContent)")
                ensure(inline == reference, label + ": embedded vs source JSON mismatch")
                ensure(page.locator("#missions article.card").count() == 11, label + ": missing missions")
                page.locator('button[aria-label="View GM-IV mission brief"]').click()
                ensure("ACTIVE_8_OF_8" in page.locator("#missionBrief").inner_text(), label + ": no GM-IV brief")
                page.locator("#missionFilter").fill("GM-V")
                ensure(page.locator("#missions article.card").count() == 1,
                       label + ": mission filter wrong")
                page.locator("#missionFilter").fill("")
                page.locator('button[data-tab="crew"]').click()
                ensure(page.locator("#crewCards article.card").count() == 23,
                       label + ": crew count not 23")
                page.locator("#crewClass").select_option("C")
                ensure(page.locator("#crewCards article.card").count() == 8,
                       label + ": conceptual roster count not 8")
                page.locator("#crewClass").select_option("ALL")
                page.locator('button[data-tab="rex"]').click()
                ensure(page.locator("#rexEvents article.card").count() == 10,
                       label + ": REX 10 event requirement")
                page.locator("#rexFilter").select_option("GM-I")
                ensure(page.locator("#rexEvents article.card").count() >= 1,
                       label + ": mission-specific REX filter failed")
                page.locator('button[data-tab="lineage"]').click()
                ensure(page.locator("svg.diagram").count() == 1, label + ": DAG missing")
                page.locator('button[data-tab="native"]').click()
                ensure(page.locator("#nativeCards .card").count() == 3,
                       label + ": native source cards missing")
                page.locator('button[data-tab="waves"]').click()
                ensure("recuperation" in page.locator('[data-pane="waves"]').inner_text().lower(),
                       label + ": wave recuperation missing")
                overflow = page.evaluate("Math.max(0,document.documentElement.scrollWidth-window.innerWidth)")
                ensure(overflow <= 1, label + ": horizontal document overflow " + str(overflow))
                ensure(not errors, label + ": JS exceptions: " + ";".join(errors))
                page.locator('button[data-tab="missions"]').click()
                screenshot = OUT / (label + ".png")
                page.screenshot(path=str(screenshot), full_page=True)
                receipt["viewports"].append({"name": label, "width": width, "height": height,
                                             "horizontal_overflow_px": overflow, "js_errors": len(errors),
                                             "screenshot": screenshot.name,
                                             "screenshot_sha256": sha(screenshot),
                                             "interactive_controls": "PASS"})
                page.close()
        finally:
            browser.close()
    receipt["checks"] = ["INLINE_JSON_PARITY", "ALL_SIX_TABS", "MISSION_BRIEF",
                         "CREW_23", "CONCEPTUAL_8", "REX_10", "GRAPH",
                         "NATIVE_CARDS", "WAVE_RECUPERATION",
                         "ZERO_JS_ERRORS", "NO_GLOBAL_HORIZONTAL_OVERFLOW"]
    receipt["result"] = "PASS_BROWSER_VISUAL_AND_FUNCTIONAL_NOT_ENGINEERING_ACCEPTANCE"
    (OUT / "qa_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"result": receipt["result"], "viewports": len(receipt["viewports"]),
                      "checks": len(receipt["checks"]), "sha": receipt["source_sha"]}))


if __name__ == "__main__":
    main()
