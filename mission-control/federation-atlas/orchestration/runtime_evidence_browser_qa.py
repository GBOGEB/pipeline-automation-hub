#!/usr/bin/env python3
"""Check the offline runtime replay in the existing Playwright browser owner.

Only recorded HTML is loaded. Controls replay its timestamps; this checker never
executes generators, dispatches workers, or publishes the page.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re


def states_at(tasks, moment):
    result = {}
    for identity, row in tasks.items():
        state = "pending"
        for event in row["events"]:
            if event["at_seconds"] <= moment:
                state = event["state"]
        result[identity] = state
    return result


def check_browser(markup, expected_head, executable=None):
    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as playwright:
        options = {"headless": True}
        if executable:
            options["executable_path"] = executable
        browser = playwright.chromium.launch(**options)
        version = browser.version
        try:
            for label, width, height in (("desktop", 1440, 1000), ("mobile", 390, 844)):
                context = browser.new_context(viewport={"width": width, "height": height},
                                              device_scale_factor=1)
                checks, errors, console_errors, requests = [], [], [], []
                view = {"viewport": label, "width": width, "height": height, "checks": checks}
                results.append(view)
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda message: console_errors.append(message.text)
                        if message.type == "error" else None)

                def forbid_external(route):
                    requests.append(route.request.url)
                    route.abort()

                page.route(re.compile(r"^https?://"), forbid_external)

                def check(name, passed, observed=None):
                    checks.append({"name": name, "pass": bool(passed), "observed": observed})

                def timeline():
                    return page.locator("#timeline .row").evaluate_all(
                        "rows => Object.fromEntries(rows.map(row => [row.dataset.id, row.querySelector('.state').textContent]))")

                def slider():
                    return float(page.locator("#time").input_value())

                def close(left, right):
                    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)

                try:
                    # Virtual time makes interval assertions independent of CI
                    # load while still executing the actual browser JS controls.
                    page.clock.install(time=datetime(2026, 1, 1, tzinfo=timezone.utc))
                    page.set_content(markup, wait_until="load")
                    page.wait_for_function("document.documentElement.dataset.ready === 'true'")
                    page.clock.pause_at(datetime(2026, 1, 1, 1, tzinfo=timezone.utc))
                    data = page.locator("#evidence").evaluate("el => JSON.parse(el.textContent)")
                    tasks, end = data["tasks"], data["metrics"]["elapsed_seconds"]
                    if not isinstance(tasks, dict) or not tasks or type(end) not in {int, float} or not math.isfinite(end) or end <= 0:
                        raise ValueError("replay requires nonempty recorded tasks and a positive finite elapsed time")
                    view["recorded_elapsed_seconds"] = end
                    count = len(tasks)
                    check("source_head_matches", data.get("source_sha") == expected_head, data.get("source_sha"))
                    check("displayed_source_head_matches", page.locator("header code").inner_text() == expected_head)
                    check("registered_task_denominator", data["counts"]["registered_tasks"] == count, count)
                    successful = sum(row["state"] == "succeeded" for row in tasks.values())
                    check("success_count_and_card", data["counts"]["successful_tasks"] == successful
                          and page.locator("#cards .num").first.inner_text() == f"{successful}/{count}")
                    check("timeline_and_table_population", page.locator("#timeline .row").count() == count
                          and page.locator("#tasks tr").count() == count, count)
                    check("task_identity_population", set(timeline()) == set(tasks), sorted(timeline()))
                    check("initial_terminal_states", timeline() == states_at(tasks, end), timeline())
                    check("slider_accepts_exact_end", close(slider(), end), {"slider": slider(), "end": end})
                    overflow = page.evaluate("Math.max(0, document.documentElement.scrollWidth - innerWidth)")
                    check("no_document_horizontal_overflow", overflow == 0, overflow)
                    check("no_live_execution_claim", "does not launch work" in page.locator("body").inner_text())

                    # The first click starts from the initial completed view.
                    # A range step that rounds below max must not prevent restart.
                    page.locator("#play").click()
                    page.clock.run_for(55)
                    tick = min(end, max(end / 160, .02))
                    check("direct_replay_restarts_from_terminal", close(slider(), tick),
                          {"slider": slider(), "expected_first_tick": tick})
                    check("direct_replay_uses_recorded_states", timeline() == states_at(tasks, tick), timeline())
                    page.locator("#reset").click()
                    check("reset_restores_zero_states", slider() == 0 and timeline() == states_at(tasks, 0), timeline())
                    page.locator("#play").click()
                    page.clock.run_for(55)
                    check("replay_advances_after_reset", close(slider(), tick), slider())
                    if tick < end:
                        page.locator("#play").click()
                        paused = slider()
                        page.clock.run_for(100)
                        check("pause_stops_replay", slider() == paused
                              and page.locator("#play").inner_text() == "Replay", slider())
                    page.locator("#reset").click()
                    page.locator("#time").evaluate(
                        "el => { el.value = el.max; el.dispatchEvent(new Event('input', {bubbles:true})); }")
                    check("slider_max_reaches_all_terminal_events", close(slider(), end)
                          and timeline() == states_at(tasks, end), {"slider": slider(), "states": timeline()})
                    page.locator("#reset").click()
                    page.clock.run_for(100)
                    check("reset_cancels_timer", slider() == 0 and page.locator("#play").inner_text() == "Replay")
                    check("no_page_errors", not errors, errors)
                    check("no_console_errors", not console_errors, console_errors)
                    check("no_external_requests", not requests, requests)
                except Exception as exc:
                    view["error"] = {"type": type(exc).__name__, "message": str(exc)}
                    check("browser_interactions_completed", False, str(exc))
                finally:
                    context.close()
        finally:
            browser.close()
    return version, results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--browser-executable", help="Optional existing Chromium executable; default is Playwright's installed Chromium")
    args = parser.parse_args(argv)
    receipt = {"schema": "missioncontrol.runtime-outcome.browser-qa.v1",
               "observed_at": datetime.now(timezone.utc).isoformat(),
               "source_sha": args.head, "html_sha256": None, "viewports": [],
               "scope": "OFFLINE_RECORDED_EXECUTION_UI", "native_attestation": False,
               "dispatch_authorized": False, "success": False}
    try:
        if re.fullmatch(r"[0-9a-f]{40}", args.head) is None:
            raise ValueError("--head must be an exact 40-character Git SHA")
        raw = args.html.read_bytes()
        receipt["html_sha256"] = hashlib.sha256(raw).hexdigest()
        receipt["browser_version"], receipt["viewports"] = check_browser(raw.decode("utf-8"), args.head, args.browser_executable)
        receipt["success"] = (len(receipt["viewports"]) == 2 and
                              all(check["pass"] for view in receipt["viewports"] for check in view["checks"]))
    except Exception as exc:
        receipt["error"] = {"type": type(exc).__name__, "message": str(exc)}
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / "browser-qa.json"
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    failed = [{"viewport": view["viewport"], "check": check["name"], "observed": check["observed"]}
              for view in receipt["viewports"] for check in view["checks"] if not check["pass"]]
    print(json.dumps({"success": receipt["success"], "source_sha": args.head,
                      "receipt": str(target), "failed_checks": failed, "error": receipt.get("error")}))
    return 0 if receipt["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
