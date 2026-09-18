# W305 First-Pass Closure Gate

The historical R3 baseline remains immutable at 25% first-pass closure. W305 creates a prospective controlled cohort rather than rewriting history.

## Merge transaction

```
Prepare
-> canonical self-test PASS
-> mutation/fault proof PASS
-> exact-head CI proof PASS
-> Codex review COMPLETE on exact head
-> zero Codex COMMENTED review bound to that exact head
-> First-Pass Closure Gate PASS
-> merge
```

The PR body carries a receipt without changing the Git head:

```html
<!-- FPC_RECEIPT_V1
{
  "schema": "first_pass_closure/v1",
  "head_sha": "<40-char PR head>",
  "required_runs": [
    {
      "repo": "GBOGEB/repo",
      "run_id": 123456789,
      "purposes": ["canonical_self_test", "mutation_test", "exact_head_ci"]
    }
  ]
}
-->
```

Every referenced run must be completed/success and must bind the same exact PR head. The union of run purposes must cover all three required proof classes.

The gate checks the Codex summary comment for a completed exact-head review. Any Codex `COMMENTED` review whose reviewed-commit prefix matches the current exact head blocks merge.

Old-head findings do not block a repaired/re-reviewed exact head.

## KPI

Prospective cohort = next 8 governed primary PRs:
- minimum 7/8 first-pass clean = 87.5%
- stretch 8/8 = 100%
- post-merge P1/P2 findings = 0
- repair PRs <= 1

This is process-quality control only; it grants no engineering, R3, runtime-GOLD, GT, procurement, acceptance, or formal credit.
