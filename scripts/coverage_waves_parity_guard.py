#!/usr/bin/env python3
"""Collection-parity guard for a pytest JUnit report (CODE PURPLE method v1, vector E).

Reads the JUnit XML that `pytest --junitxml` wrote and reports passed, failed,
errors, skipped, xfailed and xpassed separately. Strict xfails are pinned
production defects: they are counted on their own and never as passes.

Fails (exit 1) when:
- zero tests were collected (an empty run is a failure, not a pass);
- fewer than --expected-min tests were collected (collection parity lost);
- any test failed or errored (strict XPASS shows up here as a failure);
- fewer than --expect-xfail tests xfailed (a pinned defect went missing);
- any test was skipped while --max-skips is 0 (no silent skips).

Writes a JSON summary with --out and a Markdown table to $GITHUB_STEP_SUMMARY when set.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def count(junit: Path) -> dict:
    root = ET.parse(junit).getroot()
    c = {"collected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfailed": 0, "xpassed": 0}
    skips, xfails = [], []
    for case in root.iter("testcase"):
        c["collected"] += 1
        nodeid = f'{case.get("classname", "")}::{case.get("name", "")}'
        if case.find("failure") is not None:
            msg = case.find("failure").get("message", "")
            c["xpassed" if "XPASS(strict)" in msg else "failed"] += 1
        elif case.find("error") is not None:
            c["errors"] += 1
        elif (s := case.find("skipped")) is not None:
            if s.get("type") == "pytest.xfail":
                c["xfailed"] += 1
                xfails.append(nodeid)
            else:
                c["skipped"] += 1
                skips.append(f'{nodeid}: {s.get("message", "")}')
        else:
            c["passed"] += 1
    return {"counts": c, "skips": skips, "xfails": xfails}


def verdict(r: dict, expected_min: int, expect_xfail: int, max_skips: int) -> list[str]:
    c = r["counts"]
    why = []
    if c["collected"] == 0:
        why.append("ZERO_TESTS_COLLECTED")
    elif c["collected"] < expected_min:
        why.append(f"PARITY_LOST collected={c['collected']} < expected_min={expected_min}")
    if c["failed"] or c["errors"] or c["xpassed"]:
        why.append(f"RED failed={c['failed']} errors={c['errors']} xpassed_strict={c['xpassed']}")
    if c["xfailed"] < expect_xfail:
        why.append(f"PINNED_DEFECT_MISSING xfailed={c['xfailed']} < expect_xfail={expect_xfail}")
    if c["skipped"] > max_skips:
        why.append(f"SKIPS_OVER_CAP skipped={c['skipped']} > max_skips={max_skips}")
    return why


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("junit", type=Path)
    ap.add_argument("--expected-min", type=int, required=True)
    ap.add_argument("--expect-xfail", type=int, default=0)
    ap.add_argument("--max-skips", type=int, default=0)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)

    r = count(a.junit)
    why = verdict(r, a.expected_min, a.expect_xfail, a.max_skips)
    r.update(expected_min=a.expected_min, expect_xfail=a.expect_xfail, max_skips=a.max_skips,
             verdict="FAIL" if why else "PASS", reasons=why)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8")

    c = r["counts"]
    line = " ".join(f"{k}={v}" for k, v in c.items())
    print(f"COLLECTION_PARITY {r['verdict']} {line} expected_min={a.expected_min} expect_xfail={a.expect_xfail}")
    for x in r["xfails"]:
        print(f"  XFAIL (pinned defect, not a pass) {x}")
    for s in r["skips"]:
        print(f"  SKIP {s}")
    for w in why:
        print(f"  REASON {w}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### Collection parity: {r['verdict']}\n\n| " + " | ".join(c) + " |\n|"
                    + "---|" * len(c) + "\n| " + " | ".join(str(v) for v in c.values()) + " |\n\n")
            f.write("Strict xfails are pinned production defects (PD-L6-*) and are not counted as passes.\n\n")
            for w in why:
                f.write(f"- **{w}**\n")
    return 1 if why else 0


if __name__ == "__main__":
    sys.exit(main())
