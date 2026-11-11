# PR intervention experiments

`pr_intervention.py` answers one question per experiment: does acting on stale PRs unblock them more
often than leaving them alone? It applies an intervention to a random part of the eligible PRs,
keeps the rest as a holdout group, and compares the two groups after CI has had time to run.

Slice 1 has one intervention: bring the PR branch up to date with its base branch (GitHub
update-branch). Later slices add more levels (see [Ladder](#ladder)).

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

## What is measured

- **Before and after state per PR.** The CI checks (latest run per check) and the gate checks
  (`first-pass-closure`) are judged apart. A red gate means a missing receipt, not broken code.
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

- `DELIVERED_BY_UPDATE`: our update was the only change to its head. The update delivered fixes
  that already sat on the base branch, so the candidate root fixes are the base commits from the PR's
  merge base onward.
- `EXTERNAL`: its head did not change. Something outside the PR fixed it: a rerun, a base change, or
  a commit in another repository.
- `AUTHOR_PUSH`: someone pushed to the branch, so the effect is confounded.

Candidate commits are ranked by how many files they share with the PR. A candidate is never a
proven root fix (`proof: CANDIDATE_NOT_PROVEN`).

## Ladder

| Level | Intervention | Slice | Owner of the decision |
|---|---|---|---|
| L0 | Observe only (A/A test) | 1 | this tool |
| L1 | Update branch (merge; `--method rebase` opt-in) | 1 | this tool |
| L2 | Rerun failed jobs | 2 | `rerun_triage.plan()` (`RERUN_FAILED_JOBS_CANDIDATE`) |
| L3 | Debug rerun, observed as an LDAB `debug_receipt` at `REPORTED_UNVERIFIED` | 2 | `rerun_triage.plan()` (`DEBUG_RERUN_CANDIDATE`), ABACUS LDAB contract |
| L4 | Agent fix proposal PR (never merged automatically) | 3 | owner review |

Slice 3 also adds attribution across repositories (census pinned blob ids) and per-stratum policy:
level by workflow class, change size, DAG depth and failure type. Until then LDAB, Actions minutes
and cross-repository attribution are `UNKNOWN` in every record.
