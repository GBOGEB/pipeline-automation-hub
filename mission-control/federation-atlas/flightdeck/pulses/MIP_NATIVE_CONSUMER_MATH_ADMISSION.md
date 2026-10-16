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
