# LM-11 — QPS Wave Lineage & Dependency Atlas

**Mission:** `LM-11 — QPS_WAVE_LINEAGE_DEPENDENCY_RECONSTRUCTION`  
**Provider / child authority:** `GBOGEB/cryoplant-project`  
**MissionControl authority:** mission identity, orchestration, receipts and navigation  
**State:** implementation merged; hosted runtime DoV withheld at pre-execution infrastructure boundary  
**Authority transfer:** false · **formal credit delta:** 0

## Contents

1. [Mission purpose and current state](#1-mission-purpose-and-current-state)
2. [Wave identity and temporal lineage](#2-wave-identity-and-temporal-lineage)
3. [Sequence and grouping model](#3-sequence-and-grouping-model)
4. [QPS TRIAGE node and edge model](#4-qps-triage-node-and-edge-model)
5. [Full pipeline wireframe](#5-full-pipeline-wireframe)
6. [Sectional DAG catalogue](#6-sectional-dag-catalogue)
7. [Entry and exit points](#7-entry-and-exit-points)
8. [Artifact and executable classes](#8-artifact-and-executable-classes)
9. [Satellite / federation node view](#9-satellite--federation-node-view)
10. [HMI and navigation views](#10-hmi-and-navigation-views)
11. [Current DoD / DoV and first red](#11-current-dod--dov-and-first-red)
12. [Recursive continuation](#12-recursive-continuation)

## 1. Mission purpose and current state

LM-11 exists to reconstruct the complete QPS Wave estate as a governed graph rather than a sorted list of `W###` labels. It joins Wave, pulse/update, PR, commit, artifact, runtime receipt, current/historical identity and cross-repository federation evidence while preserving QPS as the engineering authority.

The executable child implementation is already merged in QPS through PR **#1382** (`f6eb1f6344e9953c095cd4dfadcf89991499f791`) and includes:

- `tools/triage/qps_wave_lineage_graph.py` — exact-head Wave/Pulse/PR/artifact extractor and DAG validator;
- `tools/triage/qps_wave_lineage_html.py` — read-only HTML explorer generator;
- `docs/QPS_WAVE_LINEAGE_START_HERE.md` — child navigation front door;
- `.github/workflows/qps-lm11-wave-lineage.yml` — hosted proof workflow.

QPS PR **#1385** subsequently bound the reproduced zero-step hosted boundary and configurable runner selector. Therefore the implementation is present, but measured graph population, Wave↔PR coverage, runtime DAG proof and generated HTML artifact remain **NOT_EXECUTED** until runner admission succeeds.

### Launch census versus current measurement

At LM-11 launch, the directly observed `triage/w###` projection contained **137 directories between W103 and W264**, with 25 numeric gaps:

`W105, W113, W118, W141, W152, W156, W157, W193–W195, W207–W215, W218, W232, W233, W237, W241, W255`.

This was never treated as the complete Wave population. Missing directories can have live lineage on controls, handovers, PRs, receipts or federation surfaces. Later evidence already includes **W265** while global `QTG_CURRENT` remains **W248**; this proves numeric maximum and global project state are different coordinates.

## 2. Wave identity and temporal lineage

A QPS Wave is a **bounded victory scope**, not merely a chronological counter. Same-scope work is represented as a pulse, correction, revisit or P3R cycle; a new Wave requires a material change of method, population, authority chain, release mechanism or workstream.

The atlas preserves four independent coordinate systems:

```text
TEMPORAL   event_sequence -> event_time -> run/release
LANE       wave -> pulse/update -> previous_in_lane
CAUSAL     causal_parent -> depends_on -> produces
SEMANTIC   predecessor -> correction/supersession -> current
```

Therefore:

```text
previous_event != causal_parent != semantic_predecessor != prior_current
W-number order  != causal order   != PR order              != current state
```

Historical nodes are never erased merely because navigation advances. Hash change is a change detector, not an authority promotion.

## 3. Sequence and grouping model

The final graph groups Waves by evidence-backed semantic family and victory scope, not by arbitrary numeric bands. Current anchor families are:

| Group | Evidence-backed role | Representative lineage |
|---|---|---|
| Genesis / global-control bootstrap | Repository, round-trip, metrics and victory-control mechanics before stable global numbering | early PR family; GENESIS rather than literal W0 |
| Federation / resource planning | Child-parent orchestration, ranked resources, exact return and re-entry | W02/W03; PR110 historical planning context → PR111 current navigation |
| Snapshot / correction | Progressive snapshots and non-destructive forward repair | W36 snapshots; W40/W41 label correction |
| HEPAK / runtime / reverse pressure | Multiple pulses/corrections inside stable engineering victory scopes | W56–W57 |
| TRIAGE / control / release | Census, maintainability, DMAIC/DoV controls, binary/release gates | W58–W61 |
| Recursive source / review / negotiation | Source returns, OFFER/RTM review, evidence mapping and recursive handover | later review/intake Waves |
| Prospective-machine / structured input | Process-control streak and typed raw-input lanes | W243–W248 and adjacent input lanes |
| Temporal-PCA / GM-I-B side-load | Cross-repo math reuse, geometry, visuals and propagation without compensating QPS runtime gates | W255–W265 parallel lineage |

The graph engine must report unresolved Wave↔PR links explicitly as `UNKNOWN`/unresolved; it may not silently infer links from numeric adjacency.

## 4. QPS TRIAGE node and edge model

### 4.1 Node classes

```text
MISSION
  +-- FAMILY
       +-- WAVE
            +-- PULSE / CORRECTION / REVISIT / P3R_CYCLE
                 +-- PR
                      +-- COMMIT
                           +-- WORKFLOW / RUNTIME_RECEIPT
                                +-- ARTIFACT

parallel context nodes:
  ISSUE | CONTROL_SURFACE | ENTRY_POINT | EXIT_POINT | EXTERNAL_REPO

artifact-role nodes:
  BINARY_HUMAN_OUT | HYBRID_CONTROL | MACHINE_STATE | CODE_CORE
```

### 4.2 Edge classes

```text
CONTAINS / PRECEDES / PARENT_OF / DEPENDS_ON
IMPLEMENTED_BY / MERGED_AS / PRODUCES / CONSUMES
SUPERSEDES / CORRECTS / REVISITS / ALIASES
READS_FROM / WRITES_TO / REFERENCES
REQUIRES / FEEDS / VALIDATES / GOVERNS
FEDERATES_TO / RETURNED_AS / REENTERS
PARALLEL_NONCOMPENSATING / PROMOTES_TO_CURRENT / DOES_NOT_IMPLY
```

Two explicit historical repairs remain model examples:

- PR110 remains reachable historical W03/planning evidence while PR111 is the current canonical navigation node for the W02 federation resource-plan family.
- PR362 retains its historical W41 label while PR363 is the forward W40 correction/current node.

## 5. Full pipeline wireframe

```text
                     SOURCE / USER / EXTERNAL RETURN
                                  |
               +------------------+------------------+
               |                  |                  |
          USER / ROOT        SOURCE RETURN      SATELLITE RECEIPT
        MD JSON YAML YML     PDF OFFER RTM      KEB / DOW / provider
               |                  |                  |
               +------------------+------------------+
                                  v
                         IMMUTABLE INGRESS
                    source locator + hash/digest
                                  |
                                  v
                              NORMALIZE
                                  |
                                  v
                      SCHEMA / ZOD / PARSE GATE
                                  |
                                  v
              PROVENANCE + SEMANTIC + SOURCE GATES
                                  |
                                  v
                         CANONICAL QPS OBJECT
                                  |
                +-----------------+-----------------+
                |                                   |
                v                                   v
        BOUNDED EXECUTION DAG                 LINEAGE DAG
                |                                   |
                v                                   v
       PR -> COMMIT -> CODE/RUN         predecessor -> successor
                |                                   |
                +-----------------+-----------------+
                                  v
                       EXACT-SHA RUN / RECEIPT
                                  |
                 +----------------+----------------+
                 |                                 |
                 v                                 v
             CODEX / KEB                       ABACUS / DOW
                 |                                 |
                 +----------------+----------------+
                                  v
                            QPS CHILD RE-ENTRY
                                  |
                    +-------------+-------------+
                    |             |             |
                  ACCEPT        REJECT        DEFER
                    |             |             |
                    v             +-------> BD / next challenge
              PROMOTED STATE
                    |
                  CONTROL
                    |
        CURRENT POINTER / HANDOVER / NAV
                    |
          +---------+----------------+
          |                          |
   HUMAN-OUT VIEWS              NEXT PULSE/WAVE
 DOCX PDF XLSX PPTX HTML              |
                                      +---- RECURSE ---->
```

**Global recursion may cycle across transactions. Bounded execution and supersession DAGs must remain acyclic.**

## 6. Sectional DAG catalogue

### 6.1 Restart / recovery spine

```text
GLOB.yaml
  -> QTG_CURRENT.yaml
  -> QPS_TRIAGE_CONTROL_PLANE_v1.yaml
  -> lineage resolver / current navigation
  -> bounded task slice
```

### 6.2 Native source-to-release DAG

```text
controlled_sources
  -> canonical_ssot
  -> zod
  -> trace_graph
  -> OCD_ADR
  -> views
  -> render_QA
  -> hashes
  -> release
```

### 6.3 Wave/PR provenance DAG

```text
WAVE
  -> PULSE/CORRECTION/REVISIT/P3R
  -> PR
  -> MERGE COMMIT
  -> changed artifacts
  -> runtime receipt
```

### 6.4 Supersession/correction DAG

```text
historical node
  -> observed defect / later authority rule
  -> correction or successor
  -> proof
  -> current node

historical provenance remains reachable
```

### 6.5 Structured-input side entry

```text
.md / .json / .yaml / .yml
  -> immutable bytes
  -> SHA-256
  -> parse / schema
  -> RAW_PROVENANCE_ONLY / UNBOUND
  -> separate human/authority curation gate
  -> canonical object only if promoted
```

### 6.6 Federation round-trip DAG

```text
QPS child payload
  -> schema/hash bind
  -> CODEX KEB semantic/provenance
  -> ABACUS DOW challenge/analysis
  -> normalized return
  -> QPS re-entry
  -> ACCEPT | REJECT | DEFER
```

### 6.7 Parallel non-compensating side-load

```text
GLOBAL QPS FIRST RED (#923) ------------------------------> unchanged
          \
           +-> temporal-PCA / provider / diagnostic lane
                -> provider proof
                -> federation/challenge
                -> diagnostic child disposition
                -> knowledge/navigation CONTROL if earned

side-load success DOES NOT compensate the global runtime gate
```

## 7. Entry and exit points

### Entry points

1. `handover/qps_recursive/GLOB.yaml` — restart root.
2. `handover/qps_recursive/QTG_CURRENT.yaml` — current global pointer.
3. `controls/QPS_TRIAGE_CONTROL_PLANE_v1.yaml` — control spine.
4. `controls/QPS_WAVE_LINEAGE_NORMALIZATION_v0.1.yaml` — historical Wave/update normalization.
5. `controls/QPS_CANONICAL_LINEAGE_RESOLVER_v1.json` — current lineage resolution authority.
6. Controlled source return / OFFER / RTM / user root input.
7. External federation receipt from CODEX/ABACUS/provider repos.
8. Historical re-entry for correction/revisit.

### Exit points

1. `ACCEPT`, `REJECT`, or `DEFER` child disposition.
2. Promoted canonical state or explicit WITHHELD/WAIT state.
3. Runtime/validation receipt with exact SHA.
4. Current pointer/handover update.
5. Human-facing generated view.
6. Federation return.
7. Next bounded pulse or justified Wave.

## 8. Artifact and executable classes

| Class | Forms | Role / guard |
|---|---|---|
| **Binary human-out** | DOCX, PDF, XLSX, PPTX, HTML | review/release/navigation view; never governing source by format alone |
| **Hybrid control** | YAML/YML, Markdown, CSV/TSV | machine + human mission/control/handover/navigation surfaces |
| **Machine state** | JSON | receipts, manifests, canonical objects, graph projections, digests |
| **Code core** | Python, TypeScript, JavaScript/MJS/CJS, shell, PowerShell | resolver, graph builder, schema/runtime logic, generators |
| **Workflow** | GitHub Actions YAML | exact-head orchestration and proof execution |

The child graph engine classifies observed paths; this atlas does not infer a language merely because it could exist.

## 9. Satellite / federation node view

```text
                         MISSION CONTROL
                              |
                              | mission / receipt / guard
                              v
                             QPS
                 +------------+------------+
                 |            |            |
                 v            v            v
             CODEX/KEB    ABACUS/DOW    gg_MATH
                 ^            ^            |
                 |            |            |
                 +------------+------------+
                              |
                           CoolProp
                       typed property adapter
```

| Node | LM-11 role | Authority boundary |
|---|---|---|
| MissionControl | mission identity, orchestration, current receipt | cannot mutate QPS engineering truth |
| QPS | graph execution, lineage child authority, final disposition | canonical child authority |
| CODEX / KEB | semantic/provenance knowledge bridge | does not self-promote QPS state |
| ABACUS / DOW | analytical challenge/measurement | challenge evidence, not child authority |
| gg_MATH | reusable mathematical kernels / temporal-PCA provider | provider math does not become project authority by propagation |
| CoolProp | typed thermophysical adapter/cross-check | property adapter, not QPS acceptance authority |

## 10. HMI and navigation views

The current mission contract calls for a read-only GUI/HMI layer. The useful views are:

- **V00 Restart Spine** — `GLOB -> QTG_CURRENT -> control -> current slice`.
- **V01 All Waves** — canonical/current and historical labels with filters.
- **V02 Supersession Map** — historical → correction/successor → current.
- **V03 Wave↔PR Crosswalk** — Wave/update, PR, merge SHA, changed artifacts, unresolved flag.
- **V04 Pulse Tree** — Wave with P/C/R/P3R children.
- **V05 QPS TRIAGE Graph** — typed nodes/edges.
- **V06 Bounded Execution DAG** — selected transaction only.
- **V07 Side-load/Re-entry DAG** — external provider/federation lane.
- **V08 Human-out Pipeline** — source → generator → QA → DOCX/PDF/XLSX/PPTX/HTML.
- **V09 Hybrid Control Pipeline** — YAML/JSON/MD state/control flow.
- **V10 Code Runtime Pipeline** — Python/TS/JS/workflow execution surfaces.
- **V11 Satellite View** — MissionControl/QPS/CODEX/ABACUS/providers.
- **V12 Current Gate vs Highest Wave** — explicitly shows `QTG W248 / #923` independently of later Wave labels such as W265.

Every interactive node shall expose text-accessible identity, path, PR/SHA and status. Colour, hover or JavaScript shall never be the sole carrier of authority information.

## 11. Current DoD / DoV and first red

### Static DoD already achieved

- Mission registered as LM-11 without creating GM-VI.
- QPS graph extractor merged.
- QPS HTML explorer generator merged.
- QPS Start Here navigation merged.
- QPS proof workflow merged.
- Zero-step hosted boundary classified and reproduced.
- Configurable hosted/self-hosted runner selector merged.

### Runtime DoV still withheld

- exact-head graph population: **NOT_EXECUTED**;
- measured Wave↔PR coverage: **NOT_EXECUTED**;
- bounded execution DAG runtime proof: **NOT_EXECUTED**;
- supersession DAG runtime proof: **NOT_EXECUTED**;
- generated JSON/Markdown/HTML proof artifact: **NOT_EXECUTED**.

### First red

`LM11_FIRST_GREATER_THAN_ZERO_STEP_EXACT_HEAD_GRAPH_RUN`

Required sequence:

```text
restore/bypass private-repo runner admission
  -> runner_id != 0
  -> steps > 0
  -> exact-current-SHA checkout
  -> unchanged graph extractor executes
  -> bounded DAG PASS
  -> supersession DAG PASS
  -> measured Wave/PR/artifact coverage emitted
  -> unresolved links explicit
  -> JSON + Markdown + HTML proof artifact
  -> independent MissionControl receipt
```

This does **not** compensate QPS issue #923. It is the same controlled infrastructure boundary expressed for LM-11.

## 12. Recursive continuation

The atlas should advance by material delta, not wholesale rewrite:

```text
REFRESH exact child head
  -> READ current lineage resolver + current pointer
  -> RUN graph census when runner admission is available
  -> DIFF prior graph digest against new graph digest
  -> CLASSIFY ADD / MODIFY / ALIAS / CORRECT / SUPERSEDE / RETIRE / NOOP
  -> PROVE changed bounded slices
  -> WELD accepted nodes/edges into current projection
  -> KEEP historical graph append-only
  -> PUBLISH navigation/HMI projection
  -> PROPAGATE independent MissionControl receipt
  -> RECURSE on next material hash delta
```

The end state is not “W1 → W2 → … → W265”. It is a temporal Golden Thread in which every observed Wave token has a disposition, every PR link is evidence-backed or explicitly unresolved, current semantic families have one current node, all predecessor evidence remains reachable, and human/machine views are deterministically regenerable from the child graph.
