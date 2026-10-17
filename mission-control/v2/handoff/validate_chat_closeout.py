"""Fail-closed structural validation for the additive CP.CLOSEOUT GitHub-first receipt.

No GitHub authentication, transcript extraction from ChatGPT, admission, or merge.
For an *exact* full-message count, optional --export provides the complete,
normalized input bytes; the original bytes must remain outside GitHub.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SHA1 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
STAGES = ("EVIDENCE_CAPTURED", "COMMITTED_TO_PR", "NATIVE_VERIFIED",
          "MERGED_TO_DEFAULT", "EXACT_MAIN_VERIFIED")
ROLES = ("user", "assistant", "tool_call", "tool_result", "system", "developer")
BD_STATES = ("OPEN", "BLOCKED", "IN_PROGRESS", "VERIFY_PENDING",
             "DEFER", "CLOSED_VERIFIED")
COUNT_FIELDS = ("user_prompts", "assistant_replies", "tool_calls")


def require(value, message):
    if not value:
        raise ValueError(message)


def github_url(value):
    return isinstance(value, str) and value.startswith("https://github.com/") and " " not in value


def count_normalized_export(raw: bytes):
    """Compute only clearly defined message event counts; no tokenizer guesses."""
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid normalized export") from exc
    require(isinstance(payload, dict), "export must be JSON object")
    require(payload.get("schema") == "code_purple.normalized_chat_export.v1", "export schema")
    require(payload.get("complete") is True, "export completeness not established")
    rows = payload.get("messages")
    require(isinstance(rows, list), "export messages")
    seen = set()
    tally = {"user_prompts": 0, "assistant_replies": 0, "tool_calls": 0}
    for entry in rows:
        require(isinstance(entry, dict) and entry.get("role") in ROLES, "export role")
        role = entry["role"]
        require(isinstance(entry.get("content", ""), str), "export content")
        msg_id = entry.get("id")
        if msg_id is not None:
            require(isinstance(msg_id, str) and msg_id and msg_id not in seen, "duplicate export id")
            seen.add(msg_id)
        if role == "user":
            tally["user_prompts"] += 1
        elif role == "assistant":
            tally["assistant_replies"] += 1
        elif role == "tool_call":
            tally["tool_calls"] += 1
    return tally


def validate(profile, receipt, export_bytes=None):
    """Return structural findings; this does NOT verify remote source authenticity."""
    require(profile.get("schema") == "code_purple.chat_closeout_profile.v1", "profile schema")
    require(receipt.get("schema") == "code_purple.chat_closeout_receipt.v1", "receipt schema")
    for field in profile["required_receipt_sections"]:
        require(isinstance(receipt.get(field), (dict, list)), "missing section " + field)
    s = receipt["session"]
    require(isinstance(s.get("id"), str) and 4 <= len(s["id"]) <= 120, "session id")
    require(s.get("source_scope") in profile["session_metrics"]["scope_states"], "session source scope")
    require(s.get("snapshot_atomic") is False, "snapshot must be non-atomic")
    export_hash = s.get("export_sha256")
    require(export_hash is None or (isinstance(export_hash, str)
                                     and SHA256.fullmatch(export_hash)), "export digest")
    stats = receipt["statistics"]
    full = stats.get("full_counts")
    require(isinstance(full, dict) and set(full) == set(COUNT_FIELDS), "full counts fields")
    require(all(v is None or (type(v) is int and v >= 0) for v in full.values()), "full count numeric")
    claimed_full = any(v is not None for v in full.values())
    require(not claimed_full or all(v is not None for v in full.values()), "partial full count claim")
    if claimed_full:
        require(s.get("source_scope") == "FULL_EXPORT_VERIFIED", "full counts require complete export")
        require(export_bytes is not None and export_hash is not None, "full counts require original export bytes")
        require(hashlib.sha256(export_bytes).hexdigest() == export_hash, "export bytes digest mismatch")
        require(count_normalized_export(export_bytes) == full, "export count mismatch")
    elif export_bytes is not None:
        require(export_hash is not None, "supplied export must be digest-bound")
        require(hashlib.sha256(export_bytes).hexdigest() == export_hash, "export bytes mismatch")
        count_normalized_export(export_bytes)
    require(stats.get("token_count") is None, "exact tokens require separate tokenizer audit")
    excerpt = stats.get("visible_context_counts")
    require(isinstance(excerpt, dict), "excerpt missing")
    for field in COUNT_FIELDS:
        value = excerpt.get(field)
        require(value is None or (type(value) is int and value >= 0), "invalid excerpt count")
    require(excerpt.get("basis") in ("CONTEXT_PARTIAL_NOT_FULL_SESSION", "NONE_AVAILABLE"),
            "excerpt count basis")
    if excerpt.get("basis") == "NONE_AVAILABLE":
        require(all(excerpt.get(k) is None for k in COUNT_FIELDS), "unobserved excerpt count")
    require(isinstance(stats.get("intent_topics"), list), "intent topics")
    require(all(isinstance(x, str) and x for x in stats["intent_topics"]), "intent labels")

    narrative = receipt["narrative"]
    for key in ("mission", "original_intent", "evolution", "decisions",
                "insights", "next_session_goal"):
        require(isinstance(narrative.get(key), str) and narrative[key].strip(), "narrative " + key)
    lineage = receipt["lineage"]
    require(isinstance(lineage.get("repositories"), list) and lineage["repositories"], "repositories")
    require(isinstance(lineage.get("prs"), list), "PR evidence")
    for pr in lineage["prs"]:
        require(isinstance(pr, dict) and github_url(pr.get("url")), "PR link")
        sha = pr.get("head_sha")
        require(sha is None or (isinstance(sha, str) and SHA1.fullmatch(sha)), "PR head")
    require(isinstance(lineage.get("native_runs"), list), "run evidence")
    for run in lineage["native_runs"]:
        require(github_url(run.get("url")), "run link")
        require(type(run.get("run_id")) is int and run["run_id"] > 0, "run id")
        require(run.get("head_sha") is None or SHA1.fullmatch(run["head_sha"]), "run head SHA")
        require(run.get("job_id") is None or (type(run["job_id"]) is int and run["job_id"] > 0),
                "job id")

    work = receipt["work"]
    for key in ("completed", "todo", "blocked"):
        require(isinstance(work.get(key), list), "work " + key)
    bd = receipt["bd_queue"]
    require(isinstance(bd, list), "BD queue")
    ids = set()
    for item in bd:
        require(isinstance(item, dict), "BD item")
        for k in profile["bd_item_minimum"]:
            require(isinstance(item.get(k), str) and item[k].strip(), "BD required " + k)
        require(item["id"] not in ids, "duplicate BD id")
        ids.add(item["id"])
        require(item["status"] in BD_STATES, "BD status")
        require(item["priority"] in ("P0", "P1", "P2", "P3"), "BD priority")

    custody = receipt["custody"]
    stage = custody.get("stage")
    require(stage in STAGES, "custody stage")
    require(custody.get("target") == "GOVERNED_MAIN", "custody target")
    if stage != "EVIDENCE_CAPTURED":
        require(github_url(custody.get("pr_url")), "PR-bound custody")
    if STAGES.index(stage) >= STAGES.index("NATIVE_VERIFIED"):
        require(github_url(custody.get("native_verification_url")), "native custody proof link")
        require(isinstance(custody.get("pr_head_sha"), str)
                and SHA1.fullmatch(custody["pr_head_sha"]), "exact PR source")
    if STAGES.index(stage) >= STAGES.index("MERGED_TO_DEFAULT"):
        require(github_url(custody.get("merged_pr_url")), "merge locator")
        require(isinstance(custody.get("merge_commit_sha"), str)
                and SHA1.fullmatch(custody["merge_commit_sha"]), "merge SHA")
        require(isinstance(custody.get("main_sha"), str)
                and SHA1.fullmatch(custody["main_sha"]), "main SHA")
        require(custody.get("authorized_merge_readback") is True, "actual merge readback missing")
    if stage == "EXACT_MAIN_VERIFIED":
        require(github_url(custody.get("exact_main_verification_url")), "exact-main proof locator")
        require(custody.get("exact_main_sha") == custody.get("main_sha"), "main source mismatch")
        require(custody.get("postmerge_checks_passed") is True, "main checks unverified")

    controls = receipt["controls"]
    for forbidden in ("raw_transcript_committed", "auto_merge",
                      "security_waiver", "branch_protection_relaxed",
                      "authority_transfer", "chat_deleted_by_assistant"):
        require(controls.get(forbidden) is False, "forbidden/unsupported: " + forbidden)
    require(controls.get("engineering_merge_admission") in ("HOLD", "ELIGIBLE", "UNKNOWN"),
            "engineering admission unknown/status")
    return {
        "status": "STRUCTURAL_PASS_NOT_GITHUB_AUTHENTICATION",
        "stage": stage,
        "exact_full_chat_counts_verified": bool(claimed_full),
        "full_chat_statistics_missing": not claimed_full,
        "bd_items": len(bd),
        "pr_references": len(lineage["prs"]),
        "engineering_merge_admission": controls["engineering_merge_admission"],
    }


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, default=here / "CHAT_CLOSEOUT_PROFILE_V1.json")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--export", type=Path, help="complete normalized export; keep outside GitHub")
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    export_bytes = args.export.read_bytes() if args.export else None
    print(json.dumps(validate(profile, receipt, export_bytes), sort_keys=True))


if __name__ == "__main__":
    main()
