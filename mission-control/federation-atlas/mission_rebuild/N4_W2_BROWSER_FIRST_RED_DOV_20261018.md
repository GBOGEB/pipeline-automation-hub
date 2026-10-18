# CODE PURPLE N+4 — W2 browser first-red and governed convergence

## Source-owned incident

- Observed native [Method Atlas run 39133866708](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39133866708), attempt **1**, exact PR #707 head `4e9579895edd17b571e689f7f402b262e6b9737a`, job `117694317468`: Playwright `Locator.wait_for` timed out after 30 seconds looking for the **first W2 Plotly chart** `.inlay .js-plotly-plot`. The preceding generated W2 files, unit cohort and Pages source/hash step ran, so the browser failure is not a Python import error.
- Verified source path: `w2_plotly.render()` creates each Plotly `to_html(...include_plotlyjs=False)` fragment inside the HTML cards; the offline `__PLOTLY_LIBRARY__` script was inserted only **after** `</main>`. The browser executes early inline `Plotly.newPlot(...)` while Plotly is undefined, so no chart is created. This is an attributable rendering-order defect, separate from #707's workflow-level error annotation.
- The first graph can also compute width before its sibling CSS grid cards are mounted, allowing **card overlap despite zero document overflow**, previously reproduced in N3. This is a second negative browser contract to preserve, not a credited separate accepted causal root.

## Three bounded pulses

1. **P1 Diagnose:** exact head/run/attempt/job/step and source-order evidence. Current Method Atlas and gg_MATH jobs are independent; no rerun storm.
2. **P2 Repair:** relocate the single bundled/offline Plotly JavaScript to before the four inline Plotly fragments, without adding network JS, new publisher, stats algorithm or dispatcher. After the grid mounts, call `Plotly.Plots.resize` on its chart DIVs.
3. **P3 Control:** existing `test_w2_evidence.py` adds a script-order and responsive-resize regression; existing `w2_browser_qa.py` now verifies all **four Plotly card-canvas widths**, in addition to 1440×1000, 1280×800, 390×844, modal, filters, zero console/page errors, zero horizontal body overflow, screenshot hashes and existing Pages SHA-256 parity.

## DMAIC, MIP, gg_MATH evidence

- Define CTQ: W2 HTML must display the **four real Plotly inlays**, not merely contain four static placeholders.
- Measure: exact PR head SHA, run/attempt/job, HTML member digests, four inlay geometry pairs (plot px, card px), and three viewport receipts.
- Analyze: initialization order is source-local, while a first-red manifestation does not mean accepted engineering-root closure.
- Improve: repaired source and native regression guards, independent from CPQ N5 and QPS private-source access.
- Control: require terminal exact-head 1+ native W2 test, 3 viewport QA, site manifest and downloaded ZIP member bytes; protect merge separately.
- MIP Modernize/Innovate have source candidates; Perpetuate awaits native repeat and authorized reviewer.
- gg_MATH: no copied statistical kernel. M1 structural, M2/M3 HOLD, PCA/BT not qualified, Six Sigma NOT ATTESTED. Queue counts are not runner capacity or stability evidence.

## Noncompensating DoV and BD

`W2_TECH_DOV = exact_head_native_test_pass AND four_charts_render AND three_viewport_QA_pass AND sources_to_pages_sha_match AND artifact_zip_member_bytes_verified`.

`MERGE_ADMISSION=HOLD`: this remains separate from branch protection, independent human approval, required check binding and a rejected negative merge canary. Main protection remains source-owner/admin return [#336](https://github.com/GBOGEB/pipeline-automation-hub/issues/336); private QPS Actions receiver access remains [#636](https://github.com/GBOGEB/pipeline-automation-hub/issues/636) until fresh source-bound proof. [#707](https://github.com/GBOGEB/pipeline-automation-hub/pull/707) owns enhanced failure annotation, not this renderer source.

No waiver, authenticated remote dispatch, QPS owner acceptance, causal root closure or merge is performed by this source-repair candidate.
