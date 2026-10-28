#!/usr/bin/env python3
"""Read-only N to N+j DMAIC control from the canonical issue_rank ledger.

This module never fetches GitHub, edits an issue, grants review/merge authority,
or treats a checkbox as verified evidence. Ledger writing/verification stays
with issue_rank.py. Comparisons use observed ledger rows, never invented pulses.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
import re
from pathlib import Path

SCHEMA = "issue-rank-wave-control/v1"
METRICS = ("open_issues", "open_prs", "tasks_done", "tasks_total",
           "criteria_untracked", "checklist_coverage", "dod_declared",
           "dov_declared", "measurable", "prs_red", "prs_unreviewed",
           "stale_21d", "actionable", "parked", "deadlocked")
PERCENT = frozenset(("checklist_coverage", "dod_declared", "dov_declared", "measurable"))
COUNTS = frozenset(METRICS) - PERCENT
SHA40 = re.compile(r"[0-9a-f]{40}\Z", re.I)
SHA64 = re.compile(r"[0-9a-f]{64}\Z", re.I)


def _time(value):
    if not isinstance(value, str):
        raise ValueError("pulse missing fetched_at")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid fetched_at") from exc
    if dt.utcoffset() is None:
        raise ValueError("fetched_at must include UTC offset")
    return dt


def _numeric(value, field):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError("invalid numeric telemetry: " + field)
    if value < 0 or (field in PERCENT and value > 1):
        raise ValueError("out-of-range telemetry: " + field)
    if field in COUNTS and not float(value).is_integer():
        raise ValueError("fractional count telemetry: " + field)
    return value


def _scope(row, scope):
    tele = row.get("telemetry")
    if not isinstance(tele, dict) or not isinstance(tele.get("scopes"), dict):
        raise ValueError("missing telemetry scopes")
    if scope not in tele["scopes"]:
        raise ValueError("missing scope: " + scope)
    metrics = tele["scopes"][scope]
    if not isinstance(metrics, dict):
        raise ValueError("invalid scope telemetry")
    values = {k: _numeric(metrics[k], k) for k in METRICS if k in metrics}
    if "open_issues" not in values or "open_prs" not in values:
        raise ValueError("open item denominator absent")
    for part, whole in (("tasks_done", "tasks_total"), ("prs_red", "open_prs"),
                        ("prs_unreviewed", "open_prs"), ("deadlocked", "open_issues"),
                        ("parked", "open_issues"), ("actionable", "open_issues")):
        if part in values and whole in values and values[part] > values[whole]:
            raise ValueError("impossible count subset: " + part)
    flow = metrics.get("flow") or {}
    burn = flow.get("net_burn_per_day") or {}
    if burn:
        for k in ("est", "lo", "hi"):
            v = burn.get(k)
            if type(v) not in (int, float) or not math.isfinite(v):
                raise ValueError("invalid net burn")
        if not burn["lo"] <= burn["est"] <= burn["hi"]:
            raise ValueError("inverted net burn interval")
    return metrics, values, flow, burn


def summarize(rows, scope="USER", j=3):
    """Compare j successive transitions; missing evidence is WITHHELD, never zero.

    A common set of source repositories and a common method version are required
    for comparable deltas. Different head SHAs are expected and retained only as
    a change count, not exposed. Overlapping Poisson windows remain descriptive.
    """
    if type(j) is not int or j < 3:
        raise ValueError("j must be an integer >= 3")
    rows = list(rows)
    if len(rows) < j + 1:
        return {"schema": SCHEMA, "scope": scope, "j": j,
                "status": "WITHHELD_MISSING_PULSES",
                "available": len(rows), "required": j + 1,
                "authority": "ADVISORY_ONLY", "merge_admission": "HOLD"}
    window = rows[-j - 1:]
    summaries, times, memberships, versions = [], [], [], []
    prev_receipt = None
    for index, row in enumerate(window):
        if type(row.get("seq")) is not int:
            raise ValueError("ledger seq missing")
        if index and row["seq"] != window[index - 1]["seq"] + 1:
            raise ValueError("non-contiguous ledger sequence")
        receipt = row.get("row_sha256")
        previous = row.get("prev_sha256")
        if receipt is not None and (not isinstance(receipt, str) or not SHA64.fullmatch(receipt)):
            raise ValueError("invalid 64-hex ledger receipt")
        if previous is not None and (not isinstance(previous, str) or not SHA64.fullmatch(previous)):
            raise ValueError("invalid previous receipt shape")
        if index and previous != prev_receipt:
            raise ValueError("mismatched previous ledger receipt link")
        prev_receipt = receipt
        tele = row.get("telemetry") or {}
        t = _time(tele.get("fetched_at"))
        if times and t <= times[-1]:
            raise ValueError("pulse time did not advance")
        times.append(t)
        heads = tele.get("heads")
        if not isinstance(heads, dict) or not heads:
            raise ValueError("head census missing")
        if any(not isinstance(k, str) or not k.startswith("GBOGEB/") or
               not (v is None or isinstance(v, str) and SHA40.fullmatch(v)) for k, v in heads.items()):
            raise ValueError("invalid 40-hex source head provenance")
        memberships.append(frozenset(heads))
        method = tele.get("method") or {}
        versions.append(method.get("version"))
        if not versions[-1]:
            raise ValueError("method version missing")
        raw, metrics, flow, burn = _scope(row, scope)
        summaries.append({
            "label": "N" if index == 0 else "N+" + str(index),
            "ledger_seq": row["seq"],
            "fetched_at": tele["fetched_at"],
            "open_issues": metrics["open_issues"],
            "open_prs": metrics["open_prs"],
            "measurable": metrics.get("measurable"),
            "dod_declared": metrics.get("dod_declared"),
            "dov_declared": metrics.get("dov_declared"),
            "criteria_untracked": metrics.get("criteria_untracked"),
            "net_burn_per_day": burn or None,
            "flow_status": flow.get("status", "UNKNOWN"),
            "head_count": len(heads),
            "source_head_changes": 0 if not index else sum(
                heads.get(k) != window[index - 1]["telemetry"]["heads"].get(k)
                for k in memberships[index] | memberships[index - 1]),
            "row_sha256": row.get("row_sha256"),
        })
    comparable = all(s == memberships[0] for s in memberships) and len(set(versions)) == 1
    reasons = []
    if any(s != memberships[0] for s in memberships):
        reasons.append("SCOPE_MEMBERSHIP_DRIFT")
    if len(set(versions)) != 1:
        reasons.append("METHOD_VERSION_DRIFT")
    if any((r.get("telemetry") or {}).get("method", {}).get("relations_complete") is False
           for r in window):
        reasons.append("INCOMPLETE_NESTED_RELATIONS")
    if any(not x.get("row_sha256") for x in summaries):
        reasons.append("MISSING_LEDGER_RECEIPT")
    if reasons:
        comparable = False
    first = _scope(window[0], scope)[1]
    last = _scope(window[-1], scope)[1]
    diff = {}
    if comparable:
        diff = {k: round(last[k] - first[k], 6) for k in METRICS
                if k in first and k in last}
        for k in PERCENT:
            if k in diff:
                diff[k + "_pp"] = round(100 * diff.pop(k), 3)
    matched_ticked = scope_added = None
    if comparable:
        deltas = [(r["telemetry"].get("delta") or {}) for r in window[1:]]
        if all(d.get("baseline") is False and
               type(d.get("tasks_ticked_net")) is int and
               type(d.get("scope_added_net")) is int for d in deltas):
            matched_ticked = sum(d["tasks_ticked_net"] for d in deltas)
            scope_added = sum(d["scope_added_net"] for d in deltas)
    independent_windows = True
    for earlier, later, a in zip(times, times[1:], window):
        fd = (_scope(a, scope)[2]).get("window_days")
        if not isinstance(fd, (int, float)) or fd <= 0 or (later - earlier).total_seconds() < fd * 86400:
            independent_windows = False
    flows = [_scope(r, scope)[2] for r in window]
    burns = [_scope(r, scope)[3] for r in window]
    valid_final_flow = all(f.get("window_days") == 14 and f.get("status") == "BURNING_DOWN"
                           and b and b.get("lo", -math.inf) > 0
                           for f, b in zip(flows, burns))
    evidence_burn = independent_windows and valid_final_flow
    if not valid_final_flow:
        reasons.append("MISSING_OR_MIXED_FINAL_14D_FLOW")
    if not independent_windows:
        reasons.append("OVERLAPPING_OR_UNKNOWN_FLOW_WINDOWS")
    return {
        "schema": SCHEMA, "scope": scope, "j": j,
        "status": "COMPARABLE_ADVISORY" if comparable else "WITHHELD_UNMATCHED",
        "comparison": {"from_seq": window[0]["seq"], "to_seq": window[-1]["seq"],
                       "matched_source_membership": comparable,
                       "method_version": versions[0] if len(set(versions)) == 1 else "DRIFT",
                       "delta": diff,
                       "matched_items_ticked_net": matched_ticked,
                       "matched_items_scope_added_net": scope_added},
        "waves": summaries,
        "control": {"independent_flow_windows": independent_windows,
                    "sustained_positive_burn_observed": bool(comparable and evidence_burn),
                    "formally_verified_dod": False,
                    "closure_credit": 0,
                    "notes": reasons},
        "dmaic": {"DEFINE": "DoD / DoV coverage remains self-reported",
                  "MEASURE": "N through N+j ledger evidence, exact scope and method",
                  "ANALYZE": "matched deltas separated from rolling-window rates",
                  "IMPROVE": "matched tick movement separated from criteria growth",
                  "CONTROL": "no green admission from advisory ranks"},
        "authority": "ADVISORY_ONLY", "merge_admission": "HOLD"
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--scope", default="USER")
    ap.add_argument("--j", type=int, default=3)
    ap.add_argument("--out", type=Path, help="optional local JSON output; never auto-publish")
    args = ap.parse_args(argv)
    from issue_rank import verify_ledger  # canonical verification owner
    count = verify_ledger(args.ledger)
    rows = [json.loads(x) for x in args.ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
    if len(rows) != count:
        raise ValueError("ledger changed during read; retry under single-writer lock")
    result = summarize(rows, scope=args.scope, j=args.j)
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
