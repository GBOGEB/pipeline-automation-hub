# Federation-Native Golden Thread v1

Status: `CANDIDATE_CANONICAL_FRONTEND`

Authority transfer: `false`

## 1. Purpose

Define the Golden Thread as a governed extension of the existing federation/QPS TRIAGE control model rather than as a parallel Event Sourcing architecture.

The Golden Thread shall provide recursive temporal lineage, deterministic reconstruction, progressively idempotent replay, SHA/digest-bound provenance, governed child re-entry, lossless semantic collapse/expand, checkpointed replay, and zero-delta dissemination across machine and human renditions.

It does **not** replace:

- SOURCE / `MASTER_INPUT` evidence;
- governed TRUTH / SSOT;
- OUTPUT / rendering surfaces;
- PATCHES / HISTORY;
- QPS TRIAGE DAG/orchestration/DoD/DoV;
- child authority `ACCEPT / REJECT / DEFER`;
- canonical BD/REX/CONTROL authority in `#85`;
- Historian current-state authority in `#76`.

## 2. Core invariant

```text
one logical fact
  -> one authority
  -> many deterministic renditions
```

Derived views shall not mutate authority. Federation shall produce zero unexplained semantic delta.

Temporal equivalent:

```text
projection may change; governed source + patch history may not
```

## 3. Four-layer truth model

### SOURCE — MASTER_INPUT

Observed or supplied evidence: documents, requirements, issues, PRs, spreadsheets, code, exact SHAs, trees, blobs, workflow returns and measured receipts.

SOURCE is preserved with provenance and is not rewritten to match a later interpretation.

### TRUTH — SSOT

The current governed logical state derived from admissible SOURCE plus accepted PATCHES.

TRUTH may be represented in JSON/YAML/YML or, where explicitly mature and controlled, an Excel engineering model. This does not create competing masters: one logical authority must be declared, and every other representation is a deterministic serialization/projection of that authority.

### OUTPUT — RENDERING

Word, PowerPoint, Excel views, HTML navigator, Markdown, PDF, charts and management summaries.

OUTPUT is regenerable. Manual edits do not silently become TRUTH.

### PATCHES — HISTORY

Accepted additions, corrections, classifications, child dispositions, merge/split/supersession edges, schema migrations, gate changes, authority changes and control transitions.

The Golden Thread therefore extends the four-layer model with replay rather than replacing it with a pure append-only database.

## 4. Wave x Pulse execution model

`Wave` remains the dependency progression dimension: a bounded execution DAG, normally topologically/Kahn sorted where applicable.

`Pulse` remains the bounded lifecycle/control transaction: refresh -> probe -> analyse -> improve/execute -> prove -> commit -> control/recurse.

Do not redefine Pulse as a generic scheduler heartbeat.

```text
WAVE  = what may execute next given dependencies
PULSE = how a bounded slice advances through evidence/control lifecycle
```

The global control system may recurse, but each bounded execution DAG and lineage DAG shall remain acyclic.

## 5. Recursive state progression

For milestone `k`:

```text
G[k] -- accepted patch set P[k] --> G[k+1]
```

Each milestone should bind sufficient identity to reproduce it:

```yaml
milestone_id:
parent_milestone:
source_sha:
tree_sha:
blob_digests: []
ssot_digest:
patch_digest:
schema_version:
authority_state:
gate_state:
render_manifest_digest:
```

Same SOURCE + same accepted PATCHES + same schema/order shall yield the same canonical TRUTH digest.

## 6. Content-addressed identity

For canonical object `x`:

```text
ID(x) = SHA256(canonicalize(x))
```

If canonical content changes, its digest changes. That shall force an explicit successor/patch/branch or governed schema migration; changed content may not masquerade as the previous state.

Git commit/tree/blob identity and SHA-256 payload identity are complementary evidence surfaces.

## 7. Federation round-trip

For governed truth `T`:

```text
local T
 -> GitHub/federation
 -> child/consumer
 -> GitHub return
 -> local T''
```

The normal invariant is:

```text
canonical(T) == canonical(T'')
```

or, where exact canonical bytes are appropriate:

```text
SHA256(T) == SHA256(T'')
```

A legitimate transformation must declare its expected semantic delta. Unexplained delta is fail-closed.

## 8. Trust -> authority -> gate spine

Dynamic child injection is resolved through the existing control spine:

```text
TELEMETRY
  -> TRUST
  -> AUTHORITY
  -> GATE
  -> PERMISSIVE / LATCHED INHIBIT
  -> EXECUTION
  -> EXACT RECEIPT
  -> CHILD RE-ENTRY
```

`ACCEPT / REJECT / DEFER` are child dispositions produced by the governed path; they are not a substitute architecture.

Canonical protections:

```text
SCHEMA PASS != CHILD ACCEPT
PARENT PASS != CHILD ACCEPT
MERGED != PERPETUATED
UNKNOWN / DEFER != 0
STATIC DoD != GLOBAL DoV
```

A parent PASS may not compensate a child non-compensating gate.

## 9. Mechanism selection

Cross-boundary integration shall use the existing federation mechanism ladder where applicable:

```text
DEP / REG / SUB / ADAPTER / LAB / FORK
```

The selected mechanism shall identify provider, consumer, authority owner, exact version/SHA, schema, acceptance gate, expected semantic delta and re-entry contract.

`FORK` is not the default response to integration friction.

## 10. Lossless semantic collapse

Many occurrences may normalize to one semantic root while every occurrence/evidence edge remains recoverable.

Required invariant:

```text
EXPAND(COLLAPSE(occurrences)) == occurrences
```

for lineage identity.

Root count may decrease. Lineage/evidence retention shall remain 100%, negative evidence shall survive, and authority/non-compensating gates shall remain visible.

## 11. Temporal checkpoint policy

A checkpoint is a replay accelerator, never a new authority.

Suitable checkpoint boundaries include:

- every N accepted patches;
- major Wave closure;
- completed DMAIC/3P cluster;
- release boundary;
- CONTROL promotion;
- schema migration;
- major federation transaction.

Minimum checkpoint identity:

```yaml
checkpoint_id:
through_event_id:
through_event_digest:
projection_schema_version:
projection_digest:
source_manifest_digest:
authority_digest:
gate_digest:
created_at:
authority_transfer: false
```

The governing proof is:

```text
replay_from_genesis(target).digest
==
replay_from_checkpoint(target).digest
```

Full PATCH history remains authoritative and reconstructible.

## 12. Progressive idempotency

Two layers are required.

### State idempotency

Repeated replay of the same governed lineage yields the same state digest.

### Side-effect idempotency

GitHub issue/PR creation, CI dispatch, child writes, closure and release publication require explicit transaction/idempotency keys and exact receipts. Deterministic projection alone does not make an external side effect idempotent.

## 13. Rendition family

One governed truth may be disseminated through:

```text
SSOT
 |- JSON / YAML / YML
 |- Markdown
 |- HTML navigator
 |- Excel
 |- Word
 `- PowerPoint
```

Every rendition shall carry or resolve the same canonical truth identity.

A renderer may omit detail for a particular audience. It may not create a new logical fact or silently change a controlled value.

## 14. Excel role

Excel may be:

1. a generated human/calculation rendition of a machine SSOT; or
2. the explicitly governed numerical SSOT when the workbook is stable, formula semantics are controlled, units/types are explicit, recalculation is deterministic, machine export exists, and round-trip validation is proven.

Excel + JSON + YAML shall never become three ungoverned competing authorities.

## 15. Cross-rendition zero-delta proof

Let canonical truth be `T` and renditions `R[i]`.

Each rendition with an extractor shall satisfy:

```text
canonical(extract(R[i])) == canonical(T)
```

The release path is therefore:

```text
SOURCE
 -> SSOT
 -> GENERATE
 -> JSON/YAML/MD/HTML/Excel/Word/PPT
 -> GitHub round-trip
 -> REGENERATE
 -> semantic digest comparison
 -> zero unexplained delta
```

Binary formats may vary in package metadata; their semantic extractor contract shall define which metadata is excluded from logical identity.

## 16. Required rebuild commands

The control surface shall converge on these bounded operations:

- `REBUILD_CURRENT`
- `REBUILD_AS_OF <milestone|SHA|timestamp>`
- `EXPAND <root|campaign|milestone>`
- `DIFF <A>..<B>`
- `VERIFY_CHECKPOINT_EQUIVALENCE`
- `VERIFY_ROUNDTRIP`
- `VERIFY_RENDITION_FAMILY`

## 17. Control invariants

```text
ONE_LOGICAL_FACT_ONE_AUTHORITY
DERIVED_VIEW_CANNOT_MUTATE_AUTHORITY
EXACT_FEDERATION_ZERO_DELTA
SAME_LINEAGE_SAME_PROJECTION_DIGEST
EXPAND_COLLAPSE_LOSSLESS
GENESIS_REPLAY_EQUALS_CHECKPOINT_REPLAY
PARENT_PASS_DOES_NOT_IMPLY_CHILD_ACCEPT
UNKNOWN_IS_NOT_ZERO
AUTHORITY_TRANSFER_FALSE_UNLESS_SEPARATELY_GOVERNED
```

## 18. Current implementation mapping

PR `#154` provides the first bounded replay kernel and cold-tail bootstrap.

This document is the normative front-end vocabulary for the next implementation slices. Generic analogies such as Event Sourcing, Saga, Circuit Breaker or Markov state may be used for discussion, but they are not the controlling architecture vocabulary.

The first extensions shall be:

1. checkpoint creation + verification + replay equivalence;
2. rendition-family zero-delta validation;
3. explicit child transaction idempotency receipts;
4. live occurrence importer only after the bounded controls remain lossless.

## 19. Definition of Done

This architecture reaches its first controlled implementation state when:

- SOURCE/TRUTH/OUTPUT/PATCHES remain distinct;
- every `k -> k+1` transition has exact lineage;
- canonical objects bind SHA/digest identity;
- genesis and checkpoint replay converge to the same projection digest;
- semantic collapse is losslessly expandable;
- child disposition remains child-authoritative;
- machine renditions prove zero semantic delta;
- binary renderers carry the same canonical identity and later gain extractor tests;
- GitHub round-trip introduces zero unexplained semantic delta;
- no render, consumer or orchestration layer silently acquires authority.

## 20. Canonical summary

```text
MASTER_INPUT / SOURCE
        |
        v
GOVERNED SSOT / TRUTH
        |
        +-- accepted PATCHES / HISTORY --> next governed state
        |
        +-- deterministic renditions --> JSON/YAML/MD/HTML/Excel/Word/PPT
        |
        +-- exact federation receipts --> child re-entry disposition
        |
        +-- temporal checkpoints -------> accelerated deterministic replay
        |
        `-- round-trip / zero-delta ----> CONTROL
```

```text
one logical truth
+ one authority
+ lossless history
+ deterministic replay
+ zero-delta federation
+ deterministic renditions
= Golden Thread
```
