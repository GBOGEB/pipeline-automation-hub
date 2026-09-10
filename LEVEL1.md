# GBOGEB Level 1 — Pipeline Automation Hub

Status: `PC3_LEVEL1_CANDIDATE`
Target: `LEVEL_1_0`
Role: `FEDERATION_ROUTING_ORCHESTRATION_HUB`

## Index

Human Level-1 navigator. Machine state: `level1/ssot.json`; gate manifest: `level1/manifest.json`; reusable skill: `skill/`; executable Level-1 kernel: `level1/runtime.py`.

Existing capability is reused: the repo already contains a Next.js application/API surface and Python document-processing scripts, including the documented `scripts/run_processing.py` path. Level-1 turns the hub into the common dispatcher for worker receipts while keeping evidence/engineering authority outside the hub.

MIP cycles: PC1 census/control, PC2 executable skill/runtime/agents, PC3 DMAIC + measured-only PCA/BT + CI orchestration proof. Structural target on this branch is 12/12 = 1.0000; observed Level-1.0 requires executed green PC3 proof.

## AOD

AOD = **Architecture–Orchestration–Decision**.

### Architecture

Owns routing, dispatch, workflow coordination, document-processing handoffs and federation transport between recent-active workers and the governed KEB/DOW/child chain.

### Orchestration

Primary federation sequence: `worker -> pipeline hub -> CODEX/KEB -> ABACUS/DOW -> cryoplant child`. The hub may fan out execution requests and correlate exact source/head/output digests.

### Decision authority

May decide routing, dispatch readiness and receipt completeness. Must not transfer or invent engineering authority; it cannot turn a worker result into QPS compliance/evidence acceptance. Authority transfer remains disabled unless a separate governed contract explicitly changes it.

## DMAIC

- **Define:** bind the routing topology, worker roles, native processing anchors, authority boundary and fixed 12-gate denominator.
- **Measure:** execute the Level-1 census at exact head and record gate state, native-runtime visibility and routing targets.
- **Analyze:** use MIP gap output first; measured PCA and explicit BT comparisons may prioritize dispatch/repair work but never assign acceptance authority.
- **Improve:** repair the smallest executable routing/runtime gap, reuse the native Next.js/Python processing paths, and add only traceable authority-safe edges.
- **Control:** exact-head CI compiles and exercises census/MIP/orchestration, proves no-input analytics DEFER, runs self-test and uploads receipts. The first red invariant becomes the next recursive repair.

MIP = **Modernize (repair/reuse), Innovate (new useful nodes/edges/functions), Perpetuate (repeat exact-SHA execution and receipts).**

## PCA

PCA is a measured multivariate dispatch/priority diagnostic. `python level1/runtime.py pca --input rows.json` requires real numeric observations; inadequate or zero-variance inputs DEFER. Synthetic self-test rows only prove the engine. PCA may guide worker allocation or repair focus; it cannot promote a worker receipt to engineering/evidence acceptance.

## BT

Bradley–Terry is an observed pairwise priority diagnostic using explicit `[winner, loser]` comparisons. No comparisons DEFER. BT may rank routing, repair or worker alternatives; it cannot replace source evidence, KEB challenge, DOW roll-up or child disposition.

## Level-1.0 DoV

`LEVEL_1_0` requires all 12 gates true and a green exact-head `Level 1 MIP` workflow. Structure without executed CI remains candidate. `authority_transfer=false` remains mandatory, and Level-1 bootstrap creates no QPS engineering/compliance/negotiation credit.
