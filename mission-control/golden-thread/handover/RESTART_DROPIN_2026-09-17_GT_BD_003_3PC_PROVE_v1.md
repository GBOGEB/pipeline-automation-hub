# RESTART DROP-IN — Golden Thread GT-BD-003 / 3PC Prove

Copy/paste the block below into a fresh session.

---

Continue the governed Golden Thread architecture mission from repository authority. Do not rely on chat memory and do not repeat already-burned predicates.

## REFRESH FIRST

Fresh-fetch before any write or current-state claim:

- `GBOGEB/pipeline-automation-hub` `master`
- `GBOGEB/cryoplant-project` `main`
- `GBOGEB/cryoplant-project#1438`
- `GBOGEB/cryoplant-project#923`
- open PRs in `GBOGEB/pipeline-automation-hub`

Then read, in order:

1. `mission-control/golden-thread/handover/SESSION_CLOSE_CURRENT_v1.yaml`
2. `mission-control/golden-thread/handover/SC_2026-09-17_GOLDEN_THREAD_LOSSLESS_HANDOVER_v1.md`
3. `mission-control/golden-thread/GOLDEN_THREAD_FRONTIER_CURRENT_v1.yaml`
4. `mission-control/golden-thread/GOLDEN_THREAD_3PR_MIP_M_20260917_v1.yaml`
5. `mission-control/golden-thread/GT_BD_003_3PC_PREPARE_W250_v1.json`
6. QPS `controls/QPS_GOLDEN_THREAD_CURRENT_v0.1.yaml`
7. QPS PR #1438 child receipt `triage/w250/QPS_W250_GT_BD_003_CHILD_GATE_AUTHORITY_RECEIPT_v1.json`
8. latest QPS #1438 workflow runs/jobs/steps and issue #923 comments.

## LAST PROVEN STATE

MissionControl close anchor:
`94ef9de83a40f114179d128d12d4835279beebab`

Burned/proven architecture sequence:

`GT-BD-006 -> GT-BD-011 Batch 001 -> GT-BD-002 -> 3PR + MIP-M -> GT-BD-003 3PC Prepare`.

Do NOT repeat those merely for ceremony.

Key exact receipts:

- PR #186 second-family importer: head `801e56855e3cb24c286b7c62469d765d4cffe413`; 8/8 hosted PASS; Replay `35174481075` / job `105053043572`; 69 tests PASS; artifact `10478466581`; SHA256 `d7f03b8771a676e6cbafe7bba1d2c9533453b52f15b7124994f27eb94213003d`.
- PR #190 GT-BD-011 Batch 001: head `f989223626599d00cd3fed65a54816f5cbd99d78`; merge `f6a9c67df2e508df85b7c4441f36b2aae50309f8`; Replay `35229457547` / job `105229427346`; 70 tests PASS; artifact `10500357116`; SHA256 `082545f330e1ae754050a03b01b6685225b7f1cb90820529387168064fa76e7e`.
- PR #191 GT-BD-002: head `98c90114dee0abeeb252e319387fb94b97df4bda`; merge `39e64d72c778e0894eba884fc9e349b92ed681e4`; Replay `35229777316` / job `105230529829`; 72 tests PASS; artifact `10500039423`; SHA256 `f18fb71211a7336b8e01016e788e545c165245f219dcd21329d87e344d2a87c6`; zero stale survivors/renditions.
- PR #194 3PR + MIP-M: final head `fae367b78d9727e4b6cbc4aebdda129b17437b21`; merge `3a65e884abe321347bd771b1b094d44e1e08cdd2`; final hosted family 8/8 PASS; Replay `35242622674` / job `105274644838`; 75 tests PASS; artifact `10505394651`; SHA256 `7538d471c9b87bceb346b15be035df4723df816ac854f18b70304da6880baba9`.
- PR #197 GT-BD-003 3PC Prepare: head `8a3addb2c6e305b7f586bd664269483810b54876`; merge `94ef9de83a40f114179d128d12d4835279beebab`; dedicated Prepare run `35244200714` / job `105280065735`; PASS; artifact `10507125081`; SHA256 `02aabfd3ccc9c22a1fc43ef79151ff6bc8ac8ddffdda66f86830849ca656156a`.

## CURRENT FIRST RED

GT-BD-003 is ACTIVE.

3PC state:

- Prepare = PASS
- Prove = WITHHELD_CHILD_ZERO_STEP
- Commit/HOLD = HOLD

Real child authority target:

- repo `GBOGEB/cryoplant-project`
- PR #1438
- exact prepared child head `0c88a8efe09ccf7cb0b11ecc19632a1191621524`
- source gate `controls/W93_R5_PVPS_TERMINAL_CHILD_GATE_v0.1.yaml`
- source gate blob `d3584cd900c583d918683eb2b02c94a08c66e84c`
- child disposition `DEFER`
- reset authority `QPS_CHILD_ONLY`

Observed child proof attempt:

- workflow `QPS W250 GT-BD-003 Child Gate Authority`
- run `35244036243`
- job `105279499163`
- steps `null`
- classification `INFRA_PREEXECUTION_ZERO_STEP`

This is not application failure evidence.

## EXECUTE NEXT

Only if QPS PR #1438 exact head or a governed successor obtains a real hosted run with `steps > 0`:

1. verify the child-owned authority validator actually executes and passes;
2. bind exact repo + PR + head + run + job + artifact + digest in one receipt;
3. execute MissionControl GT-BD-003 **3PC Prove** against that exact child receipt;
4. prove all of the following:
   - child inhibit latches;
   - parent permissives cannot compensate it;
   - unauthorized reset rejects;
   - authorized reset without reason rejects;
   - authorized reasoned reset clears the latch and all permissives;
   - repropagation with current source incompleteness reasserts the inhibit;
   - final child disposition remains `DEFER` unless QPS child authority independently changes it;
   - QPS credit delta remains zero;
   - authority transfer remains false;
5. if all Prove predicates PASS, commit GT-BD-003 architecture evidence and only then advance the architecture queue;
6. if any predicate fails, HOLD at the exact first red and repair only that proven defect.

If the child remains zero-step, STOP. Do not alter application/gate logic. Continue owner-action recovery under QPS issue #923.

## QPS NON-COMPENSATING BOUNDARY

QPS `GT_BDQ_0` remains withheld in `controls/QPS_GOLDEN_THREAD_CURRENT_v0.1.yaml`.

QPS issue #923 is still the global runtime GOLD blocker. A public MissionControl/CODEX/ABACUS PASS, merge, static receipt, or child contract existence does not advance QPS `GT_BDQ_0`.

QPS `GT_BDQ_1` may start only after QPS's own exact-head hosted Golden Thread proof genuinely executes (>0 steps), passes deterministic assertions, and binds the proof artifact identity/digest.

## CONCURRENT LANES

Keep separate:

- MissionControl #195: GM-I-C / IC3 local specialization; no compensation for GT-BD-003 or QPS.
- MissionControl #196: temporal-policy 3PR + MIP CONTROL surface; orthogonal.
- QPS HM-01/R3 local controls; no compensation for issue #923 / GT_BDQ_0.

## METHOD / STOP RULE

Canonical selector remains:

`3PR -> MIP only on measured gap -> 3PC for bounded transaction -> one 3P3 only if reusable propagation proof remains missing -> STOP`.

Do not rerun 3PR unless material repo/evidence state changed. GT-BD-003 is already in 3PC; continue at Prove, not back at Prepare, unless the child authority identity materially changes.

Preserve:
`PARENT_PASS_NE_CHILD_ACCEPT`, `ZERO_STEP_NE_APPLICATION_FAIL`, `RESET_NE_ENGINEERING_ACCEPT`, `MISSIONCONTROL_PASS_NE_QPS_GT_BDQ_PASS`, `AUTHORITY_TRANSFER_FALSE`, `UNKNOWN_NE_ZERO`.

---

Expected initial restart disposition if nothing changed:

`GT-BD-003 PREPARE=PASS / PROVE=WITHHELD / COMMIT=HOLD; wait for >0-step QPS child execution under #923 recovery.`
