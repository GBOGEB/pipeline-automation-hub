# MissionControl Temporal Test Schema v1

Status: candidate governed test schema. This document extends the existing Temporal Allocation Policy without changing its CONTROL entry thresholds.

## Core invariant

**Fabricate scenarios freely; never fabricate governed time.**

Synthetic fixtures are first-class DMAIC/V&V evidence for the mechanism, but they are never CONTROL clock evidence. Genuine scheduled observations remain the only evidence lane allowed to advance the >=86400-second governed temporal clock. `competency_promotions=0` and `authority_transfer=false` remain invariant.

## Evidence lanes

| Lane | Signal | Purpose | CONTROL clock |
|---|---|---|---|
| V&V | `VNV_SIGNAL` / `SYNTHETIC_TEST` | DMAIC, regression, boundaries, fault injection | Never |
| Runtime learning | `OBSERVED_SIGNAL` | operational learning | No |
| Governed | `CONTROL_SIGNAL` | CONTROL entry and continued temporal evidence | Yes, genuine scheduled only |
| Challenge | `CHALLENGE_SIGNAL` | independent recomputation / federation V&V | No additional clock |
| Surveillance | `SURVEILLANCE_SIGNAL` | post-CONTROL persistence and regression detection | Adds genuine observed time; does not redefine entry gate |

The lanes combine conjunctively at DOV. They are not pooled into one synthetic+real elapsed-time statistic.

## Synthetic V&V programme

A reference six-fixture sequence at 15000-second spacing is deliberately retained. Six observations create five intervals, therefore the fixture spans 75000 seconds rather than 90000 seconds. This is useful because it exercises multi-window aggregation while remaining visibly insufficient for the genuine 86400-second CONTROL clock.

The synthetic suite should cover positive gate logic and negative/boundary cases: 5/6 windows, 86399/86400 seconds, 0.699/0.700 pooled strength, direction reversal, indeterminate direction, duplicate run IDs, rerun attempts, insufficient SHA diversity, missing runner class, missing lane, REX veto, and learning-traffic crowding. Synthetic fixtures may exercise the same evaluator code path but must never be emitted as governed CONTROL receipts.

## Temporal horizons

### H0 - mechanism V&V

Continuous on code/config change. Goal: prove evaluator correctness, fail-closed behavior, provenance handling and boundary semantics. No elapsed-time claim.

### H1 - CONTROL entry: >=24 h

Existing governed gate remains unchanged: >=6 independent genuine scheduled windows, >=3 source SHAs, >=86400 seconds first-to-last, >=5 directional windows, >=0.80 direction consistency, >=0.70 pooled winner strength, latest-two agreement, >=3 hosted runner classes, baseline+held lanes, and no governing veto.

This is an entry gate, not a claim of long-term stationarity.

### H2 - medium surveillance: 72 h

Goal: establish robustness after entry without moving the entry threshold. Report direction-flip count, indeterminate fraction, rolling consistency/strength, leave-one-window-out (jackknife) minimum strength, jackknife direction preservation, early-vs-late agreement, SHA/runner/lane concentration, REX veto count and first-red count.

Candidate interpretation, initially observational rather than promotional:
- `ROBUST_72H`: no first-red/veto, no unexplained regime reversal, and dominant direction survives leave-one-window-out analysis.
- `FRAGILE_72H`: CONTROL remains valid but one observation dominates or early/late behavior materially disagrees.
- `REGRESSION_72H`: a genuine scheduled observation violates the established CONTROL claim or activates a veto.

### H3 - medium surveillance: 7 d

Goal: distinguish persistent policy behavior from a 24-72 h local regime. Report daily consistency and pooled strength, reversal count, CONTROL-state transitions, time since first-red, SHA diversity, runner/lane coverage and independent-recomputation agreement.

Candidate DOV is `PERSISTENT_7D`, not a new authority level. It describes evidence durability only.

### H4 - long surveillance: 30 d rolling

Goal: demonstrate sustained CONTROL and expose drift. Report weekly consistency/strength, CONTROL survival fraction, regression/veto counts, policy-drift events, federation recomputation disagreements and provenance failures.

Long-term evidence is rolling. A later first-red may weaken or revoke a previously established CONTROL state; CONTROL is not a permanent ratchet.

## Suggested medium-term metrics

`direction_flip_count` counts genuine directional reversals. `indeterminate_window_fraction` exposes ambiguity hidden by pooled statistics. `rolling_direction_consistency` and `rolling_pooled_winner_strength` show drift. `jackknife_min_pooled_winner_strength` and `jackknife_direction_preservation_fraction` quantify dependence on any single observation. `early_vs_late_direction_agreement` detects regime changes. `source_sha_concentration`, `runner_class_concentration`, and `lane_concentration` distinguish nominal diversity from evidence dominated by one source. `independent_recomputation_agreement_fraction` measures federation reproducibility without transferring authority.

For `short_compute`, emphasize instability characterization: flip count, indeterminate fraction, strength dispersion and correlation with runner/lane/SHA/contention. A stable negative conclusion (`NO_POLICY`) is legitimate evidence.

For `long_compute_contended`, emphasize persistence and robustness: jackknife preservation, early/late agreement, rolling pooled strength and absence of veto/regression.

## DMAIC binding

DEFINE freezes the genuine CONTROL entry contract. MEASURE collects both synthetic V&V and genuine scheduled observations in separate lanes. ANALYZE compares expected fixture behavior with runtime behavior and treats disagreement as first-red evidence. IMPROVE repairs mechanism/receipt/retention behavior, never the threshold to obtain a pass. CONTROL is entered only from genuine scheduled evidence and then observed through the 72 h, 7 d and 30 d surveillance horizons.

## Federation and propagation

Local surfaces prove locally and retain raw evidence. Receipts federate and roll up. Independent consumers may recompute the conclusion as `CHALLENGE_SIGNAL`. Roll-out distributes the governed mechanism, not an existing conclusion. Fan-out triggers independent child evaluations. Propagation carries only accepted facts with provenance and stops at veto or incompatible contract.
