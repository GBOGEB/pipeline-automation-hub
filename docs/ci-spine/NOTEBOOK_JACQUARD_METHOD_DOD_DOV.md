# CI Spine × Jacquard notebook — execution checklist, DoD/DoV and controlled frontier

> **Status:** source-bound, read-only experimental review UI. No Jacquard code is copied. No new authoritative source model, metrics kernel, scheduler, release controller, PDF editor or publisher.
>
> **Branch:** `feat/ci-spine-jacquard-provenance-explorer-20261029` · **draft PR:** [#1017](https://github.com/GBOGEB/pipeline-automation-hub/pull/1017).
>
> **Starting platform:** merged badges [#989](https://github.com/GBOGEB/pipeline-automation-hub/pull/989), merged CI index/bundle model [#992](https://github.com/GBOGEB/pipeline-automation-hub/pull/992). Exact starting master checkout: `83a4afecdad5ed41677591922c8f239316a8f638`. Historic *model* source SHA inside the B00–B09 JSON remains `ca623ab83793df6edd245942884ad5428a5fe079`; that is an earlier data snapshot, **not** the current branch/PR head.

## 1. Readout — the Jacquard research, rather than a product dependency

Jacquard's public lab notebook has three core posts (6 Aug, 14 Aug and 18 Sep 2024): **version control and provenance**, **tracking provenance** and **fine-grained provenance**.

[Jacquard notebook](https://www.inkandswitch.com/jacquard/notebook/) · [Project page](https://www.inkandswitch.com/project/jacquard/) · [Patchwork](https://www.inkandswitch.com/project/patchwork/).

| Jacquard idea | Valuable transplant | Existing Hub owner / boundary | Implemented in this PR |
| --- | --- | --- | --- |
| Build graph as navigation | Navigate *why* a chart, CI gate or document exists and which inputs it depends on | JADE `cicd_dag.py`, `workflows.py`, GOGREEN and owner DAGs | Ten bundled conceptual DAG nodes / searchable source-linked view; no new source graph owner |
| Implicit build traces | Discover provenance from actual derivation rather than duplicating Makefile definitions | GitHub run/job/attempt and existing provenance receipts; **declared authority still dominates inferred data** | Frozen exact-run timing samples with distinct source SHA, source/time labels; no live watcher |
| Source ↔ output pointers | Anchor a meaningful rendered region to precise source content | B00–B09 JSON plus renderer; GitHub source blob at a frozen ref | Exact JSON Pointer `/nodes/i` ↔ `#bundle=Bxx` and HTML document region, with source-line links |
| Mirrored comments | Keep review remarks attached to source as generated layouts change | Existing W18 DevOps location hooks, GitHub PR comments | Review/copy pointer only; no direct editing or mirror-comment write |
| Branch/draft layers | Show proposed changes without replacing approved version | GitHub PR stacks, reviews, FPC, branch hygiene | Clearly stamped `PROPOSED_DESIGN`; future diff lens separately owned |
| PDF editing and SyncTeX | Source→PDF page/box mapping for LaTeX, copy context across media | Future PDF bridge, not this notebook; engine-specific accuracy required | `pdf_location_mapping=UNAVAILABLE`, no fake PDF highlight or write operations |
| Local-first collaborative task workers | Potential discovery/branch-proposal approach for MC scouts | Existing CREW, GitHub Actions, authorized worker policy | Not adopted; no background process or privileged watcher |

Jacquard's watcher invokes commands from a collaboration interface. **Do not copy that privilege boundary into a read-only published GitHub Pages surface.** Any future execution request must return to a separately authorized source-owned queue, repo rules, exact-head receipts and reviewer approvals. Jacquard's paper-like preview should be treated as a usability approach, not as a certification or evidence substitute.

### The crucial distinction: two different graphs

1. **Declared, governed execution DAG**: the GitHub workflow jobs, explicit `needs`, source owners and release policy. This remains authoritative and fail closed.
2. **Observed provenance graph**: records how a specific artifact was produced, what has changed or which references appear stale. It can enrich navigation and recommend rebuilds, but cannot alter the execution authority DAG.

Never silently collapse both into one graph or interpret a source-mapped view as a passing test.

## 2. Source → HTML → PDF/SVG/PPT/Plotly: common pointer strategy

Current proof is real for JSON member ↔ HTML region. Future format adapters require format-specific producer receipts:

| Format | Proposed coordinate/identity | Existing path / upstream | Current truth |
| --- | --- | --- | --- |
| JSON / Python / YAML | Stable logical object ID + JSON Pointer or source line span, exact source SHA256 | CI Spine models, JADE owner modules | JSON member ↔ HTML region **implemented** |
| HTML | Semantic element ID + source ref; screenshot/viewport is presentation metadata | This notebook, existing W18 and JADE page builders | Implemented locally, browser DoV required |
| SVG | Stable element `id`, transform/viewBox and source object OID | Existing SVG/DAG layering and Mission Control renders | Architecture candidate; no new SVG element crosswalk claimed |
| Plotly HTML | `customdata` / stable `ids` for click-to-source, source-bound Plotly JSON | `mission-control/federation-atlas/mission_rebuild/w2_plotly.py`, canonical gg_MATH | Candidate bridge, not rewritten here |
| PDF from TeX | SyncTeX path+line ↔ page and point/box; correct crop/rotation/scale | LaTeX/SyncTeX; evaluate PDF.js for view/annotation | **NOT_IMPLEMENTED** in this PR |
| PDF from office/PPT/SVG | Build-time map of source object ID to output page and normalized bbox; source digest and precision class | Existing document/PID/QPS render engines, future adapter | **UNKNOWN**, do not infer from OCR alone |
| Optional-content PDF layers | PDF OCGs for named visibility layers, plus independent source references | Adobe PDF Optional Content Groups, PDF.js optional content configuration | Research only; no OCG output claimed |

A format-neutral candidate `source→render` pointer should include:
```json
{
  "schema": "ci-spine.provenance-anchor.proposed.v1",
  "source": {
    "repository": "GBOGEB/pipeline-automation-hub",
    "ref_sha": "83a4afecdad5ed41677591922c8f239316a8f638",
    "path": "docs/ci-spine/LOGICAL_BUNDLE_DAG_v1.json",
    "pointer": "/nodes/7",
    "source_sha256": "<digest from authoritative build receipt>"
  },
  "rendered": {
    "format": "html",
    "anchor": "bundle=B07",
    "view_sha256": "<digest of generated HTML>"
  },
  "pdf_mapping": null,
  "precision": "EXACT_JSON_MEMBER_HTML_ANCHOR",
  "authority_transfer": false
}
```
The placeholder digests above are intentionally **not** fabricated hashes. The actual HTML payload contains its input SHA-256 digests; the browser receipt separately hashes its view. A future PDF region requires a real `{page, box, coordinate_system, transform, mapping_algorithm, confidence, artifact_sha256}` record before it may be clickable as an exact source link.

**Source-first comments:** Review annotations belong primarily to a stable source object or logical object ID, with document bbox only as a derived visual anchor. On regeneration, resolve against the new source map; if ambiguous, show `UNRESOLVED` for review, never silently move a comment to a guessed box.

Reference implementations: [SyncTeX forward/backward mappings](https://go-synctex.github.io/docs/latest/api/), [PDF.js display/viewer layers](https://github.com/mozilla/pdf.js/blob/master/docs/contents/getting_started/index.md), [Adobe OCG layers](https://developer.adobe.com/acrobat-pdfl-sdk/guides/overview/overview-metadata), [Plotly customdata/ids](https://plotly.github.io/schema-viewer/).

## 3. Committed implementation inventory

| Asset | Purpose | Role |
| --- | --- | --- |
| `scripts/ci_spine_notebook.py` | Validate frozen B00–B09 + job samples, source digests, pointer locations, governance; deterministic HTML build/check | Derived projection, not metric owner |
| `docs/ci-spine/notebook.template.html` | Accessible, responsive and offline UI; Graph/SIPOC/Clocks/Document/Compendium lenses; zoom, search, deep links, inspector | User-facing UI template |
| `docs/ci-spine/notebook.html` | Generated, embedded-JSON standalone review surface, works under `file://` | Bounded static view |
| `tests/test_ci_spine_notebook.py` | 17 source/graph/HTML negative and positive methods | CI offline DoV |
| `scripts/ci_spine_notebook_browser.py` | Real Chromium 1440×1000 / 1280×800 / 390×844 tests and screenshots | Native browser DoV |
| `.github/workflows/ci-spine-governed-qa.yml` | Existing exact-head CI workflow extended with offline parity and disjoint browser QA after `needs: offline` | Existing CI owner, not new workflow |
| `qa/ci_spine/receipt.json` + screenshots | Runtime only: exact run/head, 3 viewport assertions, offline/console errors, HTML digest | Generated CI artifact, not committed |

The view contains *historical observed run/job samples*, not a fleet histogram or current 7-day KPI. Live metrics remain with `actions_metrics.py`; failure roots with `scale_dock.py`. The graph itself comes from `LOGICAL_BUNDLE_DAG_v1.json`, not a second algorithm.

## 4. DoD (definition of done) and DoV (definition of verification)

| Item | DoD expectation | DoV source / acceptance | State |
| --- | --- | --- | --- |
| D01 Baseline | #989/#992 merged; exact master recorded | GitHub PR API and commit SHA | DONE |
| D02 Ownership | One source for DAG, metrics, CI and HTML display | AGENTS.md L4, source links, no duplicate metric owner | DONE (implementation review pending) |
| D03 Schema | 10 bundles, 17 edges with one next-pulse return | Source-validated graph and 17 negative/positive tests | Implemented; terminal CI to attest exact head |
| D04 Provenance | Source SHA, blob/source pointer, HTML anchor, input hash and read-only classification | `--check`, pinned-source links and deep-link browser assertion | Implemented; browser DoV pending |
| D05 GUI | Five lenses, search, selected source, zoom and keyboard, 3 responsive widths | Native Chromium screenshots and DOM assertions | Implemented; browser DoV pending |
| D06 Security | 0 external JS / data network requests; output escaped; no arbitrary code execution | Negative tests + intercepted network and console errors | Implemented; browser DoV pending |
| D07 PDF honesty | No synthetic PDF page/bbox or source edit authority | Explicit `pdf_location_mapping=UNAVAILABLE` and negative tests | Implemented |
| D08 Plotly reuse | Link to existing numerical owner rather than rewrite it | Code/link review; no duplicate metrics | Implemented |
| D09 Reproducibility | Deterministic build, output matches original inputs | `python scripts/ci_spine_notebook.py --check` on exact head | CI receipt pending |
| D10 Governance | No merge, deployment, policy downgrade, bypass or branch deletion | Required checks and independent review at exact PR head | HOLD |
| D11 Publication | Existing Pages publisher opts in after qualified review; served SHA/digest readback | Separate Pages/source owner receipt and visual QA | NOT REQUESTED |
| D12 PDF bridge | Real engine-derived line/box map and reverse selection with precision diagnostics | Separate tested adapter on real document, browser comparison, no fabricated mapping | FUTURE |

### Negative/failure cases that must remain red

- Duplicate/dangling graph objects, a same-pulse cycle or a spurious in-pulse feedback.
- Unlisted/replaced source member, stale JSON hash, invalid source SHA, invalid run/job clock.
- Unsafe path and injected HTML/script inside source fields.
- Claim of `ACCEPTED`, `PDF_GEOMETRY_PROVEN` or any release authority through view JSON alone.
- Browser errors, attempted external requests, broken hash navigation, keyboard failure, unintended horizontal page overflow.
- An incomplete required CI result or missing independent review, regardless of badge color.

## 5. Continuation / branch-stack status and BD queue

| Order | Work item | State | Controlled next action |
| --- | --- | --- | --- |
| P0 | #989 badges foundation | MERGED | Read-only reference; don't re-open or reimplement |
| P0 | #992 182-workflow + B00–B09 index | MERGED | Consume frozen contracts; future index refresh through original owner |
| N+1 | #1017 Jacquard notebook proof | DRAFT / DOV | Current exact-head native offline + browser QA, screenshot/receipt, independent review, keep HOLD |
| N+2 | Plotly point → source pointer | NOT STARTED | Separate disjoint source owner PR: add stable `ids`/`customdata` and click-to-source crosswalk only after source-bound fixture |
| N+2 | PDF from LaTeX / SyncTeX bridge | NOT STARTED | Compare source mapping quality, test rectangles and full rotation/scale/crop; no dependency additions to CI spine first |
| N+3 | PDF/SVG/PPT object ID bridge | NOT STARTED | QPS/publisher-owned adapter and exact transform receipts; preserve engineering document SSOT |
| N+3 | Comments/draft layers | NOT STARTED | Consume existing W18 location hook + GitHub PR metadata; no direct write from published page |
| N+4 | Cross-format parity / regeneration | NOT STARTED | Align source SHA256, artifact digest, visual QA; separate CODEX/Pages publisher controls |
| CONTROL | 1/7/14/30-day regression checkpoints | NOT SCHEDULED | Review receipt freshness, source drift, broken anchors, first-red recurrence, job minutes and duplicate owner metrics |

**Temporal hooks:** A frozen HTML page cannot self-poll. If source versions change, regenerate and verify the same canonical input file before replacing a published view. No monitoring task or scout was launched by creating this documentation.

## 6. Local reviewer/test commands

```sh
python -m unittest discover -s tests -p 'test_ci_spine_*.py' -v
python scripts/ci_spine_notebook.py --check
python scripts/ci_spine_index.py --check --source-sha "$(git rev-parse HEAD)" --out ci-spine-index.json
# The next command requires the pinned playwright==1.56.0 + installed Chromium:
python scripts/ci_spine_notebook_browser.py
```

The rendered page is `docs/ci-spine/notebook.html`; open it locally as a file. GitHub's blob page displays HTML source, not a rendered preview. No separate Pages deployment is made here. The browser screenshot/receipt family is retained as an Actions artifact, not as a claim that a future site is already published.

**Disposition:** `IMPLEMENTED_CANDIDATE / SOURCE_BOUND / NATIVE_DOV_PENDING / MERGE_ADMISSION_HOLD`.
