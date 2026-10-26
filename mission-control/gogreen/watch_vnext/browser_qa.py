#!/usr/bin/env python3
"""Exact-head fixture-only Playwright QA; NOT GitHub Pages or engineering credit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORTS = (("desktop", 1440, 1000), ("laptop", 1280, 800), ("mobile", 390, 844))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(html_file: Path, output: Path):
    html_file = html_file.resolve()
    manifest_path = html_file.parent / "manifest.json"
    snapshot_path = html_file.parent / "snapshot.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert manifest["sha256"]["index.html"] == sha256(html_file)
    assert manifest["sha256"]["snapshot.json"] == sha256(snapshot_path)
    assert manifest["source_sha"] == snapshot["source"]["commit_sha"]
    assert snapshot["merge_admission"] == "HOLD"
    assert snapshot["fresh_authenticated_42_cell_breadth"] is None
    assert snapshot["published_pages_verified"] is False
    output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for label, width, height in VIEWPORTS:
                page = browser.new_page(viewport={"width": width, "height": height},
                                        device_scale_factor=1)
                errors = []
                page.on("pageerror", lambda error: errors.append("page:" + str(error)))
                page.on("console", lambda message: errors.append("console:" + message.text)
                        if message.type == "error" else None)
                page.goto(html_file.as_uri(), wait_until="load")
                assert page.title().startswith("CODE PURPLE Watch vNext")
                assert page.get_by_role("heading", name="Watch vNext").is_visible()
                assert page.get_by_text("MERGE ADMISSION: HOLD").count() == 1
                assert page.locator("tbody tr").count() == 15
                assert page.locator("details#provenance").get_attribute("open") is None
                page.locator("details#provenance summary").click()
                assert page.locator("details#provenance").get_attribute("open") is not None
                assert page.locator("#source-sha").inner_text() == manifest["source_sha"]
                assert page.locator("#source-blob").inner_text() == manifest["source_blob_oid"]
                metrics = page.locator(".metric").count()
                assert metrics >= 9
                geometry = page.evaluate("""() => ({
                  body: document.body.scrollWidth,
                  document: document.documentElement.scrollWidth,
                  viewport: window.innerWidth,
                  brokenImages: [...document.images].filter(i => !i.complete || i.naturalWidth === 0).length,
                  primaryHeadingCount: document.querySelectorAll('h1').length
                })""")
                assert geometry["document"] <= geometry["viewport"] + 1, geometry
                assert geometry["body"] <= geometry["viewport"] + 1, geometry
                assert geometry["brokenImages"] == 0
                assert geometry["primaryHeadingCount"] == 1
                assert not errors, errors
                shot = output / (label + ".png")
                page.screenshot(path=str(shot), full_page=True)
                results.append({
                    "viewport": label,
                    "width": width,
                    "height": height,
                    "metric_cards": metrics,
                    "mip_rows": 15,
                    "horizontal_overflow": False,
                    "broken_images": 0,
                    "page_or_console_errors": 0,
                    "provenance_details_expanded": True,
                    "screenshot_sha256": sha256(shot),
                })
                page.close()
        finally:
            browser.close()
    receipt = {
        "schema": "codepurple.watch.flightdeck-browser-qa/n2",
        "source_git_sha": manifest["source_sha"],
        "source_blob_oid": manifest["source_blob_oid"],
        "rendered_html_sha256": manifest["sha256"]["index.html"],
        "test_class": "CANDIDATE_EXACT_HEAD_BROWSER_NOT_HOSTED",
        "results": results,
        "manual_visual_review": "PENDING",
        "hosted_parity": "DEFER",
        "merge_admission": "HOLD",
        "formal_engineering_credit_delta": 0,
    }
    (output / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return receipt


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--html", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    print(json.dumps(run(a.html, a.out), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
