# Temporal effect and PCA interpretation v1

## Purpose

This note separates three concepts that must not be conflated in MissionControl temporal allocation analysis:

1. **Bradley-Terry allocation direction** used by the temporal policy engine.
2. **Allocation effect magnitude / attenuation** across genuine scheduled windows.
3. **PCA component orientation and structural stability** across separate PCA fits.

No threshold in `TEMPORAL_POLICY_CONFIG_v1.json` is changed by this diagnostic layer. It cannot create a CONTROL window, add governed clock time, promote competency, or transfer authority.

## Signed allocation effect

The temporal policy engine pools `ALLOC_SINGLE_CELL.normalized_strength` as `p_single` and reports magnitude-only winner strength:

`pooled_winner_strength = max(p_single, 1 - p_single)`

The companion signed effect is:

`D = 2 * p_single - 1`

Interpretation:

- `D > 0`: aggregate preference for `ALLOC_SINGLE_CELL`.
- `D < 0`: aggregate preference for `ALLOC_PAIRED_CELL`.
- `D = 0`: parity.
- `abs(D)`: preference magnitude.
- `pooled_winner_strength = 0.5 + abs(D)/2`.

A decrease in `pooled_winner_strength` with unchanged sign is therefore **attenuation toward parity**, not a direction reversal. A direction reversal requires the signed aggregate effect to cross zero.

For `long_compute_contended`, the diagnostic wording is deliberately conditional:

> The aggregate direction has not reversed when the signed pooled effect remains negative. A falling magnitude means the paired-cell advantage is attenuating toward parity. The policy receipt alone cannot distinguish sampling/runtime variation from genuine temporal effect decay or deblocking-driven convergence.

Deblocking-driven convergence requires joint covariate evidence such as queue/admission pressure, scarcity/contention, runner class, lane, source SHA, and time. It is not inferred from winner-strength decay alone.

## PCA temporal comparison contract

Raw PCA loading signs are orientation-indeterminate: multiplying an eigenvector by `-1` yields the same PCA solution. Therefore raw loading-sign differences between fits are not evidence of a physical or policy reversal.

Temporal PCA comparisons must perform, in order:

1. **Component matching** by maximum absolute Tucker congruence over common features.
2. **Sign alignment** after matching so orientation-only flips are normalized away.
3. **Tucker congruence check** to quantify loading-pattern similarity.
4. **Eigengap check** to flag weakly separated components whose individual identity is unstable or exchangeable.
5. Only then compare aligned loading magnitudes or relative feature signs.

The implementation uses diagnostic defaults of absolute Tucker congruence `>= 0.90` and relative eigengap `>= 0.05`. These are diagnostic-only defaults and are not CONTROL_POLICY thresholds.

A high-congruence negative raw match is classified as `ORIENTATION_ONLY_SIGN_FLIP`. A high-congruence reordered match is `COMPONENT_REORDERING_WITH_CONGRUENT_STRUCTURE`. A small eigengap marks component identity `AMBIGUOUS` even when the loading vectors are otherwise congruent.

## Governance

- Genuine scheduled temporal separation remains the only source for the `>=86400` second CONTROL clock.
- Synthetic, no-op, pull-request, push, dispatch, PCA, or diagnostic runs do not add CONTROL clock time.
- `competency_promotions = 0` remains invariant.
- `authority_transfer = false` remains invariant.
- PCA polarity does not enter the Bradley-Terry CONTROL gate.
