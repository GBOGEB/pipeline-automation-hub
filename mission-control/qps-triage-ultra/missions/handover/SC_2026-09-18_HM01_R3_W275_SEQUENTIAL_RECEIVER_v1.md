# HM-01 R3 / W275 — Sequential 3P* → MIP Receiver Handover v1

## Purpose

This is a MissionControl receiver for the newer QPS W275 repository-side sequence. It does not replace QPS source/product/acceptance authority and it deliberately does not rewrite the protected W275 federation-v4 surface used by existing DMAIC controls.

## Exact child sequence received

The repository-authoritative sequence is:

`3PR Refresh/Probe/Rank -> MIP Modernize -> MIP Innovate -> MIP Perpetuate`

Bound QPS merges:

- 3P* / 3PR: QPS #1489 -> `bb38faab791388498331ac4fee8df51242122244`
- MIP Modernize: QPS #1491 -> `5f325217c6ff5381e77be36a7aae5203c26e7546`
- MIP Innovate: QPS #1492 -> `43e23f40976279088018fcf6365be99e9888526c`
- fail-closed bundle ingress hardening: QPS #1488 -> `5e9894ce6b0eddc3506b23c7d042b998e62dc77b`
- MIP Perpetuate: QPS #1495 -> `7af4d140c38444c2b467da7144eabcfecb2598ae`

The duplicate QPS #1496 was closed unmerged as superseded provenance and grants no competing state.

## What was materially burned

### 3P* / 3PR

Fresh probing identified two separate facts:

1. two bounded physical-return discovery attempts found no qualifying successor bundle;
2. before MIP, the documented QPS-local command pointed to an operator that existed only in GEMINI.

The second fact was the nearer executable defect and was ranked ahead of physical return.

### MIP Modernize

The governed Windows producer is now physically present in the QPS repository:

`scripts/build_qps_r3_successor_handoff.ps1`

### MIP Innovate

The producer is self-locating from the QPS clone. The bounded command is now:

`powershell -ExecutionPolicy Bypass -File .\scripts\build_qps_r3_successor_handoff.ps1`

It preserves the established fail-closed constraints: no checkout/reset/clean, dirty worktree allowed, HEAD immobility, dual object proof, exact bundle advertised head, bundle verification, SHA-256 sidecar and machine receipt.

QPS #1488 additionally provides fail-closed admission from the returned bundle triplet into the already-proven capsule-v2 consumer path.

### MIP Perpetuate

QPS #1495 published the current v5 control/restart surfaces. MissionControl receives that result here without promoting or rewriting protected historical proofs.

## Current hard boundary

The single W275 physical first-red is:

`PHYSICAL_SUCCESSOR_GIT_BUNDLE_RETURN_1248290C`

Required return from the authentic Windows QPS clone:

- `QPS_R3_1248290c.bundle`
- `QPS_R3_1248290c.bundle.sha256`
- `QPS_R3_1248290c.bundle.receipt.json`

The authorized discovery retry budget of two attempts is already exhausted and both attempts returned no qualifying payload. Do not perform another blind discovery cycle without a changed owner/source signal.

## After return

Use the merged QPS fail-closed path:

`bundle triplet -> SHA/receipt/bundle admission -> capsule-v2 -> exact detached successor worktree -> five-product regeneration -> structural QA -> projection-aware parity -> render evidence -> hash-bound HUMAN visual inspection -> successor acceptance`.

Only `PASS_R3_RELEASE_PRODUCTION_DOV` releases R4.

## Current method state

- 3P* repository-side slice: PASS / complete
- MIP Modernize: PASS
- MIP Innovate: PASS
- MIP Perpetuate: PASS
- 3PC Prepare: PASS
- 3PC Prove: HOLD_WAIT_PHYSICAL_SUCCESSOR_GIT_BUNDLE
- 3PC Commit: HOLD_WAIT_PROVE
- 3P3: NOT AUTHORIZED
- R4: BLOCKED_NOT_NEXT

## Non-compensation

QPS #923 remains `RED_OWNER_ACTION`.

`GT_BDQ_0=RED_BLOCKED_ON_923_INFRA_PREEXECUTION`.

Runtime GOLD remains WITHHELD. Canonical GT credit remains NONE. QPS retains engineering/source/product/acceptance authority. Formal, engineering and negotiation credit deltas remain zero; `authority_transfer=false`.
