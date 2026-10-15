# Mission Control / Federation Flight Deck — W1 + W2

**Status:** locally built and QA verified. **GitHub integration/Pages release:** not yet promoted; this package is a working drop-in, not a newly merged canonical pipeline. **Authority:** read-only generated view; QPS `DEFER`, no independent merge or corporate document approval.

## Who are we?

Mission Control coordinates the federated source-to-evidence flight deck. ABACUS/DOW owns diagnosis and attributable first-red recovery, CODEX/KEB owns semantic execution and debugger bridges, `cryoplant-project` owns QPS engineering acceptance, `gg_MATH` owns model inputs and reproducible mathematics, and `DOCX_RTM_Automation` owns document/RTM projections. These are project roles derived from the source catalog; they are not an assertion of corporate sign-off.

## Architecture and source authority

| Level | Item | Authority |
|---|---|---|
| Controlled input | `GBOGEB/pipeline-automation-hub/mission-control/gogreen/samples/fleet_g1.json` | Original G4 six-repo/42-cell cohort; do not silently overwrite G0/G1 history |
| Controlled method and rendering contract | `flightdeck_contract.json`, existing `METHOD_OBSERVABILITY_v1.json`, `ATLAS_GRAPH_v1.yaml` | Governed GitHub text; changes go through PR |
| Observational snapshot | `head_snapshot.json` | One captured GitHub readback; changes over time; it is **not** live current HEAD |
| Code | `flightdeck.py` and optional `office_export.py` / `slides.js` | Deterministic projection generators |
| Generated JSON/HTML/SVG | `out/census.json`, `out/index.html`, `out/flightdeck.svg`, etc | Rebuild, never hand-edit authoritative data into a generated view |
| Optional generated binaries | `out/evidence_register.xlsx`, `out/federation_report.docx`, `out/mission_brief.pptx`, `out/linked_evidence_book.pdf` | Generated, not original, not corporate-approved |
| External authority | Github ruleset, QPS owner, ALX/SCK CEN official document-control records | Never inferred by renderer |

### Quick start (local folder / Windows or Linux)

Run from this package root:

```bash
python source/flightdeck.py preflight \
  --fleet source/fleet_g1.json --snapshot source/head_snapshot.json \
  --contract source/flightdeck_contract.json
python -m unittest discover -s source -p 'test_flightdeck.py' -v
python source/flightdeck.py build \
  --fleet source/fleet_g1.json --snapshot source/head_snapshot.json \
  --contract source/flightdeck_contract.json --out out
python source/office_export.py --input out/census.json --out out
python source/flightdeck.py seal --out out
python source/flightdeck.py verify --out out
```

**Binary dependencies (optional)**: `python-docx`, `openpyxl`, `reportlab`, Node.js and `pptxgenjs`. The read-only CLI+HTML/SVG/JSON uses Python standard library only. Source code `slides.js` uses PptxGenJS, not python-pptx.

**Python stdout** is an exit-code + JSON receipt (`PASS`, exact source digest, expected/verified file count). It does not print the Word/PDF or write to the GitHub API. Files are written to the explicit `--out` directory. Exit code `2` means fail-closed validation.

### Windows C:\repo / stale clone control

Execute `source/run_flightdeck.ps1 -RepoRoot C:\repo\pipeline-automation-hub -OutDir <local output>`. The wrapper compares the local clone's `master` with fetched `origin/master`, fails if stale and avoids a blind `git pull` with unreviewed mutations. The `master`/origin update and the current-head snapshot are **distinct checks**. To refresh five public repository-head snapshots only, use `-RefreshHeads` and review new source hashes; the script never copies staged USER binaries over corporate originals.

### GitHub CI and publication

The proposed `.github/workflows/flightdeck-artifact-ci.yml` is supplied as **drop-in source**, not asserted installed or running. It checks exact checkout identity, validates inputs, runs tests, builds static outputs and Office/PDF projections, and publishes an artifact named with exact SHA. It does **not** deploy GitHub Pages or self-approve merges. Actual protected `master`, required check contexts, owner authorization and a separate `deploy-pages` job require repo-owner validation before enabling; GitHub Pages content must then be fetched and compared with the generated SSOT source digest.

For GitHub integration, copy this package's `source` into `mission-control/federation-atlas/flightdeck/`, replace the local preview `fleet_g1.json` argument with canonical `mission-control/gogreen/samples/fleet_g1.json`, add a read-only link from the **existing** method atlas `build_atlas.py` into its output directory, and test it in a governed PR. Do not create a competing Pages controller. Avoid restarting unrelated green suites just to display a page.

## Source and documentation map

- [Operator runbook](RUNBOOK.md) — commands, hooks, output paths and P00–P70 decision points.
- [Document control](DOC_CONTROL.md) — corporate records, generated binaries, review and approval.
- [Wave receipts](WAVES.md) — what W1/W2 proved and what W3 still requires.
- [Source references](SOURCES.md) — exact upstream GitHub file/issue/run links.
- `out/GUIDE.md` — generated stage-by-stage report with exact combined input SHA.
- `out/census.json`, `out/bd_leaves.json`, `out/anchors.json`, `out/manifest.json` — machine-readable full evidence and digests.
- `qa/coverage.json`, `qa/browser_qa.json`, `qa/QA_RECEIPT.json` — local focused tests, interactions and output QA.

No root is closed merely by its display row, and no generated view changes company records, protected policy or repository admission.