# GoGREEN G11 — Metric convergence without double-counting

G11 is the **integration consumer**, not another owner of BD, REX, Top21 or GitHub status. It consumes already source-validated G7 and G9 native frozen snapshots, and the separately verified G10 native graph-quality receipt. The bridge refuses conflicting run IDs/attempts/repository/SHA/timestamps rather than silently reconciling them into a false green.

## Exact identity arithmetic

- G7 selected successful run IDs: **24** from four repositories / five named workflow families.
- G9 complete-window native run IDs: **57** across gg_MATH and QPS, including **46 successes, 10 failures, one cancellation**.
- Shared native run IDs: **12**, six gg_MATH M02B smoke plus six QPS native Debug DAG successful observations, all matching repository, workflow, run ID, attempt, source SHA and timestamp.
- Union of evidence identities: **24 + 57 - 12 = 69**, with **58 unique observed successes, 10 failures, one cancellation**. This union is NOT a fleet success-rate denominator: it mixes the curated G7 success slice with two complete G9 branch/window slices.
- Remaining G7-only successful events: **12**, in CODEX and Mission Control. They are not silently promoted to complete temporal populations.

## Test and coverage convergence as a per-source ledger

| Source module | Native testflight | Passing test methods | Statement scope | Branch scope |
|---|---|---:|---:|---:|
| G7 `runner_telemetry.py` | 39024046315 | 53 | 226 / 226 | 38 / 38 |
| G9 `outcome_flight.py` | 39024952274 | 49 | 152 / 152 | 20 / 20 |
| G10 `graph_quality.py` | 39025248286 | 51 | 153 / 153 | 32 / 32 |

**Total separately native-measured source scope:** 531/531 statements and 90/90 branches across three different production modules/heads. **Do not** claim whole-repository coverage or a single integrated same-head testflight. G11 additionally instruments its own production module in native CI.

G10 graph visual QA evidence: 15 SIPOC/capability nodes, 24 directed edges (8 observed / 16 declared), actual source module blob pinned, 51/51 tests and 100% scoped line/branch. Local Chromium mobile/desktop interaction smoke is supplemental, not a native browser gate.

## SIPOC + authority

S G7 selected run evidence, S G9 complete-window outcomes, S G10 graph quality -> P exact ID join and source-scoped coverage -> O deduplicated JSON, SIPOC DAG and HTML, SHA256 manifest -> C independent authority **HOLD**.

No action runner is dispatched. No source has been merged to master by this observer. No root/cause closure, security waiver, branch ruleset weakening or external artifact custody is claimed. The prior G9 #601 merge landed on the G7 source feature branch, so [#603](https://github.com/GBOGEB/pipeline-automation-hub/pull/603) exists for independent mainline admission. G10 [#602](https://github.com/GBOGEB/pipeline-automation-hub/pull/602) also remains independently reviewed.

**Native proof:** `python -m unittest discover -s mission-control/gogreen/convergence_bridge/tests -p test_reconcile.py -v`; dedicated `.github/workflows/gogreen-g11-convergence.yml` has 47 positive/adverse tests, branch/statement coverage ratchet 85%/90% and immutable output checksum contracts. A future N+1 may ratchet to 100% without changing production source if the missing coverage reveals reachable branches.
