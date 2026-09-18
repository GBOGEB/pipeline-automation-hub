# Historian BD/REX — 3P* + MIP Lossless Drop-in v1.1

Continue from repository authority only. Do not reconstruct burned predicates from chat.

## Refresh first

1. `GBOGEB/pipeline-automation-hub master`
2. `GBOGEB/ABACUS main`
3. `GBOGEB/ABACUS#1278`
4. `GBOGEB/cryoplant-project#923`

## Read next, in order

1. `mission-control/historian/handover/CURRENT.json`
2. `mission-control/historian/BD_REX_CONTROL_REGISTER_v2.json`
3. `mission-control/historian/SPECIALIST_REPAIR_CREW_REGISTRY_v2.json`
4. `mission-control/historian/handover/SC_2026-09-18_BD_REX_3P_MIP_v1.1.json`
5. `mission-control/historian/handover/PUBLICATION_CLOSURE_20260918_v1.1.json`
6. this drop-in

## Burned / do not repeat

- REX-CM-003 = CONTROL.
- REX-CM-004 = CONTROL.
- HIST-BD-018 content repair = DONE.
- ABACUS governance run `35352120094` = PASS >0 steps, workflow_count=142, policy_outcome=success, inventory_outcome=success.
- MissionControl PR #253 exact-head checks = 6/6 PASS on `45cd8dbc22b8e29f162113858ffca15f553312f4`.
- MissionControl PR #253 publication merge = `9e914d18850ed9154b6da7dbf7f2b4dfc5bf79a1`.
- PR #1277, #1280 and #253 premature/queued/red merge observations are retained negative evidence.
- cryoplant-project#923 remains open and non-compensating.

## Active control hold

`REX-CM-005 = ACTIVE_PREVENTION_WITHHELD`

Detection and repair are proven. Merge prevention is not.

CONTROL requires:

1. bind merge admission/ruleset to CI Workflow Governance or equivalent required check;
2. deliberately introduce an unclassified workflow change and prove it is non-mergeable while red;
3. repair/classify on a later distinct source and prove it is green and mergeable;
4. retain both receipts.

## Other open BD

- `HIST-BD-001`: requested-vs-observed REX semantics.
- `HIST-BD-009`: canonical negative/rejected runtime evidence retention.

## Next repo expansion

After the bounded control work, continue Historian deep-dive at `GBOGEB/Q_engineering_tools`.

No authority transfer. Formal credit delta = 0. No chat-only TODOs or decisions.
