#!/usr/bin/env python3
"""Disjoint read-only recovery frontier, consuming canonical EVERRED evidence.

The canonical owners still perform census (everred/harvest.py), failure metrics,
Actions timing, and issue ranking. This consumer does NOT issue GitHub writes,
dispatch workers, create owners, or infer verified root closure.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

SCHEMA = "gogreen.root-frontier.v1"
SOURCE_SCHEMA = "everred.census/1.0"
PUBLIC = {
    "ABACUS": "GBOGEB/ABACUS",
    "CODEX": "GBOGEB/CODEX",
    "GGMATH": "GBOGEB/gg_MATH",
    "PAH": "GBOGEB/pipeline-automation-hub",
    "QET": "GBOGEB/Q_engineering_tools",
}
PRIORITY = {"P0": 300, "P1": 200, "P2": 100, "P3": 20}
MAROON = "MAROON_SECURITY"
OWNER = "RETURN_OWNER_GOVERNANCE"
FIRST = "FIRST_RED_READER"
REPAIR = "EVERRED_ROOT_REPAIR"
CONTROL = "GOGREEN_CONTROL_REPEAT"


def _utc(text):
    if not isinstance(text, str):
        raise ValueError("SOURCE_CLOCK_MISSING")
    try:
        t = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("SOURCE_CLOCK_INVALID") from exc
    if t.utcoffset() is None:
        raise ValueError("SOURCE_CLOCK_NO_OFFSET")
    return t.astimezone(timezone.utc)


def _count(value, field):
    if type(value) is not int or value < 0:
        raise ValueError("INVALID_NONNEGATIVE_COUNT:" + field)
    return value


def _candidate(root):
    if not isinstance(root, dict):
        raise ValueError("INVALID_ROOT_ROW")
    rid = root.get("id")
    if not isinstance(rid, str) or not re.fullmatch(r"[A-Z0-9]+-RC-\d{4}-\d{4}", rid):
        raise ValueError("INVALID_ROOT_ID")
    short = rid.split("-RC-", 1)[0]
    repo = PUBLIC.get(short)
    if repo is None:
        return None  # unlisted/private repo: aggregate only, no public identity
    severity = root.get("severity")
    if severity not in PRIORITY:
        raise ValueError("UNSUPPORTED_SEVERITY")
    occurrences = _count(root.get("occurrences"), "root occurrences")
    prs = root.get("affected_prs")
    if not isinstance(prs, list) or any(type(n) is not int or n <= 0 for n in prs):
        raise ValueError("INVALID_AFFECTED_PRS")
    state = root.get("state")
    dims = root.get("dims") or {}
    if not isinstance(dims, dict):
        raise ValueError("INVALID_ROOT_DIMS")
    security = dims.get("security")
    if root.get("class") == "SECURITY_OR_POLICY" or security in {"RED", "UNKNOWN"}:
        family = MAROON
    elif state == "BLOCKED_AUTHORITY" or root.get("class") == "CONTROL_PLANE_DRIFT":
        family = OWNER
    elif state in ("VERIFIED_FIXED", "PRODUCER_GREEN"):
        family = CONTROL
    else:
        family = REPAIR
    consumers = root.get("consumers") or []
    if not isinstance(consumers, list):
        raise ValueError("INVALID_CONSUMERS")
    impacted = len(set(prs))
    impact = PRIORITY[severity] + min(occurrences, 120) + min(impacted, 30) * 4 + min(len(consumers), 20) * 2
    if family == CONTROL:
        impact *= 0.5  # lifecycle recurrence, not new source repair
    return {"id": rid, "repo": repo, "family": family,
            "severity": severity, "evidence_state": state or "UNKNOWN",
            "observed_occurrences": occurrences,
            "affected_pr_count": impacted, "declared_consumer_count": len(consumers),
            "impact_proxy": round(impact, 3),
            "action": ("OWNER_DECISION" if family == OWNER else
                       "SECURITY_ADJUDICATION" if family == MAROON else
                       "REPEAT_DISTINCT_SHA" if family == CONTROL else
                       "SOURCE_OWNED_REPAIR"),
            "path_lease": "UNVERIFIED_NO_WRITE",
            "first_red_line": "NOT_IN_SOURCE",
            "formal_closure_credit": 0}


def _unmatched(row):
    if not isinstance(row, dict):
        raise ValueError("INVALID_UNMATCHED_ROW")
    repos = row.get("repos")
    if not isinstance(repos, list) or not repos or any(not isinstance(r, str) for r in repos):
        raise ValueError("INVALID_UNMATCHED_REPOS")
    if len(repos) != 1 or repos[0] not in PUBLIC.values():
        return None  # any private or ambiguous source is withheld; no mixed public packet
    signature = row.get("signature")
    if not isinstance(signature, str) or not signature.strip():
        raise ValueError("INVALID_SIGNATURE")
    occurrences = _count(row.get("occurrences"), "unmatched occurrences")
    prs = row.get("prs") or []
    if not isinstance(prs, list) or any(type(n) is not int or n <= 0 for n in prs):
        raise ValueError("INVALID_UNMATCHED_PRS")
    # Public-safe stable routing key, *not* a substitute for the full owner-only log.
    opaque = hashlib.sha256((repos[0] + "\0" + signature).encode("utf-8")).hexdigest()[:16]
    return {"id": "SIG-" + opaque, "repo": repos[0], "family": FIRST,
            "severity": "UNCLASSIFIED", "evidence_state": "UNMATCHED_CANDIDATE",
            "observed_occurrences": occurrences,
            "affected_pr_count": len(set(prs)), "declared_consumer_count": 0,
            "impact_proxy": round(100 + min(occurrences, 120) + min(len(set(prs)), 30) * 4, 3),
            "action": "READ_FIRST_FAILED_JOB_AND_CLASSIFY",
            "path_lease": "UNVERIFIED_NO_WRITE",
            "first_red_line": "NEEDS_NATIVE_JOB_LOG",
            "formal_closure_credit": 0}


def build(census, *, now=None, max_waves=20, capacity=8, per_repo=2):
    """Stage a maximum of max_waves disjoint *candidate* cohorts, not real worker dispatches.

    Each wave limits the same repository to per_repo slots, and one candidate
    per root family in the diversity pass. File/path leases and owners are
    UNKNOWN; candidates must be qualified independently before any mutation.
    """
    if not isinstance(census, dict) or census.get("schema") != SOURCE_SCHEMA:
        raise ValueError("EVERRED_SCHEMA_MISMATCH")
    if type(max_waves) is not int or not 1 <= max_waves <= 64:
        raise ValueError("INVALID_WAVE_CAP")
    if type(capacity) is not int or not 1 <= capacity <= 32:
        raise ValueError("INVALID_CAPACITY")
    if type(per_repo) is not int or not 1 <= per_repo <= capacity:
        raise ValueError("INVALID_REPO_CAP")
    generated = _utc(census.get("generated_at"))
    now = now or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("NOW_MISSING_OFFSET")
    now = now.astimezone(timezone.utc)
    if generated > now:
        raise ValueError("SOURCE_FROM_FUTURE")
    roots, unmatched = census.get("roots"), census.get("unmatched")
    if not isinstance(roots, list) or not isinstance(unmatched, list):
        raise ValueError("EVERRED_ROWS_MISSING")
    packets, privacy_skipped = [], 0
    for source, parser in ((roots, _candidate), (unmatched, _unmatched)):
        for row in source:
            p = parser(row)
            if p is None:
                privacy_skipped += 1
                continue
            packets.append(p)
    keys = [p["id"] for p in packets]
    if len(set(keys)) != len(keys):
        raise ValueError("DUPLICATE_SOURCE_IDENTITY")
    packets.sort(key=lambda p: (-p["impact_proxy"], p["family"], p["repo"], p["id"]))
    remaining = list(packets)
    waves = []
    for wave in range(max_waves):
        if not remaining:
            break
        assigned, repo_use, family_use = [], Counter(), set()
        for diversify in (True, False):
            for p in list(remaining):
                if len(assigned) >= capacity:
                    break
                if repo_use[p["repo"]] >= per_repo:
                    continue
                if diversify and p["family"] in family_use:
                    continue
                assigned.append(p)
                remaining.remove(p)
                repo_use[p["repo"]] += 1
                family_use.add(p["family"])
        if not assigned:
            break
        waves.append({"wave": "N" if wave == 0 else "N+" + str(wave),
                      "count": len(assigned),
                      "families": dict(sorted(Counter(p["family"] for p in assigned).items())),
                      "packets": assigned,
                      "status": "STAGED_NOT_DISPATCHED",
                      "owner_path_lease": "REQUIRED"})
    age_h = round((now - generated).total_seconds() / 3600, 2)
    return {"schema": SCHEMA,
            "source": {"owner": "EVERRED/harvest.py", "schema": SOURCE_SCHEMA,
                       "generated_at": census["generated_at"], "age_hours": age_h,
                       "completeness": "AS_DECLARED_BY_SOURCE",
                       "fresh": age_h <= 48},
            "status": "STAGED_NOT_DISPATCHED" if age_h <= 48 else "STALE_SOURCE_NEEDS_RECENSUS",
            "candidate_count": len(packets),
            "private_or_unmapped_suppressed": privacy_skipped,
            "waves": waves, "remaining_candidate_count": len(remaining),
            "acceptance": {"first_red": "native run/attempt/job/step and before/after lines",
                           "security": "separate MAROON owner and negative proof; no waiver",
                           "source_repair": "exact-head terminal tests and independent reviewer",
                           "closure": "merged-main, matched repeat, recurrence and owner DoV",
                           "math": "PCA/BT_WITHHELD_UNTIL_IDENTIFIABLE_OBSERVED_OUTCOMES",
                           "last_green_last_red": "CONSUME_RED_TRACE_OWNER_NOT_IN_THIS_REGISTER"},
            "authority_transfer": False, "worker_dispatch": False,
            "merge_authorized": False, "formal_closure_credit": 0}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--census", type=Path, required=True)
    ap.add_argument("--out", type=Path, help="local read-only JSON; never auto-publish")
    ap.add_argument("--max-waves", type=int, default=20)
    ap.add_argument("--capacity", type=int, default=8)
    ap.add_argument("--per-repo", type=int, default=2)
    opts = ap.parse_args(argv)
    doc = json.loads(opts.census.read_text(encoding="utf-8"))
    result = build(doc, max_waves=opts.max_waves, capacity=opts.capacity, per_repo=opts.per_repo)
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if opts.out:
        opts.out.parent.mkdir(parents=True, exist_ok=True)
        opts.out.write_text(payload, encoding="utf-8", newline="\n")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
