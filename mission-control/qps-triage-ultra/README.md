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

## Coverage invariant
Every active frontier must close a wave with either the required evidence receipt or an explicit DEFER/PARK/PRUNE disposition. Fleet mean coverage never substitutes for the minimum-frontier coverage floor.

## Reuse
The existing `level1/runtime.py` remains the executable census/MIP/PCA/BT/orchestration engine. ULTRA extends it with fleet state; it does not duplicate healthy Level-1 logic.
