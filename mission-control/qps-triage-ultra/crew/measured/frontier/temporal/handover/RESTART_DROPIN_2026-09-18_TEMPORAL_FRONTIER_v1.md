# RESTART DROP-IN — MC-CREW-FRONTIER-004 Temporal 3PSTAR + MIP

Continue from repository authority only.

## REFRESH FIRST

Fresh-fetch:
- `GBOGEB/pipeline-automation-hub master`
- PR #246
- PR #252
- workflow run `35351860027`
- workflow run `35352260069`
- current checks on the latest temporal merge/head.

Do not reset `master` to any historical SHA below.

## READ NEXT

1. `mission-control/qps-triage-ultra/crew/measured/frontier/temporal/TEMPORAL_FRONTIER_CURRENT_v1.json`
2. `mission-control/qps-triage-ultra/crew/measured/frontier/temporal/TEMPORAL_POLICY_CONFIG_v1.json`
3. `mission-control/qps-triage-ultra/crew/measured/frontier/temporal/CONTROL_POLICY_ACCEPTANCE_v1.json`
4. `mission-control/qps-triage-ultra/crew/measured/frontier/temporal/TEMPORAL_3PSTAR_MIP_ITERATION_v3.json`
5. `mission-control/qps-triage-ultra/crew/measured/frontier/temporal/handover/SC_2026-09-18_TEMPORAL_3PSTAR_MIP_LOSSLESS_HANDOVER_v1.md`
6. `mission-control/qps-triage-ultra/crew/measured/frontier/temporal/temporal_frontier_burndown.py`
7. `.github/workflows/crew-temporal-3pstar-mip-burndown.yml`.

## STATE TO EXPECT UNLESS LIVE AUTHORITY HAS ADVANCED

- temporal CONTROL: 3/5
- CONTROL: cache reuse / short compute / validation bundle
- P0: `long_compute_contended`
- P1: `human_dependency_wait_proxy`
- full CONTROL: false
- 72 h surveillance: mature
- 7 d surveillance: not mature
- competency promotions: 0
- authority transfer: false
- formal credit delta: 0.

## PROOF / REX CHAIN

Implementation:
- PR #246
- head `1b62b2d254b70e47b654df31d40ddfd6fabdc11c`
- merge `a56e94ee92077b912a5a3480ae73a1c13b775eba`.

Late exact-head Prove PASS:
- run `35351860027`
- job `105621646115`
- 3/3 tests PASS
- `PASS_TEMPORAL_3PSTAR_MIP_ITERATION_CONTROL`.

Sequence defect:
- REX-005 / unbound promotion-proof gate
- reason: implementation merged before dedicated Prove completed.

Repair:
- PR #252
- merge `243337e7170029ccfbcf1588ce951356fd1d22a7`
- adds post-merge `push: master` exact-head recurrence.

## EXACT NEXT PREDICATE

Resolve:

`run 35352260069 / job 105622958891`.

If queued:
- stop closure;
- do not blind-rerun;
- do not classify application failure.

If PASS:
1. bind exact merged-master PASS;
2. close this temporal REX-005 occurrence to CONTROL;
3. retain 3/5 CONTROL;
4. proceed P0:
   `DECOMPOSE_SIGNED_EFFECT_BY_RUNNER_LANE_AND_TEMPORAL_HALF`;
5. proceed P1 only as controlled wait-proxy surveillance;
6. at genuine scheduled span >=604800 s, evaluate 7-day surveillance without altering entry thresholds.

If FAIL:
1. bind exact failing step;
2. repair only first red;
3. keep 3P3/closure credit withheld;
4. do not alter CONTROL thresholds.

## ACTIVE FRONTIER DETAILS

### P0 long_compute_contended

- PAIRED 9 / SINGLE 5
- consistency 0.642857 < 0.80
- winner strength 0.598760 < 0.70
- early PAIRED -> late SINGLE
- latest-two disagree
- minimum 11 clean dominant windows merely to reach consistency 0.80
- regime: `REGIME_REVERSAL_OBSERVED`.

### P1 human_dependency_wait_proxy

- SINGLE 11 / PAIRED 4
- consistency 0.733333 < 0.80
- winner strength 0.621267 < 0.70
- 7 flips
- ~21.1% indeterminate
- early SINGLE -> late SINGLE
- minimum 5 clean dominant windows merely to reach consistency 0.80
- regime: `WEAK_OR_NOISY_DIRECTION`
- never convert this proxy into a claim about real human intervention.

## PRESERVE

- frozen thresholds;
- genuine schedule-only CONTROL clock;
- all three existing CONTROL classes unless governed regression occurs;
- REX veto authority;
- historical #246 merge-before-Prove sequence as negative evidence;
- no competency promotion;
- authority_transfer=false.
