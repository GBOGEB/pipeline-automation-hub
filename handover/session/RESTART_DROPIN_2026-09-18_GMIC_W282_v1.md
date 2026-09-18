# W282 LOSSLESS RESTART DROP-IN

Continue `GM-I-C / QPS / GEMINI` from repository and Drive authority. Do **not** rely on chat memory and do not rebuild predicates already proven.

## REFRESH FIRST

1. `GBOGEB/pipeline-automation-hub master`
2. `GBOGEB/cryoplant-project main`
3. `GBOGEB/cryoplant-project#923`
4. latest QPS Release Runner Probe
5. QPS recursive chain:
   - `handover/qps_recursive/GLOB.yaml`
   - `handover/qps_recursive/SESSION_CLOSE_CURRENT.yaml`
   - `handover/qps_recursive/QTG_CURRENT.yaml`
   - `handover/qps_recursive/QTG_CURRENT_EXTENSIONS.yaml`
   - `controls/QPS_GLOBAL_BD_CURRENT_v0.1.yaml`
   - `controls/QPS_TRIAGE_BT_PRESSURE_CURRENT_v1.yaml`
   - `controls/QPS_TRIAGE_CHILD_CONTRACT_v1.json`
6. `GBOGEB/GEMINI main` and issues #12/#16
7. Drive R3 landing zone `1B0i2T7hUsSFhHiyw35PPGaeQ_40E2nNr`
8. Drive IC3 root `1FnbajqBiIjL6Y4-_7tE1D515fNWvHsu3`
9. latest genuine MissionControl Temporal Allocation Policy schedule
10. Drive `GMI-DOCENG-001` including `RAW/` and `PROOFS/`

## CURRENT CONTROL AT W282

MissionControl launch head: `f226e6e61bc84482d4856f056b292ca9322e22f8`  
QPS observed main: `039e1fa84a6b32bcdb89e65807613377d50b4bb7`  
GEMINI observed main: `439838866e77784334ef76d231f9a9e0aa4f5e5c`

### GLOBAL FIRST RED — QPS #923

Latest observed QPS exact head `722b4382...`, Release Runner Probe `35349267160`, all three jobs zero-step.

If still zero-step:

- classify `INFRA_PREEXECUTION_ZERO_STEP / RUNNER_ADMISSION`;
- do not repair application/gate code;
- do not blind-rerun;
- keep GT-BD-003 Prove WITHHELD;
- keep GT_BDQ_0 WITHHELD and GT_BDQ_1 NOT_ADMITTED.

Resume directly at Prove only after a runner is actually assigned and steps execute.

### R3 W275 LANE

Capsule-v2 = PASS. Producer tooling = PASS/MERGED. Sole physical red = exact successor Git bundle return for:

`1248290ca0a9d55ec83d0efa0235ed1a45a88eeb`

Run on the authentic Windows QPS clone:

`powershell -ExecutionPolicy Bypass -File .\scripts\build_qps_r3_successor_handoff.ps1 -QpsClone "C:\Users\gbonthuy\cryoplant-project" -OutDir ".\output\r3_successor_handoff"`

Return bundle + SHA-256 sidecar + machine receipt to Drive folder `1B0i2T7hUsSFhHiyw35PPGaeQ_40E2nNr`.

Do not rebuild capsule-v2 or producer tooling. 3PC Prepare PASS; Prove waits physical bundle; R4 blocked.

### IC3

Drive root currently had owner-only permission and no service-account Viewer ACL. Issue #12 remains external first-red.

Only a real hosted >0-step WIF/Drive run with `IC3_DRIVE_READONLY_GT0_STEP_PASS` advances IC3.

### TEMPORAL

Latest published genuine schedule: run `35319784958`, 19 windows, 389315 s, CONTROL 3/5. Thresholds frozen.

Consume only a later genuine `schedule` event. No manual CONTROL clock.

### DRIVE LOSSLESSNESS

`GMI-DOCENG-001/RAW` was empty. W274 byte/canonical proofs exist. Do not fabricate raw session history.

## W282 ARTIFACTS

- `mission-control/qps-triage-ultra/missions/receipts/GMIC_W282_3PSTAR_MIP_CONTROL_20260918_v1.yaml`
- `mission-control/grand-missions/GM_I_C_R3_SUCCESSOR_CURRENT_v1.yaml`
- `handover/session/SC_2026-09-18_GMIC_W282_3PSTAR_MIP_LOSSLESS_HANDOVER_v1.md`
- `handover/session/RESTART_DROPIN_2026-09-18_GMIC_W282_v1.md`

## RECURSE ONLY ON MATERIAL CHANGE

- QPS runner admission changes;
- physical R3 bundle returns;
- IC3 WIF/ACL changes;
- later genuine temporal schedule receipt appears;
- real RAW source bytes materialize.

Preserve `authority_transfer=false`, `formal_credit_delta=0`, and all non-compensation rules.
