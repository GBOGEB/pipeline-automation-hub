# CODE PURPLE WATCH vNext — lossless operational handover N0 (2026-10-26)

Handover identity: `CODE_PURPLE_WATCH_RESTART_20261026_N0`. Historical cutoff: 2026-10-26 00:43 CET (2026-10-25T23:43Z).

This file preserves the operational state of the retired **Federated MIP Pulse Metrics** watch, a ChatGPT scheduled task that was disabled on 2026-10-26. It also records the first fresh read-only re-check (N0) by a Claude Code session.

Restart from [RESTART_DROPIN_CODE_PURPLE_WATCH_N0_20261026.md](RESTART_DROPIN_CODE_PURPLE_WATCH_N0_20261026.md). The improvement programme is kept apart in [MIP_WATCH_EVOLUTION_20261026.md](MIP_WATCH_EVOLUTION_20261026.md) (NOT IMPLEMENTED). Machine-readable N0 state: [`mission-control/federation-atlas/watch_n0_session/`](../../mission-control/federation-atlas/watch_n0_session/).

**Evidence classes used in this file**

- **reported, not re-verified**: taken from the retired watch's chat reports (Sections 1–3 below). These are inputs, not proof. The native run, job and artifact records stay authoritative.
- **N0 observed**: read from the GitHub API by the N0 session on 2026-10-26 around 00:22–00:35Z (Section 4).
- **UNKNOWN** means not read or not readable. It is never zero, PASS or absence.

`cryoplant-project` (QPS) is private and this hub is public. QPS evidence is transport class `RESTRICTED_OWNER_RETURN` ([CENSUS_PULL_ROUTING_V2.md](../../mission-control/v2/handoff/CENSUS_PULL_ROUTING_V2.md)): no private SHA, identifier, count, defect title or workload summary is committed here. QPS rows carry only `PRIVATE_AGGREGATE_ONLY` or `UNKNOWN` (public) and point to the QPS owner's own records. The looser count-preserving projection in `jade_temple/tools/private_boundary.py` applies to public JADE outputs only and is not used for this handover.

## 1. Last reported repository identities (reported, not re-verified)

| Repository | Last reported default-branch SHA |
|---|---|
| ABACUS | `6ebebbc2aee8c400ecec7a8b9ee76fff80153c17` |
| Mission Control (`pipeline-automation-hub`) | `e4b901afa7706dee862730c4a468a96b7b07bcfc` |
| CODEX | `cb3b0d269bcd0ff9e96982cfc8276aa4bc187acf` |
| QPS (`cryoplant-project`) | `PRIVATE_AGGREGATE_ONLY` |
| gg_MATH | `61ce59f754d23e010958927a731432672abf7621` |

These are historical anchors, not current heads. Re-resolve them before any comparison.

## 2. Canonical responsibility boundaries

| Authority | Owner | Contract |
|---|---|---|
| Evidence ZIP verification | Mission Control #530 code paths | Archive and member integrity, accepted verification results |
| Authenticated six-repository breadth | Mission Control #531 code paths (workflow `CODE PURPLE Disjoint Live Census (read-only)`) | Observed and eligible population, qualifying source-bound census |
| Method viewer | Mission Control #533 code paths | DAG, SIPOC, SPINE and Atlas display; no authority to fabricate producer observations |
| ABACUS | ABACUS source owner | Tests, security, DAB, governance, coverage |
| CODEX | CODEX source owner | Federation methods, provenance, runtime, analytics and its own admission |
| QPS | QPS engineering owner | Controlled requirements, source originals, offers, RTM, engineering and owner acceptance |
| gg_MATH | gg_MATH source owner | Mathematical code, tests and statistical implementation |

**N0 correction:** #530, #531 and #533 have all been **MERGED since 2026-10-15** (#531 10:19:30Z, #530 10:19:58Z, #533 10:29:05Z). "Canonical owner" therefore means the code paths and workflows those PRs landed, not open PRs. The watch stays a read-only federation of source-owned evidence. It is not a parallel source of truth.

## 3. Open state by repository at the cutoff (reported, not re-verified)

### Mission Control: highest-priority federation blocker

- **#531 census.** 6/42 historical observations, 0/42 newly authenticated qualifying cells. The latest reported failing source job was `121323610711` in run `40244674158` (attempt 1), with HTTP 401 against ABACUS. Diagnostic artifact `12618475439`: 508 ZIP bytes / 602 member bytes.
- **Credential.** `CROSS_REPO_READ_TOKEN` was classified INVALID in an earlier token census. Whether it needs replacement, a permission fix or another owner-side remedy must be confirmed without exposing the credential.

### Method Atlas: source proof stable, admission distinct

| PR | Head | Run / job | Result | Artifact |
|---|---|---|---|---|
| #533 (original) | `bf9383bc39bedf645175184049bdb2013379041d` | `38719705691` a1 / `116370959125` | 74/74 PASS, 16 lane-process cases, series `W1.C1.I2.S0` | `11964700323` |
| #864 | `17c45076213a53f837c4fa3a3e48a5a80771e33b` | `40245424831` / `121325850892` | 888/888 PASS | `12617823984` |
| #868 | `9a9b6d9cc7dcf54d1029f918346c0027df6b186b` | `40245683096` / `121326628467` | 888/888 PASS | `12619090161` |

Both newer runs pass 18 lane-process cases, series `W1.C1.I3.S1`. Generated sizes: HTML 38,236, Mermaid 4,403 and JSON 16,695 bytes. Candidate publication was SKIPPED. An earlier master publication succeeded and stays a separate historical record.

### Mission Control First-Pass and JADE

- **#867** at head `fd34589cec56e2d5cc62a9e564ead8e46aa872c8` was RED. JADE run `40245813468` / job `121327015051`: 319 executed / 315 PASS / 4 FAIL / 0 SKIP, with stale generated CI/CD DAG outputs. First-Pass run `40245809828` / job `121327005730`: 20 contract tests passed, but the verdict was `INVALID_RECEIPT_HEAD_SHA`. *(N0: head moved and #867 has since merged; see Section 4.)*
- **#858**'s earlier 309-test recovery is valid at its own exact head only.
- **#843**'s positive First-Pass receipt is bounded positive-control evidence.
- Neither overrides #867's RED, and neither qualifies the full admission contract.

### ABACUS: test quality, coverage and security debt

- **DAB.** Latest run `40245697529` / job `121326672238`: 15,517 Flake8 findings / 4,227 read-only proposals. No G1/G2/G3 threshold closure.
- **DOW pre-commit.** Run `40245697502` executed 19 tests and failed operationally. The PASS/FAIL/SKIP split is UNKNOWN.
- **Coverage recoveries (bounded).** W76 recovered 10/10 zero-covered assets (233/233 statements, 50/50 branches). W44 gained +8 statements (240→248/260) and +8 branches (102→110/120) on a matched population. Neither establishes a global main uplift. Broad-main and changed-line coverage must be remeasured at the new exact main SHA.
- **JUnit disagreement.** B0 had 6,989 testcase records against a 7,862 suite-header claim. This stays open as a measurement-quality first-red.
- **Still needing current-head disposition:** dependency resolution, pinned `setup-python` assertions, Black, Bandit/Safety and independent review.

### CODEX: candidate recovery is not main recovery

- **Main.** The last reported Mycelium first-red was generated executable-inventory drift.
- **Reconciliation branch** `f72fbd3d3ec387fd65f1ccc7d1b58e048185f7d5`: 98 bounded N7–N10 test invocations passed. N7 coverage was 495/512 statements and 114/136 branches, with 49 unresolved registration-debt entries.
- **Admission blockers.** Workflow SUCCESS over a failed Ruff/governance receipt stays an admission blocker. Synthetic-merge executions are kept separate from exact-PR-head executions.

### QPS: owner-only evidence (`RESTRICTED_OWNER_RETURN`)

- Test, coverage and open-defect state: `UNKNOWN` in public. The retired watch's QPS observations stay with the QPS engineering owner in `cryoplant-project`; no public receipt pointer has been approved yet.
- Owner acceptance: WITHHELD.
- Bidder originals, RTM, OCD/ADR, offer analysis and release decisions stay under QPS owner control only. Neither a federation dashboard nor a passing software test may promote them.

### gg_MATH

Default branch unchanged. Earlier source-bound release tests and coverage are historical evidence only. No newly qualifying federation observation exists.

### Common governance state

| Dimension | Restart state |
|---|---|
| Merge admission | HOLD |
| Engineering acceptance | WITHHELD unless owner source proves otherwise |
| Security waiver | NONE verified |
| Newly accepted causal-root closures | 0 |
| Formal engineering credit Δ | 0 |
| M1 / M2 / M3 | PARTIAL / HOLD / HOLD |
| Local PC3 qualified policies | 2/5 (five control-policy classes, not five repositories) |
| Federation PCA / BT | NOT ASSESSABLE |
| Federation worker-hours / capacity | UNKNOWN / UNKNOWN |
| Three-transition stability proof | Not established |

Two governance observations stay separate, and neither overwrites the other:

1. The deliberate RED canary on #840 **was blocked** by GitHub, which proves enforcement on the path it tested.
2. Other PRs **merged after failed First-Pass receipts**, because First-Pass is not a required check in the effective ruleset.

### 48-hour comparable measurements (reported, not re-verified)

| Measurement | Earlier | Later | Creditable as |
|---|---|---|---|
| ABACUS W76 target assets covered | 0/10 | 10/10 | Targeted, source-blob-matched recovery |
| ABACUS W44 statements / branches | 240/260 · 102/120 | 248/260 · 110/120 | Matched test-selection expansion |
| CODEX focused statements / branches | 177/193 · 46/58 | unchanged | No change |
| QPS | `UNKNOWN` (public) | `UNKNOWN` (public) | Owner-only; not reported here |
| ABACUS Flake8 raw findings | 15,726 | 15,517 | Raw census change across different revisions; not source-matched |
| Method Atlas lane-process cases | 16 | 18 | Expanded contract; not a common-cohort uplift |
| #531 fresh authenticated breadth | 0/42 | 0/42 | No progress |
| Local PC3 policies | 3/5 | 2/5 | `short_compute` withdrawn on directional instability (fail-closed working) |

Mission Control #849 revised its fan-out *estimate* from 21.9× to 7.9×, and tests per full pass from 342,625 to 107,804. These are parsing corrections, not measured runner reductions.

## 4. N0 re-check — 2026-10-26 (N0 observed)

Default heads were read once at about 00:22Z:

| Repository | Current default head | Delta vs. anchor |
|---|---|---|
| ABACUS | `6ebebbc2aee8c400ecec7a8b9ee76fff80153c17` | unchanged |
| Mission Control | `57f08d221bc68f4e691591336ee49c71014fdbb0` | +1 commit (#865) |
| CODEX | `cb3b0d269bcd0ff9e96982cfc8276aa4bc187acf` | unchanged |
| QPS | `PRIVATE_AGGREGATE_ONLY` | `UNKNOWN` (owner-only) |
| gg_MATH | `61ce59f754d23e010958927a731432672abf7621` | unchanged |

### Material observations

1. **#865 merged to `master` while First-Pass was still running.**
   - Merged at 2026-10-25T23:39:17Z (00:39 CET). Head `164ca71e2fc9e8d26cf0cf82459b8c154f829c2a`, merge commit `57f08d2`. Zero reviews.
   - The three required checks (`validate-ultra-control`, `canonical-self-test-and-mutation`, `GOGREEN required gate`) were SUCCESS at the head.
   - First-Pass Gate run `40245731337` / job `121326773547` was created 2 s before the merge and concluded FAILURE at 23:42:46Z. Failing step: "Fail closed unless trusted controller emitted a bound PASS receipt".
   - The platform allowed the merge; AGENTS.md L1 ("never merge on red") was not satisfied. This is a new occurrence of the known root "First-Pass not a required check", not a new root.
   - All 19 push runs on `57f08d2` succeeded. Test counts are UNKNOWN.
2. **ABACUS red canary #2470 is not platform-rejected.**
   - Head `ae482b3e0f871a1f8e6b429e2d80f907ea18e1d3`; `CI/CD Test Suite` run `40247185233` failed; `mergeStateStatus=UNSTABLE`, not `BLOCKED`.
   - ABACUS `main` rules are `deletion`, `pull_request` (0 approvals), `non_fast_forward`, `code_quality` and `copilot_code_review`. There is no `required_status_checks` rule, so the verdict is `HOLD_CHECKS_NOT_ENFORCED`. Close the canary unmerged.

### Unchanged; suppressed as no-change

- **#531 census.** The last run is still `40244674158` at the old `master` `e4b901a`. It has failed on every hourly schedule; fresh breadth is 0/42. This root (repeated cross-repo HTTP 401) is a STABLE_HOLD candidate.
- **#858.** First-Pass run `40246756160` failed at both attempt 1 and attempt 2 at the same head `df38b253f82ccddd5dab426d625f6a5dfc13a43f`. That makes it persistent, not a flake.
- **QPS.** Owner-only: head delta, PR and run activity are `UNKNOWN` in public and are not classified as changed or unchanged. No main credit.

### Discrepancies

1. The Mission Control anchor `e4b901a` omits #865, which merged at 00:39 CET, 4 minutes before the stated 00:43 cutoff.
2. #530, #531 and #533 are merged (2026-10-15). The handover's "canonical PR" wording refers to their code paths.
3. #867's head moved from `fd34589cec56e2d5cc62a9e564ead8e46aa872c8` to `6699196a68fe3f75bceb02f7eb45688444d8fd72`, so the handover's #867 RED rows (JADE 315/4, `INVALID_RECEIPT_HEAD_SHA`) are stale. At the new head, the workflows that ran succeeded, and First-Pass Gate was SKIPPED four times. SKIPPED is not PASS.
4. The seven overlapping recurring watches are ChatGPT scheduled tasks. None of them are Claude Code scheduled tasks, so they could not be reconciled from the N0 session.
   - Hourly: CODE PURPLE Scaled Convergence, CODE PURPLE Governed Wave Watch, CODE PURPLE QPS Unlock Watch, ABACUS Governed Recovery Watch, Mission Control CI Gate, BREAD & BUTTER QPS Burndown.
   - Daily: ABACUS Merge and Coverage Watch.
   - Also enabled: the 14-day and 21-day one-time issue follow-ups.

### After N0, before this PR was cut (N0 observed, 00:35Z)

`master` moved three more times:

| PR | Head | Merge commit | Merged (UTC) | Reviews | Required checks | First-Pass rollup |
|---|---|---|---|---|---|---|
| #867 | `6699196a68fe` | `8db2c338` | 00:24:52 | 0 | 3/3 SUCCESS | FAILURE + 4× SKIPPED |
| #854 | `7b7f7a0fbed5` | `1cd99624` | 00:25:22 | 0 | 3/3 SUCCESS | 2× FAILURE + 2× SKIPPED |
| #871 | `7dd5d607919a` | `516b9058` | 00:29:43 | 0 | 3/3 SUCCESS | FAILURE + CANCELLED |

Whether each First-Pass FAILURE was terminal before or after its merge is UNKNOWN; it was not checked. #867 landed its own checkpoint, [`mission-control/jade_temple/DROPIN_NEXT_CHAT.md`](../../mission-control/jade_temple/DROPIN_NEXT_CHAT.md) (JADE N+11). This handover links to that checkpoint and does not duplicate it.

### N0 disposition

`MERGE_ADMISSION = HOLD` · Formal engineering credit Δ = 0 · Stability = 0/3 · QPS owner acceptance = WITHHELD · Security waiver = NONE.

## 5. Landing order (proposed, not done)

1. **This PR (preservation).** Documentation only, with no runtime or workflow changes.
2. **Governed watch contract.** Schema, source-bound reconciliation, semantic validation, deduplication and negative tests. Reuse `mission-control/golden-thread/checkpoint_replay.py` and `checkpoint_registry.py` instead of new checkpoint code (AGENTS.md L4).
3. **User-facing view.** Render canonical source results only, without becoming another metric producer.
4. **Downstream links.** ABACUS, CODEX and gg_MATH get references only. QPS-private data stays in QPS.

Do not activate a replacement watch until duplicate watch ownership is reconciled (Section 4, discrepancy 4).
