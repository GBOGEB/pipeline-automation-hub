# Historian BD/REX 3P* + MIP — Lossless Drop-in

Continue from repository authority only. Do not reconstruct this lane from chat memory.

## Refresh first

1. `GBOGEB/pipeline-automation-hub master`
2. `GBOGEB/ABACUS main`
3. `GBOGEB/ABACUS#1271`
4. `GBOGEB/ABACUS#1278`
5. `GBOGEB/cryoplant-project#923`

## Read next, in order

1. `mission-control/historian/BD_REX_CONTROL_REGISTER_v2.json`
2. `mission-control/historian/SPECIALIST_REPAIR_CREW_REGISTRY_v2.json`
3. `mission-control/historian/handover/SC_2026-09-18_BD_REX_3P_MIP_v1.json`
4. this drop-in

## Burned predicates

- REX-CM-003 is CONTROL. Do not repeat immutable-pin first proof.
- REX-CM-004 is CONTROL. Do not repeat exact-PR-head first proof.
- HIST-BD-018 is one durable root; the 2026-09-18 four-workflow escape is recurrence episode 2, not a new root.
- ABACUS content is repaired to policy schema 1.0.4 with 142/142 derived inventory and policy digest `6a975e6a9a4aefbe08111375be872915efb9dc0c6969ea51311ef20370be5d19`.
- Detection is not prevention. REX-CM-005 remains ACTIVE_PREVENTION_WITHHELD.
- cryoplant-project#923 remains non-compensating.

## Exact repeat evidence

- ABACUS PR #1271 repeat head: `a4d3c196aa4d6617acd810734ce525df23ca3e17`
- W74 run: `35349719151` — exact-head receipt PASS.
- W169 run: `35349719044` — receipt `source_sha` equals repeat head; rollout and health PASS; restart_count 0.
- CI governance run `35349719045`, validator step: immutable pins/exact-source controls PASS.

## BD-018 / REX-CM-005 evidence

- PR #1277 auto-merged before governance proof.
- PR #1280 auto-merged while governance was red.
- ABACUS `main` was observed unprotected.
- Control issue: ABACUS #1278.
- Final policy commit: `c17124160b82e0b3ff94eebb98608118296f45cf`.
- Policy-digest/report commit: `82f6edaea6a60f948dc51b6038fbad944977d676`.
- Hosted run `35351825106`: policy PASS; inventory failed on one generated repeated-command line.
- Exact generated-delta commit: `621c9ca2ab6848d524f3c8ddb831524e756c159f`.
- Final governance re-proof at handover: `35352120094`, QUEUED.

## Next executable transition

1. Re-read run `35352120094`.
2. If it executes >0 steps and PASSes, mark HIST-BD-018 repair DONE, but keep REX-CM-005 withheld.
3. Bind merge admission to CI Workflow Governance using a branch rule/ruleset or equivalent fail-closed admission.
4. Prove a deliberately unclassified workflow change is non-mergeable.
5. Prove a later classified workflow change is green and mergeable.
6. Then return Doctor.Contracts from BD-018 prevention duty as appropriate and continue HIST-BD-001 / HIST-BD-009.
7. Continue next deep-dive at `GBOGEB/Q_engineering_tools`.

No authority transfer. Formal credit delta = 0.
