# CODE PURPLE N3 — three-pulse owner-return, first-red, KPI and HTML qualification

**Evidence boundary:** GitHub Actions job data is a historical read-only source. This source tree owns a presentation adapter; the canonical six KPI definitions remain `PHASE02_KPI_TAXONOMY_v1.json`. Existing `pages_portal.py` owns publication. No native receiver dispatch, security waiver, automatic issue closure, QPS engineering acceptance or branch-rule mutation.

## P1 — owner-only governance and QPS access

- **MC #336:** At N3 baseline, `master.protected=false`. Active ruleset id `25252917` has `conditions.ref_name.include=[]`, so the active ruleset does **not** protect master; it lacks the required `First-Pass Closure Gate / first-pass-closure` status and an eligible independent human approval requirement.
- Import candidate: `N3_OWNER_MASTER_RULESET_IMPORT.json` targets `~DEFAULT_BRANCH`, requires one independent approval, resolved threads, the trusted GitHub Actions status `First-Pass Closure Gate / first-pass-closure`, and no bypass actors. This is **PROPOSED, NOT INSTALLED**. The prior QPS #1953 import proposal only requires `audit`, `validate-ultra-control`, `canonical-self-test-and-mutation`, `frozen-head-census`, with zero reviewers, and **cannot** satisfy #336 as written.
- Owner re-entry: Settings → Rules → Rulesets → import the reviewed candidate **after** verifying trusted check context/app ID and plan eligibility; read back effective `master` rules; run a non-controller RED PR to prove merge blocked, and GREEN+independently approved same-head PR to prove admission. Never interpret a static JSON file as an installed rule.
- **MC #636:** private QPS source readback still returns `SOURCE_ACCESS_UNKNOWN_FAIL_CLOSED` HTTP 404 in Mission Control native census run `39066797657`, job `117496047462`. Its ZIP/member bytes were separately verified by owner triage. A human/GitHub connector with access does **not** make the GitHub Actions `GITHUB_TOKEN` capable of reading private QPS.
- Owner re-entry: existing `tools/metric-atlas/qps_owner_flight.ps1` is a dry-run by default; approve credentials/permissions in the source owner's GitHub environment and request only bounded read-only proof, then exact-head receiver job/attempt/artifact tuple. Do not post private QPS SHA or secrets to a public PR.

## P2 — disjoint ABACUS dashboard first-red

- **ABACUS #2202:** exact-source B0 run `39066358198`, attempt 1, `4013 passed, 1 failed, 2 skipped`. The failed test expected two obsolete literal unpublished warnings; `docs/index.html` was identical on main and #2202, already displaying the newer semantic notices and disabled controls.
- **ABACUS draft #2205:** updates only `tests/test_dashboard_health_link_contract.py`; asserts source-authorized MYRRHA/Contract Baseline disclosure, disabled actions and absence of ordinary/URL-encoded unpublished links. New adversarial negative covers alternate encoded hrefs. No engineering publication link was enabled, and no unrelated Python 3.10/3.11/3.12 matrix failure is marked repaired.
- **QPS #1953/#1954:** independently successful exact-head workflow sets (12/12 each at N3 readback); reviewer eligibility and owner ruleset installation still separate.

## P3 — Mission Control #520 / #85 / #638 method and visual proof

Inputs: GitHub REST read-only `GET /repos/GBOGEB/pipeline-automation-hub/actions/runs/39066797657/jobs?per_page=100`; pinned main `bea8d0e7400e1fe50970286987d03b0e508ec212`, attempt 1, one historical producer run. Expected two native `ubuntu-24.04` jobs:
- `117496047462`: created 20:27:40Z; started 20:29:50Z; completed 20:30:03Z, queue **130 seconds**, busy **13 seconds**, failure step due private source GET 404;
- `117496047699`: created 20:27:40Z; started 20:29:54Z; completed 20:30:01Z, queue **134 seconds**, busy **7 seconds**, success.

**Scoped measurable observation (n=2, one non-independent run):** nearest-rank p95 queue wait `134s`; two observed job occupations sum `20s`. Neither is live fleet queue p95, actual runner-capacity inventory, a workforce-hour forecast, or an independently stable process. API missing/partial/forged run ID or attempt/runner/steps/clock causes explicit UNKNOWN or fail-closed.

**Six canonical KPI statuses:** `QUEUE_P95` may be tagged `OBSERVED_HISTORICAL`, denominator 2, *not* current fleet; `EXACT_HEAD_PROOF_YIELD`, `FIRST_RED_COUNT`, `ACCEPTED_RECEIPT_YIELD`, `PREDICTION_VS_ACTUAL`, `RUNNER_HEALTH` remain `UNBOUND` without their separate admissible population. The one failed native job step is a **manifestation** with a reproducible fingerprint and `root_id=null`; it is not accepted causal-root closure.

## DMAIC, MIP and stats

- **Define:** protect true technical DoV from merge rules, private-source readbacks and dashboard false-greens.
- **Measure:** source SHA/run/attempt/job, nonzero steps, start/create/complete times, exact runner class, separate job occupancy and queue wait, and six typed KPI states.
- **Analyze:** group three distinct owner lanes (merge-protection configuration, private QPS source visibility, native CI first-red), keeping one named fingerprint separate from root count.
- **Improve:** owner-importable (not installed) rule, source-disjoint ABACUS #2205, N3 historical typed KPI/HTML receipt and negative QA.
- **Control:** native test and Pages cross-hash checks, exact-head independent review, a real protected-branch RED/GREEN canary and new authenticated reception proof.
- **MIP:** Modernize = source trust and scope; Innovate = bounded queue and Plotly evidence; Perpetuate = HOLD until source owner gates and repeat evidence.

**Statistical state:** No inference of stationarity from n=2 jobs, no independent matched cross-pulse series, no PCA eigengap/congruence certificate, no connected Bradley–Terry comparison sample and no Six Sigma DPMO claim. M1 is structural/read-only, M2 and M3 are HOLD. No graph object can be counted as an independent experimental observation.

## HTML and provenance acceptance

- `n3_kpi_bridge.py`: run from existing Method Atlas, outputs `n3-metrics.json`, `n3-metrics.html`, `n3-manifest.json` with exact **presentation** SHA and separate pinned historical **producer** SHA.
- Existing Pages publisher checks complete set, source/member SHA-256, default HOLD, no dispatch or installed-rule claims, then navigates to `mission-rebuild/n3-metrics.html`.
- `test_n3_kpi_bridge.py`: 10 source/adversarial tests. Existing portal suite adds two forged/partial-negative tests. Existing native Playwright checks 1440×1000, 1280×800, 390×844, two Plotly inlays, six KPI rows, click-toggle, console/page errors, document overflow and screenshot hashes.
- **DoV:** `N3_TECH_DOV = terminal exact-head unit tests >0 AND complete native job/attempt proof AND source to Pages member-byte parity AND tri-viewport browser QA AND ZIP/member hashes independently verified`. Review/rules are **additional** noncompensating merge admission predicates. If native API unavailable, show UNKNOWN; do not substitute fixture evidence.
- Cold browser on managed workstation cannot navigate `file://` (`ERR_BLOCKED_BY_ADMINISTRATOR`); this is **DEFERRED local link/navigation QA**, not a native browser failure. No performance/coverage improvement without matched denominator.

**Governing state:** `MERGE_ADMISSION=HOLD`, `authority_transfer=false`, `security_waiver=false`, `QPS_ACCEPTANCE=UNKNOWN`, `root_closures_accepted=0`. Draft PR only, no merge or dispatcher.
