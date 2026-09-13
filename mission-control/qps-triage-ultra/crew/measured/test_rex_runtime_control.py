#!/usr/bin/env python3
from rex_runtime_control import classify_recurrence, evaluate_preflight, summarize_recurrence

SCHEMA = "missioncontrol.rex.reuse_checklist.v1"

blocked = evaluate_preflight(
    checklist_schema=SCHEMA,
    applicable_rex_ids=["REX-005", "REX-006"],
    facts={
        "namespace_registered": True,
        "vocabulary_registered": True,
        "yaml_mutation_planned": False,
        "active_assignment_current": True,
        "proof_gate_bound": False,
        "execution_context_reached": True,
    },
)
assert blocked["payload_allowed"] is False
assert blocked["preflight_complete"] is False
assert blocked["blocking_rex_ids"] == ["REX-005"]
assert blocked["triggered_rex_ids"] == ["REX-005"]

admitted = evaluate_preflight(
    checklist_schema=SCHEMA,
    applicable_rex_ids=["REX-001", "REX-002", "REX-003", "REX-004", "REX-005", "REX-006"],
    facts={
        "namespace_registered": True,
        "vocabulary_registered": True,
        "yaml_mutation_planned": False,
        "yaml_lint_prechecked": False,
        "active_assignment_current": True,
        "proof_gate_bound": True,
        "execution_context_reached": True,
    },
)
assert admitted["payload_allowed"] is True
assert admitted["preflight_complete"] is True
assert admitted["blocking_rex_ids"] == []
assert admitted["triggered_rex_ids"] == []

assert classify_recurrence("REX-005", {"counts": {}, "preventive_controls": []}) == "NEW"
assert classify_recurrence("REX-005", {"counts": {"REX-005": 1}, "preventive_controls": []}) == "RECURRING"
assert classify_recurrence("REX-005", {"counts": {"REX-005": 2}, "preventive_controls": []}) == "PERSISTENT"
assert classify_recurrence("REX-005", {"counts": {"REX-005": 1}, "preventive_controls": ["REX-005"]}) == "REGRESSION"
summary = summarize_recurrence(
    ["REX-001", "REX-005"],
    {"counts": {"REX-001": 0, "REX-005": 2}, "preventive_controls": []},
)
assert summary["by_rex_id"] == {"REX-001": "NEW", "REX-005": "PERSISTENT"}
assert summary["highest"] == "PERSISTENT"

print("PASS_REX_RUNTIME_CONTROL_BLOCKED_AND_ADMITTED")
