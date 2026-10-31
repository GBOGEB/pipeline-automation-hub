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

## 2b. Generated settings (run once, and again after adding repos)

Close PyCharm first (**File ▸ Exit**). It rewrites `.idea` on exit, and the script refuses to run while PyCharm is open.

```powershell
pwsh -File "C:\Users\gbonthuy\Documents\Codex\2026-10-23\pah-devops-n9\tools\workstation\Set-PyCharmWorkspaceConfig.ps1" -Workspace C:\repos\GBOGEB_WORKSPACE
```

It writes:

| File | What you get in PyCharm |
|---|---|
| `.idea\vcs.xml` | Every `repos\` and `worktrees\` link registered as a Git root, so you don't click "Add roots" |
| `.idea\scopes\*.xml` | Scopes **Repos**, **Worktrees**, **QPS ledger**, **YAML-JSON-TOML**, **Office-PDF**. Pick one in the Project tree's view dropdown (top-left, *Project ▾*) or in *Find in Files ▸ Scope* |
| `.idea\fileColors.xml` | Tree colours: repos blue, worktrees green, QPS ledger violet |
| `requirements-workspace.txt` | The pins the repos use (`openpyxl==3.1.5`, `PyYAML==6.0.3`, `jsonschema==4.25.1`, `pytest==8.4.2`). Reopen PyCharm and click **Install requirements** for the workspace venv |
| `%APPDATA%\JetBrains\PyCharm2025.2\tools\GBOGEB.xml` | Right-click ▸ **External Tools ▸ GBOGEB**: refresh workspace · audit selected folder · QPS dry-run / publish / export PEER / merge PEER on the selected workbook (version asked in a prompt) |

Each replaced file is kept as `*.bak-<stamp>`.

## 2c. Settings to set once by hand (IDE-wide)

| Setting | Value | Why |
|---|---|---|
| **Tools ▸ Terminal ▸ Shell path** | `pwsh.exe` | The runbook commands are PowerShell 7 |
| **Editor ▸ File Types ▸ Files Opened in Associated Applications** | add `*.xlsx;*.docx;*.pptx;*.pdf` | Double-click opens Excel/Word/PowerPoint instead of a binary view |
| **Languages & Frameworks ▸ Schemas and DTDs ▸ Remote JSON Schemas** | ✓ Allow downloading from SchemaStore.org | GitHub workflows, dependabot, pyproject: YAML/TOML validated as you type |
| **Languages & Frameworks ▸ Schemas and DTDs ▸ JSON Schema Mappings** | + → a repo `*.schema.json` → the files it governs | Validates your own contract YAML/JSON, e.g. `contracts/*.schema.json` in cryoplant-project |
| **Project tree ⋮ ▸ Appearance** | ✓ Folders Always on Top, ✓ Compact Middle Packages off; **⋮ ▸ Behavior** ✓ Always Select Opened File | Tree mirrors where you are |
| **Project ▸ Project Structure ▸ Exclude files** | `node_modules;.pytest_cache;__pycache__;_tmp;*.bundle;.venv` | Keeps indexing of 68 roots light |

YAML, JSON and TOML support is built in; no extra interpreter is needed. The Python interpreter is only for `.py` files: the venv in `C:\repos\GBOGEB_WORKSPACE\.venv` is fine.

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
