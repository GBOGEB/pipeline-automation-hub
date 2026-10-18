# JADE_CASTE N+3: point-release sprint / offline operator

This is an **additive read-only candidate** in the canonical Mission Control JADE_TEMPLE folder. Owner release J5 is a goal, not an achieved outcome. Prior work: JADE N0 #729 merged, N+1 #732 merged, N+2 #733 draft and CP-W10 first-red #734 disjoint. Do not rebase or copy N+2 source into this branch without explicit change review.

## Quick start (PowerShell on Windows)

From a checkout of the N+3 branch, use:

    powershell -NoProfile -File .\mission-control\jade_temple\sprint\Start-JadeSprint.ps1 -Mode Plan
    powershell -NoProfile -File .\mission-control\jade_temple\sprint\Start-JadeSprint.ps1 -Mode Full -MaxWorkers 2
    powershell -NoProfile -File .\mission-control\jade_temple\sprint\Start-JadeSprint.ps1 -Mode Verify

To prevent interference with existing repositories, an isolated fresh checkout is explicit:

    powershell -NoProfile -File .\mission-control\jade_temple\sprint\Start-JadeSprint.ps1 -FreshClone -CloneRef code-purple/jade-n3-release-sprint-dag-20261019 -Mode Full

Optional browser tooling is not downloaded by default. Use -InstallOptionalDependencies -WithBrowser for version-pinned Playwright + Chromium (network required). -Offline refuses both clone and install. The script creates an isolated Python 3.11+ venv in the JADE_TEMPLE_WORK directory. The Python orchestrator itself requires only the standard library.

Equivalent CLI: python mission-control/jade_temple/sprint/cli.py --mode plan --out C:\JADE_TEMPLE_WORK\output --max-workers 2. Execute local tests via --mode local or full. The N+2 readback from draft PR #733 may be supplied using --nplus2 <path>; it is never invented if missing.

## Five engineering axes plus ten additional independent denominators

The source-coverage, adversarial, integration, runner-platform and causal detection axes remain distinct. Extend with root navigation, independently served HTTPS assets, effective governance, pinned supply-chain manifests, release artifacts, observed worker pool occupancy, measured queue latency, strict local cache identity, issue/root burndown and authenticated transport lineage. All numeric release gates remain UNKNOWN until proven by original owners; historical 21/21 J0 identity is not release credit.

## Scheduling and avoiding long-dependency waiting

Only three allowlisted source-local JADE test/build checks are runnable by default. Bounded local Python concurrency is 1-4, default 2. Their cache is keyed to exact local Git HEAD, hashes of all eligible JADE project sources, command arguments, Python version, and platform. Cache reuse is local diagnostic acceleration only; a TTL, atomic lease and sha256 manifest prevent stale/noisy replay. With the optional browser QA switch, a separate one-slot browser pool is used. Pending CI, branch administration, hosted Pages HTTP, independent review, owner point-release acceptance and cross-repository transport consume **zero local slots** and stay deferred with honest UNKNOWN states. A long external wait causes work-conserving movement to an independent admissible local slice, not speculative CI dispatch.

## DAG, SIPOC, digital view and artifacts

Outputs: SPRINT_DAG.json, SPRINT_SIPOC.json, SPRINT_METRICS.json, SPRINT_QUEUE.json, SPRINT_SPINE.mmd, SPRINT_DASHBOARD.html, SHA256_MANIFEST.json, and, on a local run, LOCAL_RUN.json with individual hashed logs. The human-scale SPINE shows the workflow; the machine DAG projects 21 distinct repo gate sequences.

The current N+3 candidate does **not** install a new GitHub Pages publisher. The existing N+2 #733 Pages child and existing Method Atlas owner must complete hosted parity after independently qualified admission.

## MIP / DMAIC iteration stop

- DEFINE: 21 candidate actions (P0=5/P1=9/P2=7), date-stamped non-atomic source.
- MEASURE: per-axis opportunity denominator, native first-red, local diagnostic cache effects, queue p95 and worker occupancy only when timestamps exist.
- ANALYZE: longest dependency gates, source/owner collisions, repeated stale-head work and duplicated CI run amplification.
- IMPROVE: independent bounded local preflight workers, proper deferred owner waits, immutable evidence digests.
- CONTROL: native source-owned tests (Windows + Linux, Python 3.11/3.12) and strict admission boundaries. Do not count a cached test as a new native run or formal root closure.

Stop repeating a no-op census only after 3 comparable terminal native observations without useful gain; HOLD remains if requirements are unqualified. Only repository release owners can approve J4 and issue a J5 point-release tag, assets and rollback record.

POINT_RELEASE=TARGET_NOT_ACHIEVED; MERGE_ADMISSION=HOLD; REMOTE_DISPATCH=DISABLED; AUTHORITY_TRANSFER=false.
