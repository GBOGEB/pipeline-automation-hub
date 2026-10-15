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

## Granular SIPOC / method-lane projection (15 October 2026)

The **same** `code-purple-method-atlas.yml` workflow now builds
`lane-process.html`, `lane-process.mmd`, and `lane-process.json` by
calling `lane_process.build()` from `build_atlas.py`. This is a companion
view within the existing artifact and publisher, **not** a second workflow,
Pages release, method registry or acceptance authority.

- Canonical input: `PROCESS_LANES_v1.json` (10 lanes, 39 executable-stage
  descriptions, SIPOC input/output, KPI pressure and explicit stop rule).
- Canonical method-stage names for DMAIC, 3P*, MIP, LDAB are checked against
  `METHOD_OBSERVABILITY_v1.json`. REX/Census and M1/M2/M3 are overlays, not
  new canonical method admission.
- Output JSON measures a **historical, exact-PR-head G4** native run
  (#38707835880) and focused G4 same-source test expansion. It distinguishes
  1/42 -> 6/42 observed source/status cells from missing archived-byte proof.
  The only measured code coverage shown is 78/93 -> 93/93 statements and
  23/26 -> 26/26 branches on the same focused module.
- M2, M3, PCA, BT, worker-hours and authentic LLDB/runtime telemetry remain
  HOLD/UNKNOWN. Six scouts, two concurrent and one packet/repo are **planned
  upper bounds**, not claimed active worker count.
- Mermaid includes the same-wave feedforward nodes and marks feedback
  explicitly as belonging to the **next** pulse. HTML includes accessible
  filterable lane leaves; each shows input, output, KPI and stop reason.
- SIPOC and stage cards have no GitHub write actions. Gate P5–P9 display
  independent governance, byte-verification, stability and recurrence needs.

Execute focused checks (the existing atlas test discovery picks these up):

```bash
python -m pip install pyyaml==6.0.3
python -m unittest discover -s mission-control/federation-atlas -p 'test_*.py' -v
python mission-control/federation-atlas/build_atlas.py --out /tmp/code-purple-atlas
```

The rendered HTML is an **offline artifact**; GitHub Pages publication
and signed run/artifact-byte provenance need separate evidence and authority.
When a future authenticated G4 pulse changes the measured population, update
the source-bound observations in the same PR and re-run the exact native
renderer. Do not rewrite the old historical observation into a new claim.

## W3 convergence — use the existing single Atlas artifact producer

The Atlas workflow may generate the W1/W2 Flight Deck from the **canonical**
`mission-control/gogreen/samples/fleet_g1.json` and controlled
`mission-control/federation-atlas/flightdeck` JSON sources after completing
the 42+ native regression tests, exact-checkout binding, 95% line and 90%
branch **focused Flight Deck module** coverage floors, and a SHA-bound
manifest verification. The generated `flightdeck/index.html` and JSON/SVG
are included under the **same** `code-purple-method-atlas-<SHA>` Actions
artifact. The Atlas landing page links to its Flight Deck leaf.

**Cost control:** this is one extra stage in the existing Atlas job, **not**
a new workflow or Pages job. The controls fail closed if zero tests execute,
if the source file/coverage tool changes, if any SHA/manifest claim diverges,
or if the required six-repository 42-cell historical census fails.

**Evidence boundary:** passing the Atlas workflow is an exact-head artifact
producer proof only. Historical G4 observations remain 6/42 with 36 UNKNOWN;
original archived ZIP-byte trust, refreshed current-head observation and
corporate/QPS acceptance require independent receipts. A pre-existing Jekyll
Pages deploy does not publish this Actions artifact by itself. Do not
claim HOSTED_VERIFIED before a site URL and hosted-content digest readback.

**Owner admission:** master protection/ruleset is a separate P0 control.
Do not merge this branch without authorized gate/review process. To avoid
unnecessary GitHub Actions consumption, initial implementation is a
non-PR staging branch pending owner-controlled flight budget.

**W3 derivative parity:** because the Flight Deck HTML includes links to XLSX, DOCX, PPTX and PDF, the existing Atlas job also renders and tests nonempty versions of those four files *before* hashing/upload. Optional dependencies are pinned; no second workflow is introduced. They remain generated review copies, not corporate-approved documents.

## MIP side-load and Kubernetes leaf (2026-10-15)

The existing Atlas producer renders side-load/k8s HTML, JSON, Mermaid and SHA256 in the SAME source-bound Actions artifact, no new workflow/Pages publisher. Frozen three-repository eight-surface historical observation; DOW W74 static, W169 possible kind runtime; KEB transport and Docker/Compose, Kubernetes deferred; QPS W165/edge child remains DEFER. Filter by repo/evidence kind/search. The uniform transport PRs are CODEX #1049, ABACUS #2025 and QPS #1931, all draft candidates in this source snapshot. Native run/job/attempt, cluster sessions, QPS private original bytes and matched-scope coverage remain UNKNOWN until independently verified. Test the existing Atlas unittest discovery on exact SHA. HTML offers no write/deploy action.

## C3 unified side-loading operator — existing Atlas workflow only (2026-10-15)

The pre-existing `sideload_k8s.py` (merged PR #550) remains the primary
three-owner/eight-asset **historical source inventory**. Its exact-source records
are not replaced by the supplementary `SIDELOAD_OPERATOR_CONTRACT_v1.json`
(proof-stage vocabulary and frozen owner observations), rendered by
`build_sideload_operator.py`. The two views are siblings within the **same**
`code-purple-method-atlas.yml` artifact and its existing Pages allowlist:
`sideload-k8s.html` and `sideload-operator.html`. No second publisher,
controller or K8S worker is created.

Regenerate locally with:

```sh
python -m unittest discover -s mission-control/federation-atlas -p 'test_*.py' -v
python mission-control/federation-atlas/sideload_k8s.py --out /tmp/code-purple-atlas
python mission-control/federation-atlas/build_sideload_operator.py --out /tmp/code-purple-atlas
```

CI verifies SHA256 receipts, owner sets, 8 static assets, explicit UNKNOWN
runtime and HOLD admission before upload. Historical KEB/DOW/QPS source
snapshots are **not live statuses**; the source snapshots must be re-censused
before operator action. Native browser QA and exact-archive byte inspection
must be separately credited; successful generation is not an authenticated
K8S API/edge session. Cross-repo receipts are independently challengeable
through CODEX, ABACUS and QPS owner contracts.

### MIP-5 observed W169 telemetry overlay (historical, 2026-10-15)

`sideload_telemetry.py` consumes a **verbatim sanitized public Actions JSON receipt**
from ABACUS W169 run 38774568289 / job 116558746360 / attempt 1, artifact
11993466494; the original ZIP SHA-256 and receipt SHA-256 are pinned in
`evidence/W169_NATIVE_PIN_v1.json`. Exact byte reproduction is guarded, and
CI generates `sideload-telemetry.json` plus SHA256 sidecar. The existing
operator page displays one native W169 execution sample (API/workload success,
request p95 and cold start p95, observed restarts); its state is SOURCE-BYTES
VERIFIED ON HISTORICAL EXACT SHA, **not live Kubernetes monitoring**.

Existing `PHASE02_KPI_TAXONOMY_v1.json` remains the sole six-family KPI
registry. Across-fleet queue p95/proof yield, memory/CPU peaks, side-load
rejections and first-red propagation remain null until native normalized
population receipts exist. Do not extrapolate one W169 sample to a population,
fill nulls as zeros, infer edge readiness or override QPS child DEFER.
