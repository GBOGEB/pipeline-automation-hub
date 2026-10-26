"""Local Atlas QA: keyboard, source inspection, filters, themes, three widths.

Screenshots and receipts establish local reproducibility, never native CI or
merge admission. The browser receives local bytes and makes no network requests.
"""

import argparse
import hashlib
import json
from pathlib import Path


def qa(html, out, head="UNKNOWN"):
    from playwright.sync_api import sync_playwright

    html, out = Path(html).resolve(), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    markup = html.read_text(encoding="utf-8").replace('<link href="style.css" rel="stylesheet">', "").replace('<script src="app.js" defer></script>', "")
    css = (html.parent / "style.css").read_text(encoding="utf-8")
    js = (html.parent / "app.js").read_text(encoding="utf-8")
    checks = []
    with sync_playwright() as playwright:
        executable = "/usr/bin/chromium" if Path("/usr/bin/chromium").is_file() else None
        browser = playwright.chromium.launch(headless=True, executable_path=executable, args=["--no-sandbox"])
        try:
            for name, width, height in [("desktop", 1440, 1000), ("laptop", 1280, 800), ("mobile", 390, 844)]:
                page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                errors, requests = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("request", lambda request: requests.append(request.url) if request.url.startswith(("http:", "https:")) else None)
                page.set_content(markup, wait_until="load")
                page.add_style_tag(content=css)
                page.add_script_tag(content=js)
                page.wait_for_function("() => document.documentElement.dataset.atlasReady === 'true'")
                model = page.evaluate("() => JSON.parse(document.getElementById('source-model').textContent)")
                graphs, blocks = model.get("graphs") or [], model.get("blocks") or []
                projection_checks = {"roles": 0, "bindings": 0}

                def assert_projection(graph):
                    result = page.evaluate("""graph => {
                        const nodes = new Map([...document.querySelectorAll('#diagram-view .graph-node')].map(n => [n.dataset.node,n]));
                        const paths = [...document.querySelectorAll('#diagram-view .graph-edge')];
                        const failures = []; let roles = 0, bindings = 0;
                        for (const node of graph.nodes || []) {
                            const rendered = nodes.get(String(node.id));
                            if (rendered && node.visual_role) {
                                roles += 1;
                                if (!rendered.classList.contains(node.visual_role)) failures.push('role mismatch: ' + node.id);
                            }
                        }
                        for (const edge of graph.edges || []) {
                            const rendered = paths.find(p => p.dataset.from === String(edge.from) && p.dataset.to === String(edge.to));
                            if (rendered) {
                                bindings += 1;
                                const dashed = !['LOCAL_CONTRACT','RECEIPT','NATIVE_RECEIPT'].includes(edge.binding);
                                if (rendered.classList.contains('declared') !== dashed) failures.push('binding mismatch: ' + edge.from + ' -> ' + edge.to);
                            }
                        }
                        return {roles,bindings,failures};
                    }""", graph)
                    assert not result["failures"], result
                    projection_checks["roles"] += result["roles"]
                    projection_checks["bindings"] += result["bindings"]

                assert page.locator("#catalog-rows tr").count() == (min(30, len(graphs)) or 1)
                if graphs:
                    assert page.locator("#diagram-view .graph-node").count() > 0
                    assert_projection(graphs[0])
                    first = page.locator("#diagram-view .graph-node").first
                    first.focus()
                    page.keyboard.press("Enter")
                    assert first.get_attribute("aria-pressed") == "true"
                    assert "Directional dependencies" in page.locator("#graph-inspector").inner_text()
                    page.locator("#clear-focus").click()
                    assert page.locator("#diagram-view .graph-node[aria-pressed=true]").count() == 0
                    page.locator("[data-view=mermaid]").click()
                    assert "flowchart" in page.locator("#mermaid-source").inner_text()
                    page.locator("[data-view=edges]").click()
                    assert page.locator("#edges-view").is_visible()
                    page.locator("[data-view=diagram]").click()
                    static_index = next((index for index, graph in enumerate(graphs) if graph.get("kind") == "STATIC_CALLS" and graph.get("nodes")), None)
                    if static_index is not None:
                        page.locator("#graph-select").select_option(str(static_index))
                        assert_projection(graphs[static_index])
                        page.locator("#graph-select").select_option("0")
                    if len(graphs) > 30:
                        page.locator("#next-graphs").click()
                        assert page.locator("#graph-page").inner_text().startswith("31")
                        page.locator("#previous-graphs").click()
                if blocks:
                    page.locator("#block-rows button").first.click()
                    contract = page.locator("#block-inspector").inner_text()
                    assert "Inputs" in contract and "Outputs" in contract
                    page.locator("#block-search").fill("zzzz_no_source_matches_1234")
                    assert page.locator("#block-count").inner_text().startswith("0 /")
                    page.locator("#reset-filters").click()
                    assert page.locator("#block-rows button").count() > 0
                inventory = model.get("inventory") or {}
                modules, workflows = inventory.get("python_modules") or [], inventory.get("workflows") or []
                with_functions = next((record for record in modules if record.get("functions")), None)
                if with_functions:
                    page.locator("#source-kind").select_option("python")
                    page.locator("#source-search").fill(with_functions["path"])
                    page.locator("#source-rows button").first.click()
                    assert page.locator("#source-inspector .function-detail").count() > 0
                    page.locator("#source-inspector .function-detail summary").first.click()
                    assert page.locator("#source-inspector .function-detail").first.evaluate("node => node.open")
                with_steps = next((record for record in workflows if any(job.get("steps") for job in record.get("jobs", []))), None)
                if with_steps:
                    page.locator("#source-search").fill(with_steps["path"])
                    page.locator("#source-kind").select_option("workflow")
                    page.locator("#source-rows button").first.click()
                    assert page.locator("#source-inspector .job-detail").count() == len(with_steps["jobs"])
                    assert page.locator("#source-inspector .step-list > li").count() == sum(len(job.get("steps", [])) for job in with_steps["jobs"])
                page.locator("#source-search").fill("")
                page.locator("#source-kind").select_option("all")
                coverage_rows = (model.get("coverage") or {}).get("rows") or []
                if coverage_rows:
                    page.locator("#coverage-rows .inspect-coverage").first.click()
                    coverage_text = page.locator("#coverage-inspector").inner_text().lower()
                    assert "unmeasured modules" in coverage_text and "comparison key" in coverage_text
                    assert "native evidence" in coverage_text and "freshness" in coverage_text
                    repo = coverage_rows[0]["repository"]
                    page.locator("#coverage-repository").select_option(repo)
                    assert page.locator("#coverage-rows tr[data-coverage]:visible").count() == sum(row["repository"] == repo for row in coverage_rows)
                    page.locator("#coverage-repository").select_option("all")
                    kind = coverage_rows[0]["observation_kind"]
                    page.locator("#coverage-kind").select_option(kind)
                    assert page.locator("#coverage-rows tr[data-coverage]:visible").count() == sum(row["observation_kind"] == kind for row in coverage_rows)
                    page.locator("#coverage-kind").select_option("all")
                page.locator("#theme-mode").select_option("light")
                assert page.locator("html").get_attribute("data-theme") == "light"
                light = page.evaluate("() => ({viewport: innerWidth, document: document.documentElement.scrollWidth})")
                assert light["document"] <= width + 1, light
                page.emulate_media(color_scheme="dark")
                page.locator("#theme-mode").select_option("system")
                page.wait_for_function("() => document.documentElement.dataset.theme === 'dark'")
                page.emulate_media(color_scheme="light")
                page.wait_for_function("() => document.documentElement.dataset.theme === 'light'")
                page.locator("#theme-mode").select_option("dark")
                dimensions = page.evaluate("""() => ({viewport:innerWidth, document:document.documentElement.scrollWidth,
                    graph:document.getElementById('diagram-view').scrollWidth,
                    graph_container:document.getElementById('diagram-view').clientWidth})""")
                assert dimensions["document"] <= width + 1, dimensions
                assert not errors, errors
                assert not requests, requests
                page.evaluate("() => window.scrollTo({top:0,behavior:'instant'})")
                screenshot = out / (name + ".png")
                page.screenshot(path=str(screenshot))
                if name == "desktop" and coverage_rows:
                    page.locator("#coverage").screenshot(path=str(out / "coverage-desktop.png"), style=".nav,.skip-link{visibility:hidden!important}")
                checks.append({"viewport": name, "width": width, "height": height,
                               "document_horizontal_overflow_px": max(0, dimensions["document"] - width),
                               "graph_internal_scroll": dimensions["graph"] > dimensions["graph_container"],
                               "page_errors": errors, "network_requests": requests,
                               "theme_and_source_interactions": "PASS", "system_theme_tracks_os": True,
                               "graph_role_and_binding_checks": projection_checks,
                               "coverage_filters_and_qualification": "PASS" if coverage_rows else "NO_SUPPLIED_COVERAGE",
                               "screenshot_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest()})
                page.close()
        finally:
            browser.close()
    receipt = {"schema": "missioncontrol.orchestration.browser_qa.v1", "head_sha": head,
               "evidence_class": "LOCAL_REPRODUCIBILITY", "merge_admission": "HOLD", "checks": checks}
    (out / "browser_qa_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--head", default="UNKNOWN")
    args = parser.parse_args()
    print(json.dumps(qa(args.html, args.out, args.head), indent=2))
