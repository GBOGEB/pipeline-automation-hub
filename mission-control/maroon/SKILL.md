---
name: maroon
description: Run CODE MAROON on every open PR of GBOGEB. It reads all unresolved review threads, resolves those whose fix is already proven, and plans the rest as a Kahn DAG of disjoint worker actions: one worker per PR branch, one per finding repeated across PRs, one fold-back per systemic finding. It then launches the workers and resolves what they answered. Use when the user says "maroon", "run maroon", "code maroon", "fix review threads", "resolve open PR comments", "unblock PR merges", or when the 8-hourly MAROON pulse fires. Optional argument "dry" (plan only, write nothing), "act" (resolve only, no workers) or a repo list.
---

# CODE MAROON pulse

Source of truth: `mission-control/maroon/SKILL.md` in pipeline-automation-hub. Method details:
`mission-control/maroon/README.md`, section "Open-PR pulse".

## 0. Set up (every run)

- Find a pipeline-automation-hub checkout on `origin/master` (or the MAROON PR branch until it merges).
  Follow the worktree rule: check `git status --porcelain` and `git reflog -3` before you use it. If another
  session is live there, `git worktree add` your own. Then `git fetch` and fast-forward.
- Clear stale tokens for every `gh` call: `unset GITHUB_TOKEN GH_TOKEN` (bash), or
  `Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue` (PowerShell).
- Keep private data out of every repository. Ledger: `~/.maroon/MAROON_LEDGER.json`. Pulse output:
  `~/.maroon/pulses/<UTC yyyymmddThhmm>/`.

## 1. Read and plan (always)

```bash
python mission-control/maroon/pulse.py run --owner GBOGEB --ledger ~/.maroon/MAROON_LEDGER.json --out ~/.maroon/pulses/<stamp>
```

Read `MAROON_PULSE.md`: verdict counts, waves, ready nodes, recurring findings and gaps. A gap is a
read that failed: never report it as zero. With the argument `dry`, stop here and report.

## 2. Resolve what is already proven

```bash
python mission-control/maroon/pulse.py act --plan ~/.maroon/pulses/<stamp>/MAROON_PULSE_PLAN.json --ledger ~/.maroon/MAROON_LEDGER.json --apply
```

High-confidence verdicts only (`ANSWERED`, `SUGGESTION_APPLIED`, `OUT_OF_SCOPE`). Add `--include-medium`
(`FP_HISTORY`) only when the user asks. With the argument `act`, stop after this step and report.

## 3. Launch the workers for the ready wave

For each file in `briefs/` (at most 4 at once; the scheduled run: at most 3):

1. `python mission-control/maroon/pulse.py done --ledger <ledger> --node <id> --status DISPATCHED`
2. Spawn one background Agent (general-purpose). Its prompt is the brief, verbatim, plus where the
   target repository's local clone is. The brief's contract is binding:
   - own worktree, and stop with `HEAD_MOVED` if the head is not the one in the brief;
   - deep-read before fixing;
   - push without force;
   - reply `Fixed in <sha>.` or `Kept as is: <reason>`;
   - write the first-pass-closure receipt again;
   - never merge, approve or resolve.
3. When a worker reports `MAROON_WORKER=DONE|FAILED node=<id> ...`, record it with `pulse.py done`.
   Check its commits on GitHub first: a worker's report is not proof.

Nodes in one wave never write the same branch, so they run in parallel. Later waves wait for the next
pulse (or run them now, one wave at a time, after re-planning).

## 4. Close

After the workers, run step 1 again, then step 2 again: the workers' replies now read as `ANSWERED`,
and `close` nodes resolve them. Report:
- threads resolved;
- commits pushed per PR;
- nodes `FAILED` or `BLOCKED` (these go to the owner);
- PRs whose only remaining blocker is `HUMAN_PENDING`;
- the top recurring findings.

## 5. Method fold-back

A `fold:` node means a finding hit three or more PRs. Its worker opens one PR that stops the recurrence:
a test, lint rule, gate rule, AGENTS.md pitfall or skill line. List each one in the close-out as
`Method fold-back: <finding> -> <PR>`.

## Never

- Merge, enable auto-merge, approve, or dismiss a review.
- Push to a fork, a Dependabot or Renovate branch, or with `--force`.
- Resolve a thread whose last word is a person's (`HUMAN_PENDING`).
- Run `act --apply` from a plan older than the current heads: the moved-head check skips those writes,
  but re-plan anyway.
