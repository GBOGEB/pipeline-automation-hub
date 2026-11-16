#!/usr/bin/env python3
"""Offline Gate12 latest/baseline, initialization and hostile-input browser QA.

This exercises the recorded OG-five use case. It never grants hosted or release
credit. A missing or unsafe latest source must stop initialization, not silently
fall back to the reassuring historical baseline.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import functools
import http.server
import json
import os
import shutil
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(1440, 1000), (1280, 800), (390, 844)]
PAYLOAD = '<img src="https://invalid.example/gate12-injection" onerror="window.__gate12Injected=true">'


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError("GATE12_BROWSER_FIRST_RED: " + message)


@contextmanager
def local_site(root: Path):
    """Serve exact copied assets under production CSP; no public network needed."""
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
            else:
                super().do_GET()

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def tracked_page(browser, width: int, height: int, origin: str):
    page = browser.new_page(viewport={"width": width, "height": height}, timezone_id="UTC")
    events = {"page_errors": [], "console_errors": [], "remote_requests": []}
    page.on("pageerror", lambda error: events["page_errors"].append(str(error)))
    page.on("console", lambda msg: events["console_errors"].append(msg.text)
            if msg.type == "error" else None)
    page.on("request", lambda req: events["remote_requests"].append(req.url)
            if not (req.url.startswith(origin) or req.url.startswith("data:")) else None)
    return page, events


def clean_events(events: dict) -> None:
    require(not any(events.values()), "unexpected browser events " + repr(events))


def assert_mode(page, mode: str, passed: int) -> None:
    page.locator("#source-mode").select_option(mode)
    require(page.locator("#q-body tr").count() == 252, "selected queue population")
    require(page.locator("#scoreboard .kpi").count() == 5, "duplicated or missing KPIs")
    require(f"{passed}/60" in page.locator("#scoreboard .kpi b").all_text_contents(),
            "selected PASS total")
    require(page.locator("#pillar-grid .pillar").count() == 12, "duplicated gate pillars")
    require(page.locator("#q-gate option").count() == 13, "duplicated gate options")
    require(page.locator("#matrix-body tr").count() == 5, "observed repo population")
    require(page.locator("#matrix-body button").count() == 60, "matrix gate population")
    export = page.locator("#queue-export").get_attribute("href")
    expected = "gate12_latest_queue.csv" if mode == "latest" else "gate12_bd_queue.csv"
    require(export == expected, "CSV export did not follow selected evidence")


def positive_viewport(browser, width: int, height: int, out: Path, model: dict, origin: str) -> dict:
    latest = model["latest_recorded"]
    latest_passed = latest["metrics"]["observed_pass"]
    frozen_passed = model["metrics"]["observed_pass"]
    pulse = latest["source"]["pulse_id"]
    page, events = tracked_page(browser, width, height, origin)
    try:
        page.goto(origin + "original/gate12_hub.html", wait_until="load")
        page.wait_for_selector("#q-body tr")
        require(page.locator("#source-mode").input_value() == "latest", "latest is not default")
        require(pulse in page.locator("#readback-date").inner_text(), "recorded pulse identity")
        warning = page.locator("#source-warning").inner_text()
        require(latest["source"]["observed_date"] in warning or "days old" in warning,
                "missing freshness warning")
        require(page.locator("#pulse-history > *").count() == len(latest["progress_history"]),
                "recorded progress history")
        assert_mode(page, "latest", latest_passed)
        for _ in range(3):
            assert_mode(page, "frozen", frozen_passed)
            assert_mode(page, "latest", latest_passed)
        page.locator("#matrix-body tr").first.locator("button").nth(7).click()
        require(page.locator("#q-body tr").count() == 1, "matrix cell did not drill into its gate")
        page.locator("#q-search").fill("")
        page.locator("#q-gate").select_option("ALL")
        page.locator("#q-gate").select_option("H08")
        require(page.locator("#q-body tr").count() == 21, "gate filter")
        page.locator("#q-gate").select_option("ALL")
        page.locator("#q-status").select_option("UNOBSERVED")
        require(page.locator("#q-body tr").count() == 192, "unobserved filter")
        page.locator("#q-status").select_option("ALL")
        page.locator("#q-search").fill("H12")
        require(page.locator("#q-body tr").count() == 21, "search filter")
        page.locator("#q-search").fill("")
        dims = page.evaluate("""() => ({
            html: document.documentElement.scrollWidth,
            body: document.body.scrollWidth,
            brokenImages: [...document.images].filter(i => !i.complete || !i.naturalWidth).length
        })""")
        require(dims["body"] <= width + 2 and dims["html"] <= width + 2,
                "horizontal document overflow " + repr(dims))
        require(not dims["brokenImages"], "broken images")
        clean_events(events)
        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
        # Older Playwright implements string predicates through page eval,
        # which correctly fails under script-src 'self'. Instant scroll is
        # synchronous; inspect it directly without relaxing the production CSP.
        require(page.evaluate("() => window.scrollY") == 0, "initial screenshot scroll position")
        photo = out / f"gate12_{width}x{height}.png"
        page.screenshot(path=str(photo), full_page=True)
        return {"viewport": [width, height], "source_queue": 252,
                "latest_and_frozen": "PASS", "repeat_switch": "PASS",
                "matrix_drilldown": "PASS", "filter_controls": "PASS",
                "page_errors": 0, "console_errors": 0, "remote_requests": 0,
                "document_overflow": False, "screenshot": photo.name}
    finally:
        page.close()


def fixture_page(browser, root: Path, model: dict, origin: str):
    root.mkdir(parents=True)
    for name in ("gate12_hub.html", "gate12.css", "gate12_ui.js"):
        shutil.copyfile(ROOT / "site" / name, root / name)
    (root / "gate12_data.js").write_text(
        "window.JADE_GATE12=" + json.dumps(model) + ";\n", encoding="utf-8", newline="\n")
    page, events = tracked_page(browser, 1280, 800, origin)
    page.goto(origin + root.name + "/gate12_hub.html", wait_until="load")
    return page, events


def negative_controls(browser, tmp: Path, origin: str) -> list[dict]:
    model = json.loads((ROOT / "site/gate12_data.json").read_text(encoding="utf-8"))
    cases = []
    missing = copy.deepcopy(model)
    missing.pop("latest_recorded")
    cases.append(("missing_latest", missing))
    unsafe = copy.deepcopy(model)
    unsafe["latest_recorded"]["authority"]["merge_admission"] = "PASS"
    cases.append(("unsafe_latest_authority", unsafe))
    inconsistent = copy.deepcopy(model)
    inconsistent["latest_recorded"]["metrics"]["observed_pass"] += 1
    cases.append(("mismatched_latest_total", inconsistent))
    reports = []
    for name, mutated in cases:
        page, events = fixture_page(browser, tmp / name, mutated, origin)
        try:
            require("Initialization stopped" in page.locator("#source-warning").inner_text(),
                    name + " did not stop initialization")
            require(page.locator("#q-body tr").count() == 0,
                    name + " fell back to populated source")
            clean_events(events)
            reports.append({"case": name, "status": "PASS"})
        finally:
            page.close()
    hostile = copy.deepcopy(model)
    hostile["latest_recorded"]["queue"][0]["reason"] = PAYLOAD
    page, events = fixture_page(browser, tmp / "hostile_reason", hostile, origin)
    try:
        page.wait_for_selector("#q-body tr")
        require(PAYLOAD in page.locator("#q-body").inner_text(), "hostile reason was not plain text")
        require(page.locator("#q-body img").count() == 0, "hostile HTML became an image")
        require(not page.evaluate("Boolean(window.__gate12Injected)"), "hostile event handler executed")
        clean_events(events)
        reports.append({"case": "hostile_reason_is_text", "status": "PASS"})
    finally:
        page.close()
    return reports


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "qa/gate12"))
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "receipt.json").unlink(missing_ok=True)
    model = json.loads((ROOT / "site/gate12_data.json").read_text(encoding="utf-8"))
    with sync_playwright() as playwright:
        launch = {"headless": True}
        exe = os.environ.get("JADE_BROWSER_EXECUTABLE")
        if exe:
            launch["executable_path"] = exe
        browser = playwright.chromium.launch(**launch)
        try:
            with tempfile.TemporaryDirectory(prefix="jade-gate12-browser-") as tmp:
                root = Path(tmp)
                original = root / "original"
                original.mkdir()
                for name in ("gate12_hub.html", "gate12.css", "gate12_ui.js", "gate12_data.js"):
                    shutil.copyfile(ROOT / "site" / name, original / name)
                with local_site(root) as origin:
                    reports = [positive_viewport(browser, width, height, out, model, origin)
                               for width, height in VIEWPORTS]
                    negatives = negative_controls(browser, root, origin)
        finally:
            browser.close()
    receipt = {"schema": "jade.temple.gate12.browserqa.v1",
               "evidence_level": "LOCAL_REPRODUCIBILITY_ONLY",
               "formal_release_credit": 0, "hosted_parity": None,
               "status": "PASS", "viewports": reports,
               "tested_sources_sha256": {name: hashlib.sha256((ROOT / "site" / name).read_bytes()).hexdigest()
                    for name in ("gate12_hub.html", "gate12.css", "gate12_ui.js", "gate12_data.js")},
               "initialization_and_injection_controls": negatives}
    (out / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("JADE_GATE12_BROWSER_QA_PASS", len(reports), "viewports", len(negatives), "negative controls")


if __name__ == "__main__":
    main()
