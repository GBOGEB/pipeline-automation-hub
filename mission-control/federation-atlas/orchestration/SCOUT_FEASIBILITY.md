# Method Atlas N2: actual read-only G9 producer scaling pilot

## 1. Owner and scope

This increment builds **on**, but never replaces:
- the existing Method Atlas main.py + local broker + runtime_evidence.py,
- GOGREEN G9 outcome_flight.py as the production algorithm,
- the already-merged read_scout_scale.py for independent four-native-job
  scale admission,
- canonical Actions queue/cost metrics from jade_temple/devops/actions_metrics.py,
- GOGREEN / N6 observer and root-closure authorities.

The N2 workload runs ONLY one existing public G9 input set in a single
ephemeral GitHub Actions runner. It does not dispatch workflows or remote
workers, change broker.max_workers=4, access private QPS source, write the
checkout, create an autonomous agent or grant a token.

## 2. Experimental design

A fixed workload contains 32 input cases per block:
- 24 original source census cases: expected 57 total = 46 success +
  10 failure + 1 cancellation;
- 4 semantically valid controlled counterfactuals: expected 57 =
  45 success + 11 failure + 1 cancellation;
- 4 intentionally incomplete native-population cases: expected to
  be **rejected** with the denominator validator error and no outputs.

For each case the same G9 engine actually generates output, or correctly
rejects the invalid input. We read and hash every required generated member,
check the G9 source SHA and compare semantic outcome counts. For every
cohort, all 32 task IDs must join exactly once, independent of asynchronous
completion order. A green process exit without valid output is a failure.

Run four **balanced blocks**. Within each block, every mode sees exactly
the same set of input IDs, input digests and effective application code.

| Mode | Maximum local concurrent task carriers | Mechanism |
|---|---:|---|
| cold1 | 1 | Original G9 Python CLI, a new Python process per task |
| cold4 | 4 | Same CLI, at most four subprocesses |
| cold16 | 16 | Same CLI, at most sixteen subprocesses |
| cold32 | 32 | Same CLI, at most thirty-two subprocesses |
| warm16 | 16 | Existing G9 build() imported once and reused in-process |

Mode order is rotated ABBA in the four blocks to reduce simple
warm-up/ordering bias. Concurrency counts are **one runner's local process
slots**, NOT independent GitHub jobs, fleet worker slots, or an expanded
Method Atlas mutation limit. The warm16 mode removes interpreter startup
overhead and necessarily has a different bootstrap/caching regime. We
verify output parity before comparing it with cold16.

Total physical invocations: **4 × 32 × 5 = 640**; 560 verified positive
outputs and 80 verified negative rejections if all complete.

## 3. Measurements and mathematics

Each mode/block reports actual measured:
- wall-clock duration (seconds) of the complete 32-case fan-out/fan-in;
- accepted valid outputs per wall second, excluding invalid outcomes
  from the numerator but including their wall cost;
- median and nearest-rank p95 *individual task* duration in seconds;
- requested concurrency and **observed local in-flight peak**;
- task completion-order hash, accepted output member hashes and input
  identity parity;
- rejection count and the exact failure class of controlled negatives.

For four matched blocks p, the descriptive speedups are:

    S32,16(p) = wall_cold16(p) / wall_cold32(p)
    Swarm,16(p) = wall_cold16(p) / wall_warm16(p)

A value above 1 means lower observed wall time in the denominator
cohort for the *same workload*, during those blocks. The point
summary is the median of four paired ratios, not a fleet p95. Four
observations on one shared runner are dependent and insufficient for a
qualified inferential CI or multi-runner decision. The report deliberately
outputs confidence_interval=null and causal_fleet_scale_proven=false.

A failure or red is part of the measured result: never discard it to
improve throughput or present a green-only sample. CI fails closed on
an unexpected input rejection, missing output, unverified SHA, duplicate
fan-in or mutated source. Performance regression is reported, **not**
hidden or converted into a code failure without a predefined threshold.

## 4. Run without dispatch (local or native)

From a clean checkout of the exact desired SHA:

    HEAD=$(git rev-parse HEAD)
    python -m unittest discover -s mission-control/federation-atlas/orchestration \
      -p test_scout_feasibility.py -v
    python mission-control/federation-atlas/orchestration/scout_feasibility.py \
      --root . --head "$HEAD" --tasks 32 --pulses 4 \
      --out /tmp/method-atlas-g9-scale

Interactive review: open /tmp/method-atlas-g9-scale/index.html.
Its bar meters and table display actual measured results from a real
producer, not predicted ratios. It retains source SHA and workload SHA
and states its lack of native four-pulse admission authority explicitly.

Generated:
- scale_feasibility.json: all per-task, per-cohort and per-block
  source-bound runtime outcomes, p50/p95, fan-in and digests;
- index.html: self-contained purple review surface;
- execution_dag.mmd: true source→executor→oracle→fan-in edge semantics;
- manifest.json: SHA-256 of every outward member;
- native_gate_hold.json (native CI): the *existing* read_scout_scale.py
  retains HOLD_NO_MATCHED_NATIVE_OBSERVATIONS.

## 5. Gates and next recursive expansion

Kahn-style precedent:

    P0 existing G9 input and exact source head
       ↓
    P1 actual local 1/4 proof + SHA/negative tests
       ↓
    P2 16/32 cold proof and 16 warm-source alternative
       ↓
    P3 four paired blocks + source-bound comparison
       ↓
    P4 externally authenticated native four-pulse cross-runner
       read_scout_scale.py gate (separate, NOT satisfied here)
       ↓
    P5 owner-approved, cost-bounded wider read-only federation

Only P0-P3 can be established here; P4 requires real **independent native
run/job** observations and source-owner queue metrics. No fabricated IDs
are used to feed the canonical scale advisory.

Next iteration should replace G9-only fixture cases with approved,
**source-identical**, real Method Atlas broker DAG workloads:
registered local generators, separate source/port manifests, temporal
start/end and dependency edges, output hash reconciliation and negative
causal counterfactuals. Then repeat the same blocked design on a second
language (TypeScript DOCX queue), retaining owner custody and
security boundaries. N6 remains the sole notification owner.

**Admission rule:** Native exact-head PASS, negative regression, independent
review, effective required-status and owner acceptance before merge or
scale promotion. The present feasibility pilot cannot authorize 32
GitHub runners, 32 mutating workers, QPS engineering credit or permanent
causal-root closure.
