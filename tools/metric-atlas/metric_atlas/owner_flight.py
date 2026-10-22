"""Opt-in source-owned census launch via authenticated GitHub CLI.

Default: dry-run. A workflow-dispatch enqueue is never native test proof,
coverage acceptance, artifact validation or merge authorization.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from .census import CensusError, request

ALLOWED_OWNER_TARGETS = {
    "CODEX": "GBOGEB/CODEX",
    "QPS_ENGINEERING": "GBOGEB/cryoplant-project",
}
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
APPROVAL = "OWNER_APPROVED_N2_READONLY_CENSUS"
WORKFLOW = "qps-metric-census-receiver.yml"


class OwnerFlightError(ValueError):
    pass


def real_gh(argv):
    """Use an argument array, not a shell; never log authentication data."""
    try:
        p = subprocess.run(["gh", *argv], check=False, timeout=45,
                           text=True, capture_output=True)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise OwnerFlightError("GitHub CLI unavailable or timed out") from exc
    if p.returncode:
        raise OwnerFlightError("Authenticated GitHub CLI operation denied")
    return p.stdout.strip()


def head_for_repo(repo, gh):
    try:
        value = str(gh(["api", f"repos/{repo}/commits/main", "--jq", ".sha"])).strip()
    except Exception as exc:
        raise OwnerFlightError("Missing authorized source read for " + repo) from exc
    if SHA40.fullmatch(value) is None:
        raise OwnerFlightError("Invalid source SHA for " + repo)
    return value


def run_flight(wave, *, execute=False, approval=None, gh=None):
    if execute and approval != APPROVAL:
        raise OwnerFlightError("Explicit source-owner execution approval required")
    cli = gh if gh is not None else real_gh
    heads = {lane: head_for_repo(repo, cli)
             for lane, repo in ALLOWED_OWNER_TARGETS.items()}
    # ABACUS #2126 has not been admitted on main; no launch path here.
    manifest = request(wave, {"ABACUS": None, **heads}, selector="all")
    requested = manifest["requests"]
    if len(requested) != 2 or manifest["eligible_repos"] != 3:
        raise OwnerFlightError("Unexpected repository denominator or fan-out")
    result = {
        "schema": "qps-owner-flight/v1", "wave": wave, "manifest": manifest,
        "source_probe": "GH_CLI_AUTHENTICATED_CURRENT_MAIN_READ",
        "expected_receiver_jobs": len(requested) * 2,
        "actual_receiver_runs": None, "actual_receiver_job_ids": None,
        "actual_artifact_bytes": None, "coverage": None, "executed_tests": None,
        "engineering_acceptance": False, "authority_transfer": False,
        "events": [{"repo": q["repo"], "request_id": q["request_id"],
                    "expected_sha": q["expected_sha"],
                    "state": "DRY_RUN_NOT_TRIGGERED"} for q in requested],
        "events_submitted": 0, "admission": "HOLD",
    }
    if not execute:
        return result
    # Recheck every head before any dispatch. A later race fails closed in receiver.
    for q in requested:
        if head_for_repo(q["repo"], cli) != q["expected_sha"]:
            raise OwnerFlightError("STALE_SOURCE_HEAD: no events submitted")
    for q, event in zip(requested, result["events"]):
        argv = ["workflow", "run", WORKFLOW, "--repo", q["repo"], "--ref", "main",
                "-f", f"wave={wave}", "-f", "selector=all",
                "-f", f"request_id={q['request_id']}",
                "-f", f"expected_sha={q['expected_sha']}"]
        try:
            cli(argv)
        except Exception:
            event["state"] = "SUBMISSION_FAILED_NOT_RECEIVER_PROOF"
            result["submission_error"] = "GitHub rejected an owner dispatch"
            return result
        event["state"] = "REQUEST_SUBMITTED_NOT_RECEIVER_PROOF"
        result["events_submitted"] += 1
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description="QPS source-owner read-only census")
    p.add_argument("--wave", default="N2_20261017")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--confirm", default=None,
                   help="Explicit non-secret owner acknowledgement")
    args = p.parse_args(argv)
    try:
        result = run_flight(args.wave, execute=args.execute,
                            approval=args.confirm)
    except (CensusError, OwnerFlightError) as exc:
        p.exit(2, "OWNER_FLIGHT_HOLD: " + str(exc) + "\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "state": "SUBMISSION_ATTEMPTED" if args.execute else "DRY_RUN",
        "events_submitted": result["events_submitted"],
        "eligible_repos": result["manifest"]["eligible_repos"],
        "source_pinned_repos": len(result["manifest"]["requests"]),
        "receiver_jobs_proven": None,
    }, indent=2))
    return 2 if result.get("submission_error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
