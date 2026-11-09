#!/usr/bin/env python3
"""Bridge the existing JADE TOP21 DevOps census into a private-safe user observation.

Read only. Structural source identities are not release proof, current native
check results, weighted closure, owner approval, or worker launch authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

CENSUS_SCHEMA = "jade.devops.census.v1"
OBSERVATION_SCHEMA = "jade.portfolio-observation.v1"
RECEIPT_SCHEMA = "jade.portfolio-census-bridge.v1"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
REPO = re.compile(r"GBOGEB/[A-Za-z0-9_.-]+\Z")
CORE = frozenset({
    "GBOGEB/pipeline-automation-hub", "GBOGEB/ABACUS", "GBOGEB/CODEX",
    "GBOGEB/gg_MATH", "GBOGEB/cryoplant-project",
    "GBOGEB/DOCX_RTM_Automation", "GBOGEB/GEMINI",
})


def need(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_stamp(value: str) -> str:
    need(isinstance(value, str), "BAD_TIMESTAMP_TYPE")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("BAD_TIMESTAMP") from exc
    need(parsed.tzinfo is not None, "NAIVE_TIMESTAMP")
    return parsed.astimezone(timezone.utc).isoformat()


def convert(census: dict, registry: dict, require_count: int | None = None) -> tuple[dict, dict]:
    need(isinstance(census, dict) and census.get("schema") == CENSUS_SCHEMA,
         "WRONG_CANONICAL_CENSUS")
    need(isinstance(registry, dict) and isinstance(registry.get("private_repos"), list),
         "NO_CANONICAL_PRIVATE_REGISTRY")
    private = registry["private_repos"]
    need(all(isinstance(x, str) and REPO.fullmatch(x) for x in private),
         "INVALID_PRIVATE_REGISTRY")
    need(len(private) == len(set(private)), "DUPLICATE_PRIVATE_OWNER")
    recorded = census.get("digest_sha256")
    body = {key: value for key, value in census.items() if key != "digest_sha256"}
    need(isinstance(recorded, str) and re.fullmatch(r"[0-9a-f]{64}", recorded)
         and sha256(canonical(body)) == recorded, "SOURCE_CENSUS_DIGEST_DRIFT")
    captured = utc_stamp(census.get("observed_at_utc"))
    rows = census.get("repos")
    need(isinstance(rows, list) and bool(rows), "EMPTY_SOURCE_POPULATION")
    if require_count is not None:
        need(type(require_count) is int and require_count > 0
             and len(rows) == require_count, "INCOMPLETE_DECLARED_POPULATION")
    names: set[str] = set()
    public, frontier = [], []
    masked = 0
    for row in rows:
        need(isinstance(row, dict), "INVALID_SOURCE_ROW")
        name = row.get("repo")
        need(isinstance(name, str) and REPO.fullmatch(name), "INVALID_REPO_IDENTITY")
        need(name not in names, "DUPLICATE_REPO")
        names.add(name)
        if name in private:
            # Do not deserialize private run, PR, issue or commit identifiers.
            public.append({"repo": name, "private": True, "head_sha": None})
            masked += 1
            continue
        reachable = row.get("reachable")
        need(type(reachable) is bool, "UNKNOWN_REACHABILITY")
        head = row.get("head_sha") if reachable else None
        need(not reachable or (isinstance(head, str) and SHA40.fullmatch(head)),
             "INVALID_PUBLIC_HEAD")
        branch = row.get("branch")
        need(isinstance(branch, str) and bool(branch)
             and re.fullmatch(r"[A-Za-z0-9_./-]+", branch)
             and ".." not in branch, "INVALID_BRANCH")
        url = (f"https://github.com/{name}/commit/{head}" if head
               else f"https://github.com/{name}")
        public.append({
            "repo": name, "private": False, "head_sha": head,
            "default_branch": branch, "observed_at": captured,
            "check_counts": None,
            "check_population": "NOT_COLLECTED_BY_STRUCTURAL_CENSUS",
            "check_collection_complete": False,
            "latest_release": None, "source_urls": [url],
        })
        if name in CORE:
            frontier.append({
                "id": "HEAD:" + name, "repository": name,
                "head_sha": head, "state": "SOURCE_ONLY" if head else "UNREACHABLE",
                "status": "NOT_REQUALIFIED",
                "blocker": "Native exact-head release and effective admission proof not supplied",
                "url": url, "source_urls": [url],
            })
    observation = {
        "schema": OBSERVATION_SCHEMA, "captured_at": captured,
        "repos": public, "frontier": frontier,
    }
    receipt = {
        "schema": RECEIPT_SCHEMA, "source_schema": CENSUS_SCHEMA,
        "source_digest_sha256": recorded, "observation_sha256": sha256(canonical(observation)),
        "observed_at_utc": captured, "source_repos": len(rows),
        "private_rows_masked": masked, "core_repos_present": len(names & CORE),
        "native_check_population": None, "qualified_current_point_release": None,
        "weighted_root_closure": None, "security_waiver": False,
        "dispatch_performed": False, "merge_admission": "HOLD",
        "authority_transfer": False,
        "note": "Source structure only: no native check counts or private row identifiers",
    }
    return observation, receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census", type=Path, required=True)
    parser.add_argument("--private-registry", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--require-count", type=int)
    args = parser.parse_args(argv)
    census = json.loads(args.census.read_text(encoding="utf-8"))
    registry = json.loads(args.private_registry.read_text(encoding="utf-8"))
    observation, receipt = convert(census, registry, args.require_count)
    for path, value in ((args.out, observation), (args.receipt, receipt)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(json.dumps(value, indent=2, sort_keys=True,
                                    ensure_ascii=False).encode("utf-8") + b"\n")
    print(json.dumps({"status": "STRUCTURAL_OBSERVATION_ONLY",
                      "source_repos": receipt["source_repos"],
                      "masked": receipt["private_rows_masked"],
                      "native_checks": None, "merge_admission": "HOLD"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
