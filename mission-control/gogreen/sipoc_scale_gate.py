#!/usr/bin/env python3
"""Advisory 2-to-4 SIPOC scale gate. No new scheduler, fleet KPI or merge authority.

Consumes bounded native evidence assertions and source-aligned canonical
Actions queue metrics. External run identity is untrusted until read back from
the GitHub-native source. Never dispatches, modifies branches or awards credit.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SCHEMA = "missioncontrol.sipoc-scale-observation.v1"
OUTPUT_SCHEMA = "missioncontrol.sipoc-scale-advisory.v1"
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
METRIC_OWNER = "mission-control/jade_temple/devops/actions_metrics.py"


def _path_overlap(a, b):
    def norm(p):
        if (not isinstance(p, str) or not p or p.startswith(("/", "\\"))
                or "\\" in p or any(x in ("", ".", "..") for x in p.split("/"))):
            raise ValueError("unsafe mutation path lease")
        return p.casefold()
    a, b = norm(a), norm(b)
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _native_proof(record, source_sha):
    return (
        isinstance(record, dict)
        and type(record.get("run_id")) is int and record["run_id"] > 0
        and type(record.get("attempt")) is int and record["attempt"] > 0
        and type(record.get("job_id")) is int and record["job_id"] > 0
        and record.get("status") == "completed"
        and record.get("conclusion") == "success"
        and record.get("source_sha") == source_sha
        and isinstance(record.get("receipt_sha256"), str)
        and bool(DIGEST.fullmatch(record["receipt_sha256"]))
    )


def _census(heads):
    return (isinstance(heads, dict) and bool(heads) and all(
        isinstance(repo, str) and REPO.fullmatch(repo)
        and isinstance(sha, str) and SHA.fullmatch(sha)
        for repo, sha in heads.items()))


def assess(observation):
    if not isinstance(observation, dict) or observation.get("schema") != SCHEMA:
        raise ValueError("invalid scaling observation schema")
    if any(observation.get(k) is not False for k in
           ("authority_transfer", "dispatch_authorized", "merge_authorized")):
        raise ValueError("prohibited scaling authority escalation")
    target = observation.get("target_mutators")
    if type(target) is not int or target not in (2, 4):
        raise ValueError("unsupported mutator scale target")
    heads = observation.get("source_heads")
    if not _census(heads):
        raise ValueError("invalid exact source census")
    pulses = observation.get("pulses")
    if not isinstance(pulses, list) or not 1 <= len(pulses) <= 16:
        raise ValueError("invalid pulse population")
    ids = [p.get("pulse_id") for p in pulses if isinstance(p, dict)]
    if (len(ids) != len(pulses)
            or any(type(i) is not int or i < 1 for i in ids)
            or ids != sorted(set(ids))):
        raise ValueError("invalid nonmonotonic pulse identities")
    # Per-pulse source census; a pulse without one is read at the top-level heads.
    census = {}
    for pulse in pulses:
        pulse_heads = pulse.get("source_heads", heads)
        if not _census(pulse_heads):
            raise ValueError("invalid exact pulse source census")
        census[pulse["pulse_id"]] = pulse_heads

    reasons = []
    verified_pairs = 0
    recent = pulses[-2:]
    # A native execution or receipt may back exactly one worker or verifier
    # record across every pair of every assessed pulse.
    native_ids, receipt_ids = set(), set()
    if target == 4 and len(recent) < 2:
        reasons.append("TWO_CONSECUTIVE_PULSES_REQUIRED")
    if target == 4 and len(recent) == 2 and ids[-1] != ids[-2] + 1:
        reasons.append("PULSE_SEQUENCE_GAP")
    for pulse in recent:
        pairs = pulse.get("pairs")
        if not isinstance(pairs, list) or len(pairs) != 2:
            reasons.append("TWO_WORKER_VERIFIER_PAIRS_REQUIRED")
            continue
        active, seen = [], set()
        for pair in pairs:
            if not isinstance(pair, dict) or not isinstance(pair.get("id"), str):
                reasons.append("INVALID_PAIR_ID")
                continue
            if pair["id"] in seen:
                reasons.append("DUPLICATE_PAIR_ID")
            seen.add(pair["id"])
            repo = pair.get("repo")
            sha = heads.get(repo)
            if sha is None or pair.get("source_sha") != sha:
                reasons.append("PAIR_SOURCE_SHA_MISMATCH")
                continue
            worker, verifier = pair.get("worker"), pair.get("verifier")
            if not isinstance(worker, dict) or not isinstance(verifier, dict):
                reasons.append("INVALID_PAIR_ACTOR")
                continue
            if (not worker.get("actor") or not verifier.get("actor")
                    or worker["actor"] == verifier["actor"]):
                reasons.append("INDEPENDENT_VERIFIER_MISSING")
            wp, vp = worker.get("native"), verifier.get("native")
            if not _native_proof(wp, sha) or not _native_proof(vp, sha):
                reasons.append("EXACT_HEAD_NATIVE_PAIR_PROOF_MISSING")
            if wp == vp:
                reasons.append("VERIFIER_REUSES_WORKER_EVIDENCE")
            for record in (wp, vp):
                if not isinstance(record, dict):
                    continue
                native = (record.get("run_id"), record.get("attempt"), record.get("job_id"))
                if native in native_ids:
                    reasons.append("NATIVE_EVIDENCE_REUSED")
                native_ids.add(native)
                receipt = record.get("receipt_sha256")
                if receipt in receipt_ids:
                    reasons.append("NATIVE_RECEIPT_REUSED")
                receipt_ids.add(receipt)
            if (worker.get("mode") != "MUTATION_PROPOSAL"
                    or verifier.get("mode") != "NATIVE_PROVE"):
                reasons.append("INVALID_PAIR_MODE")
            if pair.get("first_red_roots") != [] or pair.get("lease_collision") is not False:
                reasons.append("FIRST_RED_OR_LEASE_COLLISION")
            paths = worker.get("mutation_paths")
            if not isinstance(paths, list) or not paths:
                reasons.append("MISSING_MUTATION_LEASE")
                continue
            if len(paths) != len(set(paths)):
                reasons.append("DUPLICATE_MUTATION_LEASE")
            for path in paths:
                _path_overlap(path, path)
                active.append((repo, pair.get("root_id"), path, pair["id"]))
            verified_pairs += int(_native_proof(wp, sha) and _native_proof(vp, sha))
        for n, (repo, root, path, pair_id) in enumerate(active):
            for r2, root2, p2, other_id in active[n + 1:]:
                if (repo == r2 and pair_id != other_id
                        and ((root is not None and root == root2)
                             or _path_overlap(path, p2))):
                    reasons.append("OVERLAPPING_DISJOINT_WORKER_LEASES")
        if pulse.get("first_red_recurrences") != 0 or pulse.get("security_findings") != 0:
            reasons.append("RECURRING_ROOT_OR_SECURITY_HOLD")
        if pulse.get("independent_review") is not True:
            reasons.append("PULSE_INDEPENDENT_REVIEW_MISSING")

    metrics = observation.get("metrics")
    if not isinstance(metrics, dict) or metrics.get("owner") != METRIC_OWNER:
        reasons.append("CANONICAL_METRIC_OWNER_MISSING")
    else:
        before, after = metrics.get("before"), metrics.get("after")
        if not isinstance(before, dict) or not isinstance(after, dict):
            reasons.append("COMPARABLE_METRIC_WINDOWS_MISSING")
        else:
            keys = ("scope", "denominator", "time_unit", "repo_population", "metric_key")
            if (any(before.get(k) is None or before.get(k) != after.get(k) for k in keys)
                    or before.get("metric_key") != "queue_p95_seconds"):
                reasons.append("METRIC_COHORT_NOT_COMPARABLE")
            # Each window must name the pulse it was read at and that pulse's
            # exact source census; after = latest pulse, before = an earlier one.
            bp, ap = before.get("pulse_id"), after.get("pulse_id")
            if (type(bp) is not int or type(ap) is not int
                    or ap != ids[-1] or bp not in census or not bp < ap
                    or before.get("source_heads") != census[bp]
                    or after.get("source_heads") != census[ap]):
                reasons.append("METRIC_WINDOW_NOT_SOURCE_BOUND")
            complete = True
            for m in (before, after):
                if (type(m.get("count")) is not int or m["count"] < 5
                        or type(m.get("value")) not in (int, float)
                        or not 0 <= m["value"] < float("inf")):
                    reasons.append("QUEUE_METRIC_WITHHELD_OR_UNDERSAMPLED")
                    complete = False
            if complete and after["value"] > before["value"]:
                reasons.append("QUEUE_P95_REGRESSION")
    reasons = sorted(set(reasons))
    return {
        "schema": OUTPUT_SCHEMA,
        "classification": "SCALE_CANDIDATE_EXTERNAL_GATE" if not reasons else "HOLD",
        "target_mutators": target if not reasons else 2,
        "requested_mutators": target, "pulses_assessed": ids[-2:],
        "verified_pair_evidence_records": verified_pairs,
        "causal_roots_accepted_closed": 0, "reasons": reasons,
        "native_revalidation_required": True, "evidence_trust": "UNVERIFIED_NATIVE_ASSERTIONS",
        "actual_worker_dispatch_performed": False, "merge_authorized": False,
        "dispatch_authorized": False, "authority_transfer": False,
        "engineering_credit_delta": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observation", type=Path)
    args = parser.parse_args(argv)
    out = assess(json.loads(args.observation.read_text(encoding="utf-8")))
    print(json.dumps(out, sort_keys=True, indent=2))
    return 0 if out["classification"] == "SCALE_CANDIDATE_EXTERNAL_GATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
