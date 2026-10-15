# W6 Pulse 1 — original native Atlas artifact custody (append-only)

This is **a dated evidence delta, not a new SSOT**. Canonical authoring remains the existing W4 handover and the existing \`flightdeck.py\` producer. The historical W5 parent archive is frozen (SHA-256 \`325b077f5a56a6640ed57ba948273084328ba93a675602acfc0ae0815ebd6cd5\`); the complete W6 recursive ZIP with W5 and original GitHub Actions bytes is an external, hash-checked handover rather than a Git commit.

## Identity and outcome

- Observed current \`master\`: \`d9e9d05173a8fa898197de7a069d1fcfbd906de5\` (merged #545, after #544); current branch remains unprotected and ruleset collection empty.
- Historical native Method Atlas: [run #38747222991](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38747222991); **completed success**, attempt 1, job \`116463927229\`, executed at exact SHA \`6be34434568df474eab28751a098caf57f8cc6bd\`.
- Original Actions artifact [#11981899904](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38747222991/artifacts/11981899904): 187,463 bytes, SHA-256 \`7b2bf26385797ced5171a6696b0a927ec97db34874cc9707f7a26754c3293590\`. Original ZIP was downloaded, SHA matched GitHub's published digest; ZIP CRC PASS, 30 members.
- Native \`flightdeck-tests.log\`: **42 / 42 PASS**; native source-scoped statements **272/273 = 99.63%**, branches **116/118 = 98.31%**. Source \`flightdeck/manifest.json\` SHA-256 \`f59754a663659c611e4fb6577be498ef9212390e718826a12c099ad58ff6cdd9\`. All **10** manifest entries verified byte-length and SHA-256, including HTML/SVG/JSON/MD/XLSX/DOCX/PPTX/PDF.
- Native Atlas landing contains paths for N+2 latest overlay and Flight Deck. \`federation-latest.json\` still records historical W70 failure; **do not** convert historical child RED to Atlas failure or root closure.
- Main after #545: 16 workflow runs completed success on the observed head; 24 listed checks contained 21 success and 3 skipped. The new-main Atlas workflow was **not** among its 16 run records; a successful historical producer is not native new-main requalification.
- Historical Pages #38747221043 cancelled, superseded by [#38750529277](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38750529277) success on current master. Hosted Flight Deck HTML and binary link hashes are still **UNKNOWN** without served-byte readback.
- Historical G4 6/42 observed, 36 UNKNOWN, anchors 2/5 current and 3 stale. No causal red assigned to 36 evidence leaves. Four-hop federation UNKNOWN; QPS DEFER; corporate release HOLD.

## W4 → W5 preserved IDs / transitions

| W5 | W4 original | Root | Prior state | New evidence state |
| --- | --- | --- | --- | --- |
| MC-W5-001 | W4-BD-001 | ATLAS_FIRST_RED | WAIT_TERMINAL | VERIFIED_ON_HISTORICAL_MAIN_SHA; no producer first-red in run |
| MC-W5-003 | W4-BD-003 | N2_OVERLAY_LOSS | WAIT_TERMINAL | VERIFIED_IN_NATIVE_ATLAS_ZIP |
| MC-W5-005 | W4-BD-005 | W3_NATIVE_ARTIFACT | WAIT_TERMINAL | BYTE_VERIFIED_HISTORICAL_NATIVE |
| MC-W5-013 | W4-BD-007 | LOSSLESS_RETENTION | LOCAL_VERIFIED | W5 PARENT_VERIFIED; W6 successor seal external |
| MC-W5-004 | W4-BD-004 | UNPROTECTED_MAIN | OWNER_ACTION | HOLD_OWNER — protection not configured |
| MC-W5-006 | W4-BD-008 | HOSTED_FLIGHTDECK | WAIT_RELEASE | DEPLOY_SUCCESS_SERVE_UNKNOWN |

**Forecast readback:** \`PRED-W4-001\` source-conditional native producer PASS on the historical source; \`PRED-W4-003\` now verified 42 tests and 10 files; \`PRED-W4-002\` session hook not independently checked; \`PRED-W4-004\` hosted-byte readback pending. Forecast observations are not statistical evidence for M2/M3/PCA/Bradley–Terry.

## Admission

Protected-main **HOLD**; no independent eligible human review and no security waiver, merge or owner acceptance is asserted by this change. This draft receipt PR shall not be merged automatically; do not rerun the same Atlas SHA. Next admissible slice: effective owner-approved required checks and authorized independent review, then terminal native exact-main proof, then served-byte hash parity. Existing W4 source and binary/corporate originals are immutable.

**Sources**: [W4 handover](../W4/README_START_HERE.md) · [W4 BD queue](../W4/BD_QUEUE.md) · [Issue #529](https://github.com/GBOGEB/pipeline-automation-hub/issues/529) · [Golden Thread #153](https://github.com/GBOGEB/pipeline-automation-hub/issues/153).
