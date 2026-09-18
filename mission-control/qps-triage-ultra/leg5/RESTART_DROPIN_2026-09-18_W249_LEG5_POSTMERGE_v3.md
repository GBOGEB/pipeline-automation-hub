# RESTART DROP-IN v3 — QPS W249 LEG5

Continue from repository authority only.

## REFRESH FIRST

Before using any historical SHA or executing any transition, fresh-fetch:

- `GBOGEB/cryoplant-project main`
- QPS issues #923, #1258, #1266, #1357
- QPS PR #1450 and #1456 history
- `GBOGEB/pipeline-automation-hub master`
- MissionControl PR #200, #202 and #203 history
- current workflow evidence relevant to the child runtime gate.

Historical SHAs below are anchors, not instructions to reset branches.

## READ NEXT

1. `mission-control/qps-triage-ultra/leg5/QPS_LEG5_W249_CURRENT_v1.yaml`
2. `mission-control/qps-triage-ultra/leg5/QPS_LEG5_W249_POSTMERGE_RECONCILIATION_v3.yaml`
3. `mission-control/qps-triage-ultra/leg5/SC_2026-09-18_W249_LEG5_POSTMERGE_RECONCILIATION_v3.md`
4. QPS `handover/session/SC_2026-09-18_W249_LEG5_3PSTAR_MIP_LOSSLESS_HANDOVER_v2.md`
5. QPS `handover/session/RESTART_DROPIN_2026-09-18_W249_LEG5_v2.md`

## STATE TO EXPECT UNLESS LIVE AUTHORITY HAS ADVANCED

- LEG5 process: `CONTROL_5_OF_5_REAL`
- downstream routes: `7_OF_9_CLOSED`
- #1266: open; static control integrated; runtime proof withheld
- #1357: open; governed HOLD control integrated; runtime proof withheld
- #923: open private-QPS runtime gate
- authority transfer: false
- engineering / negotiation / release / runtime-GOLD credit delta: 0

Parent/control chain:
- QPS #1450 merge `83d4d5eb8c920672f6c550ede20ce390e528bf27`
- QPS #1456 merge `bfa80d4fa9756f03dd4aaa4c6dedff92b53760d6`
- MissionControl #200 merge `073db34f68ff6a7763ac334371e3d67f7f9c3567`
- MissionControl #202 final head `ed334e916fd7d910465264895eb7c97d3909db67` -> run `35339035224` / job `105580477742` PASS real steps
- MissionControl #203 final head `43f37af2b2cc3403eefd0129042d077d5aa5d72a` -> run `35339059967` / job `105580551843` PASS real steps

The v2 receipts remain immutable snapshots; v3 supplies the later final-head proof facts.

## EXACT NEXT PREDICATE

Require a current private-QPS execution satisfying:

`runner_id != 0 && steps > 0 && validator_runner_selector_compatible`

The governed runner selector is `CRYO_RECEIPT_RUNNER`.

If this predicate is false:
- stop runtime progression;
- do not blind-rerun;
- do not edit either LEG5 validator;
- do not close #1266 or #1357;
- do not publish 8/9 or 9/9;
- do not close #1258.

If true:

1. execute current-main #1266 validator unchanged;
2. bind exact SHA/run/job/result;
3. PASS -> close #1266 and publish 8/9;
4. execute current-main #1357 validator unchanged;
5. bind exact SHA/run/job/result;
6. PASS -> close #1357 as governed non-compensating HOLD and publish 9/9;
7. verify zero undeclared LEG5 owner routes;
8. verify zero authority promotions;
9. evaluate #1258 closure.

MissionControl parent proof never compensates private QPS runtime.
