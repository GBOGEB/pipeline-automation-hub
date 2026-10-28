# N2 — Immutable-source shadow execution and split-population evidence

**State:** advisory/read-only; not merge admission, not an override for existing JADE DevOps census.

## Implemented

The scoped workflow [`ci-bundle-shadow.yml`](../.github/workflows/ci-bundle-shadow.yml) checks out the exact PR head, runs independent bundle-inventory unit and negative controls, enumerates every workflow from immutable `git ls-tree`/`git show` objects at that same SHA, and uploads a SHA/run-bound JSON report and logs. It has read-only `contents` permission, no deployment, no issue mutation, no new required status. The new workflow itself increases the observed workflow file count by one on this branch; it must not be compared with an earlier 182-workflow master count without source alignment.

```bash
python -m unittest discover -s mission-control/jade_temple/devops/tests -p 'test_ci_bundle_*.py' -v
python mission-control/jade_temple/devops/ci_bundle_inventory.py --source-sha "$(git rev-parse HEAD)" --out /tmp/ci-bundle-shadow.json
```

The helper `ci_bundle_population_evidence.py` separately observes `unittest` reported totals and excludes skipped tests from the executed count. Selection/collection remain **unknown** unless upstream emits separate evidence. Only complete source/run-matched log cohorts can have an **advisory observed** combined total; log text itself is not authenticated gate evidence.

## First-red crosswalk

- At PR #997 SHA `41f187f9395528b2009ce0fee2ffe51eba295148`, JADE N+9 DevOps census run [40723962052](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40723962052) observed **77 passing tests** in the first `test_devops_*.py` step. The existing single-step floor **89** is wrong for that step.
- Existing PR [#977](https://github.com/GBOGEB/pipeline-automation-hub/pull/977) owns the noncompensating 89→77 correction and explains the separate 12-test `test_actions_metrics.py` step. PR [#872](https://github.com/GBOGEB/pipeline-automation-hub/pull/872) owns additional fail-closed missing-blob protection and raises its integrated scoped population to 78.
- The 12 metrics tests were **not executed** in the red #997 census run, because the first step failed. Therefore the total 89 must **not** be claimed for #997; test fixtures representing 77+12 are negative-control examples, not live acceptance.
- Do not change the 90% statements / 80% branches coverage floors, the instrumented population, or the existing test-population owner to make a red green.

## Follow-through

The shadow workflow's JSON artifact provides a baseline for N1 metadata crosswalk and N3 queue-scheduler focus. The next promotion gate is source-bound inventory artifact readback, independent review, and explicit GOGREEN applicability classification. A new advisory workflow is a new CI workload and should be weighed against job minutes before expanding fleet-wide.

The N2 PR is a disjoint sibling of N1, both based on PR #997 at `1048fc4f7074e06a2118e7705d15c98383e96bf9`. All three PRs stay DRAFT/HOLD until exact-head checks and eligible review are complete.
