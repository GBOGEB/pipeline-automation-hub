# CODE PURPLE · Federated HTML QA — governed operator kit

**Mission:** `GBOGEB/pipeline-automation-hub#604` · **pilot:** G3P Live Ledger · **authority:** existing `code-purple-method-atlas.yml` + `pages_portal.py`.

HTML/SVG is a **read-only projection**. Neither passing screenshot comparisons nor working hyperlinks establish native CI success, data source truth, protected merge acceptance, causal-root closure or QPS engineering compliance.

## Provenance ladder

| Level | Required observations | Meaning |
|---|---|---|
| `STATIC_SOURCE` | title/H1/viewport, links, safe protocols, local assets, duplicate IDs, semantic controls | Can build and inspect a page |
| `BROWSER_FIXTURE` | Chromium desktop/laptop/mobile on actual ledger bytes with controlled HTTP responses; click, keyboard, refresh, negative responses, 0 JS errors; screenshots | Visual interaction passed on recorded sources, NOT live network |
| `EXACT_HEAD` | Native Actions check tests exactly PR head; receipt binds `git rev-parse HEAD`, SHA256 artifacts and browser screenshots | Reproducible PR-head QA, still not hosted |
| `PAGES_CANDIDATE` | Existing single-owner `pages_portal.py` outputs `g3p/index.html`, manifest and site-hash ledger | Approved packaging candidate, NOT website proof |
| `PAGES_HOSTED` | Approved merge and exact-main deployment; 2 consecutive HTTP 200 fetches for four critical files with exact candidate SHA256; owner review | Hosted content parity established; engineering gates remain independent |

## Existing portable commands (Linux/macOS)

```bash
python3 -m venv .venv-htmlqa
. .venv-htmlqa/bin/activate
python -m pip install --disable-pip-version-check playwright==1.57.0
python -m playwright install chromium

python -m unittest discover -s mission-control/v2 -p test_g3p_live_ledger.py -v
python -m unittest discover -s mission-control/html_qa -p 'test_*.py' -v
python -m unittest discover -s mission-control/federation-atlas -p test_pages_portal.py -v

SRC=mission-control/federation-atlas
OUT=/tmp/g3p-html-qa
mkdir -p "$OUT/atlas"
printf '<html><head><title>Atlas</title></head><body><h1>Atlas</h1></body></html>' > "$OUT/atlas/index.html"
python "$SRC/pages_portal.py" --atlas "$OUT/atlas" --out "$OUT/pages" --sha "$(git rev-parse HEAD)"
python mission-control/html_qa/prepare_sources.py --manifest "$SRC/G3P_LIVE_SOURCES_v1.json" --out "$OUT/fixtures"
python mission-control/html_qa/g3p_browser_qa.py --html "$OUT/pages/g3p/index.html" --manifest "$OUT/pages/g3p/G3P_LIVE_SOURCES_v1.json" --fixtures "$OUT/fixtures" --out "$OUT/browser"
```

For a managed Windows desktop, run `mission-control/html_qa/bootstrap_html_qa.ps1` at the repository root in PowerShell, in a user-writable clone. Configure `CHROMIUM_EXECUTABLE_PATH` for a preinstalled Chromium/Edge executable if browser installation is restricted. Do not request or store GitHub tokens to view public ledger source.

## Geometry, visual and behavioural census

- **Text/layout:** 1440×1000, 1280×800, 390×844; header/navigation, card grids, sibling panels, text horizontal clipping, body scroll overflow, sticky occlusion on mobile, graph horizontal scroll and source-link labels.
- **Actions:** reload button, manual and one-/five-/fifteen-minute scheduling, cutoff selectors, all visible anchor activation, SVG focus, Enter selection, keyboard-accessible source link.
- **Source failures:** 503 wave source, falsely promoted PASS receipt, invalid manifest, no stale-success caching or unearned causality.
- **Evidence:** all visible rows, typed associations vs directed arrows, exactly matched wave count and SHA claims, no false global coverage.
- **Diagnostics:** page/console exceptions, screenshots, source SHA256, site manifest digest, run/job identity, raw artifact receipt. Screenshots are reviewed manually to approve a visual baseline.

## Standard fanout API

For CODEX, ABACUS, GoGREEN/Flight Deck and QPS:

1. Keep the source-owned graph/HTML generator and Zod or JSON Schema as sole source of truth.
2. Copy/adapt the **tests**, not G3P's ledger data or its evidence authority.
3. Run `html_contract.py` on native HTML and write a dedicated, path-disjoint `Playwright` profile for its real filters/buttons/links.
4. Publish only after the respective source-owner exact-head CI, information classification, security and review gates.
5. Reuse the **same** Mission Control Pages publisher only for authorized public-safe MC artifacts. Other repos retain their own deployment owners; do not establish duplicate Pages deploy workflows.

The quantified rollout matrix is `HTML_QA_MATRIX_v1.json`. Security and admission cannot be outweighed by rendering scores or local test counts.

## GitHub Pages and release identity

- Existing portal **deployed** from `master`: https://gbogeb.github.io/pipeline-automation-hub/ (GitHub Actions log proof, not independently fetched in this session).
- Target **candidate only** after landing on `master`: https://gbogeb.github.io/pipeline-automation-hub/g3p/index.html .
- This feature PR must not run the canonical publish job: GitHub Actions job `publish-pages` is limited to main/publisher conditions.
- On exact-main publication `hosted_pages_verify.py` records HTTP status and repeated SHA256 parity. It does not change governance acceptance; if hosted parity fails, the Pages QA job fails.
- Human acceptance of screenshots is separate: `AXE/WCAG` and multi-browser pixel baselines are still follow-on evidence, not yet accepted.

## Future quality expansion

Use approved screenshot goldens and measured pixel-diff thresholds before automating visual baselines. Add axe-based accessibility and assistive technology keyboard/screen-reader review, contract-driven internal anchor/asset crawl for other pages, optional Firefox/WebKit variants, stale-loader race tests, duplicate interval tests, performance budgets, accessibility contrast/zoom, and runtime error reporting. A missing native denominator is **UNKNOWN**, never a zero.

**Disposition:** proposed QA standard; source-owned implementation under review; `engineering_credit_delta=0`, `merge_admission=HOLD`, `authority_transfer=false`.
