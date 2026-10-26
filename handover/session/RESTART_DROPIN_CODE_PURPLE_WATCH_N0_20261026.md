# CODE PURPLE WATCH vNext — copy/paste restart drop-in (N0, 2026-10-26)

Start a **new**, read-only, source-bound CODE PURPLE federation watch. Do not continue the old repetitive monitoring chat, and do not replay its reports.

Read first, in GitHub:

- `handover/session/LOSSLESS_HANDOVER_CODE_PURPLE_WATCH_N0_20261026.md`: state, authority map, N0 delta, discrepancies.
- `mission-control/federation-atlas/watch_n0_session/STATE_N0.json` and `EVIDENCE_LEDGER_N0.jsonl`.
- `handover/session/MIP_WATCH_EVOLUTION_20261026.md`: future work, NOT IMPLEMENTED.
- `handover/session/CODE_PURPLE_WATCH_VNEXT_EXECUTION_CROSSWALK_20261026.md`: concrete MIP-01..15 owners, implementation gaps and PR dependencies; #878 and #881 are still candidates, NOT merge acceptance.
- `mission-control/jade_temple/DROPIN_NEXT_CHAT.md`: JADE N+11 checkpoint, owned by #867.

Then re-resolve every default head and relevant PR head before comparing anything.

## Retired and overlapping watches

- The ChatGPT task **Federated MIP Pulse Metrics** was disabled on 2026-10-26. Preserve its history; do not reactivate it.
- Reconcile the other enabled ChatGPT watches before activating a replacement:
  - CODE PURPLE Scaled Convergence;
  - CODE PURPLE Governed Wave Watch;
  - CODE PURPLE QPS Unlock Watch;
  - ABACUS Governed Recovery Watch;
  - Mission Control CI Gate;
  - ABACUS Merge and Coverage Watch;
  - BREAD & BUTTER QPS Burndown.
- Do not silently disable the separately owned QPS Bread & Butter engineering watch.

## Baseline

Historical cutoff 2026-10-26 00:43 CET; N0 re-check at about 00:22–00:35Z.

| Repository | Head at N0 |
|---|---|
| ABACUS | `6ebebbc2aee8c400ecec7a8b9ee76fff80153c17` |
| Mission Control | `516b905821bc1dcb299cd454a10c8c0b0f8adce3` (after #865, #867, #854, #871) |
| CODEX | `cb3b0d269bcd0ff9e96982cfc8276aa4bc187acf` |
| QPS | `PRIVATE_AGGREGATE_ONLY` (private repo) |
| gg_MATH | `61ce59f754d23e010958927a731432672abf7621` |

The original monitored PRs, ABACUS #1998/#1990/#1989/#1994/#1997 and Mission Control #530/#531/#533, are all merged. Canonical authority lives in the code paths and workflows they landed:

- **#530:** ZIP and evidence verifier.
- **#531:** authenticated six-repository breadth producer (workflow `CODE PURPLE Disjoint Live Census (read-only)`).
- **#533:** Method Atlas viewer only.

## Retained observations

- **#531.** 6/42 historical, 0/42 fresh authenticated. Every hourly census run fails (last at N0: `40244674158`). Repeated ABACUS HTTP 401. `CROSS_REPO_READ_TOKEN` was previously classified INVALID.
- **Method Atlas.**
  - #533 `bf9383bc` scored 74/74 (16 lane cases, `W1.C1.I2.S0`).
  - #864 `17c45076` and #868 `9a9b6d9c` scored 888/888 (18 lane cases, `W1.C1.I3.S1`).
  - Do not mistake the earlier master publication for a new candidate publication.
- **Governance.**
  - #840's RED canary was blocked.
  - #865, #867, #854 and #871 merged with First-Pass not PASS. First-Pass is not a required check; the required checks are `validate-ultra-control`, `canonical-self-test-and-mutation` and `GOGREEN required gate`.
  - ABACUS red canary #2470 is UNSTABLE, not BLOCKED: `main` has no `required_status_checks`.
- **ABACUS.**
  - DAB: 15,517 Flake8 findings / 4,227 proposals.
  - Coverage: W76 10/10 and W44 +8/+8 are bounded recoveries only.
  - JUnit: 6,989 testcase records vs. a 7,862 header claim, still open.
- **CODEX.**
  - Main has executable-inventory drift.
  - Reconciliation branch `f72fbd3d` passed 98 bounded invocations; that is not a main recovery.
  - Workflow GREEN over a Ruff/governance RED remains a blocker.
- **QPS.** Owner-only (`RESTRICTED_OWNER_RETURN`): read QPS state inside `cryoplant-project` with authorized access. Never copy private counts, identifiers or defect titles into this public repo; publish only an approved receipt pointer or `UNKNOWN`. Owner acceptance WITHHELD.
- **gg_MATH.** No new qualifying transition.
- **Readiness.** PC3 2/5. M1/M2/M3 PARTIAL/HOLD/HOLD. PCA/BT NOT ASSESSABLE. Worker-hours UNKNOWN.

## Required method, per newly eligible terminal event

1. Repository, PR, current exact head, base, checkout, synthetic merge and merged-main SHA, as separate identities.
2. Run ID, run attempt, native job ID, event time, terminal conclusion, executed steps.
3. Executed/pass/fail/error/skip counts, distinguishing unique tests, platform repetitions and subtests.
4. Artifact ID, GitHub ZIP digest, independently verified ZIP and member bytes, CRC, schema, producer identity and semantic validity; otherwise UNKNOWN.
5. Covered and eligible statements and branches, with instrumented paths, source-blob SHA, test selection and tool identity.
6. Observed and eligible census cells, keeping historical and newly authenticated populations apart.
7. Accepted causal-root IDs, diagnostic fingerprints and repeated occurrences, counted separately.
8. Queue, runner and worker-hour measurements, or UNKNOWN.
9. M1/M2/M3, control policies, PCA/BT readiness and explicit noncompensating vetoes.

Compare only matched populations. Keep UNKNOWN distinct from zero, absent, skipped and not applicable. First-red means attributable terminal evidence, not the first red-looking log line.

## Alerting

Notify only for:

- a new attributable first-red, or a changed root diagnosis;
- a source-bound RED→GREEN or GREEN→RED;
- a matched-scope coverage or breadth improvement;
- a new critical mismatch in identity, artifact semantics or enforced governance;
- a real owner, security or admission authority transition;
- a materially changed measured capacity, control policy or statistical qualification.

Do not notify for unchanged polls, repeated HTTP 401, already-established REDs, artifact revalidation, queued or cancelled jobs, unchanged totals, or ordinary merges without qualifying evidence.

After three comparable no-change transitions (four distinct comparable observations), enter STABLE_HOLD for that fingerprint. Use one event journal and one last-qualified cursor.

## First actions

- **A.** Load this checkpoint and the existing templates (`handover/session/SESSION_M2_CHECKPOINT_TEMPLATE.md`, `mission-control/golden-thread/checkpoint_*.py`).
- **B.** Run one fresh read-only verification of heads and newly terminal events.
- **C.** Reconcile only new qualifying deltas.
- **D.** Produce a compact progress vector, a first-red/root queue and the next admissible owner actions.
- **E.** Plan one canonical replacement watch, after reconciling the duplicate scheduled tasks.
- **F.** Make code changes only through bounded draft PRs with exact-head native tests. Never auto-merge, approve, change security settings, dispatch or waive.

## Authority and stop rules

```
MERGE_ADMISSION=HOLD
FORMAL_ENGINEERING_CREDIT_DELTA=0
QPS_OWNER_ACCEPTANCE=WITHHELD
SECURITY_WAIVER=NONE
```

- Never fabricate a native attestation, review, root closure, release or cross-repository coverage.
- If no new qualifying terminal event exists, maintain the checkpoint silently.
