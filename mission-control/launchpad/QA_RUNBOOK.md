# MissionControl Makeover W1 P3 — exact-head visual DoV

This is the **existing Atlas Pages publisher** with one added read-only `missioncontrol/` child. The public root portal card links to the new launcher only when the generated file exists. No new deploy workflow, repository-owned mutation gateway, or permission is introduced.

## Build and QA
- `python -m unittest discover -s mission-control/launchpad -p 'test_*.py' -v`
- `python mission-control/launchpad/render_launchpad.py --out /tmp/mc-nav --sha <EXACT_CHECKOUT_SHA>`
- `python mission-control/federation-atlas/pages_portal.py --atlas <CURRENT_CANONICAL_ATLAS_BUILD> --out <EXISTING_PAGES_DEST> --sha <EXACT_CHECKOUT_SHA>`
- `python mission-control/launchpad/browser_qa.py --html <DEST>/missioncontrol/index.html --manifest <DEST>/missioncontrol/manifest.json --out <BROWSER_QA>`

## DoV ladder (non-compensating)
1. **Source:** typed 6-repo, 13-node, 19-edge crosswalk; 3 historical RECEIPT edges are not fresh current-head results. Typed dependency DAG acyclic; feedback separate.
2. **Unit:** Python 3.11/3.12 exact-head tests; focused line/branch population k/d emitted to artifacts. Never re-label module coverage as fleet coverage.
3. **Browser:** Chromium desktop 1440×1000, laptop 1280×800 and mobile 390×844; all controls actually click; six repository launch cards; graph mode/focus/keyboard; zero overflow/overlap/console red; visible source links; two independent seeded negative false-GO/false-APPLY cases.
4. **Publisher:** single existing `pages_portal.py`, resulting `site-manifest.json` digests match launch-manifest files. A stub Atlas in the *isolated browser job* proves packaging only; the separate Method Atlas pipeline performs its real Atlas build.
5. **Release:** two independent hosted HTTP readbacks against the exact merged master SHA, matching source byte hashes and security/review. **NOT VERIFIED until observed.**

## Disjoint wave order
P1 graph and model PR -> P2 HMI PR (stacked on P1) -> P3 Pages/native QA PR (stacked on P2). Those PRs have disjoint changed paths; stacked ancestry is deliberate. Merge serially under effective review and exact SHA gates. Do not interpret queued Actions jobs as workers already dispatched by this UI.

CTRL HOLD: CODEX mutation transports remain [], formal/engineering credit 0; QPS engineering and classified publication require separate owner review.
