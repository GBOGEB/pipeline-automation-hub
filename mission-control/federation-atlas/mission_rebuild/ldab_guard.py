"""Bounded, fail-closed LDAB readback for native GitHub job metadata.

A completed workflow with no jobs, no executed steps, or a queued job is not
native proof. Step-level manifestations never become causal root closures.
No runner dispatch, source mutations, or actual LLDB debugger claims.
"""
from __future__ import annotations

import hashlib
import json

VALID_STATES = frozenset({"queued", "waiting", "pending", "in_progress", "completed"})
TERMINAL = frozenset({"success", "failure", "cancelled", "skipped", "timed_out", "neutral", "action_required"})


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("LDAB_FAIL_CLOSED:" + message)


def assess_jobs(payload: dict, name: str, expected_run_id: int | None = None) -> dict:
    """Summarize exact API population; terminal job proof requires actual steps.

    `complete` means complete API pagination only, not a passing job or test.
    `terminal_success_with_steps` means successful GitHub job steps, NOT tests.
    """
    require(isinstance(payload, dict), name + " payload")
    total = payload.get("total_count")
    rows = payload.get("jobs")
    require(type(total) is int and total >= 0, name + " census count")
    require(isinstance(rows, list) and len(rows) <= total, name + " census rows")
    require(expected_run_id is None or (type(expected_run_id) is int and expected_run_id > 0),
            name + " run identity")
    ids = set()
    manifestations = []
    for job in rows:
        require(isinstance(job, dict) and type(job.get("id")) is int and job["id"] > 0,
                name + " job identifier")
        ident = job["id"]
        require(ident not in ids, name + " duplicate job")
        ids.add(ident)
        require(job.get("status") in VALID_STATES, name + " job status")
        conclusion = job.get("conclusion")
        require(conclusion is None or conclusion in TERMINAL, name + " conclusion")
        require(job["status"] == "completed" or conclusion is None,
                name + " nonterminal job conclusion")
        steps = job.get("steps")
        require(steps is None or isinstance(steps, list), name + " steps type")
        if steps is not None:
            seen_numbers = set()
            for step in steps:
                require(isinstance(step, dict) and isinstance(step.get("name"), str)
                        and bool(step["name"].strip()), name + " named step")
                number = step.get("number")
                require(type(number) is int and number > 0 and number not in seen_numbers,
                        name + " step ordinal")
                seen_numbers.add(number)
                require(step.get("status") in VALID_STATES, name + " step state")
                require(step.get("conclusion") is None or step["conclusion"] in TERMINAL,
                        name + " step conclusion")
            failed = sorted((s for s in steps if s.get("conclusion") == "failure"),
                            key=lambda s: s["number"])
            if failed:
                step = failed[0]
                canonical = json.dumps({"job_id": ident, "step": step["name"],
                                        "number": step["number"]}, sort_keys=True,
                                       separators=(",", ":"))
                manifestations.append({"job_id": ident, "first_failed_step": step["name"],
                                       "step_number": step["number"],
                                       "manifestation_fingerprint_sha256": hashlib.sha256(
                                           canonical.encode("utf-8")).hexdigest(),
                                       "root_id": None,
                                       "logs_authenticated": False,
                                       "causal_root_accepted": False})
    complete = len(rows) == total
    nonempty = total > 0
    terminal = complete and nonempty and all(j["status"] == "completed" for j in rows)
    all_success = terminal and all(j.get("conclusion") == "success" for j in rows)
    # At least one terminal completed step per successful job; this does NOT
    # assert that a test ran or that an artifact was uploaded.
    step_proof = all_success and all(
        isinstance(j.get("steps"), list) and any(
            s.get("status") == "completed" and s.get("conclusion") == "success"
            for s in j["steps"])
        for j in rows)
    bound = (None if expected_run_id is None else
             complete and nonempty and all(j.get("run_id") == expected_run_id for j in rows))
    evidence_ok = bool(step_proof and bound is True)
    return {"total": total, "observed": len(rows), "complete": complete,
            "nonempty": nonempty, "all_terminal": bool(terminal),
            "all_success": bool(all_success),
            "executed_step_receipts": bool(step_proof),
            "run_id_bound": bound,
            "terminal_success_with_steps": evidence_ok,
            "passing": sum(j.get("conclusion") == "success" for j in rows) if complete else None,
            "failing": sum(j.get("conclusion") == "failure" for j in rows) if complete else None,
            "queued": sum(j.get("status") == "queued" for j in rows) if complete else None,
            "job_ids": [j["id"] for j in rows],
            "ldab_step_manifestations": manifestations,
            "distinct_causal_roots": None,
            "lldb_native_debug_session": None,
            "actual_worker_hours": None,
            "native_tests_executed": None,
            "native_artifact_bytes_verified": False,
            "evidence_class": "GITHUB_JOB_METADATA_NOT_LOG_ROOT_PROOF"}
