# CODE PURPLE Watch vNext — N2 source-pinned flightdeck

This is the MIP-12 **candidate consumer**, not another census or dashboard metric producer. The source of measurements is only mission-control/gogreen/scale-dock/real/receipt/scale-dock.json, produced by the canonical scale-dock owner. The source Git commit and blob OID are embedded in the projection.

## Display contract

- Historical three-public-repository source-bound scale-dock pulse values appear verbatim, with the owner field path for every number. They are **not** a qualified six-repository/42-cell authenticated #531 census.
- Fresh six-repo breadth, global matched main coverage, independent root closure, required status enforcement, owner acceptance, new alerts and hosted Pages parity remain **UNKNOWN** in this view; no computed zero or PASS.
- A 15-row MIP queue is labeled proposed work, **not completion credit**. Links to candidate PRs are navigation, not PR state assertions.
- A strict allowlist projects selected source-owner scalar fields. The source receipt's embedded issue_bd can contain restricted private-QPS aggregates and is never embedded in snapshot, HTML, browser logs or artifact metadata.
- No external JavaScript, live fetch, cookie, token, GitHub mutation, worker dispatch, signal attestation, publication or authority transfer.

## Run and inspect (source commit pinned)

    python -m unittest discover -s mission-control/gogreen/watch_vnext -p 'test_*.py' -v
    python mission-control/gogreen/watch_vnext/build_view.py --rev HEAD --out /tmp/code-purple-watch-view
    python -m pip install --disable-pip-version-check playwright==1.57.0
    python -m playwright install chromium
    python mission-control/gogreen/watch_vnext/browser_qa.py --html /tmp/code-purple-watch-view/index.html --out /tmp/code-purple-watch-view/browser

The read-only flightdeck QA workflow at .github/workflows/code-purple-watch-flightdeck-qa.yml performs exact-head unit/static/browser checks at **1440×1000, 1280×800 and 390×844**, hashes screenshots and uploads a review artifact. CI green proves a candidate renderer and browser behavior at that exact head; it does **not** prove GitHub Pages deployment, live source freshness, QPS acceptance, or independently approved release. Visual screenshot acceptance remains manual.

## Integration with canonical launcher / Pages

mission-control/gogreen/launcher/ is the canonical navigation aggregator. It should link the flightdeck artifact **only after** source-owner and protected review gates qualify a stable publication candidate, and the launcher is rebuilt at one exact commit to update its complete HTML catalog. This PR deliberately does not mutate its generated index.html/launcher.json, avoiding stale metric tiles and a competing Pages publisher.

## Gates that remain unsatisfied

1. Independent qualifying review and effective required-status enforcement (master ruleset currently not proven enforced).
2. #881/#882/#890 stack source authenticity and current-head replay.
3. #531 fresh authenticated census; historical scale-dock breadth cannot substitute.
4. QPS source restricted-owner receipt; never copy private bidder, PR, run, issue, hash or record contents.
5. Manual desktop/mobile screenshots, accessibility review and post-merge hosted twice SHA-parity HTTP readback.

**Always:** MERGE_ADMISSION=HOLD, FORMAL_ENGINEERING_CREDIT_DELTA=0, QPS_OWNER_ACCEPTANCE=WITHHELD, SECURITY_WAIVER=NONE.
