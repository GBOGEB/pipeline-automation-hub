# LSAF-P0 Receiving-Agent Drop-In

Continue the existing LSAF pilot in `GBOGEB/pipeline-automation-hub`.

## Ground truth

- Parent issue: #1230
- Existing PR: #1231
- Branch: `feat/lsaf-session-genome-pilot`
- Base: `master`
- Census producer dependency: #1211
- Read `lsaf/handover/HANDOVER.md`, `manifest.yaml`, and `glob.yaml` before editing.
- Preserve `authority_transfer=false`.
- Do not merge, close, rename chats, alter protections, or perform production worker dispatch as part of this slice.
- Do not invent live PIN order; retain `UNKNOWN` where not directly observed.

## Mission

Advance from schema/cohort evidence to deterministic reconstruction:

1. normalize session/fragments;
2. derive recurrence fingerprints;
3. compile dependency graph;
4. run Kahn classification;
5. emit deterministic DAG/SIPOC/handover/drop-in/BD-queue projections;
6. create immutable N->N+1 prediction receipts;
7. add adversarial regressions;
8. prove cold-start reconstruction from repo artifacts only.

## Required output classes

`SOURCE | DERIVED | PREDICTED | UNKNOWN | SUPERSEDED`

Never promote PREDICTED to SOURCE.

## Work discipline

Use disjoint, independently revertible commits by lane:

- A: normalization + DAG/Kahn
- B: deterministic projections
- C: prediction/calibration receipts
- D: cold-start/replay tests

Before each write, inspect current #1231 head. Bind evidence and test results to exact commit SHA. Update #1230 with receipts.

## Success boundary

Maximum allowed result in this PR: `ASSIMILABLE`.

Do not claim `ASSIMILATED` until a separately governed Hub-consumer change is admitted.
