# GM-V 3P* + MIP — LOSSLESS HANDOVER v1

**As of:** 2026-09-18 15:20 Europe/Brussels  
**Mission:** GM-V Governor readiness / operational-availability boundary  
**Authority transfer:** false  
**Formal / engineering credit delta:** 0 / 0

## 1. Refresh before claims

Do not rely on this snapshot as live truth without refreshing:

1. `GBOGEB/pipeline-automation-hub master`
2. `GBOGEB/cryoplant-project main`
3. `GBOGEB/cryoplant-project#923`
4. current/open GM-V or GM-IV control PRs.

Refresh snapshot used for this transaction:

- MissionControl master: `3df37a0485874f968f0dffa02bc474c5f4645fba`
- QPS main: `039e1fa84a6b32bcdb89e65807613377d50b4bb7`
- QPS #923: **OPEN**

## 2. Read order

1. `mission-control/grand-missions/GM_V_CURRENT_v1.json`
2. `mission-control/grand-missions/GM_V_3PSTAR_MIP_CONTROL_v1.json`
3. `mission-control/grand-missions/GM_V_GOVERNOR_READINESS_CONTRACT.json`
4. `mission-control/grand-missions/validate_gm_v_3pstar_mip_control.py`
5. `.github/workflows/gm-v-3pstar-mip-control.yml`
6. this handover
7. `mission-control/grand-missions/handover/RESTART_DROPIN_2026-09-18_GM_V_v1.md`

## 3. Canonical state

```text
GM-IV
  ACTIVE_8_OF_8
  runtime capability coverage = 8/8 RUNTIME_PROVEN
  concurrency capacity claim = false
  children = []

GM-V
  HELD
  frontier_count = 16
  children = []
  crew_posture = UNALLOCATED
  launch_authorized = false

external non-compensating gate
  GBOGEB/cryoplant-project#923 = OPEN
  classification = INFRA_PREEXECUTION_ZERO_STEP / RUNNER_ADMISSION
```

GM-V Governor result remains:

`WITHHOLD_GM_V_LAUNCH_EXTERNAL_OPERATIONAL_AVAILABILITY`.

A controlled WITHHOLD is a successful governance result; it is not launch authority.

## 4. Exact predecessor evidence

### ACTIVE_8 readiness
- head `3943ae33eea2a4af6171b97517c19b79ed986fe8`
- run `35145656795`
- artifact `10467671042`
- digest `sha256:97d37b98334acbab0e1fec9bae56163e20fd5b9c2751be2495c52642bc6dd4cb`

### Post-ACTIVE8 repeat CONTROL
- merge `7af02c89ca640c180b20341e0016c5f82096da26`
- exact head `5d86dca5cb794200998c6fbc93dc1669b05ae089`
- run `35150330651`
- artifact `10469090485`
- digest `sha256:d4b6c50228969135b2c98554d3b8d2876ffb0d03daa7d191465cf89670e64d24`

### Runtime capability proof
- PR #173
- exact head `9cdb8fe35e15b675f3fe1b2492c16f9785fc3115`
- merge `ea7a9818a57d5078bc26e35ed2d1f15d79657338`
- run `35171901674`
- job `105045151537`
- artifact `10476967287`
- digest `sha256:7a5a0910db8639b642d8e63b4e37169d636ee3e6b7fc2ba0da93789ad183fc68`
- result `PASS_RUNTIME_PROVEN_CAPABILITY_CAPACITY`
- scope `CAPABILITY_COVERAGE_NOT_CONCURRENCY_CAPACITY`

### GM-V readiness gate
- PR #221
- merge `0d3b66ee8c2566ed1e5f8b83c2932e4a9160bcbb`
- post-merge run `35343419829`
- artifact `10546460986`
- digest `sha256:d1d252e6635c79baca4af4c03a89732cad2a004c96f55e0ce650f98d818090ba`
- result `WITHHOLD`

### Historical-control fix-forward
- PR #223
- merge `3df37a0485874f968f0dffa02bc474c5f4645fba`
- post-merge `GM-IV PILOT_2_OF_8 Final Recensus`: run `35343914428` SUCCESS
- post-merge `GM-IV RECON_4 Promotion Control`: run `35343914458` SUCCESS

This repaired the pre-existing stage-drift false-reds after ACTIVE_8 and added pre-merge coverage for the formerly push-only recensus path.

## 5. 3P* burn

### 3PR — PASS
- **Refresh:** current MissionControl/QPS heads and #923 state refreshed.
- **Probe:** GM-IV ACTIVE_8 shape, 8/8 runtime capability proof, GM-V HELD shape and exact gate lineage rechecked.
- **Rank:** first non-compensating red is QPS private-repository runner admission (#923).

### 3PC
- **Prepare:** `PASS_CONTROL_PREPARED`
- **Prove:** `WITHHELD_EXTERNAL`
- **Commit:** `HOLD_WAIT_PROVE`

Prepared re-entry requires, in order:
1. owner-side Actions admission material change;
2. unchanged QPS Release Runner Probe on exact current QPS SHA;
3. `runner_id != 0`;
4. `steps > 0`;
5. unchanged selected child validator;
6. exact receipt binding;
7. repeat on a distinct fresh head.

### 3P3
`NOT_AUTHORIZED` until operational availability Prove passes and the GM-V Governor returns READY.

## 6. MIP iteration

### Modernize — PASS
- ACTIVE_8 readiness became stage-aware historical CONTROL after promotion.
- PILOT_2 final recensus now retains evidence under ACTIVE_8.
- RECON_4 promotion control now retains evidence under ACTIVE_8.
- formerly push-only recensus compatibility is pre-merge testable.

### Innovate — PASS
- controlled WITHHOLD is modeled as a positive governance result;
- capability coverage, concurrency capacity and operational availability are separate predicates;
- external non-compensating gates are explicit rather than silently absorbed into parent PASS.

### Perpetuate — THIS TRANSACTION
Repository-native restart surfaces are added:
- current pointer;
- machine 3P*/MIP control;
- deterministic validator;
- exact-head CI receipt;
- this lossless handover;
- restart drop-in.

Target after publication: **0 chat-only TODOs, 0 chat-only decisions**.

## 7. Stop rules

- Do not blind-rerun #923 while no runner-admission condition changed.
- Do not repair child application/validator logic from a zero-step result.
- Do not infer concurrency capacity from 8/8 capability coverage.
- Do not infer operational availability from RUNTIME_PROVEN capability coverage.
- Do not allocate GM-V crew or bind GM-V children while GM-V is HELD.
- Do not transfer authority or formal/engineering credit.
- Do not launch GM-V from this handover.
- Refresh live heads before any re-entry claim.

## 8. Next executable transition

The next legal transition is **outside MissionControl code** until QPS runner admission materially changes.

Accepted trigger classes:
- `HOSTED_ADMISSION_RESTORED:<changed condition>`
- `SELF_HOSTED_ATTACHED:<actual labels>`

After such a trigger, resume directly at **3PC Prove**. Do not repeat already-burned 3PR or 3PC Prepare unless repository authority has materially invalidated them.

## 9. Non-compensation invariants

`PARENT_PASS_NE_CHILD_ACCEPT`  
`ZERO_STEP_NE_APPLICATION_FAIL`  
`RUNTIME_PROVEN_CAPABILITY_NE_CONCURRENCY_CAPACITY`  
`RUNTIME_PROVEN_CAPABILITY_NE_OPERATIONAL_AVAILABILITY`  
`GM_IV_PASS_NE_GM_V_LAUNCH_AUTHORITY`  
`PUBLIC_MISSIONCONTROL_PASS_NE_QPS_923_CLOSURE`  
`AUTHORITY_TRANSFER_FALSE`  
`UNKNOWN_NE_ZERO`
