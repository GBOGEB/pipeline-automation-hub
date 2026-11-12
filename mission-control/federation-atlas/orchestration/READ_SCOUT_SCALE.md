# Method Atlas N1 · read-only scout scaling (16 vs 32)

**Parent:** existing GoGREEN / Method Atlas and PAH #529; this is not a
second scheduler, observer, metric owner, queue controller or N6 notifier.

**Question:** When 16 read-only scouts are busy, does increasing to 32
improve **accepted source-bound results per wall-clock second** enough to
justify queue pressure, runner minutes and new failures? Or would a simpler
16-scout process with better cache/setup/steps outperform that increase?

## Existing authorities

- Queue and workflow timings: canonical
  mission-control/jade_temple/devops/actions_metrics.py.
- Local bounded mutating generator concurrency: Method Atlas
  BROKER_POLICY_v1.json (default 2, maximum 4); UNCHANGED by this PR.
- Mutator scale and root-governed promotion:
  mission-control/gogreen/sipoc_scale_gate.py (2-to-4 only).
- Workflow, source and process lineage: existing Method Atlas main.py.
- Code coverage populations: existing coverage_contract.py.
- Read-only scout-scale adviser: read_scout_scale.py (this change).

The scale adviser does not compute raw CI p95 or invoke the GitHub API;
it consumes **owner-precomputed metrics** with identity claims that must
be authenticated independently before an owner acts. In the absence
of observations, it outputs HOLD with NULL ratios, never a guessed
worker-capacity or synthetic fleet metric.

## Proof contract

Minimum four matching, consecutive pulse IDs in each of:

1. scouts16: baseline read-only worker cohort.
2. scouts32: experimental read-only worker cohort.
3. optimized16 (optional but recommended): same 16 scouts with
   lockfile-verified wheel cache, reduced redundant setup, batch/fan-in
   improvements or process simplification.

Every paired pulse must have exactly the same source HEAD SHA, workload
SHA256 and environment SHA256. Each native identity tuple
(run_id, attempt, job_id) must be unique, terminal and report actual
steps; failure and cancellation remain in the population. No
green-only selection.

The native source owner must corroborate the tuple through authenticated
GitHub Actions readback (including runner, step, exact head, publisher,
artifact manifest and timestamp). Data inside a user-supplied JSON
cannot self-attest. A complete favorable sample therefore returns
ADVISORY_ONLY, never READY_TO_DISPATCH or automatic scaling.

Measures per variant: accepted outputs / observed wall seconds,
runner seconds / accepted output, per-pulse source-owner queue p95,
cache hit ratio, failure/cancel/first-red counts, root recurrence.
The adviser does not mathematically pool four p95 values into a
fictional fleet p95. It checks each comparable pair.

## Execute safely

From a checked-out source:

~~~bash
python -m unittest discover -s mission-control/federation-atlas/orchestration \
  -p test_read_scout_scale.py -v

# No real four-pulse source receipts? This MUST return HOLD.
python mission-control/federation-atlas/orchestration/read_scout_scale.py \
  --out /tmp/read-scout-scale/advisory.json

# Only after an authorized, source-bound paired cohort is available:
python mission-control/federation-atlas/orchestration/read_scout_scale.py \
  --input /private/verified-read-scout-trial.json \
  --out /tmp/read-scout-scale/owner-advisory.json
~~~

No new schedule, automated dispatch, mutation, workload expansion,
GitHub PR edit, merge, budget change or environment setup is performed.

## Stop rules and next gated rollout

- Any zero-step, mixed source head, reused run/job, missing pulse,
  first-red recurrence, queue p95 regression or increasing unit cost
  blocks comparison or scaling credit.
- Favor process simplification and cache reuse over worker doubling
  when optimized16 is equal or better on comparable evidence.
- Run a bounded 2→4 local read-only evidence pilot first if owner
  authorizes, without raising the broker's mutator limit.
- Only then propose *external* 16→32 read-only scouts through the
  existing fleet execution owner and explicit budget, with stop
  conditions on p95, roots, cost and token-bearing actions.
- Real script/workflow DAG coverage remains separate from test code
  coverage and from full federation acceptance. Never infer private
  QPS owner data or assume all seven repos are accessible.

**Current disposition:** NO_MATCHED_NATIVE_OBSERVATIONS / SCALE_HOLD.
Experimental data in unit tests are intentionally synthetic and receive
**zero** fleet performance/engineering credit. Release and merge
admission remain independent.
