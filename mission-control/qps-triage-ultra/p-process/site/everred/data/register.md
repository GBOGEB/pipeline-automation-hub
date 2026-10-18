# EVERRED register

Census 2026-10-18T13:29:56+00:00 · scope GBOGEB/ABACUS, GBOGEB/CODEX, GBOGEB/cryoplant-project

## Metrics

- **occurrences_total**: 375
- **occurrences_on_independent_roots**: 20
- **distinct_signatures**: 68
- **roots_independent**: 15
- **roots_triaged_or_later**: 13
- **unmatched_signatures**: 64
- **failure_amplification**: 1.538
- **failure_amplification_note**: occurrences linked to triaged independent roots / triaged independent roots
- **signature_amplification_upper_bound**: 5.515
- **root_closure_rate**: 0.2
- **recurrence_rate**: 0.0
- **consumer_replay_coverage**: UNKNOWN
- **consumer_replay_note**: no replay outcomes recorded yet; 13 roots list consumers
- **active_roots_by_state**: {'BLOCKED_AUTHORITY': 6, 'OWNED': 1, 'TRIAGED': 2, 'PRODUCER_GREEN': 1, 'VERIFIED_FIXED': 3, 'DISCOVERED': 2}
- **occurrences_by_source**: {'main:nightly': 12, 'open-pr': 135, 'merged-pr': 228}
- **control_plane_red**: 6
- **control_plane_probed**: 6
- **dims**: {'diagnosis': {'CONFIRMED': 11, 'CANDIDATE': 2, 'UNRESOLVED': 2}, 'repair': {'PROPOSED': 7, 'NONE': 4, 'COMMITTED': 1, 'PRODUCER_VERIFIED': 3}, 'integration': {'NA': 6, 'NOT_EVALUATED': 5, 'EXACT_HEAD_PASSED': 4}, 'security': {'NA': 12, 'RED': 1, 'UNKNOWN': 2}, 'governance': {'INEFFECTIVE': 11, 'UNKNOWN': 4}, 'admission': {'NA': 8, 'HOLD': 4, 'ADMITTED': 3}, 'control': {'UNCONTROLLED': 11, 'UNDER_OBSERVATION': 4}}

## Roots

| Root | Class | State | Owner | Occurrences | PRs | Probe | Title |
|---|---|---|---|---|---|---|---|
| ABACUS-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=deletion,pull_request,non_fast_forward; gaps=2 | ABACUS default branch has no required status checks (rules emptied 12 Oct; partly restored 15 Oct) |
| ABACUS-RC-2026-0002 | EXISTING_REPOSITORY_DEBT | OWNED | GBOGEB | 0 | — |  | Fixed 75% repository coverage threshold above measured main coverage (structural admission deadlock) |
| ABACUS-RC-2026-0003 | EXISTING_REPOSITORY_DEBT | TRIAGED | — | 8 | #2090, #2091, #2098, #2109, #2144, #2145, #2151 |  | Code-quality full-red surface (Black / isort / Flake8 umbrella) |
| ABACUS-RC-2026-0004 | SECURITY_OR_POLICY | TRIAGED | — | 11 | #2058, #2077, #2090, #2091, #2098, #2109, #2144, #2145 … |  | Bandit full-scan security debt (6,363 raw observations) |
| ABACUS-RC-2026-0005 | TEST_OR_MEASUREMENT_DEFECT | PRODUCER_GREEN | GBOGEB | 0 | — |  | DMAIC measurement-receipt failure broke the broad coverage suite |
| ABACUS-RC-2026-0006 | GENERATED_ARTIFACT_DRIFT | VERIFIED_FIXED | Claude | 0 | — |  | Workflow rationalization report stale after policy change |
| ABACUS-RC-2026-0007 (derived) | TEST_OR_MEASUREMENT_DEFECT | TRIAGED | — | 16 | #2058, #2077, #2090, #2091, #2092, #2098, #2109, #2144 … |  | Full Red Proof Summary (dependent red) |
| ABACUS-RC-2026-0008 | SECURITY_OR_POLICY | DISCOVERED | — | 0 | — |  | Safety scanner exit 64 (unclassified: auth, invocation, version or vulnerability) |
| ABACUS-RC-2026-0009 | TEST_OR_MEASUREMENT_DEFECT | VERIFIED_FIXED | GBOGEB | 1 | #2144 |  | Bandit census coverage producer (module identity / JUnit receipt mismatch) |
| CODEX-RC-2026-0001 | SECURITY_OR_POLICY | DISCOVERED | — | 0 | — |  | OSV-Scanner reporter fails on every CODEX main push |
| CODEX-RC-2026-0002 | GENERATED_ARTIFACT_DRIFT | VERIFIED_FIXED | GBOGEB | 0 | — |  | Deterministic materializations differed after |
| CODEX-RC-2026-0003 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=none; gaps=4 | CODEX default branch unprotected (no ruleset) |
| CRYO-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=none; gaps=4 | cryoplant-project default branch unprotected (no ruleset) |
| GGMATH-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=none; gaps=4 | gg_MATH default branch unprotected (no ruleset) |
| PAH-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=none; gaps=6; ruleset 25252917 'QPS TRAIGE project' is active but targets no branch | pipeline-automation-hub ruleset active but targets no branch |
| QET-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=none; gaps=4 | Q_engineering_tools default branch unprotected (no ruleset) |

## Unmatched signatures (candidate roots — search the ledger before repairing)

| Signature | Occurrences | PRs | Example |
|---|---|---|---|
| `CI/CD Test Suite :: Unit Tests :: Run Unit Tests` | 54 | #2090, #2098, #2144, #2145, #2205 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39089613256/job/117563356362) |
| `CI - ABACUS Matrix :: ABACUS :: Run functional compatibility proof` | 26 | #2090, #2092, #2098, #2145, #2190, #2191 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39050952858/job/117449946700) |
| `CI - ABACUS Matrix :: ABACUS compatibility gate :: Enforce selected proof set` | 22 | #2058, #2090, #2092, #2098, #2144, #2145 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39050952858/job/117455983133) |
| `CI - ABACUS Matrix :: Python proof completeness :: Audit executed and classified-skipped proof roles` | 22 | #2058, #2090, #2092, #2098, #2144, #2145 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39050952858/job/117452971875) |
| `CI - ABACUS Matrix :: ABACUS :: Run canonical coverage and emit governed evidence` | 20 | #2090, #2092, #2098, #2144, #2145, #2190 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39050952858/job/117449946841) |
| `CODEX Semantic Runtime CI :: semantic-validation :: Run semantic validator` | 19 | #1068, #1069, #1070, #1071, #1073, #1074 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39118198940/job/117648202462) |
| `CI :: test :: Run tests` | 15 | #1068, #1069, #1070, #1071, #1072, #1073 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39118199013/job/117648202582) |
| `MissionControl Mycelium CI :: validate :: Mycelium N7: standalone continuity testflight` | 14 | #1068, #1069, #1070, #1071, #1072, #1073 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39126570729/job/117672842776) |
| `Full Stack Governance CI :: lineage-governance (abacus) :: Governance validation` | 12 | #1068, #1069, #1070, #1074, #1075, #1076 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39117733919/job/117646835366) |
| `CI Workflow Governance :: policy-and-inventory :: Fail closed on governance red` | 8 | #2090, #2091, #2101, #2144, #2145, #2202 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39131584237/job/117687687592) |
| `Validate Docs (Markdown/YAML/JSON) :: Changed docs lint :: Validate changed docs` | 7 | #2063, #2090, #2091, #2098, #2145, #2151 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39050983265/job/117449339277) |
| `Full Stack Governance CI :: lineage-governance (codex) :: Governance validation` | 7 | #1071, #1072, #1073, #1078, #1079, #1080 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39118020851/job/117647676441) |
| `W003 Governance Gate :: governance-gate :: Run governance parser on PR metadata` | 7 | #1068, #1069, #1070, #1071, #1072, #1073 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39075465807/job/117521587196) |
| `DOW + Recursive DMAIC - Enhanced CI :: Test (3.11) :: Run python -m coverage erase` | 6 | #2190, #2191, #2192, #2193, #2194, #2200 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39080367179/job/117554064162) |
| `ABACUS v032 - CI/CD Pipeline :: Test DMAIC Phases :: Install canonical dependencies` | 5 | #2058, #2063, #2144, #2145, #2151 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39050983178/job/117459950402) |
| `MIP B0 Test Admission and Coverage Evidence :: B0 report-only admission census :: Require all exact-SHA producers GREEN` | 5 | #2145, #2151, #2198, #2202, #2204 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39050983183/job/117451202034) |
| `MIP B0 Test Admission and Coverage Evidence :: B0 report-only admission census :: Upload B0 report-only evidence` | 5 | #2145, #2151, #2198, #2202, #2204 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39050983183/job/117451202034) |
| `Mission Control Lite Testflight :: native-proof :: Run selector and telemetry negative controls` | 5 | #2190, #2191, #2192, #2193, #2194 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39066207414/job/117494312953) |
| `qps-canonicalization :: validate :: Run python3 ../scripts/qps_w163_validate_namespace_collisions.py --repo-root .. --recent-pr-json triage/w163/QPS_W163_RECENT_PR_COLLISION_CENSUS_v0.1.json --github-event-json "$GITHUB_EVENT_PATH" --skip-live-pr-scan` | 5 | #1936, #1937, #1938, #1942, #1944 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/39026793048/job/117379250769) |
| `MIP B0 Test Admission and Coverage Evidence :: B0 canonical coverage producer :: Run canonical exact-head coverage surface` | 4 | #2145, #2151, #2202, #2204 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39050983183/job/117449339433) |
| `CI/CD Test Suite :: Security Scanning :: PR new-debt ratchet (Bandit)` | 4 | #2058, #2090, #2098, #2151 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39050983150/job/117449339330) |
| `DMAIC V3 Enterprise CI :: CI Summary :: Set final status` | 4 | #2077, #2191, #2194, #2200 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39024179288/job/117379745916) |
| `EVERRED V3 Governed Control Plane :: EVERRED source, provenance and negative tests (3.10) :: Verify committed Black and isort styles` | 3 | #2077, #2091, #2101 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39023241727/job/117369083206) |
| `EVERRED V3 Governed Control Plane :: EVERRED source, provenance and negative tests (3.12) :: Verify committed Black and isort styles` | 3 | #2077, #2091, #2101 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39023241727/job/117369082995) |
| `DMAIC V3 Enterprise CI :: Test on macos-latest :: Install dependencies` | 3 | #2077, #2191, #2194 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39024179288/job/117371788810) |
| `DMAIC V3 Enterprise CI :: Test on ubuntu-latest :: Install dependencies` | 3 | #2077, #2191, #2194 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39024179288/job/117371788698) |
| `DMAIC V3 Enterprise CI :: Test on windows-latest :: Install dev dependencies` | 3 | #2077, #2191, #2194 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39024179288/job/117371788684) |
| `Runtime Release Gate :: governance-checks :: Run python scripts/check_manifest.py` | 3 | #1072, #1075, #1077 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39107870576/job/117617701263) |
| `QPS W163 Namespace Collision Control :: namespace-control :: Validate taxonomy, aliases, files and bound recent PR census` | 3 | #1937, #1938, #1944 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/39026725473/job/117379055966) |
| `CI - ABACUS Matrix :: ABACUS :: Install tooling` | 2 | #2058, #2145 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39050952858/job/117449946851) |
| `a10-guard :: a10-guard :: Tender guard (new or changed files only)` | 2 | #2090, #2144 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39050617820/job/117448269427) |
| `CBD Native Evidence Metrics Testflight :: Native evidence contracts () :: Verify scope, line/branch denominator and test verdict` | 2 | #2092 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39029019192/job/117650737224) |
| `CI/CD Test Suite :: Code Quality Checks :: Per-tool code-quality new-debt ratchet` | 2 | #2058, #2077 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39024179357/job/117371789109) |
| `W286 GLOOB Pandoc 3PC Prove :: prove :: Check semantic vocabulary` | 2 | #1072, #1083 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39118198996/job/117648202643) |
| `ABACUS Multi-Format Publication :: multiformat-publication :: Validate semantic vocabulary before rendering` | 2 | #1071, #1072 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39083968053/job/117546537808) |
| `qps-canonicalization :: validate :: Run npm test` | 2 | #1940, #1941 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/39025357686/job/117375161709) |
| `G3A N14-N15 matched four-module branch flight :: matched-four-module :: Source guard` | 1 | #2145 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39050952812/job/117449248312) |
| `Pytest Config Validation :: validate-config :: Validate markers (strict mode)` | 1 | #2098 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39028597870/job/117384393654) |
| `DOW + Recursive DMAIC - Enhanced CI :: Test (3.11) :: Run pytest --benchmark-disable -v -n auto --cov=. --cov-report=term-missing --cov-report=xml` | 1 | #2092 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39029019348/job/117651094762) |
| `CBD E2E Graph Contract QA :: graph-contract (3.11) :: Execute snapshot contract and negative tests` | 1 | #2090 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39051654415/job/117451307828) |
| `TestPilot Pre-GitHub Parity :: parity :: Run bounded TestPilot fast preflight` | 1 | #2090 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39051654468/job/117451307811) |
| `TestPilot Pre-GitHub Parity :: parity :: Replay pre-push source-bound checks on exact GitHub head` | 1 | #2090 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39051654468/job/117451307811) |
| `TestPilot Pre-GitHub Parity :: parity :: Isolated fresh local Git clone and equivalent testflight` | 1 | #2090 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39051654468/job/117451307811) |
| `TestPilot Pre-GitHub Parity :: parity :: Exact-source N-to-N+1 replay comparison` | 1 | #2090 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39051654468/job/117451307811) |
| `TestPilot Pre-GitHub Parity :: parity :: Upload TestPilot receipt` | 1 | #2090 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39051654468/job/117451307811) |
| `CBD E2E Graph Contract QA :: graph-contract (3.12) :: Execute snapshot contract and negative tests` | 1 | #2090 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39051654415/job/117451307612) |
| `EVERRED V3 Governed Control Plane :: EVERRED source, provenance and negative tests (3.10) :: Produce source-bound Black repair patch on style failure` | 1 | #2077 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39024179339/job/117371827223) |
| `EVERRED V3 Governed Control Plane :: EVERRED source, provenance and negative tests (3.12) :: Produce source-bound Black repair patch on style failure` | 1 | #2077 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39024179339/job/117371827109) |
| `DMAIC V3 Bridge Integration - Test System :: 📊 Static Analysis :: Run mypy` | 1 | #2207 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39080831340/job/117537241618) |
| `Gloob causal responder :: responder :: Resolve dispatch ticket` | 1 | #2207 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39080831305/job/117537241605) |
| `MissionControl Mycelium CI :: validate :: Preflight generated-value parity before expensive tests` | 1 | #1086 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39126616941/job/117672982168) |
| `CI :: test :: Check manifest` | 1 | #1082 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39118020708/job/117647675736) |
| `GISTAU Physics Crosscheck :: crosscheck :: Gate on Ch15 canonical validation (L1)` | 1 | #1075 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39107121187/job/117615304667) |
| `ABACUS Semantic Runtime :: semantic-runtime :: Run repository semantic vocabulary validator` | 1 | #1072 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39083968227/job/117546538725) |
| `QPS KEB W43 TRIAGE :: keb-w43-triage :: Execute source-bound W43 KEB exchange` | 1 | #1072 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39083968145/job/117546538142) |
| `CODE PURPLE Branch Protection MIP V2 :: Exact-head mandatory check contract and negative testflight :: Run adversarial evidence tests` | 1 | #1072 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39083968176/job/117546537946) |
| `MASTER Contract SSOT Validation :: validate-master-contract-ssot :: Validate MASTER contract SSOT` | 1 | #1072 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39083968088/job/117546537847) |
| `ABACUS Snapshot Publication :: snapshot-publication :: Validate semantic vocabulary before visual execution` | 1 | #1072 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39083968104/job/117546537816) |
| `ABACUS Snapshot Publication :: snapshot-publication :: Upload image-native execution evidence` | 1 | #1072 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39083968104/job/117546537816) |
| `QPS W05 bidder evaluation KEB receipt :: execute-validate :: Validate repository semantic substrate` | 1 | #1072 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39083968095/job/117546537696) |
| `W86 Cryoplant Child Proof Bypass :: prove-child :: Checkout exact cryoplant merge SHA` | 1 | #1072 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39083967870/job/117546537290) |
| `W105 QPS B1-B2 MIP Probe :: qps-probe :: Checkout exact QPS child SHA` | 1 | #1072 | [run](https://github.com/GBOGEB/CODEX/actions/runs/39083967339/job/117546535920) |
| `QPS BD Queue Integrity :: parity :: Validate live issue parity and partial-return no-close guards` | 1 | #1951 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/39049288512/job/117444405286) |
| `QPS W163 CH Plot Referent Proof :: w163-chart :: Qualify CH1-CH3 plot and 19 adverse native tests with coverage` | 1 | #1944 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/39026725500/job/117379055915) |
