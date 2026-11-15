# N3.2 — measured broker execution branch arcs and owner-fenced fleet proof

Upstream PR: https://github.com/GBOGEB/pipeline-automation-hub/pull/1253
Continue on exact source HEAD, do not replace the existing broker, coverage contract or GOGREEN producer.

## 1. Measured populations (separate, never summed)

| Population | Scope | Unproven |
|---|---|---|
| TEST_SUITE_WITH_REAL_SMOKE | coverage.py statement and branch arcs reached by the N3 14-test suite, including real smoke | fleet product acceptance |
| ACTUAL_N3_50_BROKER_DAGS | standalone 50-DAG native source execution, instrumented broker, Method Atlas, G9 and warm pilot arcs | total repository or cross-repo coverage |
| NATIVE_IDENTITY_SELF_REPORT | Actions run/attempt source claims | authenticated independent runner and job/step identity |

Coverage.py is pinned to 7.13.3 and each population has its own raw JSON.
Only actual executed branch arcs contribute to runtime coverage. Unknown or missing
instrumentation is not zero. Branchless is not zero. Both denominator and covered
arcs require an eligible population, and every production file is explicit.

## 2. Native source-bound testflight

The workflow method-atlas-n32-coverage.yml runs read-only PR/manual, pins exact
checkout and Python 3.12; executes eight receipt negative tests, then N3 test suite
under separate instrumentation, then the real N3 50-DAG command under runtime-only
coverage. It exports both source-bound coverage.json files, native N3 receipt,
comparison receipt and runner self-report. Full output remains held as a GitHub
artifact. It does not change BROKER_POLICY_v1.json, source owners or watches.

Measured runtime source files: broker.py, main.py, outcome_flight.py,
warm_broker_pilot.py. The receipt rejects zero or absent measured runtime arcs,
wrong source HEAD, wrong 24 positive/26 negative DAG population and non-branch
coverage. Do not aggregate overlapping test and runtime denominators.

## 3. Independent four-native-run series

One workflow execution is ONE native run. Its 50 DAGs and four internal pulses
are not four independent GitHub jobs or independent runs. To qualify repeatability
collect four DISTINCT source-matched native run IDs, job/step IDs, accurate
actual run outcomes and immutable output digests via provider readback.
Match environment, toolchain, workload, source head, cache and queue scope.
Actual queue p95, startup/fixture load seconds and billable runner cost must be
measured and attached, including failures/cancellations. Runner ENV values
are claims only, and missing costs are NULL, not zero. The existing merged
read_scout_scale.py owner must review any wider capacity promotion.

## 4. TypeScript federation boundary

The candidate source is DOCX_RTM_Automation orchestration_ts/src/queue/JobQueue.ts.
Its owner-side producer may execute a deterministic FIFO test and generate a
source-bound hashed result from compiled TypeScript. That is a candidate component
receipt, not proof of a full multi-agent orchestration pipeline. The owner must
provide independent review/acceptance, exact-head native CI and authorized
artifact readback before Hub accepts cross-repo operational credit. No source
contents or sensitive data should be copied to Hub.

## 5. DoD and admission

Source arcs separate from test arcs; reproducible 50 DAGs; native receipt hashes;
read-only token policy; no false whole-repo or fleet percentages; four independent
native run/job proof (future); independently accepted TypeScript owner receipt
(future); effective FPC/security/protection and eligible independent review
before merge or rollout.

Disposition: N32_SOURCE_INSTRUMENTATION_CANDIDATE / NATIVE_COHORT_PENDING /
TYPECRIPT_OWNER_RECEIPT_PENDING / MERGE_ADMISSION_HOLD.
