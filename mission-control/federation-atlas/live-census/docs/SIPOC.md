# SIPOC — Federated live census and proof publishing

| Supplier | Inputs | Process | Outputs | Customers |
|---|---|---|---|---|
| GitHub repos, CI Actions, scanners, canonical owners | Repo full SHA, PR base/head, run/job/attempt, native artifact/member bytes, issue owner, root candidate | H0 source census → H1 disjoint join → H2 telemetry → H3 Testflight → H4 independent proof → H5 publish → H6 graph → H7 Control | Read-only source-bound snapshot, diagnostics, edges/nodes, unmatched blockers, accepted receipts after independent validation | ABACUS/CODEX maintainers, MissionControl, QPS owner, reviewers |

No source mutation, no inferred closure, no agent authority. The viewer's authority is always below original source and native receipt.
