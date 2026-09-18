# MC-CREW-FRONTIER-004 — Temporal 3PSTAR + MIP Lossless Handover v1

## Canonical restart

Continue from repository authority only. Do not reconstruct this lane from chat memory.

Fresh-fetch `GBOGEB/pipeline-automation-hub master` before using any SHA below. Historical SHAs are anchors, not reset targets.

Read in this order:

1. `mission-control/qps-triage-ultra/crew/measured/frontier/temporal/TEMPORAL_FRONTIER_CURRENT_v1.json`
2. `mission-control/qps-triage-ultra/crew/measured/frontier/temporal/TEMPORAL_POLICY_CONFIG_v1.json`
3. `mission-control/qps-triage-ultra/crew/measured/frontier/temporal/CONTROL_POLICY_ACCEPTANCE_v1.json`
4. `mission-control/qps-triage-ultra/crew/measured/frontier/temporal/TEMPORAL_3PSTAR_MIP_ITERATION_v3.json`
5. `mission-control/qps-triage-ultra/crew/measured/frontier/temporal/temporal_frontier_burndown.py`
6. `mission-control/qps-triage-ultra/crew/measured/frontier/temporal/test_temporal_frontier_burndown.py`
7. `.github/workflows/crew-temporal-3pstar-mip-burndown.yml`
8. this handover
9. `mission-control/qps-triage-ultra/crew/measured/frontier/temporal/handover/RESTART_DROPIN_2026-09-18_TEMPORAL_FRONTIER_v1.md`.

## Current governed state

The temporal allocation lane is **3 of 5 CONTROL**.

CONTROL classes:
- `cache_artifact_reuse` -> `CONTROL_POLICY / ALLOC_SINGLE_CELL`
- `short_compute` -> `CONTROL_POLICY / ALLOC_SINGLE_CELL`
- `validation_bundle` -> `CONTROL_POLICY / ALLOC_PAIRED_CELL`.

Non-CONTROL frontier:
- P0 `long_compute_contended`
- P1 `human_dependency_wait_proxy`.

Full-set CONTROL is false.

Frozen CONTROL thresholds are unchanged. No synthetic, PR, push or manual event is allowed to create governed CONTROL clock time. Competency promotions remain zero. `authority_transfer=false`. Formal credit delta is zero.

## Genuine scheduled authority

The current accepted class disposition remains bound to genuine schedule-event run `35319784958`:

- exact source SHA `9e7e698c1cf40b594244aba01e1ea704ef76d203`
- artifact `10536637698`
- artifact digest `sha256:d72bc6ec77c07821ef1a4191796dd0c0e008b9f05a95a46d4c913f3062648ce9`
- genuine scheduled windows: 19
- distinct scheduled source SHAs: 11
- genuine scheduled span: 389,315 s
- Linux / macOS / Windows present
- baseline + held lanes present
- REX veto: false.

72 h surveillance is mature. The 7 d surveillance horizon is not mature.

## 3P* execution history

### 3PR — Refresh / Probe / Rank

Refresh PASS:
- 3/5 CONTROL bound to genuine scheduled evidence.

Probe PASS:
- the two remaining classes do not share the same failure mechanism.

Rank PASS:

P0 — `long_compute_contended`
- dominant scheduled direction: PAIRED
- scheduled directional counts: PAIRED 9 / SINGLE 5
- consistency: 0.6428571429 < 0.80
- pooled winner strength: 0.5987602960 < 0.70
- latest-two directional windows disagree
- early direction: PAIRED
- late direction: SINGLE
- classification: `REGIME_REVERSAL_OBSERVED`
- minimum clean dominant-direction windows required merely to reach 0.80 consistency: 11
- next action: `DECOMPOSE_SIGNED_EFFECT_BY_RUNNER_LANE_AND_TEMPORAL_HALF`.

P1 — `human_dependency_wait_proxy`
- dominant scheduled direction: SINGLE
- scheduled directional counts: SINGLE 11 / PAIRED 4
- consistency: 0.7333333333 < 0.80
- pooled winner strength: 0.6212672162 < 0.70
- latest-two directional windows disagree
- direction flips: 7
- indeterminate fraction: 0.2105263158
- early direction: SINGLE
- late direction: SINGLE
- classification: `WEAK_OR_NOISY_DIRECTION`
- minimum clean dominant-direction windows required merely to reach 0.80 consistency: 5
- claim boundary: this is a controlled wait proxy, not evidence of real human intervention.

### 3PC — Prepare / Prove / Commit

Prepare PASS:
- deterministic burndown engine
- unit tests
- genuine-schedule downstream consumer
- exact-head PR/push recurrence.

Implementation PR #246 merged at `a56e94ee92077b912a5a3480ae73a1c13b775eba`.

Its dedicated Prove job was still queued at merge time. This is retained as **REX-005 / unbound promotion-proof gate** rather than hidden.

The original exact PR-head proof later executed successfully:
- run `35351860027`
- job `105621646115`
- exact head `1b62b2d254b70e47b654df31d40ddfd6fabdc11c`
- 3/3 unit tests PASS
- `PASS_TEMPORAL_3PSTAR_MIP_ITERATION_CONTROL`.

Therefore implementation correctness is proven, but the original merge-before-Prove sequence nonconformity remains historical.

Proof-gate repair PR #252 merged at `243337e7170029ccfbcf1588ce951356fd1d22a7`.

That repair adds merged-master recurrence. Its exact post-merge proof is:
- run `35352260069`
- job `105622958891`
- state at this handover: **QUEUED / zero executed steps observed**.

Do not treat the repair merge itself as Prove.

3PC Commit / 3P3 closure credit for the repair remains WITHHELD until that exact merged-master job executes successfully.

## MIP iteration

Modernize — PASS:
- replaced one generic "unstable" bucket with explicit `REGIME_REVERSAL_OBSERVED` and `WEAK_OR_NOISY_DIRECTION` mechanisms.

Innovate — PASS:
- added deterministic first-red
- consistency deficit
- pooled winner-strength deficit
- minimum clean dominant-window pressure
- surveillance regime classification.

Perpetuate — IMPLEMENTED / WAIT RUNTIME CONFIRMATION:
- each genuine scheduled Temporal Allocation Policy return can generate a governed burndown artifact;
- PR-head exact proof is retained;
- merged-master recurrence is wired;
- the current handover and restart chain are repository-native.

## Exact next predicate

First resolve:

`run 35352260069 / job 105622958891`.

If it is still queued:
- do not blind-rerun;
- do not call it failure;
- do not claim REX-005 closure.

If it executes and PASSes:
1. bind exact run/job/merge identity in a successor reconciliation;
2. mark this REX-005 occurrence CONTROLLED for the temporal lane;
3. keep the 3/5 CONTROL split;
4. continue P0 long-compute regime decomposition;
5. continue P1 wait-proxy genuine-schedule surveillance;
6. do not reopen accepted CONTROL classes absent governed regression.

If it executes and FAILs:
1. identify the first failing step;
2. classify application vs infrastructure;
3. repair only that first red;
4. preserve all thresholds and class authority;
5. keep propagation/closure credit withheld.

## Non-compensation

- No threshold lowering.
- No synthetic/manual/push/PR CONTROL clock credit.
- No competency promotion.
- No authority transfer.
- No real-human claim from `human_dependency_wait_proxy`.
- No full-set CONTROL claim.
- No re-opening of the three accepted CONTROL classes without governed regression evidence.
