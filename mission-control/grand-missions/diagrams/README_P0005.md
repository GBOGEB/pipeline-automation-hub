# GM-I-C R2 / BRIDGEHEAD — P0005 Mermaid atlas

**Snapshot:** 2026-11-10 (Europe/Brussels). **Status:** draft and read-only. This folder is a *versioned visualization of existing governed facts*, not a new DAG scheduler, a new GMI receipt owner or an overwrite of the [W0 overlay](../GM_I_C_R2_BIDIRECTIONAL_BRIDGE_CONTROL_v1.yaml) from open [Hub #1135](https://github.com/GBOGEB/pipeline-automation-hub/pull/1135).

## The three Mermaid source assets

| File | Intent | Semantics |
|---|---|---|
| [Execution lanes](GM_I_C_R2_EXECUTION_LANES_P0005.mmd) | What may proceed disjointly on separate owner branches | Parallel lanes A Hub, B GEMINI, C JADE ISO batch and D external owner habitat join only on the W4 promotion gate; not a dispatch plan |
| [Promotion dependencies](GM_I_C_R2_PROMOTION_DEPENDENCIES_P0005.mmd) | What **must finish** before the next step is admitted | Directed acyclic AND-join W0 independent FPC + W1/W2 owner DoV + effective protections + hosted W3 IC3; separate ISO batch release branch; Kahn-compatible topology |
| [SIPOC](GM_I_C_R2_SIPOC_P0005.mmd) | Who supplies, processes, receives and approves evidence | Five columns Supplier/Input/Process/Output/Customer; Drive proposal is untrusted data, broker may create a **draft PR only**, source authority remains GitHub |

**Full B-ledger:** [P0005 B01–B38 status / DoD / DoV / priorities](../GM_I_C_R2_P0005_BD_QUEUE.md). History: [P0004 32/17/15](https://github.com/GBOGEB/pipeline-automation-hub/pull/1135#issuecomment-6773322492) → P0005 **38 total / 20 DONE / 18 OPEN**; this count is **only Hub B namespace**. The separate [BridgeFlow 36-item owner ledger](https://drive.google.com/file/d/1NRaO0rlGyWuwfh4a5VuwEohQU77b8FON/view) is cross-referenced, **not aggregated**.

## SIPOC control table

| Suppliers | Inputs | Process owner | Outputs | Customers and what is **not** granted |
|---|---|---|---|---|
| GitHub protected branch and source owners | Repo commit SHA, tree and blob OIDs | GEMINI snapshot adapter W1 | Exact-SHA archive + manifest, no git metadata | Drive readers; snapshot is **not** Git authority |
| Drive-only agent / human proposer | GMI package, untrusted instructions as inert data, declared base SHA | GEMINI canonical proposal broker W2 | Quarantined REJECT or patch + draft PR + ledger receipt | CI/reviewers/owner; **not** default-branch push |
| Owner of WIF/Drive authentication | Scoped GitHub OIDC and Viewer service account, root ACL | GEMINI hosted ingress W3 | Hosted census SHA and `IC3_DRIVE_READONLY_GT0_STEP_PASS` only after a real run | Independent QA / Mission Control; connector read alone is **not** IC3 |
| Codex, security reviewers, human owner and required CI | Exact head, review completion, fail-closed negative canary, native jobs | Hub FPC / configured default-branch admission | Verifiable review + status receipt | Protected main; **no** waiver or automatic merge |
| Independently authorized second consumer | Pinned snapshot + separately approved access | W5 parity after hosted W4 | Independent semantic/byte digest and delta | Owner; not engineering or QPS release approval |

## Source authority, rendering, and QA

- Hub `master@401c57316197c81e910f0b3da7ea7322e1f109fc` is the base of this **new docs branch**, independent of #1135 and other PR heads.
- W0 overlay read from open #1135 `41e287f89fd48bc03e4ca7960f0c71fd62ca7a62` and its R2-W0..W6 `depends_on`; those wave states are **not** rewritten. R2-W1/R2-W2 may be implemented offline in parallel; **promotion** adds owner/DoV prerequisites and never starts W4 while W3 IC3 is withheld.
- GEMINI current `main@d3a885ab8593cbf9af22e6fce6c64d589ad80575`: #52 repaired #51 regression; [W2 CI](https://github.com/GBOGEB/GEMINI/actions/runs/42893743479), [profile negative CI](https://github.com/GBOGEB/GEMINI/actions/runs/42893743447), [BLSN](https://github.com/GBOGEB/GEMINI/actions/runs/42893744721) all succeeded at that head. No owner W2 P3 and no W3 hosted WIF claim.
- Structural review on the committed Mermaid files: execution **17 nodes/15 edges/7 Kahn layers**, promotion **22/20/7**, SIPOC **17/16/6**. Directed graph QA reported **zero undeclared edge endpoints** and **no cycles**, based on the explicit `-->` edge lists. The W4 AND join explicitly requires independent Hub protection **B29** and GEMINI main protection **B37** (issue #50), not just code CI. This is **not** a browser/CLI Mermaid renderer parse or a passing native CI test; [B34](../GM_I_C_R2_P0005_BD_QUEUE.md) remains open.
- The Mermaid renderer/QA method is already proposed separately in [Hub #1175](https://github.com/GBOGEB/pipeline-automation-hub/pull/1175); avoid cloning its `build_mermaid_check.py` into this docs-only branch. After that method is owner-qualified, re-render these files under its pinned version and record actual browser/SVG proof. In the meantime, do not mark the diagrams render-qualified based on topology alone.
- Colors: dark purple, violet and blush (no blue). Class colors distinguish historical source completion, review-wait, owner-held gates and dependent admission holds; **colors are not authority**.

## Admission and stop rules

1. **Exact-head checks only.** CI green from a prior commit is historical evidence, not a current gate. A quota-limited Codex review is not an eligible completed exact-head independent review.
2. **Never merge on red.** #1135, #1138, #1152, #1160 and the exclusive batch #1164 retain their required FPC holds. Do not weaken rules or invoke an unapproved waiver to ship documentation.
3. **One source-owner path.** Batch #1164 is only the nominated integration *candidate* for #1162/#1163/#1138, not a completed merge. Never integrate batch and originals independently without redoing ancestry and owner disposition.
4. **Owner IC3 is separate.** [GEMINI #12](https://github.com/GBOGEB/GEMINI/issues/12) requires scoped OIDC-WIF, service account, repository variables, Viewer ACL and real hosted non-zero census. The separate BridgeFlow Drive folder does not replace the approved root.
5. **Formal credit delta=0 / authority_transfer=false.** No QPS engineering, contract, owner release, hosted Drive, PR-merge or consumer B authority is inferred from these diagrams.
