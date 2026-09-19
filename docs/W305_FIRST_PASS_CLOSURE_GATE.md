# W305 First-Pass Closure Gate

The historical R3 baseline remains immutable at **25% first-pass closure**. W305 creates a prospective controlled cohort rather than rewriting history.

## Merge-last transaction

```
Prepare
-> canonical self-test PASS
-> mutation/fault proof PASS
-> exact-head CI proof PASS
-> Codex review COMPLETE on exact head
-> zero Codex COMMENTED review bound to exact head
-> FPC Gate PASS
-> merge
```

When the gate is red, its workflow attempts to **disable GitHub auto-merge** on the PR. This provides an enforcement path even when repository administration is unavailable. An owner-side branch rule making `First-Pass Closure Gate / first-pass-closure` required is still recommended for defense in depth.

The gate also re-runs on `pull_request_review` events, so a later Codex finding on the same SHA invalidates a previously green gate.


## Trusted-controller boundary

The merge gate executes from the repository default branch using `pull_request_target` (and re-evaluates on review changes). It does **not** execute PR-supplied gate code with a write-capable token.

Before a proof run can grant `canonical_self_test`, `mutation_test`, or `exact_head_ci`, the evaluator compares the PR head blobs for the governed proof surface against the default branch. The governed surface includes the gate workflow, proof workflow, evaluator, evaluator tests, and policy. A PR that mutates any of those files is therefore **not allowed to self-certify**.

Changes to the trusted controller itself use a bootstrap transaction:
1. open a bounded bootstrap PR;
2. require exact-head tests and Codex review-clean evidence;
3. do **not** count that bootstrap PR as a prospective FPC success;
4. after merge, run a distinct benign proof PR under the newly installed controller;
5. only after that post-bootstrap proof passes may consumers pin the new controller merge.

The gate disables auto-merge whenever the evaluator is not successful, including skipped/not-run evaluator paths, and malformed/missing policy input must still yield a deterministic FAIL receipt.

### Head-bound required status

`pull_request_target` gives the controller trusted default-branch code, but its workflow check suite is associated with the base-side event SHA rather than the proposed PR head. Therefore the controller also publishes an explicit commit status on the resolved PR head SHA using context `First-Pass Closure Gate / first-pass-closure`.

The status lifecycle is `pending -> success|failure`. Branch protection must consume this **head-bound status**, not assume that the `pull_request_target` workflow check itself is head-bound. A failure, incomplete evaluator, or earlier workflow failure leaves the head status non-success and merge remains held.

## PR-body receipt

The receipt binds successful exact-head workflow runs without changing Git content:

```html
<!-- FPC_RECEIPT_V1
{
  "schema": "first_pass_closure/v1",
  "head_sha": "<40-char PR head>",
  "required_runs": [
    {
      "repo": "GBOGEB/pipeline-automation-hub",
      "run_id": 123456789
    }
  ]
}
-->
```

Proof purposes are **not trusted from PR text**. They are derived from the controlled policy's workflow-identity allowlist using repository + workflow name + workflow path.

Every run must be `completed/success` and bind the exact PR head. The allowlisted run set must cover:
- `canonical_self_test`
- `mutation_test`
- `exact_head_ci`

## Consumer PR bootstrap

When a governed consumer PR is the first transaction to add its own proof workflow, the First-Pass Closure Gate still requires the existing allowlisted `First-Pass Closure Proof` on that same exact head. A consumer may therefore include this documentation path in its bounded change set to trigger the already-governed proof workflow. This does **not** weaken the proof identity allowlist and does not make the consumer workflow a substitute for the canonical proof.

After the allowlisted proof succeeds, bind that run in the PR-body receipt, wait for the exact-head Codex review to complete with zero material findings, then let the gate re-evaluate. Merge remains the last event.

### Dynamic dashboard safety

For HTML dashboards that render repository-controlled JSON, values must be inserted as DOM text (`textContent` / `createTextNode`) rather than interpolated into `innerHTML`. A CodeQL DOM-text-reinterpretation finding is a material pre-merge defect: repair it on a new exact head, rerun the allowlisted proof, obtain a clean exact-head review, and re-evaluate the First-Pass Closure Gate before merge.

## Review-clean test

The gate requires:
1. a Codex summary comment authored by `chatgpt-codex-connector`;
2. summary state `Completed`;
3. the exact current head prefix in that summary;
4. no Codex `COMMENTED` review bound to that exact head.

All comment and review pages are traversed; old-head findings do not block a repaired and re-reviewed head.

## Prospective KPI cohort

Next 8 governed primary PRs:
- minimum: **7/8 = 87.5% first-pass clean**
- stretch: **8/8 = 100%**
- post-merge P1/P2 findings: **0**
- repair PRs: **<=1**

Historical 25%, 210 s mean merge lead, and 169 s median remain immutable baselines.

This is process-quality control only. It grants no engineering, R3, runtime-GOLD, GT, procurement, acceptance, or formal credit.
