# FPC owner rule-suite replay: bounded evidence join (12 Nov 2026)

**Status:** read-only candidate on a draft PR. This is not a new merge gate,
historical governance verdict, self-authorizing waiver, or second BD authority.

Canonical admission classifier: taxonomy_admission_audit.py in this directory.
Canonical owner: [Hub #336](https://github.com/GBOGEB/pipeline-automation-hub/issues/336),
with #304, #372, and #85 kept distinct. Source evidence:
[27-merge exact-head audit](https://github.com/GBOGEB/pipeline-automation-hub/issues/336#issuecomment-6821575411).

## Why this thin join exists

The 11 Nov cohort has **27 merged heads**, of which 26 had a trusted FPC
FAILURE commit-status before merge and one had no FPC status. Two later
merged heads had FPC SUCCESS. This proves an **admission discrepancy requiring
reconciliation**, not who was authorized to bypass which rule.

Current repository rules are split: P-BASIC #25789280 does not require FPC;
P-SOFT #26995106 requires it and permits repository-role pull-request bypass.
Historical rule-suite audits need repository Administration **read**
permission, which this integration lacks: native GET returned HTTP 403.
The observed failure is preserved in
[evidence/OWNER_RULE_SUITES_403_20261112.json](evidence/OWNER_RULE_SUITES_403_20261112.json).

GitHub documents after_sha, ref, pushed_at, result, actor, rule evaluations,
and the Administration read requirement:
https://docs.github.com/en/rest/repos/rule-suites

## Local offline replay (does not contact GitHub)

From repository root:

~~~bash
python mission-control/issue_rank/fpc_rule_suite_join.py \
  --events mission-control/issue_rank/evidence/FPC_MERGE_COHORT_29_20261112.json \
  --source mission-control/issue_rank/evidence/OWNER_RULE_SUITES_403_20261112.json \
  --out output/fpc-owner/REPLAY.json
cd mission-control/issue_rank
python -m unittest -v test_taxonomy_admission_audit
~~~

Expected: 29 observed, 27 historical, two positive controls,
26 FAILURE / one ABSENT / two SUCCESS, 29 ADMIN_READ_403_UNRESOLVED,
zero authorized bypasses, zero formal root closures. The SHA256 digest
checks deterministic inputs; it is not a source signature.
The public Hub PR and commit-status readback is a bounded historical snapshot.

## Owner-only source evidence (not performed by this PR)

An owner with an authenticated GitHub CLI session and separate repository
Administration **read** permission can collect the narrowly scoped rule suites.
**Never paste a token into a command, PR, or artifact. No ruleset changes.**

1. Confirm read-only scope using gh auth status on the owner's workstation.
   List GitHub REST GET /repos/GBOGEB/pipeline-automation-hub/rulesets/rule-suites,
   filtering ref=refs/heads/master, time_period=week, rule_suite_result=all
   and per_page=100. Fetch **all pages**.
2. Fetch each relevant GET .../rule-suites/{id}?include_metadata=true.
   The list alone cannot identify which rule was bypassed. GitHub caps certain
   metadata to 50 entries; report possible truncation.
3. Build a fpc.rule-suite-export.v1 JSON containing the actual list and
   detailed rule_evaluations. State COMPLETE only if pagination, details,
   and the full event time window are *independently verified*; otherwise
   INCOMPLETE. Keep IDs, result, actor, after_sha, ref, pushed_at, and
   detailed rule evaluations. Never synthesize source data.
4. Replay against the same immutable event fixture. A candidate suite joins
   on exact merge_commit_sha + ref + 15-minute time tolerance. A specific
   FPC bypass additionally requires active P-SOFT and a failing
   required_status_checks evaluation explicitly identifying FPC.
5. Even an observed bypass is **not authorized** until a separate owner
   disposition records rationale, policy exception and independent review.
   Preserve merge_admission=HOLD, authority_transfer=false, and zero credit.
   Empty results are not proof of no bypass when coverage is incomplete.

### Synthetic source manifest shape, NOT real owner evidence

~~~json
{
  "schema": "fpc.rule-suite-export.v1",
  "repository": "GBOGEB/pipeline-automation-hub",
  "ref": "refs/heads/master",
  "state": "COMPLETE",
  "filter": "all",
  "pagination_complete": true,
  "details_complete": true,
  "metadata_truncated": false,
  "window_start": "2026-11-11T20:00:00Z",
  "window_end": "2026-11-12T07:00:00Z",
  "suites": []
}
~~~

Do not use this synthetic empty example as historical proof.
A COMPLETE assertion must be backed by actual owner-source receipts.

## QA K01-K12 and scaling gate

- **K01:** Unique merge-event key (PR / head SHA / merge timestamp).
- **K02:** Distinct exact head and merge-commit SHA references.
- **K03:** Explicit FPC status identity or genuine ABSENT bucket.
- **K04:** HTTP 403 is unresolved, never silently zero bypasses.
- **K05:** Incomplete pages, details, metadata, or time window fail closed.
- **K06:** Wrong merge SHA / ref / suite timestamp do not match.
- **K07:** Only explicit active P-SOFT failed required status naming FPC
  qualifies as bypass **observed**.
- **K08:** Generic bypass or missing details never become FPC-specific.
- **K09:** Multiple suites for a merge remain unresolved.
- **K10:** FPC SUCCESS is not independent owner approval.
- **K11:** Reordered input events give a deterministic identical receipt.
- **K12:** All test inputs preserve admission HOLD, no authority transfer,
  and no formal root closure.

Local pilot: **18/18 offline tests PASS**. Synthetic 29-event stress replay
injected 26 matching bypass examples and still yielded zero authorizations;
these are **synthetic examples**, not historical bypass evidence.
Real owner-source API state remains HTTP 403. Native exact-head CI is required.

~~~mermaid
flowchart TD
  A[Native PR head, merge timestamp, FPC status] --> B[Canonical admission audit]
  B --> C[Owner rule-suite evidence join]
  C --> D{Readable and complete?}
  D -- No / 403 --> H[UNRESOLVED and admission HOLD]
  D -- Yes --> E{Exact SHA, ref, time?}
  E -- No --> H
  E -- Yes --> F{Specific active FPC bypass?}
  F -- No / ambiguous --> H
  F -- Yes --> G[Bypass OBSERVED, not authorized]
  G --> I[Independent owner decision and canary]
  I --> H
~~~

## Rollout / rollback

Do not mutate the First-Pass Closure controller or rulesets. Run the
existing exact-head admission CI on the PR SHA and inspect its actual job
results. Missing or RED native checks mean HOLD. Roll back by closing the
draft PR without merging; existing master stays unchanged.
