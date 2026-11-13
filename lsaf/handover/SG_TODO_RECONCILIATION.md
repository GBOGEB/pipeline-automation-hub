# LSAF SG-01..SG-10 Reconciliation — 2026-11-13

This ledger reconciles the original Session Genome Pilot contract with current repo evidence and canonical Hub ownership. Shorthand Lane A-D labels do not replace SG-01..SG-10.

| SG | Original obligation | Current state | Evidence / gap | Next action |
|---|---|---|---|---|
| SG-01 | Define Session/Event/Fragment/Epic schemas | DONE-PILOT | explicit Session, Fragment, Event, Prediction and Epic schemas now exist | validate all fixtures against schemas; change only with migration receipt |
| SG-02 | Import existing lossless handover V1 artifacts | OPEN | handover bundle exists, but no import/migration receipt proves semantic preservation from prior V1 forms | create V1 import fixture + zero-loss comparison receipt |
| SG-03 | Build current Session census | PARTIAL-DONE | 10-session bounded cohort exists; #1211 remains producer dependency | bind cohort ingest to #1211 output; preserve absent fields as UNKNOWN |
| SG-04 | Semantic fingerprint + recurrence | PILOT | 5 session recurrence families exist | adversarial near-duplicate/false-match cases; occurrence counters; cross-reference canonical EVERRED owner |
| SG-05 | Repo/worktree allocation | PARTIAL-DONE | repo lists and logical VSW exist; physical worktree is largely absent | normalize repo/VSW/physical-worktree allocation; UNKNOWN is valid |
| SG-06 | Generate dependency DAG | READY-ADAPTER | do not duplicate canonical Hub DAG metrics | build LSAF session-fragment adapter to canonical cicd_dag / issue-reference providers; Kahn READY/BLOCKED/CYCLE/MISSING_* remains LSAF projection |
| SG-07 | Generate handover/drop-in from manifest | OPEN | current handover/drop-in are hand-authored | implement deterministic projection and byte-stability test |
| SG-08 | Add N->N+1 prediction receipt | PILOT | 5 immutable prediction seeds committed | preserve seeds; append outcomes only; add calibration scoring |
| SG-09 | Replay historical Sessions | PILOT-SCALE-GATE | 48h cohort + governed 12-case convergence pilot contract exist | execute 4 recurring + 4 stale/admission + 4 negative-control cases |
| SG-10 | Cold-start test | BLOCKED | no independent reconstruction receipt yet | run only after SG-06/07/08 outputs exist |

## Canonical-owner assimilation rule

LSAF is an adapter/composer where Hub already has an owner.

See `lsaf/assimilation/canonical_owners.yaml`.

In particular, do not reimplement canonical DAG/SIPOC metrics, EVERRED recurrence, scale-dock metrics, issue-reference parsing, title taxonomy, or session census. Consume/cross-reference those providers and keep LSAF-specific semantics in a separate namespace.

## Cross-cutting controls

Every SG item must preserve:

- SOURCE / DERIVED / PREDICTED / UNKNOWN / SUPERSEDED evidence separation
- authority_transfer=false
- exact-head evidence binding for repo/GitHub observations
- no inferred PASS/FAIL from UNKNOWN
- deterministic, independently reproducible projections where applicable
- no production Hub assimilation in P0
- one canonical owner per metric/method

## Completion policy

No SG item is complete merely because prose exists. Completion requires a repo-native artifact plus a test/receipt or an explicit governed rationale that the obligation is satisfied by an existing reusable component.

## Scale gate

Do not expand from 48h to broad history merely to increase count. Wider history is admitted only after `LSAF-P1-12CASE-CONVERGENCE` demonstrates deterministic classifications, zero false-ready, preserved negative controls and acceptable false-match behavior.

Preferred scale order after PASS:

`48h -> recoverable PINNED set -> 7-day window -> broader history`

Increase semantic diversity before raw volume.
