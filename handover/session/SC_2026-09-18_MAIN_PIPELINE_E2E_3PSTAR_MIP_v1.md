# MAIN pipeline E2E 3P* -> MIP handover

**Date:** 2026-09-18  
**Tracking:** pipeline-automation-hub#300  
**Authority transfer:** false

## 3PR

Refresh confirmed that the canonical recursive-build engine and optional Excel schedule phase are integrated into `scripts/run_processing.py`.

Probe found that orchestration confidence still depended mainly on mocks and phase-local tests.

Ranked first-red:

`MAIN_PIPELINE_E2E_PROOF_MISSING`

## MIP

### Modernize

A real subprocess test now creates a minimally valid OpenXML/PPTX package and executes the documented MAIN command through metadata processing, recursive indexing and the joined receipt.

### Innovate

The same E2E suite also executes:

`valid PPTX + real XLSX -> metadata -> recursive-build -> Excel schedule engine -> joined v2 receipt`

The suite asserts SHA-256 binding, exported CSV/XLSX presence, schedule detection and `authority_transfer=false`.

A deliberately invalid renamed `.pptx` proves the opposite branch: the MAIN command exits red and does not create recursive or joined receipts.

### Perpetuate

The real E2E suite is part of the recursive-build workflow. A green exact-head run is the DoV for this slice.

## Guardrail

All outputs remain bounded workflow/provenance evidence. They do not establish slide-content truth or QPS engineering/compliance/procurement/acceptance authority.
