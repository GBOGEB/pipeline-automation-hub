#!/usr/bin/env python3
"""Playwright visual/functional QA of PUBLIC offline taxonomy explorer.

All data is synthetic. No URLs fetched, API tokens, private titles or artifacts
uploaded. Screenshots remain in runner-local temporary directory.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

import taxonomy_explorer as explorer
import title_taxonomy as taxonomy

HUB = "GBOGEB/pipeline-automation-hub"
OTHER = "GBOGEB/ABACUS"
PRIVATE = "GBOGEB/cryoplant-project"


def fixture() -> dict:
    specs = [
        (HUB, 11, "fix(jade devops): census fails closed", "PullRequest", False),
        (HUB, 12, "feat(watch): code-purple telemetry", "Issue", False),
        (OTHER, 21, "docs: release documentation", "Issue", False),
        (PRIVATE, 31, "fix(secret vendor): TOP-SECRET-LOCAL-TEST", "Issue", True),
    ]
    return {
        "schema": explorer.RANK_SCHEMA,
        "fetched_at": "2026-10-26T16:24:00+01:00",
        "heads": {r: {"private": private, "head_sha": sha * 40}
                  for (r, private, sha) in
                  ((HUB, False, "a"), (OTHER, False, "b"), (PRIVATE, True, "c"))},
        "items": [{"key": f"{repo}#{number}", "repo": repo, "number": number,
                   "type": kind, "title": title, "private": private,
                   "title_taxonomy": taxonomy.parse_title(title, kind)}
                  for repo, number, title, kind, private in specs],
    }


def check(page, viewport: tuple[int, int], screenshot: Path) -> None:
    width, height = viewport
    page.set_viewport_size({"width": width, "height": height})
    page.reload(wait_until="load")
    page.locator("#taxonomy-rows tr").first.wait_for(state="visible")
    assert page.locator("#visible-count").inner_text() == "3"
    assert page.locator("#taxonomy-rows tr:visible").count() == 3
    assert "TOP-SECRET-LOCAL-TEST" not in page.content()
    assert PRIVATE not in page.content()
    for identifier in ("f-repo", "f-type", "f-family", "f-topic", "f-cluster",
                       "f-cohort", "f-classification", "f-text"):
        assert page.locator("label[for='" + identifier + "']").count() == 1
    # Actual interaction, not just markup inspection.
    page.select_option("#f-type", label="PullRequest")
    assert page.locator("#visible-count").inner_text() == "1"
    assert page.locator("#taxonomy-rows tr:visible").count() == 1
    page.select_option("#f-type", "")
    page.select_option("#f-family", label="fix")
    assert page.locator("#visible-count").inner_text() == "1"
    page.select_option("#f-family", "")
    page.fill("#f-text", "documentation")
    assert page.locator("#visible-count").inner_text() == "1"
    page.fill("#f-text", "")
    assert page.locator("#visible-count").inner_text() == "3"
    # Wide table scrolls in its own viewport rather than escaping the page.
    sizing = page.evaluate("""() => ({
       content: document.documentElement.scrollWidth,
       viewport: document.documentElement.clientWidth,
       tables: [...document.querySelectorAll('.table-wrap')]
          .map(el => ({width: el.clientWidth, scroll: el.scrollWidth}))
    })""")
    assert sizing["content"] <= sizing["viewport"] + 1, sizing
    # Desktop tables may fit naturally. Narrow mobile must scroll INSIDE
    # the table wrapper, never overflow the document viewport.
    if width <= 390:
        assert any(t["scroll"] > t["width"] for t in sizing["tables"]), sizing
    page.screenshot(path=str(screenshot), full_page=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="taxqa-") as tmp:
        html = Path(tmp) / "public-synthetic.html"
        html.write_text(explorer.render(fixture()), encoding="utf-8")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # Deny any network request; file: is allowed for the local fixture.
            page.route("http://**/*", lambda route: route.abort())
            page.route("https://**/*", lambda route: route.abort())
            page.goto(html.resolve().as_uri(), wait_until="load")
            for size in ((1440, 900), (768, 1024), (390, 844)):
                check(page, size, Path(tmp) / f"taxonomy-{size[0]}x{size[1]}.png")
                print(f"QA_PASS viewport={size[0]}x{size[1]} filters=3 private_leak=0")
            browser.close()
    print("BROWSER_QA_PASS offline=TRUE public_only=TRUE screenshots=local_temp_only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
