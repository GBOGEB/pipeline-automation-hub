#!/usr/bin/env python3
"""Read-only CODE PURPLE watch decision consumer.

This module NEVER collects GitHub evidence, accepts an engineering root closure,
publishes #531 breadth, sends a notification, or authorizes a merge. The caller
must obtain native observations from their canonical source owner. Cursor state
is a projection, not a second event journal or a source attestation.

No private-repository rows are accepted in the public federation projection.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime

EVENT_SCHEMA = "codepurple.watch.terminal/v1"
CURSOR_SCHEMA = "codepurple.watch.cursor/v1"
PUBLIC_REPOS = frozenset({
    "GBOGEB/ABACUS", "GBOGEB/CODEX",
    "GBOGEB/pipeline-automation-hub", "GBOGEB/gg_MATH",
})
IDENTITY_KEYS = frozenset({
    "kind", "pr_number", "pr_head_sha", "base_sha", "checkout_sha",
    "synthetic_merge_sha", "merged_main_sha",
})
NATIVE_KEYS = frozenset({
    "run_id", "attempt", "job_id", "head_sha", "completed_at", "observed_at",
})
RESULT_KEYS = frozenset({"conclusion", "fingerprint", "required_receipts"})
COVERAGE_KEYS = frozenset({
    "files", "tool", "version", "selection", "config_sha256",
    "statements", "branches",
})
TOKEN = re.compile(r"[A-Za-z0-9_.:/-]{1,96}\Z")
PATH = re.compile(r"[A-Za-z0-9_.\/-]{1,240}\Z")
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SHA64 = re.compile(r"[a-f0-9]{64}\Z")
RESULTS = frozenset({"success", "failure", "cancelled", "skipped"})
RECEIPTS = frozenset({"PASS", "FAIL", "MISSING", "UNKNOWN"})


def _require(ok, msg):
    if not ok:
        raise ValueError("WATCH_HOLD:" + msg)


def _obj(value, keys, label):
    _require(type(value) is dict and set(value) == keys, label + " fields")
    return value


def _token(value, label):
    _require(type(value) is str and TOKEN.fullmatch(value) is not None, label)
    return value


def _sha(value, label, optional=False):
    if value is None and optional:
        return None
    _require(type(value) is str and SHA40.fullmatch(value) is not None, label)
    return value


def _utc(value):
    _require(type(value) is str and value.endswith("Z"), "UTC Z timestamp")
    try:
        t = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("WATCH_HOLD:invalid timestamp") from exc
    _require(t.tzinfo is not None and t.utcoffset().total_seconds() == 0,
             "timestamp not UTC")
    return t


def _positive(value, label):
    _require(type(value) is int and value > 0, label)
    return value


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("ascii")).hexdigest()


def visibility(http_status):
    """Source reachability: no credentials/HTTP 401 -> UNKNOWN, never zero."""
    if http_status in (None, 401, 403):
        return {"qualified_cells": None, "state": "UNKNOWN", "admission": "HOLD"}
    _require(type(http_status) is int and 100 <= http_status <= 599,
             "invalid source visibility")
    return {"qualified_cells": None, "state": "REACHABLE_UNQUALIFIED"
            if http_status == 200 else "UNKNOWN", "admission": "HOLD"}


def _identity(value):
    i = _obj(value, IDENTITY_KEYS, "source identity")
    kind = i["kind"]
    _require(kind in {"PR_HEAD", "SYNTHETIC_MERGE", "MERGED_MAIN"},
             "unknown checkout identity")
    for key in IDENTITY_KEYS - {"kind", "pr_number"}:
        _sha(i[key], key, optional=True)
    head, base, checkout = i["pr_head_sha"], i["base_sha"], i["checkout_sha"]
    synthetic, merged = i["synthetic_merge_sha"], i["merged_main_sha"]
    _sha(checkout, "checkout source required")
    if kind == "PR_HEAD":
        _positive(i["pr_number"], "PR number")
        _require(head is not None and base is not None
                 and checkout == head and synthetic is None and merged is None,
                 "exact PR head is not the checkout")
    elif kind == "SYNTHETIC_MERGE":
        _positive(i["pr_number"], "PR number")
        _require(head is not None and base is not None
                 and synthetic == checkout and synthetic != head and merged is None,
                 "synthetic merge presented as PR head")
    else:
        _require(i["pr_number"] is None and head is None and base is None
                 and synthetic is None and checkout == merged,
                 "merged main identity not exact")
    return kind


def _coverage(value):
    if value is None:
        return None
    c = _obj(value, COVERAGE_KEYS, "coverage contract")
    _require(type(c["files"]) is list and c["files"], "empty source-blob cohort")
    paths = []
    for file in c["files"]:
        f = _obj(file, {"path", "blob_sha"}, "coverage blob")
        path = f["path"]
        _require(type(path) is str and PATH.fullmatch(path) is not None
                 and not path.startswith("/") and ".." not in path.split("/")
                 and "\\" not in path, "unsafe source path")
        _sha(f["blob_sha"], "source Git blob SHA")
        paths.append(path)
    _require(paths == sorted(set(paths)), "source blobs must be sorted and unique")
    for key in ("tool", "version", "selection"):
        _token(c[key], "coverage " + key)
    _require(type(c["config_sha256"]) is str
             and SHA64.fullmatch(c["config_sha256"]) is not None,
             "coverage config digest")
    for axis in ("statements", "branches"):
        m = _obj(c[axis], {"covered", "eligible"}, axis)
        _require(type(m["covered"]) is int and type(m["eligible"]) is int
                 and m["eligible"] > 0 and 0 <= m["covered"] <= m["eligible"],
                 "invalid coverage denominator")
    population = {k: c[k] for k in ("files", "tool", "version", "selection", "config_sha256")}
    population["eligible"] = {k: c[k]["eligible"] for k in ("statements", "branches")}
    return _digest(population)


def validate(event):
    e = _obj(event, {"schema", "repository", "lane", "identity", "native",
                     "result", "coverage"}, "terminal observation")
    _require(e["schema"] == EVENT_SCHEMA, "unsupported observation schema")
    _require(e["repository"] in PUBLIC_REPOS, "restricted or noncanonical repository")
    _token(e["lane"], "lane")
    kind = _identity(e["identity"])
    n = _obj(e["native"], NATIVE_KEYS, "native evidence")
    for key in ("run_id", "attempt", "job_id"):
        _positive(n[key], key)
    _sha(n["head_sha"], "native run head")
    _require(n["head_sha"] == e["identity"]["pr_head_sha"]
             if kind != "MERGED_MAIN" else
             n["head_sha"] == e["identity"]["merged_main_sha"],
             "run head not bound to correct identity")
    _require(_utc(n["completed_at"]) <= _utc(n["observed_at"]),
             "completion after observation")
    r = _obj(e["result"], RESULT_KEYS, "result")
    _require(r["conclusion"] in RESULTS, "nonterminal or unsupported result")
    if r["fingerprint"] is not None:
        _token(r["fingerprint"], "diagnostic fingerprint")
    _require(type(r["required_receipts"]) is list, "receipt list")
    names = []
    for x in r["required_receipts"]:
        _obj(x, {"name", "state"}, "required receipt")
        names.append(_token(x["name"], "required check name"))
        _require(x["state"] in RECEIPTS, "invalid required receipt state")
    _require(names == sorted(set(names)), "duplicate or unsorted required receipts")
    return _coverage(e["coverage"])


def empty_cursor():
    return {"schema": CURSOR_SCHEMA, "seen": {}, "lanes": {},
            "authority": {"merge_admission": "HOLD", "formal_credit_delta": 0,
                          "security_waiver": "NONE", "qps_acceptance": "WITHHELD"}}


def _cursor(value):
    c = _obj(value, {"schema", "seen", "lanes", "authority"}, "cursor")
    _require(c["schema"] == CURSOR_SCHEMA and type(c["seen"]) is dict
             and type(c["lanes"]) is dict, "cursor state")
    _require(c["authority"] == empty_cursor()["authority"], "forged authority")
    return c


def _signature(event):
    # Not a new root diagnosis: track failed native evidence and required vetoes.
    return _digest({"conclusion": event["result"]["conclusion"],
                    "fingerprint": event["result"]["fingerprint"],
                    "required_receipts": event["result"]["required_receipts"],
                    "coverage": ({"statements": event["coverage"]["statements"],
                                  "branches": event["coverage"]["branches"]}
                                 if event["coverage"] else None)})


def fold(events, cursor=None):
    """Deterministic, replay-idempotent projection with one alert per transition.

    Every distinct completed run/job is considered once. Unchanged repeated
    diagnostic fingerprints never send another notification. Four distinct,
    source-comparable native observations with equal results are required for
    STABLE_HOLD (three equal transitions). Late events are seen but do not
    overwrite newer lane state.
    """
    _require(type(events) is list, "event batch")
    state = copy.deepcopy(_cursor(cursor if cursor is not None else empty_cursor()))
    alerts = []
    for event in events:
        cohort = validate(event)
        n, i, r = event["native"], event["identity"], event["result"]
        lane = event["repository"] + "::" + event["lane"] + "::" + i["kind"]
        key = _digest([lane, i["checkout_sha"], n["run_id"], n["attempt"], n["job_id"]])
        payload = _digest(event)
        seen = state["seen"]
        if key in seen:
            _require(seen[key] == payload, "native identity reused with changed evidence")
            continue
        _require(len(seen) < 100000, "cursor exceeds reviewed observation budget")
        seen[key] = payload
        prev = state["lanes"].get(lane)
        if prev is not None and (
            _utc(n["completed_at"]) <= _utc(prev["completed_at"])
            or _utc(n["observed_at"]) <= _utc(prev["observed_at"])
        ):
            # Late older-source completions cannot roll back a newer lane, even
            # when GitHub reveals them after the later completion was observed.
            continue
        if r["conclusion"] in ("skipped", "cancelled"):
            # Not a verified regression or recovery and not a stability wave.
            continue
        signature = _signature(event)
        same_population = bool(prev and cohort and cohort == prev["cohort"])
        repeated = bool(same_population and prev["signature"] == signature)
        equal = prev["equal_transitions"] + 1 if repeated else 0
        reasons = []
        if r["conclusion"] == "failure" and r["fingerprint"] and (
            prev is None or prev["fingerprint"] != r["fingerprint"]
        ):
            reasons.append("ATTRIBUTABLE_RED_CANDIDATE")
        if prev and prev["conclusion"] != r["conclusion"]:
            reasons.append("RED_TO_GREEN" if r["conclusion"] == "success"
                           else "GREEN_TO_RED")
        veto = tuple(x["name"] + ":" + x["state"] for x in r["required_receipts"]
                     if x["state"] != "PASS")
        old_veto = tuple(prev["veto"]) if prev else ()
        if veto != old_veto:
            if veto:
                reasons.append("REQUIRED_RECEIPT_VETO")
            elif old_veto:
                reasons.append("REQUIRED_RECEIPT_RECOVERY_CANDIDATE")
        coverage_delta = None
        if same_population and prev["coverage"] is not None and event["coverage"] is not None:
            coverage_delta = {
                axis: event["coverage"][axis]["covered"] - prev["coverage"][axis]["covered"]
                for axis in ("statements", "branches")
            }
            if any(coverage_delta.values()):
                reasons.append("SOURCE_MATCHED_COVERAGE_CHANGE")
        # Each terminal event has at most one notification, even with many reasons.
        if reasons:
            alerts.append({"event_key": key, "lane": lane, "reasons": reasons,
                           "source": "CALLER_ASSERTED_NEEDS_NATIVE_READBACK",
                           "coverage_delta": coverage_delta, "admission": "HOLD"})
        state["lanes"][lane] = {
            "observed_at": n["observed_at"], "completed_at": n["completed_at"],
            "native_key": key,
            "checkout_sha": i["checkout_sha"], "cohort": cohort,
            "signature": signature, "conclusion": r["conclusion"],
            "fingerprint": r["fingerprint"], "veto": list(veto),
            "coverage": copy.deepcopy(event["coverage"]),
            "equal_transitions": equal,
            "mode": ("STABLE_HOLD" if equal >= 3 else
                     "ACTIVE" if cohort is not None else "STARVED"),
        }
    return state, alerts


def main(argv=None):
    """Offline opt-in cursor persistence; never contacts GitHub or sends alerts.

    The existing scale-dock hash-chained ledger remains the event authority.
    --events is a source-owned, allowlisted terminal JSONL export; --cursor
    stores only already-qualified decisions and observed native identities.
    Default is dry-run. --write-cursor uses an exclusive local lock.
    """
    import argparse
    import os
    import tempfile
    from pathlib import Path

    parser = argparse.ArgumentParser(description="CODE PURPLE consumer-only watch decisions")
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--cursor", required=True, type=Path)
    parser.add_argument("--write-cursor", action="store_true")
    args = parser.parse_args(argv)
    raw = args.events.read_bytes()
    _require(len(raw) <= 4_000_000, "events over offline budget")
    lines = raw.splitlines()
    _require(0 < len(lines) <= 2000 and all(line.strip() for line in lines),
             "empty or oversized input journal")
    try:
        events = [json.loads(line) for line in lines]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("WATCH_HOLD:invalid terminal JSONL") from exc
    prior_raw = args.cursor.read_bytes() if args.cursor.exists() else None
    prior = json.loads(prior_raw) if prior_raw is not None else empty_cursor()
    cursor, notifications = fold(events, prior)
    result = {
        "schema": "codepurple.watch.decision.v1",
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "cursor_sha256": _digest(cursor),
        "new_native_identities": len(cursor["seen"]) - len(prior["seen"]),
        "notifications": notifications,
        "notification_emission": "NONE_LOCAL_PREVIEW",
        "source_authentication": "CALLER_ASSERTED_NOT_NATIVE_READBACK",
        "admission": "HOLD",
    }
    if args.write_cursor:
        args.cursor.parent.mkdir(parents=True, exist_ok=True)
        lock = args.cursor.with_name(args.cursor.name + ".lock")
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ValueError("WATCH_HOLD:cursor single-writer lock held") from exc
        try:
            os.close(fd)
            current = args.cursor.read_bytes() if args.cursor.exists() else None
            _require(current == prior_raw, "cursor changed during evaluation")
            payload = (_canonical(cursor) + "\n").encode("ascii")
            fd2, tmp = tempfile.mkstemp(prefix=".watch_cursor_", dir=args.cursor.parent)
            try:
                with os.fdopen(fd2, "wb") as fh:
                    fh.write(payload)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, args.cursor)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        finally:
            os.unlink(lock)
    print(_canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
