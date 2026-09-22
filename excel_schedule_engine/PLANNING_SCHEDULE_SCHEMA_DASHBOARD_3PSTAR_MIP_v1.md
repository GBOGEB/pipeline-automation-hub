# 3P* + MIP — Planning Schedule Schema and Dashboard Binding

Date: 2026-09-22  
Repository: `GBOGEB/pipeline-automation-hub`  
Authority transfer: **false**

## 3PR — Refresh / Probe / Rank

### Refresh

Refreshed current `master` and global topology. The prior Excel parser, P1 hardening, MAIN-runner binding and post-merge control are already merged. Global topology explicitly names `PLANNING_SCHEDULE_SCHEMA_AND_DASHBOARD_BINDING` as the next permissible slice.

### Probe

The governed table layer detects schedule candidates, but no canonical row model, schedule-semantic validator, planning KPI package or human RYG dashboard existed.

### Rank

1. P0 — canonical schedule field mapping with source lineage.
2. P0 — deterministic validation of IDs, dates, duration and dependencies.
3. P0 — predecessor integrity including self/unknown/cycle detection.
4. P1 — owner/status/progress/float/milestone checks.
5. P1 — derived planning risk and RYG.
6. P1 — CSV/XLSX canonical schedule outputs and human dashboard.
7. P1 — SHA-256 schedule manifest + MAIN receipt binding.

## MIP — Modernize / Innovate / Perpetuate

### Modernize

Added `src/schedule_projection.py` and `schema/schedule_schema_v1.json`. Mapping is alias-based, source-scoped and non-mutating.

### Innovate

Separates **validation correctness** from **planning risk**:

- validation errors: duplicate IDs, impossible dates, invalid values, broken/cyclic predecessors, milestone semantic conflicts;
- planning risk: overdue, due-soon, blocked/on-hold and negative/zero float.

RYG combines both for human attention while keeping the finding kind explicit.

### Perpetuate

Produces hash-bound canonical CSV/XLSX, findings CSV, KPI JSON, Markdown/XLSX dashboard and schedule manifest. MAIN pipeline receipt advances to v3 and binds the schedule manifest when Excel is requested.

## SUT

```text
excel_schedule_engine/src/schedule_projection.py
excel_schedule_engine/src/excel_schedule_engine.py
scripts/run_processing.py
```

## Test System

```text
Python unittest
+ temporary governed table manifests
+ generated schedule CSVs
+ generated XLSX workbooks
+ real Excel-engine subprocess through MAIN runner
+ hosted GitHub Actions
```

## Victory contract

- all schedule candidates map into canonical fields;
- duplicate IDs and invalid dates are surfaced;
- predecessor unknown/self/cycle defects are surfaced;
- progress and milestone semantic defects are surfaced;
- CSV and XLSX canonical outputs both exist;
- Markdown and XLSX human dashboards both exist;
- schedule manifest hashes all outputs;
- MAIN receipt hashes schedule manifest;
- `authority_transfer=false`;
- zero test failures.

## Current gate

`CANDIDATE_AWAITING_HOSTED_PROOF`


## Hosted proof and merge closure

The first hosted recursive-build proof identified one bounded test-contract defect: an E2E assertion still expected pipeline receipt schema v2 after the intentional schedule-manifest binding advanced it to v3. The implementation path itself was green. The assertion was repaired and re-proven.

Final convergence used PR merge-ref proof because unrelated high-frequency master merges repeatedly overtook exact-base replay branches.

Final hosted proof on PR #408:

- Excel Schedule Engine run `35758132498`, job `106848988893`: **PASS**;
- recursive-build run `35758132496`, job `106848989090`: **PASS**;
- review threads: **0**.

PR #408 merged as `5296b400bcb543afee1a3613ff4e2cdedf2102df`.

Current classification: `ACTIVE_SCHEDULE_SCHEMA_DASHBOARD_BOUND`.

Next controlled slice: `REAL_WORKBOOK_SCHEDULE_PROOF_AND_BASELINE_DELTA` — prove the generic model against a real governed planning workbook and compare successive schedule baselines without transferring source authority.
