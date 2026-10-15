# W1/W2 flight runbook — source, tasks, hooks, outputs

## Required trigger semantics

| Trigger | Action | Writes to | Authority |
|---|---|---|---|
| USER opens GUI | Search/filter/inspect evidence and write local note | Browser memory / downloaded `flightdeck_review_notes.json` | Local notes; no GitHub POST |
| USER runs `preflight` | Read and validate SSOT/frozen head snapshot | Stdout receipt only | Read-only |
| USER runs `refresh-heads` | Read five public GitHub branch APIs in bounded sequence | `head_snapshot.json` only | New observed snapshot; not auto-green |
| USER runs `build` | Derive exactly typed leaves, anchors, GUI, SVG, Markdown | Explicit `--out` | Local reproducibility |
| USER runs `office_export` | Render selected binaries from same `census.json` | Explicit `--out` | Derivatives, not corporate originals |
| `seal` / `verify` | Hash/verify each generated output and cardinality | `manifest.json` / stdout | Local QA |
| GitHub PR path trigger | Proposed workflow checks and emits output ZIP | GitHub Actions artifact only | Native exact-SHA producer (when installed) |
| Owner approved release | Future guarded Pages deployment | GitHub Pages | External repository control, NOT implemented |
| Changed main / policy / tool / denominator | Fail old-evidence reuse, recensus and regenerate | New versioned inputs and evidence | Source revalidation |

## Task group and command outputs

`P00 -> P10 -> P20 -> P30 -> P40 -> P50 -> P60 -> P70`

`P20` uses observed owner BD/LDAB/LLDB receipts **when available**; the present standalone renderer does not run a debugger or make unverifiable root joins. `P60` is a policy/owner responsibility, not a write side-effect. GOGREEN scouts 36 UNKNOWN leaves with one accountable owner before any mutation fan-out. `P70` can display M1 input validity, but PCA, Bradley–Terry, M2 and M3 are HOLD without comparable independent trials.

### Code output example

```text
{"status":"PASS","source_semantic_sha256":"<64 hex>","repo_count":6,"target_cells":42,"observed":6,"unobserved":36}
{"status":"PASS","validated_files":10,"cells":42,"unknown":36,"anchors":5,"stale":3,"source_sha256":"<64 hex>"}
```

Each file in `out` contains or is covered by the `source_semantic_sha256` of the three input JSON files. This is not a signed supply-chain attestation. The `index.html` dashboard is fully self-contained except for explicit outgoing GitHub evidence links and relative file downloads; it can be opened locally or served by an authorized static web host.

### Developer preflight and container helpers

- Local Python interpreter: `python --version`, `python -m unittest`, `coverage run --branch`.
- Node.js for PPTX: `node --version`, `node source/slides.js out/census.json out/mission_brief.pptx`.
- Editor/manual debugger: launch `python source/flightdeck.py preflight ...` under VS Code debugpy if local debugging is needed. An LLDB/Docker/MCP receipt is only valid after an actual session; no preconfigured external port, token, runner or container is claimed here.
- Browser: `python source/qa_browser.py` uses Chromium and verifies 1440×1000, 1280×800 and 390×844 layouts, search/filter/reset, local export and no console/page errors.

## Definitions of done and verified

- **W1 IMPLEMENTED**: all 6 repo identities, 42 typed cells and 5 main anchors accounted for, 36 UNKNOWN leaves with existing #529 issue crosswalk.
- **W1 VERIFIED LOCAL**: deterministic source contract and negative controls pass.
- **W2 IMPLEMENTED**: CLI generators and user-facing artifacts exist.
- **W2 VERIFIED LOCAL**: 42/42 focused tests pass; html browser 3/3 passes; binary structural and render QA passes; file manifest matches.
- **W2 VERIFIED NATIVE**: requires a future GitHub Actions run at the committed exact checkout SHA. No local test alone grants this.
- **W3 MERGE/PUBLISH**: owner controls server-side checks, eligible review and Pages content SHA readback on protected main; remains HOLD.