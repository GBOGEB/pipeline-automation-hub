# B02 external early-adoption pilot: Taxonomy browser QA pip cache A/B

Status: **experimental, opt-in only**; no default PR behavior change and no gate promotion.

## Authoritative reuse

- Existing observed workflow: .github/workflows/taxonomy-browser-qa.yml.
- Existing synthetic/no-network behavioral suite: mission-control/issue_rank/taxonomy_browser_qa.py.
- Existing pinned actions/setup-python action (v7.0.0 commit SHA in workflow); built-in pip download-store caching, keyed by mission-control/issue_rank/browser-qa-requirements.txt. It does not cache the installed environment, Chromium browser, OS packages, test artefacts or secrets.
- No third-party action introduced, new cache action required, ADMISSION change, credential write, branch rules change, or new workflow file.

## Execution and measurement protocol

Default pull_request still runs the original, uncached browser-qa job with source SHA assertion. Manual workflow_dispatch adds one *optional* 2x matrix (`none` and `pip`) only when the user explicitly checks `cache_pilot=true`; each runner has isolated filesystem and identical Python 3.12 / Ubuntu 24.04 / pinned Playwright / synthetic tests.

1. On a reviewed pilot ref, dispatch the existing Taxonomy Explorer Playwright 3-view QA workflow with `cache_pilot=true`. Observe `cache-ab / none` and `cache-ab / pip`, which both execute exactly the same full synthetic QA. The baseline on first dispatch is cold if no matching cache exists; verify the GitHub `cache-hit` output, do not presume.
2. Repeat the same dispatch at the exact same source SHA at least three times, without changing the Python version or requirements file. The `pip` mode should report cache-hit=true on subsequent runs if the cache was saved and restored. A/B comparison of the first dispatch alone is **not** a warm-cache experiment.
3. Read each immutable artifact named `taxonomy-cache-ab-<mode>-<run_id>-<attempt>`, then compare only matched runs by mode, source SHA, runner image, Python version and Playwright top-level pin. Keep both failed and successful attempts in the denominator.
4. Use canonical JADE `actions_metrics.py` for workflow/job wall, queue, billable-minute, retry and weekly metrics. The experimental receipt records **only** local preparation and test step elapsed seconds, cache-hit, QA outcome, SHA and run identity. No competing metric owner.
5. Record p50/p95 for cold/warm installations and end-to-end job durations separately. Preserve test population, all three viewports and zero private-data leaks. If a warm improvement disappears after browser installation, classify it as limited cache opportunity rather than promoting it globally.

## T0 and DoV

Before this opt-in pilot there is no matched Taxonomy cold/warm clock in the supplied CI-spine timing sample. **T0 for the matched experiment is UNKNOWN**, not zero. The separate JADE browser QA sample showed a 28-second browser-install step, which is a candidate hypothesis, not a Taxonomy baseline or a pip cache saving.

Success requires: source-identical A/B runs, measured cache hits, 0 behavioral regressions, no test skips, no supply-chain trust regression, and a repeatable positive p50 benefit. No promoted gate, positive financial savings, or portfolio runtime reduction is claimed before complete receipts. Roll back by leaving `cache_pilot=false`; existing PR browser QA remains unchanged.

## Admission separation

PR path remains path-scoped and OBSERVED. The optional jobs do not replace FPC, Required Gate, release review, branch protection, or engineering approval. Cache keys depend only on source-controlled pinned requirements; avoid restoring privileged secrets or elevating pull_request cache write privileges. Full transitive hash locking remains a later qualification step.

Related B02 in LOGICAL_BUNDLE_DAG_v1.json, RF_MATRIX_WAVE_v1.json, #995 parent scheduler, #998 native first-red repair, #994 GOGREEN selector, and #996 CI spine index.
