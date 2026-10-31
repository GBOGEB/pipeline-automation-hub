#!/usr/bin/env python3
"""Bounded browser DoV of a read-only file:// CI spine; screenshots are QA artifacts.

Playwright is optional for local rendering. In CI it is installed and every
check is required for this scoped preview workflow; this never authorizes merge.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

HERE = Path(__file__).resolve().parent
HTML = HERE / "explorer.html"
POINTERS = HERE / "pointers" / "index.html"
QA = HERE / "qa" / "explorer"
WIDTHS = (1440, 1280, 390)


def run():
    QA.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "gbo.ci-spine.explorer-browser-qa.v1",
        "source_html_sha256": hashlib.sha256(HTML.read_bytes()).hexdigest(),
        "browser": "chromium",
        "requested_viewports": list(WIDTHS),
        "network_requests_outside_local_file": [],
        "exceptions": [],
        "cases": [],
        "pointer_cases": [],
        "merge_authorized": False,
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": 900}, device_scale_factor=1)
                page.on("pageerror", lambda exc: payload["exceptions"].append(str(exc)))
                page.on("request", lambda req: payload["network_requests_outside_local_file"].append(req.url)
                        if not req.url.startswith("file://") else None)
                page.goto(HTML.as_uri(), wait_until="load")
                expect(page.locator("#metric-workflows")).to_have_text("182")
                expect(page.locator("#metric-tests")).to_have_text("307")
                expect(page.locator("#metric-nodes")).to_have_text("10")
                expect(page.locator("#metric-runs")).to_have_text("8")
                assert page.locator("#dag g[role=button]").count() == 10, "ten selectable bundles"
                page.locator("#dag g[role=button][aria-label*='B05']").click()
                expect(page.locator("#detail")).to_contain_text("B05")
                expect(page.locator("#detail")).to_contain_text("SOURCE_FILE_ONLY")
                page.locator('[data-lens="sipoc"]').click()
                assert page.locator(".sipoc .card").count() == 5, "SIPOC 5 columns"
                page.locator('[data-lens="catalog"]').click()
                assert page.locator("#catalog-rows tr").count() == 182, "complete catalog"
                page.locator("#search").fill("actions-pin-ratchet")
                assert page.locator("#catalog-rows tr").count() == 1, "search narrows catalog"
                page.locator("#search").fill("")
                page.locator('[data-lens="timing"]').click()
                assert page.locator(".timing-row").count() == 8, "eight sampled runs"
                page.locator(".timing-name").first.click()
                expect(page.locator("#detail")).to_contain_text("Representative")
                expect(page.locator("#detail")).to_contain_text("Execution")
                assert page.locator("#detail a[href*='/actions/runs/']").count() >= 1, "exact attempt link"
                page.locator('[data-lens="plan"]').click()
                assert page.locator(".plan-card").count() == 8, "8 follow-through work items"
                page.locator(".plan-card button").first.click()
                expect(page.locator("#detail")).to_contain_text("Definition of Verification")
                page.locator('[data-lens="graph"]').click()
                page.locator("#zoom").evaluate(
                    "(el) => {el.value='160';el.dispatchEvent(new Event('input',{bubbles:true}));}")
                expect(page.locator("#zoomtext")).to_have_text("160%")
                page.locator("#reset").click()
                expect(page.locator("#zoomtext")).to_have_text("90%")
                page.locator("#edge-mode").select_option("feedback")
                assert page.locator("#dag path[stroke='#d2a85e']").count() >= 1, "temporal edge"
                page.locator("#edge-mode").select_option("all")
                if width == 1440:
                    with page.expect_download() as event:
                        page.locator("#svg-export").click()
                    download = event.value
                    assert download.suggested_filename.startswith("ci-spine-logical-dag-")
                    destination = QA / download.suggested_filename
                    download.save_as(str(destination))
                    vector = destination.read_bytes()
                    assert vector.startswith(b"<svg") or vector.startswith(b'<svg'), "SVG must be vector XML"
                    assert b"B00" in vector and b"B09" in vector, "SVG must include all bundle endpoints"
                    payload["svg_export"] = {
                        "filename": download.suggested_filename,
                        "sha256": hashlib.sha256(vector).hexdigest(),
                        "bytes": len(vector),
                    }
                page.screenshot(path=str(QA / ("full-" + str(width) + ".png")), full_page=True)
                horizontal = page.evaluate("({scroll:document.documentElement.scrollWidth,window:innerWidth})")
                assert horizontal["scroll"] <= horizontal["window"]+1, "unwanted horizontal page overflow"
                payload["cases"].append({
                    "viewport": width,
                    "views": ["graph", "sipoc", "catalog", "timing", "plan"],
                    "search": "PASS", "temporal": "PASS", "source_binding": "PASS",
                    "horizontal_overflow": False,
                })
                page.close()
            # Deep links are backed by immutable run IDs and selection state.
            page = browser.new_page()
            page.goto(HTML.as_uri() + "#lens=timing&kind=run&id=40690663789")
            expect(page.locator('[data-lens="timing"]')).to_have_attribute("aria-current", "page")
            expect(page.locator("#detail")).to_contain_text("40690663789")
            page.close()
            # Router hardening: malformed ids fall back safely, Back restores the
            # fragment-less initial view, and keyboard activation keeps focus.
            page = browser.new_page()
            page.on("pageerror", lambda exc: payload["exceptions"].append(str(exc)))
            for bad in ("constructor", "__proto__", "toString"):
                page.goto(HTML.as_uri() + "#lens=sipoc&kind=bundle&id=" + bad)
                page.reload()
                expect(page.locator('[data-lens="sipoc"]')).to_have_attribute("aria-current", "page")
                expect(page.locator("#view-subtitle")).to_have_text("bundle · B05")
            page.goto("about:blank")
            page.goto(HTML.as_uri())
            page.locator('[data-lens="timing"]').click()
            expect(page.locator('[data-lens="timing"]')).to_have_attribute("aria-current", "page")
            page.go_back()
            expect(page.locator('[data-lens="graph"]')).to_have_attribute("aria-current", "page")
            expect(page.locator("#view-subtitle")).to_have_text("bundle · B05")
            page.go_forward()
            expect(page.locator('[data-lens="timing"]')).to_have_attribute("aria-current", "page")
            page.locator('[data-lens="graph"]').click()
            node = page.locator('[data-focus-key="graph:bundle:B06"]')
            node.focus()
            page.keyboard.press("Enter")
            expect(page.locator("#view-subtitle")).to_have_text("bundle · B06")
            assert page.evaluate("document.activeElement.dataset.focusKey") == "graph:bundle:B06", \
                "keyboard focus lost after graph redraw"
            nav_b07 = page.locator('[data-focus-key="nav:bundle:B07"]')
            nav_b07.focus()
            page.keyboard.press(" ")
            expect(page.locator("#view-subtitle")).to_have_text("bundle · B07")
            assert page.evaluate("document.activeElement.dataset.focusKey") == "nav:bundle:B07", \
                "keyboard focus lost after navigator redraw"
            payload["router_cases"] = ["malformed_id_fallback", "back_forward_initial_view",
                                       "graph_enter_keeps_focus", "nav_space_keeps_focus"]
            page.close()
            # JQ-04 static companion is a separate no-script page.  The clickable
            # view-selection pointers must navigate into the existing explorer
            # without introducing network dependencies or phantom PDF anchors.
            for width in (1440, 390):
                pointer_page = browser.new_page(
                    viewport={"width": width, "height": 900},
                    device_scale_factor=1,
                )
                pointer_page.on("pageerror", lambda exc: payload["exceptions"].append(str(exc)))
                pointer_page.on(
                    "request",
                    lambda req: payload["network_requests_outside_local_file"].append(req.url)
                    if not req.url.startswith("file://") else None,
                )
                pointer_page.goto(POINTERS.as_uri(), wait_until="load")
                expect(pointer_page.locator("article.card")).to_have_count(3)
                expect(pointer_page.locator("a.action")).to_have_count(3)
                expect(pointer_page.locator("main")).to_contain_text("0 PDF RECTANGLES VERIFIED")
                expect(pointer_page.locator(".layer-stage")).to_have_count(3)
                assert pointer_page.locator('.layer-stage[data-layer="source"]').get_attribute("open") is not None
                view_layer = pointer_page.locator('.layer-stage[data-layer="views"]')
                assert view_layer.get_attribute("open") is None
                view_layer.locator("summary").click()
                assert view_layer.get_attribute("open") is not None, "view comparison is not interactive"
                expect(view_layer).to_contain_text("Two distinct, source-bound")
                assert view_layer.locator('a[href="../explorer.html#lens=sipoc&kind=bundle&id=B05"]').count() == 1
                pdf_layer = pointer_page.locator('.layer-stage[data-layer="publication"]')
                pdf_layer.locator("summary").click()
                assert pdf_layer.get_attribute("open") is not None, "publication unknown-state disclosure"
                expect(pdf_layer).to_contain_text("UNMAPPED")
                assert pdf_layer.locator("a").count() == 0, "never create an unverified PDF link"
                assert pointer_page.locator("script").count() == 0, "companion must have no script"
                for href in (
                    "../explorer.html#lens=graph&kind=bundle&id=B05",
                    "../explorer.html#lens=sipoc&kind=bundle&id=B05",
                    "../explorer.html#lens=timing&kind=run&id=40690663789",
                ):
                    assert pointer_page.locator('a.action[href="' + href + '"]').count() == 1, href
                horizontal = pointer_page.evaluate(
                    "({scroll:document.documentElement.scrollWidth,window:innerWidth})"
                )
                assert horizontal["scroll"] <= horizontal["window"] + 1, "pointer mobile overflow"
                pointer_page.screenshot(
                    path=str(QA / ("pointer-" + str(width) + ".png")), full_page=True
                )
                pointer_page.locator(
                    'a.action[href="../explorer.html#lens=graph&kind=bundle&id=B05"]'
                ).click()
                expect(pointer_page.locator('[data-lens="graph"]')).to_have_attribute(
                    "aria-current", "page"
                )
                expect(pointer_page.locator("#detail")).to_contain_text("B05")
                payload["pointer_cases"].append({
                    "viewport": width,
                    "candidate_links": 3,
                    "no_script": True,
                    "pdf_rectangles_verified": 0,
                    "navigation": "PASS",
                    "layer_comparison": "PASS",
                    "horizontal_overflow": False,
                })
                pointer_page.close()
        finally:
            browser.close()
    assert not payload["network_requests_outside_local_file"], "browser attempted external requests"
    assert not payload["exceptions"], "uncaught JavaScript errors"
    assert len(payload["cases"]) == len(WIDTHS), "incomplete viewport population"
    assert len(payload["pointer_cases"]) == 2, "incomplete JQ-04 companion UI coverage"
    (QA / "browser-receipt.json").write_text(json.dumps(payload, indent=2, sort_keys=True)+"\n",
                                             encoding="utf-8", newline="\n")
    print(json.dumps({"verdict":"PASS","widths":WIDTHS,
                      "network_calls":len(payload["network_requests_outside_local_file"]),
                      "html_sha256":payload["source_html_sha256"],
                      "merge_authorized":False}, sort_keys=True))


if __name__ == "__main__":
    run()
