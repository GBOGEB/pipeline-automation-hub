# Full recursive hook — existing Golden Thread, not a new shadow controller

## Immutable parent + next sanitized intent

The parent is the existing [Session Hook implementation](https://github.com/GBOGEB/pipeline-automation-hub/blob/f931e443cafae8b286b149ae4331a0326298730a/mission-control/golden-thread/session_hook/session_hook.py) and [Golden Thread v1](https://github.com/GBOGEB/pipeline-automation-hub/blob/f931e443cafae8b286b149ae4331a0326298730a/mission-control/golden-thread/golden_thread.py) merged by PR #540. The existing `SESSION_INTAKE_V1.json` holds only two **manually reconstructed** intents, IDs `CP-SESSION-20261015-001/002`, original turn IDs and timestamps NULL. Proposed new W4 ID `CP-SESSION-20261015-003` references its earlier parent; it is *not* automatically appended or native-qualified.

After retrieving the **real prior session_ledger.json**, create a schema-compatible sanitized batch (not a fabricated transcript) and run:

```bash
# Repo clone, exact head after permitted merge; keep prior ledger unchanged.
python mission-control/golden-thread/golden_thread.py verify /path/to/previous/session_ledger.json
python mission-control/golden-thread/session_hook/session_hook.py \
  --input /path/to/approved/W4_SANITIZED_INTAKE.json \
  --previous-ledger /path/to/previous/session_ledger.json \
  --source-sha "$(git rev-parse HEAD)" \
  --out /tmp/code-purple-w4-hook
python mission-control/golden-thread/golden_thread.py verify /tmp/code-purple-w4-hook/session_ledger.json
```

Validate all old event digests equal the new prefix; detect duplicate intent IDs, unauthorized future parents, raw chat/secrets, missing refs and backdated timestamps; add native receipt only from terminal external action. The golden-thread code hashes the event log and replays owner projections. `DROPIN` and this W4 archive do *not* substitute for prior ledger verification.

## Recursive algorithm

1. **READ / Freeze:** parse previous ZIP+manifest, verify SHA chain and attached Git exact heads; fail if absent or tampered.
2. **RECONCILE:** identify source delta, previous first-red roots, duplicate symptom IDs, completed versus open goals, new user intent.
3. **CLASSIFY / SIPOC:** map each intent → source, owner, input, output, proof, consumer, and noncompensating HOLDs.
4. **PREREGISTER:** write expected gate outcomes and test denominators *before* next run (never edit predictions after observation).
5. **EXECUTE:** perform smallest disjoint, source-owned slice; run local tests, then owner-allowed native exact-head CI; track run/job/attempt.
6. **VERIFY:** require original artifact bytes, internal source SHA, native tests, policy/approval; distinguish IMPLEMENTED / VERIFIED / ROOT_RESOLVED / ADMITTED.
7. **PROJECT:** generate new HTML/Mermaid/Markdown/Office PDFs from same SSOT; outputs carry `source_sha256`, binary SHA, QoD and generated status.
8. **APPEND:** add measured pulse to new `state/` and forecast score, produce a new content-addressed ZIP with *this W4 ZIP as byte-identical parent*.
9. **CONTROL:** source-matched exact-main recensus and independently observed recurrence before closing root; pass new handover to next session and repeat.

Never loop the same execution DAG back into itself: dashed feedback is a next-pulse edge. QPS owner `DEFER` remains even if local dashboards and native unit tests PASS.