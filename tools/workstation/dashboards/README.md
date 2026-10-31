# PC dashboard launcher

One local start page for every dashboard on the owner's workstation. Finding a page you built last week
should not depend on remembering which repo, which checkout or which dated `Documents\Codex\<date>` folder
it is in.

`build_dashboards.py` scans the folders listed in `dashboards.json` for git clones, lists every HTML page
in each one (tracked, or untracked but not ignored), and writes one self-contained page. It computes no
metric and owns no dashboard: it only links to pages that their own owners produce.

| Section | Contents |
| --- | --- |
| Search | Filters every link on the page; press `/` to focus it and `Esc` to clear it |
| ★ My pins | Pages pinned with ★, stored in the browser (`localStorage`) |
| Top dashboards | The `top` list in `dashboards.json`. `repo` + `path` entries open the newest local checkout that has the file, and say *not on PC* when none does |
| Recently changed | The 15 newest HTML files across all clones |
| Hosted & external | GitHub Pages site roots (from `gh api repos/<repo>/pages`) and the `artifacts` list |
| On this PC, per repo | One section per GitHub repo. Duplicate checkouts are merged and each page path keeps its newest copy. Entry pages (index, dashboard, launcher, `_CURRENT`, …; `entry_name_pattern`) come first, then all other HTML, then the checkouts |

Pages sites are linked at their root only. A per-page Pages URL is never inferred from committed HTML.

## Install

```powershell
pwsh -NoProfile -File tools\workstation\dashboards\Install-Dashboards.ps1
```

This copies the builder to `%USERPROFILE%\DASHBOARDS` and does the following:

- It copies `dashboards.json` only if the folder has none, so your edits survive a reinstall.
- It registers the per-user task **GBOGEB Dashboards refresh** to run daily at 08:00 with `pythonw`, so no window opens. A missed run starts later.
- It adds `DASHBOARDS.url` and `DASHBOARDS - refresh.lnk` to the desktop.
- It builds the page once.

Use `-At`, `-NoSchedule`, `-NoShortcuts`, `-NoBuild` or `-Target` to change this. Re-run the installer after you pull changes.

## Run by hand

```powershell
python build_dashboards.py              # also refreshes the GitHub Pages cache through gh
python build_dashboards.py --offline    # Pages sites from pages_cache.json only
python build_dashboards.py --config my.json --out D:\pages\index.html
```

`gh` runs without `GITHUB_TOKEN` / `GH_TOKEN`, so the keyring login is used even while a stale token is set.
Every run appends its progress to `build.log` next to the page. A full scan takes from 30 s to a few minutes,
depending on the size of the OneDrive folders and on how busy the PC is.

## Configure (`dashboards.json`)

| Key | Meaning |
| --- | --- |
| `scan_roots` | `{path, depth}` folders to search for clones. Paths accept `~` and glob patterns (`~/OneDrive - *`). A clone is never searched for nested clones |
| `include_claude_worktrees` | Also list `git worktree` checkouts (off by default; `.claude/worktrees` are usually short-lived) |
| `skip_dirs`, `skip_html_patterns` | Folders not searched, and HTML paths not listed (vendored, coverage, templates) |
| `entry_name_pattern` | Regex on the lower-cased path that marks an entry page |
| `top`, `artifacts` | Curated links. claude.ai artifacts are private to their owner unless shared, and are not discovered automatically |
| `extra_repos_online` | Repos without a local clone whose Pages site should still be listed |

## Test

```powershell
python -m unittest discover -s tools/workstation/dashboards -p test_build_dashboards.py -v
```

The tests build temporary git repos and run offline. CI runs them on Python 3.12 on Ubuntu and Windows
(`.github/workflows/workstation-dashboards-qa.yml`).
