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
