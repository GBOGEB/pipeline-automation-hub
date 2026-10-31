# Jacquard / CI Spine — provenance as navigation, not authority

**Exploration 2026-10-28 · Proposed implementation / NOT a release decision.** Reference: [Ink & Switch Jacquard notebook](https://www.inkandswitch.com/jacquard/notebook/) (entries 01, 02, 03, Aug–Sep 2024); [Patchwork](https://www.inkandswitch.com/patchwork/); [existing JADE DAG](../../mission-control/jade_temple/site/cicd_dag.html); [existing Plotly producer](../../mission-control/federation-atlas/mission_rebuild/w2_plotly.py).

## Deep-reading: what to reuse

- **01 — Universal version control.** Keep branch/head/attempt identity and current-versus-proposed review distinct. Jacquard is a research prototype, not a drop-in certified CI orchestration backend. Reuse GitHub's already-governed versioning and PR process.
- **02 — Provenance as map.** A chart or PDF should identify upstream inputs and the precise command/receipt that generated it. Jacquard's prototype infers a build graph from recorded provenance, with an optional watcher that runs shell commands. For this repo, *import the map idea, not an unrestricted watcher*: existing Actions/JADE/CREW remains the sole execution authority. Derivations feed a read-only explorer and staleness audit.
- **03 — Fine-grained source/output pointers.** Click a document/output region and find source, or navigate source→rendered result. Their initial LaTeX/PDF prototypes used SyncTeX; the authors document real imprecision issues. Source line and PDF rectangle identities are not interchangeable. Treat every mapping as a versioned, precision-labelled assertion.
- **Mirrored comments and version migration.** Anchor comments on source OID or a validated semantic object (RTM/KKS/table ID), then project into PDF/HTML; on source edit, invalidate unmapped anchors. Do not assign old page-number comments to a new PDF silently.
- **Multiple lenses:** topology, temporal jobs, source catalog, SIPOC and review status show *the same frozen evidence* without inventing parallel metrics or certification. Plotly remains the interactive chart engine where installed; standalone SVG/HTML stays the offline fallback.

## Provenance pointer contract (design)

A pointer may have these independent locations, each explicitly optional:

| Locator | Example | Precision | Safety |
| --- | --- | --- | --- |
| Source file | repository + 40-hex commit SHA + Git blob OID + path | FILE_ONLY | Links to immutable GitHub blob at snapshot SHA |
| Source lines / semantic object | path + validated line range, RTM-#### / KKS / section anchor | LINE / SEMANTIC | Requires source parser/owner manifest and drift check |
| GitHub workflow/run | workflow file + exact PR head SHA + run ID + attempt + job ID | RUN | Run success alone never implies release approval |
| HTML/SVG | generated artifact SHA256 + DOM ID or SVG element ID | ELEMENT | Verify existence at output digest before jumping |
| Plotly chart | artifact SHA256 + trace UID and point ID, not only numeric index | POINT | Rebind after trace regeneration, else UNKNOWN |
| PDF | output artifact SHA256 + page + normalized bbox + coordinate convention + optional text/object ID | RECT / APPROXIMATE | Never pretend PDF text or image parsing yields an exact mapping |
| PDF layer/view | output digest + named OCG/layer or SVG-equivalent overlay + page | LAYER | Only if checked against actual binary and owner layer inventory |

**Minimum safe mapping:** `{source:{repository,head_sha,blob_oid,path,locator}, output:{artifact_sha256,medium,locator}, relation, method, precision, evidence_class, observed_at, invalidated_by}`. A null means UNKNOWN, **never zero**. A source/OID change invalidates mapping until an explicit rebind/negative test. Inline editing is future work requiring a separate write-authority and source-to-rendered roundtrip contract.

## Existing assets to compose (avoid duplicate code)

| Canonical owner | This explorer's use | Boundary |
| --- | --- | --- |
| `jade_temple/tools/cicd_dag.py`, `site/build_cicd_dag.py` | Link to canonical FUNCTION / SHA / OID lenses | Do not edit generated `site/cicd_dag.html` or duplicate analytical metrics |
| `jade_temple/devops/workflows.py` | Source-bound workflow catalog, triggers and job `needs` DAG | This pilot's B00–B09 diagram is **logical design**, not the executable Actions graph |
| `jade_temple/devops/actions_metrics.py` | Run, queue and execution clocks | Eight selected samples are not a fleet baseline; no extrapolated success rates |
| `gogreen/required_gate/gate.py`, `ADMISSION.json` | Current enforcement owner | Do not rename check contexts or infer FPC/release authority |
| `federation-atlas/mission_rebuild/w2_plotly.py` | Optional Plotly HTML companion using the measured sample | No new independent metric computation |
| `docs/ci-spine/*.json` | Frozen indexes and logical graph already merged from PR #992 | source SHA `ca623ab83793df6edd245942884ad5428a5fe079`, **not** current master |
| PR #989 | README badges and branch custody | Badge = workflow signal, not certification |

## Pilot GUI contract

Standalone offline `explorer.html` built deterministically from the frozen evidence with no API calls or network requests. It offers a searchable 182-workflow catalog with *proposed* aliases, select-and-focus 10-bundle DAG, edge/evidence/temporal layers, keyboard and zoom, a 5-column SIPOC inspector, eight source-linked run/queue/step samples, DoD/DoV workstream navigation, shareable hash lens/selection, SVG export, and print-to-PDF. Exact heads, OIDs, run IDs and SHA status are visible in a right-side inspector; visual colors never create an admission status.

Expected user navigation: choose `B05 Browser` → view prerequisite paths → inspect the example workflow at **frozen** Git head → switch to measured browser job duration → open GitHub run → return via browser history. A PDF or engineering drawing anchor is deliberately **not fabricated**; no PDF is loaded in this pilot.

## Execution/checklist / DoD versus DoV

| ID | Work / intent | DoD (implemented capability) | DoV (independent proof) | Status |
| --- | --- | --- | --- | --- |
| JQ-00 | Foundation | PR #989 and #992 merged; source-bounded catalogs retained | Read back exact merge SHA and date | DONE (verified) |
| JQ-01 | GUI shell | Offline explorer, source badge, linked navigation, search, responsive/keyboard | deterministic generation; browser QA at 1440, 1280, 390; no unintended overflow | IN PROGRESS on separate branch |
| JQ-02 | DAG/SIPOC lenses | 10 bundles, 16 intra-pulse edges + 1 next-pulse feedback | no cycle/phantom PASS, all edges resolvable, feedback labelled | IN PROGRESS |
| JQ-03 | Runtime/receipt lens | eight real run/attempt/job/step samples; queue separate from duration | no invented metrics; view exact GitHub run and timestamp | IN PROGRESS |
| JQ-04 | Fine-grained anchor contract | typed source/output/precision model; visible unknowns | negative tests for stale SHA, wrong page/bbox, unmapped object | DESIGN ONLY |
| JQ-05 | PDF/SVG/Plotly bridge | optional offline Plotly view of existing measured run examples; future object→view pointers | Plotly exact-head CI; PDF/SVG geometry and output digest validation remain separate | PARTIAL PROTOTYPE (Plotly only) |
| JQ-06 | Mission Control fanout | scoped Read/DeepRead/Doctor provenance scouts using existing CREW roles | source receipts, false-positive review and independent DoV | PROPOSED; no scouts dispatched |
| JQ-07 | Admission & release | independent protected head checks and reviewer signoff | correct required checks/FPC, no compensation from green badge | HOLD |

**Stopping rules:** never dispatch shell from a read-only UI; never automatically accept an annotation as source authority; never merge a red or skipped required check; do not mark a source/output link EXACT until its persisted pointer is verified at exact binary hashes. Keep the original SVG/PDF/PPT/Plotly engines and their release receipts.

## Next pulse / future design

Pilot **read-only provenance at FILE / RUN granularity** first. Then add source-line/HTML-ID anchors as a separate PR, then real rendered PDF coordinates and SVG layer OIDs, then comment migration/roundtrip, then optional local-first Automerge collaboration. A Plotly companion should call the existing Plotly patterns (or import `plotly.graph_objects` solely as presentation) and embed JS offline when generating an external-facing artifact. The absence of a Plotly bundle in the portable HTML must not break navigation.
