# MC-CREW-FRONTIER-004 — Temporal short_compute re-earn lossless handover

**Date:** 2026-09-21  
**State:** `CONTROL_3_OF_5_SHORT_COMPUTE_REEARNED`  
**Authority transfer:** `false`  
**Formal credit delta:** `0`

## Result

The governed post-CONTROL regression of `short_compute` is now closed by later genuine scheduled evidence. The historical regression remains preserved; it is not deleted or rewritten.

Latest admissible scheduled authority:

- workflow: `MissionControl Temporal Allocation Policy`
- event: `schedule`
- run: `35574196822`
- analysis job: `106252442714`
- exact source SHA: `aad7c4ee3b464307365d55cb7d30999282b01838`
- conclusion: SUCCESS
- policy artifact: `10626843286`
- artifact digest: `sha256:5da6859bfcb0fad43c4339dc8ac7795dce052dbd177e6c90eaad04817a222020`

## short_compute frozen-gate result

`short_compute` is again `CONTROL_POLICY` with recommendation `ALLOC_SINGLE_CELL`.

Measured CONTROL frontier:

- independent windows: 25 >= 6
- distinct source SHAs: 10 >= 3
- temporal span: 519,001 s >= 86,400 s
- directional windows: 21 >= 5
- direction consistency: 0.9523809524 >= 0.80
- pooled winner strength: 0.7098869126 >= 0.70
- latest two directional windows agree: true
- hosted runner classes: linux, macos, windows
- lanes: baseline + held
- REX veto: false
- observed pairs: 150
- direction counts: 20 SINGLE / 1 PAIRED.

Therefore the exact success predicate in `TEMPORAL_SHORT_COMPUTE_REEARN_GATE_v1.json` is satisfied and CONTROL is re-earned.

## Current temporal state

CONTROL classes:

1. `cache_artifact_reuse`
2. `short_compute`
3. `validation_bundle`

Non-CONTROL frontier:

- P0 `long_compute_contended` — regime reversal / direction-consistency first-red.
- P1 `human_dependency_wait_proxy` — weak/noisy direction; remains a controlled-wait proxy only.

Effective state: **3/5 CONTROL**. Full-set CONTROL remains false.

## 3P* / MIP

- Refresh: PASS — later genuine schedule consumed.
- Probe: PASS — frozen re-earn gate evaluated.
- Rank: PASS — P0/P1 collapse to the two remaining non-CONTROL classes.
- Prepare: PASS — re-earn contract was frozen before the event.
- Prove: PASS — exact schedule run/job/artifact/digest bound.
- Commit: repository binding through the re-earn PR.
- MIP Modernize: current authority returns to 3/5 without erasing regression history.
- MIP Innovate: promotion is exact-run + exact-artifact + all-gate bound.
- MIP Perpetuate: v4/current/receipt/validator/restart chain published together.

## Historical lineage preserved

Historical 3/5 acceptance remains historical.
The run `35350275999` regression remains a valid governed regression record.
The new state is a **re-earn**, not retroactive invalidation of that regression.

## Next governed frontier

1. P0 `long_compute_contended`: continue genuine-schedule signed-effect decomposition and stability accumulation.
2. P1 `human_dependency_wait_proxy`: continue genuine-schedule stability measurement; never claim real-human intervention evidence from the proxy.
3. Surveil all three CONTROL classes and revoke only on later governed regression.
4. Evaluate H3 7-day persistence only when genuine schedule span reaches >=604800 s.

No manual, PR, push, synthetic, or challenge traffic creates CONTROL clock or promotion credit.

## Repository publication proof

The re-earn package was published through PR #343.

- PR head: `3512f175dc3cb695af8b2a3928848a0c18efc986`
- exact-head proof: run `35574968398`, job `106254648195`, 7 executed steps, SUCCESS
- merge SHA: `d097c8b4fbb5e0896ff16ac08cb3418f96b51a1a`
- post-merge `push: master` proof: run `35575005172`, job `106254759828`, 7 executed steps, SUCCESS

Therefore 3PC Commit/Perpetuate for this temporal re-earn publication is PASS. This does not create full-set CONTROL or any project-global promotion.

## P1 convergence — human_dependency_wait_proxy

A bounded 3P* + MIP convergence pass on the same genuine schedule authority corrected the P1 first-red without creating promotion credit.

- direction consistency: `0.80` — **PASS at frozen threshold**
- pooled winner strength: `0.6389674804` — **FAIL vs frozen 0.70**
- latest two directional windows agree: true
- direction counts: 16 SINGLE / 4 PAIRED across 20 directional windows
- latest window: 3 SINGLE / 1 PAIRED / 2 ties
- Linux latest cell pair is split; macOS and Windows each contain SINGLE + tie; baseline is mixed; held is SINGLE + tie
- claim boundary remains: `CONTROLLED_WAIT_PROXY_ONLY_NOT_REAL_HUMAN_INTERVENTION_EVIDENCE`.

Therefore P1 promotion remains WITHHELD. The correct current first-red is `pooled_winner_strength`, not `direction_consistency`. The diagnostic is `TEMPORAL_HUMAN_WAIT_P1_DIAGNOSTIC_20260921_v1.json`.

## P1 publication proof and convergence stop

P1 convergence published through PR #348:

- exact head: `b15a82340cec7bae53f1066423b0df93e8091616`
- exact-head proof: run `35578586769`, job `106265955128`, 7 executed steps, SUCCESS
- merge SHA: `a5af281352fa487add2d78012b3d7eac1e74836b`
- merged-master proof: run `35578640152`, job `106266120639`, 7 executed steps, SUCCESS

P1 MIP Perpetuate is PASS. With P0 and P1 both diagnostically decomposed, another temporal 3P*/MIP pass on the same evidence is a controlled no-op. The next temporal execution is event-driven: a later genuine schedule, or H3 7-day maturity.
