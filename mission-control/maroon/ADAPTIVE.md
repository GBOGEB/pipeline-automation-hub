# CODE MAROON adaptive closure matrix

Status: advisory routing layer. It does not replace the MAROON operations ledger, Kahn scheduler, GOGREEN root-red, EVERRED, provider review state, or merge admission.

## Purpose

Turn each current MAROON root into one explicit next lane, stop duplicate diagnosis, bound self-repair, and pass persistent red to the existing causal owners.

The closure unit remains the individual review/scanner obligation. Recurrence may share diagnosis and treatment method; it never erases child proof/readback/closure obligations.

## Actors

| Actor | Owns | Does not own |
|---|---|---|
| MAROON intake | Complete OPEN-PR/provider census and `operations.ingest()` | Repair or merge |
| `hints.py` | Finding identity, recurrence and reuse/fold-back proposals | Admission or closure |
| `adaptive.py` | One advisory next lane per root | Metrics, claims, provider mutation |
| `operations.py` | Kahn DAG, dependencies, packets, leases, fencing, claims | Root-red metrics |
| JADE CREW + MAROON coordinator | Existing bounded worker pulse | A second controller |
| Branch repair worker | Minimal owned-branch source treatment | Cross-branch writes |
| Restack worker | Reconcile stale owned branch to current default and rescan | Treat stale symptoms first |
| Fold-back worker | One source-prevention repair where the defect exists on default | Closing all children without readback |
| `closure.py` | Evidence reply, provider resolution/readback and ledger closure | Scanner-alert dismissal |
| GOGREEN root-red | First/root-red attribution after bounded failed self-repair | MAROON closure bookkeeping |
| EVERRED/red-trace owners | Persistent/oscillating workflow history | A third recurrence metric |
| Owner return | Credentials, foreign fork, policy/authority decisions | Pretend source repair |

## SIPOC

**Suppliers:** GitHub PR/review/scanner state; MAROON ledger; `hints.py`; canonical GOGREEN/EVERRED outputs; prior REX.

**Inputs:** exact head/base/source/core OIDs; finding identity; Kahn dependencies; branch/path ownership; prior attempt receipts; optional red-trace class.

**Process:** normalize -> diagnose -> route -> Kahn admit -> fenced claim -> treat/restack/fold-back or pass-on -> verify -> publish -> reply -> resolve -> readback -> close -> REX -> CONTROL.

**Outputs:** one next lane per root; bounded disjoint worker wave; source-bound closure receipts; root-red/EVERRED handoff; prevention candidate; telemetry.

**Customers:** PR owners; existing JADE/MAROON coordinator; blocked descendants; next intake pulse.

## Trigger and stop rules

A route is recalculated after a complete provider intake, head/discussion/source drift, a failed repair release, provider resolution, recurrence change, or new red-trace evidence.

A source-writing worker may start only after the canonical `operations.py` queue-plan admits the root and the real claim passes its branch/path/OID/fencing checks. **No queue-plan means zero dispatch.**

Stop or pass on instead of retrying when:

- the root is a negative canary or intent is unknown;
- source/head/core OIDs drift;
- dependencies or Kahn admission are incomplete;
- the branch is foreign or otherwise not safely writable;
- provider state and ledger state disagree (reconcile first);
- default source disappeared or moved (restack first);
- the same root has two released failed self-repair attempts;
- canonical red-trace classifies the affected path as EVERRED, GREEN_TO_RED or FLAKY;
- credentials/policy/owner authority are the real blocker.

The two-attempt budget is not a promise of two mutations. A first attempt may be analysis-only, and a root can pass on immediately when canonical red evidence already proves that another blind repair would be wasteful.

## Routing lanes

- `ANALYZE_ONLY_CANARY` — preserve the negative control.
- `OWNER_RETURN` — return exact evidence/unblock predicate.
- `LEDGER_RECONCILE` — provider is already resolved; finish durable state.
- `RESTACK_FIRST` — stale/removed default source; reconcile branch then rescan.
- `REUSE_METHOD` — apply a prior proved treatment to this exact packet.
- `PR_LOCAL_REPAIR` — minimal current-branch repair.
- `FOLD_BACK_DEFAULT` — repair systemic cause once at its source, then restack/reverify children.
- `PASS_ON_ROOT_RED` — self-repair budget exhausted; GOGREEN attributes the causal first/root red.
- `PASS_ON_EVERRED` — persistent or oscillating red is already proven.
- `HOLD` — evidence/admission is not current.

## Scaling rule

Scale **methods and disjoint execution**, not closure claims.

A systemic family can become one fold-back method and many child verification packets. The number of source edits may collapse sharply while the number of provider readbacks does not. Report both:

1. unique semantic roots/methods;
2. raw observations/children;
3. worker waves and concurrency conflicts;
4. verified closures/reopens;
5. first-red-to-root latency and repair-to-CONTROL latency when canonical owners provide them.

Increase concurrency only after comparable pulses show non-regressing closure yield and no source/claim collisions. The advisory router accepts at most four preview workers; the existing worker controller and `operations.claim()` retain the real limit.

## Current pilot boundary — 12 November 2026

The private v12 ledger contains a 51-PR provider census but only an older 88-observation executable graph. The current provider census therefore cannot safely release workers until all current unresolved items are fed through `operations.ingest()` and a fresh Kahn plan is persisted.

A conservative exact-title diagnostic on that stale graph found two systemic action-pinning families spanning 32 observations. Live ABACUS source comparison showed that some affected paths still carry the same class on default, while #2708's launcher/red-census paths are absent from current default. This validates two different routes: **fold-back source prevention** versus **restack/retire assessment**.

This pilot is method evidence, not scaling proof and not merge authority.
