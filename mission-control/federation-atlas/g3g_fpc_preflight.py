"""Read-only FPC first-red preflight; the trusted base controller is authoritative.

Never turn this diagnostic into a merge gate, artifact attestation, authorization
decision or a way to manufacture required proof. See MC issue #304.
"""
from __future__ import annotations

import json
import re
from typing import Any

RECEIPT = re.compile(r"<!--\s*FPC_RECEIPT_V1\s*(\{.*?\})\s*-->", re.S)
SHA = re.compile(r"^[0-9a-f]{40}$")
REQUIRED = frozenset(("canonical_self_test", "mutation_test", "exact_head_ci"))
SCHEMA = "missioncontrol.g3g_fpc_diagnostic.v1"


def _blocked(fingerprint: str, *, detail: str = "", run_count: int = 0) -> dict:
    return {
        "schema": SCHEMA, "first_red_fingerprint": fingerprint,
        "detail": detail, "receipt_run_count": run_count,
        "trusted_controller_verdict": None, "effective_required_status": None,
        "independent_human_approval": None, "accepted_causal_root_id": None,
        "merge_admission": "HOLD", "engineering_acceptance": "WITHHELD",
        "authority_transfer": False, "formal_credit_delta": 0,
        "evidence_class": "READ_ONLY_NON_AUTHORITATIVE_PREFLIGHT",
    }


def diagnose(pr: dict[str, Any], runs: list[dict[str, Any]]) -> dict:
    """Identify only the *first* attributable FPC preflight blocker.

    Run metadata is ordinary caller-supplied input, not a trusted GitHub
    authentication. Even when everything is observed GREEN, the trusted
    controller, eligible independent reviewer and required checks remain
    UNVERIFIED. We do not guess from a successful workflow summary.
    """
    if not isinstance(pr, dict) or not isinstance(runs, list):
        raise ValueError("FPC_INPUT_TYPE_INVALID")
    number, head, base = pr.get("number"), pr.get("head_sha"), pr.get("base_sha")
    if type(number) is not int or number < 1:
        raise ValueError("FPC_PR_NUMBER_INVALID")
    if not isinstance(head, str) or not SHA.fullmatch(head):
        raise ValueError("FPC_EXACT_HEAD_INVALID")
    if not isinstance(base, str) or not SHA.fullmatch(base):
        raise ValueError("FPC_EXACT_BASE_INVALID")
    body = pr.get("body")
    if body is not None and not isinstance(body, str):
        raise ValueError("FPC_BODY_INVALID")
    found = RECEIPT.search(body or "")
    if found is None:
        return _blocked("FPC_MISSING_RECEIPT",
                        detail="Exact-head FPC_RECEIPT_V1 PR-body marker absent")
    try:
        manifest = json.loads(found.group(1))
    except json.JSONDecodeError:
        return _blocked("FPC_INVALID_RECEIPT_JSON")
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema", "head_sha", "required_runs"
    } or manifest.get("schema") != "first_pass_closure/v1":
        return _blocked("FPC_RECEIPT_SCHEMA_OR_FIELDS")
    if manifest["head_sha"] != head:
        return _blocked("FPC_STALE_RECEIPT_HEAD")
    entries = manifest["required_runs"]
    if not isinstance(entries, list) or not entries:
        return _blocked("FPC_REQUIRED_RUNS_MISSING")
    identities = set()
    for spec in entries:
        if not isinstance(spec, dict) or set(spec) != {"repo", "run_id"}:
            return _blocked("FPC_INVALID_PROOF_ROW")
        repository, run_id = spec["repo"], spec["run_id"]
        if not isinstance(repository, str) or repository.count("/") != 1 or (
            type(run_id) is not int or run_id < 1
        ):
            return _blocked("FPC_INVALID_PROOF_IDENTITY")
        if (repository, run_id) in identities:
            return _blocked("FPC_DUPLICATE_RUN_ID")
        identities.add((repository, run_id))
    native = {(r.get("repo"), r.get("run_id")): r for r in runs
              if isinstance(r, dict)}
    for repository, run_id in sorted(identities):
        r = native.get((repository, run_id))
        if r is None:
            return _blocked("FPC_NATIVE_RUN_NOT_FETCHED", run_count=len(entries))
        if r.get("head_sha") != head:
            return _blocked("FPC_NATIVE_RUN_HEAD_MISMATCH", run_count=len(entries))
        if r.get("status") != "completed" or r.get("conclusion") != "success":
            return _blocked("FPC_NATIVE_RUN_NOT_SUCCESS", run_count=len(entries))
    # Purposes require trusted workflow identity AND candidate/base content hash
    # equivalence, not merely a run name or PR-body assertion.
    return _blocked("FPC_TRUSTED_PROOF_AND_REVIEW_UNVERIFIED",
                    detail="No candidate-controlled proof can certify required "
                           "three purposes, protected paths, Codex review, or "
                           "effective required-status rule",
                    run_count=len(entries))
