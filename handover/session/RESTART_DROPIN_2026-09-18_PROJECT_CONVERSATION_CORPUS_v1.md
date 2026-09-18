# Restart Drop-in — Project Conversation Corpus Receiver

Continue from repository authority only.

## Read first

1. `GBOGEB/GBOGEB` main
2. `GBOGEB/GBOGEB#11`
3. producer controls:
   - `governance/PROJECT_KNOWLEDGE_MAP_CURRENT_v0.1.yaml`
   - `governance/PROJECT_CONVERSATION_CORPUS_CURRENT_v0.1.yaml`
   - `governance/PROJECT_CONVERSATION_CORPUS_PROOF_20260918_v0.1.yaml`
4. `GBOGEB/pipeline-automation-hub` master
5. this receiver handover
6. QPS GLOB -> SESSION_CLOSE_CURRENT -> QTG_CURRENT before any QPS priority claim

## Burned predicates

- BLOCK regex failure: repaired and closed.
- duplicate-aware mapping: PASS.
- hosted exact-head proof: PASS.
- producer PR #11: merged.
- raw-vs-unique frequency authority: governed.
- privacy rule: raw conversation text not published to public repo by default.

## Current next predicate

Add further exact conversation exports by hash and measure them through the existing producer mapper. Do not inflate semantic frequencies with duplicate copies.
