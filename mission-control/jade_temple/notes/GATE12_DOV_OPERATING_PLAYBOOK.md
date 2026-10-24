# JADE H01-H12 DoV: Content Quality -> Runtime -> Release

**Status: SOURCE CANDIDATE; MERGE_ADMISSION=HOLD; RELEASE_CREDIT=0.** An action register does not override or upgrade an existing gate.

Canonical evidence is in ../data/FOCUS5_POINT_RELEASE_NPLUS7.json (5-repo historical observation), ../data/TOP21_PORTFOLIO.json (21-member cohort), and ../data/ROLLING5_POLICY.json (H01-H12 prerequisites). ../data/GATE12_DOV_ACTIONS.json is the **additional proposed actions and acceptance criteria**, not a second scoreboard.

## Reader / operator navigation

[Central H01-H12 cockpit](../site/gate12_hub.html) · [Machine KPI & tasks](../site/gate12_data.json) · [Full 252-slot BD queue CSV](../site/gate12_bd_queue.csv) · [GoGREEN](../site/green.html) · [Original burndown](../site/burndown.html) · [CI/CD DAG](../site/cicd_dag.html) · [MIP eight-point](../site/eightpoint.html) · [RED-trace](../site/redtrace.html).

These are repository-candidate hyperlinks; none prove that the Pages URL is live or exact-head verified.

## Acceptance ladder: nine individually veto-capable stages

| Stage | Positive proof | Never accepted as substitute |
|---|---|---|
| SOURCE_AUTHORED | canonical owner/head, source/provenance, required population | a generic README without substantive review |
| GENERATED | native builder byte parity, source Git blob OIDs and reproducible outputs | manually altered HTML/KPI |
| STATIC_QA | H01-H12 identities, content schema, local links, SHA-256 member manifest | existence of a file |
| BROWSER_QA | 1440x1000, 1280x800, 390x844, no console/page errors or document overflow, working filters | uninspected screenshots |
| STAGED_SINGLE_PUBLISHER | original hash-verifying JADE portal child, no second publisher | extra manual static copy |
| DEPLOYED | authorized Pages workflow success at exact commit/deploy id | source workflow green |
| HOSTED_SHA_VERIFIED | HTTP 200, canonical served SHA and every asset SHA-256, repeated GETs | just a reachable URL |
| RUNTIME_HEALTH_VERIFIED | relevant startup, service checks, logs, negative-path, restart and rollback | unit tests alone |
| OWNER_RELEASE_ACCEPTED | signed tag, runbook, disposition, source-bound acceptance | dashboard saying green |

## Twelve completion actions, owners and source proof

| Gate | Mandatory action | Primary owner |
|---|---|---|
| H01 | 21 exact default-head reads; current HEAD contract, avoid mixed N-1 | repository owner |
| H02 | content census of source/docs/tests/workflows/binaries; missing and ZERO-tested buckets | maintainers |
| H03 | semantic/schema/content-fidelity tests; signature on source and applicability | engineering owner |
| H04 | clean dependency-pinned deterministic build, parsers and formatting/lint on YAML/JSON/TOML | build/DevOps |
| H05 | terminal exact-head B0 native tests, counted denominator, first red, no skipped critical tests | test owner |
| H06 | independent integration and runtime smoke, negative paths, bounded restart and recovery | runtime/integration |
| H07 | CodeQL language execution (not neutral check alone), supply chain and security disposition | security owner |
| H08 | effective checked ruleset + rejected unmerged RED canary, prohibit force-push/delete | repository owner |
| H09 | head-matched independent human review or formally qualified and narrow MACH II solo-owner waiver | reviewer/owner |
| H10 | scoped statement/branch/mutation/negative-path evidence, zero critical untested assets | quality owner |
| H11 | hash-verified HTML/JSON/CSV and other applicable generated assets, browser/hosted parity | Pages/content owner |
| H12 | owner-approved release tag, deployment, ops health, rollback drill and handover | release/runtime owner |

For the hub JADE source job the currently configured scope uses >=90% statement and >=80% branch coverage, plus denominator floors of 1,615 statements and 608 branches on nine modules. These numbers are **not** universal across Top21. Each repo's chosen numeric floor must be source-approved and measured at a fixed denominator before it becomes required.

## Rebuild/check commands (repo root)

    python mission-control/jade_temple/tools/build_gate12_dov.py --check
    python -m unittest discover -s mission-control/jade_temple/tests -p 'test_*.py'
    python mission-control/jade_temple/tools/run_gate12_browser_qa.py

After any owner-controlled data update, run the generator with --write, commit generated data.js, data.json and CSV, then rerun --check. The frozen focus-five contributes 60 observed statuses (14 PASS, 8 FAIL, 38 UNKNOWN) and the other 16 repos contribute 192 UNOBSERVED slots, yielding 252 queue rows. This is **not** a current Top21 qualification metric.

## Publication / operational acceptance in landing order

1. J1 owner: enforce exact required GoGREEN and CodeQL check identities with effective rules readback. No policy text substitutes for UI activation.
2. J3 owner: submit a deliberately failing, draft JADE canary. Confirm GitHub mergeable_state=blocked while failure is present. Close unmerged.
3. J4/J5/J6/J8 workers: repair primary first reds, ensure exact-head CI, baseline/candidate parity, waiver negative tests, CODEX Atlas build.
4. J7 CI: collect source-bound 21-repo same-pulse census with tokens and permissions; reconstruct N+10 + rolling five and two independent native success receipts.
5. J9 Pages worker: *separate dependent PR*, register this cockpit and three generated data members in portal_bridge.py and hosted_parity.py allowlists, source/member SHA-256 manifests, optional child fail closed. Regenerate bound DAG outputs after changing portal_bridge.py. Owner authorizes staging/publication only when J1 and J3 are proven.
6. J9 publisher: use the **existing** Pages workflow, never a new publisher. Capture build -> deploy -> external HTTP 200 -> repeated served hash checks and Playwright browser receipts. Fix stale link and mobile overflow first.
7. H06/H12 ops owner: prove boot/health/logs/config/monitoring/restart/rollback for runtime deployments. Static Pages reachability is not equivalent to an API/service being operational.
8. J10 owner: mark gate 13 owner receipt and final JADE_STATE, release notes, tag/rollback/runbook and approved open-risk dispositions. Without acceptance, withhold release.

## KPI and burndown contract

Noncompensating scorecard: observed-pass/60; observed fail/60; outside-focus unassessed/252; FIRST_RED/READY/WAIT_DEPENDENCY; zero-tested critical modules; statement and branch coverage on a matched instrumentor; content schema and semantic accepted/eligible; complete source hashes / source population; staged files / expected; hosted-matched SHA256 / expected; actual runtime smoke jobs / applicable; unwaived security findings; qualified owner release.

Unknown numerators are NULL, not 0. Do not add unobserved slots to the observed denominator or claim causal root closure from visual convergence. Every state transition needs HEAD SHA, actor, run/job/attempt, terminal result and independent evidence. A future release receipt should record source Git OIDs and SHA-256, generator version, cross-file parity, per-viewport Playwright screenshots, defects, owner decisions and the actual binary/Pages hash list.

The cockpit is **read-only**. Neither the generator nor the browser QA can dispatch workflows, merge PRs, grant a waiver or release assets.
