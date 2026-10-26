#!/usr/bin/env python3
"""Playwright QA for the JADE N+8 red-trace page and slides (local files, no network).

Page: 1440x1000, 1280x800, 390x844 — no JS errors, no horizontal overflow, filters work
(repo / class / red-only / search change the visible row count), actor badges present.
Slides: every 16:9 slide keeps its content above the footer (no clipped content).
"""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

SITE = Path(__file__).resolve().parents[1] / "site"
VIEWPORTS = [(1440, 1000), (1280, 800), (390, 844)]


def fail(msg):
    raise SystemExit("REDTRACE_QA_FAIL: " + msg)


def main():
    rep = {"schema": "jade.temple.redtrace_browser_qa.v1", "viewports": [], "slides": []}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w, h in VIEWPORTS:
            pg = b.new_page(viewport={"width": w, "height": h})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.goto((SITE / "redtrace.html").as_uri())
            vis = lambda: pg.locator("#rt-ledger tbody tr:not([hidden])").count()
            red_only = vis()
            pg.locator("#rt-red").uncheck()
            all_rows = vis()
            if all_rows < red_only or all_rows == 0:
                fail(f"red-only toggle at {w}: {red_only}->{all_rows}")
            first_repo = pg.locator("#rt-repo option").nth(1).get_attribute("value")
            pg.select_option("#rt-repo", first_repo)
            if vis() > all_rows:
                fail("repo filter widened rows")
            pg.select_option("#rt-repo", "")
            pg.fill("#rt-q", "zz-no-such-workflow-zz")
            if vis() != 0:
                fail("search zero state")
            pg.fill("#rt-q", "")
            for a in ("agent", "owner", "ci"):
                if pg.locator(f".rt-actor-{a}").count() == 0:
                    fail(f"missing {a} actor badge")
            ov = pg.evaluate("document.documentElement.scrollWidth-innerWidth")
            if ov > 1:
                fail(f"horizontal overflow {ov}px at {w}")
            if errs:
                fail(f"browser errors at {w}: {errs[:2]}")
            rep["viewports"].append({"w": w, "h": h, "red_rows": red_only, "all_rows": all_rows, "overflow_px": ov})
            pg.close()
        pg = b.new_page(viewport={"width": 1280, "height": 720})
        pg.goto((SITE / "redtrace-slides.html").as_uri())
        res = pg.evaluate("""[...document.querySelectorAll('.slide')].map(s=>{const f=s.querySelector('.foot').getBoundingClientRect().top;
          let m=0;s.querySelectorAll(':scope > *:not(.foot)').forEach(c=>{m=Math.max(m,c.getBoundingClientRect().bottom)});return [s.id,Math.round(m-f)]})""")
        for sid, over in res:
            if over > 0:
                fail(f"slide {sid} content overflows footer by {over}px")
            rep["slides"].append({"id": sid, "clear_px": -over})
        b.close()
    rep["verdict"] = "PASS"
    print(json.dumps(rep, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
