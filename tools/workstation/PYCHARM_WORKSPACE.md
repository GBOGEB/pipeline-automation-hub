# One PyCharm view of every repo and worktree

`Invoke-WorkspaceOverview.ps1` gives two views:
- **Bird's-eye:** one Markdown/CSV overview of every clone and worktree on the PC, classified by `Invoke-WorkspaceAudit.ps1`.
- **Granular:** one PyCharm project that shows all active repos and worktrees side by side, each with its own Git root.

Both are read-only towards your repos. The PyCharm folder holds only **directory junctions** (links) to the real folders.

## 1. Build or refresh it (PowerShell 7)

```powershell
pwsh -File "C:\Users\gbonthuy\Documents\Codex\2026-10-23\pah-devops-n9\tools\workstation\Invoke-WorkspaceOverview.ps1" -PyCharmWorkspace C:\repos\GBOGEB_WORKSPACE -ExtraFolder "C:\Users\gbonthuy\OneDrive - Studiecentrum voor Kernenergie\Master_Input\QPS_ACTION_LEDGER"
```

- The run takes about 7 minutes: it audits every root and sizes every folder. Add `-SkipSize` for a faster run without sizes.
- **Overview:** `%USERPROFILE%\workspace-overview\WORKSPACE_OVERVIEW_latest.md`, plus a dated `.md`, `.csv` and `.json` per run.
- **PyCharm folder:** `C:\repos\GBOGEB_WORKSPACE\`:
  - `repos\<repo>__<folder>` — main clones;
  - `worktrees\<repo>__<folder>` — worktrees whose work has **not** landed yet (KEEP / PUSH-ME). Landed ones drop out on the next refresh.
  - `extra\<folder>` — non-git working folders from `-ExtraFolder`, e.g. the QPS ledger.
- **Refresh without re-auditing:** `-ReuseReports "%USERPROFILE%\workspace-overview\reports\<yyyyMMdd-HHmm>"`.

Keep the workspace folder **outside OneDrive** (`C:\repos\...`). OneDrive does not handle junctions well.

## 2. Open it in PyCharm (2025.2)

1. **File ▸ Open…** → select `C:\repos\GBOGEB_WORKSPACE` → **Open** (in a new window) → **Trust Project**.
   - The project name is the folder name, `GBOGEB_WORKSPACE`.
   - PyCharm writes its `.idea\` folder inside the workspace folder, never inside your repos.
2. **Register the Git roots.**
   - When the balloon **"Unregistered VCS roots detected"** appears, click **Add roots**.
   - Otherwise go to **Settings ▸ Version Control ▸ Directory Mappings** → **+** for each folder, or click the detected entries.
   - Every repo and worktree is now its own Git root.
3. **Set the interpreter:** **Settings ▸ Project ▸ Python Interpreter** → *Add Interpreter ▸ System Interpreter* → `C:\Users\gbonthuy\AppData\Local\Programs\Python\Python312\python.exe`.
4. **Keep indexing light:** **Settings ▸ Editor ▸ File Types ▸ Ignored Files and Folders** → add `node_modules`, `.venv`, `_tmp`, `*.bundle`. Or right-click a large folder → **Mark Directory as ▸ Excluded**.

## 3. Daily use

| Want | Where in PyCharm |
|---|---|
| All uncommitted changes, grouped per repo/worktree | **Commit** tool window (Alt+0) → ⚙ **Group By ▸ Repository** |
| History of one repo | **Git** tool window (Alt+9) → **Log** → repository filter (Paths / Root) |
| Branch of each repo and worktree | Branch widget, bottom-right status bar → one section per repository |
| The bird's-eye table | Open `WORKSPACE_OVERVIEW_latest.md` (Markdown preview) |
| Refresh from PyCharm | **Run ▸ Edit Configurations ▸ + ▸ Shell Script** → *Script text*: the command from section 1 → name it `Refresh workspace` |

## 4. Rules

- **Never delete inside `GBOGEB_WORKSPACE` from PyCharm or Explorer.** A tool that follows the link can delete the real folder's contents. To drop a link, rerun the script: it removes junctions only (`[IO.Directory]::Delete(link, $false)`), never the target.
- **Remove landed worktrees with the audit, not by hand:** `Invoke-WorkspaceAudit.ps1 -Root <root> -Apply`. It removes REMOVABLE linked worktrees only, re-checks each first and never forces. Then refresh the workspace.
- **One session per worktree.** PyCharm can show many worktrees at once, but edit a worktree only when no Claude session is live in it.
