# WATCH_VNEXT -- signed QPS owner-edge and local outbox

Stack: canonical CP.CLOSE #880 (merged), GoGREEN consumer #881, source-ledger adapter #882, this QPS-qualified effect gate. These are distinct ownership layers. This file is not a replacement for the QPS owner ledger, the scale-dock hash journal, or GitHub-native review and checks.

## Implementation
* watch_qps_edge.py accepts only an existing watch_decision.fold public terminal candidate and a QPS-private-owner HMAC-signed, opaque child/dependency/receipt attestation. Rejects unsupported fields, missing owner key, invalid signature, mismatched exact SHA/run/job/attempt/clock, synthetic-merge admission, raw required CI veto, and missing QPS owner authority.
* Four QPS-impact notification categories: A governed parent recovery and named QPS child; B positive source/instrumentation/denominator-matched coverage with a preceding native event; C named QPS attributable RED/root block or verified unblock; D authenticated MissionControl recovery. This module does not confer merge, root-closure, safety or release approval.
* SQLite WAL append-only native evidence, signed observation ledger, SHA256 audit chain, per-child causal-root state and single-claim PENDING -> CLAIMED -> ACKED outbox. Twelve native failures can be recorded while one unresolved root queues only one notification.
* No GitHub, ChatGPT or messaging provider calls; no automated dispatch, delivery, worker launch, schedule, private QPS identifiers, physical originals, or source-data publication.

## Owner trust boundary
QPS_OWNER_PROOF_KEY_HEX must be a hex-encoded 32+ byte secret provisioned only by an authorized QPS owner runtime, never committed/logged. Before signing, the independent owner-side process must verify actual native source run/job/attempt, QPS child/RTM authority, effective ruleset, eligible human review, security and blocked RED canary. The public consumer can verify signature integrity and owner-key possession, not independently re-authenticate native GitHub or engineering source authority.

Three private identifiers become opaque owner-secret-derived 64-hex tokens outside this repo: child_token, dependency_token and receipt_token. Never export raw QPS issue numbers, PRs, RTM atoms or vendor originals. #881 public source allowlist and #882 source SHA-chain validation must run first. Missing proof => HOLD/UNKNOWN.

The signed attestation exact fields are schema, class, effect, event_key, source_sha, run_id, attempt, job_id, completed_at, issued_at, event_sha256, candidate_sha256, baseline_sha256, child_token, dependency_token, receipt_token, checks. Checks include verified native/owner claims, **source_cohort_complete** (owner-side confirmation that no earlier eligible native row is missing), QPS native, security, required checks, independent review, last-push approval, stale dismissal, review thread resolution, current-base proof, blocked RED canary, matched coverage and MissionControl authentication.

Proof envelope consists of attestation and signature (lowercase HMAC-SHA256). Sign the canonical ASCII JSON of attestation with sorted keys, no whitespace. event_sha256 must equal SHA256 of the exact canonical full native event and candidate_sha256 must equal SHA256 of the exact canonical full candidate object; changing the native result/required checks, event classification or delta after signing is rejected. Every coverage axis must be nondecreasing (and at least one increase) before Class B may qualify. Class B additionally requires an exact preceding native event whose SHA256 matches baseline_sha256; both source blobs and statement/branch scope denominators must agree. The predecessor **must already be in the local immutable native ledger and be the immediately prior recorded event in the same lane**. No Class B outbox entry is permitted without that lineage and an owner-signed source_cohort_complete assertion. Signed completeness is conditional on the private owner independently authenticating the complete eligible cohort; the public ledger alone cannot prove that an unreachable API omitted no events.

## Offline CLI
First authenticate source, obtain a QPS private owner attestation from a separate trusted runtime, and provision QPS_OWNER_PROOF_KEY_HEX securely. Default dry run never persists state:

    python mission-control/gogreen/watch_qps_edge.py --event public-terminal.json --candidate public-transition.json --proof owner-attestation.json

To persist a qualified event locally only:

    python mission-control/gogreen/watch_qps_edge.py --event public-terminal.json --candidate public-transition.json --proof owner-attestation.json --baseline previous-terminal.json --record --database /protected/local/qps-watch-edge.db

The baseline is mandatory only for class B. This queues an opaque local notification; it does not send.

An authorized delivery adapter must claim() exactly once, send notification_id as a provider idempotency key if supported, then acknowledge() with the external provider receipt digest. After CLAIMED do not automatically resend on crash: reconcile provider receipt first. A local at-most-once claim is NOT proof of exactly-once external delivery. Provider integration remains separate.

The SQLite audit chain is append-only under the application contract, not protected against a malicious host administrator. On each qualified record/claim/ack, the verifier checks the audit chain and **replays native observations, signed receipt transitions, causal-root state and outbox pending/claimed/acked state**, rejecting swapped/deleted payloads or forged acknowledged delivery before they can be used. For rollback/truncation detection, keep the returned last_audit_sha256 in an independently trusted owner-controlled anchor and on restart use verify(db, key, expected_root=<trusted previous root>). Without that independent root, a plausible but truncated local chain could pass internal integrity verification. Never treat local hashes as external provider delivery or QPS engineering acceptance.

## Offline QA
    python -m unittest discover -s mission-control/gogreen/tests -p 'test_watch_qps_edge.py' -v
    python -m unittest discover -s mission-control/gogreen/tests -q

Negative tests: invalid signature, private fields, raw required-CI RED under signed green, missing review, stale source, synthetic merge admission, changed coverage denominator/blob, absent comparator, 12 recurring native root observations, BLOCK->UNBLOCK->BLOCK, reverse chronology, restart replay, audit tampering and single-use delivery claim.

Still UNKNOWN: real protected QPS owner signer, authenticated six-repo adapter, eligible human review, actual RED merge canary, provider messaging and current owner acceptance. MERGE_ADMISSION=HOLD; ENGINEERING_CREDIT_DELTA=0; AUTHORITY_TRANSFER=false. No real user notification or QPS release is claimed.
