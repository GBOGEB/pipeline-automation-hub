#!/usr/bin/env python3
"""Exercise the generated portfolio in offline Chromium and emit a QA receipt.

Only local review artifacts are written. Links are inspected, never followed;
no worker, scheduler, deployment, repository mutation or approval is performed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from playwright.sync_api import expect, sync_playwright

from dashboard import render


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
VIEWPORTS = {"desktop": {"width": 1440, "height": 1000},
             "mobile": {"width": 390, "height": 844}}
TABS = ("portfolio", "frontier", "clusters", "history", "sources")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--expected-checkout-sha",
                        help="Candidate code SHA; defaults to the planning-source SHA")
    parser.add_argument("--browser-executable", type=Path)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema": "jade.portfolio-browser-qa.v1", "status": "FAIL",
        "checks": [], "screenshots": [], "viewports": [],
        "native_execution": os.environ.get("GITHUB_ACTIONS") == "true",
        "playwright_version": version("playwright"),
        "expected_source_sha": args.expected_source_sha,
        "expected_checkout_sha": args.expected_checkout_sha or args.expected_source_sha,
        "merge_admission": "HOLD", "authority_transfer": False,
        "dispatch_performed": False, "publication_performed": False,
    }

    def check(condition: bool, label: str) -> None:
        if not condition:
            raise AssertionError(label)
        receipt["checks"].append(label)

    def screenshot(page, name: str) -> None:
        path = args.out / name
        page.screenshot(path=str(path), full_page=True)
        check(path.stat().st_size > 1000, "nonempty screenshot: " + name)
        receipt["screenshots"].append({"path": name, "sha256": sha256(path)})

    def no_overflow(page, label: str) -> None:
        geometry = page.evaluate("""() => ({
            viewport: document.documentElement.clientWidth,
            document: document.documentElement.scrollWidth,
            body: document.body.scrollWidth
        })""")
        check(geometry["document"] <= geometry["viewport"] + 1
              and geometry["body"] <= geometry["viewport"] + 1,
              label + " has no document overflow: " + json.dumps(geometry))

    try:
        check(bool(re.fullmatch(r"[0-9a-f]{40}", args.expected_source_sha)),
              "expected source is a full SHA")
        model = json.loads(args.model.read_text(encoding="utf-8"))
        check(model["planning_source_sha"] == args.expected_source_sha,
              "model binds the expected planning source")
        check(model["source_binding"]["canonical_inputs_match"] is True,
              "canonical source-owner inputs match the fixed planning baseline")
        checkout = subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
        receipt["checkout_sha"] = checkout
        check(bool(re.fullmatch(r"[0-9a-f]{40}", receipt["expected_checkout_sha"])),
              "expected candidate checkout is a full SHA")
        receipt["exact_checkout_verified"] = checkout == receipt["expected_checkout_sha"]
        check(receipt["exact_checkout_verified"], "checkout equals expected source")
        receipt["html_sha256"] = sha256(args.html)
        receipt["model_sha256"] = sha256(args.model)
        manifest_path = args.html.parent / "manifest.json"
        check(manifest_path.is_file(), "CLI manifest exists")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for path in (args.html, args.model):
            check(manifest["files"].get(path.name) == sha256(path),
                  "CLI manifest verifies " + path.name)
        tasks = model["plan"]["tasks"]
        check(bool(tasks), "nonzero action population exercises filters and DOV/DOD")
        check(bool(model["plan"]["clusters"]), "nonzero cluster population")
        check(model["authority"]["merge_admission"] == "HOLD"
              and model["authority"]["dispatch_performed"] is False,
              "rendered data retains non-authorizing boundary")

        with sync_playwright() as playwright:
            launch = {"headless": True}
            if args.browser_executable:
                launch["executable_path"] = str(args.browser_executable)
            browser = playwright.chromium.launch(**launch)
            receipt["chromium_version"] = browser.version
            try:
                for name, viewport in VIEWPORTS.items():
                    context = browser.new_context(
                        viewport=viewport, offline=True, service_workers="block")
                    page = context.new_page()
                    errors, requests = [], []
                    page.on("pageerror", lambda exc: errors.append(str(exc)))
                    page.on("console", lambda message: errors.append(message.text)
                            if message.type == "error" else None)
                    page.on("request", lambda request: requests.append(request.url)
                            if not request.url.startswith("file:") else None)
                    try:
                        page.goto(args.html.resolve().as_uri(), wait_until="load")
                        expect(page.locator("#kpis .card")).to_have_count(4)
                        check(True, name + " renders all four source-qualified KPI cards")
                        expect(page.locator("#portfolio")).to_be_visible()
                        expect(page.get_by_role("tab")).to_have_count(len(TABS))
                        for tab in TABS:
                            button = page.locator('[data-tab="' + tab + '"]')
                            button.click()
                            expect(button).to_have_attribute("aria-selected", "true")
                            expect(page.locator("#" + tab)).to_be_visible()
                            visible = page.locator(".panel").evaluate_all(
                                "nodes => nodes.filter(n => !n.hidden).map(n => n.id)")
                            check(visible == [tab], name + " activates only tab " + tab)
                            no_overflow(page, name + " / " + tab)
                        page.locator('[data-tab="portfolio"]').click()
                        screenshot(page, name + "-portfolio.png")

                        page.locator('[data-tab="frontier"]').click()
                        expect(page.locator("#tasks .task")).to_have_count(len(tasks))
                        check(True, name + " renders the complete action population")
                        search = page.locator("#task-search")
                        search.fill("PQA_NO_SUCH_ACTION_f73b")
                        expect(page.locator("#tasks .task")).to_have_count(0)
                        expect(page.locator("#task-count")).to_have_text(
                            "0 / " + str(len(tasks)) + " proposed actions")
                        check(True, name + " reports an empty search without inventing rows")
                        search.fill(tasks[0]["title"])
                        expected = [t for t in tasks if tasks[0]["title"].lower()
                                    in json.dumps(t, ensure_ascii=False).lower()]
                        expect(page.locator("#tasks .task")).to_have_count(len(expected))
                        check(True, name + " filters action text against actual task data")
                        search.fill("")
                        cluster = tasks[0]["cluster"]
                        page.locator("#task-cluster").select_option(cluster)
                        expected = [t for t in tasks if t["cluster"] == cluster]
                        expect(page.locator("#tasks .task")).to_have_count(len(expected))
                        check(True, name + " applies declared cluster membership")
                        search.fill(tasks[0]["title"])
                        expected = [t for t in expected if tasks[0]["title"].lower()
                                    in json.dumps(t, ensure_ascii=False).lower()]
                        expect(page.locator("#tasks .task")).to_have_count(len(expected))
                        check(True, name + " intersects cluster and search predicates")
                        search.fill("")
                        page.locator("#task-cluster").select_option("")
                        detail = page.locator("#tasks .task").first.locator("details")
                        check(not detail.evaluate("node => node.open"),
                              name + " DOV/DOD starts collapsed")
                        detail.locator("summary").click()
                        check(detail.evaluate("node => node.open"), name + " DOV/DOD expands")
                        expect(detail.locator(".criteria")).to_have_count(2)
                        for index, key in enumerate(("dov", "dod")):
                            criteria = detail.locator(".criteria").nth(index)
                            expect(criteria.locator("li")).to_have_text(tasks[0][key])
                            check(True, name + " displays source " + key.upper() + " criteria")
                        no_overflow(page, name + " / expanded action")
                        screenshot(page, name + "-frontier.png")
                        detail.locator("summary").click()
                        check(not detail.evaluate("node => node.open"),
                              name + " DOV/DOD collapses again")
                        unsafe = page.locator("a[href]").evaluate_all("""nodes => nodes
                          .map(n => n.href).filter(h => {const u = new URL(h);
                            return u.protocol !== 'https:' ||
                              !['github.com', 'api.github.com'].includes(u.hostname) ||
                              u.username || u.password || (u.port && u.port !== '443');})""")
                        check(not unsafe, name + " only exposes allowlisted HTTPS evidence links")
                        check(not errors, name + " has no console/page errors: " + repr(errors))
                        check(not requests, name + " loads offline without external requests: " + repr(requests))
                        check(len(context.pages) == 1, name + " opens no external windows")
                        receipt["viewports"].append({"name": name, **viewport,
                                                     "external_requests": requests,
                                                     "errors": errors})
                    except Exception:
                        screenshot(page, name + "-failure.png")
                        raise
                    finally:
                        context.close()

                # Exercise the renderer with hostile text, independently of the
                # model validator: escaping must hold at the presentation boundary.
                hostile = copy.deepcopy(model)
                marker = ('PQA_INERT_MARKER </script><script id="pqa-injected">'
                          'window.__portfolioInjected=true</script>'
                          '<img src="https://qa.invalid/pixel" '
                          'onerror="window.__portfolioInjected=true">')
                hostile["plan"]["tasks"][0]["title"] = marker
                hostile["plan"]["tasks"][0]["t0_ref"] = "javascript:window.__portfolioInjected=true"
                hostile_path = args.out / "inert-text-fixture.html"
                hostile_path.write_text(render(hostile), encoding="utf-8", newline="\n")
                context = browser.new_context(viewport=VIEWPORTS["desktop"], offline=True,
                                              service_workers="block")
                page = context.new_page()
                errors, requests = [], []
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                page.on("console", lambda message: errors.append(message.text)
                        if message.type == "error" else None)
                page.on("request", lambda request: requests.append(request.url)
                        if not request.url.startswith("file:") else None)
                try:
                    page.goto(hostile_path.resolve().as_uri(), wait_until="load")
                    page.locator('[data-tab="frontier"]').click()
                    expect(page.locator("#tasks h3").first).to_have_text(marker)
                    check(page.evaluate("window.__portfolioInjected === undefined"),
                          "hostile task text cannot execute a script")
                    check(page.locator("#pqa-injected, img, a[href^='javascript:']").count() == 0,
                          "hostile tags and unsafe evidence href remain inert")
                    check(not requests and not errors,
                          "hostile fixture has no requests or browser errors")
                    receipt["inert_fixture_sha256"] = sha256(hostile_path)
                finally:
                    context.close()
            finally:
                browser.close()
        receipt["status"] = "PASS"
    except Exception as exc:
        receipt["failure"] = {"type": type(exc).__name__, "message": str(exc)}
    receipt["checks_total"] = len(receipt["checks"])
    (args.out / "browser-qa-receipt.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: receipt.get(key) for key in
                     ("status", "checks_total", "native_execution", "failure")}))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
