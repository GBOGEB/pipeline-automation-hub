# CODE PURPLE — Recursive conversation → action hook, bounded pilot v1

**Owner:** MissionControl Golden Thread, existing [#153](https://github.com/GBOGEB/pipeline-automation-hub/issues/153). The adapter does **not** create a second canonical BD/REX log, QPS SSOT, or GitHub PR admission controller.

## Scope and consent boundary

A ChatGPT chat is an evolving sequence of user requests, clarifications and decisions. This adapter converts **explicitly supplied, sanitized, manually recorded** intent events to the already implemented Golden Thread v1 event vocabulary. It does not access ChatGPT internal message IDs, transcript export, hooks, websocket events, user account, hidden reasoning or automatic notifications.

The session_alias is a pseudonym, **not an actual ChatGPT conversation ID**. Original message IDs and exact source timestamps are null/UNKNOWN until independently supplied. The capture checkpoint is when an operator writes a summary, **not** evidence of when the earlier utterance occurred.

The QPS child-owned triage/code_purple/evolutionary_v1/INTENT_EVENTS.json, CODEX docs/handover/chat_to_github_prompt_sequence.md, existing MissionControl Golden Thread, #153 and BD #85 remain authoritative in their respective lanes.

## Contract: intent, decision, action and evidence

| Layer | Record | Meaning / gate |
|---|---|---|
| S0 | User message in ChatGPT | Originating instruction; cannot be assumed machine-accessible |
| S1 | Sanitized SESSION_INTAKE_V1.json | Operator-attested reconstructed intent; timestamp/message ID UNBOUND |
| S2 | OBSERVED, CLASSIFIED, ATTACHED_TO_ROOT | Canonical Golden Thread v1 hash-chain event proposal |
| S3 | WORK_ORDER_CREATED, NON_COMPENSATING_GATE_SET | Existing repo/issue owner, actionable work and explicit HOLD |
| S4 | Native GitHub commits / run / job / attempts | Separately obtained real technical evidence; not produced by user intent |
| S5 | Independent consumer replay | Actually downloaded bytes and hashes, if/when attached by a qualified producer |
| S6 | Owner ACCEPT/REJECT/DEFER and independent approval | Never inferred from user chat, workflow PASS, merge occurrence or JSON projection |

A user follow-up is REFINES_WITHOUT_SUPERSEDING unless the user explicitly revokes the previous request. The adapter puts this relation in a CLASSIFIED payload, **not** a false SUPERSEDED_BY canonical event.

A source summary never creates native EVIDENCE_ADDED or CONTROL_PROMOTED. Those require a separate qualified producer and real receipt.

## Execution / recursive logic

Capture new sanitized intent → verify ancestor and owner → compile canonical Golden Thread v1 events → seal append-only hash chain → rebuild projection → generate HTML/JSON/Mermaid/manifest → verify native producer → hand off blocked actions to existing owner → next user intent.

Use the same ledger at the next checkpoint:

~~~sh
python mission-control/golden-thread/session_hook/session_hook.py \
  --input mission-control/golden-thread/session_hook/SESSION_INTAKE_V1.json \
  --source-sha "$(git rev-parse HEAD)" \
  --out /tmp/code-purple-session-hook

python mission-control/golden-thread/golden_thread.py verify \
  /tmp/code-purple-session-hook/session_ledger.json

# For a genuinely NEW intent batch only:
python mission-control/golden-thread/session_hook/session_hook.py \
  --input NEXT_SANITIZED_INTENT_BATCH.json \
  --previous-ledger /tmp/code-purple-session-hook/session_ledger.json \
  --source-sha "$(git rev-parse HEAD)" \
  --out /tmp/code-purple-next-hook
~~~

Appending an already-observed intent ID fails closed. Historical Golden Thread events are not rewritten and their digest prefix must remain unchanged. A re-indexed logical N label never rewrites SHA/UTC/causality.

## SIPOC

| Supplier | Input | Process | Output | Consumer |
|---|---|---|---|---|
| User / manually curated session checkpoint | Sanitized summary + explicit owner, parent and unknown provenance | Validate → Golden Thread event proposal → SHA seal → replay | Traceable intent/action ledger and derived HTML/DAG | MissionControl #153 |
| CODEX KEB / ABACUS DOW / QPS | Independent exact-source native receipts | Owner verification, consumer byte replay and admission | Separate ACCEPT/REJECT/DEFER evidence | Existing repository owner and human reviewer |

## Single-pulse execution DAG

~~~mermaid
flowchart TD
  U["New user intent"] --> S["Manual sanitized capture"]
  S --> V{"Schema/privacy/owner checks"}
  V -->|"invalid"| HOLD["HOLD / correct source"]
  V -->|"valid"| G["Golden Thread v1 append-only event proposal"]
  G --> D["Deterministic projection and HTML / Mermaid"]
  D --> T["Native exact-head testflight"]
  T --> Q{"Qualified evidence/owner gate?"}
  Q -->|"no"| HOLD
  Q -->|"yes"| E["Action/recipient receipt in existing owner"]
  E --> N["Next logical user pulse"]
  HOLD -.->|"next explicit user input"| N
  N -.-> U
~~~

The feedback loop is *between* pulses. Remove the dashed edges for a bounded executable DAG.

## Metrics, decisions and versioning

The adapter measures captured_intents, owned_work_orders, unbound_turn_ids, proposed_actions, independently_native_verified_actions and unresolved_authority_gates distinctly.

- No invented exact-source conversation URL, time, original message ID or measured ChatGPT latency.
- No raw conversation transcript or secrets committed to public source control.
- A browser/dashboard render is L3 presentation QA only, not QPS engineering truth.
- This pilot input contains **two** known sanitized intents reconstructed from the current chat; it is **not** a complete chat export.
- Forecast in the JSON was committed **before implementation**, with actual outcome still null. Score it after terminal CI separately.
- SESSION_INTAKE_V1.json is a **pilot input fixture**, not an automatically updated always-on chat integration.
- Actual external GitHub writes remain governed by existing side_effect_receipts.py.

For fuller lossless provenance, the user must supply an authorized export with stable message identifiers/timestamps and explicit disclosure scope. Do not backfill unknown original chat metadata from the capture checkpoint.

## Definition of verification

1. Valid canonical Golden Thread seal, verify, replay and root expansion.
2. Cross-event root and action lineage recoverable; stable event digest prefix after append.
3. 19 negative/behavior tests pass at exact Git SHA and generated artifact digest checks pass.
4. HTML readable, searchable, mobile-safe; derived from same SHA-bound source.
5. Native CI and GitHub PR admission are separate; HOLD until required checks and eligible review.
