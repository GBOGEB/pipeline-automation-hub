# Project Conversation Corpus — 3P* + MIP Receiver

**Date:** 2026-09-18  
**Receiver:** `GBOGEB/pipeline-automation-hub`  
**Producer:** `GBOGEB/GBOGEB`  
**Producer PR:** #11  
**Producer merge:** `02c4d6ef5a4aca36a96bbd5f8163f9d45205a30a`  
**Final exact-head proof:** run `35373234111`, job `105691881706`  
**Authority transfer:** false  
**Formal credit delta:** 0

## Consumed producer state

The producer advanced the project knowledge-map lane from a small repository baseline to a privacy-safe, duplicate-aware conversation-corpus model.

Key governed findings:

- 4 physical historical source files were measured.
- 2 unique content objects exist.
- 2 files are duplicates.
- `IMPLEN_1-0509.txt`, `IMPLEN_2-0509.txt`, and `IMPLEN_3-0509.txt` share the same SHA-256 and are byte-identical.
- semantic/project frequency uses the deduplicated `aggregate_unique` view.
- physical ingest/storage volume uses `aggregate_raw`.
- raw conversation text is not committed to the public producer repository.

## 3P*

### Refresh
PASS. Producer main, producer PR #11 and MissionControl master refreshed after producer merge.

### Probe
PASS. The new material change is duplicate-aware conversation-corpus governance; no MissionControl parser copy is required.

### Rank
PASS. Receiver should bind the producer contract and preserve privacy/dedupe semantics rather than duplicate implementation.

### Prepare
PASS. Append-only receiver handover and restart drop-in created.

### Prove
PASS. Producer exact-head hosted run `35373234111` completed SUCCESS with 11 executed steps; unit tests and controlled repository corpus mapping passed.

### Commit
PASS on producer merge `02c4d6ef5a4aca36a96bbd5f8163f9d45205a30a`. Receiver commit/merge is the only remaining local action.

## MIP

### Modernize
PASS. Project conversation metrics are now governed by exact source hashes and duplicate-aware aggregation.

### Innovate
PASS. A single corpus can expose two valid views without conflation:
- raw physical ingest volume;
- unique semantic frequency.

### Perpetuate
PASS_PENDING_RECEIVER_MERGE. MissionControl now has a restart-discoverable receipt for the producer contract.

## Non-compensation

- Corpus frequency does not grant engineering/compliance/acceptance credit.
- Duplicate removal is semantic normalization, not source deletion.
- Raw source text remains outside this public receiver.
- MissionControl does not become the parser/source authority.
- This lane does not alter QPS GLOB, QTG_CURRENT, #923 or any other independent gate.

## Next predicate

Continue expanding the exact conversation corpus by source hash, preserving:
1. explicit coverage;
2. byte identity;
3. raw-vs-unique separation;
4. no raw public publication without explicit user direction.
