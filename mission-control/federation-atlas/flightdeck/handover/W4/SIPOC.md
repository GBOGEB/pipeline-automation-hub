# MissionControl W4 — SIPOC / inputs and output paths

| Supplier | Input | Process / owner | Controlled output | Consumer / admission |
|---|---|---|---|---|
| User / sanitized checkpoint | Proposed W4 intent (no raw transcript, unknown timestamps) | Golden Thread S0–S3 hash-verified append | `session_ledger.json`, derived review HTML/DAG | MissionControl #153; S4 native required |
| GitHub MissionControl | W1/W2 source, W3 workflow + schema, W4 disjoint corrections | Atlas + EVERRED native test gates | W4 CI run/job/attempt, Atlas artifact | Repo owner / effective ruleset |
| GOGREEN fleet | Six repo source identities, 42 eligible typed cells | Read-only census and dedup | 36 individually traceable observation leaves / 5 anchors | Six repo scouts + root owners |
| gg_MATH → CODEX → ABACUS | Authenticated exact-source native H1/H2/H3 receipts | Semantic/provenance challenge replay | Source-bound candidate, debugger/LDAB links | QPS child authority only |
| QPS / corporate doc manager | Approved raw binaries, source hashes and OCD/ADR SSOT | Rebuild L3 HTML/XLSX/DOCX/PPTX/PDF | Rendered review copies with QA receipt | Engineering and document owners (DEFER/HOLD) |
| Existing Pages publisher | Protected-main admitted static source and manifest | Publish through one approved pipeline | Hosted HTML + served hash readback | User/owner review portal (no authority transfer) |

**User I/O:** user supplies design/evidence/approved source and view preferences, reads HTML/cards, exports local review notes (non-authority). Python CLI executes `preflight`, `build`, `seal`, `verify`; it emits JSON/counts/digests and local static assets, not an authenticated GitHub merge/approval, not a corporate document upload and not a complete ChatGPT hook.