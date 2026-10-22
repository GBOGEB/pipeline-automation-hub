"""Deterministic read-only disjoint-worker *proposal* for QPS Metric Atlas.

Existing census.request() remains the source contract. This module consumes and
revalidates that exact manifest and creates a path/route-disjoint review plan.
It NEVER dispatches a worker, commits code, touches private materials, or
transfers merge / engineering authority. Slots are HYPOTHETICAL ceilings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import deque
from pathlib import Path

from .census import ALLOWED_REPOS, SCHEMA, CensusError, canonical, request

PLAN_SCHEMA = "code-purple.w6.disjoint-readers.v1"
ROUTES = ("native_checks", "coverage_catalog")


class DisjointScaleError(ValueError):
    pass


def _check_manifest(manifest):
    """Reconstruct exact expected manifest; reject states/ids forged in transit."""
    if (not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA or
            manifest.get("mode") != "READ_ONLY" or
            manifest.get("dispatch_enabled") is not False or
            manifest.get("authority_transfer") is not False or
            manifest.get("engineering_acceptance") is not False):
        raise DisjointScaleError("untrusted census source/authority")
    selected, deferred = manifest.get("requests"), manifest.get("not_dispatched")
    if not isinstance(selected, list) or not isinstance(deferred, list):
        raise DisjointScaleError("missing original and deferred populations")
    if (type(manifest.get("max_fanout")) is not int or
            not 1 <= manifest["max_fanout"] <= 3):
        raise DisjointScaleError("invalid fanout ceiling")
    joined = selected + deferred
    if len(joined) != 3 or len({item.get("lane") for item in joined if isinstance(item, dict)}) != 3:
        raise DisjointScaleError("source population lost or duplicated")
    heads = {}
    selectors = set()
    for r in joined:
        if not isinstance(r, dict) or r.get("repo") != ALLOWED_REPOS.get(r.get("lane")):
            raise DisjointScaleError("foreign or malformed source lane")
        heads[r["lane"]] = r.get("expected_sha")
        if r["expected_sha"] is not None:
            selectors.add(r.get("selector"))
    if len(selectors) > 1:
        raise DisjointScaleError("mixed route selectors are not canonical")
    # All-unknown source manifests still have a valid default selector.
    selector = next(iter(selectors), "all")
    try:
        expected = request(manifest["wave"], heads, selector=selector,
                           max_fanout=manifest["max_fanout"])
    except (CensusError, TypeError, KeyError) as exc:
        raise DisjointScaleError("cannot verify exact census producer") from exc
    if expected != manifest:
        raise DisjointScaleError("source manifest mutated or stale")
    return expected


def plan(manifest, *, slots=2, source_priority=None):
    """Bounded deterministic plan with one source lease per round.

    slots are a *planning* capacity, not authenticated runner capacity.
    source_priority may change fair presentation order, never lane authority.
    """
    m = _check_manifest(manifest)
    if type(slots) is not int or not 1 <= slots <= 3:
        raise DisjointScaleError("hypothetical slot ceiling must be integer 1..3")
    if source_priority is None:
        lane_order = list(ALLOWED_REPOS)
    else:
        if (not isinstance(source_priority, (list, tuple)) or
                len(source_priority) != 3 or
                set(source_priority) != set(ALLOWED_REPOS) or
                len(set(source_priority)) != 3):
            raise DisjointScaleError("priority must be an exact unique three-lane permutation")
        lane_order = list(source_priority)
    existing = {x["lane"]: x for x in m["requests"]}
    pending = {}
    for lane in lane_order:
        q = existing.get(lane)
        if q is None:
            continue
        routes = ROUTES if q["selector"] == "all" else (q["selector"],)
        pending[lane] = deque(routes)
    ordered = [lane for lane in lane_order if lane in pending]
    rounds = []
    tasks = []
    seen = set()
    # Rotate fairness between rounds, while no two slots share a repo lease.
    cursor = 0
    while any(pending.values()):
        eligible = ordered[cursor:] + ordered[:cursor]
        active = [lane for lane in eligible if pending[lane]][:slots]
        row = []
        for slot, lane in enumerate(active, 1):
            q = existing[lane]
            route = pending[lane].popleft()
            identity = (q["repo"], q["expected_sha"], route)
            if identity in seen:
                raise DisjointScaleError("duplicate route or same-head lease")
            seen.add(identity)
            ticket = "W6-" + hashlib.sha256(canonical([m["wave"], q["request_id"], route]).encode()).hexdigest()[:16]
            item = {"ticket": ticket, "round": len(rounds)+1, "slot": slot,
                    "lane": lane, "repo": q["repo"], "sha": q["expected_sha"],
                    "route": route, "request_id": q["request_id"],
                    "lease_key": q["repo"]+"@"+q["expected_sha"],
                    "state": "DRY_RUN_NOT_DISPATCHED", "run_id": None,
                    "job_id": None, "run_attempt": None, "native_evidence": None}
            row.append(item); tasks.append(item)
        rounds.append(row)
        cursor = (ordered.index(active[-1])+1) % len(ordered)
    if len(tasks) > 6 or len({x["ticket"] for x in tasks}) != len(tasks):
        raise DisjointScaleError("unbounded or duplicate task population")
    for row in rounds:
        if len(row) > slots or len({x["lease_key"] for x in row}) != len(row):
            raise DisjointScaleError("overlapping write/source ownership in one round")
    result = {
        "schema": PLAN_SCHEMA, "source_schema": SCHEMA, "wave": m["wave"],
        "mode": "OFFLINE_DISJOINT_SOURCE_REVIEW_ONLY", "execution_authority": "NONE",
        "capacity_class": "HYPOTHETICAL_NOT_MEASURED", "hypothetical_slots": slots,
        "priority_order": lane_order,
        "eligible_repositories": 3, "selected_repositories": len(ordered),
        "deferred_repositories": len(m["not_dispatched"]),
        "known_head_deferred": sum(x["state"] == "DEFERRED_FANOUT_LIMIT" for x in m["not_dispatched"]),
        "source_head_unknown": m["unknown_head_repos"],
        "route_population": len(tasks), "route_cap": 6,
        "round_count": len(rounds), "rounds": rounds,
        "deferred": m["not_dispatched"],
        "dispatch_performed": False, "workers_launched": 0,
        "source_writers_launched": 0, "native_tests_credited": None,
        "matched_coverage_change": None, "worker_hours": None,
        "causal_root_closures": None, "merge_admission": "HOLD",
        "qps_engineering_acceptance": False, "authority_transfer": False,
    }
    result["plan_sha256"] = hashlib.sha256(canonical(result).encode()).hexdigest()
    return result


def verify_plan(manifest, proposed):
    if not isinstance(proposed, dict) or proposed.get("schema") != PLAN_SCHEMA:
        raise DisjointScaleError("missing plan contract")
    base = {k:v for k,v in proposed.items() if k != "plan_sha256"}
    if proposed.get("plan_sha256") != hashlib.sha256(canonical(base).encode()).hexdigest():
        raise DisjointScaleError("plan checksum mismatch")
    expected = plan(manifest, slots=proposed.get("hypothetical_slots"),
                    source_priority=proposed.get("priority_order"))
    if expected != proposed:
        raise DisjointScaleError("plan mutation or unsupported execution authority")
    return proposed


def mermaid_dag():
    return '''flowchart LR
  MI["W6-01 | MASTER INPUT source / SHA"] --> CP["W6-02 | CODE PURPLE census"]
  CP --> MC["W6-03 | Mission Control bounded planning"]
  MC --> G1["W6-04 | Disjoint round 1"]
  G1 --> G2["W6-05 | Disjoint round 2 / route fan-in"]
  G2 --> G3["W6-06 | Subsequent bounded round"]
  G3 --> EV["W6-07 | Run/job/attempt & ZIP receipt gate"]
  EV --> OW["W6-08 | Source owner / independent review HOLD"]
  OW -.->|N+1 feedback only| N["W6-09 | NEW pulse recensus"]
  classDef master fill:#CEE8E4,stroke:#156F70,color:#184244
  classDef purple fill:#DFD5F2,stroke:#694AA8,color:#342355
  classDef mission fill:#D1E3F5,stroke:#32669E,color:#173D64
  classDef maroon fill:#F1D3DB,stroke:#A44962,color:#61283A
  classDef green fill:#D2EACB,stroke:#357A50,color:#224B30
  class MI master
  class CP purple
  class MC,G1,G2,G3 mission
  class EV,OW maroon
  class N green
'''


def mermaid_sipoc():
    return '''flowchart LR
  S["S 01 | Source owners & private QPS"] --> I["I 02 | Authenticated heads, canonical census"]
  I --> P["P 03 | Bounded, disjoint DRY-RUN plan"]
  P --> O["O 04 | Typed routes, proposed tickets, UNKNOWN receipts"]
  O --> C["C 05 | Maintainers, Mission Control, QPS reviewers"]
  C -.->|N+1 no authority transfer| R["CONTROL | new evidence epoch"]
  classDef master fill:#CEE8E4,stroke:#156F70,color:#184244
  classDef purple fill:#DFD5F2,stroke:#694AA8,color:#342355
  classDef mission fill:#D1E3F5,stroke:#32669E,color:#173D64
  classDef maroon fill:#F1D3DB,stroke:#A44962,color:#61283A
  classDef green fill:#D2EACB,stroke:#357A50,color:#224B30
  class S,I master
  class P mission
  class O maroon
  class C,R green
'''


def mermaid_spline():
    return '''flowchart LR
  N0["N0 | Freeze eligible source cohort"] --> N1["N+1 | 1-repo read-only pilot"]
  N1 --> N2["N+2 | 2-repo read-only pilot"]
  N2 --> N3["N+3 | 3-repo review proposal"]
  N3 -.->|requires independent native receipts| H["HOLD / next admissible epoch"]
  classDef purple fill:#DFD5F2,stroke:#694AA8,color:#342355
  classDef mission fill:#D1E3F5,stroke:#32669E,color:#173D64
  classDef maroon fill:#F1D3DB,stroke:#A44962,color:#61283A
  class N0,N1,N2 mission
  class N3 purple
  class H maroon
'''


def main(argv=None):
    p=argparse.ArgumentParser(description="Offline bounded, disjoint census planning (never dispatches)")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--diagrams", type=Path, required=True)
    p.add_argument("--slots", type=int, default=2)
    args=p.parse_args(argv)
    try:
        manifest=json.loads(args.manifest.read_text(encoding="utf-8"))
        result=plan(manifest,slots=args.slots)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        args.diagrams.mkdir(parents=True,exist_ok=True)
        for name,diagram in (("W6_DISJOINT_DAG.mmd",mermaid_dag()),
                             ("W6_DISJOINT_SIPOC.mmd",mermaid_sipoc()),
                             ("W6_DISJOINT_SPLINE.mmd",mermaid_spline())):
            (args.diagrams/name).write_text(diagram,encoding="utf-8")
        print(json.dumps({"mode":result["mode"],"routes":result["route_population"],
                          "rounds":result["round_count"],"dispatch_performed":False}))
        return 0
    except (OSError,ValueError,TypeError,KeyError) as exc:
        p.exit(2,"DISJOINT_SCALE_HOLD: "+str(exc)+"\n")


if __name__ == "__main__":
    raise SystemExit(main())
