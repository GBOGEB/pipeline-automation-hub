#!/usr/bin/env python3
"""Fail-closed smoke validator for TRIAGE renegade-incubator registry."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

ALLOWED = {
    "KEEP_AND_FEDERATE",
    "INCUBATE_AND_SCRUB",
    "BRIDGE_AND_SCRUB",
    "KEEP_AS_VALIDATION_SATELLITE",
    "SCOUT",
    "DEFER",
    "REJECT",
}
PRIMARY = {
    "GBOGEB/cryoplant-project",
    "GBOGEB/ABACUS",
    "GBOGEB/CODEX",
}


def validate(path: Path) -> list[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if data.get("schema") != "triage-renegade-incubator/v0.1":
        errors.append("unexpected schema")
    if data.get("authority") != "DISCOVERY_ONLY":
        errors.append("authority must remain DISCOVERY_ONLY")
    if data.get("release_credit_allowed") is not False:
        errors.append("release_credit_allowed must be false")
    if set(data.get("primary_repositories", [])) != PRIMARY:
        errors.append("primary repository set changed")
    policy = data.get("routing_policy") or {}
    if policy.get("merge_rule") != "nuance_only":
        errors.append("merge_rule must be nuance_only")
    if policy.get("duplicate_code_bulk_merge_allowed") is not False:
        errors.append("bulk duplicate merge must be disabled")
    candidates = data.get("candidates") or []
    seen: set[str] = set()
    for row in candidates:
        repo = row.get("repository")
        if not repo or repo in seen:
            errors.append(f"duplicate or missing repository: {repo!r}")
        seen.add(repo)
        if row.get("disposition") not in ALLOWED:
            errors.append(f"invalid disposition for {repo}")
        if not isinstance(row.get("approx_size_kb"), int):
            errors.append(f"missing integer approx_size_kb for {repo}")
        if row.get("disposition") not in {"SCOUT", "DEFER", "REJECT"} and not row.get("observed_sha"):
            errors.append(f"promotion-capable candidate lacks observed_sha: {repo}")
        if row.get("bridge_to") not in PRIMARY | {"TRIAGE"}:
            errors.append(f"invalid bridge target for {repo}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", nargs="?", default="triage/renegade_incubator/registry.yaml")
    args = parser.parse_args()
    errors = validate(Path(args.registry))
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: TRIAGE renegade incubator registry is bounded and fail-closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
