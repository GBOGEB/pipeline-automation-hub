# CODE PURPLE / MissionControl — W4 lossless recovery handover

**Capture (UTC):** `2026-10-15T13:28:28+00:00` · **Mission:** W4.RECOVERY.001 · **Evidence class:** historical parent bytes + live GitHub source readback + locally generated W4 review (no new native W4 CI yet).

## Resume immediately

1. Read [`DROPIN_NEXT_SESSION.md`](DROPIN_NEXT_SESSION.md); paste it in the same conversation or a new one. Read [`GOLDEN_THREAD.md`](GOLDEN_THREAD.md), [`BD_QUEUE.md`](BD_QUEUE.md) and [`ARTIFACTS_PR_AND_RETENTION.md`](ARTIFACTS_PR_AND_RETENTION.md).
2. Open [`site/index.html`](site/index.html) for interactive BD, evidence-leaf, anchor and artifact drill-down; open [`diagrams/01_convergence.mmd`](diagrams/01_convergence.mmd) for source execution.
3. Validate with `python tools/verify_handover.py .` and `python -m unittest discover -s tests -v` after extracting this ZIP.
4. On GitHub verify `master` still equals `f931e443cafae8b286b149ae4331a0326298730a` and W4 branch equals `d2ec6e0df8f5edf178a1225b79c687072479d3eb`. **If either moved, recensus first.**
5. Continue **W4-BD-001**, **W4-BD-002**, and **W4-BD-003** as disjoint first-red / overlay repair; these are staged in [W4 source branch](https://github.com/GBOGEB/pipeline-automation-hub/tree/d2ec6e0df8f5edf178a1225b79c687072479d3eb). Existing [Issue #529](https://github.com/GBOGEB/pipeline-automation-hub/issues/529) and [Mission #153](https://github.com/GBOGEB/pipeline-automation-hub/issues/153) remain BD/Golden Thread authorities.

## Do not confuse these evidence types

- **Already merged:** PR [#537](https://github.com/GBOGEB/pipeline-automation-hub/pull/537) W1/W2, [#539](https://github.com/GBOGEB/pipeline-automation-hub/pull/539) Global DoV, [#540](https://github.com/GBOGEB/pipeline-automation-hub/pull/540) Session Hook, [#541](https://github.com/GBOGEB/pipeline-automation-hub/pull/541) W3 Atlas source. W3 native Atlas first-red remains historically RED, even though source was merged.
- **Staged, not merged:** W4 source-only fix branch at `d2ec6e0df8f5edf178a1225b79c687072479d3eb`. No W4 PR, no terminal W4 native receipt, no approval and no ruleset waiver.
- **Native failure evidence:** Atlas [#38739254875](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38739254875) and [#38739428503](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38739428503): 87 tests, one false-red. Session Hook [#38739313365](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38739313365): 19 unit tests PASS but subsequent HTML title assertion fails.
- **Local rendered binaries:** The original W3 ZIP includes `.xlsx`, `.docx`, `.pptx`, `.pdf`, `.svg`, `.html`, JSON and hashes. They are **NOT new canonical GitHub source** nor hosted/approved corporate output.
- **Historical census:** 6/42 observed source/status cells, 36 unknown leaves, 2/5 comparable G4 anchor matches, 3 stale; **not** global code coverage or 36 independent defect roots.

## Integrity and custody

The `parents/` folder preserves four original ZIP files **byte-for-byte** (W1, W2, combined W1/W2, W3). `state/parent_ancestry.json` contains their SHA-256 hashes and sizes. `MANIFEST.json` hashes each new handover entry, including the frozen parents. The top-level final ZIP SHA-256 is recorded in the external release receipt after sealing, avoiding self-reference.

This guarantee is lossless for the included bytes and captured source-state references; **it is not a complete ChatGPT transcript export or a GitHub clone**. The source conversation's original message IDs and timestamps are unavailable. GitHub Actions artifacts can expire; copy critical generated ZIPs to a durable controlled store, preserve hashes and restrict confidential originals.

## Authority

`security_waiver=false; merge_authorized=false; authority_transfer=false; native_four_hop=UNKNOWN; qps_engineering=DEFER; corporate_doc_release=HOLD`.