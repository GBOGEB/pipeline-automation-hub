# LSAF-P0 Lossless Handover

## 1. Identity

- Repository: `GBOGEB/pipeline-automation-hub`
- Parent issue: #1230 — LSAF-P0 — Lossless multi-session recovery and assimilation pilot
- Pull request: #1231 — `feat(lsaf): add lossless multi-session genome and assimilation pilot`
- Branch: `feat/lsaf-session-genome-pilot`
- Base: `master`
- Last verified head before this handover pack: `b3feb4c962fe5bff2eaf3d3bb6adbd2632a3df80`
- Verified PR state at handover start: open, non-draft, `mergeable=false`
- Existing producer dependency: #1211 — session census lane
- Authority transfer: `false`
- Production assimilation: `deferred`

This handover is additive. It does not authorize merge, branch protection changes, workflow mutation, title mutation, issue closure, or child-repository authority transfer.

## 2. Purpose

Continue LSAF from a schema-first / read-only-first pilot into a deterministic reconstruction and replay implementation.

The target system is:

```text
session sources
  -> immutable events
  -> semantic fragments
  -> temporal + semantic indexes
  -> recurrence fingerprints
  -> dependency DAG
  -> Kahn READY/BLOCKED/CYCLE projection
  -> deterministic handover/drop-in projections
  -> immutable N->N+1 predictions
  -> observed outcomes + calibration
  -> cold-start reconstruction proof
  -> ASSIMILABLE
  -> [later, separately admitted] Hub consumption
```

## 3. What already exists

### 3.1 Schema and taxonomy

Under `lsaf/`:

- `README.md`
- `taxonomy.yaml`
- `schemas/session.schema.json`
- `schemas/fragment.schema.json`
- `schemas/event.schema.json`
- `schemas/prediction.schema.json`
- representative session and fragment fixtures

### 3.2 48-hour pilot cohort

- `lsaf/cohorts/2026-11-10_12/session-index.yaml`
- `lsaf/cohorts/2026-11-10_12/recurrence-ledger.yaml`

Provisional DoV already demonstrated by the bounded cohort:

- 10 recovered Sessions
- 5 recurrence fingerprints
- 6 repositories represented
- live ChatGPT PIN ordering intentionally retained as `UNKNOWN`

Do not invent missing PIN order.

### 3.3 Current recurrence families

- `GATE.EXACT_HEAD.INDEPENDENT_REVIEW`
- `QUEUE.BACKPRESSURE.N6`
- `CLOSURE.DOV_DOD.ISSUE_PR`
- `AUTOMATION.CENSUS_TO_ACTION`
- `COVERAGE.ZERO_TO_SCALE`

Treat these as semantic hypotheses backed by the pilot cohort, not universal production rules yet.

### 3.4 External mirror

Google Drive mirror root:

- folder: `codex_history`
- purpose: human archive / index / review surface only
- never treat Drive as the machine authority

Expected mirror folders:

- `00_README`
- `01_SESSION_ARCHIVE`
- `02_EPIC_VIEWS`
- `03_HANDOVERS`
- `04_DAG_SIPOC`
- `05_PREDICTION`
- `90_EXPORT`
- `99_QUARANTINE`

Git + manifest/event receipts remain authoritative.

## 4. Immediate implementation boundary

Implement the next slice without production mutation.

### Lane A — dependency/DAG compiler

Input:
- session cohort
- fragment dependencies
- recurrence ledger

Produce:
- normalized dependency nodes
- edge list
- Kahn in-degree calculation
- `READY`
- `BLOCKED`
- `CYCLE`
- `MISSING_AUTHORITY`
- `MISSING_EVIDENCE`
- deterministic `dag.mmd`

Required property:
same normalized input -> byte-stable logical ordering and identical node classification.

### Lane B — deterministic projections

Implement generation from authoritative manifest/event state into:

- `generated/handover.md`
- `generated/dropin.md`
- `generated/bd_queue.md`
- `generated/sipoc.mmd`
- `generated/dag.mmd`

Generated prose is not authoritative and must not be hand-maintained as state.

### Lane C — N->N+1 prediction receipts

Create prediction receipts before outcomes are observed.

Minimum fields:
- prediction id
- source state
- predicted next state
- predicted blocker
- predicted repository
- expected runs/commits to next boundary when available
- confidence
- timestamp

After outcome:
- append/reconcile observed state without rewriting the original prediction
- score top-1, top-3 when available
- record false-ready / false-blocked
- support Brier/calibration metrics when probabilities exist

### Lane D — cold-start reconstruction

A separate worker/session must be able to reconstruct:
- active epics
- READY queue
- blockers
- repository allocation
- next predicates
- predictions

using repository artifacts only, without prior chat context.

## 5. Explicit non-goals for this slice

Do not:

- automatically rename ChatGPT chats
- dispatch production workers from reconstructed state
- merge #1231
- close #1230
- alter branch protection
- mutate child-repo issue/PR state from inferred data
- convert UNKNOWN to PASS/FAIL without evidence
- transfer authority from child repositories
- treat repeated workflow reruns as independent evidence by default
- duplicate the #1211 census producer

## 6. Implementation guidance

Prefer small modules with deterministic pure functions.

Suggested layout:

```text
lsaf/
  compiler/
    normalize.py
    fingerprints.py
    dag.py
    project.py
    predict.py
  schemas/
  cohorts/
  tests/
    fixtures/
    test_normalize.py
    test_fingerprints.py
    test_dag.py
    test_projection.py
    test_prediction_receipts.py
  generated/
```

The names are recommendations, not authority. Reuse existing Hub utilities when compatible rather than creating parallel implementations.

## 7. Evidence model

Use evidence classes explicitly:

- `SOURCE` — directly observed source state
- `DERIVED` — deterministic transform from source
- `PREDICTED` — forward estimate, never truth
- `UNKNOWN` — insufficient evidence
- `SUPERSEDED` — preserved history no longer current

Every promoted conclusion should retain pointers to the evidence that produced it.

## 8. N->N+1 confidence rule

Do not equate age with confidence.

Distinguish:

- validation age: qualifying independent evidence accumulated after change
- staleness age: time since last qualifying validation

Confidence may increase with independent evidence and decay with staleness.

Repeated runs sharing the same head/environment/test path should receive reduced effective-observation weight.

## 9. Required tests before wider scaling

At minimum:

1. schema validation for supplied fixtures
2. deterministic normalization test
3. duplicate/recurrence fingerprint test
4. Kahn DAG acyclic case
5. Kahn cycle detection case
6. missing-authority case
7. missing-evidence case
8. deterministic generated projection test
9. immutable prediction-before-outcome test
10. false-ready negative regression
11. false-blocked negative regression
12. cold-start reconstruction equivalence test

A 12-case replay pilot is preferred before expanding beyond the bounded cohort.

## 10. DOV / DOD

### DoV

- bounded cohort remains reproducible
- at least 10 sessions
- at least 3 recurrence families
- at least 3 repositories
- deterministic DAG classification
- at least 5 preserved N->N+1 prediction receipts
- cold-start reconstruction agrees on READY/BLOCKED state

### DoD

Every recovered fragment is explicitly one of:

`BOUND | SUPERSEDED | QUARANTINED | UNKNOWN`

and identical source inputs produce identical:

- epic membership
- recurrence fingerprints
- dependency graph
- READY/BLOCKED classification
- generated handover/drop-in
- prediction source-state bindings

Operational Hub assimilation remains a separate admission decision.

## 11. Receiving-worker start sequence

1. Read `lsaf/handover/manifest.yaml`.
2. Read `lsaf/handover/glob.yaml`.
3. Inspect #1231 current head and CI before editing.
4. Inspect #1211 and reuse its census producer contract.
5. Validate existing schemas/fixtures/cohort.
6. Implement Lane A first.
7. Add adversarial tests before promoting Lane B/C.
8. Keep commits lane-specific and independently revertible.
9. Update #1230 with evidence, not narrative-only status.
10. Do not mark ASSIMILATED; the maximum state in this PR is `ASSIMILABLE`.

## 12. Stop conditions

Stop and retain fail-closed state if:

- current #1231 head diverges unexpectedly
- schema change would invalidate existing cohort without a migration receipt
- #1211 producer contract changes incompatibly
- authority ownership is ambiguous
- a generated view would need inferred PASS/FAIL
- DAG contains unresolved cycles
- cold-start reconstruction disagrees materially with the source manifest

Disposition at handover:

`LSAF_P0_ACTIVE / REPO_NATIVE_HANDOVER_BOUND / READ_ONLY_IMPLEMENTATION_NEXT / PRODUCTION_ASSIMILATION_DEFERRED`.
