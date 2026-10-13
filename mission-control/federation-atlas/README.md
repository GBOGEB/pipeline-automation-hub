# CODE PURPLE Federation Method Atlas (v0.1)

Owned by `GBOGEB/pipeline-automation-hub` Mission Control. A read-only projection, not another QPS engineering authority, release writer, or Pages publisher.

## Bounded run / task

Workflow: `.github/workflows/code-purple-method-atlas.yml`. Runs tests and emits downloadable `index.html`, `federation.svg` and `metrics.json` on PR, relevant master update, or manual method-pulse dispatch. No automatic merge, issue mutation, web publication, or engineering-state promotion.

Stages: SIPOC, DAG, DMAIC, 3P*, conditional MIP, measured PCA, BT/backtesting and LDAB. The canonical Mission Control method registry remains `mission-control/v2/MC_METHOD_PROFILE_REGISTRY_v1.json`. SIPOC/DAG/PCA/BT/LDAB are observability projections, not newly admitted canonical stage lifecycles.

`ATLAS_GRAPH_v1.yaml` is the graphical single source for node coordinates, labels and typed edges. `build_atlas.py` renders HTML/SVG/JSON without raster assets; the generated image is not itself SSOT. Source snapshot timestamps are visible, so a green check on an older source cannot be mistaken for current CI.

Doctor/REX: only observed application red, >0 executed steps, and an exact 40-digit SHA create an advisory DOCTOR_REX_LOOKUP. 0-step red goes to DOCKMASTER. Owner-external goes to RETURN_OWNER. No regression or source repair is automatically claimed. Its next integration is historical REX lookup keyed by root-family, code signature, source context and subsequent measured repeat evidence.

## Hierarchy and links

Mission -> Sprint -> Wave -> Pulse -> Run, plus cohort -> repo -> PR -> checks/receipts. Existing dashboard and source links are in `METHOD_OBSERVABILITY_v1.json`, with hosted Pages entrypoints marked `HOSTED_CANDIDATE` until a fresh Pages URL/content-identity readback. Generated artifact can be consumed by an existing governed Pages publisher; this PR MUST NOT independently enable another publisher.

Future connector: bind actual GitHub PR/check events, workflow run evidence, exact SHA and optional runner/Kubernetes telemetry; expose missing fields as UNKNOWN. Never substitute forecast output for a gate. Feed completed `CONTROL` receipts to the next iteration; preserve HOLD/RETURN/DEFER predicates.

## QA

`python -m pip install pyyaml==6.0.3 && python -m unittest discover -s mission-control/federation-atlas -p 'test_*.py' -v`

`python mission-control/federation-atlas/build_atlas.py --out /tmp/code-purple-atlas --method DMAIC --stage MEASURE`

Admission requires exact PR-head CI and reviews, then governed merge and exact-main readback. Artifact generation is not publication.

## Phase 02 KPI and glossary extension (2026-10-12)

Six and only six ID-bound KPI families are defined in `PHASE02_KPI_TAXONOMY_v1.json`: queue p95, exact-head proof yield, first-red count, accepted receipt yield, forecast-vs-actual, and runner health. Each requires source SHA, observed time, window, owner, population, unit, denominator and evidence class; all current numerical values remain null/UNBOUND until exact-source telemetry is ingested. The glossary extension lives in `mission-control/v2/MC_GLOSSARY_TAXONOMY_v2.json` with its own date, not a forged refreshed date for the 2026-09-27 snapshot.

BT is Bradley-Terry pairwise ranking (not backtesting). Forecast scoring uses `FORECAST_BACKTEST` and must be prediction-before-observation. LDAB/AHT remain contextual labels pending authoritative expansion. Doctor zero-step is reserved to Dockmaster, not application Doctor. Run `python -m unittest discover -s mission-control/federation-atlas -p 'test_*.py' -v` and the existing Mission Control v2 validator on exact head.

## CODE PURPLE control page, BD queue and ordinal series (2026-10-13)

| File | Role |
|---|---|
| `CODE_PURPLE_BD_QUEUE_v1.json` | Review findings and follow-ups as BD items (`CPQ-NNN`). Lifecycle reuses the BD/REX register (`TODO -> ACTIVE -> DONE -> CONTROL`); `flow` says whether an item can start now (READY), is in review (IN_PR), or waits (BLOCKED, HOLD, RETURN_OWNER, LINKED). Every state change is a history row keyed by series ordinal. |
| `CODE_PURPLE_ITERATION_SERIES_v1.json` | Append-only metric series keyed `W<wave>.C<cycle>.I<iteration>.S<sub>`, not by time. Each entry stores metrics recomputed from repo files, the delta to the previous entry and the SHA-256 of the previous entry. |
| `CODE_PURPLE_BEAMS_DAG_v1.json` | Ten beams (workstreams) with entry/exit criteria, triggers, feedforward and feedback edges, the critical path to the Top14 gate, SIPOC+DMAIC candidates with forecasts issued before outcomes, and the trigger table. |
| `TOP7_CENSUS_PULSES_v1.json` | Top7 recensus pulses transcribed from their governed record; proof debt per pulse. |
| `schemas/*.schema.json` | JSON Schema 2020-12 source for the queue and series. Python executes it in CI; any TypeScript/zod type must be generated from it. |
| `code_purple_series.py` | `check` (CI), `append`, `show`. Exit 0 PASS / 1 FAIL / 2 INCOMPLETE. |
| `build_code_purple.py` | Renders `code-purple.html` and `code-purple.json` (`--fragment` for hosts that add the document skeleton). |

Rule: when a change moves any computed metric (contract, coverage telemetry, topology, queue states, zero-test audit), the same PR appends a series entry:

```
python mission-control/federation-atlas/code_purple_series.py append --key W1.C1.I2.S1 --closes SUB --label "what closed"
```

`ATLAS_GRAPH_v1.yaml` edges now carry `binding: RECEIPT | DECLARED`; declared edges render dashed because no cross-repo dispatch workflow exists yet (CPQ-015).
