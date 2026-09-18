# Golden Thread v3 restart drop-in — external owner-action gate

Refresh first:

1. `GBOGEB/cryoplant-project main`
2. QPS issue `#923`
3. QPS PR `#1487`
4. `GBOGEB/pipeline-automation-hub master`
5. this v3 session close and v2 frontier.

Read:

1. `mission-control/golden-thread/handover/SESSION_CLOSE_CURRENT_v3.yaml`
2. `mission-control/golden-thread/GOLDEN_THREAD_FRONTIER_CURRENT_v2.yaml`
3. `mission-control/golden-thread/GOLDEN_THREAD_MIP_W284_20260918_v2.yaml`
4. `mission-control/golden-thread/GT_BD_003_OWNER_ACTION_REENTRY_CONTRACT_v1.json`
5. QPS `triage/w284/QPS_W284_GOLDEN_THREAD_3PSTAR_CONTROL_v0.1.yaml`

Do not repeat already-burned GT-BD-003 Prepare.

Current state:

- GT-BD-003 Prepare = PASS.
- Prove = WITHHELD_EXTERNAL_OWNER_ACTION.
- Commit = HOLD.
- QPS GT_BDQ_0 = WITHHELD.
- GT_BDQ_1 = NOT_ADMITTED.
- #923 = OPEN owner-action gate.
- authority_transfer = false.
- QPS/formal/engineering credit delta = 0.

Only admitted re-entry:

`owner-side Actions admission change -> unchanged Release Runner Probe -> runner_id != 0 -> steps > 0 -> exact child validator -> exact proof bundle -> GT-BD-003 3PC Prove`.

If the probe is still zero-step, stop with `INFRA_PREEXECUTION_ZERO_STEP`; do not repair application/gate logic.

Preserve:
`PARENT_PASS_NE_CHILD_ACCEPT`,
`ZERO_STEP_NE_APPLICATION_FAIL`,
`RESET_NE_ENGINEERING_ACCEPT`,
`MISSIONCONTROL_PASS_NE_QPS_GT_BDQ_PASS`,
`AUTHORITY_TRANSFER_FALSE`,
`UNKNOWN_NE_ZERO`.
