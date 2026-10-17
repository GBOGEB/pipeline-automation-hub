# CODE PURPLE / GoGREEN — Metric Atlas N0–N3

An **offline, read-only, scope-safe analytical playground** for parallel GitHub branches, control-flow branch coverage, test growth, execution evidence, root-leverage telemetry, temporal N-indexing, DAG/SIPOC and future N+i scenario analysis. Built for **Windows PowerShell + VS Code**, with a Linux/macOS shell bootstrap. **No third-party Python or JavaScript dependencies** are required to run the included data.

## Launch on Windows

1. Download and extract the full ZIP to a local working folder.
2. Open that folder in VS Code or PowerShell.
3. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 -RunTests -OpenDashboard
```

The bootstrap creates `.venv`, runs the test suite and builds `run/index.html`. It does not call GitHub or change source repositories. Python 3.9+ required. To run manually:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m metric_atlas.cli build
.\.venv\Scripts\python.exe -m metric_atlas.cli simulate --scope-metric MC:METHOD_ATLAS::tests_passed --pulses 3
.\.venv\Scripts\python.exe -m metric_atlas.cli verify-zip .\evidence\method_atlas_11964700323.zip --expected-sha 7f4258824b400e6def84a1c5c50dd8fbac827c316c2077854846a47e065a1eef
```

For Linux/macOS run `./bootstrap.sh`. VS Code launch configurations for build and simulation are in `.vscode/launch.json`.

### Optional: refresh GitHub read-only metadata

Install and authenticate GitHub CLI (`gh auth login`) separately. It is **optional**; no GitHub token is bundled.

```powershell
.\.venv\Scripts\python.exe -m metric_atlas.cli collect-gh --repo GBOGEB/ABACUS --pr 2080 --output run\github_2080.json
```

This fetches a PR source head and the first page of checks. The output is **RAW_CHECK_METADATA_NOT_ATTESTED**, not verified native tests, root closure or merge eligibility. You must collect subsequent run/job/attempt logs and artifact bytes before raising evidence status. No writes or merges are possible in this tool.

## Output files

| File | Use |
|---|---|
| `run/index.html` | Interactive, offline HTML dashboard: logarithmic branch-size chart, normalized overlay growth, local slopes, historical backlog, N+i simulations, DAG/SIPOC, completeness |
| `run/metric_ledger.json` | Immutable-style machine-readable measurement records with scope and provenance |
| `run/metric_ledger.csv` | Excel/Pandas/Power BI ready long-form records |
| `run/metric_events.ndjson` | Streaming append-friendly JSON Lines for waves and instrumentation |
| `run/metric_analysis.json` | Computed histories, slope, acceleration, readiness, normalized overlays and rankings |
| `run/wave_report.md` | Human-readable interpretation and next admissible engineering decisions |
| `docs/CANONICAL_DAG.mmd`, `docs/SIPOC.mmd` | Mermaid visual lineage and process contracts |
| `contracts/measurement.schema.json` | Candidate canonical field definitions for GitHub ingestion |

## Source qualification

- The included **native artifact** `method_atlas_11964700323.zip` is the 73,965-byte historical ZIP from Mission Control #533. Its contents have been independently checked for ZIP integrity and SHA-256. Historical native CODE PURPLE series has **four** steps, not 20.
- Other selected observations are explicitly tagged `REPORTED_HISTORICAL` from previously reported ABACUS and Mission Control results. They are not represented as newly fetched CI or independently re-executed tests.
- 52/66 branch coverage is a **four-module local Mission Control population**, not ABACUS or federation-wide coverage. The broader ABACUS 8,394 branch opportunities have an **UNKNOWN covered numerator**.
- The 7-PR recurring Matplotlib pattern is a failure *fingerprint*, not seven independently proven causal roots, waived security checks or merged PRs.
- Raw statement coverage changes from 17,319/30,987 to 17,371/31,028 use **unmatched populations**. The analyst must not claim a matched coverage uplift without a file/opportunity/config mapping.
- M1/M2/M3, PCA and Bradley–Terry are not granted readiness by historic viewer records. #530 remains canonical ZIP verifier; #531 remains breadth producer; #533 remains Method Atlas viewer. These sources retain distinct authority.

## N-currency and replay

`N` is the latest per-cohort observed development event, `N-1` its predecessor. A global UTC wall clock and Git ancestry are separate coordinates. A new event reindexes N without discarding its original step/timestamp or the historical evidence. Interventions after N are `N+1`, `N+2`, ... and have **SIMULATED_UNCERTIFIED** status until native proof arrives. N20 remains UNKNOWN with fewer than 20 comparable samples.

Data scope and method explanations, qualification thresholds, first-red graph, performance and resource metrics are in `docs/METHOD_AND_WAVES.md`. Historical snapshots can be rerun against original commit SHA/environment in a disposable worktree: report replay/equivalence separately from original CI attestation.

## Governance

The package never alters rulesets, CI protections, PR reviews, security severity or merges. A P0/P1 remains blocking; P2/P3 deferral requires an authorized, source-bound, tracked decision subject to effective GitHub protection. Missing status defaults to HOLD. An optional GitHub probe is READ ONLY.

## Tests and known gaps

The included negative tests assert no denominator overflow, no false scope matching, no invented N20, no fake covered branch numerator, correct historical denominator changes, ZIP integrity and non-attesting simulation. CI execution, current GitHub eligibility, worker-hours, native test count updates and larger federation breadth require fresh authenticated telemetry.
