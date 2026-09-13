# QPS TRIAGE ULTRA — Mission Control

Status: `W0_BOOTSTRAP`

QPS TRIAGE ULTRA is the persistent HOME mission-control brain for the frontier program. It duplicates HOME competencies, not every transient worker.

Operational primitive:
`Mission -> Wave -> Pulse -> Receipt -> Reallocate -> Recurse`

Authority boundary: this node may plan, route, schedule, measure, compare, correlate and recommend. It must not promote engineering/compliance truth or bypass KEB/DOW/child authority. `authority_transfer=false` remains mandatory.

## Permanent competency seats
1. U01 Mission Commander / Governor
2. U02 Chief Architect / Architecture Hat
3. U03 Project Manager / portfolio sequencing
4. U04 Fleet Orchestrator / scheduler
5. U05 Analyst / DMAIC + measured PCA + observed BT
6. U06 QA / Signalman / provenance
7. U07 Cartographer / Oculars / node-edge-temporal graph
8. U08 REX / doctrine / KEB integration

The Architecture Hat owns the coherent model of people, functions, roles, capabilities, interactions, nodes, edges, atoms, graphs, authority and temporal lineage.

## Crew capability system

The canonical candidate crew layer lives under `crew/` and adds:

- `CREW_REGISTRY_v1.json` — permanent seats, observed specialists, partial roles and conceptual crew candidates.
- `COMPETENCY_MATRIX_v1.json` — L0-L6 competency scale, evidence classes and promotion rules.
- `REX_LEARNING_LEDGER_v1.json` — bidirectional mission-to-REX-to-crew learning.
- `ROLE_DEVELOPMENT_POLICY_v1.json` — mission-feedback-driven new-role planning, trial, promotion, merge, prune and return.
- `validate_crew_system.py` — executable structural and authority validation.

Crew competence is evidence-backed state, not a title. Seeded competency vectors are planning priors until replaced by accepted mission/runtime receipts. Conceptual roles cannot hold promotion or CONTROL authority.

The Ambassador is an observed specialist role with a bounded claim/authority-reconciliation function. New roles are admitted only from repeated mission need, REX, resource pressure, authority-independence needs, or stable PCA/BT workload clusters.

## Coverage invariant
Every active frontier must close a wave with either the required evidence receipt or an explicit DEFER/PARK/PRUNE disposition. Fleet mean coverage never substitutes for the minimum-frontier coverage floor.

## Reuse
The existing `level1/runtime.py` remains the executable census/MIP/PCA/BT/orchestration engine. ULTRA extends it with fleet state; it does not duplicate healthy Level-1 logic.
