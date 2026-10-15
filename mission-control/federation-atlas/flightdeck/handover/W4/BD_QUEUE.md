# W4 BD queue — 14 disjoint owned workstreams

Proposed W4 IDs are **handover aliases**, not 14 new GitHub issues. Main authority: [MissionControl #529](https://github.com/GBOGEB/pipeline-automation-hub/issues/529) and [MissionControl #153](https://github.com/GBOGEB/pipeline-automation-hub/issues/153). Each item has a unique root family, exact proof condition and owner. The original 36 missing evidence cells are separately enumerated in [`state/leaf_register_original_g4.json`](state/leaf_register_original_g4.json), not counted as 36 causal errors.

| BD ID / evidence | Priority | Root / dimension | State | Owner | Deliverable |
|---|---|---|---|---|---|
| [W4-BD-001](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38739254875) | **P0** | ATLAS_FIRST_RED | READY_IN_BRANCH | MISSIONCONTROL_ATLAS | Own native Atlas source test |
| [W4-BD-002](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38739313365) | **P0** | SESSION_HOOK_FIRST_RED | READY_IN_BRANCH | MISSIONCONTROL_GOLDEN_THREAD | Repair session title contract mismatch after 19/19 unittest PASS |
| [W4-BD-003](https://github.com/GBOGEB/pipeline-automation-hub/pull/541) | **P0** | N2_OVERLAY_LOSS | READY_IN_BRANCH | MISSIONCONTROL_ATLAS | Restore N+2 stage and dashboard navigation excluded from merged older W3 head |
| [W4-BD-004](https://github.com/GBOGEB/pipeline-automation-hub/settings/rules) | **P0** | UNPROTECTED_MAIN | HOLD_OWNER | REPO_OWNER | Establish effective workable protected-master admission |
| [W4-BD-005](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38739428503) | **P0** | W3_NATIVE_ARTIFACT | BLOCKED_NATIVE | MISSIONCONTROL_ATLAS | Complete W3 native FlightDeck producer qualification |
| [W4-BD-006](https://github.com/GBOGEB/pipeline-automation-hub/pull/540) | **P0** | SESSION_RECURSION | BLOCKED_NATIVE | MISSIONCONTROL_GOLDEN_THREAD | Qualify canonical recursive intent hook |
| [W4-BD-007](https://github.com/GBOGEB/pipeline-automation-hub/issues/153) | **P0** | LOSSLESS_RETENTION | LOCAL_BUNDLE_READY | MISSIONCONTROL_ARCHIVIST | Preserve generated artifacts as content-addressed evidence rather than assuming PR includes binaries |
| [W4-BD-008](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38739467514) | **P1** | HOSTED_FLIGHTDECK | HOLD_RELEASE | PAGES_OWNER | Publish existing generated HTML from authorized publisher |
| [W4-BD-009](https://github.com/GBOGEB/pipeline-automation-hub/issues/529) | **P1** | FLEET_UNKNOWN_CELLS | READY_READ_ONLY | SIX_REPO_SCOUT_OWNERS | Scout 36 status-unobserved typed family cells; do not call them 36 root failures |
| [W4-BD-010](https://github.com/GBOGEB/pipeline-automation-hub/issues/529) | **P1** | HISTORICAL_ANCHOR_DRIFT | READY_READ_ONLY | FLEET_CENSUS | Refresh three stale main-anchor comparisons without rewriting G4 |
| [W4-BD-011](https://github.com/GBOGEB/ABACUS/pull/1993) | **P1** | FOUR_HOP_FEDERATION | HOLD_EXTERNAL | GG_MATH_CODEX_ABACUS_QPS | Authenticate H1 provider → H2 KEB → H3 DOW → H4 QPS owner chain |
| [W4-BD-012](https://github.com/GBOGEB/pipeline-automation-hub/pull/539) | **P1** | GLOBAL_DOV_CONSISTENCY | HOLD_OWNER | QPS_OWNER_DOV | Align product DoV snapshots to governed QPS TODO and document controls |
| [W4-BD-013](https://github.com/GBOGEB/ABACUS/issues/1660) | **P1** | CI_CREDIT_AMPLIFICATION | READY_READ_ONLY | CI_OWNER | Measure redundant PR feedback evaluations before opening multiple PR flights |
| [W4-BD-014](https://github.com/GBOGEB/pipeline-automation-hub/issues/153) | **P2** | REX_PERPETUATE | HOLD_CONTROL | REX_OWNER | Measure native root closure and reopenings across independent new-main waves |

## How to close a root

Use `IMPLEMENTED` only after source diff is committed. Use `VERIFIED` only for exact-head native tests and uploaded byte-verified receipt. Use `ROOT_RESOLVED` only after original first-red has ceased with attributable native evidence. Use `MERGE_ADMITTED` only after actual effective checks/review. Use `CONTROL` only after exact-main re-census and genuine recurrence window. No scalar counts or visualization can override an admission gate.

## Timing and branch policy

Avoid broad mutation fan-out and redundant reruns on the same source SHA. Two read-only workers in parallel is a *ceiling*, not a claim they were launched. Three repair files can be owned in disjoint slices; integrate one low-cost PR after preflight and then close only the results actually observed. Every critical item has `dod`, `evidence_url`, `blocked_by`, `source_path`, and no fabricated `owner_acceptance`.