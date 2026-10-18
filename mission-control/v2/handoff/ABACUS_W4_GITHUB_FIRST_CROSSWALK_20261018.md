# CP.HANDOFF / CP.RESUME — ABACUS W4 core-template consumer crosswalk

**Status:** MissionControl GitHub-first **read-only consumer/additive method note**, not a replacement for `CP_HANDOFF_RESUME_V1.json`, `GITHUB_FIRST_PROFILE_V1.json`, `closeout/CP_CLOSE_GITHUB_v1.json`, existing `MC_METHOD_PROFILE_REGISTRY_v1.json` or the ABACUS `LOSSLESS_HANDOVER_V2` generator. No new source queue, schema, authenticated Crew dispatcher or root closure authority.

## Published source and where-used

| Purpose | Existing canonical or additive source |
| --- | --- |
| Human handover message template | [ABACUS `handover/HANDOVER_MESSAGE_TEMPLATE.md`](https://github.com/GBOGEB/ABACUS/blob/main/handover/HANDOVER_MESSAGE_TEMPLATE.md) |
| Deterministic V2 source protocol / validation | [ABACUS `tools/handover_v2/process_spec.json`](https://github.com/GBOGEB/ABACUS/blob/main/tools/handover_v2/process_spec.json) |
| W4 dated source evidence, portable drop-in and machine readback | [ABACUS draft PR #2229](https://github.com/GBOGEB/ABACUS/pull/2229) at candidate `2f31e329078a21aaf4aa62ab1ba54e8b9b3c3709` |
| Core MissionControl handoff / resume control | `mission-control/v2/handoff/CP_HANDOFF_RESUME_V1.json` and `GITHUB_FIRST_PROFILE_V1.json` (this repository) |
| Governed G3P/N→N+3 method | `mission-control/v2/G3P_EXECUTION_OPERATOR.md`; profile registry remains canonical |
| Canonical closeout generator | `mission-control/v2/handoff/closeout/cp_close.py` (`CP.CLOSE`; `CP.CLOSEOUT` only an alias) |
| BD/LDAB root authority | [ABACUS issue #1929](https://github.com/GBOGEB/ABACUS/issues/1929) |
| Admission / remote dispatch | [ABACUS #1860](https://github.com/GBOGEB/ABACUS/issues/1860) / [CODEX #977](https://github.com/GBOGEB/CODEX/issues/977) |

## One governed GitHub-first use (not an executable API)

`CP.HANDOFF(scope="CURRENT_SESSION",mode="GITHUB_FIRST_MINIMAL",artifact="GITHUB_POINTERS+DROPIN+STATE",horizon="G3P:N_TO_N_PLUS_3")`

`CP.RESUME(source="GITHUB_FIRST",mode="VERIFY_REFRESH_EXECUTE",horizon="G3P:N_TO_N_PLUS_3")`

The receiver must read the **actual** ABACUS PR/commit and native source, not just this crosswalk. First recensus ABACUS main/PR exact heads, CODEX main, QPS **master**, all source/policy owners, actual run/job/attempt/ZIP evidence, prior vs latest first-red and matched denominator. Treat the dated ABACUS W4 source `403a794e0aac453545cff922c68273b61c527e9f` as historical and refresh before execution.

## W4 measurement (delegated evidence, not new provider)

ABACUS native [run 39065792654](https://github.com/GBOGEB/ABACUS/actions/runs/39065792654), attempt 1, PR head `43f20c25a1b922ec61f037eca47abfc28fecb3a9`: **nine/nine OS×Python jobs success**. All **nine** provider ZIP digests independently matched the downloaded bytes; all **nine** JSON/JUnit receipt pairs matched actual JUnit bytes with 25 pass per cell and zero fail/error/skip; 225/225 focused executions. GitHub-first source register in ABACUS #2229, not a CODEX/QPS acceptance receipt.

Historical ABACUS main B0 [39065946455](https://github.com/GBOGEB/ABACUS/actions/runs/39065946455), head `b1bfc7b7a5b6191e06a64fb6110d0e91f1ec5be4`, **4,013 pass, 1 dashboard publication-contract fail, 2 skip**. Any latest-main B0 and matched main/PR coverage must be freshly remeasured, not inherited. Preserve P3 secure-parser forecast **MISS 0/9** as an actual regression; later P5 focused green is a distinct source population.

## Execution edge and stop rules

`G3P N→N+3`:
1. **P1:** refresh actual live heads, primary and propagated first-red, policy and DOM/browser QA where relevant.
2. **P2:** run a bounded source-owned negative-test repair or register HOLD; no duplicate BD SSOT, no synthetic Crew.
3. **P3:** integrate only independently proven and authorized slices, emit exact native receipts, matched coverage and scoped DoV; pause on major global P0.

**Effective governance defect (separate admin owner):** identified ABACUS ruleset #24494381 approval-count 0, last-push approval disabled, resolved threads disabled and no required-status rule. Correctly admitted merge is UNKNOWN; `MERGE_ADMISSION=HOLD`. Authorized administrator must install effective controls and prove red/unapproved canary rejected; comments/CI do not substitute for the rule. No remote CODEX→ABACUS worker launch or accepted REX inferred.

**Fidelity and publication:** This explanatory crosswalk does not copy raw private test artifacts into QPS, claim a new validated V2 capsule, invent a ZIP, supply a current-live timestamp for old source or replace `master` engineering authority. Future accepted changes flow to their source-owned canonical files and are then re-observed here.
