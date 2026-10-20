# Master_Input pipeline runtime harness (#529 G09)

Re-runs the **Master_Input document pipeline** (`scripts/run_processing.py` → `ppt_processor.py` + `Recursive_Build_Master.py`) and records what it **actually does**, without changing its inputs.

```powershell
pwsh ./mission-control/pipeline_runtime/Run-MasterInputPipeline.ps1            # sandbox: repo untouched
pwsh ./mission-control/pipeline_runtime/Run-MasterInputPipeline.ps1 -Open      # open report.html after
pwsh ./mission-control/pipeline_runtime/Run-MasterInputPipeline.ps1 -InPlace   # real refresh of app/public/outputs, review with git diff
pwsh ./mission-control/pipeline_runtime/Run-MasterInputPipeline.ps1 -ExcelInput .\plan.xlsx
```
(Python-only: `python mission-control/pipeline_runtime/harness.py --report-dir <dir> [--in-place]`.)

| Question | Where in the receipt / report |
|---|---|
| Did it fail, and where? | `exit_code`, `errors.uncaught[]` (type, message and traceback **per Python process**), `errors.stderr_flagged` |
| Which processes ran? | `processes[]` (pid, parent, argv, seconds); **DAG** diagram |
| Which functions were called? | `processes[].functions[]`: `file:qualname@line`, calls, first-call order, file SHA-256 and git **O-ID** (repo code only; stdlib excluded) |
| What did it produce or change? | `outputs.created / modified / deleted` (SHA-256 + O-ID; JSON top-level keys changed) vs the committed outputs |
| Did it change its inputs? | `input.immutable` (every input hashed before and after) |
| Did it write anywhere else? | `stray_repo_writes` (whole-repo snapshot diff) |
| How does it fit together? | `sipoc.mmd`, `dag.mmd`, `spine.mmd`, `DIAGRAMS.md` (generated from the run) |

**How it observes:** `tracer/sitecustomize.py` is injected via `PYTHONPATH`, so **every** spawned Python process is traced (`sys.setprofile`, uncaught exceptions via `sys.excepthook`). The pipeline code itself is not modified.

**Report views:** `report.html` lets you switch every asset label between **name** (Python asset `file:function`, or file path), **SHA-256**, **O-ID** (git object ID) and **tags**, with short/long IDs and a filter.

## Reference run (`runs/20261020/`, sandbox, master `d3b82b13`)
- **Run:** PASS, exit 0, 3 processes, **63 functions** (`ppt_processor.py`: 27 functions and 38,141 calls; `Recursive_Build_Master.py`: 25 functions and 553 calls; `run_processing.py`: 11).
- **Inputs:** 24 Master_Input decks, **immutable**. **Stray writes:** 0.
- **Outputs vs committed (2025-09-10):** **+28 created, ~74 modified, 0 deleted**, 32 unchanged.
  - **24 metadata JSONs** gain governance keys the current code emits (`authority`, `processing_scope`, `pptx_package_validated`, `content_parsed`, `cross_reference_basis`). The committed outputs predate them.
  - **24 digital twins and 24 cross-reference files** are regenerated.
  - **27 recursive-build lineage artefacts** (`recursive_build/.buildlog/*/artefact_id.yaml`, …) were **never committed**.
- **Reading:** the committed outputs are stale relative to the code. An `-InPlace` run plus review would refresh them.
