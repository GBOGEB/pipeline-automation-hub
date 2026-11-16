# LSAF SG-01..SG-10 Reconciliation — 2026-11-13

This ledger reconciles the original Session Genome Pilot contract with current repo evidence and canonical Hub ownership. Shorthand Lane A-D labels do not replace SG-01..SG-10.

| SG | Original obligation | Current state | Evidence / gap | Next action |
|---|---|---|---|---|
| SG-01 | Define Session/Event/Fragment/Epic schemas | DONE-PILOT | explicit Session, Fragment, Event, Prediction and Epic schemas now exist | validate all fixtures against schemas; change only with migration receipt |
| SG-02 | Import existing lossless handover V1 artifacts | IMPLEMENTED-REVIEW-REPAIRED | V1 payload/hash round-trip exists and related review debt is cleared | exact-head requalification still required |
| SG-03 | Build current Session census | IMPLEMENTED-REVIEW-REPAIRED | adapter binds #1211 fields and preserves unknown timestamps as schema-valid null; #1211 remains canonical producer | exact-head requalification still required |
| SG-04 | Semantic fingerprint + recurrence | IMPLEMENTED-REVIEW-REPAIRED | deterministic fingerprint + occurrence ledger + 4 recurring-root cases remain in harness | exact-head requalification + later EVERRED cross-reference |
| SG-05 | Repo/worktree allocation | IMPLEMENTED-REVIEW-REPAIRED | repo/VSW allocation remains evidence-bound; ambiguous physical worktrees stay UNKNOWN | exact-head requalification still required |
| SG-06 | Generate dependency DAG | IMPLEMENTED-REVIEW-REPAIRED | SOURCE/DERIVED allowlist plus transitive blocker propagation and false-cycle regression added | exact-head requalification still required |
| SG-07 | Generate handover/drop-in from manifest | IMPLEMENTED-REVIEW-REPAIRED | deterministic projector/runner retained; generated prose remains DERIVED | exact-head requalification and byte-check still required |
| SG-08 | Add N->N+1 prediction receipt | IMPLEMENTED-REVIEW-REPAIRED | explicit made_at, verifiable observed outcomes, unsupported top3 removed, append-only scoring retained | exact-head requalification; then append real outcomes |
| SG-09 | Replay historical Sessions | HARNESS-IMPLEMENTED-REVIEW-REPAIRED | 48h cohort + executable 12-case 4/4/4 harness remain; review-found admission defects repaired | native exact-head 12/12 + zero false-ready still required |
| SG-10 | Cold-start test | SHADOW-HARNESS-IMPLEMENTED | repo-only reconstruction code/tests committed; self-certification explicitly forbidden | independent no-chat-context reconstruction still required after A/B/C qualification |

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

## Current external gate

The repaired head cleared all inline review threads, but Codex exact-head re-review is currently unavailable because the review quota is exhausted. FPC therefore remains a governance dependency; do not promote any SG item to DONE-PILOT solely from source repair.
