#!/usr/bin/env python3
"""N3 read-only HTML screenshot and source/Pages parity qualification."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

VIEWPORTS = ((1440, 1000), (1280, 800), (390, 844))
NAMES = ("n3-metrics.html", "n3-metrics.json", "n3-manifest.json")


def demand(ok, reason):
    if not ok:
        raise AssertionError("N3_BROWSER_QA_HOLD: " + reason)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(source, public, source_sha):
    source, public = Path(source), Path(public)
    metadata = json.loads((source / "n3-manifest.json").read_text(encoding="utf-8"))
    receipt = json.loads((source / "n3-metrics.json").read_text(encoding="utf-8"))
    parent = json.loads((public.parent / "site-manifest.json").read_text(encoding="utf-8"))
    demand(metadata["presentation_sha"] == receipt["presentation_sha"] ==
           parent["source_git_sha"] == source_sha, "presentation SHA mismatch")
    demand(metadata["producer_sha"] == receipt["producer_sha"], "native producer lineage")
    demand(metadata["merge_admission"] == receipt["authority"]["merge_admission"] == "HOLD",
           "unsafe merge promotion")
    demand(metadata["authority_transfer"] is False, "authority transfer")
    demand(set(metadata["member_sha256"]) ==
           {"n3-metrics.json", "n3-metrics.html"}, "member denominator")
    for name in NAMES:
        demand((source / name).is_file() and (public / name).is_file(),
               "missing page member " + name)
        demand(digest(source / name) == digest(public / name),
               "source/public byte drift " + name)
        demand(parent["public_files_sha256"]["mission-rebuild/" + name] ==
               digest(public / name), "site-manifest wrong " + name)
    for name, expected in metadata["member_sha256"].items():
        demand(digest(source / name) == expected, "producer member hash mismatch")
    demand(receipt["fleet_runner_capacity"] is None and
           receipt["authority"]["remote_dispatch"] is False,
           "unknown runner/cross-repo authority promotion")
    return receipt


def qualify(source, public, sha, screenshots):
    data = verify(source, public, sha)
    screenshots = Path(screenshots)
    screenshots.mkdir(parents=True, exist_ok=True)
    screenshots_receipt = []
    with sync_playwright() as playwright:
        options = {"headless": True}
        if os.environ.get("PLAYWRIGHT_EXECUTABLE_PATH"):
            options["executable_path"] = os.environ["PLAYWRIGHT_EXECUTABLE_PATH"]
        browser = playwright.chromium.launch(**options)
        for width, height in VIEWPORTS:
            page = browser.new_page(viewport={"width": width, "height": height},
                                    device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.on("console", lambda entry:
                    errors.append(entry.text) if entry.type == "error" else None)
            page.goto((Path(public) / "n3-metrics.html").resolve().as_uri(),
                      wait_until="load", timeout=30000)
            page.locator(".js-plotly-plot").first.wait_for(timeout=30000)
            demand(page.title() == "Mission Control N3 · native scoped KPI and REX", "title")
            demand(page.locator("h1").count() == 1, "primary heading")
            demand(page.locator(".js-plotly-plot").count() == 2, "two Plotly inlays")
            demand(page.locator("table tbody tr").count() == 6, "six governed KPI rows")
            detail = page.locator("#details")
            demand(detail.is_hidden(), "details initially hidden")
            page.locator("#detailToggle").click()
            demand(detail.is_visible(), "expand source details")
            demand(page.locator("#detailToggle").get_attribute("aria-expanded") == "true",
                   "aria state change")
            page.locator("#detailToggle").click()
            demand(detail.is_hidden(), "close details")
            demand(page.locator('a[href="n3-metrics.json"]').count() == 1,
                   "source JSON link")
            overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            demand(overflow <= 1, "document width overflow")
            demand(not errors, "browser console/page errors: " + "; ".join(errors))
            shot = screenshots / ("n3-%dx%d.png" % (width, height))
            page.screenshot(path=str(shot), full_page=True)
            demand(shot.stat().st_size > 10000, "nonempty screenshot")
            screenshots_receipt.append({"viewport": "%dx%d" % (width, height),
                                        "plotly_cards": 2, "kpi_rows": 6,
                                        "body_overflow_px": max(0, overflow),
                                        "errors": errors,
                                        "png_bytes": shot.stat().st_size,
                                        "png_sha256": digest(shot)})
            page.close()
        browser.close()
    return {"schema": "missioncontrol.n3.html_qa_receipt.v1",
            "presentation_sha": sha, "producer_sha": data["producer_sha"],
            "source_scope": data["scope"],
            "screenshots": screenshots_receipt,
            "source_pages_hashes": "PASS", "merge_admission": "HOLD",
            "authority_transfer": False, "qps_engineering_credit": None}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--public", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--screens", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    receipt = qualify(a.source, a.public, a.head, a.screens)
    Path(a.out).write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"N3_HTML_QA": "PASS", "screens": len(receipt["screenshots"]),
                      "presentation_sha": a.head}))
