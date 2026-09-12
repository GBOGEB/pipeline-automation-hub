# Pipeline Automation Hub

## Overview
Pipeline/orchestration repository containing the current QPS TRIAGE ULTRA control plane plus older document-processing surfaces.

The **legacy PowerPoint processor is intentionally bounded** after the M09 truth probe. It validates that an input is a PPTX/OpenXML package, hashes it, derives filename-based metadata and candidate references, and generates a metadata/template Markdown twin. It **does not parse slide text, tables, images, diagrams, or document semantics**, and it does not establish engineering/document truth.

## Project structure

```text
app/                              Next.js application and legacy output surfaces
scripts/                          Legacy processing utilities
qps/m09/                          M09 truth/regression probes
mission-control/qps-triage-ultra/ Current QPS TRIAGE ULTRA control/analytics surfaces
```

## Legacy PPTX metadata pipeline

### Inputs

Default location:

```text
app/public/master_input/
```

Only `.pptx` files that pass basic ZIP/OpenXML package validation are accepted. A renamed arbitrary file with a `.pptx` suffix is rejected fail-closed.

### Outputs

```text
app/public/outputs/
├── digital_twins/          metadata/template Markdown twins
├── metadata/               JSON filename/hash metadata
├── cross_references/       filename-derived unverified reference candidates
└── processing_summary.json
```

### Proven capability

- PPTX package validation;
- SHA-256 file identity;
- filename-derived category/priority metadata;
- filename-derived **candidate** SCK CEN references;
- deterministic/reproducible timestamps when `SOURCE_DATE_EPOCH` is supplied;
- metadata/template Markdown twins;
- repo-relative or caller-supplied input/output paths.

### Explicitly not proven by this legacy processor

- slide text/content parsing;
- table or image extraction;
- diagram/visual interpretation;
- content-derived SCK CEN reference extraction;
- PDF conversion;
- Markdown semantic/content fidelity;
- engineering, compliance, or document-truth authority.

Use a dedicated PPTX parser/rendering/OCR/document-analysis pipeline when content-derived evidence is required.

## Usage

Run from the repository root:

```bash
python scripts/run_processing.py
```

Or provide explicit paths:

```bash
python scripts/run_processing.py --input-dir path/to/pptx --output-dir path/to/output
```

Environment equivalents are also supported:

```text
PIPELINE_INPUT_DIR
PIPELINE_OUTPUT_DIR
SOURCE_DATE_EPOCH
```

A run returns non-zero when any discovered PPTX input is rejected or processing fails.

## M09 evidence boundary

The first M09 truth probe demonstrated that the historical implementation could mark deliberately invalid non-ZIP bytes named `QPLANT_Status.pptx` as completed and could derive category/reference claims from the filename alone. The Ambassador/Doctor repair therefore changes the behavior rather than hiding that history:

```text
invalid package -> REJECT
valid OpenXML package -> METADATA_ONLY_COMPLETED
filename reference -> UNVERIFIED_CANDIDATE
content_parsed -> false
authority -> METADATA_ONLY_NOT_DOCUMENT_TRUTH
```

The exact-head regression probe lives at:

```text
qps/m09/M09_LEGACY_PROCESSOR_TRUTH_PROBE.py
```

## QPS TRIAGE ULTRA

The repository also hosts the HOME/federation control plane under:

```text
mission-control/qps-triage-ultra/
```

Those control, telemetry, DMAIC, PCA, BT, federation and burndown surfaces are separate from the legacy document processor. Modernizing the legacy processor does not create a second QPS SSOT or transfer engineering authority.

## Development server

The existing Next.js application can still be started from `app/` using its project package-manager configuration. Treat UI claims about document processing according to the bounded capability above unless separately evidenced by another runtime path.

## Status

- QPS TRIAGE ULTRA control plane: active/current mission-control surface.
- Legacy PPTX processor: bounded metadata-only utility under M09 rehabilitation.
- Full PowerPoint semantic extraction pipeline: **not claimed by this README**.
