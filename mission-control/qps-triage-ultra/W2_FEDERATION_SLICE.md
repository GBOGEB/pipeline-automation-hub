# QPS TRIAGE ULTRA — W2 Federation Slice

Status: `ACTIVE / DOV WITHHELD`
Parent merge: `f41e96dfe5fde5312f3ebb5dc41fc391cb593c6d` (ULTRA PR #20)

## Objective

Turn three independently useful nodes into one governed fleet path:

`M02A receipt + M02B receipt + ULTRA receipt -> contract validation -> ALL_REQUIRED AND gate -> W2 DoV`

The slice is deliberately stronger than "three green repositories". It requires exact-source receipts, failure visibility, receipt consumption and a single governed federation decision.

## Fixed W2 DoD denominator

The denominator is frozen at 12 gates for this slice. A later wave may add new gates, but W2 history is not rewritten.

| Gate | Requirement | Current state |
|---|---|---|
| W2-01 | ULTRA W0/W1 control plane merged | PASS — `f41e96df...` |
| W2-02 | M02A W0/W1 source-recovery + first runtime merged | PASS — PR #5 / `9a9131cf...` |
| W2-03 | M02B first kernel + semantic guard package merged | PASS — PR #1 / `543567eb...` |
| W2-04 | M02A exact-head runtime executes >0 | PASS — run `34615256406` on `b52f65fc...` |
| W2-05 | M02B exact-head runtime executes >0 | PASS — run `34615269215` on `7d544a63...` |
| W2-06 | Common `qps-fleet-receipt/v1` contract exists | PASS |
| W2-07 | M02A W2 byte-identical recovered blob is source-bound | PASS — Git blob `2d23e1d0...` |
| W2-08 | M02B disconnected-comparison semantic defect repaired + challenged | IMPLEMENTED / exact-head receipt pending |
| W2-09 | M02A W2 receipt-enabled exact head returns SUCCESS | PENDING — PR #6 head `05d8e34d...` |
| W2-10 | M02B W2 receipt-enabled exact head returns SUCCESS | PENDING — merged child head `5c1d86f9...` |
| W2-11 | ULTRA W2 exact head returns SUCCESS receipt | PENDING |
| W2-12 | ULTRA consumes all three receipts and `ULTRA-M02-FED-AND-001` PASSes | PENDING |

Current fixed-denominator state: **7 PASS + 1 IMPLEMENTED/PENDING + 4 PENDING**. Strict DoD credit is **7/12 = 58.3%**; implementation-ready credit is **8/12 = 66.7%**. Neither equals DoV.

## W2 DoV

**Binary victory condition:**

> The exact W2 heads for M02A, M02B and ULTRA each execute greater than zero mission steps, emit conforming `qps-fleet-receipt/v1` SUCCESS artifacts, ULTRA validates exact-source binding and all contract invariants, then records `PASS_FEDERATION_GATE` for `ULTRA-M02-FED-AND-001`.

DoV remains **WITHHELD** until W2-09 through W2-12 are all PASS.

## Burndown / conquest order

1. **BD-01 — Three receipt-enabled exact-head runs.** Retire runner/scheduler uncertainty on the final W2 heads and collect artifacts.
2. **BD-02 — Consume receipts in HOME.** Validate source SHA, repo/mission identity, >0 execution, outcome and authority boundaries; PASS the AND gate.
3. **BD-03 — M02A materials/data provenance.** Recover physical-data sources and calculation boundaries before replacing the hosted placeholder.
4. **BD-04 — M02A Pages productization.** Real dashboard -> deterministic static build -> permanent URL -> calculation traceability -> repeatable deployment receipt.
5. **BD-05 — M02B second kernel.** Add a second independently checkable mathematical atom; do not count synthetic BT fixtures as fleet-priority evidence.
6. **BD-06 — External consumption.** One non-origin consumer must use M02A/M02B capability before E5 credit.
7. **BD-07 — Measured fleet telemetry.** Populate at least three comparable pulse rows; only then run PCA.
8. **BD-08 — Observed BT interventions.** Record explicit winner/loser outcomes from real alternative actions; only then run fleet BT.
9. **BD-09 — M01 authority closure.** HEPAK/reference cross-check -> governed property adapter -> external QPS consumer -> DoV-2 -> CONTROL.
10. **BD-10 — Fresh-checkout post-merge repeat.** Re-run final merged child/default-branch states before CONTROL promotion.

## Integration rule

Merge order after evidence is green:

`child proof -> child merge -> bind final merged SHA -> HOME receipt correlation -> HOME merge -> fresh-checkout repeat -> CONTROL`

A merge is a lineage event, not proof by itself. Ocular/dashboard views remain projections; the receipt ledger and exact-SHA evidence remain authoritative.

## Analytics state

- PCA: `DEFER_INSUFFICIENT_COMPARABLE_MEASURED_OBSERVATIONS`
- Fleet BT: `DEFER_NO_EXPLICIT_PAIRWISE_OUTCOMES`
- Runtime unknown: retired for M02A/M02B W1; still pending for the exact W2 receipt heads.
