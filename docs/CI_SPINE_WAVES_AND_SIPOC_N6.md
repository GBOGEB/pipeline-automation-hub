# N+6 disjoint worker-wave controller — offline pilot

**Control scope:** propose one SHA-bound work pulse from the `jade.devops.ci-spine.index.v1` topology contract introduced in [PR #996](https://github.com/GBOGEB/pipeline-automation-hub/pull/996). This lane is independently reviewable, but **cannot produce a real index until #996 is available**. It never calls GitHub or executes tasks.

## SIPOC / stage matrix

| Supplier | Input | Process stage | Worker lane | Output | Customer |
|---|---|---|---|---|---|
| Existing JADE census/parser | Indexed workflow source at SHA | DISCOVER | SOURCE | Canonical owner crosswalk | QA / Mission Control |
| Source classifications | Workflow/OID/edges | PREPARE | TOPOLOGY | SIPOC/DAG view | Maintainers |
| Source-index snapshots | Two provenance-bound snapshots | PREPARE | EVIDENCE | Delta/first-red classification | QA |
| Upstream lane receipts | Current SHA, run id, executed count | VERIFY | QA / TELEMETRY | Test and runtime evidence | Reviewers |
| QA + source custody | Independent review, gates | INTEGRATE | GOVERNANCE | HOLD or proposed next gate | Maintainers |
| Governed handover | Verified run receipts and lineage | CONTROL | BRANCH-CUSTODY / MISSION-CONTROL | Next pulse / prune dry-run | Future wave |

## Execution and clock boundary

```bash
python -m unittest tests/test_ci_spine_wave_plan.py -v
python scripts/ci_spine_index.py --check --source-sha "$(git rev-parse HEAD)" --out /tmp/ci-spine-index.json
python scripts/ci_spine_wave_plan.py --check \
  --index /tmp/ci-spine-index.json \
  --policy governance/ci_spine/CI_SPINE_WAVE_POLICY_V1.json \
  --out /tmp/ci-spine-wave-plan.json
```

The default policy has **3 disjoint worker slots** and **8 tasks**. The first proposed pulse is SOURCE, EVIDENCE DELTA and TOPOLOGY MATRIX. Fan-in tasks remain BLOCKED until receipt records are explicitly presented at the same source head. The planner distinguishes source-head identity from measurement time, queue wait, run wall time and execution duration; it **does not invent duration estimates** or perform scheduling in GitHub. Same-lane and overlapping path ownership are anti-affinity rules; task priorities and DAG dependencies are explicit.

A receipt with `source_sha`, `run_id`, `tests_ran` and `verdict: PASS` only counts as a **caller declaration** for planning. It is not independently authenticated by this offline tool; output says `RECEIPT_DECLARED_UNVERIFIED`. Only trusted GitHub readback plus policy/review can advance merge, release or archive custody. The controller always returns `merge: HOLD`.

### Pulse repetition and negative controls

Rebuild the source index at the next immutable head; bind every source pulse to that SHA; provide newly reviewed receipts; re-run with `--check`; inspect `candidate_workers`, `BLOCKED_DEPENDENCY`, `DEFER_OWNERSHIP_COLLISION`, and `DEFER_WORKER_CAPACITY`. Each pulse has an intervening zero-run review/repair interval. A malformed or stale source index, invalid task path, dependency cycle, missing external proof, or wrong SHA leaves execution/promotion blocked.

**No implicit 24/7 or background execution.** Creating a GitHub scheduler/worker dispatcher is a separately governed future PR, downstream of demonstrated capacity, queue constraints, dry-run controls and independent approval. This implementation is read-only and runs only when invoked.
