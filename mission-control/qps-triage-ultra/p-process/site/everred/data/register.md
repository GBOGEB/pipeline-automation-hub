# EVERRED register

Census 2026-10-25T19:36:17+00:00 · scope GBOGEB/ABACUS, GBOGEB/CODEX, GBOGEB/cryoplant-project

## Metrics

- **occurrences_total**: 452
- **occurrences_on_independent_roots**: 9
- **distinct_signatures**: 90
- **roots_independent**: 15
- **roots_triaged_or_later**: 13
- **unmatched_signatures**: 87
- **failure_amplification**: 0.692
- **failure_amplification_note**: occurrences linked to triaged independent roots / triaged independent roots
- **signature_amplification_upper_bound**: 5.022
- **root_closure_rate**: 0.2
- **recurrence_rate**: 0.0
- **consumer_replay_coverage**: UNKNOWN
- **consumer_replay_note**: no replay outcomes recorded yet; 13 roots list consumers
- **active_roots_by_state**: {'BLOCKED_AUTHORITY': 6, 'OWNED': 1, 'TRIAGED': 2, 'PRODUCER_GREEN': 1, 'VERIFIED_FIXED': 3, 'DISCOVERED': 2}
- **occurrences_by_source**: {'main:nightly': 3, 'open-pr': 313, 'merged-pr': 131, 'main:head': 5}
- **control_plane_red**: 5
- **control_plane_probed**: 6
- **dims**: {'diagnosis': {'CONFIRMED': 11, 'CANDIDATE': 2, 'UNRESOLVED': 2}, 'repair': {'PROPOSED': 7, 'NONE': 4, 'COMMITTED': 1, 'PRODUCER_VERIFIED': 3}, 'integration': {'NA': 6, 'NOT_EVALUATED': 5, 'EXACT_HEAD_PASSED': 4}, 'security': {'NA': 12, 'RED': 1, 'UNKNOWN': 2}, 'governance': {'INEFFECTIVE': 11, 'UNKNOWN': 4}, 'admission': {'NA': 8, 'HOLD': 4, 'ADMITTED': 3}, 'control': {'UNCONTROLLED': 11, 'UNDER_OBSERVATION': 4}}

## Roots

| Root | Class | State | Owner | Occurrences | PRs | Probe | Title |
|---|---|---|---|---|---|---|---|
| ABACUS-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=deletion,pull_request,non_fast_forward,code_quality,copilot_code_review; gaps=2 | ABACUS default branch has no required status checks (rules emptied 12 Oct; partly restored 15 Oct) |
| ABACUS-RC-2026-0002 | EXISTING_REPOSITORY_DEBT | OWNED | GBOGEB | 0 | — |  | Fixed 75% repository coverage threshold above measured main coverage (structural admission deadlock) |
| ABACUS-RC-2026-0003 | EXISTING_REPOSITORY_DEBT | TRIAGED | — | 7 | #2360, #2433, #2434, #2437, #2439, #2451 |  | Code-quality full-red surface (Black / isort / Flake8 umbrella) |
| ABACUS-RC-2026-0004 | SECURITY_OR_POLICY | TRIAGED | — | 2 | #2451 |  | Bandit full-scan security debt (6,363 raw observations) |
| ABACUS-RC-2026-0005 | TEST_OR_MEASUREMENT_DEFECT | PRODUCER_GREEN | GBOGEB | 0 | — |  | DMAIC measurement-receipt failure broke the broad coverage suite |
| ABACUS-RC-2026-0006 | GENERATED_ARTIFACT_DRIFT | VERIFIED_FIXED | Claude | 0 | — |  | Workflow rationalization report stale after policy change |
| ABACUS-RC-2026-0007 (derived) | TEST_OR_MEASUREMENT_DEFECT | TRIAGED | — | 9 | #2360, #2368, #2433, #2434, #2437, #2439, #2441, #2442 |  | Full Red Proof Summary (dependent red) |
| ABACUS-RC-2026-0008 | SECURITY_OR_POLICY | DISCOVERED | — | 0 | — |  | Safety scanner exit 64 (unclassified: auth, invocation, version or vulnerability) |
| ABACUS-RC-2026-0009 | TEST_OR_MEASUREMENT_DEFECT | VERIFIED_FIXED | GBOGEB | 0 | — |  | Bandit census coverage producer (module identity / JUnit receipt mismatch) |
| CODEX-RC-2026-0001 | SECURITY_OR_POLICY | DISCOVERED | — | 0 | — |  | OSV-Scanner reporter fails on every CODEX main push |
| CODEX-RC-2026-0002 | GENERATED_ARTIFACT_DRIFT | VERIFIED_FIXED | GBOGEB | 0 | — |  | Deterministic materializations differed after |
| CODEX-RC-2026-0003 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=deletion,non_fast_forward,required_status_checks,pull_request; gaps=5 | CODEX default branch unprotected (no ruleset) |
| CRYO-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=deletion,non_fast_forward,pull_request; gaps=2 | cryoplant-project default branch unprotected (no ruleset) |
| GGMATH-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=deletion,non_fast_forward,code_scanning,code_quality,copilot_code_review,pull_request; gaps=2 | gg_MATH default branch unprotected (no ruleset) |
| PAH-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | green: effective=deletion,non_fast_forward,pull_request,required_status_checks,required_linear_history,copilot_code_review,deletion,non_fast_forward,required_linear_history,copilot_code_review,code_quality; gaps=0 | pipeline-automation-hub ruleset active but targets no branch |
| QET-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=none; gaps=4 | Q_engineering_tools default branch unprotected (no ruleset) |

## Unmatched signatures (candidate roots — search the ledger before repairing)

| Signature | Occurrences | PRs | Example |
|---|---|---|---|
| `Validate Docs (Markdown/YAML/JSON) :: Changed docs lint :: Validate changed docs` | 20 | #2360, #2368, #2431, #2433, #2436, #2437 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223438065/job/121259737535) |
| `W003 Governance Gate :: governance-gate :: Run governance parser on PR metadata` | 7 | #1188, #1189, #1190, #1191, #1192, #1193 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40223207380/job/121259044358) |
| `CBD Native Evidence Metrics Testflight :: Native evidence contracts () :: Verify scope, line/branch denominator and test verdict` | 6 | #2451, #2459, #2461 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223325284/job/121259401660) |
| `CI/CD Test Suite :: Unit Tests :: Run Unit Tests` | 6 | #2451 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223165810/job/121258920800) |
| `DMAIC V3 Enterprise CI :: Test on windows-latest :: Install dev dependencies` | 6 | #2443, #2444, #2445, #2446, #2447 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222868916/job/121258028679) |
| `DMAIC V3 Enterprise CI :: Test on macos-latest :: Install dependencies` | 6 | #2443, #2444, #2445, #2446, #2447 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222868916/job/121258028656) |
| `DMAIC V3 Enterprise CI :: Test on ubuntu-latest :: Install dependencies` | 6 | #2443, #2444, #2445, #2446, #2447 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222868916/job/121258028603) |
| `DMAIC V3 Enterprise CI :: CI Summary :: Set final status` | 5 | #2443, #2444, #2445, #2446, #2447 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222868916/job/121262605887) |
| `DOW + Recursive DMAIC - Enhanced CI :: Test (3.11) :: Run python -m coverage erase` | 5 | #2443, #2444, #2445, #2446, #2447 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222868875/job/121262125977) |
| `CI/CD Test Suite :: Security Scanning :: PR new-debt ratchet (Bandit)` | 5 | #2433, #2434, #2437, #2439, #2442 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221161710/job/121252832494) |
| `W29-W33 Disjoint Frontier Coverage :: W29 native ubuntu py3.10 :: Verify files and save provenance with count reconciliation` | 3 | #2451, #2459, #2461 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223325403/job/121259402221) |
| `CBD E2E Graph Contract QA :: graph-contract (3.12) :: Execute snapshot contract and negative tests` | 3 | #2451, #2459, #2461 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223325443/job/121259402125) |
| `CBD E2E Graph Contract QA :: graph-contract (3.11) :: Execute snapshot contract and negative tests` | 3 | #2451, #2459, #2461 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223325443/job/121259401980) |
| `W29-W33 Disjoint Frontier Coverage :: W29 native ubuntu py3.12 :: Verify files and save provenance with count reconciliation` | 3 | #2451, #2459, #2461 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223325403/job/121259401927) |
| `ABACUS W13 Weighted Neural SPINE :: graph-proof (3.11) :: Native W13 typed graph checks and coverage` | 3 | #2451, #2459, #2461 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223325219/job/121259401212) |
| `ABACUS W13 Weighted Neural SPINE :: graph-proof (3.12) :: Native W13 typed graph checks and coverage` | 3 | #2451, #2459, #2461 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223325219/job/121259400895) |
| `W26 TestPilot matched behavioral coverage :: ubuntu-latest matched coverage :: Test negative coverage receipt semantics` | 3 | #2451 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223164746/job/121258918170) |
| `a10-guard :: a10-guard :: Tender guard (new or changed files only)` | 3 | #2437, #2441, #2445 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222856970/job/121257992840) |
| `Full Stack Governance CI :: lineage-governance (abacus) :: Governance validation` | 3 | #1187, #1192, #1193 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40223207328/job/121259044159) |
| `CI :: test :: Check stale artifacts` | 3 | #1187, #1192, #1193 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40223207283/job/121259044012) |
| `CI/CD Test Suite :: Code Quality Checks :: Per-tool code-quality new-debt ratchet` | 2 | #2441, #2442 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221786424/job/121254719469) |
| `TestPilot Pre-GitHub Parity :: parity :: Run bounded TestPilot fast preflight` | 2 | #2431, #2442 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221786372/job/121254718704) |
| `TestPilot Pre-GitHub Parity :: parity :: Replay pre-push source-bound checks on exact GitHub head` | 2 | #2431, #2442 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221786372/job/121254718704) |
| `TestPilot Pre-GitHub Parity :: parity :: Isolated fresh local Git clone and equivalent testflight` | 2 | #2431, #2442 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221786372/job/121254718704) |
| `TestPilot Pre-GitHub Parity :: parity :: Exact-source N-to-N+1 replay comparison` | 2 | #2431, #2442 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221786372/job/121254718704) |
| `TestPilot Pre-GitHub Parity :: parity :: Upload TestPilot receipt` | 2 | #2431, #2442 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221786372/job/121254718704) |
| `CI Workflow Governance :: policy-and-inventory :: Fail closed on governance red` | 1 | #2457 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223312240/job/121259360464) |
| `EVERRED V3 Governed Control Plane :: EVERRED source, provenance and negative tests (3.12) :: Verify committed Black and isort styles` | 1 | #2451 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223164840/job/121258919239) |
| `EVERRED V3 Governed Control Plane :: EVERRED source, provenance and negative tests (3.10) :: Verify committed Black and isort styles` | 1 | #2451 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223164840/job/121258919048) |
| `MIP B0 Test Admission and Coverage Evidence :: B0 canonical coverage producer :: Run canonical exact-head coverage surface` | 1 | #2451 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223164895/job/121258918922) |
| `W26 TestPilot matched behavioral coverage :: windows-latest matched coverage :: Test negative coverage receipt semantics` | 1 | #2451 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223164746/job/121258918186) |
| `cryoplant-project Federation Check :: Federation Smoke (cryoplant-project) :: Run cryoplant-project local smoke tests` | 1 | #2451 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40223164508/job/121258918089) |
| `Ariana CI/CD :: DOW / KEB / QPS evidence-only two-lane join :: Require both native lanes to be green` | 1 | #2445 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222856887/job/121260703346) |
| `Ariana CI/CD :: DOW / KEB / QPS evidence-only two-lane join :: Upload source-bound federation join` | 1 | #2445 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222856887/job/121260703346) |
| `DMAIC V3 Test Suite - Continuous Integration :: Unit Tests (3.12) :: Install dependencies` | 1 | #2445 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222856947/job/121260251651) |
| `CI - ABACUS Matrix :: ABACUS :: Install tooling` | 1 | #2445 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222856859/job/121260086493) |
| `MIP Python Compatibility Combined-Head Probe :: compatibility (3.12) :: Install full canonical DMAIC requirement set` | 1 | #2445 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222856990/job/121257992845) |
| `Ariana CI/CD :: Ariana/DOW native :: Install source-owned test dependencies` | 1 | #2445 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222856887/job/121257992708) |
| `Ariana CI/CD :: Ariana/DOW native :: Upload named local evidence (fail if missing)` | 1 | #2445 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222856887/job/121257992708) |
| `CI - ABACUS Matrix :: Benchmark baseline - no coverage :: Install benchmark dependencies` | 1 | #2445 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222856859/job/121257992679) |
| `W72 Clean Clone Proof :: clean-clone :: Install from clean checkout` | 1 | #2445 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40222856956/job/121257992331) |
| `CI/CD Test Suite :: Code Quality Checks :: (job failed, no failed step)` | 1 | #2368 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39829407794/job/120918457390) |
| `CI - ABACUS Matrix :: ABACUS compatibility gate :: Enforce selected proof set` | 1 | #2433 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40220486675/job/121253435574) |
| `CI - ABACUS Matrix :: Python proof completeness :: Audit executed and classified-skipped proof roles` | 1 | #2433 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40220486675/job/121252310202) |
| `CI - ABACUS Matrix :: ABACUS :: Run canonical coverage and emit governed evidence` | 1 | #2433 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40220486675/job/121250823764) |
| `MissionControl Inventory Autoregen :: autoregen :: Commit refreshed receipts to the PR branch` | 1 | #1178 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40133918972/job/120991290970) |
| `MissionControl Mycelium CI :: validate :: Preflight generated-value parity before expensive tests` | 1 | #1178 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40133910012/job/120991262343) |

## Private repositories (aggregate counts only; no rows are published)

| Repo | Occurrences | Distinct signatures | Unmatched signatures | Linked roots |
|---|---|---|---|---|
| GBOGEB/cryoplant-project | 299 | 40 | 40 | — |
