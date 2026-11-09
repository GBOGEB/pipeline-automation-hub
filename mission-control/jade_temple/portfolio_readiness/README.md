# Portfolio readiness: clusters, evidence and the next bounded wave

This directory adds a user-facing projection over the existing JADE and Mission Control owners. It connects a topic or epic to its repositories, granular tasks, source evidence, DOV/DOD and dependency order. The same projected data produces HTML, a machine-readable report, an action queue and a Mermaid DAG.

The operating goal is **source correction → exact-head native proof → independent review → effective admission verification → owner decision → comparable post-merge CONTROL**. A source-bound intake precedes that chain. The default plan contains sixteen tasks in eight clusters; the only initial candidate is the intake. Later stages remain visible and held until their required evidence is supplied.

## 1. Run the read-only projection

Run from the repository root. Choose a real observation time and the exact Hub source SHA used for this projection:

```bash
python mission-control/jade_temple/portfolio_readiness/portfolio_readiness.py \
  --as-of 2026-11-09T14:00:00+01:00 \
  --source-sha 897298dc3ed1a45607121b205617d4c103e7b226 \
  --plan mission-control/jade_temple/portfolio_readiness/plan.json \
  --out mission-control/issue_rank/out/portfolio_readiness
```

The timestamp and SHA above are an example bound to this plan's starting source. Capture fresh values for the next pulse, read the new source and update the plan through the same review process. A fresh rendering timestamp does not refresh the source observations underneath it.

Optional inputs:

| Argument | Input contract | Purpose |
|---|---|---|
| `--observation` | Source-bound observation supported by the projection CLI | Add current frontier observations separately from historical JADE evidence. |
| `--issue-snapshot` | Canonical `jade.issue-rank.snapshot.v2` input | Use the existing issue-ranking owner for issue/PR lineage, checklist status, pressure and rollups. |
| `--previous` | Previous portfolio projection | Compare compatible observations while retaining missing or stale inputs. |
| `--out` | Local generated-output directory | Keep the report and intermediate inputs outside tracked source. |

Run `--help` for the implemented options and validation. This first version projects plans and evidence; worker launch, schedule activation and GitHub mutations remain owned by their existing control paths.

### Outputs

| File | Use |
|---|---|
| `index.html` | Cluster-to-task navigation, dated evidence and source links. |
| `portfolio_readiness.json` | Machine-readable projection with source identities and explicit authority. |
| `action_queue.csv` | Portable task/owner/DOV/DOD review queue. |
| `execution_dag.mmd` | Dependency view over the canonical Kahn layering. |
| `watch_request.json` | Inactive monitoring request for existing scheduler owners to review and bind. |

These outputs are projections. Regenerate them from source; keep their source SHA, input digests, observation time and evidence state together.

The source-binding check reads local Git objects without fetching. It reports
`BASELINE_INPUTS_MATCH`, `BASELINE_INPUT_DRIFT` or `UNRESOLVED_BASELINE` for the
canonical owner code and recorded inputs. The consumer's working bytes are hashed
separately. A correctly shaped SHA alone does not authenticate those files, and
matching local Git blobs does not establish native execution or current release
qualification.

## 2. One owner for each definition

[AGENTS.md](../../../AGENTS.md) governs source ownership, overlap checks, exact pulse identities and generated JADE inputs. The facade delegates to the established modules.

| Concern | Canonical owner | Consumer responsibility |
|---|---|---|
| J0–J5 readiness meaning | [JADE_CASTE method](../03_JADE_CASTE_METHOD.md) | Display inventory, navigation, hosted evidence, governed candidate and released states distinctly. |
| H01–H12 collection | [focus5_pulse.py](../tools/focus5_pulse.py), [workflow registry](../data/FOCUS5_GATE_EVIDENCE_REGISTRY.json) | Preserve exact-head workflow evidence and owner/independent gates. |
| Temporal pulses, streaks and golden thread | [rolling5.py](../tools/rolling5.py) | Read verified hash-pinned snapshots and expose the latest source date. |
| Gate definitions and owner action queue | [build_gate12_dov.py](../tools/build_gate12_dov.py) | Preserve the frozen source date and its declared denominator. |
| Kahn layering and bounded candidate planning | [lifecycle.py](../devops/lifecycle.py) | Reuse `topo_layers()` and `rf_pulse_plan()`; show held dependencies and capacities. |
| B00–B09 bundle/SIPOC and bounded replay | [rf_matrix_wave.py](../tools/rf_matrix_wave.py) | Route deeper execution designs through the existing receipt and ancestry contracts. |
| Issue/PR graph, urgency, reverse pressure and rollups | [issue_rank.py](../../issue_rank/issue_rank.py) | Consume canonical ranking and public-safe projection. |
| Checklist and reference parsing | [triway_burndown.py](../../qps-triage-ultra/issue-expedition/triway_burndown.py) | Reuse through issue_rank; a tick remains a source declaration until verified. |
| Family, topic and technical-cluster classification | [title_taxonomy.py](../../issue_rank/title_taxonomy.py) | Keep disjoint primary families separate from nonexclusive topic facets. |
| Actions performance and queue metrics | [actions_metrics.py](../devops/actions_metrics.py) | Import source-owned values and denominators. |
| Public projection boundary | [private_boundary.py](../tools/private_boundary.py), issue_rank.redact | Preserve private-repository aggregate boundaries before output. |
| Statistical design and execution | [mip_statistical_qualification.py](../../federation-atlas/flightdeck/pulses/mip_statistical_qualification.py), [mip_provider_execution.py](../../federation-atlas/flightdeck/pulses/mip_provider_execution.py) | Route eligible requests to the exact [gg_MATH provider](https://github.com/GBOGEB/gg_MATH). |
| Existing Pages publication | [pages_portal.py](../../federation-atlas/pages_portal.py) | Stage a child through the canonical publisher after its parity and review gates. |

A change to a metric definition belongs in its owner module and its own reviewable branch. This consumer can add views, navigation and input validation without creating a competing metric.

### Historical source dates remain visible

The Gate12 owner can intentionally project a frozen FOCUS5 source while rolling5 contains later snapshots. Both are valid within their declared dates. Display each date and source identity. Do not substitute the Gate12 counts for a current census or combine evidence from different pulses into a single supposedly contemporaneous result.

Current-head comparison has three useful states: matching public identity, changed public identity and unavailable identity. A private aggregate marker is not a public SHA and cannot prove current-head parity.

## 3. Core seven, Top21 and user-defined clusters

The user's core interacting repositories are:

| Repository | Federation role |
|---|---|
| `GBOGEB/pipeline-automation-hub` | Mission Control, orchestration, canonical telemetry and projection owners. |
| `GBOGEB/ABACUS` | DOW evidence, runtime consumption and governed acceptance. |
| `GBOGEB/CODEX` | Contracts, semantic/provenance exchange and Mycelium consumer surfaces. |
| `GBOGEB/cryoplant-project` | Private engineering sources, canonical owner decisions and product evidence. |
| `GBOGEB/gg_MATH` | Numerical kernels, uncertainty and method qualification. |
| `GBOGEB/DOCX_RTM_Automation` | Document extraction, traceability, rendering and artifact proof. |
| `GBOGEB/GEMINI` | BLSN configuration, governed handover and cross-agent/Drive bridge. |

The canonical Top21 population remains the [Mission Control cohort roster](../../federation-atlas/central/top21/TOP21_COHORT_ROSTER.json). Core seven is a user's operational lens over the wider federation. FOCUS5 is a bounded observation window. None of these populations silently replaces another.

A cluster can span repositories and share a task or source with another cluster. Its count is a view of membership. Summing overlapping cluster counts does not produce a unique fleet total. Weighted closure remains unqualified until parent/child discovery, canonical root identity, duplicate disposition and complete weights are source qualified.

### Topic and epic entry

The plan makes the user's entry point explicit:

- `topic`: the human goal for this bounded slice;
- `clusters[].domain`: the functional area;
- `clusters[].epic`: the larger outcome;
- `clusters[].issue_refs`: existing repository-qualified issue identities;
- `tasks[].intent`: why this action matters;
- `tasks[].dov` and `tasks[].dod`: required verification and completion predicates.

Issue references and topic membership provide navigation. They do not close an issue, certify an edge or inherit another repository's acceptance.

## 4. Plan contract and disjoint lanes

[plan.json](plan.json) uses `jade.portfolio-plan.v1`. Every task has an identity, cluster, phase, crew, state, source identity, source reference, dependencies, declared paths and explicit DOV/DOD.

| Field | Meaning |
|---|---|
| `source_sha` | Exact Hub planning-source SHA against which this plan is validated. |
| `target_repo` | Repository that owns the work and its acceptance. |
| `target_head_sha` | Optional separately captured target identity; absence is unknown. |
| `t0_ref` | Source URL establishing the task's starting evidence/owner route. |
| `depends_on` | Task IDs that must complete before this task can qualify. |
| `touch_paths` | Exact repository-relative source paths for the target owner; use no globs, aliases or directory guesses. |
| `write_pr` | False in this preview. An intended edit is not an executed dispatch or path lease. |
| `state` | READY, HOLD or FAILED in the first version; no unverified DONE records. |
| `phase` / `crew` | Canonical lifecycle maturity phase and worker role. |

The planning source SHA is not the target repository's current head. Repository identity, branch, target SHA and declared paths must all be rechecked before an actual writer is assigned. A path declaration in this preview does not reserve that path against another active branch.

The default caps are two candidate workers and one candidate per cluster. The canonical planner also preserves its stack and dependency constraints. Changing a cap requires a documented source-owner policy decision and capacity evidence.

### Seven-stage execution order

1. **Intake:** recover starting intent, current heads, source ownership and the live frontier.
2. **Source lanes:** read/repair Hub, ABACUS, CODEX and N6 in disjoint owner paths; build the JADE consumer and reconcile bridge/artifact inputs.
3. **Native proof:** join the independently source-bound receipts for the selected scope.
4. **Independent review:** qualify reviewer eligibility and review freshness against each final head.
5. **Effective admission:** verify current required rules, trusted publishers and a permitted rejected-RED canary.
6. **Owner decision:** record the concrete merge/release decision and read back its result.
7. **CONTROL:** compare matched post-merge observations and retain regression/failure identity.

The DAG contains dependencies inside one pulse. Feedback belongs to the next pulse. A CONTROL-to-plan learning edge is temporal and does not create a shortcut through current admission gates.

### DOV and DOD

DOV is the verification evidence needed to evaluate a task: source SHA, native run/job/attempt, test population, digest, review identity or owner receipt. DOD is the complete behavior or accepted outcome required to finish it. The plan records both so that “implemented”, “tested locally”, “native verified”, “reviewed”, “merged” and “released” cannot collapse into one state.

The first version intentionally has no accepted execution-state adapter. Extending it to consume DONE requires the canonical receipt-validation path and independent authentication; a user-edited JSON value is insufficient.

## 5. Recursive and evolutionary operating method

Use the smallest evidence-bound wave that changes a blocking condition.

**DMAIC** is useful when the outcome is to characterize and reduce a known defect or variation: define the source population and criterion, measure it, analyze the first red, improve the source, then control recurrence. **MIP — Modernize, Innovate, Perpetuate** is useful when evolving capabilities: modernize existing interfaces, trial a bounded new capability, and perpetuate the accepted behavior through tests, receipts and ownership.

Their order follows the problem. A regression can begin with DMAIC and use MIP to preserve the repair. A new user-facing capability can begin with MIP design, then use DMAIC to measure its reliability. Neither method bypasses the source-to-admission dependency chain.

For every pulse retain:

- the original intent and canonical root identity;
- the source population, instrument version and exact heads;
- attempted action, proof acquired and actual outcome;
- scope growth separately from completion;
- old-to-new and new-to-old dependencies;
- failure identity, deferred decisions and supersession reasons;
- a concrete N+1 action and an N+2 expectation to score later.

Predictions are recorded before outcomes. Later observations score those predictions; history is not rewritten to fit the result. Repeated observations of the same source/run do not become independent trials.

### Golden thread and Mycelium

The golden thread follows the evidence chain from source identity through generator/build, native test, review, artifact digest, admission and owner release. Mycelium provides the wider web of typed references and linked work. A reference can establish association without establishing a causal or blocking dependency.

The user can start wide with cluster counts and missing evidence, then go deep through the exact task, issue, PR, commit, workflow, run, attempt and artifact. Conversely, a new first-red root can be followed upward to every affected cluster without duplicating the root's closure credit.

## 6. CRON and temporal telemetry

`watch_request.json` starts inactive. It describes the monitoring request for the existing scheduler owners. Bind the request to the current MIP, N6, weekly calibration or bridge role after checking ownership and cadence. This avoids duplicate collectors measuring the same population under competing definitions.

A monitoring pulse should:

1. capture one source identity per repository;
2. consume canonical collectors with bounded pagination, timeouts and cache freshness;
3. retain partial, unavailable and complete source states;
4. project cluster counts and granular source links;
5. calculate deltas only for comparable observations;
6. stop or park when no new eligible evidence exists;
7. route a changed first red or source identity to the existing owner lane.

Expose capture time, source time, observation age, method version, numerator, denominator, missingness and scope. A new dashboard timestamp is not a new measurement. Point-release readiness, queue wait, code coverage and formal closure each keep their own definitions.

The delta's comparability is limited to the view schema and declared cohort. It is
not a qualified native CONTROL comparison. An unchanged issue snapshot remains
the same evidence when its calculated age increases; a declared source-freshness
transition is a separate event. The initial 24-hour display threshold is a preview
policy, not an accepted operational SLO or a statistical control limit.

## 7. PCA, Bradley–Terry and reverse pressure

Use existing issue-rank pressure to prioritize work while its assumptions remain visible. Its current contract calls the ordering `NON_BT_REVERSE_PRESSURE_PAGERANK`; it is advisory and does not claim observed pairwise outcomes.

For PCA, prepare a source-bound observation-by-feature matrix, its units/scaling, missingness policy and sampling geometry. Retain eigenvalue/eigengap and subspace diagnostics. Temporal comparisons must align component identities and signs before interpreting changes.

For Bradley–Terry, collect actual eligible pairwise outcomes with identities and a defensible comparison population. Verify identifiability, graph connectivity and finite-fit conditions. PCA loadings or derived strengths are not observed wins. Swapping labels does not manufacture a reverse trial.

Use [ggmath_provider_binding_v1.json](../../qps-triage-ultra/ggmath_provider_binding_v1.json) and the canonical design/execution adapters. Provider math, local numerical agreement and synthetic fixtures do not create empirical process evidence or engineering acceptance. A withheld fit is a useful result when the data do not support it.

## 8. Envisaged implementation TODO

### Current bounded consumer

- [ ] Read canonical JADE pulse and owner-action outputs without changing their definitions.
- [ ] Preserve source dates and the distinction between frozen, latest historical and current-head observations.
- [ ] Render topic/cluster/repository/task navigation and source-linked DOV/DOD.
- [ ] Delegate Kahn and candidate selection to the canonical lifecycle owner.
- [ ] Consume canonical issue snapshot/ranking when provided; otherwise show it as unavailable.
- [ ] Project private evidence before producing public output.
- [ ] Emit an inactive watch request with explicit scheduler ownership and bounded cadence intent.
- [ ] Run focused positive and negative tests plus browser interaction/layout verification.
- [ ] Bind a reviewable branch and native exact-head result before any completion claim.

These are reusable acceptance checks; current completion belongs in source-bound tests, native receipts and the PR. The checkboxes are not a live status database.

### Next source-owner improvements

- [ ] Reconcile Gate12 frozen-snapshot selection with the intended latest-pulse view in the Gate12 owner.
- [ ] Add an authenticated execution-receipt adapter through the existing RF matrix contract before accepting DONE.
- [ ] Complete source-qualified root/child discovery and deduplication before a weighted closure rate.
- [ ] Add complete same-method workflow-history receipts and queue/recovery comparison.
- [ ] Bind experimental-design receipts and actual pairwise outcomes before numerical PCA/BT promotion.
- [ ] Stage the public-safe child through the existing publisher and verify served SHA/browser parity.
- [ ] Score N+1/N+2 predictions against later actuals and preserve the resulting REX.
- [ ] Expand parallelism only after source, runtime and owner capacity are evidenced across repeated observations.

## 9. Acceptance and release boundary

A useful local view is complete when its inputs, canonical delegation, output lineage, privacy and user interaction are verified. Repository admission additionally requires terminal native proof on the final head, eligible independent review, effective protection and the owner's decision. A point release additionally requires its actual tag/version, assets, publication and rollback proof.

Keep these outcomes separate in reports. The facade's authority remains read-only and its release/admission state remains held until the responsible source owner supplies the required evidence.
