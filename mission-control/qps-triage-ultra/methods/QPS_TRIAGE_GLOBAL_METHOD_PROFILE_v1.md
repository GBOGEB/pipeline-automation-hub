# QPS TRIAGE Global Method Profile v1

**Scope:** GBOGEB Mission Control / horizontal QPS TRIAGE

**Authority:** orchestration, triage, provenance and method-selection only. This document does not create QPS engineering, procurement, compliance, acceptance or release authority. QPS engineering promotion remains a `GBOGEB/cryoplant-project` child re-entry decision.

## Why this exists

QPS TRIAGE now spans source-bound engineering evidence, reliability analytics, RTM/DTM/ADR/OCD tooling, exact-SHA runtime proof, PCA/BT diagnostics and fleet orchestration. Repeating a full framework pass for every change creates noise. The reusable rule is therefore to select the **minimum method sequence that creates new evidence or removes the current blocker**.

Canonical execution primitive:

```text
Mission -> Wave -> Pulse -> Receipt -> Reallocate -> Recurse
```

Canonical closure selector:

```text
3PR -> MIP if an observed structural/recurrence gap exists
    -> 3PC if a bounded transaction/re-entry must be proven
    -> 3P3 once if local DoV is satisfied but reusable propagation proof is missing
    -> STOP
```

## Method catalogue

| Method | Use when | Required output | Do not use for |
|---|---|---|---|
| **3PR** | state/evidence changed materially; current first blocker is unknown or stale | refreshed authority map, current CG/BG/EX/QH/KR, first-red, bounded next action | ceremonial re-analysis of already-proved state |
| **MIP** | an observed structural or recurrence gap prevents convergence | Modernize repair, one evidence-backed Innovation, Perpetuation/control hook | speculative feature growth without a measured gap |
| **3PC** | publication, child re-entry, acceptance, release, exact-SHA or other bounded transaction must cross a gate | Prepare exact inputs, Prove execution/quality/receipt, Commit or explicit HOLD/DEFER | broad discovery or portfolio diagnosis |
| **3P3** | local DoV is already satisfied but reusable cross-repo/generalisation proof is still absent | one propagation/generalisation receipt and stop decision | repeated fan-out or early propagation before local proof |

## 3PR pulse geometry for QPS TRIAGE

A QPS TRIAGE 3PR wave uses the existing horizontal authority split rather than inventing three new authorities:

```text
                        H4_QPS_TRIAGE
              coordinator / veto / BT scheduling
                         /     |     \
                        /      |      \
                       v       v       v
                P1 / H1_QPS  P2 / H2_KEB  P3 / H3_DOW
                child truth   semantics     independent
                + re-entry    + provenance  measurement
                       \       |       /
                        \      |      /
                         v     v     v
                     wave disposition
                ACCEPT / DEFER / PARK / PRUNE
```

### P1 — H1_QPS: authority / source / re-entry

Questions:
- What is the authoritative QPS source or child state?
- What exact source SHA / artifact / bidder / requirement is being consumed?
- Is the proposed output engineering truth, a tooling projection, or an analytical scenario?
- What child re-entry would be required for engineering promotion?

### P2 — H2_KEB: semantics / provenance / anti-overclaim

Questions:
- Are engineering dispositions separated from tooling/model dispositions?
- Are `SOURCE_BOUND`, `SCENARIO`, and `USER_OVERRIDE` visibly distinct?
- Are terms and identifiers canonical and unambiguous?
- Is exact-source lineage preserved through transforms and generated views?

### P3 — H3_DOW: independent measurement / delivery proof

Questions:
- Did the intended executable path actually run (`EX > 0`)?
- Did it pass the relevant quality gate (`QH = PASS`)?
- Is there a durable exact-SHA receipt (`KR`)?
- What measured denominator, gap and residual remain?
- PCA/BT may rank or diagnose work, but cannot create engineering authority.

## QPS TRIAGE applicability model

The common applicability contract should cover six distinct planes without conflating them:

1. **QPS Requirements / procurement-facing obligations**
2. **ADR architecture decisions**
3. **OCD operational scenarios and degraded states**
4. **RTM / DTM traceability and evidence maturity**
5. **Reliability / mission analytics** — MTBF, lambda, exposure, Poisson, containment and consequence as analytical consumers
6. **Mission Control projection** — scheduling, first-red, receipts, reallocation, REX and recurrence control

The following state classes must remain separate:

```text
QPS child disposition        ACCEPT / DEFER / REJECT / ...
Tooling triage disposition   ACCEPT / DEFER / NEEDS_SOURCE / ...
Reliability model state      ACTIVE / SCENARIO_ONLY / EXCLUDED
Mission execution state      DIAGNOSE / PROVE / COMMIT / STOP / ...
```

No state in one class silently promotes another class.

## Reliability-specific guardrail

A component MTBF is an initiating-event input. It is **not** a QPS system-event MTBF and does not consume a Table-10 budget until the failure path establishes architecture response, preserved state, recovery, common-cause treatment and highest consequence class.

Recommended analytical chain:

```text
source-bound component evidence
          |
          v
native failure rate by state
          |
          +--> state exposure -> mu -> P(0), P(>=1), P(k)
          |
          v
architecture / containment consequence
          |
          +--> p_propagate_to_beam
          +--> event_class NONE/A/B/C
          +--> MTTR / MDT / spares
          |
          v
child re-entry / Table-10 allocation (only if accepted)
```

## Three-wave burn-in pattern

### H4_QPS_TRIAGE:W1 — 3PR + MIP-M

Goal: refresh current authority/runtime state and modernize the applicability contract.

Victory condition:
- three pulse receipts exist (H1/H2/H3);
- applicability distinguishes reliability-model state from triage/engineering disposition;
- Mission Control is registered as a projection plane;
- no authority transfer occurs.

### H4_QPS_TRIAGE:W2 — 3PC + MIP-I

Goal: perform one bounded child re-entry transaction using the reliability bridge and one real source-bound atom.

Victory condition:
- Prepare: exact source + exact consumer identity pinned;
- Prove: deterministic calculations and fail-closed system consequence reproduced;
- Commit: child accepts the analytical consumer contract or explicitly DEFERs it;
- Innovation: shared operating-state ledger fields are attached without creating a competing SSOT.

### H4_QPS_TRIAGE:W3 — 3P3 + MIP-P

Goal: propagate the proven pattern once into global Mission Control and durable restart/control surfaces.

Victory condition:
- one reusable cross-repo receipt;
- recurrence/REX/control hook;
- canonical restart card;
- no repeated fan-out after generalisation proof.

## Stop-gate logic

```text
changed state/evidence?
   no -> STOP / REPEAT
   yes
    |
   3PR
    |
observed structural gap?
   yes -> MIP-M/I/P only as needed
    |
bounded transaction required?
   yes -> 3PC
    |
local DoV satisfied but reusable propagation missing?
   yes -> one 3P3
    |
   STOP
```

A green badge without intended executed steps is not proof. Activity without an accepted receipt changes diagnosis but gives zero promotion credit.

## Sub-chat / session decomposition

Use separate sessions only where authority, runtime or evidence density warrants it:

- **S-H4 / Mission Control:** portfolio state, wave plan, receipts, BT/PCA resource pressure, REX and stop decisions.
- **S-H1 / QPS child:** source consequence, architecture, Table-10 and engineering re-entry only.
- **S-H2 / KEB semantics:** glossary, schema, provenance, authority/state separation and exact-source challenges.
- **S-H3 / DOW runtime:** census, executable proof, KPI denominators, independent calculations and delivery QA.
- **S-DASH / specialist UI:** dashboard interaction/layout only after model/authority contracts are stable.

A session must hand back a compact receipt to H4 rather than becoming a parallel authority.

## Global KPI contract

Every pulse reports:

```text
before -> observed -> delta -> target -> remaining gap
CG / BG / EX / QH / KR / DR / SR / WD / PB
```

`PB` and PCA/BT are progress/priority diagnostics. They never substitute for source-bound QPS child disposition.
