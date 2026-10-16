"""Source-exact read-only ABACUS MIP collector into Mission Control.

GitHub REST run + attempt jobs are acquired at fixed public host, without
redirects, mutation or convenience 'latest' selection. The producer itself is
imported from a separately git-verified exact ABACUS commit checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import tempfile
from http.client import HTTPSConnection
from pathlib import Path

from mip_source_consumer import consume

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
ROOT = "/repos/GBOGEB/ABACUS/actions/runs/"
MAX_PAGES = 12


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def integer(x):
    return type(x) is int and x > 0


def https_get(path, token=None):
    require(re.fullmatch(
        r"/repos/GBOGEB/ABACUS/actions/runs/[1-9][0-9]*"
        r"(?:/attempts/[1-9][0-9]*/jobs\?per_page=100&page=[1-9][0-9]*)?",
        path) is not None, "GitHub endpoint must be exact native run/jobs path")
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "code-purple-mip-native-source-consumer",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    client = HTTPSConnection("api.github.com", timeout=25)
    try:
        client.request("GET", path, headers=headers)
        response = client.getresponse()
        require(response.status == 200, "native GitHub API HTTP " +
                str(response.status))
        return json.load(response)
    finally:
        client.close()


def collect(source_sha, selections, getter=https_get):
    require(isinstance(source_sha, str) and SHA40.fullmatch(source_sha),
            "exact source SHA required")
    require(isinstance(selections, list) and 1 <= len(selections) <= 100,
            "bounded explicit run selection required")
    identity_set = set()
    runs, jobs = [], []
    for record in selections:
        require(isinstance(record, list) and len(record) == 2
                and all(integer(x) for x in record),
                "each selection requires exact native run/attempt")
        run_id, attempt = record
        require(run_id not in identity_set, "duplicate native run ID")
        identity_set.add(run_id)
        native = getter(ROOT + str(run_id))
        require(isinstance(native, dict)
                and native.get("id") == run_id
                and native.get("run_attempt") == attempt
                and native.get("head_sha") == source_sha
                and isinstance(native.get("path"), str)
                and native["path"].startswith(".github/workflows/")
                and native.get("html_url") ==
                    f"https://github.com/GBOGEB/ABACUS/actions/runs/{run_id}",
                "native workflow identity/attempt/SHA/path mismatch")
        runs.append({key: native.get(key) for key in (
            "id", "run_attempt", "head_sha", "name", "path", "html_url",
            "created_at", "status", "conclusion")})
        total = None
        received = []
        for page in range(1, MAX_PAGES + 1):
            result = getter(ROOT + str(run_id) + "/attempts/" + str(attempt) +
                            "/jobs?per_page=100&page=" + str(page))
            require(isinstance(result, dict)
                    and type(result.get("total_count")) is int
                    and 0 <= result["total_count"] <= MAX_PAGES * 100
                    and isinstance(result.get("jobs"), list),
                    "invalid attempt-specific jobs page")
            if total is None:
                total = result["total_count"]
            require(result["total_count"] == total
                    and len(result["jobs"]) <= 100
                    and len(received) + len(result["jobs"]) <= total,
                    "jobs pagination total changed")
            received.extend(result["jobs"])
            if len(received) == total:
                break
            require(result["jobs"], "partial empty jobs page")
        require(total is not None and len(received) == total,
                "native job census incomplete")
        seen = set()
        for job in received:
            require(isinstance(job, dict) and integer(job.get("id"))
                    and job["id"] not in seen
                    and job.get("run_id") == run_id
                    and job.get("run_attempt") == attempt
                    and job.get("head_sha") == source_sha,
                    "native job identity/SHA/attempt mismatch")
            seen.add(job["id"])
            slim = {key: job.get(key) for key in (
                "id", "run_id", "run_attempt", "head_sha", "name",
                "status", "conclusion", "created_at", "started_at",
                "completed_at")}
            if "runner_id" in job:
                slim["runner_id"] = job["runner_id"]
            if job.get("steps") is not None:
                require(isinstance(job["steps"], list), "invalid native step list")
                slim["steps"] = [{key: s.get(key) for key in (
                    "name", "number", "status", "conclusion")}
                    for s in job["steps"]]
            jobs.append(slim)
    return {"repository": "GBOGEB/ABACUS", "source_sha": source_sha,
            "runs": runs, "jobs": jobs, "gate_bindings": {}}


def canonical_producer(root, expected_sha):
    require(isinstance(expected_sha, str) and SHA40.fullmatch(expected_sha),
            "ABACUS producer exact commit required")
    p = Path(root)
    require(p.is_dir() and not p.is_symlink(), "missing ABACUS checkout")
    try:
        observed = subprocess.check_output(
            ["git", "-C", str(p), "rev-parse", "HEAD"],
            text=True, timeout=10).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("ABACUS provider git receipt missing") from exc
    require(observed == expected_sha, "ABACUS provider source drift")
    path = p / "tools" / "mip_ci_wave_telemetry.py"
    require(path.is_file() and not path.is_symlink(),
            "canonical producer module absent")
    spec = importlib.util.spec_from_file_location("canonical_abacus_mip", path)
    require(spec is not None and spec.loader is not None,
            "canonical module loader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def project(source_sha, selections, producer_module, getter=https_get):
    native = collect(source_sha, selections, getter)
    metrics = producer_module.summarize(native)
    raw = (json.dumps(metrics, sort_keys=True, indent=2,
                      allow_nan=False) + "\n").encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    binding = {
        "schema": "code-purple.mip-input-binding.v1",
        "repository": "GBOGEB/ABACUS",
        "head_sha": source_sha,
        "producer_path": "tools/mip_ci_wave_telemetry.py",
        "producer_sha256": digest,
        "artifact_bytes_authenticated": False,
        "authority_transfer": False,
    }
    downstream = consume(binding, metrics)
    return {
        "schema": "code-purple.mip.native-rest-bridge.v1",
        "source_sha": source_sha, "run_attempts": selections,
        "selected_workflow_count": len(native["runs"]),
        "selected_job_count": len(native["jobs"]),
        "native_request_payload_sha256": hashlib.sha256(json.dumps(
            native, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "canonical_producer_digest_sha256": digest,
        "native_job_metadata_collected": True,
        "native_artifact_zip_bytes_authenticated": False,
        "source_selection_full_repository_population": None,
        "first_red": {
            "unique_signatures": downstream["observed"]["first_red_unique_signatures"],
            "manifestations": downstream["observed"]["first_red_manifestations"],
            "red_job_denominator": downstream["observed"]["red_jobs_total"],
            "attribution_fraction": downstream["observed"]["first_red_attribution_fraction"],
        },
        "observed": downstream["observed"],
        "confidence_intervals": downstream["confidence_intervals"],
        "authority_transfer": False, "merge_authorized": False,
        "formal_root_closures": None, "qps_acceptance": "DEFER",
        "admission": "HOLD",
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--sha", required=True)
    p.add_argument("--run", action="append", required=True)
    p.add_argument("--abacus-checkout", type=Path, required=True)
    p.add_argument("--producer-sha", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    selections = []
    for raw in args.run:
        require(raw.count(":") == 1 and all(part.isdecimal()
                for part in raw.split(":")), "native run selector is ID:ATTEMPT")
        selections.append([int(x) for x in raw.split(":")])
    require(not args.out.is_symlink(), "output symlink not permitted")
    module = canonical_producer(args.abacus_checkout, args.producer_sha)
    result = project(args.sha, selections, module,
                     getter=lambda path: https_get(
                         path, os.environ.get("GITHUB_TOKEN")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=args.out.parent,
                                prefix="." + args.out.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp, args.out)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
