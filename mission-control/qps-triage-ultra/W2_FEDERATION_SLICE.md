# QPS TRIAGE ULTRA — W2 Federation Slice

Status: `CONTROL / DoD 12/12 / DoV ACHIEVED + REPEATED`
Parent merge: `f41e96dfe5fde5312f3ebb5dc41fc391cb593c6d` (ULTRA PR #20)
Proof head: `505b6ef3fb48daf305d5be9877fbaf3ee9f78930`
Proof run: `34617530641`
W2 merge: `8d71e73bb59b5ebf36bd11dcb458b55ac365fd32`
Post-merge repeat: `34617570505`

## Objective — achieved

W2 turned independently useful nodes into one governed fleet path:

`M02A receipt + M02B receipt + ULTRA receipt -> contract validation -> ALL_REQUIRED AND gate -> W2 DoV`

Both the exact PR-head proof and the merged-master repeat returned:

- `PASS_FEDERATION_GATE`
- validated nodes: `M02A`, `M02B`, `ULTRA`
- validated outcomes: all `SUCCESS`
- `is_project_dov=true`

This is federation/control DoV only. It does **not** transfer engineering or compliance authority; both remain false in the receipt contract.

## Fixed W2 DoD denominator — frozen

| Gate | Requirement | Final state |
|---|---|---|
| W2-01 | ULTRA W0/W1 control plane merged | PASS — `f41e96df...` |
| W2-02 | M02A W0/W1 source-recovery + first runtime merged | PASS — PR #5 / `9a9131cf...` |
| W2-03 | M02B first kernel + semantic guard package merged | PASS — PR #1 / `543567eb...` |
| W2-04 | M02A exact-head runtime executes >0 | PASS — run `34615256406` |
| W2-05 | M02B exact-head runtime executes >0 | PASS — run `34615269215` |
| W2-06 | Common `qps-fleet-receipt/v1` contract exists | PASS |
| W2-07 | M02A byte-identical recovered numerics blob source-bound | PASS — `2d23e1d0...` |
| W2-08 | M02B disconnected-comparison defect repaired + challenged | PASS — repair run `34617236017` |
| W2-09 | M02A W2 receipt exact head SUCCESS | PASS — run `34616804184` |
| W2-10 | M02B W2 repaired receipt exact head SUCCESS | PASS — run `34617236017` |
| W2-11 | ULTRA W2 exact head SUCCESS receipt | PASS — run `34617530641` |
| W2-12 | HOME consumes all three receipts and AND gate PASSes | PASS — exact proof + merged repeat |

**Final strict DoD = 12/12 = 100%.**

## DoV evidence

Exact proof artifact digest:
`sha256:c32ff7353e4f687f8271585410dfc01f96275e1090623afbf7efb480beab9e12`

Post-merge repeat artifact digest:
`sha256:43172dd2773c015d6db6d76600193fc46f92539bac21c0762de318d7e9391d2c`

The post-merge repeat checked out exact merged master `8d71e73b...`, asserted that SHA, executed HOME validation, emitted a new HOME receipt, consumed the child inbox, and re-passed the explicit federation gate.

## REX retained

Two useful reds remain part of history rather than being erased:

1. M02B run `34616625888`: BT kernel passed but independent test import failed because repo root was absent from `sys.path`. A FAILURE receipt was still emitted/uploaded. The repair then passed on `43d23c38...` / run `34617236017`.
2. ULTRA pre-gate workflow-definition red: a YAML plain scalar containing JSON `: ` syntax failed before job creation. It was repaired using a block scalar; gate semantics were unchanged.

## Closed W2 burndown

- BD-01 three exact-head receipt runs — **CLOSED**
- BD-02 HOME receipt consumption + AND gate — **CLOSED**
- BD-10 post-merge HOME repeat — **CLOSED**

Remaining capability work is carried into W3. W2 is not extended after closure.

## Analytics boundary

- PCA remains `DEFER_INSUFFICIENT_COMPARABLE_MEASURED_OBSERVATIONS`.
- Fleet BT remains `DEFER_NO_EXPLICIT_PAIRWISE_OUTCOMES`.
- Synthetic fixtures remain implementation evidence only.

## Control rule

`proof -> merge -> exact merged repeat -> CONTROL`

A later regression reopens a new control event or wave; it does not rewrite W2 history.
