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


## R6 trusted-base controller

R5 demonstrated that byte-binding only the proof workflow is insufficient when the candidate checkout can also replace the evaluator and its tests. R6 moves the promotion decision to a **trusted PR-base controller**.

For ordinary governed PRs:

1. `pull_request_target` resolves the live PR number, head SHA and base SHA without executing candidate content.
2. the gate checks out the exact PR **base SHA** into a separate trusted controller directory;
3. unit tests, policy and `first_pass_closure_gate.py` execute only from that base revision;
4. the candidate exact-head proof run is treated as evidence data;
5. any candidate change to a protected FPC controller path returns `CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP`;
6. the final workflow parses the emitted JSON and requires schema v3, `PASS_FIRST_PASS_CLOSURE_GATE`, `merge_allowed=true`, exact head/base binding, zero exact-head Codex findings and zero authority transfer.

A synthesized FAIL receipt can therefore never satisfy the final job merely because an evaluator process exited zero.

### Controller-maintenance bootstrap

The controller cannot safely certify a PR that changes the controller itself. Such a PR is a bootstrap transaction and is deliberately rejected by the ordinary gate. It requires an independent exact-head code review with zero material findings and must be followed after merge by a distinct non-controller canary PR. The canary must obtain a full trusted-base FPC PASS before W305 #314 can close or the QPS consumer can activate.

The candidate proof workflow now runs on every PR to `master`; it proves candidate behavior but never supplies promotion authority by itself.


## R7 rename and head-status hardening

R6 established trusted-base admission, but its first independent review exposed a protected-path rename escape: GitHub represents a rename with both `filename` and `previous_filename`. Admission must therefore test **both** names against the protected controller set. Moving a protected controller to an unprotected destination is still a controller mutation and requires the bootstrap path.

The trusted controller also publishes the FPC outcome directly on the resolved **PR head SHA** using status context `First-Pass Closure Gate / first-pass-closure`. This is required because the `pull_request_target` workflow/check-suite identity belongs to a trusted base-side event and is not, by itself, a branch-protection proof on the candidate head.

Head-status lifecycle:

```
PR resolved
-> head status PENDING
-> trusted base checkout/tests/evaluator
-> bound PASS receipt validation
-> receipt artifact upload
-> head status SUCCESS only if all required stages succeeded
-> otherwise head status FAILURE / no success
-> final complete-predicate auto-merge hold
-> fail-closed job
```

Runs are serialized per PR with cancellation of an older in-progress run. This prevents a stale review/edit run from publishing SUCCESS after a newer run has already observed a new finding. The final auto-merge hold is evaluated **after** receipt artifact and head-status publication, so artifact/status failure cannot escape merely because receipt validation itself passed.

Controller-maintenance PRs remain deliberately non-self-certifying. R7 itself must be merged only as an explicit reviewed bootstrap with zero material P1/P2 findings, followed by a distinct non-controller canary. That canary must carry an exact-head proof receipt, clean exact-head review, trusted-base FPC PASS, and the head-bound status success **before** merge.

No R7 bootstrap or canary changes QPS engineering, release, acceptance, runtime-GOLD, or formal credit.
