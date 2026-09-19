# RESTART DROP-IN — GM-V 3P* + MIP v3

Continue from repository authority only.

READ FIRST:
1. `mission-control/grand-missions/GM_V_3PSTAR_MIP_REFRESH_20260918T1656_v3.json`
2. `mission-control/grand-missions/handover/SC_2026-09-18_GM_V_3PSTAR_MIP_LOSSLESS_HANDOVER_v3.md`
3. `mission-control/grand-missions/GRAND_MISSION_REGISTRY.json`
4. `GBOGEB/cryoplant-project#923`

EXPECTED STATE UNLESS LIVE AUTHORITY ADVANCED:
- GM-IV = ACTIVE_8_OF_8
- GM-IV canonical children = []
- GM-V = HELD
- GM-V children = []
- GM-V crew = UNALLOCATED
- #923 = rank-0 external runner-admission first red
- 3PC Prove = WITHHELD_EXTERNAL_OWNER_ACTION

REENTRY:
Refresh MissionControl master + QPS main + issue #923. If owner-side Actions admission did not materially change, STOP without rerun. If it changed, run the unchanged Release Runner Probe and require runner_id != 0 and steps > 0 before any child validator or GM-V launch transaction.
