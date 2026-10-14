#!/usr/bin/env python3
"""MissionControl plan-only QPS/gg_MATH P4 wormhole DAG.

Never dispatch runners or turn a proposed source identity into a native attestation.
MissionControl owns routing and first-red ordering; QPS child owns disposition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
STAGES = (
    ("P1", "GBOGEB/gg_MATH", "SOURCE_BOUND_NATIVE_PROVIDER_PROOF", ()),
    ("P4_KEB", "GBOGEB/CODEX", "EXACT_SEMANTIC_PROVENANCE_WITNESS", ("P1",)),
    ("P4_DOW", "GBOGEB/ABACUS", "INDEPENDENT_RUNTIME_AND_TELEMETRY_RECEIPT", ("P4_KEB",)),
    ("P3_QPS", "GBOGEB/cryoplant-project", "PRIVATE_CHILD_SOURCE_AND_OWNER_DISPOSITION", ("P4_DOW",)),
    ("P4_RETURN", "GBOGEB/pipeline-automation-hub", "CONTROL_REENTRY_AND_REX_RETURN", ("P3_QPS",)),
)


def canonical_sha256(value: dict[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     allow_nan=False, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_dag(stages: list[dict[str, Any]]) -> None:
    nodes = set()
    for stage in stages:
        ident = stage["id"]
        if ident in nodes:
            raise ValueError("duplicate stage id")
        for dep in stage["needs"]:
            if dep not in nodes:
                raise ValueError("non-topological or unknown dependency")
        nodes.add(ident)
    if len(stages) != len(STAGES) or nodes != {s[0] for s in STAGES}:
        raise ValueError("missing canonical stage")


def plan(*, provider_sha: str, artifact_sha256: str) -> dict[str, Any]:
    if not isinstance(provider_sha, str) or not SHA.fullmatch(provider_sha):
        raise ValueError("provider sha must be exact 40-hex")
    if not isinstance(artifact_sha256, str) or not DIGEST.fullmatch(artifact_sha256):
        raise ValueError("provider artifact must be exact sha256")
    stages = [
        {
            "id": ident, "repo": repo, "requires": requirement,
            "needs": list(deps), "state": "BLOCKED_MISSING_AUTHENTICATED_RECEIPT",
            "run_id": None, "job_id": None, "verified_source_sha": None,
            "worker_executed": False, "authority_transfer": False,
        }
        for ident, repo, requirement, deps in STAGES
    ]
    validate_dag(stages)
    body = {
        "schema": "missioncontrol.qps_math_wormhole_plan/v1",
        "mission": "QPS-P4-GG-MATH-WORMHOLE",
        "provider_sha": provider_sha,
        "provider_artifact_sha256": artifact_sha256,
        "source_contract": "gg-math-qps-wormhole/v1",
        "qps_contract": "qps-triage-child-contract/1.1.0",
        "mode": "PLAN_ONLY_NO_DISPATCH",
        "steps": stages,
        "measurements": {
            "planned_stages": len(stages),
            "authenticated_stage_receipts": 0,
            "workers_executed": 0,
            "qps_dispositions": 0,
            "deferred_stages": len(stages),
            "first_red": "P1:SOURCE_BOUND_NATIVE_PROVIDER_PROOF",
        },
        "current_QTG_modified": False,
        "qps_child_disposition": "DEFER",
        "authority_transfer": False,
        "engineering_acceptance": False,
        "formal_credit_delta": 0,
    }
    return {**body, "receipt_sha256": canonical_sha256(body)}


def verify(result: dict[str, Any]) -> None:
    if not isinstance(result, dict):
        raise ValueError("plan not object")
    expected = plan(provider_sha=result.get("provider_sha", ""),
                    artifact_sha256=result.get("provider_artifact_sha256", ""))
    if result != expected:
        raise ValueError("modified topology, execution, authority or receipt hash")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-sha", required=True)
    parser.add_argument("--artifact-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    output = plan(provider_sha=args.provider_sha, artifact_sha256=args.artifact_sha256)
    verify(output)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"mode": output["mode"], "measurements": output["measurements"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
