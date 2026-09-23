# Consolidated DEVOPS Drive — RUN-DELTA + Real Workbook Schedule

**Date:** 2026-09-23  
**Repository:** `GBOGEB/pipeline-automation-hub`  
**Canonical task:** issue #410  
**Execution mode:** sequential `3P* -> MIP`  
**Authority transfer:** false  
**Formal engineering/compliance credit delta:** 0

## 1. Purpose

This is the single chat/session handover for the two active DevOps/control lanes. Do not split them into separate session narratives unless a real repository or authority boundary requires a child issue.

```text
CONSOLIDATED DEVOPS DRIVE #410
        |
        +--> A. RUN-DELTA BASELINE v0.3       [CONTROLLED / MERGED]
        |
        +--> B. REAL WORKBOOK SCHEDULE PROOF  [OPEN / NEXT]
```

## 2. Lane A — RUN-DELTA BASELINE v0.3

### Controlled state

Producer:
- `GBOGEB/GBOGEB#16` functional merge:
  `47517d993d3148c261af85dd8080ee7c30997036`
- final exact-head proof:
  run `35842427940`, job `107120424797`, SUCCESS, 15 executed steps
- `GBOGEB/GBOGEB#17` post-merge control merge:
  `99bf0f61018ff6798c661d44256077c0b14297a3`

Controlled baseline:
- ID: `RUN_B_V03`
- physical files: 21
- unique SHA objects: 14
- duplicate copies: 7
- physical-set SHA:
  `7eade723ee5b146476a0a8d6d20a08ae19fa0448d178afd41f1fc85f4d66e691`
- semantic-set SHA:
  `9f32b634dc68b9cc95cf5aff426f95bf179fedf9458a9cd8f9213245e705a0e2`

Measured RUN_A -> RUN_B change:
- physical files: +11
- unique semantic objects: +6
- duplicate copies: +5
- added SHA objects: 6
- removed SHA objects: 0
- CHAT_ONLY graph delta: 0
- ALL_UNIQUE graph-node delta: +88
- ALL_UNIQUE graph-edge delta: +85
- BLOCK delta: 0
- KEB delta: 0
- STEP_in delta: 0
- STEP_out delta: 0
- HUMAN delta: 0
- VISUAL delta: +2, entirely ARTEFACT_ONLY
- quantitative delta: 0

Views:
`CHAT_ONLY | ARTEFACT_ONLY | CODE_ONLY | ALL_UNIQUE | PHYSICAL_RAW`

### Lane A next predicate

Do not reopen v0.3 implementation. Compare the next exact source set as `RUN_C` against `RUN_B_V03`.

Escalate only a real attributable delta:
- removed SHA object;
- source-class conflict;
- BLOCK/KEB/STEP anchor change;
- CHAT_ONLY graph change;
- parser-mode transition;
- privacy regression;
- material HUMAN/VISUAL/quantitative drift.

## 3. Lane B — REAL_WORKBOOK_SCHEDULE_PROOF_AND_BASELINE_DELTA

### Proven predecessor

`PLANNING_SCHEDULE_SCHEMA_AND_DASHBOARD_BINDING` is closed.

Evidence:
- pipeline-automation-hub#408 implementation:
  `5296b400bcb543afee1a3613ff4e2cdedf2102df`
- final Excel proof:
  run `35758132498`, job `106848988893`, PASS
- final recursive/MAIN proof:
  run `35758132496`, job `106848989090`, PASS
- pipeline-automation-hub#409 post-merge control:
  `288e44f21724efe1bd46a699af6fa47d115fbee5`
- post-merge Excel re-proof:
  run `35758313505`, job `106849601173`, PASS
- post-merge recursive re-proof:
  run `35758313675`, job `106849601163`, PASS
- GBOGEB/GBOGEB#15 global promotion:
  `46a8b2bebd5daa0f53a5b4a6f2e983582effcb4d`
- project manifest:
  `v0.3.1 / ACTIVE_SCHEDULE_SCHEMA_DASHBOARD_BOUND`
- global topology:
  `ACTIVE_SCHEDULE_SCHEMA_DASHBOARD_BOUND`

### Proven schedule flow

```text
ActiveDocs/MASTER.xlsx
        |
        v
EXCEL_SCHEDULE_ENGINE
        |
        +--> all logical tables -> CSV
        +--> all logical tables -> XLSX
        +--> table_manifest.json
        |
        v
MAP_CANONICAL_SCHEDULE_SCHEMA
        |
        +--> activity_id
        +--> activity_name
        +--> start_date
        +--> finish_date
        +--> duration_days
        +--> predecessor_ids
        +--> owner
        +--> status
        +--> progress_pct
        +--> total_float_days
        +--> milestone
        |
        v
VALIDATE_SCHEDULE_SEMANTICS
        |
        +--> missing / duplicate IDs
        +--> Start > Finish
        +--> duration validity
        +--> unknown predecessors
        +--> self predecessors
        +--> predecessor cycles
        +--> owner / status
        +--> progress 0..100
        +--> float
        +--> milestone semantics
        |
        v
CANONICAL SCHEDULE PROJECTION
        +--> canonical_schedule.csv
        +--> canonical_schedule.xlsx
        |
        v
PLANNING KPI / RISK MODEL
        |
        +--> validation pass %
        +--> field completeness %
        +--> overdue
        +--> progress
        +--> milestones
        +--> negative / zero float
        +--> canonical status counts
        |
        v
RYG HUMAN DASHBOARD
        +--> schedule_dashboard.md
        +--> schedule_dashboard.xlsx
        |
        v
schedule_manifest.json
        |
        +--> SHA-256 binds projection + dashboard
        |
        v
pipeline_run_receipt.json v3
```

RYG contract:
- RED: validation error, overdue active work, negative float, blocked status;
- YELLOW: warning, due-soon work, zero float, on-hold status;
- GREEN: none of the above.

RYG is decision support only. It cannot alter source truth.

### Boundary

The engine, schema mapping, validation semantics, outputs, dashboard generation, lineage and orchestration are proven.

**The actual governed project planning workbook has not yet been proven.**

### Lane B open tasks

1. identify and freeze the actual governed schedule workbook;
2. bind exact source hash and source locator;
3. ingest without mutating source authority;
4. classify real headers and mapping coverage;
5. quantify unmapped / ambiguous fields;
6. run semantic validation on real rows;
7. inspect real RED / YELLOW / GREEN findings;
8. establish governed Baseline T0;
9. bind T0 schedule manifest + receipt;
10. ingest later exact Baseline T1;
11. calculate additions / deletions / date slips;
12. calculate progress / float delta;
13. calculate milestone movement;
14. generate human baseline-change dashboard;
15. bind T0/T1 hashes, outputs and receipts;
16. distinguish source-data defects from mapper/schema defects before repair.

## 4. Unified execution contract

```text
SOURCE AUTHORITY
      |
      +--> exact source identity / SHA
      |
      +--> controlled parser / mapper / engine
      |
      +--> semantic validation
      |
      +--> derived views / dashboards
      |
      +--> manifest + receipt
      |
      +--> RUN / BASELINE DELTA
      |
      +--> HUMAN disposition
```

Common guards:
- source/master remains authority;
- generated view != SSOT;
- RYG != source truth;
- hash change != semantic change;
- physical duplicate != new semantic evidence;
- zero-step != application defect;
- no raw project-chat publication by default;
- no engineering/compliance/acceptance credit from DevOps proof;
- no source-class repair unless a real regression is observed.

## 5. 3P* / MIP consolidated state

### RUN-DELTA lane
- Refresh: PASS
- Probe: PASS
- Rank: PASS
- Prepare: PASS
- Prove: PASS
- Commit: PASS_MERGED
- Modernize: PASS
- Innovate: PASS
- Perpetuate: PASS_MERGED

### Schedule lane
- predecessor implementation: PASS_MERGED
- hosted proof: PASS
- post-merge proof: PASS
- global promotion: PASS
- real-workbook proof: OPEN
- baseline T0: OPEN
- baseline T1 delta: OPEN

## 6. Exact restart order

1. refresh issue #410;
2. refresh `GBOGEB/GBOGEB` main;
3. read:
   - `governance/PROJECT_RUN_DELTA_CURRENT_v0.3.yaml`
   - `governance/PROJECT_RUN_DELTA_POSTMERGE_CLOSURE_20260923_v0.3.yaml`
4. refresh `GBOGEB/pipeline-automation-hub` master;
5. read schedule predecessor control from #408/#409 and global #15;
6. execute the **first unresolved Lane B task**;
7. append exact SHA/run/job/receipt to issue #410 before moving to the next task.

## 7. Definition of victory

Close issue #410 only when both are true:

1. RUN-DELTA v0.3 remains controlled and `RUN_B_V03` is the governed comparison baseline; and
2. the actual schedule workbook has:
   - governed T0 receipt;
   - at least one real T1 receipt;
   - baseline-delta output;
   - human change dashboard;
   - exact source/output hashes.

No authority transfer. No formal engineering/compliance credit unless separately granted by the relevant authority.
