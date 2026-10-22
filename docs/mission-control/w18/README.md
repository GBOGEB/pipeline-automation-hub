# CP-W18-FLEET-DOV-20261017 | one master, multiple verified communication surfaces

> **Authority boundary:** Read-only public-source projection. No issue mutation, waiver,
> independent A10/security approval, ruleset change, main merge, QPS engineering
> acceptance or replacement of the BD/REX SSOT. Pages is *not* declared published.

## Master, identity and source lineage

- Stable slug: `cp-w18-fleet-dov-20261017`.
- Only fact/value master for this package: [`snapshot.json`](snapshot.json), with
  immutable frozen observation time and documented non-atomic GitHub readback.
- `manifest.json` holds its SHA-256 and every generated rendition digest. This
  provides exact cross-rendition parity, not a digital signature or security review.
- Canonical control authorities are **MissionControl BD/REX #85**, fleet issue
  controller #153, hub projection #358, ABACUS admission #1860 and the existing
  `mission-control/v2/handoff` CP.CLOSE/CP.HANDOFF protocol.
- Fleet census [PR #663](https://github.com/GBOGEB/pipeline-automation-hub/pull/663)
  remains historical **152 open** at 18:11:56Z. Later GitHub searches returned
  **142 open**. This master preserves both observations; it does not edit or
  retimestamp #663's earlier 152-row evidence population.

## Consistent audience renditions and source binding

| Audience / use | Surface | Generator | Content identity |
|---|---|---|---|
| Mission Controller / executive | [`index.html`](index.html) | `render.py` + `runtime.js` | embedded master SHA |
| Root owners / BD triage | [`cards.html`](cards.html) | same generator | embedded same SHA; filterable leaf cards |
| Meeting chair / review board | [`deck.html`](deck.html) | same generator | embedded same SHA; six keyboard/navigator slides and print mode |
| Excel, Power BI, telemetry ingestion | [`metrics.csv`](metrics.csv) | same generator | same six named KPI families, explicit empty UNKNOWN fields |
| Standalone PowerPoint handout | `CP_W18_FLEET_DOV_20261017.pptx` | `build_deck.js` reads same JSON | same SHA in speaker notes; 8 rendered slides |

The **PPTX is a local downloadable candidate**, not committed as an unreviewed
binary into public GitHub. It may be regenerated using `node` with `pptxgenjs`
installed and the PPTX helper library configured as `PPTXGENJS_HELPERS`.

GitHub source paths under `docs/mission-control/w18/` are *reviewed-source
candidates* until PR merge. The likely Pages path would be
`https://gbogeb.github.io/pipeline-automation-hub/mission-control/w18/`,
but **no HTTP 200, exact content hash or deployment claim exists** for this path.
Do not present that proposed URL as currently published.

## Rebuild and verify

```bash
cd docs/mission-control/w18
python render.py
python -m unittest discover -s tests -v
python tests/browser_qa.py
# Optional with PptxGenJS + accessible helper library:
PPTXGENJS_HELPERS=/path/to/pptxgenjs_helpers node build_deck.js /tmp/CP_W18_FLEET_DOV_20261017.pptx
```

`browser_qa.py` uses Chromium from `/usr/bin/chromium`; adjust the executable
path on other machines. It uses Playwright `page.set_content`, so no live
external network is required. The online dashboard may optionally load Plotly
2.35.2 from its pinned CDN; an equivalent static SVG fallback provides offline
chart access with bounded Y axis and honest two-point provenance.

**Build invariants:** master cardinality and denominator checks; mismatch
fails closed; 11 ticket reductions = 9 duplicates + 2 work-item completions;
no root closure inferred; N14(200/446) and W16(231/444) never scored as a
matched same-source growth slope; current B9 changed-line eligible population
remains UNKNOWN; queue p95 and original full-chat prompts are null, not zero;
PCA, Bradley-Terry and Six Sigma capability are NOT QUALIFIED.

## Measured work and present DOD/DOV

- **Session DOD**: 3/8 verified tasks (fleet issue census, closure classification,
  separate B0/B9/current-epoch first-red attribution). Two further
  implementation/candidate tasks, security owner HOLD, CI HOLD and Pages TODO.
  This is a workflow deliverable count, not global programme completion.
- **Global DOV**: **2 PASS / 3 PARTIAL / 3 HOLD** across eight independent
  verification domains; explicitly non-compensating, not a weighted average.
- **Issues**: 153 -> 142 (observed net -11); this controller did not execute the
  nine duplicate or two worker-closure mutations. *Formal root closures credited
  by this controller = 0*. The number of distinct fleet-wide remaining roots
  is UNKNOWN because deduplication is not complete.
- **W16**: native 157 passing tests at exact head
  `e7195fe5588514f65891ddb8181725b9325fe19d`;
  231/444 branch obligations (52.03%); Phase 8 identical source blob
  30 -> 63 of 118 (+33); separate Python 3.12 five-file 336/560 (60%).
- **N+1 native blockers**: Python 3.10 TOML first-red had a candidate repair
  on #2156 but no successor-head native runs returned; Python requirements
  PR #2161 has four specifier-string test assertion failures per job; Ariana
  `defusedxml` is missing at collection on PR #2164. A10 independent human
  disposition and protected-main governance remain separate.

## Telemetry, uncertainty and decision boundaries

Six tracked core KPI families are fleet issue burndown, frozen branch reach,
matched terminal proof yield, verified root closure, queue/run time and
statistical CONTROL. All have source references, optional numerator and
*explicit denominator*. Only data-supported metrics contain numbers.

A fleet issue count is not a first-red count; a first-red manifestation is
not one independent causal root; a passed B0 is not B9 >=80% changed-line
admission; a preliminary static/dashboard page is not a deployed Pages URL;
queue p95 needs actual job timestamps; six-sigma DPMO needs a defined
opportunity denominator; PCA and BT need qualified independent measurement
populations and pair comparisons, respectively.

## Next bounded G3P envelope

**N+1:** owner adjudicates A10, frozen-head rerun for `coverage[toml]` W16 and
Python marker assertion repair. **N+2:** source-own Ariana `defusedxml`
collection under one disjoint root, then retest ABACUS B0 and dashboard
populations. **N+3:** current-main governance and B9 changed-line matched
proof, plus independent repetitions and queue p95 before CONTROL promotion.
One confirmed global blocker stops later slots, recorded as `NOT_RUN`, never
implicit success. Recheck the latest PR heads before any source action.

## Maintained evidence sources

- [Global controller #153](https://github.com/GBOGEB/pipeline-automation-hub/issues/153),
  [BD/REX #85](https://github.com/GBOGEB/pipeline-automation-hub/issues/85),
  [local BD queue #358](https://github.com/GBOGEB/pipeline-automation-hub/issues/358)
- [ABACUS W16 #2156](https://github.com/GBOGEB/ABACUS/pull/2156),
  [Python matrix #2161](https://github.com/GBOGEB/ABACUS/pull/2161),
  [dashboard #2164](https://github.com/GBOGEB/ABACUS/pull/2164)
- [A10 #1996](https://github.com/GBOGEB/ABACUS/issues/1996),
  [main governance #2087](https://github.com/GBOGEB/ABACUS/issues/2087),
  [B9 coverage #1866](https://github.com/GBOGEB/ABACUS/issues/1866),
  [gg_MATH runtime #27](https://github.com/GBOGEB/gg_MATH/issues/27)

## V2 follow-up: actionable register and screenshot-free DevOps location hooks

The original frozen `snapshot.json` and its SHA-256 remain **unchanged**. This is a view/navigation extension, not a reclassification or merge gate. The dashboard's formerly external-only “Open global BD register” now opens `cards.html#bd-register` (the eight W18 BD leaves), while keeping a separate direct link to canonical GitHub #153. The dashboard adds a `Recursive TODO` view that preserves W17's 24/3/10 readback, source-epoch 231/444 + Phase8 +33, 153→143→142 census sequence, and the root dependency trail #153→#85→#358→source-owner issues.

Interactive dashboard, leaf cards, HTML deck and diagram nodes support a **DevOps hooks: ON/OFF** toggle. Click the context-specific “Comment / copy” button to receive a stable `CP-W18/<view>/<key>` ID, shareable relative route (hosted URL not yet verified), source digest and GitHub PR/issue. It drafts (but does **not** send) a comment. Copy its Markdown, open the selected issue and paste manually. No authentication tokens, write APIs, screenshots, global memory or storage are needed. Use `locator_index.json` for deterministic navigation without the graphical interface. See `RECURSIVE_W17_W18_FOCUS.md` for the recursive W17→W18 TODO/BD continuity protocol.

Rebuild and verify:

```sh
python render.py
python -m unittest discover -s tests -v
python tests/browser_qa.py
python devops_browser_qa.py
```

The browser environment may restrict localhost or `file://` cross-page navigation. Browser QA therefore verifies the generated relative link destinations statically, loads each self-contained rendition offline, and separately exercises its fragment/deep-link logic; this is **not** a hosted GitHub Pages HTTP-200 acceptance claim. Clipboard tests use an explicit mocked browser clipboard and exercise generated comment text and the direct user action. System clipboard interoperability remains client/browser dependent; the comment text is selectable for manual copy.

The old eight-slide PowerPoint remains a static presentation from the same frozen master; the DevOps toggle is **HTML-only**. To annotate a PowerPoint-specific visual, reference its corresponding `deck.html#slide-XX` locator in the GitHub issue comment.
