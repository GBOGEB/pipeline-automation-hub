# QPS TRIAGE N5 - Evidence-gated adaptive scaling

Second bounded iteration after the N4 evidence-penetration metrics. This is a
**decision aid only**: no repository dispatch, approvals, ruleset modifications
or merge authority.

## Scale states

| Preconditions | Recommendation | Actual execution |
|---|---|---|
| Private QPS read or dispatch approval unverified | HOLD | 0 |
| CODEX / QPS source receiver admission unknown | HOLD | 0 |
| Both receivers admitted and authorized, 4 native receipts missing | GO_PILOT_2x4_ONLY | Owner controlled |
| Four terminal and ZIP proofs, canonical #530 unverified | HOLD_CANONICAL_ZIP | 0 |
| 4/4 accepted, ABACUS #2126 still open | HOLD_ABACUS_ADMISSION | 0 |
| P0/P1, required checks or security disposition incomplete | HOLD | 0 |
| Two scope-matched full pilot pulses, ABACUS/owner approvals satisfied | PROPOSE_3x6_OWNER_REVIEW | 0; owner review required |

## SIPOC

| Supplier | Input | Process | Output | Consumer |
|---|---|---|---|---|
| N4 metric engine | qps-metric-pulse/v1, SHA/route identity | Validate population | Bound evidence | N5 |
| Source owners | Merged receivers, required checks | Admission confirmation | Owner status | N5 |
| Private QPS operator | Authorized source-read/dispatch | Authorization | Scoped permission | N5 |
| Canonical #530 verifier | Accepted ZIP receipt | Provenance | Formal acceptance | N5 |
| Mission Control | Matched pulse observations | Stability check | Review recommendation | Maintainer |

## Minimal offline use

    from metric_atlas.adaptive_scale import decide
    # Import genuine N4 pulse JSON and explicit owner confirmation.
    decision = decide(pulse, owner_flags, previous=prior_pulse)
    print(decision)

N5 is independently importable; a subsequent integrated acceptance test
should check the N4 producer and N5 consumer together.

## Acceptance arithmetic

Evidence E_N = verified_ZIP_routes / planned_routes.
This is a route-evidence fraction, **not code coverage**.
Numerator and denominator are preserved and must not be silently conflated.

A single full-pilot pulse does not establish repeatability. Same-cohort
success twice is required before proposing 3x6, alongside ABACUS admission,
canonical ZIP validation and owner security controls.

N20, PCA, Bradley-Terry, Six Sigma capability, worker-hour yield and
statement/branch coverage uplift stay UNKNOWN without authenticated inputs.

## Recorded baseline (17 October 2026)

- N1-N2 controller suite: 39 to 48 native tests PASS (+9 / +23.08%).
- N4 contains 10 newly authored tests, N5 11. Local standalone suite:
  64/64 PASS including 43 earlier tests. Native PR-head CI still required.
- Independently verified CODEX/QPS receiver routes: 0 of four planned.
- Private QPS source read from hub: HOLD (HTTP 404 observed).
- Canonical #530 receiver ZIP acceptance: UNKNOWN.
- ABACUS #2126: OPEN / HOLD; P0-P1, A10, Python and CI requirements unchanged.
- Merge admission and QPS engineering acceptance: HOLD.

Never expand because analytics test counts rise. First obtain exact-head
terminal native receiver/ZIP receipts on both admitted source repositories;
obtain authorization and pass the existing branch rules before broader fanout.
