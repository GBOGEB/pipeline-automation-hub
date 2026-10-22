# Metric Atlas: temporal/SIPOC/coverage math and qualification

## Typed metric unit and provenance

Atomic observation: `(repo, source_head_sha, run_id, run_attempt, job_id, artifact_id, module_or_file_scope, population_fingerprint, timestamp, metric, numerator, denominator, evidence_class)`.

A **branch** in `covered_branches / possible_branches` is a control-flow coverage opportunity, not a Git branch. A **development branch** is a source line of development; a **lane** is a logical programme workstream. These three meanings must not be conflated. One PR may span modules, one module may be shared across PRs, and repository totals may duplicate common files. Union/deduplicate before rolling up.

There are three orthogonal axes:

1. Repository/worktree/time (commit ancestry + current PR head + merge base).
2. Test/coverage population (file set, execution filters, tool/config fingerprints, exact opportunity counts).
3. Programme/process lineage (wave, pulse, task, root ID, fingerprint, SIPOC lane, acceptance evidence).

`N` indexes a *per-series observed event*, newest N=0 and prior N-1, N-2. A global UTC axis is separate; two N=0 points from distinct repos do not indicate simultaneity. Source events without verified timestamps use sequence labels, not invented clock times. Preserve original event records and reconstruct N positions when new evidence arrives.

## Metrics and mathematical safeguards

- Ratio `C=num/den` only when both are measured, `den>0`, `0<=num<=den`.
- **Scope-matched uplift** `C(N)-C(N-1)` only with identical file/opportunity/config/version fingerprints (or a documented remapping strategy such as per-line identity matched intersection).
- Test-count growth `g=(p_N-p_prior)/p_prior`, where tests refer to the same named suite and qualification says count only, not performance/coverage. Increase in test count is not automatically quality improvement.
- Pulse slope `v=(y_N-y_prior)/(N_N-N_prior)`; acceleration `a=v_N-v_prior` requires three or more points. These are per-pulse changes, not elapsed-time velocity without trusted timestamps.
- Rolling `N20=mean(last 20 observations)` requires at least 20 comparable samples. When fewer are available, emit UNKNOWN rather than 4-point estimate labeled N20.
- Growth index `I(N)=100*y(N)/y(first)` only when positive baseline; declines on good metrics such as errors are interpreted in their own direction.
- Stability: require at least five finite pulse slopes, then slope coefficient of variation; better stability model separately estimates recurrence frequency, change-point confidence and failed rerun probability with appropriate exposure denominators.
- Yield per worker-hour and p95 queue latency remain UNKNOWN absent authenticated worker-hours and timestamps. Avoid dividing by commits or raw PR count as a surrogate for hours.
- `root_id` only once a first failing step, matched source changes and owner receipt establish causality. Matching job name is a *category*; matching first-red is a *fingerprint*; accepted `root_id` is stronger evidence. Count unique PRs per root, not workflow manifestations.
- PCA requires complete, deduplicated row-level observations, consistent variables and sensible conditioning. Native #533 historical method threshold: >=60 complete rows. Bradley-Terry requires authenticated terminal paired comparisons; native method ledger threshold >=30 pairs and >=5 positive outcomes. Thresholds are qualification criteria, not proof of readiness.
- Logarithmic charts are for comparing opportunity magnitudes, not converting all populations into one coverage metric. Use `log10(x)` only when `x>0`, with explicit treatment for zero, negative and missing values.

## N-index progression / DOE

- **N0 / DEFINE**: freeze repository cohort, metric contract, current head, denominator and historical snapshot URI.
- **N+1 / MEASURE**: fetch native logs, first-red, attempt, artifact bytes and granular statement/branch denominators. Produce null-aware ledger and reproducible ZIP verifier receipt.
- **N+2 / ANALYZE/IMPROVE**: rank source-owner repairs by `expected PR releases per engineering hour * verified attribution confidence` subject to critical-security constraints; run disjoint negative/regression testflight on exact head.
- **N+3 / CONTROL**: verify required gates and independent approvals; serial admission only if genuinely eligible; monitor post-merge recurrence and matched coverage under identical scope.
- **N+4 / EVOLVE**: attach 20-point history, matching PCA/BT/queue metrics only after denominator and independence criteria pass; consider automation of safe repeatable read-only work.

## Prioritization with incomplete data

Prioritization is a Pareto decision with dimensions leverage, regression risk, urgency, resource cost, scope confidence and criticality. A scalar weighted score may be used for scenario exploration, but never as a substitute for security/governance hard gates. Unknown cost is not zero cost. Classify `GO_PROVE`, `GO_EXECUTE`, `HOLD_REQUIRED`, `CONTROL_POSTMERGE` independently.

## Stability / health KPI families to add as data becomes available

- Code health: touched-file Black findings, Flake8 issues per 1k touched LOC, Bandit P0/P1 count by unique finding, Safety status and severity; baseline and new-debt counted separately.
- Tests: collected/pass/fail/skip/deselect/quarantine counts and methods; new negative/reverse cases; matched branch/statement opportunities and changed lines.
- Pipeline: queue seconds p50/p95, execution seconds p50/p95, attempts per successful native proof, cache-hit/saved-seconds, testflight cancellations from head churn.
- Coverage: exact common intersection, newly introduced opportunity coverage, total population movement and config identity; carry named scopes not global rollups.
- Graph: distinct nodes/edges, degree centrality, bridge dependencies, unique proven root IDs, repeated fingerprints, fan-out blocked PRs; lineage of emitted outputs.
- Organization: worker-hours, productive proof per hour, lease collisions, orchestration overhead, accepted actual merges per 100 CI runner-hours.
- Maturity: historical data completeness, trend reproducibility, provenance quality, method readiness, audit-control adherence.

## Replay and reproducibility

1. Select a historical PR exact source SHA and immutable native run/job/attempt. Save runner OS, Python distribution, wheels/constraints and CLI test filters.
2. Re-run in a fresh throwaway checkout (not `main`) using captured lockfiles; mark an emulation/replay when native original environment cannot be recreated.
3. Reproduce old metrics, preserve original proof and report a delta against same original population. Reject false attestation where run/sha/attempt differs.
4. Apply a source-owned candidate fix in a disjoint branch. Compare **A -> B -> A** against the baseline to detect hidden environmental/temporal effects.
5. Append (never overwrite) derived measurements with new timestamp, provenance, scope and `REPLAYED` classification in a future schema revision; current validator intentionally accepts only listed classifications.

## Roles

Mission Control #530: canonical downloaded ZIP verifier. #531: six-repo breadth producer. #533: Method Atlas viewer. This atlas is an additional offline analysis projection; it does not supplant those authorities, qualify QPS acceptance, or modify GitHub branch protections.
