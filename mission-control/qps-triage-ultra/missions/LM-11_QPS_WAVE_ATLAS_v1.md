# LM-11 — QPS Wave Lineage & Dependency Atlas

Status: **RECON_ACTIVE_INDEX_BUILD**  
Provider: `GBOGEB/cryoplant-project`  
Authority transfer: **false**  
Formal credit delta: **0**

## Contents

1. [Purpose and authority](#1-purpose-and-authority)
2. [What a Wave means](#2-what-a-wave-means)
3. [Observed Wave topology](#3-observed-wave-topology)
4. [Main groups](#4-main-groups)
5. [QPS TRIAGE nodes and edges](#5-qps-triage-nodes-and-edges)
6. [Full workflow wireframe](#6-full-workflow-wireframe)
7. [Sectional DAGs](#7-sectional-dags)
8. [Entry and exit points](#8-entry-and-exit-points)
9. [Artifact and code classes](#9-artifact-and-code-classes)
10. [HMI and navigation](#10-hmi-and-navigation)
11. [First red and reconciliation](#11-first-red-and-reconciliation)
12. [Recursive continuation](#12-recursive-continuation)

## 1. Purpose and authority

LM-11 reconstructs the complete temporal, semantic and execution lineage of QPS Waves, pulses, PRs, receipts and satellite round-trips. It is a cartography/control mission: it does not replace QPS TRIAGE, create engineering truth, change bidder/source authority, or award formal credit.

The provider remains the QPS child authority. MissionControl holds the mission index and read-only atlas. The authoritative QPS lineage surfaces are the Wave normalization control, canonical lineage resolver, recursive restart/current pointers, graph/pipeline registries and child disposition surfaces.

## 2. What a Wave means

A Wave is a bounded victory scope, not merely a chronological counter. Same-scope work remains inside the Wave as a pulse, correction, revisit or P3R cycle. A new Wave is justified only by material change of method, population, authority chain, release mechanism or workstream.

Therefore:

```text
W-number order != causal order != PR order != current semantic lineage
```

and:

```text
absence of triage/wNNN/ != proof that WNNN never existed
```

A Wave may be represented by controls, handovers, federation receipts, root-level TRIAGE artifacts or PR history without a dedicated `triage/wNNN/` directory.

## 3. Observed Wave topology

The exact QPS main observed by launch is `29a3a619b17b37eca5accfa2fd747401a2387c7b`; its latest observed Wave-labelled merge is W264. Dedicated `triage/w###` directories form only one projection of the history. The repository also contains Wave-labelled recursive handovers and controls outside those directories.

The current reconstruction uses four independent coordinates:

```text
Temporal:  global_seq / time / release
Lane:      previous_in_lane / wave / pulse
Causal:    causal_parent / depends_on / produces
Semantic:  predecessor / supersedes / corrects / alias / current
```

These coordinates must never be silently collapsed.

## 4. Main groups

The following are **initial evidence-backed grouping anchors**, not yet a claim that every Wave inside a numeric interval belongs to one homogeneous family.

### 4.1 Genesis and early global-control family

Early PRs predate stable global Wave numbering and are normalized as genesis/control pulses rather than a literal global W0. This group establishes repository, round-trip, metrics and victory-control mechanics.

### 4.2 Federation and early resource-plan lineage

W02/W03 and related federation work establish child/parent orchestration, resource planning, exact evidence return and the distinction between semantic reuse and duplication. Resolver revision drift around PR110/111 is the current LM-11 first red.

### 4.3 Snapshot, correction and review families

W36 demonstrates progressive snapshot supersession. W40/W41 demonstrates historical label drift repaired by a correction edge rather than history rewrite.

### 4.4 HEPAK / reverse-pressure / runtime families

W56 and W57 are strong examples of one Wave carrying multiple pulses and corrections: lineage recovery, independent challenge, federation re-entry, runtime DoV, source recovery, PCA/BT analysis and test-harness repair.

### 4.5 TRIAGE / control / release architecture families

W58–W61 show maintainability architecture, repository census, DoV/DMAIC/KPI control, review/control and outward release/binary gates. They are useful reference families for how LM-11 should group many PRs under one victory scope rather than count every PR as another Wave.

### 4.6 Recursive source, review and intake families

Later QPS history contains source-return, review, negotiation, structured-input and recursive handover lanes. Dedicated `triage/w###` folders and `handover/qps_recursive/W###_*` surfaces must be joined by semantic identity rather than treated as separate histories.

### 4.7 Visual / semantic SSOT / root-input families

Current QTG lineage explicitly carries W231 visual diagnostics, W235 semantic SSOT, W238–W240 root intake and subsequent prospective-machine snapshots as separate non-compensating or sequential control families.

### 4.8 Prospective-machine and structured-input control

W243–W248 establish the Leg-6 prospective-machine streak through 5-of-5 process CONTROL. JSON/YAML/YML input lanes continue separately and do not inherit source or engineering authority merely from successful parsing.

### 4.9 Temporal-PCA / GM-I-B side-load family

W255/W256 establish provider-bound temporal-PCA control; W257 formalizes the GM-I-B integration variant; later W258–W264 extend geometry/visual/propagation work. This lane is parallel/non-compensating to QPS runtime GOLD and demonstrates cross-repository reuse without duplicate mathematical kernels.

## 5. QPS TRIAGE nodes and edges

QPS already defines system, requirement/evidence and federation graphs. LM-11 adds a temporal-wave overlay without replacing them.

```text
NODE CLASSES

[Wave] [Pulse] [Correction] [Revisit] [P3R]
  |
  +--> [PR] --> [Commit] --> [Run] --> [Receipt]
  |                                  |
  |                                  +--> [Artifact]
  |
  +--> [Source] --> [Canonical Object]
  |
  +--> [Current Pointer]
  |
  `--> [Satellite Repo]

EDGE CLASSES

PRECEDES       temporal only
PARENT_OF      causal generation
DEPENDS_ON     execution prerequisite
PRODUCES       output generation
CONSUMES       input use
EVIDENCED_BY   proof linkage
SUPERSEDES     semantic successor
CORRECTS       forward repair
REVISITS       new evidence reopens same scope
ALIASES        same object/digest alternate identity
BRIDGES        cross-surface connection
FEDERATES_TO   parent/satellite transaction
RETURNED_AS    federation return
REENTERS       child re-entry
FORKS / JOINS  bounded graph structure
PARALLEL_NONCOMPENSATING
PROMOTES_TO_CURRENT
```

## 6. Full workflow wireframe

```text
                       REPOSITORY / EXTERNAL INPUTS
                                  |
           +----------------------+----------------------+
           |                      |                      |
       USER/ROOT              SOURCE RETURN       PARENT/SATELLITE
   MD JSON YAML YML          PDF/OFFER/RTM/etc     RECEIPT / KEB / DOW
           |                      |                      |
           +----------------------+----------------------+
                                  v
                         [ IMMUTABLE INGRESS ]
                         hashes + source locator
                                  |
                                  v
                              NORMALIZE
                                  |
                                  v
                         Z0 exact contract
                                  |
                                  v
                       Z1 parse / schema gate
                                  |
                                  v
                provenance + semantic + source gates
                                  |
                                  v
                         CANONICAL QPS OBJECT
                                  |
                    +-------------+-------------+
                    |                           |
                    v                           v
             EXECUTION DAG                LINEAGE DAG
                    |                           |
                    v                           v
              OBSERVED RUN            prior/current/supersedes
                    |                           |
                    +-------------+-------------+
                                  v
                         RECEIPT / EXACT SHA
                                  |
                              Z2 / Z3
                                  |
                    +-------------+-------------+
                    |                           |
                 CODEX/KEB                 ABACUS/DOW
                    |                           |
                    +-------------+-------------+
                                  v
                            CHILD RE-ENTRY
                                  |
                    +-------------+-------------+
                    |             |             |
                 ACCEPT         REJECT         DEFER
                    |             |             |
                    v             +-------> BD / next CG
             PROMOTED STATE
                    |
                 CONTROL
                    |
        CURRENT POINTER / HANDOVER / NAV
                    |
          +---------+----------+
          |                    |
   HUMAN OUTPUTS         NEXT PULSE/WAVE
 DOCX PDF XLSX PPTX HTML         |
                                 `---- RECURSE ---->
```

Global recursion may cycle across transactions. Each bounded execution DAG and each lineage DAG must remain acyclic.

## 7. Sectional DAGs

### 7.1 Native QPS source-to-release DAG

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

### 7.2 Federation round-trip DAG

```text
child_ssot
  -> schema_hash
  -> CODEX_KEB
  -> ABACUS_DOW
  -> CODEX_normalize
  -> child_reentry
  -> ACCEPT | REJECT | DEFER
```

### 7.3 Root structured-input side entry

```text
.md/.json/.yaml/.yml
  -> immutable byte snapshot
  -> SHA256 fingerprint
  -> syntax/structure parse
  -> RAW_PROVENANCE_ONLY / UNBOUND
  -> human curation + authority gate
  -> canonical object (only if separately promoted)
```

### 7.4 Wave correction/supersession path

```text
historical node
  -> observed defect/new evidence
  -> CORRECTION or REVISIT
  -> proof
  -> successor node
  -> SUPERSEDES/CORRECTS edge
  -> current navigation projection

historical node remains provenance-reachable
```

### 7.5 Parallel non-compensating side-load

```text
main QPS BD -------------------------------> unchanged hard gate
       \
        +-> side-load provider
             -> exact provider proof
             -> federation/challenge
             -> QPS diagnostic ACCEPT/DEFER
             -> optional knowledge/control promotion

side-load success != main-gate compensation
```

## 8. Entry and exit points

### Entry points

- `handover/qps_recursive/GLOB.yaml` — restart root.
- `handover/qps_recursive/QTG_CURRENT.yaml` — live recursive pointer.
- controlled sources and canonical SSOT surfaces.
- root `.md/.json/.yaml/.yml` unbound inputs.
- source-return lanes.
- external KEB/DOW/provider receipts.
- historical re-entry for corrections/revisits.

### Exit points

- child `ACCEPT`, `REJECT`, `DEFER`.
- promoted canonical state.
- CONTROL or explicit WITHHELD/WAIT/DEFER state.
- exact-SHA receipt/artifact.
- current pointer/handover update.
- outward release view.
- next bounded pulse/Wave.

## 9. Artifact and code classes

| Class | Observed forms | Role |
|---|---|---|
| Human-facing generated output | DOCX, PDF, XLSX, PPTX, HTML | Review/navigation/release views; not governing source |
| Hybrid control | YAML/YML + Markdown | Mission/control/handover/burndown/read-navigation; human and machine readable |
| Machine state | JSON | Receipts, manifests, lineage projections, canonical objects, digests |
| Code core | Python | resolvers, validators, generators, census, analysis/runtime |
| Contract code | TypeScript/Zod | executable ingress/receipt/data-boundary validation |
| Orchestration/helper code | shell/PowerShell; other languages only when observed | workflow/application of handover and CI utilities |

No language is inferred from expectation alone. JavaScript, for example, becomes part of LM-11 only if the full repository census observes a material `.js` execution surface.

## 10. HMI and navigation

Recommended read-only HMI views:

1. **Wave Timeline** — Wave/pulse/PR/run sequence with correction/revisit markers.
2. **Dependency DAG** — selected bounded lineage/execution DAG with entry/exit highlighting.
3. **Family Map** — grouped semantic families, current versus historical nodes.
4. **Satellite Round-trip** — QPS ↔ CODEX/KEB ↔ ABACUS/DOW ↔ provider repos.
5. **Artifact Flow** — source/hybrid/code/receipt/human-output layers.
6. **Delta Watch** — hashes changed since last accepted index, classified as ADD/MODIFY/ALIAS/SUPERSEDE/NOOP.

The HMI is a projection only. Every visual node must expose exact canonical ID, path, PR, SHA and evidence class. Navigation must not depend solely on JavaScript, hover, animation or colour.

## 11. First red and reconciliation

The initial launch exposed a useful real lineage defect:

```text
older Wave normalization / double-3PR closure:
    PR110/W03 and PR111/W02 = DISTINCT SUCCESSOR NODES

later canonical lineage resolver / navigation projection:
    PR111 = CURRENT
    PR110 = SUPERSEDED PLANNING SIDECAR
```

LM-11 records this as `LINEAGE_AUTHORITY_POINTER_DRIFT_110_111`. It is not resolved by deleting or rewriting either historical interpretation. The required repair is to establish resolver revision/authority precedence and encode the transition explicitly.

This is also the template for the >W250 census: apparent contradictions are temporal lineage events to reconcile, not reasons to discard provenance.

## 12. Recursive continuation

The canonical recursion for the atlas is:

```text
REFRESH exact QPS head
  -> census repo/PR/Wave tokens
  -> DIFF against prior LM-11 index
  -> classify NEW / CHANGE / ALIAS / CORRECTION / SUPERSESSION
  -> bind evidence
  -> rebuild affected graph section only
  -> validate bounded DAGs
  -> publish read-only current projection
  -> retain historical graph
  -> recurse on next material hash delta
```

The target end state is a complete machine-readable graph plus human atlas in which every observed Wave token has a disposition, every PR relation is evidence-backed or explicit UNKNOWN, every current family has at most one current node, and all historical provenance remains reachable.
