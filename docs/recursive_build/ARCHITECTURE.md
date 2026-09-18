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
