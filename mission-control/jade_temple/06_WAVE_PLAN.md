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
| A | cryoplant | Pin every action to a commit SHA; fail-closed core suite through `jade-reusable-ci.yml`; burn down untested live modules in slices | `build.pinned_actions`, `test.fail_closed` |
| A2 | hub census | Count `src.`-prefixed imports as tested (`src/golden_thread.py` is tested but read as untested); a declared rule for archive trees, which hold all 4 of cryoplant's zero-case test files | `test.fail_closed` (cryoplant) |
| B | cryoplant + hub | Automated release tags and changelog | `release.automation` (S5 L2 → L3+) |
| C | cryoplant + QPS TRIAGE | Installable packages for the calculation core and the triage logic; a read-only HTTP API deployed through `jade-reusable-deploy.yml` | `deploy.contract`, `operate.rollback`, `monitor.live_parity` |
| D | hub | Register both as hub consumers; one census pulse per wave | `control.red_trace` |
| E | ML | Time series first (plant process data; census pulses as a series); DNN/CNN only with labelled data; GAN last, for synthetic data | after C |

N+10 baseline:
- cryoplant stages: S0 L1, S1 L4, S2 L3, S3 L3, S4 L2, S5 L2, S6–S9 L3.
- Untested modules: 275 of 524 live modules. The other 456 of the census's 731 are archive copies.
- The hub is weakest at S1 L1 (lint configuration), S4 L2 (security scan in CI), S5 L2 (release automation) and S0 L2 (code-owners file).
- Wave A is GBOGEB/cryoplant-project#2071: action uses pinned 53/422 → 425/425; 13 new tests; zero-test guard `min-tests: 13`.

Recursive hooks:
- **Each pulse:** `census.py scan --iteration N<k+1> --baseline-census N<k>`. A probe that flipped to PASS closes its wave row; a flip to FAIL becomes the next wave's first item.
- **Burn-down slices:** each slice appends its test files to the caller's `test-args` and raises `min-tests`. Lowering it is a first red.
- **Pins:** Dependabot moves the SHA pins weekly, and each pulse recounts them. Pinned below 100% is a regression.
- **The JADE DAG:** after a pulse lands, re-pin `data/CICD_DAG_POLICY.json` and regenerate per AGENTS.md L7 (#834 → #837).
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