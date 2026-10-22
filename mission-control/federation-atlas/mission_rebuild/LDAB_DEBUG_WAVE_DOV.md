# CODE PURPLE / Mission Control — LDAB native false-green repair

## Root (source-owned)
The W2 `sample_jobs` complete API-population test formerly allowed an empty census (0/0), or a queued/step-less job, to be interpreted as successful native work if its containing workflow run had a success conclusion. This is a **proof-admission defect**, not evidence that a GitHub-native runner actually executed a no-op.

**Fix:** one authoritative `ldab_guard.assess_jobs` performs nonzero job population, unique job ID, terminal job status, completed executed-step receipt and expected run-ID consistency checks. W2 `native_success_with_known_job_population` now requires these additional predicates. That indicator is job-metadata proof only, **not tests/coverage/bytes/merge admission**.

## LDAB vs LLDB

- **LDAB:** read-only `run -> job -> first failed step` manifestations are typed with job ID, step ordinal and deterministic fingerprint. Fingerprint does not imply accepted causal root; `root_id=null`, `logs_authenticated=false`. Full causal classification requires downloaded native job/step logs and an authorized source-owner disposition.
- **LLDB:** native crash debugger, not the LDAB log-classification lane. No relevant crash trace or debugger session was verified. Local `lldb --version` itself failed with missing `libpython3.11.so.1.0`; this is a local environment/tooling blocker and not a CI failure. Do not manufacture a debugger pass or install uncertain libraries on a runner.

## DAG/SIPOC projection

The existing Method Atlas remains authoritative: **5 repository nodes + 39 process stages + 10 beams = 54 source-model nodes**; 38 process-sequence + 13 beam edges = 51 graph edges. The crosswalk verifies unique node IDs, no orphan endpoints, 10 lanes and 39 stage atoms, LDAB stage membership, five SIPOC roles, no same-pulse DAG cycles and only N->N+1 FEEDBACK. It emits `ldab-sipoc.json`, `ldab-sipoc.mmd` and a SHA-256 manifest into the **existing Atlas upload**, not another Pages publisher or SSOT. It never joins a cross-repo edge by inference.

## DMAIC / MIP and DOV

Define: restore integrity of the native proof predicate. Measure: run ID, head, attempt (run-level only), distinct job IDs, terminal job outcomes and executed-step count. Analyze: classify missing jobs vs queued vs first failing step without fake root closure. Improve: bounded W2 consumer guard + graph crosswalk. Control: negative fixtures + native exact-head CI/coverage + next source SHA. MIP Modernize now has local source/test evidence; Perpetuate remains HOLD pending terminal CI and reviewer governance.

Local cold fixture results on **this exact new guard source family** before commit:
- 25/25 unit tests passing after correcting one mistaken cycle test fixture;
- `ldab_guard.py`: 50/50 statements and 10/10 branches (100% both);
- `ldab_dag_sipoc.py`: combined focused **115/131 statements (87.786%) and 22/24 branches (91.667%)** across the two modules;
- `python -m compileall` and `python -m tabnanny` PASS;
- Ruff, Black and Flake8 NOT RUN (not installed in local environment); browser/LLDB **NOT RUN**.
These percentages describe local tests on this **new focused population**, never whole-main, changed-line or cross-repo coverage.

Native DoV requires current exact-head Method Atlas to reach terminal and execute >0 tests, pass the new fail-closed unit cohort and focused coverage, generate graph/LDAB JSON + Mermaid with matching SHA-256, and publish artifact bytes for independent readback. At source time, Mission Control GitHub Actions had a large queue and W1/W2 source runs remained queued; no native DoV is credited here. Keep merge and security admission independently HOLD until effective required checks and eligible human review.

## Operator re-entry

1. Confirm queue/in-progress native jobs, `run_attempt` and current PR head; don't rerun identical queued runs.
2. If execution begins, bind run/job/step identities. Log first failed step as a manifestation, then fetch native logs; only afterward rank an attributable root by source owner.
3. Distinguish syntax/tabnanny (cold), Ruff/Black/Flake8 (not run until installed), Python coverage (focused), and security tests (independent).
4. For actual native crash, authorize a bounded LLDB session, pin executable/build/OS debug symbols and record its log. Otherwise `LLDB_NOT_INVOKED`.
5. Validate DAG/SIPOC output hashes, and preserve `MERGE_ADMISSION=HOLD` until governed admission.

No CI cancellation, rerun flood, security waiver, causal-root closure, remote worker launch, QPS acceptance or merge is authorized by this diagnostic wave.
