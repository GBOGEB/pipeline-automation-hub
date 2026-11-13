#!/usr/bin/env python3
"""Offline Chromium QA for the five real SVG source-to-render mappings.

Run only on a locally generated SVG bridge. No network, editor, remote APIs,
release authority, or PDF mapping is present in this review surface.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HTML = HERE / "index.html"
RECEIPT = HERE / "SOURCE_SVG_POINTERS_v1.json"
QA = ROOT / "qa" / "ci_spine" / "svg_bridge"
WIDTHS = (1440, 390)


def run() -> dict:
    QA.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(RECEIPT.read_text("utf-8"))
    source_sha256 = hashlib.sha256(HTML.read_bytes()).hexdigest()
    if manifest["output"]["sha256"] != source_sha256:
        raise AssertionError("SVG_BRIDGE_RENDER_DIGEST_FIRST_RED")
    out = {"schema": "gbo.ci-spine.svg-browser-qa.v1", "html_sha256": source_sha256,
           "source_blob_oid": manifest["source"]["git_blob_oid"],
           "cases": [], "exceptions": [], "external_requests": [],
           "merge_authorized": False, "pdf_mapping": "UNMAPPED"}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 860}, device_scale_factor=1)
                page.on("pageerror", lambda error: out["exceptions"].append(str(error)))
                page.on("request", lambda request: out["external_requests"].append(request.url)
                        if not request.url.startswith("file://") else None)
                page.goto(HTML.as_uri(), wait_until="load")
                expect(page.locator("#objects button")).to_have_count(5)
                expect(page.locator("#drawing [data-bridge-id]")).to_have_count(5)
                expect(page.locator("#selected-label")).to_have_text("MissionControl SSOT")
                page.locator("#source-node-next").click()
                expect(page.locator("#selected-label")).to_have_text("Next / React")
                expect(page.locator("#source-link")).to_have_attribute(
                    "href", re.compile(r"https://github\.com/GBOGEB/pipeline-automation-hub/blob/[0-9a-f]{40}/.+#L\d+"))
                assert page.url.endswith("#node=next"), page.url
                page.locator("#zoom-in").click()
                expect(page.locator("#zoom-reset")).to_have_text("95%")
                page.locator("#toggle-flows").uncheck()
                assert page.locator("#drawing").evaluate(
                    "(node) => getComputedStyle(node.querySelector('path.flow')).display") == "none"
                page.locator("#toggle-labels").uncheck()
                assert page.locator("#drawing").evaluate(
                    "(node) => getComputedStyle(node.querySelector('text.label')).display") == "none"
                page.locator("#toggle-flows").check()
                page.locator("#toggle-labels").check()
                assert page.locator("#drawing").evaluate(
                    "(node) => getComputedStyle(node.querySelector('path.flow')).display") != "none"
                page.screenshot(path=str(QA / ("bridge-" + str(width) + ".png")), full_page=True)
                overflow = page.evaluate(
                    "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
                assert overflow <= 3, "SVG_BRIDGE_PAGE_OVERFLOW_FIRST_RED:" + str(width) + ":" + str(overflow)
                page.goto(HTML.as_uri() + "#node=parity", wait_until="load")
                expect(page.locator("#selected-label")).to_have_text("Release parity")
                page.goto(HTML.as_uri() + "#node=unmapped", wait_until="load")
                expect(page.locator("#selection-status")).to_contain_text("UNMAPPED")
                assert page.locator("#source-link").get_attribute("href") is None
                out["cases"].append({"width": width, "select": "PASS", "zoom": "PASS",
                                     "layers": "PASS", "hash_routing": "PASS",
                                     "invalid_route": "PASS", "page_overflow_px": overflow})
                page.close()
        finally:
            browser.close()
    if out["exceptions"] or out["external_requests"] or len(out["cases"]) != len(WIDTHS):
        raise AssertionError("SVG_BRIDGE_BROWSER_FIRST_RED:" + json.dumps(out, sort_keys=True))
    (QA / "receipt.json").write_text(json.dumps(out, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("SVG_BRIDGE_BROWSER_QA=PASS; viewports=1440,390; external_requests=0")
    return out


if __name__ == "__main__":
    run()
