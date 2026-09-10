# GBOGEB Level 1 — Pipeline Automation Hub

Status: `PC1_CONTROL_PLANE`
Target: `LEVEL_1_0`
Role: `FEDERATION_ROUTING_ORCHESTRATION_HUB`

## Index

Human Level-1 navigator. Machine state: `level1/ssot.json`; gate manifest: `level1/manifest.json`; reusable skill: `skill/`; executable Level-1 kernel arrives in PC2.

Existing capability is reused: the repo already contains a Next.js application/API surface and Python document-processing scripts, including the documented `scripts/run_processing.py` path. Level-1 turns the hub into the common dispatcher for worker receipts while keeping evidence/engineering authority outside the hub.

MIP cycles: PC1 census/control, PC2 executable skill/runtime/agents, PC3 DMAIC + measured-only PCA/BT + CI orchestration proof. Structural targets: 0.3333 -> 0.7500 -> 1.0000; observed Level-1.0 requires executed green PC3 proof.

## AOD

AOD = **Architecture–Orchestration–Decision**.

### Architecture

Owns routing, dispatch, workflow coordination, document-processing handoffs and federation transport between recent-active workers and the governed KEB/DOW/child chain.

### Orchestration

Primary federation sequence: `worker -> pipeline hub -> CODEX/KEB -> ABACUS/DOW -> cryoplant child`. The hub may fan out execution requests and correlate exact source/head/output digests.

### Decision authority

May decide routing, dispatch readiness and receipt completeness. Must not transfer or invent engineering authority; it cannot turn a worker result into QPS compliance/evidence acceptance. Authority transfer remains disabled unless a separate governed contract explicitly changes it.
