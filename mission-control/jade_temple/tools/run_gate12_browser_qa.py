#!/usr/bin/env python3
"""Offline JADE H01-H12 Pages candidate QA; never grants hosted or release credit."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(1440, 1000), (1280, 800), (390, 844)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "qa/gate12"))
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    uri = (ROOT / "site/gate12_hub.html").resolve().as_uri()
    reports = []
    with sync_playwright() as playwright:
        launch = {"headless": True}
        exe = os.environ.get("JADE_BROWSER_EXECUTABLE")
        if exe:
            launch["executable_path"] = exe
        browser = playwright.chromium.launch(**launch)
        try:
            for width, height in VIEWPORTS:
                page = browser.new_page(viewport={"width": width, "height": height})
                errors, console, remote = [], [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda msg: console.append(msg.text)
                        if msg.type == "error" else None)
                page.on("request", lambda req: remote.append(req.url)
                        if not (req.url.startswith("file://") or req.url.startswith("data:")) else None)
                page.goto(uri, wait_until="load")
                page.wait_for_selector("#q-body tr")
                observed = page.locator("#q-body tr").count()
                if observed != 252:
                    raise ValueError("GATE12_QUEUE_CARDINALITY: " + str(observed))
                page.locator("#q-gate").select_option("H08")
                if page.locator("#q-body tr").count() != 21:
                    raise ValueError("GATE12_PILLAR_FILTER_FIRST_RED")
                page.locator("#q-gate").select_option("ALL")
                page.locator("#q-status").select_option("UNOBSERVED")
                if page.locator("#q-body tr").count() != 192:
                    raise ValueError("GATE12_UNOBSERVED_FILTER_FIRST_RED")
                page.locator("#q-status").select_option("ALL")
                page.locator("#q-search").fill("H12")
                if page.locator("#q-body tr").count() != 21:
                    raise ValueError("GATE12_SEARCH_FIRST_RED")
                page.locator("#q-search").fill("")
                dims = page.evaluate("""() => ({
                    width: innerWidth,
                    html: document.documentElement.scrollWidth,
                    body: document.body.scrollWidth,
                    brokenImages: [...document.images].filter(i => !i.complete || !i.naturalWidth).length
                })""")
                if dims["body"] > width + 2 or dims["html"] > width + 2:
                    raise ValueError("GATE12_HORIZONTAL_OVERFLOW: " + repr(dims))
                if dims["brokenImages"] or errors or console or remote:
                    raise ValueError("GATE12_BROWSER_FIRST_RED: " +
                                     repr((errors, console, remote, dims)))
                photo = out / f"gate12_{width}x{height}.png"
                page.screenshot(path=str(photo), full_page=True)
                reports.append({"viewport": [width, height],
                                "source_queue": observed,
                                "filter_controls": "PASS",
                                "page_errors": 0,
                                "console_errors": 0,
                                "remote_requests": 0,
                                "document_overflow": False,
                                "screenshot": photo.name})
                page.close()
        finally:
            browser.close()
    receipt = {"schema": "jade.temple.gate12.browserqa.v1",
               "evidence_level": "LOCAL_REPRODUCIBILITY_ONLY",
               "formal_release_credit": 0,
               "hosted_parity": None,
               "status": "PASS", "viewports": reports}
    (out / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("JADE_GATE12_BROWSER_QA_PASS", len(reports))


if __name__ == "__main__":
    main()
