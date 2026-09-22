# LOSSLESS HANDOVER — 3P* + MIP / HIST-BD-033

## Authority

- Execution wave: **PARTIAL**
- Authority transfer: **false**
- Formal credit delta: **0**
- Canonical BD lifecycle: pipeline-automation-hub#85
- Historian parent: pipeline-automation-hub#76
- MIP stabilization: pipeline-automation-hub#372

## Exact snapshot

- pipeline-automation-hub master: `216e13914c0fd9d559f6fdc50c0f2a3df3f42cf1`
- ABACUS main: `a9926a4f460833fd467a12af2fc09c333079261b`
- cryoplant-project main: `df84ddc293efd3c9fdb2e8cb098c745d26bdac3a`
- BD033 repair PR: cryoplant-project#1634
- BD033 repair head: `8d0a99bc7185a00ffa35d34c60df16ba570b447a`
- BD033 issue: cryoplant-project#1635

## 3PR outcome

### Refresh — PASS

The prior register had 32 durable roots, all DONE/CONTROL. Current independent
gates remain:

1. cryoplant-project#923 — private GitHub Actions admission; zero-step,
   non-compensating.
2. ABACUS#1278 / REX-CM-005 — merge-admission prevention requires repo-admin
   branch/ruleset binding.
3. ABACUS#1313 — Appendix 8.4/source-evidence work order; source return required.

### Probe — PASS / MATERIAL FIRST-RED

Merged cryoplant-project#1629 introduced a repo-local trust-anchor file for BT0
HEPAK evidence. Current-code audit found that repository content could still
self-assert the supposed owner boundary by setting:

- `status=ACTIVE_TRUST_ANCHOR`
- `authority=OWNER_SOURCE_ATTESTATION`
- an arbitrary matching 64-char source digest in anchor and receipt.

The positive unit fixture exercised exactly that path with `"b"*64`.

This is a genuinely new semantic defect and is allocated as **HIST-BD-033**:
`repo_local_active_trust_anchor_can_self_attest_arbitrary_source_digest`.

### Rank — PASS

1. HIST-BD-033 -> **PROVE / HOLD_RUNNER**
2. cryoplant-project#923 -> **RETURN / OWNER_ACTION_REQUIRED**
3. REX-CM-005 -> **RETURN / OWNER_ADMIN_REQUIRED**
4. ABACUS#1313 -> **RETURN / SOURCE_EVIDENCE_REQUIRED**

No unrelated application repair is justified.

## Repair lineage

### #1629 — merged precursor

- merge: `23162ea21df0459d5778237ce301f326fa338d06`
- result: useful first hardening, but not a true independent trust boundary.
- runtime checks remain non-executed because of #923.
- merge occurred while exact-head Codex review was still running; retained as
  REX-CM-005 recurrence evidence.

### #1633 — INVALIDATED_STALE_BRANCH

A follow-up draft was built by copying whole files from the old #1629 branch.
Exact PR diff exposed unrelated rollback of newer BT2 population/tolerance
logic. #1633 was closed before merge. This is negative evidence and a process
lesson: always diff a current-main surgical rebuild before proof.

### #1634 — current repair

Created **draft-first** from current main. Exact diff is BT0-only.

Repair:
- require repo receipt + ACTIVE repo anchor + owner-controlled environment
  workbook/SHA agreement;
- env keys:
  - `QPS_HEPAK_OWNER_SOURCE_SHA256`
  - `QPS_HEPAK_OWNER_SOURCE_WORKBOOK`
- project anchor remains `PENDING_TRUSTED_DIGEST`;
- optional `source_file` must remain inside the governed root;
- no real digest was invented.

Proof state at snapshot:
- exact-head Codex review: **running/pending**
- verify-ssot run `35732308950`, job `106760673654`: failure with
  `steps=null`
- Global Victory Score run `35732308999`, job `106760675823`: failure with
  `steps=null`
- those runtime reds are #923 admission evidence, not application failure.
- #1634 remains DRAFT and must not be merged until current-head review is
  consumed and any material finding is repaired.

## MIP

### Modernize — PASS

- durable roots: 32 -> 33
- current open semantic roots: 0 -> 1
- zero-step fan-out remains deduplicated to #923
- stale branch #1633 is INVALIDATED, not a new BD

### Innovate — PASS_CANDIDATE

Reusable control pattern:
`repo receipt + repo anchor + owner-controlled execution attestation`.

Additional process control:
`current-main rebuild -> exact diff -> draft-first -> review/proof -> merge`.

### Perpetuate — PASS_PARTIAL

- HIST-BD-033 entered the living register as ACTIVE
- Doctor.Contracts + Historian own proof/closure
- REX-CM-005 recurrence now includes cryoplant #1629
- no runtime GOLD, engineering acceptance, numerical credit, or source digest
  has been promoted

Measured pulse:
- prior roots: 32
- new roots: 1
- retired roots: 0
- reopened roots: 0
- **net_BD_delta = +1**
- reason: genuine new current-code discovery

## Owner/admin actions

### cryoplant-project#923

1. Restore private-repository Actions admission / billing / usage, or attach a
   trusted self-hosted runner.
2. Do **not** change workflow/application semantics to work around zero-step
   admission.
3. Rerun unchanged Release Runner Probe.
4. Required proof: `runner_id != 0` and `steps > 0`.
5. Then rerun unchanged current validator and retain exact receipt.
6. Repeat on a fresh later SHA before GOLD/control promotion.

### REX-CM-005

Bind required checks to branch/ruleset merge admission. CONTROL requires:
- a deliberately red governed change that is mechanically non-mergeable; then
- a distinct later classified/green change that is mergeable.

### BT0 HEPAK source

Provide the **real** workbook identity and SHA-256 through the owner-controlled
execution boundary. Do not infer a digest from file name, File Library ID, or
repo-local receipt consistency.

## Exact continuation edge

1. Refresh cryoplant-project#1634 and exact head.
2. Consume current-head Codex review.
3. If material finding -> repair **only that finding** and re-request review.
4. If clean -> keep implementation prepared; runtime proof remains held by
   #923 unless a trusted >0-step execution becomes available.
5. If #923 owner state changed -> run unchanged Release Runner Probe first.
6. Only after required proof may HIST-BD-033 move ACTIVE -> DONE.
7. REX-CM-005 remains prevention-withheld until admin admission proof.
8. ABACUS#1313 remains source-return work; do not infer Appendix 8.4 states.
9. After BD033 disposition, resume F2 Historian pressure selection.

## Stop rules

- zero-step != application failure
- merge != proof
- review clean != runtime GOLD
- File Library reference != byte digest
- repo-local authority string != independent owner attestation
- no synthetic engineering/numerical/formal credit
- do not reopen CONTROL lanes without observed regression

## Drop-in continuation

```text
NEXT_AGENT_INSTRUCTION

Execution mode: sequential, strict.
EXECUTION_WAVE_TYPE = PARTIAL
authority_transfer = false
formal_credit_delta = 0

REFRESH FIRST:
- GBOGEB/cryoplant-project main
- GBOGEB/cryoplant-project#1634
- GBOGEB/cryoplant-project#1635
- GBOGEB/cryoplant-project#923
- GBOGEB/ABACUS#1278 (REX-CM-005)
- GBOGEB/ABACUS#1313
- GBOGEB/pipeline-automation-hub#85/#76/#372

CANONICAL CURRENT ROOT:
HIST-BD-033 = repo_local_active_trust_anchor_can_self_attest_arbitrary_source_digest

EXPECTED REPAIR:
cryoplant-project#1634
expected head at handover:
8d0a99bc7185a00ffa35d34c60df16ba570b447a
state at handover: DRAFT / exact-head Codex review pending

DO NEXT:
1. consume #1634 exact-head review;
2. repair only if a material finding survives current code;
3. do not treat cryoplant runtime reds as product failures while #923 jobs have steps=null;
4. if #923 owner-side state changed, run unchanged Release Runner Probe and require runner_id != 0 + steps > 0 before validator/GOLD;
5. keep project HEPAK anchor PENDING_TRUSTED_DIGEST until real owner-controlled workbook identity + SHA-256 are supplied;
6. move HIST-BD-033 to DONE only after required proof + current-code survival;
7. keep REX-CM-005 ACTIVE_PREVENTION_WITHHELD until branch/ruleset admission blocks a deliberate red;
8. keep ABACUS#1313 SOURCE_PENDING; do not infer Appendix 8.4 topology;
9. then resume next F2 Historian deep-dive by measured unresolved pressure.

NEGATIVE EVIDENCE TO RETAIN:
- #1629 merged before review completed;
- #1633 closed INVALIDATED_STALE_BRANCH because exact diff exposed unrelated BT2 rollback;
- #923 zero-step jobs are infrastructure pre-execution, non-compensating.

Do not fabricate source, runner, review, compliance, numerical, or acceptance evidence.
```
