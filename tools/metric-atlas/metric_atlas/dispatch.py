"""Explicitly authorized, source-bound cross-repo QPS census dispatch only.

Dry-run is the default. Dispatch acknowledges an event enqueue (HTTP 204), not
receiver execution, tests, artifact validation or an admission decision.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

from .census import ALLOWED_REPOS, SCHEMA, CensusError, canonical


class DispatchError(ValueError):
    pass


def plan(manifest):
    if manifest.get("schema") != SCHEMA or manifest.get("mode") != "READ_ONLY":
        raise DispatchError("census schema/mode mismatch")
    reqs = manifest.get("requests")
    if not isinstance(reqs, list) or len(reqs) > 3:
        raise DispatchError("unbounded request slice")
    if len(set(q.get("repo") for q in reqs)) != len(reqs):
        raise DispatchError("duplicate target repository")
    for q in reqs:
        if q.get("repo") != ALLOWED_REPOS.get(q.get("lane")):
            raise DispatchError("out-of-allowlist target")
        if q.get("state") != "PLANNED_NOT_DISPATCHED":
            raise DispatchError("invalid dispatch prestate")
    return reqs


def dispatch(manifest, *, execute=False, environment=None, opener=None):
    reqs = plan(manifest)
    out = [{"repo": q["repo"], "request_id": q["request_id"],
            "expected_sha": q["expected_sha"], "state": "DRY_RUN_NOT_TRIGGERED"}
           for q in reqs]
    if not execute:
        return {"schema": "qps-dispatch-receipt/v1", "events": out,
                "triggered": 0, "receiver_job_ids": None, "receiver_results": None}
    env = environment if environment is not None else os.environ
    if (env.get("GITHUB_REPOSITORY") != "GBOGEB/pipeline-automation-hub" or
            env.get("GITHUB_REF") != "refs/heads/master" or
            env.get("GITHUB_EVENT_NAME") != "workflow_dispatch" or
            env.get("QPS_DISPATCH_APPROVED") != "YES"):
        raise DispatchError("owner-controlled default-branch approval missing")
    token = env.get("QPS_TRIAGE_DISPATCH_TOKEN")
    if not token or len(token) < 20:
        raise DispatchError("separate cross-repository dispatch credential missing")
    http_open = opener or urllib.request.urlopen
    for i, q in enumerate(reqs):
        url = "https://api.github.com/repos/{}/dispatches".format(q["repo"])
        body = {"event_type": "qps-metric-census-v1", "client_payload": {
            "wave": q["wave"], "selector": q["selector"],
            "lane": q["lane"], "expected_sha": q["expected_sha"],
            "request_id": q["request_id"]}}
        req = urllib.request.Request(
            url, data=canonical(body).encode("utf-8"), method="POST",
            headers={"Authorization": "Bearer " + token,
                     "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json",
                     "User-Agent": "QPS-TRIAGE-Control-Plane"})
        with http_open(req, timeout=20) as response:
            if response.status != 204:
                raise DispatchError("repository dispatch did not return HTTP 204")
        out[i]["state"] = "HTTP_204_EVENT_ENQUEUED_NOT_PROVEN_EXECUTED"
    return {"schema": "qps-dispatch-receipt/v1", "events": out,
            "triggered": len(reqs), "receiver_job_ids": None, "receiver_results": None}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--execute", action="store_true")
    a = p.parse_args()
    try:
        payload = dispatch(json.loads(a.manifest.read_text(encoding="utf-8")), execute=a.execute)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"dispatch_mode": "EXECUTE" if a.execute else "DRY_RUN",
                          "events_enqueued": payload["triggered"]}))
    except (ValueError, OSError) as exc:
        p.exit(2, "DISPATCH_HOLD: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
