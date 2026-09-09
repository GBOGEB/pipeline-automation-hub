#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
import yaml

ALLOWED = {"MODERNIZE_AND_FEDERATE","KEEP_AS_VALIDATION_SATELLITE","DEFER","STORAGE_ONLY","REJECT"}
PRIMARY = {"GBOGEB/cryoplant-project","GBOGEB/ABACUS","GBOGEB/CODEX"}

def validate(path: Path) -> list[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if data.get("schema") != "triage-renegade-incubator/v0.2": errors.append("unexpected schema")
    if data.get("authority") != "DISCOVERY_ONLY": errors.append("authority must remain DISCOVERY_ONLY")
    if data.get("release_credit_allowed") is not False: errors.append("release_credit_allowed must be false")
    if set(data.get("primary_repositories", [])) != PRIMARY: errors.append("primary repository set changed")
    policy = data.get("routing_policy") or {}
    if policy.get("merge_rule") != "modernize_locally_federate_bounded_delta": errors.append("unexpected merge rule")
    if policy.get("duplicate_code_bulk_merge_allowed") is not False: errors.append("bulk duplicate merge must be disabled")
    candidates = data.get("candidates") or []
    seen=set()
    for row in candidates:
        repo=row.get("repository")
        if not repo or repo in seen: errors.append(f"duplicate or missing repository: {repo!r}")
        seen.add(repo)
        if row.get("disposition") not in ALLOWED: errors.append(f"invalid disposition for {repo}")
        if not isinstance(row.get("approx_size_kb"), int): errors.append(f"missing integer approx_size_kb for {repo}")
        if row.get("disposition") not in {"DEFER","STORAGE_ONLY","REJECT"} and not row.get("observed_sha"): errors.append(f"promotion-capable candidate lacks observed_sha: {repo}")
        if row.get("bridge_to") not in PRIMARY | {"TRIAGE"}: errors.append(f"invalid bridge target for {repo}")
    coverage=data.get("coverage") or {}
    if coverage.get("explored_repositories") != len(candidates): errors.append("coverage denominator does not match candidate count")
    return errors

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("registry", nargs="?", default="triage/renegade_incubator/registry.yaml")
    errors=validate(Path(parser.parse_args().registry))
    if errors:
        [print(f"FAIL: {e}") for e in errors]; return 1
    print("PASS: W02 satellite coverage registry is bounded and fail-closed"); return 0
if __name__ == "__main__": raise SystemExit(main())
