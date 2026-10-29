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


## Completed source-bound shadow pulse

- **Run:** [40728019289](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40728019289), exact PR #1014 SHA `96954d16dc12d7443aaa7043d4efa18abbe0ebc1`
- **Result:** `CI bundle immutable-source inventory (advisory)` **SUCCESS**; 20 native tests passed
- **Artifact:** `ci-bundle-shadow-96954d16dc12d7443aaa7043d4efa18abbe0ebc1-40728019289`, artifact ID `12834585155`; ZIP SHA-256 `d02bfa0793c0495d2d7ba94bef00856c7f6a0e7468cc103a889980e63f28def3`
- **Inventory:** 183 workflow YAMLs, zero workflow YAML parse errors, zero malformed-job errors, zero job-DAG cycle/dangling anomalies, **three unclassified candidates**
- **Unclassified (heuristic UNKNOWN):** `gm-i-b-cycle3-propagation-proof-relay.yml`, `gm-i-b-cycle3-propagation-proof.yml`, `historian-register-control.yml`. These are not evidence of nonexistent tests or a failed workflow.
- **Coverage interpretation:** B00 161, B01 1, B02 109, B03 7, B04 1, B05 18, B07 9, B08 3, B10 69, B11 27, B12 9 assignments; B06/B09 no detected hints. Assignments overlap, so counts are neither unique workflow counts nor verified test/coverage counts.

## N2 evidence-hardening follow-through

Additional adversarial checks now reject mixed run attempts, extra unlisted cohorts, unrelated/concatenated test summaries, disconnected footers, malformed totals and invalid cohort definitions. The `observe` helper can now record `run_attempt`; the reconciler includes that attempt in its same-source/run identity. An unexpected third log **cannot** increase 77+12 into an apparent acceptance count. All outputs remain `ADVISORY_ONLY`.

The 20-test success and artifact above refer **only** to the earlier exact head `96954d16…`. The new N2 hardening commits require a fresh exact-head testflight. None of these observations override the unrelated census 89-versus-77 first red owned by #977 or missing-blob work owned by #872.
