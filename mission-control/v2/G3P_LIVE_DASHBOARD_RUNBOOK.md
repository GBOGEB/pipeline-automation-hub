# G3P live pulse-lineage viewer — read-only N+1 → N+6

**Owner:** Mission Control G3P / #604. **Status:** candidate source implementation, NOT independently admitted.

This upgrades the existing `n3_wave_federation.py` HTML generator without altering `compile_waves`, the append-only N3/N6 ledgers, DoD/DoV criteria, or autonomous runner admission. The six node source claims and input ledger hashes remain frozen.

## Run locally (Python standard library only)

From the repository root:

```powershell
py -3 -m venv .venv-g3p
.\.venv-g3p\Scripts\python.exe mission-control/v2/g3p_live_dashboard.py --ledgers mission-control/federation-atlas/CBD_GOLDEN_GRAPH_N3_20261017.json mission-control/federation-atlas/CBD_GOLDEN_GRAPH_N6_20261017.json --serve --port 8765
```

Open `http://127.0.0.1:8765/`. CTRL+C stops the local process. Nothing is scheduled when the browser/tab or server is closed. On Unix/macOS use `python3 -m venv .venv-g3p` and `.venv-g3p/bin/python`.

Controls: **Reload ledger**, cyclic polling (off/5/15/30 seconds), push-style server-sent revision events, N+i slider, Play/Pause historical replay, clicked/keyboard-selected pulse, typed DAG/SIPOC and read-only source SHA/LOCAL test provenance.

The server runs **loopback only**, reads the two allowlisted paths on each request, returns **409** for invalid ledgers, and never pushes to GitHub or executes code from a ledger.

- `GET /`: self-contained offline HTML + bundled N+6 snapshot
- `GET /api/lineage`: recomputed source-bound JSON, `Cache-Control: no-store`
- `GET /api/events`: revision notifications by text/event-stream, bounded 180-second connection
- `GET /health`: validator status; 503 when source invalid

Generate downloadable offline assets:

```powershell
.\.venv-g3p\Scripts\python.exe mission-control/v2/g3p_live_dashboard.py --ledgers mission-control/federation-atlas/CBD_GOLDEN_GRAPH_N3_20261017.json mission-control/federation-atlas/CBD_GOLDEN_GRAPH_N6_20261017.json --out-dir .\artifacts\g3p-n6
```

Outputs: `g3p-lineage.html`, `g3p-lineage.json`, `g3p-lineage.mmd`, `g3p-manifest.json` with SHA256 of all generated artifacts. The offline HTML replay works; **live refresh requires the loopback feeder**, not GitHub's static blob viewer.

## QA and acceptance

```powershell
.\.venv-g3p\Scripts\python.exe -m unittest discover -s mission-control/v2 -p test_n3_wave_federation.py -v
.\.venv-g3p\Scripts\python.exe -m unittest discover -s mission-control/v2 -p test_g3p_live_dashboard.py -v
```

Local run: 36/36 graph+feeder tests; focused two-source-module statement 229/238, branch 55/64, combined 284/302. This is a **new source scope**, not a matched before/after 14-test cohort coverage gain. Chromium DOM smoke shows N+6=6 nodes/5 edges/1 gap/61 LOCAL; N+3=3 nodes/2 edges/NOT_RUN unknown; source change pushes a different revision; forged approval refused. Browser direct localhost navigation was blocked by this runner; DOM/JS tested using `page.set_content`; HTTP/SSE verified independently through `urllib`.

Native Python 3.11/3.12 must test exact PR head and artifact receipts; **no existing HOLD, source_authentication:false or cross-wave DECLARED_GAP is promoted**.

Live refresh consumes changed *local ledger files* only, not native GitHub Actions updates on its own. A future authenticated producer may atomically export a newly admitted receipt, after which the feeder will show the new read-only projection. Do not backfill previous receipt statuses.

## Extension hooks

Reuse `compile_waves` for DAG semantics. Never infer run-job success, causal-root closure, weighted fleet coverage or native CI from HTML update status. Client-generated provenance is a presentation/QA receipt only.
