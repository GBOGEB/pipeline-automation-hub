# GM-I-C P0009 — append-only post-merge admission witness (12 November 2026)

The canonical [P0008 CP.CLOSE worktree](../w11-gmic-r2-p0008/README.md) and 46-row B ledger remain immutable. This is a **source-pinned observation**, not a second scheduler, bridge, FPC controller or an owner acceptance receipt.

Ten selected GM-I-C family Hub PRs were merged with an exact-head trusted FPC failure **recorded before the merge** and zero GitHub APPROVED reviews on those PRs. Each event's SHA, run and timestamp is in `POSTMERGE_AUDIT.json`. The Hub ruleset 25789280 is active but currently requires no independent approvals and omits the trusted FPC context. We did **not** reconstruct every historical version of that ruleset; the record does not pretend to prove when it was configured.

Root authority: [Hub #336](https://github.com/GBOGEB/pipeline-automation-hub/issues/336). Owner/admin must approve and apply a non-bypassable exact-head FPC context, after-last-push independent review and genuinely rejected RED versus admitted GREEN canaries. No reviewer, ruleset or code waiver may be invented to close #336.

The Kahn graph is a **proof/sequence projection only**: source census → classified audit → #336 owner policy → enforce rule → negative and positive canary → W0 DoV. Independently, GEMINI #44 W1/W2 source protocol, #12 hosted IC3 and #50 main protection must pass before W4. W5 and W6 remain sequential. A historical source merge is never W4 proof.

### Execution
`python mission-control/v2/handoff/closeout/w12-gmic-r2-p0009/test_p0009.py`

`python mission-control/v2/handoff/closeout/w12-gmic-r2-p0009/build_p0009.py --out ./p0009-release`

The offline runner writes a self-contained ZIP, SHA-256 receipt, CSV and local HTML dashboard with JSON import/export. The HTML's **reload** action reloads embedded data, not GitHub APIs. For live recensus, repeat the authenticated source tool reads and rebuild a *new* snapshot.

**Hold:** `10_MERGED_WITH_PREMERGE_FPC_RED / APPROVED_REVIEW_0 / B46_BASELINE_22_DONE_24_OPEN / ISSUE_CLOSURE_DELTA_0 / W4_HOLD / AUTHORITY_TRANSFER_FALSE`.
