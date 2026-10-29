# JQ-04 — precise claims for source-to-view pointers

> **Stack:** #989 (MERGED) + #992 (MERGED) → [#1002 parent: offline Jacquard-inspired explorer](https://github.com/GBOGEB/pipeline-automation-hub/pull/1002) → **this focused child**. No changes to master, PR protection, admission rules, workflow names, code-generation engines, or PDF sources.
>
> **Status:** IMPLEMENTED CANDIDATE / NATIVE DoV PENDING / independent approval HOLD. Distinct from the source catalog SHA `ca623ab83793df6edd245942884ad5428a5fe079`.

## What is real, rather than inferred?

- [`POINTER_MAP_v1.json`](POINTER_MAP_v1.json) has **three candidate** source-object → offline-view pointers: logical DAG B05 to graph selection, B05 to its SIPOC view, and the source-bound sampled run `40690663789` to its run-clock view.
- Both original **source files** are bound to Git blob OIDs at **parent #1002 head** `4cc045d322fb65fef8fb00b2cd93e50bbc52bbd8`. The explorer **HTML binary** is independently bound to Git blob OID and SHA-256 `a7cbae8da2753404241b99a50f999f3f7526f111c30e86c102025d81aa283e0c`, observed by exact-head generator and Chromium QA in Actions run [40726398983](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/40726398983).
- The selected JSON pointers (`/nodes/5` and `/runs/0`) are checked against actual semantic identifiers, not just guessed coordinates. Their output URL hashes are checked against the existing `explorer.html` router and DOM container IDs.
- [`index.html`](index.html) is a small, **offline, zero-script, source-to-view navigation companion** with three real clickable routes and disclosed provenance. It complements #1002's five-lens GUI; it does not fork the graph/layout or recompute metrics.
- The **PDF/OCG/page/bbox** placeholder is `UNMAPPED_NO_VERIFIED_BINARY`. There is **no PDF link** and no claim of a working PDF-layer or per-rectangle mapping. The first PDF pilot needs actual owner binaries, a source mapping, normalized coordinate convention, digest, page-range checks and independent visual DoV.

## Executable contract and negative-first proof

```bash
python docs/ci-spine/pointers/test_pointer_contract.py
python docs/ci-spine/pointers/pointer_contract.py --out /tmp/ci-spine-pointer-receipt.json
```

The existing #1002 path-scoped workflow `test(ci-spine): provenance explorer QA` is extended **in its existing static job**, not by creating a new runner or replacing any gate. It retains its original 20-test explorer QA, browser DoV and Plotly proof, adds **25 pointer tests**, checks the nonzero executed-test count, and uploads a candidate pointer receipt. Tested failure modes: wrong source SHA/blob, mutated HTML binary SHA/digest, invalid or dangling JSON pointer, object/selection mismatch, external URL, wrong hash route, missing DOM anchor, fake PDF rectangle/OCG link, duplicated pointer, external script and misleading green/authority assertions.

Receipt values:
- `verdict=SOURCE_BOUND_VIEW_SELECTION_ONLY`;
- `mapped=3` (only after validation), `unknown_pdf_pointers=1`;
- `pdf_rectangles_verified=0`;
- `merge_authorized=false`.

The immutable **view binary is parent #1002's exact head**. When the parent explorer changes, this pilot must rebind its SHA-256 and blob OID from a newly verified build before it can qualify again. No automatic rebinding or fabricated mapping to newer PDFs.

## Chaperone: DoD / DoV / next step by workstream

| ID | Purpose | Definition of Done | Definition of Verification | State |
| --- | --- | --- | --- | --- |
| JQ-00 | Baseline | #989 and #992 merged | GitHub exact merge readback | DONE |
| JQ-01 | Existing GUI | Five-lens offline explorer, search, zoom, SVG export, linked results | [#1002] native 20 tests, Chromium viewports, zero external requests | HOSTED PASS on parent head; CodeQL/FPC still HOLD |
| JQ-02 | Logical DAG/SIPOC | Ten bundles, 17 edges, typed N+1 feedback | Existing deterministic/cycle/phantom-negative tests | HOSTED PASS on parent head, no live-authority upgrade |
| JQ-03 | Runtime | Eight sampled run/queue/step receipts | Exact run/attempt and immutable test assertions | HOSTED PASS on parent head; not fleet statistics |
| **JQ-04** | **Typed pointers** | 3 source-bound HTML view selections + no-fake-PDF marker | 25 negative and positive controls, exact SHA/HTML OIDs, offline nav, existing static CI | **IMPLEMENTED CANDIDATE → NATIVE DoV PENDING** |
| JQ-05 | PDF/Plotly | Plotly companion; PDF/OCG pointer model separate | Existing Plotly passed; no live PDF binary map | PLOTLY PASS; PDF UNMAPPED |
| JQ-06 | Scouts | Research Jacquard, Patchwork, SyncTeX, FileWeaver, Automerge/CRDT | Compare source/license/version, overlap, security and test costs | RESEARCH ONLY, no worker dispatch |
| JQ-07 | Governance | Exact-head CI, required checks/FPC and eligible independent review | Qualified source/receipt set + security review, no red waiver | HOLD |


## JQ-04b — native comparison layers, additive child-branch iteration

Added a **script-free three-stage disclosure** to the existing pointer atlas, preserving the three manifest-bound navigation actions and the original source/view hashes. A reviewer can expand: (1) the frozen B05 source identity; (2) graph and SIPOC selections on the parent explorer; (3) the explicit **UNMAPPED** PDF/OCG boundary, which has no link and grants no false precision. This is a complementary reading surface, not a new metric owner, live dashboard or PDF conversion.

New local controls cover the three native details panels, unchanged no-script CSP, and absence of a publication link. The existing Chromium QA exercises both graph/SIPOC and unknown-publication disclosures at 1440 and 390 px, alongside the original three exact pointer routes. No output viewer bytes, pointer source OIDs, or stored target SHA-256s were changed by this iteration. CI is requalified at the **new child PR head**; prior green receipts do not transfer.

**Chaperone stop:** JQ-04b does not promote JQ-04 or JQ-05 to engineering acceptance. Parent #1002 security / review first reds and its children #1019/#1021 remain separate; a parent rebuild must rebind #1018's viewer digest before admitting pointer evidence. Review/merge admission HOLD.

## Why Jacquard is relevant, but not directly imported

Ink & Switch's [Jacquard entries 01–03](https://www.inkandswitch.com/jacquard/notebook/) explore provenance as a navigation map, source↔compiled-document pointers, synchronized scrolling, mirrored comments and inline source editing from PDFs. Their authors also warn that SyncTeX mappings can be imprecise. Existing GitHub + JADE DAG + Mission Control renderers remain the authoritative infrastructure here. A future PDF mapping must include a real **page/normalized bbox/OCG** and **exact output binary digest**; matching a legend label or a similar-looking drawing is insufficient.

### Follow-through gates

1. **Parent #1002:** resolve CodeQL first red, qualify First-Pass Closure (skipped on inspected head), independently review. `merge_admission=HOLD` regardless of existing passing static/browser/Plotly checks.
2. **Child JQ-04:** run the new 22-test suite on an exact branch head, inspect log/receipt and linked UI, verify that intentional wrong input fails. No status context renaming.
3. **Controlled change of viewer:** after parent #1002 changes, regenerate exact HTML, obtain new SHA-256 and blob OID from the same head, then rebind this map and rerun tests. Old link remains historical, not live.
4. **Further branch (separate):** one physically provided owner PDF + explicit source-to-rect mapping, failure cases for re-pagination, wrong OCG, coordinate transform, missing PDF, drift and misleading mirrored comments. Avoid introducing arbitrary file watchers or shell execution into the HTML GUI.
