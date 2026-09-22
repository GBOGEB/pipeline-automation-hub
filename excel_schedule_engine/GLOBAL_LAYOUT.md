# Excel Schedule Engine — Global Layout

## Repository placement

```text
GBOGEB/GBOGEB                       global topology / discovery
        |
        v
GBOGEB/pipeline-automation-hub      MAIN orchestration + parser/export engine
        |
        +-- excel_schedule_engine/
        |    +-- src/excel_schedule_engine.py
        |    +-- tests/test_excel_schedule_engine.py
        |    +-- project_manifest.json
        |    `-- README.md
        |
        +-- ActiveDocs/MASTER.xlsx         SOURCE
        +-- Outputs/excel/tables_csv/      derived CSV tables
        +-- Outputs/excel/tables_xlsx/     derived XLSX tables
        +-- Outputs/excel/table_manifest.json
        `-- Reports/schedule_index.{csv,md}

GBOGEB/ExcelAddinInstaller           legacy/external Excel add-in packaging surface
                                     not parser authority; no authority transfer
```

## KEB execution map

```text
[KEB: EXCEL_SCHEDULE_ENGINE]
       |
       +--> [D1 DISCOVER]
       |       |-- Excel Table found? ---- YES --> export ListObject range
       |       `-- NO --> non-empty sheet? YES --> export used range
       |
       +--> [D2 REPRESENT]
       |       |-- CSV  (machine / MAIN pipeline)
       |       `-- XLSX (human / planning review)
       |
       +--> [D3 CLASSIFY]
       |       `-- >=2 schedule header groups? --> schedule_candidate=YES
       |
       +--> [D4 PROVE]
       |       |-- both files exist
       |       |-- SHA-256 recorded
       |       |-- manifest row emitted
       |       `-- tests pass
       |
       `--> [D5 HANDOVER]
               |-- table_manifest.json
               |-- schedule_index.csv
               `-- schedule_index.md
```

## Human status legend

```text
GREEN  = parser/export/test condition proven
YELLOW = table discovered but schedule semantics need human review
RED    = export/test failure; no promotion
GRAY   = external/legacy surface; not in authority path
```


## Planning/schedule schema + dashboard extension

```text
Excel schedule candidate CSVs
        |
        v
[KEB: MAP_CANONICAL_SCHEDULE_SCHEMA]
        |
        +--> activity ID / name
        +--> start / finish / duration
        +--> predecessors
        +--> owner / status / progress
        +--> float / milestone
        |
        v
[KEB: VALIDATE_SCHEDULE_SEMANTICS]
        |
        +--> IDs / duplicates
        +--> dates / duration
        +--> predecessor resolution + cycle detection
        +--> owner / status / progress
        +--> float / milestone semantics
        |
        v
[KEB: BUILD_SCHEDULE_PROJECTION]
        |
        +--> canonical_schedule.csv
        +--> canonical_schedule.xlsx
        +--> validation_findings.csv
        |
        v
[KEB: CALCULATE_PLANNING_KPIS]
        |
        +--> validation pass rate
        +--> field completeness
        +--> overdue / float / milestone / progress KPIs
        |
        v
[KEB: BUILD_RYG_DASHBOARD]
        |
        +--> schedule_dashboard.md
        +--> schedule_dashboard.xlsx
        |
        v
[KEB: BIND_SCHEDULE_MANIFEST]
        `--> schedule_manifest.json + SHA-256 output bindings
```

RYG is a derived planning indicator. RED/YELLOW never rewrites source workbook facts or transfers authority.
