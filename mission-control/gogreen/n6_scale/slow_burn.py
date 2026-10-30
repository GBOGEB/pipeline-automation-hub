"""N+6 MissionControl bounded CREW planner: no autonomous merge/dispatch.

Reuses CREW roles and source-bound N3 concepts; schedules a *proposal* only.
GitHub Actions is the actual bounded runner, governed by queue admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "missioncontrol.n6.crew_intake/v1"
OUT_SCHEMA = "missioncontrol.n6.crew_plan/v1"
SHA = re.compile(r"[0-9a-f]{40}\Z")
ROLES = {"SCOUT", "READER", "ENGINEER", "SMOKER", "DOCTOR",
         "DOCKMASTER", "QA", "ANALYST", "ORCHESTRATOR"}
REPOS = {"GBOGEB/ABACUS", "GBOGEB/CODEX", "GBOGEB/cryoplant-project",
         "GBOGEB/gg_MATH", "GBOGEB/pipeline-automation-hub"}
PRIORITY = {"P0": 4, "P1": 3, "P2": 2, "P3": 1}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def valid_int(value):
    return type(value) is int and value >= 0


def path_normalized(value):
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    if value.startswith("/") or value.endswith("/") or "//" in value:
        return False
    return all(x not in ("", ".", "..") for x in value.split("/"))


def collides(a, b):
    """Parent/child wildcard lease collisions count as a shared writer."""
    aa, bb = a.removesuffix("/**"), b.removesuffix("/**")
    return aa == bb or (a.endswith("/**") and bb.startswith(aa + "/")) or (
        b.endswith("/**") and aa.startswith(bb + "/")
    )


def validate(intake):
    require(isinstance(intake, dict) and intake.get("schema") == SCHEMA,
            "unrecognized intake schema")
    require(intake.get("execution") == "BRANCH_ONLY_NO_MERGE",
            "branch-only operation required")
    require(intake.get("authority_transfer") is False, "authority transfer forbidden")
    queue = intake.get("queue")
    require(isinstance(queue, dict), "queue observation missing")
    for key in ("queued", "running", "queued_limit", "running_limit"):
        require(valid_int(queue.get(key)), "invalid queue count: " + key)
    require(queue["queued_limit"] > 0 and queue["running_limit"] > 0,
            "queue limits must be positive")
    require(isinstance(intake.get("observed_utc"), str)
            and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ",
                             intake["observed_utc"]) is not None,
            "UTC observation required")
    lanes = intake.get("lanes")
    require(isinstance(lanes, list) and 1 <= len(lanes) <= 30,
            "bounded candidate lane population required")
    observed = set()
    for lane in lanes:
        require(isinstance(lane, dict), "malformed lane")
        ident, repo, head = lane.get("id"), lane.get("repo"), lane.get("head_sha")
        require(isinstance(ident, str) and re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,40}", ident)
                and ident not in observed, "duplicate or invalid lane id")
        observed.add(ident)
        require(repo in REPOS and isinstance(head, str) and SHA.fullmatch(head),
                "unknown repository or unbound source SHA")
        require(lane.get("role") in ROLES, "unregistered CREW operational role")
        require(lane.get("priority") in PRIORITY, "unsupported lane priority")
        require(lane.get("state") in ("READY", "FIRST_RED", "WAITING"),
                "invalid lifecycle state")
        require(valid_int(lane.get("first_red")) and
                valid_int(lane.get("zero_covered_files")), "invalid burden counts")
        paths = lane.get("paths")
        require(isinstance(paths, list) and paths and
                all(path_normalized(p) for p in paths) and len(set(paths)) == len(paths),
                "invalid or duplicate path leases")
        require(type(lane.get("budget_minutes")) is int and
                1 <= lane["budget_minutes"] <= 30, "unbounded runner budget")
        require(lane.get("merge_authorized") is False, "worker cannot authorize merge")
        cov = lane.get("coverage")
        if cov is not None:
            require(isinstance(cov, dict) and cov.get("source_sha") == head
                    and type(cov.get("covered")) is int
                    and type(cov.get("eligible")) is int
                    and 0 <= cov["covered"] <= cov["eligible"] and cov["eligible"] > 0,
                    "coverage population not matched to exact source")
    return intake


def make_plan(intake, max_slots=2, horizon=6):
    validate(intake)
    require(type(max_slots) is int and 1 <= max_slots <= 3,
            "bounded concurrent runners 1..3")
    require(type(horizon) is int and 1 <= horizon <= 12,
            "bounded horizon must be 1..12")
    queue = intake["queue"]
    pressure = queue["queued"] >= queue["queued_limit"] or (
        queue["running"] >= queue["running_limit"]
    )
    ordered = sorted(intake["lanes"], key=lambda x: (
        -PRIORITY[x["priority"]], -x["first_red"], -x["zero_covered_files"], x["id"]
    ))
    admitted = []
    deferred = []
    for lane in ordered:
        reason = None
        if lane["state"] == "WAITING":
            reason = "WAITING_FOR_DEPENDENCY"
        elif pressure or queue["running"] + len(admitted) >= queue["running_limit"]:
            reason = "DEFER_QUEUE_PRESSURE"
        elif len(admitted) >= max_slots:
            reason = "BOUNDED_SLOT_CAPACITY"
        else:
            for active in admitted:
                if active["repo"] == lane["repo"] and any(
                    collides(p, q) for p in lane["paths"] for q in active["paths"]
                ):
                    reason = "SOURCE_PATH_LEASE_CONFLICT"
                    break
        if reason:
            deferred.append({"id": lane["id"], "reason": reason})
            continue
        admitted.append(lane)

    def ticket(x):
        key = ":".join((x["repo"], x["head_sha"], x["id"],
                        "|".join(sorted(x["paths"]))))
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]

    return {
        "schema": OUT_SCHEMA,
        "observed_utc": intake["observed_utc"],
        "horizon_target": f"N+{horizon}",
        "admission": "HOLD",
        "mode": "BRANCH_TEST_PROPOSAL",
        "queue_admission": "DEFER" if pressure else "EVALUATED",
        "observed_queue": dict(queue),
        "slots": [{"ticket": ticket(x), "id": x["id"], "role": x["role"],
                   "repo": x["repo"], "head_sha": x["head_sha"],
                   "paths": x["paths"], "budget_minutes": x["budget_minutes"],
                   "state": "PROPOSED_NOT_DISPATCHED"} for x in admitted],
        "deferred": deferred,
        "candidate_population": len(ordered),
        "proposed_slots": len(admitted),
        "worker_runs_started": 0,
        "terminal_native_run_receipts": 0,
        "measured_coverage_delta": None,
        "measured_zero_coverage_reduction": None,
        "merge_authorized": False,
        "authority_transfer": False,
        "mip_dmaic": {
            "define": "six controlled source-bound checkpoints, not six inferred successes",
            "measure": "queue pressure, first-red, zero-covered file cohort, source-matched coverage",
            "analyse": "priority, root-recurrence, zero-coverage yield, lease conflicts",
            "improve": "only independent path-disjoint bounded branch jobs",
            "control": "exact-head CI, matched denominator, no merge until independent gates"
        },
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--intake", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-slots", type=int, default=2)
    a = p.parse_args(argv)
    out = make_plan(json.loads(a.intake.read_text(encoding="utf-8")),
                    max_slots=a.max_slots)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n",
                     encoding="utf-8", newline="\n")
    print(json.dumps({"plan": out["horizon_target"], "slots": out["proposed_slots"],
                      "deferred": len(out["deferred"]),
                      "queue": out["queue_admission"], "merge": out["admission"]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
