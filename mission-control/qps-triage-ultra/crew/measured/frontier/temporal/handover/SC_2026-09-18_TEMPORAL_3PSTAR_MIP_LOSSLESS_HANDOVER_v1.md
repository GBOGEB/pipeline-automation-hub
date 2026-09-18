# MC-CREW-FRONTIER-004 — Temporal 3PSTAR + MIP Lossless Handover v2

## Canonical restart

Continue from repository authority only. The earlier 3/5 text in v1 is superseded by governed post-CONTROL regression evidence.

Read first:
1. `TEMPORAL_FRONTIER_CURRENT_v1.json`
2. `TEMPORAL_3PSTAR_MIP_ITERATION_v3.json`
3. `TEMPORAL_CONTROL_REGRESSION_v1.json`
4. `TEMPORAL_SHORT_COMPUTE_REEARN_GATE_v1.json`
5. `TEMPORAL_POLICY_CONFIG_v1.json`
6. this handover
7. restart drop-in.

## Current governed state

Effective temporal CONTROL is **2 of 5**, not 3 of 5.

CONTROL:
- `cache_artifact_reuse`
- `validation_bundle`

Revoked / re-earn required:
- P0 `short_compute`

Other active frontier:
- P1 `long_compute_contended`
- P2 `human_dependency_wait_proxy`

Full-set CONTROL remains false.

## Why short_compute regressed

Genuine scheduled authority:
- run `35350275999`
- exact source SHA `f226e6e61bc84482d4856f056b292ca9322e22f8`
- artifact `10549864368`
- digest `sha256:6d1ee0018358fff48a83d006322ba1e0b504b32a1cf68e8b4c3e98d0001713c3`
- 20 scheduled windows
- 12 distinct source SHAs
- span 410,680 s.

`short_compute` pooled winner strength fell from 0.7008026573 to 0.6907625244, below the frozen 0.70 gate. CONTROL is therefore revoked.

The latest genuine scheduled window was globally neutral: 3 SINGLE wins vs 3 PAIRED wins. It is not uniform neutrality:
- Linux: indeterminate
- macOS: SINGLE
- Windows: PAIRED
- baseline lane: SINGLE
- held lane: PAIRED.

Classification: `HABITAT_AND_LANE_HETEROGENEITY_OBSERVED`.

## Re-earn contract

`short_compute` may re-enter CONTROL only when a **later genuine schedule-event** Temporal Allocation Policy receipt satisfies every frozen gate again, including:
- independent windows >= 6
- distinct source SHAs >= 3
- temporal span >= 86,400 s
- directional windows >= 5
- direction consistency >= 0.80
- pooled winner strength >= 0.70
- latest two directional windows agree
- >=3 hosted runner classes
- baseline + held lanes
- no persistent/regression REX veto.

No PR, push, manual, synthetic or challenge evidence can restore CONTROL.

## Proof / REX chain

REX-005 remains CONTROLLED:
- implementation #246 late exact-head proof: run `35351860027`, job `105621646115`, PASS.
- proof repair #252 post-merge recurrence: run `35352260069`, job `105622958891`, PASS.

That proof controls the sequencing defect; it does not compensate the later short_compute policy regression.

## 3P* / MIP current position

- Refresh: PASS_WITH_GOVERNED_POST_CONTROL_REGRESSION
- Probe: PASS_THREE_DISTINCT_FAILURE_MODES
- Rank: P0 short_compute regression; P1 long_compute regime reversal; P2 human wait proxy weak/noisy
- Prepare: PASS
- Prove: PASS for temporal control machinery
- Perpetuate: PASS for the machinery and restart chain; policy state remains surveillance-driven.

## Guards

- frozen thresholds unchanged
- genuine schedule only for CONTROL clock
- historical 3/5 acceptance retained as history, not current truth
- no competency promotion
- no authority transfer
- formal credit delta 0
- human wait proxy is not real-human evidence.
