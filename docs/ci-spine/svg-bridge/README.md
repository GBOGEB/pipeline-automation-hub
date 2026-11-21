# JQ09 — SVG source ⇄ review-object bridge

> **Status:** `IMPLEMENTED_CANDIDATE / NATIVE_DOV_PENDING / MERGE_ADMISSION_HOLD`. This is a bounded read-only Jacquard-inspired extension of the already-merged CI Spine notebook. No new execution scheduler, authoritative DAG owner, metric owner, required check, PDF writer, workflow job, or branch deletion.

## 1. Verified starting lineage

| Lane | Source | Readback / scope | State |
| --- | --- | --- | --- |
| Foundation | [#989](https://github.com/GBOGEB/pipeline-automation-hub/pull/989) | README status badges and branch-custody guidance | MERGED |
| Test catalog and B00–B09 | [#992](https://github.com/GBOGEB/pipeline-automation-hub/pull/992) | Frozen 182 workflows, 307 test-named files, logical bundle DAG | MERGED |
| Offline explorer | [#1002](https://github.com/GBOGEB/pipeline-automation-hub/pull/1002) | Standalone HTML DAG/SIPOC and Plotly presentation | MERGED |
| Jacquard notebook | [#1017](https://github.com/GBOGEB/pipeline-automation-hub/pull/1017) | Read-only linked source/review text, historical samples | MERGED |
| HTML pointer atlas | [#1018](https://github.com/GBOGEB/pipeline-automation-hub/pull/1018) | Three content-bound source-to-HTML view selections | MERGED |
| Plotly point↔run | [#1239](https://github.com/GBOGEB/pipeline-automation-hub/pull/1239) | Eight historical run/attempt point identities, independent lane | OPEN / do not duplicate |
| **JQ09 SVG bridge** | `feat/ci-spine-svg-bridge-jq09-20261113` | Five real SVG rectangles, layer toggles, immutable line links | CANDIDATE / review pending |

**Base source commit:** `54e6b01ac7ada5bfad15562b4f99f7381a4fd73f` (Hub master, 2026-11-13). **Owner source:** `mission-control/qps-triage-ultra/site/assets/diagrams/qps-web-architecture.svg`, Git blob `8a947a18a76bd87029b0c237be81505eb86f0891`. The diagram's five boxes are MissionControl SSOT, Next/React, Jekyll/HTML, QPS UI tokens and Release parity. Six source SVG paths show connections, not independently qualified engineering requirements.

## 2. What is implemented

The `svg_bridge.py` stdlib-only adapter reads the **existing** source SVG, refuses any source-blob drift, verifies its viewBox, five box labels, six connection paths, safe XML subset and all real x/y/width/height coordinates. It creates a derived offline HTML review surface with:

- A selectable five-object source list and click/keyboard selectable SVG rectangles, named by source-derived labels.
- Separate layer controls for connection paths and labels, with in-viewport zoom (45%–220%). Mobile overflow belongs inside the diagram viewport.
- A source inspector: immutable source Git commit, blob SHA, source SHA-256, source line, SVG coordinates and normalized bbox.
- Shareable `#node=...` routes with unmapped IDs **failing visibly** rather than navigating to a guessed object.
- Source-derived `SVG_RECT_SOURCE_GEOMETRY` precision and `UNMAPPED_NO_VERIFIED_BINARY` for PDF. No permission to edit a live SVG, run a shell command, dispatch CI, promote a result or claim engineering/compliance authority.

The adapter writes `index.html` and `SOURCE_SVG_POINTERS_v1.json`. Its sidecar hashes the **actual generated HTML bytes** plus the real source SVG, and binds all five object IDs. It is source-provenance navigation, not a new generic SVG processing engine.

## 3. Reproducible local use (PowerShell or terminal)

From an exact checkout of the review branch, or after a later qualified merge:

```powershell
python docs/ci-spine/svg-bridge/svg_bridge.py
python docs/ci-spine/svg-bridge/svg_bridge.py --check
python docs/ci-spine/svg-bridge/test_svg_bridge.py
Start-Process docs/ci-spine/svg-bridge/index.html
```

Browser QA uses the Playwright dependency already installed by the existing `ci-spine-governed-qa` Chromium job (not required locally simply to view HTML):

```powershell
python docs/ci-spine/svg-bridge/browser_svg_bridge_qa.py
```

The existing `.github/workflows/ci-spine-governed-qa.yml` now builds this derivative, runs the negative suite and browser DoV on its existing jobs, and uploads the HTML, source-bound manifest, logs and viewport screenshots as CI artifacts. **No additional jobs or new external package dependencies.** Source SVG is unchanged.

## 4. DoD / DoV chaperone

| ID | DoD: expected capability | DoV: proof to inspect | State |
| --- | --- | --- | --- |
| JQ09-01 | Real owner-controlled input SVG, immutable 40-character blob OID | Exact tree match, SHA256 and 5-node/6-flow parse | CODE COMMITTED; native check pending |
| JQ09-02 | Stable source→SVG rect pointers and normalized geometry | 14 negative/positive tests, stale-blob/malformed/remote-script failures | CODE COMMITTED; native check pending |
| JQ09-03 | User GUI selection, keyboard access, layer toggle, 2-way source link and zoom | Chromium 1440 + 390, selected/unknown/scroll, screenshot and external-request proof | CODE COMMITTED; browser receipt pending |
| JQ09-04 | Deterministic output HTML + sidecar actual digest | `svg_bridge.py --check` and CI uploaded HTML/JSON hashes | CODE COMMITTED; native artifact pending |
| JQ09-05 | Noncompensating merge governance and current-state labels | PR head checks, independent review, effective FPC/rules and no waiver | HOLD |
| JQ09-06 | Actual PDF page, OCG/layer and normalized rectangle with physical verification | Real owner PDF source + hash + page/coordinate transform + stale-reflow negative test | BLOCKED: NO VERIFIED PDF MAPPING |
| JQ09-07 | Synced source-anchored comments across SVG/PDF revisions | Stable semantic object ID, rebind, unmatched→UNRESOLVED and independent review | DESIGN ONLY |

## 5. Reconciliation and stack policy

Keep JQ08 Plotly point links in [#1239](https://github.com/GBOGEB/pipeline-automation-hub/pull/1239) **disjoint** from JQ09 SVG source geometry. Their fan-in is conceptual until both provide independently qualified exact-head artifacts. The existing JADE workflow parser, canonical GitHub Actions owner, QPS web source and CI Spine pointer validator remain source of truth. Neither JQ08 nor JQ09 can approve release.

**Next controlled order:** (1) inspect native tests on JQ09 head and repair first reds; (2) inspect Chromium screenshots and exact source-to-SVG click; (3) obtain eligible independent review; (4) use the current QPS source owner to select one real engineering SVG/PDF diagram for optional follow-on JQ10; (5) only then consider PDF.js optional-content/rectangle mapping. Jacquard's source/output links and mirrored comments are an interaction pattern, not an authorization to copy its experimental watcher into a privileged GitHub runner.

References: [Jacquard notebook](https://www.inkandswitch.com/jacquard/notebook/) · [CI Spine five-lens explorer](../explorer.html) · [Provenance pointer atlas](../pointers/index.html) · [Canonical QPS owner](../../../mission-control/qps-triage-ultra/README.md).
