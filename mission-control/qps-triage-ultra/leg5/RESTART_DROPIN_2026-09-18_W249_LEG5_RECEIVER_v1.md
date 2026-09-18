# MissionControl restart drop-in — QPS LEG5 W249 3P* + MIP receiver

Start from repository authority.

Read:
1. `mission-control/qps-triage-ultra/leg5/QPS_LEG5_W249_3PSTAR_MIP_RECEIVER_v1.yaml`
2. `mission-control/qps-triage-ultra/leg5/QPS_LEG5_W249_DEPENDENCY_GRAPH_v1.json`
3. QPS PR #1450 at exact head `2b7315ab135f8245c38db00fcaf9395dbb80fe15`
4. QPS issues #923, #1258, #1266, #1357
5. QPS successor ledger v0.5 and proof-debt receipt on the child PR.

Preserve:
- QPS LEG5 remains 7/9 until child runtime proof closes the two routes.
- MissionControl is a receiver/control plane only.
- Parent proof never substitutes QPS private runner execution.
- authority transfer = false.
- formal / engineering / negotiation / runtime-GOLD credit delta = 0.

Next legal transition:
QPS runner admission -> current-main #1266 validator -> #1266 closure on PASS -> current-main #1357 validator -> #1357 closure on PASS -> 9/9 ledger -> #1258 closure evaluation.

If QPS execution remains zero-step, STOP on runtime progression. Only update parent pointers when child authority legitimately advances.
