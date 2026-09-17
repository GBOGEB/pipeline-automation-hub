#!/usr/bin/env python3
"""GM-I-C exact Git-object ingress adapter.

Consumes a real git bundle plus an existing QPS control checkout, verifies the frozen
R3 source commit is actually present in Git object storage, imports it without network
access, and optionally dispatches the already-governed QPS R3 local executor.

This adapter is deliberately fail-closed. It never synthesizes Git identity, timing,
receipt counts, or authority credit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

EXPECTED_SHA = "70964e5f1577231512f4104b26f5f6649ad8cb39"
RUNNER = "scripts/run_r3_final_local_exact_worktree_v2.sh"


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def emit(out: Path, payload: dict) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fail(out: Path, payload: dict, reason: str, code: int = 2) -> int:
    payload.update({"state": "DEFER", "classification": reason, "authority_transfer": False, "formal_credit_delta": 0})
    emit(out, payload)
    print(reason, file=sys.stderr)
    return code


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--qps-control-checkout", type=Path, required=True)
    p.add_argument("--expected-sha", default=EXPECTED_SHA)
    p.add_argument("--receipt", type=Path, default=Path("GM_I_C_INGRESS_RECEIPT.json"))
    p.add_argument("--execute-r3", action="store_true")
    args = p.parse_args()

    t0 = time.monotonic()
    payload = {
        "schema": "missioncontrol.gm_i_c_ingress_receipt.v1",
        "mission_id": "GM-I-C",
        "event": "GIT_OBJECT_INGRESS",
        "expected_source_sha": args.expected_sha,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "bundle": str(args.bundle.resolve()),
        "qps_control_checkout": str(args.qps_control_checkout.resolve()),
        "r3_dispatched": False,
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }

    if not args.bundle.is_file():
        return fail(args.receipt, payload, "BUNDLE_NOT_FOUND")
    if not (args.qps_control_checkout / ".git").exists():
        return fail(args.receipt, payload, "QPS_CONTROL_CHECKOUT_NOT_GIT_WORKTREE")

    payload["bundle_sha256"] = sha256(args.bundle)

    verify = run(["git", "bundle", "verify", str(args.bundle)], check=False)
    payload["bundle_verify_rc"] = verify.returncode
    if verify.returncode != 0:
        payload["bundle_verify_stderr"] = verify.stderr[-4000:]
        return fail(args.receipt, payload, "BUNDLE_VERIFY_FAIL")

    heads = run(["git", "bundle", "list-heads", str(args.bundle)], check=False)
    if heads.returncode != 0:
        return fail(args.receipt, payload, "BUNDLE_LIST_HEADS_FAIL")
    advertised = [line.split()[0] for line in heads.stdout.splitlines() if line.strip()]
    payload["advertised_heads"] = advertised
    if args.expected_sha not in advertised:
        return fail(args.receipt, payload, "EXPECTED_SHA_NOT_ADVERTISED_BY_BUNDLE")

    status = run(["git", "status", "--porcelain"], cwd=args.qps_control_checkout, check=False)
    if status.returncode != 0:
        return fail(args.receipt, payload, "QPS_CONTROL_STATUS_FAIL")
    if status.stdout.strip():
        payload["control_dirty_paths"] = status.stdout.splitlines()
        return fail(args.receipt, payload, "QPS_CONTROL_CHECKOUT_DIRTY")

    fetch_ref = f"refs/gm-i-c/{args.expected_sha}"
    fetch = run(
        ["git", "fetch", "--no-tags", str(args.bundle), f"{args.expected_sha}:{fetch_ref}"],
        cwd=args.qps_control_checkout,
        check=False,
    )
    payload["bundle_fetch_rc"] = fetch.returncode
    if fetch.returncode != 0:
        payload["bundle_fetch_stderr"] = fetch.stderr[-4000:]
        return fail(args.receipt, payload, "BUNDLE_IMPORT_FAIL")

    cat = run(["git", "cat-file", "-e", f"{args.expected_sha}^{{commit}}"], cwd=args.qps_control_checkout, check=False)
    if cat.returncode != 0:
        return fail(args.receipt, payload, "EXPECTED_COMMIT_NOT_PRESENT_AFTER_IMPORT")

    resolved = run(["git", "rev-parse", args.expected_sha], cwd=args.qps_control_checkout).stdout.strip()
    payload["resolved_source_sha"] = resolved
    if resolved != args.expected_sha:
        return fail(args.receipt, payload, "SOURCE_SHA_MISMATCH")

    payload["ingress_verify_seconds"] = round(time.monotonic() - t0, 6)
    payload["state"] = "INGRESS_VERIFIED"
    payload["classification"] = "REAL_GIT_OBJECT_INGRESS_PASS"

    if args.execute_r3:
        runner = args.qps_control_checkout / RUNNER
        if not runner.is_file():
            return fail(args.receipt, payload, "GOVERNED_R3_RUNNER_MISSING")
        t1 = time.monotonic()
        proc = run(["bash", str(runner)], cwd=args.qps_control_checkout, check=False)
        payload["r3_dispatched"] = True
        payload["r3_execute_seconds"] = round(time.monotonic() - t1, 6)
        payload["r3_returncode"] = proc.returncode
        payload["r3_stdout_tail"] = proc.stdout[-8000:]
        payload["r3_stderr_tail"] = proc.stderr[-8000:]
        if proc.returncode != 0:
            payload["state"] = "DEFER"
            payload["classification"] = "R3_EXECUTOR_RETURNED_NONZERO"
            emit(args.receipt, payload)
            return proc.returncode or 3
        payload["state"] = "R3_DISPATCH_COMPLETED"
        payload["classification"] = "REAL_GIT_OBJECT_INGRESS_AND_R3_DISPATCH_PASS"

    emit(args.receipt, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
