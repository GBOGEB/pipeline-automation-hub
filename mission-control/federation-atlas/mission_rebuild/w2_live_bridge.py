#!/usr/bin/env python3
"""Read-only, bounded GitHub native observation to Mission Control W2.

No second gg_MATH statistical kernel, source mutation, dispatch, merge, or
cross-repository engineering acceptance. Each API response is an observation,
NOT an atomic cross-repository snapshot or verified downloaded artifact.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ATLAS = HERE.parent
SHA = re.compile(r"[a-f0-9]{40}\Z")
W1_REPO = "GBOGEB/pipeline-automation-hub"
GG_REPO = "GBOGEB/gg_MATH"
W1_PR, W1_RUN = 669, 39060705443
GG_RUNS = (39047980808, 39049078036)
W1_HEAD = "28b6b0dd6910cf730456fcdbf0c95b157626773b"
BRIDGE = ATLAS / "GG_MATH_CONVERGENCE_BRIDGE_v1.json"
ALLOWED_REPOS = frozenset((W1_REPO, GG_REPO))
SCHEMA = "missioncontrol.makeover.w2_native_observation.v1"


def require(condition, message):
    if not condition:
        raise ValueError("MC_W2_FAIL_CLOSED:" + message)


class ReadOnlyGithub:
    def __init__(self, token=None):
        self.token = token or None

    def __call__(self, repo, suffix):
        require(repo in ALLOWED_REPOS, "repository outside read-only allowlist")
        require(isinstance(suffix, str) and suffix.startswith("/")
                and ".." not in suffix and "://" not in suffix, "unsafe API path")
        url = "https://api.github.com/repos/" + repo + suffix
        headers = {"Accept": "application/vnd.github+json",
                   "User-Agent": "missioncontrol-w2-readonly",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as rsp:
            require(rsp.status == 200, "unexpected GitHub status")
            raw = rsp.read(2_500_001)
        require(len(raw) <= 2_500_000, "bounded API response")
        return json.loads(raw)


def run_status(run, expected, run_id):
    require(isinstance(run, dict) and run.get("id") == run_id, "native run identity")
    require(run.get("head_sha") == expected, "native head SHA")
    require(type(run.get("run_attempt")) is int and run["run_attempt"] >= 1,
            "native attempt identity")
    require(run.get("status") in ("queued", "waiting", "pending", "requested",
                                  "in_progress", "completed"), "run status enum")
    return {"run_id": run_id, "head_sha": expected,
            "attempt": run["run_attempt"], "status": run["status"],
            "conclusion": run.get("conclusion"),
            "url": "https://github.com/" + (W1_REPO if run_id == W1_RUN else GG_REPO)
                   + "/actions/runs/" + str(run_id),
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at")}


def sample_jobs(payload, name):
    require(isinstance(payload, dict) and type(payload.get("total_count")) is int,
            name + " job census")
    total = payload["total_count"]
    rows = payload.get("jobs", [])
    require(isinstance(rows, list) and 0 <= len(rows) <= total, name + " job population")
    for r in rows:
        require(type(r.get("id")) is int and r.get("status") in
                ("queued", "waiting", "pending", "in_progress", "completed"), name + " job record")
    covered = total == len(rows)
    return {"total": total, "observed": len(rows), "complete": covered,
            "passing": sum(r.get("conclusion") == "success" for r in rows) if covered else None,
            "failing": sum(r.get("conclusion") == "failure" for r in rows) if covered else None,
            "queued": sum(r.get("status") == "queued" for r in rows) if covered else None,
            "job_ids": [r["id"] for r in rows], "actual_worker_hours": None}


def artifacts(payload):
    require(isinstance(payload, dict) and type(payload.get("total_count")) is int,
            "artifact census")
    rows = payload.get("artifacts", [])
    require(len(rows) <= payload["total_count"], "artifact population")
    return {"total": payload["total_count"], "observed": len(rows),
            "complete": len(rows) == payload["total_count"],
            "records": [{"id": v.get("id"), "name": v.get("name"),
                         "zip_bytes_reported": v.get("size_in_bytes"),
                         "github_digest_reported": v.get("digest"),
                         "archive_bytes_independently_verified": False}
                        for v in rows]}


def maybe(client, repo, suffix, errors, key):
    try:
        return client(repo, suffix)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as e:
        errors[key] = type(e).__name__ + ": " + str(e)[:120]
        return None


def make(client, head, bridge, observed_at):
    require(isinstance(head, str) and SHA.fullmatch(head), "consumer checkout identity")
    require(bridge.get("schema") == "missioncontrol.gg_math_convergence_bridge.v1"
            and bridge.get("snapshot_atomic") is False
            and bridge.get("controls", {}).get("merge_admission") == "HOLD"
            and bridge.get("controls", {}).get("authority_transfer") is False,
            "canonical gg_MATH bridge custody")
    require(bridge["provider"]["source_head_sha"] == "37afe75d9911691698a849b21fcfad0df1844432",
            "pinned gg_MATH producer head")
    require(bridge["provider"]["native_candidate_run"] == GG_RUNS[0],
            "provider run identity")
    require(bridge["method"]["live_pulse_receipts_ingested"] == 0,
            "unacknowledged bridge ingestion")
    errors = {}
    first = maybe(client, W1_REPO, "/actions/runs/" + str(W1_RUN), errors, "w1_run")
    w1 = run_status(first, W1_HEAD, W1_RUN) if first else None
    jobs_raw = maybe(client, W1_REPO, "/actions/runs/" + str(W1_RUN) + "/jobs?per_page=100",
                     errors, "w1_jobs") if first else None
    w1_jobs = sample_jobs(jobs_raw, "W1") if jobs_raw else None
    a_raw = maybe(client, W1_REPO, "/actions/runs/" + str(W1_RUN) + "/artifacts?per_page=100",
                  errors, "w1_artifacts") if first else None
    w1_artifacts = artifacts(a_raw) if a_raw else None
    reviews_raw = maybe(client, W1_REPO, "/pulls/669/reviews?per_page=100", errors, "reviews")
    require(reviews_raw is None or isinstance(reviews_raw, list), "review response type")
    reviews_count = len(reviews_raw) if reviews_raw is not None and len(reviews_raw) < 100 else None
    independent_approvals = (sum(x.get("state") == "APPROVED" and
                                 x.get("user", {}).get("login") != "GBOGEB"
                                 for x in reviews_raw) if reviews_count is not None else None)
    queued_raw = maybe(client, W1_REPO, "/actions/runs?status=queued&per_page=1",
                       errors, "fleet_queued")
    running_raw = maybe(client, W1_REPO, "/actions/runs?status=in_progress&per_page=1",
                        errors, "fleet_in_progress")
    def count(p):
        return (p.get("total_count")
                if (isinstance(p, dict) and type(p.get("total_count")) is int
                    and p["total_count"] >= 0) else None)
    # Cross-repository actions: a repo-scoped token may not have gg_MATH access.
    provider = []
    for n, source in zip(GG_RUNS, (bridge["provider"]["source_head_sha"],
                                   "d073992785c68820c3c9aa44260314fb82bd8f34")):
        rr = maybe(client, GG_REPO, "/actions/runs/" + str(n), errors, "gg_run_" + str(n))
        status = run_status(rr, source, n) if rr else None
        jj = maybe(client, GG_REPO, "/actions/runs/" + str(n) + "/jobs?per_page=100",
                   errors, "gg_jobs_" + str(n)) if rr else None
        aa = maybe(client, GG_REPO, "/actions/runs/" + str(n) + "/artifacts?per_page=100",
                   errors, "gg_artifacts_" + str(n)) if rr else None
        provider.append({"run": status, "jobs": sample_jobs(jj, "gg_MATH") if jj else None,
                         "artifacts": artifacts(aa) if aa else None})
    match = provider[0]["run"]
    drift = ("CONSUMER_SNAPSHOT_STALE_PROVIDER_TERMINAL" if match is not None
             and match["status"] == "completed"
             and bridge["provider"]["native_conclusion_at_observation"] == "QUEUED"
             else "FRESHNESS_UNVERIFIED" if match is None else "NO_STALE_TERMINAL_PROOF")
    available = (w1 is not None and w1["status"] == "completed"
                 and w1["conclusion"] == "success"
                 and w1_jobs is not None and w1_jobs["complete"]
                 and w1_jobs["failing"] == 0)
    return {"schema": SCHEMA, "source_head_sha": head,
            "observed_at_utc": observed_at,
            "atomic_cross_repo_snapshot": False, "evidence_class": "GITHUB_API_METADATA_READ_ONLY",
            "w1": {"pr": W1_PR, "source_head_sha": W1_HEAD,
                   "run": w1, "jobs": w1_jobs, "artifacts": w1_artifacts,
                   "attempt_2": ("NOT_PRESENT" if w1 and w1["attempt"] == 1
                                 else "ATTEMPT_EXISTS_NEEDS_JOB_CHECK" if w1 else "UNKNOWN"),
                   "native_success_with_known_job_population": bool(available)},
            "fleet": {"queued_run_count": count(queued_raw),
                      "in_progress_run_count": count(running_raw),
                      "capacity_slots": None, "actual_worker_hours": None,
                      "queue_velocity": None, "queue_p95": None,
                      "population_clock": "NON_ATOMIC_READBACK"},
            "review": {"recorded_reviews": reviews_count,
                       "independent_approvals": independent_approvals,
                       "merge_admission": "HOLD",
                       "historical_merged_without_dov": True},
            "gg_math": {"provider": provider, "stale_bridge_classification": drift,
                        "canonical_math_source": "kernels/convergence_control.py",
                        "canonical_plotly_source": "mission/federation/convergence_dashboard.py",
                        "native_live_pulse_receipts_ingested": 0,
                        "provider_plotly_artifact_bytes_verified_by_this_consumer": False},
            "unknown_burndown": {
                "coverage": {"status": "UNKNOWN",
                             "covered_statements": None, "total_statements": None,
                             "covered_branches": None, "total_branches": None,
                             "delta_pp": None, "unblock": "CURRENT_HEAD_NATIVE_COVERAGE_MEMBER_WITH_MATCHED_SCOPE"},
                "worker": {"status": "UNKNOWN_CAPACITY_AND_HOURS",
                           "slots": None, "hours": None,
                           "unblock": "NATIVE_RUNNER_ASSIGNMENT_AND_JOB_START_END"},
                "reviews": {"status": "KNOWN_ZERO" if reviews_count == 0
                            else "RECORDED_NOT_ACCEPTANCE" if reviews_count is not None
                            else "UNKNOWN", "observed": reviews_count,
                            "unblock": "INDEPENDENT_ELIGIBLE_APPROVAL_BEFORE_NEXT_GOVERNED_MERGE"},
                "method": {"m1": "STRUCTURAL_MODEL_NOT_GAGE_RR",
                           "m2": "HOLD_NO_REPLICATED_MATCHED_SERIES",
                           "m3": "HOLD_NO_CAPABILITY_CTQ",
                           "pca": "NOT_ASSESSABLE_NO_AUTHENTICATED_FEATURE_VECTORS",
                           "bt": "NOT_ASSESSABLE_NO_CONNECTED_PAIRED_COMPARISONS",
                           "six_sigma": "NOT_ATTESTED",
                           "unblock": "GG_MATH_NATIVE_PULSE_RECEIPTS_AND_INDEPENDENT_CTQ"} },
            "governance": {"merge_admission": "HOLD", "authority_transfer": False,
                           "security_waiver": False, "qps_acceptance": None,
                           "formal_root_closure_credit": 0},
            "readback_errors": errors}


def write_receipt(snapshot, output):
    path = Path(output)
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_text(json.dumps(snapshot, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--head", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--fixture", default=None,
                   help="Offline fixture only: output clearly remains synthetic test data")
    a = p.parse_args()
    bridge = json.loads(BRIDGE.read_text(encoding="utf-8"))
    if a.fixture:
        payload = json.loads(Path(a.fixture).read_text(encoding="utf-8"))
        def source(repo, suffix):
            k = repo + suffix
            require(k in payload, "fixture missing " + k)
            return payload[k]
        client = source
        evidence_kind = "SYNTHETIC_TEST_FIXTURE_NOT_NATIVE"
    else:
        client = ReadOnlyGithub(os.environ.get("GITHUB_TOKEN"))
        evidence_kind = "GITHUB_API_METADATA_READ_ONLY"
    observed = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    result = make(client, a.head, bridge, observed)
    result["evidence_class"] = evidence_kind
    digest = write_receipt(result, a.out)
    print(json.dumps({"W2_READ_ONLY_STATUS": "CAPTURED_WITH_HOLDS",
                      "sha256": digest,
                      "w1_attempt": result["w1"]["run"]["attempt"] if result["w1"]["run"] else None,
                      "gg_math_freshness": result["gg_math"]["stale_bridge_classification"]}))
