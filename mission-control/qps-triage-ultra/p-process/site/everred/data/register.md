# EVERRED register

Census 2026-10-30T13:14:25+00:00 · scope GBOGEB/ABACUS, GBOGEB/CODEX, GBOGEB/cryoplant-project

## Metrics

- **occurrences_total**: 494
- **occurrences_on_independent_roots**: 14
- **distinct_signatures**: 109
- **roots_independent**: 15
- **roots_triaged_or_later**: 13
- **unmatched_signatures**: 103
- **failure_amplification**: 1.077
- **failure_amplification_note**: occurrences linked to triaged independent roots / triaged independent roots
- **signature_amplification_upper_bound**: 4.532
- **root_closure_rate**: 0.267
- **recurrence_rate**: 0.0
- **consumer_replay_coverage**: UNKNOWN
- **consumer_replay_note**: no replay outcomes recorded yet; 13 roots list consumers
- **active_roots_by_state**: {'BLOCKED_AUTHORITY': 5, 'OWNED': 1, 'TRIAGED': 2, 'PRODUCER_GREEN': 1, 'VERIFIED_FIXED': 4, 'DISCOVERED': 2}
- **occurrences_by_source**: {'main:head': 32, 'main:nightly': 3, 'open-pr': 36, 'merged-pr': 423}
- **control_plane_red**: 5
- **control_plane_probed**: 6
- **dims**: {'diagnosis': {'CONFIRMED': 11, 'CANDIDATE': 2, 'UNRESOLVED': 2}, 'repair': {'PROPOSED': 6, 'NONE': 4, 'COMMITTED': 1, 'PRODUCER_VERIFIED': 4}, 'integration': {'NA': 6, 'NOT_EVALUATED': 5, 'EXACT_HEAD_PASSED': 4}, 'security': {'NA': 12, 'RED': 1, 'UNKNOWN': 2}, 'governance': {'INEFFECTIVE': 10, 'UNKNOWN': 4, 'EFFECTIVE': 1}, 'admission': {'NA': 8, 'HOLD': 4, 'ADMITTED': 3}, 'control': {'UNCONTROLLED': 10, 'UNDER_OBSERVATION': 5}}

## Roots

| Root | Class | State | Owner | Occurrences | PRs | Probe | Title |
|---|---|---|---|---|---|---|---|
| ABACUS-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=deletion,pull_request,non_fast_forward,code_quality,copilot_code_review; gaps=2 | ABACUS default branch has no required status checks (rules emptied 12 Oct; partly restored 15 Oct) |
| ABACUS-RC-2026-0002 | EXISTING_REPOSITORY_DEBT | OWNED | GBOGEB | 0 | — |  | Fixed 75% repository coverage threshold above measured main coverage (structural admission deadlock) |
| ABACUS-RC-2026-0003 | EXISTING_REPOSITORY_DEBT | TRIAGED | — | 3 | #2510 |  | Code-quality full-red surface (Black / isort / Flake8 umbrella) |
| ABACUS-RC-2026-0004 | SECURITY_OR_POLICY | TRIAGED | — | 2 | — |  | Bandit full-scan security debt (6,363 raw observations) |
| ABACUS-RC-2026-0005 | TEST_OR_MEASUREMENT_DEFECT | PRODUCER_GREEN | GBOGEB | 0 | — |  | DMAIC measurement-receipt failure broke the broad coverage suite |
| ABACUS-RC-2026-0006 | GENERATED_ARTIFACT_DRIFT | VERIFIED_FIXED | Claude | 0 | — |  | Workflow rationalization report stale after policy change |
| ABACUS-RC-2026-0007 (derived) | TEST_OR_MEASUREMENT_DEFECT | TRIAGED | — | 9 | #2470, #2488, #2496, #2506, #2508, #2510, #2520 |  | Full Red Proof Summary (dependent red) |
| ABACUS-RC-2026-0008 | SECURITY_OR_POLICY | DISCOVERED | — | 0 | — |  | Safety scanner exit 64 (unclassified: auth, invocation, version or vulnerability) |
| ABACUS-RC-2026-0009 | TEST_OR_MEASUREMENT_DEFECT | VERIFIED_FIXED | GBOGEB | 9 | #2515, #2517, #2520 |  | Bandit census coverage producer (module identity / JUnit receipt mismatch) |
| CODEX-RC-2026-0001 | SECURITY_OR_POLICY | DISCOVERED | — | 0 | — |  | OSV-Scanner reporter fails on every CODEX main push |
| CODEX-RC-2026-0002 | GENERATED_ARTIFACT_DRIFT | VERIFIED_FIXED | GBOGEB | 0 | — |  | Deterministic materializations differed after |
| CODEX-RC-2026-0003 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=deletion,non_fast_forward,required_status_checks,pull_request; gaps=5 | CODEX default branch unprotected (no ruleset) |
| CRYO-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=deletion,non_fast_forward,pull_request; gaps=2 | cryoplant-project default branch unprotected (no ruleset) |
| GGMATH-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=deletion,non_fast_forward,code_scanning,code_quality,copilot_code_review,pull_request; gaps=2 | gg_MATH default branch unprotected (no ruleset) |
| PAH-RC-2026-0001 | CONTROL_PLANE_DRIFT | VERIFIED_FIXED | GBOGEB | 0 | — | green: effective=deletion,non_fast_forward,pull_request,required_status_checks,required_linear_history,copilot_code_review,deletion,non_fast_forward,required_linear_history,copilot_code_review,code_quality; gaps=0 | pipeline-automation-hub ruleset active but targets no branch |
| QET-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=none; gaps=4 | Q_engineering_tools default branch unprotected (no ruleset) |

## Unmatched signatures (candidate roots — search the ledger before repairing)

| Signature | Occurrences | PRs | Example |
|---|---|---|---|
| `CI/CD Test Suite :: Unit Tests :: Run Unit Tests` | 30 | #2470, #2488, #2506, #2508 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057242270/job/124067753810) |
| `CI :: test :: Run tests` | 13 | #1211, #1213, #1218, #1219, #1222, #1223 | [run](https://github.com/GBOGEB/CODEX/actions/runs/41057339198/job/124068076205) |
| `CI - ABACUS Matrix :: ABACUS compatibility gate :: Enforce selected proof set` | 10 | #2470, #2488, #2504, #2506, #2508, #2519 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057241961/job/124073124781) |
| `CI - ABACUS Matrix :: Python proof completeness :: Audit executed and classified-skipped proof roles` | 10 | #2470, #2488, #2504, #2506, #2508, #2519 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057241961/job/124073064550) |
| `MIP B0 Test Admission and Coverage Evidence :: B0 report-only admission census :: Require all exact-SHA producers GREEN` | 10 | #2470, #2488, #2504, #2506, #2508, #2514 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057241899/job/124071919841) |
| `MIP B0 Test Admission and Coverage Evidence :: B0 report-only admission census :: Upload B0 report-only evidence` | 10 | #2470, #2488, #2504, #2506, #2508, #2514 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057241899/job/124071919841) |
| `CI - ABACUS Matrix :: ABACUS :: Run canonical coverage and emit governed evidence` | 10 | #2470, #2488, #2504, #2506, #2508, #2519 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057241961/job/124069463271) |
| `MIP B0 Test Admission and Coverage Evidence :: B0 canonical coverage producer :: Run canonical exact-head coverage surface` | 10 | #2470, #2488, #2504, #2506, #2508, #2514 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057241899/job/124067944758) |
| `CODEX Semantic Runtime CI :: semantic-validation :: Run semantic validator` | 9 | #1211, #1213, #1217, #1219, #1222, #1224 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40482900938/job/122117394507) |
| `W003 Governance Gate :: governance-gate :: Run governance parser on PR metadata` | 7 | #1206, #1208, #1211, #1213, #1217, #1228 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40726993914/job/123460047434) |
| `CI - ABACUS Matrix :: ABACUS :: Run functional compatibility proof` | 6 | #2470, #2488, #2504, #2506, #2508 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057241961/job/124069463246) |
| `a10-guard :: a10-guard :: Tender guard (new or changed files only)` | 5 | #2496, #2513, #2517, #2518, #2520 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40482959610/job/122117594995) |
| `CI Workflow Governance :: policy-and-inventory :: Fail closed on governance red` | 5 | #2496, #2513, #2517, #2518, #2520 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40482959447/job/122117594007) |
| `CODEX Semantic Runtime CI :: semantic-validation :: Run tests` | 5 | #1218, #1223, #1228, #1229 | [run](https://github.com/GBOGEB/CODEX/actions/runs/41057339221/job/124068076859) |
| `DMAIC V3 Enterprise CI :: CI Summary :: Set final status` | 4 | #2488, #2509, #2520 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057242432/job/124070819550) |
| `DMAIC V3 Enterprise CI :: Test on ubuntu-latest :: Install dev dependencies` | 4 | #2488, #2509, #2520 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057242432/job/124067753893) |
| `DMAIC V3 Enterprise CI :: Test on macos-latest :: Install dev dependencies` | 4 | #2488, #2509, #2520 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057242432/job/124067753886) |
| `DMAIC V3 Enterprise CI :: Test on windows-latest :: Install dev dependencies` | 4 | #2488, #2509, #2520 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057242432/job/124067753838) |
| `TestPilot Pre-GitHub Parity :: parity :: Run bounded TestPilot fast preflight` | 4 | #2510, #2516, #2520, #2522 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013160782/job/123923379257) |
| `TestPilot Pre-GitHub Parity :: parity :: Upload TestPilot receipt` | 4 | #2510, #2516, #2520, #2522 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013160782/job/123923379257) |
| `ABACUS W13 Weighted Neural SPINE :: graph-proof (3.11) :: Native W13 typed graph checks and coverage` | 3 | #2513, #2518, #2520 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41024726310/job/123960006662) |
| `ABACUS W13 Weighted Neural SPINE :: graph-proof (3.12) :: Native W13 typed graph checks and coverage` | 3 | #2513, #2518, #2520 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41024726310/job/123960006549) |
| `DOW + Recursive DMAIC - Enhanced CI :: Test (3.11) :: Run python -m coverage erase` | 2 | #2488 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057242217/job/124069969101) |
| `CI/CD Test Suite :: Security Scanning :: PR new-debt ratchet (Bandit)` | 2 | #2496, #2520 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40482959459/job/122117594502) |
| `CI/CD Test Suite :: Code Quality Checks :: Per-tool code-quality new-debt ratchet` | 2 | #2496, #2520 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40482959459/job/122117593942) |
| `CI - ABACUS Matrix :: Benchmark baseline - no coverage :: Run isolated microbenchmarks` | 2 | #2504, #2519 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41011612488/job/123918526193) |
| `Validate Docs (Markdown/YAML/JSON) :: Changed docs lint :: Validate changed docs` | 2 | #2513, #2520 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41024726293/job/123960006658) |
| `SPINE Gate :: spine-gate :: Run SPINE gate (terms, secrets, import closure)` | 2 | #1210, #1212 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40349753119/job/121666268991) |
| `Deploy Next.js site to Pages :: build :: Detect package manager` | 1 | main | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057242280/job/124070467050) |
| `MIP B0 Test Admission and Coverage Evidence :: DAB proposal worker DAB-<sha>-E731-* :: Set up job` | 1 | main | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057241899/job/124068459893) |
| `DOW + Recursive DMAIC - Unified CD Pipeline :: Lint & Validate :: Run pre-commit hooks` | 1 | main | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057242112/job/124067752755) |
| `Session Tuple CI/CD :: test (3.10) :: Run Full Test Suite` | 1 | main | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057242035/job/124067751400) |
| `Session Tuple CI/CD :: test (3.10) :: Test Report` | 1 | main | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057242035/job/124067751400) |
| `Continuous Integration Pipeline :: Unit Tests (windows-latest, 3.11) :: Run Tests` | 1 | main | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057241880/job/124067751207) |
| `export-docs :: export :: Export` | 1 | main | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41057241955/job/124067751120) |
| `EVERRED V3 Governed Control Plane :: EVERRED source, provenance and negative tests (3.10) :: Verify committed Black and isort styles` | 1 | #2517 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41010460299/job/123914923257) |
| `W81 Repair Outcome Block :: governance-report-preview :: Generate exact workflow rationalisation candidate` | 1 | #2517 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41010460421/job/123914923162) |
| `EVERRED V3 Governed Control Plane :: EVERRED source, provenance and negative tests (3.12) :: Verify committed Black and isort styles` | 1 | #2517 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41010460299/job/123914923087) |
| `TestPilot Pre-GitHub Parity :: parity :: Replay pre-push source-bound checks on exact GitHub head` | 1 | #2510 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41011823629/job/123919185234) |
| `TestPilot Pre-GitHub Parity :: parity :: Isolated fresh local Git clone and equivalent testflight` | 1 | #2510 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41011823629/job/123919185234) |
| `TestPilot Pre-GitHub Parity :: parity :: Exact-source N-to-N+1 replay comparison` | 1 | #2510 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41011823629/job/123919185234) |

## Private repositories (aggregate counts only; no rows are published)

| Repo | Occurrences | Distinct signatures | Unmatched signatures | Linked roots |
|---|---|---|---|---|
| GBOGEB/cryoplant-project | 276 | 62 | 62 | — |
