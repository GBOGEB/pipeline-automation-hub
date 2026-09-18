# Recursive Build MAIN-runner integration — lossless handover

**Date:** 2026-09-18  
**Tracking:** pipeline-automation-hub#286  
**Authority transfer:** false

## Sequence

`3PR Refresh -> Probe -> Rank -> MIP Modernize -> Innovate -> Perpetuate`

## 3PR

Merged PR #279 proved the canonical recursive-build engine, but the documented MAIN command still stopped after metadata processing.

First-red:

`CANONICAL_RECURSIVE_BUILD_NOT_WIRED_INTO_MAIN_RUNNER`

## MIP

### Modernize

`scripts/run_processing.py` now executes:

```text
validated PPTX metadata processing
        |
        v
processing_summary.json
        |
        v
Recursive_Build_Master.py
        |
        v
recursive_build/build_receipt.json
```

The recursive phase executes only after the metadata summary is PASS.

### Innovate

The MAIN runner emits `pipeline_run_receipt.json`, binding the two phase receipts with SHA-256.

That receipt proves execution/provenance only. It is not a source SSOT and cannot create engineering, compliance, procurement, acceptance, or document-truth authority.

### Perpetuate

- integration tests cover phase ordering and joined hashes;
- recursive-build CI watches the MAIN runner and integration tests;
- README documents the actual MAIN path and output surface;
- this handover and the MissionControl receipt preserve restart state.

## Restart

Refresh `master`, then read:

1. `scripts/run_processing.py`
2. `scripts/Recursive_Build_Master.py`
3. `tests/test_run_processing_recursive_integration.py`
4. `docs/recursive_build/ARCHITECTURE.md`
5. tracking issue #286 / associated PR

Do not add Tkinter to CI. Local interactive launchers may wrap the same CLI only.
