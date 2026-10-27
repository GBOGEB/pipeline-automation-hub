#!/usr/bin/env python3
"""Read-only public-repository ingress audit of proposed taxonomy census assets.

An archive SHA proves byte identity, not source classification, declassification
or owner consent. Never assign PUBLIC_ACCEPTED from self-declared manifest values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
from pathlib import Path

SCHEMA = "jade.taxonomy-public-ingress.v1"
SHA = re.compile(r"^[a-f0-9]{64}$", re.I)
RISK_EXT = (".zip", ".tar", ".gz", ".7z", ".sqlite", ".parquet",
            ".xlsx", ".pdf", ".json", ".csv", ".html")
ROOT = "mission-control/issue_rank/title_census/"


def _canonical_path(path: str) -> str:
    if not isinstance(path, str) or not path or "\\" in path or "\x00" in path:
        raise ValueError("INVALID_SOURCE_PATH")
    if path.startswith("/") or path.startswith("../") or "/../" in path or "//" in path:
        raise ValueError("UNSAFE_SOURCE_PATH")
    norm = posixpath.normpath(path)
    if norm != path or norm.startswith("../") or norm == ".":
        raise ValueError("NON_CANONICAL_SOURCE_PATH")
    return norm


def audit(changed: list[dict], attestations: dict | None = None) -> dict:
    if not isinstance(changed, list):
        raise ValueError("CHANGES_NOT_LIST")
    claims = attestations or {}
    if not isinstance(claims, dict):
        raise ValueError("ATTESTATIONS_NOT_OBJECT")
    seen, candidates = set(), []
    for row in changed:
        if not isinstance(row, dict):
            raise ValueError("CHANGE_NOT_OBJECT")
        path = _canonical_path(row.get("filename"))
        if path in seen:
            raise ValueError("DUPLICATE_PATH")
        seen.add(path)
        # Only this product family's raw/data/dashboard ingress is in scope.
        if not path.startswith(ROOT):
            continue
        rel = path[len(ROOT):]
        risk = (rel.startswith(("data/", "outputs/", "dashboard/", "reference/"))
                or path.lower().endswith(RISK_EXT))
        if not risk:
            continue
        claim = claims.get(path)
        if claim is None:
            grade, reason = "HOLD", "NO_OWNER_SOURCE_CLASSIFICATION"
        elif not isinstance(claim, dict):
            raise ValueError("ATTESTATION_SHAPE_INVALID")
        elif claim.get("visibility") in ("PRIVATE", "RESTRICTED", "UNKNOWN"):
            grade, reason = "HOLD", "SOURCE_NOT_PUBLIC"
        elif claim.get("visibility") != "PUBLIC":
            grade, reason = "HOLD", "SOURCE_VISIBILITY_UNVERIFIED"
        elif not SHA.fullmatch(str(claim.get("sha256") or "")):
            grade, reason = "HOLD", "CONTENT_SHA256_ABSENT"
        elif not claim.get("owner_approval_receipt"):
            grade, reason = "HOLD", "OWNER_APPROVAL_ABSENT"
        else:
            # Even documented claims must be independently byte-verified.
            grade, reason = "REVIEW_CANDIDATE", "INDEPENDENT_BYTE_AND_OWNER_CHECK_REQUIRED"
        candidates.append({"path": path, "risk": True, "status": grade, "reason": reason})
    blocked = sum(x["status"] == "HOLD" for x in candidates)
    result = {"schema": SCHEMA, "public_repository": True,
              "changed_files_examined": len(seen), "census_assets": len(candidates),
              "assets_on_hold": blocked,
              "review_candidates_not_approved": len(candidates) - blocked,
              "items": sorted(candidates, key=lambda x: x["path"]),
              "admission": "HOLD" if candidates else "NO_CENSUS_INGRESS_OBSERVED",
              "byte_verified": False, "declassification_authorized": False,
              "merge_admission": "HOLD", "formal_credit_delta": 0}
    result["sha256"] = hashlib.sha256(json.dumps(
        {k: v for k, v in result.items() if k != "sha256"},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--changed-files", type=Path, required=True)
    p.add_argument("--attestations", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    rows = json.loads(args.changed_files.read_text(encoding="utf-8"))
    claims = json.loads(args.attestations.read_text(encoding="utf-8")) if args.attestations else None
    report = audit(rows, claims)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"INGRESS_AUDIT assets={report['census_assets']} hold={report['assets_on_hold']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
