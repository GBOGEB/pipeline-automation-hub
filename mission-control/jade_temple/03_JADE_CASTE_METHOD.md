# JADE_CASTE readiness ladder v0 — additive, non-authoritative

> **Doc** JT-03 · **Status** PROPOSAL · **Release** UNNAMED (owner sets SemVer) · **Admission** `MERGE_ADMISSION=HOLD` · **Updated** 2026-10-31

| Level | Meaning | Minimum source-bound exit |
|---|---|---|
| J0 — INVENTORIED | Repo in canonical Top21 roster | Real owner/name, default branch, dated exact commit identity and non-atomic readback disclosed |
| J1 — NAVIGABLE | Root is intelligible | README/actual spelling, source map, owner, stable canonical links and primary build/test manifests; no broken-link claim without tests |
| J2 — PUBLISHED | HTML accessible | HTTP(S) hosted page **tested**, served version/source SHA bound, static asset/link/browser checks; local HTML alone insufficient |
| J3 — GOVERNED-CANDIDATE | Rules/profile proposed | MACH applicability by owner + effective protection/read-only audit, check names, reviewers, security, negative RED gate test plan |
| J4 — RELEASE-READY | Candidate qualified, not released | Terminal exact-head CI/security/runnable tests, branch/diff coverage on matched denominator, eligible human approval and blocked RED canary, domain-owned release plan, P0 BD disposition |
| J5 — RELEASED | Owner admitted point release | Signed/verified source tag, release assets, URLs, publication/rollback evidence and independently permitted merge/readback |

**Fail closed:** `J0` is a census classification, not proof of readiness. J1–J5 are `UNASSESSED` until owner-authenticated evidence. Do not assign green from README existence, local test totals, static HTML or historical success. External/upstream-derived/archival cohorts may require an approved `NOT_APPLICABLE_WITH_JUSTIFICATION` path; this is not an automatic passing score.

## Metrics, comparisons, and scaling

- Cohort N/D = verified J-level repos / **approved eligible** scope, also show `unknown` and `not_applicable`; never silently shrink 21.
- Root hygiene backlog N/D = owner-accepted actionable root items / owner-reviewed root candidates, **not** `706 defects`.
- Hosting = separately verified HTTP+SHA pages / applicable repos; report unknown separately. No assumption of automatic Pages publication.
- Native CI = terminal successful required jobs / all required exact-SHA jobs, with run/attempt/job/step links and required names.
- Governance = mandatory protections proven / owner-required controls, with an independent negative RED canary.
- Release = owner-admitted tagged releases / approved eligible repos; release version context per repo.
- Deltas require matched source, instrumentor, scope and configuration. A 2026-10-17 tree/2026-10-18 commit pair is **not** itself a matched coverage comparison.

## Stop/retrigger policy

1. **Local wave stop:** all bounded tests, static/visual QA and hash receipts pass; any missing native or authority evidence remains HOLD, not a local repair retry spiral.
2. **Scale:** double candidate slice only after proof yield is positive, first-red roots non-overlapping and runtime/owner capacity authenticated; otherwise remain at same size or reassign to a higher-value P0 root.
3. **No-value stop:** three comparable eligible pulses show N+1=N for readiness *and* blocker closure *and* proof acquisition, or existing blockers cannot be changed by current authority. Label `PAUSE_NO_NEW_EVIDENCE`, not automatically statistically STABLE.
4. **Stable release eligibility:** only after repeated qualified independent observations and owner-adopted control thresholds. Never assert Six Sigma from a handful of tests.
5. **Retrigger:** new exact SHA, changed ruleset, fresh CI first-red, new source owner, release candidate/tag, verified hosted page, issue disposition or explicit instruction.

---

**Nav:** [← 02 Charter](02_CHARTER.md) · [Index](00_START_HERE.md) · [04 Root SPINE contract →](04_REPO_ROOT_SPINE_CONTRACT.md)
