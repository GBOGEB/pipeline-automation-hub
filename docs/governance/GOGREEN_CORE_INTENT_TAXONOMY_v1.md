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

## Governed continuation monikers — addendum 17 October 2026

The source of machine vocabulary is [MC_GLOSSARY_TAXONOMY_v2.json](../../mission-control/v2/MC_GLOSSARY_TAXONOMY_v2.json), section `n3_continuation_extension`. The human aliases below are **not** historical renames of `3PR`, `3PC`, `3P3` or `W###`.

- **3P* / 3PSTAR:** three **consecutive source-bound measured pulses**, N→N+1→N+2→N+3. Every N+i has a new terminal exact-head/attempt observation, classified first-red or PASS, metric numerator and denominator, comparable-scope check and chained receipt. A terminal RED can be a measured checkpoint while preserving an explicit repair task. Three commits, PRs or green workflows are **not** sufficient.
- **3W* / 3WSTAR:** three coordinated work packages; scheduling may be serial, parallel disjoint or hybrid with a dependency barrier. A wave has a worker/PR and integration disposition; it may contain multiple pulses, and three waves do **not** imply N+3.
- **N3! / N3_CONTINUE:** a single bounded active invocation of 3PSTAR in which the executor may select routine work, retry within explicit caps, read logs, use disjoint authorized PR branches and verify evidence without recurring user queries. No background daemon or future unsupervised work is promised.
- **Checkpoint:** append-only N+i source/run/attempt/job and scoped metric receipt, with owner, timestamp, before/after comparability, identified failure or verified success and next legal action.
- **Major blocker:** P0/P1, unknown/failed required admission gate for an intended action, owner lease conflict, absent exact-head/native proof, required ruleset change, unaccepted engineering authority or irreconcilable scope. Stop affected N+ progression and return `HOLD_MAJOR` with a source-bound partial receipt; do not invent N+3.
- **N3 return:** plan vs actual, counted pulses versus native green tests, coverage/test denominators, job/root families, PR/head status, wave DAG/SIPOC, REX controls, hashes and drop-in re-entry. `N3_MEASURED_COMPLETE` never means automatic GO_MERGE.

**Runtime companion:** [GoGREEN N3 continuation README](../../mission-control/gogreen/n3_continuation/README.md) and source contract `mission-control/gogreen/n3_continuation/protocol.py`. Mainline admission remains governed by the unchanged section above.
