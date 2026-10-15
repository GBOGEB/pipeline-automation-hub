# CODE PURPLE — M3 recursive, semantically lossless continuity

**Owner:** MissionControl #153; [M3 validation PR #549](https://github.com/GBOGEB/pipeline-automation-hub/pull/549). **QPS ACCEPT:** DEFER. **Outward release:** HOLD. **Admission:** independent check / eligible reviewer / protected-main controls not established.

This is a **reproducible, source-bound continuation** of existing M2. It does not duplicate QPS engineering SSOT or expose an automatic ChatGPT message API. The available user-intent source consists of 15 manually summarized M2 directives and one newer summarized M3 directive. Exact original ChatGPT message IDs/times remain UNKNOWN. No transcript-level losslessness is claimed.

## Source hierarchy — immutable ancestors first

Read in this order:

1. [M1 session hook](../../../../golden-thread/session_hook/README.md) (original intent → owned action; reuse only).
2. [Canonical M2_STATE.json](../M2_STATE.json), fixed Git blob `88380f1840bce1bc72008b5ee953e580bfe9d604`, original 15 intents/20 actions.
3. [Full M2 handover](https://github.com/GBOGEB/pipeline-automation-hub/blob/master/handover/session/LOSSLESS_HANDOVER_CODE_PURPLE_M2_20261015.md).
4. [Dated M2 live reconciliation](https://github.com/GBOGEB/pipeline-automation-hub/blob/master/handover/session/CODE_PURPLE_M2_LIVE_RECONCILIATION_20261015.md), Git blob `5c2e4530bf8e298afb8cd48daf2a42a5daba5631`, seven subsequent action addenda M2-A21..A27.
5. [M3_INPUT.json](M3_INPUT.json): one new bounded user-intent summary, four new disjoint actions M3-A01..A04, six exact historical repository heads, nine independent release gates, and preregistered forecast.
6. [M3 validator + report generator](m3_handover.js) and [36 native negative/control tests](test_m3_handover.js).
7. [M3 copy/paste pickup](M3_DROPIN.md); the exact-head generator also produces the complete human-readable 18–20 KB handover.

This is **semantic/action losslessness across the supplied source materials**, not proof that unseen chat messages, private files, agent environments, hidden history, or external systems were captured.

## Output families and reproduction

Native command from repository root:

```bash
HEAD_SHA="$(git rev-parse HEAD)"
node mission-control/federation-atlas/m2_session/continuation/test_m3_handover.js
node mission-control/federation-atlas/m2_session/test_m2_portal.js
node mission-control/federation-atlas/m2_session/m2_portal.js --check
node mission-control/federation-atlas/m2_session/continuation/m3_handover.js \
  --source-sha "$HEAD_SHA" --out /tmp/m3-handover
node mission-control/federation-atlas/m2_session/continuation/m3_handover.js \
  --check --source-sha "$HEAD_SHA" --out /tmp/m3-handover
```

The generated outputs are **M3_INDEX.json, M3_FULL_HANDOVER.md, M3_DROPIN.md, M3_DAG.mmd, M3_DASHBOARD.html and M3_MANIFEST.json**, all deterministic for an exact head. They are attached to GitHub Actions runs as review artifacts. The corresponding original JSON and GitHub Markdown source files stay in Git; no handover ZIP or TAR is committed.

### Evidence-class matrix

| Capability | Supported proof | Not supported |
|---|---|---|
| Source ancestry | Exact pinned M2 Git blob and M2 reconciliation blob; 16 intents, 31 actions | Complete private chat transcript or original message times |
| Code/testflight | Native 36 M3 controls + 12 M2 portal + 8 canonical Golden Thread + 19 session tests, each exact-head when terminal | Formal independent reviewer/merge authority |
| Derived HTML | Offline responsive, searchable, byte-hashed projection; browser QA separate | Live pipeline execution, Pages publishing, Docker/LLDB/MCP connection |
| Federation | One historical G1→G5 same-repo byte replay | CODEX→ABACUS→QPS accepted native recipient |
| QPS engineering | Historical 70/90 formal obligations, 36/45 breadth, 34/45 depth | Fresh engineering recensus, eight original bytes, safety authorization |
| Security | Historical CODEX 1,221 nonblocking Ruff findings retained; ABACUS active roots separately owned | 1,221 unique roots or waived security |

## Actual stabilization wave record

| Wave | Stable source | DoV | Finding |
|---|---|---|---|
| W0 · freeze | `44e38e8d9090496310667a292d29d13fd596c2f9` | M2 source+overlay pins in M3_INPUT | 15+20+7+4 preserved in preregistered contract |
| W1 · backend | `20ad5679b4369a253eb04bc7d92d5a1dfe2cbb93` | Generator structural contract implemented | Historical QPS and governance HOLD |
| W2 · first native | `4b833c09d343b365ee9802354d85f2e125435f57` | [Run 38767081417](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38767081417) | 34/34 actual tests PASS, but expected-count guard was 35: native job FAIL. Other Golden Thread job PASS |
| W3 · count/control repair | `e8a6d85cafe28b638730fe936607d9cf698a3655` | [Run 38767581063](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38767581063) | 35/35 new native tests PASS, M2 12 tests PASS, inherited M1 8+19 PASS, 6 generated outputs SHA-parity PASS |
| W4 · mobile polish | HEAD must be refreshed | New exact-head CI required | Card layout, accessible field labels, 36th responsive control. Results unscored until terminal |

W3's actual GitHub artifact was `11990247311`, ZIP archive SHA-256 `fb6a73d7e3e36650167a2a36a541d6d14447a407207ea0d6dbe969d69fec9d87`. An independent downloaded-byte check verified all five primary generated outputs and the manifest on W3 source. Browser inspection at 1440x1000, 1280x800 and 390x844 also passed technically, with a W4 mobile readability improvement identified. The HTML projection remains **L3 presentation only**.

## Current release P0 / P1 dependency order

First restore effective required checks, branch protection and eligible human review for releasing repositories; historic merges do not become approved through successful checks. Resolve ABACUS #1993/#2003 disjoint first-reds and current CODEX attributed Ruff/security debt. Then independently authenticate the KEB→DOW→QPS recipient chain with exact SHA, run, job, attempt, downloaded bytes and owner verdict. Bind the eight original QPS physical objects and obtain #75/#943 authorized engineering decisions. Only then execute governed outward binary/Pages QA and exact-main REX.

No unverified CI root, LLM review comment, configured crew entry, or HTML button is a proof of owner acceptance.

## Stop / handover protocol

When a conversation exceeds 3–5 substantial pulses, the source head drifts, first-red ownership changes or the user interface slows: finish the atomic GitHub update, append a source-bound DoV, preserve ALL unknowns/HOLDs, provide [M3_DROPIN.md](M3_DROPIN.md), and terminate the long chat. Do not silently replace M2_STATE, rescore the preregistered forecast in place, use ZIP/TAR as the handover SSOT, or invent original ChatGPT message IDs.
