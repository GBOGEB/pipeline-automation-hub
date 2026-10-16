# CODE PURPLE — Impact CENSUS, CBD, DMAIC and SIPOC

Version: 2026-10-16 / W2. This is a controlled *supporting projection*.

## Outcome / global DoV

Primary measurable output: one source-supported QPS engineering decision, one
independently accepted deliverable, or one verified obligation closure.
A green producer, more PR rows, additional tests, or a submitted RFI is **not**
equivalent to engineering value.

- Historical QPS baseline: 70/90 obligations; do not alter without QPS SSOT.
- Historical MissionControl GOGREEN: 6/42 observed typed cells.
- New cross-repository native replay: UNKNOWN.
- QPS owner approval: DEFER.
- Independent engineering root closures this wave: 0.

## Pulse-to-pulse comparable measures

| Measure | N snapshot | N+1 scope | Interpretation |
|---|---:|---:|---|
| PRs with exact-head GitHub status | 5 | 15 | Breadth of observed PR population only |
| Main repository heads | unrecorded in N | 5 | Intervening-main impact census |
| Root owner families identified | 9 | 6 clustered ownership links | Different denominators; not a burndown |
| Conflicting canonical ownership sets | not measured | 2 | Python compatibility and workflow policy |
| Source-matched coverage uplift | UNKNOWN | UNKNOWN | Require identical eligible population |
| Native DOW/KEB/QPS four-hop | UNKNOWN | UNKNOWN | No fixture promotion |
| Accepted product gain | 0 | 0 | QPS-only owner gate |

The projection MUST reject duplicate keys, changed SHA without rebaseline,
negative workflow denominators, owner references absent from this census,
and any attempted transfer of A10, security, or QPS authority.

## Causal dependency DAG

~~~mermaid
flowchart TD
    A[GitHub exact-head and default-main CENSUS]
    B{Identity + cohort matched?}
    C[Rebase/re-census before comparison]
    D[First-red classification + root fingerprints]
    E[Source-owned disjoint fixes]
    F[Native tests, coverage and security gates]
    G{Independent review + A10 + Safety?}
    H[KEB challenge + DOW native replay]
    I[QPS private population, units and thresholds]
    J{Authorized QPS decision}
    K[Engineering value and DoV receipt]
    HOLD[HOLD / preserve lineage]

    A --> B
    B -->|No| C --> D
    B -->|Yes| D
    D --> E --> F --> G
    G -->|No| HOLD
    G -->|Yes| H --> I --> J
    J -->|DEFER| HOLD
    J -->|ACCEPT| K
~~~

## SIPOC

| Supplier | Input | Process | Output | Customer |
|---|---|---|---|---|
| Repo owners | PR/base/main exact SHAs | Fresh recensus + impact | Source identity ledger | MissionControl |
| ABACUS DOW / LDAB | Debug, BD, CI root receipts | Deduplicate, repair, native replay | Proven causal transitions | CODEX/KEB, QPS |
| CODEX/KEB and gg_MATH | Mathematical receipt and native ZIP | Independent semantics + byte check | Qualified challenge | QPS |
| QPS engineering owner | Population, units, thresholds, supplier responses | Project-specific engineering review | ACCEPT, REJECT or DEFER | Engineering delivery |
| MissionControl | All supporting projections | Disjoint routing, KPI roll-up and review | Proposed next wave | Source owners |

## Scaling / fan-out / fan-in

- Candidate concurrency: **2** source-disjoint workers; scale to **4**
  only after comparable native queue p95, no shared mutable files,
  terminal exact-head evidence, and accepted source-owner agreement.
- MissionControl coordinates, but does not run cross-repo repair by inference.
- CH-BD chain stages: provider -> KEB -> DOW -> QPS -> owner;
  4 evidence handoffs, zero authenticated current completions credited.
- Archive immutable N and N-1. New N+1 receives parent digest and
  its own source manifest; fresh data never overwrites old observations.

## DMAIC, MIP, REX, LDAB, LLDB and 3P*

1. **Define**: deliverable or engineering decision owner wants.
2. **Measure**: exact SHA, eligible denominators, run/job/attempt,
   artifact digest, source coverage, queue/runner times, root.
3. **Analyze**: root-fingerprint clustering, collision/critical-path
   graph and independent negative controls.
4. **Improve**: source-owned repair, not first-red suppression.
5. **Control**: exact-head native proof and repeated recensus; zero
   accepted closure until independent authorization.

- MIP process maturity and DMAIC CONTROL are withheld if observations
  differ in instrument, population or SHA.
- PCA/BT must not fit historical revisions, synthetic fixtures or
  cross-repo job counts as independent engineering trials.
- REX counts only accepted source-bound root transitions.
- LDAB discovery is not LLDB debugger execution. Debugger receipts
  require runner identity, session ID, adapter, steps and port lease
  where applicable.
- 3P* may route proposal/probe actions; promotion is a separate gate.

## Completion tests

- DoD: committed producer and 24 negative/positive tests execute natively.
- DoV-E1: exact-head artifact bytes and three original plus three
  impact output member hashes independently verified.
- DoV-E2: current PR-head and main-head recensus after any intervening work.
- DoV-E3: independent source/security owner disposition, actual verified root
  transition, and QPS acceptance where engineering is concerned.

This page **does not** grant DoV-E1/E2/E3 automatically.
