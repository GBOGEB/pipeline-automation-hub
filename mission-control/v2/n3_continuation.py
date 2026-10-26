#!/usr/bin/env python3
"""Governed three-pulse continuation receipt validator and resumable ledger.

This program does not dispatch runners, bypass review, or merge code. It records
external actions only after source-bound receipts arrive and rejects unsafe chains.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
VALID_STATUS = {"SOURCE_COMMITTED", "LOCAL_VALIDATED", "BLOCKED"}
BLOCKERS = {
    "BRANCH_DRIFT", "SOURCE_IDENTITY_CONFLICT", "OWNER_LEASE_CONFLICT",
    "P0_P1_SECURITY", "A10_OR_GOVERNANCE_FAIL", "NATIVE_PROOF_FAILED",
    "DEPENDENCY_INCOMPLETE", "POLICY_VIOLATION", "UNKNOWN_HIGH_RISK",
}


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("utf-8")).hexdigest()


def check(value, reason):
    if not value:
        raise ValueError(reason)


def head(value):
    return isinstance(value, str) and bool(SHA.fullmatch(value))


def safe_path(path):
    return (isinstance(path, str) and bool(path) and path[0] != "/"
            and "\\" not in path and "//" not in path
            and all(part not in ("", ".", "..") for part in path.split("/")))


def validate(ledger):
    check(isinstance(ledger, dict), "ledger must be an object")
    check(ledger.get("schema") == "missioncontrol.n3_continuation.v1", "schema mismatch")
    check(ledger.get("mode") == "N3-AUTO" and ledger.get("operation") == "3P-CONT",
          "invalid mode; 3W is NOT a three-pulse continuation")
    check(ledger.get("authority_transfer") is False, "authority transfer forbidden")
    m = ledger.get("mission", {})
    check(isinstance(m.get("id"), str) and m["id"].strip(), "mission ID required")
    check(isinstance(m.get("repo"), str) and REPO.fullmatch(m["repo"]), "repository must be owner/name")
    check(isinstance(m.get("wave"), str) and m["wave"].strip(), "wave identity required")
    check(isinstance(m.get("start_sha"), str) and head(m["start_sha"]), "start SHA invalid")
    n = ledger.get("start_ordinal")
    check(type(n) is int and n >= 0, "start ordinal must be nonnegative integer")
    policy = ledger.get("policy", {})
    check(policy.get("max_pulses") == 3, "exactly three pulses are authorized")
    for key in ("security_waiver", "merge_without_review", "unbounded_dispatch"):
        check(policy.get(key) is False, "unsafe autonomous policy: " + key)
    paths = policy.get("allowed_paths")
    check(isinstance(paths, list) and bool(paths)
          and len(set(paths)) == len(paths) and all(safe_path(p) for p in paths),
          "allowed paths must be nonempty, distinct, repository-relative")
    receipts = ledger.get("receipts")
    check(isinstance(receipts, list) and len(receipts) <= 3, "too many pulse receipts")
    prev_sha = m["start_sha"]
    prev_digest = None
    major_blocked = False
    for i, r in enumerate(receipts):
        check(isinstance(r, dict), "receipt must be an object")
        check(not major_blocked, "pulse after major blocker is forbidden")
        check(r.get("ordinal") == n + i + 1 and type(r.get("ordinal")) is int,
              "nonconsecutive pulse ordinal")
        expected = f"{m['repo']}::{m['id']}::{m['wave']}::PULSE-{n+i+1}"
        check(r.get("pulse_id") == expected, "qualified pulse identity mismatch")
        check(r.get("input_source_sha") == prev_sha, "broken input/output source lineage")
        check(r.get("prev_receipt_digest") == prev_digest, "broken receipt hash chain")
        check(head(r.get("output_source_sha")), "output SHA invalid")
        check(r.get("status") in VALID_STATUS, "unsupported pulse status")
        check(r.get("merge_admission") in ("HOLD", "UNKNOWN"),
              "no independent admission authority in N3-AUTO")
        check(r.get("security_waiver") is False and r.get("authority_transfer") is False,
              "receipt attempts authority escalation")
        paths_changed = r.get("changed_paths", [])
        check(isinstance(paths_changed, list), "changed paths must be a list")
        for path in paths_changed:
            check(safe_path(path) and any(
                path == parent or path.startswith(parent.rstrip("/") + "/")
                for parent in paths), "mutation outside declared path lease")
        tests = r.get("tests", {})
        check(isinstance(tests, dict) and tests.get("kind") in
              ("NOT_RUN", "LOCAL", "NATIVE_EXACT_HEAD"), "test provenance missing")
        check(type(tests.get("passed")) is int and tests["passed"] >= 0 and
              type(tests.get("failed")) is int and tests["failed"] >= 0,
              "test counts invalid")
        if tests["kind"] == "NOT_RUN":
            check(tests["passed"] == tests["failed"] == 0, "untested proof claim")
        if tests["kind"] == "NATIVE_EXACT_HEAD":
            check(tests.get("tested_sha") == r["output_source_sha"],
                  "native tests not on output exact head")
        check(r.get("coverage_delta") is None or (
            r.get("coverage_matched") is True and
            isinstance(r.get("coverage_delta"), (int, float)) and
            not isinstance(r.get("coverage_delta"), bool)),
            "unmatched coverage delta")
        blocker = r.get("major_blocker")
        check(blocker is None or blocker in BLOCKERS, "unknown major blocker")
        check((r["status"] == "BLOCKED") == (blocker is not None),
              "major blocker/status disagreement")
        if r["status"] == "BLOCKED":
            check(r["output_source_sha"] == prev_sha and paths_changed == [],
                  "blocked pulse cannot claim source mutation")
            major_blocked = True
        prev_sha = r["output_source_sha"]
        prev_digest = digest(r)
    return {
        "schema": "missioncontrol.n3_continuation_result.v1",
        "mission_id": m["id"],
        "start_ordinal": n,
        "target_ordinal": n + 3,
        "completed_receipts": len(receipts),
        "next_ordinal": None if major_blocked or len(receipts) == 3 else n + len(receipts) + 1,
        "disposition": ("STOP_MAJOR_BLOCKER" if major_blocked else
                        "THREE_PULSES_RECORDED_NON_ADMITTED" if len(receipts) == 3
                        else "CONTINUE_BOUNDED"),
        "latest_source_sha": prev_sha,
        "merge_admission": "HOLD",
        "authority_transfer": False,
        "last_receipt_digest": prev_digest,
    }


def record(ledger, receipt):
    state = validate(ledger)
    check(state["next_ordinal"] is not None, "no legal next pulse")
    candidate = deepcopy(ledger)
    candidate["receipts"].append(receipt)
    return candidate, validate(candidate)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("ledger", type=Path)
    p.add_argument("--record", type=Path, help="append one externally observed pulse receipt")
    p.add_argument("--out", type=Path, help="write ledger to this path after validation")
    a = p.parse_args()
    ledger = json.loads(a.ledger.read_text(encoding="utf-8"))
    if a.record:
        check(a.out is not None, "--out required for --record")
        receipt = json.loads(a.record.read_text(encoding="utf-8"))
        ledger, result = record(ledger, receipt)
    else:
        result = validate(ledger)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(ledger, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 2 if result["disposition"] == "STOP_MAJOR_BLOCKER" else 0


if __name__ == "__main__":
    raise SystemExit(main())
