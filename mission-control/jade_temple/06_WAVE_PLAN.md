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

## Revenue-core DevOps waves A–E (cryoplant-project + QPS TRIAGE, from census N+10)

Goal: make `cryoplant-project` and QPS TRIAGE (`mission-control/qps-triage-ultra`) dependable, sellable assets: libraries, an API and repeatable outcomes. Each wave is measured by the DevOps census (`devops/census.py`); a wave is done when the next census pulse shows its probes flip, not when a PR merges.

| Wave | Repository | Work | Probes it should move |
|---|---|---|---|
| A | cryoplant | Pin every action to a commit SHA; fail-closed core suite through `jade-reusable-ci.yml`; burn down untested live modules in slices | `build.pinned_actions`, `test.fail_closed`; the burn-down itself closes only on `test.controlled` (coverage floor ≥ 80 and untested ≤ 20% of modules) |
| A2 | hub census | Two tasks, each closed on its own signal. The code and both regression tests landed in #852 (`devops/census.py`, `devops/tests/test_devops_census.py`); every pulse scanned with it records `live_py_untested`, `live_zero_case_files`, `archived_test_files` and `archived_py_modules` in each repository's `tests` block. Each task still closes only when the next pulse shows its signal. **Imports:** count `src.`-prefixed imports as tested (`src/golden_thread.py` is tested but read as untested). **Archives:** a declared rule for archive trees, which hold all 4 of cryoplant's zero-case test files | Imports: regression test `test_src_prefixed_import_maps_to_the_module` passes, and cryoplant's `live_py_untested` drops by the modules that `src.` imports cover (no probe: `test.fail_closed` ignores import coverage). Archives: regression test `test_archived_copies_are_counted_apart_from_live_code` passes, and `test.fail_closed` (cryoplant) flips once `live_zero_case_files` is 0. An archive-only flip closes only the archives task |
| B | cryoplant + hub | Automated release tags and changelog | `release.automation` (S5 L2 → L3+). The probe flips on any tag-triggered build or deploy job, so B also closes on a receipt: a workflow run that created the tag itself and a changelog entry for that tag, both linked from the wave PR |
| C | cryoplant + QPS TRIAGE | Installable packages for the calculation core and the triage logic; a read-only HTTP API deployed through `jade-reusable-deploy.yml` | Plumbing: `deploy.contract`, `operate.rollback`, `monitor.live_parity`. These do not show that the packages or the API work, so C also needs, per deliverable: **package**: a CI job builds the wheel, installs it into a clean virtual environment and runs an import and smoke-calculation test; **API**: `deploy.verified` and `monitor.canary`, from a post-deploy and a scheduled read-only `GET` that returns 200 and the deployed source SHA. QPS TRIAGE is a hub directory the census does not scan, so its two checks run in hub workflows and the wave receipt names those runs |
| D | hub | Register both as hub consumers; one census pulse per wave; remediate cryoplant's 9 EVERRED red-trace workflows | `control.red_trace` closes only when those EVERRED entries are gone. The census does not observe that by itself: `scan` reads `control.red_trace` from the committed `data/RED_TRACE_FEDERATION_N8.json`. So the closing pulse re-harvests each core repository at the census head, in the same PR (AGENTS.md L6, L7). For each core repository: (1) take `<sha>` = that repository's `head_sha` from the new census file, the one SHA for this pulse; (2) extract its workflows at that SHA from the census cache, `mkdir -p <roots>/<name> && git --git-dir ../_jade_cache/<owner>__<name>.git archive <sha> .github/workflows | tar -x -C <roots>/<name>`; (3) harvest with `python mission-control/gogreen/red_trace/red_trace.py --repo <owner/name> --branch <default branch from TOP21_PORTFOLIO.json> --root <roots>/<name> --out <reports>/<name>` (`--out` is a directory and `red_trace.json` is written inside it; the branch defaults to `master`, which is wrong for ABACUS, CODEX, cryoplant-project and gg_MATH; `--root` makes the pinned-ID scan read that repository's workflows, not the hub's); (4) `red_trace.py` reads a branch, not a SHA, so confirm `unset GITHUB_TOKEN GH_TOKEN; gh api repos/<owner/name>/commits/<branch> --jq .sha` (PowerShell: `Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue; gh api repos/<owner/name>/commits/<branch> --jq .sha`) equals `<sha>` both before and after the harvest. Clear the tokens first (AGENTS.md L9-L10): a stale `GITHUB_TOKEN` outranks the stored `gh` login and returns 401, and a failed check never counts as a match. If the branch moved, retake the older snapshot, either the census or this harvest, until both agree. Never publish a mixed pulse. Then rebuild the snapshot with `python mission-control/jade_temple/tools/build_redtrace_data.py --reports <reports>`, and list each repository's `<sha>` in the pulse PR. Registration itself has no census probe yet (QPS TRIAGE is a hub directory, not a scanned repository), so it is checked against the hub consumer list |
| E | ML | Time series first (plant process data; census pulses as a series); DNN/CNN only with labelled data; GAN last, for synthetic data | Starts after C. No census probe covers it, so E1 (time series) closes on a committed forecast receipt: a forecast of one named census series (e.g. cryoplant `live_py_untested` per pulse) backtested on the latest pulse held out, over at least 5 pulses, beating the last-value baseline, with a test that re-computes the backtest. DNN/CNN and GAN are not scheduled: each gets its own acceptance check before it starts |

N+10 baseline:
- cryoplant stages: S0 L1, S1 L4, S2 L3, S3 L3, S4 L2, S5 L2, S6–S9 L3.
- Untested modules: 275 of 524 live modules. The other 456 of the census's 731 are archive copies.
- The hub is weakest at S1 L1 (lint configuration), S4 L2 (security scan in CI), S5 L2 (release automation) and S0 L2 (code-owners file).
- Wave A is GBOGEB/cryoplant-project#2071: action uses pinned 53/422 → 425/425; 13 new tests; zero-test guard `min-tests: 13`.

Recursive hooks:
- **Each pulse** (from the repository root): `python mission-control/jade_temple/devops/census.py fetch --cache ../_jade_cache --baseline-census mission-control/jade_temple/data/DEVOPS_CENSUS_N<k>.json`, then `python mission-control/jade_temple/devops/census.py scan --cache ../_jade_cache --iteration N<k+1> --baseline-census mission-control/jade_temple/data/DEVOPS_CENSUS_N<k>.json --out mission-control/jade_temple/data/DEVOPS_CENSUS_N<k+1>.json --objects mission-control/jade_temple/data/DEVOPS_OBJECTS_N<k+1>.json`. A wave row closes only when every acceptance signal in its row holds in the same pulse: all its listed probes, plus any receipt or check the row names. A single probe that flips to PASS closes only the task it belongs to, never the row. A flip to FAIL becomes the next wave's first item.
- **Burn-down slices:** each slice appends its test files to the caller's `test-args` and raises `min-tests`. Lowering it is a first red.
- **Pins:** Dependabot moves the SHA pins weekly, and each pulse recounts them. `build.pinned_actions` passes at 90%, so the 100% ratchet is checked on the raw `actions_pinned / actions_total` ratio per repository, not on the probe; any drop below 100% is a regression.
- **The JADE DAG:** the census is a pinned DAG input, so the pulse PR itself re-pins `data/CICD_DAG_POLICY.json` and regenerates and verifies the whole chain per AGENTS.md L7 with `python mission-control/jade_temple/tools/regen.py --write`, the single entrypoint added in #868 (`--list` prints its 12-step chain). Commit the census and policy first: the launcher step reads blob OIDs at a commit, so on `REGEN_DEFER launcher` commit and run `--write` again. Then `python mission-control/jade_temple/tools/regen.py --check` must report `REGEN_OK` before the pulse lands. Never land a pulse and re-pin later.
- **Gates:** write the FPC receipt before a wave PR leaves draft, and merge only once first-pass-closure is green on that exact head, Codex review included.

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