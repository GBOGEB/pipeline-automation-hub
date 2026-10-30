# B09 canonical recheck-pressure telemetry — first measured goal producer

## Intent and source authority

The only recheck run-record share computation belongs to `mission-control/jade_temple/devops/actions_metrics.py` (existing JADE owner). The independent RF matrix adapter in PR #1010 only checks a supplied threshold and cannot invent the metric or authorize an admission. This branch is stacked on PR #998's first-red repair; #994 remains the distinct owner of recheck selector/recovery behavior.

## T0 / planned T1

- T0 snapshot from the 28 Oct 2026 source-bound CI-spine audit: 363/1,000 recent repository workflow-run records named `GOGREEN Required Gate Re-check`, 278 cancelled. The ratio 0.363 is event pressure, not billed time, CI test results or causal-root closures.
- Pilot goal (advisory): no more than 0.20 recheck-record share among the **most recent 1,000** complete repository workflow runs. A missing or smaller sample does not become zero: it is `PARTIAL_UNKNOWN` with `value: null`.
- Every new T1 requires the captured collector repository default-head SHA, observation time, exact source path, fixed sample identity and a reproducible JSON SHA-256. Historical runs in the sample can have DIFFERENT original head SHAs; the collector head is only a measurement-pulse identity.
- Changed production recheck triggers are NOT in this PR. No T1 reduction, queue saving or billed-minute improvement has yet been achieved or claimed.

## Read-only command line

First obtain the **default-branch master SHA once**, using a GitHub connection with read permission. On Windows remove stale `GITHUB_TOKEN`/`GH_TOKEN` environment variables before invoking `gh`. Then run the canonical collector and, after its cached readback succeeds:

```bash
python mission-control/jade_temple/devops/actions_metrics.py fetch \
  --cache /tmp/jade-actions --since 2026-10-29 --until 2026-10-30 \
  --repo GBOGEB/pipeline-automation-hub --job-budget 100
python mission-control/jade_temple/devops/actions_metrics.py pressure \
  --cache /tmp/jade-actions --since 2026-10-29 --until 2026-10-30 \
  --repo GBOGEB/pipeline-automation-hub --source-sha <EXACT_MASTER_SHA> \
  --out /tmp/recheck-pressure.json
```

**P1 observation-window guard:** the `--until` date must reach the current observation UTC date (30 Oct for this shown example); substitute the actual UTC date on later runs. A historical window that ends before that date is `PARTIAL_UNKNOWN`, even if it contains 1,000 older records. The cache must also have actually been refreshed; a local file alone cannot independently attest that no newer runs exist. `pressure` uses only existing cache files and makes **no** API or credential calls. Existing `fetch` enforces the daily/hourly pagination saturation fail-closed, which is intentionally not overridden. If a source window is missing or contains fewer than 1,000 records, leave the observed value NULL and collect more evidence. Never backfill with synthetic successes.

To evaluate the target with RF N+1, pass the actual `pressure` JSON as `--observation /tmp/recheck-pressure.json` to `mission-control/jade_temple/tools/rf_matrix_wave.py` using the SAME source SHA. The adapter can return `TARGET_REACHED_UNVERIFIED` and recommends independent review; that is not a GitHub acceptance predicate. Its goal only matches the proposed same-method cohort.

## Negative evidence and ownership

16 focused tests prove fixed denominator, 363/1,000, cancellation identity, duplicate exclusion, future timestamp rejection, malformed source, name/event semantics, order-independent SHA, partial/empty unknown, completed-runs-only cohort, missing source-day cache files kept unknown, a receipt hash bound to the cohort's run identities (`cohort_sha256`), and no-token CLI projection. Existing Actions Metrics tests and their job clock/cost functions remain authoritative and unchanged outside this scoped addition.

## DoV and wave progression

- [ ] Parent #998 independently reviewed/qualified; exact-head original JADE CI green.
- [ ] This source owner's full test population and coverage are green on the final exact head.
- [ ] Compare T0 and T1 using the identical last-1,000-run cohort definition and source readback.
- [ ] Confirm recovery of genuine red gates, first-red recurrence, job-seconds and cancellation separately; reduce redundant runs without dropping required tests.
- [ ] If the target is not met, issue a new bounded RF pulse with previous source and T1 receipt; if a trusted observed target is met, STOP for independent review, never auto-merge.

**No cache, workflow trigger, branch rule, ADMISSION, security permission, artifact release or autonomous runner change in this PR.**
