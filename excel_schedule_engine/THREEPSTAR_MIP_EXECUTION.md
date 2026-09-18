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


---

## P1 Post-Merge Review Iteration — 2026-09-18

### 3PR — Refresh / Probe / Rank

Refresh observed that PR #275 and the global topology PR had merged, and that the hosted Excel Schedule Engine proof completed successfully with real steps. Post-merge Codex review then identified three P1 defects in the compact XLSX rendition path.

Ranked P1 defects:

1. Relocated formula references could retain source coordinates and calculate incorrectly.
2. Normalized output names could collide and overwrite prior logical-table exports.
3. Tableless used-range fallback could start at A1 instead of the actual used-range origin.

### MIP — Modernize / Innovate / Perpetuate

- Modernize: formula-mode XLSX exports now translate A1 formulas from source coordinates to compact destination coordinates and recreate source Excel Table definitions so structured references retain a valid table context.
- Innovate: logical export IDs now bind sheet, source kind, source name and source range through SHA-256 suffixes, with an in-run duplicate guard.
- Perpetuate: used-range extraction now consumes the exact `calculate_dimension()` range, and three regression tests were added.

### 3PC — Prepare / Prove / Commit

Local proof after the repair:

```text
python -m unittest -v test_excel_schedule_engine.py
6 tests -> PASS
```

The repair is bounded to rendition correctness and does not transfer authority.
