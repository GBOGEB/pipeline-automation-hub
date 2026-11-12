# PR intervention experiments

`pr_intervention.py` answers one question per experiment: does acting on stale PRs unblock them more
often than leaving them alone? It applies an intervention to a random part of the eligible PRs,
keeps the rest as a holdout group, and compares the two groups after CI has had time to run.

Each experiment applies one intervention, chosen with `--intervention` on `before`:

- `update` (default): bring the PR branch up to date with its base branch (GitHub update-branch).
- `rerun`: rerun the failed jobs of the newest failed run on the PR's exact head.
- `debug-rerun`: the same rerun with runner and step debug logging.

For the two rerun levels, `rerun_triage.plan()` decides per PR and the tool follows it exactly
(see [Rerun levels](#rerun-levels)). `--gate-check` (repeatable) names checks that are judged as
gates rather than CI, for example `--gate-check "PR Feedback Gate"` on ABACUS.

## Run it

Start every PowerShell 7 window with
`Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue`, then:

```powershell
Set-Location "<pipeline-automation-hub checkout>"
python mission-control/gogreen/pr_intervention.py before --repo GBOGEB/pipeline-automation-hub
python mission-control/gogreen/pr_intervention.py act --experiment PRX-<id>            # dry run
python mission-control/gogreen/pr_intervention.py act --experiment PRX-<id> --apply    # writes to GitHub
# wait for CI; optionally take a fresh census pulse first:
python mission-control/gogreen/scale_dock_series.py pulse
python mission-control/gogreen/pr_intervention.py after --experiment PRX-<id> --min-hours 6
python mission-control/gogreen/pr_intervention.py report --experiment PRX-<id> --out report.md
```

`after` can run several times (for example at 6 h, 24 h and 72 h). Running `after` without `act`
gives an A/A test: both groups are untouched, so the effect should be zero within its interval.
Run one before trusting a real result.

Run it from a workstation with your `gh` login, not from Actions. Commits pushed with an Actions
`GITHUB_TOKEN` do not start `pull_request` workflows, so CI would never run on the updated branch.

## Eligibility

A PR is eligible only when none of these hold. Each reason is recorded per PR.

| Reason | Why the PR is left out |
|---|---|
| `DRAFT` | Not ready for CI spend |
| `FORK` | The branch is in another repository |
| `STACKED` | Its base is not the default branch; use `gh stack sync` (PR_CONFLICT_RUNBOOK section 3) |
| `YOUNG` | Younger than `--min-age-days` (default 7) |
| `CURRENT` / `BEHIND_UNKNOWN` | Not behind its base, or the compare could not be read |
| `CONFLICT` | update-branch cannot resolve conflicts; resolve them hunk by hunk (runbook section 2) |
| `RECENT_PUSH` / `PUSH_TIME_UNKNOWN` | Head commit newer than `--quiet-hours` (default 24): a live session may own the branch |
| `OPT_OUT_LABEL` | Labelled `no-auto-update` or `do-not-rebase` |

Eligible PRs are split by `sha256(experiment | repo#number | head SHA)`. That makes the split
reproducible from the ledger alone; nobody picks which PRs get treated.

`act` reads each treated PR again immediately before writing. Labels, draft state, base branch and
conflicts can change after `before` without moving the head, so any of them, or a moved head, skips
the write (`OPT_OUT_LABEL`, `DRAFT`, `BASE_CHANGED`, `CONFLICT`, `HEAD_MOVED`, `NOT_OPEN`). After an
accepted update, `act` reads back the exact head it produced. For a merge update, that head must have the
recorded head as its first parent. It is stored as `new_head`.

## What is measured

- **Before and after state per PR.** The CI checks (latest run per check) and the gate checks
  (`first-pass-closure`, as a check run or as a `<workflow> / first-pass-closure` commit status) are
  judged apart. A red gate means a missing receipt, not broken code. A check whose latest run was
  cancelled counts as pending, never as green.
- **Outcome.** Green or merged is a success. Red, or closed without merging, is a known non-success
  (`CLOSED_UNMERGED` is counted in the denominator, not dropped). Pending or unreadable is unknown.
- **Effect.** The rate of PRs that are green or merged in the treated group minus that rate in the
  holdout group, by intention to treat, with a Newcombe hybrid score 95% interval. The same is
  computed for PRs that were red before (unblocked rate). If either group has fewer than
  `--min-arm` (default 5) known outcomes, the effect is `UNKNOWN`, not zero.
- **Costs.** Regressions (green before, red after), author pushes during the window, gate checks
  that turned red, and `fpc_receipts_invalidated`. Every accepted update moves the head, so the PR's
  First-Pass Closure receipt must be written again.
- **Census context.** The latest scale-dock pulse at `before` and at `after`, with its RED-job delta
  per repo. If both read the same pulse, the delta is `SAME_PULSE`.

## Butterflies (positive transitions)

Any PR that turns green, merges or loses its conflict counts as a positive transition, whether or not
it was eligible. It is attributed as:

- `DELIVERED_BY_UPDATE`: the head is exactly the one our update produced (`new_head`). If that head
  was not read back, the PR still qualifies when its head is a two-parent merge commit whose first
  parent is the recorded head. The update delivered fixes that already sat on the base branch, so the
  candidate root fixes are the base commits from the PR's merge base onward.
- `EXTERNAL`: its head did not change. Something outside the PR fixed it: a rerun, a base change, or
  a commit in another repository.
- `AUTHOR_PUSH`: someone pushed to the branch, so the effect is confounded. A force-push that keeps
  the commit count still counts, because heads are compared by SHA.
- `UNVERIFIED`: the update was accepted but its head could not be confirmed (for example a rebase
  that was not read back).

Candidate commits are ranked by how many files they share with the PR. A candidate is never a
proven root fix (`proof: CANDIDATE_NOT_PROVEN`).

## Ladder

| Level | Intervention | Slice | Owner of the decision |
|---|---|---|---|
| L0 | Observe only (A/A test) | 1 | this tool |
| L1 | Update branch (merge; `--method rebase` opt-in) | 1 | this tool |
| L2 | Rerun failed jobs (`--intervention rerun`) | 2 | `rerun_triage.plan()` (`RERUN_FAILED_JOBS_CANDIDATE`) |
| L3 | Debug rerun (`--intervention debug-rerun`), observed as an LDAB `debug_receipt` at `REPORTED_UNVERIFIED` | 2 | `rerun_triage.plan()` (`DEBUG_RERUN_CANDIDATE`), `bd_ldab_consumer.check_observation()` |
| L4 | Agent fix proposal PR (never merged automatically) | 3 | owner review |

Slice 3 adds attribution across repositories (census pinned blob ids) and per-stratum policy:
level by workflow class, change size, DAG depth and failure type. Until then Actions minutes and
cross-repository attribution are `UNKNOWN` in every record.

## Rerun levels

`before` builds one `rerun_triage` snapshot per repository. For each PR it takes the newest completed
run on the exact head (failed runs first). It classifies the run from GitHub job metadata only (no log
download, `classifier: job_metadata_v1`). `gh run rerun --failed` reruns every failed job of the run,
so the classifier looks at all failed jobs and takes the most actionable one:

| Failed jobs of the run | `failure_kind` | `logs_insufficient` | Usual triage decision |
|---|---|---|---|
| Any failed job has a failed step | `UNCLASSIFIED` | false | `INSPECT_FIRSTRED` |
| Every failed job ran no step (lost its runner) | `TRANSIENT`, cause `runner_lost` | false | `RERUN_FAILED_JOBS_CANDIDATE` |
| Otherwise (failed jobs ran steps, none failed) | `UNCLASSIFIED` | true | `DEBUG_RERUN_CANDIDATE` |
| Run succeeded | `NONE` | false | `EVALUATE_INDEPENDENT_GATES` |

`rerun_triage` decides, in its own order: a PR behind its base is `RECONCILE_MAIN` (the `update`
level's job), a second attempt is `RETRY_EXHAUSTED`, and so on. Only `RERUN_FAILED_JOBS_CANDIDATE`
PRs are eligible for `rerun`, and only `DEBUG_RERUN_CANDIDATE` PRs for `debug-rerun`. Every other
PR records `TRIAGE_<decision>` as its reason. To change those rules, change `rerun_triage.py` in a PR
of its own (AGENTS.md L4).

`act` reruns failed jobs only (`gh run rerun <id> --failed`, plus `--debug` at L3). It goes ahead only
if the run is still the same completed, failed attempt that triage judged; otherwise it records
`RUN_MOVED`. A rerun keeps the head, so it does not invalidate FPC receipts.

`after` reads each rerun's attempt and conclusion, bound to the attempt our rerun dispatched (the
recorded attempt + 1). If someone reran the run again after us, the run is
`DISPATCHED_ATTEMPT_UNIDENTIFIABLE`: its conclusion is not reported as ours and a green PR is
attributed `UNVERIFIED`. For `debug-rerun` on ABACUS or CODEX, the dispatched attempt's own jobs
become an LDAB `debug_receipt` observation, validated by `bd_ldab_consumer.check_observation()`:
`proof_level: REPORTED_UNVERIFIED`, `real_probe_steps: 0`. Actions debug logging is not a debugger
session. Other repositories record `NOT_IN_LDAB_SCOPE`. A PR that turns green with an unchanged head
after our accepted rerun is attributed `DELIVERED_BY_RERUN`.
