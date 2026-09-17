# MissionControl Golden Thread v1

Status: `CANDIDATE_IMPLEMENTATION`

Authority transfer: `false`

Parent control surfaces:

- `pipeline-automation-hub#153` — fleet-global issue register / two-ended BD pinch orchestration.
- `pipeline-automation-hub#85` — canonical BD / REX / CONTROL lifecycle authority.
- `pipeline-automation-hub#76` — Historian current-state verification and missed-work lineage.

This package adds a **replay and provenance substrate**. It does not allocate a new Grand Mission, does not replace the canonical BD lifecycle, and does not allow MissionControl projections to promote repo-local engineering truth.

## 1. Golden Thread invariant

```text
projection may change; source history may not
```

The authoritative model is:

```text
GitHub / exact receipts / source evidence
              |
              v
      occurrence/evidence events
              +
       normalisation events
              |
              v
      append-only hash chain
              |
       deterministic replay
              |
              v
  regenerable materialised views
  roots / campaigns / BD queue / CONTROL / age / pinch
```

The v1 deterministic invariant is:

```text
same ordered ledger
+ same projection schema version
= same projection digest
```

## 2. Why this is not merely "event sourcing"

The supplied architecture Read is directionally correct but needs four controls to remain safe in MissionControl:

1. **Progressive idempotency has two layers.** Replay idempotency means the same immutable ledger regenerates the same projection. External side effects (GitHub writes, child injection, CI dispatch, closure) also require their own idempotency key / exact receipt; deterministic JSON alone does not make a side effect idempotent.
2. **Accept / Reject / Defer is an admission/disposition state machine.** It can participate in a saga, but is not itself equivalent to the Saga or Circuit Breaker patterns.
3. **`S[k+1] = f(S[k], event)` is deterministic state transition, not necessarily a probabilistic Markov claim.** The normalised state must already contain all authority/gate context required for the next transition.
4. **Snapshots accelerate replay; they never truncate lineage.** A snapshot must bind the parent event digest and projection digest. The event ledger remains authoritative, so no "snapshot compaction" may erase negative evidence, split/merge history, or a non-compensating gate.

A Merkle tree can be added later for block-level proofs. V1 deliberately uses a simpler event hash chain first because it directly proves deletion/reordering/tampering without introducing a second indexing authority.

## 3. Event model

Supported canonical events:

- `OBSERVED`
- `BOOTSTRAP_RECONSTRUCTED`
- `CLASSIFIED`
- `ROOT_CREATED`
- `ATTACHED_TO_ROOT`
- `WORK_ORDER_CREATED`
- `CAMPAIGN_ATTACHED`
- `EVIDENCE_ADDED`
- `AUTHORITY_BOUNDARY_ASSERTED`
- `NON_COMPENSATING_GATE_SET`
- `STATE_CHANGED`
- `CONTROL_PROMOTED`
- `MERGED_INTO`
- `SPLIT_FROM`
- `SUPERSEDED_BY`
- `INVALIDATED`
- `REOPENED`
- `RETIREMENT_CANDIDATE`

Every event carries `previous_event_digest` and `this_event_digest`. Existing historical material imported after the fact uses `BOOTSTRAP_RECONSTRUCTED` and preserves both the source-observed timestamp and later reconstruction timestamp.

## 4. Rebuild modes

```bash
python mission-control/golden-thread/golden_thread.py verify LEDGER.json
python mission-control/golden-thread/golden_thread.py rebuild-current LEDGER.json --out current.json
python mission-control/golden-thread/golden_thread.py rebuild-as-of LEDGER.json GT-0008 --out as_of.json
python mission-control/golden-thread/golden_thread.py expand-root LEDGER.json ROOT-LS --out expanded.json
python mission-control/golden-thread/golden_thread.py diff LEDGER.json GT-0008 GT-0013 --out diff.json
```

Historical boundaries may be an event id, an ISO-8601 timestamp, or a source SHA explicitly bound by an event.

## 5. Lossless-collapse controls

Semantic collapse is a projection operation only. V1 preserves:

- every occurrence;
- every evidence atom;
- every attach/split/merge/supersede edge;
- authority domain;
- non-compensating-gate state;
- negative evidence;
- `UNKNOWN_NEEDS_READER` until an explicit later event resolves it.

A root may be compact in the current view while `expand-root` reconstructs the occurrences, work orders, evidence and successor/predecessor lineage beneath it.

The safety target remains:

```text
issue noise DOWN
+ duplicate roots DOWN
+ executable clarity UP
+ lineage retention == 100%
+ authority inversions == 0
```

## 6. Child injection / disposition contract

Golden Thread does not directly execute a child. A child transaction should be modelled as:

```text
CHILD_INJECTION_REQUESTED
    -> current-state / authority preflight
    -> ACCEPT | REJECT | DEFER
    -> exact child receipt if accepted
    -> EVIDENCE_ADDED / STATE_CHANGED
```

V1 keeps the event vocabulary intentionally narrow and records child disposition inside `CLASSIFIED` / `STATE_CHANGED` payloads. A later schema revision may promote these to first-class event types only after multiple observed consumers need them.

Required protection:

```text
parent orchestration PASS != child authority PASS
```

No parent receipt may compensate a child repo's non-compensating gate.

## 7. Temporal snapshots

Recommended checkpoint object for a later v1.1:

```json
{
  "schema": "missioncontrol.golden_thread_snapshot.v1",
  "through_event_id": "GT-1000",
  "through_event_digest": "sha256:...",
  "projection_schema_version": 1,
  "projection_digest": "sha256:...",
  "created_at": "...",
  "authority_transfer": false
}
```

A checkpoint is a cache. Replay from genesis must remain possible, and replay from a checkpoint must converge to the same current projection digest.

## 8. Bootstrap fixture

`fixtures/COLD_TAIL_BOOTSTRAP_LEDGER_v1.json` reconstructs the bounded `#153` cold-tail sample:

- `ABACUS#581` — Line-S parent/source occurrence;
- `ABACUS#583` — subordinate Line-S work-order occurrence;
- `ABACUS#585` — historical CI defect evidence / retirement candidate with current-run proof withheld;
- `CODEX#237` — helper applicability remains `UNKNOWN_NEEDS_READER` pending capability/DoD crosswalk.

`ROOT-LS` in the fixture is explicitly a **projection-local bootstrap semantic root**, not a newly allocated canonical `HIST-BD-NNN` identifier. Canonical BD allocation remains under `#85`.

## 9. DoD / DoV for this slice

The slice is complete when:

- ledger hash-chain verification detects tampering/reordering;
- `REBUILD_CURRENT` is deterministic by digest;
- `REBUILD_AS_OF` reproduces an earlier projection boundary;
- `EXPAND_ROOT ROOT-LS` recovers all three Line-S occurrences;
- `DIFF A..B` emits the intervening immutable events and metric delta;
- bootstrap events distinguish original source time from reconstruction time;
- no GM/LM registry mutation occurs;
- authority transfer remains false.

Fleet-wide ingestion, live GitHub harvesting, Merkle block proofs, snapshot acceleration, and child-side-effect idempotency receipts remain the next bounded implementation layers.
