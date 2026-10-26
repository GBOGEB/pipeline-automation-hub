# JADE FOCUS5 Actions usage + performance metrics — reading (2026-10-01 .. 2026-10-26)

Source: `data/ACTIONS_METRICS_FOCUS5.json` (`jade.devops.actions-metrics.v1`), observed `2026-10-26T11:35:37Z`.
Sortable per-workflow table: `site/actions_metrics.csv` (773 rows, one per repo × workflow; same columns as the
two GitHub Insights pages plus class, band, event, coverage and blob OID).
Producer: `devops/actions_metrics.py` (owner in AGENTS.md *Metric ownership*). The private repo is aggregate-only
(`tools/private_boundary.py`).

## How to read the numbers

* **Run tier = full coverage.** Every run created in the period: runs, run failure / cancel / rerun rate,
  run wall time, trigger event.
* **Job tier = sample.** Job lists were read for 38.8 % of fleet runs, round-robin over (ISO week × workflow).
  Columns without a prefix are **observed** over that sample; `est_*` scales each workflow by its own coverage
  (stratified estimator) and is an **estimate**.
* **Binding.** Each repo carries the default-head SHA read at projection time. `same_pulse` compares it to
  `DEVOPS_CENSUS_N11.json`: only gg_MATH is equal. The census is a day older for the others, so a census
  re-pulse is needed before the two are joined (AGENTS.md L5).

## Per repo and fleet total

| repo | runs | run fail % | cancel % | job coverage | est. job runs | est. billable min | job fail % (est.) | est. failed-job min | job run p50 / mean | job queue p50 / mean / p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| pipeline-automation-hub | 16,840 | 10.4 | 5.5 | 0.34 | 19,001 | 29,045 | 9.5 | 2,305 | 13 s / 37 s | 3 s / 5 m 01 s / 30 m 36 s |
| cryoplant-project (private, aggregate) | 9,739 | 16.7 | 4.2 | 0.44 | 14,584 | 20,250 | 16.4 | 5,564 | 11 s / 42 s | 3 s / 41 s / 3 m 20 s |
| gg_MATH | 475 | 4.0 | 2.5 | 1.00 | 562 | 644 | 5.9 | 46 | 8 s / 27 s | 69 s / 14 m 35 s / 49 m 17 s |
| DOCX_RTM_Automation | 145 | 17.9 | 3.4 | 1.00 | 167 | 219 | 16.2 | 27 | 9 s / 38 s | 67 s / 6 m 15 s / 21 m 41 s |
| yaml-grammar | 2 | 0.0 | 0.0 | 1.00 | 2 | 2 | 0.0 | 0 | 6 s | 2 s |
| **FOCUS5 total** | **27,201** | **12.6** | **5.0** | **0.39** | **34,316** | **50,160** | — | **7,942** | 12 s / 39 s | 3 s / 3 m 33 s / 24 m 34 s |

### Cross-check against the GitHub Insights pages (pipeline-automation-hub, current month)

| metric | Insights | this producer | verdict |
|---|---:|---:|---|
| total job runs | 18,046 | 19,001 (est.) | agrees within 5 % (our window runs a few hours later) |
| job failure rate | 9 % | 9.5 % (est.) | agrees |
| avg job run time | 34 s | 37 s observed / 50 s est. | agrees on the observed sample |
| failed job usage | 1,839 min | 2,305 min (est.) | +25 %, sampling error on a few heavy workflows |
| total minutes | 21,991 | 29,045 (est.) | **+32 %**: driven by `Push on master` (CodeQL, 9.9 % coverage, est. 7,107 vs Insights 5,277) |
| avg job queue time | 20 m 20 s | 5 m 01 s observed | **not reproduced**. REST job `created_at -> started_at` gives a much shorter queue. Insights probably measures queueing differently, or its mean is dominated by the 15–18 Oct storm, which the sample under-weights. Open item. |

Run-tier figures are exact. Treat job-tier minutes and queue as indicative until coverage rises or until the
Insights CSV export is imported as a second source.

## What the groupings already say

**1. A mid-October storm, not a steady load.** Fleet runs per ISO week: W40 882, W41 1,158, **W42 11,156**,
**W43 9,977**, W44 (2 days) 4,028. Hub peak day: 17 Oct, 3,149 runs. Failed runs peak in W43 (1,760). The queue
tail sits in the same window. Rank by week before ranking by workflow, otherwise the storm reads as a property
of whichever workflows happened to run then.

**2. Volume is concentrated in a few always-on PR workflows.** Hub runs by trigger: pull_request 7,646, push
4,734, pull_request_target 1,395, dynamic 1,357, workflow_run 989, schedule 449. On every PR event,
`W3-16 M03 W0 Recon` and `QPS TRIAGE ULTRA Federation Control` run about 1,230 times each, and `Zero-Test Gate
Guard` about 1,020 times. The first two fail almost never (< 0.5 %). On push, about ten `GM-FLEET-03 / W3-1x`
pilot workflows run about 328 times each and never fail. That means high run count, near-zero signal: the
first candidates for path filters or a merged dispatcher.

**3. One gate carries most of the red.** `pull_request_target` is a single workflow, `First-Pass Closure Gate`:
1,567 runs, **75.6 % job failure**, 45 % of runs skipped. That is the red the AGENTS.md "red means stop"
lesson is about. It is red by design until the PR-body receipt is filled. Count it as *gate state*, not
*CI health*, in any failure metric.

**4. Class (role) groupings, fleet, observed sample.**

| class | workflows | runs | job fail % | min / run |
|---|---:|---:|---:|---:|
| GATE | 47 | 7,243 | 12.6 | 0.56 |
| CENSUS_TELEMETRY | 47 | 6,872 | 10.3 | 0.49 |
| OTHER (unclassified) | 163 | 6,107 | 12.3 | 0.91 |
| TEST_QA | 39 | 2,401 | **19.7** | 1.09 |
| EXPERIMENT_PROBE | 57 | 2,401 | 7.9 | 0.92 |
| SECURITY | 405 | 1,355 | **2.3** | 1.27 |
| BUILD_DEPLOY | 13 | 805 | 11.5 | 1.30 |

Gates plus census/telemetry are 52 % of all runs, yet cost about half a minute each: cheap per run, dear in
aggregate. TEST_QA fails most. SECURITY is the most reliable class. Its 405 "workflows" are mostly Dependabot
dynamic runs, each with a unique name ("pip in /x – Update #…"), so group them by `path` rather than by name.
163 workflows are still OTHER: extend the class rules in `CLASSES` (the code) rather than tagging by hand.

**5. Duration band predicts failure.** Mean job run time band vs job failure rate (fleet): < 10 s 5.3 %,
10 s–1 m 12.5 %, 1–5 m 15.5 %, **5–15 m 27.5 %**. Nine long workflows (110 runs) cost 10.8 min per run.
In the hub they are `Running Copilot Code Review` (13 m, 31.6 % fail), `Push on master` CodeQL (5 m),
`GOGREEN Red-Trace Ledger` (4.9 m), `GOGREEN Federation Spine` (3.4 m, 17.6 %), `CODE PURPLE Method Atlas`
(2.7 m) and `GOGREEN Required Gate` (2.5 m, 24.5 % job fail). This matches the Insights performance page
sorted by *Avg run time*: long jobs are where failed minutes accumulate.

**6. Queue is a tail problem, located in a few lanes.** The fleet median job queue is 3 s, and p95 is
24.6 min. The worst hub lanes: `MissionControl gg_MATH convergence read-only` (mean 46 min, p95 3.2 h,
90 jobs), the four `MCEX-W1 stage-only factorial branch` lanes (p95 ≈ 3.3 h) and `CBD Subtype Worker
Orchestrator` (30 min). These are fan-out lanes queued behind the hosted-runner concurrency limit. gg_MATH and
DOCX_RTM_Automation have higher median queue (≈ 70 s) than the hub (3 s), even at tiny volume. They wait for
the shared account's runners while the hub storms.

**7. Schedules are few but heavy.** 538 scheduled runs (5 workflows) cost 3.4 min per run, the highest of
any trigger. `CODE PURPLE Disjoint Live Census` fails 46.6 % of its runs. A scheduled red with no PR to
block is invisible unless it is surfaced, so it belongs on the EVERRED / red-trace watch list.

**8. Data hygiene.** One hub workflow surfaces under its file path instead of a name:
`.github/workflows/code-purple-m3-lossless.yml`, 22/22 runs failed. A path instead of a name usually means
GitHub could not parse the file, so it would fail at startup on every push. That is not yet confirmed. yaml-grammar ran twice in the window, so its census lifecycle stages are not
exercised by CI.

## Next pulses

1. Run `fetch` again after each API reset. The cache keeps all completed job lists, and coverage
   (now 0.34 hub / 0.44 cryoplant) rises toward 1.0 without re-reading anything.
2. Re-pulse the DevOps census so `same_pulse` can turn true, then join census stages to these rows by repo.
3. Import the Insights CSV export (download icon on both pages) as a second source to close the queue-time gap.
4. Add a scheduled `fetch` + `project` to the weekly census refresh, with an `actions/cache` for the run/job
   cache. Today the job runs only the offline tests.
