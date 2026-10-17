#!/usr/bin/env python3
"""Three-viewport browser, source/parity and interaction acceptance for W1.

Use native Playwright on the exact-head generated output. No network, workers,
live CI authentication, merge authorization or engineering credit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

VIEWPORTS = ((1440, 1000), (1280, 800), (390, 844))
GRAPH_FILENAMES = ("index.html", "graph.json", "graph.mmd", "manifest.json")


def require(test, reason):
    if not test:
        raise AssertionError("MC_W1_DOV_FAIL: " + reason)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_static(source, portal, expected_sha):
    source = Path(source)
    portal = Path(portal)
    model = json.loads((source / "graph.json").read_text(encoding="utf-8"))
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    require(model["source_sha"] == manifest["source_sha"] == expected_sha, "checkout source mismatch")
    require(manifest["merge_admission"] == model["gate"]["merge_admission"] == "HOLD", "unsafe admission")
    require(manifest["authority_transfer"] is False and manifest["security_waiver"] is False, "unsafe authority")
    require(model["scheduler"]["dispatch_authorized"] is False, "dispatch authorization forged")
    for name, expected in manifest["files_sha256"].items():
        require(digest(source / name) == expected, "source member mismatch: " + name)
    require(tuple(sorted(manifest["files_sha256"])) == ("graph.json", "graph.mmd", "index.html"), "source members")
    site = json.loads((portal.parent / "site-manifest.json").read_text(encoding="utf-8"))
    require(site["source_git_sha"] == expected_sha and site["merge_authorized"] is False, "portal source mismatch")
    for name in GRAPH_FILENAMES:
        require((portal / name).is_file(), "missing portal file: " + name)
        require(digest(portal / name) == digest(source / name), "portal differs from source: " + name)
        require(site["public_files_sha256"]["mission-rebuild/" + name] == digest(portal / name),
                "portal site-manifest mismatch: " + name)
    require((source / "graph.mmd").read_text(encoding="utf-8").startswith("flowchart LR"), "Mermaid output")
    p = model["population"]
    require(p["repositories"] == 5 and p["lanes"] == 10 and p["process_atoms"] == 39
            and p["beams"] == 10 and p["nodes"] == 54, "controlled population")
    require(p["edges"] == len(model["edges"]), "edge denominator")
    require(all(e["temporal"] == "NEXT_PULSE" for e in model["edges"]
                if e["kind"] == "FEEDBACK"), "invalid feedback clock")
    return model


def browser(source, portal, expected_sha, screenshot_dir):
    model = validate_static(source, portal, expected_sha)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    details = []
    with sync_playwright() as api:
        browser = api.chromium.launch(headless=True)
        for width, height in VIEWPORTS:
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda err: errors.append("PAGEERROR: " + str(err)))
            page.on("console", lambda msg: errors.append("CONSOLE: " + msg.text) if msg.type == "error" else None)
            page.goto((Path(portal) / "index.html").resolve().as_uri(), wait_until="load")
            require(page.title() == "MISSION CONTROL | Federation Rebuild", "page title")
            require(page.locator("h1").count() == 1, "primary heading")
            require(page.locator("#repos a").count() == model["population"]["repositories"], "repo cards")
            require(page.locator("#nodes button.node").count() == model["population"]["nodes"], "initial atom population")
            require(page.locator("#sipoc > div").count() == 5, "SIPOC labels")
            require(page.locator("#workers > div").count() == len(model["scheduler"]["workers"]), "worker rows")
            for link in page.locator("#repos a").all():
                require(link.get_attribute("href").startswith("https://github.com/GBOGEB/"), "unsafe repo link")
                require("noopener" in (link.get_attribute("rel") or ""), "unsafe external target")
            page.locator("#layer").select_option("STAGE")
            require(page.locator("#nodes button.node").count() == 39, "stage filter")
            page.locator("#layer").select_option("BEAM")
            require(page.locator("#nodes button.node").count() == 10, "beam filter")
            page.locator("#nodes button.node").first.click()
            require("BEAM_" in page.locator("#details pre").inner_text(), "node selection")
            page.locator("#query").fill("NO_SUCH_GRAPH_ATOM_999")
            require(page.get_by_text("No matches.", exact=True).count() == 1, "search zero state")
            page.locator("#reset").click()
            require(page.locator("#nodes button.node").count() == 54, "reset complete")
            require(page.locator("#beam-dag [role=button]").count() == 10, "SVG beam controls")
            page.locator("#beam-dag [role=button]").first.click()
            require("BEAM_" in page.locator("#details pre").inner_text(), "SVG selection")
            over = page.evaluate("({doc:document.documentElement.scrollWidth,viewport:window.innerWidth})")
            require(over["doc"] <= over["viewport"] + 1, "document horizontal overflow at " + str(width))
            require(not errors, "browser console/page errors: " + "; ".join(errors))
            image = screenshot_dir / ("mission-w1-%dx%d.png" % (width, height))
            page.screenshot(path=str(image), full_page=True)
            require(image.stat().st_size > 10000, "empty viewport screenshot")
            details.append({"width": width, "height": height, "errors": len(errors),
                            "document_horizontal_overflow_px": max(0, over["doc"]-over["viewport"]),
                            "repo_cards": 5, "stage_nodes": 39, "beam_nodes": 10,
                            "worker_instances": len(model["scheduler"]["workers"]),
                            "screenshot_bytes": image.stat().st_size,
                            "screenshot_sha256": digest(image)})
            page.close()
        browser.close()
    return {"schema": "missioncontrol.makeover.w1_browser_qa.v1",
            "checkout_sha": expected_sha, "viewports": details,
            "checks": {"source_hash": "PASS", "portal_parity": "PASS", "mermaid_structure": "PASS",
                       "interactive_repos": "PASS", "interactive_layers": "PASS",
                       "node_select": "PASS", "svg_dag": "PASS",
                       "search_and_reset": "PASS", "no_body_overflow": "PASS",
                       "zero_browser_errors": "PASS"},
            "claim_scope": "EXACT_HEAD_NATIVE_LOCAL_BROWSER_BUILD_ONLY",
            "actual_worker_hours": None, "cross_repo_coverage_uplift": None,
            "merge_admission": "HOLD", "qps_owner_acceptance": None}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--portal", required=True)
    p.add_argument("--sha", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--screens", required=True)
    a = p.parse_args()
    data = browser(Path(a.source), Path(a.portal), a.sha, Path(a.screens))
    Path(a.out).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"W1_DOV": "PASS", "viewports": len(data["viewports"]),
                      "native_SHA": a.sha, "receipt": a.out}, sort_keys=True))
