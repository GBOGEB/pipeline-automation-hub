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
    events, gaps = [], {"MISSING_NATIVE_COMPLETION": 0, "MISSING_NATIVE_IDENTITY": 0}
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
            _fail(decision._utc(completed) > decision._utc(stamp),
                  "native completion after observation")
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


def main(argv=None):
    p = argparse.ArgumentParser(description="Offline public source-ledger watch adapter")
    p.add_argument("--ledger", type=Path, default=source.LEDGER)
    p.add_argument("--output", type=Path, help="opt-in, public-only JSONL snapshot")
    a = p.parse_args(argv)
    records, _ = source.read_ledger(a.ledger)  # validates ordinal, canonical bytes and SHA256 chain
    events, report = project(records)
    if a.output:
        payload = "".join(decision._canonical(x) + "\n" for x in events).encode("ascii")
        a.output.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".watch_feed_", dir=a.output.parent)
        try:
            with os.fdopen(fd, "wb") as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            os.replace(tmp, a.output)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    print(decision._canonical(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
