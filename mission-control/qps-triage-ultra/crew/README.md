# MissionControl Crew Capability System v1

Status: `CANDIDATE_CANONICAL`

Baseline source head: `55ce66b04ef6dee9630c1976efa8051fd21d451b`

This layer closes the gap between having named crews and knowing, quantitatively and evidentially, what those crews can do.

## Canonical artifacts

- `CREW_REGISTRY_v1.json` — crew seats, specialist archetypes and conceptual roles.
- `COMPETENCY_MATRIX_v1.json` — level definitions, competency dimensions and evidence rules.
- `REX_LEARNING_LEDGER_v1.json` — lessons routed back into crew behavior, validators and role development.
- `ROLE_DEVELOPMENT_POLICY_v1.json` — mission-feedback-driven role proposal, trial, promotion, merge and retirement lifecycle.
- `validate_crew_system.py` — dependency-free structural and governance validator.

## Evidence classes

`OBSERVED` means the role is explicitly present in repository mission/control material.

`PARTIAL` means the role is observed but its competency vector is not yet supported by enough measured mission receipts to call it proven.

`CONCEPTUAL` means MissionControl intends to test the role, but the role must not be treated as operationally proven or authoritative.

No conceptual role may receive promotion or CONTROL authority. No competency score is considered measured unless linked to accepted mission receipts.

## Existing observed foundation

The permanent HOME seats U01-U08 come from `architecture.yaml` and `README.md`. Specialist roles and activation/return behavior are evidenced by `HANDOVER_SESSION_2026-09-12_RUNNER_CREW.yaml`, M09 control material and the expedition fleet ledger. The Ambassador is retained as an explicit specialist role because it is already observed in live mission-control history.

## Operating loop

```text
mission feedback
  -> first red / repeated REX / capacity pressure / semantic gap
  -> role need hypothesis
  -> CONCEPTUAL role card
  -> bounded trial mission
  -> accepted/rejected receipts
  -> competency evidence update
  -> PARTIAL or OBSERVED promotion
  -> repeated independent evidence
  -> CONTROL eligibility
  -> REX feedback / merge / prune / return
```

## Quantitative rule

A competency level is not a title. It is an evidence-backed state. Seeded values are planning priors only and must be replaced by measured receipt-derived values as missions execute.

## Authority boundary

This layer may describe, recommend, allocate and learn. It does not transfer engineering, compliance, KEB, DOW or child-system authority. `authority_transfer=false` remains mandatory.
