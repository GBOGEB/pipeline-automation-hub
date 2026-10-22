"""QPS N3: independently join census receipts to terminal native GitHub evidence.

The receiver writes a SUCCESS claim before its job terminates. This module
never credits that claim until a separate authenticated GitHub API query
confirms its exact run, attempt, job, source head and terminal conclusion.
ZIP integrity and member bytes are independent, later proof stages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

from .census import ALLOWED_REPOS, CensusError, validate_receipt

ROUTES = ("native_checks", "coverage_catalog")
WORKFLOW = "qps-metric-census-receiver.yml"
MAX_REPOS = 3
MAX_ROUTES = 6
MAX_ZIP_BYTES = 8_000_000


def _key(repo, run_id, route):
    return f"{repo}|{run_id}|{route}"


def _native_evidence(receipt, run, job):
    """Return independent terminal proof or a specific HOLD reason."""
    if type(run) is not dict or type(job) is not dict:
        return "HOLD_NATIVE_DATA_MISSING"
    if (run.get("id") != receipt["run_id"] or
            run.get("head_sha") != receipt["target_sha"] or
            run.get("run_attempt") != receipt["run_attempt"]):
        return "HOLD_RUN_IDENTITY_MISMATCH"
    if run.get("event") not in ("workflow_dispatch", "repository_dispatch"):
        return "HOLD_UNEXPECTED_TRIGGER"
    if WORKFLOW not in str(run.get("path", "")):
        return "HOLD_WRONG_WORKFLOW"
    if run.get("status") != "completed":
        return "HOLD_RUN_NOT_TERMINAL"
    if (job.get("id") != receipt["job_id"] or
            job.get("run_id") != receipt["run_id"] or
            (job.get("head_sha") is not None and
             job["head_sha"] != receipt["target_sha"])):
        return "HOLD_JOB_IDENTITY_MISMATCH"
    if (job.get("run_attempt") is not None and
            job["run_attempt"] != receipt["run_attempt"]):
        return "HOLD_ATTEMPT_MISMATCH"
    if (job.get("status") != "completed" or
            not str(job.get("name", "")).endswith(
                "QPS Census receiver " + receipt["route"])):
        return "HOLD_JOB_NOT_TERMINAL_OR_WRONG_ROUTE"
    if (run.get("conclusion") != "success" or
            job.get("conclusion") != "success" or
            receipt.get("outcome") != "SUCCESS"):
        return "HOLD_TERMINAL_FIRST_RED"
    return "TERMINAL_SOURCE_BOUND"


def verify_zip(path, receipt):
    """Inspect real archive and exact untrusted member bytes; no extraction."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_ZIP_BYTES:
        raise CensusError("missing or oversized native artifact ZIP")
    raw = path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != 1 or len(set(names)) != 1:
            raise CensusError("native census ZIP must contain one receipt")
        name = names[0]
        if (name.startswith("/") or "\\" in name or ".." in name.split("/") or
                name.split("/")[-1] != receipt["route"] + ".json"):
            raise CensusError("unexpected ZIP path or receipt member")
        if archive.testzip() is not None:
            raise CensusError("ZIP CRC mismatch")
        member = archive.getinfo(name)
        if member.file_size > MAX_ZIP_BYTES:
            raise CensusError("ZIP expansion too large")
        data = archive.read(name)
    try:
        inside = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise CensusError("invalid receipt bytes") from exc
    if inside != receipt:
        raise CensusError("receipt member bytes differ from supplied receipt")
    return {"zip_bytes": len(raw),
            "zip_sha256": hashlib.sha256(raw).hexdigest(),
            "member": name, "member_bytes": len(data),
            "member_sha256": hashlib.sha256(data).hexdigest(),
            "byte_integrity": "PASS",
            "canonical_530_accepted": False}


def audit(manifest, receipts, *, native_fetch=None, zip_paths=None):
    """Fail-closed bounded join. native_fetch is an authenticated API adapter."""
    if (manifest.get("schema") != "qps-metric-census/v1" or
            manifest.get("eligible_repos") != MAX_REPOS or
            len(manifest.get("requests", [])) > MAX_REPOS):
        raise CensusError("invalid or unbounded source census")
    expected = {}
    for request in manifest["requests"]:
        repo = request["repo"]
        if repo != ALLOWED_REPOS.get(request["lane"]):
            raise CensusError("out-of-scope producer")
        for route in ROUTES if request["selector"] == "all" else (request["selector"],):
            if route not in ROUTES:
                raise CensusError("unknown DAG route")
            pair = (repo, route)
            if pair in expected:
                raise CensusError("duplicate route in manifest")
            expected[pair] = request
    if len(expected) > MAX_ROUTES:
        raise CensusError("more than six read-only routes")
    groups = {k: [] for k in expected}
    for receipt in receipts:
        validate_receipt(receipt, manifest)
        if receipt["execution_sha"] != receipt["target_sha"]:
            raise CensusError("receiver execution/target SHA mismatch")
        pair = (receipt["repo"], receipt["route"])
        if pair not in groups:
            raise CensusError("receipt outside planned route")
        if receipt not in groups[pair]:
            groups[pair].append(receipt)
    rows = []
    for (repo, route), req in expected.items():
        rs = groups[(repo, route)]
        row = {"repo": repo, "route": route, "head_sha": req["expected_sha"],
               "request_id": req["request_id"], "terminal_job_id": None,
               "run_attempt": None, "artifact": None,
               "status": "HOLD_RECEIPT_MISSING"}
        if len(rs) > 1:
            row["status"] = "HOLD_MULTIPLE_DISTINCT_RECEIPTS"
        elif rs:
            rec = rs[0]
            row["run_id"] = rec["run_id"]
            row["run_attempt"] = rec["run_attempt"]
            row["job_id"] = rec["job_id"]
            row["status"] = "HOLD_NATIVE_LOOKUP_REQUIRED"
            if native_fetch is not None:
                try:
                    run, job = native_fetch(repo, rec["run_id"], rec["job_id"])
                    status = _native_evidence(rec, run, job)
                except (OSError, ValueError, KeyError, RuntimeError):
                    status = "HOLD_NATIVE_LOOKUP_DENIED"
                row["status"] = status
                if status == "TERMINAL_SOURCE_BOUND":
                    row["terminal_job_id"] = rec["job_id"]
                    filename = (zip_paths or {}).get(_key(repo, rec["run_id"], route))
                    if filename is None:
                        row["status"] = "HOLD_ARTIFACT_BYTES_UNKNOWN"
                    else:
                        try:
                            row["artifact"] = verify_zip(filename, rec)
                            row["status"] = "VERIFIED_LOCAL_ZIP_AND_NATIVE_JOB"
                        except (CensusError, OSError, zipfile.BadZipFile):
                            row["status"] = "HOLD_ARTIFACT_BYTES_INVALID"
        rows.append(row)
    return {
        "schema": "qps-metric-postflight/v1", "wave": manifest["wave"],
        "eligible_repos": MAX_REPOS,
        "planned_repos": len(manifest["requests"]),
        "eligible_routes": MAX_ROUTES,
        "planned_routes": len(expected),
        "receipts_supplied": len(receipts),
        "terminal_native_jobs_confirmed": sum(
            x["terminal_job_id"] is not None for x in rows),
        "byte_verified_routes": sum(
            x["status"] == "VERIFIED_LOCAL_ZIP_AND_NATIVE_JOB" for x in rows),
        "native_test_count": None, "coverage_statement_uplift": None,
        "coverage_branch_uplift": None, "worker_hours": None,
        "root_closures_accepted": None, "merge_admission": "HOLD",
        "qps_engineering_acceptance": False,
        "canonical_530_zip_acceptance": False, "rows": rows,
    }


def _gh_json(repo, kind, ident):
    endpoint = f"repos/{repo}/actions/{kind}/{ident}"
    try:
        p = subprocess.run(["gh", "api", endpoint], capture_output=True,
                           text=True, timeout=40, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("authenticated GitHub CLI unavailable") from exc
    if p.returncode:
        raise RuntimeError("authenticated GitHub API refused native read")
    return json.loads(p.stdout)


def authenticated_fetch(repo, run_id, job_id):
    if repo not in ALLOWED_REPOS.values():
        raise CensusError("repository outside allowlist")
    return (_gh_json(repo, "runs", run_id),
            _gh_json(repo, "jobs", job_id))


def main(argv=None):
    p = argparse.ArgumentParser(description="QPS native terminal receipt fan-in")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--receipts", type=Path, required=True)
    p.add_argument("--zip-map", type=Path)
    p.add_argument("--verify-native", action="store_true",
                   help="Use independently authenticated gh api reads")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    manifest = json.loads(a.manifest.read_text(encoding="utf-8"))
    receipts = json.loads(a.receipts.read_text(encoding="utf-8"))
    zips = json.loads(a.zip_map.read_text(encoding="utf-8")) if a.zip_map else {}
    result = audit(manifest, receipts,
                   native_fetch=authenticated_fetch if a.verify_native else None,
                   zip_paths=zips)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "planned_routes", "terminal_native_jobs_confirmed",
        "byte_verified_routes", "merge_admission")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
