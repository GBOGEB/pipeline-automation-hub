# QPS TRIAGE ULTRA — Mission Control

Status: `W0_BOOTSTRAP`

QPS TRIAGE ULTRA is the persistent HOME mission-control brain for the frontier program. It duplicates HOME competencies, not every transient worker.

Operational primitive:
`Mission -> Wave -> Pulse -> Receipt -> Reallocate -> Recurse`

Authority boundary: this node may plan, route, schedule, measure, compare, correlate and recommend. It must not promote engineering/compliance truth or bypass KEB/DOW/child authority. `authority_transfer=false` remains mandatory.


## Mission Control v2 operating model

New Mission Control orchestration semantics are governed by `mission-control/v2/MISSION_CONTROL_CURRENT_v2.json` and its bound glossary, method-profile, telemetry, DMAIC and validator controls. Historical QPS TRIAGE / 3P* / MIP receipts retain their original meaning and are not rewritten.

Key namespace rules for new machine identifiers: `MC` means Mission Control; Monte Carlo uses `MONTE_CARLO` or `MC_SIM`; mission-control coverage maturity uses `MCOV-0..MCOV-5`; software coverage remains qualified numeric coverage fields. Crew members and runners are separate resource concepts.

## Permanent competency seats
1. U01 Mission Commander / Governor
2. U02 Chief Architect / Architecture Hat
3. U03 Project Manager / portfolio sequencing
4. U04 Fleet Orchestrator / scheduler
5. U05 Analyst / DMAIC + measured PCA + observed BT
6. U06 QA / Signalman / provenance
7. U07 Cartographer / Oculars / node-edge-temporal graph
8. U08 REX / doctrine / KEB integration

The Architecture Hat owns the coherent model of people, functions, roles, capabilities, interactions, nodes, edges, atoms, graphs, authority and temporal lineage.

## Crew capability system

The canonical candidate crew layer lives under `crew/` and adds:

- `CREW_REGISTRY_v1.json` — permanent seats, observed specialists, partial roles and conceptual crew candidates.
- `COMPETENCY_MATRIX_v1.json` — L0-L6 competency scale, evidence classes and promotion rules.
- `REX_LEARNING_LEDGER_v1.json` — bidirectional mission-to-REX-to-crew learning.
- `ROLE_DEVELOPMENT_POLICY_v1.json` — mission-feedback-driven new-role planning, trial, promotion, merge, prune and return.
- `validate_crew_system.py` — executable structural and authority validation.

Crew competence is evidence-backed state, not a title. Seeded competency vectors are planning priors until replaced by accepted mission/runtime receipts. Conceptual roles cannot hold promotion or CONTROL authority.

The Ambassador is an observed specialist role with a bounded claim/authority-reconciliation function. New roles are admitted only from repeated mission need, REX, resource pressure, authority-independence needs, or stable PCA/BT workload clusters.

## Coverage invariant
Every active frontier must close a wave with either the required evidence receipt or an explicit DEFER/PARK/PRUNE disposition. Fleet mean coverage never substitutes for the minimum-frontier coverage floor.

## Reuse
The existing `level1/runtime.py` remains the executable census/MIP/PCA/BT/orchestration engine. ULTRA extends it with fleet state; it does not duplicate healthy Level-1 logic.

## Repository function topology

Repository routing is controlled by function rather than by historical activity alone. The current machine-readable topology is `topology/QPS_REPO_FUNCTION_TOPOLOGY_v1.yaml`; the human control view is `topology/QPS_REPO_FUNCTION_TOPOLOGY_v1.md`.

The topology distinguishes `ACTIVE_USED`, `EXECUTION_SATELLITE`, `CONTROL_RESERVE`, `CONDITIONAL_RESERVE`, `DORMANT_CANDIDATE`, and `MAINTENANCE_ONLY`. These are routing states only. They do not alter the authority boundary above.

Current high-value route: QPS engineering/source/disposition remains in `GBOGEB/cryoplant-project`; `GBOGEB/Q_engineering_tools` is the bounded exact-payload execution carrier when child Actions admission is blocked; `GBOGEB/CODEX` and `GBOGEB/ABACUS` remain semantic and independent-measurement receivers; `GBOGEB/gg_MATH` is a reusable math provider held in CONTROL reserve. Dormant candidates receive no workers until a named source/consumer blocker justifies activation.

## gg_MATH math bridge

QPS TRIAGE consumes `GBOGEB/gg_MATH` kernels without vendoring them. `ggmath_provider_binding_v1.json` pins the provider by exact 40-character SHA and lists the SHA-256 of every bound kernel (plus its import closure and the GM-I-A measured pulses). `ggmath_bridge.py` fetches those files by that SHA, verifies every digest, and executes only the verified bytes; a mismatch, a missing file or an import outside the bound closure stops with a `DEFER_*` status.

- **Adapters** (`ggmath_bridge.py`): BT strength with Wald intervals and bootstrap rank frequency (classical MLE only when the win graph is strongly connected); BT order effect from forward and *independently observed* reverse trials (never swapped labels); reverse-pressure BT over measured lane queue waits; PCA retention (scree, MP edge, PA95, eigengap guard, bootstrap subspace); PCA alignment and temporal subspace uncertainty; RMT calibration; convergence classification; temporal principal-angle / Grassmann trace. Every output carries a `threshold_kind` and `authority_transfer: false`. PCA outputs are tagged `bt_admissible: false`, and BT rejects any record with PCA/RMT provenance.
- **Flow KPIs** (`ggmath_flow_kpi.py`): flow efficiency `execute/(queue+execute)`, queue/execute ratio and a closed-window Little's-law consistency field, computed on the GM-I-A pulses and the fleet iteration ledger.
- **Plotly** (`ggmath_plotly.py`): deterministic figure JSON in `site/_data/ggmath_bridge_figures.json`, rendered by `site/ggmath-bridge.md` with an offline plotly.js that the web build vendors from `plotly==7.0.0`. No CDN.
- **JADE hook** (`ggmath_jade_hook_v1.json`, `ggmath_jade_hook.py`): disabled by default. Enable it in a reviewed PR once `jade_temple/tools/rolling5.py` is on master. It is read-only.

Regenerate with `python ggmath_bridge.py build` and then `python ggmath_plotly.py`. Bump the pin with `python ggmath_bridge.py rebind --sha <40-hex>`, which recomputes every digest from the new SHA, then rebuild and review the diff.

## P process (Code Purple × EVERRED)

`p-process/` holds the acute Code Purple mode and the recursive EVERRED 3.0 mode as one loop: lift census, root ledger, ruleset drift probe, BASIC rulesets for owner import, and a refreshable site with a 16:9 companion PDF. See `p-process/README.md`.
