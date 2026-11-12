# JQ-08: Plotly point-to-source navigation (controlled pilot)

**Snapshot**: Hub master `c66feef5c886ebc359bf38d4ea832e23b5ec5c46` at 2026-11-12T12:33:28Z. **Proposed** interface refinement; no CI admission, owner PDF mapping, deployment or automatic execution.

## Starting evidence

- [#989](https://github.com/GBOGEB/pipeline-automation-hub/pull/989) and [#992](https://github.com/GBOGEB/pipeline-automation-hub/pull/992) MERGED.
- [#1002](https://github.com/GBOGEB/pipeline-automation-hub/pull/1002), [#1017](https://github.com/GBOGEB/pipeline-automation-hub/pull/1017), [#1018](https://github.com/GBOGEB/pipeline-automation-hub/pull/1018) MERGED. The existing explorer, notebook, and three-pointer atlas stay canonical.
- Input: [eight historical sampled runs](RUN_TIMING_SAMPLES_20261028.json), **not** latest fleet data. Existing owner `plotly_projection.py` draws those rows; `actions_metrics.py` owns measured fleet metrics.

## DoD / DoV and branch guidance

| ID | To implement (DoD) | Independent verification (DoV) | State |
| --- | --- | --- | --- |
| JQ08-01 | Preserve sampled source data; stable point IDs keyed by run and attempt | Positive+negative tests: uniqueness, malformed IDs, source SHA/attempt and unknown queue handling | IN WORK |
| JQ08-02 | Offline Plotly bar selection updates a sourced inspector, links to the existing explorer's exact run selection and GitHub attempt | Native rendered HTML contains stable ids and no external script tags; browser interaction after head CI | IN WORK |
| JQ08-03 | Emit separate source-bound JSON receipt: input digest, chart digest, point population and claim precision | Check sidecar digest against actual output; reject cross-run or cross-attempt substitution | IN WORK |
| JQ08-04 | No automated execution, tracking, PDF geometry or pseudo-certification | Static negative tests and native job results; no new dependencies/permissions/workflow | HOLD pending evidence |
| JQ08-05 | Propagate links into larger GUI and real owner PDFs after exact geometry is available | Independent PDF page/bbox/OCG inspection, redraw/re-paginate drift test and owner review | FUTURE, UNMAPPED |
| JQ08-06 | Qualified delivery/merging | Exact PR head native CI, Codex review, FPC and effective rulesets verified; owner signoff | HOLD |

**Architecture:** Chart is a presentation adapter using existing run snapshots; links are resolved only from an allowlisted source-run table, not arbitrary clicked label strings. Its JSON sidecar declares `PLOTLY_POINT_SELECTION`, which is **not** `PDF_RECT_EXACT`, engineering acceptance or merge authority. Browser UI never submits code or mutations.

**Test intent:** click both queue and execution bars for one run; same semantic source selected; source SHA/run attempt match; malformed/unmapped point yields no fabricated navigation. Both local `file://` and the CI artifact bundle must navigate to the existing explorer's `#lens=timing&kind=run&id=<run-id>`.

**Maintenance:** regenerate the chart from the canonical eight-run samples; do not copy the run metrics, make new performance owners, or silently refresh historical inputs. Output receipt is generated alongside the HTML, not committed as a current live measurement.

### Deep-read overlap

- Jacquard [fine-grained provenance](https://www.inkandswitch.com/jacquard/notebook/) demonstrates source↔built-document navigation and source-anchored comments, with SyncTeX precision limitations.
- Patchwork [universal pointers and comments](https://www.inkandswitch.com/patchwork/notebook/11/) treats app-specific target selection separately from a generic comment UI.
- For this pilot use stable Plotly `ids` and `customdata`; keep any later comment storage separate from output rectangle guesses.
