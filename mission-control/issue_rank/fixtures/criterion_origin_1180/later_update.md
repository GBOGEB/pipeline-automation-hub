<!-- CL_REVIEW_CAPACITY_20261110 -->
## Continuation: exact-head review attempted — 10 November 2026

Head remains `dae9c7fa814e93e29a0a12aed799ed7afb6ba64e`; its completed native proof is retained. A [genuine manual Codex review request](https://github.com/GBOGEB/pipeline-automation-hub/pull/1181#issuecomment-6779867786) returned an [exact-head failed review summary](https://github.com/GBOGEB/pipeline-automation-hub/pull/1181#issuecomment-6779871524) and the provider's [code-review usage-limit reply](https://github.com/GBOGEB/pipeline-automation-hub/pull/1181#issuecomment-6779872193). No source finding was established by this failed attempt. Do not repeatedly retry until capacity changes.

**CL01–CL07 remain complete; CL08/CL09 remain open.** Remaining active work: one exact-head review/admission wave, then one merged-source replay/closure wave (potentially combined if no source finding); the external review-capacity wait has no honest fixed pulse count. Current source checks remain successful; draft skipped FPC checks do not override the trusted failure.

The separately requested origin/supersession increment is #1182, stacked on this candidate. It does not change this issue's original nine closure predicates or justify delaying CL09 after this repair is admitted.

---

<!-- CRITERION_LINEAGE_CURRENT_V1 -->
## Latest execution — 10 November 2026

**Candidate:** [draft PR #1181](https://github.com/GBOGEB/pipeline-automation-hub/pull/1181), exact head `dae9c7fa814e93e29a0a12aed799ed7afb6ba64e`. **CL01–CL07 complete; CL08–CL09 open (7/9 scoped items).**

Existing native [issue-ranking](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/42903237506) and [triway](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/42903237825) QA PASS on Python 3.11 and 3.12. The ranking job executes 197 tests per interpreter and achieves 93% owner coverage; triway's separate 38-test job achieves 86%. Same-file #1171 compatibility is verified separately with 13 thread-tool and 38 triway tests.

The final source review has no unresolved finding, but it is advisory and does not substitute for an eligible independent GitHub review or trusted FPC. The [trusted controller](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/42903278604) is RED with `CODEX_REVIEW_NOT_COMPLETED_ON_EXACT_HEAD`; successful source checks and skipped draft gates do not compensate. The next finite boundary is CL08 admission, followed by CL09 merged-source replay. No issue closure credit is claimed.

The original nine IDs and scope follow; their wording is retained and checked state is updated only for the supplied evidence.

---

## Purpose and original scope — 10 November 2026

Parent: #308 (Issue Expedition). Consumers: #324 (measured W3) and #358 (repository burndown view). This is one finite defect in the existing checklist owner, not a new ranking engine or standing census.

At `master@401c57316197c81e910f0b3da7ea7322e1f109fc`, `issue_rank.diff()` compares checklist movement only by checked/total counts. Replacing an unfinished original obligation A with unrelated obligation B at the same counts returns `checklist_moves=[]`, `tasks_ticked_net=0`, `scope_added_net=0`. The original obligation disappears from the pulse history. The canonical parser truncates display text at 300 characters and its ranking adapter at 200, so identities must be derived before either display limit.

## Original DoD

- [x] CL01 — Reproduce the equal-count replacement defect against the recorded master source and locate the canonical owners.
- [x] CL02 — Canonical `triway_burndown.checklist()` emits content identities from the complete criterion, independent of tick state and ordering; duplicate occurrences remain countable.
- [x] CL03 — Existing `issue_rank.diff()` reports added/removed/reopened/ticked/withdrawn criteria and preserves section information without converting withdrawal to completion.
- [x] CL04 — Legacy snapshots without full criterion identities are explicitly incomparable; first-observed evidence is not presented as issue-creation history.
- [x] CL05 — Existing aggregate semantics and private/public redaction remain intact; self-reported ticks confer no verified closure credit.

## Original DoV and finite closure

- [x] CL06 — Adversarial owner tests cover equal-count replacement, edits beyond display limits, duplicate text, reorder, withdrawal/reopen, legacy inputs and private projection; existing coverage floor passes.
- [x] CL07 — Verify compatibility with disjoint PR #1171 parked-intent changes and obtain existing Python 3.11/3.12 native owner checks on the final candidate SHA.
- [ ] CL08 — Independent exact-head review, trusted FPC and all required checks pass; owner admits the change under the existing policy.
- [ ] CL09 — After accepted integration, replay the original reproducer on the actual merged source and attach the result, SHA and native run receipts; then close this defect issue.

No indefinite observation period is required by this issue. Any new defect discovered by CL06–CL09 gets its own linked obligation and explicit dependency; it does not silently replace CL01–CL09. Parent #308/#324/#358 remain governed by their original broader predicates.

## Lane and overlap

Implementation branch: `feat/issue-criterion-lineage-20261110`, based on current master above. Paths: existing `mission-control/qps-triage-ultra/issue-expedition/triway_burndown.py`, `mission-control/issue_rank/issue_rank.py`, their wired owner tests and method documentation.

Open-PR inventory: 22 open Hub PRs inspected. PR #1171 at `2009096823fd1ae6f6fe17180aa8b56458a19702` touches the same parser file only in `parked_intent()/parked_intent_meta()`; the checklist hunks are disjoint. Its branch remains separately owned. Existing issue-rank and issue-expedition native workflows provide the test path.

## Closure semantics

An edited checkbox is source text, not independent DoV. Removed, withdrawn, transferred and superseded obligations remain distinct from completed obligations. No issue closure, default-branch push, merge waiver, scheduler activation or authority transfer follows from this implementation alone.

`SOURCE_AND_NATIVE_QA_PASS / MERGE_ADMISSION_HOLD / FORMAL_CREDIT_DELTA=0 / AUTHORITY_TRANSFER=false`
