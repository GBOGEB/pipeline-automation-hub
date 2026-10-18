# JADE_CASTE N+2 — MIP / DMAIC / GoGREEN survival and measured burn-down

**As-of:** 19 October 2026, non-atomic GitHub readbacks. **Programme:** CODE PURPLE (evidence/governance), EVERRED (failure roots), GoGREEN (positive capability preservation), JADE_TEMPLE (Top21 landing/readiness). **Admission:** HOLD. **Source owners:** ABACUS admission; CODEX federation; QPS engineering; Mission Control this read-only projection.

## DEFINE — why N+1 alone cannot stop

JADE N+1 PR #732 merged at `ae0c652ccaa3dc0d55cd4edc4ad83dc491de917e`, with 0 recorded independent human reviews, and Mission Control master remained `protected=false` at readback. Exact-head JADE N+1 QA passed 44/44 tests and 3/3 viewports, and [Method Atlas postmerge run 39169421552](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39169421552) succeeded on that SHA, including its **single Pages deploy publisher**. The published bundle listed `/jade/` assets. These do not by themselves establish independent served SHA parity for JADE or eligible merge protections.

The same main source had a [strict zero-test audit first-red](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39169421620): **77 of 78** unittest gate invocations statically resolved, one `cp-w10-federation-handover.yml` selector used the shell variable `$ROOT`. This is an `UNRESOLVED` selector, not evidence that the CP-W10 test suite has zero collected tests. Preserve the exact source-bound symptom and repair in a **disjoint workflow owner lane**, without relaxing the audit.

## MEASURE — declared denominators, no compensating score

| Evidence unit | N+1 baseline | N+2 readback | Credit |
|---|---:|---:|---|
| Mission-selected Top21 repository identity | 21 | 21 | J0 inventory observed, non-atomic |
| Default heads changed across pulses | n/a | **3 / 21** | ABACUS, CODEX, Mission Control; invalidate inherited current-head check credit |
| Open owner next-release work orders | **21** | **21** | **0** owner-qualified closures, no fictitious burndown |
| Work order priorities | 5 P0, 9 P1, 7 P2 | Same | Proposed owner queue, not mandated SLA |
| GoGREEN census overlap | 13/21 | 13/21 | Historical selection, do not call 21/21 green |
| Historical root review suggestions | 706/880 | unchanged | Filename/path heuristic, not confirmed bugs |
| JADE module native source + browser | 44 tests / 3 viewports on PR head | Previous evidence retained | Successful scoped capability, no fleet coverage credit |
| Mission Control merged-main checks | Previously unbound | 23 success / 3 skipped / **1 failure** = 27 observed | Failed check retained; skipped is not green |
| Current-main eligible reviewer / effective ruleset | unknown | **not qualified** | PR #732 0 recorded reviews, protected false |
| JADE served HTTP and SHA parity | unknown | **unknown** | Dedicated independent staged-asset verifier implemented, not yet native-hosted proven |
| Fleet statement / branch coverage | null | null | Do not infer from JADE-focused tests |
| Qualified releases | null | null | Independent owner approval required |

Current first-red signature: `cp-w10-federation-handover.yml :: python -m unittest discover -s "$ROOT" -p test_cp_close.py -v`, run **39169421620**, job **117799185507**, base SHA `ae0c652ccaa3dc0d55cd4edc4ad83dc491de917e`. A source-owner correction shall replace only the selector with the literal actual directory and retain its full native 25+ negative suite, candidate/PR head and exact-job receipts.

## ANALYZE — why historical GoGREEN is not current launch readiness

The 17 October merged-outcome GoGREEN sample is **41 PRs / 509 native check IDs / 33 failed-check manifestations on a separate Top21 population**. JADE's structural N11 cohort overlaps by 13 repositories only; the remaining 8+8 are not missing test failures, simply different cohorts. The N+2 head census confirms 3 changing default heads across 21 and 8 repos with no branch-filtered sampled runs; zero returned runs means `UNKNOWN`.

The actionable acceptance chain is **source/pinned head -> instrumented tests/negative controls -> exact-head security -> independent review -> effective required checks/RED canary -> served Pages/asset hash -> owner release**. A successful GitHub Actions job, a Pages deployment and QPS engineering ACCEPT are independent units. A QA renderer is never an engineering-truth authority.

## IMPROVE — source-owned disjoint implementation

1. **JADE controller:** immutable `READBACK_NPLUS2.json` (21), `EVIDENCE_EVENTS_NPLUS2.json` (6 native/source-bound events), `STOP_MODEL_NPLUS2.json` and pure fail-closed controller. Source SHA and denominator checks prevent N−1→N aliases.
2. **GoGREEN HTML:** static `burndown.html`, CSS/JS, offline imported dataset and CSV with full Top21 rows; shows action burden (21→21), current main check mix (23/3/1), current-head drift (3), evidence gates and last first-red. The N+1 HTML remains available; root and Pages landing point to N+2.
3. **One Pages publisher:** extend existing `pages_portal.py`/`portal_bridge.py` with N+2 hash-bound child, *not* a second deploy workflow. Strict `burndown-manifest.json` and original N+1 site-manifest checks remain. `hosted_parity.py` independently retrieves every `/jade/` file at least twice from the canonical origin, matches the exact-main publisher SHA and all file hashes, with 8 bounded retries and fail-closed origin/redirect/oversize guards. Native hosted execution still required.
4. **QA and test coverage:** local 92 unittest cases PASS, browser 1440x1000 / 1280x800 / 390x844 PASS, zero outgoing requests. Focused source-branch instrumentor `coverage.py 7.13.3` measured 279/291 statements **95.88%**, 113/130 branches **86.92%**, *only* for `stop_rules.py`, `hosted_parity.py`, `build_burndown.py`, `portal_bridge.py`; **no** fleet coverage gain claimed.
5. **Separate first-red source lane:** CP-W10 unittest selector correction, independent source owner PR and native zero-test audit; no test culling, no waiver, no GoGREEN automatic closure.

## PERPETUATE — executable stop rules

**Rule ordering** (never sum compensating gate points):

- `REPAIR_FIRST_RED` when an exact-source first-red is observed. Preserve run/job/attempt identity and audit denominator.
- `WAIT_NATIVE` when an exact source still has nonterminal native jobs: do not create duplicate runner/worker dispatch.
- `OWNER_BLOCKED` for missing independent approvals, mandatory status checks, blocked RED canary or security owner.
- `PIVOT_DISJOINT_OWNER` only after **three consecutive comparable terminal** N−1/N/N+1 source+cohort+instrumentor+denominator+head populations with **no** new qualified owner action, causal closure, branches or federation edges; null is not zero and any pending roots invalidate plateau. Stop repetitive recensus only; do not abandon open gates.
- `TARGET_MET_STOP_ENGINEERING` only if all **nine** independent gate dimensions PASS, at least two distinct successful native run receipts, no pending jobs or current first-red. Even then, the software cannot merge or issue a point release without separate authorized owner decision.

These rules are implemented in `tools/stop_rules.py`, covered by negative synthetic cases including changed SHA, changed denominator, unknown branch count, false waiver, duplicated native run, drifted Pages manifest and unrelated host. Current controller disposition: **`REPAIR_FIRST_RED`**, `MERGE_ADMISSION=HOLD`.

## BD queue and next admissible pulses

- **W+1:** exact-head native N+2 JADE tests, focused branch+statement source denominator, three viewport browser; Method Atlas integration native/PR-head publish skip expected. Observe first-red and repair on the same PR.
- **W+2:** after *governed* merge, existing publisher should stage `/jade/burndown.html`, then perform independent **hosted JADE 16-file, 2-round SHA parity** against the same main SHA. Record run ID, attempt and asset hashes. Without it J2 remains UNKNOWN.
- **W+3:** independently qualify effective branch requirements, eligible reviewer and blocked-RED canary, then owner-select five P0 repo release pilots. Do not run broad Top21 workers until owner issue/roots assigned and disjoint path leases secured.
- **W+4:** preserve N+1/N+2 observations; emit a new pulse only on head/approval/native terminal/served parity/root disposition change. Three identical matched pulses switch to a new BD angle, not an automatic approval.

**STOP now:** never perform unreviewed merge, security waiver, rule bypass, release-tag publication, owner authority transfer or a fabricated zero-unknown score. No autonomous recurring monitoring is promised by this handover.
