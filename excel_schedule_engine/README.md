# Excel Schedule Engine

Governed Excel parser/export lane for the MAIN pipeline.

## Purpose

Treat an `.xlsx`/`.xlsm` workbook as SOURCE input and project every logical table into two separate renditions:

- CSV: machine/LLM/automation friendly
- XLSX: human/stakeholder friendly

The engine also creates a machine table manifest and human schedule indexes. Exports are derived views; they do not acquire source authority.

## What is exported

1. Every defined Excel Table (`ListObject`) in every worksheet.
2. If a worksheet has no defined Excel Tables, its non-empty used range is exported as one logical table by default.
3. Empty worksheets are skipped.

Each logical table becomes:

```text
Outputs/excel/tables_csv/<sheet>__<table>.csv
Outputs/excel/tables_xlsx/<sheet>__<table>.xlsx
```

Global indexes:

```text
Outputs/excel/table_manifest.json
Reports/schedule_index.csv
Reports/schedule_index.md
```

## Schedule classification

The engine never rewrites table meaning. It only marks a table as a `schedule_candidate` when at least two recognized planning/scheduling header groups are present, such as activity/task, start, finish, duration, owner, status, dependency, progress or float.

That classification is discovery metadata, not project truth.

## MAIN pipeline layout

```text
ActiveDocs/MASTER.xlsx
        |
        v
[EXCEL_SCHEDULE_ENGINE]
        |
        +--> Outputs/excel/tables_csv/*.csv
        +--> Outputs/excel/tables_xlsx/*.xlsx
        +--> Outputs/excel/table_manifest.json
        `--> Reports/schedule_index.{csv,md}
                    |
                    v
             MAIN pipeline / KEB consumers
```

## Run

```bash
python excel_schedule_engine/src/excel_schedule_engine.py ActiveDocs/MASTER.xlsx --output-root .
```

To export only true Excel Tables and skip sheet-used-range fallback:

```bash
python excel_schedule_engine/src/excel_schedule_engine.py ActiveDocs/MASTER.xlsx --output-root . --tables-only
```

Cell read mode defaults to `formula` to preserve formula expressions. Use cached values only when the workbook has been recalculated by Excel or another trusted calculation runtime:

```bash
python excel_schedule_engine/src/excel_schedule_engine.py ActiveDocs/MASTER.xlsx --output-root . --cell-mode cached
```

## Test

```bash
python -m unittest discover -s excel_schedule_engine/tests -v
```

## SUT / Test System

- SUT: `src/excel_schedule_engine.py`
- Test System: Python `unittest` + generated temporary workbooks via `openpyxl`
- Victory: every logical table gets both CSV and XLSX outputs, hashes are recorded, schedule candidates are indexed, empty sheets are skipped, and `authority_transfer=false` remains explicit.


## Canonical planning/schedule projection

Schedule-candidate CSV renditions are now mapped into a single canonical planning projection without writing back to the workbook.

Canonical fields include activity identity/name, start/finish, duration, predecessors, owner, canonical status, progress, total float and milestone semantics. The machine contract is published in:

```text
excel_schedule_engine/schema/schedule_schema_v1.json
```

Validation covers:

- missing/duplicate IDs;
- start > finish and unparseable dates;
- invalid/negative duration;
- unresolved/self/cyclic predecessors;
- missing owner/status and unknown statuses;
- progress outside 0..100;
- invalid total float;
- non-zero milestone span/duration.

Planning risk is separate from data validity. RYG is derived as:

```text
RED    = validation error OR overdue OR negative float OR BLOCKED
YELLOW = validation warning OR due-soon OR zero float OR ON_HOLD
GREEN  = no RED/YELLOW condition
```

Generated outputs:

```text
Outputs/excel/schedule/canonical_schedule.csv
Outputs/excel/schedule/canonical_schedule.xlsx
Outputs/excel/schedule/validation_findings.csv
Outputs/excel/schedule/schedule_kpis.json
Outputs/excel/schedule/schedule_manifest.json
Reports/schedule_dashboard.md
Reports/schedule_dashboard.xlsx
```

For deterministic comparisons, use `--schedule-as-of YYYY-MM-DD`. The default due-soon horizon is 14 calendar days and can be changed with `--schedule-due-soon-days`.

The schedule manifest SHA-binds every canonical/dashboard output and retains `authority_transfer=false`.
