# W380 Process family: lane/stage matrix, SIPOC, DAG and SPINE

**Governance:** projection only, no independent worker, metric owner, maturity probe scorer, ACK broker or publisher. Inputs and stage-contracts are from canonical W379 lane_lifecycle.py and JADE mission-control/jade_temple/devops/lifecycle.py.

## Matrix / source identity
- 7 lanes A-G × 10 stages S0-S9 = 70 stable lane.stage IDs.
- 63 within-lane stage edges, 13 proposed strictly forward cross-lane handoffs, 1 G.S9 -> A.S0 NEXT_PULSE feedback edge.
- The source stage DAG remains acyclic when NEXT_PULSE feedback is excluded.
- Stage scores are **not derived from lane observations**: L0-L5 belong to repo census. An unverified observation is no more than OBSERVED_PASS_UNVERIFIED; no independent real maturity credit.
- Real queue wait, capacity, accepted closures and ACK readback remain unknown.

## Source ownership and SIPOC
Suppliers: metric atlas census, GOGREEN/EVERRED roots, issue_rank, JADE DAG, cryoplant-project engineering, W377/PUB-R07, assurance owners.
Inputs: immutable packets with commit SHA, blob OID, W379 source-bound observations.
Process: each lane follows S0 PLAN through S9 CONTROL; cross-lane process handoffs are declared, not dispatch receipts.
Outputs: SHA256-bound graph JSON, three Mermaid projections, and a fully self-contained HTML matrix.
Customers: Mission Control, reviewer and source-owning repositories.

INTERFACES are proposal relationships, not accepted authority transfer. No direct source or controlled binary paths are published.

## Interactive HTML matrix
Locally generated 70-cell grid, with lane/stage selectors, per-cell evidence and full SIPOC detail on click. All repository-provided content is bound by DOM textContent, never innerHTML. Script terminators are encoded before embedding JSON. Works without external libraries, network or cookies. Native browser/e2e QA remains a separate gate.

## Native test gates
Python 3.11/3.12 exact-head, positive/negative tests, optimized -O, branch-aware >=85% new-module coverage, deterministic SHA256 manifest. No owner handoff or CI badge can be treated as full admission.

Run with PYTHONPATH=tools/metric-atlas:
python -m unittest discover -s tools/metric-atlas/tests -p test_lane_process_graph.py -v
python -O -m unittest discover -s tools/metric-atlas/tests -p test_lane_process_graph.py -v
python -m metric_atlas.lane_process_graph --snapshot tools/metric-atlas/tests/w379_empty_snapshot.json --out /tmp/w380-graph

Dependencies: #993 integration → #999 ACK causality repair → this disjoint graph PR. The W380 P2 finite train is a separate PR; no merge until predecessor proof, exact-head independent review and FPC process/ruleset admission.
