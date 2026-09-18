# 3P* + MIP Execution Receipt — Excel Schedule Engine

Date: 2026-09-18

## 3PR — Refresh / Probe / Rank

### Refresh

- `GBOGEB/pipeline-automation-hub` refreshed before write.
- `GBOGEB/GBOGEB` refreshed before global-layout write.
- Existing Golden Thread rule retained: one logical fact, one authority, many deterministic renditions.
- `GBOGEB/ExcelAddinInstaller` classified as an external/legacy Excel add-in packaging surface, not the parser authority.

### Probe

Observed gap: MAIN pipeline has Excel-producing RTM utilities but no bounded generic engine that exports every logical workbook table separately to both CSV and XLSX while emitting a schedule/data index and manifest.

### Rank

1. P0 — deterministic all-table discovery and dual CSV/XLSX export.
2. P0 — machine manifest with SHA-256 and explicit no-authority-transfer semantics.
3. P1 — schedule-candidate discovery for planning/scheduling views.
4. P1 — human Markdown/CSV index and global layout discoverability.
5. P1 — CI/unit proof.

## MIP — Modernize / Innovate / Perpetuate

### Modernize

Added a standalone `openpyxl` engine with a narrow CLI, no dependence on the older document processor and no claim that exported views become SSOT.

### Innovate

Added dual rendition per logical table plus deterministic manifest hashes and conservative schedule-header signal classification.

### Perpetuate

Added unit tests, project manifest, root discoverability, global topology hook, and CI contract. The design is restartable from repo state rather than chat state.

## 3PC — Prepare / Prove / Commit

### Prepare

SUT, test system, directory contract, authority boundary and success criteria are explicit in the project manifest and README.

### Prove

Local pre-commit proof:

```text
python -m unittest discover -s excel_schedule_engine/tests -v
3 tests -> PASS
```

Proof covers defined Excel Table extraction, fallback used-range extraction, separate CSV/XLSX outputs, schedule classification, manifest/index generation, tables-only mode, and `authority_transfer=false`.

### Commit

Dedicated PR against `GBOGEB/pipeline-automation-hub:master`, plus a separate global-layout PR against `GBOGEB/GBOGEB:main`.

## Current gate

`READY_FOR_PR_AND_HOSTED_CI`
