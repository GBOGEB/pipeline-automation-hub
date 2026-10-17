# GoGREEN G7 — What works, and how do we improve it?

**Authority:** This is a read-only temporal projection under Mission Control GoGREEN. The producer `runner_telemetry.py` consumes frozen native GitHub branch-head, run and job metadata alongside **the existing** Top7/Top14/Top21 cohort roster (`GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json`). It does not own that registry, a new BD queue, REX history or any source repository's CI gate.

## Native event, execution and maturity denominators (16–17 Oct 2026 UTC)

| Signal | Native transcription | What it means / what it cannot mean |
|---|---:|---|
| Canonical Top21 sources | 21/21 source heads verified | Seven each in Top7, extension Top14 and extension Top21; **not** CI admission |
| Existing source branch protections | 1/21 reported protected (ABACUS) | Read-only REST boolean, **not** effective required-check verification |
| Selected successful workflow run IDs | 24 | Five workflow families from four repositories, **selected successful observations**; not a success percentage |
| Run families | 5 | GitHub run ID, attempt, ordinal, event, source SHA and creation timestamp; ordinal gaps are UNKNOWN |
| Current-source-head successes among selected runs | 4/24 | Successful selected workflow on current default HEAD, **not** whole-repo green |
| Native sampled jobs | 10 | Four exact run/job pages: Mission Control, gg_MATH, QPS native debug and CODEX debug |
| Runner-executed job successes | 9 | One QPS Docker job was skipped (zero valid runner time); no green credit for skipped |
| Sampled runner busy time | 235 seconds = 3.9167 busy runner-minutes | Execution occupancy across ten job records; **not billing, CPU demand or fleet capacity** |
| Real red sentinel runs | 2 | QPS canonicalization red and Mission Control GoGREEN G0 red retained as counterexamples |
| Whole-repo coverage / independent statistical trials | UNKNOWN | Require qualified matched native scope, test population and independent repetition |

**Repeats and maturity:** Six selected native successes exist for Mission Control `Zero-Test Gate Guard`, six for gg_MATH `M02B Math Bunker Smoke`, six for QPS `QPS TRIAGE Debug DAG Pilot`, two for CODEX `QPS Perpetual Debug Control`, and four for CODEX `Renderer Lint Guard`. QPS's 181–186 series has zero intervening run-number gaps **within the stated window**; other series have unobserved gaps. The measured time between first and last successful observation is a maturity-span proxy, not a test of independence or future reliability.

## SIPOC and code RFE — meaningful downstream capability

| Supplier/input | Code or native producer | Actual useful capability | Output/consumer | Next improvement |
|---|---|---|---|---|
| Mission Control tests and CI | Zero-Test Gate Guard (merged) | Reject a false GREEN from zero executed unittest cases | Audit artifact → CI gatekeeper | Inject deliberately undiscoverable tests across matrix OSes |
| gg_MATH kernel | M02B Math Bunker Smoke | Execute kernel plus independent challenge/receipt | Math consumer (proposal) | Conditioning extremes, metamorphic invariants, exact environment/repeat controls |
| QPS native debug sessions | QPS TRIAGE Debug DAG Pilot | Plan → native LLDB breakpoint/step → DAG rollup in real GitHub jobs | QPS debug evidence, next pulse | Prove optional Docker path and failure/recovery without touching plant control |
| CODEX debug adapters | QPS Perpetual Debug Control | Docker LLDB + JS/debugpy + LLDB/MCP + heartbeat/control gate | Source-bound runtime jobs and terminal receipts | Backend-specific outcome/latency, injected failure, avoid redundant launch |
| CODEX renderer | Renderer Lint Guard | Detect renderer lint regressions | CODEX CI | Seed hostile/truncated layout and negative serialization |
| Mission Control GoGREEN | `execution_adapter.py` (merged #593) | Six allowlisted scratch tasks, SQLite lease, idempotent replay, ephemeral Ed25519 receipts | Golden Thread scratch receipts, **local pilot only** | Independent trusted signer, path fencing, replay on exact native head |
| Mission Control GoGREEN | `bd_queue_wave.py` (merged #595) | Four-repo read-only PR/workflow census with alias-safe symptoms | BD queue owner, **native first-red pending** | Shared CI repair #597 and matched branch coverage |
| ABACUS EVERRED | #2090 candidate wave planner | Plan disjoint source-owner repair waves | EVERRED root investigation, **draft** | Native first-red attribution, Black and Safety independently |

These are producer-consumer **links**, not permission to invoke CODEX, QPS, independent Crew/REX or GitHub write actions. An output edge becomes a qualified RECEIPT only when source SHA, workflow/job attempt, output bytes and source owner acceptance are matched.

## Process DAG and admission

```text
S (Top21 canonical roster + verified repo heads)
     -> I (GitHub run ID, attempt, job ID, runner timestamps, source SHA)
         -> P_SOURCE (fail-closed temporal comparison) --observed--> O (hashed JSON/HTML/DAG)
         -> P_REVERSE (positive + hostile negative tests) --declared--> C (owner admission)
         -> P_REX (first-red fingerprint and canonical root lookup) --declared--> C
         -> CAP_* (eight source-owned abilities) --declared--> O
O --declared/review required--> C (independent security, rulesets, REX and QPS)
```

Existing canonical method-plane planner: `../sipoc_instances.py`, the Atlas `../federation-atlas/PROCESS_LANES_v1.json` and Mission Control's existing approved SIPOC process instances. G7 is **not** a second scheduler. It emits `sipoc_dag.json` with typed `OBSERVED`/ `DECLARED` edges and never dispatches target work.

## Reproduction (stdlib producer and native coverage workflow)

```bash
python -m unittest discover -s mission-control/gogreen/success_graph/tests -v
python mission-control/gogreen/success_graph/runner_telemetry.py \
  --input mission-control/gogreen/success_graph/samples/native_success_20261017.json \
  --registry mission-control/grand-missions/GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json \
  --source-sha "$(git rev-parse HEAD)" --out /tmp/gogreen-g7
```

The native `.github/workflows/gogreen-g7-success-graph.yml` runs 51 positive/negative tests, records **statement and branch coverage numerator/denominator** for the new producer (module-scoped ratchets 80% and 75%) and hashes `metrics.json`, `sipoc_dag.json`, `index.html`, `source_census.json`, `manifest.json`. GitHub Actions run ID/attempt/source SHA enter the separate native receipt. It does not deploy GitHub Pages or alter the older GoGREEN/REX/BD registers.

## Next execution decisions and pruning candidates

**KEEP/EXPAND:** Protect Zero-Test Guard, mathematical metamorphic/kernel evidence, genuine QPS/CODEX debug-control runtime, branch coverage and native provenance receipts. Expand positive and reverse tests together per source owner.

**MERGE only after equivalence:** Consolidate duplicated workflow-event snapshots from GoGREEN BD, EVERRED and G7 **as projections around their existing canonical root**, not by creating a new overlapping root register. A workflow label is not a root ID; a run ID may appear in several views but must be credited once.

**PRUNE proposals (never automatic deletion):** Redundant same-SHA full reruns, duplicate unsigned dashboard exports, and repeated derived-statics when the canonical publisher already emits a verified artifact. Pruning requires output-equivalence proof, owner authorization and before/after native tests.

**DEFER:** Direct remote Crew dispatch, an inferred Top21 maturity promotion, independent lifetime/survival estimates, queueing-theory capacity prediction, whole-repo coverage aggregation and production engineering credit. No cohort admission or root closure has been authorized.

**Safety:** `authority_transfer=false`, `dispatch_authorized=false`, `security_waiver=false`, `merge_authorized=false`, `root_closure_credit=0`. No source mutation outside this branch, no rerun flood, no weakened required checks.
