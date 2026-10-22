#!/usr/bin/env python3
"""Second-stage evidence-only five-repository qualification.

A scheduled workflow may finish green with a DEFERRED census. This consumer
runs ONLY after the source job produced NATIVE_READ and its same-run artifact.
It never accepts an offline fixture, a token-missing diagnostic or a repository
status alone as a fresh authenticated readback. It does not make the six-repo
canonical #531 claim, and grants no merger or engineering acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SHA = re.compile(r"[a-f0-9]{40}\Z")
EXPECTED = {
    "ABACUS": "main",
    "CODEX": "main",
    "pipeline-automation-hub": "master",
    "cryoplant-project": "main",
    "gg_MATH": "main",
}


def qualify(directory: Path, *, expected_master: str, run_id: int,
            attempt: int) -> dict:
    if not isinstance(expected_master, str) or not SHA.fullmatch(expected_master):
        raise ValueError("NATIVE_CENSUS_HOLD: invalid source head")
    if type(run_id) is not int or run_id < 1 or type(attempt) is not int or attempt < 1:
        raise ValueError("NATIVE_CENSUS_HOLD: invalid run/attempt")
    directory = Path(directory)
    raw_snapshot = (directory / "snapshot.json").read_bytes()
    snapshot = json.loads(raw_snapshot)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    listed = manifest.get("files_sha256")
    if (manifest.get("schema") != "codepurple.live.bundle.v1" or
            not isinstance(listed, dict) or
            set(listed) != {"snapshot.json", "nodes.json", "edges.json",
                            "diagnostics.json", "events.ndjson"}):
        raise ValueError("NATIVE_CENSUS_HOLD: incomplete manifest")
    for member, expected_digest in listed.items():
        if not isinstance(expected_digest, str) or not re.fullmatch(
                r"[a-f0-9]{64}", expected_digest):
            raise ValueError("NATIVE_CENSUS_HOLD: missing member digest")
        physical = directory / member
        if not physical.is_file() or hashlib.sha256(
                physical.read_bytes()).hexdigest() != expected_digest:
            raise ValueError("NATIVE_CENSUS_HOLD: member digest mismatch")
    if (snapshot.get("schema") != "codepurple.disjoint_live_census.v1" or
            snapshot.get("origin") != "NATIVE_GITHUB_READ" or
            snapshot.get("observation_quality") !=
            "NATIVE_READ_ONLY_NOT_ARTIFACT_VERIFIED"):
        raise ValueError("NATIVE_CENSUS_HOLD: fixture/connector is not native GET")
    if manifest.get("source_digest") != snapshot.get("source_digest"):
        raise ValueError("NATIVE_CENSUS_HOLD: source/manifest digest mismatch")
    repos = snapshot.get("repositories")
    if (not isinstance(repos, list) or len(repos) != len(EXPECTED) or
            len({r.get("name") for r in repos}) != len(EXPECTED)):
        raise ValueError("NATIVE_CENSUS_HOLD: incomplete five-repo census")
    mapped = {r["name"]: r for r in repos}
    if set(mapped) != set(EXPECTED):
        raise ValueError("NATIVE_CENSUS_HOLD: wrong repository identity")
    for name, branch in EXPECTED.items():
        r = mapped[name]
        if r.get("branch") != branch or not isinstance(r.get("sha"), str) or not SHA.fullmatch(r["sha"]):
            raise ValueError("NATIVE_CENSUS_HOLD: repo branch/SHA missing")
    if mapped["pipeline-automation-hub"]["sha"] != expected_master:
        raise ValueError("NATIVE_CENSUS_HOLD: checkout/federation head changed")
    authority = snapshot.get("authority", {})
    if (authority.get("merge_authorized") is not False or
            authority.get("security_waiver") is not False or
            authority.get("root_closures_verified") is not None or
            authority.get("admission") != "HOLD" or
            authority.get("crew_dispatch") != "STAGED_NOT_LAUNCHED"):
        raise ValueError("NATIVE_CENSUS_HOLD: authority promotion")
    return {
        "schema": "codepurple.five_repo.native_read_qualification.v1",
        "qualification": "FIVE_REPO_NATIVE_GET_BUNDLE_VERIFIED",
        "six_repo_canonical_breadth": None,
        "source_sha": expected_master,
        "workflow_run_id": run_id,
        "run_attempt": attempt,
        "member_count": len(listed),
        "source_digest": snapshot["source_digest"],
        "rechecked_repositories": sorted(EXPECTED),
        "accepted_causal_root_closures": None,
        "qps_owner_acceptance": "WITHHELD",
        "merge_admission": "HOLD",
        "security_waiver": False,
        "authority_transfer": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--directory", required=True, type=Path)
    p.add_argument("--expected-master", required=True)
    p.add_argument("--run-id", required=True, type=int)
    p.add_argument("--attempt", required=True, type=int)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    q = qualify(a.directory, expected_master=a.expected_master,
                run_id=a.run_id, attempt=a.attempt)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(q, indent=2, sort_keys=True)+"\n",
                        encoding="utf-8")
    print("FIVE_REPO_QUALIFIED=PASS; CANONICAL_SIX_REPO_BREADTH=UNKNOWN; "
          "ADMISSION=HOLD")


if __name__ == "__main__":
    main()
