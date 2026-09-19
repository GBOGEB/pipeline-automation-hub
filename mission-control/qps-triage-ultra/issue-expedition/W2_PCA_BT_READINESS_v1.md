# ISSUE-EXPEDITION W2 — measured issue telemetry

As of 2026-09-19T06:23:00Z, Wave 2 contains **11** bound issue rows. Four Historian child issues were closed with successor/control lineage retained. The only currently allocation-eligible runnable issue in this bounded snapshot is **pipeline-automation-hub#314**.

## Admission result

- **PCA: WITHHELD.** Eligibility is filtered before variance analysis; N=1 allocation-eligible row is not an admissible multivariate population.
- **Bradley-Terry: WITHHELD.** There are zero observed same-crew-slot pair outcomes and therefore no connected comparison graph.
- Operational ordering remains **NON_BT_REVERSE_PRESSURE** with gate-first P0 semantics.
- Unknown metrics remain `null`, never silently converted to zero.

## Current routing

| Issue | Action | Allocation eligible | Notes |
|---|---|---:|---|
| pipeline-automation-hub#314 | P0 EXECUTE_NOW | yes | Exact-head FPC proof queued; branch frozen |
| pipeline-automation-hub#304 | P0 BLOCKED_DEPENDENCY | no | Held behind #314 |
| cryoplant-project#1550 | P0 BLOCKED_DEPENDENCY | no | Consumer held behind clean parent gate |
| gg_MATH#4 | DONE_CLOSE | no | Residual math BD routed to gg_MATH#27 |
| Q_engineering_tools#32 | DONE_CLOSE / CONTROL | no | W2F repair survives; #923 not compensated |
| GEMINI#6 | DONE_CLOSE / SUPERSEDED | no | Residuals routed to GEMINI#12/#16 |
| orchestration-sandbox#1 | DONE_CLOSE / REFERENCE_ONLY | no | No actionable debt |
| GEMINI#12 | EXTERNAL_RETURN | no | WIF/service-account/Drive ACL |
| GEMINI#16 | EXTERNAL_RETURN | no | Physical successor Git bundle |
| ABACUS#1278 | EXTERNAL_RETURN | no | Owner/admin required-status/ruleset |
| cryoplant-project#923 | EXTERNAL_RETURN | no | Private-repo runner admission veto |

## Next measurement trigger

Re-run readiness only after at least one additional internally runnable issue competes for the same bounded crew slot with measured queue/execution metadata. BT requires explicit pair-selection records; PCA requires an adequate filtered observed matrix.

No engineering, release, runtime-GOLD, or acceptance authority is created by this ledger.
