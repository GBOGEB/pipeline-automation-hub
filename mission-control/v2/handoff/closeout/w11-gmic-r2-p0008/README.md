# GM-I-C R2 P0008 — CP.CLOSE canonical handover extension

**Status:** REVIEWABLE SOURCE CANDIDATE · `MERGE_ADMISSION=HOLD` · captured 11 November 2026 (Europe/Brussels, **date-only**, non-atomic GitHub readback).

This directory is an **additive, source-bound consumer of the existing CP.CLOSE nine-artifact generator**. It is not another GitHub handover schema, scheduler, BD root owner, global glossary or transcript. [Canonical method](../README.md) · [protocol](../../CP_HANDOFF_RESUME_V1.json) · [ABACUS V2 process](https://github.com/GBOGEB/ABACUS/blob/main/tools/handover_v2/process_spec.json) · [ABACUS message template](https://github.com/GBOGEB/ABACUS/blob/main/handover/HANDOVER_MESSAGE_TEMPLATE.md).

## Start here

1. Verify `../records/CP-GMIC-R2-P0008-20261111/MANIFEST.json` **only once committed and native --check PASS**. Before that, use the [sanitized version-bound intake](../intakes/CP-GMIC-R2-P0008-20261111.json) and the exact-head workflow artifact, **not** an assumed sealed record.
2. Read the [full source-qualified B01–B46 historical projection](BD_B01_B46_READONLY.json): 46 total, 22 scoped DONE, 24 open (8 review-wait, 3 actionable, 8 owner-hold, 5 dependency-hold), weighted unique-root closure NULL. Its source is [Hub #1135 P0007](https://github.com/GBOGEB/pipeline-automation-hub/pull/1135#issuecomment-6779729295). No B ID was retired; prior B01–B38 = 38/20/18.
3. Read the [copy-ready drop-in](NEXT_CHAT_DROPIN.md) and the [frontier DAG](P0008_CONTINUATION_DAG.mmd). Re-census *live* sources and effective rules before any edits. No automatic ChatGPT action follows from these monikers.
4. Keep **CODEX SEM-01–SEM-16**, **Drive BridgeFlow 36 items**, **Hub B01–B46** and **canonical CODE PURPLE CPQ** strictly non-additive.
5. For an authorized local Git checkout, run the canonical generator (no second generator):

```bash
C=mission-control/v2/handoff/closeout
N=CP-GMIC-R2-P0008-20261111
BD=mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json
python "$C/cp_close.py" --intake "$C/intakes/$N.json" --bd "$BD" --out "$C/records/$N" --zip "/tmp/$N.zip"
python "$C/cp_close.py" --intake "$C/intakes/$N.json" --bd "$BD" --out "$C/records/$N" --check
python -m unittest discover -s "$C" -p test_cp_gmic_p0008.py -v
```

The original `CP.CLOSE GitHub Handover QA` workflow has an additive `gmic-p0008-closeout` job that invokes this same generator, verifies SHA-256 and ZIP CRC, checks 46 task identities, runs adversarial tests, and uploads a nine-artifact ZIP for 21 days. It **does not** push to main. The code path is kept separate from public QPS engineering/private offer source bytes.

## Six disjoint source-owner lanes

| Lane | What is already source-verified | Exact next DoV that remains |
| --- | --- | --- |
| **A — GEMINI W1/W2** | #48 and #52 merged, source-qualified synthetic wire corpus/BLSN | #44 owner decides canonical broker wire, CHANGED/idempotency and P2/P3; no duplicate broker |
| **B — Hub FPC** | #1135 22/22 native, #1138 9/9, #1152 22/22, #1160 6/6 | Independent after-last-push review, genuinely trusted FPC green on each eligible exact head |
| **C — protections** | #1139 controller main landed; CODEX #1282 is now merged | B25/B29/B37 require owner policy, effective Hub/GEMINI last-push reviews, RED and GREEN canaries |
| **D — hosted IC3** | GEMINI #12 has owner-side root observation only | Approved OIDC-WIF principal, scoped Drive Viewer ACL and actual hosted GT0 step/item proof |
| **E — ISO** | #1164 16/16 native, source ancestry established | Single exclusive route with owner review, FPC success, authorized integration, source PR disposition |
| **F — Mermaid** | #1175 27 browser/method tests, #1179 23 native successes incl 3 renders and 7 Kahn tests at d4414bbc | Eligible exact-head review, trusted FPC, owner admission and integrated post-merge readback |

All six lanes retain distinct source-owner path leases. The W4 AND-join needs A, B, C (Hub **and** GEMINI), D, and F admission and is **not** implied by this handover.

## Change/authority ledger

- **Hub master at snapshot:** `401c57316197c81e910f0b3da7ea7322e1f109fc`.
- **CODEX main:** `c7535442cd325d2b7602fcadf7677aa235ecdafd`, merge #1282; check full required review admission independently, not inferred from merged state.
- **GEMINI main:** `fec1ded1a5730327fcadd7389b2bb43156ea967d`, merge #48; outstanding #44/#50/#12 owner gates unaffected by native corpus success.
- **Hub diagram:** #1179 `d4414bbc20364e00d58d2f5179e94c68e37dd2a7`, trusted FPC RED; method owner #1175 `10c93e2268e62ab8584f8e915d60c3707116f81d`, FPC RED.
- **Hub W0:** #1135 `41e287f89fd48bc03e4ca7960f0c71fd62ca7a62`, native 22/22 success, trusted FPC RED. Codex review-quota messages are not approval or automatic waiver.
- **CODEX semantic aliases:** source merged does not mean old W111 status/action collisions can be reused. Preserve exact registered aliases (same candidate bytes) and keep `3P*`, `3PC`, `3PR`, `3MP` distinct. No natural-language guarantee beyond the allowlist.
- **Local Windows worktrees:** `C:\DEV` and `C:\repos` are *not inspected*. B44 requires a read-only inventory before any rename or soft refactor.
- **Losslessness limit:** 8 reconstructed visible intents ≠ 8 original user messages; full user prompt count, hidden history, tokens and original timestamps stay UNKNOWN/null. This is GitHub-first operational continuity, **not** a `V2_SCHEMA_AND_REPLAY_VERIFIED` archive of unavailable raw conversations.

## DoD, DoV and acceptance

**DoD:** intake and 46-row sidecar committed on a narrow branch; no duplicate source owner; copy-ready restart; existing generator reused; adversarial tests and source/policy pointers present.  
**DoV:** exact-head native 9-member manifest+ZIP CRC, deterministic replay parity and at least 10 executed scoped tests; record source SHA/run/job/attempt/ZIP hash separately.  
**Admission:** independent review, effective required checks, owner approval, authorized merge and default-branch re-readback. These remain separate. If pending, publish `SESSION_CLOSED_WITH_HOLD` and return this branch/PR plus the restart prompt.
