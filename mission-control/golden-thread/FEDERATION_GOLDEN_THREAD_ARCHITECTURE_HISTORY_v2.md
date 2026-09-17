# GBOGEB Federation & Golden Thread — Architecture + Process History v2

Status: `CANDIDATE_CANONICAL_COMPANION`

As of: `2026-09-17 Europe/Brussels`

Authority transfer: `false`

This note reconciles the historical federation narrative with the live MissionControl Golden Thread implementation. It is additive to `FEDERATION_NATIVE_GOLDEN_THREAD_v1.md`; it does not replace repo-local engineering authority, `#85` BD/REX/CONTROL lifecycle authority, `#76` Historian authority, or QPS TRIAGE controls.

## 1. Governing interpretation

The Golden Thread is partly a name for architecture that pre-dated the name and partly a real September 2026 implementation increment.

The safe statement is therefore:

```text
pre-existing federation doctrine
+ explicit temporal/replay semantics
+ executable checkpoint/idempotency/zero-delta controls
= current Golden Thread architecture
```

Do not describe Golden Thread as either:

1. a wholly new replacement architecture; or
2. merely a retrospective label with no new implementation.

Both are now false.

## 2. Three evidence classes for this history

Every historical assertion should be understood as one of:

- `REPO_VERIFIED_CURRENT` — directly observed on current/default repository state in this architecture pass;
- `REPO_VERIFIED_HISTORICAL` — directly observed in a PR/commit/issue record;
- `RECORDED_NARRATIVE_UNREVERIFIED` — present in prior architecture/session narrative but not independently recovered in this pass.

Missing evidence remains a gap; it is not silently upgraded to fact.

## 3. Inception to present

### Phase 0 — pre-federation origin

Three GBOGEB repositories are independently verifiable as extant origin surfaces:

- `GBOGEB/DOCX_RTM_Automation`
- `GBOGEB/GEMINI`
- `GBOGEB/CODESPACES_jyperter`

Evidence class: `REPO_VERIFIED_CURRENT` for repository existence.

The stronger causal statement that these three directly merged into one federation is retained only as `RECORDED_NARRATIVE_UNREVERIFIED` until commit/issue/ADR lineage is bound. Their individual original problem statements and exact federation-convergence date also remain historical gaps.

### Phase 1 — federation role separation

The recorded narrative places ABACUS and CODEX on distinct responsibility planes rather than one blended monorepo. That separation survives in current federation doctrine, although the roles have evolved:

```text
QPS / cryoplant-project = domain/product SSOT and engineering release assembly
ABACUS                  = runtime/science/analysis/validation support
CODEX                   = governance/automation/CI/publication
MissionControl          = cross-repo orchestration/attestation
```

The important invariant is ownership separation, not one frozen 2026 label for each repository.

### Phase 2 — governance hardening

The recorded W010 branch/PR-hygiene program remains useful historical context, including branch classification, deletion gates, ownership taxonomy and merged-PR completeness concerns.

Evidence class in this pass: `RECORDED_NARRATIVE_UNREVERIFIED` for the exact June 2026 six-PR W010 sequence. Current repositories contain later W010-labelled programs as well, so `W010` by itself is not a globally unique historical identifier. Future provenance should bind repository + PR numbers + exact SHAs.

The historical statement that direct GitHub connector access was unavailable may be true for that execution environment, but it is not a present architectural blocker: a connected GitHub read/write surface is available in the current execution environment.

### Phase 3 — execution bootstrap

The recorded PR-001 lineage introduced concepts later recognizable as Golden Thread precursors: manifest-bound SSOT, relative-path discipline, patch/history counters, session handover state and fail-closed preflight contracts.

Evidence class in this pass: `RECORDED_NARRATIVE_UNREVERIFIED` for the exact `patches/PATCH_COUNTER` and `SESSION/SESSION_STATE.yaml` origin claim because those names were not recovered on the current indexed default branches during this pass.

This phase should therefore be described as a predecessor lineage, not as the current canonical implementation surface.

### Phase 4 — validation harness / Waves 1–3

The recorded narrative identifies executable physics/regression/property/boundary validation and a deliberately incomplete solver adapter, with Waves 4–5 designed but not yet verified in that historical slice.

Evidence class here remains `RECORDED_NARRATIVE_UNREVERIFIED` unless the original PR/commit set is rebound.

The architectural lesson is still valid: explicit frontier/withheld states are preferable to papering over missing execution.

### Phase 5 — federation-scale architecture consolidation

Prior sessions refer to a `federation_kit` architecture comprising:

- Wave and DMAIC-pulse as orthogonal axes;
- four-layer SSOT discipline;
- telemetry -> trust -> authority -> gate control spine;
- permissives / latched inhibits;
- reflexive DAG concepts;
- downstream invalidation concepts;
- governor/bounded-worker handover architecture;
- cross-boundary mechanism selection.

Important current correction: the literal `federation_kit` package/name was not recovered on current indexed default branches in this pass. The controlling current implementation vocabulary is now materialized under `pipeline-automation-hub/mission-control/golden-thread/` and related MissionControl/federation controls.

The mechanism ladder is explicitly normative in the current Golden Thread frontend:

```text
DEP / REG / SUB / ADAPTER / LAB / FORK
```

but the claim that this ladder is formalized by CODEX `ADR-0001` is not currently supported. The current CODEX `governance/adr/ADR-0001-runtime-debug-governance.md` is a Runtime Debug Governance Policy. The true originating ADR/registry authority for the mechanism ladder therefore needs a provenance binding rather than a guessed reference.

Likewise, the claim that one `reference-registry.yaml` governs approximately 40 external repositories is not yet verified here. The root ABACUS `reference-registry.yaml` currently points to a QPS Line-S-specific registry. Federation-registry scope/count requires a dedicated census before being stated as current fact.

### Phase 6A — Golden Thread naming and convergence

September 2026 gave the existing doctrine a stronger unifying vocabulary:

```text
SOURCE  = MASTER_INPUT
TRUTH   = governed SSOT
OUTPUT  = deterministic rendering
PATCHES = immutable HISTORY
```

The governing invariant is:

```text
one logical fact
-> one authority
-> many deterministic renditions
```

Wave and Pulse remain independent axes:

```text
WAVE  = what may execute next given dependency topology
PULSE = how a bounded slice advances through evidence/control lifecycle
```

`ACCEPT / REJECT / DEFER` are child dispositions produced after telemetry/trust/authority/gate processing; they are not a substitute architecture and should not be reused as a generic backlog status taxonomy.

### Phase 6B — Golden Thread executable runtime

This is the part that is genuinely new implementation rather than naming.

Merged PR `#154` added the first bounded runtime:

- append-only hash-chain verification;
- deterministic `REBUILD_CURRENT`;
- historical `REBUILD_AS_OF`;
- lossless `EXPAND_ROOT`;
- immutable `DIFF A..B`;
- governed event schema and cold-tail fixture;
- tamper/as-of/expand/diff/authority tests.

Its bounded local proof reported 8/8 unit tests PASS, 14 ledger events, zero orphan occurrences and 100% lineage-retention coverage.

Merged PR `#159` added the v1.1 temporal contract and makes two temporal coordinates explicit:

```text
k = semantic/authoritative SSOT generation
e = governed Golden Thread event sequence
```

This prevents governance history from being conflated with engineering state mutation:

```text
REJECT                         -> e+1, k unchanged
DEFER                          -> e+1, k unchanged
ACCEPT advisory/non-authority  -> e+1, k unchanged
ACCEPT + authoritative delta   -> e+1, k+1
```

The same layer adds child injection/disposition idempotency contracts, exact receipt requirements and deterministic temporal checkpoints.

Merged PR `#161` adds:

- digest-bound checkpoint creation;
- genesis-replay == checkpoint-replay proof;
- tamper detection;
- rejection of replay before checkpoint boundary;
- JSON/YAML/Markdown/HTML rendition-family zero-delta verification;
- explicit withholding of Word/PPT/Excel zero-delta credit until binary extractors exist.

Hosted Golden Thread Replay and Golden Thread Control workflows have returned successful runs on the implementation heads.

Therefore the former statement "temporal snapshotting is M0 / genuinely unresolved" is obsolete. Bounded checkpoint semantics and replay equivalence are implemented; what remains open is fleet-wide checkpoint cadence, retention/storage economics and operating policy.

## 4. Current architecture model

### 4.1 Authority layers

```text
SOURCE / MASTER_INPUT
        |
        v
TRUTH / GOVERNED SSOT -----------------------------+
        |                                           |
        +-- accepted PATCHES / HISTORY ------------+--> successor semantic generation k
        |
        +-- control/history events --------------------> event sequence e only
        |
        +-- deterministic renditions
        |
        +-- federation child transactions
        |
        +-- immutable checkpoints / replay accelerators
        `-- exact receipts / round-trip proof
```

A checkpoint is never a second authority. A rendering is never a second authority. A MissionControl projection is never repo-local engineering truth.

### 4.2 Temporal identity

A milestone should bind at least:

```yaml
semantic_generation_k: integer
event_sequence_e: integer
ssot_digest: sha256|null
thread_digest: sha256
projection_digest: sha256
checkpoint_digest: sha256|null
git_anchor:
  repository: owner/repo
  commit_sha: sha
schema_version: string
authority_digest: sha256
gate_digest: sha256
render_manifest_digest: sha256|null
authority_transfer: false
```

This is stronger than a single `S(k+1)=f(S(k), delta)` model because it distinguishes semantic evolution from control/history evolution.

### 4.3 Child transaction contract

```text
CHILD_INJECTION_REQUESTED
 -> telemetry/current-state evidence
 -> trust classification
 -> authority preflight
 -> gate
 -> permissive OR latched inhibit
 -> execution if admitted
 -> exact child receipt
 -> ACCEPT | REJECT | DEFER
 -> immutable history event
 -> authoritative delta only if separately admitted
```

Required idempotency controls:

- unique `injection_key`;
- unique `idempotency_key` per logical obligation;
- ACCEPT requires exact child receipt;
- authoritative ACCEPT additionally requires accepted-delta digest + resulting SSOT digest;
- REJECT retains reason/negative evidence;
- DEFER retains owner + re-entry trigger;
- duplicate obligations/dispositions fail closed.

### 4.4 Progressive idempotency ladder

The v1.1 temporal contract establishes a useful five-level ladder:

```text
I0 input      same idempotency key => no duplicate child obligation
I1 replay     same sealed ledger => same thread/projection digest
I2 transition same base k + same accepted deltas => same successor k/SSOT digest
I3 recursive  same boundary => same expanded subtree/checkpoint digest
I4 temporal   same sealed historical boundary + schema => same milestone checkpoint
```

A future `I5_federation_roundtrip` should require a real provider->consumer->return transaction with zero unexplained semantic delta and exact external side-effect receipts.

### 4.5 Invalidation architecture

The phrase `downstream-cone invalidation` should no longer be presented as already solved implementation. No current implementation surface was recovered by direct search in this pass.

Adopt an explicit invalidation receipt instead:

```yaml
invalidation_id: INV-...
trigger_event_id: ...
trigger_digest: sha256:...
reason: ...
scope: NODE|DMAIC_CLUSTER|DESCENDANT_CONE|RENDITION_ONLY|FULL_REPLAY
root_nodes: []
affected_nodes: []
affected_renditions: []
recompute_from_checkpoint: null|checkpoint_id
non_compensating_gates_preserved: true
closure_proof:
  expected_affected_count: integer
  recomputed_count: integer
  stale_survivor_count: integer
  projection_digest_before: sha256:...
  projection_digest_after: sha256:...
```

Granularity is therefore a real architecture decision, but it sits inside a defined receipt contract rather than an informal per-node/per-cluster question.

### 4.6 Wave x Pulse x temporal coordinates

Do not nest Wave and Pulse.

A work item may be located by four independent coordinates:

```text
DAG position:        Wave / node / dependency cone
control cadence:     DMAIC/3P Pulse
semantic generation: k
event history:       e
```

This yields a more complete state key:

```text
ExecutionCoordinate = (wave_node, pulse_id, k, e)
```

where only governed authoritative deltas advance `k`.

## 5. Maturity scale

- `M0` concept only;
- `M1` prototype/schema exists, not integrated;
- `M2` documented/normative with partial implementation;
- `M3` integrated and executing in at least one governed repo/PR/workflow path;
- `M4` validated under representative fleet-scale load/failure and hardened across multiple independent consumers.

## 6. Repo-grounded maturity assessment

| Component | Level | Current basis | Remaining gap |
|---|---:|---|---|
| Wave x DMAIC-pulse orthogonality | M2 | normative Golden Thread frontend | scheduler/orchestrator enforcement not directly proved here |
| Four-layer SOURCE/TRUTH/OUTPUT/PATCHES discipline | M2-M3 | normative frontend + replay/projection implementation | federation-wide conformance proof |
| Append-only hash-chain + deterministic replay | M3 | merged #154 + tests | fleet-scale/live ingestion |
| Historical as-of / expand / diff | M3 | merged #154 + bounded proof | larger multi-repo corpus |
| Temporal k/e model | M3 | merged #159 contract/runtime/tests | representative cross-repo authoritative deltas |
| Child idempotency/disposition validation | M3 | merged #159 + fail-closed tests | real provider/consumer write round trip |
| Temporal checkpoint construction | M3 | merged #159/#161 | cadence/storage/retention policy at fleet scale |
| Genesis == checkpoint replay equivalence | M3 | merged #161 + hosted workflow | repeat across independent corpora |
| JSON/YAML/MD/HTML zero-delta rendition family | M3 | merged #161 + hosted workflow | real public/federated round trip |
| Word/PPT/Excel semantic zero-delta | M1-M2 | contract/normative intent; credit explicitly withheld | governed extractors + tests |
| Telemetry->trust->authority->gate spine | M2 | normative frontend | implementation proof for bottom-up permissives/latching inhibits |
| Bottom-up permissive / latched-inhibit behavior | M1-M2 | named doctrine | executable gate-state model + latch/reset tests |
| Downstream-cone invalidation | M0-M1 | claimed in historical design narrative; no current code recovered here | explicit invalidation runtime + tests |
| Mechanism ladder DEP/REG/SUB/ADAPTER/LAB/FORK | M2 | normative current Golden Thread frontend | bind true source ADR/registry; current CODEX ADR-0001 is not this ladder |
| Federation reference registry / ~40-repo scope | UNKNOWN | broad-scope claim not verified; root ABACUS registry is deprecated to Line-S-specific registry | locate canonical registry + exact census |
| Reflexive DAG nodes | M1 | historical design term | semantics under resequencing/replay not bound |
| Live GitHub occurrence importer | M1 | explicitly listed as next bounded layer | implement exact idempotent importer |
| Fleet-wide historical bootstrap | M1 | bounded cold-tail fixture exists | scale only after live importer/round-trip controls |
| Merkle/block proof layer | M0 / DEFERRED | explicitly optional future optimization | justify only if fleet scale requires it |

No M4 claim is made yet.

## 7. Architecture burn-down: use canonical BD lifecycle

Do not create a parallel lifecycle called `OPEN / SCOPED / WIP / BLOCKED / CLOSED` as authoritative state. `#85` already owns the canonical BD lifecycle:

```text
TODO / ACTIVE / DONE / CONTROL / SUPERSEDED / INVALIDATED / UNKNOWN_NEEDS_READER
```

A compact symbol may be used for display, but every architecture gap must retain:

```yaml
bd_id: GT-BD-...
bd_state: TODO|ACTIVE|DONE|CONTROL|SUPERSEDED|INVALIDATED|UNKNOWN_NEEDS_READER
routing_disposition: EXECUTE_NOW|WORK_ORDER_CHILD|EXTERNAL_WAIT|CONTROL_WATCH|...
child_gate_disposition: null|ACCEPT|REJECT|DEFER
owner: ...
next_bounded_action: ...
victory_predicate: ...
evidence_refs: []
```

`ACCEPT / REJECT / DEFER` belongs only in `child_gate_disposition` when a real child transaction exists. It is not a generic review-state field.

## 8. Rebased architecture BD queue

1. `GT-BD-001` — fleet checkpoint cadence/storage/retention policy. Bounded checkpoint semantics are DONE; fleet operating policy remains TODO.
2. `GT-BD-002` — downstream invalidation receipt/runtime and granularity. TODO.
3. `GT-BD-003` — executable permissive/latching-inhibit gate model and reset semantics. TODO/ACTIVE when implementation starts.
4. `GT-BD-004` — historical GitHub-connector absence. SUPERSEDED as present blocker; current connected GitHub surface exists. Preserve as historical environment constraint only.
5. `GT-BD-005` — reflexive DAG semantics under wave resequencing/replay. TODO.
6. `GT-BD-006` — live GitHub occurrence importer with idempotency keys. TODO.
7. `GT-BD-007` — Word/PPT/Excel semantic extractors and zero-delta tests. TODO.
8. `GT-BD-008` — real GitHub/provider-consumer-return round-trip receipt (`I5`). TODO.
9. `GT-BD-009` — mechanism-ladder provenance: locate/adopt true ADR/registry authority; do not cite current CODEX ADR-0001 as ladder authority. TODO.
10. `GT-BD-010` — canonical federation reference-registry location + exact repo census. UNKNOWN_NEEDS_READER.
11. `GT-BD-011` — fleet-wide bootstrap after importer/round-trip controls remain lossless. DEFERRED/TODO by dependency.

## 9. Present state — September 17, 2026

The present state is stronger than the earlier companion notes implied:

- Golden Thread v1 replay runtime is merged;
- temporal k/e contract is merged;
- child idempotency/disposition validation is merged;
- temporal checkpoint construction is merged;
- checkpoint/genesis equivalence proof is merged;
- JSON/YAML/Markdown/HTML zero-delta rendition controls are merged;
- hosted Golden Thread workflows have returned PASS on implementation heads;
- GitHub repository read/write access is available in the current execution environment;
- binary Office zero-delta, live occurrence ingestion, downstream invalidation runtime, gate-latch execution proof and fleet checkpoint operating policy remain open.

The architecture is therefore best described as **bounded M3 Golden Thread runtime with federation-wide M4 still withheld**.

## 10. Target architecture

```text
                         MASTER_INPUT / SOURCE
                                  |
                                  v
                         GOVERNED SSOT / TRUTH
                                  |
                     +------------+-------------+
                     |                          |
                     v                          v
          semantic generation k          event/history e
          accepted authority delta       accept/reject/defer/control
                     |                          |
                     +------------+-------------+
                                  |
                                  v
                       IMMUTABLE GOLDEN THREAD
                 hash chain + exact Git/SHA anchors
                                  |
              +-------------------+--------------------+
              |                   |                    |
              v                   v                    v
       CHECKPOINT/REPLAY     CHILD FEDERATION      RENDITION FAMILY
       digest-equivalent     idempotent receipts   JSON/YAML/MD/HTML
       acceleration          authority re-entry    Office/PDF later
              |                   |                    |
              +-------------------+--------------------+
                                  |
                                  v
                         ZERO-DELTA CONTROL
                                  |
                  invalidation / recompute receipts
                                  |
                                  v
                    BD / REX / CONTROL feedback
```

The Golden Thread does not become a new SSOT, mission authority, BD lifecycle or engineering authority plane. It is the immutable replay/provenance/control substrate connecting those existing authorities without losing temporal lineage.

## 11. Definition of Done for the next maturity step

The next maturity step is achieved when:

- one live multi-repo child transaction is injected with an idempotency key and exact receipt;
- ACCEPT/REJECT/DEFER behavior is observed through the actual authority/gate path;
- an authoritative ACCEPT advances `k` exactly once while pure control events advance only `e`;
- a checkpoint before that transaction replays to the exact same post-transaction projection as genesis;
- downstream invalidation emits a complete affected-set receipt and leaves zero stale survivors;
- JSON/YAML/MD/HTML remain zero-delta;
- at least one Office binary family member has a governed semantic extractor and zero-delta proof;
- a real GitHub/provider/consumer/return round trip reaches `I5` with zero unexplained semantic delta;
- no parent PASS compensates a child gate;
- no generated view, checkpoint or MissionControl projection acquires authority.

Only after repeat proof on distinct repositories/corpora should the relevant controls be considered for M4 promotion.
