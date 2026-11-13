# LSAF SG-01..SG-10 Reconciliation — 2026-11-13

This ledger reconciles the original Session Genome Pilot contract with current repo evidence. It is intended to prevent shorthand lane labels from hiding unfinished obligations.

| SG | Original obligation | Current state | Evidence / gap | Next action |
|---|---|---|---|---|
| SG-01 | Define Session/Event/Fragment/Epic schemas | PARTIAL-DONE | Session, Fragment, Event, Prediction schemas exist; Epic remains implicit in strings/taxonomy rather than a dedicated schema | add explicit Epic schema or document why taxonomy is sufficient |
| SG-02 | Import existing lossless handover V1 artifacts | OPEN | Handover bundle exists, but no import/migration receipt proves semantic preservation from prior V1 forms | create V1 import fixture + zero-loss comparison receipt |
| SG-03 | Build current Session census | PARTIAL-DONE | 10-session bounded cohort exists; #1211 remains producer dependency | bind cohort ingest to #1211 output contract; preserve missing fields as UNKNOWN |
| SG-04 | Semantic fingerprint + recurrence | PILOT | 5 recurrence families exist in the 48h ledger | run adversarial near-duplicate / false-match cases; record occurrence counters |
| SG-05 | Repo/worktree allocation | PARTIAL-DONE | repo lists exist per session; logical VSW concept defined; physical worktree binding is largely absent | add allocation normalization and UNKNOWN physical-worktree handling |
| SG-06 | Generate dependency DAG | READY | Lane A is READY; no executable compiler/receipt yet | implement normalization + Kahn READY/BLOCKED/CYCLE/MISSING_* |
| SG-07 | Generate handover/drop-in from manifest | OPEN | current HANDOVER/DROPIN are hand-authored continuation assets | implement deterministic projection and byte-stability test |
| SG-08 | Add N->N+1 prediction receipt | READY | prediction schema exists; no preserved pilot receipt cohort yet | seed >=5 immutable prediction receipts before outcomes |
| SG-09 | Replay historical Sessions | PILOT | one bounded 48h replay exists | execute governed 12-case convergence pilot with classification metrics |
| SG-10 | Cold-start test | BLOCKED | design exists; no independent reconstruction receipt | run after SG-06/07/08 and compare READY/blockers/next predicates |

## Cross-cutting controls

Every SG item must preserve:

- SOURCE / DERIVED / PREDICTED / UNKNOWN / SUPERSEDED evidence separation
- authority_transfer=false
- exact-head evidence binding for repo/GitHub observations
- no inferred PASS/FAIL from UNKNOWN
- deterministic, independently reproducible projections where applicable
- no production Hub assimilation in P0

## Completion policy

No SG item is considered complete merely because prose exists. Completion requires a repo-native artifact plus a test/receipt or an explicit governed rationale that the obligation is satisfied by an existing reusable component.

## Scale gate

Do not expand from 48h to broad history merely to increase count. Wider history is admitted only after the 12-case convergence pilot demonstrates deterministic classifications, acceptable false-match behavior, and preserved negative controls.
