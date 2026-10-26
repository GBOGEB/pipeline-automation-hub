# CODE PURPLE WATCH vNext — bounded consumer (MIP-01/02/04/09/11/14)

This implementation **continues**, rather than replaces, the N0 historical handover in PR #876. It uses existing canonical owners listed in `AGENTS.md`, not a second source producer or an unscheduled background agent. The source of truth for default-head pulses remains the immutable SHA256-chained `gogreen/scale_dock_series.py` ledger. The source of authenticated six-repo breadth remains merged Mission Control #531; ZIP bytes remain merged #530; Method Atlas #533 remains read-only.

## Implemented in this bounded PR

`watch_decision.py` is an **offline pure decision consumer** with an opt-in local cursor writer, not a Github Actions collector or notification service.

- Five separate checkout identities: PR head, base, actual checkout, synthetic merge and merged main; source run/job/attempt bound to the declared head.
- Strictly public allowlisted source rows and exact typed schema. Private QPS rows, undocumented fields and unsafe source paths fail closed rather than leaking into a public artifact.
- Noncompensating native required receipt vetoes even if the parent workflow is GREEN. The consumer never reports merge admission or engineering credit.
- Same-source-blob/same tool+version+selection+config **and denominators** for comparable statement and branch deltas. An equal denominator alone is not proof of comparability.
- Replay-safe native key (repo, lane, checkout, run, attempt, job); conflicting data for the same key fails. One notification candidate with multiple reasons per meaningful transition, repeated same first-red suppressed.
- Terminal cancelled/skipped cannot improve readiness. Out-of-order observed events are retained as seen but cannot roll back a newer lane.
- Distinct native events and a matched population are mandatory for stability. Four comparable equal observations produce three equal transitions and STABLE_HOLD, not four repeated polls.
- The local cursor is a **decision projection**, not an event journal. Default CLI is read-only; explicit `--write-cursor` takes an exclusive single-writer lock and atomically replaces the local cursor.

## Usage (offline only)

```bash
python -m unittest discover -s mission-control/gogreen/tests -p 'test_watch_decision.py' -v

# Inputs must be independently prepared by the public canonical source owners.
# This command does not issue GitHub API requests and sends no notifications.
python mission-control/gogreen/watch_decision.py \
  --events /path/to/public-owner-terminals.jsonl \
  --cursor /path/to/public-watch-cursor.json

# Only after operator review of producer lineage, opt in to durable cursor update.
python mission-control/gogreen/watch_decision.py \
  --events /path/to/public-owner-terminals.jsonl \
  --cursor /path/to/public-watch-cursor.json --write-cursor
```

Each JSONL line has schema `codepurple.watch.terminal/v1` and **exactly** these top-level fields: `schema`, `repository`, `lane`, `identity`, `native`, `result`, `coverage` (nullable). See synthetic test fixtures `tests/test_watch_decision.py` for valid shapes and mutation controls. Records are caller assertions until source-native readback; no field in the schema is a signature or source certificate.

Consumer outputs always say `admission=HOLD`, `notification_emission=NONE_LOCAL_PREVIEW` and `source_authentication=CALLER_ASSERTED_NOT_NATIVE_READBACK`. An ACCESS_DENIED or missing source token maps to UNKNOWN, never zero.

## Explicit gaps (do not claim DONE)

1. The canonical source-owned **adapter** that prepares these strict public JSONL records has NOT been added; neither the historic chat event journal nor the candidate cursor can claim authenticated fleet breadth. Do not feed the handover's reported rows into this interface as native proof.
2. No notification transport, scheduler, automatic watcher or overlapping-watch disablement has been implemented or authorized. A returned notification is a **candidate for an operator-reviewed message**, not a delivered alert.
3. Owner-accepted causal root closure, JUnit-count reconciliation, QPS private readback, actual runner worker-hours, verified Pages deployment, and PCA/BT promotion are still separate unsatisfied contracts.
4. The existing `federation/convergence/converge.py` and `golden-thread/checkpoint_replay.py` remain owners of convergence and replay logic. This module is the narrowly scoped terminal-to-notification projection, not their replacement.
5. The dashboard integration must consume this cursor plus owner-source data through `gogreen/launcher/` after source review; do not insert a hardcoded independent KPI.

## Acceptance route

Bounded draft PR -> exact-head G4 unit tests (with adversarial fixtures) -> native receipt and mandated CI/security -> independent reviewer + First-Pass gate -> governed merge/readback -> only then update the historic N0 handover's implementation status. Until then MIP-01/02/04/09/11/14 are **CANDIDATE / PARTIAL**, not DONE.

**Noncompensating invariants:** merge HOLD, no security waiver, no QPS engineering acceptance, no formal-credit delta, no remote dispatch or mutation.
