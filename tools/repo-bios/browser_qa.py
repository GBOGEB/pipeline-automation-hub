"""Optional local-content Chromium QA; does not attest hosted parity."""
import argparse
import hashlib
import json
from pathlib import Path


def run(report_dir, output, executable=None):
    from playwright.sync_api import sync_playwright
    report_dir, output = Path(report_dir), Path(output)
    data = json.loads((report_dir / "report.json").read_text())
    body = (report_dir / "index.html").read_text()
    expected = {r["repository"]: r for r in data["repositories"]}
    output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as p:
        options = {"headless": True}
        if executable:
            options["executable_path"] = executable
        browser = p.chromium.launch(**options)
        try:
            for label, width, height in [("desktop", 1440, 1000), ("mobile", 390, 844)]:
                page = browser.new_page(viewport={"width": width, "height": height})
                errors, requests = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: requests.append(request.url)
                        if request.url.startswith(("http:", "https:")) else None)
                # Managed Chrome can forbid file: navigation; content QA is explicit.
                page.set_content(body, wait_until="load")
                assert page.locator("main > section").count() == len(expected)
                tested, graphs, decisions = 0, 0, 0
                for name, repo in expected.items():
                    page.locator("#search").fill(name)
                    assert page.locator("main > section").count() == 1
                    for pipeline in repo.get("development", {}).get("pipelines", []):
                        view = page.locator(f'details[data-pipeline="{pipeline["id"]}"]')
                        view.locator(":scope > summary").click()
                        assert view.get_by_text("Entry-file LOC:", exact=False).count() == 1
                        buttons = view.locator('svg rect[role="button"]')
                        if pipeline["nodes"] and not pipeline["graph_error"]:
                            assert buttons.count() == len(pipeline["nodes"])
                            buttons.first.click()
                            assert view.get_by_text("Execution readiness: NOT_EVALUATED", exact=False).count() == 1
                            buttons.last.focus()
                            buttons.last.press("Enter")
                            assert pipeline["nodes"][-1]["id"] in view.locator('[aria-live="polite"]').inner_text()
                            graphs += 1
                        if pipeline["adr_sources"]:
                            adr = view.get_by_text("ADR / decision source crosswalk", exact=False).locator("..")
                            adr.locator(":scope > summary").click()
                            for row in adr.locator("details > summary").all():
                                row.click()
                            assert adr.get_by_text("Acceptance: NOT_EVALUATED", exact=False).count() == len(pipeline["adr_sources"])
                            decisions += len(pipeline["adr_sources"])
                        tested += 1
                page.locator("#search").fill("GBOGEB/ABACUS")
                focused = page.locator('details[data-pipeline="dmaic-orchestrator"]')
                if focused.count():
                    focused.locator(":scope > summary").click()
                    focused.locator('svg rect[role="button"]').first.click()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                assert not errors, errors
                assert not requests, requests
                page.screenshot(path=str(output / f"{label}.png"), full_page=False)
                results.append(dict(viewport=label, pipelines_inspected=tested,
                    graphs_click_and_keyboard=graphs, decision_crosswalks=decisions,
                    document_overflow=False, javascript_errors=errors, external_requests=requests))
                page.close()
        finally:
            browser.close()
    receipt = dict(qualification="LOCAL_CONTENT_QA_NOT_HOSTED_PARITY", generator=data.get("generator"),
        html_sha256=hashlib.sha256((report_dir / "index.html").read_bytes()).hexdigest(),
        report_sha256=hashlib.sha256((report_dir / "report.json").read_bytes()).hexdigest(), results=results)
    (output / "browser-qa.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--executable")
    options = parser.parse_args()
    run(options.report_dir, options.out, options.executable)
