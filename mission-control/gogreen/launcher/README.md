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
| `sources.json` | Declares each tile: owner, input file, field paths, related pages; and the launcher page list |
| `build_launcher.py` | Reads the inputs at one commit with `git cat-file`, writes `launcher.json` and `index.html` |
| `launcher_template.html` | Self-contained page (no external scripts or styles; CSP `default-src 'none'`) |
| `launcher.json` | Generated snapshot: source SHA, blob OID of every input, values, missing fields |
| `index.html` | Generated page; do not hand-edit |

## How to open it (entry and discovery)

The launcher is the hub's single entry page. Its **Access** section repeats these steps, and fills in the real local path when you open the page from disk.

**On this computer.** Every page link is relative, so the whole set works from any checkout with no server and no network.
1. Open File Explorer at your checkout of `pipeline-automation-hub` (or a worktree of it).
2. Go to `mission-control\gogreen\launcher\` and double-click `index.html`.
3. From PowerShell, in the checkout:
   ```powershell
   git pull --ff-only
   Start-Process .\mission-control\gogreen\launcher\index.html
   explorer .\mission-control\gogreen\launcher
   ```

**On GitHub.**
- Repository: <https://github.com/GBOGEB/pipeline-automation-hub>
- This page's folder on master: <https://github.com/GBOGEB/pipeline-automation-hub/tree/master/mission-control/gogreen/launcher>

  GitHub shows the source of an HTML file, not the rendered page. Each page card in the launcher links to its GitHub source at the commit the launcher was read at.
- To get a local copy: `git clone https://github.com/GBOGEB/pipeline-automation-hub.git`.

**Hosted.** Only the CODE PURPLE method atlas is published, at <https://gbogeb.github.io/pipeline-automation-hub/>. It is declared under `hosted` in `sources.json`, and the build accepts only `https://*.github.io/` URLs there.

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
| Scale dock (real pulses) | `gogreen/scale_dock.py` over `gogreen/scale_dock_series.py` | `gogreen/scale-dock/real/receipt/scale-dock.json` |

Field paths are dotted; `name[]` maps the rest of the path over a list and `name{}` over a
mapping's entries, each read as `{"key": k, "value": v}` (used for the repo-keyed `p_state.json`).

Paths are under `mission-control/`.

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
regenerated page with the same title is not stale; a changed title is reported by page path. The `GOGREEN launcher` workflow runs only when this directory changes, so an
owner's PR is never blocked by this page; the page can lag an owner until it is rebuilt, and it
shows the commit it was read at.
