# QPS Expedition Fleet — Temporal Status Hook

**Rule:** the canonical mission table is authoritative. Everything below it is a derived view of `analytics/EXPEDITION_FLEET_ITERATION_LEDGER_v1.json` and must never replace the mission receipts.

## Canonical mission table

| Mission | Wave / pulse | State | Current BG | Next CG | Crew | DoV | Resource action |
|---|---|---|---|---|---|---|---|
| M01 CoolProp/private QPS | CONTROL | external-blocked | private runner admission + low-T HEPAK authority | runner>0 and steps>0; licensed HEPAK receipt | Dockmaster + PM/TM/QA | withheld in private child | keep one cell |
| M03 GitHub MCP | CONTROL | bounded DoV-3 | broader operation parity only | recurrence/selective pruning | tiny Control | 3 bounded | contract |
| M05 Provenance | CONTROL | bounded DoV-3 | C5 time-separated recurrence only | observe future recurrence, no feature growth | QA + PM/TM/Governor | 3 bounded | contract |
| M06 Telegraf Observer | RETURN | reference/park | low marginal value for one-metric state slice | re-enter only for real time-series/multi-signal need | tiny reference | DoV-1 | return crew |
| M07 Leak dashboard | CONTROL | split disposition | historical project inputs need current source reconciliation | re-enter only on source return/current consumer need | Governor + PM | DoV-1 kernel | return generalists |
| M08 Cryogenic workspace | CONTROL | quarantine/reference | property provenance + dimensional source inputs | independent reference grid + source-bound geometry/units | Scientist + TM/Governor | DoV-1 control | return generalists |
| M09 Legacy document processor | EXECUTE | queued truth probe | executed truth classification pending | exact-head invalid-PPTX truth receipt | Smoker + Analyst + QA | pending | active small cell |
| W3-15 Observed BT | CONTROL | PASS/MERGED | none | preserve evidence | HOME control | PASS | close |
| W3-12 HEPAK | IMPROVE→EXECUTE | external-local | licensed HEPAK numeric receipt | 8-row CSV + manifest → adapter/consumer | TM + Scientist + QA | sole W3 gate | local licensed action |

## Fast fleet dashboard

```text
W3 STRICT           15/16  ███████████████████░  93.75%
W3-12 HEPAK          OPEN  ████████████████████  sole gate
M09 truth probe     QUEUED  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒  in flight
M01 private runner   HOLD  ███░░░░░░░░░░░░░░░░░  external
M05 provenance    CONTROL  ████████████████████  DoV-3 bounded
M06 observer         PARK  ██████████░░░░░░░░░░  DoV-1/value stop
M07 leak kernel   CONTROL  ██████████░░░░░░░░░░  DoV-1 split
M08 N3 guard      CONTROL  ██████████░░░░░░░░░░  DoV-1 quarantine
```

## Runtime topology

```text
                         ┌── M01 private runner ── EXTERNAL HOLD
                         │
HOME / ORCHESTRATOR ─────┼── W3-12 HEPAK ──────── LOCAL LICENSED EXECUTION
                         │
                         ├── M09 truth probe ───── QUEUED / RUNNABLE
                         │
                         ├── M05 provenance ────── CONTROL
                         ├── M06 observer ───────── RETURN/PARK
                         ├── M07 leak kernel ────── CONTROL
                         └── M08 N3 guard ───────── CONTROL
```

## Measured execution economics

| Pulse | Queue s | Runtime s | Dominant cost | Artifact | Outcome / decision |
|---|---:|---:|---|---:|---|
| M05 exact attest | 3 | 14 | official attestation | 8.4 kB | high conversion; continued to bounded DoV-3 |
| M06 Telegraf | 2 | 410 | Go build 379 s | 150.8 MB | runtime PASS, value gate says PARK |
| M07 leak kernel | 160 | 16 | runner queue | 1.3 kB | DoV-1 PASS; split promote/quarantine |
| M08 guard | 98 | 8 | runner queue | — | DoV-1 quarantine PASS |
| W3-15 analytics | 487 | 10 | runner queue | 2.9 kB | W3 gate PASS |
| M09 truth | — | — | queued | — | pending |

### Derived signal

For the lightweight successful control pulses, **queue delay is now generally larger than execution time**. This is a fleet scheduling observation, not the same defect as M01's completed `runner_id=0` execution-habitat failure. M06 is the outlier: its work itself is expensive because 379 of 410 seconds are compilation, and the retained artifact is ~150 MB for a one-metric proof. That is why its crew was returned rather than scaled.

## DMAIC / PCA / BT

```text
DMAIC
DEFINE   PASS — mission objectives and authority boundaries are explicit
MEASURE  PASS — exact run/SHA/runner/timing/receipt rows now span multiple missions
ANALYZE  PASS — queue, compilation, external-local licence and authority are separated blockers
IMPROVE  ACTIVE — M09 truth pulse + W3-12 preflight/local execution hand-off
CONTROL  ACTIVE — M03/M05/M06/M07/M08 contracted appropriately

PCA (portfolio expedition)
DEFER — row count is no longer the only issue. Missions are heterogeneous capability classes.
Activate only after normalized comparable features exist across >=3 missions and >=2 pulses/class.

BT / reverse pressure
ACTIVE — explicit outcomes guide resource conversion.
1. W3-12 has highest strategic leverage but needs licensed local execution.
2. M09 is highest currently runnable information-gain pulse.
3. M01 retains one Dockmaster cell only.
4. M06/M07/M08 generalist capacity is returned.
```

## Temporal hook

```text
observe
  ↓
append event/iteration
  ↓
canonical mission table
  ↓
BG / CG reduction
  ↓
PM + TM + Analyst allocation
  ↓
execute / first-red
  ↓
QA receipt
  ↓
Governor disposition
  ↓
contract / expand / reinforce / return
  ↓
recurse
```

### Current conquest

`W3-15 PASS → strict W3 = 15/16 → W3-12 HEPAK is sole strategic gate.`

Cloud capacity should continue useful runnable work (currently M09) while the W3-12 local licensed execution package remains fail-closed and ready for the Windows+Excel+HEPAK runtime. The two lanes must not be conflated.
