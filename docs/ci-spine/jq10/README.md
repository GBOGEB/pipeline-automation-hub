# JQ10 — cross-media source-object contract and repository adapter boundary

> **STATUS: DRAFT / SOURCE-SAFE METHOD ONLY / RELEASE HOLD.** This directory introduces a candidate interface, not a new renderer or source authority. No private binaries, personal paths, QPS contract text, generated user-data PDF or native-source hashes are committed here.

## 1. Starting platform and overlap

- Read-only semantic viewpoint is inherited from merged #989 (README badges), #992 (CI suite index), #1002 (Jacquard explorer), #1017 (notebook) and #1018 (JQ04 three exact source-to-view pointers).
- **JQ04 canonical owner:** `docs/ci-spine/pointers/pointer_contract.py`. Do not fork its source/OID matching, selector dispatch or the HTML explorer.
- **JQ08 separate live PR #1239:** Plotly trace/point customdata, point-to-source links and digest receipts. No competing Plotly code here.
- **JQ09 separate live PR #1249:** real SVG element/group IDs and native geometry. No competing SVG code here.
- **Golden Thread:** `mission-control/golden-thread/office_semantic_carrier.py` already carries semantic digests inside DOCX/XLSX/PPTX; do not reproduce it.
- **Native specialist owners:** ABACUS (Office semantics), MINERVA_PID (drawing layer/group parsing), DOCX_RTM_Automation (RTM/Word source), cryoplant-project (restricted owner acceptance). This contract is a hand-off surface, not ownership transfer.

## 2. Single contract, distinct locators

`MEDIA_SOURCE_VIEW_CONTRACT_v0.json` documents the candidate record shape and fail-closed rules. It is an **example grammar**, not a finalized JSON Schema or evidence registry. No object is automatically verified merely because it can be expressed in this structure.

| Common identity | Native input locator | Output/view locator | Admissible status |
| --- | --- | --- | --- |
| Source revision + file SHA-256 | DOCX bookmark, paragraph or RTM ID | HTML anchor or source PDF page | Unmapped until producer receipt |
| Source revision + OOXML part identity | PPTX slide / cNvPr shape / group ancestry | SVG element, PDF rectangle | Geometry candidate only until cross-format validation |
| Source revision + vector source hash | SVG element ID / transform / viewBox | HTML/SVG element, Plotly point | Native IDs and view selection can be verified separately |
| Output PDF SHA-256 + page box convention | PDF native span/rectangle/OCG xref | PDF.js rendered layer/page | Navigation only; not an upstream Office/DOCX binding |
| Source model + immutable chart digest | Plotly trace UID + stable point ID | Linked inspector/selection | JQ08 owner verification required |

A PDF OCG can control **visibility**, not provenance. A PDF with zero OCGs may still contain thousands of linework primitives and multiple visual systems. Likewise, a PPTX native group is not a PDF OCG and a DOCX bookmark count is not the number of unique RTMs.

### Separate evidence graph from execution graph

`source custody → native reader → typed object selector → producer map → view projection → QA receipt → owner disposition`

All edges are typed. A `SOURCE_RENDER_VERIFIED` claim needs two exact binary digests, source object identity, render object identity, build/provenance receipt, layout transform and adversarial mismatch controls. `UNKNOWN`, `UNMAPPED` and stale refs may not be silently promoted. The existing GitHub/JADE/GOGREEN DAG, check identities and rulesets remain authoritative for CI and merge.

## 3. Local mixed-format pilot — privacy-safe status (13 November 2026)

A **separate private local** read-only skill pilot used five older accessible binary specimens across PDF, PPTX and DOCX, plus five recent indexed-only references whose original bytes could not be materialized in the current session. It confirmed five native file SHA-256s and 120 sample native locators; the output remained `CROSS_MEDIA_UNMAPPED`. The generic pilot exercised 18 synthetic negative/positive tests, three Chromium viewports and a separate offline Plotly companion; the corresponding full files/receipts stay in user-private handover, **not** this repository.

No user-supplied contract, drawing, source digest, confidential title, PDF content, screenshot or derived user-data artifact is included in this PR. Those byte-level numbers do not qualify cross-media precision or engineering acceptance.

## 4. Skill strategy

The reusable `cross-media-source-map` Skill is the **read-only orchestration** unit: discover physically accessible source bytes, classify `INDEX_ONLY_NO_BYTES` separately, call existing format-specific readers, issue hashes and native selectors, render a local exploratory atlas, and fail closed on missing source/false linkage. It is distributed separately as a validated skill package, not copied into Hub as a second semantic engine.

Compose:
1. **JADE OG5 artifact router** for initial MASTER_INPUT type/topic inventory;
2. **cross-media-source-map** for bounded native locator + dashboard + QA receipts;
3. **source-owner specialist** (DOCX_RTM_Automation, ABACUS, MINERVA_PID, QPS) for true RTM/KKS/shape genealogy and engineering authority;
4. **JQ04/JQ08/JQ09** for approved linked view selectors and branch-specific acceptance.

## 5. Chaperoned DoD / DoV

| ID | Goal | DoD | DoV | Status |
| --- | --- | --- | --- | --- |
| JQ10-01 | Inspect owners and overlap | Existing modules and PR lanes listed | Exact default-head + PR readback | DONE for current baseline |
| JQ10-02 | Common semantic contract | Typed source, render, relation, annotation, visibility, revision schema candidate | Independent source-owner review | CANDIDATE |
| JQ10-03 | Private local native pilot | File digests, 120 sample locators, 18 adverse controls | Source-byte reread + 3 viewport browser proof | LOCAL PASS; NOT PORTABLE RELEASE |
| JQ10-04 | JQ08 Plotly | Stable point IDs and chart mapping | Separate PR #1239 exact-head CI/review | SEPARATE / HOLD |
| JQ10-05 | JQ09 SVG | Stable SVG IDs, group hierarchy, source-bound HTML | Separate PR #1249 exact-head CI/review | SEPARATE / HOLD |
| JQ10-06 | PDF/OCG source link | Real owner PDF, normalized geometry, actual OCG inventory and producer correspondence | Independent positive/negative cross-render maps | BLOCKED; NO FALSE CLAIM |
| JQ10-07 | Review annotations | Comment anchored to source ID; derived projections invalidated on source edit | Migrate/rebind negative tests + permission contract | DESIGN ONLY |
| JQ10-08 | Release | Exact-head mandatory CI, eligible independent review, source-owner signoff | No RED waiver, no skipped required check | HOLD |

## 6. Next bounded implementation

The first production-grade candidate should be **one source-owned Word/RTM object + its generated PDF**, not the entire heavy drawing: capture native RTM/bookmark identity, authored output PDF page/normalized rectangle and both digests from the same build, prove forward/backward navigation and five adversarial changes (source reflow, wrong page, changed output hash, missing object and ambiguous same-text match). In parallel, leave drawing group/L0D clustering with MINERVA_PID and Plotly point links with #1239.

**Do not dispatch a watcher, mutate a binary, auto-post a comment, publish private source content or merge any PR from a reader/viewer.** Revision and approval are separate owned operations.
