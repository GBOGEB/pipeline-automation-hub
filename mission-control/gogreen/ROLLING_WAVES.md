# MissionControl G0 → G1 → G2 → G3 → G4 → … | evolutionary scorecard

**Canonical owner:** existing [GOGREEN G4 PR #531](https://github.com/GBOGEB/pipeline-automation-hub/pull/531). This source-bound view is a measurement presentation, **not an independent master ledger or admission gate**.

## What each wave must show

| Wave | Fleet observed | Fleet breadth | Native unit tests | Focused statements | Focused branches | New evidence |
|---|---:|---:|---:|---:|---:|---|
| G0 | 1/42 | 2.38% | UNKNOWN | UNKNOWN | UNKNOWN | Historical fixed-scope baseline reconstructed by G1 |
| G1 | 6/42 | 14.29% | 39 | 93/93 | 26/26 | +5 native status-only fleet cells |
| G2 | 6/42 | 14.29% | 55 | 93/93 | 26/26 | +16 regression tests; 2 bounded CODEX first-reds measured as recovered |
| G3 | 6/42 | 14.29% | 75 | 93/93 | 26/26 | +20 native regression tests, no breadth increase; root transition UNKNOWN |
| G4 | WAIT FOR EVIDENCE | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | **No forecast counted as actual** |

G0 and G1 were emitted together by [G4 run 38707835880](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38707835880), native job `116331559228`, completed 2026-10-15 08:45:13 UTC. G2 is supported by independent [G4 run 38709078403](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38709078403), job `116335723230`, completed 08:56:08 UTC. G3 is supported by [G4 run 38711768920](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38711768920), job `116344608477`, completed 09:17:11 UTC, 75/75 native tests PASS; the 20-test increase exercises the new source-bound timeline contract. **The same instrumented `pulse_rollup.py` source SHA-256 `7044c23c7d0e84ee1122dae85df683abb12677c4d4da60b621fce9cef8202555` and coverage.py 7.13.3** support a scope-matched zero coverage change G1→G2.

The two recovered first-red predicates are Mycelium generated-value parity and the published HTML stale-manifest check in CODEX #1044→#1045. Neither is a verified permanently closed root across the current fleet. **No independent GitHub artifact ZIP bytes were validated by the six-repository discovery census**. An Actions artifact upload digest is distinct from independent archive-byte verification.

## How to append G4, G5 and later

1. Capture the next **terminal** native run/job and immutable 40-hex Git SHA. Read the result, do not invent a successful run or duplicate a previously observed logical wave.
2. Record the UTC run completion, scope, full catalog identities, comparable code-coverage tool/source/denominator and test discovery population. If the target repo/family population changes, start a **new scope cohort** rather than comparing percentages across changed denominators.
3. Append exactly one record to `samples/wave_timeline.json`. Never replace G0/G1/G2 rows; old Git history and an optional `--previous` ledger comparison enforce the append-only contract.
4. Run the source-bound producer (native CI does this):
   ```sh
   python mission-control/gogreen/wave_timeline.py \
     --input mission-control/gogreen/samples/wave_timeline.json \
     --out "$RUNNER_TEMP/gogreen-pulses" \
     --source-sha "$(git rev-parse HEAD)"
   ```
5. Verify `wave_timeline.json`, `wave_timeline.sha256`, `wave_timeline.md` and `wave_timeline.html`. The HTML view is a compact monochrome responsive page with per-wave bars, delta metrics and native workflow links. GitHub Actions uploads these files **as evidence artifacts**, not to live Pages.
6. Require the [GOGREEN G4 native workflow](https://github.com/GBOGEB/pipeline-automation-hub/actions/workflows/gogreen-pulses.yml) to pass exact-head tests, source/UTC/denominator-negative controls and manifest/provenance assertions. Preserve pending external checks and merge admission separately.
7. Add verified root/coverage/fleet deltas to canonical [MissionControl #153](https://github.com/GBOGEB/pipeline-automation-hub/issues/153), [CODEX #1037](https://github.com/GBOGEB/CODEX/issues/1037), and [ABACUS #1929](https://github.com/GBOGEB/ABACUS/issues/1929); avoid redundant controller PRs.

### Comparability and DMAIC contract

A wave may **decrease** on a compatible metric: never suppress regressions. `UNKNOWN` remains null/UNKNOWN. Native test count `55` means 55 executed local suite checks, **not** 55 independently closed causal roots and **not** 55% fleet coverage. The fixed 42-cell fleet observation breadth and coverage of one Python module are distinct. Current G2 breadth remained 6/42, while regression depth rose 39→55.

- **3PR:** Refresh current source evidence → Probe negative controls and runtime evidence → Rank attributable roots.
- **MIP:** Modernize/Innovate tracked by exact-head proof; Perpetuate deferred until repeated independent main-branch control.
- **DMAIC:** Define/Measure/Analyze/Improve observations persist per wave; CONTROL requires stable, comparable independent trials.
- **REX / LDAB / LLDB:** first-red source fingerprints are tracked; debugger-session receipts, worker capacity, true reopening and RCA closure remain UNKNOWN unless recorded.
- **PCA / BT:** unavailable with the current tiny/nonindependent trial series; do not fit inferential stability or pairwise rank claims.
- **3PC:** Prepare/Prove/Commit remains contingent on branch protection, independent review and owner authority. QPS returns DEFER.

G4 is the next unmeasured wave. G3 improved native regression depth only; **G4 has no credited actual gain yet**.
