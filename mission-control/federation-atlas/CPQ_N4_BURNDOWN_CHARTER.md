# CODE PURPLE — N+4 14-item CPQ charter

This is a review-only navigation view. Canonical source: `CODE_PURPLE_BD_QUEUE_v1.json`; no second root ledger. All five DONE are repair/proof milestones, not CONTROL or independent causal-root closures.

## DONE candidates substantiated by prior native receipts

- CPQ-004 — CODE PURPLE gate_ledger PASS/FAIL/UNKNOWN, native exact-run 38932665934 parity tests PASS. No Top14 admission inferred.
- CPQ-007 — Graph binding RECEIPT vs DECLARED and dashed-edge negative tests in test_atlas.py; native 38932665934 PASS. QPS receipt added, MC->QPS dispatch remains DECLARED.
- CPQ-012 — document-organization-system/main 6b4529cc746bb1cbdd938d564cc7b01ff719e0c2 run 38218661281 job 114709316495 SUCCESS with seven successful steps. Repeat CONTROL pending.
- CPQ-014 — QPS main 577353ed5f9cb1d3c19cb2a0967ea13e14fc683e, native run 38930253268 job 117072106782 SUCCESS with 7 steps. Read-only QPS->JOIN receipt; separate qps-canonicalization 38926132761 FAIL.
- CPQ-017 — Native Method Atlas 38932665934 passed source metrics and hash-chain test; new ordinal series entry appended, formal CONTROL distinct-head repeat pending.

## Nine unresolved source-owned work orders

- CPQ-003 [ACTIVE/LINKED] v0.1 atlas QA claims had no SHA, run or receipt. Owner: Hub Atlas #520. Next: Native browser+SVG seeded-failure CI. DoV: Atlas source, unit tests and a browser-level (Playwright or equivalent) render check run in hub CI on the exact head.
- CPQ-005 [ACTIVE/IN_PR] No as-of date or evidence age on the atlas. Owner: Hub Atlas #520. Next: Visible age+TTL stale flag with negative test. DoV: Each source shows its as-of date and age; stale sources are flagged.
- CPQ-009 [TODO/HOLD] Kubernetes and TCP telemetry have no data source. Owner: Runner telemetry provider #520. Next: 3 comparable observations/2 missions from named runner. DoV: Re-entry predicate met: >=3 MEASURED comparable rows across >=2 missions (FLEET_TELEMETRY_SCHEMA pca_gate) and a named runner telemetry source.
- CPQ-010 [TODO/READY] ABACUS-I2 recorded as PENDING although its exact-head proof and G75 recurrence exist. Owner: ABACUS/DMAIC #419. Next: Bind I2 exact run/job and CONTROL handoff. DoV: GM_DMAIC_EVOLUTION contract binds I2 D1 and D2 to exact-head job ids and moves I2 to completed_iterations with CONTROL lineage.
- CPQ-011 [TODO/READY] Second fresh Top7 recensus pulse is not recorded. Owner: Top7 current-source #419. Next: Qualify paired Top7 run class/coverage then evaluate predicate. DoV: Pulse 2 recorded in TOP7_CENSUS_PULSES_v1.json with exact head SHAs and run ids for all 7 repos, and top7_proof_debt_two_pulse_nonincreasing set from pulse 1 vs pulse 2.
- CPQ-013 [TODO/BLOCKED] max_unchanged_root_auto_repeat_after_control is null, which blocks both promotion gates. Owner: DMAIC #428 after CPQ-010. Next: After 010, fix same-source root-repeat denominator. DoV: The metric has a written denominator (controlled roots x subsequent exact-head runs of the owning job) and a value bound to run ids.
- CPQ-015 [TODO/RETURN_OWNER] No cross-repo dispatch and return path exists; 'dispatch' edges are declarations. Owner: CODEX #977 and Hub #63. Next: Owner-approved lease/idempotency/REX gateway, default DENY. DoV: One bounded satellite task is dispatched from the hub and returns exact source, head and output digests (MIP/FEDERATION_ACTIVITY.yaml next_victory).
- CPQ-016 [UNKNOWN_NEEDS_READER/RETURN_OWNER] PRs merged while First-Pass Closure was red or still running (REX-CM-005 recurrence). Owner: Hub admin #336. Next: Owner install required status; RED-block/GREEN-admit canary. DoV: Owner/admin ruleset makes first-pass-closure a required status (#336) and a red check provably blocks merge.
- CPQ-018 [UNKNOWN_NEEDS_READER/LINKED] LM-10 MIP roundtrip gg_MATH -> Mission Control -> ABACUS/QPS has no state newer than 2026-09-21. Owner: gg_MATH #27 + ABACUS #1164. Next: Verify ABACUS third-hop pulse3, then repeat distinct-source. DoV: Pulse 3 consumer (ABACUS #1164) state read back and recorded; 3P* pulse states bound to run ids.

## SIPOC / DAG / concurrency

Input: canonical 18-item queue + current exact-head runs. Process: first-red attributable recensus; root owner; one file-lease writer; native proof; exact-source replay. Output: receipt and consistent iteration series. Control: no DOV inflation, A10/security separate.

P0 external non-compensating: CPQ-016 owner/admin. Parallel disjoint: CPQ-003, CPQ-005, CPQ-010, CPQ-011. CPQ-013 waits for CPQ-010. CPQ-015 requires authorized credentials, and CPQ-009/018 require further native evidence. Top7 pulse2 is source-bound but **not matched/comparable**; do not upgrade Top14. No new agent dispatch.

`P0_ADMISSION=HOLD` · `formal_credit_delta=0` · `authority_transfer=false` · `root_closures=UNKNOWN`.
