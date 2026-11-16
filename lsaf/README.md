# LSAF — Lossless Session Assimilation Fabric

## Purpose

LSAF-P0 recovers ChatGPT session work into repo-native, evidence-bearing state without transferring authority from child repositories or allowing reconstructed state to mutate production.

The pilot is intentionally schema-first and read-only-first.

## Authority

- Git + manifest/event receipts are the machine authority.
- Google Drive `codex_history` is a human-facing mirror/index only.
- ChatGPT sessions are recoverable sources, not durable authority.
- Child repository authority remains local: `authority_transfer=false`.
- Hub assimilation is deferred until replay and cold-start proof are complete.

## Pilot cohort

Initial replay window: the last 48 hours of recoverable session material.

Existing producer dependency: issue/PR lane #1211, which moves the session census producer into `tools/threads/session_census.py`.

## Lifecycle

```text
RAW
 -> CAPTURED
 -> INDEXED
 -> SEMANTICALLY_BOUND
 -> DEPENDENCY_ORDERED
 -> EXECUTABLE
 -> EXECUTED
 -> VERIFIED
 -> ASSIMILABLE
 -> ASSIMILATED
 -> MONITORED
 -> RETIRED

side states:
UNKNOWN | BLOCKED | SUPERSEDED | QUARANTINED | REJECTED
```

## Deterministic projections

The manifest/event source should compile reproducibly into:

- `handover.md`
- `dropin.md`
- `dag.mmd`
- `sipoc.mmd`
- `bd_queue.md`
- `predictions.md`

Generated prose is a projection, not the source of truth.

## P0 acceptance

The pilot is not assimilation-qualified until:

1. at least 10 Sessions are recovered;
2. at least 3 recurring multi-session topics are recognized;
3. at least 3 repositories are represented;
4. every fragment is BOUND, SUPERSEDED, QUARANTINED, or UNKNOWN;
5. replay from identical inputs yields identical epic membership, blockers, READY queue, and handover;
6. N->N+1 prediction receipts remain immutable after outcomes are observed;
7. a cold-start consumer reconstructs the same state without relying on chat memory.

Governance disposition: `SCHEMA_FIRST / READ_ONLY_FIRST / AUTHORITY_TRANSFER_FALSE / HUB_ASSIMILATION_DEFERRED`.
