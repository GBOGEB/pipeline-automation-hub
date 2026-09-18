# MissionControl restart drop-in — QPS W249 LEG5 runner-compat successor

Start from repository authority.

Refresh:
- `GBOGEB/pipeline-automation-hub master`
- this successor PR/head
- QPS main and PR #1456
- QPS issues #923, #1258, #1266, #1357

Read:
1. `mission-control/qps-triage-ultra/leg5/QPS_LEG5_W249_3PSTAR_MIP_RECEIVER_v1.yaml`
2. `mission-control/qps-triage-ultra/leg5/QPS_LEG5_W249_3PSTAR_MIP_EXECUTION_RECEIPT_v1.yaml`
3. `mission-control/qps-triage-ultra/leg5/QPS_LEG5_W249_RUNNER_COMPAT_RECEIVER_v2.yaml`
4. `mission-control/qps-triage-ultra/leg5/QPS_LEG5_W249_RUNNER_COMPAT_DEPENDENCY_GRAPH_v2.json`
5. QPS PR #1456 exact head `20fbe0af279342129fbb63a0a22a4ee63b42a496`, merge `bfa80d4fa9756f03dd4aaa4c6dedff92b53760d6`
6. QPS successor handover v2.

Preserve:
- historical #1450 / MC #200 receipts unchanged;
- QPS #1456 is the append-only child successor that hardens runner compatibility;
- LEG5 remains 7/9;
- #1266 and #1357 remain runtime-withheld;
- #923 remains the private-QPS execution first red;
- parent public execution cannot compensate private QPS runtime;
- authority_transfer=false and all child credit deltas remain zero.

Exact next child predicate:

`runner_id != 0 && steps > 0 && validator_runner_selector_compatible`

The governed selector is `CRYO_RECEIPT_RUNNER`, default `["ubuntu-latest"]`. A self-hosted bypass is admissible only when the configured probe and both LEG5 validators select that same admitted runner family.

If the child remains zero-step, STOP runtime progression and make no validator repair.
