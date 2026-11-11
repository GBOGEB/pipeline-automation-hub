# Unsticking conflicted and stacked PRs

Method lessons from the 2026-11-09 pass over all open GBOGEB PRs. Use them together with
`Invoke-DraftPrPass.ps1` (triage), `Resolve-RegenConflicts.ps1` (generated outputs) and
`scripts/fpc_receipt.py` (FPC gate). Start every PowerShell 7 window with:

```powershell
Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue
```

## 1. Triage

```powershell
Set-Location "<pipeline-automation-hub checkout>"
pwsh -NoProfile -Command "& ./tools/workstation/Invoke-DraftPrPass.ps1 -Repo ABACUS,pipeline-automation-hub,cryoplant-project,GEMINI -IncludeReady"
```

Pass several repos through `-Command`. Under `-File` the comma list reaches `-Repo` as one string,
and gh fails with "Could not resolve to a Repository".

## 2. Resolve conflicts hunk by hunk, never file by file

`git checkout --theirs <file>` (or `--ours`) takes that side's **whole file**. Every
non-conflicting change the other side made to the same file is silently dropped. On
2026-11-09 that removed a PR's new test from `test_workflow_policy.py`; the tests still passed.

- Before resolving, list what the PR changed in each conflicted file:
  `git diff $(git merge-base origin/main <head>) <head> -- <file>`.
- Edit only the `<<<<<<< … >>>>>>>` blocks. To restore the markers after a wrong pick, run
  `git checkout -m -- <file>`.
- If main already landed the same fix, take main's side for that hunk and adapt the PR's test to
  main's version rather than re-implementing it.
- Generated files (for example ABACUS `docs/ci/WORKFLOW_RATIONALIZATION.md` from
  `ci/governance/audit_ci_workflows.py`): take either side, then re-run the generator and its
  `--check`.
- Check whether a PR is still needed. If its diff against main is empty after resolving, main has
  absorbed it: close it instead of pushing an empty merge.

## 3. GitHub-native stacks (`gh stack`)

A PR in a GitHub stack cannot be retargeted. `gh pr edit --base` fails with
"Cannot change the base branch because the pull request is part of a stack".
When the bottom PR is obsolete:

```powershell
gh stack checkout <top PR number>
gh stack view --json
gh stack unstack <stack number>
gh pr edit <top PR> --base main
gh pr close <bottom PR> --comment "Superseded: ..."
```

`gh stack checkout` prints the stack number. Close the bottom PR only **after** the retarget.
Deleting a base branch closes every PR stacked on it.

When the bottom is still wanted, run `gh stack sync`. It rebases and pushes with
`--force-with-lease`, so run it only when Invoke-DraftPrPass shows no `LIVE` session on those
branches. A stack whose PRs have no conflicts but stay `BLOCKED` is usually red only on the
First-Pass Closure gate (`FINAL_RECEIPT_STATUS_NOT_PASS`): write the receipt (section 4).

## 4. FPC receipts

```powershell
python scripts/fpc_receipt.py --pr <N> --repo GBOGEB/pipeline-automation-hub --dry-run
python scripts/fpc_receipt.py --pr <N> --repo GBOGEB/pipeline-automation-hub --write
```

Run `--write` only once the dry-run lists `required_runs`. `INCOMPLETE` means the
"First-Pass Closure Proof" workflow has not run on that exact head yet.

A sparse checkout of this repo that holds only `tools/workstation` cannot run it. The script
needs `scripts/` and the policy in `mission-control/quality/`:

```powershell
git sparse-checkout add scripts mission-control/quality
```

## 5. Hooks on merge-from-main commits

A repo pre-commit hook that scans `--staged` files sees **every file main changed** when you
commit a merge from main. ABACUS `a10_guard.py` blocks on files already on main, and hangs on
very large merges. Run the CI form (`python tools/a10_guard.py --diff origin/main`). If it is OK,
commit that merge with `--no-verify` only with the owner's approval, and say so in the commit
message.
