# GoGreen launcher

One page that links the existing GoGreen, JADE, Mission Control and PURPLE / P-process pages and
shows the headline numbers for completion, progress, TODO, BD-queue, health, DMAIC, MIP, MYCELIUM,
the golden thread, P-process mode, EVERRED and the Code Purple queue and iteration series.

**It computes no metric.** Each tile reads fields verbatim from the committed output of the
metric's canonical owner (AGENTS.md L4), and every input is read at one commit (L6). A field that
is missing or `null` renders as *unknown*, never as zero. To change a number, change its owner,
not this page.

| File | Role |
|---|---|
| `sources.json` | Declares each tile: owner, input file, field paths, related pages; the launcher page list; the verified GitHub Pages site root; the cross-repo Dashboards hub |
| `build_launcher.py` | Reads the inputs at one commit with `git cat-file`, writes `launcher.json` and `index.html` |
| `launcher_template.html` | Self-contained page (no external scripts or styles; CSP `default-src 'none'`) |
| `launcher.json` | Generated snapshot: source SHA, blob OID of every input, values, missing fields, HTML catalog |
| `index.html` | Generated page; do not hand-edit |

## Tiles and owners

| Tile | Owner | Input |
|---|---|---|
| Completion | `jade_temple/tools/rolling5.py` | `jade_temple/site/rolling5.json` |
| Progress | `jade_temple/site/build_burndown.py` | `jade_temple/site/burndown.json` |
| TODO, Health | `v2/adoption/validate_mc_s2_a4_dashboard.py` | `v2/adoption/MC_S2_A4_DASHBOARD_TODO_SURFACE_20260927_v1.json` |
| BD-queue, GoGreen runs | `gogreen/comparative` | `gogreen/comparative/comparison.json` |
| BD-queue (JADE) | `jade_temple` | `jade_temple/data/BD_QUEUE.csv` |
| Code health | `federation-atlas/central/code_health.py` | `federation-atlas/central/CODE_HEALTH_CENTRAL_v1.json` |
| DMAIC | `grand-missions` (`gm-dmaic-evolution.yml`) | `grand-missions/GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json` |
| DMAIC R3 control | `grand-missions` (`hm01-r3-dmaic-control.yml`) | `grand-missions/R3_DMAIC_CONTROL_CURRENT_v1.json` |
| MYCELIUM | `gogreen/mycelium_history` | `gogreen/mycelium_history/W10_LAST_GOOD_APPEND_20261018.json` |
| Golden Thread | `jade_temple/tools/rolling5.py` (`golden_thread()`) | `jade_temple/site/rolling5.json` |
| MIP (eight-point) | `jade_temple/site/build_eightpoint.py` | `jade_temple/site/eightpoint.json` |
| P-process mode | `qps-triage-ultra/p-process/p_decide.py` | `qps-triage-ultra/p-process/site/data/p_state.json` |
| EVERRED | `qps-triage-ultra/p-process/everred/harvest.py` | `qps-triage-ultra/p-process/site/everred/data/everred.json` |
| BD-queue (Code Purple) | `federation-atlas` (`build_code_purple.py`) | `federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json` |
| Code Purple iterations | `federation-atlas/code_purple_series.py` | `federation-atlas/CODE_PURPLE_ITERATION_SERIES_v1.json` |

Field paths are dotted; `name[]` maps the rest of the path over a list and `name{}` over a
mapping's entries, each read as `{"key": k, "value": v}` (used for the repo-keyed `p_state.json`).

Paths are under `mission-control/`.

## Dashboards (cross-repo hub)

The **Dashboards** section, first on the page, lists the dashboards to start from across repositories:
BnB (Bread and Butter), the cryoplant QPS dashboard launcher, the Master Input repo ledger, the CODE BNB
cockpits, EVERRED, the G3P live ledger and the issue-rank title census artifact. They are declared in
`sources.json` `hub`:

- An entry with only a `path` is in this repository. The build reads it at the build commit (a missing
  file fails the build) and records the page's title, so `--check` names a retitled hub page
  (`hub changed: <path>`). It gets **Open** (relative), **GitHub** and **History** links.
- An entry with `repo`, `ref` and `path` is in another repository (cryoplant-project is private). It is
  declared, not probed: GitHub source and history links, plus a copyable `start <repo>\<path>` command
  that opens the page from a clone of that repository (the section shows the `git clone` command once
  per repository). Its Pages site returned 404 for these paths, so no Pages URL is given.
- The BnB `url` entry links to the claude.ai artifact as written. It is private to its owner unless
  shared, and the `bnb-dashboard-pull` scheduled task republishes it each weekday.
- The issue-rank title census links to its hosted claude.ai artifact, documented in
  `mission-control/issue_rank/title_census/README.md`; it is private until shared.

`hub.verified` records when and how the cross-repo entries were checked. Re-check them and update it
when a target moves.

## All pages (catalog) and How to access

`launcher.json` also carries a `catalog`: every committed `*.html` file at the read-at commit
(`git ls-tree -r --full-tree`), sorted by `group` then `path`. Each entry has `path`, `group` (the
first two directory levels, e.g. `docs/mission-control`, `mission-control/jade_temple`), `title`
(the page's `<title>`, else its file name), `href` (relative to this directory) and `github`
(`{repo_url}/blob/{source_sha}/{path}`). The page adds a **History** link per row
(`{repo_url}/commits/{source_sha}/{path}`). The catalog is navigation only: no blob OID, no metric.
Some entries are templates or Jekyll layouts that only render after their own build.

The page's **How to access** section explains three ways in:

- **Local / File Explorer**: `git clone https://github.com/GBOGEB/pipeline-automation-hub.git`, then
  open `mission-control\gogreen\launcher\index.html` by double-clicking it in File Explorer, or run
  `start mission-control\gogreen\launcher\index.html` / `explorer mission-control\gogreen\launcher`
  from the clone root. When the page is opened from disk (`file:`), it shows its own folder and the
  clone root, and the relative **Open** links open sibling pages from the clone. In that case each
  **All pages** row also shows the page's local path for File Explorer, with a **Copy** button (it
  selects the text where the browser blocks the clipboard on `file:`). The clone root is worked out
  from the page's own `file://` address, so no machine path is committed.
- **GitHub**: the repository and this page's source at the read-at commit. github.com shows HTML
  as source, so render pages from a clone or through the Pages site.
- **GitHub Pages**: only the site root recorded under `pages_site` in `sources.json`, with how and
  when it was verified (`gh api repos/GBOGEB/pipeline-automation-hub/pages` on 2026-10-25: status
  built, build_type workflow, source master:/docs). Which pages the Pages workflow publishes is not
  verified, so no per-page Pages URL is emitted. Re-verify and update `pages_site` if the Pages
  configuration changes.

## Build and check

```bash
python mission-control/gogreen/launcher/build_launcher.py            # read owners at HEAD, write outputs
python mission-control/gogreen/launcher/build_launcher.py --rev <sha> # read owners at a given commit
python mission-control/gogreen/launcher/build_launcher.py --check     # fail if outputs are stale
python -m unittest discover -s mission-control/gogreen/launcher -p "test_*.py"
```

`--check` rebuilds from the commit in memory and compares everything except the recorded
`source_sha` and `source_date`. When an owner updates an input, it reports that input by path. Rebuild and
commit the outputs. Linked pages are navigation, not inputs: only their titles are recorded, so a
regenerated page with the same title is not stale; a changed title is reported by page path. The catalog follows the same rule: a regenerated page with the same title is not stale; an added, removed or retitled HTML file is reported by path (`catalog added/removed/retitled`). The `github` links name the read-at commit and are ignored by `--check`, like `source_sha`. The `GOGREEN launcher` workflow runs only when this directory changes, so an
owner's PR is never blocked by this page; the page can lag an owner until it is rebuilt, and it
shows the commit it was read at.
