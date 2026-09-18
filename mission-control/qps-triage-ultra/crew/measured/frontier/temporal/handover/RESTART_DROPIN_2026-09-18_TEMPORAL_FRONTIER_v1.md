# RESTART DROP-IN — Temporal frontier v2

Refresh `GBOGEB/pipeline-automation-hub master` first.

## Canonical state

Current temporal state is:

`CONTROL_REGRESSION_ACTIVE_2_OF_5_CONTROL_THREE_CLASS_FRONTIER`

Do **not** restart from the older 3/5 text.

Read:
1. `TEMPORAL_FRONTIER_CURRENT_v1.json`
2. `TEMPORAL_3PSTAR_MIP_ITERATION_v3.json`
3. `TEMPORAL_CONTROL_REGRESSION_v1.json`
4. `TEMPORAL_SHORT_COMPUTE_REEARN_GATE_v1.json`
5. `TEMPORAL_POLICY_CONFIG_v1.json`.

## Current frontier

P0 `short_compute`
- CONTROL revoked
- first red: pooled winner strength
- current 0.6907625244
- frozen minimum 0.70
- latest genuine schedule run `35350275999`
- latest window 3 SINGLE / 3 PAIRED
- habitat/lane heterogeneity observed
- action: wait for a later genuine scheduled receipt and re-evaluate every frozen gate.

P1 `long_compute_contended`
- regime reversal
- continue runner/lane/temporal decomposition.

P2 `human_dependency_wait_proxy`
- weak/noisy
- continue genuine scheduled stability measurement
- never relabel as real-human evidence.

## Re-entry rule

Only a later successful **schedule-event** Temporal Allocation Policy receipt can re-earn short_compute CONTROL. PR/push/manual/synthetic evidence is non-promoting.

REX-005 sequencing control remains PASS and independent of the short_compute regression.

authority_transfer=false; formal_credit_delta=0.
