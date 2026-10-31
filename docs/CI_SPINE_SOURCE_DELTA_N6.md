# CI spine pulse-delta and first-red/change custody

This is a separate reviewable evidence lane from the [CI authority index PR #996](https://github.com/GBOGEB/pipeline-automation-hub/pull/996) and [disjoint-wave controller PR #1001](https://github.com/GBOGEB/pipeline-automation-hub/pull/1001). It does not reparse workflow YAML: it compares two **canonical** `jade.devops.ci-spine.index.v1` snapshots and reports source changes. No GitHub API reads, actions, or destructive operations.

## Run only after both snapshots are source-bound

```bash
python -m unittest tests/test_ci_spine_delta.py -v
python scripts/ci_spine_delta.py --check \
  --before /tmp/ci-spine-index-P0.json \
  --after /tmp/ci-spine-index-P1.json \
  --out /tmp/ci-spine-delta-P0-P1.json
```

The comparator requires 40-hex source identities, SHA256 workflow source fingerprints, parse/anchor integrity and a noncompensating `merge_admission=HOLD`. Two different projections at one commit are a first-red reproducibility conflict. It recognizes source-file additions, modifications, disappearances, job-needs DAG changes, triggers, schedules, permission changes, reuse indicators and authority rebinding. Missing workflows require custody review, **not deletion**. Changed permissions/dispatch/scheduling/job structure are `safety_attention`, not automatic vetoes or authorizations.

### Observable and unobservable

| Measurement | Reported | Authoritative source |
|---|---|---|
| Source SHA and 64-hex workflow hash | Yes | CI spine index, git checkout |
| Workflow additions, removals, modified fingerprints | Yes | This deterministic comparison |
| Job needs, trigger, schedule and privilege deltas | Yes | Canonical `devops/workflows.py` projection |
| Queue seconds, runtime seconds, billable minutes | **NOT MEASURED** | Existing `actions_metrics.py` |
| Root recovery, recurrence, blame/first-red status | **NOT MEASURED** | Existing `scale_dock.py` / EVERRED |
| Real job execution, review, effective required checks | **NOT EVALUATED** | GitHub run/check/review evidence |
| Merge, release or branch deletion authority | **HOLD** | Branch rules, FPC, owners, eligible review |

## MIP/DMAIC next-pulse loop

Read one immutable previous index and one exact-head current index -> compute and review changed identities -> correlate *separately* with same-window runtime/recovery evidence from metric owners -> write an ACCEPT/REPAIR/DEFER decision with reviewer attribution -> only then release the next proposed worker pulse. This prevents credit for pure workflow count changes, stale badge greens, or improved durations with a decreased tested population.

**Scope:** nothing is scheduled, merged, deleted or promoted; this is an offline contract, not a live fleet KPI. Negative test fixtures must run on the reviewed head before adoption.
