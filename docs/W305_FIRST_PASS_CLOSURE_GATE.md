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


## R5 self-protection hardening

The gate now treats its proof-workflow implementation as part of proof identity. A run is not trusted solely because repository, workflow name and workflow path match the allowlist: the allowlisted workflow content at the candidate head must be byte-identical to the same workflow path at the PR base SHA. A PR therefore cannot rewrite the allowlisted proof workflow and use that rewritten workflow as its own proof.

The workflow also resolves the PR number before fallible checkout/test/evaluation work. The auto-merge hold runs under `always()` whenever the gate is not proven green, including skipped/not-run evaluator states. If the evaluator never emits a receipt, the workflow synthesizes a machine-readable `FAIL_FIRST_PASS_CLOSURE_GATE` receipt before artifact upload.

Policy missing/invalid JSON and unexpected admission exceptions are normalized into deterministic fail receipts rather than escaping the evidence path.

These controls are process-quality protections only. Repository-owner required-status/ruleset enforcement remains the preferred independent defense-in-depth boundary.


## R5 closure proof anchor — 2026-09-19

The R5 self-protection implementation is present in the repository authority used by this proof transaction. PR #335 exists to bind the exact-head canonical proof, review-clean result, and closure/consumer handoff receipts without introducing a second implementation authority.

A successful proof on this PR demonstrates the integrated state containing:
- trusted-base workflow-content identity binding;
- deterministic early-failure receipts;
- fail-closed auto-merge cleanup for non-success/skipped evaluator states;
- the R5 mutation and policy-load fault matrix.

This proof anchor changes no engineering or release authority.
