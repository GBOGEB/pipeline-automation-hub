#!/usr/bin/env python3
"""Render the latest observed pulse separately from immutable historical measurements."""
from __future__ import annotations
import argparse
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = "missioncontrol.federation.latest_status/v1"


def validate(status, history):
    if status.get("schema") != SCHEMA or status.get("snapshot_kind") != "HISTORICAL_READBACK_NOT_LIVE":
        raise ValueError("unrecognized, non-frozen status source")
    if status.get("program_pulse") != "N+2":
        raise ValueError("N+2 requires its own append-only event")
    rows = history.get("observations")
    if not isinstance(rows, list) or len(rows) != 7:
        raise ValueError("historical source population missing")
    qps = [r for r in rows if r["repo"] == "GBOGEB/cryoplant-project"]
    if len(qps) != 6 or {r["pulse"] for r in qps} != {0, 1, 2}:
        raise ValueError("QPS P0/P1/P2 must be preserved")
    original_scope = {(f["path"], f["sha256"]) for f in qps[0]["scope"]}
    for r in qps:
        if ({(f["path"], f["sha256"]) for f in r["scope"]} != original_scope
            or r["line"]["eligible"] != 135 or r["branch"]["eligible"] != 48):
            raise ValueError("QPS source identity or denominator changed")
    qps_pulses = []
    for n in (0, 1, 2):
        two = [r for r in qps if r["pulse"] == n]
        if len(two) != 2 or len({r["python"] for r in two}) != 2:
            raise ValueError("cross-Python source receipt missing")
        a, b = two
        for key in ("head_sha", "run_id", "line", "branch", "tests_passed", "selection", "scope"):
            if a[key] != b[key]:
                raise ValueError("native Python population mismatch")
        qps_pulses.append(a)
    last = qps_pulses[-1]
    if (last["line"] != {"covered": 135, "eligible": 135}
        or last["branch"] != {"covered": 48, "eligible": 48}
        or last["tests_passed"] != 51 or last["run_id"] != 38707522432):
        raise ValueError("latest QPS coverage cannot be invented")
    past = [r for r in rows if r["repo"] == "GBOGEB/ABACUS"]
    cur = status["w70"]
    if (len(past) != 1 or past[0]["status"] != "QUEUED"
        or past[0]["run_id"] != cur["run_id"]
        or past[0]["head_sha"] != cur["head_sha"]):
        raise ValueError("W70 observed terminal run identity mismatch")
    if (cur["state"] != "TERMINAL_FAIL" or cur["line"] is not None
        or cur["branch"] is not None or cur["tests_passed"] != 21
        or cur["tests_executed"] != 21):
        raise ValueError("W70 terminal first-red does not validate source coverage")
    atlas = status["atlas"]
    if (atlas["state"] != "PASS_MERGED" or atlas["tests_passed"] != 58
        or atlas["tests_executed"] != 58):
        raise ValueError("Atlas native evidence missing")
    if status["source_tuple_reconciled"] is not False or status["qps_accepted"] is not False:
        raise ValueError("fixtures cannot grant whole-chain or QPS authority")
    fleet = status["census"]
    if (fleet["core_repos"], fleet["branches"], fleet["open_prs"], fleet["open_issues"]) != (5, 613, 38, 146):
        raise ValueError("incorrect N+2 fleet snapshot; append N+3 to refresh")
    for sha in status["main_sha"].values():
        if not re.fullmatch("[a-f0-9]{40}", sha):
            raise ValueError("invalid exact-main SHA")
    stages = status["timeline"]
    if [r["program_pulse"] for r in stages] != ["N", "N+1", "N+2"]:
        raise ValueError("historical N pulses must stay ordered")
    if [r["w70"] for r in stages] != ["QUEUED", "FAILED", "FAILED"]:
        raise ValueError("historical W70 transitions lost")
    return {"schema": "missioncontrol.federation.latest_rollup/v1",
            "pulse": "N+2", "historical_status_preserved": True,
            "qps_source_pulse": "P2",
            "qps_line": last["line"], "qps_branch": last["branch"],
            "qps_tests_per_python": 51, "qps_pulses": qps_pulses,
            "w70": cur, "atlas": atlas, "census": fleet,
            "stages": stages, "source_tuple_reconciled": False,
            "native_cross_repo_chain_verified": None,
            "qps_engineering_decision": "DEFER",
            "security_waiver": False, "measured_breadth": {"verified": 1, "eligible": 5}}


def render(result):
    esc = html.escape
    r = result
    lines = []
    for p in r["qps_pulses"]:
        lp = 100 * p["line"]["covered"] / p["line"]["eligible"]
        bp = 100 * p["branch"]["covered"] / p["branch"]["eligible"]
        lines.append(f'<div class="pulse"><b>P{p["pulse"]}</b>'
                     f'<div><div class="track"><span style="width:{lp:.2f}%;background:#69d9b5"></span></div>'
                     f'<div class="track"><span style="width:{bp:.2f}%;background:#91aff7"></span></div></div>'
                     f'<span>{lp:.2f}% / {bp:.2f}% <small>{p["tests_passed"]} tests/Python</small></span></div>')
    rows = "".join("<tr><td>" + esc(p["program_pulse"]) + "</td><td>" + esc(p["w70"]) +
                   "</td><td>" + esc(p["atlas"]) + "</td><td>" +
                   str(p["open_prs"] if p["open_prs"] is not None else "UNKNOWN") + "</td><td>" +
                   str(p["branches"] if p["branches"] is not None else "UNKNOWN") + "</td></tr>"
                   for p in r["stages"])
    return ("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MissionControl — latest federation pulse N+2</title>
<style>
body{font:15px/1.6 system-ui;background:#101726;color:#e8eff9;max-width:1100px;margin:25px auto;padding:0 18px}
h1{font-size:30px;letter-spacing:-.04em}.hint{padding:14px;border:1px solid #927146;background:#30261f;border-radius:9px}
section{margin:17px 0;padding:19px;background:#1b2940;border:1px solid #40516c;border-radius:12px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.cards>div{background:#263952;border-radius:10px;padding:15px}.num{font-size:26px;font-weight:780}
.ok{color:#69d9b5}.red{color:#ffa396}.muted,small{color:#b5c7de}
table{border-collapse:collapse;width:100%}td,th{text-align:left;border-bottom:1px solid #465873;padding:10px}
.pulse{display:grid;grid-template-columns:46px 1fr 170px;gap:12px;align-items:center;margin:18px 0}
.track{height:13px;background:#34425a;overflow:hidden;border-radius:8px;margin:4px 0}
.track span{display:block;height:100%}small{display:block;font-size:12px}
a{color:#9dd6ff}</style></head><body>
<p class="muted">CODE PURPLE · Historical exact-source readback · 15 October 2026</p>
<h1>Latest observed pulse (N+2)</h1>
<p class="hint">Snapshot, not live polling. The original W70 QUEUED observation is preserved in the prior dataset.
Its run subsequently finished FAILURE at source-coverage validation. QPS P2 is its latest scoped coverage pulse;
project N+2 is not an artificial QPS P3.</p>
<div class="cards">
<div><small>QPS scoped line + branch</small><div class="num ok">100% / 100%</div>135/135 lines · 48/48 branches</div>
<div><small>ABACUS W70 native</small><div class="num red">TERMINAL RED</div>21/21 tests · coverage UNKNOWN</div>
<div><small>MissionControl #532</small><div class="num ok">58/58 PASS</div>Merged, native artifact produced</div>
<div><small>Five-repo PRs / refs</small><div class="num">38 / 613</div>38 open PRs · 613 branches</div>
<div><small>Inspected coverage breadth</small><div class="num">1 / 5</div>Not full fleet coverage</div>
</div><section><h2>Project checkpoint progression</h2>
<table><tr><th>Program wave</th><th>W70</th><th>Atlas</th><th>Open PRs</th><th>Branches</th></tr>""" + rows + """</table></section>
<section><h2>QPS actual coverage pulses (P0 → P2)</h2>
<p class="muted">Mint = lines; blue = branches. Source digests and denominators match.</p>""" +
           "".join(lines) + """</section>
<section><h2>First-red and control gates</h2>
<p><a href="https://github.com/GBOGEB/ABACUS/actions/runs/38707957236">W70 run #38707957236</a>:
<code>coverage must include exactly one owned source file</code>; <code>--source</code>
overrode <code>--include</code>. Observed 31/76 manifestations open (not 31 unique roots).
Actual module line/branch coverage: UNKNOWN.</p>
<p>Four-hop provider source SHA differs from consumer synthetic fixtures. Authenticated native chain:
UNKNOWN. QPS engineering decision: DEFER. Merge security controls: HOLD.</p></section>
<p class="muted">No GitHub Pages deployment, job dispatch, merge, security waiver, or issue closure.
Regenerate only from an independently verified later N+3 observation.</p></body></html>""")


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--status",type=Path,default=Path(__file__).with_name("FEDERATION_STATUS_N2_v1.json"))
    ap.add_argument("--history",type=Path,default=Path(__file__).with_name("FEDERATION_OBSERVED_PULSES_v1.json"))
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    report=validate(json.loads(args.status.read_text(encoding="utf-8")),
                    json.loads(args.history.read_text(encoding="utf-8")))
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"federation-latest.html").write_text(render(report),encoding="utf-8")
    (args.out/"federation-latest.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",
                                                   encoding="utf-8")
    print(json.dumps({"pulse":report["pulse"],"w70":report["w70"]["state"],
                      "qps":report["qps_source_pulse"],"pr":report["census"]["open_prs"]}))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
