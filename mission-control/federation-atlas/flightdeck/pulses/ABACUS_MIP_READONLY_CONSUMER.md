# CODE PURPLE — ABACUS MIP v2 → Mission Control (N+18)

**Status: supporting consumer; engineering admission HOLD.** The canonical metric
producer is [ABACUS #2033](https://github.com/GBOGEB/ABACUS/pull/2033).
The canonical mathematics provider is [gg_MATH](https://github.com/GBOGEB/gg_MATH/tree/main/kernels).
Mission Control consumes evidence and emits only a bounded projection. It does
not create a duplicate root ledger, scanner fingerprint authority or HTML SSOT.

## Source and binary lineage

1. The workflow input selects a single exact 40-character ABACUS commit SHA.
2. The existing Mission Control GitHub read-only transport retrieves the full
   bounded GitHub pull-request workflow census at that SHA, plus each run and
   attempt-scoped native job. Missing pages, duplicates and source drift abort.
3. A second checkout of that exact ABACUS commit runs its own canonical
   tools/mip_ci_wave_telemetry.py executable on the native input.
4. The Mission Control consumer validates source SHA/schema, independent HOLD
   gates, workflow and queue denominators, native first-red IDs and hashed
   signatures, and a separate total for missing step attribution.
5. Inputs, canonical producer projection and the supporting view are available
   as GitHub Actions diagnostic artifacts, without being promoted to verified
   multi-hop/Rex custody or QPS admission.

The full input byte digest in Mission Control is local reproducibility, **not**
proof of original native artifact custody. A complete first-page bound of 50
workflow runs and up to ten 100-job pages per attempt is enforced. Any incomplete
or inaccessible census remains UNKNOWN rather than a synthetic zero.

To replay negative controls locally, run Python unittest discovery in
mission-control/federation-atlas/flightdeck/pulses using the file pattern
test_abacus_mip_*.py. To collect an exact head in GitHub, dispatch the
CODE PURPLE ABACUS MIP Readonly Consumer workflow with abacus_sha.

## Metrics and statistical preconditions

- Workflow success share (%) = 100 × successful workflow records / all observed
  workflow records; cancelled, pending and other conclusions stay separate.
  This percentage is descriptive, not reliability or engineering throughput.
- First-red signatures group workflow path, job name, step name and numeric
  step ordinal, with source job/run/attempt IDs. Repeated signatures are
  correlated manifestations, not confirmed causal roots.
- Queue p95 uses job creation → job start. Workflow creation → job start is a
  different clock; fallback samples and under-20 samples are excluded from
  qualified cross-wave comparisons, while still retained in telemetry.
- The provider at authoring is gg_MATH main SHA
  d44b8e26818e4af9bbb02ec0d8369e57af3699bd.
  Provider kernels (kernels/uncertainty.py, stats_core.py, bt_uncertainty.py,
  pca_reference.py and pca_alignment.py) are reused rather than copied.

| Analysis | Required independent, matched evidence | Current |
|---|---|---|
| Descriptive workflow %, first-red signature recurrence | complete exact-source native run/job/step evidence | measurable |
| 90/95/99% fixed-horizon CI | independently sampled and calibrated series with declared estimator | NOT ESTIMATED |
| PCA/PC1 explained variance % | independent, comparable n × p multivariate waves; rank, eigengap, alignment | HOLD |
| Bradley–Terry win probability % | independently matched paired repair comparisons and graph connectivity | HOLD |
| ANOVA | replicated independent factor groups, variance/residual design | HOLD |
| MANOVA | full-rank multivariate group/residual geometry | HOLD |

A failure repeated across many CI runners does not create a population of
independent trials. Bootstrap, Wilson, parametric CI, PCA, BT, ANOVA and MANOVA
cannot acquire inferential credibility merely from job count. The consumer
intentionally emits null statistics with explicit reasons; gg_MATH alone owns
the executable mathematical inference after qualification.

## Repair and dependency DAG

ABACUS exact source → native run/job/attempt → ABACUS v2 producer →
Mission Control supporting projection → disjoint source-owned BD work →
exact-head negative/proof tests → separate A10/Safety/reviewer governance →
QPS owner-value only after independent acceptance.

Immediate non-statistical priority: #2033 test/ratchet sources,
#2026 Python 3.10 compatibility, then #2004/#2047 combined formatter/census
integration. Do not infer a merge or change branch protection to make a chart green.

**Invariant:** authority_transfer=false; merge_admission=HOLD;
qps_acceptance=DEFER; formal causal roots UNKNOWN; four-hop proof UNKNOWN.
