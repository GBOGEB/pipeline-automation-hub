# Recursive Build architecture — 3P* + MIP v1

## Scope

This surface indexes outputs from the bounded legacy metadata pipeline. It is a workflow/control layer, **not** a QPS engineering, compliance, procurement, acceptance, or document-truth authority.

## Sequential method burn

### 3P* / 3PR

**Refresh:** current implementation was `scripts/recursive_build.py` on master `b3a7df1f7aa24765c243eb282dca58d3c9ea3668`.

**Probe:** the old implementation had a hard-coded runtime path, wall-clock output timestamps, no per-artefact lineage receipt, no global JSON index, no Top-N ranked index, no reproducibility contract, and no dedicated tests/CI.

**Rank:** first-red = `RECURSIVE_BUILD_NOT_REPRODUCIBLE_OR_LINEAGE_COMPLETE`.

## MIP

### Modernize

`scripts/Recursive_Build_Master.py` is the new canonical implementation.

It provides:

- explicit `--outputs-dir`;
- deterministic time through `--generated-at` or `SOURCE_DATE_EPOCH`;
- SHA-256 lineage on metadata inputs and generated indexes;
- per-artefact `.buildlog/<artefact>/artefact_id.yaml`;
- `index.json`, `index_top30.md`, `master_index.md`, and `build_receipt.json`;
- compatibility via `scripts/recursive_build.py`.

### Innovate

A deliberately bounded relevance score is introduced:

`0.70 * priority + 0.20 * bounded reference density + 0.10 * hash presence`

This score is static, transparent, deterministic, and limited to workflow curation. It must never be read as engineering importance or acceptance status.

### Perpetuate

Control is maintained through:

- `tests/test_recursive_build_master.py`;
- `.github/workflows/recursive-build.yml`;
- local VS Code tasks;
- a build receipt with hashes;
- this architecture note and a lossless session handover.

## Tkinter / local interaction boundary

Interactive Tkinter prompts are **not** placed inside GitHub Actions. Hosted CI is headless and must remain deterministic. If a local GUI chooser is desired, it should call the same CLI and create a machine-readable invocation receipt.

## Ariana boundary

Ariana is optional runtime observability for local development. The GBOGEB fork is not modified here. The VS Code task detects Ariana when available and otherwise falls back to plain Python. Ariana is therefore an observation adapter, not a build authority or mandatory dependency.

## Authority guardrail

All generated records declare:

`METADATA_ONLY_NOT_DOCUMENT_TRUTH`

Filename-derived or metadata-derived references remain candidates. No score, hash, index, successful CI job, or polished outward view creates engineering or acceptance credit.


## MAIN runner integration — v2

The canonical engine is now a required second phase of `scripts/run_processing.py`.

```text
ppt_processor.py
  -> processing_summary.json
  -> Recursive_Build_Master.py
  -> recursive_build/build_receipt.json
  -> pipeline_run_receipt.json
```

The runner is fail-closed between phases: recursive indexing is not executed when the metadata summary is red.

`pipeline_run_receipt.json` binds `processing_summary.json` and `recursive_build/build_receipt.json` by SHA-256 and carries the same `METADATA_ONLY_NOT_DOCUMENT_TRUTH` guardrail. It is a provenance/control receipt, not a source SSOT.


## MAIN runner Excel schedule binding — v3

The MAIN runner may now add the governed Excel schedule/data table engine as an explicit optional third phase. Existing PPTX metadata + recursive-build behavior remains unchanged when no Excel workbook is requested.

```text
ppt_processor.py
  -> processing_summary.json
  -> Recursive_Build_Master.py
  -> recursive_build/build_receipt.json
  -> [optional] excel_schedule_engine.py
       -> Outputs/excel/tables_csv/*.csv
       -> Outputs/excel/tables_xlsx/*.xlsx
       -> Outputs/excel/table_manifest.json
       -> Reports/schedule_index.{csv,md}
  -> pipeline_run_receipt.json (v2)
```

The joined receipt SHA-binds the Excel table manifest when the phase is requested, including table counts, schedule-candidate counts, error count and `authority_transfer=false`. Excel failure is fail-closed for an explicitly requested Excel phase; omission of `--excel-input` preserves the historical two-phase path.

This binding is orchestration/provenance only. The workbook remains SOURCE input and the CSV/XLSX exports remain derived renditions.


## MAIN real E2E proof — v4

The CI control now includes a real subprocess proof of the documented MAIN command, not only mocked orchestration.

Three branches are exercised with disposable fixtures:

1. minimally valid PPTX -> metadata -> recursive build -> joined receipt = PASS;
2. deliberately invalid bytes renamed to `.pptx` -> fail-closed before recursive/joined receipt;
3. valid PPTX + real XLSX -> metadata -> recursive build -> Excel schedule export -> joined v2 receipt = PASS.

The E2E proof checks the SHA-256 links recorded in `pipeline_run_receipt.json` and preserves the metadata-only/derived-rendition authority boundaries.
