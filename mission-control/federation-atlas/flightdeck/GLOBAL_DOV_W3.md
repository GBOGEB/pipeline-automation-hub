# Global DoV W3 — Owner outcomes first

This is an additive, read-only control within the **already merged** W1/W2 federation flight deck. No second Pages publisher or duplicate CI policy is introduced.

## Purpose

Turn the federation from a collection of successful jobs into a repeatable way to make **QPS engineering deliverables usable**. Rank work by an actual owner-facing outcome, attributable evidence, readiness, dependency and verification gate, never just by a CI-green count or a model score.

## Rebuild

From repository root:

```sh
python -m unittest discover -s mission-control/federation-atlas/flightdeck -p 'test_global_dov_runner.py' -v
python mission-control/federation-atlas/flightdeck/global_dov_runner.py \
  --source mission-control/federation-atlas/flightdeck/global_dov_owner_control_v1.json \
  --out /tmp/global-dov
```

Outputs: `scorecard.json`, `owner_actions.csv`, `index.html`, `manifest.json`.

## Outcomes and source separation

| Control | Count | Boundary |
|---|---:|---|
| QPS product obligations (Wave AF historical) | 70/90 | No gain this wave |
| QPS product breadth | 36/45 | Not repository breadth |
| QPS verified product depth | 34/45 | Not independent federation replay |
| GOGREEN observed evidence (frozen G4) | 6/42 | 36 UNKNOWN, not failures |
| New four-hop native replay | UNKNOWN/4 | No synthetic promotion |
| Owner-accepted release | UNKNOWN/1 | Human/company decision |

The QPS queue's 20 remaining obligations and the four detailed live TODO cards' 19 remaining obligations disagree. The aggregate TODO candidate file also shows stale TODO-001/002 states compared with the completed detailed cards. Both are explicit source conflicts. Reconcile upstream; never silently change either original controlled snapshot.

## Next value-producing gates

**Parallel P0:** QPS TODO-011 Windows/Office release acceptance plus recensus of live six-repository source heads. **P1:** source-qualified bidder evidence for CC #75 and selected design #72/#87, followed by separate engineering computation and nonoverlapping Table-10 allocation. **P2:** complete missing GOGREEN evidence cells and authenticate the new gg_MATH/KEB/DOW/QPS route. **P3:** owner-controlled publication of a sanitized, exact-main page after ruleset, admission and independent content-hash readback.

These priorities are a deterministic **proposed owner sequence**, not Bradley–Terry or PCA ranking. Value is credited only for an accepted deliverable, a source-qualified engineering state change or a verified obligation closure.

## DoD and DoV

- IMPLEMENTED: code/data and tests committed, no authority transfer.
- LOCALLY_VERIFIED: source contract + negative tests + hashes + human rendering QA pass.
- NATIVE_VERIFIED: exact SHA terminal workflow, non-zero execution, eligible artifact receipts.
- PRODUCT_READY: QPS product owner verifies required sources, format QA, safety and technical gates.
- ENGINEERING_ACCEPTED: explicit authorized recipient acceptance in the proper controlled system.

Current W3 disposition: **IMPLEMENTED / NATIVE_PENDING**. `QPS=DEFER`, `MERGE=HOLD`, `native_new_federation=UNKNOWN`.
