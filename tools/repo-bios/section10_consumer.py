#!/usr/bin/env python3
"""Read-only join of genuine BIOS output and canonical Top21 receipt; never admission."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
H64 = re.compile(r"[0-9a-f]{64}\Z")
REPO = re.compile(r"GBOGEB/[A-Za-z0-9_.-]+\Z")


def need(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(obj: object) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def consume(bios: dict, observation: dict, receipt: dict, expected_sha: str) -> dict:
    need(isinstance(expected_sha, str) and SHA.fullmatch(expected_sha), "INVALID_EXPECTED_SHA")
    need(isinstance(bios, dict) and bios.get("schema") == "jade.repo-bios.source-report.v1", "BIOS_SCHEMA")
    need(bios.get("authority") == "SOURCE_INVENTORY_ONLY"
         and bios.get("merge_authorized") is False
         and bios.get("release_authorized") is False, "BIOS_AUTHORITY")
    need(isinstance(bios.get("repositories"), list) and bios["repositories"], "BIOS_EMPTY")
    bios_repos = {}
    for row in bios["repositories"]:
        need(isinstance(row, dict), "BIOS_ROW")
        name, sha = row.get("repository"), row.get("source_sha")
        need(isinstance(name, str) and REPO.fullmatch(name) and name not in bios_repos, "BIOS_REPO_ID")
        need(isinstance(sha, str) and SHA.fullmatch(sha), "BIOS_SHA")
        need(isinstance(row.get("tree_oid"), str) and SHA.fullmatch(row["tree_oid"]), "BIOS_TREE")
        need(isinstance(row.get("runtime_kpis"), dict)
             and row["runtime_kpis"].get("state") == "UNKNOWN", "BIOS_RUNTIME")
        bios_repos[name] = sha
    need(bios_repos.get("GBOGEB/pipeline-automation-hub") == expected_sha, "BIOS_NOT_EXACT_HEAD")
    need(isinstance(observation, dict) and observation.get("schema") == "jade.portfolio-observation.v1",
         "TOP21_SCHEMA")
    need(isinstance(receipt, dict)
         and receipt.get("schema") == "jade.portfolio-census-bridge.v1"
         and receipt.get("source_schema") == "jade.devops.census.v1", "TOP21_RECEIPT_SCHEMA")
    need(receipt.get("merge_admission") == "HOLD"
         and receipt.get("authority_transfer") is False
         and receipt.get("dispatch_performed") is False, "TOP21_AUTHORITY")
    need(isinstance(receipt.get("observation_sha256"), str)
         and H64.fullmatch(receipt["observation_sha256"])
         and receipt["observation_sha256"] == digest(observation), "TOP21_DIGEST")
    need(isinstance(receipt.get("source_digest_sha256"), str)
         and H64.fullmatch(receipt["source_digest_sha256"]), "TOP21_SOURCE_DIGEST")
    rows = observation.get("repos")
    need(isinstance(rows, list) and len(rows) == 21
         and receipt.get("source_repos") == 21, "TOP21_POPULATION")
    top21, private = {}, 0
    for row in rows:
        need(isinstance(row, dict), "TOP21_ROW")
        name = row.get("repo")
        need(isinstance(name, str) and REPO.fullmatch(name) and name not in top21, "TOP21_REPO_ID")
        if row.get("private") is True:
            need(row.get("head_sha") is None, "TOP21_PRIVATE_LEAK")
            private += 1
            top21[name] = None
        else:
            sha = row.get("head_sha")
            need(sha is None or (isinstance(sha, str) and SHA.fullmatch(sha)), "TOP21_SHA")
            top21[name] = sha
    need(receipt.get("private_rows_masked") == private, "TOP21_PRIVATE_COUNT")
    need(receipt.get("native_check_population") is None
         and receipt.get("qualified_current_point_release") is None, "TOP21_FALSE_NATIVE")
    return {
        "schema": "portfolio.bios-top21-native/v1",
        "integration_sha": expected_sha,
        "bios_digest_sha256": digest(bios),
        "top21_digest_sha256": digest(observation),
        "top21_source_digest_sha256": receipt["source_digest_sha256"],
        "top21_original_observed_at": receipt.get("observed_at_utc"),
        "bios_repositories": sorted(bios_repos),
        "top21_count": len(rows),
        "private_rows_masked": private,
        "matched_repositories": sorted(set(bios_repos) & set(top21)),
        "qualification": "NATIVE_INPUT_VALIDATED_SOURCE_ONLY",
        "release_authorized": False,
        "merge_admission": "HOLD",
        "current_native_check_population": None,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bios", type=Path, required=True)
    p.add_argument("--top21", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--expected-sha", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    docs = [json.loads(path.read_text(encoding="utf-8"))
            for path in (args.bios, args.top21, args.receipt)]
    result = consume(*docs, args.expected_sha)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(json.dumps(result, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    print(json.dumps({"qualification": result["qualification"],
                      "integration_sha": result["integration_sha"],
                      "top21_count": result["top21_count"],
                      "admission": "HOLD"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
