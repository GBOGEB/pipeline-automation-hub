# QPS TRIAGE / GoGREEN Metric Census — N1 federation handover

Status: **IMPLEMENTED AS DRAFT PRS; SOURCE OBSERVATION / DISPATCH NOT YET FULLY ADMITTED.** Mission Control [#622](https://github.com/GBOGEB/pipeline-automation-hub/pull/622) is the controller; ABACUS [#2126](https://github.com/GBOGEB/ABACUS/pull/2126), CODEX [#1065](https://github.com/GBOGEB/CODEX/pull/1065), and cryoplant-project [#1946](https://github.com/GBOGEB/cryoplant-project/pull/1946) are the source-owned receivers.

## Canonical ownership and physical scope

- **QPS TRIAGE ULTRA** already has a governed W2 `qps-fleet-receipt/v1` control/AND gate. This new `qps-metric-census/v1` is a separate **observation** contract; it must not claim the existing federation DoV, security waiver or engineering acceptance.
- Three distinct physical producer repos: ABACUS (Python/CI), CODEX (transformation/negative tests), cryoplant-project (QPS engineering). **QPS is a lane inside cryoplant-project, not an additional repository count.**
- Fourth physical repository: pipeline-automation-hub (registry, router, candidate priority analytics, source/review control).
- [Mission Control #530](https://github.com/GBOGEB/pipeline-automation-hub/pull/530) owns canonical ZIP verification; [#531](https://github.com/GBOGEB/pipeline-automation-hub/pull/531) owns six-repository breadth; [#533](https://github.com/GBOGEB/pipeline-automation-hub/pull/533) owns Method Atlas visualization. This census cannot take credit for any of those three domains.

## Pulse mechanics

1. N0: `verify-census-contract` executes the locally authored Python contracts and emits native DAG/SIPOC artifacts on exact controller head.
2. N1: `plan-three-repo-slice` reads allowed current `main` heads, creates deterministic source SHA + selector + wave request IDs, and emits a **dry-run** manifest. No remote CI is triggered by default.
3. N2: Once source-owned receiver PRs have passed existing rules/merged, an owner may select `workflow_dispatch/dispatch_fanout=true` on `master` and install restricted cross-repo `QPS_TRIAGE_DISPATCH_TOKEN`. The controller calls `workflow_dispatch` on each receiver's `qps-metric-census-receiver.yml` at `main` with the four declared inputs (`wave`, `selector`, `request_id`, `expected_sha`), not arbitrary executable commands. The fine-grained token therefore needs only **Actions: Read and write** on the three receivers and **no Contents permission**. Receivers keep their `repository_dispatch` trigger during the transition. HTTP 204 means **enqueued only**, not executed.
4. N3: Each receiver validates head SHA and request ID, routes to `native_checks` and/or `coverage_catalog`, and emits a read-only native run/attempt/job receipt. Missing job IDs, stale heads and unrecognized repos HOLD.
5. N4: Import independently downloaded native artifacts, validate ZIP hashes/member bytes with #530, roll up with Metric Atlas by source identity and population fingerprint, choose the next owner-controlled repair wave. QPS owner acceptance remains separate.

## Identity, evidence and safeguards

Contract fields: `wave`, `request_id`, `lane`, `repo`, `expected_sha`, `selector`, then receiver `target_sha`, `execution_sha`, `run_id`, `run_attempt`, `job_id`, `route`, `outcome`, `evidence_class`.

Private source reads need an authorized **read-only** `QPS_FEDERATION_READ_TOKEN` separate from **dispatch** `QPS_TRIAGE_DISPATCH_TOKEN`. If absent or denied, cryoplant-project stays in the eligible denominator as `HOLD_SOURCE_HEAD_UNKNOWN`, is not dispatched, and contributes no fabricated SHA.

Run/job/check metadata and test-file inventories are **not native executed-test totals or coverage measurements**. Root IDs require independent first-red fingerprints plus owner disposition. Missing `coverage numerator / denominator / scope fingerprint` remains UNKNOWN, not zero.

## Parallel stock/flow and normalization

| Independent cohort | Earlier | Current | Absolute delta | Relative delta | Stock/flow interpretation |
|---|---:|---:|---:|---:|---|
| Method Atlas passing tests | 53 | 74 | +21 | +39.62% | Small baseline, large fractional depth growth |
| ABACUS Python 3.12 passing tests | 2,243 | 2,257 | +14 | +0.62% | Much larger executed-test stock, smaller proportional change |
| ABACUS broad branch opportunities | UNKNOWN | 8,394 opportunities | UNKNOWN | UNKNOWN | Denominator only; no covered numerator |
| Local four-module branch coverage | 52/66 | 52/66 | UNKNOWN | UNKNOWN | Different module scope, not comparable to broad ABACUS |

Normalize each comparable test cohort as `I(N) = 100*T(N)/T(N0)`; preserve raw `T(N)` stock and marginal `Delta T` flow on separate axes. For time, preserve both pulse index and wall-clock `observed_at`; do not treat two repositories' N as a shared timestamp. N20 stability remains UNKNOWN with fewer than 20 matched observations.

## Resource and priority decision

Prioritize candidate next actions by verified distinct root leverage, affected sources, source-owner admissibility, and measured cost. If worker-hours, native job attempts or matched coverage denominators are unavailable, **do not compute numeric yield or an artificial winner**. A common failure label alone does not constitute a proven shared root.

Slice control: initial `max_fanout = 3` physical producers; `selector=all` authorizes at most two read-only DAG routes per repo (maximum 6 receiver jobs) after explicit activation. Avoid repeated source/test reruns until census first-red cluster evidence supports a disjoint source-owner repair.

## Local CLI / IDE

With Python 3.9+ and the Metric Atlas folder on `PYTHONPATH`:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
python -m metric_atlas.census request --wave N1 --heads run/qps_heads.json --output run/qps_requests.json
python -m metric_atlas.dispatch --manifest run/qps_requests.json --output run/qps_dispatch_dryrun.json
python -m metric_atlas.census rollup --manifest run/qps_requests.json --receipts run/qps_receipts.json --output run/qps_rollup.json
python -m metric_atlas.census diagrams --output run/qps_diagrams
```

**No GitHub branch protection, security P0/P1 gate, independent approval, ownership or merge condition has been weakened.**
