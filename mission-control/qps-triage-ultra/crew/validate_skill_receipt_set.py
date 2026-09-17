#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from pathlib import Path

ALLOWED_SKILLS = {"math", "plots", "math-plots"}
SCHEMA = "missioncontrol.crew.skill_resolution_receipt.v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def fail(message: str) -> None:
    raise SystemExit(message)


def canonical_semantic_receipt(receipt: dict) -> dict:
    keys = [
        "schema",
        "skill",
        "source_repo",
        "source_ref",
        "skills_repo",
        "skills_ref",
        "resolution_mode",
        "resolved_skill_path",
        "entrypoint_sha256",
        "authority_transfer",
        "status",
    ]
    return {key: receipt.get(key) for key in keys}


def validate_receipt(receipt: dict, expected_repo: str, expected_ref: str, skills_ref: str) -> None:
    if receipt.get("schema") != SCHEMA:
        fail("receipt schema mismatch")
    skill = receipt.get("skill")
    if skill not in ALLOWED_SKILLS:
        fail(f"unexpected skill: {skill}")
    if receipt.get("status") != "PASS_SKILL_BUNDLE_RESOLUTION":
        fail(f"non-pass skill receipt: {skill}")
    if receipt.get("source_repo") != expected_repo:
        fail(f"source repo mismatch: {skill}")
    if receipt.get("source_ref") != expected_ref or not HEX40.fullmatch(expected_ref):
        fail(f"source ref mismatch or non-SHA: {skill}")
    if receipt.get("skills_repo") != "GBOGEB/skills":
        fail(f"skills repo mismatch: {skill}")
    if receipt.get("skills_ref") != skills_ref or not HEX40.fullmatch(skills_ref):
        fail(f"skills ref mismatch or non-SHA: {skill}")
    digest = receipt.get("entrypoint_sha256")
    if not isinstance(digest, str) or not HEX64.fullmatch(digest):
        fail(f"missing or invalid entrypoint digest: {skill}")
    if receipt.get("authority_transfer") is not False:
        fail(f"authority inversion detected: {skill}")
    expected_path = f"skills/{skill}/SKILL.md"
    if receipt.get("resolved_skill_path") != expected_path:
        fail(f"resolved path mismatch: {skill}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipts-dir", type=Path, required=True)
    parser.add_argument("--expected-source-repo", required=True)
    parser.add_argument("--expected-source-ref", required=True)
    parser.add_argument("--skills-ref", required=True)
    parser.add_argument("--expected-count", type=int, default=3)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    files = sorted(args.receipts_dir.glob("*.json"))
    if len(files) != args.expected_count:
        fail(f"expected {args.expected_count} receipt files, found {len(files)}")

    receipts = []
    seen_skills = set()
    semantic_payloads = set()
    for path in files:
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"invalid JSON in {path}: {exc}")
        validate_receipt(
            receipt,
            expected_repo=args.expected_source_repo,
            expected_ref=args.expected_source_ref,
            skills_ref=args.skills_ref,
        )
        skill = receipt["skill"]
        if skill in seen_skills:
            fail(f"duplicate skill receipt: {skill}")
        seen_skills.add(skill)
        semantic = canonical_semantic_receipt(receipt)
        semantic_json = json.dumps(semantic, sort_keys=True, separators=(",", ":"))
        semantic_sha = hashlib.sha256(semantic_json.encode("utf-8")).hexdigest()
        if semantic_sha in semantic_payloads:
            fail("duplicate semantic receipt payload")
        semantic_payloads.add(semantic_sha)
        receipts.append(semantic)

    if seen_skills != ALLOWED_SKILLS:
        fail(f"skill set mismatch: {sorted(seen_skills)}")

    receipts.sort(key=lambda item: item["skill"])
    canonical = json.dumps(receipts, sort_keys=True, separators=(",", ":"))
    set_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    result = {
        "schema": "missioncontrol.crew.mip_hardened_skill_receipt_set.v1",
        "source_repo": args.expected_source_repo,
        "source_ref": args.expected_source_ref,
        "skills_repo": "GBOGEB/skills",
        "skills_ref": args.skills_ref,
        "skills": sorted(seen_skills),
        "receipt_count": len(receipts),
        "receipt_set_sha256": set_digest,
        "authority_transfer": False,
        "status": "PASS_MIP_HARDENED_SKILL_RECEIPT_SET",
    }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
