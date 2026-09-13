#!/usr/bin/env python3
"""Shared runtime REX control for measured/frontier task runners.

The kernel separates three facts that were previously conflated:
- preflight evaluation before payload execution;
- observed postflight REX events;
- temporal recurrence classification from prior evidence.

It is intentionally structural. It does not invent manual evidence that the
wrapper cannot observe.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


PASS_STATES = {"PASS", "NOT_APPLICABLE"}
RECURRENCE_ORDER = ["NEW", "RECURRING", "PERSISTENT", "REGRESSION"]


def _eval(rex_id: str, passed: bool, evidence: str, *, not_applicable: bool = False) -> dict:
    return {
        "rex_id": rex_id,
        "status": "NOT_APPLICABLE" if not_applicable else ("PASS" if passed else "BLOCK"),
        "evidence": evidence,
    }


def evaluate_preflight(*, checklist_schema: str, applicable_rex_ids: list[str], facts: dict) -> dict:
    """Evaluate registered REX controls before payload execution.

    Required facts are deliberately small and observable by all current runners:
    namespace_registered, vocabulary_registered, yaml_mutation_planned,
    active_assignment_current, proof_gate_bound, execution_context_reached.
    """
    evaluations = []
    applicable = list(applicable_rex_ids)

    for rex_id in applicable:
        if rex_id == "REX-001":
            evaluations.append(_eval(rex_id, bool(facts.get("namespace_registered")), "registered mission/task/assignment/crew namespace"))
        elif rex_id == "REX-002":
            evaluations.append(_eval(rex_id, bool(facts.get("vocabulary_registered")), "registered task/competency vocabulary"))
        elif rex_id == "REX-003":
            yaml_mutation = bool(facts.get("yaml_mutation_planned"))
            if not yaml_mutation:
                evaluations.append(_eval(rex_id, True, "task does not mutate YAML", not_applicable=True))
            else:
                evaluations.append(_eval(rex_id, bool(facts.get("yaml_lint_prechecked")), "planned YAML mutation requires prechecked lint"))
        elif rex_id == "REX-004":
            evaluations.append(_eval(rex_id, bool(facts.get("active_assignment_current")), "assignment is current in predeclared manifest and crew registry"))
        elif rex_id == "REX-005":
            evaluations.append(_eval(rex_id, bool(facts.get("proof_gate_bound")), "victory/acceptance condition and exact-source proof gate are bound"))
        elif rex_id == "REX-006":
            # If this Python wrapper is executing, this job is not a zero-step
            # preexecution failure. It does not prove another repo/account is healthy.
            evaluations.append(_eval(rex_id, bool(facts.get("execution_context_reached")), "runtime wrapper reached executable context"))
        else:
            evaluations.append(_eval(rex_id, False, "no runtime evaluator registered"))

    blocking = [e["rex_id"] for e in evaluations if e["status"] not in PASS_STATES]
    triggered = list(blocking)
    return {
        "checklist_version": checklist_schema,
        "rex_ids_checked": applicable,
        "evaluations": evaluations,
        "triggered_rex_ids": triggered,
        "blocking_rex_ids": blocking,
        "preflight_complete": not blocking,
        "payload_allowed": not blocking,
    }


def _walk_rex_postflights(node, counts, preventive_controls):
    if isinstance(node, dict):
        post = node.get("rex_postflight")
        if isinstance(post, dict):
            ids = post.get("rex_ids_observed") or []
            effective = post.get("preventive_action_effective") is True
            for rex_id in ids:
                counts[rex_id] += 1
                if effective:
                    preventive_controls.add(rex_id)
        for value in node.values():
            _walk_rex_postflights(value, counts, preventive_controls)
    elif isinstance(node, list):
        for value in node:
            _walk_rex_postflights(value, counts, preventive_controls)


def collect_history(paths: list[Path]) -> dict:
    """Collect prior REX occurrences from provenance-bound JSON evidence."""
    counts = defaultdict(int)
    preventive_controls = set()
    seen_files = 0
    for root in paths:
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else sorted(root.rglob("*.json"))
        for path in candidates:
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            seen_files += 1
            _walk_rex_postflights(doc, counts, preventive_controls)
    return {
        "counts": dict(counts),
        "preventive_controls": sorted(preventive_controls),
        "evidence_files_scanned": seen_files,
    }


def classify_recurrence(rex_id: str, history: dict) -> str:
    prior = int(history.get("counts", {}).get(rex_id, 0))
    if prior <= 0:
        return "NEW"
    if rex_id in set(history.get("preventive_controls", [])):
        return "REGRESSION"
    if prior == 1:
        return "RECURRING"
    return "PERSISTENT"


def summarize_recurrence(rex_ids: list[str], history: dict) -> dict:
    classes = {rex_id: classify_recurrence(rex_id, history) for rex_id in rex_ids}
    if not classes:
        return {"by_rex_id": {}, "highest": None}
    highest = max(classes.values(), key=RECURRENCE_ORDER.index)
    return {"by_rex_id": classes, "highest": highest}
