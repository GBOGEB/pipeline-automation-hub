# GoGREEN core-intent integration and deferred-review taxonomy (v1)

Status: PROPOSED; no rule relaxation or authority transfer. Owner: repository maintainers. Scope: federation policy vocabulary and read-only fan-out contract.

## Objective
Integrate independently proven functional PR intent into the repository's protected default branch promptly, while recording optional review and hardening work as explicit post-merge CONTROL debt. No failing required check, security blocker, unresolved required approval, or engineering acceptance is deferred.

## Decision taxonomy
- GO_EXECUTE: bounded implementation/scout may proceed in an isolated branch.
- GO_PROVE: execute source-bound tests and generate evidence; not merge admission.
- GO_MERGE: exact-head candidate meets all effective required GitHub checks, reviews, thread rules, security and owner-domain acceptance; recheck immediately before merge.
- DEFER_NONCRITICAL: optional review finding has owner, issue link, expiry/re-entry trigger and nonblocking justification; not a bypass.
- SPLIT_CORE: extract independently passing core functionality into a smaller PR; re-test on new exact head.
- HOLD_REQUIRED: required gate, critical finding, mergeability or source evidence absent or failed.
- RETURN_OWNER: configuration, approval or domain acceptance belongs to an external authorized owner.
- CONTROL_POSTMERGE: merged core with tracked noncritical follow-up; never equivalent to completed formal assurance.
- UNKNOWN: unavailable evidence, never interpreted as success.

## Fan-out lanes
- Mission Control / pipeline-automation-hub: orchestrates read-only census, dependency DAG, work leases, evidence joins and federation status; never becomes domain SSOT.
- ABACUS: CI, first-red, CBD roots, regression tests, coverage and admission evidence.
- CODEX: implementation, parser and code-contract verification.
- cryoplant-project (QPS): engineering acceptance and controlled source statements.
- gg_MATH: comparable-cohort analysis, uncertainty and readiness qualification.
- Other GBOGEB repositories: discover through paginated repository inventory; classify owner, default branch, applicability, existing controls and adoption readiness before any mutation.

## Merge admission (fail closed)
1. Fetch fresh PR metadata and effective protection/rulesets from an authorized source.
2. Bind tests, coverage and review evidence to exact head SHA and workflow attempts.
3. Require all effective required checks green, relevant security dispositions, approvals and enforced thread resolution.
4. Require domain-owner acceptance when relevant; check mergeability and base drift.
5. Re-read head, merge with expected_head_sha; treat GitHub rejection as HOLD.
6. Verify default-branch merge SHA and post-merge checks; publish provenance.
7. Transfer only explicitly noncritical deferred findings into tracked CONTROL issues.

## Glossary
- Core intent: minimum functional behavior that justifies the PR.
- GoGREEN: positive, reproducible evidence that core functionality works.
- EVERRED: first-red/root recovery lane; failed-job associations are not causal roots.
- CODE PURPLE: assurance and merge-admission governance; not a global green prerequisite for independent PRs.
- Exact head: immutable candidate commit SHA used for all admission evidence.
- First-red: earliest attributable failing step in a defined execution, not automatically a causal root.
- Manifestation: observed failed job/test/step; multiple manifestations may share a root.
- Root: deduplicated cause backed by source evidence and owner disposition.
- Fan-out: independent repo-local work dispatched from a federation plan without transferring authority.
- Intervening window: time-boxed integration opportunity, not a bypass.
- Deferred review: noncritical tracked post-merge work allowed by existing rules, never missing required approval.
- CONTROL: proven ongoing monitoring/recurrence prevention, not merely a merged PR.
- Cohort: a scope-matched population with declared denominator and comparable source/configuration.
- M1/M2/M3: progressive statistical readiness; no PCA/Bradley-Terry ranking without qualified data.
- GO / NO-GO: per-PR admission outcome, distinct from federation-wide health.

## Adoption and validation
Publish this contract centrally first. Fan out read-only inventory to core repositories, then use repo-local PRs for adoption after each repository's owner confirms applicability. Negative tests shall prove that stale SHA, required red, missing approval, critical security finding, absent QPS acceptance, or unknown rulesets all return HOLD. Track core-intent lead time, merged functional slices, deferred issue age, first-red/root burndown, scope-matched coverage, and post-merge regression recurrence.
