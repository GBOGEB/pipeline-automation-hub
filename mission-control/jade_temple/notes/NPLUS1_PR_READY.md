# JADE_TEMPLE N+1 — GitHub draft PR reviewer scope

Suggested title: `feat(jade-temple N+1): source-bound GoGREEN Top21 readiness, shared Pages child and MIP controls`

**Base:** `GBOGEB/pipeline-automation-hub:master`. **Branch:** `docs/jade-temple-gogreen-nplus1-20261018`. Always re-read both latest heads and check status. This implementation is independent from the already merged JADE bootstrap PR #729.

## Additive files and bounded existing-file modifications

- New `mission-control/jade_temple/data/*NPLUS1.json` — frozen sourced 21-row current-head/BD register, separate 13/8/8 cohort crosswalk and metric controls.
- New `mission-control/jade_temple/site/green_template.html`, `jade.css`, `jade.js`, `build_green.py` and generated `green.html`, `jade_data.js`, `snapshot.json`, `site-manifest.json`, `top21_bd_queue.csv` — offline responsive GoGREEN view, deterministic manifest, named source digest.
- New `mission-control/jade_temple/portal_bridge.py`, two focused unittest modules, and browser QA helper. Existing site `index.html`/`template.html` only get additive navigation.
- Existing `mission-control/federation-atlas/pages_portal.py` only gains a hash-validated `/jade/` child and one link; `README.md` only gains pointer; `00_START_HERE.md` gains N+1 pointer.
- New `.github/workflows/jade-temple-readonly-qa.yml` with read-only permissions/checkout SHA and positive/negative native tests; no Pages deployment job.
- New full MIP/README/Top21 technical TODO and lossless restart receipt.

## Explicit native acceptance

1. Confirm changed-path disjointness and current base; local generator output byte-match on committed exact head.
2. Run 44 standard-library tests and three responsive Playwright viewports, negative CSP/data/manifest controls, artifact SHA and hosted staging source hash.
3. Independently run the actual existing Mission Control method-atlas publisher's PR-scoped render to ensure the `pages_portal.py` bridge integrates with its other views (without deploying from PR).
4. Security, eligible independent reviewer, effective protected ruleset, required check and blocked RED canary remain separate. Do NOT waive or bypass.
5. Postmerge, if independently authorized, use **existing** Pages publisher only; HTTP verify served pages and all assets against recorded source hash, otherwise leave HOSTED_UNKNOWN.

`MERGE_ADMISSION=HOLD`, local QA does not qualify current-main release or QPS acceptance. No protected-rule mutation or reviewer impersonation performed.
