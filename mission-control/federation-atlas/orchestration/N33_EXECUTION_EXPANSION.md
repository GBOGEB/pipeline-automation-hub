# N3.3 — actual Method Atlas main.py execution-path branch expansion

## Authority and baseline

Stack this candidate on existing N3 broker PR #1253 (which already contains merged
N3.2 runtime coverage work from #1257). Frozen source blob is
`41f04e8719981be6564cf6de33f365d83c7a2264` for
`mission-control/federation-atlas/orchestration/main.py`.
Previous measured REAL N3.2 broker path: **27 executed of 276 eligible branch arcs**.
This is a source-file/runtime-population result, not whole-repository coverage.

The experiment re-executes the 50-DAG N3.2 producer on its *own exact
candidate head* and requires both eligible denominator 276 and precisely
27 executed arcs. It separately runs the real production CLI commands:
`plan`, `build`, and `run-local --workers 1/2/4`, each with separate
coverage.py data and current on-disk output verification.

Only the UNION of `main.py` executed branch arc identities across the five
positive CLI cohorts counts as added runtime coverage. The frozen 27 earlier
arcs must still be covered by those commands. Overlapping arc denominators
are never added. The proposed target is >=60/276; the actual result controls
the report, and the target alone cannot waive a semantic failure.

## Positive execution verification

- **Plan:** actual canonical broker `plan`, 8 source-registry tasks, Kahn
  dependencies and manifest-stable deterministic output. Plan's native JSON
  lacks an embedded source SHA; binding is through the exact checkout and
  enclosing receipt, never a fabricated field.
- **Build:** actual `main.py build`; `main.py check --out`; full output-member
  SHA256, size, source-digest, manifest and authority verification. Existing
  rendered graph and inventory sources remain untouched.
- **Run-local:** three actual isolated clean Git worktrees pinned to the
  identical exact commit; local broker workers 1/2/4 (max 4 unchanged);
  all eight registered generators execute, seven producer/bundle directories
  reconciled against broker-declared output hashes, every predecessor and
  ready-wait/verification timestamp inspected by the existing receipt oracle.
  Entire CLI command is instrumented, not just a unit-test or stub scheduler.
  Child subprocess branch arcs are NOT instrumented by this experiment;
  coverage is restricted to `main.py`.

## Fail-closed controls

1. Stale SHA submitted to the actual `plan` CLI.
2. Missing source root submitted to actual `check` CLI.
3. Malformed source snapshot submitted to actual `plan` CLI.
4. Corrupt a generated `style.css` output byte; the actual
   `verify_bundle` must fail, then the untouched bytes must reverify.
5. Kahn dependency cycle rejected by the actual `layers` guard.
6. Simulated `source_changed_during_run` on a genuine local-run receipt
   rejected by `validate_local_receipt`. This is an adversarial receipt
   fixture, not a claim that the checked-out source was ever changed.

All tests distinguish expected negative evidence from a green main pipeline.

## Performance and scale classification

Report real elapsed wall time per cohort and the broker's observed
elapsed/ready-p95/peak-running tasks for each worker count. Installation time,
cache-hit ratio, billed minutes and fleet queue p95 require independent
native provider readback: set NULL until actually available. A single native
runner that sequentially executes 1/2/4 cannot infer a fleet performance
confidence interval. No worker expansion beyond the existing four-worker
source policy, remote dispatch or new N6 watch.

## DoD/DoV

- [ ] Native head-bound 9+ adversarial tests, syntax and zero-test guards.
- [ ] Original 27/276 baseline reproduced on the new exact head.
- [ ] Real plan output, deterministic repeat and exact source link.
- [ ] Actual build/check and full manifest/member hashes.
- [ ] Three actual eight-task runs for 1/2/4 with verified broker
      output hashes, queue and causal timestamps.
- [ ] New executed arc identity count and honest 60/276 target status.
- [ ] Six distinct negative guards and source-clean checkout.
- [ ] Eligible independent approval, exact-head native/FPC and effective
      protection decision before any merge or source-admission credit.

No original files, rulesets, watches, private QPS source, tokenized actions or
owner authority are changed by this pilot.

`N33_REAL_MAIN_EXECUTION_CANDIDATE / BASELINE_27_ARCS_FROZEN /
FLEET_SCALE_HOLD / INDEPENDENT_REVIEW_OPEN / MERGE_ADMISSION_HOLD`
