# AGENTS.md

Standing rules for every session working in `GBOGEB/pipeline-automation-hub`, human or agent.
They come from the 2026-10-23 CI retrospective (EVERRED / P-process / JADE DAG, PRs #781 and #787).
Read this file before you build anything.

## Working rules

Windows workstations: a stale `GITHUB_TOKEN` in the environment makes `gh` return 401. Start every
`gh` or `git push` command with `unset GITHUB_TOKEN GH_TOKEN;` (PowerShell: `Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue`).

### L1. Never merge on red; fix the gate input or downgrade the gate explicitly

A gate that fails on every PR teaches everyone to ignore red. Before merging:

- Read why the gate is red, not just that it is red:
  `gh pr checks <PR>`
- If the First-Pass Closure gate is red because the receipt is missing or stale, fix the input: put an
  `<!-- FPC_RECEIPT_V1 {...} -->` block in the PR body that names the exact head SHA and the
  successful run ids (format: `docs/W305_FIRST_PASS_CLOSURE_GATE.md`, section "PR-body receipt").
  Dry-run the gate locally (read-only API calls):
  `python scripts/first_pass_closure_gate.py --repo GBOGEB/pipeline-automation-hub --pr <PR> --token "$(gh auth token)" --policy mission-control/quality/FIRST_PASS_CLOSURE_POLICY_v1.json`
- If the gate itself is wrong, downgrade it in its own reviewed PR (owner decision, recorded in the PR)
  instead of merging past it. "It is always red" is never a reason to merge.

### L4. One owner per metric; check before you build, import instead of copying

EVERRED and the P-process metrics were built twice (#781 and the JADE DAG #787) before being reconciled.

- Before writing a metric, page, gate or tool, check master and open PRs:
  `python scripts/preflight_overlap.py <term> [<term> ...] [--path <dir-or-file>]`
  (for example `python scripts/preflight_overlap.py everred p_decide rolling5 --path mission-control/gogreen`).
  It lists matching open PRs (title, branch, changed files) and matching files and `def`/`class`
  names on `origin/master`, then prints an "Already owned by" summary.
- If something already owns it, import its function (see [Metric ownership](#metric-ownership)) or
  extend its PR. Do not copy the code into a second module. `cicd_dag.scale_docks()` is the pattern:
  it loads `scale_dock.py` with `importlib` and calls its dockers instead of re-implementing them.
- If you must change the owner's definition, change it in the owner module, in a PR of its own.

### L5. Push branches early

Rolling-5 sat local-only and had to ship inside #787; a pushed branch would have been its own reviewable PR.

- Push right after the first commit, then open a draft PR:
  `git push -u origin HEAD`
  `gh pr create --draft --base master`
- One concern per branch. If a second concern appears, branch it off and push it as its own PR.

### L6. Snapshots come from one pulse

The census and the gate snapshot were read at different commits in 4 of 5 focus repos.

- Read each repo's head SHA once per pulse and use that SHA for every snapshot taken in that pulse
  (census, gate snapshot, FOCUS5 rows):
  `gh api repos/<owner>/<repo>/commits/<branch> --jq .sha`
- Record the SHA with the data: FOCUS5 rows carry `source_sha`, the DevOps census carries each
  repo's `head_sha`. They must be equal for the same pulse; if they differ, retake the older one rather
  than publishing a mixed pulse.
- Add the pulse to the rolling-5 ledger only after both snapshots agree:
  `python mission-control/jade_temple/tools/rolling5.py --append-pulse data/FOCUS5_<X>.json --pulse-id P<NNNN>`

### L7. Pinned OIDs: regenerate the JADE DAG when you touch its inputs

The generated JADE outputs pin the git blob OIDs of the p-process files,
`mission-control/gogreen/scale_dock.py` and the DevOps census (full list: `objects` and `sources` in
`mission-control/jade_temple/data/CICD_DAG_POLICY.json`). Changing any of them turns JADE QA red by
design until the outputs are regenerated.

- After changing a pinned input, and after every merge of master into your branch, regenerate and verify
  in the same PR with one command. It runs the whole chain in dependency order, leaves fresh steps alone
  and then runs every check (`--list` prints the chain, plain `regen.py` only checks):
  ```
  python mission-control/jade_temple/tools/regen.py --write
  ```
  If it reports `REGEN_DEFER launcher`, commit and run it again: the launcher reads its inputs at HEAD.
- Never hand-edit `site/cicd_dag.*`, `site/rolling5.*` or `diagrams/CICD_DAG_*.mmd`; they are generated.
- Line endings are hashed. `.gitattributes` keeps text LF on every platform; on Windows write generated
  files with `newline="\n"` and `encoding="utf-8"`.

## Metric ownership

One canonical module per metric. Import these; do not re-implement them. Paths are repo-relative.

| Metric / output | Canonical module | Import / call | Produces |
|---|---|---|---|
| EVERRED census (occurrences, roots, root closure / recurrence rates) | `mission-control/qps-triage-ultra/p-process/everred/harvest.py` | `harvest()`, `matches()`, `run_probes()`; metrics are computed in `main()` and written to `everred.json` | `site/everred/data/everred.json` (`everred.census/1.0`) |
| EVERRED register page | `mission-control/qps-triage-ultra/p-process/everred/build_page.py` | CLI only (renders from `everred.json`) | `site/everred/index.html` |
| P-process mode per repo | `mission-control/qps-triage-ultra/p-process/p_decide.py` | `decide(census, everred, drift, cp_repos)`, `repo_of()` | `site/data/p_state.json` (`p-process.state/1.0`) |
| P-process home page and deck | `mission-control/qps-triage-ultra/p-process/build_p_process.py` | CLI only | `site/index.html`, `site/P-process-deck.pdf` |
| Scale dock (first-red / root-red metrics, EVERRED / Code Purple / P-process docks, cross-source consistency) | `mission-control/gogreen/scale_dock.py` | `red_metrics()`, `dock_everred()`, `DOCKERS[name]()` (`dock_code_purple`, `dock_p_process`, `dock_issue_bd`, `dock_crosswalk`), `dock_consistency()`, `DOCK_SCHEMAS`, `evaluate()` | `codepurple.scale-dock.series.v1` |
| Scale-dock real pulses (live default-head RED/RECOVERED jobs, sha256-chained pulse ledger) | `mission-control/gogreen/scale_dock_series.py` | `observe()`, `append()`, `verify()`, `series()`; reuses `bd_queue_wave`, `harvest` and `scale_dock` | `gogreen/scale-dock/real/pulses.jsonl` (`codepurple.scale-dock.pulse-ledger.v1`) |
| Rolling-5 window (NIRVANA rotation, streaks, golden thread, SOURCE_RED) | `mission-control/jade_temple/tools/rolling5.py` | `project()`, `verified_pulses()`, `append_pulse()`, `streak_stats()`, `nirvana()`, `source_red()` | `site/rolling5.json`, `site/rolling5.csv` |
| CI/CD DAG + SIPOC (FUNCTION / SHA / OID lenses, DAG stats, red-trace EVERRED ratios) | `mission-control/jade_temple/tools/cicd_dag.py` | `project()`, `dag_stats()`, `critical_path()`, `gate_frontier()`, `everred_metrics()`, `scale_docks()` (delegates to `scale_dock.py`), `git_blob_oid()` | `site/cicd_dag.json`, `site/cicd_dag_crosswalk.csv`, `diagrams/CICD_DAG_*.mmd` |
| CI/CD DAG page | `mission-control/jade_temple/site/build_cicd_dag.py` | renders `cicd_dag.project()`; no metrics of its own | `site/cicd_dag.html` |
| Issue triway burndown (oldest / newest / connected orderings, explicit DoD/DoV checklist, owner-review queue) | `mission-control/qps-triage-ultra/issue-expedition/triway_burndown.py` | `checklist()`, `references()`, `parked_intent()`, `priority()`, `project()`, `collect()`; the issue parsers (DoD / DoV / STEPS sections, typed references) for every issue tool | `missioncontrol.issue_expedition.triway.v1` |
| Issue burndown ranking (method v2: unknown-not-zero urgency, pressure rank = PageRank with urgency restart and own / inherited split, Monte Carlo rank intervals, deadlocks and blocker chains, lifecycle golden thread via rolling5, flow with exact Poisson intervals, predicate leaks, lanes, per-repo / FOCUS4 / JADE TOP21 / USER rollups, private_boundary projection, chained pulse ledger; imports its checklist and reference parsing from triway above; SCC / chain / Poisson / rank statistics in `issue_math.py`) | `mission-control/issue_rank/issue_rank.py` | `build_graph()`, `unblock_pressure()`, `pagerank()`, `betweenness()`, `urgency()`, `lifecycle_thread()`, `flow()`, `predicate_leaks()`, `monte_carlo()`, `rank()`, `diff()`, `redact()`, `append_ledger()` | `out/<scope>/issue_rank.json` (`jade.issue-rank.v2`, local only, gitignored) |
| Issue/PR title-family grammar and recursive vocabulary (sole SSOT, additive; classification and linked candidates never alter issue state) | `mission-control/issue_rank/title_taxonomy.py` | `parse_title()`, `summary()`, `associated_families()`; consumed by issue_rank and triway | `jade.title-taxonomy.v1` / per-repo, JADE and USER family and leaf-cluster views |
| DevOps fleet census (exact-head blob ids, lifecycle stages) | `mission-control/jade_temple/devops/census.py` | `fetch` / `scan` / `check` / `report` subcommands | `data/DEVOPS_CENSUS_N9.json`, `data/DEVOPS_OBJECTS_N9.json` |
| Actions usage + performance metrics (per workflow / repo / FOCUS5 fleet: billable minutes, job run and queue time, job failure rate, failed-job minutes, class / band / event groupings) | `mission-control/jade_temple/devops/actions_metrics.py` | `aggregate()`, `project()`, `fetch` / `project` subcommands; reuses `bd_queue_wave.utc()` / `percentile()` / `queue_seconds()` | `data/ACTIONS_METRICS_FOCUS5.json` (`jade.devops.actions-metrics.v1`), `site/actions_metrics.csv` |

Note the two EVERRED views: `harvest.py` owns the root register metrics (per root, from Actions
failures); `cicd_dag.everred_metrics()` owns the per-workflow red-trace ratios (`everred_ratio`,
`recovery_rate`, `flake_rate`) over `data/RED_TRACE_FEDERATION_N8.json`. Do not add a third.
To load a module from a hyphenated directory, use `importlib.util.spec_from_file_location` as
`cicd_dag.scale_docks()` does.
