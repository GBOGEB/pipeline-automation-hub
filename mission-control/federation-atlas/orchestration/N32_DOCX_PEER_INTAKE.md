# N3.2 DOCX TypeScript owner-return admission boundary

This is a read-only, typed sibling of the canonical five-repository
federation/exact_head_receipts.py. It does not extend that owner's fixed
reconciliation cohort and does not create a second federation scheduler.

Source owner PR: https://github.com/GBOGEB/DOCX_RTM_Automation/pull/113
Hub runtime branch proof: https://github.com/GBOGEB/pipeline-automation-hub/pull/1257

## Evidence inputs

- Exact DOCX source HEAD, not PR synthetic merge SHA.
- Native DOCX ZIP containing the six-test log, owner_receipt.json, manifest.json.
- Optional separately collected GitHub REST readback: run ID, attempt, job ID,
  completed status, nonzero steps, artifact ZIP SHA and exact checked-out head.
- No raw DOCX binary or private document content, no tokens.

## What the intake proves

All ZIP members are declared, bounded, non-symlink and unencrypted;
owner_receipt.json SHA equals manifest; all three source file/lock digests
exist with correct shape; 32 actual compiled TS queue FIFO identities,
repeat identical output, empty-queue, wrong-order and adapter duplicate
guards are present. The source owner explicitly disclaims native duplicate
rejection, full DOCX agent orchestration, JS branch coverage and owner approval.

The intake returns typed component CONTENT_VERIFIED but
owner_admission=PENDING_INDEPENDENT_ACCEPTANCE. An externally supplied
GitHub readback JSON can be shape- and SHA-matched here, but because
that record is not authenticated inside the Python process,
native_readback=NOT_AUTHENTICATED_BY_OFFLINE_VALIDATOR remains unchanged.

## Owner decision chain

Source PR #113 native TypeScript execution PASS → external source/job and
artifact SHA readback → independent DOCX reviewer APPROVED on exact head →
effective protection/FPC decision → owner acceptance → optional Hub federation
aggregation through its existing source owner. Until all gates qualify,
no cross-repository operational or branch-coverage credit.

## Command

python mission-control/federation-atlas/orchestration/n32_docx_peer_intake.py
  --zip <owner-github-native-archive.zip> --head <exact_DOCX_SHA>
  --out /tmp/n32-docx-intake.json

Disposition: ACTUAL_TS_COMPONENT_RECEIPT_CAN_BE_VALIDATED /
JS_BRANCH_COVERAGE_UNKNOWN / OWNER_ACCEPTANCE_PENDING /
FLEET_FEDERATION_AND_MERGE_ADMISSION_HOLD.
