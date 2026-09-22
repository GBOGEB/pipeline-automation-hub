# LOSSLESS HANDOVER — 3P* + MIP / HIST-BD-033

## Authority and state

- execution_wave_type: PARTIAL
- authority_transfer: false
- formal_credit_delta: 0
- central Historian: pipeline-automation-hub#76
- living BD/REX control: pipeline-automation-hub#85
- MIP stabilization: pipeline-automation-hub#372
- MissionControl publication PR: pipeline-automation-hub#393 (DRAFT at handover)

## Exact repository snapshot used by this handover

- pipeline-automation-hub master before publication: `216e13914c0fd9d559f6fdc50c0f2a3df3f42cf1`
- ABACUS main observed: `a9926a4f460833fd467a12af2fc09c333079261b`
- cryoplant-project main observed after concurrent advance: `0fa104517fd98c57903ddc37f3fd34958694c80c`
- current BD033 repair PR: cryoplant-project#1645
- current BD033 repair head: `40e75847c562d8c2074b983ca9a03167bf3bff05`
- BD033 issue: cryoplant-project#1635

## 3P* result

### Refresh — PASS

Independent non-coding gates remain:
1. cryoplant-project#923 — private Actions runner/admission; zero-step failures are non-compensating.
2. ABACUS#1278 / REX-CM-005 — owner/admin branch/ruleset merge-admission binding.
3. ABACUS#1313 — Appendix 8.4/source evidence return; do not infer topology.

### Probe — PASS / material first-red

HIST-BD-033:
`repo_local_active_trust_anchor_can_self_attest_arbitrary_source_digest`

The merged #1629 design could encode ACTIVE_TRUST_ANCHOR +
OWNER_SOURCE_ATTESTATION and an arbitrary matching SHA in repository content.
That is not independent owner authority.

### Rank — PASS

1. HIST-BD-033 — ACTIVE; repair/review + owner environment + source + runner proof.
2. #923 — RETURN/OWNER_ACTION_REQUIRED.
3. REX-CM-005 — RETURN/OWNER_ADMIN_REQUIRED.
4. ABACUS#1313 — RETURN/SOURCE_EVIDENCE_REQUIRED.

## Repair genealogy — retain all negative evidence

### #1629 — merged precursor

- merge `23162ea21df0459d5778237ce301f326fa338d06`
- improved receipt/anchor binding but did not create independent owner authority
- merged while exact-head review was still running; retained under REX-CM-005 recurrence
- private runtime remained non-executed under #923

### #1633 — INVALIDATED_STALE_BRANCH

Whole-file carry-forward from an older branch.
Exact diff exposed unrelated rollback of newer BT2 population/tolerance logic.
Closed before merge. Do not reuse.

### #1634 — P1 review surface, closed unmerged

A caller-settable environment candidate was reviewed.
Codex P1: arbitrary process env values do not authenticate owner authority.
Required protected execution or signed/secret-backed attestation.
Branch subsequently advanced beyond that PR surface, so it was not reused as proof.

### #1645 — CURRENT DRAFT REPAIR

Current exact head:
`40e75847c562d8c2074b983ca9a03167bf3bff05`

Exact current-base diff guard:
- 5 changed files
- no `validate_bt2` or `BT2_BFLOW` hunks
- HMAC signed-attestation logic present
- manual protected environment path present
- explicit regression that public workbook/SHA env variables do not create authority

Design:
- HMAC-SHA256 canonical payload includes schema, status, authority,
  source_workbook, source_workbook_sha256, source_reference.kind/id.
- signature field: `owner_attestation_hmac_sha256`.
- verification key env: `QPS_HEPAK_OWNER_ATTESTATION_HMAC_KEY`.
- project-authoritative path is manual-only job using GitHub Environment:
  `qps-hepak-owner-attestation`.
- ordinary PR job receives no owner secret.
- checked-in project anchor remains PENDING; no real digest/signature is invented.
- test-only HMAC key/signature fixtures exercise code only and are not project evidence.

At snapshot the post-P1 exact-head Codex review has been requested and is pending.
Keep #1645 DRAFT until it is consumed.

## MIP

### Modernize — PASS

- prior durable roots: 32
- new root: HIST-BD-033
- durable roots: 33
- open semantic roots: 1
- zero-step private Actions fan-out remains deduplicated to #923

### Innovate — ACTIVE_REPAIR

Reusable pattern now under review:
`repo receipt + repo anchor + HMAC signed canonical payload + protected owner secret`.

Process control:
`refresh main -> surgical change -> exact current-base diff -> draft-first -> review -> proof -> merge`.

### Perpetuate — PASS_PARTIAL

- BD033 stays ACTIVE
- Doctor.Contracts + Historian remain assigned
- REX-CM-005 stays prevention-withheld
- runtime GOLD, engineering/numerical acceptance and source trust remain WITHHELD

Measured pulse:
- prior roots 32
- new roots 1
- retired 0
- reopened 0
- net_BD_delta = +1 (genuine new current-code discovery)

## Required owner/admin actions

### A. cryoplant-project#923

1. Restore private-repo Actions admission/billing/usage or attach a trusted self-hosted runner.
2. Do not change product/workflow semantics to bypass zero-step admission.
3. Rerun the unchanged Release Runner Probe.
4. Require runner_id != 0 and steps > 0.
5. Then rerun unchanged current validator and retain exact receipt.
6. Repeat on a distinct later SHA before GOLD/control promotion.

Representative zero-step evidence retained:
- verify-ssot run35732308950/job106760673654: steps=null
- Global Victory Score run35732308999/job106760675823: steps=null

### B. BT0 authenticated owner channel

1. Create/configure GitHub Environment `qps-hepak-owner-attestation`.
2. Protect it with owner/admin review policy appropriate to the repository.
3. Set environment secret `QPS_HEPAK_OWNER_ATTESTATION_HMAC_KEY`.
4. Never commit or paste the HMAC key.
5. Obtain the real HEPAK workbook SHA-256; File Library ID is not a digest.
6. Promote/sign the anchor only from that real owner/source evidence.
7. Dispatch the manual owner-attested job only after real receipt + signed anchor exist.

### C. REX-CM-005

Bind required governance/checks to branch/ruleset merge admission.
CONTROL requires:
- deliberately red governed change is mechanically non-mergeable;
- distinct later green/classified change is mergeable;
- both receipts retained.

### D. ABACUS#1313

Await real Appendix 8.4/source evidence.
Do not infer valve states, recovery path, or mode-dependent V_eff.

## Exact continuation edge

1. REFRESH cryoplant-project main + #1645 + #1635 + #923.
2. CONSUME #1645 current-head Codex review.
3. If material finding -> repair only that finding, re-diff, re-review.
4. If review clean -> keep draft/proof hold until owner environment/source/runner prerequisites are met; do not create synthetic runtime proof.
5. If #923 changes -> run unchanged Release Runner Probe first.
6. Only after authenticated owner source + protected job + >0-step proof + merge/current-code survival may HIST-BD-033 become DONE.
7. Keep REX-CM-005 ACTIVE_PREVENTION_WITHHELD.
8. Keep ABACUS#1313 SOURCE_PENDING.
9. Then resume next F2 Historian pressure selection.

## Stop rules

- zero-step != application failure
- merge != proof
- review clean != runtime GOLD
- File Library reference != byte digest
- plain/caller-set env != owner authority
- test HMAC key/signature != project evidence
- repo-local authority label != authenticated owner return
- no synthetic engineering, numerical, compliance, or acceptance credit

## Drop-in continuation

```text
NEXT_AGENT_INSTRUCTION

execution_mode = sequential_strict
EXECUTION_WAVE_TYPE = PARTIAL
authority_transfer = false
formal_credit_delta = 0

REFRESH FIRST:
- GBOGEB/cryoplant-project main
- GBOGEB/cryoplant-project#1645
- GBOGEB/cryoplant-project#1635
- GBOGEB/cryoplant-project#923
- GBOGEB/ABACUS#1278
- GBOGEB/ABACUS#1313
- GBOGEB/pipeline-automation-hub#85/#76/#372/#393

CANONICAL ACTIVE ROOT:
HIST-BD-033 =
repo_local_active_trust_anchor_can_self_attest_arbitrary_source_digest

CURRENT REPAIR:
GBOGEB/cryoplant-project#1645
expected head at handover:
40e75847c562d8c2074b983ca9a03167bf3bff05
state: DRAFT
post-P1 exact-head Codex review: PENDING at handover

DO NEXT:
1. consume #1645 exact-head review;
2. repair only a material surviving current-head finding;
3. keep exact diff BT0-only; reject any BT2 rollback;
4. do not treat cryoplant runtime reds as product failures while #923 jobs have steps=null;
5. require owner/admin protected environment qps-hepak-owner-attestation and secret QPS_HEPAK_OWNER_ATTESTATION_HMAC_KEY before project-authoritative owner-attested execution;
6. require the real HEPAK workbook digest + signed anchor; do not infer from File Library ID;
7. if #923 owner state changes, run unchanged Release Runner Probe and require runner_id != 0 + steps > 0;
8. move HIST-BD-033 to DONE only after authenticated source + protected execution + >0-step proof + merge/current-code survival;
9. keep REX-CM-005 prevention-withheld until branch/ruleset admission blocks a deliberate red;
10. keep ABACUS#1313 source-pending;
11. update/merge MissionControl #393 only after its artifacts match the final #1645 proof state.

NEGATIVE EVIDENCE TO RETAIN:
- #1629 merged before review completion;
- #1633 INVALIDATED_STALE_BRANCH due BT2 rollback in exact diff;
- #1634 Codex P1: caller-set env is not authenticated owner authority;
- #923 zero-step failures are infrastructure pre-execution.

Do not fabricate source, signature, secret, runner, review, compliance,
numerical, engineering, or acceptance evidence.
```
