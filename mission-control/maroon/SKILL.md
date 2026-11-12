---
name: maroon
description: Run CODE MAROON on every open PR of GBOGEB, by hand or from the 8-hourly pulse. It scans every open PR's review threads into the private operations ledger and adds diagnosis hints (recurrence, history, false-positive signals, bot/fork no-push, group, one-method and fold-back proposals). It then plans a Kahn wave of disjoint roots, claims at most two, launches workers that fix or justify, and closes threads only with proof. Use when the user says "maroon", "run maroon", "code maroon", "fix review threads", "resolve open PR comments" or "unblock PR merges", or when the MAROON pulse fires. Optional argument "dry" (scan, hints and plan only) or a repo list.
---

# CODE MAROON run

The contract is `mission-control/maroon/OPERATIONS.md` (owner: `operations.py`, `closure.py`). This skill
only sequences it and adds `hints.py`. When the two disagree, OPERATIONS.md wins.

## 0. Set up

- Use a pipeline-automation-hub checkout. Run `git status --porcelain` and `git reflog -3` first. If a
  session is live there, `git worktree add` your own. Then `git fetch` and fast-forward.
- Clear stale tokens for every `gh` call: `unset GITHUB_TOKEN GH_TOKEN`. In PowerShell:
  `Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue`.
- `operations.py` uses `fcntl`, so it needs Linux, macOS or WSL. On native Windows it fails at import:
  run it in WSL or stop and report.
- Private paths: ledger `~/.maroon/MAROON_OPERATIONS.json`, pulse output `~/.maroon/pulses/<pulse id>/`.
  The pulse id is unique per run, for example `P<UTC yyyymmddThhmm>`.

## 1. Intake, hints, plan

```bash
python mission-control/maroon/operations.py --ledger ~/.maroon/MAROON_OPERATIONS.json scan --repos <scope> --pulse <id>
python mission-control/maroon/hints.py --ledger ~/.maroon/MAROON_OPERATIONS.json --out ~/.maroon/pulses/<id> --check-heads
python mission-control/maroon/operations.py --ledger ~/.maroon/MAROON_OPERATIONS.json plan --workers 2
```

The scope is the standing scope in OPERATIONS.md, unless the user named repositories. Read
`MAROON_HINTS.md` and the plan's `ready`, `held` and `admission_reasons`. A gap is UNKNOWN, never zero.
With `dry`, stop here and report.

## 2. Group what the hints prove is one treatment

A `GROUP_FINDINGS` proposal is a candidate only. Read the source at the head. When one treatment covers
every member, call `operations.group_findings(...)` with that method and the proof refs. Plan again.

## 3. Claim and launch workers

For each ready root, up to `available_slots` (never more than 2):

1. Claim it: `operations.py claim --root <id> --worker <name>`.
2. Spawn one background Agent. Its prompt is the claimed packet, the hints for its members, and the
   OPERATIONS.md stages (diagnose, treat, verify, publish, reply, resolve, readback, close, REX). Rules:
   - work in its own worktree;
   - make the expected-head check before every write;
   - push without force;
   - never write to a branch with a `NO_PUSH_*` hint;
   - re-run the JADE generator on `PINNED_OID` paths;
   - never merge or approve.
3. Close threads only through `resolve_answered.py --proofs <private proofs.json> --ledger <ledger> --apply`,
   with `code_maroon.closure-proof.v1` proofs that the worker actually produced.
4. Check each worker's commits and readback on GitHub before you report them.

## 4. Report and fold back

Report:
- threads closed with proof;
- commits per PR;
- roots held, and why;
- `HUMAN_PENDING` or owner decisions;
- the top `SYSTEMIC` and `RECURRING` findings.

For each `FOLD_BACK`, open or list one method PR and record `Method fold-back: <finding> -> <PR>`.

## Never

- Merge, enable auto-merge, approve, or dismiss a review or alert.
- Resolve a thread without its proof.
- Push with force, or to a fork or bot branch.
- Run more workers than OPERATIONS.md and the CREW ceiling allow.
