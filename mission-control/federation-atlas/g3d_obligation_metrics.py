#!/usr/bin/env python3
"""CODE PURPLE read-only five-obligation metric roll-up.

This is a non-authoritative *view* of pinned native/source evidence. It may not
resolve reviews, accept QPS, close causal roots, or dispatch workers.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SCHEMA = "missioncontrol.code_purple.g3d_obligation_snapshot.v1"
OUT_SCHEMA = "missioncontrol.code_purple.g3d_obligation_metrics.v1"
PARENTS = ("GOVERNANCE", "ADMISSION", "CREDENTIALS", "BROWSER", "FEDERATION")
SHA = re.compile(r"[a-f0-9]{40}\Z")


def need(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError("G3D_METRICS_FAIL_CLOSED: " + reason)


def rate(num: int, den: int) -> float:
    need(type(num) is int and type(den) is int and den > 0 and 0 <= num <= den,
         "invalid integer count and denominator")
    return round(100.0 * num / den, 4)


def validate(snapshot: dict) -> dict:
    need(isinstance(snapshot, dict) and snapshot.get("schema") == SCHEMA, "schema")
    need(snapshot.get("authority_transfer") is False and
         snapshot.get("merge_admission") == "HOLD" and
         snapshot.get("security_waiver") is False, "authority custody")
    parents = snapshot.get("parents")
    need(isinstance(parents, list) and
         tuple(p["id"] for p in parents) == PARENTS, "five fixed obligations")
    need(all(p["status"] in ("HOLD", "PARTIAL", "BLOCKED_OWNER")
             for p in parents), "cannot precredit closed obligations")
    need(all(isinstance(p.get("canonical_issue"), str)
             and p["canonical_issue"].startswith("https://github.com/GBOGEB/")
             for p in parents), "canonical issue reference")
    history = snapshot.get("history")
    need(isinstance(history, list) and len(history) >= 2, "source pulse history")
    clocks = [h.get("n") for h in history]
    need(all(type(n) is int and n >= 0 for n in clocks)
         and clocks == sorted(set(clocks)), "monotone unique pulse clock")
    denominator = history[0].get("workflow_denominator")
    need(type(denominator) is int and denominator > 0, "workflow count")
    shas = set()
    for h in history:
        need(h.get("workflow_denominator") == denominator,
             "non-matched workflow population")
        need(type(h.get("classified")) is int and
             0 <= h["classified"] <= denominator, "classified count")
        need(isinstance(h.get("source_sha"), str)
             and SHA.fullmatch(h["source_sha"]), "exact source identity")
        need(h["source_sha"] not in shas, "repeated source is not independent pulse")
        shas.add(h["source_sha"])
        need(h.get("evidence_class") in
             ("EXACT_SOURCE_AUDIT", "NATIVE_POLICY_AUDIT"), "source evidence class")
    evidence = snapshot.get("terminal")
    need(isinstance(evidence, list), "terminal provenance")
    for e in evidence:
        need(e["parent"] in PARENTS and SHA.fullmatch(e["source_sha"]),
             "terminal source binding")
        need(e.get("conclusion") in
             ("success", "failure", "cancelled", "skipped", "queued",
              "in_progress", "UNKNOWN"), "terminal conclusion")
        need(type(e.get("run_id")) is int and e["run_id"] > 0 and
             type(e.get("attempt")) is int and e["attempt"] > 0,
             "run and attempt identity")
        job = e.get("job_id")
        need(job is None or (type(job) is int and job > 0), "job ID")
        need(e["conclusion"] not in ("success", "failure") or job is not None,
             "terminal run without job")
    fingerprints = snapshot.get("fingerprints")
    need(isinstance(fingerprints, list) and
         len({f["id"] for f in fingerprints}) == len(fingerprints),
         "deduplicated fingerprint labels")
    for f in fingerprints:
        c = f.get("observed_occurrences")
        need(c is None or (type(c) is int and c >= 1),
             "unknown occurrence is not zero")
        need(f.get("accepted_root_id") is None,
             "source-owned root disposition absent")
    need(snapshot.get("accepted_causal_root_closures") == 0,
         "accepted causal closures cannot be inferred")
    need(snapshot.get("human_worker_hours") is None and
         snapshot.get("runner_capacity_slots") is None,
         "worker capacity unknown, not zero")
    c = snapshot.get("coverage")
    need(isinstance(c, dict) and c.get("evidence_class") ==
         "HISTORICAL_MATCHED_SCOPE_ONLY", "coverage cannot be federation-wide")
    for kind in ("statements", "branches"):
        q = c.get(kind)
        need(isinstance(q, dict) and q["scope"] == c["scope"] and
             type(q["before"]) is int and type(q["after"]) is int and
             type(q["denominator"]) is int and
             0 <= q["before"] <= q["denominator"] and
             0 <= q["after"] <= q["denominator"] and
             q["denominator"] > 0, "historical coverage scope/denominator")
    forecasts = snapshot.get("forecasts")
    need(isinstance(forecasts, list) and len(forecasts) == 2 and
         [f.get("target_n") for f in forecasts] ==
         [clocks[-1] + 1, clocks[-1] + 2],
         "rolling N+2 target ordering")
    need(all(f.get("issued_before_outcome") is True and
             f.get("outcome") is None and
             f.get("probability") is None for f in forecasts),
         "unobserved prediction must stay frozen")
    return snapshot



def summarize_live_epoch(e: dict, fixed: dict) -> dict:
    """Separate fixed-cohort history, new arrivals and PR-head native proof.

    This is a frozen observation, not a live API claim. The external GitHub
    source/main must be re-read before any current-main admission assertion.
    """
    need(isinstance(e, dict) and
         e.get("schema") == "missioncontrol.code_purple.g3f_live_source_epoch.v1",
         "live-epoch schema")
    need(e.get("evidence_class") ==
         "EXACT_SOURCE_AUDIT_PLUS_NATIVE_PR_GOVERNANCE", "source class")
    need(e.get("merge_admission") == "HOLD" and
         e.get("authority_transfer") is False and
         e.get("security_waiver") is False and
         e.get("accepted_root_closures") == 0, "authority custody")
    need(all(e.get(x) is None for x in (
        "fresh_authenticated_breadth", "source_matched_new_coverage",
        "actual_human_worker_hours", "runner_slots")),
        "unknown cannot be interpreted as zero")
    h, before, repaired, main = (
        e["historical_fixed"], e["pre_repair"],
        e["repair_head"], e["main_source_at_observation"])
    for row in (h, before, repaired, main):
        need(SHA.fullmatch(row.get("source_sha", "")), "live SHA")
        den, got = row.get("workflow_total"), row.get("classified")
        need(type(den) is int and den > 0 and
             type(got) is int and 0 <= got <= den,
             "live cohort denominator and classified numerator")
    need(h["workflow_total"] == fixed["workflow_denominator"] and
         h["source_sha"] == fixed["source_sha"] and
         h["classified"] == fixed["classified"], "frozen cohort lineage")
    need(before["workflow_total"] == repaired["workflow_total"] ==
         main["workflow_total"], "matched 209-denominator wave")
    need(main["classified"] == repaired["classified"] and
         repaired["classified"] >= before["classified"],
         "candidate/main source count regression")
    arrivals = e["arrivals_since_fixed"]
    retired = e["retired_since_fixed"]
    need(isinstance(arrivals, list) and isinstance(retired, list) and
         len(arrivals) == len(set(arrivals)) and
         len(retired) == len(set(retired)) and
         not (set(arrivals) & set(retired)) and
         all(isinstance(name, str) and name.endswith(".yml")
             for name in arrivals + retired), "unique workflow identities")
    need(h["workflow_total"] + len(arrivals) - len(retired) ==
         main["workflow_total"], "workflow inflow/outflow conservation")
    resolved = repaired["newly_classified"]
    need(isinstance(resolved, list) and
         len(resolved) == len(set(resolved)) and
         set(resolved) <= set(arrivals) and
         len(resolved) == repaired["classified"] - before["classified"],
         "newly classified source members")
    native = repaired["native_governance"]
    need(native["conclusion"] == "success" and
         all(type(native[x]) is int and native[x] > 0
             for x in ("run_id", "run_attempt", "job_id")),
         "terminal native source identity")
    need(native["unit_tests_run"] == native["unit_tests_passed"] and
         native["unit_tests_failed"] == 0 and
         native["unit_tests_skipped"] == 0 and
         native["extra_tests_run"] == native["extra_tests_passed"] and
         native["report_check"] == "PASS",
         "native test denominator/report parity")
    need(main.get("native_main_run_id") is None, "no main CI credit")
    need(all(SHA.fullmatch(main[x]) for x in
             ("policy_blob_sha", "report_blob_sha")), "main binary blob identity")
    protection = e["effective_governance_at_observation"]
    need(protection["required_approving_reviews"] == 0 and
         protection["required_status_rules"] == 0 and
         protection["require_last_push_approval"] is False and
         protection["required_review_thread_resolution"] is False,
         "do not forge effective review protection")
    return {
        "observed_at_utc": e["observed_at_utc"],
        "evidence_class": e["evidence_class"],
        "historical_cohort_total": h["workflow_total"],
        "new_arrivals": len(arrivals), "retirements": len(retired),
        "pre_repair": {
            "source_sha": before["source_sha"],
            "classified": before["classified"],
            "total": before["workflow_total"],
            "unclassified": before["workflow_total"]-before["classified"]},
        "repair_head": {
            "source_sha": repaired["source_sha"],
            "classified": repaired["classified"],
            "total": repaired["workflow_total"],
            "unclassified": repaired["workflow_total"]-repaired["classified"],
            "native_governance_run": native["run_id"],
            "native_job": native["job_id"],
            "native_run_attempt": native["run_attempt"],
            "unit_tests_passed": native["unit_tests_passed"],
            "extra_tests_passed": native["extra_tests_passed"],
            "scope": "PR_HEAD_EXACT_SHA_ONLY",
            "technical_gate": "PASS"},
        "main_source": {
            "source_sha": main["source_sha"],
            "classified": main["classified"],
            "total": main["workflow_total"],
            "native_main_gate": "UNKNOWN_NOT_CREDITED"},
        "newly_classified_names": resolved,
        "private_census_breadth": None,
        "actual_human_worker_hours": None,
        "root_closures_verified": 0,
        "effective_independent_admission": False,
        "source_repair_pass_not_programme_admission": True
    }


def summarize(snapshot: dict) -> dict:
    s = validate(snapshot)
    rows = s["history"]
    den = rows[0]["workflow_denominator"]
    series = [
        {"n": r["n"], "source_sha": r["source_sha"],
         "classified": r["classified"], "total": den,
         "remaining": den - r["classified"],
         "classified_pct": rate(r["classified"], den),
         "evidence_class": r["evidence_class"]}
        for r in rows
    ]
    velocities = [
        {"from_n": a["n"], "to_n": b["n"],
         "classified_gain": b["classified"] - a["classified"]}
        for a, b in zip(rows, rows[1:])
    ]
    last = rows[-1]
    cover = {}
    for kind in ("statements", "branches"):
        x = s["coverage"][kind]
        cover[kind] = {
            "before": x["before"], "after": x["after"],
            "denominator": x["denominator"],
            "change_percentage_points":
                round(rate(x["after"], x["denominator"]) -
                      rate(x["before"], x["denominator"]), 4),
            "evidence_class": "HISTORICAL_ONLY_NOT_CURRENT_FEDERATION"
        }
    terminal = []
    for e in s["terminal"]:
        terminal.append({
            **e,
            "qualifies_for_admission": False,
            "reason": "independent effective controls and full DoV absent"
        })
    live = (summarize_live_epoch(s["live_epoch"], rows[-1])
            if s.get("live_epoch") is not None else None)
    return {
        "schema": OUT_SCHEMA,
        "authority_transfer": False, "merge_admission": "HOLD",
        "parents_total": 5, "parents_verified_closed": 0,
        "parent_status": {p["id"]: p["status"] for p in s["parents"]},
        "owner_issues": {p["id"]: p["canonical_issue"] for p in s["parents"]},
        "workflow_scope": "ABACUS_EXACT_SAME_188_SOURCE_DEFINITIONS",
        "workflow_source_history": series,
        "source_progress_velocity": velocities,
        "source_current_unclassified": den - last["classified"],
        "source_current_unclassified_scope": "HISTORICAL_FIXED_188_NOT_LIVE",
        "latest_source_epoch": live,
        "source_current_multiple_matches": s["source_multiple_matches"],
        "source_goal_achieved": (last["classified"] == den and
                                 s["source_multiple_matches"] == 0),
        "terminal_receipts": terminal,
        "native_full_governance_pass": False,
        "historical_coverage": cover,
        "fresh_census_breadth": None,
        "historical_census_observed": s["historical_census"]["observed"],
        "historical_census_eligible": s["historical_census"]["eligible"],
        "fingerprints_count": len(s["fingerprints"]),
        "accepted_causal_root_closures": 0,
        "total_causal_roots": None,
        "human_worker_hours": None, "runner_capacity_slots": None,
        "maturity": {"M1": "PARTIAL", "M2_LOCAL": "PARTIAL",
                     "M2_FEDERATION": "HOLD", "M3": "HOLD"},
        "PCA_federation_readiness": "NOT_QUALIFIED",
        "BT_federation_readiness": "NOT_QUALIFIED",
        "six_sigma_capability": "NOT_IDENTIFIABLE",
        "rolling_forecasts_unscored": s["forecasts"]
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path,
                    default=Path(__file__).with_name(
                        "G3D_OBLIGATION_SNAPSHOT_v1.json"))
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    out = summarize(json.loads(a.input.read_text(encoding="utf-8")))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print("G3D_METRICS=PASS; SOURCE_CLASSIFIED=" +
          str(out["workflow_source_history"][-1]["classified"]) +
          "; PARENTS_CLOSED=0; ADMISSION=HOLD")


if __name__ == "__main__":
    main()
