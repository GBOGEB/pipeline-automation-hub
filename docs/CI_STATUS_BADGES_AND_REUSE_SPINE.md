# CI status badges, reuse spine, and branch extraction

> **Status:** source-bound pilot, 2026-10-28. Documentation only. **Not certification, not release admission, and not authorization to merge, delete, deploy, or accept engineering output.**
>
> **Entry:** [root README](../README.md) | [existing AGENTS ownership](../AGENTS.md) | [existing branch-hygiene workflow](../.github/workflows/branch-hygiene.yml) | [historical branch lists](../governance/branch_hygiene/README.md)

## 1. Make the trust signal honest

GitHub's workflow badge reports a workflow-run conclusion, **not** an independent certification and **not** the result of every required check on the current pull-request head. The GitHub badge endpoint defaults to the default branch, or to the last run on any branch if the default branch has no run. For this repo, explicitly scope display badges to `branch=master`.

| README signal | Existing workflow | What it exercises | What it does NOT prove |
| --- | --- | --- | --- |
| Zero-test gate | [zero-test-gate-guard.yml](../.github/workflows/zero-test-gate-guard.yml) | Audit of test collection on changed workflows/tests and master | Every project feature or current PR head has passing tests |
| JADE DevOps census | [jade-devops-census.yml](../.github/workflows/jade-devops-census.yml) | Scheduled/default-branch census and offline contract tests | Live fleet acceptance, fresh global state, merge authority |
| Golden Thread replay | [golden-thread.yml](../.github/workflows/golden-thread.yml) | Deterministic ledger, historical replay and temporal controls | Engineering authority, current production availability |

**Badge interpretation:** a green badge is the latest matching workflow result, possibly older than the current `master` commit if that workflow was skipped by path filters. A red badge is a real failure signal; a missing badge is not a pass. Always follow the workflow link and inspect the exact run, event, SHA, attempt, job count, skipped tests, receipt and required checks before any approval.

**Merge predicate:** current PR head + required checks from effective branch rules + independent eligible review/thread disposition + owner-specific source-to-evidence policy. Follow [AGENTS.md](../AGENTS.md). A badge can inform discovery but is never an input that overrides this predicate.

GitHub documentation: https://docs.github.com/en/actions/how-tos/monitor-workflows/add-a-status-badge

## 2. Own a narrow custom layer; reuse the proven infrastructure

| Layer | Reuse instead of inventing | Project-specific responsibility |
| --- | --- | --- |
| Source / CI primitives | GitHub Actions, pinned checkout/setup actions, artifacts, branch rules | Path-scoped workflow selection and identity contracts |
| Reusable CI | [jade-reusable-ci.yml](../.github/workflows/jade-reusable-ci.yml), existing zero-test and coverage controls | Define test population, acceptance bounds and legitimate negative tests |
| Provenance and release | Existing exact-SHA CI receipts, first-pass closure policy and artifact manifests | Interpret and qualify source-to-evidence links; never claim authority from green alone |
| Telemetry | `scale_dock.py`, `actions_metrics.py`, `rolling5.py` | Causality, rate denominators, historical deltas, issue/PR priority |
| DAG / SIPOC | `cicd_dag.py` and existing Mission Control projections | Object identities, supplier/input/process/output/customer edges, dependency ordering |
| Branch custody | `branch-hygiene.yml` + `branch_hygiene_delete.py` | Decide which intent survives, belongs in the canonical owner, and merits extraction |
| Documentation / Compendium | Plain README, linked source files, existing site generators | Explain the project: why, constraints, decisions, exceptional conditions and loose ends |

**Duplication control:** per AGENTS L4, search `master` and open PRs for matching modules/metrics before creating another owner. Reuse functions and existing workflows; customize only an adapter, an ownership decision or a domain test. Favor `workflow_call` for repeatable CI; do not assume a test result transfers to another repository or commit.

### Textual SIPOC and dependency spine

| ID | Supplier | Input | Process / authoritative owner | Output | Customer / use | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| SP-01 | GitHub repository | Exact commit SHA, file tree | Existing pinned checkout and CI | Job/step runs at identified SHA | CI consumer | Exact-head match |
| SP-02 | Existing tests | Defined test population and negatives | `jade-reusable-ci.yml` or domain test workflow | Executed count, coverage and receipt | Review / quality | No zero-test false green |
| SP-03 | GitHub runs | Jobs, attempts, timestamps, conclusions | `actions_metrics.py` and `scale_dock.py` | Weighted failure/recovery series with denominators | Mission Control / DMAIC | No aggregate run-count conflation |
| SP-04 | Workflow source + evidence | SHA/OID, DAG edges, historical pulses | `cicd_dag.py` and `rolling5.py` | DAG/SIPOC crosswalk and temporal deltas | Project compendium | Source-bound, no hindsight |
| SP-05 | Governance | Review decision, policy, exact-head receipts | Existing first-pass closure gate / rulesets | Approval-eligible or HOLD | Maintainer | Noncompensating required gates |

Dependency order: **SP-01 → SP-02 → SP-03 → SP-04 → SP-05**. External acceptance/engineering authority is downstream and separately controlled.

## 3. Branch pruning and retaining only the useful part

Existing branch inventory (2026-10-11, **historical**): 353 non-default branches in W1 (271 `delete`), W2 (53 `archive`), W3 (18 `archive`), W4 (11 `archive`). Do not treat the census as an executable live decision. The existing script uses expected-head lease, protection checks, open-PR checks, merged-ancestry proof or SHA-checked archival tag. Start with a fresh, read-only dry run. W4 explicitly contains potentially unlanded executable fixes and requires extra owner review.

**Pilot branch case, observed 2026-10-28:** `mission/gm-iv-runtime-capacity-proof` was present at commit `1f69bcbd6b84ee84f412f53290301612917d61cc`, unprotected, with **4 ahead / 3059 behind** the then-current master `ca623ab83793df6edd245942884ad5428a5fe079`. Its comparison showed four changed paths: a workflow, one JSON contract and two Python scripts. This is a good **candidate for selective reuse examination**, **not** proof that its four changes are still wanted or can be merged. A newer `gm-iv-runtime-capacity-proof-v2.yml` workflow already exists; review semantic overlap first.

### Three safe extraction methods (choose one)

1. **Keep selected file contents, not old branch history:** branch from current master; fetch old branch; `git restore --source=origin/mission/gm-iv-runtime-capacity-proof -- mission-control/grand-missions/GM_IV_RUNTIME_CAPACITY_MEASUREMENT_CONTRACT.json`; inspect and commit only after validating against current canonical owner. This creates a new commit; it does *not* import every old change.
2. **Keep selected commits:** create a fresh branch from current master and `git cherry-pick -x <reviewed-commit>` for independently valid commits. If old commits are mixed, split by files instead of blindly cherry-picking.
3. **Keep directory-specific history:** use `git subtree split --prefix=<directory> <old-ref> -b extract/<name>` in a disposable clone, then audit the resulting history. It extracts a directory, not an arbitrary sub-file selection. `git filter-repo` rewrites history and belongs only in a disposable clone/new repo.

A Git branch normally points to a full repository tree, **not** a folder-only snapshot. To retain just one directory as a standalone product, use a filtered/subtree history in a separate extraction branch or repository. Do not force-push the old branch, disturb stacked PR bases, delete an open-PR head, or dispose of the source before proof and an archive tag.

**Governed prune order:** classify → inspect file/commit overlap and downstream PR dependency → extract/rebase and validate only surviving intent → archive tag and verify exact SHA → recheck current branch head and rules → delete only via the existing guarded workflow when approved → retain restore receipt. No branch is deleted by this documentation pilot.

## 4. One bounded experiment, not another platform

| Stage | Task | Proof / stop criterion |
| --- | --- | --- |
| P0 Discover | Read source GitHub `setup-node` badge syntax, current Hub workflows, AGENTS and branch inventory | Named existing owner for every capability; no duplicate workflow |
| P1 Pilot | Add three live, branch-scoped existing workflow badges to the root README and this trust index | Badges link to actual workflow files; zero new runners |
| P2 Validate | Inspect linked run histories, SHA freshness, check population, PR rules and existing CI on the pilot head | Record exact run IDs and failing paths; do not claim a pass before observed |
| P3 Scale | Apply the same lightweight, source-bound README pattern repo-by-repo when it helps navigation | One owner per metric, versioned compendium, no badge-as-certification |
| P4 Prune | Run the existing lossless W1–W4 dry-runs with fresh expected SHAs | Review and archive unlanded sources before explicit deletion |

**Scope of this pilot:** README and documentation only; no workflows, tests, branch rules, required checks, PR states or source code changed. Any further implementation must use an independent reviewed PR, exact-head evidence, and the existing repository protections.
