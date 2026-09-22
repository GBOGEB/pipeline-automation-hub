# LOSSLESS HANDOVER — DOCX style convergence — 2026-09-22

## Exact starting line

START HERE: Refresh `GBOGEB/DOCX_RTM_Automation` main. The style convergence PR `#78` merged as `429be3f276fa6d83e135a2251d793f60bffeae45`, but merge is **not proof**. Consume the exact-main push runs `35734733309` (render) and `35734733288` (Python) and require executed steps before changing any code or style.

## Authority

Primary implementation:
`GBOGEB/DOCX_RTM_Automation`

Consumer/semantic producer:
`GBOGEB/document-organization-system`

MissionControl:
`GBOGEB/pipeline-automation-hub`

Authority transfer: false  
Formal credit delta: 0

## Frozen approved baseline

The user explicitly approved the corrected pre-style DOCX/PDF baseline.

- DOCX SHA-256: `e936ffcb89eb7da13b8be8d447c8453b5b4499a4907390816846f5c8ec94a6b9`
- PDF SHA-256: `654e74630861b5b398ab577d55da5f692bf4549b0af480498822428109353b02`

It remains the immutable visual-regression baseline. JSON remains semantic SSOT.

## Current style candidate

`QPS_TECH_GRAPHITE_TEAL_COPPER_V1`

Intent:
- graphite body;
- deep-teal hierarchy;
- copper special-number / requirement-ID accents;
- granular font names, sizes, colors, captions, metadata, numbering, spacing, tables and callouts.

The style MIP previously closed the technical evidence gap:
- deterministic render-host font resolution;
- visible QA specimen for captions/tables/callouts;
- font fallback is explicit, not hidden;
- semantic source/projection invariance PASS;
- canonical DOCX/PDF/PNG render PASS;
- independent visual QA PASS.

Bound prior proof:
- DOCX feature PR `#74` -> `fbb931d28b551f33f6988882c9a983dc69dcde42`
- DOCX control PR `#75` -> `f7620c308be6fb4288b19f6dcd59e2a27df57d6a`
- render `35730488674` / `106754547718`
- artifact digest `sha256:f791e91b39604f5761e316ced3ef0c4cda6fcb39ef10c71aa3edd92d74516b00`
- producer receipt `document-organization-system#73` -> `3c57b9ed674f50af7650ba9aa306d6b182caee28`

## Why one more convergence pulse was justified

The prior style-control starting point was `d295d8af...`. Fresh census found current main at `6c6d40e...`, 18 commits later. The intervening delta touched the render workflow and data-rich test surface.

Therefore the first-red was not a new style defect. It was:

`CURRENT_MAIN_STYLE_PROOF_FRESHNESS`

No style or semantic change was made.

## 3P* + MIP result

- 3PR Refresh: PASS
- 3PR Probe: PASS
- 3PR Rank: PASS
- MIP Modernize: NO BEHAVIOR CHANGE REQUIRED
- MIP Innovate: NO NEW STYLE TOKEN REQUIRED
- MIP Perpetuate: exact-main re-proof requested
- 3PC Prepare: PASS
- 3PC Prove: HOLD — runner admission
- 3PC Commit: PR merged, **not yet promoted as proof**

Convergence lineage:
- source issue `DOCX_RTM_Automation#77`
- convergence PR `#78`
- merge `429be3f276fa6d83e135a2251d793f60bffeae45`
- post-merge proof-hold issue `#79`

## CI state at handover

PR head attempt:
- render `35734650599` / `106768670365` — queued, steps=null
- Python `35734650610` / `106768670682` — queued, steps=null

Control-only retry:
- render `35734720600` / `106768908429` — queued, steps=null
- Python `35734720574` / `106768909951` — queued, steps=null

Exact merged-main push:
- render `35734733309` / `106768951742` — queued, steps=null
- Python `35734733288` / `106768952582` — queued, steps=null

Classification:
`INFRASTRUCTURE_PREEXECUTION_RUNNER_ADMISSION`

No repair is justified from any of those zero-step states.

## Re-entry decision

If exact-main push proof becomes green:
1. require steps > 0;
2. require Python CI PASS;
3. require data-rich render PASS;
4. require semantic invariance PASS;
5. require pagination/style/specimen/font-resolution gates PASS;
6. close `CURRENT_MAIN_STYLE_PROOF_FRESHNESS`;
7. close `DOCX_RTM_Automation#79`;
8. bind receipt upstream;
9. return the only style first-red to `USER_STYLE_REVIEW`.

If an executed step turns red:
repair only that exact first-red.

If still zero-step:
hold. Do not mutate the candidate.

## Human gate after machine convergence

Once current-main proof is green, the next gate is intentionally human:

`USER_STYLE_REVIEW`

The assistant may report visual QA but must not convert it into user style preference. The user must explicitly approve, reject or request changes to `QPS_TECH_GRAPHITE_TEAL_COPPER_V1` before it can replace the accepted baseline.

## Do not do

- do not infer style approval from the earlier DOCX/PDF baseline approval;
- do not change semantic JSON to solve a styling issue;
- do not commit font files;
- do not treat fallback fonts as user preference;
- do not create another repair PR from queued/steps=null evidence;
- do not replace the approved baseline without explicit user style approval.
