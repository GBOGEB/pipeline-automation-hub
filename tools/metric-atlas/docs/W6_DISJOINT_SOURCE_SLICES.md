# CODE PURPLE W6-B | disjoint source-reader flight, no new scheduler

This adds a **pure deterministic adapter** `metric_atlas.disjoint_scale` on top of existing canonical `metric_atlas.census.request`; dispatch, `owner_flight`, `postflight`, #530 ZIP verification, CODEX/Mycelium and private QPS authorities are unchanged. It does **not** launch authenticated workers or edit any SSOT.

## Contract

1. Rebuild the entire three-lane request manifest byte-for-byte through the existing W5 census request implementation. Reject forged IDs, dropped deferred lanes, unauthorized repos, missing heads reclassified as known, Boolean fan-out and mixed route selectors.
2. Expand only the approved read-only route names. One source repository has **at most one ticket per proposed round**; no lease/path collision is allowed within a round. Existing owner write leases remain separate and unissued.
3. Bounded planning ceiling `--slots {1,2,3}` is *hypothetical*, **not measured runner availability**. Actual jobs, tests, coverage, worker hours and root closures remain null/zero-not-dispatched.
4. Source/pulse ordering is deterministic; create SHA256 of the entire plan. Allow an explicit exact permutation to prioritize QPS MASTER INPUT first in an offline reviewer view without changing the underlying source order or control authority.
5. Deferred and no-authorized-head lanes are retained as explicit ledger rows. No join may silently convert UNKNOWN to green. Feedback is to **N+1** only.

## Three bounded illustrative pulses (not native distributed executions)

| Pulse | Source fanout | Max routes | Proposed rounds (2 slots; source-distinct) | Admission |
|---|---:|---:|---:|---|
| N+1 | 1 known source | 2 | 2 | HOLD |
| N+2 | 2 known sources | 4 | 2 | HOLD |
| N+3 | 3 known sources | 6 | 3 | HOLD |

`python -m metric_atlas.disjoint_scale --manifest requests.json --slots 2 --output plan.json --diagrams graphs/`

The resulting `W6_DISJOINT_DAG.mmd`, `W6_DISJOINT_SIPOC.mmd`, `W6_DISJOINT_SPLINE.mmd` use numerically coded stages and semantic pastel classes. One pulse's execution slice is acyclic. `N+1` feedback is a separate node.

## Tests and optional Docker

`PYTHONPATH=tools/metric-atlas python -m unittest discover -s tools/metric-atlas/tests -p 'test_disjoint_scale_w6.py' -v`

A constrained, **non-networked, no-credential, read-only** Compose example lives at `containers/w6-readonly.compose.yaml`. It runs two disjoint local test families against the mounted checkout; operators must resolve/pin the base image digest before trusted deployment. The container harness has not been executed in this wave because Docker is unavailable in the current executor; native GitHub Python tests are the qualification source.

Outward views never become source authority; no automatic dispatch and no engineering acceptance. Require independent human review and effective main protection before any release.
