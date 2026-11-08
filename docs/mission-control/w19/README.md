# W19 governed integer issue burndown — source-bound reconstruction

**Status:** RECONSTRUCTED_VIEW / SOURCE_HOLD / NATIVE_QA_PENDING / MERGE_ADMISSION_HOLD.

This is **not** recovery of the lost original HTML. The previously committed burndown.html and README.md contained a 155-byte tool-retrieval failure, not the owner's original session artifact. PD-GPAH-001 tracks that incident.

## Single source of truth and reproducibility

- Governing input: observations.json, schema code-purple.w19.integer-burndown.v1.
- Source Git blob OID at reconstruction: 12691dcde4b3d483388f702dc4a7082e18ee9870.
- Observed counts: 153, 149, 144, 142, 141, 141 (integer ticket observations).
- Historical membership: 141 retained; 0 added/removed; 10 metadata updates.
- Source-backed sample: 20 identities (5 HOT, 5 COLD, 10 GATE).
- The 12 historical ticket closures are **not** accepted engineering root closures.
- authority_transfer=false, engineering_root_closure_credit=0,
  formal_root_closure_credit=0, merge_admission=HOLD.

The renderer uses Python stdlib; its output is a deterministic HTML/SVG
projection with a source Git blob OID and an embedded read-only copy of the
exact JSON. The JSON owns the metrics; the viewer does not recensus GitHub or
write to any repo. There are no external scripts or live APIs.

Rebuild and check from repository root:

    python docs/mission-control/w19/render.py --write
    python docs/mission-control/w19/render.py --check
    python -m pytest -q tests/test_w19_integer_burndown.py

The optional Plotly adapter is deliberately inactive unless an approved local
Plotly bundle is supplied and enabled. The no-dependency SVG chart renders
offline by default. Integer ticks, observed hover labels, CSV export, and
show/hide/reset of **illustrative, not-observed, not-a-prediction** scenarios
remain available without Plotly.

## Negative controls and acceptance

The source family includes tests for fractional counts, duplicate identity,
partial search pages, denominator drift, fabricated engineering credit,
renderer contamination, and mutation-induced source divergence. The view
tests were restored from 3 strict xfails to executed assertions; the existing
coverage-waves family guard has been updated to require 0 xfails and its
revised collection floor.

**Required before merge:**
- [ ] Exact-head Windows and Ubuntu coverage-waves parity pass.
- [ ] Source render --check passes; tool error absent.
- [ ] Playwright at 1440x1000, 1280x800, 390x844: zero errors and overflow,
      controls exercised, screenshots inspected, offline request check.
- [ ] Exact-head First-Pass Closure / GOGREEN and independent review approved.
- [ ] Negative canary executed, first/root-red reconciled, owner admission.
- [ ] Source changes trigger new source hashes and regenerated HTML.

**Evidence boundary:** structural checks may be verified by native CI;
visual/Playwright and independent acceptance remain DEFER until executed.
No engineering, compliance, or formal credit is transferred by this dashboard.
