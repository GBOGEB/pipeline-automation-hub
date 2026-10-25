# EVERRED register

Census 2026-10-25T18:44:03+00:00 · scope GBOGEB/ABACUS, GBOGEB/CODEX, GBOGEB/cryoplant-project

## Metrics

- **occurrences_total**: 151
- **occurrences_on_independent_roots**: 6
- **distinct_signatures**: 64
- **roots_independent**: 15
- **roots_triaged_or_later**: 13
- **unmatched_signatures**: 62
- **failure_amplification**: 0.462
- **failure_amplification_note**: occurrences linked to triaged independent roots / triaged independent roots
- **signature_amplification_upper_bound**: 2.359
- **root_closure_rate**: 0.267
- **recurrence_rate**: 0.0
- **consumer_replay_coverage**: UNKNOWN
- **consumer_replay_note**: no replay outcomes recorded yet; 13 roots list consumers
- **active_roots_by_state**: {'BLOCKED_AUTHORITY': 5, 'OWNED': 1, 'TRIAGED': 2, 'PRODUCER_GREEN': 1, 'VERIFIED_FIXED': 4, 'DISCOVERED': 2}
- **occurrences_by_source**: {'open-pr': 96, 'merged-pr': 53, 'main:head': 2}
- **control_plane_red**: 5
- **control_plane_probed**: 6
- **dims**: {'diagnosis': {'CONFIRMED': 11, 'CANDIDATE': 2, 'UNRESOLVED': 2}, 'repair': {'PROPOSED': 6, 'NONE': 4, 'COMMITTED': 1, 'PRODUCER_VERIFIED': 4}, 'integration': {'NA': 6, 'NOT_EVALUATED': 5, 'EXACT_HEAD_PASSED': 4}, 'security': {'NA': 12, 'RED': 1, 'UNKNOWN': 2}, 'governance': {'INEFFECTIVE': 10, 'UNKNOWN': 4, 'EFFECTIVE': 1}, 'admission': {'NA': 8, 'HOLD': 4, 'ADMITTED': 3}, 'control': {'UNCONTROLLED': 10, 'UNDER_OBSERVATION': 5}}

## Roots

| Root | Class | State | Owner | Occurrences | PRs | Probe | Title |
|---|---|---|---|---|---|---|---|
| ABACUS-RC-2026-0001 | CONTROL_PLANE_DRIFT | BLOCKED_AUTHORITY | GBOGEB | 0 | — | RED: effective=deletion,pull_request,non_fast_forward,code_quality,copilot_code_review; gaps=2 | ABACUS default branch has no required status checks (rules emptied 12 Oct; partly restored 15 Oct) |
| ABACUS-RC-2026-0002 | EXISTING_REPOSITORY_DEBT | OWNED | GBOGEB | 0 | — |  | Fixed 75% repository coverage threshold above measured main coverage (structural admission deadlock) |
| ABACUS-RC-2026-0003 | EXISTING_REPOSITORY_DEBT | TRIAGED | — | 6 | #2360, #2434, #2437, #2438, #2439 |  | Code-quality full-red surface (Black / isort / Flake8 umbrella) |
| ABACUS-RC-2026-0004 | SECURITY_OR_POLICY | TRIAGED | — | 0 | — |  | Bandit full-scan security debt (6,363 raw observations) |
| ABACUS-RC-2026-0005 | TEST_OR_MEASUREMENT_DEFECT | PRODUCER_GREEN | GBOGEB | 0 | — |  | DMAIC measurement-receipt failure broke the broad coverage suite |
| ABACUS-RC-2026-0006 | GENERATED_ARTIFACT_DRIFT | VERIFIED_FIXED | Claude | 0 | — |  | Workflow rationalization report stale after policy change |
| ABACUS-RC-2026-0007 (derived) | TEST_OR_MEASUREMENT_DEFECT | TRIAGED | — | 7 | #2360, #2368, #2433, #2434, #2437 |  | Full Red Proof Summary (dependent red) |
| ABACUS-RC-2026-0008 | SECURITY_OR_POLICY | DISCOVERED | — | 0 | — |  | Safety scanner exit 64 (unclassified: auth, invocation, version or vulnerability) |
| ABACUS-RC-2026-0009 | TEST_OR_MEASUREMENT_DEFECT | VERIFIED_FIXED | GBOGEB | 0 | — |  | Bandit census coverage producer (module identity / JUnit receipt mismatch) |
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
| `Validate Docs (Markdown/YAML/JSON) :: Changed docs lint :: Validate changed docs` | 12 | #2360, #2368, #2422, #2431, #2436, #2437 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221786375/job/121254718510) |
| `W003 Governance Gate :: governance-gate :: Run governance parser on PR metadata` | 12 | #1167, #1168, #1169, #1170, #1188, #1189 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40221900954/job/121255075310) |
| `CI/CD Test Suite :: Security Scanning :: PR new-debt ratchet (Bandit)` | 6 | #2434, #2437, #2438, #2439, #2442 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221786424/job/121254719389) |
| `Stranded-push guard :: guard :: (job failed, no failed step)` | 5 | #2086, #2091, #2092 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012345/job/121255418502) |
| `Release Runner Probe :: hosted-runner-probe :: (job failed, no failed step)` | 5 | #2086, #2091, #2092, #2093 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012268/job/121255418435) |
| `W71 Unresolved Binary Lineage Census :: unresolved-binary-lineage :: (job failed, no failed step)` | 4 | #2086, #2091, #2092, #2093 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012294/job/121255418399) |
| `W69 Runner Family Discrimination :: ubuntu_latest :: (job failed, no failed step)` | 4 | #2086, #2091, #2092, #2093 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012333/job/121255418363) |
| `CI/CD Test Suite :: Code Quality Checks :: Per-tool code-quality new-debt ratchet` | 3 | #2441, #2442 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221786424/job/121254719469) |
| `a10-guard :: a10-guard :: Tender guard (new or changed files only)` | 3 | #2437, #2441 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221740474/job/121254575404) |
| `CI - ABACUS Matrix :: ABACUS compatibility gate :: Enforce selected proof set` | 3 | #2433, #2438 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40220997476/job/121256467816) |
| `CI - ABACUS Matrix :: Python proof completeness :: Audit executed and classified-skipped proof roles` | 3 | #2433, #2438 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40220997476/job/121256395094) |
| `QPS PR binary refresh :: refresh-current-pr :: (job failed, no failed step)` | 3 | #2086, #2091, #2092 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012300/job/121255418514) |
| `Release Runner Probe :: configured-runner-probe :: (job failed, no failed step)` | 3 | #2086, #2091, #2092 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012268/job/121255418436) |
| `W56 Total Repo Control :: recurrence-control :: (job failed, no failed step)` | 3 | #2086, #2092, #2093 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012270/job/121255418381) |
| `Global Victory Score :: emit-global-victory-score :: (job failed, no failed step)` | 3 | #2086, #2091, #2092 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012293/job/121255418343) |
| `W56 Total Repo Control :: sentinel :: (job failed, no failed step)` | 3 | #2086, #2091, #2092 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012270/job/121255418282) |
| `W56 Total Repo Control :: total-repo-census :: (job failed, no failed step)` | 3 | #2086, #2091, #2092 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012270/job/121255418252) |
| `qps-canonicalization :: validate :: (job failed, no failed step)` | 3 | #2086, #2092, #2093 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012256/job/121255418250) |
| `TRIAGE PXA Runner Sentinel :: sentinel :: (job failed, no failed step)` | 3 | #2086, #2092, #2093 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012267/job/121255418243) |
| `DELTA_1 Federation Smoke :: federation-smoke :: (job failed, no failed step)` | 3 | #2086, #2091, #2092 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012281/job/121255418203) |
| `TestPilot Pre-GitHub Parity :: parity :: Run bounded TestPilot fast preflight` | 2 | #2431, #2442 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221786372/job/121254718704) |
| `TestPilot Pre-GitHub Parity :: parity :: Replay pre-push source-bound checks on exact GitHub head` | 2 | #2431, #2442 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221786372/job/121254718704) |
| `TestPilot Pre-GitHub Parity :: parity :: Isolated fresh local Git clone and equivalent testflight` | 2 | #2431, #2442 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221786372/job/121254718704) |
| `TestPilot Pre-GitHub Parity :: parity :: Exact-source N-to-N+1 replay comparison` | 2 | #2431, #2442 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221786372/job/121254718704) |
| `TestPilot Pre-GitHub Parity :: parity :: Upload TestPilot receipt` | 2 | #2431, #2442 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40221786372/job/121254718704) |
| `QPS KEB W43 TRIAGE :: keb-w43-triage :: Execute source-bound W43 KEB exchange` | 2 | #1170, #1171 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40124460556/job/120962793127) |
| `W69 Runner Family Discrimination :: ubuntu_2204 :: (job failed, no failed step)` | 2 | #2092, #2093 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012333/job/121255418865) |
| `verify-ssot :: verify :: (job failed, no failed step)` | 2 | #2086, #2092 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012321/job/121255418451) |
| `DELTA_1 Federation Smoke :: coolprop-property-tunnel :: (job failed, no failed step)` | 2 | #2086, #2092 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012281/job/121255418403) |
| `CI - ABACUS Matrix :: ABACUS :: Run canonical coverage and emit governed evidence` | 1 | #2438 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40220997476/job/121253114657) |
| `CI/CD Test Suite :: Code Quality Checks :: (job failed, no failed step)` | 1 | #2368 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/39829407794/job/120918457390) |
| `CI Workflow Governance :: policy-and-inventory :: Fail closed on governance red` | 1 | #2425 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40105070967/job/120904950429) |
| `DMAIC V3 Enterprise CI :: CI Summary :: Set final status` | 1 | #2426 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40106140099/job/120908896318) |
| `DOW + Recursive DMAIC - Enhanced CI :: Test (3.11) :: Run python -m coverage erase` | 1 | #2426 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40106140130/job/120908719381) |
| `DMAIC V3 Enterprise CI :: Test on ubuntu-latest :: Install dependencies` | 1 | #2426 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40106140099/job/120908106543) |
| `DMAIC V3 Enterprise CI :: Test on windows-latest :: Install dev dependencies` | 1 | #2426 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40106140099/job/120908106488) |
| `DMAIC V3 Enterprise CI :: Test on macos-latest :: Install dependencies` | 1 | #2426 | [run](https://github.com/GBOGEB/ABACUS/actions/runs/40106140099/job/120908106445) |
| `CI :: test :: Check stale artifacts` | 1 | #1192 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40221715719/job/121254501200) |
| `Full Stack Governance CI :: lineage-governance (abacus) :: Governance validation` | 1 | #1192 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40221715682/job/121254500587) |
| `MissionControl Inventory Autoregen :: autoregen :: Commit refreshed receipts to the PR branch` | 1 | #1178 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40133918972/job/120991290970) |
| `MissionControl Mycelium CI :: validate :: Preflight generated-value parity before expensive tests` | 1 | #1178 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40133910012/job/120991262343) |
| `MIP QPS External Probe :: qps_external_probe :: Checkout exact cryoplant child` | 1 | #1171 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40124460446/job/120962793063) |
| `CODE PURPLE Branch Protection MIP V2 :: Exact-head mandatory check contract and negative testflight :: Run adversarial evidence tests` | 1 | #1170 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40124449411/job/120962762693) |
| `MASTER Contract SSOT Validation :: validate-master-contract-ssot :: Validate MASTER contract SSOT` | 1 | #1170 | [run](https://github.com/GBOGEB/CODEX/actions/runs/40124449364/job/120962762562) |
| `QPS TRIAGE Debug DAG Pilot :: execute QPS native LLDB node :: (job failed, no failed step)` | 1 | main | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40221352100/job/121254405875) |
| `QPS Triage Console Refresh :: refresh :: Propose snapshot as a PR (never merges)` | 1 | main | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40221569815/job/121254065844) |
| `JADE CI (core suite, fail-closed) :: ci / Tests (zero-test guard + coverage floor) :: (job failed, no failed step)` | 1 | #2092 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40222012614/job/121255419183) |
| `QPS W163 Namespace Collision Control :: namespace-control :: (job failed, no failed step)` | 1 | #2091 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40221766904/job/121254659089) |
| `TRIAGE Repository Census :: runner-preflight :: (job failed, no failed step)` | 1 | #2086 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40221899977/job/121255072354) |
| `QPS W371 / W373 offer cool-down check and :: offer-check :: (job failed, no failed step)` | 1 | #2086 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40221899969/job/121255072108) |
| `W69 Runner Family Discrimination :: windows_latest :: (job failed, no failed step)` | 1 | #2093 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40223306028/job/121259343078) |
| `QPS BDQ identity crosswalk controls :: crosswalk (3.12) :: (job failed, no failed step)` | 1 | #2093 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40223306016/job/121259342741) |
| `QPS W369 LOOP boil-off :: loop :: (job failed, no failed step)` | 1 | #2093 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40223306029/job/121259342708) |
| `QPS Dependency SPINE Read-only Census :: Five-repository contract, QPS exact-head native observer :: (job failed, no failed step)` | 1 | #2093 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40223305977/job/121259342700) |
| `QPS CODE_BNB N3 daily owner burn-down (read-only) :: n3-browser-offline :: Browser 3-viewport interaction and offline security QA` | 1 | #2071 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40116415306/job/120938638597) |
| `QPS BB JADE LKT source-safe qualification :: pwsh-interface-smoke :: Run actions/checkout@<sha>` | 1 | #2071 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40116415710/job/120938517483) |
| `QPS BD Queue Integrity :: parity :: Validate live issue parity and partial-return no-close guards` | 1 | #2071 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40116415722/job/120938517314) |
| `QPS N0 source-safe universal layout native qualification :: layout / ubuntu-latest / py3.11 :: Run exact-head Git tracked file and source-anchor recensus` | 1 | #2062 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40104157173/job/120926356515) |
| `QPS N0 source-safe universal layout native qualification :: layout / ubuntu-latest / py3.12 :: Run exact-head Git tracked file and source-anchor recensus` | 1 | #2062 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40104157173/job/120926356460) |
| `QPS N0 source-safe universal layout native qualification :: layout / windows-latest / py3.12 :: Run actions/checkout@<sha>` | 1 | #2062 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40104157173/job/120926356432) |
| `QPS N0 source-safe universal layout native qualification :: layout / windows-latest / py3.11 :: Run actions/checkout@<sha>` | 1 | #2062 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40104157173/job/120926356288) |
| `QPS W368 cool-down full rebuild :: cooldown :: Deck views (PPTX is SKIPPED without the private SCK master)` | 1 | #2061 | [run](https://github.com/GBOGEB/cryoplant-project/actions/runs/40103505738/job/120900315619) |
