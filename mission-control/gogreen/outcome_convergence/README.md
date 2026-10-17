# GoGREEN G9 — 57 native all-outcome runs, no success-only denominator

This wave is deliberately **different from** G7's 24 *selected successful* runs. It freezes two complete GitHub Actions REST first pages for the same inclusive 16–17 October 2026 UTC period, default `main` branch, and verifies `api_total_count == returned_count <= 100` before computing any ratio. The latest snapshot has 27 gg_MATH and 30 cryoplant-project runs. It is complete **only for these named two branch-window populations as observed**, not full repository history.

| Repo | Terminal native run IDs | Success | Failure | Cancelled | Distinct source SHAs |
|---|---:|---:|---:|---:|---:|
| gg_MATH | 27 | 26 | 0 | 1 | 6 |
| cryoplant-project | 30 | 20 | 10 | 0 | 9 |
| **Bounded total** | **57** | **46** | **10** | **1** | Repositories not pooled for source-scope comparability |

**Added code capability:** `outcome_flight.py` reconstructs per-workflow success/failure/other, unique source heads, latest state, ordinal gaps, queue-start proxy and updated-to-start execution proxy, and writes `metrics.json`, `sipoc_dag.json`, `index.html` and a SHA256 manifest. It is strictly read-only and can independently reproduce the metrics from a Git-tracked source-bound native census.

**DMAIC / MIP:** DEFINE population, MEASURE exact attempts/SHA/elapsed clocks, ANALYZE matched workflow family (not root inferred from label), IMPROVE source-owner tests, CONTROL repeat on fresh source and compare N/N+1 by identical workflow/scope and independent approval. Frequency, time span and failure manifestation multiplicity are not independent statistical trials. Queue and execution durations are GitHub timestamps **proxies**, not billing or runner CPU. The G9 DAG records first-red-to-REX as a DECLARED dependency, not an admitted root closure.

**Native tests:** 49 positive/adversarial tests and coverage.py 7.13.3 with hard 85% scoped statement and 80% scoped branch ratchet, alongside 57-run all-outcome/hashed output acceptance. Incomplete first page, time inversions, duplicated IDs/attempts, fake success/promotion, fake source or URL, and forged root closures fail closed.

**Next:** Gather paginated jobs + steps for non-green QPS workflow families; pair with G7 success-only job observations, synthesize *no* fake causal root. Fan out two independent source-owner repairs only after first-red evidence and path lease. QPS canonicalization has six failures and two successes within the observed eight, so it is a more valuable *root diagnosis* target than rerunning six redundant manifestations. `formal_admission=HOLD`.
