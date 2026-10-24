# GoGreen launcher

One page that links the existing GoGreen, JADE and Mission Control pages and shows the headline
numbers for completion, progress, TODO, BD-queue, health, DMAIC, MIP, MYCELIUM and the golden
thread.

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
commit the outputs. The `GOGREEN launcher` workflow runs only when this directory changes, so an
owner's PR is never blocked by this page; the page can lag an owner until it is rebuilt, and it
shows the commit it was read at.
