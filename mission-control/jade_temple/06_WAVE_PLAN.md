# JADE_CASTE iterative waves — N0 to N+3 and controlled scale-up

## J0 (current): Project and source reconnaissance

- Preserved SHA/CRC-verified CODE PURPLE N+2 predecessor archive, 32 member files.
- Derived Mission Control N11 21-repository summary with historical count provenance.
- Queried 21 non-atomic default heads and case-sensitive root README paths.
- Authored portable project resources, HTML candidate, root SPINE, gate/BD queue, soft method profile. This is LOCAL / READ-ONLY on GitHub until a draft PR is actually made.

## J1 — Five disjoint core owner pilots

1. `pipeline-automation-hub`: keep authoritative cohort and central dashboard; add JADE read-only project pointer and render QA without new scheduler or roster.
2. `ABACUS`: preserve N+2 critical dashboard as independent source-owned PR candidate; add root brief only when first-red/native evidence and changed-path census permit.
3. `CODEX`: exact-head federation consumer and site/release pilot after CODEX main SHA change.
4. `cryoplant-project`: separate QPS domain release versioning; never promote engineering compliance from dashboard.
5. `gg_MATH`: validate hosted method views and point-release version/repro controls.

**Each lane:** census → one additive owner-owned docs/manifests PR → local tests → native exact-head runs + Pages evidence → review/RED canary → J-level transition only on full proof. Workers are disjoint by repository and path, not assumed authenticated.

## J2 — Seven extension repos

`ariana`, `GEMINI`, `DOCX_RTM_Automation`, `Q_engineering_tools`, `cryo_leak_rate_dashboard`, `cryogenic-accelerator-workspace`, `document-organization-system`.

Retarget slice size by historical root-review volume (e.g. DOCX 62, cryo leak 115): only pilot one owner-approved alias/entrypoint family at a time; do not blindly fan out file moves.

## J3 — Nine support / upstream-derived repos

`github_documentorganisatiesysteem_GBOGEB`, `github-mcp-server`, `docker-stacks`, `yaml-grammar`, `prettier`, `vscode-powershell`, `cli`, `python-sdk`, `skills`. Assign upstream license/ownership and Pages applicability first; no intrusive rewrites of upstream-heavy files.

## Revenue-core DevOps waves A–E (cryoplant-project + QPS TRIAGE)

Goal: make `cryoplant-project` and QPS TRIAGE (`mission-control/qps-triage-ultra`) dependable, sellable assets: libraries, an API and repeatable outcomes. The DevOps census (`devops/census.py`) measures each wave. A wave row closes only when **every** acceptance signal in its row holds in the same committed pulse; a single probe flipping to PASS closes only its own task, never the row. A flip to FAIL becomes the next wave's first item. `cryoplant-project` is private: this plan and every public JADE output name it only by repository name, path and counts (`tools/private_boundary.py`), never by SHA, run, issue or PR number.

| Wave | Repository | Work | Closes when (all, in one pulse) |
|---|---|---|---|
| A | cryoplant | Pin every action to a commit SHA; fail-closed core suite through `jade-reusable-ci.yml`; burn down untested live modules in slices | `build.pinned_actions`, `test.fail_closed` and `test.controlled` all PASS, and the raw pinned ratio `actions_pinned / actions_total` is 100% |
| A2, A3 | hub census | Measurement fixes: `src.`-prefixed imports count as tested; archived copies, and `*_snapshot/` trees backed by a `PROVENANCE.csv`, are counted apart from live code | Their regression tests in `devops/tests/test_devops_census.py` pass on master. A pulse-to-pulse change cannot isolate them, because repository changes move the same counts |
| B | cryoplant + hub | Automated release tags and a changelog | `release.automation` PASS, plus a receipt: a workflow run that created the tag itself and the changelog entry for that tag, both linked from the wave PR |
| C | cryoplant + QPS TRIAGE | Installable packages for the calculation core and the triage logic; a read-only HTTP API | **Package:** a CI job builds the wheel, installs it into a clean virtual environment and runs an import and smoke-calculation test. **API:** a hosting step that actually runs the service (the reusable deploy publishes static Pages or records an artifact promotion; it does not run a service), and a post-deploy and a scheduled read-only `GET` returning 200 and the deployed source SHA, recorded in a receipt. `deploy.contract` and `operate.rollback` must also PASS. `monitor.live_parity` reads `site-manifest.json` from GitHub Pages, so it covers Pages outputs only, not the API |
| D | hub | Register both as hub consumers; remediate cryoplant's 9 EVERRED red-trace workflows | `control.red_trace` PASS, and for each of the 9 original workflows either a green run at the pulse head or an owner-approved retirement. A zero EVERRED count alone is not enough: a workflow that goes green once can turn red again. Registration is checked against the hub consumer list |
| E | ML | Time series first (plant process data; census pulses as a series); DNN/CNN only with labelled data; GAN last, for synthetic data | Starts after C. E1 closes on a committed forecast receipt: one named census series, backtested on the latest pulse held out over at least 5 pulses, beating the last-value baseline, with a test that re-computes the backtest. DNN/CNN and GAN each get their own acceptance check before they start |

Where things stand (committed N+11, hub master):
- Wave A: every cryoplant action was pinned and the fail-closed core suite runs on every pull request. Burn-down slice 3 alone added tests for 260 previously untested live modules, and a read of cryoplant main with the master census now shows `test.controlled` PASS. The next committed pulse records it.
- A2 and A3 are merged, each with its regression test.
- The hub is weakest at S1 L1 (lint configuration), S4 L2 (security scan in CI), S5 L2 (release automation) and S0 L2 (code-owners file).

Pulse procedure (each wave is measured by one pulse; the tools own the commands):
1. **Fetch once.** `census.py fetch` caches every roster repository at its default-branch head. Those cached heads are the pulse's only heads: the red-trace harvest and the scan both read them (AGENTS.md L6). A private repository's head never leaves the workstation; public outputs carry only `private_boundary.py` projections, and a head that cannot be compared is UNKNOWN, never "unchanged".
2. **Wave D pulses: harvest before scanning.** `scan` reads `data/RED_TRACE_FEDERATION_N8.json` before it reads any repository, so harvest each core repository with `gogreen/red_trace/red_trace.py` and rebuild that file with `tools/build_redtrace_data.py` first. Pass `--branch` from `TOP21_PORTFOLIO.json` and `--root` set to that repository's workflows at the cached head. `red_trace.py` reads a branch, not a SHA, so if the branch head no longer equals the cached head, fetch again and redo both steps. `red_trace.py` reads only `GITHUB_TOKEN`: clear stale tokens first (AGENTS.md L9–L10), then hand that one process a fresh token from `gh auth token` without printing or saving it.
3. **Scan authenticated.** Run `census.py scan` with `--api-token-env` set to a read token, and accept the pulse only if `sources.api.mode` is `token`, `census.py check` passes, and every repository reports `blobs_unread` 0. A file that was never read is not evidence of absence.
4. **Register the pulse in CI.** Generate its reading with `census.py report`, add its `check` and `report --check` lines to `.github/workflows/jade-devops-census.yml`, and point that workflow's weekly refresh at the new pulse.
5. **Re-pin the JADE DAG in the same PR.** Re-pin `data/CICD_DAG_POLICY.json`, commit, and run `tools/regen.py --write` (12-step chain, `--list`; re-run after `REGEN_DEFER launcher`). Then `tools/regen.py --check` must report `REGEN_OK`, and `tools/cicd_dag.py --check --strict-pulse` must pass, so the census and the rolling-5 gate snapshot come from one pulse (AGENTS.md L6, L7). Never land a pulse and re-pin later.
6. **Burn-down slices** add their tests inside an existing suite's test tree or in their own workflow (slice 3: `tests/burndown`, `jade-ci-burndown.yml`), and raise that suite's `min-tests` and coverage floor to the measured values. Lowering either is a first red.
7. **Gates:** write the FPC receipt before a wave PR leaves draft, and merge only once first-pass-closure is green on that exact head, Codex review included.

Narrative hooks:
- **A, "red means something":** green is evidence once nothing is floating and nothing passes empty.
- **B, "every version is nameable":** a partner can depend on cryoplant vX.Y.Z.
- **C, "from repository to product":** the core becomes libraries and an API, with rollback and a live-version check.
- **D, "one control room":** the hub federates both, and each pulse says whether the fleet improved and why.
- **E, "learning from our own history":** pulses and plant data become the first series to forecast.

## Feedback and stop rules

- One **G3P** = one wave with three **sequential** comparable pulses. `N-1` historical source, `N` refreshed observation, `N+1..N+3` future verified receipts only if actually executed.
- Scale 1→2→4 disjoint owner slices only after admissible exits; escalate critical blocker remediation, not speculative runner fan-out. No staged runner is counted until authenticated execution.
- Required metrics per pulse: J-level verified N/D, root accepted/remaining (not 706 auto-defects), source SHA, first-red root IDs, hosted/asset SHA, terminal jobs, queue p50/p95 if timestamps, security, approvals, denominator eligibility, evidence yield and diff coverage.
- **Stop/pause** when all targeted J4 requirements are fulfilled or current proofs are blocked, no owner allows the next action, new head invalidates comparable baseline, or three matched pulses show no useful progress. `PAUSE_NO_VALUE` does not prove Six Sigma stability.