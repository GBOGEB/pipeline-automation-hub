# Mission Control RUN-i — scout, prove, scale

**Scope:** a small read-only decision adapter over the existing GOGREEN
`subtype_orchestrator.py` work-packet scheduler. Do not create a second SSOT,
invent a worker, rewrite queue telemetry, or let an HTML view confer authority.
Use `regime_controller.py` for repeated SAME-HEAD queue observations and
`flightdeck/pulses/reverse_pressure.py` for canonical owner pressure.

## Why scouts?

A **scout** discovers whether a correction can be applied safely to more
targets. Its measurable value is fewer wasted full CI runs, better first-red
attribution, reduced duplicated implementations, and a larger number of
verified reuse candidates per unit of effort. **Branches are an isolation
mechanism; they are not a KPI.**

| Environment | Valid work | Cannot claim |
|---|---|---|
| COLD_CLONE | pinned-source static lint, negative tests, dependency probes | native GitHub run, integration or persistent runner |
| SCOUT_BRANCH | disjoint trial fix and changed-file test contract | automatic merge or cross-repo closure |
| INTEGRATION_BRANCH | compatible recipes, exact-head combined CI | independent A10/security decision |
| MAIN_READONLY | observe accepted baseline and detect regressions | change protected main or experiment in production |

The **canonical repair owner** retains the source fix; scouts return evidence
and a patch proposal. The integration branch consumes source-linked candidates.
Mission Control consumes metrics; it does not cherry-pick or merge by itself.

## RUN-i contract: intent → evidence → halt or next scout

A run has explicit `N+i` identity, immutable before/after heads, UTC observation
times, workflow counts, a population digest only when justified, critical
first-red names, proposed source-owned packets, and any advisory scanner
observation. `scout_run_control.py` invokes the existing subtype scheduler.

**Stop / early halt:** if a critical enforcement workflow fails, the
first-red budget is exceeded, or a matched cohort regresses, **HALT MUTATING
FAN-OUT**. Read-only scouting can continue with max two planned slots.
Mismatch of head, schema, evidence grade or packet ownership fails closed.
This program does not cancel running GitHub jobs or GitHub Actions queues.

**DoD (Definition of Done):** syntax, focused negative tests, exact-head
source identity, all required native tests, source-owned patch, unresolved
first-red and disjoint worker ownership recorded. Planned packets alone are
only definition, not completed work.

**DoV (Definition of Value):** independent native proof on a matching head,
genuine causal-root reduction (not scanner occurrence elimination alone),
replicated compatible target evidence, reviewed security/A10, and a tangible
owner-usable outcome. Without it the state remains HOLD.

## Metrics and forecasting

| Metric | Baseline and ending measurement | Comparability |
|---|---|---|
| Workflow PASS/FAIL | observed status counts and observed run denominator | delta only on identical source population digest and terminal checks |
| YAML/Semgrep | findings, rules, scanned files and SARIF source | occurrence count, not engineering roots; advisory separate |
| Reuse reach | candidate PRs with exact SHA and owner | proposed reach, not successful repairs |
| First-red recovery | same failure predicate at before/after run/job | require independent matched native evidence |
| Queue p50/p95 and worker-minutes | runner timestamps / measured receipts | UNKNOWN until native job-level timing |
| Root closure / DoV | independent accepted causal root IDs | UNKNOWN without owner authorization |

The forecast is **conditional**, not a promise:
`expected_saved_ci_work = repeated_matrix_runs_avoided × observed_cost_per_matrix`
only when both factors are actually measured. A branch-count increase has no
positive economic value by itself.

Three bounded scouting waves should be:

1. **RUN-i SCOUT:** two read-only packets classify inherited formatting roots
   and YAML scanner findings; record first-reds, stable candidate IDs and
   source denominators.
2. **RUN-i+1 PROVE:** one owner-selected path-lease repair is tested cold,
   negative cases first; halt at any new critical red, head drift or waiver.
3. **RUN-i+2 SCALE:** prove an integration head, then broaden to two disjoint
   targets only after native terminal evidence and queue/resource stability.
   An unproven target goes back to scouting, not protected main.

## CLI and existing CI hook

```sh
python mission-control/gogreen/scout_run_control.py \
  --input /path/to/run_i_observations.json \
  --out /tmp/gogreen-run-i

python -m unittest discover -s mission-control/gogreen/tests -p 'test_scout_run_control.py' -v
```

The input embeds the existing `missioncontrol.cbd-subtype-plan.v1` packet
contract; see `tests/test_scout_run_control.py` for a **synthetic fixture**
modelled on the ABACUS #2047 21- vs 23-workflow cohorts. Those denominators
are **incomparable**. The existing `.github/workflows/gogreen-pulses.yml`
tests `mission-control/gogreen/**` on an exact PR head. Its real run/job
outcomes are needed before this adapter can claim native DoD.

The output comprises `scout_run.json`, a SHA-256 digest and a compact Markdown
review. No worker launches, detached background process, branch changes,
GitHub API calls or admission occur through the adapter.

## Security and evidence boundary

The ABACUS #2047 YAML Semgrep scan on exact
`821e4508df4cad1b777e8b3b5f6663f4940a4130`
observed 756 candidate findings over 160 files with 3 rules, in native run
`38908374433`. The SARIF artifact ID is `12049990712`. Existing
`continue-on-error: true` means a green workflow does **not** establish
a clean security finding population.

Never add the 756 YAML occurrences to the 1,009 broader Semgrep occurrences
as if they were disjoint roots. Deduplicate by artifact/rule/location/config,
then by independently accepted cause. Preserve statuses PASS/FAIL/UNKNOWN
and evidence class. No auto-merge, A10 waiver, Safety bypass, QPS acceptance,
Crew/REX authenticated worker assertion or PCA/Bradley–Terry inference.
