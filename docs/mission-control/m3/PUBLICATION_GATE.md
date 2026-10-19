# Mission Control M3 — owner-controlled publication promotion

## Disposition
**STAGED CANDIDATE ONLY / P0 HOLD.** This change builds a source-digested seven-leaf offline release candidate in the existing native M3 proof job. It does **not** enable Pages, change default-branch settings, grant a security waiver, dispatch a worker, merge a PR, or supply an owner approval.

## What a qualified candidate contains

The *same exact-head* `mission-control-m3-graph.yml` contract job builds `out/m3/site` with M3 index/state/measured telemetry, M2 index/pipeline/federation, and the existing code-purple-live census entrypoint. The `m3_publication_preflight.js` validator binds each leaf's SHA-256, verifies the telemetry's digest of the M3 state, checks navigation and authority invariants, rejects missing files, and writes `out/m3/publication-preflight.json`. An explicit missing-leaf and forged-digest test runs before the artifact can be considered prepared.

Run `node mission-control/federation-atlas/m3_session/m3_publication_preflight.js --site out/m3/site --out out/m3/publication-preflight.json --sha <EXACT_40_HEX_HEAD>` **only after** the M3 job builds its native `out/m3/site`; then `EXPECTED_SHA=<EXACT_40_HEX_HEAD> node mission-control/federation-atlas/m3_session/test_m3_publication_preflight.js`.

## Two-stage authority boundary

1. **Candidate preparation (this workflow):** `contents: read`, no Pages write permission, no deployment action. The downloaded M3 artifact is *reviewable offline*. The source digest and job receipt are not hosted URL proof.
2. **Owner-controlled publication (not activated):** designated maintainer confirms an authenticated approval tied to the intended release exact commit and permitted repo; checks active effective rulesets and required human reviews; independently provisions/enables a single existing governed Pages publisher; verifies Pages source branch/path and access; deploys only a reviewed exact-SHA package; checks HTTPS status and byte digests for the publicly served HTML/JSON; records the approving principal, run/job/attempt, exact main SHA, Pages URL and observed hosted hashes. If any step is unknown, status remains WITHHELD. An unapproved environment or merely present HTML file is not publication.

## Historical merge versus admission

- Mission Control [#667](https://github.com/GBOGEB/pipeline-automation-hub/pull/667) was merged as GitHub fact, but had **no recorded submitted approval** at the 17 October review census. A merge is not retrospectively called correctly governed.
- Current M3 source retains older pinned six-repo observation SHAs. These identify historical observations, **not** real-time source freshness.
- No evidence is offered that the proposed public URL is served; the GitHub Pages API could not be read from this connector. Pages verification stays `null`, never false-zero substitution.

## QA and controlled promotion

Required publication acceptance: native exact-head contract and Chromium 1440/1280/390 screenshots, complete seven-leaf digests, source/crosswalk parity, independent reviewer approval, effective policy and branch SHA readback, owner Pages/environment approval, and fetched hosted-byte parity. A failed check is an explicit HOLD. Do not install another independent publisher to bypass an existing one.

This is a non-authoritative projection over Mission Control V2 / Golden Thread / existing live census, and does not affect QPS engineering acceptance.
