# GM-V LOSSLESS RESTART DROP-IN v1

Continue GM-V from repository authority only. Do **not** reconstruct or replay already-burned predicates.

## REFRESH FIRST

1. `GBOGEB/pipeline-automation-hub master`
2. `GBOGEB/cryoplant-project main`
3. `GBOGEB/cryoplant-project#923`
4. relevant open/current GM-IV / GM-V PRs and workflow runs.

Historical refresh anchors from this handover:
- MissionControl `3df37a0485874f968f0dffa02bc474c5f4645fba`
- QPS `039e1fa84a6b32bcdb89e65807613377d50b4bb7`

## READ NEXT

1. `mission-control/grand-missions/GM_V_CURRENT_v1.json`
2. `mission-control/grand-missions/GM_V_3PSTAR_MIP_CONTROL_v1.json`
3. `mission-control/grand-missions/handover/SC_2026-09-18_GM_V_3PSTAR_MIP_LOSSLESS_HANDOVER_v1.md`
4. `mission-control/grand-missions/GM_V_GOVERNOR_READINESS_CONTRACT.json`
5. `mission-control/grand-missions/validate_gm_v_3pstar_mip_control.py`

## EXPECTED STATE UNLESS LIVE AUTHORITY ADVANCED

- GM-IV = `ACTIVE_8_OF_8`
- GM-IV runtime capability = `RUNTIME_PROVEN`, 8/8 capability coverage
- concurrency capacity = **not claimed**
- GM-V = `HELD`
- GM-V children = `[]`
- GM-V crew posture = `UNALLOCATED`
- GM-V launch authority = false
- #923 = OPEN / runner-admission first red
- 3PR = PASS
- MIP Modernize = PASS
- MIP Innovate = PASS
- MIP Perpetuate = repository-native handover/control
- 3PC Prepare = PASS
- 3PC Prove = WITHHELD_EXTERNAL
- 3PC Commit = HOLD
- 3P3 = NOT_AUTHORIZED

## DO NOT RE-RUN IF NO MATERIAL ADMISSION CHANGE

If no repository-visible or owner-returned
`HOSTED_ADMISSION_RESTORED` / `SELF_HOSTED_ATTACHED`
transition exists, stop. Do not burn another zero-step child probe.

## RE-ENTRY AFTER MATERIAL ADMISSION CHANGE

1. Run the **unchanged** QPS Release Runner Probe on the exact current QPS SHA.
2. Require `runner_id != 0` and `steps > 0`.
3. Execute the unchanged selected QPS child validator on that same exact SHA.
4. Bind repo + branch/PR + head SHA + schema/version + digest + result.
5. Repeat on a distinct fresh head.
6. Re-evaluate the GM-V Governor.
7. Only if it returns READY may a **separate GM-V launch transaction** be opened.

Preserve all non-compensation rules and `authority_transfer=false`.
