# W3 single-publisher convergence receipt

## Origin and scope
- Parent source: `210f0b7f9a8f7fff41e6c49f2053f0afb4b40647` (previous W1/W2 source merged via PR #537).
- New source: use exact PR/commit SHA, once flight is explicitly authorized.
- One existing `CODE PURPLE Method Atlas (read-only)` workflow; one uploaded artifact; no new trigger, worker launcher, Pages publisher or write token.
- Inputs: canonical `mission-control/gogreen/samples/fleet_g1.json` (historical six repos and 42 eligible cells) + `flightdeck_contract.json` + historical `head_snapshot.json`.
- The same single Atlas producer generates all four linked Office/PDF files before sealing.\n- Generated paths: `/tmp/code-purple-atlas/index.html`, `/tmp/code-purple-atlas/flightdeck/index.html`, `flightdeck/census.json`, `flightdeck/anchors.json`, `flightdeck/bd_leaves.json`, `flightdeck/manifest.json`, `flightdeck-coverage.json`, `flightdeck-tests.log`.
- Focused floors (not fleet-wide coverage): >=42 actual tests; >=95% line and >=90% branch, coverage 7.13.3, exactly 1 measured module.
- SHA binding: GitHub checkout HEAD == source in census/manifest.
- Fail-close: every source, test, SHA, count, output and digest error produces a failed CI step.
- W3 native: PENDING (until PR / approved dispatch and terminal producer receipt).
- Pages release: HOLD (preexisting Jekyll deploy is not artifact identity readback).
- Main ruleset: MISSING at last readback; no automatic merge or security waiver.
- QPS: DEFER; 36 of 42 historical G4 cells remain UNKNOWN, not failures.
- Fleet anchors: 2/5 historical G4 anchors match; 3 stale.
- H1-to-H4 native cross-repo proof remains unestablished.

## Exact stages

```text
GitHub source (frozen exact SHA)
  -> current Method Atlas unit tests / graph / Code Purple series
  -> Flight Deck 42+ unittest and 95/90 focused coverage
  -> canonical GOGREEN 6 x eight-family catalog validation
  -> build 42 leaf cards / five anchors / 36 open evidence leaves
  -> manifest + exact SHA verification
  -> single Atlas Actions artifact
  -> Owner gate: required checks + eligible review + controlled merge
  -> Separate allowed Pages publication and hosted content readback
```

**No proof credited for archive download, current-main ancestry, publication,
corporate document release, or QPS engineering ACCEPT from a green HTML page.**

## Adjacent owner DoV implementation

The post-W1/W2 MissionControl main added `mission-control/federation-atlas/flightdeck/global_dov_runner.py` and `global_dov_owner_control_v1.json` via PR #539. This W3 integration **consumes and links** that distinct Global DoV authority; it does not duplicate, promote or replace the owner-action runner. The Atlas Flight Deck remains a read-only evidence projection; Global DoV admission remains governed separately.
