# JADE_TEMPLE — N+4 owner-bound sprint to POINT RELEASE (target only)

## Verified predecessor and active candidate

- Existing main at N+4 branch creation: `39e46b0df026ce050a07198aae96b8ee8ad1d35f`, with N+3 [PR #736](https://github.com/GBOGEB/pipeline-automation-hub/pull/736) merged (GitHub event only).
- N+4 [PR #737](https://github.com/GBOGEB/pipeline-automation-hub/pull/737) is a separate draft; all post-merge PS1/CI/visual improvements are proposed here, **not credited to N+3**.
- N+2 [PR #733](https://github.com/GBOGEB/pipeline-automation-hub/pull/733) remains the separate Pages/stop-controller owner; CP-W10 [PR #734](https://github.com/GBOGEB/pipeline-automation-hub/pull/734) retains the strict zero-test first-red.
- JADE J0 source roster = 21 dated exact identities, but J1..J5 qualified release populations remain UNKNOWN. POINT_RELEASE=TARGET_NOT_ACHIEVED.

## DMAIC / MIP

| Phase | Owner/output | Measured unit and fail-closed decision |
| --- | --- | --- |
| DEFINE | Mission Control Top21 canonical roster | Keep 21 distinct eligible owners, 5 P0/9 P1/7 P2; 13-overlap historical GoGREEN is a **different** population |
| MEASURE | JADE 15-axis DAG and SIPOC | 253 nodes, 420 typed edges, 6 static layers; structural exposure not actual work completions; 15 separate N/D values |
| ANALYZE | CODEX/Mycelium + ABACUS/DELTA_1 | First-red propagation, queue P95 with observed timestamps only, configured versus occupied pool, long wait and source-head cache invalidation |
| IMPROVE | JADE local bounded 1..4 test workers | First source testflight, separate Windows PS1 isolated venv run; second same-head cache pulse; no remote dispatch |
| CONTROL | Each original repo owner | Native terminal exact SHA; security; independent review; blocked RED canary; hosted SHA parity; J4 candidate and J5 signed release only by owner |

## Disjoint sprint owner lanes

| P0 core owner | Dependency / targeted pilot | No-authority shortcut forbidden |
| --- | --- | --- |
| ABACUS | Current-first-red, A10/Safety, native statement/branch, mandatory merge gates | Never credit old GREEN or zero-review merge |
| pipeline-automation-hub | N+2 Pages/hosted child; N+4 PS1 and SVG/pool diagnostics; N+2/CP-W10 disjoint owner PRs | No second Pages publisher and no direct main edits |
| CODEX | Mycelium task-instance/replay, authenticated federation stage and reader | No client-side Action trigger without owner gateway |
| cryoplant-project | QPS domain/version, engineering evidence and RED-canary protection | No remote tag/release from JADE |
| gg_MATH | Provider-proof, exact-head package/version and hosted method parity | No inferred same-cohort coverage |

## Task DAG / critical external waits

J0 source -> J1 root SPINE -> J2 hosted HTTP; five engineering dimensions and dependency/supply-chain checks remain independent. J3 review/admin, J2 HTTPS and external GitHub CI are `DEFERRED_OWNER`: consume zero local Python workers. J4 must fan-in J1, J2 applicability, J3, five engineering proofs and supply-chain. J5 requires explicit owner's release/tag/asset/rollback authorization; this programme has zero such authority.

## Existing resources (do not duplicate)

- JADE Top21 source files, N+2 MIP/GoGREEN stop controller, static JADE existing Pages staging and the sole Method Atlas Pages publisher.
- CODEX `scripts/id_work_conserving_scheduler.py` and `mission_control/mycelium/control_manifest.yaml` supply existing aging, value-density and REX policy.
- ABACUS `runtime/execution/federated-execution-scheduler.yaml` (DELTA_1), `core/execution_backbone/backbone.py`, `tools/recovery/w32_runner_telemetry.py` and bounded MCP 2/4/8 capacity experiment provide scheduling and runner instrumentation.
- Python >=3.11, Git and Windows PowerShell; `Start-JadeSprint.ps1` creates a venv with no default network installation. Playwright==1.56.0/coverage==7.13.3 and Chromium are **optional**.

## Repeatable release-preparation command (Windows)

    powershell -NoProfile -File .\mission-control\jade_temple\sprint\Start-JadeSprint.ps1 -Mode Full -Offline -MaxWorkers 2

Then inspect `output/SPRINT_METRICS.json`, `output/SPRINT_DAG.json`, `output/SPRINT_SIPOC.json`, `output/LOCAL_RUN.json`, `output/SPRINT_DASHBOARD.html`, and `output/SHA256_MANIFEST.json` under `JADE_TEMPLE_WORK`. `-FreshClone -CloneRef code-purple/jade-n4-powershell-cache-dag-20261019` intentionally creates a separate source checkout; no original files are disposed or moved.

## N / N+1 testflight control

- N+3 [run 39173863431](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39173863431): Windows Python 3.12 source testflight PASS with SHA-verified 253/420/15-source artifact; Ubuntu queued at last bounded readback. This is historical exact-head N+3 evidence, not current N+4 CI.
- N+4 initial [run 39174276231](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39174276231): Windows FAIL source Python syntax in newly added SVG HTML anchor quoting. Source correction `2c60466f...` and compile guard `8f43c05b...` are committed on this new PR; current native qualification must use a fresh exact head.
- Desired first local pulse: 3 independently allowed Python checks pass; second same-head pulse: at least 3 eligible cache hits with actual log hashes. This is a TARGET until native evidence, not performance measurement.
- After qualification, improve pool capacity only from measured per-worker throughput and nonblocking queue p95; stop if marginal throughput gain is not material or failure rate rises. Three comparable terminal pulses with no readiness/root/coverage movement cause `PIVOT_DISJOINT_OWNER`, not J5 green.

Gate constants: `MERGE_ADMISSION=HOLD`; `J5=TARGET_NOT_ACHIEVED`; `AUTO_DISPATCH=OFF`; `RELEASE_TAGS=NONE_FROM_THIS_SPRINT`; `SECURITY_WAIVER=false`.

## N+5 immutable branch-first repair and push qualification

- N+4 PR #737 merged at early head `45c1e0e...` with actual Python syntax first-red, even though source fixes had been added later to its branch. That merge is not qualified point release or native source acceptance.
- N+5 branch `code-purple/jade-n5-exact-head-testflight-20261019` is derived from actual master `d757aee382e0a0daf278d28fc08a6f032bcc6ea8` and carries the precise five disjoint subsequent repairs (including Python source quoting and Windows native preflight).
- A bounded branch-specific GitHub push workflow now collects exact head native Linux3.11 / Windows3.12 without creating a PR that might merge prematurely. No separate publisher, no native runner dispatch from local script, no release tag.
- Do not create further PR or claim current-main repair until N+5 push workflow terminal checks and complete artifact hashes are examined; then source owner may stage human review and P0 branch rule canary.
