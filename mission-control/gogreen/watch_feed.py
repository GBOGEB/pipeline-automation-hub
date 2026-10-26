#!/usr/bin/env python3
"""Lossless source-owned PUBLIC pulse -> strict watch terminal adapter (offline).

Input is the existing SHA256-chained scale_dock_series ledger, verified by
its OWN read_ledger(). Only public pulse.findings may cross the adapter.
Private issue_bd, QPS fields and owner-unverified metrics are never serialized.
Old rows without a native job completion timestamp are gaps, not evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


source = _load("watch_feed_scale_dock_owner", HERE / "scale_dock_series.py")
decision = _load("watch_feed_decision_consumer", HERE / "watch_decision.py")
SOURCE_AUTHORITY = "READ_ONLY_OBSERVATION_NO_ROOT_CLOSURE_NO_DISPATCH"


def _fail(condition, message):
    if condition:
        raise ValueError("WATCH_FEED_HOLD:" + message)


def _opaque(prefix, value):
    _fail(type(value) is not str or not value, "missing diagnostic identity")
    return prefix + hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def project(records):
    """Project verified source-ledger records; never duplicate its journal.

    No source/job clock may be manufactured from the observation clock.
    Unqualified legacy pulses are excluded with explicit aggregate gap counts.
    """
    _fail(type(records) is not list, "source records must be a list")
    events, gaps = [], {"MISSING_NATIVE_COMPLETION": 0, "MISSING_NATIVE_IDENTITY": 0,\n                        "NATIVE_AFTER_PULSE": 0}
    for record in records:
        _fail(type(record) is not dict
              or record.get("schema") != source.LEDGER_SCHEMA
              or record.get("authority") != SOURCE_AUTHORITY,
              "noncanonical source-owned pulse")
        pulse = record.get("pulse")
        _fail(type(pulse) is not dict or type(pulse.get("findings")) is not list
              or type(pulse.get("source_heads")) is not dict,
              "invalid source pulse")
        stamp = pulse.get("observed_at")
        decision._utc(stamp)
        for finding in pulse["findings"]:
            _fail(type(finding) is not dict, "invalid source finding")
            repo = finding.get("repo")
            _fail(repo not in decision.PUBLIC_REPOS, "restricted/private finding")
            sha = pulse["source_heads"].get(repo)
            _fail(finding.get("source_sha") != sha, "source-head drift")
            decision._sha(sha, "public exact default-head SHA")
            _fail(finding.get("owner_accepted") is not False,
                  "watch cannot assume independent root acceptance")
            _fail(finding.get("state") not in {"RED", "RECOVERED"},
                  "unsupported source state")
            native = [finding.get(k) for k in ("run_id", "attempt", "job_id")]
            if not all(type(x) is int and x > 0 for x in native):
                gaps["MISSING_NATIVE_IDENTITY"] += 1
                continue
            completed = finding.get("completed_at")
            if completed is None:
                gaps["MISSING_NATIVE_COMPLETION"] += 1
                continue
            if decision._utc(completed) > decision._utc(stamp):
                # An older immutable pulse may have been sampled before a job\n                # completed. Retain the gap but never poison all later pulses.\n                gaps["NATIVE_AFTER_PULSE"] += 1
                continue
            state = "failure" if finding["state"] == "RED" else "success"
            fprint = finding.get("fingerprint")
            event = {
                "schema": decision.EVENT_SCHEMA,
                "repository": repo,
                "lane": _opaque("JOB_", finding.get("id")),
                "identity": {
                    "kind": "MERGED_MAIN", "pr_number": None,
                    "pr_head_sha": None, "base_sha": None,
                    "checkout_sha": sha, "synthetic_merge_sha": None,
                    "merged_main_sha": sha,
                },
                "native": {
                    "run_id": native[0], "attempt": native[1], "job_id": native[2],
                    "head_sha": sha,
                    "completed_at": completed, "observed_at": stamp,
                },
                "result": {
                    "conclusion": state,
                    "fingerprint": _opaque("FP_", fprint) if fprint else None,
                    # Unknown mandatory check status is NOT a PASS. The owner
                    # must supply required receipts in a separate qualified join.
                    "required_receipts": [],
                },
                "coverage": None,  # scale_dock findings are not blob-matched coverage
            }
            decision.validate(event)
            events.append(event)
    return events, {
        "schema": "codepurple.watch.public-feed/v1",
        "authority": "CANONICAL_SCALE_DOCK_CHAIN_VALIDATED_BY_CALLER",
        "events_exported": len(events), "gaps": gaps,
        "native_evidence_authentication": "READBACK_REQUIRED",
        "fresh_six_repo_breadth": None,
        "coverage_promotion": None,
        "root_closures_accepted": None,
        "private_source_rows_emitted": 0,
        "merge_admission": "HOLD",
    }



def select_batch(events, cursor=None, limit=2000, byte_limit=4_000_000):
    """Bounded incremental consumer snapshot, never a second source ledger.

    The existing watch_decision cursor is the sole processed-identity record.
    Source records are not removed, rewritten or marked accepted here.
    """
    _fail(type(limit) is not int or not 1 <= limit <= 2000, "consumer batch limit")
    prior = decision._cursor(cursor if cursor is not None else decision.empty_cursor())
    unique = {}
    for event in events:
        decision.validate(event)
        n, i = event["native"], event["identity"]
        lane = event["repository"] + "::" + event["lane"] + "::" + i["kind"]
        key = decision._digest([lane, i["checkout_sha"], n["run_id"],
                                n["attempt"], n["job_id"]])
        evidence_hash = decision._native_payload(event)
        if key in prior["seen"]:
            _fail(prior["seen"][key] != evidence_hash, "cursor native collision")
            continue
        if key in unique:
            _fail(decision._native_payload(unique[key]) != evidence_hash,
                  "source native collision")
            continue
        unique[key] = event
    def order(e):
        n = e["native"]
        return (decision._utc(n["completed_at"]), n["run_id"],
                n["attempt"], n["job_id"], e["repository"], e["lane"])
    pending = sorted(unique.values(), key=order)
    chosen, total_bytes = [], 0
    for event in pending:
        size = len(decision._canonical(event).encode("ascii")) + 1
        _fail(size > byte_limit, "single terminal event exceeds consumer budget")
        if len(chosen) == limit or total_bytes + size > byte_limit:
            break
        chosen.append(event)
        total_bytes += size
    return chosen, {
        "eligible_distinct_unseen": len(pending),
        "deferred_for_next_cursor": len(pending) - len(chosen),
        "already_seen_or_repeated": len(events) - len(pending),
        "selected_bytes": total_bytes,
        "consumer_cursor_advanced": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Offline public source-ledger watch adapter")
    p.add_argument("--ledger", type=Path, default=source.LEDGER)
    p.add_argument("--output", type=Path, help="opt-in, public-only JSONL snapshot")
    p.add_argument("--cursor", type=Path, help="existing watch_decision cursor for incremental batches")
    p.add_argument("--limit", type=int, default=2000, help="max distinct native events (1..2000)")
    a = p.parse_args(argv)
    records, _ = source.read_ledger(a.ledger)  # validates ordinal, canonical bytes and SHA256 chain
    events, report = project(records)
    if a.output:
        cursor = (json.loads(a.cursor.read_text(encoding="utf-8"))
                  if a.cursor and a.cursor.exists() else decision.empty_cursor())
        selected, info = select_batch(events, cursor=cursor, limit=a.limit)
        report.update(info)
        report["events_projected_before_cursor"] = report["events_exported"]
        report["events_exported"] = len(selected)
        report["output_written"] = bool(selected)
        report["export_state"] = ("BOUNDED_PUBLIC_EVENTS" if selected else
                                  "NO_NEW_NATIVE_EVENTS_NO_CONSUMER_FILE")
        if selected:
            payload = "".join(decision._canonical(x) + "\n" for x in selected).encode("ascii")
            a.output.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".watch_feed_", dir=a.output.parent)
            try:
                with os.fdopen(fd, "wb") as file:
                    file.write(payload)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(tmp, a.output)
                if os.name == "posix":
                    directory_fd = os.open(a.output.parent, os.O_RDONLY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        elif a.output.exists():
            # The output is explicitly transient, never the canonical ledger;
            # leave no stale previous batch masquerading as a new result.
            a.output.unlink()
    print(decision._canonical(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
