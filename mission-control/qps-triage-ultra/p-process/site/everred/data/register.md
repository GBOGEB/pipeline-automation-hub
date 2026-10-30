# EVERRED register

Census 2026-10-30T08:12:18+00:00 · scope GBOGEB/ABACUS, GBOGEB/CODEX, GBOGEB/cryoplant-project

## Metrics

- **occurrences_total**: 496
- **occurrences_on_independent_roots**: 15
- **distinct_signatures**: 106
- **roots_independent**: 15
- **roots_triaged_or_later**: 13
- **unmatched_signatures**: 100
- **failure_amplification**: 1.154
- **failure_amplification_note**: occurrences linked to triaged independent roots / triaged independent roots
- **signature_amplification_upper_bound**: 4.679
- **root_closure_rate**: 0.267
- **recurrence_rate**: 0.0
- **consumer_replay_coverage**: UNKNOWN
- **consumer_replay_note**: no replay outcomes recorded yet; 13 roots list consumers
- **active_roots_by_state**: {'BLOCKED_AUTHORITY': 5, 'OWNED': 1, 'TRIAGED': 2, 'PRODUCER_GREEN': 1, 'VERIFIED_FIXED': 4, 'DISCOVERED': 2}
- **occurrences_by_source**: {'main:head': 8, 'main:nightly': 3, 'open-pr': 140, 'merged-pr': 345}
- **control_plane_red**: 5
- **control_plane_probed**: 6
- **dims**: {'diagnosis': {'CONFIRMED': 11, 'CANDIDATE': 2, 'UNRESOLVED': 2}, 'repair': {'PROPOSED': 6, 'NONE': 4, 'COMMITTED': 1, 'PRODUCER_VERIFIED': 4}, 'integration': {'NA': 6, 'NOT_EVALUATED': 5, 'EXACT_HEAD_PASSED': 4}, 'security': {'NA': 12, 'RED': 1, 'UNKNOWN': 2}, 'governance': {'INEFFECTIVE': 10, 'UNKNOWN': 4, 'EFFECTIVE': 1}, 'admission': {'NA': 8, 'HOLD': 4, 'ADMITTED': 3}, 'control': {'UNCONTROLLED': 10, 'UNDER_OBSERVATION': 5}}

## Roots

| Root | Class | State | Owner | Occurrences | PRs | Probe | Title |
|---|---|---|---|---|---|---|---|
| ABACUS-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=deletion,pull_request,non_fast_forward,code_quality,copilot_code_review; gaps=2 | ABACUS default branch has no required status checks (rules emptied 12 Oct; partly restored 15 Oct) |
| ABACUS-RC-2026-0002 | EXISTING_REPOSITORY_DEBT | OWNED | GBOGEB | 0 | — |  | Fixed 75% repository coverage threshold above measured main coverage (structural admission deadlock) |
| ABACUS-RC-2026-0003 | EXISTING_REPOSITORY_DEBT | TRIAGED | — | 2 | #2510 |  | Code-quality full-red surface (Black / isort / Flake8 umbrella) |
| ABACUS-RC-2026-0004 | SECURITY_OR_POLICY | TRIAGED | — | 1 | — |  | Bandit full-scan security debt (6,363 raw observations) |
| ABACUS-RC-2026-0005 | TEST_OR_MEASUREMENT_DEFECT | PRODUCER_GREEN | GBOGEB | 0 | — |  | DMAIC measurement-receipt failure broke the broad coverage suite |
| ABACUS-RC-2026-0006 | GENERATED_ARTIFACT_DRIFT | VERIFIED_FIXED | Claude | 0 | — |  | Workflow rationalization report stale after policy change |
| ABACUS-RC-2026-0007 (derived) | TEST_OR_MEASUREMENT_DEFECT | TRIAGED | — | 8 | #2368, #2470, #2483, #2486, #2496, #2510, #2523 |  | Full Red Proof Summary (dependent red) |
| ABACUS-RC-2026-0008 | SECURITY_OR_POLICY | DISCOVERED | — | 0 | — |  | Safety scanner exit 64 (unclassified: auth, invocation, version or vulnerability) |
| ABACUS-RC-2026-0009 | TEST_OR_MEASUREMENT_DEFECT | VERIFIED_FIXED | GBOGEB | 12 | #2515, #2517, #2520, #2523 |  | Bandit census coverage producer (module identity / JUnit receipt mismatch) |
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
| `MIP B0 Test Admission and Coverage Evidence :: B0 report-only admission census :: Require all exact-SHA producers GREEN` | 12 | #2368, #2470, #2488, #2503, #2504, #2506 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548492/job/123927113829) |
| `MIP B0 Test Admission and Coverage Evidence :: B0 report-only admission census :: Upload B0 report-only evidence` | 12 | #2368, #2470, #2488, #2503, #2504, #2506 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548492/job/123927113829) |
| `CI/CD Test Suite :: Unit Tests :: Run Unit Tests` | 12 | #2470, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548586/job/123924601789) |
| `MIP B0 Test Admission and Coverage Evidence :: B0 canonical coverage producer :: Run canonical exact-head coverage surface` | 12 | #2368, #2470, #2488, #2503, #2504, #2506 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548492/job/123924601301) |
| `CI :: test :: Run tests` | 12 | #1211, #1213, #1218, #1219, #1222, #1223 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40915690935/job/123595174409) |
| `CI - ABACUS Matrix :: ABACUS compatibility gate :: Enforce selected proof set` | 10 | #2368, #2470, #2488, #2503, #2504, #2506 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548303/job/123928446114) |
| `CI - ABACUS Matrix :: Python proof completeness :: Audit executed and classified-skipped proof roles` | 10 | #2368, #2470, #2488, #2503, #2504, #2506 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548303/job/123928385357) |
| `CI - ABACUS Matrix :: ABACUS :: Run canonical coverage and emit governed evidence` | 10 | #2368, #2470, #2488, #2503, #2504, #2506 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548303/job/123925396285) |
| `CODEX Semantic Runtime CI :: semantic-validation :: Run semantic validator` | 10 | #1211, #1213, #1216, #1217, #1219, #1222 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40903920597/job/123553368691) |
| `CI - ABACUS Matrix :: Benchmark baseline - no coverage :: Run isolated microbenchmarks` | 9 | #2368, #2488, #2503, #2504, #2506, #2507 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548303/job/123924600897) |
| `CI - ABACUS Matrix :: ABACUS :: Run functional compatibility proof` | 8 | #2368, #2470, #2488, #2503, #2504, #2506 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548303/job/123925396343) |
| `CI Workflow Governance :: policy-and-inventory :: Fail closed on governance red` | 8 | #2483, #2487, #2496, #2513, #2517, #2518 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548622/job/123924601213) |
| `W003 Governance Gate :: governance-gate :: Run governance parser on PR metadata` | 8 | #1205, #1206, #1208, #1211, #1213, #1217 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40726993914/job/123460047434) |
| `a10-guard :: a10-guard :: Tender guard (new or changed files only)` | 7 | #2487, #2496, #2513, #2517, #2518, #2520 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548271/job/123924599720) |
| `CI/CD Test Suite :: Code Quality Checks :: Per-tool code-quality new-debt ratchet` | 6 | #2368, #2483, #2486, #2496, #2520, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548586/job/123924601332) |
| `TestPilot Pre-GitHub Parity :: parity :: Run bounded TestPilot fast preflight` | 5 | #2510, #2516, #2522, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41024759456/job/123960119202) |
| `TestPilot Pre-GitHub Parity :: parity :: Upload TestPilot receipt` | 5 | #2510, #2516, #2522, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41024759456/job/123960119202) |
| `DMAIC V3 Enterprise CI :: Test on windows-latest :: Install dev dependencies` | 4 | #2488, #2509, #2520, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548468/job/123924600890) |
| `ABACUS W13 Weighted Neural SPINE :: graph-proof (3.12) :: Native W13 typed graph checks and coverage` | 4 | #2513, #2518, #2520, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548324/job/123924600364) |
| `ABACUS W13 Weighted Neural SPINE :: graph-proof (3.11) :: Native W13 typed graph checks and coverage` | 4 | #2513, #2518, #2520, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548324/job/123924599911) |
| `CODEX Semantic Runtime CI :: semantic-validation :: Run tests` | 4 | #1218, #1223, #1228 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40915690822/job/123595173292) |
| `DMAIC V3 Enterprise CI :: CI Summary :: Set final status` | 3 | #2488, #2509, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548468/job/123926928868) |
| `SPINE Gate :: spine-gate :: Run SPINE gate (terms, secrets, import closure)` | 3 | #1205, #1210, #1212 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40349753119/job/121666268991) |
| `DOW + Recursive DMAIC - Enhanced CI :: Test (3.11) :: Run python -m coverage erase` | 2 | #2488, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548650/job/123926220105) |
| `DMAIC V3 Enterprise CI :: Test on ubuntu-latest :: Install dependencies` | 2 | #2488, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548468/job/123924601147) |
| `EVERRED V3 Governed Control Plane :: EVERRED source, provenance and negative tests (3.10) :: Verify committed Black and isort styles` | 2 | #2517, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548494/job/123924601106) |
| `CI/CD Test Suite :: Security Scanning :: PR new-debt ratchet (Bandit)` | 2 | #2496, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548586/job/123924601005) |
| `Validate Docs (Markdown/YAML/JSON) :: Changed docs lint :: Validate changed docs` | 2 | #2513, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548595/job/123924600958) |
| `EVERRED V3 Governed Control Plane :: EVERRED source, provenance and negative tests (3.12) :: Verify committed Black and isort styles` | 2 | #2517, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548494/job/123924600933) |
| `DMAIC V3 Enterprise CI :: Test on macos-latest :: Install dependencies` | 2 | #2488, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548468/job/123924600914) |
| `W81 Repair Outcome Block :: governance-report-preview :: Generate exact workflow rationalisation candidate` | 2 | #2517, #2523 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41013548446/job/123924600823) |
| `DMAIC V3 - Cognitive Loop CI/CD :: P0: PHASE0 Validation Gate :: Run PHASE0 Validation` | 1 | main | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41024759494/job/123960119458) |
| `TestPilot Pre-GitHub Parity :: parity :: Replay pre-push source-bound checks on exact GitHub head` | 1 | #2510 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41011823629/job/123919185234) |
| `TestPilot Pre-GitHub Parity :: parity :: Isolated fresh local Git clone and equivalent testflight` | 1 | #2510 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41011823629/job/123919185234) |
| `TestPilot Pre-GitHub Parity :: parity :: Exact-source N-to-N+1 replay comparison` | 1 | #2510 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/41011823629/job/123919185234) |
| `DMAIC V3 Enterprise CI :: Test on macos-latest :: Install dev dependencies` | 1 | #2509 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40917436947/job/123601311438) |
| `DMAIC V3 Enterprise CI :: Test on ubuntu-latest :: Install dev dependencies` | 1 | #2509 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40917436947/job/123601311321) |
| `Deploy GitHub Pages :: build :: Build verified Pages output` | 1 | main | [run](https://github.com/GBOGEB/CODEX/actions/runs/41008417440/job/123908539039) |

## Private repositories (aggregate counts only; no rows are published)

| Repo | Occurrences | Distinct signatures | Unmatched signatures | Linked roots |
|---|---|---|---|---|
| GBOGEB/cryoplant-project | 272 | 62 | 62 | — |
