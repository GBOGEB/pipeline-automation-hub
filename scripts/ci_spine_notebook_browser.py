#!/usr/bin/env python3
"""Real Chromium QA for the read-only CI Spine provenance notebook.

Runs offline via file:// and rejects network activity, JS errors, broken
deep-links, body overflow, missing source lenses, and false PDF authority.
Not a deployment, PDF geometry test, merge acceptance or fleet metric owner.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs/ci-spine/notebook.html"
OUT = ROOT / "qa/ci_spine"
SIZES = ((1440, 1000), (1280, 800), (390, 844))
SCHEMA = "ci-spine.provenance-notebook.browser-qa.v1"


def assert_that(condition, message):
    if not condition:
        raise AssertionError("CI_SPINE_BROWSER_FIRST_RED:" + message)


def verify(page, width, height, screenshot):
    page.set_viewport_size({"width": width, "height": height})
    page.goto(PAGE.resolve().as_uri(), wait_until="load")
    page.locator("#bundles li").first.wait_for(state="visible")
    assert_that(page.locator("#bundles li").count() == 10, "BUNDLE_COUNT")
    assert_that(page.locator('#inspector-id').inner_text() == "B07", "DEFAULT_BUNDLE")
    assert_that(page.locator('.gnode').count() == 10, "SVG_POPULATION")
    assert_that(page.locator('.edge').count() == 17, "EDGE_POPULATION")
    assert_that(page.locator("#scale").inner_text() == "100%", "ZOOM_BASELINE")
    page.locator("#zoom-in").click()
    assert_that(page.locator("#scale").inner_text() == "120%", "ZOOM_IN")
    page.locator("#reset").click()
    assert_that(page.locator("#scale").inner_text() == "100%", "ZOOM_RESET")
    page.locator("#search").fill("B06")
    assert_that(page.locator("#bundles li").count() == 1, "SEARCH_FILTER")
    page.locator("#search").fill("")
    page.locator(".bundle").filter(has_text="B03").first.click()
    assert_that("#bundle=B03" in page.url, "BIDIRECTIONAL_DEEPLINK")
    page.locator("[data-view=sipoc]").click()
    assert_that(page.locator("#sipoc article").count() == 5, "SIPOC_FIVE_COLUMNS")
    assert_that(page.locator("#view-sipoc").is_visible(), "SIPOC_TAB")
    page.locator("[data-view=timing]").click()
    assert_that(page.locator("#timing-rows tr").count() == 10, "MEASURED_JOB_SAMPLES")
    assert_that("UNKNOWN never becomes zero" in
                page.locator("#view-timing").inner_text(), "CLOCK_BOUNDARY")
    page.locator("[data-view=document]").click()
    assert_that(page.locator("#view-document").is_visible(), "DOCUMENT_LENS")
    assert_that(page.locator("#paper-tag").inner_text().startswith("B03"),
                "SOURCE_REGION_JOIN")
    assert_that("PDF layer" in page.locator(".doc-info").inner_text() and
                "UNAVAILABLE" in page.locator(".doc-info").inner_text(),
                "PDF_NOT_FABRICATED")
    source_link = page.locator("#doc-source-link").get_attribute("href")
    assert_that(source_link.startswith("https://github.com/GBOGEB/pipeline-automation-hub/blob/")
                and "#L" in source_link, "SOURCE_LINE_LINK")
    page.locator("[data-view=compendium]").click()
    assert_that(page.locator(".comp-card").count() == 4, "CROSSFORMAT_LINKS")
    page.locator("[data-view=graph]").click()
    svg_node = page.locator(".gnode").filter(has_text="B08").first
    svg_node.focus()
    svg_node.press("Enter")
    assert_that(page.locator("#inspector-id").inner_text() == "B08", "KEYBOARD_SVG")
    page.goto(PAGE.resolve().as_uri() + "#bundle=B07&view=document", wait_until="load")
    assert_that(page.locator("#inspector-id").inner_text() == "B07" and
                page.locator("#view-document").is_visible(), "RELOAD_DEEPLINK")
    sizing = page.evaluate("""() => ({
        viewport: document.documentElement.clientWidth,
        scroll: document.documentElement.scrollWidth,
        body: document.body.scrollWidth
    })""")
    assert_that(sizing["scroll"] <= sizing["viewport"] + 1 and
                sizing["body"] <= sizing["viewport"] + 1,
                "BODY_OVERFLOW:" + json.dumps(sizing))
    # Visible screenshot of the actual DAG, rather than the document lens.
    page.locator("[data-view=graph]").click()
    page.screenshot(path=str(screenshot), full_page=True)
    return {"viewport": [width, height], "svg_nodes": 10, "edges": 17,
            "timing_job_samples": 10, "keyboard": "PASS",
            "deeplink": "PASS", "no_body_overflow": True,
            "screen_name": screenshot.name}


def main():
    from playwright.sync_api import sync_playwright

    assert_that(PAGE.is_file(), "HTML_NOT_FOUND")
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors, outbound = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("request", lambda req: outbound.append(req.url)
                if req.url.startswith(("http://", "https://")) else None)
        page.route("http://**/*", lambda route: route.abort())
        page.route("https://**/*", lambda route: route.abort())
        receipts = []
        try:
            for width, height in SIZES:
                result = verify(page, width, height,
                                OUT / ("notebook_%dx%d.png" % (width, height)))
                receipts.append(result)
                print("CI_SPINE_BROWSER_VIEW_PASS=%dx%d" % (width, height))
        finally:
            browser.close()
    assert_that(not errors, "JS_ERRORS:" + repr(errors[:5]))
    assert_that(not outbound, "EXTERNAL_REQUESTS:" + repr(outbound[:5]))
    src_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert_that(re.fullmatch("[0-9a-f]{40}", src_sha) is not None, "SOURCE_SHA")
    expected = os.environ.get("EXPECTED_SHA")
    if expected:
        assert_that(expected == src_sha, "EXACT_HEAD_MISMATCH")
    receipt = {
        "schema": SCHEMA, "source_class": "LOCAL_NATIVE_BROWSER_QA_NOT_ADMISSION",
        "repo": "GBOGEB/pipeline-automation-hub", "head_sha": src_sha,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "view_sha256": hashlib.sha256(PAGE.read_bytes()).hexdigest(),
        "screenshots": receipts, "console_errors": errors,
        "external_requests": outbound, "merge_admission": "HOLD",
        "pdf_geometry": "UNAVAILABLE", "authority_transfer": False,
        "dispatched_work": False,
    }
    (OUT / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                                      encoding="utf-8", newline="\n")
    print("CI_SPINE_BROWSER_QA_PASS offline=true viewports=3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
