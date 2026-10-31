# Workstation audit runner

`Invoke-WorkspaceAudit.ps1` is a recurring check for the owner's Windows workstation. It turns three CI lessons into one report:

| Lesson | What the audit does |
| --- | --- |
| L5: push branches early | Marks a repo or worktree **PUSH-ME** when it has commits that are on no remote (or it is ahead of its upstream) and the oldest of them is older than `-PushAfterHours` (default 4). |
| L8: stale `GITHUB_TOKEN` | Reports `GITHUB_TOKEN` / `GH_TOKEN` at Process, User and Machine scope, tests each value with `gh api user`, and compares the result with the `gh` keyring login. It prints the command that removes the token. It never runs that command. |
| L9: C: is tight | Measures every git repo or worktree directly under `-Root`, classifies each one, and adds up the space that removing the **REMOVABLE** entries would free. |

The script needs PowerShell 7 (`pwsh`), `git` and `gh`. It installs nothing. Every `gh` call runs in a child process without `GITHUB_TOKEN`/`GH_TOKEN`, so the keyring login works even while a stale token is still set. The script's own environment is never changed.

## Run it

```powershell
# Report only (the default). Writes a table, then a JSON file to $env:TEMP.
pwsh -NoProfile -File tools\workstation\Invoke-WorkspaceAudit.ps1

# Choose the root, the threshold or the report folder
pwsh -NoProfile -File tools\workstation\Invoke-WorkspaceAudit.ps1 -Root D:\work -PushAfterHours 8 -ReportPath $env:LOCALAPPDATA\workspace-audit

# Faster run without measuring sizes, or without the token check
pwsh -NoProfile -File tools\workstation\Invoke-WorkspaceAudit.ps1 -SkipSize -SkipTokenCheck
```

## Classes

| Class | Meaning |
| --- | --- |
| **REMOVABLE** | Clean (no modified or untracked files), no unpushed commits, and its PR is merged or closed, or HEAD is already in the default branch. Clones must also pass these checks: they host no linked worktrees, have no stash entries, have no unpushed commits on any local branch, and are not the last clone of their repo under the root. |
| **PUSH-ME** | Its commits exist only locally (no upstream, or ahead of it) and are older than `-PushAfterHours`. Push them and open a draft PR. |
| **KEEP** | Anything else, with the reason: dirty, an open PR, younger unpushed work, the main repo of other worktrees, locked, or excluded because it is in use. |
| **LEFTOVER** | A folder that matches `-LeftoverPattern` (`wt-*`, `qa-tmp-*`, `ABACUS*`, `CODEX*`) but has no `.git`. These are usually what remains of a removed worktree, such as a `.pytest_cache` or an empty folder. They are only reported. Check them, then delete them yourself. |

Unpushed commits are counted against all remote-tracking refs. A clone with a narrow fetch refspec, like `mc-integration`, never gets those refs for branches it pushes. In that case the script asks `git ls-remote origin` before it calls the work unpushed.

## `-Apply` (removal)

```powershell
pwsh -NoProfile -File tools\workstation\Invoke-WorkspaceAudit.ps1 -Apply                      # linked worktrees only
pwsh -NoProfile -File tools\workstation\Invoke-WorkspaceAudit.ps1 -Apply -AllowCloneDelete    # also duplicate clones (interactive)
```

- Removes only the **REMOVABLE** entries. Before each removal it checks the entry again, and skips it if it became dirty, gained unpushed commits, or moved HEAD since the scan.
- Linked worktrees are removed with `git worktree remove <path>` and never with `--force`, so git also refuses if anything is left uncommitted. The branch itself is kept.
- Standalone clones are removed only when `-AllowCloneDelete` is also passed. They go to the **Recycle Bin**, not a hard delete. Windows asks before it permanently deletes a folder that is too big for the Recycle Bin, so run this interactively. Do not schedule `-AllowCloneDelete`. The space comes back only after you empty the Recycle Bin.
- Afterwards it runs `git worktree prune` in every main repo it saw.
- `-Exclude` (default `wt-jade5`, `wt-lesson*`) lists folder names that are never removed.

## Fixing a stale token (lesson 8)

If the report shows a token with `Valid = False`, remove it yourself and open a new shell:

```powershell
[Environment]::SetEnvironmentVariable('GITHUB_TOKEN', $null, 'User')
[Environment]::SetEnvironmentVariable('GITHUB_TOKEN', $null, 'Machine')   # elevated shell, only if set there
Remove-Item Env:GITHUB_TOKEN -ErrorAction SilentlyContinue                # current shell only
```

A value set only at Process scope was usually inherited from the parent app, such as a desktop app that was started while the variable was still set. Restart that app after removing the User/Machine value.

## Wiring into the weekly disk-hygiene task (report only)

The existing scheduled task `\Disk Hygiene (weekly)` runs `python ...\codex-tools\tools\disk_hygiene\disk_hygiene.py --apply` on Mondays at 08:30. To have it also produce this audit, add a second action. Do **not** pass `-Apply`.

1. Copy the script to a stable location, because worktrees come and go:

   ```powershell
   $dst = 'C:\Users\gbonthuy\Documents\Codex\codex-tools\tools\workstation'
   New-Item -ItemType Directory -Force $dst | Out-Null
   Copy-Item tools\workstation\Invoke-WorkspaceAudit.ps1 $dst
   ```

2. Add the action (your own account, no elevation needed if you created the task):

   ```powershell
   $task = Get-ScheduledTask -TaskName 'Disk Hygiene (weekly)'
   $audit = New-ScheduledTaskAction -Execute 'pwsh.exe' `
       -Argument "-NoProfile -NonInteractive -File `"$dst\Invoke-WorkspaceAudit.ps1`" -ReportPath `"$env:LOCALAPPDATA\workspace-audit`"" `
       -WorkingDirectory $dst
   Set-ScheduledTask -TaskName 'Disk Hygiene (weekly)' -Action (@($task.Actions) + $audit)
   ```

3. Each Monday, read the newest `workspace-audit-*.json` in `%LOCALAPPDATA%\workspace-audit`. Run `-Apply` by hand when the REMOVABLE list looks right.

To undo step 2, run `Set-ScheduledTask -TaskName 'Disk Hygiene (weekly)' -Action $task.Actions[0]`.

## In use right now (2026-10-23)

These worktrees under the work root are in use by active sessions. Do not remove them, even if the audit marks them REMOVABLE later:

- `wt-jade5`
- the seven lesson workers' `wt-lesson*` worktrees. Six of them existed when this was written: `wt-lesson1-fpc`, `wt-lesson2-rulesets`, `wt-lesson3-pins`, `wt-lesson4-rules`, `wt-lesson6-jade` and `wt-lesson9-workstation`.

The default `-Exclude` already covers `wt-jade5` and `wt-lesson*`. Once those PRs land, rerun the audit, and they will show up as REMOVABLE when they are clean.

# Generated-output conflict resolver

`Resolve-RegenConflicts.ps1` clears merge conflicts that are only in generated, SHA-pinned outputs, such as `mission-control/gogreen/launcher/launcher.json` and `index.html`. These files embed blob OIDs and commit SHAs. Every merge to master moves them, so every open PR that also touched them conflicts. Resolving the hunks by hand is wasted work: the right content is whatever the generators produce from the merged sources.

The generated set is read from `CHAIN` in `mission-control/jade_temple/tools/regen.py` at the base commit (the owner of that list). Add more with `-ExtraGenerated 'path/**'`.

```powershell
# Dry run for one or more PRs. Merges and regenerates in a scratch worktree, pushes nothing.
pwsh -NoProfile -File tools\workstation\Resolve-RegenConflicts.ps1 -Pr 1036,1038

# Every open CONFLICTING PR in the repo: dry run first, then push the ones that end RESOLVED
pwsh -NoProfile -File tools\workstation\Resolve-RegenConflicts.ps1 -All
pwsh -NoProfile -File tools\workstation\Resolve-RegenConflicts.ps1 -All -Push
```

For each PR, the script merges `origin/<base>` into the PR head in one reused scratch worktree (`-WorkTree`, default `%TEMP%\pah-regen-resolver`, removed at the end). It takes the base copy of each conflicted generated file, commits the merge, then runs `regen.py --write` and commits until nothing changes. It ends with `regen.py --check`. The push is a fast-forward of the PR branch, guarded by `--force-with-lease` against the head it merged into. It never changes draft state, never comments and never merges.

| Class | Meaning |
| --- | --- |
| **MANUAL** | A conflicted path is not a generated output. Nothing is changed. Resolve it by hand, then run `regen.py --write`. |
| **STALE** | After regen, a step that is fresh at the base is still stale at the PR. Not pushed (`-AllowStale` overrides). Steps already stale at the base are listed, but don't block. |
| **FAIL** | git, gh or a generator failed, or the branch moved while the script ran. Re-run. |
| **LIVE** | Another worktree on the branch is dirty or has a reflog entry younger than `-LiveMinutes`. Leave it to that session. |
| **FORK** | The head is in a fork. Resolve it there. |
| **RESOLVED** | Clean merge plus regen, and `--check` passes. Dry run only: re-run with `-Push`. |
| **PUSHED** | Pushed. Once CI finishes on the new head, write the FPC receipt (`python scripts/fpc_receipt.py --pr N --write`, or pass `-WriteReceipt`). |
| **NOOP** | The PR already contains the base, and regen changed nothing. |

The script exits 1 if any PR ends FAIL or STALE. A JSON report is written to `-ReportPath`.

# PC dashboard launcher

`dashboards/` builds one local start page that links every HTML page in every clone on the workstation,
plus the top dashboards, GitHub Pages sites and claude.ai artifacts. It is rebuilt daily by a scheduled task.
Install it with `pwsh -NoProfile -File tools\workstation\dashboards\Install-Dashboards.ps1`; see
[dashboards/README.md](dashboards/README.md).
