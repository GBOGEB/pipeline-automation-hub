# JADE N-series / OID crosswalk — read-only overlay v0.1

> Authority: `READ_ONLY_PROJECTION` · Admission: `HOLD` · Source evidence: DECLARED / UNVERIFIED at this layer. This project does not replace `cicd_dag.py`, its OID lens, EVERRED, CODEX KEB, ABACUS DOW, QPS Object BIOS or the existing JADE publisher.

## Source, implementation and invocation

- **Registry:** [data/N_SERIES_REGISTRY_v1.json](data/N_SERIES_REGISTRY_v1.json), 23 namespaced node records and 22 typed relationships.
- **Generator:** [tools/nseries_overlay.py](tools/nseries_overlay.py), which invokes the *existing* `devops/lifecycle.py::topo_layers` Kahn method rather than duplicating it.
- **Adversarial tests:** [tools/test_nseries_overlay.py](tools/test_nseries_overlay.py).
- **Generated local views:** `diagrams/GLOBAL_N_SERIES.mmd`, `diagrams/N_SERIES_DEPENDENCIES.mmd`, `site/nseries_atlas.html`, `site/nseries_atlas.json`. No new hosted publisher or canonical metric owner is created.

From the repository root, with Python 3.11+:

```powershell
Remove-Item Env:GITHUB_TOKEN, Env:GH_TOKEN -ErrorAction SilentlyContinue
python -m unittest discover -s mission-control/jade_temple/tools -p test_nseries_overlay.py -v
python mission-control/jade_temple/tools/nseries_overlay.py --write
python mission-control/jade_temple/tools/nseries_overlay.py --check
Start-Process mission-control/jade_temple/site/nseries_atlas.html
```

The CI workflow for this overlay runs tests and generates a downloadable **candidate artifact**, but does not mutate owner repos or publish under JADE's shared site. If generated outputs are later committed, they must be regenerated and checked on the exact PR head, and their stale state cannot be treated as admission.

## Type system and governance

| Edge type | Kahn hard dependency? | Admission meaning |
| --- | --- | --- |
| `HARD_DAG` | Yes, within declared GLOBAL method only | Proposed global ordering; **not** native execution |
| `TEMPORAL_SUCCESSOR` | No | Historical/source-declared progression |
| `CANDIDATE_LINEAGE` | No | Review required before stronger semantics |
| `REFERENCE_ONLY` | No | Search/where-used pointer; no authority transfer |
| `NEXT_PULSE` | No | Temporal feedback, excluded from same-pulse cycle analysis |

The integer names are namespace-local: `GLOBAL:N6`, `WATCH:N6`, `MYCELIUM:N7` and `QPS.DOC:N400` do not belong to one numerical scale. A graph reference cycle is not a Kahn worker-dispatch cycle. Never turn source owner links into executable edges without exact-head native receipts, independent qualification and an owner decision.

**OID is not one universal identifier.** JADE FUNCTION/SHA/OID relates to Git source/blob identity. The QPS `publishing/r07/object_bios.schema.json` relates to source-bound engineering elements. PUB-R07 workflow OIDs name process lanes. These identifiers require a *typed, owner-accepted* relationship before semantic promotion.

## Existing canonical boundaries

- JADE DAG and OID view: `tools/cicd_dag.py`, `data/CICD_DAG_POLICY.json`, `site/cicd_dag.html`.
- Kahn implementation: `devops/lifecycle.py` (`topo_layers`).
- Code/P-process, EVERRED, issue/BD ranking: their existing owners as specified in root `AGENTS.md`.
- CODEX MYCELIUM: `GBOGEB/CODEX/mission_control/mycelium/continuity/` (historical view).
- QPS topology: `GBOGEB/cryoplant-project/tools/repo_topology/n4/` (declared vs runtime separated).
- QPS semantic object authority: `GBOGEB/cryoplant-project/publishing/r07/object_bios.schema.json`.
- GoGREEN: `mission-control/gogreen/scale-dock/` (no duplicate metrics or dispatch).

## DoD / DoV

DoD for this *bounded source increment* is: isolated branch, schema and generator present, adversarial tests executed on an exact head, artifact outputs inspectable, independent review and owner acceptance recorded. Native acceptance, effective FPC and required checks remain separate gates.

**Current claims:** source implementation available for review. Native test results, hosted user acceptance, human approval, real source-scale throughput and final merge admission remain **UNKNOWN / HOLD** until exact-head receipts exist. No policy, FPC controller, owner root ledger, queue schedule or W169 runtime is changed here.
