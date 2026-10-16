# MIP native-source consumer and statistical admission

Owner boundary: **ABACUS #2033** emits the canonical `abacus.mip.ci-wave-telemetry.v2` JSON; Mission Control only projects and prioritizes. **gg_MATH** is the canonical mathematical library; no independent PCA/BT/ANOVA kernel is implemented here. QPS holds release/engineering authority.

Invocation: `python mip_source_consumer.py --binding binding.json --producer source.json --out view.json`. The binding must declare schema `code-purple.mip-input-binding.v1`, repository `GBOGEB/ABACUS`, exact head SHA, producer path `tools/mip_ci_wave_telemetry.py`, original producer JSON SHA-256, `artifact_bytes_authenticated=false` and `authority_transfer=false`. The locally supplied source bytes must match the declared digest. **A self-declared digest does not authenticate the GitHub native artifact**; an independent acquisition proof is still required.

The output is a disposable projection, not a second root register, SSOT or dashboard. Read-only execution enforces count identities, first-red deduplication denominators, timestamp-source counts, and governance HOLD. Root closures are unverified and kept null. Repeated jobs on one SHA are correlated, not independent experimental observations.

## Statistical gate for decision-making

| Method | Required geometry | Current admission |
| --- | --- | --- |
| Descriptive workflow success | Terminal exact-SHA workflow outcomes, complete denominator | Allowed as non-causal per-head rate |
| 90/95/99% Wilson binomial intervals | Independently exchangeable, same-scope Bernoulli trials; declared sampling design | HOLD; returned interval estimates null |
| Queue p50/p95 | Same native job timestamps, matched runner/workflow cohorts, sufficient independently sampled runs | HOLD cross-wave |
| PCA / temporal PCA | Independent matched n-by-p matrix; effective rank, eigengaps, loading alignment and stability | HOLD; gg_MATH provider only |
| Bradley–Terry | Connected comparison graph, admissible direct pairwise outcomes, finite-MLE conditions | HOLD; no fabricated win probabilities |
| ANOVA | Replicated matched groups, residual/variance diagnostics, adjustment for multiple tests | HOLD |
| MANOVA | Independent multivariate groups, identifiable covariance and full model rank | HOLD |

A nominal interval at 90/95/99% from 21 workflow checks would be misleading because the checks share a source head, dependencies and runners. The three levels are deliberately reported as requested but remain **unestimated** until a valid experimental unit and independent repeated waves are identified. Never interpret workflow-success percentages as project-acceptance percentages.

Roadmap: acquire exact-head ABACUS producer artifact; verify native run/job/attempt + byte digest; consume projection; attach first-red manifestations to canonical ABACUS owner roots; rank deterministic dependency blocking; commission gg_MATH fit only after observational maturity gate; score rolling N+2 forecasts against independent actuals. Preserve QPS DEFER, four-hop UNKNOWN, merge HOLD.

## N+19 controlled breadth / denominator expansion

The consumer now fails closed when first-red semantic fingerprints differ from
the canonical ABACUS JSON digest of workflow path, job name, step name and
numeric step ordinal. Each source manifestation must carry a unique native
`run_id:attempt:job_id`; manifestation groups must reconcile to the
`terminal_by_outcome` population. Missing native step detail remains in
`red_jobs_without_attributed_first_step` rather than being silently dropped.

New descriptive quality denominators (not independent statistical trials):

- `red_jobs_total` = failure + timed_out + startup_failure job outcomes.
- `first_red_attribution_fraction` = attributed red jobs / all red jobs; NULL
  when there are no red jobs.
- `first_red_signature_compression_fraction` = 1 - distinct first-red
  signatures / attributed red jobs, a repeated-symptom compression indicator,
  NOT the fraction of engineering roots repaired.
- `queue_native_fraction` = job-created timestamp samples / all measured
  queue samples; NULL when the sample population is empty.
- Job terminal+pending counts and queue clock-source counts are reconciled
  separately, preserving workflow/job and queue/run clocks.

Testing now includes native positive/negative controls, property-style
metamorphic reordering and complementarity, numerical 90/95/99 reference
checks, 100-signature/200-manifestation deterministic load fixtures,
invalid/duplicate SHA and job provenance, denominator falsification,
NaN/boolean/negative timing, and source binary hardlink/symlink protection.
The projection output is atomically replaced only after full validation.
Coverage.py records **actual** producer-consumer line and branch denominators
in the native PR test job; no fabricated global coverage numerator is used.

## Provider reuse versus synthetic tests

The Mission Control CI explicitly checks out the public canonical provider
`GBOGEB/gg_MATH` at exact immutable reference commit
`40ab86f2c821f50a85ace1556f656197b317e795` (draft provider PR #55)
with credentials persistence disabled. It runs the provider's own six
numerical/metamorphic Wilson test families and emits a JSON receipt with
`class=SYNTHETIC_REFERENCE_ONLY` for a labelled 5/10 illustrative example:

| Level | Wilson lower | Wilson upper |
| --- | ---: | ---: |
| 90% | ~0.269271 | ~0.730729 |
| 95% | ~0.236593 | ~0.763407 |
| 99% | ~0.184226 | ~0.815774 |

These are fixed-horizon approximate numerical reference values, **not**
intervals calculated from ABACUS workflow-check counts. Independent Bernoulli
sampling, absence of optional stopping and matched selection must be proven
before a production interval is admitted. gg_MATH #55 being green or even
merged would NOT establish those sampling assumptions.

## Math-guided decision ladder

1. **Deterministic first-red/DAG selection:** prioritize native first-red,
   root ownership, unblock-reach and exact-head fixability; do not confuse
   repeated failure symptoms with independent defects.
2. **Independent run-level design:** define a sampling unit, distinct exact
   run/attempts, same-scope workflows/runner/configuration, and residual
   dependence diagnostics. Preserve job-created vs workflow-created clocks.
3. **Qualified 90/95/99% intervals:** use gg_MATH Wilson for proven
   independent Bernoulli designs or its mean/other reference kernels for
   appropriately modeled scalar outcomes; no repeated-look interval without
   valid confidence-sequence design.
4. **PCA:** require independently observed n-by-p data, explicit metric units,
   variation and effective rank, eigen-gap tests, loading alignment and
   held-out stability; do not fit PC1 to one source head.
5. **Bradley-Terry:** require a connected graph of matched pairwise candidate
   outcomes, absence of separated win/loss components and uncertainty
   diagnostics; no invented BT "win %" from scanner counts.
6. **ANOVA/MANOVA:** define genuinely replicated treatments/groups,
   multivariate covariance rank and diagnostics; conduct inference only with
   justified residual structure, corrections and vetted distributions.
7. **Control:** score immutable N+2 predictions when future independent
   outcomes arrive; distinguish descriptive shift, statistical evidence and
   causal engineering root closure.

The current MC contract does not grant PCA, BT or ANOVA/MANOVA fitting
authority. `authority_transfer=false`, `merge_authorized=false`,
`accepted_bd_root_closures=null`, `qps_engineering_acceptance=DEFER`.
