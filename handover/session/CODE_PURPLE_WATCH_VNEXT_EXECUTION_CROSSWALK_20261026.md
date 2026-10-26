# CODE PURPLE WATCH vNext — execution crosswalk, dependencies and release receipts

**Control identity:** CODE_PURPLE_WATCH_RESTART_20261026_N0 / MIP_WATCH_EVOLUTION_20261026  
**Class:** implementation handoff, not an engineering or merged-main acceptance receipt  
**Source baseline:** historical report cutoff 2026-10-26 00:43 CET; subsequent observations must carry independently refreshed UTC GitHub identities.

This is the bridge between the **lossless N0 historical handover** and the **separate MIP improvement programme**. Keep both originals. In particular, retaining chat history or creating a documentation PR is not the same as implementing the monitor.

## What was preserved, what is being built

- Preservation owner: [N0 handover](LOSSLESS_HANDOVER_CODE_PURPLE_WATCH_N0_20261026.md), [N0 restart seed](RESTART_DROPIN_CODE_PURPLE_WATCH_N0_20261026.md), [MIP work backlog](MIP_WATCH_EVOLUTION_20261026.md), and [N0 source-class ledger](../../mission-control/federation-atlas/watch_n0_session/).
- Canonical ZIP source: Mission Control merged #530; extend \`mission-control/gogreen/verify_native_zip.py\`, never create a second verifier.
- Canonical fresh authenticated breadth: merged #531 and \`code-purple-live-census.yml\`; preserve historical 6/42 separately from qualifying fresh cells, currently not established. No substitute breadth claims.
- Canonical Method Atlas: merged #533 and \`mission-control/federation-atlas/build_atlas.py\`, strictly a **consumer/viewer**.
- Existing append-only SHA256-chained public pulse journal: \`mission-control/gogreen/scale_dock_series.py\`; existing golden-thread checkpoint/replay: \`mission-control/golden-thread/checkpoint_replay.py\`.
- Existing convergence and stable-stop methodology: \`federation/convergence/converge.py\`; existing read-only navigation and tile consumer: \`mission-control/gogreen/launcher/\`.
- Additional bounded implementation: [draft PR #878](https://github.com/GBOGEB/pipeline-automation-hub/pull/878) extends the #530 verifier with JSON-object semantics, contradictory producer-binding rejection and adversarial fixtures. It is **not merged**, no First-Pass admission proof is claimed.

## The fifteen MIP items — current implementation/disposition crosswalk

"EXISTING PARTIAL" means a canonical code path exists, **not** that the MIP definition of done is met. An item does not become DONE until tests, source identity, governance and (where applicable) main readback prove the complete requirement.

| MIP | Priority | Canonical code or planned bounded change | State / missing exit evidence |
|---|---|---|---|
| 01 | P0 | \`gogreen/scale_dock_series.py\` hash-chain; \`golden-thread/checkpoint_replay.py\` | EXISTING PARTIAL: one last-qualified notification cursor, deterministic cross-source replay and durable event identity still unproven |
| 02 | P0 | Source identity consumer contract extending canonical ingestion | OPEN: distinguish PR head, base, checkout, synthetic merge, merged main without silent substitution |
| 03 | P0 | #530 verifier \`gogreen/verify_native_zip.py\`; PR #878 | CANDIDATE: semantic/producer-negative tests committed; exact-head execution, upstream producer provenance and governed admission still required |
| 04 | P0 | Trusted \`scripts/first_pass_closure_gate.py\` and GoGREEN required gate | EXISTING PARTIAL: workflow-success with mandatory failed native receipt must be an explicit veto in the watch consumer |
| 05 | P0 | #530 byte verifier / #531 authenticated breadth / #533 viewer | OWNER MAP PRESERVED; enforce incompatible producer-authority test and source-owned readback |
| 06 | P0 | ChatGPT task scheduler, owner-reviewed responsibility table | OPERATOR HOLD: overlapping tasks require a readback/one-owner decision. Do not silently disable independently owned watches |
| 07 | P1 | Native test/JUnit producer, downstream reconciliation consumer | OPEN: reconcile testcase records, header totals, matrix cases and skips with an eligibility contract |
| 08 | P1 | \`federation-atlas/coverage_integrity.py\` + source-blob cohort registry | EXISTING PARTIAL: matched blobs, tools, selection and opportunities for each claimed delta |
| 09 | P1 | EVERRED \`harvest.py\`, GoGREEN \`scale_dock_series.py\` | EXISTING PARTIAL: occurrence/fingerprint/root independence and independent owner closure in cross-repo reporting |
| 10 | P1 | \`gogreen/success_graph/runner_telemetry.py\` | EXISTING PARTIAL: actual runner utilization/queue/throughput qualified, not inferred |
| 11 | P1 | \`federation/convergence/converge.py\` plateau() | EXISTING PARTIAL: four distinct eligible observations, notify-once cursor and stable-HOLD reactivation |
| 12 | P1 | \`gogreen/launcher\`, Method Atlas, JADE pages | OPEN: a read-only integrated source-bound watch tile/view, browser QA and published route proof |
| 13 | P2 | gg_MATH statistical producer, federation consumer | HOLD: PCA/BT populations and connected comparison qualification not yet sufficient |
| 14 | P2 | Canonical negative-test suites + PR #878 | EXISTING PARTIAL: adversarial/reverse/replay acceptance for each required veto remains to be demonstrated |
| 15 | P2 | \`mission-control/v2/handoff\`, N0 checkpoint and restart seed | EXISTING PARTIAL: governed automatic session-to-repo preservation and independent replay receipt are not installed |

**No item is marked DONE solely by this crosswalk.**

## Three bounded landing lanes (no implicit merge)

1. **Lane A — immutable operational checkpoint**: review #876 for exact source and private-transport classification; retain the N0 history, gap register, restart seed and this implementation crosswalk. Strictly preserve historical claims as reported, never refetch/relabel them as newly native.
2. **Lane B — control-plane contracts**: qualify #878's canonical semantic ZIP verifier; then add one **consumer-only** exact-identity / required-receipt / comparable-population / deduplicated-notification state machine, with negative and out-of-order replay tests. It may **read** the owner journal, but cannot publish competing #530/#531 metrics or overwrite historical events.
3. **Lane C — one navigable view**: extend the existing GoGREEN launcher and Method Atlas navigation to consume frozen owner-owned readback; show last-qualified timestamp, PR/run/job, fresh-versus-historical breadth, first-red/root/occurrence, required vetoes, coverage cohort and dashboard unknowns. Do not create another Pages publisher.

Implement in dependency order: A → B → C; allow parallel source-only hardening after preflight overlap checks, but **no** authority transfer or unreviewed merge.

## Source/privacy guardrail

The federation hub is public. QPS source is **RESTRICTED_OWNER_RETURN**: no QPS private SHA, issue/PR/run/job ID, issue title, bidder source, private defect or derived price may appear in public JSONL, public Pages, PR body or cross-repo test fixtures. For public handover, only a public constant such as \`PRIVATE_AGGREGATE_ONLY\` and an owner-controlled route name are permitted. The existing JADE count-preserving projection does **not** validate arbitrary new watch JSONL; a dedicated allowlist / fail-closed test is required before new public event export.

## Noncompensating gates and release receipt

Do not infer security closure from successful workflow conclusions. No independent approval, no required status, absent receipt, source drift, incomplete run, broken semantic ZIP, owner review absent, or unauthorized QPS original -> HOLD. A candidate's synthetic merge SHA is not its PR head, even if all tests pass.

Required exit proof for every bounded PR: exact base/head; changed paths and compare; native completed job with relevant tests actually executed; required-check and clean independent review readback; negative/false-GREEN proof; archive/member evidence when claimed; no QPS privacy leakage; and post-merge exact-main check **only after** a governed merge. No worker dispatch, token change, settings change, approval, security waiver, auto-merge or watch activation in this plan.

**Invariant until proven otherwise:** MERGE_ADMISSION=HOLD; QPS_OWNER_ACCEPTANCE=WITHHELD; SECURITY_WAIVER=NONE; FORMAL_ENGINEERING_CREDIT_DELTA=0.
