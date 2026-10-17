# CODE PURPLE N7 — bounded 32 → 40 → 48 → 64 census continuation

**Status:** Local source-bound census replay verified; **draft review only**, no new native tests, merges, waivers, authenticated first-red roots or debugger sessions. Source: `GBOGEB/ABACUS` head `94222bd2b9ba75563b41e6b7e6b058ea06ca6c0d`, historical B0 artifact `6326d5ab…`. This document is an additive metric projection for draft [Metric Atlas #646](https://github.com/GBOGEB/pipeline-automation-hub/pull/646), **not** a replacement of `metric_atlas.census` or the global source SSOT.

## Three measured pulses

| Pulse | New / cumulative distinct files | New eligible arcs | New already-missed arcs | Known missed/file | Predeclared gate |
|---|---:|---:|---:|---:|---|
| A4 | 8 / 40 | 610 | 246 | 30.75 | PASS read-only density ≥16 |
| A5 | 8 / 48 | 236 | 217 | 27.125 | PASS read-only density ≥16 |
| A6 | 16 / 64 | 586 | 406 | 25.375 | PASS read-only density ≥16 |

**Cumulative:** 64/299 known measured modules, 3,132/8,328 previously-known eligible arcs, 792 already-covered arcs, 2,340 known missed arcs. Baseline N6 32-file receipt and all three new partial receipts are linked by the original parent-terminal SHA and the N7 continuation manifest digest. There are no overlapping source files.

## Boundaries and evidence

- Frozen N6 parent manifest SHA: `f8ed2072ffb68473796bab7ce5148c2973b45f404eceed4d2848f0e634d38b73`.
- Frozen N6 final partial SHA: `47a68c8b6e08d5a5c08d2cdc76e341e056515c5e395adddd24791b0730a0f685`.
- N7 manifest SHA: `9ee96a1c7da7dc5eb7f5bf59edff9253b0869fb2aac4d840326ed44c3d86eb13`.
- N7 final partial SHA: `f3777344d2a4198e995835dab2129ce0c39ee2f973cbe725eaa0368fade7383f`.
- Local full continuation: 29/29 Python regression tests passed and 3/3 Playwright viewports passed, with no browser errors or horizontal overflow. **The standalone N7 continuation source and 29-test suite are packaged in a separate local lossless handover archive and are not part of this PR commit.** The old N6 owner-repo code has native CI; this N7 evidence JSON has not received its own source-execution proof.
- Census only: 2 local readers; zero source-writing workers launched; zero new CI jobs dispatched by this local census. New covered-branch gains, confirmed failure roots, hardware runtime, LLDB/DAP sessions and approved reviews remain **UNKNOWN**.
- No silent numerator promotion: the source head is unchanged and the full known branch denominator remains 8,328. Enlarging the sample does not raise the source denominator or execute tests.

## Next bounded decision

Maintain source census scale separately from repair workers. Candidate A7/A8/A9 sizes are 64 → 80 → 96 → 128, but expected diminishing opportunity density makes the final 128-file step **conditional**. Require a new exact-head native artifact, provenance completeness, stable reviewer/owner capacity, and useful cause-specific test opportunity before considering any source-writing fan-out. Reject new coverage credit from a subset replay or changed denominators. Retain ABACUS BD/LDAB as an observation join and LLDB as a separately authenticated diagnostic tool. Security, A10 and independent review gates remain mandatory.

Machine receipt: `tools/metric-atlas/docs/ADAPTIVE_CENSUS_N7_READONLY_ROLLUP.json`.
