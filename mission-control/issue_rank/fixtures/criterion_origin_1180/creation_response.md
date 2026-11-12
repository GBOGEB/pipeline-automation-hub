## Purpose and original scope — 10 November 2026

Parent: #308 (Issue Expedition). Consumers: #324 (measured W3) and #358 (repository burndown view). This is one finite defect in the existing checklist owner, not a new ranking engine or standing census.

At `master@401c57316197c81e910f0b3da7ea7322e1f109fc`, `issue_rank.diff()` compares checklist movement only by checked/total counts. Replacing an unfinished original obligation A with unrelated obligation B at the same counts returns `checklist_moves=[]`, `tasks_ticked_net=0`, `scope_added_net=0`. The original obligation disappears from the pulse history. The canonical parser truncates display text at 300 characters and its ranking adapter at 200, so identities must be derived before either display limit.

## Original DoD

- [x] CL01 — Reproduce the equal-count replacement defect against the recorded master source and locate the canonical owners.
- [ ] CL02 — Canonical `triway_burndown.checklist()` emits content identities from the complete criterion, independent of tick state and ordering; duplicate occurrences remain countable.
- [ ] CL03 — Existing `issue_rank.diff()` reports added/removed/reopened/ticked/withdrawn criteria and preserves section information without converting withdrawal to completion.
- [ ] CL04 — Legacy snapshots without full criterion identities are explicitly incomparable; first-observed evidence is not presented as issue-creation history.
- [ ] CL05 — Existing aggregate semantics and private/public redaction remain intact; self-reported ticks confer no verified closure credit.

## Original DoV and finite closure

- [ ] CL06 — Adversarial owner tests cover equal-count replacement, edits beyond display limits, duplicate text, reorder, withdrawal/reopen, legacy inputs and private projection; existing coverage floor passes.
- [ ] CL07 — Verify compatibility with disjoint PR #1171 parked-intent changes and obtain existing Python 3.11/3.12 native owner checks on the final candidate SHA.
- [ ] CL08 — Independent exact-head review, trusted FPC and all required checks pass; owner admits the change under the existing policy.
- [ ] CL09 — After accepted integration, replay the original reproducer on the actual merged source and attach the result, SHA and native run receipts; then close this defect issue.

No indefinite observation period is required by this issue. Any new defect discovered by CL06–CL09 gets its own linked obligation and explicit dependency; it does not silently replace CL01–CL09. Parent #308/#324/#358 remain governed by their original broader predicates.

## Lane and overlap

Implementation branch: `feat/issue-criterion-lineage-20261110`, based on current master above. Paths: existing `mission-control/qps-triage-ultra/issue-expedition/triway_burndown.py`, `mission-control/issue_rank/issue_rank.py`, their wired owner tests and method documentation.

Open-PR inventory: 22 open Hub PRs inspected. PR #1171 at `2009096823fd1ae6f6fe17180aa8b56458a19702` touches the same parser file only in `parked_intent()/parked_intent_meta()`; the checklist hunks are disjoint. Its branch remains separately owned. Existing issue-rank and issue-expedition native workflows provide the test path.

## Closure semantics

An edited checkbox is source text, not independent DoV. Removed, withdrawn, transferred and superseded obligations remain distinct from completed obligations. No issue closure, default-branch push, merge waiver, scheduler activation or authority transfer follows from this implementation alone.

`IMPLEMENTATION_IN_PROGRESS / MERGE_ADMISSION_HOLD / FORMAL_CREDIT_DELTA=0 / AUTHORITY_TRANSFER=false`
