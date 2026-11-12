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
  It lists matching open PRs (title, branch, changed files, and the added lines of each PR's diff,
  so a function that exists only inside an open PR is reported as "defined in open PR #n at
  path:line") and matching files and `def`/`class` names on `origin/master`, then prints an
  "Already owned by" summary. The diff scan covers at most `--diff-limit` PRs (default 50), each cut
  at `--diff-max-chars`; `--no-diff` skips it (2026-11-12: it had missed `transitive_reduction` in #1209).
- If something already owns it, import its function (see [Metric ownership](#metric-ownership)) or
  extend its PR. Do not copy the code into a second module. `cicd_dag.scale_docks()` is the pattern:
  it loads `scale_dock.py` with `importlib` and calls its dockers instead of re-implementing them.
- If you must change the owner's definition, change it in the owner module, in a PR of its own.
- Before stacking on someone's open PR, and again before you push, `git fetch` its branch and read
  `git log <your-base>..origin/<their-branch>`. Another session may be building the same thing on it
  right now (2026-11-11: #1207 duplicated `maroon/operations.py`, pushed to #1178 an hour into the work).
  If it is, stop and turn your work into an add-on to theirs.

### L5. Push branches early

Rolling-5 sat local-only and had to ship inside #787; a pushed branch would have been its own reviewable PR.

- Push right after the first commit, then open a draft PR:
  `git push -u origin HEAD`
  `gh pr create --draft --base master`
- One concern per branch. If a second concern appears, branch it off and push it as its own PR.

**Codex reviews are rationed.** The Codex review quota is small and shared by every session. It ran out
from 2026-11-09, and on 2026-10-30 it left 31 PRs red. On 2026-11-11 the owner turned automatic review and
automatic security review off in the personal Codex settings and set each repository to follow them. A
repository entry set to "All PRs" overrides that and reviews drafts too: draft #1194 was reviewed when it
opened. First-Pass Closure still needs a completed Codex review on the exact head, so no PR passes until
someone asks for one.

- Keep the PR a draft until it is final: tests pass locally and every commit is pushed. While automatic
  review was on, opening a PR and marking it ready each spent one attempt (#1164, #1194).
- Only the session that owns the PR marks it ready. Then comment `@codex review` once. Don't push until
  the review lands. Fix every finding in one commit, then ask once more.
- Batch small PRs that touch disjoint files and not the control plane (the FPC gate and policy, required-gate
  ledgers, rulesets): merge each `--no-ff` into one batch PR and ask for one review (#1164 = #1163 + #1162
  + #1138). A PR whose base is another PR's branch goes with that PR.
- Ask for `@codex security review` only for changes to workflow permissions, `pull_request_target`, secrets
  or tokens, or any dependency that is added or changes version. CodeQL covers the rest on every head. The
  hub has no osv-scanner job (ABACUS does), so nothing here scans dependency versions for known
  vulnerabilities.
- If Codex replies with its usage-limit message, don't ask again in the same window.

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

### Windows shell pitfalls

Each of these cost time on the owner's workstation (2026-11-09/10, GEMINI#40, GEMINI#47, #1162).

- **Git Bash rewrites leading-slash arguments.** MSYS turns `/AGENTS.md` into
  `C:/Program Files/Git/AGENTS.md`, so `git sparse-checkout set /path` silently stores a wrong pattern.
  Prefix such commands with `MSYS_NO_PATHCONV=1`, then read the result back with `git sparse-checkout list`.
- **Validate a captured SHA before you use it.** In a mis-configured sparse checkout, `FIX=$(git rev-parse HEAD)`
  captured something other than a bare SHA, so `git cherry-pick "$FIX"` failed after `git reset --hard` had
  already run, and the commit could only be recovered from the reflog (#1135, 2026-11-09). Capture with
  `H=$(git rev-parse HEAD 2>/dev/null | grep -E '^[0-9a-f]{40}$')`, stop if it is empty, and never chain a
  destructive reset after a capture you have not checked.
- **PowerShell splits unquoted commas.** `gh repo list --json name,isFork` passes an array, and `gh`
  receives the wrong argument. Quote the list: `--json 'name,isFork'`.
- **A failed `gh` call can look like an empty answer.** A GitHub 5xx printed an error and returned no
  output, so a script went on with zero repos. Check `$LASTEXITCODE` (or `$?`) after every `gh` call,
  retry a few times, then stop. Never treat empty output as "nothing to do".
- **Owner-only temp folders block git.** `tempfile.TemporaryDirectory()` creates a folder that `git
  merge-file` cannot read ("Permission denied"), and a `.pytest_cache` created the same way can't be
  deleted. Make scratch folders with `os.makedirs` under `tempfile.gettempdir()` and remove them in `finally`.
- **`Remove-Item -Recurse -Force` stops at the first locked entry**, after deleting part of the folder
  (on 2026-11-10 it deleted `.git` first). Check the clone is fully pushed before you start, and check
  `Test-Path` afterwards.
- **CRLF checkouts.** With `core.autocrlf=true`, a patch made against git blobs (LF) fails `git apply`
  in the working tree. Use `git apply --cached`, or apply it in an LF worktree.

## Metric ownership

One canonical module per metric. Import these; do not re-implement them. Paths are repo-relative.

| Metric / output | Canonical module | Import / call | Produces |
|---|---|---|---|
| EVERRED census (occurrences, roots, root closure / recurrence rates) | `mission-control/qps-triage-ultra/p-process/everred/harvest.py` | `harvest()`, `matches()`, `run_probes()`; metrics are computed in `main()` and written to `everred.json` | `site/everred/data/everred.json` (`everred.census/1.0`) |
| EVERRED register page | `mission-control/qps-triage-ultra/p-process/everred/build_page.py` | CLI only (renders from `everred.json`) | `site/everred/index.html` |
| QA engines and K-<TYPE>-NN checks by binary type | `mission-control/registry/engine_catalog.py` + `ENGINE_CATALOG.yaml` | CLI: `validate`, `matrix`, `probe` | Check matrix, engine probe JSON |
| P-process mode per repo | `mission-control/qps-triage-ultra/p-process/p_decide.py` | `decide(census, everred, drift, cp_repos)`, `repo_of()` | `site/data/p_state.json` (`p-process.state/1.0`) |
| P-process home page and deck | `mission-control/qps-triage-ultra/p-process/build_p_process.py` | CLI only | `site/index.html`, `site/P-process-deck.pdf` |
| Scale dock (first-red / root-red metrics, EVERRED / Code Purple / P-process docks, cross-source consistency) | `mission-control/gogreen/scale_dock.py` | `red_metrics()`, `dock_everred()`, `DOCKERS[name]()` (`dock_code_purple`, `dock_p_process`, `dock_issue_bd`, `dock_crosswalk`), `dock_consistency()`, `DOCK_SCHEMAS`, `evaluate()` | `codepurple.scale-dock.series.v1` |
| Scale-dock real pulses (live default-head RED/RECOVERED jobs, sha256-chained pulse ledger) | `mission-control/gogreen/scale_dock_series.py` | `observe()`, `append()`, `verify()`, `series()`; reuses `bd_queue_wave`, `harvest` and `scale_dock` | `gogreen/scale-dock/real/pulses.jsonl` (`codepurple.scale-dock.pulse-ledger.v1`) |
| Rolling-5 window (NIRVANA rotation, streaks, golden thread, SOURCE_RED) | `mission-control/jade_temple/tools/rolling5.py` | `project()`, `verified_pulses()`, `append_pulse()`, `streak_stats()`, `nirvana()`, `source_red()` | `site/rolling5.json`, `site/rolling5.csv` |
| CI/CD DAG + SIPOC (FUNCTION / SHA / OID lenses, DAG stats, red-trace EVERRED ratios) | `mission-control/jade_temple/tools/cicd_dag.py` | `project()`, `dag_stats()`, `critical_path()`, `gate_frontier()`, `everred_metrics()`, `scale_docks()` (delegates to `scale_dock.py`), `git_blob_oid()` | `site/cicd_dag.json`, `site/cicd_dag_crosswalk.csv`, `diagrams/CICD_DAG_*.mmd` |
| CI/CD DAG page | `mission-control/jade_temple/site/build_cicd_dag.py` | renders `cicd_dag.project()`; no metrics of its own | `site/cicd_dag.html` |
| Issue triway burndown (oldest / newest / connected orderings, explicit DoD/DoV checklist, owner-review queue) | `mission-control/qps-triage-ultra/issue-expedition/triway_burndown.py` | `checklist()`, `references()`, `parked_intent()`, `parked_intent_meta()`, `priority()`, `project()`, `collect()`; the issue parsers (DoD / DoV / STEPS sections, typed references) for every issue tool | `missioncontrol.issue_expedition.triway.v1` |
| Issue burndown ranking (method v2: unknown-not-zero urgency, pressure rank = PageRank with urgency restart and own / inherited split, Monte Carlo rank intervals, deadlocks and blocker chains, lifecycle golden thread via rolling5, flow with exact Poisson intervals, predicate leaks, lanes, per-repo / FOCUS4 / JADE TOP21 / USER rollups, private_boundary projection, chained pulse ledger; imports its checklist and reference parsing from triway above; SCC / chain / Poisson / rank statistics in `issue_math.py`) | `mission-control/issue_rank/issue_rank.py` | `build_graph()`, `unblock_pressure()`, `pagerank()`, `betweenness()`, `urgency()`, `lifecycle_thread()`, `flow()`, `predicate_leaks()`, `monte_carlo()`, `rank()`, `diff()`, `redact()`, `append_ledger()` | `out/<scope>/issue_rank.json` (`jade.issue-rank.v2`, local only, gitignored) |
| Issue/PR title-family grammar and recursive vocabulary (sole SSOT, additive; classification and linked candidates never alter issue state) | `mission-control/issue_rank/title_taxonomy.py` | `parse_title()`, `summary()`, `associated_families()`; consumed by issue_rank and triway | `jade.title-taxonomy.v1` / per-repo, JADE and USER family and leaf-cluster views |
| DevOps fleet census (exact-head blob ids, lifecycle stages) | `mission-control/jade_temple/devops/census.py` | `fetch` / `scan` / `check` / `report` subcommands | `data/DEVOPS_CENSUS_N9.json`, `data/DEVOPS_OBJECTS_N9.json` |
| MAROON diagnosis hints (finding identity by scanner rule or significant words, recurrence ONCE/REPEAT/RECURRING/SYSTEMIC, frequency and modal path, METHOD/REX/SCALING/PINNED_OID tags, bot/fork no-push, seen-fixed and false-positive history, group / one-method / fold-back proposals) | `mission-control/maroon/hints.py` | `finding_key()`, `rule_of()`, `analyse()`; reads the `operations.py` ledger as JSON and never writes it; queue, leases, Kahn plan and closure stay with `operations.py` / `closure.py` | `code_maroon.hints.v1` (private), `code_maroon.hints_public.v1` counts only |
| Topological layering (Kahn waves; wave index = longest-path layer; cycle check that names the stuck nodes) | `mission-control/jade_temple/devops/lifecycle.py` | `topo_layers(nodes, edges)`; from other trees load it with `importlib` as `tools/alkane_dag.py` and metric-atlas `lane_lifecycle.py` do | waves as `list[list[str]]`; `ValueError` on a cycle or an unknown endpoint |
| Actions usage + performance metrics (per workflow / repo / FOCUS5 fleet: billable minutes, job run and queue time, job failure rate, failed-job minutes, class / band / event groupings) | `mission-control/jade_temple/devops/actions_metrics.py` | `aggregate()`, `project()`, `fetch` / `project` subcommands; reuses `bd_queue_wave.utc()` / `percentile()` / `queue_seconds()` and `wddd.iso_week_key()` | `data/ACTIONS_METRICS_FOCUS5.json` (`jade.devops.actions-metrics.v1`), `site/actions_metrics.csv` |
| Week codes on the ISO 8601 week calendar for every GBOGEB repo (`YYYY-w##DDD` codes and `w##DDD` labels, which are project codes, not ISO 8601 syntax; `YYYY-Www` week key, weeks per ISO year, 13-week quarter convention, workday spans; Mermaid schedule patterns with `axisFormat w%V`) | `mission-control/jade_temple/devops/wddd.py` + `WDDD_WEEK_CODES.md` | `to_w_code()`, `from_w_code()`, `iso_week_key()`, `weeks_in_iso_year()`, `quarter_13w()`, `add_workdays()`; `actions_metrics.iso_week()` delegates to it; other trees and repos load it with `importlib` from a pinned hub commit | `2026-w46MON`, `2026-W46`; `ValueError` on a bare code without an ISO year |
| Transcript file recovery (last Write per path plus replayed Edits from Claude Code JSONL; `complete` / `partial` per path; refuses output inside a git work tree) | `tools/threads/extract_writes.py` | `iter_calls()`, `rebuild()`, `dump()`; CLI `list` / `dump` | `OUTDIR/MANIFEST.json` and rebuilt files in a private scratch folder (never committed) |

Note the two EVERRED views: `harvest.py` owns the root register metrics (per root, from Actions
failures); `cicd_dag.everred_metrics()` owns the per-workflow red-trace ratios (`everred_ratio`,
`recovery_rate`, `flake_rate`) over `data/RED_TRACE_FEDERATION_N8.json`. Do not add a third.
To load a module from a hyphenated directory, use `importlib.util.spec_from_file_location` as
`cicd_dag.scale_docks()` does.
