# GM-V LOSSLESS RESTART DROP-IN v2

Continue from repository authority. Preserve v1 as history and PR #239 as the immediate control predecessor.

## REFRESH FIRST
1. `GBOGEB/pipeline-automation-hub master`
2. `GBOGEB/cryoplant-project main`
3. `GBOGEB/cryoplant-project#923`
4. current GM-V/GM-IV and sibling GM-I-C transactions

## READ
1. `mission-control/grand-missions/GM_V_CURRENT_v1.json`
2. `mission-control/grand-missions/GM_V_3PSTAR_MIP_CONTROL_v1.json`
3. `mission-control/grand-missions/handover/SC_2026-09-18_GM_V_3PSTAR_MIP_LOSSLESS_HANDOVER_v2.md`
4. `mission-control/grand-missions/GM_V_GOVERNOR_READINESS_CONTRACT.json`
5. `mission-control/grand-missions/validate_gm_v_3pstar_mip_control.py`

## EXPECTED STATE UNLESS LIVE AUTHORITY ADVANCED
- GM-IV `ACTIVE_8_OF_8`
- capability coverage 8/8 RUNTIME_PROVEN
- concurrency capacity not claimed
- GM-V `HELD`, children `[]`, crew `UNALLOCATED`
- 3PC Prove `WITHHELD_EXTERNAL`
- #923 first-red

Fresh snapshot:
- QPS main `eeac2b60fc16e5b2131d4054f95da0b0c663cc40`
- PR #1476 head `458dae93993a970d94c5a8c85c2d04e40390e454`
- Release Runner Probe `35350233629`: three jobs, all 0 steps
- verify-ssot `35350233647` / `105616351882`: 0 steps

If no owner-side admission change is visible: STOP, no rerun.

If admission changed:
`unchanged probe -> runner_id != 0 -> steps > 0 -> exact child validator -> exact receipt -> distinct fresh-head repeat -> GM-V Governor`.

Only Governor READY permits a separate GM-V launch transaction. Keep `authority_transfer=false` and zero formal/engineering credit.
