#!/usr/bin/env python3
"""MissionControl federation pulse overlay: historical evidence, not admission."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHA40 = re.compile(r"^[a-f0-9]{40}$")
SHA64 = re.compile(r"^[a-f0-9]{64}$")
CORE_REPOS = (
    "GBOGEB/gg_MATH", "GBOGEB/CODEX", "GBOGEB/ABACUS",
    "GBOGEB/cryoplant-project", "GBOGEB/pipeline-automation-hub",
)
HOPS = CORE_REPOS[:4]
STATUSES = {"QUEUED", "RUNNING", "TERMINAL_PASS", "TERMINAL_RED"}
PROOF = {"INSPECTED_ARTIFACT", "RUN_QUEUED", "RUN_RUNNING"}
SCHEMA = "missioncontrol.federation.observed_pulses/v1"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def exact_int(value, positive=False):
    return type(value) is int and (value > 0 if positive else value >= 0)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def identity_scope(row):
    files = row["scope"]
    return tuple(sorted((f["path"], f["sha256"]) for f in files))


def count_ratio(data, key):
    value = data[key]
    require(isinstance(value, dict) and set(value) == {"covered", "eligible"},
            key + " denominator missing")
    c, n = value["covered"], value["eligible"]
    require(exact_int(c) and exact_int(n, True) and c <= n,
            key + " coverage numerator invalid")
    return {"covered": c, "eligible": n,
            "pct": round(100.0 * c / n, 2)}


def validate(data):
    require(isinstance(data, dict) and data.get("schema") == SCHEMA,
            "unknown federation pulse schema")
    require(data.get("classification")
            == "HISTORICAL_EXACT_SOURCE_SNAPSHOT_NOT_LIVE",
            "snapshot must not claim live evidence")
    require(data.get("repositories") == list(CORE_REPOS),
            "five exact federation repositories required")
    methods = data.get("method_receipts")
    require(isinstance(methods, dict)
            and methods.get("pca_feature_count") == 6,
            "method family contract mismatch")
    for key, value in methods.items():
        if key == "pca_feature_count":
            continue
        require(value is None or exact_int(value),
                "invalid non-negative method count: " + key)
    rows = data.get("observations")
    require(isinstance(rows, list) and rows, "observations required")
    seen = set()
    for row in rows:
        require(isinstance(row, dict), "invalid observation")
        require(row.get("repo") in CORE_REPOS
                and isinstance(row.get("wave"), str) and row["wave"],
                "unrecognized repository/wave")
        require(exact_int(row.get("pulse"))
                and exact_int(row.get("run_id"), True)
                and exact_int(row.get("run_attempt"), True),
                "invalid exact native run/pulse/attempt identity")
        require(isinstance(row.get("head_sha"), str)
                and SHA40.fullmatch(row["head_sha"]),
                "head must be immutable 40-digit SHA")
        require(row.get("python") in {"3.10", "3.11", "3.12", "3.13"},
                "unknown Python stratum")
        require(row.get("status") in STATUSES
                and row.get("evidence_class") in PROOF,
                "unknown status/evidence class")
        require(row.get("native_replay_authenticated") is None
                and row.get("engineering_acceptance") is False,
                "unauthorized claim of native federation/QPS acceptance")
        key = (row["repo"], row["wave"], row["pulse"], row["python"])
        require(key not in seen, "duplicate pulse/Python receipt")
        seen.add(key)
        if row["status"].startswith("TERMINAL"):
            require(row["evidence_class"] == "INSPECTED_ARTIFACT"
                    and exact_int(row.get("artifact_id"), True)
                    and isinstance(row.get("receipt_sha256"), str)
                    and SHA64.fullmatch(row["receipt_sha256"]),
                    "terminal coverage needs native artifact reference")
            require(exact_int(row.get("tests_passed"))
                    and exact_int(row.get("tests_executed"))
                    and 0 <= row["tests_passed"] <= row["tests_executed"],
                    "test counts invalid")
            require(row["tests_passed"] == row["tests_executed"],
                    "source coverage evidence requires passing test selection")
            count_ratio(row, "line")
            count_ratio(row, "branch")
            scope = row.get("scope")
            require(isinstance(scope, list) and scope,
                    "instrumented file scope absent")
            require(len({s["path"] for s in scope}) == len(scope),
                    "duplicate scope path")
            for f in scope:
                require(set(f) == {"path", "sha256"}
                        and f["path"].startswith("scripts/")
                        and isinstance(f["sha256"], str)
                        and SHA64.fullmatch(f["sha256"]),
                        "invalid measured source digest/path")
            require(isinstance(row.get("selection"), str)
                    and row["selection"], "test selection missing")
        else:
            require(row["evidence_class"]
                    == ("RUN_QUEUED" if row["status"] == "QUEUED"
                        else "RUN_RUNNING"), "pending evidence state mismatch")
            require(all(row.get(k) is None for k in
                        ("line", "branch", "tests_passed", "tests_executed",
                         "scope", "artifact_id", "receipt_sha256")),
                    "pending event cannot contain speculative measurements")
    return rows


def rollup(data):
    rows = validate(data)
    groups = defaultdict(list)
    for r in rows:
        groups[(r["repo"], r["wave"], r["pulse"])].append(r)
    timeline = []
    for (repo, wave, pulse), cells in sorted(groups.items()):
        statuses = {x["status"] for x in cells}
        require(len(statuses) == 1, "cross-Python terminal state mismatch")
        lead = cells[0]
        terminal = lead["status"].startswith("TERMINAL")
        if terminal:
            for other in cells[1:]:
                require((lead["run_id"], lead["head_sha"], lead["selection"],
                         lead["tests_executed"], lead["line"], lead["branch"],
                         identity_scope(lead))
                        == (other["run_id"], other["head_sha"],
                            other["selection"], other["tests_executed"],
                            other["line"], other["branch"],
                            identity_scope(other)),
                        "cross-Python source, run, coverage or selection mismatch")
        timeline.append({
            "repo": repo, "wave": wave, "pulse": pulse,
            "head_sha": lead["head_sha"], "run_id": lead["run_id"],
            "status": lead["status"],
            "python_strata": sorted(x["python"] for x in cells),
            "source_artifact_receipts": len(cells) if terminal else 0,
            "tests_executed": lead["tests_executed"] if terminal else None,
            "line": count_ratio(lead, "line") if terminal else None,
            "branch": count_ratio(lead, "branch") if terminal else None,
            "selection": lead["selection"] if terminal else None,
            "source_scope": list(identity_scope(lead)) if terminal else None,
            "delta": {"line_pp": None, "branch_pp": None,
                      "new_lines": None, "new_branches": None,
                      "new_tests": None, "covered_lines_per_added_test": None,
                      "classification": "NO_COMPARABLE_PRIOR_PULSE"},
        })
    prior = {}
    for p in timeline:
        key = (p["repo"], p["wave"])
        before = prior.get(key)
        if p["line"] is not None and before and before["line"] is not None:
            compatible = (p["source_scope"] == before["source_scope"]
                          and all(p[k]["eligible"] == before[k]["eligible"]
                                  for k in ("line", "branch")))
            if compatible:
                tests = p["tests_executed"] - before["tests_executed"]
                newlines = p["line"]["covered"] - before["line"]["covered"]
                newbranches = p["branch"]["covered"] - before["branch"]["covered"]
                same_selection = (tests == 0
                                  and p["selection"] == before["selection"])
                p["delta"] = {
                    "line_pp": round(p["line"]["pct"]
                                     - before["line"]["pct"], 2),
                    "branch_pp": round(p["branch"]["pct"]
                                       - before["branch"]["pct"], 2),
                    "new_lines": newlines, "new_branches": newbranches,
                    "new_tests": tests,
                    "covered_lines_per_added_test":
                    round(newlines / tests, 3) if tests > 0 else None,
                    "classification":
                    "SAME_SELECTION" if same_selection else
                    "EXPANDED_OR_CHANGED_TEST_SELECTION",
                }
            else:
                p["delta"]["classification"] = "DIFFERENT_SOURCE_OR_DENOMINATOR"
        if p["line"] is not None:
            prior[key] = p
    proven = sorted({r["repo"] for r in rows
                    if r["status"].startswith("TERMINAL")})
    producer = sorted({r["repo"] for r in rows})
    pca = data["method_receipts"].get("pca_complete_rows")
    bt = data["method_receipts"].get("bt_terminal_pairs")
    positive = data["method_receipts"].get("bt_positive_outcomes")
    min_pca = max(50, 10 * data["method_receipts"]["pca_feature_count"])
    pca_state = ("UNKNOWN" if pca is None else
                 "ELIGIBLE_TO_ANALYZE" if pca >= min_pca
                 else "HOLD_INSUFFICIENT_N")
    bt_state = ("UNKNOWN" if bt is None or positive is None else
                "ELIGIBLE_TO_ANALYZE" if bt >= 30 and positive >= 5
                else "HOLD_INSUFFICIENT_N")
    output = {
        "schema": "missioncontrol.federation.wave_rollup/v1",
        "evidence_state": data["classification"],
        "observed_date": data["observed_date"],
        "repository_denominator": len(CORE_REPOS),
        "four_evidence_hops": list(HOPS),
        "fifth_repo_orchestration_only": CORE_REPOS[-1],
        "producer_repositories_observed": producer,
        "producer_breadth": {"observed": len(producer),
                             "eligible": len(CORE_REPOS)},
        "measured_coverage_repositories": proven,
        "measured_coverage_breadth": {"observed": len(proven),
                                      "eligible": len(CORE_REPOS)},
        "timeline": timeline,
        "method_readiness": {
            "PCA": {"complete_rows": pca, "min_complete_rows": min_pca,
                    "state": pca_state},
            "BT": {"terminal_pairs": bt, "positive_outcomes": positive,
                   "min_terminal_pairs": 30, "min_positive": 5,
                   "state": bt_state},
            "MIP": data["method_receipts"]["mip_verified_repairs"],
            "DMAIC": data["method_receipts"]["dmaic_controlled_iterations"],
            "REX": data["method_receipts"]["rex_controlled_root_ids"],
            "LDAB": data["method_receipts"]["ldab_diagnostic_root_ids"],
            "LLDB": data["method_receipts"]["lldb_debug_sessions"],
            "CENSUS_UNIQUE_ROOTS":
            data["method_receipts"]["unique_confirmed_roots"],
            "3P_RUNNER_QUEUE_SECONDS":
            data["method_receipts"]["runner_queue_wait_seconds"],
            "CREW_DISPATCHES": data["method_receipts"]["crew_dispatch_receipts"],
        },
        "native_cross_repo_chain_verified": None,
        "qps_owner_decision": "DEFER",
        "protected_main_admitted": None,
        "security_waiver": False,
        "authority_transfer": False,
    }
    return {**output, "receipt_sha256":
            hashlib.sha256(canonical(output).encode()).hexdigest()}


def render(result):
    escape = html.escape
    cells = []
    for p in result["timeline"]:
        c = p["line"]
        l = "UNKNOWN" if c is None else f"{c['covered']}/{c['eligible']} = {c['pct']:.2f}%"
        b = p["branch"]
        bt = "UNKNOWN" if b is None else f"{b['covered']}/{b['eligible']} = {b['pct']:.2f}%"
        delta = p["delta"]
        gain = ("UNKNOWN" if delta["line_pp"] is None else
                f"{delta['line_pp']:+.2f} pp / {delta['branch_pp']:+.2f} pp")
        url = ("https://github.com/" + p["repo"]
               + "/actions/runs/" + str(p["run_id"]))
        cells.append("<tr><td>" + escape(p["repo"].split("/")[-1]) +
                     "</td><td>" + escape(p["wave"]) + " · " +
                     str(p["pulse"]) + "</td><td><a href='" +
                     escape(url, quote=True) + "'>" + escape(p["status"]) +
                     "</a></td><td>" + escape(l) + "</td><td>" +
                     escape(bt) + "</td><td>" + escape(gain) +
                     "</td><td>" + escape(delta["classification"]) +
                     "</td></tr>")
    methods = result["method_readiness"]
    readiness = "".join("<tr><td>" + escape(k) + "</td><td>" +
                        escape(str(v)) + "</td></tr>"
                        for k, v in methods.items())
    breadth = result["measured_coverage_breadth"]
    summary = (f"{breadth['observed']}/{breadth['eligible']} "
               "repositories have inspected focused coverage receipts.")
    return ("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>MissionControl — Federation Observed Wave Metrics</title>
<style>body{font:15px system-ui;max-width:1180px;margin:36px auto;padding:0 16px;
background:#101726;color:#e6edf8}a{color:#8bceff}table{border-collapse:collapse;width:100%}
td,th{padding:10px;border-bottom:1px solid #42506b;text-align:left}th{color:#add5ff}
section{margin:24px 0;padding:20px;background:#1b2840;border-radius:12px}
small{color:#a9b9d0}</style></head><body><h1>Measured federation pulses</h1>
<p>""" + escape(result["observed_date"]) + """ · Historical observed evidence, NOT live polling</p>
<section><h2>Depth and breadth</h2><p>""" + escape(summary) +
            """</p><p>QPS source and test-scope gains are separate from authenticated
cross-repository replay and owner approval.</p></section><section><h2>Per-wave pulses</h2>
<table><tr><th>Repo</th><th>Wave · Pulse</th><th>Run state</th>
<th>Lines</th><th>Branches</th><th>Δ line / branch</th><th>Comparison class</th>
</tr>""" + "".join(cells) + """</table></section>
<section><h2>Readiness / missing telemetry</h2><table>""" +
            readiness + """</table><p>Unknown diagnostics remain unknown. PCA and BT
are advisory and never satisfy a security or QPS engineering admission gate.</p></section>
<small>Source: pinned observed-pulse JSON; immutable report digest """ +
            escape(result["receipt_sha256"]) + """; no worker dispatch or automatic merge.</small>
</body></html>""")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=HERE /
                    "FEDERATION_OBSERVED_PULSES_v1.json")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    incoming = json.loads(args.input.read_text(encoding="utf-8"))
    output = rollup(incoming)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "federation-wave-metrics.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    (args.out / "federation-wave.html").write_text(
        render(output), encoding="utf-8")
    print(canonical({"measured_breadth": output["measured_coverage_breadth"],
                     "pca": output["method_readiness"]["PCA"]["state"],
                     "bt": output["method_readiness"]["BT"]["state"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
