# Mission Control M3 — Federation Flightdeck (W0)
**Status:** non-authoritative, source-linked implementation candidate; `P0=HOLD`.

## Navigation
- Entry: `docs/mission-control/m3/index.html`
- Frozen source: `docs/mission-control/m3/state.json`
- Existing authoritative owners remain `mission-control/v2/`, `mission-control/federation-atlas/`, and CODEX Mycelium. Existing M2 remains unchanged.

## DAG and graph semantics
Typed atoms aggregate into 6 repository nodes, 8 P00-P70 process nodes, bridging nodes, scheduler/worker/proof nodes and first-red root nodes. Edges are `dependency`, `federation`, `proof`, `publication`, or `feedback`. The default `DECLARED` binding produces dashed paths; it **never** proves execution. Source-bound native receipts are separately listed.

## Projection contract
`state.json` freezes six exact default-branch SHAs at the 2026-10-17 GitHub readback. It does **not** refresh itself. The refresh button merely reloads the same static JSON. No browser credentials, GitHub mutation or hidden dispatch. The HTML fetches adjacent JSON over HTTP; for local inspection serve `python -m http.server` from the repo root and open `http://127.0.0.1:8000/docs/mission-control/m3/index.html`.

## Native first-red and worker evidence
ABACUS PR #2162 B0 exact-head run 39056877380 failed overall, with eight separate successful DAB proposal-worker jobs and their own artifacts. These are not CODEX-authenticated Crew dispatches. PR #2161 matrix run 39056628120 failed all 3 interpreter jobs. CODEX PR #975 historically merged; CODEX issue #977 remains 0/7. ABACUS issue #1860 remains 1/12. Correctly governed merge remains unverified.

## Three-pulse next slice (NOT launched)
- W1/P1: MC owner PR native/HTML QA, verify exact-head source and merge-gate policies; no standalone Pages publication.
- W2/P2: CODEX owner selects authenticated ABACUS-local execution architecture, stage-only by default, tests principal/head/scope/idempotency/replay/concurrency.
- W3/P3: ABACUS owners fix first-red #2161/#2162 on disjoint source paths; exact-head retests and security/human review before admission.

## Governance
Root #1885 historical 53 broken href occurrences (50 MYRRHA, 2 reports, 1 expression) and six historical ticket duplicate closures are NOT engineering root closures. Same-population main and diff coverage is UNKNOWN, not zero. Source freeze does not grant remote engineering authority. Changes require independent review, exact head CI and ruleset re-entry. This branch/PR is an architecture and visualization proposal, not a correctly admitted main merge.

## QA
Run `node mission-control/federation-atlas/m3_session/test_m3_contract.js` for graph/authority/anchor invariants. Browser acceptance target: 1440x1000, 1280x800, 390x844; no document overflow, missing assets, console/page errors; use existing `mission-control/html_qa` before promotion. CSS/SVG visualization is review-only. Native exact-head QA remains outstanding until workflow proof.
